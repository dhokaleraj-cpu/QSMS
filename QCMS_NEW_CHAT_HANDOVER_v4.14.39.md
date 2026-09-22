# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.39

### 1. Controlled baseline
- **Application Version:** `4.14.39`
- **Build:** `41439-ANDROID-CI-SIGNATURE-PERMANENT-FIX`
- **Project path:** `/Users/dhokaleraj/QSMS`
- Preserve Git history, Streamlit Cloud deployment, Supabase production/master/transaction/quality/supply-chain data, attachments and local secrets.
- Continue versioning from **v4.14.40+**.

### 2. Android permanent APK verification fix
- Android source: **v0.1.7**.
- Preserve v4.14.38 session-safe drawer navigation; internal menu navigation must never hard-load a route that can discard the active Streamlit authenticated session.
- Fixed Home/Search/Complaints mobile footer remains removed.
- GitHub Android workflow derives `versionName`, `versionCode` and APK filename from Gradle on every build; never hard-code historical Android versions in CI checks.
- Capture the actual `apksigner` process status with `PIPESTATUS[0]` when piping to `tee`.
- Required APK signature condition for the current minSdk 26 test APK: `apksigner` success and `Verified using v2 scheme ...: true`.
- v1/v3/v3.1/v4/SourceStamp false values are informational and do not independently fail CI.
- Verify `zipalign`, package id, APK versionName and versionCode before uploading the artifact.
- Artifact name is stable: `QCMS-Mobile-TEST-APK`; contained APK filename is dynamic, e.g. `QCMS_Mobile_v0.1.7_TEST.apk`.
- Local Mac build helper applies the same checks and writes a `.signature.txt` report plus `.sha256`.

### 3. Preserved mobile/runtime behavior
- Native WebViews always request `native_mobile=1` and use the QCMS mobile user-agent.
- Streamlit native mode remains content-only with no duplicate desktop shell/footer.
- No Supabase service-role/admin key is embedded in mobile clients.
- iPhone/iPad source remains v0.1.2 and is not changed by this Android CI hotfix.

### 4. Database baseline
- v4.14.39 requires **no new schema migration**.
- v4.14.36 Complaint notification migration and active notifier baseline remain preserved.
- Do not ask for manual SQL for this release.

### 5. Deployment rule
Every release remains one self-contained macOS `.command` updater with backup, dirty-Git protection, source replacement, dependency verification, compile, online-readiness, phase verification, complete pytest, Git commit/push and remote SHA verification.

### 6. Mobile binary rule
- Android source/build helpers must always be supplied; include APK only when actually compiled and signature-verified.
- Never rename a source ZIP as APK or imply an unbuilt binary is installable.
