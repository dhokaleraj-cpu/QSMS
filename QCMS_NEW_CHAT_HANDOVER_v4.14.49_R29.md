# QCMS v4.14.49 R29 — native QCMS Android app v2.0.0 + R28 database fix

- **New native Android app (QCMS v2.0.0)**, built from the approved R28 designs (Teal Material):
  Login with fingerprint / face unlock and 15-minute lock · Home KPI tiles + "Needs your action" ·
  Purchase Orders (Pending / Approved / Cancelled, swipe to approve, PO preview with lines grid, totals,
  print-section tick-boxes, approve & send / do not send, cancel with reason) · Customer Order stage
  tracker · Inspect (controlled QCMS entry forms with camera upload) · Quality Assets with
  Valid / Due / Overdue and calibration history · Part Master RM grid · Admin deletion approvals.
  Every grid scrolls left/right and up/down with frozen header and first column.
- Same login, Row Level Security and permissions as the website (only the public publishable key is in the app;
  the password is never stored; session key in Android Keystore).
- GitHub builds the APK automatically (workflow "QCMS Native Android App APK", artifact QCMS-NATIVE-APP-APK,
  file QCMS_App_v2.0.0.apk). Fixed test signing key: new APKs install over the old one.
- PO Approval page accepts `?po=<id>` so the app opens the exact PO for the PDF / email preview.
- **R28 database fix:** the automatic R28 recovery stopped on live data ("material_section_name" empty in
  very old history rows). Empty values now get the default "Primary Raw Material" and every restored row,
  price row and Jominy row is applied one by one (a bad row is skipped, never stops the whole update).
  The updater applies it automatically.

## Handover notes
- Native app source: mobile/android_qcms_app (Java, framework only, package com.fourstar.qcmsapp, minSdk 26,
  target 35). CI: .github/workflows/qcms-native-app-apk.yml. Old WebView app (mobile/android_first_app) unchanged.
- Sandbox has no Android SDK / Google Maven: Java sources were compile-checked against API stubs only;
  the real build + lint runs in GitHub Actions.
- Supabase URL + publishable key are BuildConfig fields in app/build.gradle.
