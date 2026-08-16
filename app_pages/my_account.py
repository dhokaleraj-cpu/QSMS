from __future__ import annotations

import streamlit as st

from core.auth import current_profile, verify_current_password
from core.database import get_session_client
from core.permissions import role_label
from core.ui import page_header, save_success_popup, section_bar, stage_section


def render() -> None:
    page_header("My Account", "Manage your own QCMS login password and view your current account information.", "Account")
    profile = current_profile() or {}

    with stage_section("A", 'LOGIN ACCOUNT', key="my_account_render_a"):
        c1, c2, c3 = st.columns(3, gap="small")
        c1.text_input("Name", value=str(profile.get("full_name") or ""), disabled=True)
        c2.text_input("Email / Username", value=str(profile.get("email") or ""), disabled=True)
        c3.text_input("QCMS Role", value=role_label(profile), disabled=True)

    with stage_section("B", 'CHANGE LOGIN PASSWORD', 'Available to every signed-in QCMS user. Your current password is verified before the change is accepted.', key="my_account_render_b"):
        current = st.text_input("Current Password", type="password", key="my_account_current_password")
        c1, c2 = st.columns(2, gap="small")
        new_password = c1.text_input("New Password", type="password", key="my_account_new_password")
        confirm_password = c2.text_input("Confirm New Password", type="password", key="my_account_confirm_password")
        st.caption("Use at least 10 characters. The new password applies to your QCMS login immediately.")

        if st.button("Change My Login Password", type="primary", width="stretch"):
            try:
                if len(new_password) < 10:
                    raise ValueError("Use a new password with at least 10 characters.")
                if new_password != confirm_password:
                    raise ValueError("New Password and Confirm New Password do not match.")
                verify_current_password(current)
                client = get_session_client()
                if client is None:
                    raise RuntimeError("A live QCMS session is required to change your password.")
                response = client.auth.update_user({"password": new_password})
                if not getattr(response, "user", None):
                    raise RuntimeError("Supabase did not confirm the password change.")
                save_success_popup("Your QCMS login password was changed successfully.")
            except Exception as exc:
                st.error(str(exc))
