"""QCMS R14 · Email module: Send Email, Email Groups, My Email Settings, Sent log."""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from core.auth import current_profile
from core.permissions import is_admin
from core.repository import Repository
from core.ui import page_header, portal_table, save_success_dialog, section_bar, stage_section
from core import mail_service as ms

SETUP_SQL_NOTE = "The Email module's secure tables are not installed yet. Ask the System Administrator to run supabase/migrations/20261009100000_qcms_r14_personal_mail.sql in Supabase → SQL Editor."


def _user() -> tuple[dict, str, str]:
    profile = current_profile() or {}
    return profile, str(profile.get("id") or ""), str(profile.get("email") or "").strip()


def _tables_ready(repo: Repository) -> bool:
    try:
        repo.select("qcms_mail_groups", limit=1, require_live=True)
        return True
    except Exception:
        return False


def _employees(repo: Repository) -> list[dict]:
    return [r for r in repo.select("employees", order_by="first_name", limit=5000) if str(r.get("status") or "ACTIVE").upper() == "ACTIVE"]


def _groups(repo: Repository) -> list[dict]:
    try:
        return repo.select("qcms_mail_groups", eq={"status": "ACTIVE"}, order_by="group_name", limit=1000)
    except Exception:
        return []


# ----------------------------------------------------------------------------- My Email Settings
def render_my_settings() -> None:
    """R17: no Microsoft 365 sign-in. Emails go through the default email server (Admin → Email Settings)."""
    page_header("My Email Settings", "Your emails are sent through the company's default email server. No Office 365 sign-in is needed.", "Email")
    repo = Repository(); profile, user_id, login_email = _user()
    sender_name, sender_email = _sender_identity(repo, profile, login_email)
    from core.system_settings import get_email_from_mode
    mode = get_email_from_mode(repo)
    with stage_section("A", "MY FROM NAME & EMAIL", "Edit how your emails appear. Saved for your login only.", key="email_my_identity"):
        with st.form("email_my_from_form", border=False):
            c1, c2 = st.columns(2, gap="small")
            new_name = c1.text_input("From name", value=sender_name)
            new_email = c2.text_input("From / reply-to email", value=sender_email)
            saved_from = st.form_submit_button("Save From details", type="primary", width="stretch")
        if saved_from:
            try:
                ms.save_user_from(repo, user_id, new_name, new_email)
                save_success_dialog("From details saved", f"Your emails will show **{new_name.strip()}** and replies will go to **{new_email.strip()}**.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        company = _company_mailbox(repo)
        if mode == "USER":
            st.caption(f"Recipients see **{sender_name} <{sender_email}>** as the sender (company server sends as you).")
        else:
            st.caption(f"Recipients see **{sender_name} via QCMS <{company or 'company mailbox'}>**; when they press Reply it goes to **{sender_email}**.")
    with stage_section("B", "MY SIGNATURE", "Added at the end of emails you send from QCMS (stored only in this browser session).", key="email_my_signature"):
        st.session_state["qcms_mail_signature"] = st.text_area("Signature", value=st.session_state.get("qcms_mail_signature", f"{sender_name}\nFour Star Industries Pvt. Ltd."), height=90)


# ----------------------------------------------------------------------------- Send Email
COMPANY_MODE = "Company mailbox (shows my name & email)"
PERSONAL_MODE = "My Microsoft 365 mailbox"


def _sender_identity(repo: Repository, profile: dict, login_email: str) -> tuple[str, str]:
    """Signed-in user's From name and email: saved My Email Settings value first, then Employee Master, then login."""
    saved = ms.load_user_from(repo, str(profile.get("id") or ""))
    if saved.get("name") and saved.get("email"):
        return str(saved["name"]), str(saved["email"])
    name = str(profile.get("full_name") or "").strip()
    email = login_email
    try:
        from core.auth import current_employee_id
        emp_id = current_employee_id(refresh=False)
        if emp_id:
            emp = repo.get("employees", emp_id) or {}
            name = ms.employee_name(emp) or name
            email = ms.employee_email(emp) or email
    except Exception:
        pass
    return name or email.split("@")[0], email


def _company_mailbox(repo: Repository) -> str:
    try:
        row = (repo.select("qcms_email_settings", limit=1) or [{}])[0]
        return str(row.get("sender_email") or "")
    except Exception:
        return ""


def _wait_for_outbox(repo: Repository, ids: list[str], timeout: float = 45.0) -> list[dict]:
    """Poll the outbox until every row is SENT/FAILED (or timeout). Returns the latest rows."""
    deadline = time.time() + timeout
    rows: list[dict] = []
    while True:
        rows = []
        for outbox_id in ids:
            try:
                found = repo.select("qcms_notification_outbox", eq={"id": outbox_id}, limit=1, require_live=True)
            except TypeError:
                found = repo.select("qcms_notification_outbox", eq={"id": outbox_id}, limit=1)
            except Exception:
                found = []
            rows.append(dict(found[0]) if found else {"id": outbox_id, "status": "UNKNOWN"})
        if all(str(r.get("status")) in {"SENT", "FAILED", "UNKNOWN"} for r in rows) or time.time() >= deadline:
            return rows
        time.sleep(1.5)


def _outbox_outcome(rows: list[dict], result: dict | None = None) -> tuple[str, str | None]:
    """Map outbox rows to the Send Email status shown to the user."""
    statuses = [str(r.get("status") or "") for r in rows]
    if statuses and all(s == "SENT" for s in statuses):
        return "SENT", None
    errors = "; ".join(str(r.get("last_error") or "") for r in rows if str(r.get("status")) == "FAILED" and r.get("last_error"))
    if "FAILED" in statuses:
        return ("PARTIAL" if "SENT" in statuses else "FAILED"), (errors or str((result or {}).get("error") or "") or "The email server did not accept the email.")[:900]
    return "QUEUED", "The email server is still sending - it will be delivered in a moment. Check My Sent Emails."


def _upload_company_attachments(repo: Repository, attachments: list[tuple[str, bytes, str]]) -> list[dict]:
    import re
    import uuid
    from core.database import get_session_client
    if not attachments:
        return []
    client = get_session_client()
    if client is None:
        raise RuntimeError("Attachments need a live QCMS session (not available in preview mode).")
    manifest = []
    folder = f"{repo.tenant_id}/notification_exports/{uuid.uuid4().hex}"
    for name, data, ctype in attachments:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "attachment")).strip("_") or "attachment"
        path = f"{folder}/{safe}"
        client.storage.from_("quality-documents").upload(path, data, {"content-type": ctype or "application/octet-stream", "upsert": "false"})
        manifest.append({"bucket": "quality-documents", "object_path": path, "file_name": safe, "mime_type": ctype or "application/octet-stream", "generated": False})
    return manifest


def render_send() -> None:
    page_header("Send Email", "Send to employees, departments and email groups. The email shows your own name and email address as the sender.", "Email")
    repo = Repository(); profile, user_id, login_email = _user()
    tables_ready = _tables_ready(repo)
    if not tables_ready:
        st.caption("Email Groups need the R14/R15 database step; sending works now.")
    # R17: the Email module always uses the default email server (no Office 365 sign-in).
    mode = COMPANY_MODE
    store = None
    from core.system_settings import get_email_from_mode
    from_mode = get_email_from_mode(repo)
    default_name, default_email = _sender_identity(repo, profile, login_email)
    c1, c2 = st.columns(2, gap="small")
    sender_name = c1.text_input("From name", value=default_name, key="mail_from_name").strip() or default_name
    sender_email = c2.text_input("From / reply-to email", value=default_email, key="mail_from_email").strip() or default_email
    account = {"mailbox_email": sender_email}
    company = _company_mailbox(repo)
    if from_mode == "USER":
        st.caption(f"Recipients see **{sender_name} <{sender_email}>** as the sender. (Change the default in My Email Settings.)")
    else:
        st.caption(f"Recipients see **{sender_name} via QCMS <{company or 'company mailbox'}>** and replies go to **{sender_email}**. (Change the default in My Email Settings.)")
    employees = _employees(repo); groups = _groups(repo)
    emp_label = {str(e["id"]): f"{ms.employee_name(e)} · {e.get('department') or '-'} · {ms.employee_email(e) or 'no email'}" for e in employees}
    departments = sorted({str(e.get("department") or "").strip() for e in employees if str(e.get("department") or "").strip()})
    group_label = {str(g["id"]): f"{g.get('group_name')} ({len(g.get('member_employee_ids') or []) + len(g.get('extra_emails') or [])})" for g in groups}

    with st.form("qcms_send_email_form", border=False):
        section_bar("TO", "Choose people, whole departments or saved groups. Typed addresses: separate with ; or ,")
        c = st.columns(3, gap="small")
        to_emp = c[0].multiselect("Employees", list(emp_label), format_func=emp_label.get, key="mail_to_emp")
        to_dep = c[1].multiselect("Departments", departments, key="mail_to_dep")
        to_grp = c[2].multiselect("Email groups", list(group_label), format_func=group_label.get, key="mail_to_grp")
        to_extra = st.text_input("Other addresses (To)", key="mail_to_extra")
        with st.expander("CC / BCC", expanded=False):
            cc_emp = st.multiselect("CC employees", list(emp_label), format_func=emp_label.get, key="mail_cc_emp")
            cc_extra = st.text_input("CC other addresses", key="mail_cc_extra")
            bcc_extra = st.text_input("BCC other addresses", key="mail_bcc_extra")
        hide = st.checkbox("Send department / group recipients as BCC (recipients do not see each other)", value=True, key="mail_hide")
        subject = st.text_input("Subject", key="mail_subject")
        body = st.text_area("Message", height=220, key="mail_body")
        files = st.file_uploader("Attachments (max 10 MB in total)", accept_multiple_files=True, key="mail_files")
        importance = st.radio("Importance", ["normal", "high"], horizontal=True, format_func=str.title, key="mail_importance")
        preview = st.form_submit_button("Review recipients", type="primary", width="stretch")

    if preview:
        direct, warn1 = ms.resolve_recipients(employees=employees, groups=groups, employee_ids=to_emp, extra_emails=[to_extra])
        bulk, warn2 = ms.resolve_recipients(employees=employees, groups=groups, departments=to_dep, group_ids=to_grp, exclude=[r.email for r in direct])
        cc, warn3 = ms.resolve_recipients(employees=employees, groups=groups, employee_ids=cc_emp, extra_emails=[cc_extra], exclude=[r.email for r in direct + bulk])
        bcc_typed, warn4 = ms.resolve_recipients(employees=employees, groups=groups, extra_emails=[bcc_extra], exclude=[r.email for r in direct + bulk + cc])
        to = direct + ([] if hide else bulk)
        bcc = (bulk if hide else []) + bcc_typed
        attachments = [(f.name, f.getvalue(), f.type or "application/octet-stream") for f in (files or [])]
        st.session_state["_qcms_mail_pending"] = {"to": to, "cc": cc, "bcc": bcc, "subject": subject, "body": body, "attachments": attachments, "importance": importance, "warnings": warn1 + warn2 + warn3 + warn4}

    pending = st.session_state.get("_qcms_mail_pending")
    if pending:
        section_bar("REVIEW & SEND", "Check the recipient list, then send.")
        for w in pending["warnings"]:
            st.warning(w)
        rows = [{"Type": t, "Name": r.name, "Email": r.email, "From": r.source} for t, lst in (("To", pending["to"]), ("CC", pending["cc"]), ("BCC", pending["bcc"])) for r in lst]
        st.markdown(f"**{len(rows)} recipient(s)** · Subject: **{pending['subject'] or '(no subject)'}** · {len(pending['attachments'])} attachment(s)")
        if rows:
            portal_table(pd.DataFrame(rows), hide_index=True, width="stretch", height=min(360, 60 + 32 * len(rows)))
        s1, s2 = st.columns(2, gap="small")
        if s1.button(f"Send email to {len(rows)} recipient(s)", type="primary", width="stretch", disabled=not rows, key="mail_send_now"):
            status, error, count = "SENT", None, 1
            if mode == COMPANY_MODE:
                try:
                    from core.notification_service import NotificationService
                    total = sum(len(a[1]) for a in pending["attachments"])
                    if total > ms.COMPANY_MAX_ATTACHMENT_BYTES:
                        raise ValueError(f"Attachments are {total / 1048576:.1f} MB. The limit is 10 MB per email.")
                    with st.spinner("Sending through the company mailbox..."):
                        manifest = _upload_company_attachments(repo, pending["attachments"])
                        rows_out = ms.company_outbox_rows(subject=pending["subject"], html_body=ms.body_html(pending["body"], st.session_state.get("qcms_mail_signature", "")), text_body=pending["body"],
                                                          to=pending["to"], cc=pending["cc"], bcc=pending["bcc"], sender_name=sender_name, sender_email=sender_email, attachment_manifest=manifest, from_mode=from_mode)
                        count = len(rows_out)
                        inserted = [repo.insert("qcms_notification_outbox", r) for r in rows_out]
                        result = NotificationService(repo).dispatch(inserted)
                        # R19: the edge function keeps sending even when this call times out
                        # ("The read operation timed out"), so the outbox rows are the truth.
                        ids = [str(r.get("id")) for r in inserted if r and r.get("id")]
                        rows_now = _wait_for_outbox(repo, ids, timeout=15.0)
                        if any(str(r.get("status")) == "PENDING" for r in rows_now):
                            NotificationService(repo).dispatch([r for r in rows_now if str(r.get("status")) == "PENDING"])
                            rows_now = _wait_for_outbox(repo, ids)
                    status, error = _outbox_outcome(rows_now, result)
                except Exception as exc:
                    status, error = "FAILED", str(exc)[:900]
            else:
                try:
                    payloads = ms.build_messages(subject=pending["subject"], html_body=ms.body_html(pending["body"], st.session_state.get("qcms_mail_signature", "")),
                                                 to=pending["to"], cc=pending["cc"], bcc=pending["bcc"], attachments=pending["attachments"], importance=pending["importance"])
                    count = len(payloads)
                    with st.spinner("Sending from your Microsoft 365 mailbox..."):
                        token, _ = store.access_token()
                        errors = ms.send_messages(token, payloads)
                    if errors:
                        status, error = ("PARTIAL" if len(errors) < count else "FAILED"), "; ".join(errors)[:900]
                except Exception as exc:
                    status, error = "FAILED", str(exc)[:900]
            try:
                repo.insert("qcms_mail_sent_log", {"sender_email": str(account.get("mailbox_email")), "subject": pending["subject"], "recipient_count": len(rows), "recipient_summary": ", ".join(r["Email"] for r in rows[:40]) + (" …" if len(rows) > 40 else ""), "message_count": count, "status": status, "error_text": error})
            except Exception:
                pass
            if status in {"SENT", "QUEUED"}:
                st.session_state.pop("_qcms_mail_pending", None)
                for key in ("mail_subject", "mail_body", "mail_to_extra", "mail_cc_extra", "mail_bcc_extra"):
                    st.session_state.pop(key, None)
                if mode == COMPANY_MODE:
                    save_success_dialog("Email sent" if status == "SENT" else "Email queued", f"Your email **{pending['subject']}** {'was sent' if status == 'SENT' else 'is queued'} to **{len(rows)}** recipient(s). Replies go to **{sender_email}**.")
                else:
                    save_success_dialog("Email sent", f"Your email **{pending['subject']}** was sent to **{len(rows)}** recipient(s) from {account.get('mailbox_email')}. A copy is in your Outlook Sent Items.")
                st.rerun()
            else:
                st.error(f"Email not fully sent: {error}")
        if s2.button("Edit / cancel", width="stretch", key="mail_cancel"):
            st.session_state.pop("_qcms_mail_pending", None); st.rerun()


# ----------------------------------------------------------------------------- Email Groups
def render_groups() -> None:
    page_header("Email Groups", "Saved distribution lists (e.g. Quality Team, Plant Heads). Everyone can use them; the creator or an administrator can edit.", "Email")
    repo = Repository(); profile, user_id, _ = _user()
    if not _tables_ready(repo):
        st.error(SETUP_SQL_NOTE); return
    employees = _employees(repo)
    emp_label = {str(e["id"]): f"{ms.employee_name(e)} · {e.get('department') or '-'} · {ms.employee_email(e) or 'no email'}" for e in employees}
    groups = repo.select("qcms_mail_groups", order_by="group_name", limit=1000)
    labels = {"__new__": "＋ New group", **{str(g["id"]): f"{g.get('group_name')} · {g.get('status')}" for g in groups}}
    choice = st.selectbox("Group", list(labels), format_func=labels.get, key="mail_group_pick")
    row = next((g for g in groups if str(g["id"]) == choice), {})
    can_edit = not row or str(row.get("created_by")) == user_id or is_admin(profile)
    with st.form(f"mail_group_form_{choice}", border=False):
        name = st.text_input("Group name", value=str(row.get("group_name") or ""), disabled=not can_edit)
        description = st.text_input("Description", value=str(row.get("description") or ""), disabled=not can_edit)
        members = st.multiselect("Members (employees)", list(emp_label), default=[str(x) for x in (row.get("member_employee_ids") or []) if str(x) in emp_label], format_func=emp_label.get, disabled=not can_edit)
        extra = st.text_area("Other email addresses (one per line)", value="\n".join(row.get("extra_emails") or []), height=80, disabled=not can_edit)
        status = st.radio("Status", ["ACTIVE", "INACTIVE"], index=0 if str(row.get("status") or "ACTIVE") == "ACTIVE" else 1, horizontal=True, disabled=not can_edit)
        saved = st.form_submit_button("Save group", type="primary", width="stretch", disabled=not can_edit)
    if not can_edit:
        st.caption("Only the creator of this group or an administrator can change it.")
    if saved:
        try:
            if not name.strip():
                raise ValueError("Enter a group name.")
            emails, bad = [], []
            for line in extra.splitlines():
                for piece in [p for p in line.replace(";", ",").split(",") if p.strip()]:
                    (emails if ms._valid(piece) else bad).append(piece.strip())
            if bad:
                raise ValueError("Invalid email address(es): " + ", ".join(bad))
            payload = {"group_name": name.strip(), "description": description.strip() or None, "member_employee_ids": members, "extra_emails": emails, "status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
            repo.update("qcms_mail_groups", choice, payload) if row else repo.insert("qcms_mail_groups", payload)
            save_success_dialog("Email group saved", f"**{name.strip()}** saved with {len(members) + len(emails)} recipient(s).")
            st.rerun()
        except Exception as exc:
            st.error("Duplicate group name — choose another name." if "duplicate" in str(exc).lower() else str(exc))
    if row and can_edit and st.button("Delete this group", key="mail_group_delete"):
        repo.delete("qcms_mail_groups", choice); st.rerun()


# ----------------------------------------------------------------------------- Sent log
def render_sent() -> None:
    page_header("My Sent Emails", "Emails you sent from QCMS (visible only to you).", "Private")
    repo = Repository()
    if not _tables_ready(repo):
        st.error(SETUP_SQL_NOTE); return
    rows = repo.select("qcms_mail_sent_log", order_by="sent_at", desc=True, limit=500)
    if not rows:
        st.info("No emails sent from QCMS yet."); return
    portal_table(pd.DataFrame([{"Sent": str(r.get("sent_at") or "")[:16].replace("T", " "), "Subject": r.get("subject"), "Recipients": r.get("recipient_count"), "Status": r.get("status"), "Detail": r.get("error_text") or r.get("recipient_summary")} for r in rows]), hide_index=True, width="stretch", height=560)
