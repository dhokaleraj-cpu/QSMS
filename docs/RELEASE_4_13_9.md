# QCMS v4.13.9 — RM Procurement Link / RMTC Incremental Part / Item-wise PO Technical Data

## Fixes
- Customer Purchase Orders now contribute their own order quantity when the live RM procurement gate is re-evaluated. This fixes eligible FSI-RM orders disappearing from RM Procurement / Purchase Orders after save.
- Direct Forging orders remain excluded from FSI RM Procurement by design.
- Approved RMTC Part Worksheet extension now supports a newly pending/on-hold/rejected Part while existing Accepted covered Parts stay released under PARTIALLY_APPROVED state.
- Purchase Order PDF renders each FSI Part item line followed immediately by that item’s Raw Material / Forging Parameters and FSI Technical Data before the next item line.

## Non-regression
- v4.13.8 multi-order RM PO allocation genealogy is preserved.
- Supplier + FSI Part price history and Part Master supplier technical data snapshots are preserved.
- Original/customer Part Number remains internal; supplier PO uses FSI Part Number.
