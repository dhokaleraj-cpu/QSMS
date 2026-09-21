#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$ROOT/QCMSMobileIOS.xcodeproj"
SCHEME="QCMSMobileIOS"
ARCHIVE="$ROOT/build/QCMSMobileIOS.xcarchive"
EXPORT="$ROOT/build/export"
TEAM_ID="${QCMS_APPLE_TEAM_ID:-}"

printf '\n============================================================\n QCMS Mobile iPhone/iPad - Build IPA\n============================================================\n'
command -v xcodebuild >/dev/null 2>&1 || { echo "ERROR: Xcode command line tools are not installed. Install Xcode first."; exit 1; }
[ -n "$TEAM_ID" ] || { echo "ERROR: Set your Apple Team ID first:"; echo 'export QCMS_APPLE_TEAM_ID="YOUR_TEAM_ID"'; exit 1; }
mkdir -p "$ROOT/build"
cat > "$ROOT/build/ExportOptions.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>method</key><string>development</string>
<key>signingStyle</key><string>automatic</string>
<key>teamID</key><string>${TEAM_ID}</string>
</dict></plist>
PLIST
xcodebuild -project "$PROJECT" -scheme "$SCHEME" -configuration Release -destination 'generic/platform=iOS' DEVELOPMENT_TEAM="$TEAM_ID" -allowProvisioningUpdates archive -archivePath "$ARCHIVE"
xcodebuild -exportArchive -archivePath "$ARCHIVE" -exportPath "$EXPORT" -exportOptionsPlist "$ROOT/build/ExportOptions.plist" -allowProvisioningUpdates
IPA="$(find "$EXPORT" -maxdepth 1 -name '*.ipa' -print -quit)"
[ -n "$IPA" ] || { echo "ERROR: Xcode completed without an IPA."; exit 1; }
cp "$IPA" "$HOME/Downloads/QCMS_Mobile_iPhone_iPad_v0.1.0.ipa"
echo "IPA ready: $HOME/Downloads/QCMS_Mobile_iPhone_iPad_v0.1.0.ipa"
