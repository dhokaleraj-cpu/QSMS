# QUALITY CONTROL MONITORING SYSTEM (QCMS)

## Current controlled release — v4.14.28

Build: `41428-OSP-BATCH-GENEALOGY-TWO-DAY-EXCEL`

This release strengthens OSP genealogy by carrying the QCMS/FSI Batch Number and Material Out remarks through Sample Receipt, OSP Dimensional, OSP MetLAB and OSP Inward; every OSP selector exposes Part Number + FSI Batch + Vendor Batch. Approved OSP layouts now synchronize the inspection-required flags so an approved Dimensional layout cannot disappear from the Sample inspection queue. It also adds every-two-day XLSX digests for overdue Customer Orders and Supply Chain pending/overdue lists. The live v4.14.28 database migration and overdue-notifier Edge Function are applied during controlled release packaging; the macOS updater performs source deployment without requiring Supabase CLI login or manual SQL.

## v4.14.25 controlled edit and exact-record reload
- Purchase Order register now provides **Edit Selected Purchase Order** for users with Supply Chain Edit permission.
- PO revision keeps Supplier and source Part identity controlled, protects received genealogy, refreshes current master snapshots when requested, recalculates commercial totals, returns the PO to approval, and requires supplier reconfirmation after approval.
- Master and transaction edit widgets are namespaced by selected record ID + saved update timestamp so selecting a record always reloads that exact saved record rather than previous Streamlit widget state.
- Reference Master learned suggestions always put the persisted saved value first during edit.
- Records Centre provides **Open Selected Record for Controlled Edit** and routes the selection to its owning module so module approval/genealogy controls remain enforced.
- Material Inward, OSP, NPD/APQP, Complaints, Supply Chain generic transactions and major master forms use record-specific edit state.
- PO page loading uses page memoization, bulk received/source calculations and cached confirmation/branch lookups to reduce repeated Supabase calls.
- When master data changes, new transactions use current master data. A controlled PO edited later can refresh its current master snapshots while the original/prior values remain traceable in the audit log.

## Deployment
- Source-only release; no new Supabase migration is required.
- Required live database baseline remains v4.14.22 / `QCMS_V41422_FULL_READY`.
- Online Supabase baseline recheck is informational/non-blocking and cannot prevent Git/Streamlit source deployment.
- Existing production/master/RMTC/OSP/Supply Chain data and local secrets are preserved.
