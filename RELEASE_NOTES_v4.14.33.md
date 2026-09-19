# QCMS v4.14.33

Build: `41433-PO-PORTRAIT-TERMS-BATCH-PRINT-EMAIL-ANDROID-SDK`

## Purchase Order print
- Standard Terms & Conditions remain **portrait A4 only**.
- Controlled visible terms blocks are packed into unused white space instead of placing two pages in landscape.
- On the current FSI/703/F04 2023 template, the 12 physical source pages compact to approximately **7 portrait terms pages**.
- Clause wording and sequence are retained; the supplier-safe Customer identity removal and Part Master Part Description from v4.14.32 remain preserved.

## Batch Purchase Orders
- Purchase Order PDF page now includes **Batch Print / Email Multiple Purchase Orders**.
- Multi-select Purchase Orders, choose **1-5 copies per PO**, and download one combined print-ready PDF.
- Batch email sends each APPROVED PO separately to that PO's configured Supplier email with the generated controlled PO PDF attached.
- Cancelled, unapproved or missing-email records block batch email but do not block batch printing.

## Samsung Android test helper
- `BUILD_AND_INSTALL_SAMSUNG.command` upgraded to QCMS Mobile v0.1.1.
- If `~/Library/Android/sdk` is missing, the helper installs Google's official Android CLI for the current Mac user, then installs Platform 35, Build Tools 35.0.0 and Platform Tools before building the debug APK.

## Database
- Source-only release. Database baseline remains v4.14.28. No manual SQL is required.
