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
    page_header("My Email Settings", "Connect your own Microsoft 365 mailbox. Only you can see this page's connection — not other users and not administrators.", "Private")
    repo = Repository(); profile, user_id, login_email = _user()
    if not _tables_ready(repo):
        st.error(SETUP_SQL_NOTE); return
    config = ms.load_config(repo)
    st.markdown(
        "- QCMS uses **Sign in with Microsoft** (same as Outlook). Your Microsoft password is entered only on Microsoft's page — **QCMS never sees or stores it**.\n"
        "- After sign-in QCMS keeps only an **encrypted, revocable** permission to send mail as you. The database lets **only you** read it; there is no administrator access.\n"
        f"- You must sign in with your QCMS login email: **{login_email or 'not set'}**. Emails you send appear in your own Outlook **Sent Items**."
    )
    if not config.ready:
        st.warning("Email sending is not set up yet. Missing: " + "; ".join(config.missing()))
        return
    store = ms.MailAccountStore(repo, config, user_id)
    try:
        account = store.get()
    except Exception as exc:
        st.error(f"Could not read your email connection: {exc}"); return

    with stage_section("A", "MICROSOFT 365 CONNECTION", "Connect, test or disconnect your mailbox.", key="email_my_connection"):
        if account:
            c = st.columns(3, gap="small")
            c[0].metric("Status", "Connected")
            c[1].metric("Mailbox", str(account.get("mailbox_email") or ""))
            c[2].metric("Connected on", str(account.get("connected_at") or "")[:10])
            b1, b2 = st.columns(2, gap="small")
            if b1.button("Test connection", width="stretch", key="email_test"):
                try:
                    token, _ = store.access_token()
                    me = ms.graph_me(token)
                    st.success(f"Connection OK — Microsoft 365 mailbox {ms.mailbox_address(me)} is ready to send.")
                except Exception as exc:
                    st.error(str(exc))
            if b2.button("Disconnect my mailbox", width="stretch", key="email_disconnect"):
                store.disconnect()
                save_success_dialog("Mailbox disconnected", "Your Microsoft 365 connection was deleted from QCMS. You can also remove 'QCMS' under Microsoft My Account → App permissions.")
                st.rerun()
        flow = st.session_state.get("_qcms_ms365_device_flow")
        if not flow:
            if st.button(("Reconnect" if account else "Connect") + " Microsoft 365 (Sign in with Microsoft)", type="primary", width="stretch", key="email_connect"):
                try:
                    flow = ms.start_device_login(config)
                    flow["_started"] = time.time()
                    st.session_state["_qcms_ms365_device_flow"] = flow
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        else:
            remaining = int(flow.get("expires_in", 900) - (time.time() - flow.get("_started", time.time())))
            st.info("**Step 1** · Open the Microsoft sign-in page:")
            st.link_button("Open microsoft.com/devicelogin", str(flow.get("verification_uri") or "https://microsoft.com/devicelogin"), width="stretch")
            st.markdown(f"**Step 2** · Enter this code: <span style='font-size:28px;font-weight:800;letter-spacing:.12em;color:#0B6E70'>{flow.get('user_code')}</span>", unsafe_allow_html=True)
            st.caption(f"Sign in with {login_email}. The code expires in about {max(remaining // 60, 0)} minutes.")
            st.markdown("**Step 3** · After Microsoft says *You have signed in*, click Finish:")
            f1, f2 = st.columns(2, gap="small")
            if f1.button("Finish connection", type="primary", width="stretch", key="email_finish"):
                result = {"status": "pending"}
                with st.spinner("Waiting for Microsoft..."):
                    for _ in range(6):
                        result = ms.poll_device_login(config, str(flow.get("device_code")))
                        if result["status"] != "pending":
                            break
                        time.sleep(max(int(flow.get("interval", 5)), 3))
                if result["status"] == "ok":
                    try:
                        me = ms.graph_me(result["access_token"])
                        mailbox = ms.assert_login_mailbox(me, login_email)
                        store.save(mailbox=mailbox, display_name=str(me.get("displayName") or ""), refresh_token=str(result.get("refresh_token") or ""), scope=str(result.get("scope") or ""))
                        st.session_state.pop("_qcms_ms365_device_flow", None)
                        save_success_dialog("Mailbox connected", f"**{mailbox}** is connected. You can now send email from Email → Send Email.")
                        st.rerun()
                    except Exception as exc:
                        st.session_state.pop("_qcms_ms365_device_flow", None)
                        st.error(str(exc))
                elif result["status"] == "pending":
                    st.warning("Microsoft has not confirmed the sign-in yet. Finish signing in on the Microsoft page, then click Finish again.")
                else:
                    st.session_state.pop("_qcms_ms365_device_flow", None)
                    st.error({"expired": "The code expired. Click Connect again.", "declined": "Sign-in was cancelled."}.get(result["status"], str(result.get("message") or "Sign-in failed.")))
            if f2.button("Cancel", width="stretch", key="email_cancel"):
                st.session_state.pop("_qcms_ms365_device_flow", None); st.rerun()

    with stage_section("B", "MY SIGNATURE", "Added at the end of emails you send from QCMS (stored only in this browser session).", key="email_my_signature"):
        st.session_state["qcms_mail_signature"] = st.text_area("Signature", value=st.session_state.get("qcms_mail_signature", f"{profile.get('full_name') or ''}\nFour Star Industries Pvt. Ltd."), height=90)


# ----------------------------------------------------------------------------- Send Email
COMPANY_MODE = "Company mailbox (shows my name & email)"
PERSONAL_MODE = "My Microsoft 365 mailbox"


def _sender_identity(repo: Repository, profile: dict, login_email: str) -> tuple[str, str]:
    """Signed-in user's display name and email (Employee Master first, then the login profile)."""
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
        st.caption("Email Groups and My Microsoft 365 need the R14/R15 database step; Company mailbox sending works now.")
    config = ms.load_config(repo) if tables_ready else ms.MailConfig("", "", "")
    store = ms.MailAccountStore(repo, config, user_id) if config.ready else None
    try:
        account = store.get() if store else None
    except Exception:
        account = None
    modes = [COMPANY_MODE] + ([PERSONAL_MODE] if config.ready else [])
    mode = st.radio("Send using", modes, index=modes.index(PERSONAL_MODE) if account and PERSONAL_MODE in modes else 0, horizontal=True, key="mail_send_mode",
                    help="Company mailbox: QCMS sends through the company email account set by the administrator — no personal sign-in needed, recipients see your name and email and replies come to you. My Microsoft 365: sent from your own Outlook (copy in your Sent Items).")
    sender_name, sender_email = _sender_identity(repo, profile, login_email)
    if mode == PERSONAL_MODE and not account:
        st.info("Connect your Microsoft 365 mailbox first, or choose Company mailbox.")
        pages = st.session_state.get("_qsms_pages", {})
        if "email-my-settings" in pages:
            st.page_link(pages["email-my-settings"], label="Open My Email Settings", icon=":material/settings:")
        return
    if mode == COMPANY_MODE:
        account = {"mailbox_email": sender_email}
        st.caption(f"From: **{sender_name} <{sender_email}>** · sent through the company mailbox · replies come to you")
    employees = _employees(repo); groups = _groups(repo)
    emp_label = {str(e["id"]): f"{ms.employee_name(e)} · {e.get('department') or '-'} · {ms.employee_email(e) or 'no email'}" for e in employees}
    departments = sorted({str(e.get("department") or "").strip() for e in employees if str(e.get("department") or "").strip()})
    group_label = {str(g["id"]): f"{g.get('group_name')} ({len(g.get('member_employee_ids') or []) + len(g.get('extra_emails') or [])})" for g in groups}
    if mode == PERSONAL_MODE:
        st.caption(f"From: **{account.get('mailbox_email')}**")

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
        files = st.file_uploader("Attachments (total: 10 MB company mailbox · 3 MB Microsoft 365)", accept_multiple_files=True, key="mail_files")
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
                                                          to=pending["to"], cc=pending["cc"], bcc=pending["bcc"], sender_name=sender_name, sender_email=sender_email, attachment_manifest=manifest)
                        count = len(rows_out)
                        inserted = [repo.insert("qcms_notification_outbox", r) for r in rows_out]
                        result = NotificationService(repo).dispatch(inserted)
                    sent_n = int(result.get("sent") or 0); failed_n = int(result.get("failed") or 0)
                    if result.get("error") or failed_n:
                        detail = str(result.get("error") or "")
                        if not detail:
                            ids = [str(r.get("id")) for r in inserted if r and r.get("id")]
                            rows_now = [repo.get("qcms_notification_outbox", i) or {} for i in ids]
                            detail = "; ".join(str(r.get("last_error") or "") for r in rows_now if r.get("last_error"))
                        status, error = ("PARTIAL" if sent_n else "FAILED"), (detail or "Company mailbox did not accept the email.")[:900]
                    elif not sent_n:
                        status, error = "QUEUED", "Queued — will be sent by the company mailbox shortly."
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
                    save_success_dialog("Email sent" if status == "SENT" else "Email queued", f"Your email **{pending['subject']}** {'was sent' if status == 'SENT' else 'is queued'} to **{len(rows)}** recipient(s). Recipients see **{sender_name} <{sender_email}>** as the sender and replies come to you.")
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
    page_header("My Sent Emails", "Emails you sent from QCMS (visible only to you). Full copies are in your Outlook Sent Items.", "Private")
    repo = Repository()
    if not _tables_ready(repo):
        st.error(SETUP_SQL_NOTE); return
    rows = repo.select("qcms_mail_sent_log", order_by="sent_at", desc=True, limit=500)
    if not rows:
        st.info("No emails sent from QCMS yet."); return
    portal_table(pd.DataFrame([{"Sent": str(r.get("sent_at") or "")[:16].replace("T", " "), "Subject": r.get("subject"), "Recipients": r.get("recipient_count"), "Status": r.get("status"), "Detail": r.get("error_text") or r.get("recipient_summary")} for r in rows]), hide_index=True, width="stretch", height=560)
