# QUALITY CONTROL MONITORING SYSTEM (QCMS)

## Current controlled release — v4.14.48
Build `41448-PO-WATERMARK05-APPROVER-SESSION-STABILITY-ANDROID-EVERY-RELEASE`.

QCMS v4.14.48 changes the Purchase Order PDF watermark to exactly **5% opacity** and merges it underneath the page content. Approved PO page 1 resolves and prints the actual Employee Master approver identity plus the saved approval date/time; legacy approved POs can recover the approver through the stored approving profile linkage.

The website/Android refresh login bridge is stabilized so normal field clicks do not remount a changing authentication component or create duplicate/stacked Streamlit page regions. Browser-storage write/clear operations are fire-and-forget, the bridge is zero-height, and refresh uses the same-origin persistence cookie first.

Android **v0.2.3 / versionCode 14** preserves the compact v1.2-style native hamburger drawer with expandable submenus and auto-hide after route selection. The GitHub **QCMS Android Test APK** workflow now runs on **every push to `main`** and remains manually runnable, so every QCMS version can produce a verified Android test APK artifact.

The controlled database schema remains **v4.14.45**; v4.14.48 requires no new Supabase migration or manual SQL.

## Deployment
Use the self-contained `QSMS_LIVE_DEPLOY_UPDATE_v4.14.48.command`. It backs up the current project, protects local secrets/data, validates the embedded source, verifies the v4.14.45 public schema contract, runs compile/readiness/phase/full pytest, commits and pushes Git, and verifies the remote SHA. The push automatically triggers the GitHub Android APK workflow. For local Samsung installation, use `mobile/android_qcms/BUILD_AND_INSTALL_SAMSUNG.command`.

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
