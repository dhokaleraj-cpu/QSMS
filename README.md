# QCMS v4.14.9

Current controlled build: `4149-DEPENDENCY-BOOTSTRAP-REMOTE-DEPLOY`

Deployment-target and notification-workflow release. It preserves all v4.14.6 functional changes and adds next-stage department/employee responsibility routing, module email templates, generated QCMS PDF + controlled document attachments, supplier/vendor notification copies, Party Master notification addresses and automatic open/overdue PDF email schedules. It also extends Deployment Diagnostics with the live Git origin/HEAD and Streamlit main-file proof because the user screenshot on 26-Aug-2026 showed the live runtime still serving v4.14.1. No existing business/master/quality/Supply Chain data is reset.

---

# QCMS v4.14.6

Current controlled build: `4146-LIVE-RUNTIME-DIAGNOSTICS-FORCE-REDEPLOY`

Deployment-enforcement release. It preserves all v4.14.5 functional changes and makes the live runtime self-verifying: the build/version strip appears on every authenticated page, Admin contains Deployment Diagnostics with runtime Git HEAD and feature markers, MetLAB and Dimensional edit controls remain visible even when no saved rows are returned, and Supply Chain Home has a direct Opening Stock & Import action. The updater performs a forced second redeploy commit and verifies the remote SHA. Existing data and the now-working email configuration are preserved.

---

# QCMS v4.14.5

Current controlled build: `4145-DEPLOY-VERIFY-DIRECT-REPORT-EDIT-SMTP-TENANT-GUIDE`

# QCMS v4.14.4 — Report Edit / Master Duplicate / Opening Stock Import / SMTP Guidance

Build: `4144-METLAB-EDIT-MASTER-DUPLICATE-OPENING-IMPORT-SMTP-GUIDE`

Corrective release after v4.14.3. It removes the MetLAB `StopIteration` plan-selection crash, makes RMTC / MetLAB / Dimensional report amendment controls prominent and password-controlled for users with module Edit permission, restricts master duplicate-word checking to controlled identity fields only, adds a dedicated Opening Stock import/export utility, and adds actionable Microsoft 365 SMTP AUTH guidance for error 535 5.7.139. Existing v4.14.3 multiple-grade, lead-time, staged-opening-stock, OSP, Purchase Order and authentication controls are preserved.

No production/master/quality/Supply Chain data is reset by this release.

---

# QCMS v4.14.3 — Part / Supply / Authentication Controls

Build: `4143-PART-GRADES-LEADTIME-OPENING-STOCK-PASSWORD-EDIT-O365`

This release preserves all v4.14.2 Purchase Order visibility and full item-wise price-history behavior, and adds: duplicate Part Description allowance, multiple approved Part grades, multiple supplier/raw-material sections, supplier lead-time-driven PO delivery dates with editable override, opening stock by Supply Chain stage including OSP source support, Customer Order attachments, functional Supply Chain/Procurement/Business Development/Management roles and departments, password-controlled controlled amendments for RMTC/MetLAB/Dimensional reports, batched Part Master data grids, password recovery/change-password controls, and server-side Microsoft 365 SMTP configuration support.

No production/master/quality/Supply Chain data is reset by this release.

---

# QCMS v4.14.2

Build: `4142-PO-ORDER-VISIBILITY-FULL-PRICE-HISTORY`

Purchase Order corrective release: fixes the PO-page runtime `section_bar` error, keeps every open Customer Order / Schedule visible with explicit eligibility, uses one eligibility source for both display and selection, and prints the full supplier/FSI-Part Price Revision History beneath every PO item. Closed historical price revisions and remarks remain in the print history. Existing QCMS data and prior v4.14.x workflows are preserved.

---

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
