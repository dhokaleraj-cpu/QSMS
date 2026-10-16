# QCMS v4.14.49 R34 — NEW native STAWN QCMS app for iPhone and iPad (v1.0.0)

Native SwiftUI app (iPhone + iPad, iOS / iPadOS 16+), folder `mobile/ios_stawn_qcms`, bundle id `com.stawnprecision.qcms`.
Same Supabase login, data, permissions and print layouts as the website and the Android app.

Native in v1.0.0
- Sign in, Face ID / Touch ID unlock, Keychain session, auto-lock after 15 minutes
- Home with live counters, all 79 modules in Supply / Quality / Masters / More, global search bar at the top
- Every register (spreadsheet grid, search, status filters, Register PDF, CSV) and every record (details, child tables,
  photos & documents incl. upload, history, delete / deletion request)
- Website print-layout PDFs (MetLAB, Bend Test, Dimensional, Inward, RMTC, complaint, calibration, standard room, QC calc,
  Universal record PDF) with View · Save to Files · AirPrint · Email · Share; full report shown on the record
- Reports Centre, Records Centre, PO approve / cancel, Standard Room entry, My Account, About

Opened from the website inside the app (marked WEB): RMTC / Inward / MetLAB / Bend / Dimensional entry, OSP, Customer Orders
and PO creation, NPD / APQP, masters editing, admin, KPI dashboards, Report Builder.

Build: `mobile/ios_stawn_qcms/BUILD_STAWN_QCMS_iOS.command` (check · testflight · adhoc); GitHub workflow
"STAWN QCMS iOS iPadOS App Build" compiles it on every push. No database change. Android app unchanged (v3.3.0).
