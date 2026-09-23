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
[ -n "$MOBILE_VERSION" ] || fail "Unable to read Android versionName."
[ -n "$MOBILE_CODE" ] || fail "Unable to read Android versionCode."

echo "============================================================"
echo " QCMS Mobile v${MOBILE_VERSION} - FIRST APP RECOVERY"
echo "============================================================"
echo "Project : $HERE"
echo "Package : $PACKAGE"
echo "SDK     : $SDK"

grep -Fq 'QCMSClassicShell/1.0.2' app/src/main/java/com/fourstar/qcms/MainActivity.java || fail "Classic first-app user agent missing."
# Inspect executable architecture markers only; comments must never trip this validation.
if grep -Eq '^[[:space:]]*.*setUserAgentString\(.*QCMSMobile/' app/src/main/java/com/fourstar/qcms/MainActivity.java; then fail "Native-wrapper user agent detected."; fi
if grep -Eq '^[[:space:]]*(private|public|protected).*(openDrawer|closeDrawer)\(' app/src/main/java/com/fourstar/qcms/MainActivity.java || grep -Fq '__qcmsNativeNavigate' app/src/main/java/com/fourstar/qcms/MainActivity.java; then fail "Later native route/drawer architecture detected; refusing classic recovery build."; fi

mkdir -p "$SDK"
find_sdkmanager(){
  local candidate
  for candidate in "$SDK/cmdline-tools/latest/bin/sdkmanager" "/opt/homebrew/bin/sdkmanager" "/usr/local/bin/sdkmanager"; do
    [ -x "$candidate" ] && { printf '%s\n' "$candidate"; return 0; }
  done
  command -v sdkmanager 2>/dev/null || true
}
SDKMANAGER="$(find_sdkmanager)"
if [ -z "$SDKMANAGER" ]; then
  say "ANDROID SDK / CLI BOOTSTRAP"
  if command -v brew >/dev/null 2>&1; then
    brew install --cask android-commandlinetools || true
    SDKMANAGER="$(find_sdkmanager)"
  fi
fi
[ -n "$SDKMANAGER" ] || fail "Android sdkmanager not found. Install Android Studio once, then rerun."

say "ANDROID PLATFORM 35 / PLATFORM-TOOLS"
yes | "$SDKMANAGER" --sdk_root="$SDK" --licenses >/dev/null 2>&1 || true
"$SDKMANAGER" --sdk_root="$SDK" "platform-tools" "platforms;android-35" "build-tools;35.0.0"
ADB="$SDK/platform-tools/adb"
[ -x "$ADB" ] || fail "adb was not installed at $ADB"

command -v java >/dev/null 2>&1 || fail "Java 17 is required."
JAVA_MAJOR="$(java -version 2>&1 | awk -F'[\".]' '/version/ {print $2; exit}')"
[ -z "$JAVA_MAJOR" ] || [ "$JAVA_MAJOR" -ge 17 ] || fail "Java 17+ required; current major=$JAVA_MAJOR"

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
OUTPUT_APK="$HOME/Downloads/QCMS_Mobile_FIRST_APP_v${MOBILE_VERSION}_TEST.apk"
cp -p "$APK" "$OUTPUT_APK"

SIG_REPORT="$OUTPUT_APK.signature.txt"
set +e
"$SDK/build-tools/35.0.0/apksigner" verify --verbose --print-certs "$OUTPUT_APK" | tee "$SIG_REPORT"
APKSIGN_RC=${PIPESTATUS[0]}
set -e
[ "$APKSIGN_RC" -eq 0 ] || fail "APK signature verification failed (exit $APKSIGN_RC)."
grep -Fq "Verified using v2 scheme (APK Signature Scheme v2): true" "$SIG_REPORT" || fail "APK Signature Scheme v2 is not true."
"$SDK/build-tools/35.0.0/zipalign" -c -P 16 -v 4 "$OUTPUT_APK" >/dev/null || fail "APK zip alignment verification failed."
shasum -a 256 "$OUTPUT_APK" > "$OUTPUT_APK.sha256"
printf 'APK READY: %s\n' "$OUTPUT_APK"
[ "${QCMS_BUILD_ONLY:-0}" = "1" ] && exit 0

"$ADB" start-server >/dev/null
DEVICES=( $("$ADB" devices | awk 'NR>1 && $2=="device" {print $1}') )
if [ "${#DEVICES[@]}" -eq 0 ]; then
  echo "No authorised Android phone connected. APK build is complete."
  exit 0
fi
[ "${#DEVICES[@]}" -eq 1 ] || fail "Multiple Android devices connected."
DEVICE="${DEVICES[0]}"
say "INSTALL FIRST-APP RECOVERY"
"$ADB" -s "$DEVICE" install -r "$OUTPUT_APK"

say "VERIFY INSTALLED VERSION"
PKG_INFO="$("$ADB" -s "$DEVICE" shell dumpsys package "$PACKAGE" 2>/dev/null || true)"
echo "$PKG_INFO" | grep -F "versionName=$MOBILE_VERSION" >/dev/null || fail "Installed versionName mismatch."
echo "$PKG_INFO" | grep -E "versionCode=${MOBILE_CODE}([[:space:]]|$)" >/dev/null || fail "Installed versionCode mismatch."

say "LAUNCH QCMS FIRST-APP RECOVERY"
"$ADB" -s "$DEVICE" shell am force-stop "$PACKAGE" >/dev/null || true
"$ADB" -s "$DEVICE" shell am start -n "$PACKAGE/$ACTIVITY" >/dev/null
printf '\nSUCCESS: QCMS Mobile %s launched. Navigation is now owned by the QCMS web application itself; there is no Android route drawer.\n' "$MOBILE_VERSION"
