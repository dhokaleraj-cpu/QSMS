# QCMS 4.14.49 R14 — 9 October 2026

Includes R13 (KPI dashboards, AI admin switch, grouped layout), R12, R11 and R10.

## Email module (new left-menu group "Communication → Email")
- **Send Email**: to employees, whole departments, saved email groups and typed addresses; CC/BCC; attachments up to 3 MB; review recipient list before sending; large lists split automatically (max 450 per message); department/group recipients sent as BCC by default.
- **Email Groups**: saved distribution lists usable by everyone; editable by the creator or an administrator.
- **My Email Settings**: each user connects their **own Office 365 mailbox with "Sign in with Microsoft"**. QCMS never sees the Microsoft password; it keeps only an encrypted, revocable sign-in token. The database lets **only that user** read it — no administrator access. Mailbox must match the QCMS login email. Sent mail appears in the user's own Outlook Sent Items.
- **My Sent Emails**: private log of what you sent from QCMS.
- **Admin → System Settings → Microsoft 365 sign-in**: one-time Entra app registration (step-by-step inside the app).
- Uses Microsoft Graph (OAuth), so it keeps working after Microsoft switches off password SMTP for Office 365 (planned from late December 2026).

## Fixes and layout
- Global Search is now a compact search box at the top-left, directly under the menu.
- Online app start-up: the "Restoring QCMS session" step can no longer wait forever; after 3 short retries the Login screen is shown.
- Lower memory per user (database read cache keeps one copy instead of two) to reduce the risk of the online app restarting.
- New dependency: `cryptography` (already present via Supabase; now listed explicitly).

## Database
New SQL migration (owner-only security): `supabase/migrations/20261009100000_qcms_r14_personal_mail.sql` — run once in Supabase SQL Editor (see handover).
