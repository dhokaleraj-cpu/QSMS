# QCMS v4.12.9 — Hardened Portal UI + Pocket Flow

- Build: `4129-HARDENED-PORTAL-UI-POCKET-FLOW`.
- Hardens the red top bar and charcoal side rail at the actual keyed Streamlit container level so theme/DOM changes cannot make them white.
- Adds explicit high-contrast borders to text, number, date, select, multiselect, textarea and upload controls.
- Rebuilds shared workflow progress, including Supply Chain Selected Order Flow, as responsive bordered pocket cards.
- Gives Master and Dashboard cards fixed content/action zones so counts, labels and navigation links cannot overlap.
- Adds direct report shortcuts into Supply Chain, RMTC, Inward, OSP, Inspection, Complaint, NPD/APQP and QC submenus while retaining the full Reports Centre.
- Preserves all v4.12.8 database, master, transaction, quality-decision, export and traceability logic.
- No new Supabase migration is required.
