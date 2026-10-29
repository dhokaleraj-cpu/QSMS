# QCMS Android app v3.0.0 (native, all modules) - QCMS R30

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
(workflow **STAWN QCMS Android App APK**, artifact **QCMS-NATIVE-APP-APK**, file
`STAWN_QCMS_v3.7.0.apk`). The test APK is signed with the fixed key `app/qcms-debug.keystore`,
so a new APK installs over the previous one without uninstalling.

Install on the phone: download the artifact zip from GitHub → Actions → latest run, unzip,
open `STAWN_QCMS_v3.7.0.apk` on the phone, allow "Install unknown apps" for the browser / Files app.
The older WebView app (`com.fourstar.qcms.test`) can stay installed; this app is `com.fourstar.qcmsapp`.

## v3.0.0 (R30)
Every QCMS module runs natively (tabs Home · Supply · Quality · Masters · More); no website pages are needed.
Grids are spreadsheet canvases: slide in all directions, pinch zoom, frozen header and first column. See RELEASE_NOTES_v4.14.49_R30.md.

## v3.1.0 (R31)
⇩ in the top bar of every screen: Download PDF, Download Excel (.xlsx), View PDF, Print, Email from QCMS (PDF + Excel attached), Share.

## v3.2.0 (R32)
App name STAWN QCMS; launcher icon from the STAWN logo mark (adaptive + monochrome).

## v3.3.0 (R33)
Website print-layout PDFs on the phone (MetLAB, Bend Test, Dimensional, RMTC, Material Inward, complaints, calibration, standard room, QC calculations, Universal record PDF for every other record); full report shown on the record; Reports Centre, Records Centre; global search bar at the top; About page (STAWN PRECISION PRIVATE LIMITED).

## v3.4.0 (R35)
KPI start dashboard after login (qcms_kpi_dashboard: pending tasks, cards, charts; Quality · Supply Chain · Production · NPD · Management,
auto-switch every 20 s, pauses 60 s after a tap; Home overview one tap away). Notification inbox + bell with unread count, Android
notifications every 15 min via JobScheduler (channels qcms_alerts / qcms_alerts_approval), WhatsApp alerts opt-in. Global search also uses
qcms_global_search and lists matching modules. Licence check (qcms_licence_status) with a STAWN licence screen; licence details in About.

## v3.5.0 (R37)
KPI drill-down: tapping a KPI card or a module infographic card (qcms_module_cards strip per department) lists the records behind
the number (qcms_kpi_records); a row opens the record natively (else the module / website page), hold a row for Print PDF.
Pending tasks open their record. "+" in the top bar: New transaction (native New form, else website entry page), New e-mail,
New query (Global Search) and Search & AI. Global search: hold a result for Print PDF (Preview / Save / Share; dedicated print
layout, Universal Record PDF for any other table). Asset and PO screens offer the print PDF too (also from the top-bar ⇩).
Cards also honour a server "drill" object (table + PostgREST filter) and, on older databases, a label -> key map with
client-side status filters. Supply / Quality / Masters / More tabs show the module infographic cards on top. "+" New transaction
only lists modules with Create permission; New query opens Global Search with the keyboard up; search results have a Results PDF.

## v3.7.0 (R39) - website parity
- STAWN Developer Console (developer only): licences, companies, company admins, any company's profile / logo, login cover photo, trial-data purge.
- Licence & Company; licensed company logo + employee photo in the top bar; app version only in My Account / About.
- Employee photo, reports-to / escalation / direct reports / approval routes.
- OSP: one Material Out + Returnable Delivery Challan form, register, record (Details / Print / Vendor returns), OSP queues.
- Indirect Purchase (POs, approval, requisitions, GRN, items, stock ledger); PO amendments with effective date; approved PO PDF saved + opened.
- PPAP Document Manager (packages, elements, documents, ZIP, send to customer, assignment e-mail with part details + drawings / specs).
- RMTC QR: PNG / JPEG / PDF / 100 x 60 mm label, Quality e-mail on approval; sections applicable; horizontal chemistry / Jominy grids with mm row.
- Part Processes with drawings / specs revisions, ECN / PCN (required when a drawing is replaced), ECN register, Part sections applicable.
- Module KPI cards, My Dashboards, Inventory & Stock reports, search / KPI / notifications open the exact record; department-first e-mail subjects.
- Parity matrix: mobile/ANDROID_WEB_PARITY.md (123 web routes: 120 native, 3 in-app web pages).

## v3.6.0 (R38)
Chemistry and Jominy are horizontal everywhere in the app: elements (C, Mn, Si, S, P, Cr, Ni, Mo, ...) and Jominy distances
(J1/16", J2/16", ...) are columns; Jominy also shows a Distance (mm) row (n/16 x 25.4 mm, J5/16" = 7.94 mm) so both scales are
visible. Applies to the RMTC, MetLAB, Material Grade and Part Master record views and to their print PDFs; wide grids wrap into
bands that fit A4 (ChemGrid.java).
