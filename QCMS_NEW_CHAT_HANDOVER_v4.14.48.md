# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.49

### Controlled baseline
- Application Version: `4.14.49`
- Build: `41449-ANDROID-SINGLE-NATIVE-DRAWER-V12`
- Project path: `/Users/dhokaleraj/QSMS`
- Database schema baseline: `4.14.45` (unchanged).

### PO print
- APPROVED / PENDING APPROVAL watermark is exactly **5% opacity**, light ink, and merged underneath page content.
- Approved PO page 1 includes the real Employee Master approver identity and saved approval date/time.
- Single-PO, batch-print and email/PDF paths use the same enriched Purchase Order header.

### Browser / Android session stability
- Persistent auth payload no longer contains a changing timestamp.
- Auth storage write/clear actions do not emit Streamlit state/trigger reruns.
- Auth bridge mounts are zero-height and hidden by global CSS.
- Refresh attempts same-origin cookie restore before mounting the localStorage bridge.
- This removes the stacked/duplicate-page visual behavior reproduced from the supplied video while preserving refresh login restoration.

### Android
- Android `0.2.3` / versionCode `14`.
- v1.2-style native hamburger drawer + expandable submenu + auto-hide remain active.
- GitHub Android APK workflow runs on every `main` push and remains manually runnable.

### Deployment
- One self-contained macOS `.command` updater with backup, secret preservation, schema-baseline verification, compile, readiness, phase verification, complete pytest, Git commit/push and remote SHA verification.
- No new Supabase migration for v4.14.49.
