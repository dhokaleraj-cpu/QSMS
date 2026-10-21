"""R35 · My Notifications: approval requests, tasks and updates for the signed-in user (web inbox).

The same rows reach the STAWN QCMS Android / iPhone / iPad apps (in-app inbox + phone notification) and,
when the company switched it on and the user opted in, WhatsApp.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from core import licence_service as lic
from core.auth import current_profile
from core.db_errors import db_message
from core.ui import page_header, save_success_popup, section_bar, stage_section

IST = ZoneInfo("Asia/Kolkata")


def _when(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(IST)
        return dt.strftime("%d-%m-%Y %H:%M")
    except Exception:
        return str(value)[:16]


def _open_route(route: str | None) -> None:
    route = str(route or "").strip().strip("/")
    if not route:
        return
    pages = st.session_state.get("_qcms_page_by_path") or {}
    page = pages.get(route.split("?")[0])
    if page is not None:
        st.switch_page(page)
    else:
        st.info(f"Open the module '{route}' from the menu.")


def render() -> None:
    page_header("My Notifications", "Approval requests, tasks assigned to you and updates on your records.", "Notifications")
    profile = current_profile() or {}

    top1, top2, top3 = st.columns([2.2, 1.2, 1.2], gap="small", vertical_alignment="bottom")
    view = top1.segmented_control("Show", ["Unread", "All"], default="Unread", key="qcms_notif_view") or "Unread"
    if top2.button("Refresh", icon=":material/refresh:", width="stretch"):
        lic.unread_count(force=True)
        st.rerun()
    try:
        rows = lic.my_notifications(limit=200, unread_only=view == "Unread")
    except Exception as exc:
        st.error("Notifications are not available yet: " + db_message(exc))
        rows = []
    unread_ids = [str(r["id"]) for r in rows if not r.get("is_read")]
    if top3.button("Mark all read", icon=":material/done_all:", width="stretch", disabled=not unread_ids):
        try:
            n = lic.mark_read(None)
            save_success_popup(f"{n} notification(s) marked as read.", queue_for_rerun=True)
            st.rerun()
        except Exception as exc:
            st.error(db_message(exc))

    if not rows:
        st.success("You are all caught up – no notifications here." if view == "Unread" else "No notifications yet.")
    for row in rows:
        icon = lic.CATEGORY_ICON.get(str(row.get("category") or "").upper(), "🔔")
        unread = not row.get("is_read")
        with st.container(border=True):
            c1, c2 = st.columns([6, 1.6], gap="small", vertical_alignment="center")
            with c1:
                title = f"{icon} **{row.get('title') or 'Notification'}**" + ("  :red-badge[NEW]" if unread else "")
                st.markdown(title)
                if row.get("body"):
                    st.caption(str(row["body"])[:600])
                st.caption(f"{str(row.get('category') or '').title()} · {_when(row.get('created_at'))}"
                           + (f" · {row.get('module_key')}" if row.get("module_key") else ""))
            with c2:
                if row.get("web_route") and st.button("Open", key=f"qcms_notif_open_{row['id']}", icon=":material/open_in_new:", width="stretch"):
                    try:
                        if unread:
                            lic.mark_read([str(row["id"])])
                    except Exception:
                        pass
                    _open_route(row.get("web_route"))
                if unread and st.button("Mark read", key=f"qcms_notif_read_{row['id']}", width="stretch"):
                    try:
                        lic.mark_read([str(row["id"])])
                        st.rerun()
                    except Exception as exc:
                        st.error(db_message(exc))

    with stage_section("B", "WHATSAPP ALERTS ON MY MOBILE",
                       "Optional. Approval requests and tasks for you are also sent to your WhatsApp number once the company "
                       "administrator has switched on WhatsApp in Admin → Licence & Company.", key="qcms_notif_my_wa"):
        wa = lic.whatsapp_settings()
        st.caption("Company WhatsApp: " + ("ON" if wa.get("enabled") else "OFF – the administrator has not switched it on yet"))
        c1, c2, c3 = st.columns([1.4, 2.0, 1.2], gap="small", vertical_alignment="bottom")
        opt_in = c1.toggle("Send my alerts on WhatsApp", key="qcms_my_wa_opt_in")
        mobile = c2.text_input("My WhatsApp number (with country code)", placeholder="+91 98XXXXXXXX", key="qcms_my_wa_mobile")
        if c3.button("Save", type="primary", width="stretch", key="qcms_my_wa_save"):
            try:
                out = lic.set_my_whatsapp(opt_in, mobile)
                save_success_popup("WhatsApp preference saved" + (f" for {out.get('mobile_number')}" if out.get("mobile_number") else "") + ".")
            except Exception as exc:
                st.error(db_message(exc))
    st.caption(f"Signed in as {profile.get('email') or ''}. Notifications are kept for every user separately; nobody else can read yours.")
