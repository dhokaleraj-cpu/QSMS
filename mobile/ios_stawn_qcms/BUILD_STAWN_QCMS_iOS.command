#!/bin/bash
# STAWN QCMS for iPhone and iPad - build check, open in Xcode, or archive + upload to TestFlight.
#   ./BUILD_STAWN_QCMS_iOS.command              -> generate project, build check (simulator), open Xcode
#   ./BUILD_STAWN_QCMS_iOS.command testflight   -> archive + upload to App Store Connect (TestFlight)
#   ./BUILD_STAWN_QCMS_iOS.command adhoc        -> archive + export a signed .ipa to ~/Downloads (registered devices)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
VERSION="1.0.0"
BUILD_NO="$(date +%Y%m%d%H%M)"
MODE="${1:-check}"
LOG="$HOME/Downloads/STAWN_QCMS_iOS_build_log.txt"
say() { printf '\n============================================================\n %s\n============================================================\n' "$1"; }

say "STAWN QCMS iPhone / iPad app v$VERSION ($BUILD_NO)"
if ! xcodebuild -version >/dev/null 2>&1; then
  echo "Xcode is not selected. Run once:  sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"
  echo "(Install Xcode from the Mac App Store first if needed.)"
  exit 1
fi
xcodebuild -version
python3 make_project.py "$VERSION" "$BUILD_NO" || exit 1

TEAM_ID="${STAWN_APPLE_TEAM_ID:-}"
if [ -z "$TEAM_ID" ] && [ -f "$HOME/.stawn_apple_team_id" ]; then TEAM_ID="$(cat "$HOME/.stawn_apple_team_id")"; fi

case "$MODE" in
  check)
    say "BUILD CHECK (iOS Simulator, no signing)"
    if xcodebuild -project STAWNQCMS.xcodeproj -scheme STAWNQCMS -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' \
         -configuration Debug CODE_SIGNING_ALLOWED=NO build > "$LOG" 2>&1; then
      echo "iOS app build: OK"
    else
      echo "iOS app build FAILED. Errors:"
      grep -E "error:" "$LOG" | head -40
      echo "Full log: $LOG  (send it to Claude)"
    fi
    open STAWNQCMS.xcodeproj
    echo
    echo "In Xcode: target STAWNQCMS > Signing & Capabilities > Team = your Apple Developer team."
    echo "Connect the iPhone / iPad, pick it at the top and press Run (or Product > Archive for TestFlight)."
    ;;
  testflight|adhoc)
    [ -n "$TEAM_ID" ] || { echo "Set your Apple Team ID once:  echo YOURTEAMID > ~/.stawn_apple_team_id   (developer.apple.com > Membership)"; exit 1; }
    say "ARCHIVE (Release, team $TEAM_ID)"
    rm -rf build && mkdir -p build
    xcodebuild -project STAWNQCMS.xcodeproj -scheme STAWNQCMS -configuration Release -destination 'generic/platform=iOS' \
      DEVELOPMENT_TEAM="$TEAM_ID" -allowProvisioningUpdates archive -archivePath build/STAWNQCMS.xcarchive > "$LOG" 2>&1 \
      || { grep -E "error:" "$LOG" | head -40; echo "Archive failed - log: $LOG"; exit 1; }
    METHOD="app-store"; DEST="upload"
    if [ "$MODE" = "adhoc" ]; then METHOD="ad-hoc"; DEST="export"; fi
    cat > build/ExportOptions.plist <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>method</key><string>${METHOD}</string>
<key>destination</key><string>${DEST}</string>
<key>signingStyle</key><string>automatic</string>
<key>teamID</key><string>${TEAM_ID}</string>
<key>manageAppVersionAndBuildNumber</key><false/>
</dict></plist>
PLIST
    say "EXPORT ($METHOD / $DEST)"
    xcodebuild -exportArchive -archivePath build/STAWNQCMS.xcarchive -exportPath build/export -exportOptionsPlist build/ExportOptions.plist \
      -allowProvisioningUpdates >> "$LOG" 2>&1 || { tail -30 "$LOG"; echo "Export failed - log: $LOG"; exit 1; }
    if [ "$MODE" = "adhoc" ]; then
      IPA="$(find build/export -name '*.ipa' -print -quit)"
      cp "$IPA" "$HOME/Downloads/STAWN_QCMS_iOS_v${VERSION}.ipa" && echo "IPA: ~/Downloads/STAWN_QCMS_iOS_v${VERSION}.ipa"
    else
      echo "Uploaded to App Store Connect. In 10-30 minutes it appears in TestFlight (appstoreconnect.apple.com > Apps > STAWN QCMS > TestFlight)."
    fi
    ;;
  *) echo "Usage: $0 [check|testflight|adhoc]"; exit 1 ;;
esac
