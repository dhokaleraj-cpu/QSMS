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
    ("SUPPLY_CHAIN", "Supply Chain"),
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
        department = str((profile or {}).get("department") or "").upper().replace(" ", "_")
        management = role == "MANAGEMENT" or department == "MANAGEMENT"
        supply_function = role in {"SUPPLY_CHAIN", "PROCUREMENT", "BUSINESS_DEVELOPMENT", "MANAGEMENT"} or department in {"SUPPLY_CHAIN", "SUPPLYCHAIN", "PROCUREMENT", "BUSINESS_DEVELOPMENT", "MANAGEMENT"}
        default_write = role in {"QUALITY_MANAGER", "MASTER_DATA", "METLAB_APPROVER", "PROCUREMENT", "MANAGEMENT"} or management
        inward_write = role in {"QUALITY_MANAGER", "QUALITY_ENGINEER", "SQA", "PRODUCTION", "SUPPLY_CHAIN", "PROCUREMENT", "MANAGEMENT"} or department in {"SUPPLY_CHAIN", "SUPPLYCHAIN", "PROCUREMENT", "MANAGEMENT"}
        npd_write = role in {"QUALITY_MANAGER", "QUALITY_ENGINEER", "MASTER_DATA", "SQA", "PRODUCTION", "BUSINESS_DEVELOPMENT", "MANAGEMENT"} or department in {"BUSINESS_DEVELOPMENT", "MANAGEMENT"}
        qc_tools_write = role in {"QUALITY_MANAGER", "QUALITY_ENGINEER", "METLAB_APPROVER", "SQA", "MANAGEMENT"}
        complaint_write = role in {"QUALITY_MANAGER", "QUALITY_ENGINEER", "SQA", "PRODUCTION", "BUSINESS_DEVELOPMENT", "MANAGEMENT"}
        supply_write = role in {"QUALITY_MANAGER", "QUALITY_ENGINEER", "MASTER_DATA", "SQA", "PRODUCTION"} or supply_function
        write_allowed = supply_write if module_key == "SUPPLY_CHAIN" else (complaint_write if module_key == "COMPLAINT_MANAGEMENT" else (qc_tools_write if module_key == "QC_CALCULATION_TOOLS" else (npd_write if module_key == "NPD_APQP" else (inward_write if module_key in {"MATERIAL_INWARD", "OSP_TRANSACTIONS", "DIMENSIONAL_REPORT"} else default_write))))
        return {
            "can_view": True,
            "can_create": write_allowed,
            "can_edit": write_allowed,
            "can_archive": False,
            "can_approve": role in {"QUALITY_MANAGER", "METLAB_APPROVER", "MANAGEMENT"},
        }
    row = rows[0]
    return {key: bool(row.get(key)) for key in ("can_view", "can_create", "can_edit", "can_archive", "can_approve")}


def current_permissions(module_key: str) -> dict[str, bool]:
    return module_permissions(st.session_state.get("profile") or {}, module_key)
