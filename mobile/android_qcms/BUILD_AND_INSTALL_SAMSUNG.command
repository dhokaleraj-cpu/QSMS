#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
GRADLE_VERSION="8.9"
BOOT="$HOME/.gradle/qcms-bootstrap"
GRADLE_HOME="$BOOT/gradle-$GRADLE_VERSION"
PACKAGE="com.fourstar.qcms.test"
ACTIVITY="com.fourstar.qcms.MainActivity"

say(){ printf '\n=== %s ===\n' "$1"; }
fail(){ printf '\nERROR: %s\n' "$1" >&2; exit 1; }

MOBILE_VERSION="$(sed -n "s/^[[:space:]]*versionName[[:space:]]*['\"]\([^'\"]*\)['\"].*/\1/p" "$HERE/app/build.gradle" | head -1)"
MOBILE_CODE="$(sed -n "s/^[[:space:]]*versionCode[[:space:]]*\([0-9][0-9]*\).*/\1/p" "$HERE/app/build.gradle" | head -1)"
[ -n "$MOBILE_VERSION" ] || fail "Unable to read Android versionName from app/build.gradle."
[ -n "$MOBILE_CODE" ] || fail "Unable to read Android versionCode from app/build.gradle."
echo "============================================================"
echo " QCMS Mobile v${MOBILE_VERSION} - Native V1.2 Drawer"
echo "============================================================"
echo "Project : $HERE"
echo "Package : $PACKAGE"
echo "SDK     : $SDK"

grep -Fq 'setText("MENU")' app/src/main/java/com/fourstar/qcms/MainActivity.java || fail "Visible native MENU button missing from source."
grep -Fq 'hamburger.setOnClickListener(v -> openDrawer())' app/src/main/java/com/fourstar/qcms/MainActivity.java || fail "Native MENU click binding missing."
grep -Fq 'drawerLayer.setVisibility(View.VISIBLE)' app/src/main/java/com/fourstar/qcms/MainActivity.java || fail "Native drawer open implementation missing."
if grep -Fq 'showStableStreamlitBrowser' app/src/main/java/com/fourstar/qcms/MainActivity.java; then fail "Legacy dual navigation architecture is still present."; fi

mkdir -p "$SDK"
find_android_cli(){
  local candidate
  for candidate in "$HOME/.android/cli/bin/android" "$HOME/.android/cli/latest/bin/android" "/opt/homebrew/bin/android" "/usr/local/bin/android"; do
    [ -x "$candidate" ] && { printf '%s\n' "$candidate"; return 0; }
  done
  command -v android 2>/dev/null || true
}
find_sdkmanager(){
  local candidate
  for candidate in "$SDK/cmdline-tools/latest/bin/sdkmanager" "$HOME/.android/cli/bin/sdkmanager" "/opt/homebrew/bin/sdkmanager" "/usr/local/bin/sdkmanager"; do
    [ -x "$candidate" ] && { printf '%s\n' "$candidate"; return 0; }
  done
  command -v sdkmanager 2>/dev/null || true
}
ANDROID_CLI="$(find_android_cli)"
SDKMANAGER="$(find_sdkmanager)"
if [ -z "$ANDROID_CLI" ] && [ -z "$SDKMANAGER" ]; then
  say "ANDROID SDK / CLI BOOTSTRAP"
  echo "Android development tools were not found. QCMS will install Google's official Android CLI for this Mac user."
  ARCH="$(uname -m)"
  if [ "$ARCH" = "arm64" ]; then CLI_ARCH="darwin_arm64"; else CLI_ARCH="darwin_x86_64"; fi
  INSTALLER_URL="https://dl.google.com/android/cli/latest/${CLI_ARCH}/install.sh"
  curl -fsSL --retry 3 "$INSTALLER_URL" | bash
  export PATH="$HOME/.android/cli/bin:$HOME/.android/cli/latest/bin:$PATH"
  ANDROID_CLI="$(find_android_cli)"
  SDKMANAGER="$(find_sdkmanager)"
fi

say "ANDROID PLATFORM 35 / PLATFORM-TOOLS"
if [ -n "$ANDROID_CLI" ]; then
  echo "Using Android CLI: $ANDROID_CLI"
  "$ANDROID_CLI" --sdk="$SDK" sdk install platforms/android-35 build-tools/35.0.0 platform-tools
elif [ -n "$SDKMANAGER" ]; then
  echo "Using sdkmanager: $SDKMANAGER"
  yes | "$SDKMANAGER" --sdk_root="$SDK" --licenses >/dev/null 2>&1 || true
  "$SDKMANAGER" --sdk_root="$SDK" "platform-tools" "platforms;android-35" "build-tools;35.0.0"
else
  fail "Android CLI/SDK manager could not be installed or found."
fi
ADB="$SDK/platform-tools/adb"
[ -x "$ADB" ] || fail "adb was not installed at $ADB"

command -v java >/dev/null 2>&1 || fail "Java 17 is required but java is not available."
JAVA_MAJOR="$(java -version 2>&1 | awk -F'[\".]' '/version/ {print $2; exit}')"
[ -z "$JAVA_MAJOR" ] || [ "$JAVA_MAJOR" -ge 17 ] || fail "Java 17 or newer is required. Current Java major: $JAVA_MAJOR"

mkdir -p "$BOOT"
if [ ! -x "$GRADLE_HOME/bin/gradle" ]; then
  ZIP="$BOOT/gradle-$GRADLE_VERSION-bin.zip"
  say "GRADLE $GRADLE_VERSION"
  curl -L --fail --retry 3 -o "$ZIP" "https://services.gradle.org/distributions/gradle-$GRADLE_VERSION-bin.zip"
  rm -rf "$GRADLE_HOME"
  unzip -q "$ZIP" -d "$BOOT"
fi

printf 'sdk.dir=%s\n' "$SDK" > local.properties
say "BUILD DEBUG APK"
"$GRADLE_HOME/bin/gradle" --no-daemon clean :app:assembleDebug :app:lintDebug
APK="$HERE/app/build/outputs/apk/debug/app-debug.apk"
[ -f "$APK" ] || fail "APK not produced: $APK"
mkdir -p "$HOME/Downloads"
OUTPUT_APK="$HOME/Downloads/QCMS_Mobile_v${MOBILE_VERSION}_TEST.apk"
cp -p "$APK" "$OUTPUT_APK"

SIG_REPORT="$OUTPUT_APK.signature.txt"
set +e
"$SDK/build-tools/35.0.0/apksigner" verify --verbose --print-certs "$OUTPUT_APK" | tee "$SIG_REPORT"
APKSIGN_RC=${PIPESTATUS[0]}
set -e
[ "$APKSIGN_RC" -eq 0 ] || fail "APK signature verification failed (exit $APKSIGN_RC)."
grep -Fq "Verified using v2 scheme (APK Signature Scheme v2): true" "$SIG_REPORT" || fail "APK Signature Scheme v2 verification is not true."
printf 'APK SIGNATURE: PASS (v2 verified)\n'
"$SDK/build-tools/35.0.0/zipalign" -c -P 16 -v 4 "$OUTPUT_APK" >/dev/null || fail "APK zip alignment verification failed."
shasum -a 256 "$OUTPUT_APK" > "$OUTPUT_APK.sha256"
printf 'APK READY: %s\n' "$OUTPUT_APK"
[ "${QCMS_BUILD_ONLY:-0}" = "1" ] && exit 0

"$ADB" start-server >/dev/null
DEVICES=( $("$ADB" devices | awk 'NR>1 && $2=="device" {print $1}') )
if [ "${#DEVICES[@]}" -eq 0 ]; then
  echo "No authorised Android phone is connected. APK build is complete."
  "$ADB" devices || true
  exit 0
fi
[ "${#DEVICES[@]}" -eq 1 ] || fail "Multiple Android devices are connected. Disconnect all except the Samsung test phone."
DEVICE="${DEVICES[0]}"

say "INSTALL EXACT QCMS TEST PACKAGE TO $DEVICE"
"$ADB" -s "$DEVICE" install -r "$OUTPUT_APK"

say "VERIFY INSTALLED PACKAGE / VERSION"
PKG_INFO="$("$ADB" -s "$DEVICE" shell dumpsys package "$PACKAGE" 2>/dev/null || true)"
echo "$PKG_INFO" | grep -F "versionName=$MOBILE_VERSION" >/dev/null || fail "Installed package versionName is not $MOBILE_VERSION."
echo "$PKG_INFO" | grep -E "versionCode=${MOBILE_CODE}([[:space:]]|$)" >/dev/null || fail "Installed package versionCode is not $MOBILE_CODE."
printf 'Installed package: %s\nAndroid version : %s (code %s)\n' "$PACKAGE" "$MOBILE_VERSION" "$MOBILE_CODE"

if "$ADB" -s "$DEVICE" shell pm list packages | grep -qx 'package:com.fourstar.qcms'; then
  printf '\nNOTE: a legacy package com.fourstar.qcms is also installed. Its icon may look similar.\nThis command will now launch the verified %s package so you can test the correct app.\n' "$PACKAGE"
fi

say "LAUNCH VERIFIED QCMS APP"
"$ADB" -s "$DEVICE" shell am force-stop "$PACKAGE" >/dev/null || true
"$ADB" -s "$DEVICE" shell am start -n "$PACKAGE/$ACTIVITY" >/dev/null
printf '\nSUCCESS: launched QCMS Mobile %s. The maroon top bar must show MENU at the upper-left. Tap MENU to open the native drawer.\n' "$MOBILE_VERSION"
