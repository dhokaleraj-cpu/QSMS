# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.46

### 1. Controlled baseline
- **Application Version:** `4.14.46`
- **Build:** `41446-ANDROID-V12-DRAWER-PERSISTENT-AUTH`
- **Project path:** `/Users/dhokaleraj/QSMS`
- Preserve Git history, Streamlit Cloud deployment, Supabase production/master/transaction/quality/supply-chain data, attachments and local secrets.
- Continue versioning from **v4.14.47+**.
- Database schema remains **v4.14.45**; v4.14.46 adds no SQL migration and does not require Supabase CLI authentication.

### 2. Android v0.2.2 — v1.2-style navigation restored
- `versionCode 13`, user-agent `QCMSMobile/0.2.2`.
- Active navigation is the compact native v1.2-style hamburger drawer.
- Drawer is hidden by default and opens only from the top-left Menu button.
- Module groups expand to their native submenus; Dashboard/Search/Templates remain one-tap routes.
- Any route/submenu selection immediately closes the drawer before loading the selected page, so the content area returns to full screen automatically.
- `native_mobile=1&native_nav=native` keeps Streamlit desktop/sidebar/footer chrome out of the Android WebView.
- The old Streamlit-sidebar controller remains only as backward compatibility for Android v0.2.0/v0.2.1 and is not the active v0.2.2 path.

### 3. Persistent login / refresh recovery
- Browser refresh, Android WebView refresh, or an Android native drawer route load can create a new Streamlit WebSocket/Python session. QCMS now restores Supabase authentication before the Login screen is rendered.
- **Primary persistence:** Streamlit Components v2 writes the current Supabase access/refresh session to origin-scoped browser/WebView `localStorage` (`qcms.auth.session.v2`) and reads it back on a fresh Streamlit session.
- Components v2 runs with app-page DOM privileges and returns the stored session to Python; QCMS then calls Supabase `set_session()` and reloads the user profile/permissions.
- **Compatibility fallback:** the previous same-origin `SameSite=Strict` cookie bridge remains for upgrade recovery and for browsers where the v2 bridge is unavailable.
- Refreshed/rotated Supabase tokens are synchronized back to localStorage after restoration.
- Logout signs out Supabase and clears both localStorage and fallback cookies.
- No authentication token is placed in URL parameters, Android SharedPreferences, logs, or QCMS application tables.

### 4. v4.14.45 business rules preserved
- Same numeric price may exist for different Part Master records.
- Raw Material Details may link a Source Raw Forging / Casting Part.
- Supply Chain can inherit shared source forging/casting price/technical identity while retaining finished-Part genealogy.
- Inspection Layout Plan Number remains automatic from Stage + Process + Part + Layout Name and one current layout per controlled scope.

### 5. Deployment rule
Every release remains one self-contained macOS `.command` updater with backup, dirty-Git protection, source replacement, dependency verification, compile, readiness, phase verification, complete pytest, Git commit/push and remote SHA verification. v4.14.46 requires no Supabase schema change, no manual SQL and no local Supabase login.
