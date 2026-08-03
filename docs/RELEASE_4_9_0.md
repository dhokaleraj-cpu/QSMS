# QSMS 4.9.0 — OSP Transactions and Two-Stage Quality Gate

## Dashboard and quality visibility

- The Recent Heat Status grid now shows Global Heat Quantity, Global Heat Balance Quantity, inward steel and the existing Heat status information.
- Quality KPI cards use category-specific colors so pending, accepted, reserve/hold and rejected workload can be recognized immediately.
- OSP workload is included in the Quality workspace and Records Centre.

## Part and inspection master controls

Part Master now contains Process & Inward Specifications for each Part Number:

- Process and Process Type
- Inward Type: Material Inward or OSP Process
- Process Specification
- Dimensional inspection required
- MetLAB inspection required
- One-part sample quantity
- Sequence, status and remarks

OSP inspection layouts are controlled by Part Number, Process, Inward Type and Layout Type. Only Approved OSP layouts matching the selected Part and outsourced Process can be used. This ensures that only the parameters defined for the related OSP process are loaded into the inspection report.

## OSP transaction workflow

1. **Material Out** — select a quality-released Material Inward lot by Heat Number and Part Number, then select the approved OSP Vendor, outsourced Process and Part Process Specification. The system controls the available production quantity and creates the source/child batch genealogy.
2. **One-part Sample Receipt** — record the sample reference, OSP Vendor Batch Number and sample quantity before accepting the full processed batch.
3. **Sample Quality Gate** — complete OSP Sample Dimensional and MetLAB inspections. Full OSP inward remains blocked until every required sample inspection is Accepted or Accepted Under Reserve.
4. **Full OSP Inward** — record the complete dispatched quantity with receipt challan, Vendor Invoice Number/Date, TC Number/Date and the same OSP Vendor Batch Number validated during sample inspection.
5. **Receipt Quality Gate** — complete OSP Receipt Dimensional and MetLAB inspections using only the approved Part/Process OSP layouts.
6. **Production Release** — the processed batch becomes available for the next production process only after every required receipt inspection is Accepted or Accepted Under Reserve.

## Traceability and validation

- Heat Number, Heat Code, Part Number, source Material Inward, OSP Vendor, Process, Process Specification, OSP Job, Vendor Batch Number and production batch remain linked through the full workflow.
- OSP Material Out is permitted only from a Material Inward lot already released by Dimensional and MetLAB quality approval.
- Dispatched quantity cannot exceed the released Material Inward production balance.
- Full OSP inward must equal the dispatched quantity and cannot be recorded before the sample gate is approved.
- The OSP Vendor Batch Number used for full inward must match the batch validated during the one-part sample gate.
- Production release is blocked until the post-receipt quality gate is approved.
- Existing QSMS records, attachments, credentials and Supabase transactions are preserved.
