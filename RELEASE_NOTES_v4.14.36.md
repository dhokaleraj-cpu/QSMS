# QCMS v4.14.36 Release Notes

**Build:** `41436-COMPLAINT-EMAIL-REGISTERS-REMINDERS-MOBILE-DRAWER`

## Complaint Management
- Added separate **Customer Complaint Register** and **Supplier Complaint Register** table-grid pages with search/filter controls, email status, RCA, open-action count, responsible employee, target closure, heat/batch and controlled record actions.
- Added **Complaint Email Configuration & Reminders** for complaint-specific routes, templates, department/employee routing, CC, optional Customer/Supplier copy, attachment/PDF controls and email delivery history.
- Complaint entry and register email sending uses the controlled **review To/CC + confirmation popup** before a message is queued.
- Added manual resend/send from a saved complaint record.
- Added automatic reminder schedules for Customer complaints, Supplier complaints and complaint follow-ups. Open/due/overdue selection, due-within days, cadence, local hour, department/employee and optional external-party copy are configurable.
- Hourly notification worker now respects `run_every_days` for all schedules and gathers Complaint-module due/overdue/follow-up records.

## Mobile app UI
- Android mobile source is **v0.1.4**. The long Streamlit main menu/submenu is hidden inside the app. Navigation is provided by a compact dark native top bar, STAWN icon, slide-out drawer and bottom **Home / Search / Complaints** bar, based on the supplied reference-video interaction pattern.
- iPhone/iPad universal source is **v0.1.1** with the same native drawer/bottom-navigation approach and STAWN icon.
- Existing live QCMS authentication, permissions, RLS and audit behavior remain the source of truth; mobile clients do not embed a Supabase service-role key.

## Preserved from v4.14.35
- Supplier PO confirmation reminder stop/pre-send guard.
- Supplier-safe PO print, PDF/Excel approval watermark, one-click ZIP with individual PO PDFs.
- Portrait Purchase Order terms, PO workspace/edit/approval behavior, Global Search, Bend Test, RMTC and all quality/supply-chain controls.

## Database
- Additive migration `20260921190000_qcms_v41436_complaint_email_register_mobile.sql` seeds complaint templates/routes/schedules without deleting business data or overwriting existing customized rows.

### Verification
- Complete pytest suite: **538 passed**.
- Python compilation, online-readiness and phase verification passed before packaging.

### Live notification runtime
- Additive v4.14.36 Complaint notification migration was applied to the controlled Supabase project during release packaging.
- `qcms-overdue-notifier` **v6 ACTIVE** supports the new complaint reminder schedule keys and `run_every_days` cadence while preserving legacy complaint schedule aliases.
- No manual SQL step is required for this controlled release.
