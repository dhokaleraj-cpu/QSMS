# QCMS v4.14.44 Release Notes

Build: `41444-ANDROID-NATIVE-MENU-SUBMENU-RESTORE`

## Android navigation recovery
- Android app advances to **v0.2.1 / versionCode 12**.
- Restores a compact permanent native Android top bar with a **Menu** button.
- The Menu button opens/closes Streamlit's official grouped sidebar; page selection remains owned by Streamlit so the authenticated WebView session is preserved.
- Restores Streamlit's collapsed sidebar control off-screen for Android only, overriding the desktop global CSS that previously hid it.
- Sidebar module groups are expanded so page options are immediately visible when the menu is opened.
- Restores the current module **sub-menu** inside the Android content area in a two-column mobile layout.
- Adds DOM observer/retry support only for opening/closing the sidebar and auto-closing it after a page selection; route navigation itself is not performed by Android JavaScript.
- The obsolete bottom Home/Search/Complaints footer remains removed.
- No hard WebView route reload is used for menu selection.

## APK verification
- Dynamic Android version detection and explicit APK Signature Scheme v2 verification remain preserved.
- Optional v1/v3/v3.1/v4/SourceStamp `false` lines remain non-fatal for the internal debug APK.

## Database
- No new Supabase schema migration is required.
- Existing v4.14.36+ database baseline and production data are preserved.
