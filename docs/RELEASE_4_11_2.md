# QCMS 4.11.2 — Export Shipment Header & Module Theme

This release changes only the standalone QCMS application shell/navigation presentation.

## Visual shell
- Deep navy-to-blue rounded Four Star Industries header.
- White centered QUALITY CONTROL MONITORING SYSTEM title.
- Company logo/name at left; user, role, live state, app version and local date/time at right.
- Separate white MODULES heading bar.
- Transparent module rail beneath the heading with dark inactive labels and a blue-gradient active module.
- Compact white second-level navigation.
- Light blue/white application background to preserve readability.

## Functional preservation
- Central Records routing remains unchanged.
- No Supabase migration is required.
- Existing authentication, records, permissions, attachments, complaints/CAPA, RMTC, OSP, inspections, NPD/APQP and reporting logic are unchanged.

Build: `4112-EXPORT-SHELL`.
