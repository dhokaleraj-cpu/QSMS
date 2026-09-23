# QUALITY CONTROL MONITORING SYSTEM (QCMS)

## Current controlled release — v4.14.49
Build `41449-ANDROID-SINGLE-NATIVE-DRAWER-V12`.

QCMS v4.14.49 is an Android navigation recovery release. Android **v0.2.4 / versionCode 15** uses one authoritative native V1.2-style navigation drawer outside the WebView. The maroon native top bar always contains a visible **MENU** control; the drawer expands module submenus and auto-hides after a page selection. All alternate DOM/Streamlit-sidebar Android navigation code has been removed from the active Android source.

The Android install helper verifies the exact `com.fourstar.qcms.test` package/version and launches it automatically, preventing confusion with older similarly named QCMS apps. GitHub **QCMS Android Test APK** builds on every push to `main` and remains manually runnable.

The controlled database schema remains **v4.14.45**. No new Supabase migration or manual SQL is required. Existing v4.14.48 PO watermark, approver identity, persistent refresh-login and duplicate-page fixes remain preserved.

Use `QSMS_LIVE_DEPLOY_UPDATE_v4.14.49.command` for the controlled source deployment, then build/install Android v0.2.4 from GitHub Actions or `mobile/android_qcms/BUILD_AND_INSTALL_SAMSUNG.command`.
