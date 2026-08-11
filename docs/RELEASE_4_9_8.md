# QCMS 4.9.8 - Duplicate Control, Record PDFs, NPD Checkpoints and QC Calculation Tools

## Scope

- Case-insensitive duplicate prevention for controlled masters, including Process and Inspection Stage code/name protection.
- Common A4 controlled-record PDF output for record-centric modules, while keeping the existing RMTC, Material Inward, MetLAB, Dimensional and report PDFs.
- NPD Process Flow checkpoints / bullet points under each operation, copied into each NPD order for Pending / In Progress / Completed / Hold / N/A tracking.
- Employee Master links for NPD process responsibility, process checkpoints, APQP coordinator and APQP deliverable owner.
- New QC Calculation Tools module with Jominy, DI Value and ASTM E 140-02 Table 1 hardness conversion tools.
- Stored QC calculation records with controlled PDF output.

## Data safety

The release is additive. Existing QCMS records are not deleted or reset. Existing legacy duplicate Process names are grandfathered until the controlled name itself is edited; new duplicates are rejected.
