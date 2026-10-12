# QCMS v4.14.49 R21 — Approved designs, Print Layout Designer, Asset Number

- **Approved designs applied:** Purchase Order print = **B5 Teal Bands**; Login = **L1** (FOUR STAR INDUSTRIES PRIVATE LIMITED).
- **Print Layout Designer** (Admin → Print Layout Designer) for Purchase Order, RMTC, MetLAB, Bend Test,
  Dimensional, Material Inward and other quality records:
  - A · Design selector (B1–B5)
  - B · Colours & style (heading colour, table lines, remarks / conclusion colours, heading style, fills, font sizes)
  - C · Title, company name and footer text
  - D · Show / hide PO sections (plant, vendor, reference, old PO, ship-to, source reference, technical data,
    price history, special instructions, approval stamp)
  - E · Rename any heading
  - Live preview with sample data, Save (admin only), Reset to approved default, JSON export, version history / restore.
  - Every new print and every emailed PDF uses the saved layout immediately.
- **Design selector on PO PDF page:** print the selected PO with the saved layout or any of B1–B5.
- **Asset Number** in Quality Asset Master (unique per company, searchable, importable as "Asset Number").
  Shown in Calibration & Validation (selection lists, link register, record list, PDF, Excel), Standard Room
  Inspection and the KPI overdue-gauge table.
- One SQL step: `QCMS_R21_RUN_IN_SUPABASE.sql` (adds quality_assets.asset_number).
