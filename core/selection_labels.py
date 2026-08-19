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


def reference_record_label(definition: Any, row: Mapping[str, Any], lookup_maps: Mapping[str, Mapping[str, str]] | None = None) -> str:
    """Detailed Reference Master selector label.

    Keeps the controlled code first, then adds the human-readable name or
    description and useful context. Lookup fields are resolved to their rich
    master labels so selectors never force users to interpret UUIDs.
    """
    lookup_maps = lookup_maps or {}
    fields = {field.name: field for field in definition.fields}
    ordered: list[str] = []
    for name in (
        definition.auto_code_field,
        *definition.natural_key,
        *definition.columns,
        "party_name", "stage_name", "asset_name", "description",
        "approval_reference", "address", "remarks",
    ):
        if name and name not in ordered:
            ordered.append(name)

    pieces: list[str] = []
    seen_values: set[str] = set()
    for name in ordered:
        raw = row.get(name)
        if raw in (None, "", [], {}):
            continue
        field = fields.get(name)
        if field and field.lookup:
            value = lookup_maps.get(field.lookup, {}).get(str(raw), str(raw))
        elif isinstance(raw, bool):
            value = "Yes" if raw else "No"
        elif isinstance(raw, (list, tuple, set)):
            value = ", ".join(str(item) for item in raw if str(item).strip())
        else:
            value = str(raw)
        value = " ".join(value.split())
        if not value:
            continue
        if len(value) > 90:
            value = value[:87].rstrip() + "..."
        signature = value.casefold()
        if signature in seen_values:
            continue
        seen_values.add(signature)

        is_code = name == definition.auto_code_field or name in definition.natural_key or name.endswith("_code")
        is_name = name.endswith("_name") or name in {"party_name", "stage_name", "asset_name", "description"}
        if is_code or is_name:
            piece = value
        else:
            label = field.label if field else name.replace("_", " ").title()
            piece = f"{label}: {value}"
        pieces.append(piece)
        if len(pieces) >= 7:
            break
    return " · ".join(pieces) or str(row.get("id"))
