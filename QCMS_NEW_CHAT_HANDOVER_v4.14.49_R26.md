# QCMS v4.14.49 R26 — Register PDF crash fix, PO lines on first page, GRAND TOTAL row

- **Fixed:** `reportlab LayoutError` on Purchase Orders (Purchase Order Register PDF Export). Wide registers are now split
  into column groups (first column repeated, "columns 1 of 4"), long cell text is shortened, the PDF is built only when
  you click "PDF Export", and a layout problem can never crash the page again (compact retry / safe fallback).
- **PO print:** as many complete line items as fit go on the **first page** (each with its source reference, technical
  data and price history); the rest continue on item pages, several per page. Hiding sections fits more lines.
- **GRAND TOTAL row** after the last line item (multi-line POs): PO lines · total quantity per UOM · subtotal · GST ·
  grand total.
- No database step.
