# QCMS / QSMS New-Chat Handover — v4.14.1

## Continuation instruction
Start a new ChatGPT conversation, attach/reference this file and say:

> Continue QCMS development from v4.14.1. Preserve all existing data, workflows, UI contracts and deployment conventions in this handover.

This file is the controlled continuity baseline for subsequent QCMS development.

---

## Current release
- Product name: **QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)**
- Version: **4.14.1**
- Build: **4141-HEAT-SUM-METLAB-TRAVERSE-LOGIN-APPROVAL-PO-PRICE**
- Live local project folder: `/Users/dhokaleraj/QSMS`
- Git deployment: existing repository/branch must always be preserved.
- Supabase project: **QSMS** (`xxrxopzxzyjnzumrwuwy`)
- Streamlit Cloud deploys from the existing GitHub repository.

### Deployment convention
Always deliver one self-contained `.command` file and one Terminal command. The user does not want separate/manual SQL steps.

Preferred command pattern:

```bash
cd /Users/dhokaleraj/QSMS && chmod +x ~/Downloads/QSMS_LIVE_DEPLOY_UPDATE_vX.Y.Z.command && (xattr -d com.apple.quarantine ~/Downloads/QSMS_LIVE_DEPLOY_UPDATE_vX.Y.Z.command 2>/dev/null || true) && ~/Downloads/QSMS_LIVE_DEPLOY_UPDATE_vX.Y.Z.command
```

Updater requirements:
1. Backup before modifying source.
2. Preserve `.git`, `.venv`, `.env`, `.streamlit/secrets.toml`, uploads/logs/exports.
3. No data reset/delete unless explicitly requested.
4. Compile source.
5. Run `scripts/check_online_readiness.py`.
6. Run `scripts/verify_phase1.py`.
7. Run complete pytest suite.
8. Commit controlled source to the existing Git repo and push the existing branch.
9. Do not ask for a Supabase `YES` confirmation.
10. If a DB migration is required, apply it directly to QSMS Supabase while preparing the release.

---

# Non-regression rules

## Data
- Existing production/master/quality/Supply Chain/RMTC/OSP data must be preserved.
- Migrations are additive or carefully backward-compatible.
- Do not reset Supabase data during normal updates.
- Duplicate-safe imports: existing rows are skipped; only missing/new records are imported unless an explicit controlled update workflow is requested.
- Major master duplicate matching also checks meaningful 2–3 word similarity.

## Identity and confidentiality
- `Part Number` = original/customer part identity.
- `FSI Part Number` = secondary/internal/supplier-facing identity.
- Both should be separately available throughout QCMS where Part Number is used.
- Supplier-facing Purchase Orders use **FSI Part Number** so confidential original/customer identity is not exposed.

## UI contract
Current enterprise visual direction:
- Deep maroon/red top header on authenticated pages.
- Dark charcoal left navigation rail with white text and maroon active selection.
- Login is isolated: no app menubar/side rail.
- Login left side uses the Four Star factory image cropped to its frame; right side is the IDENTIFICATION panel.
- Workspace is white/light neutral grey.
- Labels are bold/dark; major headings and collapsible section titles are bold maroon.
- Fields/read-only pockets use white/light-neutral backgrounds with visible grey borders; no yellow field fill.
- Tables/grids have deterministic borders/header styling.
- KPI/status cards must keep icon column separate from text so icons never overlap labels/values.
- Collapsible A/B/C... sections must remain clearly styled as headings rather than body text.
- Footer on login and all authenticated pages:
  **Developed by Rajesh Dhokale | dhokaleraj@icloud.com | Copyrights by STAWN**

---

# Major functional modules

## RMTC
- RMTC Header → Part Worksheet → Validation/Decision → Material Inward eligibility.
- Same heat/certificate can cover multiple Parts.
- Approved RMTC can be extended with another compatible Part via **Approved RMTC · Add Part Worksheet**.
- Existing Accepted Parts remain released while newly added Part goes through its own Part Worksheet, automated validation and final decision.
- v4.14.0 also exposes added-Part validation/decision controls from the main RMTC Validation & Decision screen when RMTC is `PARTIALLY_APPROVED`.
- Same approved RMTC may be reused until its global certified steel quantity is consumed.
- Global heat steel balance is the cumulative consumption ceiling.
- **v4.14.1:** Heat Number is the global genealogy identity, while each distinct Supplier RMTC Number remains a separate certificate. The Global Heat certified quantity is the **sum of active, non-rejected RMTC certificate quantities** for that Heat. A same-Heat / different-Supplier-RMTC receipt therefore adds new certified capacity; same Heat + same Supplier RMTC duplicate protection remains.
- Material Inward uses only Part-specific RMTC decisions accepted/accepted-under-reserve.

## Material Inward
- Can be standalone or Supply Chain linked.
- Supply Chain Link can be enabled/disabled.
- RMTC/Heat/Part genealogy is preserved downstream.

## OSP
- Material Out → sample receipt → OSP Dimensional + MetLAB sample gate → partial/full OSP inward → final inspection → production release.
- Vendor Batch Number is shown in sample-approved OSP selection.
- Partial receipt quantity is allowed and remaining vendor balance stays open.
- MetLAB has Supplier and OSP Vendor separately.

## Inspection layouts
- Characteristic can be NUMBER or TEXT.
- NUMBER uses Min/Max validation.
- TEXT has no Min/Max and uses normalized text similarity; pass threshold is >=75%.

## Reports
- PDF/Excel/print where applicable.
- Heat Number Global Balance includes Qty kg and Balance kg transaction data.
- Supply Chain monthly Order/Dispatch MIS includes Customer and Part identity.
- Reports Centre provides links to RMTC/Inward/OSP/Dimensional/MetLAB/Supply Chain/NPD/APQP/QC/etc.

## MetLAB / Dimensional quality controls — v4.14.1
- MetLAB report number is generated automatically from the controlled `METLAB_REPORT` number sequence.
- MetLAB year token is **YY** (for example `MLAB-D9-26-00008`), with yearly reset logic and the existing counter preserved during migration.
- Printed MetLAB parameter serial numbers are always sequential integers `1, 2, 3 ...`, independent of layout subgroup numbering.
- MetLAB PDF controlled typography is approximately 20% larger than the prior base report style and uses page space more effectively.
- New **Case Depth / Microhardness Traverse** supports multiple named locations, default distance points `0.05, 0.10, 0.20, 0.30 ... mm`, live chart preview, PDF traverse table + Distance-vs-Hardness chart, and Excel traverse sheet.
- MetLAB has a controlled **Conclusion**: `PENDING`, `ON_HOLD`, `ACCEPTED`, `ACCEPTED_UNDER_RESERVE`, `REJECTED`, with Conclusion Remark. `ACCEPTED` is blocked when an applicable result is out of specification/not evaluated.
- Dimensional and MetLAB New/Edit pages allow direct selection of existing reports. DRAFT variable inputs are editable. FINAL records require **Controlled Amendment**, which returns the amended report to DRAFT and clears prior validation/approval timestamps for fresh authorization.
- Out-of-spec observations are visually emphasized in portal tables, PDF, and Excel. FAIL/REJECTED uses strong red styling; HOLD/Accepted Under Reserve uses amber; PASS/Accepted uses positive styling where applicable. Final Decision and MetLAB Conclusion use the same controlled status logic.
- **Approved By** resolves to the Employee Master record for the current logged-in QCMS user. Finalization is allowed only when that logged-in employee has the module approval authority. The database rechecks both permission and employee identity.

---

# Supply Chain baseline

## Flow 1 — RM Responsible FSI
Customer Order → RM Procurement → RM Receipt (Material Inward) → RM to Forger → Forging Order → Forging Receipt → Part Production → Dispatch

## Flow 2 — RM Responsible Forger / Supplier
Customer Order → Forging Order → Forging Receipt → Part Production → Dispatch

### Customer Order / Schedule
- Customer PO and six-month schedule entry.
- Supply Flow is now a **first-class database field** (`FSI_RM` / `DIRECT_FORGING`) in v4.14.0. Do not rely only on remarks parsing.
- Entry shows available system stock vs rolling 3-month demand.
- RM Procurement Required is controlled from the shortage decision.
- FSI-RM order with insufficient stock can enter RM Procurement.
- Direct Forging bypasses RM procurement stages.

### PO source visibility
v4.14.0 rule:
- Purchase Order page must show **every open Customer Order/Schedule** in a PO eligibility table with explicit `ELIGIBLE` or `WAITING / NOT REQUIRED` reason.
- Eligible rows are separately selectable.
- No order may silently disappear because of a second UI-only flow interpretation.
- RM PO: FSI-RM + RM procurement required + pending RM balance.
- Forging PO: Direct Forging customer order OR FSI-RM after RM-to-Forger dispatch.

### Controlled Purchase Orders
Two types:
- Raw Material Purchase Order
- Forging Purchase Order

Controls already implemented:
- Automatic PD-series PO numbering.
- Multiple compatible Customer Orders/Schedules can be combined on one RM PO.
- Allocation genealogy retained by source order/schedule.
- Supplier + FSI Part price history: Start Date / End Date / Price / **Remark**; blank End Date = current.
- Supplier-specific Part Master Raw Material technical data is Heading/Value based and snapshots to the PO.
- HSN/SAC introduced in v4.14.0: Part Master default + PO line override/snapshot.
- PO remains linked to RM Inward/Forging Receipt.
- Reports: pending PO, RM orders, RM section, supplier, RM-for-Part.

### Purchase Order PDF
Reference layout: FSI PO `PD900289 10-08-2026 SUNRISE ENGINEERING 2353.pdf`.
Current print contract:
- Plant/Vendor/Ship-To / quotation / requisitioner / Ship Via / Incoterm / Delivery / Payment Term.
- Item line uses FSI Part Number.
- HSN/SAC prints under item identity.
- **No vertical grid dividers inside the item body.**
- First page reserves enlarged item pockets for up to 2 item/technical/price-history blocks.
- Additional items continue on controlled item continuation pages, up to 3 per continuation page.
- Each item is immediately followed by **RAW MATERIAL / FORGING PARAMETERS & FSI TECHNICAL DATA** for that item.
- **v4.14.1:** each item is also followed by **PRICE REVISION HISTORY** (Start Date / End Date / Price / Remark) from the Supplier + FSI Part price history snapshot.
- Standard FSI/703/F04 terms pages are appended after item pages.

---

# Email notifications — v4.14.0

## Admin page
**Admin → Email Server & Notifications**

Contains:
- SMTP Enable
- SMTP Host / Port
- Username
- Password/App Password (write-only field; blank retains saved value)
- Sender Name / Sender Email / Reply-To
- STARTTLS / SSL
- Timeout
- Responsibility Routing
- Test Email
- Retry Pending/Failed
- Notification Outbox audit

## Server-side delivery
Supabase Edge Function: **`qcms-send-email`**
- deployed with JWT verification.
- SMTP delivery runs server-side.
- ordinary application users do not receive SMTP credentials.
- Business transactions never roll back because SMTP is unavailable; message remains Pending/Failed in the outbox for retry.

## Default live routes
- RMTC approval pending → **Gulab Varpe** (`metlab@fourstarindustries.com`)
- MetLAB approval pending → **Gulab Varpe**
- Dimensional approval pending → **Nitin Nanavare** (`quality@fourstarindustries.com`)

Configurable additional routes:
- RM Procurement Pending
- RM Receipt Pending
- Forging Order Pending
- Forging Receipt Pending
- OSP Sample Pending

Notifications are currently wired at key transaction points including RMTC submission/new RMTC Part review, new Dimensional/MetLAB draft, RM-required Customer Order/Schedule, controlled PO handoff and OSP sample receipt.

SMTP is intentionally disabled until the Administrator enters valid email-server credentials.

---

# Important latest live example / acceptance test
Customer Orders used during v4.14.0 source-list validation:
- `DANA0001`: FSI_RM, RM required 3,490 kg, no RM PO yet → must be eligible in Raw Material PO.
- `DANA0002`: DIRECT_FORGING, no forging PO yet → must be eligible in Forging PO and not in RM PO.

These rows were verified against live Supabase after v4.14.0 Supply Flow migration.

---

# Release history summary
- v4.12.0: Supply Chain + flexible inspection stages baseline.
- v4.12.1: master-driven standalone MetLAB/Dimensional reports.
- v4.12.2–4.12.5: linked Supply Chain, dual flow, Order/Dispatch MIS, quality conclusion/final decision.
- v4.12.6–4.13.5: enterprise portal UI iterations, responsive rail/header, pocket cards, fields, grids, login/footer polish.
- v4.13.4: approved RMTC reuse by global heat balance + duplicate-safe imports.
- v4.13.6: approved RMTC added Part, OSP partial receipts, NUMBER/TEXT layouts, approved source consolidation into Part Master.
- v4.13.7: FSI Part Number, Supply Chain stock procurement gate, controlled RM/Forging PO, RMTC approved Part Worksheet page.
- v4.13.8: multi-source RM PO, Supplier+FSI Part price history, supplier-specific PO technical data.
- v4.13.9: RM procurement visibility correction, incremental RMTC Part release guard, item-wise PO technical print.
- v4.14.0: explicit Supply Flow + always-visible PO eligibility/reasons, added-Part validation/decision from approval screen, HSN/SAC + cleaner PO item print, Email Server & Responsibility Routing + server-side notification outbox.
- **v4.14.1: additive same-Heat capacity across distinct Supplier RMTCs, MetLAB YY auto-numbering, sequential parameter print serials, multi-location Case Depth Traverse + chart, controlled MetLAB Conclusion, direct MetLAB/Dimensional edit + controlled amendment, login-employee approval gate, OOS visual controls in portal/PDF/Excel, and PO Part price-revision history with Remarks.**

---

# Development priorities after v4.14.1
When continuing, first verify these live screens after each change:
1. RMTC Entry / Global Heat Balance → same Heat + different Supplier RMTC additive certificate capacity without duplicate-certificate regression.
2. MetLAB New/Edit → automatic YY report number, sequential print serial, Conclusion, Case Depth Traverse, chart, PDF/Excel.
3. Dimensional New/Edit → direct report selection, controlled amendment, OOS highlighting and approval gate.
4. Employee Master / login identity → approval authority mapping and Approved By=current login employee.
5. Part Master → Supplier + FSI Part price history including Remark.
6. Purchase Order PDF → per-Part technical data + price revision history.
7. Customer Orders / Purchase Orders → v4.14.0 Supply Flow and PO eligibility non-regression.
8. Admin → Email Server & Notifications and outbox non-regression.

Never remove earlier data logic or UI contracts unless explicitly requested.
