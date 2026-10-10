# QCMS v4.14.49 R18 — Print alignment, email delivery fix, editable From

## 1. Print alignment (all Design B prints)
- Headings centred; text columns (Parameter, Characteristic, Description, Remarks, Supplier, Method) left;
  measured / status columns (Sr, Specification, Min, Max, Observations, Actual, Unit, Result, Status, Decision, Date) centred;
  quantities (kg, Qty, Pcs, Balance, Value) right-aligned. Plain numbers in text columns are centred.
- Bend Test report: Baking / Aging and Bend Test Results values centred.

## 2. Email delivery fix
- Cause: Microsoft 365 accepted the message but then bounced it (NDR 5.7.60 "SendAsDenied") because the From address was the user's
  mailbox, which cloud@fourstarindustries.com is not allowed to send as.
- Now (default): From = **"User Name via QCMS" <cloud@fourstarindustries.com>**, **Reply-To = the user's email** — always delivered.
- Admin → System Settings → Email Module: choose "Company mailbox shows the user's name" (default) or "User's own email"
  (only after Microsoft 365 Send As permission is granted).
- Edge function qcms-send-email v6 deployed.

## 3. Editable From
- Email → My Email Settings: edit and save your From name and From / reply-to email (per user).
- Send Email: From name and email can also be changed for one email.
