# QCMS v4.14.49 R28 — Raw Material data-loss fix + recovery, PO add orders, scroll grids, auto database update

- **CRITICAL FIX · Raw Material details disappearing:** saving a Part's grid rows (Raw Material Details, Jominy,
  technical data, heat treatment) looked up an "equal" row WITHOUT the Part, so a row of another Part
  (same supplier / section / grade) was MOVED to the Part being saved. Every save is now limited to its own Part,
  and a grid row that belongs to another Part is refused.
- **Recovery (applied automatically by the updater):** every Raw Material row a Part lost is re-created from the
  audit history (remarks "[restored by QCMS R28]"), with its supplier technical data; the Part's price history is
  pointed back to it; lost Jominy rows are restored. This also fixes the RM PO error "selected Customer Orders do not
  share one common supplier-specific Raw Material record" (K11696 + K160).
- **Quality Assets:** the same Asset Name may repeat (many SNAP GAUGES); the Asset Number must be unique.
- **Calibration:** instruments / equipment are calibrated directly — no Part / Process link. Only gauges, fixtures and
  jigs are linked to a Part / Process.
- **Purchase Order edit:** all fields editable (dates, plant, ship-to, terms, quotation, currency, other charges,
  remarks, line item no. / HSN / price / GST, allocations) and **Add Customer Orders to this Purchase Order**
  (same checks as a new PO; same item is clubbed into the existing line; PO returns to approval).
  Supplier change = Cancel & Reissue with New Supplier.
- **Cancelled PO releases everything:** its Customer Orders go back to OPEN (5 orders stuck "In Progress" fixed) and
  are immediately available for a new PO; cancelled PO lines no longer count in Part usage.
- **Grids:** every table scrolls left/right and up/down inside its frame, with fixed header and first column and
  visible scroll bars.
- **Automatic database update:** the updater applies the SQL itself through the Supabase Management API (one-time
  personal access token kept only in the macOS Keychain). No more SQL Editor copy / paste.
- **Android app:** UI designs for approval in docs/android/QCMS_R28_Android_App_Designs.pdf.

## Handover notes
- R28 SQL: supabase/migrations/20261017100000_qcms_r28_part_rows_recovery_assets.sql (+ .check.sql), listed in
  supabase/auto_apply.json, applied by scripts/apply_sql.py (ledger table public.qcms_applied_sql).
- Token: Keychain service QCMS_SUPABASE_ACCESS_TOKEN (remove with `python3 scripts/apply_sql.py --forget-token`).
- Future SQL: add the file to supabase/auto_apply.json; the updater applies it once.
