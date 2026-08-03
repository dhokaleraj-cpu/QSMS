# QSMS 4.8.7 — Live Navigation, Dashboard and Attachments

## Dashboard
- Removed Part, Customer, Supplier and Steel Mill master KPI cards.
- Retained quality and transaction KPIs only.
- Quick Action cards now use distinct color themes and tinted card surfaces.

## Navigation
- Added a persistent submenu below every top-level module.
- Masters, RMTC, Inward, Inspections, Records and Templates expose their related pages directly.

## Optional attachments
- RMTC Entry supports three optional files.
- Material Inward supports three optional files.
- Files are stored in the private `quality-documents` Supabase bucket.
- Existing files can be downloaded at any time.
- Adding an empty attachment slot is permitted.
- Replacing or deleting an existing attachment requires the current QSMS password.
- Attachment deletion follows module archive permissions and tenant isolation.

## Deployment
- Live-first GitHub/Streamlit deployment is supported; no local application run is required.
- Plotly and HTTPX are declared directly in production requirements.
