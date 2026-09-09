# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.29

### 1. Authoritative controlled baseline

Use **only** this baseline for future development:

- **Application Version:** `4.14.29`
- **Build:** `41429-RMTC-BEND-CHEM-CASEDEPTH-PERMISSIONS`
- **Project path:** `/Users/dhokaleraj/QSMS`
- **Supabase project ref:** `xxrxopzxzyjnzumrwuwy`
- **Database schema required:** controlled v4.14.28 live contract; v4.14.29 has **no new database migration**.
- Preserve existing Git repository, branch/history and Streamlit Cloud deployment.
- Preserve all Supabase production/master/RMTC/OSP/Quality/Supply Chain/NPD/Complaint/Calibration data and attachments.
- Never rebuild from an older archive when this controlled baseline is available.

### 2. Permanent deployment rules

1. Every release is one self-contained macOS `.command` updater plus one copy/paste Terminal command.
2. Backup before source modification and protect dirty/uncommitted Git work with a safety stash.
3. Preserve `.git`, `.env`, `.streamlit/secrets.toml`, uploads, logs, exports, virtual environment and Supabase link state.
4. Compile, run online-readiness/phase verification, run the **complete pytest suite**, commit, push the existing branch and verify local/remote SHA.
5. Required Supabase migrations should be applied automatically during controlled release packaging whenever possible. Do not ask the user to manually run SQL unless technically unavoidable.
6. Do not reset, truncate or delete business data to solve source/schema problems.
7. Do not remove a working feature unless explicitly requested.
8. Continue versioning from **v4.14.29 → v4.14.30+**.
9. v4.14.29 is source-only and reuses the already-applied v4.14.28 schema contract; do not add a fake migration merely to increment the app version.

### 3. v4.14.29 — RMTC Approved Raw Material Source

- Part Master **Approved Sources** are stored in `part_supplier_links` while controlled RM production details are stored in `part_raw_material_details`.
- RMTC **Approved Raw Material Source** must combine both masters.
- An approved Supplier / Steel Mill with a matching ACTIVE Raw Material Detail is selectable and persists the real `selected_source_detail_id` from `part_raw_material_details`.
- If the approved Supplier / Steel Mill has no ACTIVE Raw Material Detail, it remains visible with a setup-required warning; RMTC save is blocked until Raw Material Type, Grade, Input Weight, Section Size and Forging Route are completed in Part Master.
- Parts created before Approved Sources became mandatory retain backward-compatible ACTIVE Raw Material Detail selection when no approved source links exist.

### 4. v4.14.29 — Users & Access section rights

- Unified permission precedence remains: Admin/Super Admin, explicit User override, Role defaults, Department defaults, controlled legacy fallback.
- Module permissions remain View, Create, Edit, Validate/Review, Approve, Delete/Archive.
- Section permissions remain default-visible according to effective module permission unless an explicit section override is created.
- **All QCMS modules now appear in the section-rights matrix**, not only the older partial catalog.
- The section matrix includes a readable Module column plus Module Key / Section Key and View/Create/Edit overrides.
- Confidential sections such as Part Master Price History and Supplier Technical Data remain separately controllable.
- User↔Employee link persistence and Employee Master email protection remain mandatory.

### 5. v4.14.29 — Bend Test inspection method / sub category

- Bend Test is implemented as a **MetLAB Inspection Method / Sub Category**, not as a new database `layout_type`.
- Layout Master keeps `layout_type=METLAB` and stores `inspection_method=BEND_TEST` in characteristic `layout_metadata`.
- New Bend Test layouts can load controlled starter rows based on the supplied FSI Bend Test report:
  - Baking Temperature
  - Baking Time
  - Base Metal Hardness below plating
  - Load
  - CHT
  - Bend Angle
  - Bend Test Status
  - Plating Surface Condition
- Specifications remain editable and controlled per Part/customer before approval.
- Bend Test numeric “record achieved value” characteristics may have a controlled Specification without forcing an artificial Min/Max band.
- Bend Test report output uses **BEND TEST REPORT**, **BAKING / AGING**, **BEND TEST RESULTS** and Bend Test evidence/photo labels.

### 6. v4.14.29 — Chemical analysis horizontal grid

- Linked Raw Material MetLAB chemical analysis is horizontal in the app and PDF.
- Controlled order: **C, Mn, Si, S, P, Cr, Ni, Mo, V, Al, Cu, Nb, Ti**, then any configured extra elements, with **Al/N2 Ratio last when configured**.
- App rows show Spec. Min, Spec. Max, RMTC Achieved and an editable MetLAB Achieved row.
- NA / Result / Remark remains available in the expandable per-element control.
- PDF section is titled **CHEMICAL ANALYSIS · ASTM E 415 / IS 8811** and uses the same horizontal sequence.
- Historical/extra element data is preserved; no chemistry source row is discarded simply because it is not one of the standard columns.

### 7. v4.14.29 — Case Depth Traverse checkbox and locations

- Every MetLAB Layout characteristic exposes **Case Depth Traverse** checkbox plus **Traverse Location**.
- When checked, Traverse Location is mandatory (examples: Ground Face, ID, OD).
- Multiple checked characteristics create multiple controlled traverse locations.
- Report entry reads location/specification from the approved Inspection Layout and the operator enters only distance-wise HV readings.
- Default traverse distances continue from 0.05 mm and preserve existing multi-location chart logic.
- Historical layouts whose Parameter text contains “Case Depth” remain compatible as legacy fallback.

### 8. v4.14.29 — reusable MetLAB references

- MetLAB **Specification Reference** is a reusable controlled value.
- MetLAB **Reference Documents / Statements** supports multiple selections.
- Operators can select an existing value or type a new one; new values are remembered after the report saves.
- Reusable values use existing `master_value_catalog`; no new schema is required.
- Saved Reference Documents / Statements persist in the report `results` JSON and print in a dedicated PDF section.

### 9. v4.14.29 — conclusion remark and visual result highlighting

- MetLAB report entry includes **Conclusion Remark (optional)** in addition to Conclusion, Final Decision and Decision Reason.
- Conclusion Remark persists in report `results` JSON.
- PDF conclusion block uses differentiated background/font styling:
  - Conclusion: highlighted blue, bold.
  - Conclusion Remark: separate warm highlight, italic.
  - Final Decision: status-dependent green/red/amber/blue fill and bold font.
  - Decision Reason: separate neutral row.
- Dimensional inspection PDF uses the same high-visibility conclusion/final-decision block.
- Excel Conclusion and Decision sheet also applies differentiated fill/font styling.

### 10. v4.14.29 — OSP batch identity

- Existing v4.14.28 genealogy remains authoritative: Part Number + FSI Batch Number + Vendor Batch Number wherever available.
- OSP labels now spell out **FSI Batch Number** and **Vendor Batch Number** explicitly.
- Material Out source selection also shows **Source Batch / Lot**. Released Material Inward source batch follows the existing `SRC-{inward_number}` genealogy; Opening Stock shows its lot reference.
- OSP registers continue to show FSI Batch Number and Vendor Batch Number.
- Material Out Remarks remain visible downstream at Sample Receipt, OSP Dimensional, OSP MetLAB and OSP Inward.

### 11. Preserved v4.14.28 OSP and notification baseline

Flow remains:
**Material Out → Sample Receipt → Sample Dimensional/MetLAB gate → OSP Inward → Post-receipt inspections/release**.

Preserve:
- FSI OSP batch genealogy.
- Approved OSP layout as authoritative evidence that an inspection is required.
- Part + FSI Batch + Vendor Batch selectors/context.
- Material Out remarks downstream.
- Two-day XLSX Customer Order/RM/PO/Forging Receipt digests and dedicated supply digest notifier.
- Existing daily/other schedules.

### 12. Preserved MetLAB boundary

- `part_metallurgical_requirements` is for **Final Dispatch / Customer Dispatch MetLAB only**.
- Raw Material Inward MetLAB must select an **APPROVED MetLAB Layout from Layout Master** intended for Material Inward.
- Raw Material Inward must exclude `FINAL_METALLURGICAL` layouts and must not silently fall back to Part Master metallurgical requirements.
- Historical reports keep their saved layout basis.
- Standalone/OSP MetLAB, Dimensional, conclusions, decisions, approval/reopen, images and PDF logic remain preserved.

### 13. Preserved Purchase Order / Supply Chain baseline

Preserve controlled RM and Forging POs, approvals, self-approval controls, PO edit/reapproval, cancel/reissue, supplier PO confirmation, supplier emails/supporting documents, controlled RM identity/HSN/SAC/technical data, source allocation genealogy, supply-chain overdue priority cards and all existing supply flows.

### 14. Preserved Complaint / Calibration / Standard Room / NPD baseline

Preserve Complaint Heat/Batch/photos/PDF/Excel, Calibration & Validation with gauge/fixture links and due reminders, Standard Room inspections and NPD/APQP process/status/email-card functions.

### 15. v4.14.29 acceptance checks after deployment

1. Part Master approved Supplier/Steel Mill appears in RMTC → Approved Raw Material Source when matching ACTIVE RM details exist.
2. Approved source with missing RM details is visible but clearly blocked with the setup warning.
3. Users & Access → Section View/Create/Edit lists section rows for all 16 QCMS modules.
4. MetLAB Layout Master offers **Bend Test** and a new Bend Test layout loads the controlled starter parameters.
5. Bend Test report PDF uses Bend Test title/sections and evidence labels.
6. Chemical Analysis is horizontal and follows C→Ti order; Al/N2 Ratio is last when configured.
7. Case Depth Traverse checkbox + Traverse Location can create multiple locations and report-entry traverse columns.
8. MetLAB Reference Documents / Statements can be reused and newly entered values reappear after save.
9. Conclusion Remark prints as a separate highlighted row and Final Decision is visually status-highlighted.
10. OSP selection lists show FSI Batch Number / Vendor Batch Number and Material Out source batch/lot context.
11. Existing RMTC, OSP, PO, Supply Chain, MetLAB boundary, Complaints, Calibration, Standard Room and NPD behavior shows no regression.
12. Complete pytest suite passes before packaging/deployment.

### 16. New-chat starter prompt

> Continue development of my **QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)** from controlled release **v4.14.29 / build 41429-RMTC-BEND-CHEM-CASEDEPTH-PERMISSIONS**. Read `QCMS_NEW_CHAT_HANDOVER_v4.14.29.md` first and treat it as the authoritative baseline. Preserve all Supabase data, Git history and Streamlit Cloud deployment. Continue versioning from v4.14.30 onward. Every release must be one self-contained macOS `.command` updater with backup, complete tests, Git push and remote SHA verification. v4.14.29 is source-only and uses the existing v4.14.28 database contract; do not add or request manual SQL unless a future change genuinely requires a schema migration.
