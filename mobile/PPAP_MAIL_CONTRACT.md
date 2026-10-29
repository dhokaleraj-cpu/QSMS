# PPAP assignment e-mail · client contract (R39)

"As soon as a PPAP is created the e-mail must go to the responsible person with all part details and drawings including
related specification, and reminders to be sent."

Server side: `supabase/migrations/20261029100000_qcms_r39_ppap_mail.sql` (applied live) and the edge function
`qcms-ppap-due-notifier` (daily reminders). The website (`core/ppap_service.PpapService.send_assignment_mail`) and the
Android app (`PpapData.assignmentMail`) call exactly the same two endpoints with the signed-in user's JWT (never service_role).

## 1. Queue: `POST /rest/v1/rpc/qcms_ppap_assignment_mail`

```json
{"p_package_id": "<uuid>", "p_element_ids": null, "p_resend": false, "p_app_url": "https://<website>"}
```

* returns `uuid[]` - ids of `qcms_notification_outbox` rows (one per responsible employee); `[]` = nothing to send
  (same mail already queued today, no responsible employee with an e-mail address, or all elements NA / Completed).
* `p_element_ids`: `null` = all open elements of the package (package created / "Send assignment e-mail again"),
  otherwise only the changed elements.
* `p_resend: true` bypasses the once-per-day de-duplication ("Send assignment e-mail again").
* Errors are plain messages (not signed in / no PPAP create-edit right / package not found) - show them to the user.

## 2. Send: `POST /functions/v1/qcms-send-email` `{"outbox_ids": [...]}`

Skip the call when the array is empty. The function attaches the storage files listed in `attachment_manifest`.

## When the clients call it

| Event | `p_element_ids` | `p_resend` |
|---|---|---|
| Package created (PPAP page, APQP "Create PPAP package", Android new package) | `null` | `false` |
| Element responsible person newly set / changed, or due date changed while assigned (open elements only; `needs_assignment_mail`) | changed ids | `false` |
| Bulk "Assign several elements at once" | changed ids | `false` |
| "Send assignment e-mail again" (package or element) | `null` / element id | `true` |

E-mail never blocks a save; the outcome is shown as a message.

## E-mail content

* Subject (department first): `<Department> · PPAP <package no> · <part no (name)> · your <n> element(s) due from DD-MM-YYYY`
  (department of the responsible employee, default Quality).
* Body: package no., customer PPAP no., submission level, customer due date, PPAP owner; PART DETAILS (part no., FSI
  part no., name, customer part no., drawing no. / rev., material grade, weights, section, route, customer); the
  person's elements table (no., element, due date, status, remarks); CURRENT DRAWINGS & SPECIFICATIONS table; link to
  the package page.
* Attachments (`qcms_ppap_part_context`): current (status ACTIVE) part drawings (finish / forging / heat-treatment),
  process drawings and process specifications of the active process routes, OSP process drawings, and documents of the
  customer standards linked to the part. Drawings first, then specifications, up to 18 files / 10 MB; the rest are listed
  by name ("open it in QCMS").
* Recipients: internal employees of the tenant only (`employees.email`), CC the package owner. Customer data is allowed
  (internal mail); the mail never goes to a customer or supplier address.

## Daily reminders (`qcms-ppap-due-notifier`, pg_cron 07:50 IST)

One digest per responsible employee for elements due within 3 days or overdue (CC reporting manager when overdue), subject
`<Department> · PPAP elements due · <n> item(s) · DD-MM-YYYY`, with the same part details and drawings / specifications list.
Attachment rule: a file is attached only when it was not already attached to the same person in a SENT PPAP e-mail
(assignment or reminder) within the last 7 days - so the first reminder carries the files, later reminders list them
("Attached on DD-MM-YYYY"), they are re-attached once a week, and a new drawing revision is attached at once.

## Customer submission (separate flow)

"Send PPAP package to the customer" (website section E, Android `PpapSend`): only the package's own documents, recipients
belonging to another customer / supplier are refused, attachments up to 10 MB / 18 files, otherwise a 7-day signed ZIP link;
event `PPAP_PACKAGE_SUBMISSION`, logged in `ppap_customer_submissions`.
