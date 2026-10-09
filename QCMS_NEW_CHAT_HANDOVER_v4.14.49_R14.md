# QCMS / QSMS cumulative handover — 4.14.49 R14

Release date: 9 October 2026. Supersedes R13–R10. Base 4.14.49, build 41449-ANDROID-SINGLE-NATIVE-DRAWER-V12; manifest release_revision = R14.

## Install
```bash
bash "$HOME/Downloads/QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R14.command"
```
The updater also creates `QCMS_CREDENTIAL_KEY` (Fernet) at the top of the Mac's `.streamlit/secrets.toml` if missing (never overwritten — changing it forces all users to reconnect). Copy secrets to Streamlit Cloud after install: `cat ~/QSMS/.streamlit/secrets.toml | pbcopy` → app ⋮ → Settings → Secrets → paste → Save.

## Database migration (one time)
`supabase/migrations/20261009100000_qcms_r14_personal_mail.sql` creates:
- `qcms_user_mail_accounts` — RLS enabled + FORCED; policies only `user_id = auth.uid()`; no admin policy; anon revoked. Stores Fernet-encrypted MS365 refresh token.
- `qcms_mail_groups` — tenant read; insert by tenant user; update/delete by creator or profiles.role ADMIN.
- `qcms_mail_sent_log` — owner-only select/insert.
Direct apply through the Supabase connector timed out during preparation (not applied) — run in Supabase → SQL Editor. Confidentiality limits: the Supabase project owner (postgres/service role) bypasses RLS and could see ciphertext; decrypting additionally needs the Streamlit secret key. No QCMS screen or API path shows credentials to anyone.

## Microsoft 365 (Entra) one-time setup
Entra → App registrations → New (single tenant, no redirect) → copy Application (client) ID + Directory (tenant) ID into Admin → System Settings (or secrets QCMS_MS365_CLIENT_ID / QCMS_MS365_TENANT_ID) → Authentication: Allow public client flows = Yes → API permissions: Microsoft Graph delegated Mail.Send, User.Read, offline_access → Grant admin consent.

## R14 contracts
- core/mail_service.py: MailConfig/load_config; encrypt/decrypt (Fernet); device-code start/poll; refresh_access_token; graph_me; assert_login_mailbox (must equal QCMS login email); resolve_recipients (ACTIVE employees only, dedupe, warnings); build_messages (≤450 recipients/message, BCC split, 3 MB attachments, HTML-escaped body); send_messages (Graph /me/sendMail; 401/403 → MailAuthError); MailAccountStore (owner-only table, refresh-token rotation).
- app_pages/email_center.py: render_send / render_groups / render_my_settings / render_sent; routes email-send, email-groups, email-my-settings, email-sent; module "Email"; rail group "Communication".
- core/system_settings.py: get/set_system_value; keys qcms.system.ms365_tenant_id / client_id.
- streamlit_app.py: compact search container key `qcms_top_search`; restore guard `_qcms_auth_restore_attempts` (≤3 retries then login).
- core/repository.py: single stored copy for fallback + fresh cache (limits 300 / 200 entries).
- tests/test_r14_mail_search_startup.py (7 tests, no network).

## Online "spinner forever" investigation
Supabase logs: app traffic normal until ~08:55 UTC 9 Oct, then no app requests (only scheduler) — the online app stopped before reaching the database. Check Streamlit Cloud → Manage app → logs for the actual error (dependency install or start-up), then Reboot app.

## Design
`QCMS_Layout_Concepts_R14.html`: A Teal Command Center · B Workspace Mega-Menu · C Grouped Navigator · D Launchpad Home — awaiting user choice for R15.
