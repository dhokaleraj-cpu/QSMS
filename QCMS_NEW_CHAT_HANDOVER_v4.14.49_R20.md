# QCMS v4.14.49 R20 — PO clubbing, linked-record delete, record status window, supplier email To/CC

- **PO duplicate-key error fixed** (`uq_supply_rm_supplier_order_no`): one RM PO can now club several Customer
  Orders of the same supplier (run `QCMS_R20_RUN_IN_SUPABASE.sql` once). PO creation is atomic: if any line fails,
  the incomplete PO is cancelled automatically and its Customer Orders are free again. Cancelled POs release orders.
- **Club by RM section**: Parts that need the same steel (grade · RM section · size) go into ONE RM PO line
  (Linked Finished Parts printed). Raw forging / casting data in Part Master is ignored for RM POs.
  New "Club by Raw Material Section" filter in Purchase Order Entry.
- **Delete PO**: new server function deletes a PO with its own lines/sources/stages; only real receipts, inwards,
  forging receipts or active replacement POs block it. Any blocked delete now lists the linked transactions
  (type, reference, status, created by, date). "Check linked records" button before deleting.
- **Status window** (Records Centre → Record History, PO page, Part Master): created by / edited by and every field
  change (old → new) for transactions and masters, from the audit log.
- **Supplier emails**: To = supplier email, everyone else in CC. Preview (To/CC/subject/body/attachments + PO PDF)
  before sending.
- **KPI Dashboards**: number-first tiles, minimal text.
- **Login**: FOUR STAR INDUSTRIES PRIVATE LIMITED (design L1); 5 login options for approval.
- **PO print**: Design B family (B1 default) — teal headings, white body, coloured remarks; 5 options for approval.

## Handover notes
- New: core/record_history.py, core/dependency_map.py, migration 20261012100000_qcms_r20_po_club_delete_history.sql.
- Delete flow: core/delete_service.run_delete → qcms_delete_purchase_order (falls back to generic RPC if missing).
- PO print themes: core/purchase_order_reporting.PO_DESIGNS (B1..B5), purchase_order_pdf_bytes(..., design=).
- Pending user approval: PO print design (B1 applied) and login design (L1 applied).
