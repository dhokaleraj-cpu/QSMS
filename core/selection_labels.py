from __future__ import annotations

from typing import Any, Mapping


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _join(*values: Any) -> str:
    return " · ".join(value for value in (_clean(v) for v in values) if value)


def party_label(row: Mapping[str, Any], *, include_type: bool = False) -> str:
    location = ", ".join(value for value in (_clean(row.get("city")), _clean(row.get("state")), _clean(row.get("country"))) if value)
    approval = _clean(row.get("approval_status"))
    party_types = ", ".join(str(v) for v in (row.get("party_types") or [])) if include_type else ""
    return _join(row.get("party_code"), row.get("party_name"), location, approval, party_types)


def customer_label(row: Mapping[str, Any]) -> str:
    return party_label(row)


def supplier_label(row: Mapping[str, Any]) -> str:
    return party_label(row)


def steel_mill_label(row: Mapping[str, Any]) -> str:
    return party_label(row)


def process_label(row: Mapping[str, Any]) -> str:
    process_type = _clean(row.get("process_type")).replace("_", " ").title()
    special = "Special Process" if bool(row.get("special_process")) else ""
    cqi = _clean(row.get("cqi_standard"))
    return _join(row.get("process_code"), row.get("process_name"), process_type, special, cqi)


def part_label(row: Mapping[str, Any], *, customer_name: str = "", grade_code: str = "") -> str:
    drawing = _join(row.get("drawing_number"), f"Rev {_clean(row.get('drawing_revision'))}" if _clean(row.get("drawing_revision")) else "")
    return _join(row.get("part_number"), row.get("part_name"), customer_name, grade_code, drawing)


def material_grade_label(row: Mapping[str, Any]) -> str:
    revision = f"Rev {_clean(row.get('revision'))}" if _clean(row.get("revision")) else ""
    return _join(row.get("material_number"), row.get("grade_code"), row.get("standard"), revision)


def employee_label(row: Mapping[str, Any]) -> str:
    name = " ".join(value for value in (_clean(row.get("first_name")), _clean(row.get("last_name"))) if value)
    return _join(row.get("employee_code"), name, row.get("designation"), row.get("department"), row.get("plant"))


def inspection_stage_label(row: Mapping[str, Any]) -> str:
    return _join(row.get("stage_code"), row.get("stage_name"), f"Seq {row.get('sequence_no')}" if row.get("sequence_no") is not None else "")


def quality_asset_label(row: Mapping[str, Any]) -> str:
    return _join(row.get("asset_code"), row.get("asset_name"), row.get("asset_type"), row.get("serial_number"), row.get("location"))


def inspection_plan_label(row: Mapping[str, Any]) -> str:
    revision = f"Rev {_clean(row.get('revision'))}" if _clean(row.get("revision")) else ""
    return _join(row.get("plan_number"), revision, row.get("sample_plan"), row.get("status"))


def customer_standard_label(
    row: Mapping[str, Any],
    *,
    customer_name: str = "",
    process_name: str = "",
) -> str:
    revision = f"Rev {_clean(row.get('revision_number'))}" if _clean(row.get("revision_number")) else ""
    return _join(row.get("standard_code"), row.get("standard_name"), revision, process_name, customer_name)
