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

    # Login-only stylesheet. It deliberately targets Streamlit's stable data-testid
    # containers instead of page-key classes so Streamlit Cloud rerenders cannot
    # silently fall back to the default layout.
    st.markdown(
        """
        <style>
        header[data-testid="stHeader"]{height:0!important;background:transparent!important;}
        div[data-testid="stToolbar"],#MainMenu,footer,[data-testid="stStatusWidget"]{display:none!important;}
        div[data-testid="stAppViewContainer"]{
          background:
            radial-gradient(circle at 15% 8%,rgba(14,116,181,.16),transparent 27%),
            radial-gradient(circle at 88% 92%,rgba(5,55,99,.10),transparent 28%),
            linear-gradient(135deg,#EAF2F8 0%,#F8FBFD 48%,#EEF5FA 100%)!important;
          min-height:100vh!important;
        }
        section[data-testid="stMain"],section.main{background:transparent!important;}
        div[data-testid="stMainBlockContainer"],section.main>div.block-container{
          width:100%!important;max-width:610px!important;margin:0 auto!important;
          padding:4.0vh 22px 1.2rem!important;
        }
        .qcms-login-brand-card{
          position:relative;overflow:hidden;background:#FFFFFF;border:1px solid #B9CDE0;border-radius:18px;
          padding:18px 22px 17px;text-align:center;box-shadow:0 14px 36px rgba(8,52,88,.13);margin-bottom:16px;
        }
        .qcms-login-brand-card:before{content:"";position:absolute;top:0;left:0;right:0;height:6px;background:linear-gradient(90deg,#073A68,#0B6DAA,#13A6D7);}
        .qcms-login-brand-card:after{content:"";position:absolute;width:120px;height:120px;border-radius:50%;right:-54px;top:-60px;background:rgba(15,126,190,.07);}
        .qcms-login-logo-wrap{height:58px;display:flex;align-items:center;justify-content:center;margin-bottom:7px;position:relative;z-index:1;}
        .qcms-login-logo{width:160px!important;max-height:56px!important;object-fit:contain!important;}
        .qcms-login-logo-fallback{font-size:32px;font-weight:950;color:#0A4777;}
        .qcms-login-brand-title{font-family:Aptos,"Segoe UI",Arial,sans-serif;font-size:29px;font-weight:950;line-height:1.02;letter-spacing:-.018em;color:#075EA5;text-transform:uppercase;position:relative;z-index:1;}
        .qcms-login-brand-sub{font-size:11px;font-weight:700;color:#62788A;margin-top:7px;line-height:1.38;position:relative;z-index:1;}
        .qcms-login-badges{display:flex;justify-content:center;gap:6px;flex-wrap:wrap;margin-top:10px;position:relative;z-index:1;}
        .qcms-login-badges span{padding:4px 8px;border-radius:999px;background:#EDF6FC;border:1px solid #C9E0EF;color:#175F91;font-size:8.5px;font-weight:900;letter-spacing:.035em;}
        div[data-testid="stForm"]{
          background:#FFFFFF!important;border:1px solid #C4D5E3!important;border-radius:16px!important;
          padding:18px 20px 20px!important;box-shadow:0 10px 26px rgba(8,52,88,.09)!important;margin:0!important;
        }
        .qcms-login-form-title{font-size:18px;font-weight:950;color:#0D3657;margin:0 0 2px;}
        .qcms-login-form-sub{font-size:10.5px;font-weight:650;color:#718596;margin:0 0 12px;}
        div[data-testid="stForm"] label[data-testid="stWidgetLabel"] p{font-size:12.5px!important;font-weight:900!important;color:#113B5C!important;margin-bottom:4px!important;}
        div[data-testid="stForm"] div[data-baseweb="input"]{
          min-height:46px!important;background:#FBFDFF!important;border:1px solid #B7CCDD!important;border-radius:9px!important;
          box-shadow:inset 0 1px 1px rgba(5,50,82,.02),0 2px 7px rgba(5,50,82,.04)!important;transition:.15s ease!important;
        }
        div[data-testid="stForm"] div[data-baseweb="input"]:focus-within{border-color:#0B75B5!important;box-shadow:0 0 0 3px rgba(11,117,181,.11),0 4px 12px rgba(5,50,82,.06)!important;}
        div[data-testid="stForm"] input{font-size:12.5px!important;font-weight:700!important;color:#17384F!important;}
        div[data-testid="stForm"] .stFormSubmitButton>button{
          width:100%!important;min-height:45px!important;margin-top:7px!important;border:0!important;border-radius:9px!important;
          background:linear-gradient(95deg,#075A91 0%,#0B7DBC 55%,#0A93C8 100%)!important;color:#FFFFFF!important;
          box-shadow:0 8px 18px rgba(7,100,157,.24)!important;font-size:13px!important;font-weight:950!important;letter-spacing:.02em!important;
        }
        div[data-testid="stForm"] .stFormSubmitButton>button:hover{transform:translateY(-1px)!important;box-shadow:0 10px 22px rgba(7,100,157,.30)!important;}
        details[data-testid="stExpander"]{background:rgba(255,255,255,.88)!important;border:1px solid #CFDDE8!important;border-radius:11px!important;box-shadow:0 4px 12px rgba(8,52,88,.05)!important;}
        details[data-testid="stExpander"] summary{font-size:11px!important;font-weight:850!important;color:#274861!important;}
        .qcms-login-preview-separator{height:1px;background:linear-gradient(90deg,transparent,#C7D6E2,transparent);margin:.45rem 0 .15rem;}
        .qcms-login-preview-note{text-align:center;font-size:9px;font-weight:650;color:#84929D;margin-top:-.25rem;}
        .qcms-login-footer{text-align:center;font-size:10.5px;font-weight:750;color:#243A4C;line-height:1.55;padding-top:8px;}
        .qcms-login-footer span{display:inline-block;padding:0 7px;color:#8A98A4;}
        .qcms-login-version{display:inline-block;margin-top:3px;padding:3px 8px;border-radius:999px;background:#E8F3FA;border:1px solid #C2DEEE;color:#0C6299;font-size:8.5px;font-weight:900;}
        @media(max-width:700px){
          div[data-testid="stMainBlockContainer"],section.main>div.block-container{max-width:96vw!important;padding:1rem 12px .8rem!important;}
          .qcms-login-brand-card{padding:16px 13px 14px}.qcms-login-brand-title{font-size:22px}.qcms-login-brand-sub{font-size:9.5px}
          div[data-testid="stForm"]{padding:15px 14px 17px!important}.qcms-login-footer{font-size:9.5px}.qcms-login-footer span{padding:0 4px;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f'''<div class="qcms-login-brand-card">
          <div class="qcms-login-logo-wrap">{logo}</div>
          <div class="qcms-login-brand-title">QUALITY CONTROL<br>MONITORING SYSTEM</div>
          <div class="qcms-login-brand-sub">Four Star Industries &middot; Controlled Quality Records &middot; Inspection &middot; NPD/APQP &middot; Complaint &amp; CAPA Management</div>
          <div class="qcms-login-badges"><span>SECURE ACCESS</span><span>LIVE TRACEABILITY</span><span>CONTROLLED RECORDS</span><span>QCMS {safe(settings.version)}</span><span>BUILD 4109-LOGIN-IMPORT-GUARD</span></div>
        </div>''',
        unsafe_allow_html=True,
    )

    with st.form("phase1_login_form"):
        st.markdown('<div class="qcms-login-form-title">Secure Sign In</div><div class="qcms-login-form-sub">Use your registered company email and QCMS password.</div>', unsafe_allow_html=True)
        email = st.text_input("User Name", placeholder="name@company.com")
        password = st.text_input("Password", type="password", placeholder="Enter password")
        submitted = st.form_submit_button("LOGIN TO QCMS", type="primary", width="stretch")
    if submitted:
        try:
            login(email, password)
            st.rerun()
        except Exception as exc:
            st.error(_friendly_error(exc, "Sign-in"))

    with st.expander("Forgot password"):
        reset_email = st.text_input("Registered email", key="reset_email", placeholder="name@company.com")
        if st.button("Send recovery email", key="send_recovery", width="stretch"):
            try:
                request_password_reset(reset_email)
                st.success("Recovery instructions were requested. Check the registered inbox.")
            except Exception as exc:
                st.error(_friendly_error(exc, "Password recovery"))

    if settings.allow_preview:
        st.markdown('<div class="qcms-login-preview-separator"></div>', unsafe_allow_html=True)
        if st.button("Open controlled Phase 1 preview", width="stretch", key="open_controlled_preview"):
            start_preview()
        st.markdown('<div class="qcms-login-preview-note">Preview is read-only and never writes to Supabase.</div>', unsafe_allow_html=True)

    st.markdown(
        f'''<div class="qcms-login-footer">Developed by Rajesh Dhokale <span>|</span> dhokaleraj@icloud.com <span>|</span> Copyrights to jrdhokale<br><span class="qcms-login-version">App Version {safe(settings.version)} · Build 4109-LOGIN-IMPORT-GUARD</span></div>''',
        unsafe_allow_html=True,
    )

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
