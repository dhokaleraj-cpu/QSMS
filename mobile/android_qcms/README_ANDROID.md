# QCMS Mobile 0.2.4 — single native V1.2-style drawer

Android navigation is fully native and lives outside the WebView. Streamlit CSS and page reruns cannot hide the Android MENU button or drawer.

Visible behavior:
- A compact maroon top bar is always visible.
- A white MENU label + hamburger icon is always at upper-left.
- Tap MENU to open the full native QCMS module drawer.
- Tap a module header to expand/collapse its submenu.
- Tap a page to navigate; the drawer closes automatically.
- Android Back closes the drawer first.

The local build/install helper verifies the exact package/version and launches `com.fourstar.qcms.test` automatically to avoid opening an older similarly named QCMS app.
