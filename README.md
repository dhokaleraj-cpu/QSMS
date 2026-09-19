# QUALITY CONTROL MONITORING SYSTEM (QCMS)

## Current controlled release — v4.14.32

Build `41432-PO-PRINT-COMPACT-RM-TYPES-ANDROID-TEST`.

v4.14.32 makes the supplier-facing PO safer and more compact: Customer identity/name is removed from the print, Part Master **Part Description** is added, Customer PO Number/Position remain as source references, and the controlled Standard Terms are imposed two-up on landscape A4 to reduce the terms section from 12 to 6 physical pages. Part Master Raw Material Type is controlled to **Forging, Round Black Bar, Casting, Bright Bar, Ground Bar**. The release also includes an Android QCMS test shell and Mac build/install helper for Samsung testing.

Required live database baseline remains v4.14.28; v4.14.32 adds no schema migration.

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
- Required live database baseline remains v4.14.28; v4.14.30 adds no schema migration.
- Online Supabase baseline recheck is informational/non-blocking and cannot prevent Git/Streamlit source deployment.
- Existing production/master/RMTC/OSP/Supply Chain data and local secrets are preserved.
