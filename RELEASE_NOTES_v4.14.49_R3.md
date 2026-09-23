# QCMS v4.14.49 R3 — Stability Hotfix + GitHub First-App APK

R3 keeps the controlled QCMS version/build at v4.14.49 / `41449-ANDROID-SINGLE-NATIVE-DRAWER-V12` while correcting runtime issues reported after deployment.

## Corrections

- Fixed Purchase Order Approval crash caused by undefined `_quantity_text`.
- Pending PO Approval worklist now shows pending days, escalation level, Level 2 employee and Level 2 email.
- Preserves the live automatic PO approval overdue notifier and configured approval-route escalation; R3 does not downgrade or redeploy the production worker.
- Fixed duplicate/blank login surface by removing the Components-v2 persistent-auth UI bridge and retaining the zero-size same-origin cookie/session restore path.
- OSP Dimensional / MetLAB draft save verifies returned database ID, preserves selected disposition, switches to Edit Existing on success and displays the real database error on failure.
- Replaced the large Case Depth Traverse not-applicable blue box with a compact caption.
- Added a dedicated First-App Android client v1.0.2 using one WebView and website-controlled navigation to avoid Android route translation back to Home.
- Added an automatic GitHub APK workflow on every `main` push. GitHub uses Temurin Java 17 and Android SDK 35, avoiding the user's obsolete local JavaAppletPlugin / Apple-Silicon incompatibility.

## Android artifact

Workflow: `QCMS First-App Android APK`

Artifact: `QCMS-FIRST-APP-APK`

APK: `QCMS_Mobile_FIRST_APP_v1.0.2_TEST.apk`

## Database

No schema migration. Existing schema v4.14.45 remains unchanged.
