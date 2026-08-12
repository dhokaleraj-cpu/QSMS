from __future__ import annotations

import time
from typing import Any

import streamlit as st

from core.config import get_settings, is_preview_session
from core.database import get_session_client, new_client
from core.ui import logo_data_uri, render_public_brand, safe


PREVIEW_PROFILE = {
    "id": "phase1-preview-user",
    "tenant_id": "00000000-0000-0000-0000-000000000001",
    "full_name": "Quality Control Preview",
    "email": "preview@fsi.local",
    "role": "QUALITY_MANAGER",
    "status": "ACTIVE",
}


def current_profile() -> dict[str, Any] | None:
    if is_preview_session():
        st.session_state.setdefault("profile", PREVIEW_PROFILE.copy())
    return st.session_state.get("profile")


def is_logged_in() -> bool:
    return current_profile() is not None


def _friendly_error(exc: Exception, action: str) -> str:
    text = str(exc)
    lower = text.lower()
    if "invalid login credentials" in lower or "invalid_credentials" in lower:
        return "The email address or password is incorrect."
    if "email not confirmed" in lower:
        return "Confirm the Supabase email message, then sign in."
    if "already registered" in lower or "already been registered" in lower:
        return "This email address is already registered. Use Sign in or password recovery."
    if "setup code" in lower:
        return "The one-time administrator setup code is not valid."
    if "first administrator has already been created" in lower:
        return "The first administrator is already configured. Sign in with that account."
    if "supabase is not configured" in lower:
        return text
    return f"{action} failed: {text}"


def _fetch_profile(client: Any, user_id: str) -> dict[str, Any]:
    for _ in range(3):
        response = client.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        if response.data:
            return dict(response.data[0])
        time.sleep(0.2)
    raise RuntimeError("The authenticated account has no QCMS profile. Ask the QCMS administrator to verify user provisioning.")


def login(email: str, password: str) -> dict[str, Any]:
    if not email.strip() or not password:
        raise ValueError("Email and password are mandatory.")
    client = new_client()
    response = client.auth.sign_in_with_password({"email": email.strip(), "password": password})
    if not response.user:
        raise RuntimeError("Authentication failed.")
    profile = _fetch_profile(client, str(response.user.id))
    if str(profile.get("status") or "ACTIVE").upper() != "ACTIVE":
        client.auth.sign_out()
        raise PermissionError("This QCMS account is not active.")
    st.session_state["supabase_client"] = client
    st.session_state["profile"] = profile
    st.session_state.pop("_qsms_preview", None)
    return profile


def bootstrap_available(client: Any | None = None) -> bool:
    if is_preview_session():
        return False
    try:
        client = client or new_client()
        response = client.rpc("qsms_bootstrap_available").execute()
        value = response.data
        if isinstance(value, list):
            if not value:
                return False
            value = value[0]
            if isinstance(value, dict):
                value = next(iter(value.values()), False)
        return bool(value)
    except Exception:
        return False


def register_first_administrator(full_name: str, email: str, password: str, setup_code: str) -> dict[str, Any]:
    if not all([full_name.strip(), email.strip(), password, setup_code.strip()]):
        raise ValueError("Full name, email, password and setup code are mandatory.")
    if len(password) < 8:
        raise ValueError("Use a password with at least 8 characters.")
    client = new_client()
    response = client.auth.sign_up(
        {
            "email": email.strip(),
            "password": password,
            "options": {"data": {"full_name": full_name.strip()}},
        }
    )
    if not response.user:
        raise RuntimeError("Supabase did not create the account.")
    if getattr(response, "session", None):
        st.session_state["supabase_client"] = client
        st.session_state["profile"] = _fetch_profile(client, str(response.user.id))
        return claim_first_administrator(setup_code, full_name)
    return {
        "confirmation_required": True,
        "message": "Account created. Confirm the email, then sign in and enter the one-time setup code once.",
    }


def claim_first_administrator(setup_code: str, full_name: str = "") -> dict[str, Any]:
    client = get_session_client()
    if client is None:
        raise RuntimeError("A live Supabase session is required.")
    client.rpc(
        "qsms_claim_first_admin",
        {"p_setup_code": setup_code.strip(), "p_full_name": full_name.strip() or None},
    ).execute()
    auth_response = client.auth.get_user()
    if not auth_response.user:
        raise RuntimeError("The signed-in user could not be resolved.")
    profile = _fetch_profile(client, str(auth_response.user.id))
    st.session_state["profile"] = profile
    return profile


def needs_first_admin_claim(profile: dict[str, Any] | None = None) -> bool:
    profile = profile or current_profile() or {}
    return (
        not is_preview_session()
        and str(profile.get("role") or "VIEWER").upper() != "ADMIN"
        and bootstrap_available(get_session_client())
    )



def verify_current_password(password: str) -> None:
    """Re-authenticate the signed-in user before a destructive action."""
    if is_preview_session():
        raise PermissionError("Deletion is disabled in controlled preview mode.")
    profile = current_profile() or {}
    email = str(profile.get("email") or "").strip()
    if not email or not password:
        raise ValueError("Enter your current QCMS password.")
    verifier = new_client()
    try:
        response = verifier.auth.sign_in_with_password({"email": email, "password": password})
        if not response.user:
            raise PermissionError("Password verification failed.")
    except Exception as exc:
        raise PermissionError("The password is incorrect. The selected row was not deleted.") from exc
    finally:
        try:
            verifier.auth.sign_out({"scope": "local"})
        except Exception:
            # Never fall back to the default global scope because that would
            # terminate the user's other active QCMS sessions.
            pass

def request_password_reset(email: str) -> None:
    if not email.strip():
        raise ValueError("Enter the registered email address.")
    client = new_client()
    settings = get_settings()
    options = {"redirect_to": settings.qsms_url}
    method = getattr(client.auth, "reset_password_for_email", None)
    if callable(method):
        method(email.strip(), options)
        return
    fallback = getattr(client.auth, "reset_password_email", None)
    if callable(fallback):
        fallback(email.strip(), options)
        return
    raise RuntimeError("Password recovery is not available in the installed Supabase client.")


def start_preview() -> None:
    st.session_state["_qsms_preview"] = True
    st.session_state["profile"] = PREVIEW_PROFILE.copy()
    st.session_state.pop("supabase_client", None)
    st.rerun()


def logout() -> None:
    client = st.session_state.get("supabase_client")
    if client is not None:
        try:
            client.auth.sign_out()
        except Exception:
            pass
    for key in ("profile", "supabase_client", "_qsms_preview", "selected_master_record"):
        st.session_state.pop(key, None)
    st.rerun()


def render_login() -> None:
    settings = get_settings()
    uri = logo_data_uri()
    logo = f'<img class="qcms-login-logo" src="{uri}" alt="Four Star Industries">' if uri else '<div class="qcms-login-logo-fallback">FSI</div>'

    _, center, _ = st.columns([0.20, 1.60, 0.20])
    with center:
        with st.container(key="qcms_login_shell"):
            hero, panel = st.columns([1.08, 0.92], gap="large", vertical_alignment="center")
            with hero:
                st.markdown(
                    f'''<div class="qcms-login-hero">
                      <div class="qcms-login-logo-wrap">{logo}</div>
                      <div class="qcms-login-eyebrow">FOUR STAR INDUSTRIES</div>
                      <div class="qcms-login-title">QUALITY CONTROL<br>MONITORING SYSTEM</div>
                      <div class="qcms-login-subtitle">Connected quality. Controlled decisions. Complete traceability.</div>
                      <div class="qcms-login-feature-list">
                        <div class="qcms-login-feature"><span>01</span><div><b>Material &amp; RMTC control</b><small>Heat genealogy, inward quality and controlled release.</small></div></div>
                        <div class="qcms-login-feature"><span>02</span><div><b>Inspection intelligence</b><small>Dimensional, MetLAB, OSP and validation workflows.</small></div></div>
                        <div class="qcms-login-feature"><span>03</span><div><b>NPD &amp; APQP visibility</b><small>Process status, customer standards and accountable ownership.</small></div></div>
                      </div>
                      <div class="qcms-login-badges"><span>SECURE ACCESS</span><span>LIVE TRACEABILITY</span><span>CONTROLLED RECORDS</span></div>
                      <div class="qcms-login-version">Plant {safe(settings.plant_code)} &nbsp;•&nbsp; QCMS {safe(settings.version)}</div>
                    </div>''',
                    unsafe_allow_html=True,
                )
            with panel:
                with st.container(key="qcms_login_panel"):
                    st.markdown(
                        '<div class="qcms-login-panel-head"><div class="qcms-login-lock">✓</div>'
                        '<div><div class="qcms-login-welcome">Welcome back</div>'
                        '<div class="qcms-login-help">Sign in to your controlled quality workspace using your registered company email.</div></div></div>',
                        unsafe_allow_html=True,
                    )
                    with st.form("phase1_login_form"):
                        email = st.text_input("Email address", placeholder="name@company.com")
                        password = st.text_input("Password", type="password", placeholder="Enter your password")
                        submitted = st.form_submit_button("Sign in to QCMS", type="primary", width="stretch")
                    if submitted:
                        try:
                            login(email, password)
                            st.rerun()
                        except Exception as exc:
                            st.error(_friendly_error(exc, "Sign-in"))

                    st.markdown('<div class="qcms-login-security">Protected by role-based access, password verification and audit traceability.</div>', unsafe_allow_html=True)
                    with st.expander("Forgot password?"):
                        reset_email = st.text_input("Registered email", key="reset_email", placeholder="name@company.com")
                        if st.button("Send recovery email", key="send_recovery", width="stretch"):
                            try:
                                request_password_reset(reset_email)
                                st.success("Recovery instructions were requested. Check the registered inbox.")
                            except Exception as exc:
                                st.error(_friendly_error(exc, "Password recovery"))

                    if settings.allow_preview:
                        st.markdown('<div class="qcms-login-preview-label">CONTROLLED PREVIEW</div>', unsafe_allow_html=True)
                        if st.button("Open read-only preview", width="stretch", key="open_controlled_preview"):
                            start_preview()
                        st.caption("Preview mode is session-only and never writes to Supabase.")


def render_first_admin_claim() -> None:
    render_public_brand()
    _, center, _ = st.columns([1, 1.1, 1])
    with center:
        with st.container(border=True, key="fsi_login_card"):
            st.markdown('<div class="fsi-login-card-title">Activate first administrator</div>', unsafe_allow_html=True)
            st.markdown('<div class="fsi-login-help">Your email is confirmed. Enter the one-time setup code to complete the controlled administrator activation.</div>', unsafe_allow_html=True)
            with st.form("first_admin_claim"):
                full_name = st.text_input("Full name", value=str((current_profile() or {}).get("full_name") or ""))
                setup_code = st.text_input("One-time setup code", type="password")
                activate = st.form_submit_button("Activate administrator", type="primary", width="stretch")
            if activate:
                try:
                    claim_first_administrator(setup_code, full_name)
                    st.success("Administrator role activated.")
                    st.rerun()
                except Exception as exc:
                    st.error(_friendly_error(exc, "Administrator activation"))
            if st.button("Sign out", key="claim_sign_out", width="stretch"):
                logout()
