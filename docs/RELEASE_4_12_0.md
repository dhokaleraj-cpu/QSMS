# QCMS 4.12.0 — Supply Chain, Flexible Inspection Stages & Interactive Status Cards

Build: `4120-SUPPLY-CHAIN-INSPECTION`

## Supply Chain
- New customer-order Master Reference stays linked through RM procurement, RM receipt, RM dispatch to forging supplier, forging order/receipt, machining, finished goods and customer dispatch.
- Supports Purchase Orders and six-month Monthly Schedule batch entry. Monthly references use `PART_MM_YYYY`.
- Duplicate Purchase Order/Position and duplicate Customer/Part/Month schedules are blocked.
- Required RM kg = Customer Order pcs × selected forging supplier Gross Weight from Part Raw Material Details.
- Cumulative RM purchase quantity cannot exceed 125% of the customer-order RM requirement. This is enforced in PostgreSQL, not only in the UI.
- Duplicate active RM purchase order for the same Customer Order + RM Supplier and duplicate active Forging Order for the same Customer Order + Forging Supplier are blocked.
- RM dispatch cannot exceed RM received against the same customer order.
- Forging supplier RM balance shows RM dispatched versus RM consumed.
- Traceability search by customer Master Reference shows the complete supply-chain timeline and supplier balance.

## Inspection flexibility
- Dimensional and MetLAB reports add Standalone Stage Report mode with Raw Material Stage, OSP Stage and Final Dispatch Stage.
- Standalone reports do not require RMTC, inward-lot, production-batch or OSP-job linkage.
- Existing QCMS Linked Flow remains unchanged.

## NPD and complaint status
- NPD process cards are clickable; selected card can update Status, Completed Date and Remarks. Remarks are shown on the card.
- Overdue NPD cards use a pulsing red highlight.
- Customer/Supplier complaints show workflow status cards using the same status-card concept.

## Part Master / UI
- E - Raw Material Details supports multiple named sections and displays Supplier Name / Location.
- App form font sizing is increased by about 20%.
- KPI/status/NPD card heights are reduced by about 20%.

## Database safety
Migration `20260819113132_qcms_supply_chain_flexible_inspections_v4120.sql` is additive. It creates seven Supply Chain tables, adds `material_section_name` to Part Raw Material Details, and extends the allowed inspection-stage values. No existing transaction is deleted, renumbered or reset.
