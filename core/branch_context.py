from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from core.config import get_settings
from core.repository import Repository


def branch_snapshot(row: Mapping[str, Any] | None) -> dict[str, Any]:
    r = dict(row or {})
    address_parts = [
        str(r.get("address_line1") or "").strip(),
        str(r.get("address_line2") or "").strip(),
        str(r.get("address_line3") or "").strip(),
    ]
    address_parts = [v for v in address_parts if v]
    locality = ", ".join(
        v for v in (
            str(r.get("city") or "").strip(),
            str(r.get("state") or "").strip(),
            str(r.get("postal_code") or "").strip(),
            str(r.get("country") or "").strip(),
        ) if v
    )
    address = ", ".join([*address_parts, locality] if locality else address_parts)
    return {
        "branch_id": r.get("id"),
        "branch_code": r.get("branch_code"),
        "plant_code": r.get("plant_code") or r.get("branch_code"),
        "name": r.get("branch_name") or r.get("branch_code"),
        "branch_name": r.get("branch_name") or r.get("branch_code"),
        "address1": r.get("address_line1"),
        "address2": r.get("address_line2"),
        "address3": r.get("address_line3"),
        "address": address,
        "city": r.get("city"),
        "state": r.get("state"),
        "postal_code": r.get("postal_code"),
        "country": r.get("country"),
        "tax_identifier": r.get("gstin"),
        "gstin": r.get("gstin"),
        "contact_person": r.get("contact_person"),
        "phone": r.get("phone"),
        "email": r.get("email"),
    }


def active_company_branches(repo: Repository | None = None) -> list[dict[str, Any]]:
    r = repo or Repository()
    try:
        return r.select("company_branches", eq={"status": "ACTIVE"}, order_by="branch_code", limit=500)
    except Exception:
        return []


def _employee_plant(repo: Repository, profile: Mapping[str, Any] | None = None) -> str:
    employee_id = str((profile or {}).get("employee_id") or "")
    try:
        if not employee_id:
            employee_id = str(repo.rpc("qcms_current_login_employee_id") or "")
        employee = repo.get("employees", employee_id) if employee_id else None
        return str((employee or {}).get("plant") or "").strip()
    except Exception:
        return ""


def resolve_current_branch(repo: Repository | None = None, profile: Mapping[str, Any] | None = None, *, refresh: bool = False) -> dict[str, Any]:
    """Resolve one reusable Company Branch for the current login.

    Employee Master ``plant`` is matched against Branch Code, Plant Code or Branch Name.
    If it does not match, the active default Company Branch is used. This context is
    available to every module and is used as the issuing branch on Purchase Orders.
    """
    cache_key = "_qcms_current_company_branch"
    if not refresh and isinstance(st.session_state.get(cache_key), dict):
        cached = dict(st.session_state[cache_key])
        if cached.get("id"):
            return cached
    r = repo or Repository()
    rows = active_company_branches(r)
    if rows:
        plant = _employee_plant(r, profile).casefold()
        if plant:
            for row in rows:
                values = {
                    str(row.get("branch_code") or "").strip().casefold(),
                    str(row.get("plant_code") or "").strip().casefold(),
                    str(row.get("branch_name") or "").strip().casefold(),
                }
                if plant in values:
                    st.session_state[cache_key] = dict(row)
                    return dict(row)
        default = next((row for row in rows if bool(row.get("is_default"))), rows[0])
        st.session_state[cache_key] = dict(default)
        return dict(default)
    settings = get_settings()
    fallback = {
        "id": None,
        "branch_code": settings.plant_code,
        "plant_code": settings.plant_code,
        "branch_name": f"{settings.company_name} · {settings.plant_code}",
        "status": "ACTIVE",
        "is_default": True,
    }
    return fallback


def branch_label(row: Mapping[str, Any] | None) -> str:
    r = dict(row or {})
    return f"{r.get('branch_code') or r.get('plant_code') or '-'} · {r.get('branch_name') or '-'}"
