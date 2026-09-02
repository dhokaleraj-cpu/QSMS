# QCMS/QSMS Handover — v4.14.25

Authoritative source baseline: **v4.14.25** / build **41425-PO-EDIT-MASTER-STATE-TRANSACTION-EDIT-PERFORMANCE**.

Continue all previously controlled functions from v4.14.24 and earlier. Do not rebuild from an older archive.

## v4.14.25 additions
- Controlled Purchase Order edit with reapproval/reconfirmation.
- Latest master snapshot refresh on later PO revision while audit preserves prior values.
- Exact selected-record reload across master and transaction editors using record-specific Streamlit widget namespaces.
- Reference-master persisted value first in learned dropdowns.
- Records Centre controlled edit routing to source modules.
- Expanded record-specific edit state for Material Inward, OSP, NPD/APQP, Complaints and Supply Chain transaction editors.
- PO page request cache and bulk totals/receipt/source loading.

## Permanent deployment rules
- Preserve all Supabase production/master/quality/RMTC/OSP/Supply Chain data.
- Preserve existing Git repository, branch and Streamlit deployment.
- Every release is one self-contained macOS `.command` updater.
- Back up first, compile, run full pytest suite, commit/push existing branch, verify remote SHA.
- Never require manual SQL unless automatic migration is technically impossible.
- v4.14.25 is source-only; database baseline remains v4.14.22 / `QCMS_V41422_FULL_READY`.
