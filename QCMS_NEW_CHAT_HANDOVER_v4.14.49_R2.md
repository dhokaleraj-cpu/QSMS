# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Controlled Handover — v4.14.49 R2

### Controlled identity
- Application Version: `4.14.49`
- Build: `41449-ANDROID-SINGLE-NATIVE-DRAWER-V12`
- Release revision: `R2`
- Previous controlled application release: `4.14.48`
- Database schema baseline: `4.14.45`; no v4.14.49/R2 migration.
- Project path: `/Users/dhokaleraj/QSMS`

### R2 purpose
The first v4.14.49 source introduced the correct single native Android navigation architecture, but deployment was blocked by stale historical test allow-lists and a regression in the Android SDK bootstrap helper. R2 fixes the release/testing package without changing the v4.14.49 business feature identity.

### Android navigation architecture
- Android v0.2.4 / versionCode 15.
- Native maroon top bar and visible MENU button live outside the WebView.
- MENU click opens the native drawer directly.
- Expandable native module/submenu groups are the only active Android navigation architecture.
- Drawer closes after page selection, outside tap, or Back.
- Streamlit CSS cannot hide the native top bar/menu.
- Obsolete Streamlit-sidebar/DOM navigation bridge code remains excluded from Android.

### Android build/install reliability
- `BUILD_AND_INSTALL_SAMSUNG.command` again contains automatic `ANDROID SDK / CLI BOOTSTRAP` when Android CLI/sdkmanager is unavailable.
- Dynamic version/APK naming remains in use.
- APK v2 signature and zipalign checks remain mandatory.
- Exact package `com.fourstar.qcms.test` is verified and auto-launched.
- GitHub Android workflow remains automatic on every main push and manually runnable.

### Regression repair
- All historical release identity tests now recognize v4.14.49/build 41449 where appropriate.
- Previous-release mapping includes `4.14.49 -> 4.14.48`.
- Legacy Android tests recognize `QCMSMobile/0.2.4`.
- Route normalization guard is present before native URL loading.

### Deployment rule
Use `QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R2.command`. It accepts an existing local `VERSION=4.14.49`, backs up/stashes failed-release work, installs the corrected controlled payload, runs compile/readiness/phase/focused Android tests and the complete pytest suite, then and only then commits/pushes and verifies remote SHA.
