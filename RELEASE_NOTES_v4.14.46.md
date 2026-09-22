# QCMS v4.14.46 — Android v1.2 Drawer + Persistent Login

- Version: **4.14.46**
- Build: **41446-ANDROID-V12-DRAWER-PERSISTENT-AUTH**
- Android: **v0.2.2 / versionCode 13**
- Database schema: **4.14.45 unchanged**; no Supabase migration is required.

## Android navigation
- Restores the compact native hamburger drawer based on the earlier v1.2-style Android navigation.
- Drawer and all submenus are hidden by default.
- Tapping the top-left Menu button opens the drawer; module groups expand their second-level options.
- Selecting any page closes the drawer immediately and opens the canonical QCMS route, returning the user to a clean full-screen content view.
- The Android v0.2.2 path no longer depends on Streamlit sidebar DOM discovery or delayed JavaScript route-click bridges.
- Streamlit desktop/sidebar/footer chrome remains hidden inside the Android WebView.

## Persistent authentication
- Fixes the repeated Login screen after normal browser refresh, Android WebView refresh and direct native-menu route loads.
- Primary persistence uses **Streamlit Components v2 + origin-scoped localStorage**. After successful Supabase sign-in, QCMS stores the current access/refresh session in `qcms.auth.session.v2`.
- On a fresh Streamlit session, the v2 browser bridge returns the stored session to Python before the Login gate; QCMS restores Supabase with `set_session()` and reloads the profile/permissions.
- Current/rotated Supabase tokens are synchronized back to localStorage after restore.
- The former `SameSite=Strict` cookie bridge remains as a backward-compatible fallback for upgrades.
- Logout clears localStorage and fallback cookies and signs out the Supabase session.
- Tokens are never put in route URLs, logs, Android preferences or QCMS database tables.

## Preserved
- All v4.14.45 shared raw forging/casting source, cross-Part price-history and controlled inspection-layout rules.
- Android dynamic APK identity/signature verification and GitHub CI build.
- iPhone/iPad source remains unchanged.
