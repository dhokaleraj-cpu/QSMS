# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.40

### 1. Controlled baseline
- **Application Version:** `4.14.40`
- **Build:** `41440-ANDROID-NAV-READY-QUEUE-BUTTON-BRIDGE`
- **Project path:** `/Users/dhokaleraj/QSMS`
- Preserve Git history, Streamlit Cloud deployment, Supabase production/master/transaction/quality/supply-chain data, attachments and local secrets.
- Continue versioning from **v4.14.41+**.

### 2. Android navigation correction
- Android source is **v0.1.8 / versionCode 9**.
- The old fixed-retry page-link bridge that could show `QCMS navigation is still loading. Please try the menu again.` is superseded.
- Native menu navigation is queued in JavaScript until Streamlit controls are actually rendered.
- Hidden `QCMS_NAV::<route>` Streamlit buttons call `st.switch_page(...)`, keeping the existing authenticated Streamlit session.
- A DOM MutationObserver and 250 ms queue drain timer complete pending navigation after slow login/rerender cycles.
- The bridge is reinstalled on drawer open and before every navigation request.
- No hard `WebView.loadUrl(nativeUrl(path))` route navigation is used.
- Android bottom Home/Search/Complaints footer remains removed.

### 3. APK verification
- Preserve v4.14.39 dynamic Android version identity, real `apksigner` exit capture, v2=true requirement, zipalign/package/version verification and nonfatal optional v1/v3/v4/SourceStamp false values.

### 4. Database
- Existing v4.14.36 Complaint notification schema baseline remains live.
- v4.14.40 adds no schema change and requires no manual SQL.

### 5. Preserved application functionality
Complaint cards/email/reminders, Purchase Order approval worklist/draft approver email, PO edit/PDF/confirmation flow, RMTC, Supply Chain, OSP, MetLAB, dimensional, Bend Test, NPD/APQP, Calibration, Standard Room, permissions and audit remain preserved.

### 6. Deployment rule
Every release remains one self-contained macOS `.command` updater with backup, source replacement, dependency verification, compile, readiness verification, complete pytest, Git commit/push and remote SHA verification. Do not request manual SQL unless technically unavoidable.

### 7. Mobile binary rule
Android source/build helpers must always be supplied; include APK only when actually compiled and signature-verified. Never rename a source ZIP as an APK.
