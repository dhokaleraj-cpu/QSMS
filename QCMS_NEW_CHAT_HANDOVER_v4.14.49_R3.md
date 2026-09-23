# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## New-Chat Handover — v4.14.49 R3 Stability Hotfix

### 1. Controlled baseline
- Application version remains `4.14.49`.
- Build remains `41449-ANDROID-SINGLE-NATIVE-DRAWER-V12` for compatibility with the controlled historical regression suite.
- Release revision: `R3`.
- Project path: `/Users/dhokaleraj/QSMS`.
- Database schema remains `4.14.45`; no migration is required by R3.
- Preserve Git history, Streamlit Cloud deployment, Supabase production data, attachments and local secrets.

### 2. Duplicate login / blank-page stability
- The Components-v2 browser-storage authentication bridge is disabled in R3 because it could leave a second login/page surface mounted during reruns.
- Persistent refresh authentication uses the same-origin zero-size cookie bridge and Supabase `set_session` restore path.
- The cookie restore is attempted before login UI rendering, so a normal refresh can restore the authenticated session without mounting an extra browser component.
- Logout still clears the persistent session.

### 3. Purchase Order approval crash
- `app_pages/supply_chain.py` now defines `_quantity_text()` locally before the Pending Approval worklist uses it.
- Fixes the Streamlit Cloud `NameError: _quantity_text is not defined` in `_pending_po_approval_rows`.
- Pending Approval rows now expose Pending Days, Escalation Level, Level 2 Employee and Level 2 Email for management visibility.

### 4. Pending PO approval overdue email
- Production `qcms-overdue-notifier` remains the authoritative live worker and is not downgraded/redeployed by R3.
- Existing automatic `PO_PENDING_APPROVAL` schedule remains daily and uses configured Supply Chain approval routes / escalation responsibility.
- Level 1 and Level 2 thresholds remain available through the notification schedule / approval-route configuration. R3 surfaces Level 2 responsibility in the PO worklist.

### 5. OSP inspection save reliability
- OSP Dimensional / MetLAB draft save now writes the selected disposition, verifies that a saved report ID is returned, and switches the screen to `Edit Existing` after successful save.
- If persistence fails, the UI now shows the actual save error instead of appearing to do nothing.

### 6. MetLAB Case Depth message
- When the approved layout has no Case Depth / Microhardness Traverse characteristic, the large blue information panel is removed.
- A compact `Not applicable for this approved layout` caption is shown instead.

### 7. Android — First-App recovery client
- A separate stable client is provided under `mobile/android_first_app`.
- Android version: `1.0.2`, versionCode `18`.
- Architecture: one WebView, website-controlled navigation, no native route translation and no `QCMSMobile/*` native-mode user agent.
- User agent: `QCMSClassicShell/1.0.2`.
- Current STAWN/QCMS application icon is included.
- The first-app client is intended to avoid the route conversion problem where every menu click landed on Dashboard/Home.

### 8. GitHub APK build — authoritative Android build path
- Workflow: `.github/workflows/qcms-first-app-apk.yml`.
- Workflow name: `QCMS First-App Android APK`.
- Runs automatically on every push to `main` and can also be started manually with `workflow_dispatch`.
- Uses Ubuntu + Temurin Java 17 + Android SDK 35, so the user's obsolete local Apple Java plugin is not used.
- Artifact: `QCMS-FIRST-APP-APK`.
- APK: `QCMS_Mobile_FIRST_APP_v1.0.2_TEST.apk`.
- GitHub verifies build, lint, APK Signature Scheme v2, zipalign and SHA-256 before artifact upload.

### 9. R3 validation
- Focused R3 regression: 5 passed.
- Complete suite in packaging environment excluding the single Streamlit-import-only module: 607 passed.
- `scripts/verify_phase1.py`: PASS / 0 errors.
- `scripts/check_online_readiness.py`: PASS / 268 required files / 0 missing.
- The updater runs the complete real pytest suite using `/Users/dhokaleraj/QSMS/.venv` before Git commit/push.

### 10. Deployment rule
Use `QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R3.command`. It creates a safety backup/stash, installs the controlled payload, preserves secrets/data, compiles, runs readiness + phase checks + complete pytest, commits/pushes, and verifies the remote SHA. The successful main push triggers the GitHub First-App APK build automatically.
