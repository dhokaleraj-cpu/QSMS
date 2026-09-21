# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Controlled handover — v4.14.35

### Controlled baseline
- Application Version: `4.14.35`
- Build: `41435-PO-WATERMARK-REMINDER-MOBILE-IOS`
- Project: `/Users/dhokaleraj/QSMS`
- Previous controlled source: `4.14.34`
- Preserve Git history, Streamlit Cloud deployment, Supabase production data, attachments, secrets, permissions and all prior working functions.

### Purchase Order print / Excel
- Supplier-facing source reference must not print Customer identity, linked Customer Part Number, or Customer Delivery Date.
- Preserve Customer PO Number + PO Position + Part Master Description + allocated Qty/UOM for traceability.
- Preserve the purchased item / FSI Part identity on the actual PO item line.
- Every generated PO PDF page, including Terms & Conditions, must show a light diagonal `APPROVED` or `PENDING APPROVAL` watermark based on `approval_status`.
- Dedicated PO Excel export prints the same status watermark on every printed worksheet page through repeating headers.
- Batch PO download remains one-click ZIP containing one separate PDF per selected PO. Never merge different POs into one PDF.

### Supplier PO confirmation reminder fix
- Migration: `20260921133000_qcms_v41435_po_confirmation_reminder_guard.sql`.
- Reminder eligibility requires current APPROVED/open PO, current confirmation still PENDING, and no current-revision `SUPPLIER_PO_CONFIRMATION` attachment.
- Current-revision attachment submission cancels pending/failed/sending reminder outbox rows.
- Reminder Edge Function calls `qcms_po_reminder_allowed`, atomically claims the outbox via `qcms_claim_notification_for_send`, then rechecks with `qcms_notification_send_is_current` immediately before SMTP.
- A later revision/request date makes an older attachment historical; reminders can resume for the new revision.
- Live migration was applied and reminder Edge Function v3 deployed/validated during release preparation.

### Android mobile v0.1.3
- Application id test build remains `com.fourstar.qcms.test`.
- STAWN image is the launcher icon.
- Native hamburger control collapses/expands QCMS main rail and module submenu.
- Main menu and submenu are collapsed automatically after each page load so content is immediately visible on Samsung/mobile screens.
- GitHub Actions APK build workflow is updated for v0.1.3.
- A compiled APK must only be claimed when an actual successful Android build exists; source ZIP is not an APK.

### iPhone / iPad mobile v0.1.0
- Universal SwiftUI/WKWebView package at `mobile/ios_qcms`.
- Same live HTTPS QCMS login/session model; no service-role secret embedded.
- STAWN icon included.
- Native menu control uses the same collapsed-default navigation model.
- `BUILD_IPA_ON_MAC.command` requires Xcode + Apple Team ID + valid signing/provisioning. Do not claim a signed IPA if those credentials were not available for the build.

### Deployment rule
Every release remains one self-contained macOS `.command` updater with backup/safety stash, source replacement, compile, online-readiness, phase verification, complete pytest, Git commit/push and remote SHA verification. Do not reset or truncate business data. Required migrations should be packaged/applied automatically or already verified live; never ask for manual SQL unless technically unavoidable.

### Continue next
Continue versioning from `v4.14.36+`.
