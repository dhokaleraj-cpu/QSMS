# STAWN QCMS for iPhone and iPad (native SwiftUI app) — v1.0.0

Universal native app (iPhone + iPad, iOS / iPadOS 16 or newer). Same Supabase login, data, permissions (RLS) and
print layouts as the website and the Android app. Only the publishable key is in the app.

## What is native in v1.0.0
- Sign in, Face ID / Touch ID unlock, keep-me-signed-in (refresh token in the iOS Keychain), auto-lock after 15 minutes.
- Home with live counters and quick open; tabs Supply · Quality · Masters · More with every QCMS module (79).
- Global search bar at the top of every tab (same 27 sources as the website).
- Every register as a spreadsheet grid (slide ↔ ↕), search, status filters, Register PDF, CSV for Excel.
- Every record: details, linked child tables, photos & documents (view, add photo / file), record history, delete / deletion request.
- **Print layout PDF exactly like the website** for MetLAB, Bend Test, Dimensional, Material Inward, RMTC, complaints,
  calibration, standard room, QC calculations and the Universal Record PDF for every other record — View, Save to Files,
  AirPrint, Email, Share. MetLAB / Bend / Dimensional / RMTC / Inward / complaint records also show the full report on screen.
- Reports Centre and Records Centre, Purchase Order approve / cancel, Standard Room entry form, My Account (password change), About.

## Opened from the website inside the app (marked WEB)
Entry / workflow screens that have many business rules (RMTC entry and worksheets, Material Inward, MetLAB / Bend / Dimensional
entry, OSP, Customer Orders and PO creation, NPD / APQP, masters editing, admin, KPI dashboards, Report Builder) open the
matching website page inside the app until they are ported natively.

## Build and install (Mac with Xcode 15 or newer)
1. `cd ~/QSMS/mobile/ios_stawn_qcms && ./BUILD_STAWN_QCMS_iOS.command` → generates the Xcode project, runs a build check and opens Xcode.
2. Xcode → target **STAWNQCMS** → Signing & Capabilities → Team = your Apple Developer team (bundle id `com.stawnprecision.qcms`).
3. Connect the iPhone / iPad, choose it at the top, press **Run**. (First time on the device: Settings → Privacy & Security → Developer Mode → On.)
4. For colleagues: create the app in App Store Connect (bundle id `com.stawnprecision.qcms`, name STAWN QCMS), then
   `echo YOURTEAMID > ~/.stawn_apple_team_id` and `./BUILD_STAWN_QCMS_iOS.command testflight` → TestFlight → invite testers.
   `./BUILD_STAWN_QCMS_iOS.command adhoc` exports a signed .ipa for devices registered in your developer account.

GitHub workflow **STAWN QCMS iOS iPadOS App Build** compiles the app on every push (no signing).
