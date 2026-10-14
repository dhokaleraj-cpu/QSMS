# QCMS Android app v2.0.0 (native) - QCMS R29

Native Android app built from the approved R28 designs (Teal Material). Framework-only Java
(no third-party libraries), minSdk 26 (Android 8), targetSdk 35 (Android 15).

## Screens
| Tab | What it does |
|---|---|
| Login | Email + password (Supabase Auth), keep me signed in, fingerprint / face unlock, locks after 15 min in background |
| Home | KPI tiles (POs awaiting approval, supplier confirmations, open customer orders, calibrations overdue / due 30 days, deletion requests for Admin) + "Needs your action" list + quick-entry button |
| Orders | Purchase Orders: Pending / Approved / Cancelled / All with counts, search, swipe a pending card right to approve. PO screen: header, Customer Orders on the PO, scrollable line grid, totals, print-section tick-boxes, "Approve & send to supplier" or "Approve, do not send", Cancel PO with reason. Customer Orders: search + stage tracker |
| Inspect | OSP dimensional / MetLAB, dimensional, MetLAB, bend test, inward, RMTC, standard room, complaints - the controlled QCMS forms inside the app with camera photo upload |
| Assets | Quality assets with Valid / Due / Overdue status, filters (overdue, due 30 d, gauges, instruments), asset detail + calibration history grid |
| More | Part Master RM details viewer (frozen-pane grid), global search, KPI dashboards, records, reports, security settings, sign out |

Every grid scrolls left / right and up / down with a fixed header row and first column.

## Security
* The user's own Supabase login is used for every call: the same Row Level Security and
  module permissions as the website. Only the public *publishable* key is in the app.
* The password is never stored. The refresh token is encrypted with an AES-256 key held in
  the Android Keystore. Admin deletion approvals ask for the password again.

## Build
GitHub builds it automatically on every push to main that changes `mobile/android_qcms_app`
(workflow **QCMS Native Android App APK**, artifact **QCMS-NATIVE-APP-APK**, file
`QCMS_App_v2.0.0.apk`). The test APK is signed with the fixed key `app/qcms-debug.keystore`,
so a new APK installs over the previous one without uninstalling.

Install on the phone: download the artifact zip from GitHub → Actions → latest run, unzip,
open `QCMS_App_v2.0.0.apk` on the phone, allow "Install unknown apps" for the browser / Files app.
The older WebView app (`com.fourstar.qcms.test`) can stay installed; this app is `com.fourstar.qcmsapp`.
