# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.26

### 1. Authoritative controlled baseline

Treat the following as the **only authoritative baseline** for continued development:

- **Application Version:** `4.14.26`
- **Build:** `41426-COMPLAINT-MEDIA-CALIBRATION-STANDARD-ROOM-NPD-CARDS`
- **Project path on Rajesh's Mac:** `/Users/dhokaleraj/QSMS`
- **Git repository:** existing QSMS repository; preserve current branch and history.
- **Streamlit Cloud:** preserve existing deployment; source push to the existing Git branch triggers deployment.
- **Supabase project ref:** `xxrxopzxzyjnzumrwuwy`
- **Live Supabase schema:** **v4.14.26 is already applied and verified**.
- **Live overdue notifier Edge Function:** `qcms-overdue-notifier` **version 4 / ACTIVE / verify_jwt=false**.
- **Full source regression at release packaging:** **461/461 tests passed**.
- **Registered Streamlit pages:** 83.

Do not rebuild from v4.14.25, v4.14.24, older archives, or old conversation snippets. v4.14.26 includes all prior controlled functions plus the changes below.

---

### 2. Permanent release/deployment rules

These are non-negotiable unless the user explicitly changes them:

1. Preserve **all existing Supabase production data**, including Masters, RMTC, Material Inward, OSP, Quality reports, Complaints, Supply Chain, NPD/APQP, User/Employee mappings, notifications and attachments.
2. Never reset, truncate, recreate or delete production data to solve a source issue.
3. Preserve the existing `.git`, branch, remote and Streamlit Cloud deployment.
4. Preserve `.env`, `.streamlit/secrets.toml`, uploads, logs, exports and `supabase/.temp`/link state.
5. Every release must be delivered as **one self-contained macOS `.command` updater** plus one copy/paste Terminal command.
6. The updater must create a backup before source modification and protect dirty/uncommitted work with a Git safety stash.
7. The updater must compile source, run readiness/phase verification, run the **complete pytest suite**, commit, push the existing branch and compare local/remote SHA.
8. Required Supabase migrations should normally be applied automatically during controlled release packaging. Do not ask the user to manually run SQL unless automatic migration is technically impossible.
9. Repeated Mac-side Supabase CLI/Data-API verification gates caused false deployment failures in v4.14.20–v4.14.22. For a release whose migration is already applied live, the `.command` should be **source-only and must not block on Supabase login, access token, curl, DNS, or API verification**.
10. Never remove a previously working function unless explicitly requested.
11. Continue versioning from **v4.14.26 → v4.14.27+**.

---

### 3. Core access-control architecture that must remain

Effective permissions are intended to drive both UI and database actions, not just button visibility.

- Super Admin / Admin authority remains highest.
- Permission precedence uses explicit User controls with Role and Department configuration/fallback according to the controlled permission engine introduced in v4.14.18+.
- Module permissions include View, Create, Edit, Validate/Review, Approve and Delete/Archive.
- Section permissions are default-visible and allow controlled hiding/creation/editing of confidential sections such as Part Master Price History.
- Role and Department are linked in Users & Access.
- Employee ↔ User links must persist and Employee Master email must never be overwritten by login email.
- Top-level authority (Rajesh Dhokale / Management / Vice President) can have **no Reports-To**.
- User and database activity auditing remains required for create/update/delete and significant user actions.
- Transactions use `qcms_delete_transaction_row`; Masters use `qsms_delete_master_row`. Never route a transaction through the master-delete RPC.

---

### 4. Purchase Order / Supply Chain controlled baseline

Preserve all previously implemented PO functionality:

- Controlled RM and Forging Purchase Orders.
- Live employee/requisitioner resolution.
- Explicit User/Role/Department permissions must allow the real database action if Create/Edit is granted.
- PO status and approval workflow: new/revised PO → Pending Approval → approved controlled PO.
- Configured approval route before Reports-To fallback; self-approval controlled.
- Pending PO cannot be received against.
- PO cancel + reissue with alternate supplier, releasing source allocations.
- Controlled PO editing added in v4.14.25. Supplier and source Part identity remain genealogy-protected; supplier change uses Cancel & Reissue.
- PO revisions refresh current master snapshot and require reapproval and supplier reconfirmation while historical values remain in audit.
- Supplier PO confirmation stage after PO approval, with confirmation reference/date, confirmed delivery date, remarks and attachment.
- Downstream receipt is gated until supplier confirmation, while historical receipt genealogy remains protected.
- Daily supplier PO confirmation reminder until confirmation is recorded.
- Daily PO Pending Approval and RM Procurement Pending/Due/Overdue notifications.
- PO print layout includes HSN/SAC, RM Type, Grade, Section Size and Supplier Technical Data rows checked **Include on PO**.
- Same supplier RM or forging used by multiple finished Parts can be consolidated on the supplier-facing PO when controlled item identity/technical/commercial conditions match, while each Finished Part / Customer Order quantity allocation remains traceable.
- v4.14.25 performance work uses page cache/bulk totals to reduce PO loading time.
- **v4.14.26 Supply Chain Home:** overdue Customer Orders display first as red priority cards showing Customer, Part, Delivery, Days Overdue and Next Stage.

Supply Chain flows that must remain traceable:

- FSI RM → RM PO/Receipt → Forger route → Forging Receipt → Production → Dispatch.
- Supplier-responsible RM → Forging route → Production → Dispatch.
- FSI RM → Direct Production (no forging) → Dispatch.
- Opening Stock / OSP route and existing Material Inward bridge.

---

### 5. RMTC / Heat rules that must remain

- Same Heat can have multiple QCMS RMTC/TC records when Supplier RMTC/TC number is different.
- Same Heat shares one internal/canonical Heat Code and global Heat quantity/balance logic.
- Each separately approved RMTC remains selectable for Material Inward.
- “Add New RMTC for This Heat Number” must create a **blank new certificate** and keep only Heat context/Internal Heat Code; it must not carry the old Supplier RMTC, Part selection, source, Steel Mill, quantity, Prepared By, dates or remarks.
- A new RMTC/TC has its own certified quantity while the global Heat ledger combines the Heat capacity/commitment according to existing controls.
- Approved RMTC can add additional Part Numbers through the controlled worksheet/validation/decision logic.
- Preserve global Heat balance, planned production steel and inbound steel genealogy.

---

### 6. Master and transaction editing baseline

v4.14.25 fixed stale Streamlit state. Preserve these rules:

- Selecting an existing Master/transaction must load the exact persisted row, not another record's previous widget values.
- Record widget namespaces use Record ID + updated timestamp/record token.
- Reference-master learned values must put the saved value first.
- **New Record** must start blank rather than carrying the previous Master record.
- Records Centre has controlled edit routing back to source modules.
- All controlled transactions should have a practical Edit route where business genealogy allows it.
- Latest Master data applies to new transactions and can refresh controlled editable transactions when reopened/saved, while historical/audit snapshots remain traceable.

---

### 7. OSP baseline

Preserve:

- Material Out, Sample Receipt, OSP Dimensional, OSP MetLAB and OSP Inward flows.
- Direct Edit/Delete controls with module permissions and current-password confirmation.
- OSP delete restores/reverses eligible source allocation and blocks unsafe deletion once downstream genealogy depends on the record.
- OSP Dimensional/MetLAB finalized records use controlled reopen/edit logic.
- OSP sample/full-inward quality gates and production release gates remain intact.

---

### 8. MetLAB / Dimensional baseline

Preserve:

- Standalone and OSP reports.
- RLS Create/Edit permission alignment fixed in v4.14.18/19.
- Conclusion, Final Decision, Decision Reason, Prepared/Validated/Approved employee logic.
- Case Depth/Microhardness traverse logic and graphs.
- Microstructure images accept PNG/JPG/JPEG/BMP/TIF/TIFF/WEBP/GIF where supported.
- PDF/Excel print/download and report-number logic.
- Actual photographs in applicable report PDFs.

---

### 9. Complaint Management — v4.14.26 additions

Both Customer Complaint and Supplier Complaint now require/preserve:

- **Heat Number** field.
- **Batch Code / Lot Number** field.
- Multiple photographs and attachments.
- Actual complaint photographs embedded into the complaint PDF print layout.
- Actual photographs embedded in the complaint Excel workbook on a Photographs sheet, plus attachment register.
- PDF and Excel downloads available directly at the relevant complaint Entry/Analysis/Records screen level.
- Complaint search/register includes Heat and Batch identity.
- Existing 5-Why, Root Cause, CAPA/multiple actions, follow-up, Debit Note/Commercial Settlement, closure/effectiveness and approval logic remains.

---

### 10. Calibration & Validation — new v4.14.26 module

New module permission key: **`CALIBRATION_VALIDATION`**.

New Streamlit pages:

- `calibration-validation`
- `standard-room-inspection`

Existing `quality_assets` remains the controlled Gauge/Fixture/Instrument master. v4.14.26 adds validation-specific master fields and these new transaction tables:

- `quality_asset_part_process_links`
- `quality_asset_calibration_records`
- `standard_room_inspection_records`

#### Part / Process → Gauge / Fixture link

Each controlled Quality Asset can be linked to:

- Part Number
- Process
- Calibration / Validation / Both
- Characteristic / intended use
- Frequency
- Responsible employee
- Last service date
- Next due date
- Active/inactive status

Controlled frequencies currently include:

- 1 Month = 30 days
- 3 Months = 90 days
- 6 Months = 180 days
- 1 Year = 365 days
- 2 Years = 730 days
- Custom

Asset attachments include:

- Gauge / Fixture Drawing
- Gauge / Fixture Photograph
- Reference/Instruction

#### Calibration / Validation record

Records include:

- Calibration or Validation
- Service date
- Result: Accepted / Limited Use / Rejected / Pending
- Report Number
- Certificate Number
- Agency
- Performed/verified by employee
- Next Due Date
- Status and remarks
- Calibration/Validation report attachment
- Calibration certificate attachment
- Same-screen PDF and Excel download
- Password-protected controlled delete

An accepted/limited-use record updates the controlled next due date and applicable Quality Asset master date fields.

#### Daily Quality reminder

Schedule key: **`CALIBRATION_VALIDATION_DUE`**

- Enabled live.
- 08:00 Asia/Kolkata.
- 30-day advance window.
- Includes overdue and open/due records.
- Recipient Department: **Quality**.
- Template: `CALIBRATION_VALIDATION_DUE_DIGEST`.
- The reminder repeats daily until the applicable controlled record updates the next due date beyond the due window.

---

### 11. Standard Room Inspection — new v4.14.26 module

Supported instrument types include:

- CMM
- Counter
- VMM
- Roughness Tester
- Height Gauge
- Profile Projector
- Roundness Tester
- Contour Tracer
- Hardness Tester
- Other

Each inspection can record:

- Inspection date
- Report number
- Controlled Quality Asset/instrument
- Instrument type
- Part Number
- Process
- Heat Number
- Batch Code
- Quantity inspected
- Pass / Fail / Hold / Pending
- CMM/VMM program or method reference
- Operator/Inspector employee
- Remarks
- Report/output attachment
- Inspection/setup photograph
- Same-screen PDF and Excel
- Register with Created By User, Last Modified By User and Data Entry Status
- Password-protected controlled delete

---

### 12. NPD / APQP email status cards — v4.14.26

The live `qcms-overdue-notifier` Edge Function is now **version 4 ACTIVE** and includes visual NPD process-stage cards in `NPD_PROCESS_OPEN_OVERDUE` email bodies.

Card status contract:

- **Completed:** green (`#DCFCE7`, dark green text)
- **Overdue:** red
- **In Process:** blue
- **On Hold:** purple
- **Pending:** amber

Email summary shows Part, Order, Customer, Delivery and Progress. Process cards show Operation, Process name, status and target date. The user supplied screenshot of NPD cards is the intended visual reference.

---

### 13. Notifications already active/preserved

Do not remove existing notification schedules/functions:

- Customer Order open/overdue
- PO Pending Approval
- RM Procurement pending/due/overdue
- RM PO open/overdue
- Forging order open/overdue
- OSP expected return open/overdue
- NPD process open/overdue
- Supplier PO Confirmation daily reminder
- **Calibration/Validation due (new v4.14.26)**

Edge functions currently relevant:

- `qsms-user-admin` — v5 ACTIVE
- `qcms-send-email` — v3 ACTIVE
- `qcms-overdue-notifier` — **v4 ACTIVE**
- `qcms-po-confirmation-reminder` — v2 ACTIVE

---

### 14. v4.14.26 live database verification

Controlled release packaging verified on live Supabase:

- `qcms_release_schema_version()` → `4.14.26`
- `quality_asset_part_process_links` exists
- `quality_asset_calibration_records` exists
- `standard_room_inspection_records` exists
- new tables map to module `CALIBRATION_VALIDATION`
- `QUALITY_ASSET` and `CALIBRATION_RECORD` attachments map to `CALIBRATION_VALIDATION`
- `CALIBRATION_VALIDATION_DUE` schedule is ACTIVE, 8am Asia/Kolkata, 30 days ahead, includes overdue/open, recipient department Quality.

The v4.14.26 `.command` should therefore be source-only with **no Mac-side Supabase login/API verification gate**.

---

### 15. Current release acceptance checks

Before calling v4.14.26 stable in a fresh chat, verify live after Git/Streamlit deployment:

1. Customer Complaint: save Heat + Batch; attach multiple images; PDF contains photos; Excel contains embedded photos.
2. Supplier Complaint: same checks.
3. Complaint same-screen PDF/Excel works.
4. Supply Chain Home shows overdue Customer Orders first in red priority cards.
5. Calibration & Validation is visible to appropriately permitted Quality users.
6. Link Gauge/Fixture to Part + Process and set 1-month / 6-month / 1-year/custom frequency.
7. Attach Gauge/Fixture drawing/photo.
8. Save Calibration/Validation record and verify next due date updates.
9. Standard Room Inspection can save CMM/VMM/Roughness/Counter records with Part + Heat + Batch.
10. Standard Room PDF/Excel works.
11. NPD overdue email shows process cards and completed cards green.
12. No previous PO/RMTC/OSP/permissions functions regress.

---

### 16. New-chat starter prompt

Paste this in the next chat and attach this handover plus the latest `.command` file:

> Continue development of my **QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)** from controlled release **v4.14.26 / build 41426-COMPLAINT-MEDIA-CALIBRATION-STANDARD-ROOM-NPD-CARDS**. Read the attached `QCMS_NEW_CHAT_HANDOVER_v4.14.26.md` first and treat it as the authoritative continuity baseline. Preserve all Supabase data, Git history and Streamlit Cloud deployment. Continue versioning from v4.14.27 onward. Every release must be one self-contained macOS `.command` updater with backup, complete tests, Git push and remote SHA verification. The live v4.14.26 Supabase schema is already applied, and `qcms-overdue-notifier` v4 is active. Do not rebuild from older archives or remove any working function unless explicitly requested.



---
# v4.14.27 ADDENDUM — FINAL METLAB / PO EMAIL TEMPLATE FIELDS

Authoritative version: **4.14.27** / build **41427-FINAL-METLAB-LAYOUT-PO-EMAIL-FIELDS**.

1. **MetLAB source boundary**
   - `part_metallurgical_requirements` is reserved only for the Final Dispatch / customer-dispatch MetLAB layout.
   - Raw Material Inward MetLAB must select an approved MetLAB layout from Inspection Layout Master.
   - Raw Material stage selection excludes `requirement_scope = FINAL_METALLURGICAL`.
   - No automatic RMTC/Part-Master fallback is allowed when an approved Raw Material Inward Layout Master plan is missing.
   - Historical saved reports retain their saved layout basis for traceability.

2. **Email template database fields**
   - Admin → Email Server & Notifications → Module Email Templates provides a database/context field picker.
   - Fields display the QCMS source table/relationship and insert placeholders into Subject or Body.
   - Purchase Order context includes aggregated supplier-facing Part Number(s), original Part Number(s), quantity, UOM, item description, PO dates, supplier and commercial header fields.

3. **Forging PO release template**
   - `FORGING_PO_CREATED` is the controlled supplier release template and includes generated PO PDF + available supporting documents.
   - After approval QCMS uses the RM/Forging release event rather than the generic `PO_APPROVED` supplier email.
   - Supplier PO Confirmation remains a separate stage; daily priority reminders continue until signed confirmation is recorded.

4. **Deployment**
   - Live Supabase migration `qcms_v41427_final_metlab_layout_po_email_fields` is applied and verified.
   - Future macOS updater is source-only for this release; no manual SQL or Supabase login is required.
