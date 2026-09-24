# QCMS/QSMS handover — 4.14.49 R6

## Authoritative baseline
- R6 incorporates R4 stability/GitHub workflows, R5 NaN serialization, and R6 MetLab stage isolation.
- Local project: /Users/dhokaleraj/QSMS; deployment branch: main.
- Keep VERSION 4.14.49 and compatibility build 41449-ANDROID-SINGLE-NATIVE-DRAWER-V12. Release revision is R6.
- Schema baseline remains 4.14.45. This release performs no SQL migration, production-data cleanup, or Edge Function deployment.
- Preserve Git history, Streamlit Cloud, Supabase data, local secrets, and attachments.

## User requirement
Part Master section H (Metallurgical Requirements) is used ONLY for Final Dispatch MetLab, immediately before part dispatch. Raw Material / Material Inward MetLab inspection must use its selected approved Layout Master layout only. This applies to all parts, including 40257237.

## Live evidence — 24 September 2026, read-only
Part 40257237 has an approved GENERAL/MATERIAL_INWARD MetLab layout:
- Plan number: 7237RMMETLAB01
- Name: 7237 RM INWARD METLAB
- Characteristic: HARDNESS; lower 140; upper 210.
An approved OSP case-carburizing layout also exists. The query found no approved FINAL_METALLURGICAL layout for this part; use the existing Part Master generate/approve workflow when a final dispatch report is required.
Legacy RMTC requirement records contain final criteria including case depth, surface/core hardness, and ENP requirements. The old inward screen copied those into editable acceptance criteria, despite filtering the main layout correctly.

## R6 changes
- InspectionService recognizes raw-material reports by RAW_MATERIAL_STAGE/MATERIAL_INWARD scope or inward_lot_id.
- Only GENERAL/MATERIAL_INWARD MetLab layouts qualify for raw-material selection. No fallback to Final/OSP when an inward layout is missing.
- Final Dispatch selection no longer falls back to a raw-material layout.
- Wrong-stage historic layouts are not allowed to bypass the raw-layout filter. Editable drafts can select the proper inward layout; review results and save.
- Inward result rows are rebuilt from Layout Master. Existing measurements are restored only by matching characteristic ID, without copying old specification limits.
- RMTC chemistry/Jominy are read-only references. RMTC and Section H data do not populate editable inward acceptance requirements.
- Save and export paths filter inward results to selected layout characteristic IDs and clear legacy non-layout result sections. Case-depth data is excluded when the inward layout has no applicable case-depth characteristic.
- Final-scope layouts are rejected on save outside FINAL_DISPATCH_STAGE, including OSP.
- Finalization of a legacy inward report with non-layout criteria requires review and draft save first.
- Section H is explicitly labeled Final Dispatch Only in Part Master. RMTC template generation no longer imports Section H; separate raw-material heat-treatment details remain available for certificates.
- Existing database reports are not bulk rewritten. Export uses a filtered copy; the original remains stored until an authorized edit/save. Wrong-stage historic reports require controlled review before export/finalization.

## R5 fix retained
core/repository.py _json_ready recursively maps missing numeric/pandas values to null, preserves finite values, strings, zero and false, and rejects infinity with a clear message. Applies to nested MetLab rows, create/update, bulk saves and RPC parameters. The original NaN HTTPX JSON error was reproduced and a strict-JSON regression suite added.

## Earlier fixes retained
Cookie-only login restoration; disabled duplicate Components-v2 authentication surface; PO quantity formatter; queued OSP Edit Existing transition before widget creation; compact case-depth not-applicable caption; overdue employee/threshold controls; separate single-WebView Android recovery client and GitHub workflow.

## Files and deployment
Run only QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R6.command. It embeds the full controlled source; no ZIP extraction or separate R5 patch is needed. The updater creates a backup/safety stash, installs source, preserves configured secrets/data directories, runs compile/readiness/phase/focused/full tests, commits, pushes main, and verifies remote SHA. No force push.

Command:
```bash
bash ~/Downloads/QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R6.command
```

GitHub workflow: QCMS First-App Android APK. Artifact: QCMS-FIRST-APP-APK. APK: QCMS_Mobile_FIRST_APP_v1.0.2_TEST.apk. CI uses Java 17/API 35, so the obsolete local Apple Java plugin is not required.

## Deployment limits and acceptance
Local tests and packaging do not establish a successful live deployment or Android build. After updater success, wait for Streamlit Cloud deployment. Check part 40257237 Raw Material MetLab against layout 7237RMMETLAB01: only its hardness criterion (140–210) should be used; no Section H case depth/plating criteria. Save and reopen a draft, then check PDF/Excel. Final Dispatch must use an approved Final Metallurgical layout generated from Section H. Test browser refresh/login and Android navigation after installing the GitHub APK.

Do not mass-edit old approved reports or redeploy older bundled Edge Functions. Retain the updater backup and safety stash until acceptance is complete. Deployment failures should be diagnosed from the exact terminal log, not bypassed by skipping tests.
