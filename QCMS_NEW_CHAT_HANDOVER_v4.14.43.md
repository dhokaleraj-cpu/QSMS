# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.43

### Controlled baseline
- Application Version: `4.14.43`
- Build: `41443-ANDROID-STREAMLIT-SIDEBAR-NAV`
- Project path: `/Users/dhokaleraj/QSMS`
- Continue versioning from `v4.14.44+`.

### Android mobile baseline
- Android `v0.2.0`, versionCode `11`.
- Android loads `native_mobile=1&native_nav=streamlit`.
- Android navigation is owned by Streamlit's official sidebar router, collapsed by default.
- The active Android UI no longer depends on the native drawer/DOM bridge.
- Page selection remains in the current authenticated Streamlit session.
- Bottom Home/Search/Complaints footer remains removed.
- iPhone/iPad behavior is unchanged.

### Database / deployment
- Database schema baseline remains `4.14.36`; no new SQL is required.
- Continue using one self-contained macOS `.command` updater with backup, compile, readiness, phase verification, pytest, Git commit/push and remote SHA verification.
