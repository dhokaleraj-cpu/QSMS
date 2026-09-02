# QCMS v4.14.27

Build: `41427-FINAL-METLAB-LAYOUT-PO-EMAIL-FIELDS`

- Part Master Metallurgical Requirements are explicitly Final Dispatch MetLAB only.
- Raw Material Inward MetLAB excludes `FINAL_METALLURGICAL` layouts and requires manual selection from approved Layout Master MetLAB layouts.
- Standalone Raw Material Stage MetLAB follows the same Layout Master-only rule.
- Final Dispatch MetLAB continues to use the controlled Final Metallurgical layout generated from Part Master requirements.
- Email Template administration now includes an event-specific Database Field picker with source-table labels and one-click insertion into Subject or Body.
- Forging Purchase Order release email is seeded with the Four Star Purchasing template requested by the user.
- PO release context now supplies aggregated Part Number, Quantity/UOM, item description, supplier and header fields.
- Supplier release email is sent after PO approval using `FORGING_PO_CREATED` / `RM_PO_CREATED`; supplier confirmation reminders continue separately until confirmation.
- Live v4.14.27 Supabase migration applied and verified; no user-side SQL is required.
