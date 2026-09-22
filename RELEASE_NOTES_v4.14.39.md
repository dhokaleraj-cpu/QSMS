# QCMS v4.14.39 Release Notes

**Build:** `41439-ANDROID-CI-SIGNATURE-PERMANENT-FIX`

## Android APK verification permanent fix

- Android source advances to **v0.1.7** while preserving the v0.1.6 session-safe drawer navigation and removal of the fixed mobile footer.
- GitHub APK CI no longer contains historical hard-coded APK names/version checks. It reads `versionName` and `versionCode` from `mobile/android_qcms/app/build.gradle` every run.
- `apksigner` verification captures the signer process status using `PIPESTATUS[0]` even while output is written through `tee`.
- CI explicitly requires **APK Signature Scheme v2 = true** and validates zip alignment, package id, versionName and versionCode.
- v1/v3/v3.1/v4/SourceStamp `false` output is treated as informational for the current internal debug APK, not as a failure by itself.
- Local Mac/Samsung builder now follows the same rules, writes a signature report, verifies zip alignment, and derives its Downloads APK filename from Gradle.

## Database / server

- No new Supabase schema migration.
- Existing v4.14.36 schema/notifier baseline remains unchanged.
- No production/master/transaction/quality/supply-chain data reset or truncation.
