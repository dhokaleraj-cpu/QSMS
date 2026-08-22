# QCMS v4.13.8

Build: `4138-MULTI-RM-PO-PRICE-HISTORY-TECH-DATA`

Controlled release for multi-source Raw Material Purchase Orders, supplier/FSI-Part price history, supplier-specific Part Master technical data, approved-RMTC Part Worksheet extension, Customer Order three-month stock/procurement checks, supplier PO print/control, receipt-linked procurement MIS, and the secondary FSI Part Number identity.

Key controls:
- One Raw Material PO can consolidate multiple eligible Customer Orders / Monthly Schedules while retaining allocation genealogy to every source schedule.
- Supplier + FSI Part price history is controlled by Start Date / End Date / Price, with open-ended current price support and historical PO backfill.
- Supplier-specific Raw Material technical data is maintained as flexible Heading / Value rows in Part Master and snapshots automatically to the PO.
- Approved RMTCs can be extended to another compatible Part Worksheet without releasing the original/customer part identity externally.
- Customer Order / Schedule entry snapshots available system stock against rolling three-month schedule demand and controls whether RM procurement can be raised.
- Controlled RM/Forging Purchase Orders use the FSI/703/F04 print concept and remain linked through Material Inward / Forging Receipt.
- Supplier-facing Purchase Order item identity uses FSI Part Number; original/customer Part Number remains available internally for genealogy.
- Purchase Order reports include pending POs, RM orders, RM section orders, supplier orders, and RM-for-Part orders.
- Existing QCMS quality, OSP, Supply Chain, reports, security, UI and historical data remain preserved.
