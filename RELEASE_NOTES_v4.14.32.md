# QCMS v4.14.32 Release Notes

**Build:** `41432-PO-PRINT-COMPACT-RM-TYPES-ANDROID-TEST`

## Purchase Order print

- Supplier-facing PO print no longer shows the **Customer name / Customer identity**.
- Controlled source traceability remains available as **Customer PO Number, PO Position, Part Number, Part Description, Quantity, UOM and Delivery Date**.
- **Part Description** is resolved from the linked **Part Master** and shown both in the item section and source-reference grid.
- The QCMS application itself still retains Customer identity internally for genealogy, order selection, reports and authorised users; only the supplier-facing PO print is changed.

## Compact Terms & Conditions

- The authoritative `FSI_STANDARD_PO_TERMS_2023.pdf` content is preserved.
- Terms pages are imposed **two original pages per landscape A4 sheet**.
- Existing 12 terms pages therefore print as approximately **6 physical terms sheets**, reducing paper/page count without changing the legal terms text.
- PO Number and PO Date continue to be stamped on the controlled terms pages.

## Raw Material Type

New/editable Raw Material Type values are controlled to:

1. Forging
2. Round Black Bar
3. Casting
4. Bright Bar
5. Ground Bar

Existing historical values are retained and remain visible on their existing Part records for backward compatibility, but the reusable free-add Raw Material Type control is removed.

## Android test shell

- Added `mobile/android_qcms` Android Studio project for immediate Samsung/Android testing.
- HTTPS-only WebView shell uses the existing live QCMS Streamlit URL and therefore preserves the same login, Supabase database, RLS, permissions, audit trail and documents.
- Includes PDF/file downloads and browser file upload handling.
- Includes `BUILD_AND_INSTALL_SAMSUNG.command` for Mac build + USB install when Android Studio/SDK and USB debugging are available.
- No Supabase service-role key is stored in the Android app.

## Database / deployment

- Source-only release.
- Required live database baseline remains **v4.14.28**.
- No new Supabase migration or manual SQL is required.
- Existing production/master/transaction data, attachments, Git history and Streamlit deployment remain preserved.
