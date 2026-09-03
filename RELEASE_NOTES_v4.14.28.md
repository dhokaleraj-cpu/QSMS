# QCMS v4.14.28 Release Notes

**Build:** `41428-OSP-BATCH-GENEALOGY-TWO-DAY-EXCEL`

## OSP genealogy and selector identity

- OSP Material Out now exposes the generated Four Star Industries/QCMS **FSI Batch Number**.
- Sample Receipt, OSP Dimensional, OSP MetLAB, OSP Inward and OSP Records show **Part Number + FSI Batch Number + Vendor Batch Number** in selectors/context.
- Material Out Remarks are carried and displayed at Sample Receipt, OSP inspections and OSP Inward.
- OSP inspection report snapshots persist the FSI Batch Number in `batch_number`.

## Sample Dimensional queue reliability

- An APPROVED OSP Dimensional/MetLAB Layout is authoritative evidence that the corresponding inspection is required.
- Legacy Process Specification flags are synchronized from approved OSP layouts.
- Open OSP jobs have `required_tests` synchronized so UI eligibility and the database quality gate use the same requirement.
- This corrects cases where Sample Receipt existed but OSP Dimensional showed no pending/new records despite an approved Dimensional layout.

## Two-day Excel notification digests

A dedicated `qcms-supply-digest-notifier` Edge Function sends these internal schedules every two days:

1. **Overdue Customer Orders** — XLSX to Supply Chain, Marketing/Business Development, Management and Procurement/Purchasing routing.
2. **Pending RM Orders / RM Procurement** — XLSX to Supply Chain.
3. **Pending Purchase Orders** — XLSX to Supply Chain.
4. **Pending/Overdue Forging Receipts** — XLSX to Supply Chain.

The scheduler now supports:
- `run_every_days`
- multiple `recipient_departments`
- `export_format` (`PDF`, `XLSX`, `BOTH`)

Recipient routing understands controlled department/role aliases for Marketing/Business Development and Procurement/Purchasing while preserving exact employee/department routing.

## Preserved v4.14.27 controls

- Part Master metallurgical requirements remain **Final Dispatch MetLAB only**.
- Raw Material Inward MetLAB uses an approved Layout Master plan and excludes Final Metallurgical layouts.
- Forging PO release email template and database/context field picker remain active.
- All v4.14.26 Calibration, Standard Room, Complaints, NPD cards, Supply Chain priority cards and earlier controlled functions remain preserved.

## Deployment

- Version: `4.14.28`
- Build: `41428-OSP-BATCH-GENEALOGY-TWO-DAY-EXCEL`
- Live migration: `20260903103000_qcms_v41428_osp_batch_two_day_excel_digest.sql`
- No production data reset or truncation is permitted.

### Duplicate-email protection

- The dedicated supply digest notifier is separate from the general `qcms-overdue-notifier`, so existing daily/NPD/Calibration notifications remain unchanged.
- Interim `*_2DAY` schedule rows created during release development are disabled.
- The active Every-2-Days schedules use one dedicated state table and one cron job: `qcms-supply-digest-notifier-hourly`.
- Live Edge Function baseline: `qcms-supply-digest-notifier` v1 / ACTIVE.
