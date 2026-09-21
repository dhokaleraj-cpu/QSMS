# QUALITY CONTROL MONITORING SYSTEM (QCMS)

## Current controlled release — v4.14.37
Build `41437-MOBILE-FULL-NAV-COMPLAINT-CARDS-PO-APPROVAL-DRAFT-EMAIL`.

Complaint dashboard status is now card-based; Complaint email can attach controlled PDF/documents and explicitly copy the Customer/Supplier before confirmation. Purchase Order Approval has a Pending Approval KPI/table and multi-PO approver-email action with PENDING APPROVAL watermarked draft PDFs.

Native Android 0.1.5 and iPhone/iPad 0.1.2 render QCMS content-only inside the WebView and use the native expandable drawer plus fixed Home/Search/Complaints bottom navigation, eliminating the long Streamlit rails/submenus from the mobile app.

The v4.14.36 Complaint email/reminder database configuration and qcms-overdue-notifier v6 remain the controlled runtime baseline; v4.14.37 requires no additional schema migration.

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
