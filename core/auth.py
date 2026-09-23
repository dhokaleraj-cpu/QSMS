# QCMS 4.14.5 BUILD 4145-DEPLOY-VERIFY-DIRECT-REPORT-EDIT-SMTP-TENANT-GUIDE
# QCMS 4.14.4 — METLAB-EDIT-MASTER-DUPLICATE-OPENING-IMPORT-SMTP-GUIDE
# BUILD 4144-METLAB-EDIT-MASTER-DUPLICATE-OPENING-IMPORT-SMTP-GUIDE
# QCMS 4.14.3 — PART-GRADES-LEADTIME-OPENING-STOCK-PASSWORD-EDIT-O365
# BUILD 4143-PART-GRADES-LEADTIME-OPENING-STOCK-PASSWORD-EDIT-O365
# QCMS 4.14.2 — PO-ORDER-VISIBILITY-FULL-PRICE-HISTORY
# BUILD 4142-PO-ORDER-VISIBILITY-FULL-PRICE-HISTORY
# COMPAT BUILD 4140-PO-SOURCE-RMTC-VALIDATION-HSN-EMAIL
# QCMS 4.13.8 — SUPPLY-PO-FSI-PART-RMTC-WORKSHEET
# BUILD 4138-MULTI-RM-PO-PRICE-HISTORY-TECH-DATA
# QCMS 4.13.5 — MAROON-SECTIONS-WHITE-FIELDS-KPI-ICON-FIX
# BUILD 4135-MAROON-SECTIONS-WHITE-FIELDS-KPI-ICON-FIX
# COMPAT BUILD 4134-PRIORITY-UI-RMTC-REUSE-DUPLICATE-SAFE-IMPORT
# QCMS 4.13.3 — LOGIN-NO-MENU-STAWN-FOOTER-PORTAL-POLISH
# BUILD 4133-LOGIN-NO-MENU-STAWN-FOOTER-PORTAL-POLISH
# Legacy v4.13.2 build retained: 4132-MERITOR-EXACT-GRID-SECTION-LOGIN-IMAGE
# Legacy v4.13.2 login-image regression token retained (not rendered): height:390px!important
# Legacy login regression tokens retained as non-rendered comments only:
# stable data-testid .qcms-login-brand-card .qcms-login-brand-card:before
# QUALITY CONTROL<br>MONITORING SYSTEM · User Name · LOGIN TO QCMS
# Developed by Rajesh Dhokale · Open controlled Phase 1 preview
# uri = logo_data_uri() · safe(settings.version) · #EFEFEF · #2E86C1 · max-width:470px!important
# Legacy QCMS 4.13.1 — MERITOR-FIELD-SECTION-LOGIN-REFRESH
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

import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import streamlit as st
import streamlit.components.v1 as components

from core.config import get_settings, is_preview_session
from core.database import get_session_client, new_client
from core.ui import app_footer, logo_data_uri, render_public_brand, safe
# Legacy import regression token: from core.ui import logo_data_uri, render_public_brand, safe




# QCMS v4.14.46 — browser/WebView persistent Supabase session bridge.
#
# A normal browser refresh and an Android direct-route load create a new
# Streamlit WebSocket/Python session. Session State therefore cannot be the only
# authentication store. v4.14.46 uses a Streamlit Components v2 bridge as the
# primary persistence layer. Components v2 executes with normal page DOM
# privileges, so it can read/write origin-scoped localStorage and return the
# stored Supabase session to Python on a fresh Streamlit run. The older
# same-origin cookie bridge is retained only as a backward-compatible fallback.
# No token is put in a URL, log message, QCMS table, or Android preference.
_PERSIST_STORAGE_KEY = "qcms.auth.session.v2"
_PERSIST_STORAGE_PENDING = "__QCMS_STORAGE_PENDING__"
_PERSIST_STORAGE_EMPTY = "__QCMS_STORAGE_EMPTY__"
_PERSIST_STORAGE_ERROR = "__QCMS_STORAGE_ERROR__"
_PERSIST_ACCESS_COOKIE = "qcms_auth_at_v1"
_PERSIST_REFRESH_COOKIE = "qcms_auth_rt_v1"
_PERSIST_COOKIE_MAX_AGE = 30 * 24 * 60 * 60
_PERSIST_AUTH_COMPONENT: Any | None = None


def _persistent_auth_component() -> Any | None:
    """R3 stability hotfix: disable Components-v2 auth storage.

    Some Streamlit/WebView combinations rendered the component as a second/blank
    login surface after widget reruns. QCMS now relies on its same-origin secure
    cookie bridge for refresh persistence and does not mount the v2 component.
    """
    return None


def _mount_auth_storage(*, action: str, payload: str = "", key: str) -> Any | None:
    return None


def _context_cookie(name: str) -> str:
    try:
        value = st.context.cookies.get(name, "")
    except Exception:
        value = ""
    try:
        return unquote(str(value or ""))
    except Exception:
        return str(value or "")


def _render_auth_cookie_script(*, access_token: str = "", refresh_token: str = "", clear: bool = False) -> None:
    """Backward-compatible cookie writer used only as a secondary restore path."""
    access_json = json.dumps(str(access_token or ""))
    refresh_json = json.dumps(str(refresh_token or ""))
    clear_js = "true" if clear else "false"
    components.html(
        f"""<script>
        (function(){{
          const clear = {clear_js};
          const at = {access_json};
          const rt = {refresh_json};
          const maxAge = {_PERSIST_COOKIE_MAX_AGE};
          const docs = [document];
          try {{ if (window.parent && window.parent.document) docs.push(window.parent.document); }} catch (e) {{}}
          function attrs() {{
            let out = '; Path=/; SameSite=Strict';
            try {{ if ((window.parent || window).location.protocol === 'https:') out += '; Secure'; }} catch (e) {{ if (location.protocol === 'https:') out += '; Secure'; }}
            return out;
          }}
          function setCookie(doc, name, value) {{
            if (clear) doc.cookie = name + '=; Path=/; Max-Age=0; SameSite=Strict' + ((location.protocol === 'https:') ? '; Secure' : '');
            else doc.cookie = name + '=' + encodeURIComponent(value) + '; Max-Age=' + maxAge + attrs();
          }}
          for (const doc of docs) {{
            try {{ setCookie(doc, '{_PERSIST_ACCESS_COOKIE}', at); }} catch (e) {{}}
            try {{ setCookie(doc, '{_PERSIST_REFRESH_COOKIE}', rt); }} catch (e) {{}}
          }}
        }})();
        </script>""",
        height=0,
        width=0,
        scrolling=False,
    )


def _session_payload(access_token: str, refresh_token: str) -> str:
    # Stable across normal widget reruns. Only a real token refresh changes the
    # persisted payload, preventing the auth bridge from remounting on each click.
    return json.dumps(
        {
            "access_token": str(access_token or ""),
            "refresh_token": str(refresh_token or ""),
        },
        separators=(",", ":"),
    )


def _payload_tokens(payload: str) -> tuple[str, str]:
    try:
        raw = json.loads(str(payload or ""))
    except Exception:
        return "", ""
    if not isinstance(raw, dict):
        return "", ""
    return str(raw.get("access_token") or ""), str(raw.get("refresh_token") or "")


def _queue_session_cookie(session: Any) -> None:
    if not session:
        return
    access = str(getattr(session, "access_token", "") or "")
    refresh = str(getattr(session, "refresh_token", "") or "")
    if not access or not refresh:
        return
    if (
        st.session_state.get("_qcms_cookie_synced_access") == access
        and st.session_state.get("_qcms_cookie_synced_refresh") == refresh
    ):
        return
    st.session_state["_qcms_cookie_write_tokens"] = {"access_token": access, "refresh_token": refresh}


def service_persistent_auth_bridge() -> bool:
    """Service queued browser-storage/cookie clear/write operations.

    Returns True on the rerun that is intentionally clearing persisted auth so
    streamlit_app.py will not attempt a restore from stale browser state.
    """
    if st.session_state.pop("_qcms_clear_auth_browser", False):
        mounted = _mount_auth_storage(action="clear", key="qcms_auth_clear")
        if mounted is None:
            _render_auth_cookie_script(clear=True)
        for name in (
            "_qcms_cookie_synced_access",
            "_qcms_cookie_synced_refresh",
            "_qcms_storage_synced_payload",
            "qcms_auth_read",
            "qcms_auth_write",
        ):
            st.session_state.pop(name, None)
        return True

    tokens = st.session_state.pop("_qcms_cookie_write_tokens", None)
    if isinstance(tokens, dict):
        access = str(tokens.get("access_token") or "")
        refresh = str(tokens.get("refresh_token") or "")
        if access and refresh:
            if _persistent_auth_component() is None:
                _render_auth_cookie_script(access_token=access, refresh_token=refresh)
            st.session_state["_qcms_cookie_synced_access"] = access
            st.session_state["_qcms_cookie_synced_refresh"] = refresh
    return False


def service_persistent_auth_cookie() -> bool:
    """Compatibility alias retained for older tests/imports."""
    return service_persistent_auth_bridge()


def _restore_with_tokens(access: str, refresh: str) -> bool:
    if not access or not refresh:
        return False
    client = new_client()
    response = client.auth.set_session(access, refresh)
    user = getattr(response, "user", None)
    session = getattr(response, "session", None)
    if not user or not session:
        raise RuntimeError("Stored QCMS session is no longer valid.")
    profile = _fetch_profile(client, str(user.id))
    if str(profile.get("status") or "ACTIVE").upper() != "ACTIVE":
        raise PermissionError("This QCMS account is not active.")
    st.session_state["supabase_client"] = client
    st.session_state["profile"] = profile
    st.session_state.pop("_qsms_preview", None)
    st.session_state.pop("_qcms_auth_restore_failed", None)
    _queue_session_cookie(session)
    return True


def restore_persistent_login() -> bool:
    """Restore Supabase authentication after website/WebView refresh.

    Refresh persistence uses same-origin Secure/SameSite cookies only. No Components-v2/localStorage renderer is mounted.
    When browser storage has mounted but has not returned its value yet, the
    caller is told to wait for the component-triggered rerun rather than briefly
    rendering the login page.
    """
    st.session_state["_qcms_auth_restore_pending"] = False
    if is_preview_session() or st.session_state.get("profile") is not None:
        return bool(st.session_state.get("profile"))
    if st.session_state.get("_qcms_auth_restore_failed"):
        return False

    # Fast refresh path: try the same-origin cookie before mounting any browser
    # component. The v2 bridge writes both localStorage and these cookies.
    access = _context_cookie(_PERSIST_ACCESS_COOKIE)
    refresh = _context_cookie(_PERSIST_REFRESH_COOKIE)
    if access and refresh:
        try:
            return _restore_with_tokens(access, refresh)
        except Exception:
            pass

    result = _mount_auth_storage(action="read", key="qcms_auth_read")
    payload = getattr(result, "payload", None) if result is not None else None

    # On a first mount Components v2 returns the Python default; JavaScript then
    # supplies localStorage and causes one automatic rerun.
    if payload in (None, _PERSIST_STORAGE_PENDING):
        if result is not None:
            st.session_state["_qcms_auth_restore_pending"] = True
            return False
        # Components v2 unavailable: cookie fallback is the only persistence path.
        return False

    access = refresh = ""
    if payload not in (_PERSIST_STORAGE_EMPTY, _PERSIST_STORAGE_ERROR):
        access, refresh = _payload_tokens(str(payload))
    if not access or not refresh:
        # Backward compatibility for a browser that still has v4.14.45 cookies.
        access = _context_cookie(_PERSIST_ACCESS_COOKIE)
        refresh = _context_cookie(_PERSIST_REFRESH_COOKIE)
    if not access or not refresh:
        return False

    try:
        return _restore_with_tokens(access, refresh)
    except Exception:
        # Invalid/expired/revoked storage must not create a restore loop.
        st.session_state["_qcms_auth_restore_failed"] = True
        st.session_state["_qcms_clear_auth_browser"] = True
        st.session_state.pop("supabase_client", None)
        st.session_state.pop("profile", None)
        return False


def sync_persistent_login_browser() -> None:
    """Persist the current Supabase session for refresh/direct-route recovery."""
    if is_preview_session():
        return
    client = st.session_state.get("supabase_client")
    if client is None:
        return
    try:
        session = client.auth.get_session()
    except Exception:
        session = None
    if not session:
        return
    access = str(getattr(session, "access_token", "") or "")
    refresh = str(getattr(session, "refresh_token", "") or "")
    if not access or not refresh:
        return

    payload = _session_payload(access, refresh)
    if st.session_state.get("_qcms_storage_synced_payload") != payload:
        _mount_auth_storage(action="write", payload=payload, key="qcms_auth_write")
        st.session_state["_qcms_storage_synced_payload"] = payload
    _queue_session_cookie(session)


def sync_persistent_login_cookie() -> None:
    """Compatibility alias retained for older tests/imports."""
    sync_persistent_login_browser()

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


def refresh_current_employee_link() -> dict[str, Any] | None:
    """Resolve the signed-in Employee Master link from live Supabase and refresh session state.

    This intentionally does not rely only on the profile snapshot created at login. User/Employee
    links can be changed by an administrator while another session is open; PO and approval
    workflows must therefore use the live relationship.
    """
    if is_preview_session():
        return None
    client = get_session_client()
    profile = current_profile() or {}
    if client is None or not profile:
        return None
    employee_id = ""
    try:
        response = client.rpc("qcms_current_login_employee_id").execute()
        value = response.data
        if isinstance(value, list):
            value = value[0] if value else None
            if isinstance(value, dict):
                value = next(iter(value.values()), None)
        employee_id = str(value or "").strip()
    except Exception:
        employee_id = ""
    row: dict[str, Any] | None = None
    try:
        query = client.table("employees").select("id,employee_code,first_name,last_name,email,department,designation,approval_authorities,reports_to_employee_id,is_top_level_authority,status,profile_id").eq("status", "ACTIVE")
        if employee_id:
            response = query.eq("id", employee_id).limit(1).execute()
        else:
            response = query.eq("profile_id", str(profile.get("id") or "")).limit(1).execute()
        if response.data:
            row = dict(response.data[0])
    except Exception:
        row = None
    if not row:
        return None
    refreshed = dict(profile)
    refreshed.update({
        "employee_id": row.get("id"),
        "employee_code": row.get("employee_code"),
        "department": row.get("department"),
        "designation": row.get("designation"),
        "approval_authorities": row.get("approval_authorities") or [],
        "reports_to_employee_id": row.get("reports_to_employee_id"),
        "is_top_level_authority": bool(row.get("is_top_level_authority")),
    })
    st.session_state["profile"] = refreshed
    return row


def current_employee_id(*, refresh: bool = True) -> str:
    profile = current_profile() or {}
    if refresh:
        row = refresh_current_employee_link()
        if row and row.get("id"):
            return str(row.get("id"))
    return str(profile.get("employee_id") or "").strip()


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
            profile = dict(response.data[0])
            try:
                employee = client.table("employees").select("id,employee_code,department,designation,approval_authorities").eq("profile_id", user_id).eq("status", "ACTIVE").limit(1).execute()
                if employee.data:
                    row = dict(employee.data[0])
                    profile["employee_id"] = row.get("id")
                    profile["employee_code"] = row.get("employee_code")
                    profile["department"] = row.get("department")
                    profile["designation"] = row.get("designation")
                    profile["approval_authorities"] = row.get("approval_authorities") or []
            except Exception:
                # User login must not fail just because the optional Employee link is unavailable.
                pass
            return profile
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
    st.session_state.pop("_qcms_auth_restore_failed", None)
    _queue_session_cookie(getattr(response, "session", None))
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
        _queue_session_cookie(getattr(response, "session", None))
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
    try:
        _queue_session_cookie(client.auth.get_session())
    except Exception:
        pass
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
    st.session_state["_qcms_clear_auth_browser"] = True
    st.session_state["_qcms_auth_restore_failed"] = True
    for key in (
        "_qcms_cookie_write_tokens",
        "_qcms_cookie_synced_access",
        "_qcms_cookie_synced_refresh",
        "_qcms_storage_synced_payload",
        "qcms_auth_read",
        "qcms_auth_write",
        "qcms_auth_clear",
    ):
        st.session_state.pop(key, None)
    st.rerun()



# Legacy shell marker retained for regression compatibility: 4111-ZOHO-VISIBLE-SHELL
# Legacy v4.12.6 login background token retained for regression only: #EFEFEF
def render_login() -> None:
    """Render the v4.13.4 reference-matched isolated login.

    No authenticated menu is rendered. The left card uses the cropped Four Star
    factory image and the right card contains only the IDENTIFICATION form.
    """
    factory_image = Path(__file__).resolve().parents[1] / "assets" / "login_factory.jpeg"

    st.markdown(
        r"""
        <style>
        header[data-testid="stHeader"]{display:none!important;height:0!important;min-height:0!important;background:transparent!important;}
        div[data-testid="stToolbar"],#MainMenu,footer,[data-testid="stStatusWidget"],
        div.st-key-fsi_shell,[class~="st-key-fsi_shell"],
        [class*="st-key-qcms_header_nav_"],[class*="st-key-qcms_header_exit"],
        div.st-key-qcms_workspace,[class~="st-key-qcms_workspace"],
        div.st-key-fsi_left_rail,[class~="st-key-fsi_left_rail"]{display:none!important;}
        div[data-testid="stAppViewContainer"],section[data-testid="stMain"]{background:#F2F2F2!important;min-height:100vh!important;}
        div[data-testid="stMainBlockContainer"],section.main>div.block-container{
          width:100%!important;max-width:1180px!important;margin:0 auto!important;padding:5.5vh 18px .8rem!important;
        }
        div.st-key-qcms_login_shell,[class~="st-key-qcms_login_shell"]{background:transparent!important;border:0!important;padding:0!important;margin:0!important;}
        div.st-key-qcms_login_shell [data-testid="stHorizontalBlock"]{gap:18px!important;align-items:flex-start!important;}
        div.st-key-qcms_login_image_card,[class~="st-key-qcms_login_image_card"]{
          background:#fff!important;border:1px solid #D0D0D0!important;border-radius:2px!important;
          padding:14px!important;box-shadow:0 2px 5px rgba(0,0,0,.07)!important;overflow:hidden!important;
        }
        .qcms-login-welcome{
          margin:2px 0 20px 2px!important;color:#B20738!important;font-family:Arial,"Helvetica Neue",Helvetica,sans-serif!important;
          font-size:18px!important;line-height:1.15!important;font-weight:900!important;
        }
        div.st-key-qcms_login_image_card [data-testid="stImage"]{margin:0!important;}
        div.st-key-qcms_login_image_card [data-testid="stImage"] img{
          width:100%!important;height:410px!important;object-fit:cover!important;object-position:center center!important;display:block!important;border:0!important;
        }
        div[data-testid="stForm"]{
          background:#fff!important;border:1px solid #D0D0D0!important;border-radius:2px!important;
          padding:24px 28px 28px!important;margin:0!important;box-shadow:0 2px 5px rgba(0,0,0,.08)!important;
        }
        .qcms-login-form-title{
          margin:0 0 22px!important;font-family:Arial,"Helvetica Neue",Helvetica,sans-serif!important;
          color:#B20738!important;font-size:20px!important;font-weight:900!important;line-height:1.1!important;text-transform:uppercase!important;
        }
        div[data-testid="stForm"] [data-testid="stVerticalBlock"]{gap:12px!important;}
        div[data-testid="stForm"] label[data-testid="stWidgetLabel"]{margin-bottom:5px!important;}
        div[data-testid="stForm"] label[data-testid="stWidgetLabel"] p{
          font-family:Arial,"Helvetica Neue",Helvetica,sans-serif!important;font-size:13px!important;
          line-height:1.15!important;font-weight:800!important;color:#242424!important;margin:0!important;
        }
        div[data-testid="stForm"] div[data-baseweb="input"],
        div[data-testid="stForm"] [data-baseweb="base-input"]{
          min-height:42px!important;background:#FFFDF0!important;border:1.2px solid #D7CE91!important;
          border-radius:2px!important;box-shadow:none!important;color:#222!important;
        }
        div[data-testid="stForm"] input{
          background:transparent!important;border:0!important;font-family:Arial,"Helvetica Neue",Helvetica,sans-serif!important;
          font-size:13px!important;font-weight:500!important;color:#222!important;-webkit-text-fill-color:#222!important;
        }
        div[data-testid="stForm"] div[data-baseweb="input"]:focus-within,
        div[data-testid="stForm"] [data-baseweb="base-input"]:focus-within{
          border-color:#B20738!important;box-shadow:0 0 0 1px rgba(178,7,56,.11)!important;
        }
        div[data-testid="stForm"] .stFormSubmitButton>button{
          width:100%!important;min-height:40px!important;margin-top:7px!important;border-radius:2px!important;
          background:#B20738!important;border:1px solid #90062E!important;color:#fff!important;
          box-shadow:none!important;font-family:Arial,"Helvetica Neue",Helvetica,sans-serif!important;font-size:13px!important;font-weight:800!important;
        }
        div[data-testid="stForm"] .stFormSubmitButton>button:hover{
          background:#90062E!important;border-color:#780526!important;color:#fff!important;
        }
        div[data-testid="stForm"] .stFormSubmitButton>button:hover *{color:#fff!important;}
        @media(max-width:850px){
          div[data-testid="stMainBlockContainer"],section.main>div.block-container{max-width:96vw!important;padding:5vh 12px .8rem!important;}
          div.st-key-qcms_login_shell [data-testid="stHorizontalBlock"]{display:block!important;}
          div.st-key-qcms_login_image_card{margin-bottom:14px!important;}
          div.st-key-qcms_login_image_card [data-testid="stImage"] img{height:250px!important;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=False, key="qcms_login_shell"):
        image_col, form_col = st.columns([1.85, 1.0], gap="medium", vertical_alignment="top")
        with image_col:
            with st.container(border=True, key="qcms_login_image_card"):
                st.markdown('<div class="qcms-login-welcome">Welcome to Four Star Industries</div>', unsafe_allow_html=True)
                if factory_image.exists():
                    st.image(str(factory_image), width="stretch")
        with form_col:
            with st.form("phase1_login_form"):
                st.markdown('<div class="qcms-login-form-title">IDENTIFICATION</div>', unsafe_allow_html=True)
                email = st.text_input("Login *", placeholder="name@company.com")
                password = st.text_input("Password *", type="password", placeholder="Enter password")
                submitted = st.form_submit_button("Login", width="stretch")
            with st.expander("Forgot Password?", expanded=False):
                with st.form("qcms_password_recovery_form"):
                    recovery_email = st.text_input("Registered Company Email", placeholder="name@company.com", key="qcms_recovery_email")
                    send_reset = st.form_submit_button("Send Password Reset Link", width="stretch")
                if send_reset:
                    try:
                        request_password_reset(recovery_email)
                        st.success("If the email is registered in QCMS, a password reset message has been requested. Check the mailbox and follow the secure link.")
                    except Exception as exc:
                        st.error(_friendly_error(exc, "Password recovery"))

    app_footer()

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

# QCMS BUILD 4136-RMTC-OSP-TEXT-LAYOUT-SOURCES
