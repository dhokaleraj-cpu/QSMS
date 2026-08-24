from __future__ import annotations

import pandas as pd
import streamlit as st

from core.notification_service import NotificationService
from core.permissions import is_admin
from core.repository import Repository
from core.ui import page_header, portal_table, save_success_popup, stage_section, subpage_navigation

EVENTS = (
    ("RMTC_APPROVAL_PENDING", "RMTC approval pending"),
    ("DIMENSIONAL_APPROVAL_PENDING", "Dimensional inspection approval pending"),
    ("METLAB_APPROVAL_PENDING", "MetLAB approval pending"),
    ("RM_PROCUREMENT_PENDING", "Raw Material procurement pending"),
    ("RM_RECEIPT_PENDING", "Raw Material receipt pending"),
    ("FORGING_ORDER_PENDING", "Forging order pending"),
    ("FORGING_RECEIPT_PENDING", "Forging receipt pending"),
    ("OSP_SAMPLE_PENDING", "OSP sample inspection pending"),
)


def render() -> None:
    subpage_navigation(("user-access", "Users & Access", ":material/admin_panel_settings:"), ("masters", "Masters Home", ":material/database:"))
    page_header("Email Server & Notifications", "SMTP server settings, workflow responsibility routing, delivery test and retry outbox.", "Administrator")
    profile = st.session_state.get("profile") or {}
    if not is_admin(profile):
        st.error("Administrator access is required.")
        return
    repo = Repository(); notifier = NotificationService(repo)
    existing_rows = repo.select("qcms_email_settings", limit=1)
    existing = existing_rows[0] if existing_rows else {}

    with stage_section("A", "EMAIL SERVER SETTINGS", "SMTP password is write-only in the UI. Leave Password blank to keep the saved password.", key="email_settings_server"):
        c = st.columns(4, gap="small")
        enabled = c[0].toggle("Enable Email Notifications", value=bool(existing.get("enabled", False)))
        host = c[1].text_input("SMTP Host", value=str(existing.get("smtp_host") or ""), placeholder="smtp.office365.com")
        port = c[2].number_input("SMTP Port", min_value=1, max_value=65535, value=int(existing.get("smtp_port") or 587), step=1)
        sender_name = c[3].text_input("Sender Name", value=str(existing.get("sender_name") or "QCMS"))
        c = st.columns(4, gap="small")
        username = c[0].text_input("SMTP Username", value=str(existing.get("smtp_username") or ""))
        password = c[1].text_input("SMTP Password / App Password", type="password", value="", placeholder="Leave blank to keep saved password")
        sender_email = c[2].text_input("Sender Email", value=str(existing.get("sender_email") or ""))
        reply_to = c[3].text_input("Reply-To", value=str(existing.get("reply_to") or ""))
        c = st.columns(3, gap="small")
        use_tls = c[0].toggle("STARTTLS", value=bool(existing.get("use_tls", True)))
        use_ssl = c[1].toggle("SMTP SSL", value=bool(existing.get("use_ssl", False)))
        timeout = c[2].number_input("Timeout seconds", min_value=5, max_value=120, value=int(existing.get("timeout_seconds") or 20), step=1)
        if st.button("Save Email Server Settings", type="primary", width="stretch"):
            payload = {
                "enabled": enabled, "smtp_host": host.strip() or None, "smtp_port": int(port),
                "smtp_username": username.strip() or None, "sender_email": sender_email.strip() or None,
                "sender_name": sender_name.strip() or "QCMS", "reply_to": reply_to.strip() or None,
                "use_tls": use_tls, "use_ssl": use_ssl, "timeout_seconds": int(timeout),
            }
            if password.strip(): payload["smtp_password"] = password
            elif existing.get("smtp_password") is not None: payload["smtp_password"] = existing.get("smtp_password")
            try:
                saved, _ = repo.upsert_by("qcms_email_settings", payload, natural_key={"tenant_id": repo.tenant_id})
                existing = saved
                save_success_popup("Email server settings saved.", queue_for_rerun=True); st.rerun()
            except Exception as exc: st.error(str(exc))

    with stage_section("B", "RESPONSIBILITY ROUTING", "Map each pending workflow event to the next responsible Employee. The Employee Master email address is used automatically.", key="email_settings_routes"):
        employees = [e for e in repo.select("employees", order_by="first_name", limit=5000) if str(e.get("status") or "ACTIVE") == "ACTIVE"]
        employee_options = {str(e.get("id")): f"{e.get('employee_code')} · {e.get('first_name')} {e.get('last_name')} · {e.get('email') or 'NO EMAIL'}" for e in employees}
        routes = {str(r.get("event_key")): r for r in repo.select("qcms_notification_routes", limit=500)}
        event = st.selectbox("Workflow Event", [k for k,_ in EVENTS], format_func=lambda k: dict(EVENTS).get(k,k))
        row = routes.get(event) or {}
        emp_ids = [""] + list(employee_options)
        current_emp = str(row.get("employee_id") or "")
        c=st.columns(3,gap="small")
        employee_id = c[0].selectbox("Responsible Employee", emp_ids, index=emp_ids.index(current_emp) if current_emp in emp_ids else 0, format_func=lambda v: employee_options.get(v,"— Not assigned —"))
        fallback = c[1].text_input("Fallback Email", value=str(row.get("fallback_email") or ""))
        route_enabled = c[2].toggle("Route Enabled", value=bool(row.get("enabled", False)))
        subject = st.text_input("Email Subject", value=str(row.get("subject_template") or f"QCMS · {dict(EVENTS).get(event,event)}"))
        if st.button("Save Responsibility Route", type="primary", width="stretch"):
            payload={"event_key":event,"route_label":dict(EVENTS).get(event,event),"employee_id":employee_id or None,"fallback_email":fallback.strip() or None,"subject_template":subject.strip() or None,"enabled":route_enabled}
            try:
                repo.upsert_by("qcms_notification_routes",payload,natural_key={"tenant_id":repo.tenant_id,"event_key":event})
                save_success_popup("Notification responsibility route saved.", queue_for_rerun=True); st.rerun()
            except Exception as exc: st.error(str(exc))
        route_frame=[]
        for key,label in EVENTS:
            r=routes.get(key) or {}; emp=next((e for e in employees if str(e.get('id'))==str(r.get('employee_id'))),{})
            route_frame.append({"Event":label,"Employee":" ".join(v for v in (str(emp.get('first_name') or ''),str(emp.get('last_name') or '')) if v),"Email":emp.get('email') or r.get('fallback_email'),"Enabled":bool(r.get('enabled',False))})
        portal_table(pd.DataFrame(route_frame),hide_index=True,width="stretch",height=330)

    with stage_section("C", "TEST & NOTIFICATION OUTBOX", "Send a test message or retry failed/pending workflow notifications. Business transactions are never rolled back if email delivery fails.", key="email_settings_test"):
        test_email = st.text_input("Test Recipient Email", value=str(profile.get("email") or ""))
        c=st.columns(2,gap="small")
        if c[0].button("Send Test Email", type="primary", width="stretch"):
            try:
                row=notifier.enqueue("EMAIL_SERVER_TEST",subject="QCMS · Email server test",body_text="QCMS email server test completed from Email Server & Notifications settings.",recipient_email=test_email,recipient_name="QCMS Administrator",context={"test":True})
                result=notifier.dispatch([row] if row else [])
                if result.get("error"): st.warning(f"Test queued but delivery returned: {result.get('error')}")
                else: save_success_popup("Test email queued/delivery requested.", queue_for_rerun=True); st.rerun()
            except Exception as exc: st.error(str(exc))
        if c[1].button("Retry Pending / Failed Email", width="stretch"):
            result=notifier.retry_pending(limit=50)
            if result.get("error"): st.warning(str(result.get("error")))
            else: save_success_popup(f"Retry requested for {result.get('processed',0)} notification(s).", queue_for_rerun=True); st.rerun()
        outbox=repo.select("qcms_notification_outbox",order_by="created_at",desc=True,limit=200)
        if outbox:
            frame=pd.DataFrame([{"Created":r.get("created_at"),"Event":r.get("event_key"),"Recipient":r.get("recipient_email"),"Subject":r.get("subject"),"Status":r.get("status"),"Attempts":r.get("attempts"),"Sent":r.get("sent_at"),"Last Error":r.get("last_error")} for r in outbox])
            portal_table(frame,hide_index=True,width="stretch",height=420)
        else: st.info("No notification outbox records yet.")
