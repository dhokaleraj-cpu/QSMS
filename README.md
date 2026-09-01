# QCMS v4.14.23

Current controlled build: `41423-SOURCE-ONLY-DEPLOY-RMTC-MASTER-DELETE`

This release is a deployment and master-entry reliability hotfix on top of v4.14.21.

- Public Supabase release verification uses the project publishable key and requires no `supabase login`.
- Master Data Centre **New Record** opens a blank form; editing remains through Records / Edit.
- Same-Heat **Add New RMTC / TC** clears the previous certificate widget state while retaining only Heat identity.
- v4.14.21 transaction-delete routing remains preserved so OSP/MetLAB/Dimensional records never go through the master-delete RPC.
- Existing production/master/RMTC/OSP/Supply Chain data is preserved.


## v4.14.23 source-only deployment recovery
- No new Supabase migration is required; live database baseline remains v4.14.22 / `QCMS_V41422_FULL_READY`.
- Online Supabase verification is non-blocking so a local Data API/DNS issue cannot prevent Git/Streamlit deployment.
- Same-Heat **Add New RMTC / TC** uses a fresh selector/form nonce and preserves only Heat identity.
- Master Data Centre **New Record** requests clear the prior edit selector and open blank forms.
- Transaction delete routing sends OSP/MetLAB/Dimensional/RMTC/Material Inward/Supply Chain transactions to `qcms_delete_transaction_row`, not the master-delete RPC.
