# QCMS / QSMS New-Chat Handover — v4.14.18

Authoritative release: **4.14.18**
Build: **41418-PERMISSIONS-AUDIT-EMPLOYEE-OSP-RMTC-METLAB-RLS-PDF**

Treat the self-contained v4.14.18 deployment command as the authoritative source. Preserve all production Supabase data, Git history, Streamlit deployment, masters, RMTC/OSP/quality/Supply Chain transactions, reports and previously working features.

## v4.14.18 additions
- User, Role and Department permission hierarchy uses ADMIN → USER → ROLE → DEPARTMENT → LEGACY precedence in both UI and database/RLS.
- Supply Chain PO tables map correctly to SUPPLY_CHAIN so assigned Create/Edit permissions authorize PO submission.
- Section overrides have View/Create/Edit; no row = default visible/inherit module.
- Employee Master legacy authority values cannot crash the multiselect.
- Top-level authority may have no Reports-To.
- User administration preserves employee email and existing Employee link unless explicitly changed; employee unlink requires an explicit confirmation.
- The deployed `qsms-user-admin` Edge Function v2 returns both flat and nested user/employee fields for compatibility and never copies login email into Employee Master.
- Conservative audit-backed recovery repairs provable employee links/email corruption only.
- Comprehensive record mutation audit and user page/module/section activity register.
- Password-protected master delete center.
- Universal controlled PDF download for business registers and selected records.
- Standalone MetLAB/Dimensional RLS Save 403 fixed by aligning DB INSERT/UPDATE policies with effective Create/Edit permissions.
- OSP Delete/Archive permission supports password-controlled OSP receipt/transaction deletion with source-quantity restoration and downstream safety blocks.
- Same Heat Number may carry multiple QCMS/Supplier RMTC records while one established Internal Heat Code is reused; approved records remain separately selectable for Material Inward.
- v4.14.18 Supabase migration is automatic/verified; never require manual SQL unless technically impossible.

## Deployment convention
One self-contained macOS `.command` release only. Backup before install, protect `.git`, `.venv`, `.env`, `.streamlit/secrets.toml`, uploads/logs/exports, run compile/readiness/phase/full pytest, verify/apply Supabase additively, commit/push existing branch and verify local/remote SHA.

## Previous baseline
The entire v4.14.17 handover remains non-regression history below.

# QCMS / QSMS New-Chat Handover — v4.14.17

## Authoritative baseline
- Product: QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
- Version: **4.14.17**
- Build: **41417-AUTO-MIGRATION-APPROVAL-ROUTES-MANIFEST-SYNC**
- Local project: `/Users/dhokaleraj/QSMS`
- Main app: `streamlit_app.py`
- Backend: production Supabase project `xxrxopzxzyjnzumrwuwy`
- Existing Git repository/branch and Streamlit Cloud deployment must be preserved.

## Controlled deployment rule
Every future release must remain one self-contained macOS `.command` updater that backs up the project, preserves `.git`, `.venv`, `.env`, `.streamlit/secrets.toml`, uploads/logs/exports and Supabase link state, verifies/applies required additive Supabase SQL automatically, compiles, runs readiness + phase verification + complete pytest, commits/pushes the existing Git branch and verifies remote SHA. Never reset production data.

## v4.14.17 delta
- Tenant-scoped writes fixed for Department Defaults, User Section Permissions, Approval Routes and Supply Stage Responsibilities.
- Admin → Users & Access includes Module Approval Routes.
- PO approval precedence: Configured Route → Reports-To Manager → different employee with Supply Chain Approve permission. Self-approval is blocked except Admin override.
- PO approval notification and PO register use the same approval target.
- Automatic remote Supabase schema guard verifies v4.14.16 baseline and applies the controlled v4.14.17 migration when missing.
- Deployment Manifest, README, release notes and build marker synchronized.

## Non-regression baseline retained
- Explicit user permissions override department defaults; department defaults override role fallback.
- Entry/Create → Validate/Review → Approve remain separate.
- Section-level confidentiality controls remain.
- PENDING_APPROVAL PO cannot be received.
- Cancel/reissue releases source allocations and preserves replacement linkage.
- RM PO item/print contains FSI Part Number, HSN/SAC, Raw Material Type, Material Grade and Section Size; RM PO excludes unrelated forging parameters.
- Supply Chain stage responsibility notifications and status-coloured Excel exports remain.
- Flow 1, Flow 2 and Flow 3 (FSI RM → Direct Production) remain traceable.
- RMTC, Material Inward, OSP, MetLAB, Dimensional, Part Master, NPD/APQP, complaints and reporting workflows remain preserved.

## Future instruction
Start all subsequent work from v4.14.18. Use targeted changes; never rebuild from an older archive. Continue versioning v4.14.19+.
