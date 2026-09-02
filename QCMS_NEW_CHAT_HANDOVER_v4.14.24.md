# QCMS v4.14.24 handover

Authoritative release: **4.14.24 / 41424-PO-TECH-GRID-LIVE-IMPORT-APQP-DATE**.

This is a source-only release on the already-controlled v4.14.22+ Supabase schema. It preserves all previous v4.14.23 same-Heat RMTC, blank-master and transaction delete-routing fixes.

New contracts:
1. Supplier Technical Data rows checked **Include on PO** must print in the controlled PO PDF as an item-specific grid.
2. Master Import downloads must include current live master-data reference sheets; users fill variable/new values only and use exact current master values.
3. APQP overdue KPI must tolerate blank/invalid due dates without page failure.

Deployment remains one self-contained macOS `.command`, with backup, compile/readiness/phase verification, full pytest, non-blocking database baseline status, existing Git branch push and remote SHA verification.
