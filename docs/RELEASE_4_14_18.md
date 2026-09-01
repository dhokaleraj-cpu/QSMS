# QCMS v4.14.18 — User/Role/Department Permissions, Audit, PDF and Employee Recovery

Build: `41418-PERMISSIONS-AUDIT-EMPLOYEE-OSP-RMTC-METLAB-RLS-PDF`

## Controlled fixes
- Fixes the Employee Master Streamlit multiselect crash by retaining legacy/custom authority values in the option list.
- Fixes Users & Access parsing of the deployed nested `profile` / `employee` payload so saved roles no longer appear as VIEWER and Employee links remain selected.
- User administration no longer overwrites Employee Master email with login email and blocks accidental employee unlink unless explicitly confirmed.
- Safely relinks only unlinked employees that have a unique exact email match to one unused active QCMS profile.
- Safely restores an overwritten Employee Master email only when the earliest audited employee email proves the correct value and matches the currently linked profile.
- Adds Top-level Authority so the highest authorised employee can intentionally have no Reports-To.

## Permission model
Effective permissions are now shared between Streamlit and Supabase/RLS:
`ADMIN → explicit User override → Role default → Department default → legacy role fallback`.

Supply Chain PO header/item/source/opening-stock tables now map to `SUPPLY_CHAIN`, fixing the case where Create permission was visible but PO submission was rejected by RLS.

Sections support View / Create / Edit overrides. No section override means the section is visible by default when the parent module is viewable. Sensitive Part Master Price History and Supplier Technical Data are also guarded at the Data API/RLS layer.

## OSP, RMTC and inspection fixes
- Fixes Standalone MetLAB/Dimensional Save 403 by making inspection INSERT/UPDATE RLS use the same effective module Create/Edit permissions shown in Users & Access.
- OSP Transactions now have password-confirmed Delete/Archive controls for erroneous OSP inward receipts and parent OSP jobs. Deletion is permission-controlled, reverses the source allocation, recalculates receipt totals/status and blocks deletion once quality/downstream production genealogy exists.
- The same Heat Number can have another QCMS RMTC with a different Supplier RMTC Number while reusing the established Internal Heat Code. After approval, each RMTC remains independently selectable in Material Inward and shares the Heat genealogy/global balance.

## Audit and records
- Database CREATE / UPDATE / DELETE audit is normalized across tenant-scoped records with actor capture.
- Page/module/section and repository actions are recorded in the QCMS user activity register.
- Admin → Users & Access includes Activity and Record Change Audit registers with PDF download.
- Records Centre includes password-protected master deletion and a Universal PDFs tab for business registers and individual records.

## Live User Admin service
- `qsms-user-admin` Edge Function v2 is compatible with both flat and nested user payloads, preserves Employee Master email, and requires explicit employee unlink confirmation.

## Deployment safety
- Additive migration only; no production/master/quality/RMTC/OSP/Supply Chain transactional reset.
- One `.command` updater backs up, preserves Git/secrets/data folders, compiles, verifies, runs full pytest, verifies/applies Supabase schema, pushes the existing branch, and verifies local/remote SHA.
