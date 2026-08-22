# QCMS v4.13.8 — Multi RM PO / Supplier Price History / Part Technical Data

Build: `4138-MULTI-RM-PO-PRICE-HISTORY-TECH-DATA`

## Controlled changes

- Raw Material Purchase Orders can consolidate multiple eligible Customer Orders / Monthly Schedules in one supplier PO while preserving allocation genealogy to every source schedule.
- Purchase-order vendor lines are grouped by supplier-specific Part Master raw-material configuration and FSI Part Number.
- Supplier + FSI Part price history is maintained as **Start Date / End Date / Price**; a blank End Date represents the current price.
- Existing controlled PO history is backfilled into the price-history register where price changes can be determined.
- Part Master → Raw Material Details now owns flexible **Heading / Value** technical data rows for each supplier-specific material source.
- Purchase Orders snapshot and print the Part Master technical data automatically; those values are no longer re-entered on the PO page.
- Existing v4.13.7 single-source purchase orders are backfilled into the new source-allocation model where possible.
- Original/customer Part Number remains internal to QCMS. Supplier-facing PO identity continues to use the FSI Part Number.
- Existing RM Inward, forging, RMTC, OSP, quality, reports, audit, permissions and transaction history are preserved.

## Database

Two additive migrations:

- `20260822213000_qcms_multi_rm_po_price_history_technical_data_v4138.sql`
- `20260822213100_qcms_multi_rm_po_history_backfill_v4138.sql`

Both are non-destructive. They add source allocation, supplier price-history and supplier-specific technical-data structures and backfill compatible existing PO records.
