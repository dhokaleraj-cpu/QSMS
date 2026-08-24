# QCMS v4.14.0 — PO Source / RMTC Added-Part Validation / HSN-SAC / Email Notifications

Build: `4140-PO-SOURCE-RMTC-VALIDATION-HSN-EMAIL`

## Corrective workflow changes
- Supply Flow is now stored directly on each Customer Order (`FSI_RM` or `DIRECT_FORGING`) instead of depending only on a remarks marker.
- Purchase Order source section shows every open Customer Order / Schedule with explicit `ELIGIBLE` or `WAITING / NOT REQUIRED` reason.
- RM PO source selection uses the saved RM requirement/balance. Forging PO source selection supports Direct Forging Customer Orders and FSI-RM orders after RM-to-Forger dispatch.
- Approved RMTCs with a newly added Part Worksheet can validate and decide the pending added Part without reopening or invalidating Parts that were already accepted.

## Purchase Order print
- Part Master and PO lines support HSN / SAC Code.
- Supplier PO item body removes vertical grid dividers.
- First page reserves generous space for up to three item/technical-data blocks; further items use controlled continuation pages.
- Each item line is followed by that Part/Supplier Raw Material / Forging Parameters & FSI Technical Data.
- The controlled FSI/703/F04 terms remain appended after item pages.

## Email notification workflow
- Admin page: Email Server & Notifications.
- Tenant SMTP configuration with write-only password field in the UI.
- Configurable event-to-Employee responsibility routing.
- Reliable outbox with Sent / Pending / Failed audit and retry.
- Server-side `qcms-send-email` Supabase Edge Function; SMTP credentials are never sent to ordinary users.
- Default live routes: RMTC + MetLAB approval to Gulab Varpe; Dimensional approval to Nitin Nanavare.
- Additional configurable events: RM Procurement, RM Receipt, Forging Order, Forging Receipt and OSP Sample.
- Notification delivery failure never rolls back the underlying QCMS transaction.

## Data preservation
The migration is additive. Existing Customer Orders, RM/Forging transactions, Parts, RMTCs, Inward, OSP, Inspection, reports and historical records remain unchanged.
