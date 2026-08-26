# QCMS v4.14.3 Release Notes

**Build:** `4143-PART-GRADES-LEADTIME-OPENING-STOCK-PASSWORD-EDIT-O365`

## Included

- Part Description is no longer treated as a duplicate key; Part Number and FSI Part Number remain protected.
- Multiple approved material grades can be assigned to a Part while one remains the primary/default grade.
- Multiple Raw Material / Forging rows are allowed for the same Part and Supplier, including Material Grade, Raw Material Section and supplier lead time.
- PO Delivery Date defaults from the selected supplier/raw-material lead time and remains editable.
- Opening stock is maintained by Part and Supply Chain stage. Finished Goods contributes to customer-order available stock. Eligible WIP/opening-stock stages can be selected directly for OSP Material Out while retaining genealogy.
- Customer Orders support controlled file attachments.
- Functional business roles/departments include Supply Chain, Management, Business Development and Procurement.
- RMTC, MetLAB and Dimensional final records can be reopened for controlled edit by a user with module Edit permission after current-password verification; Administrator role is not required. Re-validation and approval are mandatory after amendment.
- Part Master table editors are grouped in forms so cell edits are submitted in batches instead of rerunning after every cell.
- Login includes password recovery; signed-in users can change their own password.
- Microsoft 365 SMTP is supported through Admin → Email Server & Notifications. SMTP credentials are server-side only and are not embedded in this source package or updater.
- v4.14.2 Purchase Order customer-order visibility, section-bar crash correction and complete item-wise Price Revision History print are preserved.

## Data safety

Migration is additive/backward-compatible. No existing production/master/quality/Supply Chain/RMTC/OSP rows are deleted or reset.
