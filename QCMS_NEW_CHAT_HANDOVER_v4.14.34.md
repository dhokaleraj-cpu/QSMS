# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Controlled handover — v4.14.34

- Application: 4.14.34
- Build: 41434-INDIVIDUAL-PO-PDF-ZIP-ANDROID-APK-BUILD
- Previous controlled source: 4.14.33
- Project: /Users/dhokaleraj/QSMS
- Database contract: inherited v4.14.28; no new migration or live DB verification in this release.
- Preserve Git, secrets, runtime files, production data, permissions, approvals and all prior working features.

## Latest user requirements
Batch PO print must return individual files, not one combined inter-PO PDF.
User requests an actual Android APK for Samsung testing, not only the project ZIP.

## Implemented PO change
purchase_order_pdf_files() creates one PDF per saved PO, with its own portrait T&C.
purchase_order_files_zip_bytes() packages exactly those bytes into a safe flat ZIP.
Copies per PO 1–5 stay inside each corresponding PO file. Duplicate id selections
are removed. Distinct ids with the same display number receive collision-safe names.
No missing/no-items selected PO is silently skipped. The PDF workspace provides
both the bulk ZIP and individual PDF buttons. Batch emails remain separate per supplier.
Do not return the combined batch helper to this UI.

## Android status — do not overclaim
Android source is v0.1.2, debug application id com.fourstar.qcms.test.
No APK was compiled here: SDK absent and download attempts failed.
.github/workflows/qcms-android-test-apk.yml builds after mobile-source pushes or manual dispatch,
runs assembleDebug/lintDebug, checks signatures/alignment/package/version, then uploads a test APK artifact.
This workflow has not yet been executed/verified on the user's GitHub repository.
Repository Actions policy/build-minute limits and push permission for workflow files apply.
The optional Mac BUILD_APK_ONLY.command writes a successful build to Downloads, no phone required.
The mobile app is an online WebView shell, not a native/offline replacement. Production
signing still requires a company-controlled key. Test signing cache is not a durable signing system.

## Deployment
Single self-contained macOS updater: backup/safety stash, source install, compile,
readiness/phase checks, complete pytest, existing-branch commit/push, remote SHA check.
No manual SQL. Preserve runtime paths and Android local build state.
Do not claim live DB/Edge/cron verification when only inherited metadata is available.
Continue development from v4.14.35+.
