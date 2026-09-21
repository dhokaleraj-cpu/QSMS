# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.38

### 1. Controlled baseline
- **Application Version:** `4.14.38`
- **Build:** `41438-ANDROID-NAV-SESSION-BRIDGE-FOOTER-REMOVE`
- **Project path:** `/Users/dhokaleraj/QSMS`
- Preserve Git history, Streamlit Cloud deployment, Supabase production/master/transaction/quality/supply-chain data, attachments and local secrets.
- Continue versioning from **v4.14.39+**.

### 2. Android mobile correction
- **Android source version:** `0.1.6`.
- Fixed the native drawer/submenu login-loop: internal QCMS navigation must **not** use hard `WebView.loadUrl()` route changes after Login.
- `streamlit_app.py` renders a hidden native navigation bridge containing Streamlit `st.page_link` elements for registered QCMS pages.
- Android calls the bridge through `evaluateJavascript` and clicks the corresponding Streamlit page link. This preserves the authenticated Streamlit session while changing page routes.
- Android retries the bridge while the Streamlit page is rendering and never falls back to a hard internal route load.
- Initial native launch still uses `native_mobile=1`, and QCMS mobile user-agent detection remains preserved.

### 3. Android UI baseline
- The fixed bottom **Home / Search / Complaints** footer/navigation is removed.
- The hard-refresh icon is removed from the Android top bar to avoid accidental session reset.
- Keep the compact top bar, hamburger drawer, expandable module/submodule groups, STAWN icon, file upload/download, safe insets and content-only Streamlit rendering.
- Native mobile content uses the full screen below the top bar with reduced bottom padding.

### 4. iPhone/iPad
- iPhone/iPad remains at source version `0.1.2` in this Android-focused release.
- Do not imply a signed IPA exists unless actually signed/exported with the user's Apple Team/provisioning.

### 5. Preserved v4.14.37 functionality
- Complaint dashboard status cards and detailed Customer/Supplier registers.
- Complaint controlled PDF/supporting-document email and explicit Customer/Supplier copy.
- PO Pending Approval KPI/grid, selected approver draft-email action and PENDING APPROVAL watermarked PDF.
- Supplier Confirmation remains independent from PO editing.
- All existing RMTC, Inward, OSP, MetLAB, Bend Test, Global Search, NPD/APQP, Calibration, Standard Room, permissions, audit, reports and supply-chain controls remain preserved.

### 6. Database/runtime
- Required database baseline remains **v4.14.36**.
- v4.14.38 adds **no new schema requirement** and must not ask for manual SQL.
- Existing notification workers/schedules remain preserved.

### 7. Deployment rule
Every release remains one self-contained macOS `.command` updater with backup, dirty-Git protection, source replacement, dependency verification, compile, online-readiness, phase verification, complete pytest, Git commit/push and remote SHA verification.

### 8. Mobile binary rule
- Android source/build helpers must always be supplied; include APK only when actually compiled and signature-verified.
- iPhone/iPad source/build helper must always be supplied; include IPA only when actually signed/exported.
- Never rename a source ZIP as APK/IPA or imply an unsigned/unbuilt binary is installable.
