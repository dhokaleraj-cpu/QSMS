# QUALITY CONTROL MONITORING SYSTEM (QCMS)

## Current controlled release — v4.14.44
Build `41444-ANDROID-NATIVE-MENU-SUBMENU-RESTORE`.

Android **v0.2.1 / versionCode 12** restores a permanent native QCMS top bar with a Menu button. The button opens and closes Streamlit's official grouped sidebar inside the existing authenticated WebView, so page selection remains Streamlit-owned and does not use hard WebView route reloads.

The Android-only CSS override restores the Streamlit sidebar and its collapsed control after the desktop global style hides them. Sidebar module groups are expanded for immediate access, and the active module's QCMS sub-menu is restored in a phone-friendly two-column layout. The obsolete Home/Search/Complaints bottom footer remains removed.

The dynamic Android APK version/signature verification introduced in v4.14.39 remains preserved. QCMS v4.14.44 requires no new Supabase schema migration; the controlled database baseline remains v4.14.36 and all existing production data, permissions, attachments, approvals and audit history are preserved.

## Deployment
Use the self-contained `QSMS_LIVE_DEPLOY_UPDATE_v4.14.44.command`. It backs up the current project, protects local secrets/data, validates the embedded source, runs compile/readiness/phase/full pytest, commits and pushes Git, and verifies the remote SHA. Then build/install Android v0.2.1 using `mobile/android_qcms/BUILD_AND_INSTALL_SAMSUNG.command`.

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
