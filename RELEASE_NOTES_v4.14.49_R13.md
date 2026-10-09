# QCMS 4.14.49 R13 — 9 October 2026

Includes R12 (Teal design, faster re-runs, AI key script), R11 and R10.

## AI Assistant switch for the System Administrator
- New **Admin → System Settings**: AI Assistant mode = Enabled for all users / Administrators only / Disabled. Shows whether the Claude key is configured and which model is used.
- When disabled, Global Search shows Keyword Search only. Optional emergency override: `QCMS_AI_MODE = "DISABLED"` in Streamlit secrets.
- Stored in the existing `master_value_catalog` table — no SQL migration.

## Top-10 KPI Dashboards (new page "KPIs")
1. Supplier On-Time Delivery · 2. Purchase Order Pipeline · 3. Customer Order Fulfilment · 4. Incoming Material Quality (PPM) · 5. RMTC Approval & Compliance · 6. Lab & Inspection First-Pass Yield · 7. OSP Vendor Performance · 8. Complaints & CAPA (8D) · 9. Gauge Calibration Compliance · 10. NPD & APQP Health.
- KPI overview strip, period filter, status badges (On target / Watch / Action needed), charts with data tables, action lists (overdue items) and Excel download per dashboard. Each dashboard is shown only to users who can View its module.

## Restructured layout
- Top menu: Home · KPIs · Masters · Supply · Quality · Reports · Records · Admin.
- Left menu grouped: Overview (Dashboard, KPI Dashboards, Search & AI) · Master Data · Procurement · Quality (RMTC, Inward, Inspections, OSP, Complaints, Calibration) · Engineering (NPD/APQP, QC Tools) · Reports & Records · Administration.

No SQL migration.
