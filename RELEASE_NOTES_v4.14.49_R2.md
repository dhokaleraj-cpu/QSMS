# QCMS v4.14.49 R2 — Android Native Drawer Release Regression Repair

This is a packaging/test compatibility revision of controlled release v4.14.49. The application version and build identity remain `4.14.49` / `41449-ANDROID-SINGLE-NATIVE-DRAWER-V12`; no Supabase schema change is introduced.

## Why R2 exists
The first v4.14.49 updater correctly introduced the single native Android drawer, but the complete Mac regression suite stopped before Git push because stale historical non-regression tests still capped their accepted release/build/user-agent lists at v4.14.48 / Android v0.2.1. The Android build helper had also lost the older automatic Android SDK/CLI bootstrap marker and capability.

## Corrections
- Extended historical regression contracts to accept controlled release v4.14.49 and previous release v4.14.48.
- Extended Android regression contracts through `QCMSMobile/0.2.4`.
- Restored `ANDROID SDK / CLI BOOTSTRAP` to the Samsung build/install helper using Google's official Android command-line installer when no CLI/sdkmanager is present.
- Preserved dynamic Android version/APK/signature verification and exact package launch.
- Restored the route-normalization source guard in `MainActivity.navigate()` while retaining the one native Android drawer architecture.
- Updated current-release compatibility tests so they validate v4.14.49 rather than incorrectly forcing v4.14.48.
- No business logic, PO watermark, Supabase data, or QCMS schema is changed by R2.

## Validation
- Previously failing legacy/current release tests: 157 passed.
- Full source suite in the packaging environment with minimal Streamlit/Supabase import stubs: 608 passed.
- Full suite excluding the one Streamlit-importing test module, with no stubs: 597 passed.
- The six tests in the Streamlit-importing module passed with import-only stubs; they exercise PO watermark/approver output, auth bridge source contract, and Android workflow source contract, not a running Streamlit server.
- Online readiness: PASS, 268 required files, 0 missing.
- Phase verification: PASS, 0 errors.
- Android native drawer / legacy compatibility focused suite: PASS.

The actual updater still runs the complete pytest suite using `/Users/dhokaleraj/QSMS/.venv` on the QCMS Mac before any Git commit/push is allowed.
