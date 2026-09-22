# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.45

### 1. Controlled baseline
- **Application Version:** `4.14.45`
- **Build:** `41445-SHARED-RAW-SOURCE-LAYOUT-CONTROL`
- **Project path:** `/Users/dhokaleraj/QSMS`
- Preserve Git history, Streamlit Cloud deployment, Supabase production/master/transaction/quality/supply-chain data, attachments and local secrets.
- Continue versioning from **v4.14.46+**.

### 2. Raw Material / Part Master rules
- Supplier Price History remains keyed by Supplier + Part + UOM/date (with Raw Material Detail as the strongest application identity). **The same numeric price is allowed on different Part Master records.**
- `part_raw_material_details.source_part_id` links a target finished Part's Forging/Casting row to another ACTIVE Part Master used as the common raw forging/casting source.
- The Source Raw Forging / Casting Part selector is available only for Raw Material Type **Forging** or **Casting**.
- Self-links, cross-tenant links and circular Part-source genealogy are blocked.

### 3. Shared forging/casting Supply Chain behavior
- `SupplyChainService.raw_source_context()` resolves the selected source Part and compatible raw row.
- Forging PO grouping prefers explicit source-Part identity; supplier forging part number remains the fallback grouping mechanism.
- Current supplier price and PO price history first use the target Part and then fall back to the source Part when target commercial history is missing.
- PO technical snapshots can inherit source raw technical data while preserving target finished-Part allocations/genealogy.

### 4. Inspection Layout control
- Layout Plan Number is controlled automatically as **Stage + Process + Part Number + Layout Name**.
- Inspection Stage is mandatory for manually maintained new/edit layouts.
- Only one current (`DRAFT`, `APPROVAL_PENDING`, or `APPROVED`) layout is allowed for the same Part + Stage + Process + Layout Type + Inward Type + Requirement Scope.
- Historical/retired rows may remain `SUPERSEDED`; `FINAL_METALLURGICAL` generated plans remain exempt.

### 5. Database baseline
- v4.14.45 adds the additive migration `20260922070000_qcms_v41445_shared_raw_source_layout_scope.sql`.
- The controlled updater uses `scripts/qcms_remote_schema_guard.py` to verify/apply this migration automatically and validates the public `qcms_release_contract_v41445()` marker.
- Do not ask the user to run manual SQL unless automatic migration is technically impossible in their environment.

### 6. Android
- Android remains **v0.2.1 / versionCode 12** from v4.14.44.
- Native top Menu + Streamlit grouped sidebar/submenu, session-safe no-hard-reload navigation, removed bottom footer, and dynamic APK/signature verification are preserved.
- This v4.14.45 release does not require an Android binary rebuild; the existing Android app receives the server/business-rule changes after Streamlit deployment.

### 7. Deployment rule
Every release remains one self-contained macOS `.command` updater with backup, dirty-Git protection, source replacement, automatic Supabase verify/apply when required, dependency verification, compile, online-readiness, phase verification, complete pytest, Git commit/push and remote SHA verification.

### Validation
- Python compile: **PASS**.
- Online readiness: **255 required files / 0 missing**.
- Phase verification: **PASS / 0 errors**.
- Complete pytest regression suite: **581 tests passed**.


### v4.14.45 updater R2 deployment guard
- Production QSMS schema `4.14.45` and `QCMS_V41445_FULL_READY` were pre-applied/verified before R2 was issued.
- R2 Data API verification sends both `apikey` and `Authorization: Bearer` headers and retries for schema-cache propagation.
- If the Mac cannot query the public Data API, R2 accepts only the bundled project-scoped certificate whose migration SHA-256 matches the embedded v4.14.45 migration.
- Therefore local `SUPABASE_ACCESS_TOKEN`, `supabase login`, and manual SQL are not required for this release.
