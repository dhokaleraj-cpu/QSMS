# QCMS v4.14.19

Build: `41419-PO-LIVE-EMPLOYEE-DELETE-USER-STATUS-SAME-HEAT-CONFIRMATION-IMAGES`

## Controlled changes

- Resolves the logged-in Employee from live Supabase for Purchase Order creation, so a stale Streamlit session cannot disable an otherwise permitted PO.
- Shows exact PO creation blockers instead of a silently disabled button.
- Preserves User ↔ Employee links during role/status updates and verifies the link persisted. Employee Master email is never overwritten by login email.
- Adds Created By User, Last Modified By User and Data Entry Status to controlled transaction registers and the Records Centre.
- Keeps OSP transaction/receipt deletion under OSP Delete/Archive permission with password and stock-allocation reversal.
- Adds module-permission controlled, password-protected transaction deletion for other root transactions; downstream genealogy blocks unsafe deletion.
- Makes Add New RMTC for This Heat a genuinely fresh TC form. Same Heat can have multiple RMTC/TC records when Supplier RMTC numbers differ; canonical Heat Code and global Heat ledger remain linked.
- Microstructure image upload accepts PNG, JPG/JPEG, BMP, TIF/TIFF, WEBP and GIF.
- Adds Supplier Purchase Order Confirmation after PO approval, with mandatory confirmation attachment/reference.
- Sends an immediate supplier confirmation request after PO approval and a daily high-priority supplier reminder until confirmation is recorded.
- Daily reminders stop when the PO confirmation is confirmed or cancelled.
- Supplier confirmation appears in Supply Chain flow/responsibility status and is fully audited.

No production/master/quality/RMTC/OSP/Supply Chain data is reset.

## Final scope additions
- Common supplier RM item and common supplier forging part numbers can be reused across multiple finished Parts. Compatible sources consolidate to one supplier PO item while `supply_purchase_order_sources` retains finished-Part/customer-order genealogy.
- Supplier PO Confirmation is a hard gate before new RM/Forging receipt execution; historical POs with existing receipts are grandfathered.
- Daily Supply Chain digests include Purchase Orders pending approval and RM Procurement awaiting PO / due / overdue. Existing RM/Forging order overdue supplier notifications remain active.
- Standalone MetLAB/Dimensional insert/update RLS is reasserted against the same effective permission engine as the UI.
- Records Centre routes OSP deletes through safe reversal RPCs and all controlled transaction deletes require Delete/Archive permission plus current-password confirmation.
