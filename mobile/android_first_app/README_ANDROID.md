# QCMS Mobile 1.0.2 — First-App Architecture Recovery

This is deliberately based on the original QCMS Android v0.1.0 architecture that used one hardened WebView and allowed the QCMS website itself to own navigation.

## Why this build exists
Later native-drawer releases translated Android menu taps into QCMS routes. On the affected device those route requests fell back to Dashboard/Home. This recovery removes that layer completely.

- No Android native route drawer.
- No JavaScript navigation bridge.
- No `native_mobile=1` or `native_nav=native` flag.
- No `QCMSMobile/*` user-agent token (which tells the server to hide its web menus).
- QCMS page links are handled by Streamlit/QCMS directly inside the WebView.
- Current STAWN/QCMS app icon is retained.
- WebView cookies are flushed to disk after page load and when the app pauses.

## First launch
If the existing QCMS URL is already stored it is reused automatically. Any old native-mobile route parameters are removed. Otherwise enter the normal root HTTPS QCMS URL, e.g. `https://your-qcms.streamlit.app`.

Do not enter a `/dashboard` page URL and do not add `native_mobile=1`.
