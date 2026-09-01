# QCMS v4.14.23 Handover

Authoritative source release: **v4.14.23** / `41423-SOURCE-ONLY-DEPLOY-RMTC-MASTER-DELETE`.
Database schema baseline: **v4.14.22 / QCMS_V41422_FULL_READY** (no v4.14.23 migration required).

This release exists to unblock Git/Streamlit deployment after local Supabase Data API verification repeatedly failed despite the live schema already being verified. The updater must never request `supabase login`, `SUPABASE_ACCESS_TOKEN`, or manual SQL for v4.14.23. Online schema recheck is informational only.
