# QCMS 4.9.9

## Controlled deletion, save confirmation, live trial cleanup and Jominy distance reliability

- Adds current-password-protected permanent deletion controls to NPD Process Flow, NPD Orders, APQP, OSP Transactions, linked OSP MetLAB/Dimensional records and QC Calculation Records, while retaining all existing delete controls in Masters, RMTC, Inward and Inspections.
- Extends the tenant-scoped `qsms_delete_master_row` RPC to the new NPD/APQP, OSP and QC Calculation root records. Parent records with linked non-cascading transactions remain protected by foreign keys.
- Standardizes save confirmations using QCMS toast/pop-up notifications plus a visible success message after reruns.
- Adds controlled automatic Material Grade serial numbers (`MAT-0001`, `MAT-0002`, ...); referenced legacy grades are preserved and backfilled rather than deleted.
- Corrects RMTC Jominy distance conversion by resolving the Jominy master ID first and automatically converting 1/16-inch distances to millimetres (`distance_16th × 25.4 / 16`).
- Live trial cleanup removed the identified RMTC, Material Inward and Dimensional trial transactions, the unrelated trial RMTC attachment metadata, one unreferenced trial Material Grade and the unreferenced duplicate Dispatch process.
