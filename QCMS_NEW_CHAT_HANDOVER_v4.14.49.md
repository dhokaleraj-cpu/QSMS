# QUALITY CONTROL MONITORING SYSTEM (QCMS)
## Complete New-Chat Handover — v4.14.49

### Controlled baseline
- Application version: `4.14.49`
- Build: `41449-ANDROID-SINGLE-NATIVE-DRAWER-V12`
- Project: `/Users/dhokaleraj/QSMS`
- Database schema baseline: `4.14.45` (unchanged)
- Continue versioning from `v4.14.50+`.

### Android authoritative architecture
- Android: `0.2.4`, versionCode `15`, debug package `com.fourstar.qcms.test`.
- **Only one Android navigation implementation is permitted:** native maroon top bar + visible `MENU` button + native expandable drawer.
- MENU/top bar/drawer are native Android views outside WebView; Streamlit CSS/DOM cannot hide them.
- MENU button uses vector `ic_qcms_menu.xml` plus visible text `MENU` and calls `openDrawer()` directly.
- Drawer is hidden by default, opens on MENU click, expands module submenus, and closes after page selection/outside tap/Back.
- Do not reintroduce `showStableStreamlitBrowser`, `toggleStreamlitSidebar`, `installStreamlitSidebarController`, `__qcmsNativeNavigate`, DOM route-click bridges, or queued JavaScript navigation into Android `MainActivity`.
- Server native-mode selection must remain generic for future `QCMSMobile/*` versions; do not hard-code an Android version.

### Why prior releases could still show no menu
- Native-mode CSS intentionally hides Streamlit sidebar/collapsed controls, so using Streamlit sidebar as the Android-visible menu was structurally fragile.
- Several old navigation implementations remained in the source lineage and changed which path was active by version/query state.
- Debug APK package is `com.fourstar.qcms.test`; a legacy `com.fourstar.qcms` can coexist and look similar. The v0.2.4 installer verifies and launches the exact corrected package.

### Installation identity guard
- Local helper verifies installed `versionName` and `versionCode` via `dumpsys package`.
- It launches `com.fourstar.qcms.test/com.fourstar.qcms.MainActivity` itself after successful install.
- App label includes `0.2.4` to distinguish it from an older installed APK.
- GitHub Android workflow runs for every main push and manual dispatch and verifies the native menu source before Gradle compilation.

### Preserved application functions
All v4.14.48 PO 5% watermark, approver identity, persistent-login, duplicate-page fix, Supply Chain, RMTC, OSP, MetLAB, Complaints, NPD/APQP, permissions and audit features remain preserved.

### Deployment rule
Continue with one self-contained macOS `.command` updater with backup, source verification, compile, online-readiness, phase verification, focused Android navigation regression, complete pytest, Git commit/push and remote SHA verification. No manual SQL for v4.14.49.
