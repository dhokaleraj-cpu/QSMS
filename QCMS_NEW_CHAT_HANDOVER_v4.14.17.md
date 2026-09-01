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
Start all subsequent work from v4.14.17. Use targeted changes; never rebuild from an older archive. Continue versioning v4.14.18+.
