# QCMS v4.14.42 Release Notes

Build: `41442-LOCAL-JAVAC-OPTIONAL-CI-COMPILE-GUARD`

## Fixed
- Fixed the v4.14.41 updater stopping at the complete pytest suite on Macs that do not have a functional JDK.
- The Android lambda regression test now probes `javac -version` and skips only that compile test when the JDK is unavailable. This handles the macOS `/usr/bin/javac` launcher case where the command exists but reports “Unable to locate a Java Runtime that supports javac.”
- GitHub Android CI remains the authoritative compile gate with Temurin Java 17 and Gradle `:app:assembleDebug :app:lintDebug`.

## Preserved
- Android v0.1.9 final/effectively-final lambda capture fix.
- Session-safe queued navigation and removed mobile footer.
- Dynamic APK naming and v2 signature verification.
- Existing Supabase/database baseline; no manual SQL.
