#!/bin/bash
# STAWN QCMS for iPhone and iPad - build check, open in Xcode, or archive + upload to TestFlight.
#   ./BUILD_STAWN_QCMS_iOS.command              -> generate project, build check (simulator), open Xcode
#   ./BUILD_STAWN_QCMS_iOS.command device       -> build + install on the iPhone / iPad connected by cable; registers the device
#                                                  with your Apple Developer team automatically (fixes "Your team has no devices")
#   ./BUILD_STAWN_QCMS_iOS.command testflight   -> archive + upload to App Store Connect (TestFlight)
#   ./BUILD_STAWN_QCMS_iOS.command adhoc        -> archive + export a signed .ipa to ~/Downloads (registered devices)
#   ./BUILD_STAWN_QCMS_iOS.command free         -> FREE Apple ID (no paid membership): install on your own iPhone / iPad
#                                                  by cable; app must be re-installed every 7 days; no push notifications
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
VERSION="1.4.0"
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
if [ "$MODE" = "free" ]; then
  say "FREE APPLE ID BUILD (Personal Team)"
  PTEAM="${STAWN_PERSONAL_TEAM_ID:-}"
  [ -z "$PTEAM" ] && [ -f "$HOME/.stawn_apple_personal_team_id" ] && PTEAM="$(tr -d ' \n\r' < "$HOME/.stawn_apple_personal_team_id")"
  if [ -z "$PTEAM" ]; then
    # Xcode > Settings > Accounts stores the free "Personal Team" with isFreeProvisioningTeam = 1
    PTEAM="$(defaults read com.apple.dt.Xcode IDEProvisioningTeams 2>/dev/null | tr -d '\n' | sed -n 's/.*isFreeProvisioningTeam = 1;[^}]*teamID = \([A-Z0-9]\{10\}\).*/\1/p' | head -1)"
  fi
  if [ -z "$PTEAM" ]; then
    PTEAM="$(defaults read com.apple.dt.Xcode IDEProvisioningTeams 2>/dev/null | tr -d '\n' | sed -n 's/.*teamID = \([A-Z0-9]\{10\}\);[^}]*isFreeProvisioningTeam = 1.*/\1/p' | head -1)"
  fi
  if [ -n "$PTEAM" ]; then echo "$PTEAM" > "$HOME/.stawn_apple_personal_team_id"; echo "Personal Team: $PTEAM"; else
    echo "Personal Team not found yet: Xcode > Settings > Accounts > + > Apple ID, sign in with your normal Apple ID, then run this again."
    echo "(You can also pick 'Your Name (Personal Team)' in Signing & Capabilities after Xcode opens.)"
  fi
  STAWN_PERSONAL_TEAM=1 python3 make_project.py "$VERSION" "$BUILD_NO" "$PTEAM" || exit 1
  open STAWNQCMS.xcodeproj
  echo
  echo "Install on your iPhone / iPad with a FREE Apple ID:"
  echo "  1. Connect the iPhone / iPad by cable, unlock it, tap 'Trust This Computer'."
  echo "  2. On the device: Settings > Privacy & Security > Developer Mode > On (it restarts)."
  echo "  3. In Xcode choose the device at the top, then press Run (the play button)."
  echo "  4. First launch on the device: Settings > General > VPN & Device Management > your Apple ID > Trust."
  echo "Limits of a free Apple ID: the app stops opening after 7 days - connect and press Run again;"
  echo "max 3 apps; no push notifications (the in-app bell and inbox still work)."
  exit 0
fi
# ---- Apple Team ID (R41b): env > PAID team in Xcode > Settings > Accounts > ~/.stawn_apple_team_id > Keychain certificate ----
# A free "Personal Team" (your own name) cannot sign Push Notifications, so it is never used for this app.
TEAM_ID="${STAWN_APPLE_TEAM_ID:-}"
[ -z "$TEAM_ID" ] && TEAM_ID="$(python3 xcode_teams.py paid 2>/dev/null)"
if [ -z "$TEAM_ID" ] && [ -f "$HOME/.stawn_apple_team_id" ]; then TEAM_ID="$(tr -d ' \n\r' < "$HOME/.stawn_apple_team_id")"; fi
if [ -z "$TEAM_ID" ]; then
  for CN in "Apple Distribution" "Apple Development" "iPhone Distribution" "iPhone Developer"; do
    for T in $(security find-certificate -a -c "$CN" -p 2>/dev/null | openssl x509 -noout -subject 2>/dev/null | sed -n 's/.*OU *= *\([A-Z0-9]\{10\}\).*/\1/p'); do
      python3 xcode_teams.py isfree "$T" || { TEAM_ID="$T"; break; }
    done
    [ -n "$TEAM_ID" ] && break
  done
fi
if [ -n "$TEAM_ID" ] && python3 xcode_teams.py isfree "$TEAM_ID"; then
  echo "Team $TEAM_ID is your free Personal Team - it cannot sign this app (Push Notifications). Ignoring it."
  TEAM_ID=""
fi
if [ -z "$TEAM_ID" ]; then
  echo "Teams known to Xcode:"; python3 xcode_teams.py list | sed 's/^/  /'
fi
if [ -z "$TEAM_ID" ] && [ -t 0 ] && [ "$MODE" != "check" ]; then
  echo "Enter the Team ID of STAWN PRECISION PRIVATE LIMITED (developer.apple.com > Account > Membership details, 10 characters)."
  read -r -p "Apple Team ID (or press Enter to skip): " TEAM_ID
fi
if [ -n "$TEAM_ID" ]; then
  echo "$TEAM_ID" > "$HOME/.stawn_apple_team_id"
  echo "Apple Team ID: $TEAM_ID (saved in ~/.stawn_apple_team_id)"
fi
python3 make_project.py "$VERSION" "$BUILD_NO" "$TEAM_ID" || exit 1

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
    echo "Signing for your own iPhone / iPad (fixes 'Your team has no devices' / 'No profiles were found'):"
    echo "  1. Xcode > Settings > Accounts: add your Apple ID (Team shows there)."
    echo "  2. Connect the iPhone / iPad with a cable, unlock it, tap 'Trust This Computer'."
    echo "  3. iPhone: Settings > Privacy & Security > Developer Mode > On (restart when asked)."
    echo "  4. In Xcode pick the iPhone / iPad at the top (not 'Any iOS Device') - Xcode registers it."
    echo "  5. Signing & Capabilities > Try Again, then press Run."
    echo "Or let this script do it:  ./BUILD_STAWN_QCMS_iOS.command device"
    echo "No device at hand? Use TestFlight - no device registration needed:"
    echo "  ./BUILD_STAWN_QCMS_iOS.command testflight"
    ;;
  device)
    [ -n "$TEAM_ID" ] || { echo "Set your Apple Team ID once:  echo YOURTEAMID > ~/.stawn_apple_team_id   (developer.apple.com > Account > Membership details)"; exit 1; }
    say "INSTALL ON THE CONNECTED iPHONE / iPAD (team $TEAM_ID)"
    DEV_JSON="$(mktemp -t stawn_devices).json"
    xcrun devicectl list devices --json-output "$DEV_JSON" >/dev/null 2>&1 || true
    UDID="${STAWN_DEVICE_UDID:-}"
    if [ -z "$UDID" ]; then
      UDID="$(python3 -c 'import json,sys
try: devices = json.load(open(sys.argv[1])).get("result", {}).get("devices", [])
except Exception: devices = []
for d in devices:
    hw = d.get("hardwareProperties", {})
    if hw.get("platform") == "iOS" and hw.get("udid"):
        print(hw["udid"]); break' "$DEV_JSON")"
    fi
    if [ -z "$UDID" ]; then
      echo "No iPhone / iPad found. Connect it by cable, unlock it, tap 'Trust This Computer',"
      echo "turn on Settings > Privacy & Security > Developer Mode (it restarts), then run this again."
      exit 1
    fi
    echo "Device: $UDID"
    rm -rf build && mkdir -p build
    # -allowProvisioningDeviceRegistration adds this iPhone / iPad to the team and creates the development profile.
    xcodebuild -project STAWNQCMS.xcodeproj -scheme STAWNQCMS -configuration Debug -destination "id=$UDID" \
      -derivedDataPath build/dd DEVELOPMENT_TEAM="$TEAM_ID" -allowProvisioningUpdates -allowProvisioningDeviceRegistration build > "$LOG" 2>&1 \
      || { grep -E "error:" "$LOG" | head -40; echo "Build failed - log: $LOG  (send it to Claude)"; exit 1; }
    APP="$(find build/dd/Build/Products -maxdepth 2 -name 'STAWN QCMS.app' -print -quit)"
    xcrun devicectl device install app --device "$UDID" "$APP" >> "$LOG" 2>&1 \
      || { tail -20 "$LOG"; echo "Install failed - log: $LOG"; exit 1; }
    echo "Installed STAWN QCMS v$VERSION on the device. First launch: Settings > General > VPN & Device Management is NOT needed for a paid team."
    echo "Signing in Xcode now works too: pick this device at the top (not 'Any iOS Device') and press Run."
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
  *) echo "Usage: $0 [check|device|testflight|adhoc|free]"; exit 1 ;;
esac
