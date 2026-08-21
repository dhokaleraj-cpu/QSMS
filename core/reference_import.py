from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from core.master_service import MasterService


@dataclass
class ImportPreview:
    customer: dict[str, Any]
    suppliers: list[dict[str, Any]]
    material_grade: dict[str, Any]
    chemistry: list[dict[str, Any]]
    part: dict[str, Any]
    processes: list[dict[str, Any]]
    warnings: list[str]


def _cell(frame: pd.DataFrame, row: int, col: int) -> Any:
    try:
        value = frame.iat[row, col]
    except Exception:
        return None
    if pd.isna(value):
        return None
    return value


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
    return float(match.group()) if match else None


def _code_from_name(name: str, prefix: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", name.upper())[:8]
    return f"{prefix}-{cleaned or 'NEW'}"


def parse_reference_workbook(content: bytes) -> ImportPreview:
    sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None)
    required = {"Part Master", "Customer Master", "Vendor Supplier Master", "Material Grade Master", "Process Master"}
    missing = sorted(required.difference(sheets))
    if missing:
        raise ValueError(f"Missing expected worksheet(s): {', '.join(missing)}")

    customer_sheet = sheets["Customer Master"]
    supplier_sheet = sheets["Vendor Supplier Master"]
    material_sheet = sheets["Material Grade Master"]
    part_sheet = sheets["Part Master"]
    process_sheet = sheets["Process Master"]

    customer = {
        "party_code": _text(_cell(customer_sheet, 2, 4)).upper(),
        "party_name": _text(_cell(customer_sheet, 2, 2)),
        "party_types": ["CUSTOMER"],
        "address": _text(_cell(customer_sheet, 4, 2)),
        "country": _text(_cell(customer_sheet, 5, 2)),
        "approval_status": "APPROVED",
        "status": "ACTIVE",
        "remarks": "Imported from Customer Master worksheet.",
    }

    primary_supplier_name = _text(_cell(supplier_sheet, 2, 2))
    primary_supplier = {
        "party_code": _text(_cell(supplier_sheet, 2, 4)).upper(),
        "party_name": primary_supplier_name,
        "party_types": ["SUPPLIER"],
        "address": _text(_cell(supplier_sheet, 4, 2)),
        "country": _text(_cell(supplier_sheet, 5, 2)),
        "approval_status": "APPROVED",
        "status": "ACTIVE",
        "remarks": f"Supplier type: {_text(_cell(supplier_sheet, 4, 4))}. Imported from Vendor Supplier Master.",
    }

    grade_code = _text(_cell(material_sheet, 2, 2))
    material_grade = {
        "grade_code": grade_code,
        "standard": "",
        "revision": "Current",
        "status": "ACTIVE",
        "remarks": "Imported from Material Grade Master worksheet.",
    }
    chemistry: list[dict[str, Any]] = []
    for row in range(5, len(material_sheet.index)):
        element = _text(_cell(material_sheet, row, 1)).replace("%", "")
        if not element:
            continue
        chemistry.append({
            "element": element,
            "minimum": _number(_cell(material_sheet, row, 2)),
            "maximum": _number(_cell(material_sheet, row, 3)),
            "unit": "%",
            "test_method": "",
        })

    part_number = _text(_cell(part_sheet, 2, 2))
    part_name = _text(_cell(part_sheet, 2, 4))
    part_grade = _text(_cell(part_sheet, 5, 2))
    source_rows = []
    suppliers = [primary_supplier]
    for row in range(12, min(len(part_sheet.index), 20)):
        source_name = _text(_cell(part_sheet, row, 1))
        if not source_name:
            continue
        source_rows.append({
            "supplier_name": source_name,
            "forging_weight_kg": _number(_cell(part_sheet, row, 2)),
            "gross_weight_kg": _number(_cell(part_sheet, row, 3)),
            "section": _text(_cell(part_sheet, row, 4)),
            "forging_route": _text(_cell(part_sheet, row, 5)),
        })
        if source_name.casefold() != primary_supplier_name.casefold():
            suppliers.append({
                "party_code": _code_from_name(source_name, "SUP"),
                "party_name": source_name,
                "party_types": ["SUPPLIER"],
                "approval_status": "PENDING",
                "status": "ACTIVE",
                "remarks": "Alternate forging source found in Part Master; complete supplier approval details before use.",
            })

    special_characteristics: list[dict[str, Any]] = []
    positions = [_text(_cell(part_sheet, 17, col)) for col in (1, 2, 3)]
    requirements = [_text(_cell(part_sheet, 18, col)) for col in (1, 2, 3)]
    for position, requirement in zip(positions, requirements):
        if position or requirement:
            special_characteristics.append({"type": "JOMINY", "position": position, "requirement": requirement})
    if _text(_cell(part_sheet, 21, 2)):
        special_characteristics.append({
            "type": "HEAT_TREATMENT",
            "process": _text(_cell(part_sheet, 21, 2)),
            "case_depth": _text(_cell(part_sheet, 22, 2)),
            "core_requirement": _text(_cell(part_sheet, 23, 2)),
        })

    first_source = source_rows[0] if source_rows else {}
    part = {
        "part_number": part_number,
        "part_name": part_name,
        "material_grade": part_grade,
        "finished_weight_kg": _number(_cell(part_sheet, 4, 2)),
        "forging_weight_kg": first_source.get("forging_weight_kg"),
        "gross_weight_kg": first_source.get("gross_weight_kg"),
        "section_size": first_source.get("section"),
        "manufacturing_route": "",
        "special_characteristics": special_characteristics,
        "status": "ACTIVE",
        "remarks": "Imported from Part Master. Source details: " + "; ".join(
            f"{row['supplier_name']} | forging {row['forging_weight_kg']} kg | gross {row['gross_weight_kg']} kg | {row['section']} | {row['forging_route']}"
            for row in source_rows
        ),
    }

    processes: list[dict[str, Any]] = []
    for row in range(2, len(process_sheet.index)):
        name = _text(_cell(process_sheet, row, 2))
        if not name:
            continue
        normalized = name.casefold()
        outsourced = any(token in normalized for token in ("carbur", "qt", "temper", "nitrid", "gear shap"))
        special = any(token in normalized for token in ("carbur", "qt", "temper", "nitrid"))
        processes.append({
            "process_code": _code_from_name(name, "P"),
            "process_name": name,
            "process_type": "OUTSOURCED" if outsourced else "IN_HOUSE",
            "special_process": special,
            "cqi_standard": "CQI-9" if special else "",
            "status": "ACTIVE",
            "remarks": "Imported from Process Master worksheet.",
        })

    warnings = [
        "Drawing cells contain attachment placeholders only; no drawing file is embedded in the uploaded master workbook.",
        "Steel-mill approval is not present in the workbook and must be completed before RMTC approval.",
        "Alternate forging-source weights and routes are preserved in Part remarks because the current controlled schema stores one primary weight set per part.",
    ]
    if part_grade and part_grade.casefold() != grade_code.casefold():
        warnings.append(f"Part Master uses {part_grade}, while Material Grade Master defines {grade_code}; both grades will be retained separately.")

    return ImportPreview(customer, suppliers, material_grade, chemistry, part, processes, warnings)


def apply_reference_import(preview: ImportPreview, service: "MasterService") -> dict[str, int]:
    """Duplicate-safe reference import: create missing keys only, never update existing records."""
    result = {"created": 0, "updated": 0, "skipped": 0}

    def insert_party_if_missing(payload: dict[str, Any]) -> dict[str, Any]:
        existing = service.repo.find_one("parties", eq={"party_code": payload["party_code"]})
        if existing:
            result["skipped"] += 1
            return existing
        result["created"] += 1
        return service.repo.insert("parties", payload)

    customer = insert_party_if_missing(dict(preview.customer))

    supplier_rows: list[dict[str, Any]] = []
    for payload in preview.suppliers:
        supplier_rows.append(insert_party_if_missing(dict(payload)))

    grade = service.repo.find_one(
        "material_grades",
        eq={"grade_code": preview.material_grade["grade_code"], "revision": preview.material_grade.get("revision")},
    )
    if grade:
        result["skipped"] += 1
    else:
        grade = service.repo.insert("material_grades", preview.material_grade)
        result["created"] += 1

    part_source = dict(preview.part)
    part_grade_code = str(part_source.pop("material_grade", "") or "")
    part_grade = service.repo.find_one("material_grades", eq={"grade_code": part_grade_code}) if part_grade_code else None
    if not part_grade and part_grade_code:
        part_grade = service.repo.insert(
            "material_grades",
            {"grade_code": part_grade_code, "revision": "Current", "status": "ACTIVE", "remarks": "Created from Part Master material grade."},
        )
        result["created"] += 1

    for chemistry in preview.chemistry:
        natural = {"material_grade_id": grade["id"], "element": chemistry["element"]}
        if service.repo.find_one("material_grade_elements", eq=natural):
            result["skipped"] += 1
            continue
        service.repo.insert("material_grade_elements", {**chemistry, "material_grade_id": grade["id"]})
        result["created"] += 1

    part_payload = {
        **part_source,
        "customer_id": customer["id"],
        "material_grade_id": (part_grade or grade)["id"],
    }
    part = service.repo.find_one("parts", eq={"part_number": part_payload["part_number"]})
    if part:
        result["skipped"] += 1
    else:
        part = service.repo.insert("parts", part_payload)
        result["created"] += 1

    for supplier in supplier_rows:
        natural = {"part_id": part["id"], "supplier_id": supplier["id"], "steel_mill_id": None}
        if service.repo.find_one("part_supplier_links", eq=natural):
            result["skipped"] += 1
            continue
        service.repo.insert(
            "part_supplier_links",
            {
                "part_id": part["id"],
                "supplier_id": supplier["id"],
                "steel_mill_id": None,
                "supplier_part_number": part["part_number"],
                "approval_reference": "Imported source; steel mill approval pending",
                "approved": False,
            },
        )
        result["created"] += 1

    for process in preview.processes:
        if service.repo.find_one("processes", eq={"process_code": process["process_code"]}):
            result["skipped"] += 1
            continue
        service.repo.insert("processes", process)
        result["created"] += 1

    service._lookup_cache.clear()
    return result

