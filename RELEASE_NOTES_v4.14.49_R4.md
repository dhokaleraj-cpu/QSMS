# QCMS 4.14.49 R4

R4 includes the R3 cookie-only login restoration, local PO quantity formatter, and compact MetLab case-depth caption. OSP post-save mode changes now occur before widget creation on the next rerun, avoiding the Streamlit session-state mutation error after database save.

The Android test workflow validates either the native or classic source architecture. The recommended recovery build remains QCMS First-App Android APK (single WebView; website navigation). Both workflows reject competing native navigation in classic sources. GitHub builds with Java 17 and Android API 35.

User Access > Module Approval Routes now exposes automatic reminders and the overdue-hours threshold for each responsible employee/level. Email Settings also exposes the existing optional schedule escalation employees and thresholds. PO worklist Level 2 uses the configured route, not the approver's manager.

Production verification: dedicated PO reminder cron is enabled hourly; 10 PO_APPROVAL_OVERDUE emails recorded SENT in the last 3 days. Existing levels 1 and 2 use EMP-0024 at 24 and 48 hours. Choose a different employee in Level 2 if required. Live Edge Functions were read and synchronized into the source archive, not redeployed. Production schema already has the fields; no database migration is performed.

Validation: complete Python suite 613 passed, 1 skipped; phase check zero errors; readiness 268 files, zero missing. Native/classic workflow guards executed, including rejection of conflicting code. No live UI acceptance test or GitHub APK build was performed in this workspace. The updater reruns checks before commit/push.

Run the R4 command from Downloads. A successful main push triggers QCMS First-App Android APK. Download artifact QCMS-FIRST-APP-APK. The local obsolete Apple Java plugin is not used. Preserve the backup and safety stash until acceptance testing is complete.
