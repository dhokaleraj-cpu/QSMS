# QCMS Mobile - Android test shell v0.1.0

This project is the first Samsung/Android test client for the existing QCMS Streamlit application.
It does **not** copy or fork QCMS data. It loads the existing live HTTPS QCMS URL inside a hardened Android WebView, so the same login, Supabase data, RLS, permissions, audit records, PDFs and workflows are used.

## Device target
- Samsung Galaxy S26 Ultra / current Samsung Android devices
- minSdk 26, targetSdk 35
- Java 17 / Android Gradle Plugin 8.7.3

## First launch
1. Enter the live HTTPS QCMS Streamlit URL.
2. Sign in with the normal QCMS employee login.
3. Test Dashboard, Global Search, Purchase Orders, PDF downloads, approvals and file uploads.
4. Use the top-right menu to change the QCMS URL.

## Samsung USB test
1. On the Samsung phone: Settings > About phone > Software information > tap Build number 7 times.
2. Settings > Developer options > enable USB debugging.
3. Connect the phone to the Mac by USB-C and accept the RSA debugging prompt.
4. Run `BUILD_AND_INSTALL_SAMSUNG.command` from this folder.

## Security
- HTTPS only; clear-text HTTP is blocked.
- No Supabase service-role key is stored in the Android app.
- Login cookies are handled by Android WebView.
- Existing QCMS server-side permissions/RLS remain authoritative.

## Scope of v0.1.0
This is an intentionally lightweight mobile shell for immediate device testing. A later native mobile phase can add push notifications, QR/barcode scanning, direct camera capture, controlled offline inspection queues and biometric re-authentication without replacing the existing QCMS backend.
