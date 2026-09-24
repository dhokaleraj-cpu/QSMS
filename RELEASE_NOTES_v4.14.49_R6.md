# QCMS 4.14.49 R6

Raw Material / Material Inward MetLab now uses Layout Master acceptance requirements only. Part Master section H is reserved for Final Dispatch MetLab.

For part 40257237, the live approved inward layout is 7237RMMETLAB01 (7237 RM INWARD METLAB), with HARDNESS 140–210. Final requirements previously leaked through copied RMTC data and historical-layout/fallback selection.

R6 corrects selection, saved-draft loading, save-time validation, finalization checks, and report export filtering. RMTC chemistry/Jominy remains reference-only. Existing stored report history is not bulk modified. If an old draft used a wrong-stage layout, select the correct inward layout and review it before saving.

Includes the NaN save fix and the preceding login, OSP save, PO approval, escalation, and GitHub Android workflow fixes. No new database migration or production Edge Function deployment.

Download the command to Downloads and run:
```bash
bash ~/Downloads/QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R6.command
```
The full source is embedded; the separate source ZIP is for reference/recovery. The updater backs up, installs, tests, commits and pushes main. A successful push starts QCMS First-App Android APK in GitHub Actions. Download QCMS-FIRST-APP-APK after the build succeeds.

See QCMS_NEW_CHAT_HANDOVER_v4.14.49_R6.md for technical details and the validation report for exact test results and limits.
