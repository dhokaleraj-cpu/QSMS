#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
GRADLE_VERSION="8.9"
BOOT="$HOME/.gradle/qcms-bootstrap"
GRADLE_HOME="$BOOT/gradle-$GRADLE_VERSION"

say(){ printf '\n=== %s ===\n' "$1"; }
fail(){ printf '\nERROR: %s\n' "$1" >&2; exit 1; }

echo "============================================================"
echo " QCMS Mobile v0.1.2 - Samsung Android build & install"
echo "============================================================"
echo "Project : $HERE"
echo "SDK     : $SDK"

mkdir -p "$SDK"

find_android_cli(){
  local candidate
  for candidate in \
    "$HOME/.android/cli/bin/android" \
    "$HOME/.android/cli/latest/bin/android" \
    "/opt/homebrew/bin/android" \
    "/usr/local/bin/android"; do
    if [ -x "$candidate" ]; then printf '%s\n' "$candidate"; return 0; fi
  done
  if command -v android >/dev/null 2>&1; then command -v android; return 0; fi
  return 1
}

find_sdkmanager(){
  local candidate
  for candidate in \
    "$SDK/cmdline-tools/latest/bin/sdkmanager" \
    "$HOME/.android/cli/bin/sdkmanager" \
    "/opt/homebrew/bin/sdkmanager" \
    "/usr/local/bin/sdkmanager"; do
    if [ -x "$candidate" ]; then printf '%s\n' "$candidate"; return 0; fi
  done
  if command -v sdkmanager >/dev/null 2>&1; then command -v sdkmanager; return 0; fi
  return 1
}

ANDROID_CLI="$(find_android_cli || true)"
SDKMANAGER="$(find_sdkmanager || true)"

if [ -z "$ANDROID_CLI" ] && [ -z "$SDKMANAGER" ]; then
  say "ANDROID SDK / CLI BOOTSTRAP"
  echo "Android development tools were not found. QCMS will install Google's official Android CLI for this Mac user."
  ARCH="$(uname -m)"
  if [ "$ARCH" = "arm64" ]; then CLI_ARCH="darwin_arm64"; else CLI_ARCH="darwin_x86_64"; fi
  INSTALLER_URL="https://dl.google.com/android/cli/latest/${CLI_ARCH}/install.sh"
  echo "Installing Android CLI for $ARCH..."
  curl -fsSL --retry 3 "$INSTALLER_URL" | bash
  export PATH="$HOME/.android/cli/bin:$HOME/.android/cli/latest/bin:$PATH"
  ANDROID_CLI="$(find_android_cli || true)"
  SDKMANAGER="$(find_sdkmanager || true)"
fi

say "ANDROID PLATFORM 35 / PLATFORM-TOOLS"
if [ -n "$ANDROID_CLI" ]; then
  echo "Using Android CLI: $ANDROID_CLI"
  # Android CLI is the current Google-recommended SDK package manager.
  "$ANDROID_CLI" --sdk="$SDK" sdk install platforms/android-35 build-tools/35.0.0 platform-tools
elif [ -n "$SDKMANAGER" ]; then
  echo "Using legacy sdkmanager: $SDKMANAGER"
  yes | "$SDKMANAGER" --sdk_root="$SDK" --licenses >/dev/null 2>&1 || true
  "$SDKMANAGER" --sdk_root="$SDK" "platform-tools" "platforms;android-35" "build-tools;35.0.0"
else
  fail "Android CLI/SDK manager could not be installed or found."
fi

ADB="$SDK/platform-tools/adb"
[ -x "$ADB" ] || fail "adb was not installed at $ADB"

# Android Gradle Plugin 8.7.x requires Java 17.
if ! command -v java >/dev/null 2>&1; then
  fail "Java 17 is required but 'java' is not available. Install JDK 17 (for example Temurin 17) and rerun this same command."
fi
JAVA_MAJOR="$(java -version 2>&1 | awk -F'[\".]' '/version/ {print $2; exit}')"
if [ -n "$JAVA_MAJOR" ] && [ "$JAVA_MAJOR" -lt 17 ] 2>/dev/null; then
  fail "Java 17 or newer is required. Current Java major version: $JAVA_MAJOR"
fi

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
"$GRADLE_HOME/bin/gradle" --no-daemon clean :app:assembleDebug
APK="$HERE/app/build/outputs/apk/debug/app-debug.apk"
[ -f "$APK" ] || fail "APK not produced: $APK"
# Keep the user-facing APK in Downloads even when no phone/ADB device is attached.
mkdir -p "$HOME/Downloads"
OUTPUT_APK="$HOME/Downloads/QCMS_Mobile_v0.1.2_TEST.apk"
cp -p "$APK" "$OUTPUT_APK"
"$SDK/build-tools/35.0.0/apksigner" verify --verbose "$OUTPUT_APK" || fail "APK signature verification failed."
printf '\nAPK READY: %s\n' "$OUTPUT_APK"
shasum -a 256 "$OUTPUT_APK" > "$OUTPUT_APK.sha256"
if [ "${QCMS_BUILD_ONLY:-0}" = "1" ]; then exit 0; fi

echo
"$ADB" start-server >/dev/null
mapfile_supported=0
if command -v mapfile >/dev/null 2>&1; then mapfile_supported=1; fi
if [ "$mapfile_supported" -eq 1 ]; then
  mapfile -t DEVICES < <("$ADB" devices | awk 'NR>1 && $2=="device" {print $1}')
else
  DEVICES=( $("$ADB" devices | awk 'NR>1 && $2=="device" {print $1}') )
fi
if [ "${#DEVICES[@]}" -eq 0 ]; then
  echo "APK built successfully: $APK"
  echo "No authorised Samsung phone is connected. Enable Developer options > USB debugging, reconnect USB-C, accept the RSA prompt, then rerun this same command."
  "$ADB" devices || true
  exit 0
fi
if [ "${#DEVICES[@]}" -gt 1 ]; then
  echo "Multiple Android devices are connected. Disconnect all except the Samsung test phone and rerun."
  "$ADB" devices
  exit 1
fi
DEVICE="${DEVICES[0]}"
say "INSTALL TO SAMSUNG DEVICE $DEVICE"
"$ADB" -s "$DEVICE" install -r "$APK"
echo
echo "SUCCESS: QCMS Mobile installed. Open 'QCMS Mobile' on the Samsung phone and enter the live HTTPS QCMS URL."
