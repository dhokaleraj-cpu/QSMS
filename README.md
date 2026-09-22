# QUALITY CONTROL MONITORING SYSTEM (QCMS)

## Current controlled release — v4.14.39
Build `41439-ANDROID-CI-SIGNATURE-PERMANENT-FIX`.

Android 0.1.6 fixes the mobile menu login-loop by routing drawer selections through hidden Streamlit `st.page_link` elements instead of hard `WebView.loadUrl()` page loads. This keeps the existing authenticated Streamlit session alive while changing QCMS pages.

The Android fixed Home/Search/Complaints footer has been removed and mobile content now uses the reclaimed screen height. The top-bar hard-refresh control is also removed so an accidental full browser reload cannot drop the in-memory QCMS login.

Complaint dashboard cards, Complaint PDF/document email with optional Customer/Supplier copy, Purchase Order Pending Approval worklist/draft approver email, all permissions/audit controls and the v4.14.36 live database/notification baseline remain preserved. v4.14.39 requires no new Supabase schema migration. The Android CI/APK verification flow now derives version identity from Gradle and validates apksigner v2 without treating optional signature schemes as failures.

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
