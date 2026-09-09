# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.30

### 1. Authoritative controlled baseline

Use **only** this baseline for future development:

- **Application Version:** `4.14.30`
- **Build:** `41430-RMTC-SUPPLIER-DEDUP-BEND-GLOBAL-SEARCH`
- **Project path:** `/Users/dhokaleraj/QSMS`
- **Supabase project ref:** `xxrxopzxzyjnzumrwuwy`
- **Database schema required:** controlled v4.14.28 live contract; v4.14.30 has **no new database migration**.
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
8. Continue versioning from **v4.14.30 → v4.14.31+**.
9. v4.14.30 is source-only and reuses the already-applied v4.14.28 schema contract; do not add a fake migration merely to increment the app version.

### 3. v4.14.30 — RMTC Approved Raw Material Source de-duplication

- RMTC **Approved Raw Material Source** must show **one row per approved Supplier**, regardless of how many ACTIVE Part Master Raw Material Detail rows or historical/current approved-source rows exist for that Supplier.
- Source construction groups `part_raw_material_details` and `part_supplier_links` by Supplier.
- The Supplier selector key is Supplier-based (`SUPPLIER:{supplier_id}`), not Raw Material Detail based.
- Selecting a Supplier exposes a separate **Raw Material Detail** selector containing the eligible Part Master material section / section size / forging route records.
- If the Supplier has one eligible detail, it is automatically selected. If it has multiple, the employee selects the exact detail once.
- The selected Raw Material Detail continues to persist as the real `selected_source_detail_id`; supplier de-duplication must never destroy RM section/route genealogy.
- An approved Supplier with no ACTIVE Raw Material Detail remains visible with a setup-required warning and cannot be saved until the Part Master detail is completed.
- Parts created before Approved Sources became mandatory retain backward-compatible Supplier grouping from ACTIVE raw-material details when no approved source links exist.

### 4. v4.14.30 — dedicated Bend Test discovery

- Bend Test remains a **MetLAB Inspection Method / Sub Category** (`BEND_TEST`); do not create a new incompatible database `layout_type`.
- Dedicated navigation is provided for:
  - **Inspections → Bend Test Entry**
  - **Records → Bend Test**
  - **Reports → Bend Test**
  - Inspection Home → **Bend Test Report** card
- Dedicated entry filters layouts/reports to `BEND_TEST`; general MetLAB entry remains available for all other MetLAB inspection methods.
- If no approved Bend Test layout exists for the selected Part/stage, the operator receives a clear instruction to create/approve the Bend Test Layout in Inspection Layout Master.
- Saved Bend Test records open back to the dedicated Bend Test entry through controlled record-routing logic.
- Existing v4.14.29 Bend Test starter characteristics and PDF sections remain authoritative: Baking/Aging, Load, CHT, Bend Angle, Bend Test Status, plating condition and evidence/photographs.

### 5. v4.14.30 — permission-aware Global Search

- A persistent application-shell search field is available on QCMS pages and submits to **Search → Global Search**.
- Minimum search length is two characters and search executes only on submit/Enter, avoiding a database query on every keystroke.
- Major searchable register families include:
  - Part / Material Grade / Process / Reference Party / Employee masters
  - Inspection Layouts
  - RMTC / Heat data
  - Material Inward
  - Production / FSI Batch
  - OSP jobs and receipts
  - Dimensional / MetLAB / Bend Test reports
  - Complaints
  - Customer Orders, RM Procurement, Purchase Orders, RM Receipts/Dispatch, Forging Orders/Receipts and downstream Supply Chain records
  - NPD / APQP
  - Calibration / Validation assets and records
  - Standard Room inspection records
- Search terms include, where present: Part Number, FSI Part Number, Part Name, Drawing, Heat Number/Code, RMTC, FSI Batch, Vendor Batch, Supplier/Customer/OSP Vendor, PO/order/reference numbers, report/certificate number and descriptive text.
- Part and Party master matches are expanded by controlled foreign-key relationships so linked transaction records appear even when a transaction does not duplicate the human-readable master name/number.
- Search respects existing `module_permissions(...).can_view` and the normal Repository/Supabase tenant/RLS policy. Search does not bypass security or expose a module the employee cannot View.
- One unavailable/optional register must not break the complete search; unavailable sources are skipped while all available controlled sources continue.
- Search results can be filtered by module and opened through the controlled source-module record routing.

### 6. Preserved v4.14.29 — Users & Access section rights

- Unified permission precedence remains: Admin/Super Admin, explicit User override, Role defaults, Department defaults, controlled legacy fallback.
- Module permissions remain View, Create, Edit, Validate/Review, Approve, Delete/Archive.
- Section permissions remain default-visible according to effective module permission unless an explicit section override is created.
- All controlled QCMS modules appear in the section-rights matrix.
- Confidential sections such as Part Master Price History and Supplier Technical Data remain separately controllable.
- User↔Employee link persistence and Employee Master email protection remain mandatory.

### 7. Preserved v4.14.29 — Chemical Analysis / Case Depth / references / conclusion

- Linked Raw Material MetLAB Chemical Analysis remains horizontal.
- Controlled order remains **C, Mn, Si, S, P, Cr, Ni, Mo, V, Al, Cu, Nb, Ti**, configured extras, then **Al/N2 Ratio** when configured.
- Case Depth Traverse remains an explicit per-characteristic checkbox with Traverse Location and multiple-location capability.
- Specification Reference and Reference Documents / Statements remain reusable controlled values.
- Conclusion Remark remains separate from Conclusion / Final Decision and retains differentiated report styling.

### 8. Preserved OSP genealogy and batch identity

Flow remains:
**Material Out → Sample Receipt → Sample Dimensional/MetLAB gate → OSP Inward → Post-receipt inspections/release**.

Preserve:
- Part Number + FSI Batch Number + Vendor Batch Number wherever available.
- Approved OSP layout as authoritative evidence that an inspection is required.
- Material Out Remarks downstream.
- OSP report snapshots carrying FSI Batch Number.
- Two-day XLSX Customer Order/RM/PO/Forging Receipt digests and dedicated supply digest notifier.

### 9. Preserved MetLAB boundary

- `part_metallurgical_requirements` is for **Final Dispatch / Customer Dispatch MetLAB only**.
- Raw Material Inward MetLAB must select an **APPROVED MetLAB Layout from Layout Master** intended for Material Inward.
- Raw Material Inward must exclude `FINAL_METALLURGICAL` layouts and must not silently fall back to Part Master metallurgical requirements.
- Historical reports keep their saved layout basis.
- Standalone/OSP MetLAB, Dimensional, conclusions, decisions, approval/reopen, images and PDF logic remain preserved.

### 10. Preserved RMTC / Heat baseline

- Same Heat can have multiple RMTC/TC certificates when Supplier RMTC Number differs.
- Same Heat shares canonical Internal Heat Code/global Heat balance.
- Each approved RMTC remains independently selectable for Material Inward.
- **Add New RMTC for This Heat Number** creates a fresh certificate while retaining only Heat/Internal Heat Code context.
- Approved RMTC may add Part worksheets with validation/decision without invalidating already accepted Parts.

### 11. Preserved Purchase Order / Supply Chain baseline

Preserve controlled RM and Forging POs, approvals, self-approval controls, PO edit/reapproval, cancel/reissue, supplier PO confirmation, supplier emails/supporting documents, controlled RM identity/HSN/SAC/technical data, source allocation genealogy, supply-chain overdue priority cards and all existing supply flows.

### 12. Preserved Complaint / Calibration / Standard Room / NPD baseline

Preserve Complaint Heat/Batch/photos/PDF/Excel, Calibration & Validation with gauge/fixture links and due reminders, Standard Room inspections and NPD/APQP process/status/email-card functions.

### 13. v4.14.30 acceptance checks after deployment

1. RMTC → Approved Raw Material Source shows each approved Supplier exactly once even when Part Master has multiple Raw Material Detail/source records for that Supplier.
2. Selecting that Supplier exposes the required **Raw Material Detail** choice separately; exact `selected_source_detail_id`, RM Section and Forging Route are preserved.
3. Approved Supplier with no ACTIVE Raw Material Detail remains visible with the controlled setup warning and cannot be saved incorrectly.
4. **Inspections → Bend Test Entry** is visible and opens the dedicated Bend Test report entry.
5. **Records → Bend Test** and **Reports → Bend Test** show only Bend Test records/reports.
6. Inspection Home contains a visible **Bend Test Report** card.
7. The persistent QCMS Global Search accepts Part/Heat/RMTC/Batch/Supplier/Customer/PO/Report searches and opens the controlled source record.
8. Searching a Part Number or Supplier/Customer name can surface linked transaction records through relationship expansion.
9. Employees without View permission for a module receive no results from that module; tenant/RLS controls remain effective.
10. Existing horizontal Chemical Analysis, Case Depth Traverse, reusable references, Conclusion formatting, OSP genealogy, RMTC, PO/Supply Chain, MetLAB boundary, Complaints, Calibration, Standard Room and NPD behavior shows no regression.
11. Online-readiness and phase verification pass.
12. Complete pytest suite passes before packaging/deployment.

### 14. New-chat starter prompt

> Continue development of my **QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)** from controlled release **v4.14.30 / build 41430-RMTC-SUPPLIER-DEDUP-BEND-GLOBAL-SEARCH**. Read `QCMS_NEW_CHAT_HANDOVER_v4.14.30.md` first and treat it as the authoritative baseline. Preserve all Supabase data, Git history and Streamlit Cloud deployment. Continue versioning from v4.14.31 onward. Every release must be one self-contained macOS `.command` updater with backup, complete tests, Git push and remote SHA verification. v4.14.30 is source-only and uses the existing v4.14.28 database contract; do not add or request manual SQL unless a future change genuinely requires a schema migration.
