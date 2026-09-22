# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.44

### Controlled baseline
- Application Version: `4.14.44`
- Build: `41444-ANDROID-NATIVE-MENU-SUBMENU-RESTORE`
- Project path: `/Users/dhokaleraj/QSMS`
- Preserve Git history, Streamlit Cloud deployment, Supabase production/master/transaction/quality/supply-chain data, attachments and local secrets.
- Continue versioning from `v4.14.45+`.

### Android production wrapper
- Android: `v0.2.1`, `versionCode 12`.
- Permanent native top bar restores the Android Menu button.
- Menu button toggles Streamlit's official sidebar inside the same authenticated WebView/session.
- Streamlit's globally hidden collapsed-control is restored off-screen for Android so menu access cannot disappear because of desktop CSS.
- Sidebar navigation groups are expanded for immediate page visibility.
- The active module's QCMS sub-menu is restored in the content area using a phone-friendly two-column layout.
- Sidebar auto-close is attempted after selecting a page.
- No hard WebView route load for module navigation; no bottom Home/Search/Complaints footer.
- Dynamic APK identity and explicit v2 apksigner verification remain preserved.

### Full native Android direction
- A fully native Android QCMS can be built, but it should be a separate phased client using secure QCMS APIs for login, permissions, Masters, RMTC, Supply Chain, OSP, inspections, complaints, files, approvals, reports and notifications.
- Never embed Supabase service-role/admin credentials in the Android client.
- v4.14.44 focuses on making the production wrapper navigation reliable first.

### Database/deployment
- No new schema requirement in v4.14.44; database baseline remains v4.14.36.
- Every release remains one self-contained `.command` updater with backup, dirty-Git protection, source replacement, compile, readiness/phase verification, full pytest and Git push/remote-SHA verification.
