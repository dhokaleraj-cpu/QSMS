# QCMS v4.14.0

Build: `4140-PO-SOURCE-RMTC-VALIDATION-HSN-EMAIL`

Corrective workflow + notification release for Purchase Order source visibility, incremental Approved-RMTC Part validation/decision, HSN/SAC supplier print, clean item-wise Purchase Order layout, and configurable next-responsibility email notifications.

Key controls:
- Customer Order Supply Flow is stored directly and every open order is visible on the PO eligibility grid with a reason.
- DANA-style FSI-RM orders remain eligible for RM PO until RM balance is ordered; Direct-Forging orders appear in Forging PO until forging quantity is ordered.
- Newly added Parts under an approved RMTC can be validated and decided independently while previously accepted Parts remain released.
- PO supports HSN/SAC and removes vertical body grid lines with more item/technical-data space and continuation pages.
- Admin Email Server & Notifications provides SMTP settings, employee responsibility routing, test/retry outbox and server-side delivery.
- Existing v4.13.9 and earlier data/logic remain preserved.

---

# QCMS v4.13.9

Build: `4139-RM-PROCUREMENT-LINK-RMTC-PART-PO-ITEM-TECH`

Corrective controlled release for Customer Order → RM Procurement/PO visibility, incremental Approved RMTC Part Worksheet extension, and item-wise Purchase Order technical data.

Key controls:
- FSI-RM Customer Orders / Schedules retain their saved procurement decision and are rechecked with the correct order demand when the pending RM list is rendered.
- Customer Purchase Orders contribute their own order quantity to the live three-month procurement check; Monthly Schedules continue to use their saved rolling schedule demand.
- Direct Forging orders remain intentionally excluded from RM Procurement.
- Approved RMTCs can be extended with a pending Part Worksheet while previously accepted covered Parts remain released.
- PARTIALLY_APPROVED RMTC state now supports accepted covered Parts together with a newly pending/on-hold/rejected Part Worksheet.
- Purchase Order PDF prints each FSI Part item line followed immediately by that Part/Supplier Raw Material / Forging Parameters and FSI Technical Data before the next item line.
- Existing v4.13.8 multi-order RM PO, Supplier/FSI Part price history, technical-data snapshots, FSI Part confidentiality and historical data remain preserved.

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
