# QCMS v4.14.45 — Shared Raw Source + Controlled Layout Identity

## Release identity
- Version: **4.14.45**
- Build: **41445-SHARED-RAW-SOURCE-LAYOUT-CONTROL**
- Previous controlled release: **4.14.44**
- Android: **v0.2.1 / versionCode 12 preserved unchanged**

## Part Master / Raw Material
- Supplier Price History remains **Part-scoped**. The same numeric price/rate is valid on different Part Master records; there is no cross-Part price uniqueness rule.
- Raw Material Details now include **Source Raw Forging / Casting Part**. For a Forging or Casting row, the user can select another ACTIVE Part Master as the common raw forging/casting source used to manufacture the current finished Part.
- The source Part must be in the same tenant, cannot be the same Part, and circular source genealogy is blocked.
- Target finished-Part genealogy remains intact even when several finished Parts use one common source forging/casting.

## Supply Chain / Purchase Orders
- Forging PO consolidation can group target finished Parts by their explicit Source Raw Forging / Casting Part.
- Supplier technical data, HSN, supplier forging identity, current price, and price history can fall back to the linked source Part when the target Part does not carry its own commercial row.
- Each finished Part allocation remains preserved in `supply_purchase_order_sources`.

## Inspection Layout Master
- Plan Number is now generated automatically as:
  **Inspection Stage + Process + Part Number + Layout Name**.
- New/edit layouts require Inspection Stage so the controlled identity can be generated consistently.
- QCMS permits only **one current layout** in the same Part + Inspection Stage + Process + Layout Type + Inward Type + Requirement Scope.
- Existing duplicates are preserved as history by superseding all but the highest-priority current row.
- Auto-generated `FINAL_METALLURGICAL` plans remain outside this uniqueness rule.

## Database / deployment
- New additive migration: `20260922070000_qcms_v41445_shared_raw_source_layout_scope.sql`.
- Updater **R2** first verifies the release contract through the public Supabase Data API using both `apikey` and `Authorization` headers with retry handling.
- The production QSMS v4.14.45 migration has already been pre-applied and verified. R2 contains a project-scoped, migration-SHA-bound pre-applied contract certificate, so a Mac without `SUPABASE_ACCESS_TOKEN` or `supabase login` can still complete safely.
- No manual SQL step or local Supabase CLI authentication is required for this release.
- Existing business records, attachments, secrets and Git history are preserved.

### Validation
- Python compile: **PASS**.
- Online readiness: **255 required files / 0 missing**.
- Phase verification: **PASS / 0 errors**.
- Complete pytest regression suite: **581 tests passed**.
