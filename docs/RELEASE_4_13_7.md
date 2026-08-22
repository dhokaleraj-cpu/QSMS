# QCMS v4.13.7 — Supply PO / FSI Part / Approved RMTC Worksheet

Build: `4137-SUPPLY-PO-FSI-PART-RMTC-WORKSHEET`

## Approved RMTC Part Worksheet Extension

A dedicated **Approved RMTC Part Worksheet** page allows an Accepted / Accepted Under Reserve RMTC to be extended to another compatible Part Number. Existing accepted Part worksheets remain available; the new Part is taken through its controlled worksheet and validation/decision process.

## Customer Order Stock / RM Procurement Decision

Customer Order and six-month Schedule entry evaluates the QCMS system-available quantity against the rolling three-month schedule demand. The entry stores the stock, three-month demand, shortage, RM-procurement flag and decision snapshot. Raw Material Purchase Orders are blocked when current available quantity is equal to or greater than the rolling three-month schedule quantity.

## Controlled Purchase Orders

The Supply Chain Purchase Order workspace creates **RAW MATERIAL** and **FORGING** Purchase Orders. The controlled print follows the supplied FSI purchase-order concept: Plant, Vendor, Ship-To, requisitioner, ship-via, Incoterm, delivery/payment terms, item/tax grid, weight/RM/tool/profit/packaging details, remarks, special instructions and FSI standard terms pages.

RM POs are linked to the existing RM Procurement / Material Inward transaction chain. Forging POs are linked to the Forging Order / Forging Receipt chain. Receipt posting updates the controlled PO status to Open, Partial or Closed.

Reports include Pending Purchase Orders, Raw Material Orders, RM Section Orders, Supplier Orders and RM-for-Part Number Orders.

## FSI Part Number Confidentiality

Part Master now maintains a separate **FSI Part Number** in addition to the original/customer Part Number. Both identities are shown independently inside QCMS operational records. Supplier-facing Purchase Order print uses FSI Part Number only so the original/customer Part Number is not exposed on that document.

## Data Safety

The migration is additive. Existing customer orders, RMTCs, inward lots, OSP, inspections, supply-chain transactions, attachments and approvals are preserved.
