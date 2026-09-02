from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from core.permissions import is_admin
from core.repository import Repository

MODULES = (
    ("PART_MASTER", "Part Master"),
    ("MATERIAL_GRADE", "Material Grade"),
    ("REFERENCE_MASTERS", "Reference Masters"),
    ("EMPLOYEE_MASTER", "Employee Master"),
    ("RMTC_ENTRY", "RMTC Entry"),
    ("MATERIAL_INWARD", "Material Inward"),
    ("OSP_TRANSACTIONS", "OSP Transactions"),
    ("INSPECTION_LAYOUTS", "Inspection Layouts"),
    ("DIMENSIONAL_REPORT", "Dimensional Report"),
    ("METLAB_REPORT", "MetLAB Report"),
    ("NPD_APQP", "NPD & APQP"),
    ("QC_CALCULATION_TOOLS", "QC Calculation Tools"),
    ("COMPLAINT_MANAGEMENT", "Complaint Management"),
    ("CALIBRATION_VALIDATION", "Calibration & Validation"),
    ("SUPPLY_CHAIN", "Supply Chain"),
    ("USER_ACCESS", "Users & Access"),
)

_PERMISSION_KEYS = ("can_view", "can_create", "can_edit", "can_archive", "can_validate", "can_approve")


def _profile_department(profile: Mapping[str, Any] | None, repository: Repository) -> str:
    """Resolve department from the linked Employee Master without modifying employee email."""
    value = str((profile or {}).get("department") or "").strip()
    if value:
        return value
    pid = str((profile or {}).get("id") or "").strip()
    email = str((profile or {}).get("email") or "").strip().casefold()
    try:
        rows = repository.select("employees", eq={"status": "ACTIVE"}, limit=5000)
    except Exception:
        return ""
    for row in rows:
        if pid and str(row.get("profile_id") or "") == pid:
            return str(row.get("department") or "").strip()
    # Email fallback is read-only and exists only for older unlinked records.
    for row in rows:
        if email and str(row.get("email") or "").strip().casefold() == email:
            return str(row.get("department") or "").strip()
    return ""


def _permission_row(row: Mapping[str, Any], *, archive_default: bool = False) -> dict[str, bool]:
    return {
        "can_view": bool(row.get("can_view")),
        "can_create": bool(row.get("can_create")),
        "can_edit": bool(row.get("can_edit")),
        "can_archive": bool(row.get("can_archive", archive_default)),
        "can_validate": bool(row.get("can_validate")),
        "can_approve": bool(row.get("can_approve")),
    }


def _legacy_role_permissions(profile: Mapping[str, Any] | None, module_key: str) -> dict[str, bool]:
    role = str((profile or {}).get("role") or "VIEWER").upper().replace(" ", "_")
    if role in {"VIEWER", "AUDITOR"}:
        return {key: key == "can_view" for key in _PERMISSION_KEYS}
    supply_roles = {"SUPPLY_CHAIN", "PROCUREMENT", "PRODUCTION", "MANAGEMENT"}
    quality_roles = {"QUALITY_MANAGER", "QUALITY_ENGINEER", "METLAB_APPROVER", "SQA"}
    if module_key == "SUPPLY_CHAIN":
        write = role in supply_roles | {"QUALITY_MANAGER", "MASTER_DATA"}
    elif module_key in {"RMTC_ENTRY", "MATERIAL_INWARD", "DIMENSIONAL_REPORT", "METLAB_REPORT", "OSP_TRANSACTIONS"}:
        write = role in quality_roles | {"PRODUCTION", "MANAGEMENT"}
    elif module_key == "NPD_APQP":
        write = role in quality_roles | {"PRODUCTION", "BUSINESS_DEVELOPMENT", "MANAGEMENT", "MASTER_DATA"}
    elif module_key == "CALIBRATION_VALIDATION":
        write = role in quality_roles | {"MANAGEMENT", "MASTER_DATA"}
    else:
        write = role in quality_roles | {"MASTER_DATA", "MANAGEMENT"}
    validate = role in {"QUALITY_MANAGER", "QUALITY_ENGINEER", "METLAB_APPROVER", "SQA", "SUPPLY_CHAIN", "PROCUREMENT", "MANAGEMENT"}
    if module_key == "DIMENSIONAL_REPORT":
        approve = role in {"QUALITY_MANAGER", "QUALITY_ENGINEER", "SQA", "MANAGEMENT"}
    elif module_key == "METLAB_REPORT":
        approve = role in {"QUALITY_MANAGER", "METLAB_APPROVER", "MANAGEMENT"}
    else:
        approve = role == "MANAGEMENT"
    return {
        "can_view": True,
        "can_create": write,
        "can_edit": write,
        "can_archive": False,
        "can_validate": validate,
        "can_approve": approve,
    }


def module_permissions_with_source(
    profile: Mapping[str, Any] | None,
    module_key: str,
    repo: Repository | None = None,
) -> tuple[dict[str, bool], str]:
    """Return effective module rights and the source that granted/denied them.

    Compatibility contract: explicit User Module Permission row is authoritative.

    v4.14.18 precedence is shared with Supabase:
    ADMIN → explicit User override → Role defaults → Department defaults → legacy fallback.
    """
    if is_admin(profile):
        return ({key: True for key in _PERMISSION_KEYS}, "ADMIN")
    repository = repo or Repository()
    module_key = str(module_key or "").upper()
    pid = str((profile or {}).get("id") or "")

    try:
        rows = repository.select("user_module_permissions", eq={"profile_id": pid, "module_key": module_key}, limit=1)
    except Exception:
        rows = []
    if rows:
        return _permission_row(rows[0]), "USER OVERRIDE"

    role = str((profile or {}).get("role") or "VIEWER").upper().replace(" ", "_")
    try:
        role_rows = repository.select(
            "role_module_defaults",
            eq={"role": role, "module_key": module_key, "status": "ACTIVE"},
            limit=1,
        )
    except Exception:
        role_rows = []
    if role_rows:
        return _permission_row(role_rows[0]), f"ROLE · {role.replace('_', ' ')}"

    department = _profile_department(profile, repository)
    if department:
        try:
            defaults = repository.select(
                "department_module_defaults",
                eq={"department": department, "module_key": module_key, "status": "ACTIVE"},
                limit=1,
            )
        except Exception:
            defaults = []
        if defaults:
            return _permission_row(defaults[0]), f"DEPARTMENT · {department}"

    return _legacy_role_permissions(profile, module_key), f"LEGACY ROLE · {role.replace('_', ' ')}"


def module_permissions(profile: Mapping[str, Any] | None, module_key: str, repo: Repository | None = None) -> dict[str, bool]:
    permissions, _ = module_permissions_with_source(profile, module_key, repo)
    return permissions


def section_permissions(
    profile: Mapping[str, Any] | None,
    module_key: str,
    section_key: str,
    repo: Repository | None = None,
) -> dict[str, bool]:
    """Section override. No row means inherit module rights and remain visible by default."""
    repository = repo or Repository()
    module = module_permissions(profile, module_key, repository)
    if is_admin(profile):
        return {"can_view": True, "can_create": True, "can_edit": True}
    pid = str((profile or {}).get("id") or "")
    try:
        rows = repository.select(
            "user_section_permissions",
            eq={"profile_id": pid, "module_key": str(module_key).upper(), "section_key": str(section_key).upper()},
            limit=1,
        )
    except Exception:
        rows = []
    if not rows:
        return {
            "can_view": bool(module.get("can_view")),
            "can_create": bool(module.get("can_create")),
            "can_edit": bool(module.get("can_edit")),
        }
    row = rows[0]
    can_view = bool(row.get("can_view")) and bool(module.get("can_view"))
    return {
        "can_view": can_view,
        "can_create": can_view and bool(row.get("can_create")) and bool(module.get("can_create")),
        "can_edit": can_view and bool(row.get("can_edit")) and bool(module.get("can_edit")),
    }


def current_permissions(module_key: str) -> dict[str, bool]:
    return module_permissions(st.session_state.get("profile") or {}, module_key)
