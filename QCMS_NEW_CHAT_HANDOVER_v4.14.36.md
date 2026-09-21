# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.36

### Controlled baseline
- **Application Version:** `4.14.36`
- **Build:** `41436-COMPLAINT-EMAIL-REGISTERS-REMINDERS-MOBILE-DRAWER`
- **Project path:** `/Users/dhokaleraj/QSMS`
- Preserve Git history, Streamlit Cloud deployment, Supabase production/master/transaction/quality/supply-chain data, attachments and secrets.
- Continue versioning from **v4.14.37+**.

### v4.14.36 Complaint Management
- Dedicated Customer Complaint Register and Supplier Complaint Register table-grid pages.
- Complaint grid exposes Complaint No., Date, Party, Part, Subject, Severity, Heat, Batch, Responsible, Target Closure, RCA, Open Actions, Email status/date, Complaint status and entry/user status.
- Complaint Email Configuration controls event routes, internal department/employee, CC, optional Customer/Supplier copy, templates, PDF/attachment options and email delivery register.
- Complaint email from entry/register/saved record requires employee review of recipients and explicit confirmation before queue/send.
- Automatic schedules: `COMPLAINT_CUSTOMER_OPEN_OVERDUE`, `COMPLAINT_SUPPLIER_OPEN_OVERDUE`, `COMPLAINT_FOLLOWUP_DUE`.
- Reminder controls include local hour, run-every-days cadence, due-within window, open/overdue flags, internal department/employee and optional external-party copy.
- `qcms-overdue-notifier` supports complaint schedules and enforces `run_every_days` cadence.

### Mobile UI baseline
- Android **v0.1.4**: compact dark native top bar, STAWN icon, slide-out drawer, bottom Home/Search/Complaints navigation, Streamlit main/module menus hidden inside native app.
- iPhone/iPad **v0.1.1**: same interaction model; universal iPhone/iPad Xcode project; IPA requires Apple signing/team on macOS Xcode.
- Do not expose service-role keys in mobile binaries. Existing QCMS login/RLS/permission/audit rules remain authoritative.

### Preserved v4.14.35 and earlier
- PO confirmation reminder guard, supplier-safe PO print, approval watermark on PDF/Excel, individual multi-PO ZIP, portrait T&C, PO edit/approval controls.
- RMTC supplier de-duplication, Bend Test, Global Search, OSP genealogy, MetLAB boundary, calibration, standard room, NPD/APQP, complaint media/CAPA, permissions/audit.

### Deployment rule
Every release remains one self-contained macOS `.command` updater with backup, complete compilation/readiness/phase verification/pytest, Git commit/push and remote SHA verification. Required Supabase migration/Edge Function updates should be automatic or pre-applied as part of controlled packaging whenever possible; do not request manual SQL unless unavoidable.

### Verification
- Complete pytest suite: **538 passed**.
- Python compilation, online-readiness and phase verification passed before packaging.

### Live notification runtime
- Additive v4.14.36 Complaint notification migration was applied to the controlled Supabase project during release packaging.
- `qcms-overdue-notifier` **v6 ACTIVE** supports the new complaint reminder schedule keys and `run_every_days` cadence while preserving legacy complaint schedule aliases.
- No manual SQL step is required for this controlled release.
