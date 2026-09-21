# QCMS v4.14.38 Release Notes

**Build:** `41438-ANDROID-NAV-SESSION-BRIDGE-FOOTER-REMOVE`

## Android navigation/login-loop correction
- Android source is advanced to **0.1.6**.
- Drawer/submenu selections no longer call `WebView.loadUrl()` for an internal QCMS route.
- Native mode renders a hidden Streamlit `st.page_link` bridge for the registered pages. The Android wrapper clicks the correct Streamlit page link with JavaScript, so page navigation stays inside the existing Streamlit browser session and preserves the QCMS login/session state.
- Android retries the page-link bridge briefly while Streamlit is rendering. If the bridge is not ready, the app shows a short message and does **not** fall back to a hard route reload.
- The initial QCMS load still includes `native_mobile=1`; mobile user-agent detection remains preserved.

## Android UI correction
- Removed the fixed bottom **Home / Search / Complaints** navigation shown in the Android screenshot.
- Removed the top-bar hard refresh button because a browser-level reload can create a new Streamlit session and return an authenticated user to Login.
- Compact native top bar, hamburger drawer, expandable module/submodule groups, safe insets, upload/download support and STAWN icon remain preserved.
- Mobile content bottom padding is reduced because the old 68dp footer no longer exists.

## Preserved functionality
- v4.14.37 Complaint dashboard cards and Customer/Supplier registers.
- Complaint controlled PDF/supporting-document email and explicit Customer/Supplier copy before confirmation.
- Purchase Order Pending Approval KPI/grid, multi-select approver email and PENDING APPROVAL draft PDF.
- PO edit/reapproval, Supplier Confirmation independence, RMTC, Inward, OSP, MetLAB, Bend Test, Global Search, NPD/APQP, Calibration, Standard Room, permissions, audit and reporting.

## Database/runtime
- Required database baseline remains **v4.14.36**.
- No new Supabase schema migration or manual SQL is required by v4.14.38.
- Existing Complaint notification/runtime workers remain preserved.

## Verification intent
- Full Python compile, online-readiness, phase verification and complete pytest remain mandatory in the controlled updater.
- Android source/build helpers are supplied. An APK is installable only when it is genuinely compiled and `apksigner` verified by the Android build environment.
