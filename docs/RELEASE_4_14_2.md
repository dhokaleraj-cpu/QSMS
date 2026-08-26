# QCMS 4.14.2

Build: `4142-PO-ORDER-VISIBILITY-FULL-PRICE-HISTORY`

## Purchase Order corrections
- Every open Customer Order / Schedule remains visible in Purchase Order source status.
- RM and Forging PO selection are driven by the same eligibility result shown in the grid.
- The saved Customer Order RM procurement decision is authoritative at PO creation; unrelated later stock movements cannot silently invalidate an already-approved RM requirement.
- Missing FSI Part Number can be entered in the controlled supplier-facing PO item grid without exposing the customer Part Number.
- RM allocation and supplier Raw Material compatibility controls remain enforced.

## Price revision history
- Closed/inactive historical revisions are retained and printed.
- Part Master supports Start Date, End Date, Basic Rate, Freight, Tool Cost, P&F, Profit, ICC/Rej., Currency, UOM and Remark.
- Every PO item prints its own complete supplier/FSI Part history.
- Each PO item prints the complete controlled Supplier / FSI Part revision register available in its snapshot; legacy reprints can be enriched from Part Master without modifying the transaction.
- Long history continues onto controlled item-specific pages before standard FSI terms.

No production/master/quality data is reset or deleted.
