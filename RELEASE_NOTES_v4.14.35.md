# QCMS v4.14.35 — PO watermark, reminder guard, mobile navigation and iOS package

## Purchase Order print / Excel
- Supplier-facing PO source reference no longer prints the linked customer Part Number or customer Delivery Date.
- Customer PO Number, PO Position, Part Master Description, allocated Quantity and UOM remain for controlled traceability.
- The purchased item / FSI Part identity remains on the PO item line because it is the supplier-facing item being ordered.
- Every PO PDF page, including portrait Terms & Conditions pages, carries a light diagonal status watermark:
  - `APPROVED` when `approval_status = APPROVED`.
  - `PENDING APPROVAL` otherwise.
- A controlled PO Excel export is available from the dedicated PO PDF page. Its printed pages repeat the same approval status watermark in the page header.
- Batch print keeps one independent PDF per selected PO. One click downloads all selected POs inside one ZIP; different POs are never merged into one PDF.

## Supplier PO confirmation reminder hardening
- Live migration `20260921133000_qcms_v41435_po_confirmation_reminder_guard.sql` is included.
- `qcms_po_reminder_allowed` suppresses reminder generation as soon as the current supplier confirmation document is submitted or confirmation is otherwise recorded.
- Obsolete queued reminders are cancelled automatically when confirmation state / attachment / PO state changes.
- The reminder Edge Function now claims the outbox row atomically and rechecks current confirmation state immediately before SMTP send.
- A document from an older confirmation revision does not suppress reminders for a later re-request.
- Submission stops chasing but does not bypass controlled PO approval / supplier-confirmation decision / receipt genealogy.

## Android v0.1.3
- Native hamburger button added.
- QCMS left main menu and module submenu collapse automatically after page load so mobile users reach content immediately.
- Menu can be expanded on demand and collapses again after navigation.
- Supplied STAWN icon is used as the Android launcher icon.
- Existing live QCMS HTTPS login, permissions, RLS, audit, downloads and uploads remain.

## iPhone / iPad
- New universal `mobile/ios_qcms` Xcode source package for iPhone and iPad.
- WKWebView uses the same live QCMS HTTPS application and the same collapse/expand navigation behaviour.
- Supplied STAWN icon is included as the App Icon.
- `BUILD_IPA_ON_MAC.command` archives and exports a development IPA after the user supplies an Apple Team ID and valid Apple signing/provisioning credentials.
- No service-role Supabase key is embedded.

## Controlled database / Edge state
- The v4.14.35 reminder-guard migration was applied to the live QCMS Supabase project during release preparation.
- `qcms-po-confirmation-reminder` Edge Function v3 was deployed during release preparation.
- Validation transaction checks were rolled back and no validation email was sent.
