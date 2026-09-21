# QCMS Mobile for iPhone and iPad - v0.1.2

Universal iPhone/iPad WKWebView shell for the live HTTPS QCMS application.

- Uses the attached STAWN icon.
- Main QCMS menu and module submenu are collapsed by default on mobile.
- Native menu button opens/collapses navigation.
- Uses the same live QCMS login, permissions, Supabase RLS and audit controls.
- No Supabase service-role key is embedded.

## Build
1. Install Xcode on the Mac.
2. Open `QCMSMobileIOS.xcodeproj`.
3. Select target `QCMSMobileIOS` > Signing & Capabilities and choose your Apple Development Team.
4. Use a unique bundle ID if your Apple account requires it.
5. Connect iPhone/iPad and Run, or use the supplied `BUILD_IPA_ON_MAC.command`.

A signed installable IPA cannot be created without an Apple Development/Distribution identity and provisioning profile belonging to your Apple account.

## v0.1.2 mobile UI
- Compact dark native header with STAWN icon.
- Slide-out drawer for QCMS modules.
- Bottom Home / Search / Complaints navigation.
- Streamlit main/module navigation is hidden inside the native app so content begins immediately.
