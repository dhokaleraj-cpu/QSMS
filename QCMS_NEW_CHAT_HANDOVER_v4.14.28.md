# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.28

### 1. Authoritative controlled baseline

Use **only** this baseline for future development:

- **Application Version:** `4.14.28`
- **Build:** `41428-OSP-BATCH-GENEALOGY-TWO-DAY-EXCEL`
- **Project path:** `/Users/dhokaleraj/QSMS`
- **Supabase project ref:** `xxrxopzxzyjnzumrwuwy`
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
8. Continue versioning from **v4.14.28 → v4.14.29+**.
9. Avoid Mac-side `supabase login`/access-token/network verification as a hard deployment gate after a release migration has already been applied and verified live.

### 3. Permissions / User / Employee baseline

- Effective access is controlled by the unified permission engine: Admin/Super Admin, explicit User override, Role defaults, Department defaults, then controlled legacy fallback.
- Module permissions: View, Create, Edit, Validate/Review, Approve, Delete/Archive.
- Section permissions are default-visible and can hide confidential sections such as Price History and Supplier Technical Data.
- Role + Department + Employee are linked in Users & Access.
- User↔Employee link must persist after role/permission updates.
- Employee Master email must never be overwritten by login email.
- Top-level authority may have no Reports-To.
- Create/update/delete and significant user actions remain auditable.
- Transaction deletes use `qcms_delete_transaction_row`; master deletes use `qsms_delete_master_row`.

### 4. Master / transaction edit baseline

- Selecting an existing record must load that exact persisted record, never stale values from another Streamlit widget state.
- Record widget namespace is tied to selected record identity/update token.
- **New Record** opens a blank form.
- Records Centre can route a selected record to its controlled module editor.
- Controlled transactions should be editable where genealogy allows it; downstream-dependent changes can be blocked.
- Latest master data is used for new transactions and may refresh controlled edited transactions while prior values remain traceable in audit/history.

### 5. Purchase Order / Supply Chain baseline

Preserve:

- Controlled RM and Forging POs.
- Live employee/requisitioner resolution.
- Pending Approval → configured approver/Reports-To → approved/open workflow; self-approval controls.
- Pending POs cannot be received against.
- PO editing with reapproval and supplier reconfirmation.
- Cancel & Reissue with alternate supplier and released source allocations.
- Supplier PO Confirmation with attachment and daily supplier reminder until confirmation.
- PO PDF includes controlled RM identity, HSN/SAC, Supplier Technical Data rows checked **Include on PO**, price/history data as configured.
- Same purchased RM/forging can support multiple finished Parts/Customer Orders while supplier-facing PO lines may consolidate when controlled identity/commercial conditions match; genealogy remains per source allocation.
- Supply Chain Home shows overdue Customer Orders first in red priority cards.
- PO page performance uses bulk/cached lookups rather than repeated per-row queries.

Supply flows remain:
- FSI RM → RM PO/Receipt → RM to Forger → Forging → Forging Receipt → Production → Dispatch.
- Supplier/Forger RM → Forging → Receipt → Production → Dispatch.
- FSI RM → Direct Production → Dispatch.

### 6. RMTC / Heat baseline

- Same Heat can have multiple RMTC/TC certificates when Supplier RMTC Number differs.
- Same Heat shares canonical Internal Heat Code/global Heat balance.
- Each approved RMTC remains independently selectable for Material Inward.
- **Add New RMTC for This Heat Number** must create a blank new certificate and retain only Heat/Internal Heat Code context.
- New RMTC has its own certified quantity; global Heat ledger combines controlled capacity/commitments.
- Approved RMTC may add Part worksheets with validation/decision without invalidating already accepted Parts.

### 7. MetLAB boundary — mandatory from v4.14.27

- `part_metallurgical_requirements` is for **Final Dispatch / Customer Dispatch MetLAB only**.
- Part Master Final Metallurgical requirements generate/use the Final Dispatch Metallurgical layout.
- Raw Material Inward MetLAB must select an **APPROVED MetLAB Layout from Layout Master** intended for Material Inward.
- Raw Material Inward must exclude `FINAL_METALLURGICAL` layouts and must not silently fall back to Part Master metallurgical requirements.
- Historical reports keep their saved layout basis.
- Standalone/OSP MetLAB, Dimensional, case depth/microhardness, conclusions, decisions, approval/reopen and image/PDF logic remain preserved.
- Microstructure images support common formats including BMP.

### 8. OSP baseline and v4.14.28 genealogy rules

Flow remains:
**Material Out → Sample Receipt → Sample Dimensional/MetLAB gate → OSP Inward → Post-receipt inspections/release**.

v4.14.28 requirements:

- Every OSP job has a Four Star Industries/QCMS **FSI Batch Number** (`osp_batch_code`) generated from the controlled OSP child production batch.
- OSP selectors/context show **Part Number + FSI Batch Number + Vendor Batch Number** wherever available.
- Material Out Remarks are displayed downstream at Sample Receipt, OSP Dimensional, OSP MetLAB and OSP Inward.
- OSP inspection report snapshots persist the FSI Batch Number in the report batch field.
- An **APPROVED OSP inspection layout is authoritative** evidence that its inspection type is required even if an old Part Process Specification flag is false.
- Migration synchronizes Process Specification flags and open `osp_jobs.required_tests` from approved OSP layouts.
- The OSP quality gate and UI queue must therefore agree.

Live investigation motivating v4.14.28:
- Job `OSP-D9-2026-00004`, Part `40257237`, Heat `A41489` had Sample Receipt recorded and an APPROVED Dimensional layout (`7237 DIMENSIONAL AFTER CC`) but old `dimensional_required=false`, hiding the Sample Dimensional queue.
- v4.14.28 fixes this class of mismatch globally, not only this one job.

### 9. Complaint / Calibration / Standard Room / NPD baseline

Preserve v4.14.26 functions:

- Customer/Supplier Complaints: Heat Number, Batch Code, photos embedded in PDF/Excel, same-screen PDF/Excel.
- Calibration & Validation: Gauge/Fixture → Part → Process links; drawings/photos; frequency (1m/3m/6m/1y/2y/custom); calibration/validation history and next-due date; daily 30-day-prior Quality reminders; reports/certificates.
- Standard Room Inspection: CMM, Counter, VMM, Roughness Tester, Height Gauge, Profile Projector, Roundness, Contour, Hardness, Other; Part/Process/Heat/Batch; status; report/photos; PDF/Excel.
- NPD overdue email body shows operation cards; Completed green, Overdue red, In Process blue, Hold purple, Pending amber.

### 10. PO supplier email baseline — v4.14.27

Controlled `FORGING_PO_CREATED` supplier release template:

Dear Supplier,

Forging Purchase Order `{{po_number}}` has been released through QCMS.
Supplier: `{{supplier_name}}`
Part Number: `{{part_number}}`
Quantity: `{{quantity}}`
Delivery Date: `{{delivery_date}}`
Next Stage: `{{next_stage}}`

Please send us the order confirmation in next 2-3 days with duly stamp and sign.

The controlled Purchase Order PDF and available supporting documents are attached.

Regards,
Four Star Industries Pvt Ltd
Purchasing Team

- Sent after PO approval/release.
- Controlled PO PDF + available supporting documents attached.
- Supplier PO Confirmation remains a separate downstream stage.
- Admin Email Templates includes a database/context field picker to insert placeholders into Subject/Body.

### 11. Notification schedules — v4.14.28

Preserve all existing schedules plus these new internal **every-two-day Excel** digests:

1. `CUSTOMER_ORDER_OVERDUE_BIENNIAL` (internal legacy key; cadence is every **2 days**)
   - Overdue Customer Orders.
   - XLSX.
   - Recipient routing: Supply Chain, Marketing/Business Development, Management, Procurement/Purchasing.
2. `RM_PENDING_BIENNIAL`
   - Pending/overdue RM Procurement requirements.
   - XLSX to Supply Chain.
3. `PO_PENDING_BIENNIAL`
   - Pending Purchase Orders requiring action.
   - XLSX to Supply Chain.
4. `FORGING_RECEIPT_OVERDUE_BIENNIAL`
   - Outstanding overdue Forging Receipt quantities.
   - XLSX to Supply Chain.

Delivery uses the dedicated `qcms-supply-digest-notifier` Edge Function and `qcms-supply-digest-notifier-hourly` cron. The interim duplicate `*_2DAY` schedules are disabled.

Scheduler supports:
- `run_every_days`
- multiple `recipient_departments`
- `export_format` = PDF / XLSX / BOTH

Recipient alias rules are future-safe:
- Marketing also matches Business Development/Sales or BUSINESS_DEVELOPMENT role.
- Procurement also matches Purchasing/Purchase or PROCUREMENT role.
- Supply Chain and Management match controlled department/role identities.

### 12. v4.14.28 acceptance checks after deployment

1. OSP Sample Receipt selector shows Part Number + FSI Batch Number + Vendor Batch Number.
2. Sample Receipt page shows Material Out Remarks.
3. Job `OSP-D9-2026-00004` appears in **OSP Dimensional → Pre-inward Sample → Pending/New** after schema synchronization.
4. OSP Dimensional/MetLAB context shows Part + FSI Batch + Vendor Batch + Material Out Remarks.
5. OSP Inward selector/context shows Part + FSI Batch + Vendor Batch + Material Out Remarks.
6. Report snapshot carries FSI Batch Number.
7. Two-day Customer Order digest produces XLSX and routes to configured Supply Chain/Marketing/Management/Procurement recipients.
8. Two-day RM Order, PO Pending and Forging Receipt overdue digests produce XLSX for Supply Chain.
9. Existing daily/other schedules continue to function.
10. No regression in RMTC, MetLAB boundary, PO email/confirmation, Complaints, Calibration, Standard Room, NPD, User permissions or delete/edit controls.

### 13. New-chat starter prompt

Paste this into a new chat and attach this handover + latest `.command` file:

> Continue development of my **QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)** from controlled release **v4.14.28 / build 41428-OSP-BATCH-GENEALOGY-TWO-DAY-EXCEL**. Read `QCMS_NEW_CHAT_HANDOVER_v4.14.28.md` first and treat it as the authoritative baseline. Preserve all Supabase data, Git history and Streamlit Cloud deployment. Continue versioning from v4.14.29 onward. Every release must be one self-contained macOS `.command` updater with backup, complete tests, Git push and remote SHA verification. Do not rebuild from older archives or remove working functions unless explicitly requested.
