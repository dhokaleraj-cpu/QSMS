# QCMS v4.14.49 — Android Single Native V1.2 Drawer Recovery

## Why this release exists
The Android navigation bar/drawer remained unreliable across many releases because the mobile source had accumulated **multiple competing navigation architectures**. Deep inspection found all of the following in the same lineage:

1. a native Android drawer,
2. a Streamlit-sidebar controller,
3. hidden DOM/`st.page_link` click bridges,
4. queued JavaScript navigation,
5. version-specific `QCMSMobile/0.x.x` server detection.

The QCMS CSS also intentionally hides the normal Streamlit sidebar/collapsed control in native content mode. Therefore any Android implementation that tries to make the WebView/Streamlit sidebar serve as the visible mobile menu can disappear again when CSS or Streamlit DOM structure changes.

A second practical risk was APK identity: debug builds use `com.fourstar.qcms.test`, while an older `com.fourstar.qcms` installation can remain on the same phone with a similar icon. Opening the older package makes a corrected source build appear unchanged.

## Structural correction
- Android advances to **v0.2.4 / versionCode 15**.
- `MainActivity` now contains **one authoritative navigation architecture only**: a native V1.2-style Android top bar + expandable drawer.
- The visible **MENU** button and drawer are native Android views **outside the WebView**. Streamlit CSS cannot hide them.
- The top bar is forced visible/front after each WebView page load and uses a real vector hamburger icon plus the text `MENU`, avoiding font/glyph-only failure.
- `MENU` click is directly wired to `openDrawer()`.
- Drawer modules expand/collapse by tap; child page selection closes the drawer and navigates in the same WebView.
- Drawer closes on outside tap and Android Back.
- The bottom Home/Search/Complaints footer stays removed.
- Obsolete `showStableStreamlitBrowser`, Streamlit-sidebar controller, queued DOM bridge, and native JS navigation code are removed from current Android source.
- Streamlit server routing is now **version independent**: any `QCMSMobile/*` client defaults to native-drawer mode unless `native_nav=streamlit` is explicitly requested for diagnostics.

## Exact APK/package verification
- App label is **QCMS Mobile 0.2.4**.
- Debug package is `com.fourstar.qcms.test`.
- Local build/install verifies `versionName=0.2.4` and `versionCode=15` from the installed phone package.
- It launches the exact package/activity automatically after install.
- If legacy `com.fourstar.qcms` is also installed, the helper warns about it so the wrong icon is not opened.

## GitHub APK
`QCMS Android Test APK` continues to run on every push to `main` and by manual `workflow_dispatch`. Before Gradle compile, CI now verifies that the real native MENU/open-drawer source exists and that legacy competing navigation methods are absent.

## Preserved
- v4.14.48 5% PO watermark and real approver identity.
- Persistent browser/WebView login recovery.
- Duplicate/stacked-page auth-bridge correction.
- Supply Chain, RMTC, OSP, MetLAB, Complaints, NPD/APQP, permissions and audit.
- Database schema remains **v4.14.45**; no SQL migration.
