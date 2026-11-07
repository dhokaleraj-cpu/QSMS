# STAWN QCMS v4.14.49 R41: iPhone / iPad build fix, delete automatic reminders (web + Android 3.8.0 + iOS 1.4.0)

## Delete automatic e-mail reminders
- **Website:** Admin › Email Settings › **E1 · Delete automatic email reminders**.
  - Pick one or more reminders, enter your current QCMS password, tick the confirmation and press **Delete selected reminders**.
  - Their automatic e-mails stop for everyone.
  - To pause a reminder instead, switch off "Enabled" in section E.
- **Android app:** Admin › Email Settings › Automatic schedules › **Delete reminder** (password required).
- **PPAP and PO approval reminders stop too.** Deleting "PPAP Documents · Due / Overdue" stops the daily PPAP reminders. Deleting "Purchase Orders Pending Approval" stops the overdue-approval reminder e-mails as well as the digest. The updater uploads these two reminder functions to Supabase.

## iPhone / iPad app v1.4.0 (build 5)
- **Xcode signing error fixed:** "Your team has no devices… / No profiles for 'com.stawnprecision.qcms' were found".
  - `./BUILD_STAWN_QCMS_iOS.command device` installs on the iPhone / iPad connected by cable. It adds the device to your Apple Developer team, so the error goes away.
  - Release / Archive no longer forces "Apple Distribution". That setting clashed with automatic signing. TestFlight uploads are still signed for distribution.
  - The Team ID is now read from Xcode › Settings › Accounts.
- **Privacy manifest** added. Apple requires it for TestFlight / App Store uploads.
- **New modules:**
  - **Native lists:** Indirect Purchase (POs, requisitions, GRN, items, stock ledger), PPAP Document Manager and ECN / PCN Register.
  - **Website pages inside the app:** RMTC QR Codes, OSP inspection queues, Inventory reports, My Dashboards, Licence & Company and Automatic Email Reminders.
- **RMTC print PDF:** the QR is the public link (no login).
- **GitHub iOS build check:** now runs on macOS 15 / Xcode 16 and also compiles the Release device build.
