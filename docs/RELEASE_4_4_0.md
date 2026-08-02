# QSMS 4.4.0

- Export Shipment Monitoring System inspired blue/white enterprise theme.
- Redesigned Master Data Centre cards with live record counts.
- Back and sibling navigation on every hidden master and RMTC page.
- Password-protected permanent deletion for selected master records and child-grid rows.
- Delete access uses module-level `can_archive` permission, displayed as **Delete** in Administration.
- Removed silent deletion/inactivation when rows are removed from an editable grid.
- Supabase RPC enforces tenant and module permission before any permanent deletion.
