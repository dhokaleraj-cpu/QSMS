"""QCMS R14 · Personal Microsoft 365 email (Send Email module).

Each user connects THEIR OWN Microsoft 365 mailbox with "Sign in with Microsoft"
(OAuth 2.0 device-code flow, delegated Mail.Send). QCMS never sees the Microsoft
password. Only a revocable refresh token is kept:

* encrypted by the app (Fernet, key = secret ``QCMS_CREDENTIAL_KEY``) before storage;
* stored in ``qcms_user_mail_accounts`` whose database security (RLS) lets ONLY the
  owner read/write the row — there is no administrator policy;
* removable at any time ("Disconnect"), and revocable by the user in Microsoft.

The connected mailbox must be the same address as the user's QCMS login email.
Mail is sent with Microsoft Graph ``POST /me/sendMail`` and saved in the user's own
Outlook Sent Items.
"""
from __future__ import annotations

import base64
import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping, Sequence

LOGIN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/{endpoint}"
GRAPH_URL = "https://graph.microsoft.com/v1.0"
SCOPES = "offline_access User.Read Mail.Send"
DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
MAX_RECIPIENTS_PER_MESSAGE = 450          # Exchange Online limit is 500
MAX_ATTACHMENT_BYTES = 3 * 1024 * 1024    # Graph inline attachment limit per request ≈ 3–4 MB
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

PostFn = Callable[..., Any]


class MailSetupError(RuntimeError):
    """Configuration missing (admin / server key)."""


class MailAuthError(RuntimeError):
    """Sign-in expired or was revoked — user must reconnect."""


# ----------------------------------------------------------------------------- configuration
@dataclass(frozen=True)
class MailConfig:
    tenant_id: str
    client_id: str
    credential_key: str

    @property
    def ready(self) -> bool:
        return bool(self.tenant_id and self.client_id and self.credential_key)

    def missing(self) -> list[str]:
        out = []
        if not self.tenant_id:
            out.append("Microsoft 365 Directory (tenant) ID — Admin → System Settings")
        if not self.client_id:
            out.append("Microsoft 365 Application (client) ID — Admin → System Settings")
        if not self.credential_key:
            out.append("Server encryption key QCMS_CREDENTIAL_KEY — Streamlit secrets (created automatically by the updater)")
        return out


def load_config(repo: Any) -> MailConfig:
    from core.config import _secret
    from core.system_settings import MS365_CLIENT_KEY, MS365_TENANT_KEY, get_system_value
    tenant, _ = get_system_value(repo, MS365_TENANT_KEY, secret_name="QCMS_MS365_TENANT_ID")
    client, _ = get_system_value(repo, MS365_CLIENT_KEY, secret_name="QCMS_MS365_CLIENT_ID")
    key = str(_secret("QCMS_CREDENTIAL_KEY", "") or "").strip()
    return MailConfig(tenant.strip(), client.strip(), key)


# ----------------------------------------------------------------------------- encryption
def _fernet(key: str):
    from cryptography.fernet import Fernet
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(value: str, key: str) -> str:
    return _fernet(key).encrypt(str(value).encode()).decode()


def decrypt_secret(token: str, key: str) -> str:
    from cryptography.fernet import InvalidToken
    try:
        return _fernet(key).decrypt(str(token).encode()).decode()
    except InvalidToken as exc:
        raise MailAuthError("Your saved Microsoft 365 connection can no longer be opened (the server key changed). Please connect again.") from exc


def new_credential_key() -> str:
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


# ----------------------------------------------------------------------------- HTTP helpers
def _post(url: str, *, data: Mapping[str, Any] | None = None, json: Any = None, headers: Mapping[str, str] | None = None, http: PostFn | None = None):
    if http is not None:
        return http("POST", url, data=data, json=json, headers=headers)
    import httpx
    return httpx.post(url, data=data, json=json, headers=dict(headers or {}), timeout=60.0)


def _get(url: str, *, headers: Mapping[str, str], http: PostFn | None = None):
    if http is not None:
        return http("GET", url, headers=headers)
    import httpx
    return httpx.get(url, headers=dict(headers), timeout=30.0)


def _json(response: Any) -> dict:
    try:
        return dict(response.json() or {})
    except Exception:
        return {}


# ----------------------------------------------------------------------------- OAuth device-code flow
def start_device_login(config: MailConfig, *, http: PostFn | None = None) -> dict:
    if not (config.tenant_id and config.client_id):
        raise MailSetupError("Microsoft 365 sign-in is not configured yet. Ask the QCMS System Administrator (Admin → System Settings).")
    response = _post(LOGIN_URL.format(tenant=config.tenant_id, endpoint="devicecode"), data={"client_id": config.client_id, "scope": SCOPES}, http=http)
    body = _json(response)
    if getattr(response, "status_code", 200) >= 400 or "device_code" not in body:
        raise MailSetupError(f"Microsoft sign-in could not start: {body.get('error_description') or body.get('error') or getattr(response, 'status_code', '')}")
    return body


def poll_device_login(config: MailConfig, device_code: str, *, http: PostFn | None = None) -> dict:
    """Return {'status': 'pending'|'ok'|'expired'|'declined'|'error', ...tokens}."""
    response = _post(LOGIN_URL.format(tenant=config.tenant_id, endpoint="token"), data={"grant_type": DEVICE_GRANT, "client_id": config.client_id, "device_code": device_code}, http=http)
    body = _json(response)
    if "access_token" in body:
        return {"status": "ok", **body}
    error = str(body.get("error") or "")
    if error in {"authorization_pending", "slow_down"}:
        return {"status": "pending"}
    if error == "expired_token":
        return {"status": "expired"}
    if error in {"authorization_declined", "access_denied"}:
        return {"status": "declined"}
    return {"status": "error", "message": body.get("error_description") or error or "Unknown sign-in error"}


def refresh_access_token(config: MailConfig, refresh_token: str, *, http: PostFn | None = None) -> dict:
    response = _post(LOGIN_URL.format(tenant=config.tenant_id, endpoint="token"), data={"grant_type": "refresh_token", "client_id": config.client_id, "refresh_token": refresh_token, "scope": SCOPES}, http=http)
    body = _json(response)
    if "access_token" not in body:
        raise MailAuthError("Your Microsoft 365 sign-in has expired or was revoked. Open My Email Settings and connect again." + (f" ({body.get('error')})" if body.get("error") else ""))
    return body


def graph_me(access_token: str, *, http: PostFn | None = None) -> dict:
    response = _get(f"{GRAPH_URL}/me?$select=displayName,mail,userPrincipalName", headers={"Authorization": f"Bearer {access_token}"}, http=http)
    body = _json(response)
    if getattr(response, "status_code", 200) >= 400:
        raise MailAuthError(f"Microsoft Graph refused the profile request: {(body.get('error') or {}).get('message') if isinstance(body.get('error'), dict) else body}")
    return body


def mailbox_address(me: Mapping[str, Any]) -> str:
    return str(me.get("mail") or me.get("userPrincipalName") or "").strip()


def assert_login_mailbox(me: Mapping[str, Any], login_email: str) -> str:
    """The connected mailbox must be the user's own QCMS login email."""
    mailbox = mailbox_address(me)
    upn = str(me.get("userPrincipalName") or "").strip()
    wanted = str(login_email or "").strip().casefold()
    if not wanted:
        raise MailSetupError("Your QCMS login has no email address. Ask the administrator to set it in Users & Access.")
    if wanted not in {mailbox.casefold(), upn.casefold()}:
        raise MailSetupError(f"You signed in to Microsoft as {mailbox or upn}. Please sign in with your own QCMS login email {login_email}.")
    return mailbox or upn


# ----------------------------------------------------------------------------- recipients
@dataclass(frozen=True)
class Recipient:
    email: str
    name: str = ""
    source: str = ""


def _valid(email: Any) -> str:
    text = str(email or "").strip()
    return text if EMAIL_RE.match(text) else ""


def employee_email(row: Mapping[str, Any]) -> str:
    return _valid(row.get("email") or row.get("login_email") or row.get("work_email"))


def employee_name(row: Mapping[str, Any]) -> str:
    return " ".join(v for v in (str(row.get("first_name") or "").strip(), str(row.get("last_name") or "").strip()) if v) or str(row.get("employee_code") or "")


def resolve_recipients(
    *,
    employees: Sequence[Mapping[str, Any]],
    groups: Sequence[Mapping[str, Any]],
    employee_ids: Iterable[str] = (),
    departments: Iterable[str] = (),
    group_ids: Iterable[str] = (),
    extra_emails: Iterable[str] = (),
    exclude: Iterable[str] = (),
) -> tuple[list[Recipient], list[str]]:
    """Expand employees / departments / groups / typed addresses into unique recipients.

    Returns (recipients, warnings). Only ACTIVE employees with a valid email are used.
    """
    active = {str(e.get("id")): e for e in employees if str(e.get("status") or "ACTIVE").upper() == "ACTIVE"}
    out: dict[str, Recipient] = {}
    warnings: list[str] = []
    skip = {str(x).strip().casefold() for x in exclude if str(x).strip()}

    def add(email: str, name: str, source: str) -> None:
        key = email.casefold()
        if key and key not in skip and key not in out:
            out[key] = Recipient(email, name, source)

    for eid in employee_ids:
        row = active.get(str(eid))
        if not row:
            continue
        email = employee_email(row)
        if email:
            add(email, employee_name(row), "Employee")
        else:
            warnings.append(f"{employee_name(row)} has no email address in Employee Master.")
    wanted_depts = {str(d).strip().casefold() for d in departments if str(d).strip()}
    if wanted_depts:
        found = 0
        for row in active.values():
            if str(row.get("department") or "").strip().casefold() in wanted_depts:
                email = employee_email(row)
                if email:
                    add(email, employee_name(row), f"Department {row.get('department')}"); found += 1
        if not found:
            warnings.append("No employee with an email address was found in the selected department(s).")
    by_group = {str(g.get("id")): g for g in groups if str(g.get("status") or "ACTIVE").upper() == "ACTIVE"}
    for gid in group_ids:
        group = by_group.get(str(gid))
        if not group:
            continue
        for eid in group.get("member_employee_ids") or []:
            row = active.get(str(eid))
            if row and employee_email(row):
                add(employee_email(row), employee_name(row), f"Group {group.get('group_name')}")
        for email in group.get("extra_emails") or []:
            if _valid(email):
                add(_valid(email), "", f"Group {group.get('group_name')}")
    for raw in extra_emails:
        for piece in re.split(r"[;,\s]+", str(raw or "")):
            if not piece:
                continue
            email = _valid(piece)
            if email:
                add(email, "", "Typed")
            else:
                warnings.append(f"Ignored invalid email address: {piece}")
    return list(out.values()), warnings


def chunk(items: Sequence[Any], size: int = MAX_RECIPIENTS_PER_MESSAGE) -> list[list[Any]]:
    return [list(items[i:i + size]) for i in range(0, len(items), size)] or [[]]


# ----------------------------------------------------------------------------- message building & sending
def body_html(text: str, signature: str = "") -> str:
    """Plain text from the editor → safe HTML (line breaks kept, no script injection)."""
    paragraphs = html.escape(str(text or "")).replace("\r\n", "\n").split("\n\n")
    content = "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs if p.strip() or len(paragraphs) == 1)
    if signature.strip():
        content += "<p style='color:#5C7778'>" + html.escape(signature).replace("\n", "<br>") + "</p>"
    return f"<div style=\"font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#173233\">{content}</div>"


def build_messages(
    *, subject: str, html_body: str, to: Sequence[Recipient], cc: Sequence[Recipient] = (), bcc: Sequence[Recipient] = (),
    attachments: Sequence[tuple[str, bytes, str]] = (), importance: str = "normal",
) -> list[dict]:
    """Return Graph sendMail payloads, split so no message exceeds the recipient limit.

    When the total is above the limit, To/CC go in the first message and BCC
    recipients are spread over follow-up copies.
    """
    if not str(subject or "").strip():
        raise ValueError("Enter a subject.")
    if not (to or cc or bcc):
        raise ValueError("Select at least one recipient.")
    total = sum(len(a) for _, a, _ in attachments)
    if total > MAX_ATTACHMENT_BYTES:
        raise ValueError(f"Attachments are {total / 1048576:.1f} MB. The limit is 3 MB per email — share large files by link instead.")
    att = [{"@odata.type": "#microsoft.graph.fileAttachment", "name": name, "contentType": ctype or "application/octet-stream", "contentBytes": base64.b64encode(data).decode()} for name, data, ctype in attachments]

    def addr(rows: Sequence[Recipient]) -> list[dict]:
        return [{"emailAddress": {"address": r.email, **({"name": r.name} if r.name else {})}} for r in rows]

    fixed = len(to) + len(cc)
    if fixed > MAX_RECIPIENTS_PER_MESSAGE:
        raise ValueError(f"To + CC has {fixed} addresses. Put large lists in BCC (limit {MAX_RECIPIENTS_PER_MESSAGE} per message).")
    first_bcc_room = MAX_RECIPIENTS_PER_MESSAGE - fixed
    bcc = list(bcc)
    batches = [bcc[:first_bcc_room]] + chunk(bcc[first_bcc_room:]) if len(bcc) > first_bcc_room else [bcc]
    batches = [b for b in batches if b] or [[]]
    messages = []
    for index, bcc_part in enumerate(batches):
        message = {
            "subject": str(subject).strip(), "importance": importance,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": addr(to) if index == 0 else [],
            "ccRecipients": addr(cc) if index == 0 else [],
            "bccRecipients": addr(bcc_part),
            "attachments": att,
        }
        if index > 0 and not message["toRecipients"]:
            message["toRecipients"] = []
        messages.append({"message": message, "saveToSentItems": index == 0})
    return messages


def send_messages(access_token: str, payloads: Sequence[dict], *, http: PostFn | None = None) -> list[str]:
    errors = []
    for payload in payloads:
        response = _post(f"{GRAPH_URL}/me/sendMail", json=payload, headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}, http=http)
        status = getattr(response, "status_code", 202)
        if status not in (200, 202):
            body = _json(response)
            message = (body.get("error") or {}).get("message") if isinstance(body.get("error"), dict) else str(body or status)
            if status in (401, 403):
                raise MailAuthError(f"Microsoft refused to send ({status}): {message}. Reconnect in My Email Settings.")
            errors.append(f"{status}: {message}")
    return errors


# ----------------------------------------------------------------------------- per-user account store (owner-only table)
ACCOUNT_TABLE = "qcms_user_mail_accounts"


class MailAccountStore:
    def __init__(self, repo: Any, config: MailConfig, user_id: str) -> None:
        self.repo = repo; self.config = config; self.user_id = str(user_id or "")

    def get(self) -> dict | None:
        rows = self.repo.select(ACCOUNT_TABLE, eq={"user_id": self.user_id}, limit=1, require_live=True)
        return dict(rows[0]) if rows else None

    def save(self, *, mailbox: str, display_name: str, refresh_token: str, scope: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        payload = {"user_id": self.user_id, "provider": "MS365", "mailbox_email": mailbox, "display_name": display_name or None,
                   "encrypted_refresh_token": encrypt_secret(refresh_token, self.config.credential_key), "token_scope": scope or SCOPES, "connected_at": now, "updated_at": now}
        existing = self.get()
        return self.repo.update(ACCOUNT_TABLE, str(existing["id"]), payload) if existing else self.repo.insert(ACCOUNT_TABLE, payload)

    def disconnect(self) -> None:
        existing = self.get()
        if existing:
            self.repo.delete(ACCOUNT_TABLE, str(existing["id"]))

    def access_token(self, *, http: PostFn | None = None) -> tuple[str, dict]:
        account = self.get()
        if not account:
            raise MailAuthError("Connect your Microsoft 365 mailbox first (Email → My Email Settings).")
        refresh = decrypt_secret(str(account.get("encrypted_refresh_token") or ""), self.config.credential_key)
        tokens = refresh_access_token(self.config, refresh, http=http)
        now = datetime.now(timezone.utc).isoformat()
        changes: dict[str, Any] = {"last_used_at": now, "updated_at": now}
        if tokens.get("refresh_token") and tokens.get("refresh_token") != refresh:
            changes["encrypted_refresh_token"] = encrypt_secret(tokens["refresh_token"], self.config.credential_key)
        try:
            self.repo.update(ACCOUNT_TABLE, str(account["id"]), changes)
        except Exception:
            pass
        return str(tokens["access_token"]), account


# ----------------------------------------------------------------------------- R16 company mailbox
# "Like the payroll email module": QCMS sends through the company SMTP account configured by the
# administrator (Admin → Email Settings), but the email shows the signed-in user's own name and
# email address as the sender. Recipients' replies go to the user.
COMPANY_EVENT_KEY = "USER_EMAIL"
COMPANY_MAX_RECIPIENTS = 90          # keep each SMTP message well below typical relay limits
COMPANY_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


def company_outbox_rows(
    *, subject: str, html_body: str, text_body: str, to: Sequence[Recipient], cc: Sequence[Recipient] = (), bcc: Sequence[Recipient] = (),
    sender_name: str, sender_email: str, attachment_manifest: Sequence[Mapping[str, Any]] = (),
) -> list[dict]:
    """Return qcms_notification_outbox rows for the company-mailbox send (one row per message).

    The edge function ``qcms-send-email`` reads ``context.to_emails`` and ``context.sender_*``:
    From = "User Name <user@company>"; if the SMTP server refuses to send as the user it retries
    as "User Name via QCMS <company mailbox>" with Reply-To = the user.
    """
    if not str(subject or "").strip():
        raise ValueError("Enter a subject.")
    if not (to or cc or bcc):
        raise ValueError("Select at least one recipient.")
    sender_email = _valid(sender_email)
    if not sender_email:
        raise ValueError("Your QCMS login has no valid email address, so the email cannot show you as the sender.")
    fixed = len(to) + len(cc)
    if fixed > COMPANY_MAX_RECIPIENTS:
        raise ValueError(f"To + CC has {fixed} addresses. Put large lists in BCC (limit {COMPANY_MAX_RECIPIENTS} per message).")
    room = COMPANY_MAX_RECIPIENTS - fixed
    bcc = list(bcc)
    batches = [bcc[:room]] + chunk(bcc[room:], COMPANY_MAX_RECIPIENTS) if len(bcc) > room else [bcc]
    batches = [b for b in batches if b] or [[]]
    rows: list[dict] = []
    for index, part in enumerate(batches):
        to_list = [r.email for r in to] if index == 0 else []
        cc_list = [r.email for r in cc] if index == 0 else []
        primary = to_list[0] if to_list else sender_email   # BCC-only copies go "to" the sender
        rows.append({
            "event_key": COMPANY_EVENT_KEY,
            "recipient_email": primary,
            "recipient_name": (to[0].name if index == 0 and to else sender_name) or None,
            "cc_emails": cc_list,
            "bcc_emails": [r.email for r in part],
            "subject": str(subject).strip(),
            "body_text": text_body,
            "body_html": html_body,
            "template_key": COMPANY_EVENT_KEY,
            "attachment_manifest": list(attachment_manifest),
            "is_automatic": False,
            "status": "PENDING",
            "context": {"to_emails": to_list, "sender_name": sender_name, "sender_email": sender_email, "from_mode": "SEND_AS_USER", "message_index": index + 1, "message_count": len(batches)},
        })
    return rows
