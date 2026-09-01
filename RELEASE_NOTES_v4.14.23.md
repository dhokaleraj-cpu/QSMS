# QCMS v4.14.23

Build: `41423-SOURCE-ONLY-DEPLOY-RMTC-MASTER-DELETE`

Source-only deployment recovery. No new Supabase schema migration. Requires the already-live v4.14.22 contract.

- Supabase online recheck is non-blocking for this source-only release.
- Same-Heat Add New RMTC/TC gets a fresh selector/form nonce and blank certificate state.
- Master Data Centre New Record opens blank forms.
- Transaction delete routing fixes OSP/MetLAB/Dimensional and all controlled transaction roots.
