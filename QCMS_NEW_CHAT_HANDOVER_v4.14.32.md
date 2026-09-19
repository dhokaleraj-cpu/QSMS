# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## New-Chat Handover — v4.14.32

### 1. Controlled baseline

- **Application Version:** `4.14.32`
- **Build:** `41432-PO-PRINT-COMPACT-RM-TYPES-ANDROID-TEST`
- **Project path:** `/Users/dhokaleraj/QSMS`
- **Supabase project ref:** `xxrxopzxzyjnzumrwuwy`
- **Database schema baseline:** `4.14.28` (already applied/live)
- Preserve existing Git repository/branch/history, Streamlit Cloud deployment, business data, attachments, secrets and Supabase link state.
- Continue future versioning from **v4.14.33+**.

### 2. Permanent deployment rule

Every release remains one self-contained macOS `.command` updater plus one copy/paste command. Back up before source replacement, safety-stash dirty source work, preserve `.git`, `.env`, `.streamlit/secrets.toml`, `.venv`, uploads/logs/exports/Supabase link state, compile, run online readiness, phase verification and full pytest, commit/push the existing branch and verify local/remote SHA. Do not reset/truncate business data and do not remove working functions unless explicitly requested.

### 3. v4.14.32 Purchase Order print contract

- Supplier-facing Purchase Order print must **not show Customer name / Customer identity**.
- Customer identity remains internal to QCMS genealogy, authorised UI, reports and Customer Order relationships.
- Supplier print source-reference grid contains: **Customer PO Number, PO Position, Part Number, Part Description, Quantity, UOM, Delivery Date**.
- Part Description is resolved from **Part Master** at controlled print/reprint time.
- Item section also shows **Part Description** separately from supplier item/FSI identity and HSN/SAC.
- Existing v4.14.31 PO workspace remains: PO Entry, Order List, Edit Purchase Order, Purchase Order PDF, Approval / Supplier Confirmation.
- Supplier Confirmation never blocks editing; pending-approval POs remain editable and approved revisions return to reapproval.

### 4. Terms & Conditions print contract

- `templates/FSI_STANDARD_PO_TERMS_2023.pdf` remains the authoritative terms source.
- Terms are printed **2-up on landscape A4** to utilise page area and reduce the 12 source terms pages to approximately 6 physical sheets.
- Terms content itself is not rewritten or shortened.
- Dynamic PO Number/Date stamping is preserved.

### 5. Raw Material Type contract

Controlled standard values:
- Forging
- Round Black Bar
- Casting
- Bright Bar
- Ground Bar

The Part Master Raw Material Type field no longer exposes free reusable-list addition for new arbitrary types. Historical types already stored on existing Part rows remain visible for backward-compatible editing.

### 6. Android mobile test baseline

- Android project: `mobile/android_qcms`
- Package: `com.fourstar.qcms`
- App name: `QCMS Mobile`
- Test release: `0.1.0`
- minSdk 26 / targetSdk 35.
- First launch asks for the live HTTPS QCMS Streamlit URL and stores it locally on the device.
- Uses the same live QCMS authentication, Supabase data/RLS/permissions/audit trail; no service-role key is embedded.
- WebView supports JavaScript/DOM storage/cookies, file selection and controlled downloads.
- Mac helper: `mobile/android_qcms/BUILD_AND_INSTALL_SAMSUNG.command` builds a debug APK and installs it to one authorised USB-debugging Android device when Android Studio/SDK is available.
- This v0.1.0 is a mobile test shell. Future native phases may add FCM push notifications, QR/barcode scan, direct camera capture, offline controlled inspection queues and biometric re-authentication.

### 7. Preserved v4.14.31 and earlier baseline

Preserve PO subpages and controlled pre-approval editing; RMTC approved Supplier de-duplication; dedicated Bend Test entry/records/reports; permission-aware Global Search; horizontal Chemical Analysis; Case Depth Traverse locations; reusable MetLAB reference statements; conclusion highlighting; OSP FSI/Vendor batch genealogy; final-vs-inward MetLAB boundary; complaints/photos/exports; calibration/validation; Standard Room; NPD/APQP cards; two-day Supply Chain Excel digests; all RMTC/Heat/OSP/Supply Chain/Quality data and attachments.

### 8. Acceptance checks

1. PO PDF contains no Customer name/identity.
2. PO PDF shows Part Description from Part Master.
3. PO source reference shows Customer PO No., Position, Part Number, Part Description, Qty, UOM and Delivery.
4. Standard terms section is compacted two-up and physical terms page count is reduced by roughly 50%.
5. Raw Material Type standard options are exactly Forging, Round Black Bar, Casting, Bright Bar, Ground Bar for new selections.
6. Existing legacy Raw Material Type values remain safe on existing records.
7. Android project files and Samsung Mac build/install helper are included.
8. Android app enforces HTTPS and contains no Supabase service-role key.
9. v4.14.31 PO edit/approval/supplier confirmation workflow has no regression.
10. Online readiness, phase verification and complete pytest pass before packaging.

### 9. New-chat starter prompt

> Continue development of my **QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)** from controlled release **v4.14.32 / build 41432-PO-PRINT-COMPACT-RM-TYPES-ANDROID-TEST**. Read `QCMS_NEW_CHAT_HANDOVER_v4.14.32.md` first and treat it as authoritative. Preserve all Supabase data, Git history and Streamlit Cloud deployment. Continue versioning from v4.14.33 onward. Every release must remain one self-contained macOS `.command` updater with backup, complete tests, Git push and remote SHA verification. v4.14.32 is source-only and uses the existing v4.14.28 database contract.
