#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
ADB="$SDK/platform-tools/adb"
SDKMANAGER="$SDK/cmdline-tools/latest/bin/sdkmanager"
GRADLE_VERSION="8.9"
BOOT="$HOME/.gradle/qcms-bootstrap"
GRADLE_HOME="$BOOT/gradle-$GRADLE_VERSION"

echo "============================================================"
echo " QCMS Mobile v0.1.0 - Samsung Android build & install"
echo "============================================================"
echo "Project : $HERE"
echo "SDK     : $SDK"

if [ ! -d "$SDK" ]; then
  echo "ERROR: Android SDK not found at $SDK"
  echo "Install Android Studio once, open SDK Manager, and install Android SDK Platform 35."
  exit 1
fi

if [ -x "$SDKMANAGER" ]; then
  yes | "$SDKMANAGER" --licenses >/dev/null 2>&1 || true
  "$SDKMANAGER" "platform-tools" "platforms;android-35" "build-tools;35.0.0" >/dev/null
fi

if [ ! -x "$ADB" ]; then
  echo "ERROR: adb not found. Install Android SDK Platform-Tools from Android Studio SDK Manager."
  exit 1
fi

mkdir -p "$BOOT"
if [ ! -x "$GRADLE_HOME/bin/gradle" ]; then
  ZIP="$BOOT/gradle-$GRADLE_VERSION-bin.zip"
  echo "Downloading Gradle $GRADLE_VERSION..."
  curl -L --fail --retry 3 -o "$ZIP" "https://services.gradle.org/distributions/gradle-$GRADLE_VERSION-bin.zip"
  rm -rf "$GRADLE_HOME"
  unzip -q "$ZIP" -d "$BOOT"
fi

printf 'sdk.dir=%s\n' "$SDK" > local.properties
"$GRADLE_HOME/bin/gradle" --no-daemon clean :app:assembleDebug
APK="$HERE/app/build/outputs/apk/debug/app-debug.apk"
[ -f "$APK" ] || { echo "ERROR: APK not produced: $APK"; exit 1; }

echo
"$ADB" start-server >/dev/null
DEVICES=( $("$ADB" devices | awk 'NR>1 && $2=="device" {print $1}') )
if [ "${#DEVICES[@]}" -eq 0 ]; then
  echo "APK built successfully: $APK"
  echo "No authorised Samsung device is connected. Enable USB debugging, reconnect, accept the RSA prompt and run this command again."
  exit 0
fi
if [ "${#DEVICES[@]}" -gt 1 ]; then
  echo "Multiple Android devices are connected. Disconnect all except the Samsung test phone and rerun."
  "$ADB" devices
  exit 1
fi
DEVICE="${DEVICES[0]}"
echo "Installing to Android device: $DEVICE"
"$ADB" -s "$DEVICE" install -r "$APK"
echo
echo "SUCCESS: QCMS Mobile installed. Open 'QCMS Mobile' on the Samsung phone and enter the live HTTPS QCMS URL."
