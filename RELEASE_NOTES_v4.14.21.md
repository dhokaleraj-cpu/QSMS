# QCMS v4.14.21

## Deployment recovery and delete routing hotfix
- Falls back to `/tmp` when macOS `$TMPDIR` points to a stale/deleted folder, preventing `mktemp: No such file or directory`.
- Adds a read-only public v4.14.21 Supabase release contract so an already-live schema can be verified without requiring a Management API token or manual Supabase CLI login.
- Routes root transaction deletion through `qcms_delete_transaction_row`; true master rows continue through `qsms_delete_master_row`.
- Fixes OSP MetLAB/Dimensional/Records deletion paths that incorrectly called the master-delete RPC.
- Delete failures are shown inline as controlled business errors instead of crashing the whole Streamlit page.
- Preserves all v4.14.20 same-Heat RMTC and OSP edit/delete functionality. No production data reset.
