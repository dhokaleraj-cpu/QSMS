# QCMS NEW CHAT CONTINUATION — v4.12.1

Date: 19-Aug-2026

## Baseline
- Current application version: **4.12.1**
- Build: **4121-MASTER-DRIVEN-STANDALONE-REPORTS**
- Stack: Streamlit + Supabase/PostgreSQL, GitHub `main` deployment to Streamlit Cloud.
- Continue all existing QCMS modules and historical behavior; this release is additive.

## Non-regression rules
1. Never delete/reset production data, users, permissions, attachments, transaction IDs or existing report history unless explicitly requested.
2. Supabase migrations must be additive/backward-compatible.
3. Existing linked RMTC / Material Inward / OSP / Final Inspection workflows remain available. Standalone reports are an additional entry path.
4. Controlled A4 portrait report layout, page footer/version, record-level PDF printing and audit traceability must remain.
5. Part Master is the controlling source for report master data; avoid duplicate report-specific master data.

## Standalone report logic — v4.12.1
- User selects Part Number first.
- Auto-populate/display from Part Master: Part Name, Customer, Material Grade, Drawing Number and Revision.
- Supplier selection is master-driven; approved Part-Supplier links are preferred.
- Header traceability includes Report No/Date, Heat Number, Heat Code, Supplier/HT/OSP Batch Number, Internal/FSI Batch Number, Supplier Invoice/Reference, Quantity, Sample/Lot Reference and Supply/Process Condition.
- OSP Stage: list only OSP process groups configured for the selected part; show process specification/drawing/revision; automatically select the approved layout generated from that Part Master OSP process.
- Final MetLAB: automatically prefer the Final Metallurgical layout generated from Part Master Metallurgical Requirements.
- MetLAB retains four microstructure photographs and prepared/approved sign-off.

## Database migration
Apply `supabase/migrations/20260819170000_qcms_master_driven_standalone_reports_v4121.sql`. It only adds report context columns/indexes and master-context triggers; it does not delete/reset existing data.

## Laboratory report reference used
The supplied MLAB workbook was used as the structural reference for Part/Customer/Supplier, Material, Heat/Batch, quantity, condition/reference, result section, microstructure and sign-off information.
