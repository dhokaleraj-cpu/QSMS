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
    ("USER_ACCESS", "Users & Access"),
)


def module_permissions(profile: Mapping[str, Any] | None, module_key: str, repo: Repository | None = None) -> dict[str, bool]:
    if is_admin(profile):
        return {"can_view": True, "can_create": True, "can_edit": True, "can_archive": True, "can_approve": True}
    repository = repo or Repository()
    rows = repository.select(
        "user_module_permissions",
        eq={"profile_id": str((profile or {}).get("id") or ""), "module_key": module_key},
        limit=1,
    )
    if not rows:
        role = str((profile or {}).get("role") or "VIEWER").upper()
        default_write = role in {"QUALITY_MANAGER", "MASTER_DATA", "METLAB_APPROVER"}
        inward_write = role in {"QUALITY_MANAGER", "QUALITY_ENGINEER", "SQA", "PRODUCTION"}
        npd_write = role in {"QUALITY_MANAGER", "QUALITY_ENGINEER", "MASTER_DATA", "SQA", "PRODUCTION"}
        qc_tools_write = role in {"QUALITY_MANAGER", "QUALITY_ENGINEER", "METLAB_APPROVER", "SQA"}
        write_allowed = qc_tools_write if module_key == "QC_CALCULATION_TOOLS" else (npd_write if module_key == "NPD_APQP" else (inward_write if module_key in {"MATERIAL_INWARD", "OSP_TRANSACTIONS", "DIMENSIONAL_REPORT"} else default_write))
        return {
            "can_view": True,
            "can_create": write_allowed,
            "can_edit": write_allowed,
            "can_archive": False,
            "can_approve": role in {"QUALITY_MANAGER", "METLAB_APPROVER"},
        }
    row = rows[0]
    return {key: bool(row.get(key)) for key in ("can_view", "can_create", "can_edit", "can_archive", "can_approve")}


def current_permissions(module_key: str) -> dict[str, bool]:
    return module_permissions(st.session_state.get("profile") or {}, module_key)
