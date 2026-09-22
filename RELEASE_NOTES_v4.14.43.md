# QCMS v4.14.43

## Android navigation recovery
- Android v0.2.0 removes the native Java drawer from the active UI path.
- Android now uses Streamlit's own collapsed sidebar/hamburger navigation.
- All menu selections are handled directly by `st.navigation`, preserving the logged-in Streamlit session.
- The active Android path no longer uses DOM-click timing, hidden navigation widgets, retries, or hard route `WebView.loadUrl()` navigation.
- The menu starts collapsed and returns to the selected page after navigation.
- Bottom Home/Search/Complaints footer remains removed.
- iPhone/iPad native navigation remains unchanged.
- No database migration is required.
