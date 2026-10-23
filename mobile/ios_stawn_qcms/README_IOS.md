# STAWN QCMS for iPhone and iPad (native SwiftUI app) — v1.1.0 (build 2)

Universal native app (iPhone + iPad, iOS / iPadOS 16 or newer). Same Supabase login, data, permissions (RLS) and
print layouts as the website and the Android app. Only the publishable key is in the app.

## New in v1.1.0
- **KPI start dashboard** (first tab after login, `qcms_kpi_dashboard`): pending tasks first, KPI cards and charts (Swift Charts)
  for Quality · Supply Chain · Production · NPD · Management. Switches department every 20 s with a slide animation; tapping a
  department pauses the auto-switch for 60 s. Pull to refresh. The previous Home (counters + quick open) is the house button.
- **Notifications**: bell with unread badge on the main screens, inbox (Unread / All, Mark all read, tap opens the record or
  the matching website page), WhatsApp opt-in with mobile number, app icon badge = unread count.
- **Push notifications (APNs)**: permission is asked after sign in; the device token is registered with
  `qcms_register_push_device` (`IOS` for Release / TestFlight, `IOS_SANDBOX` for Debug builds from Xcode). Tapping a push opens the inbox.
- **Global search** now also searches every business table and field on the server (`qcms_global_search`, e.g. "J5/16") and
  lists matching modules / screens (e.g. "bend test").
- **Licence**: the licensed company is shown on Home / Dashboard, full licence details in About. If the licence is not valid
  the app shows a STAWN licence screen (contact, About, Sign out; company admins can enter a licence key).

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

## Push notifications (APNs)
The app already contains the Push Notifications entitlement (`STAWNQCMS/STAWNQCMS.entitlements`, `aps-environment`) and
`UIBackgroundModes` → `remote-notification`. One-time setup by STAWN (no secret is ever stored in the app or in Git):
1. developer.apple.com → Certificates, Identifiers & Profiles → **Identifiers** → `com.stawnprecision.qcms` → enable
   **Push Notifications** → Save. (Xcode → Signing & Capabilities then shows *Push Notifications*; automatic signing refreshes the profiles.)
2. developer.apple.com → **Keys** → **+** → name "STAWN QCMS APNs" → tick **Apple Push Notifications service (APNs)** → Continue →
   Register → **Download** `AuthKey_XXXXXXXXXX.p8` (only once!) and note the **Key ID**. Your **Team ID** is under Membership details.
3. Give the key to the Supabase edge function `qcms-push-dispatch` (runs every 2 minutes):
   ```bash
   supabase secrets set APNS_KEY_P8="$(cat AuthKey_XXXX.p8)" APNS_KEY_ID=XXXX APNS_TEAM_ID=XXXX --project-ref xxrxopzxzyjnzumrwuwy
   ```
4. Builds run from Xcode (Debug) register as `IOS_SANDBOX` (APNs sandbox); TestFlight / App Store builds register as `IOS`
   (APNs production — Xcode re-signs `aps-environment` to *production* when distributing). Keep the `.p8` file private.

## Build and install (Mac with Xcode 15 or newer)
1. `cd ~/QSMS/mobile/ios_stawn_qcms && ./BUILD_STAWN_QCMS_iOS.command` (or `python3 make_project.py 1.1.0 2` to only regenerate) → generates the Xcode project, runs a build check and opens Xcode.
2. Xcode → target **STAWNQCMS** → Signing & Capabilities → Team = your Apple Developer team (bundle id `com.stawnprecision.qcms`).
3. Connect the iPhone / iPad, choose it at the top, press **Run**. (First time on the device: Settings → Privacy & Security → Developer Mode → On.)
4. For colleagues: create the app in App Store Connect (bundle id `com.stawnprecision.qcms`, name STAWN QCMS), then
   `echo YOURTEAMID > ~/.stawn_apple_team_id` and `./BUILD_STAWN_QCMS_iOS.command testflight` → TestFlight → invite testers.
   `./BUILD_STAWN_QCMS_iOS.command adhoc` exports a signed .ipa for devices registered in your developer account.

### Fix: "Your team has no devices from which to generate a provisioning profile" / "No profiles for 'com.stawnprecision.qcms' were found"
Xcode makes a *development* profile only for devices registered in your team. Either:
- **Register your device:** connect the iPhone / iPad by cable → unlock → *Trust This Computer* → Settings → Privacy & Security →
  Developer Mode → On → in Xcode choose that device at the top (not "Any iOS Device") → Signing & Capabilities → **Try Again**.
  (Or add the UDID at developer.apple.com → Certificates, Identifiers & Profiles → Devices.)
- **Or skip devices completely with TestFlight:** Release builds sign with *Apple Distribution*, which needs no device.
  Create the app record in App Store Connect (bundle id `com.stawnprecision.qcms`), then run `./BUILD_STAWN_QCMS_iOS.command testflight`.
The build script now finds your Team ID from the signing certificate in the Keychain (or asks once) and saves it in
`~/.stawn_apple_team_id`, so the regenerated Xcode project keeps the Team.

GitHub workflow **STAWN QCMS iOS iPadOS App Build** compiles the app on every push (no signing).

## Without a paid Apple Developer membership (free Apple ID, R36)
1. Xcode > Settings > Accounts > + > Apple ID: sign in with your normal Apple ID ("Your Name (Personal Team)" appears).
2. `cd ~/QSMS/mobile/ios_stawn_qcms && ./BUILD_STAWN_QCMS_iOS.command free`
3. Connect the iPhone / iPad by cable, Trust, turn on Developer Mode, pick the device in Xcode, press Run.
4. On the device: Settings > General > VPN & Device Management > your Apple ID > Trust.
Limits: re-install every 7 days (connect + Run), max 3 free apps per device, no push notifications (bundle id
`com.stawnprecision.qcms.free`, push entitlement left out). The in-app bell / inbox, KPI dashboard and everything else work.

## iPad
The same app is universal (iPhone + iPad). Use any route above with the iPad connected / signed in to TestFlight.
