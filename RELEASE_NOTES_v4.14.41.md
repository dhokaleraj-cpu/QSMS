# QCMS v4.14.41 Release Notes

**Build:** `41441-ANDROID-LAMBDA-COMPILE-PERMANENT-FIX`

## Android compile correction
- Fixed `:app:compileDebugJavaWithJavac` failure in `MainActivity.java`.
- Root cause: `route` was assigned and then conditionally reassigned before being captured by a lambda, so Java did not consider it effectively final.
- Permanent pattern: normalize into a mutable temporary, then capture `final String route`.
- Added a regression test to prevent this exact callback-capture error from returning.

## Android identity
- Android source: **v0.1.9** (`versionCode 10`).
- Existing queued session-safe navigation, footer removal, and dynamic APK/signature CI checks remain preserved.

## Database
- No new Supabase migration. Database baseline remains v4.14.36.
