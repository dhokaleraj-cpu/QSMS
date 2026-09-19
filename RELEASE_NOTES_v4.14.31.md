# QCMS v4.14.31 — Purchase Order Workspace / Pre-Approval Edit / Customer Reference PDF

## Controlled release

- Version: `4.14.31`
- Build: `41431-PO-WORKSPACE-PREAPPROVAL-EDIT-CUSTOMER-REF-PDF`
- Database baseline: `4.14.28`
- Database migration: **not required**

## Purchase Order workspace

Purchase Orders now have dedicated pages/tabs for **PO Entry**, **Order List**, **Edit Purchase Order**, **Purchase Order PDF**, and **Approval / Supplier Confirmation**. This separates creation, editing, printing and approval work instead of forcing all actions into one long page.

## Edit before approval

A PO in `PENDING_APPROVAL` can be edited and saved directly. **Supplier Confirmation is not required to edit a PO.** Editing an already-approved PO returns it to `PENDING_APPROVAL`; supplier acknowledgement is handled separately after the new approval/release. Supplier changes continue to use Cancel & Reissue to preserve controlled genealogy.

## PO source identity / selection list

PO selectors and the Order List show the linked source identity including **Customer, Customer PO Number, PO Position, Part Number, FSI Part Number, PO source quantity/UOM and Customer Delivery Date**.

## Controlled Purchase Order PDF

Each controlled PO item now includes a **CUSTOMER PO / SOURCE REFERENCE** table containing Customer, Customer PO Number, Position, Part Number, Quantity, UOM and Delivery Date. Multiple source allocations remain traceable for consolidated RM/Forging POs.

## Supplier Confirmation

Supplier Confirmation remains a downstream controlled stage and **never blocks PO editing**. The dedicated Approval / Supplier Confirmation page makes the status visible. It becomes actionable after approval/release.

## Preserved baseline

All v4.14.30 RMTC approved-supplier de-duplication, Bend Test discovery, Global Search, horizontal Chemical Analysis, Case Depth Traverse, OSP genealogy, notification schedules, permissions, Complaints, Calibration/Standard Room and NPD/APQP functions remain preserved.
