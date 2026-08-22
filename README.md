# QCMS v4.13.7

Build: `4137-SUPPLY-PO-FSI-PART-RMTC-WORKSHEET`

Controlled release for approved-RMTC Part Worksheet extension, Customer Order three-month stock/procurement checks, Raw Material and Forging Purchase Orders, supplier PO print/control, receipt-linked procurement MIS, and a secondary FSI Part Number used alongside the original/customer Part Number throughout QCMS.

Key controls:
- Approved RMTCs can be extended to another compatible Part Worksheet without releasing the original/customer part identity externally.
- Customer Order / Schedule entry snapshots available system stock against rolling three-month schedule demand and controls whether RM procurement can be raised.
- Controlled RM/Forging Purchase Orders use the FSI/703/F04 print concept and remain linked through Material Inward / Forging Receipt.
- Supplier-facing Purchase Order item identity uses FSI Part Number; original/customer Part Number remains available internally for genealogy.
- Purchase Order reports include pending POs, RM orders, RM section orders, supplier orders, and RM-for-Part orders.
- Existing QCMS quality, OSP, Supply Chain, reports, security, UI and historical data remain preserved.
