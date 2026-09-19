# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.33

### 1. Authoritative controlled baseline
- **Application Version:** `4.14.33`
- **Build:** `41433-PO-PORTRAIT-TERMS-BATCH-PRINT-EMAIL-ANDROID-SDK`
- **Project path:** `/Users/dhokaleraj/QSMS`
- **Database schema baseline:** `4.14.28` (already applied)
- Preserve existing Git repository/history, Streamlit Cloud deployment, Supabase production data, attachments and secrets.

### 2. v4.14.33 Purchase Order print
- Supplier-facing PO remains customer-identity-safe.
- Part Master Part Description remains printed.
- Terms & Conditions are **portrait A4 only**.
- The controlled FSI/703/F04 2023 terms are compacted by moving visible content into otherwise unused white space; no landscape terms pages are created.
- The current 12 physical source terms pages compact to about 7 portrait A4 terms pages while retaining visible clause wording/order.

### 3. Batch Purchase Order print/email
- Purchase Order PDF workspace contains **Batch Print / Email Multiple Purchase Orders**.
- Multi-select POs and choose 1-5 physical copies per PO.
- One combined PDF is produced for print.
- Batch email sends each selected APPROVED PO separately to its own Supplier email with its generated controlled PO PDF.
- Unapproved, cancelled or missing-Supplier-email POs block email only; batch print remains available.
- Existing single-PO email remains available.

### 4. Android Samsung test
- QCMS Mobile helper is v0.1.1.
- Missing `~/Library/Android/sdk` no longer immediately fails. The helper bootstraps Google's Android CLI, installs Platform 35 / Build Tools 35.0.0 / Platform Tools, builds the debug APK, detects the authorised Samsung device with ADB and installs using `adb install -r`.
- Mobile remains a secure shell around the live QCMS HTTPS application; no Supabase service-role key is embedded.

### 5. Preserved controlled functions
- Preserve v4.14.32 controlled Raw Material Types: Forging, Round Black Bar, Casting, Bright Bar, Ground Bar.
- Preserve PO Entry / Order List / Edit / PDF / Approval-Supplier Confirmation subtabs.
- Preserve pre-approval editing, reapproval after approved-PO revision, non-blocking Supplier Confirmation, Cancel & Reissue, HSN/SAC, technical data, price history and source genealogy.
- Preserve RMTC supplier de-duplication, Bend Test, Global Search, OSP genealogy, MetLAB boundary, complaints, calibration, standard room, NPD/APQP and all existing permission/audit controls.

### 6. Deployment rule
Every release remains one self-contained macOS `.command` updater with backup, source replacement, dependency verification, compile, online-readiness, phase verification, complete pytest, Git commit/push and remote SHA verification. Do not ask for manual Supabase SQL unless a future change genuinely requires schema modification.

### 7. Next version
Continue from **v4.14.34+**.
