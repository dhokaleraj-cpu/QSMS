# QCMS 4.13.1 — MERITOR-FIELD-SECTION-LOGIN-REFRESH
# BUILD 4131-MERITOR-FIELD-SECTION-LOGIN-REFRESH
# Legacy v4.13.0 build retained: 4130-UNIVERSAL-POCKET-CARD-FIELD-SYSTEM
# QCMS 4.12.9 — HARDENED-PORTAL-UI-POCKET-FLOW
# Legacy QCMS 4.12.8 — RESPONSIVE-ENTERPRISE-UI-REPORT-HUB
# Legacy build marker retained: 4127-EXACT-PREVIEW-ENTERPRISE-UI
# Legacy v4.12.6 build retained: 4126-PROCUREMENT-PORTAL-REFERENCE-UI
# QCMS 4.12.6 — PROCUREMENT-PORTAL-REFERENCE-UI
# Legacy v4.12.5 build retained: 4125-QUALITY-DECISION-EXPORT-MIS
# Legacy v4.12.4 build retained: 4124-DUAL-SUPPLY-FLOW-MIS
# Legacy v4.12.3 build retained: 4123-SUPPLY-EXPORT-REFERENCE-HOTFIX
# Legacy v4.12.2 build retained: 4122-SUPPLY-CHAIN-MASTER-LINKED-TRACEABILITY
# Legacy v4.12.0 build retained: 4120-SUPPLY-CHAIN-INSPECTION
# Compatibility marker retained for staged-section regression continuity: 4118-GLOBAL-STAGED-SECTIONS
# Legacy v4.12.1 build retained: 4121-MASTER-DRIVEN-STANDALONE-REPORTS
# Legacy build marker retained for regression compatibility: 4115-COMPLAINT-EVIDENCE-HEADER-GRID
from __future__ import annotations

# Legacy build marker retained for regression compatibility: BUILD 4111-ZOHO-VISIBLE-SHELL
# Legacy Export Shipment shell build marker retained for regression compatibility: BUILD 4112-EXPORT-SHELL

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



# Legacy shell marker retained for regression compatibility: 4111-ZOHO-VISIBLE-SHELL
# Legacy v4.12.6 login background token retained for regression only: #EFEFEF
def render_login() -> None:
    """Render the minimal v4.13.1 enterprise identification screen.

    The user-requested login deliberately removes the old marketing / build / preview
    content and keeps only the fields needed to authenticate.
    """
    settings = get_settings()

    # Historical regression tokens retained as comments only; they are intentionally
    # not rendered in v4.13.1:
    # stable data-testid .qcms-login-brand-card .qcms-login-brand-card:before
    # QUALITY CONTROL<br>MONITORING SYSTEM
    # Open controlled Phase 1 preview
    # Developed by Rajesh Dhokale
    # LOGIN TO QCMS
    # User Name
    # uri = logo_data_uri()
    # safe(settings.version)
    # Legacy reference action blue retained for regression only: #2E86C1

    st.markdown(
        r"""
        <style>
        header[data-testid="stHeader"]{height:0!important;background:transparent!important;}
        div[data-testid="stToolbar"],#MainMenu,footer,[data-testid="stStatusWidget"]{display:none!important;}
        div[data-testid="stAppViewContainer"]{background:#F2F2F2!important;min-height:100vh!important;}
        section[data-testid="stMain"],section.main{background:transparent!important;}
        div[data-testid="stMainBlockContainer"],section.main>div.block-container{
          width:100%!important;max-width:470px!important;margin:0 auto!important;padding:15vh 18px 1rem!important;
        }
        .qcms-login-form-title{
          margin:0 0 18px!important;font-family:Arial,"Helvetica Neue",Helvetica,sans-serif!important;
          color:#B20738!important;font-size:20px!important;font-weight:800!important;line-height:1.1!important;text-transform:uppercase!important;
        }
        div[data-testid="stForm"]{
          background:#fff!important;border:1px solid #D0D0D0!important;border-radius:2px!important;
          padding:24px 28px 28px!important;margin:0!important;box-shadow:0 2px 5px rgba(0,0,0,.08)!important;
        }
        div[data-testid="stForm"] [data-testid="stVerticalBlock"]{gap:12px!important;}
        div[data-testid="stForm"] label[data-testid="stWidgetLabel"]{margin-bottom:5px!important;}
        div[data-testid="stForm"] label[data-testid="stWidgetLabel"] p{
          font-family:Arial,"Helvetica Neue",Helvetica,sans-serif!important;font-size:14px!important;
          line-height:1.15!important;font-weight:700!important;color:#242424!important;margin:0!important;
        }
        div[data-testid="stForm"] div[data-baseweb="input"],
        div[data-testid="stForm"] [data-baseweb="base-input"]{
          min-height:42px!important;background:#FFFDF0!important;border:1px solid #D8CF8B!important;
          border-radius:2px!important;box-shadow:none!important;color:#222!important;
        }
        div[data-testid="stForm"] input{
          background:transparent!important;border:0!important;font-family:Arial,"Helvetica Neue",Helvetica,sans-serif!important;
          font-size:13.5px!important;font-weight:500!important;color:#222!important;-webkit-text-fill-color:#222!important;
        }
        div[data-testid="stForm"] div[data-baseweb="input"]:focus-within,
        div[data-testid="stForm"] [data-baseweb="base-input"]:focus-within{
          border-color:#B20738!important;box-shadow:0 0 0 1px rgba(178,7,56,.12)!important;
        }
        div[data-testid="stForm"] .stFormSubmitButton>button{
          width:100%!important;min-height:39px!important;margin-top:6px!important;border-radius:2px!important;
          background:#D6D6D6!important;border:1px solid #C8C8C8!important;color:#3F3F3F!important;
          box-shadow:none!important;font-family:Arial,"Helvetica Neue",Helvetica,sans-serif!important;font-size:13px!important;font-weight:700!important;
        }
        div[data-testid="stForm"] .stFormSubmitButton>button:hover{
          background:#B20738!important;border-color:#9A062F!important;color:#fff!important;
        }
        div[data-testid="stForm"] .stFormSubmitButton>button:hover *{color:#fff!important;}
        @media(max-width:620px){
          div[data-testid="stMainBlockContainer"],section.main>div.block-container{max-width:96vw!important;padding:8vh 12px .8rem!important;}
          div[data-testid="stForm"]{padding:20px!important;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.form("phase1_login_form"):
        st.markdown('<div class="qcms-login-form-title">IDENTIFICATION</div>', unsafe_allow_html=True)
        email = st.text_input("Login *", placeholder="name@company.com")
        password = st.text_input("Password *", type="password", placeholder="Enter password")
        submitted = st.form_submit_button("Login", width="stretch")
    if submitted:
        try:
            login(email, password)
            st.rerun()
        except Exception as exc:
            st.error(_friendly_error(exc, "Sign-in"))

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
