"""R35 · STAWN QCMS licensing, company profile, STAWN developer console, in-app notifications and WhatsApp.

All checks run in the database (security definer RPCs, see
supabase/migrations/20261021120000_qcms_r35_notifications_licensing.sql). This module only wraps them for
the website. Nothing here holds a secret: the licence signing secret stays in public.qcms_licence_secret
(no API access) and the WhatsApp / APNs / FCM tokens are Edge Function secrets.
"""
from __future__ import annotations

import time
from typing import Any, Mapping

import streamlit as st

from core.database import get_session_client
from core.repository import Repository

PRODUCT = "STAWN QCMS"
DEVELOPER_NAME = "STAWN PRECISION PRIVATE LIMITED"
LOGO_BUCKET = "quality-documents"
STATUS_CACHE_KEY = "_qcms_r35_licence_status"
STATUS_TTL_SECONDS = 600
UNREAD_CACHE_KEY = "_qcms_r35_unread_count"
UNREAD_TTL_SECONDS = 45

COMPANY_FIELDS = (
    ("legal_name", "Registered company name *"),
    ("display_name", "Short name shown in the app"),
    ("address_line1", "Address line 1 *"),
    ("address_line2", "Address line 2"),
    ("city", "City *"),
    ("state", "State *"),
    ("country", "Country"),
    ("pincode", "PIN code"),
    ("gstin", "GSTIN"),
    ("pan", "PAN"),
    ("cin", "CIN"),
    ("contact_person", "Contact person *"),
    ("contact_email", "Contact e-mail *"),
    ("contact_phone", "Contact phone *"),
    ("website", "Website"),
    ("industry", "Industry"),
)
REQUIRED_COMPANY_FIELDS = ("legal_name", "address_line1", "city", "state", "contact_person", "contact_email", "contact_phone")

CATEGORY_ICON = {"APPROVAL": "✅", "TASK": "📌", "UPDATE": "🔔", "INFO": "ℹ️", "ALERT": "⚠️"}


def _repo() -> Repository:
    return Repository()


def _rpc(name: str, params: Mapping[str, Any] | None = None) -> Any:
    return _repo().rpc(name, dict(params or {}))


# ---------------------------------------------------------------- licence
def licence_status(*, force: bool = False) -> dict:
    """Online licence check (cached 10 minutes per session). Never raises."""
    cached = st.session_state.get(STATUS_CACHE_KEY)
    if not force and isinstance(cached, dict) and time.time() - float(cached.get("_at", 0)) < STATUS_TTL_SECONDS:
        return dict(cached.get("data") or {})
    try:
        data = _rpc("qcms_licence_status") or {}
        if isinstance(data, list):
            data = data[0] if data else {}
        data = dict(data or {})
    except Exception as exc:  # licence RPC not installed yet / offline / preview
        data = {"valid": True, "status": "UNCHECKED", "reason": f"Licence check unavailable: {exc}", "product": PRODUCT,
                "unchecked": True}
    st.session_state[STATUS_CACHE_KEY] = {"_at": time.time(), "data": data}
    return data


def clear_cache() -> None:
    for key in (STATUS_CACHE_KEY, UNREAD_CACHE_KEY):
        st.session_state.pop(key, None)


def licence_blocks_use(status: Mapping[str, Any]) -> bool:
    """True when the company has a licence record that is not valid. A missing RPC never blocks."""
    if status.get("unchecked") or status.get("is_stawn_developer"):
        return False
    return not bool(status.get("valid", True)) and str(status.get("status") or "") not in {"", "UNCHECKED"}


def validate_key(key: str) -> dict:
    return dict(_rpc("qcms_validate_licence", {"p_key": key}) or {})


def activate_key(key: str) -> dict:
    result = dict(_rpc("qcms_activate_licence", {"p_key": key}) or {})
    clear_cache()
    return result


# ---------------------------------------------------------------- company profile
def company_profile(tenant_id: str | None = None) -> dict:
    repo = _repo()
    tid = tenant_id or repo.tenant_id
    try:
        rows = repo.select("qcms_company_profiles", eq={"tenant_id": tid}, limit=1)
    except Exception:
        rows = []
    return dict(rows[0]) if rows else {"tenant_id": tid}


def missing_company_fields(profile: Mapping[str, Any]) -> list[str]:
    labels = dict(COMPANY_FIELDS)
    return [labels[f].rstrip(" *") for f in REQUIRED_COMPANY_FIELDS if not str(profile.get(f) or "").strip()]


def save_company_profile(values: Mapping[str, Any], *, complete: bool, profile_id: str | None = None) -> dict:
    repo = _repo()
    tid = str(values.get("tenant_id") or repo.tenant_id)
    payload = {k: (str(values.get(k) or "").strip() or None) for k, _ in COMPANY_FIELDS}
    if values.get("logo_path"):
        payload["logo_path"] = values["logo_path"]
    payload["updated_by"] = profile_id
    if complete:
        missing = missing_company_fields(payload)
        if missing:
            raise ValueError("Fill these company details before finishing the setup: " + ", ".join(missing))
        payload.update({"setup_complete": True, "completed_by": profile_id})
    client = get_session_client()
    if client is None:
        raise RuntimeError("A live QCMS session is required.")
    from datetime import datetime, timezone

    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    if complete:
        payload["completed_at"] = payload["updated_at"]
    existing = company_profile(tid)
    if existing.get("created_at"):
        res = client.table("qcms_company_profiles").update(payload).eq("tenant_id", tid).execute()
    else:
        res = client.table("qcms_company_profiles").insert({**payload, "tenant_id": tid}).execute()
    clear_cache()
    rows = getattr(res, "data", None) or []
    return dict(rows[0]) if rows else payload


def upload_company_logo(file: Any, tenant_id: str | None = None) -> str:
    client = get_session_client()
    if client is None:
        raise RuntimeError("A live QCMS session is required to upload the logo.")
    data = file.getvalue()
    if not data:
        raise ValueError("The selected logo file is empty.")
    if len(data) > 2 * 1024 * 1024:
        raise ValueError("Use a logo smaller than 2 MB (PNG or JPG).")
    tid = tenant_id or _repo().tenant_id
    ext = "png" if str(getattr(file, "type", "")).endswith("png") else "jpg"
    path = f"{tid}/company_profile/company_logo.{ext}"
    client.storage.from_(LOGO_BUCKET).upload(path, data, {"content-type": getattr(file, "type", None) or "image/png", "upsert": "true"})
    return path


def company_logo_bytes(path: str | None) -> bytes | None:
    if not path:
        return None
    cache = st.session_state.setdefault("_qcms_r35_logo_cache", {})
    if path in cache:
        return cache[path]
    try:
        client = get_session_client()
        data = bytes(client.storage.from_(LOGO_BUCKET).download(path)) if client else None
    except Exception:
        data = None
    cache[path] = data
    return data


# ---------------------------------------------------------------- STAWN developer console
def dev_overview() -> list[dict]:
    return list(_rpc("qcms_dev_licence_overview") or [])


def dev_issue_licence(tenant_id: str, plan: str, max_users: int, valid_to: Any, modules: list[str], notes: str) -> dict:
    return dict(_rpc("qcms_dev_issue_licence", {
        "p_tenant_id": tenant_id, "p_plan": plan, "p_max_users": int(max_users),
        "p_valid_to": valid_to.isoformat() if valid_to else None, "p_modules": modules or ["ALL"], "p_notes": notes or None,
    }) or {})


def dev_update_licence(licence_id: str, *, status: str | None = None, max_users: int | None = None, valid_to: Any = None,
                       clear_valid_to: bool = False, plan: str | None = None) -> dict:
    return dict(_rpc("qcms_dev_update_licence", {
        "p_licence_id": licence_id, "p_status": status, "p_max_users": max_users,
        "p_valid_to": valid_to.isoformat() if valid_to else None, "p_clear_valid_to": bool(clear_valid_to), "p_plan": plan,
    }) or {})


def dev_create_company(code: str, name: str, plant_code: str = "") -> str:
    return str(_rpc("qcms_dev_create_company", {"p_tenant_code": code, "p_tenant_name": name, "p_plant_code": plant_code or None}) or "")


def dev_assign_profile(email: str, tenant_id: str, role: str = "ADMIN") -> dict:
    return dict(_rpc("qcms_dev_assign_profile", {"p_email": email, "p_tenant_id": tenant_id, "p_role": role}) or {})


# ---------------------------------------------------------------- notifications
def unread_count(*, force: bool = False) -> int:
    cached = st.session_state.get(UNREAD_CACHE_KEY)
    if not force and isinstance(cached, dict) and time.time() - float(cached.get("_at", 0)) < UNREAD_TTL_SECONDS:
        return int(cached.get("n") or 0)
    try:
        n = int(_rpc("qcms_unread_notification_count") or 0)
    except Exception:
        n = 0
    st.session_state[UNREAD_CACHE_KEY] = {"_at": time.time(), "n": n}
    return n


def my_notifications(limit: int = 100, unread_only: bool = False) -> list[dict]:
    return list(_rpc("qcms_my_notifications", {"p_limit": int(limit), "p_unread_only": bool(unread_only)}) or [])


def mark_read(ids: list[str] | None = None) -> int:
    n = int(_rpc("qcms_mark_notifications_read", {"p_ids": ids}) or 0)
    st.session_state.pop(UNREAD_CACHE_KEY, None)
    return n


def send_notification(*, profile_id: str | None, employee_id: str | None, title: str, body: str, category: str = "UPDATE",
                      module_key: str | None = None, web_route: str | None = None) -> Any:
    return _rpc("qcms_notify", {
        "p_recipient_profile_id": profile_id, "p_recipient_employee_id": employee_id, "p_title": title, "p_body": body,
        "p_category": category, "p_module_key": module_key, "p_related_table": None, "p_related_id": None, "p_web_route": web_route,
    })


# ---------------------------------------------------------------- WhatsApp
WHATSAPP_FIELDS = ("enabled", "phone_number_id", "business_account_id", "api_version", "approval_template", "task_template",
                   "update_template", "template_language", "send_categories", "default_country_code", "app_link")


def whatsapp_settings() -> dict:
    repo = _repo()
    try:
        rows = repo.select("qcms_whatsapp_settings", eq={"tenant_id": repo.tenant_id}, limit=1)
    except Exception:
        rows = []
    return dict(rows[0]) if rows else {}


def save_whatsapp_settings(values: Mapping[str, Any], profile_id: str | None = None) -> None:
    client = get_session_client()
    if client is None:
        raise RuntimeError("A live QCMS session is required.")
    repo = _repo()
    payload = {k: values.get(k) for k in WHATSAPP_FIELDS if k in values}
    payload["updated_by"] = profile_id
    if whatsapp_settings():
        client.table("qcms_whatsapp_settings").update(payload).eq("tenant_id", repo.tenant_id).execute()
    else:
        client.table("qcms_whatsapp_settings").insert({**payload, "tenant_id": repo.tenant_id}).execute()


def set_my_whatsapp(opt_in: bool, mobile: str | None) -> dict:
    return dict(_rpc("qcms_set_my_whatsapp", {"p_opt_in": bool(opt_in), "p_mobile_number": mobile or None}) or {})


def whatsapp_test(to: str, template: str = "hello_world") -> dict:
    client = get_session_client()
    if client is None:
        raise RuntimeError("A live QCMS session is required.")
    res = client.functions.invoke("qcms-whatsapp-dispatch", invoke_options={"body": {"action": "test", "to": to, "template": template}})
    import json

    raw = res if isinstance(res, (bytes, str)) else getattr(res, "data", res)
    try:
        return json.loads(raw) if isinstance(raw, (bytes, str)) else dict(raw or {})
    except Exception:
        return {"ok": False, "error": str(raw)[:300]}
