# QCMS 4.10.9

- Fixes the login NameError by importing `logo_data_uri` and `safe` from `core.ui`.
- Preserves the existing local GitHub `.git/config`, current branch, and `origin` URL during deployment.
- Adds regression tests for login helper imports and the visible build fingerprint `4109-LOGIN-IMPORT-GUARD`.
- Retains the v4.10.8 detailed Complaint Analysis / CAPA workflow and live Supabase schema.
