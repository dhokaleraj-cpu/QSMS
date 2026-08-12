# QCMS 4.10.0

## Universal controlled deletion
- Selected user-facing masters, transactions, inspections, NPD/APQP records and QC calculation records expose controlled delete actions.
- Every permanent delete verifies the signed-in user's current QCMS password first and still requires the module's Delete (`can_archive`) permission.
- Database foreign-key controls prevent deletion of records that are still referenced by downstream transactions.

## My Account password change
- Every signed-in user has a **My Account** page from the application header.
- Users verify their current password and can set a new login password with confirmation.
- The legacy **First administrator** field/tab is no longer shown on the login page.

## NPD one-screen order process status
- All pending NPD Part Numbers / Orders are presented as rows in one compact matrix.
- Process operations appear directly next to each Part Number with real-time status and target date.
- The pending matrix can be printed/downloaded as a controlled PDF.

## Master import
- All controlled master definitions can be imported from Excel/CSV through **Masters → Master Import**.
- Master template strips now provide **Import / Upload Master File** for master templates.
- Existing natural keys are updated instead of duplicated; database duplicate controls remain active.

## MetLAB and RMTC microstructure photographs
- Standard and OSP MetLAB reports support up to four microstructure photographs with an editable title for every photograph.
- RMTC supports three microstructure photographs with editable titles.
- Photograph titles flow into the controlled PDF layouts.

## PDF access
- PDF download/print remains available on individual records and is now also available to all users with View access from Records Centre registers and the pending NPD process matrix.

## Database
Migration: `20260812113000_qcms_universal_delete_account_import_print_v4100.sql`.
The migration is additive to permissions/deletion routing and does not reset existing QCMS production data.
