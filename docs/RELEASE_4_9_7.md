# QCMS 4.9.7 — NPD / APQP Process Tracking

- Adds one top-level **NPD / APQP** group module.
- Adds **Process Flow Designer** with Part Master selection and Process Master operational sequencing (0, 10, 20, ...).
- Adds **NPD Status** order entry with customer, order quantity, start date and customer delivery date.
- Creates order-specific process snapshots from the approved part process flow.
- Adds target dates, real-time overdue evaluation and colour-coded process cards for Pending / In Progress / Completed / Hold / Overdue.
- Adds process-level target date, completion date, responsible person and remarks updates.
- Adds **APQP** project header and phase / deliverable status tracking using the existing PPAP/APQP schema.
- Adds standard APQP gate starter rows and calculated completion percentage.
- Adds NPD/APQP module permissions and tenant-level RLS for the new tables.
- Existing QCMS users, RMTC, Inward, OSP, Inspection, report and attachment data are preserved.
