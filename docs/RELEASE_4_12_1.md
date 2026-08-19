# QCMS 4.12.1 — Master-Driven Standalone Quality Reports

Build: `4121-MASTER-DRIVEN-STANDALONE-REPORTS`

## Standalone MetLAB and Dimensional reports
- Part Number remains the controlling selection.
- Customer and Material Grade are automatically loaded from Part Master and shown read-only.
- Supplier / OSP Vendor is selected from controlled party/master data; Raw Material/Final stages prefer Part-approved suppliers and OSP stage uses active supplier/OSP-vendor masters.
- Heat Number, Heat Code, Supplier/HT/OSP Batch Number, Internal/FSI Batch Number, Supplier Invoice / Reference, Quantity, Sample/Lot Reference and Supply / Process Condition are available in standalone report headers.
- Drawing Number / Revision is displayed from the current Part Master.

## OSP stage
- OSP Process is selected only from active Part + OSP Process requirements.
- Process Specification and controlled process drawing details are displayed from Part Master.
- The approved Dimensional / MetLAB layout is selected automatically from the Part + OSP Process controlled layout. Manual layout selection is removed from standalone OSP reporting.

## Final MetLAB
- Final Dispatch stage automatically prioritizes the approved `FINAL_METALLURGICAL` layout generated from Part Master Metallurgical Requirements.

## Controlled PDF output
- Standalone reports now print Customer, Material Grade, Supplier/OSP Vendor, Heat Number, Heat Code, Supplier/HT/OSP Batch Number, Internal/FSI Batch Number, Supplier Invoice/Reference, Quantity, Drawing/Revision, Process/Condition and Sample/Lot reference in the report header, following the supplied Metallurgical Laboratory report structure.

## Database safety
Migration `20260819170000_qcms_master_driven_standalone_reports_v4121.sql` is additive. It adds report header snapshot/reference fields and database-side Part Master enforcement for Customer and Material Grade. No existing report, transaction, result, attachment, approval or identifier is deleted or reset.
