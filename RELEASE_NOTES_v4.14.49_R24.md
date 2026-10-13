# QCMS v4.14.49 R24 — "Sections shown on print" everywhere in Purchase Orders

The same tick-box grid as the Print Layout Designer (Plant, Vendor, Reference, Old PO, Ship To, PO Source Reference,
RM Details & Technical Data, Price Revision History, Comments / Special Instructions, Approval Stamp) is now in:
- PO Entry (saved with the new PO; Preview PO PDF uses it)
- Order List, Edit PO, PO PDF and the PO register: tick / untick → Preview → Save for this PO
- PO PDF / Excel downloads (use the ticked sections immediately)
- Batch print: optional "same print sections for all selected POs"
- Every PO email: record email panels, batch PO emails and PO approval emails choose the sections of the attached PDF
Print Layout Designer section D now uses short labels (no overlapping text) and stays the default for new POs.
No database step (uses the R23 print_options column, already applied).
