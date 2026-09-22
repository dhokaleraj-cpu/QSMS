# QCMS v4.14.40 Release Notes

**Build:** `41440-ANDROID-NAV-READY-QUEUE-BUTTON-BRIDGE`

## Android navigation permanent correction
- Fixes the message **“QCMS navigation is still loading. Please try the menu again.”**
- Removes the short fixed-timeout dependency that could expire before Streamlit finished rendering after login or a rerun.
- Native menu selections are now queued until the Streamlit navigation bridge is ready.
- Hidden native navigation controls are Streamlit buttons; their callbacks use `st.switch_page(...)`, preserving the active authenticated Streamlit session.
- A MutationObserver and a 250 ms pending-route drain timer automatically execute a queued route as soon as the controls appear.
- The bridge is reinstalled before navigation and whenever the drawer opens.
- The old false loading toast is removed.

## Android
- Android source: **v0.1.8** (`versionCode 9`).
- Bottom Home/Search/Complaints footer remains removed.
- No hard WebView route reload is used for drawer navigation.
- v4.14.39 dynamic version/signature CI verification remains preserved.

## Database
No new schema migration. Existing Supabase data and the v4.14.36 notification schema baseline are preserved.
