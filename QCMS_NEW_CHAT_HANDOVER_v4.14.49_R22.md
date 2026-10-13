# QCMS v4.14.49 R22 — Clear delete reasons, status everywhere, opening stock at suppliers, Part Designation

- **Delete errors explained:** a blocked delete now shows the plain reason plus a table of every linked record with
  *Reference*, *Belongs To* (PO number + status), *Status*, *Created By* and **How to fix**.
  - Purchase Order: its own lines / sources / stages are removed with it; only RM Receipts, Material Inwards,
    Forging Receipts or an active replacement PO block it — named by number.
  - Customer Order (new server delete): links to **cancelled** POs are released automatically; an active PO
    (e.g. PD9121000079 Pending Approval) is named with the fix "cancel or delete the PO first".
  - "Check linked records" shows what will block before you delete. Raw database text ({'message': …}) is gone everywhere.
- **Status in every selection list:** [ACTIVE], [INACTIVE], [OPEN], [CANCELLED] … on masters, parties, parts, orders, POs and records.
- **Customer Order labels everywhere:** Customer PO · Pos · Part · FSI · Ref · Customer · Qty [STATUS].
- **Opening stock at Supplier / Vendor:** Stock Location (At FSI / At Supplier / At Vendor) + the party holding it,
  new stage **Casting**, location summary, import columns "Stock Location" and "Location Party Code".
- **Part Designation:** Process Flow Designer numbers operations automatically (Forging/Casting = 0, then 10, 20, 30…)
  and shows Part Designations K4404-0, K4404-10, K4404-20… from the FSI Part Number; stored on every operation and
  updated automatically if the FSI Part Number changes. Checkpoints stay with their process when renumbered.
- **Price history fix:** periods are now per Supplier + Raw Material record + UOM; a new price automatically closes the
  previous open price (End Date = new Start Date − 1); remaining overlaps show the exact dates.
- One SQL step: QCMS_R22_RUN_IN_SUPABASE.sql.

## Handover
- New: core/db_errors.py; record_history.linked_records (OWNED_CHILDREN, FIX_HINTS); selection_labels.with_status/customer_order_label; npd_apqp.auto_operation_numbers.
- SQL tested on a local PostgreSQL 16 stub (price auto-close, customer order delete, PO delete, designation trigger).
