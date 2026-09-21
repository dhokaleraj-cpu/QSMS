# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.37

### 1. Controlled baseline
- **Application Version:** `4.14.37`
- **Build:** `41437-MOBILE-FULL-NAV-COMPLAINT-CARDS-PO-APPROVAL-DRAFT-EMAIL`
- **Project path:** `/Users/dhokaleraj/QSMS`
- Preserve Git history, Streamlit Cloud deployment, Supabase production/master/transaction/quality/supply-chain data, attachments and local secrets.
- Continue versioning from **v4.14.38+**.

### 2. Complaint dashboard cards
- Customer and Supplier Complaint status views use responsive dashboard cards like Supply Chain status cards.
- Each card shows Complaint No., party, subject, target date, severity, status, open-action count and compact workflow-stage status for Complaint → Containment → Root Cause → Corrective Action → Verification → Closure.
- Detailed Customer Complaint Register and Supplier Complaint Register table grids remain available separately.

### 3. Complaint email / PDF / party copy
- Complaint email supports the controlled Complaint PDF generated from the exact saved complaint.
- Active complaint photographs/supporting documents can be attached through the standard notification attachment manifest.
- Entry email, saved-record email and register email provide an explicit **Send copy to Customer/Supplier** choice before the recipient confirmation dialog.
- The selected Party Master/Responsible email is added only when this control is enabled.
- Complaint Email Configuration, templates/routes, manual send confirmation, delivery outbox and automatic open/due/overdue/follow-up reminder schedules remain controlled.

### 4. Purchase Order approval worklist
- Purchase Order → Approval / Supplier Confirmation begins with a **Pending Approval** KPI/count and table-grid worklist.
- Grid shows PO, Supplier, Parts, Qty, dates, requisitioner, resolved approver/email/level, value and status.
- Multi-select Pending Approval POs and choose **Email Selected Draft POs to Approver**.
- Each PO is sent separately to its resolved approver after a confirmation dialog with its controlled **PENDING APPROVAL** watermarked draft PO PDF and configured controlled attachments.
- Supplier Confirmation does not block PO edit; existing reapproval/self-approval/genealogy controls remain preserved.

### 5. Native mobile UI baseline
- **Android 0.1.5** and **iPhone/iPad 0.1.2** use the STAWN application icon.
- Compact native top bar + hamburger drawer + expandable module groups/submenus + fixed bottom Home/Search/Complaints navigation.
- Native WebViews always request `native_mobile=1` and use platform-specific QCMS mobile user-agent strings.
- In native mode `streamlit_app.py` renders QCMS **content only**: desktop shell/header/global-search strip/left rail/module submenu/footer are not rendered.
- Streamlit native mode persists through session/page switches and also detects the QCMS mobile user-agent.
- No Supabase service-role/admin key is embedded in mobile clients.

### 6. Complaint notification runtime
- v4.14.36 additive Complaint email configuration migration is already the database baseline.
- `qcms-overdue-notifier` **v6 ACTIVE** supports Complaint Customer/Supplier open-overdue and Follow-up schedules plus `run_every_days` cadence.
- v4.14.37 itself adds no new schema requirement; do not ask for manual SQL.

### 7. Preserved functionality
- v4.14.35 PO confirmation reminder guard, supplier-safe PO print, PDF/Excel approval watermark, individual multi-PO ZIP.
- Portrait T&C, Part Description, PO edit/approval controls, RMTC supplier de-duplication, Bend Test, Global Search, OSP genealogy, MetLAB boundary, Complaints CAPA/media, Calibration, Standard Room, NPD/APQP, permissions and audit.

### 8. Deployment rule
Every release remains one self-contained macOS `.command` updater with backup, dirty-Git protection, source replacement, dependency verification, compile, online-readiness, phase verification, complete pytest, Git commit/push and remote SHA verification. Required Supabase changes should be automatic or pre-applied; never request manual SQL unless technically unavoidable.

### 9. Mobile binary rule
- Android source/build helpers must always be supplied; include APK only when actually compiled and signature-verified.
- iPhone/iPad source/build helper must always be supplied; include IPA only when actually signed/exported with the user's Apple Team/provisioning.
- Never rename a source ZIP as APK/IPA or imply an unsigned/unbuilt binary is installable.
