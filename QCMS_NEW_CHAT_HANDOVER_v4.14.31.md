# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.31

### 1. Authoritative controlled baseline

Use **only** this baseline for future development:

- **Application Version:** `4.14.31`
- **Build:** `41431-PO-WORKSPACE-PREAPPROVAL-EDIT-CUSTOMER-REF-PDF`
- **Project path:** `/Users/dhokaleraj/QSMS`
- **Supabase project ref:** `xxrxopzxzyjnzumrwuwy`
- Database schema required: controlled **v4.14.28** live contract. v4.14.31 has **no new database migration**.
- Preserve existing Git repository, branch/history, Streamlit Cloud deployment, production/master/transaction data and attachments.

### 2. Permanent deployment rules

1. Every release is one self-contained macOS `.command` updater plus one copy/paste Terminal command.
2. Backup before source modification and protect dirty/uncommitted Git work with a safety stash.
3. Preserve `.git`, `.env`, `.streamlit/secrets.toml`, uploads, logs, exports, virtual environment and Supabase link state.
4. Compile, run online-readiness/phase verification, complete pytest, commit, push existing branch and verify local/remote SHA.
5. Apply required Supabase migrations automatically when genuinely needed; do not request manual SQL unless unavoidable.
6. Never reset/truncate/delete business data to solve source/schema problems.
7. Do not remove working functions unless explicitly requested.
8. Continue versioning from **v4.14.31 → v4.14.32+**.

### 3. v4.14.31 — Purchase Order workspace

Purchase Order navigation has dedicated pages/tabs:
- **PO Entry** — create Raw Material or Forging POs.
- **Order List** — searchable register with key customer-source identity.
- **Edit Purchase Order** — dedicated controlled editor.
- **Purchase Order PDF** — review source identity and download/print controlled PDF.
- **Approval / Supplier Confirmation** — approval route plus downstream supplier acknowledgement.

### 4. PO editing / confirmation rule

- `PENDING_APPROVAL` POs are directly editable.
- **Supplier Confirmation is never required to edit or save a PO.**
- Saving a pending PO keeps it in controlled Pending Approval.
- Revising an approved PO returns it to Pending Approval.
- Supplier Confirmation is a separate downstream stage and becomes actionable after approval/release.
- If an approved PO with a prior supplier acknowledgement is revised, that acknowledgement becomes pending again after the revision/reapproval cycle.
- Supplier identity and source Part genealogy remain immutable in-place; Supplier change uses Cancel & Reissue.

### 5. PO source identity / PDF

PO selection labels, Order List and controlled PDF expose:
- Customer
- Customer PO Number
- Customer PO Position
- Customer Order / Schedule reference
- Part Number
- FSI Part Number
- PO allocated quantity + UOM
- Customer Delivery Date

The controlled Purchase Order PDF prints a **CUSTOMER PO / SOURCE REFERENCE** table for each purchased item. Consolidated POs retain every source allocation.

### 6. Preserved v4.14.30 baseline

Preserve RMTC approved-supplier de-duplication/two-step RM detail selection, dedicated Bend Test Entry/Records/Reports, permission-aware relationship-expanded Global Search, section-wise permissions, OSP batch genealogy and all earlier Supply Chain/Quality/NPD/Complaint/Calibration functions.

### 7. Acceptance checks

1. Purchase Order workspace shows PO Entry, Order List, Edit Purchase Order, Purchase Order PDF and Approval / Supplier Confirmation pages.
2. A Pending Approval PO opens in Edit Purchase Order and saves without Supplier Confirmation.
3. Editing an approved PO returns it to Pending Approval without blocking the edit on supplier confirmation status.
4. Order List shows Customer PO Number, PO Position, Part Number and PO source quantity.
5. PO selectors include Customer PO/Position/Part/Qty context.
6. Controlled PO PDF prints Customer PO / Source Reference data.
7. Approval page preserves self-approval/routing controls.
8. Supplier Confirmation remains downstream and does not block editing.
9. No regression in RMTC, Bend Test, Global Search, MetLAB, OSP, permissions or notifications.
10. Online-readiness, phase verification and complete pytest pass.

### 8. New-chat starter prompt

> Continue development of my **QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)** from controlled release **v4.14.31 / build 41431-PO-WORKSPACE-PREAPPROVAL-EDIT-CUSTOMER-REF-PDF**. Read `QCMS_NEW_CHAT_HANDOVER_v4.14.31.md` first and treat it as authoritative. Preserve all Supabase data, Git history and Streamlit Cloud deployment. Continue versioning from v4.14.32 onward. Every release must be one self-contained macOS `.command` updater with backup, complete tests, Git push and remote SHA verification. v4.14.31 is source-only and uses the existing v4.14.28 database contract.
