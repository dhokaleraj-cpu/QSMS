# QCMS v4.12.8 — Responsive Enterprise UI + Report Hub

Build: `4128-RESPONSIVE-ENTERPRISE-UI-REPORT-HUB`

## Fixed
- Removed the v4.12.7 fixed-position overlay architecture that allowed content to scale underneath the left menu.
- Rebuilt the application body as a true two-column Streamlit workspace: navigation rail + content canvas.
- Top red navigation remains in normal flow and all page links are clickable.
- Explicit heading/subheading foreground colours prevent invisible text on similar backgrounds.
- Pocket/KPI cards, fields, section titles and data grids now use one consistent enterprise preview stylesheet.
- Removed layered legacy CSS from `apply_global_style`; v4.12.8 uses one stylesheet only.

## Reports
Reports Centre now exposes direct report routes for Supply Chain Order / Dispatch MIS, Supply Chain Traceability, Heat Balance, OSP Heat Balance, RMTC, Material Inward, Dimensional Inspection, MetLAB, Complaints, NPD Status, APQP, QC Calculations, Inspection Layouts and Customer Standards.

## Database
No new Supabase migration is required.
