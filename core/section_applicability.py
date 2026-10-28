"""QCMS R38 · "Sections applicable" for RMTC reports (built on the Part Master control in ``core.part_sections``).

Part level  : ``parts.section_applicability`` (jsonb, owned by ``core.part_sections``; missing key = applicable).
RMTC level  : ``rmtc_approvals.applicable_sections`` (jsonb, NULL = not chosen yet -> defaults from the covered Parts).

An RMTC section is applicable by default when it is applicable for at least one covered Part (a Part section that is
Not Applicable for EVERY covered Part defaults to Not Applicable). The user can tick / untick per RMTC. A Not Applicable
RMTC section is hidden in the Part Worksheet, saved as NOT_APPLICABLE rows (so the server validation skips it) and
omitted from the RMTC print PDF.

Public contract::

    RMTC_SECTIONS                      ordered (key, label, print_title, description)
    RMTC_SECTION_KEYS / RMTC_SECTION_LABELS
    normalize_rmtc_sections(value)            -> dict[key, bool]   (None / {} / bad -> all True)
    default_rmtc_sections(part_rows)          -> dict[key, bool]   (from the covered Parts' applicability: jsonb
                                                                     section_applicability and/or text[] applicable_sections)
    part_values(part_row) / section_key(label)
    rmtc_sections(record, part_rows=None)     -> dict[key, bool]   (stored choice, else Part defaults)
    stored_rmtc_sections(mapping)             -> value for rmtc_approvals.applicable_sections
    rmtc_not_applicable_labels(mapping)       -> list[str]
    is_mechanical_requirement(name)           -> bool (same tokens as the RMTC print split)
    requirement_applicable(name, mapping)     -> bool (mechanical -> 'mechanical', else 'heat_treatment')
    na_chemistry_rows / na_jominy_rows / na_requirement_rows   NOT_APPLICABLE rows for a skipped worksheet section
    metlab_group_applicable(part_row, group)  -> bool  (MetLAB hook: 'osp_metlab' / 'final_metallurgical' / 'jominy' / 'chemistry')
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Sequence

from core.part_sections import applicable_from_row

# key, user label, RMTC print section title, description
RMTC_SECTIONS: tuple[tuple[str, str, str, str], ...] = (
    ("heat_balance", "Global Heat Quantity Balance & Record List", "GLOBAL HEAT QUANTITY BALANCE & RECORD LIST",
     "Heat steel balance and the RMTC records of the same Heat."),
    ("supplier_mechanical", "Supplier RMTC Mechanical Properties", "SUPPLIER RMTC MECHANICAL PROPERTIES",
     "Mechanical values reported on the supplier certificate."),
    ("chemistry", "Chemical Composition", "Chemical Composition", "Part Worksheet C - chemistry against the grade limits."),
    ("jominy", "Jominy Results", "Jominy Results", "Part Worksheet D - actual / calculated Jominy."),
    ("di_value", "DI / Hardenability", "DI / Hardenability", "Part Worksheet E - actual / calculated DI, grain size."),
    ("mechanical", "Mechanical Properties (Part requirements)", "Mechanical Properties",
     "Tensile / yield / elongation / impact rows of the Part requirements."),
    ("heat_treatment", "Heat Treatment & Other Requirements", "Heat Treatment & Other Requirements",
     "Hardness, grain size, inclusion, microstructure, UT, macro-etch and other Part requirement rows."),
    ("microstructure", "Microstructure Photographs", "RMTC MICROSTRUCTURE PHOTOGRAPHS", "Three controlled microstructure photos."),
)
RMTC_SECTION_KEYS: tuple[str, ...] = tuple(row[0] for row in RMTC_SECTIONS)
RMTC_SECTION_LABELS: dict[str, str] = {row[0]: row[1] for row in RMTC_SECTIONS}
# RMTC keys that inherit their default from the same Part Master key (core.part_sections)
PART_DEFAULT_KEYS: tuple[str, ...] = ("chemistry", "jominy", "di_value", "heat_treatment", "microstructure")

MECHANICAL_TOKENS: tuple[str, ...] = ("tensile", "yield", "elongation", "reduction", "impact", "proof", "mechanical", "uts")

_TRUE = {"1", "true", "yes", "y", "on", "applicable", "t"}
_FALSE = {"0", "false", "no", "n", "off", "na", "n/a", "not applicable", "f"}


def _bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().casefold()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    return default


def _mapping(value: Any) -> Mapping[str, Any] | None:
    if value is None:
        return None
    data = value
    if isinstance(data, (bytes, str)):
        try:
            data = json.loads(data or "null")
        except (TypeError, ValueError):
            return None
    return data if isinstance(data, Mapping) else None


def normalize_rmtc_sections(value: Any) -> dict[str, bool]:
    data = _mapping(value) or {}
    return {key: _bool(data.get(key), True) for key in RMTC_SECTION_KEYS}


def stored_rmtc_sections(mapping: Mapping[str, Any]) -> dict[str, bool]:
    return normalize_rmtc_sections(mapping)


def default_rmtc_sections(part_rows: Iterable[Mapping[str, Any]] | None) -> dict[str, bool]:
    """All True, except a Part section that is Not Applicable for every covered Part."""
    result = {key: True for key in RMTC_SECTION_KEYS}
    rows = [row for row in (part_rows or []) if row]
    if not rows:
        return result
    per_part = [part_values(row) for row in rows]
    for key in PART_DEFAULT_KEYS:
        result[key] = any(values.get(key, True) for values in per_part)
    return result


def part_values(row: Mapping[str, Any]) -> dict[str, bool]:
    """Part-level applicability: ``parts.section_applicability`` (jsonb map) and, when present and non-empty,
    ``parts.applicable_sections`` (text[] of APPLICABLE keys / labels; a Part-default key missing from it = Not Applicable)."""
    values = dict(applicable_from_row(row))
    listed = row.get("applicable_sections")
    if isinstance(listed, str):
        try:
            listed = json.loads(listed)
        except (TypeError, ValueError):
            listed = [part.strip() for part in listed.strip("{}").split(",") if part.strip()]
    if isinstance(listed, (list, tuple, set)) and listed:
        wanted = {section_key(item) for item in listed}
        for key in PART_DEFAULT_KEYS:  # RMTC-only sections (heat balance, mechanical) stay applicable by default
            values[key] = key in wanted
    return values


_KEY_ALIASES = {
    "chemical": "chemistry", "chemicalcomposition": "chemistry", "chemicalanalysis": "chemistry",
    "jominyhardenability": "jominy", "hardenability": "di_value", "di": "di_value", "dihardenability": "di_value",
    "mechanicalproperties": "mechanical", "suppliermechanicalproperties": "supplier_mechanical",
    "heattreatment": "heat_treatment", "otherrequirements": "heat_treatment", "hardness": "heat_treatment",
    "grainsize": "heat_treatment", "inclusionrating": "heat_treatment", "ultrasonictest": "heat_treatment",
    "macroetch": "heat_treatment", "microstructurephotographs": "microstructure", "heatbalance": "heat_balance",
}


def section_key(value: Any) -> str:
    """RMTC section key from a key / label ("Chemical Composition" -> "chemistry")."""
    text = str(value or "").strip()
    if text in RMTC_SECTION_KEYS:
        return text
    for key, label, title, _ in RMTC_SECTIONS:
        if text.casefold() in (label.casefold(), title.casefold()):
            return key
    compact = "".join(ch for ch in text.casefold() if ch.isalnum())
    return _KEY_ALIASES.get(compact, compact)


def rmtc_sections(record: Mapping[str, Any] | None, part_rows: Iterable[Mapping[str, Any]] | None = None) -> dict[str, bool]:
    """Stored RMTC choice when present (NULL / {} = not chosen), else the defaults from the covered Parts."""
    stored = _mapping((record or {}).get("applicable_sections"))
    if stored:
        return normalize_rmtc_sections(stored)
    return default_rmtc_sections(part_rows)


def rmtc_not_applicable_labels(mapping: Mapping[str, Any] | None) -> list[str]:
    values = normalize_rmtc_sections(mapping or {})
    return [RMTC_SECTION_LABELS[key] for key in RMTC_SECTION_KEYS if not values[key]]


def is_mechanical_requirement(name: Any) -> bool:
    text = str(name or "").casefold()
    return any(token in text for token in MECHANICAL_TOKENS)


def requirement_applicable(name: Any, mapping: Mapping[str, Any] | None) -> bool:
    values = normalize_rmtc_sections(mapping or {})
    return values["mechanical"] if is_mechanical_requirement(name) else values["heat_treatment"]


# ----------------------------------------------------------------------------- NOT_APPLICABLE rows for skipped sections
def na_chemistry_rows(templates: Sequence[Mapping[str, Any]]) -> list[dict]:
    return [{
        "material_grade_element_id": t.get("id"), "element": t.get("element"), "minimum_value": t.get("minimum"),
        "maximum_value": t.get("maximum"), "actual_value": None, "unit": t.get("unit") or "%", "result": "NOT_APPLICABLE",
        "remarks": "Section not applicable for this RMTC",
    } for t in templates]


def na_jominy_rows(templates: Sequence[Mapping[str, Any]]) -> list[dict]:
    return [{
        "jominy_distance_id": t.get("jominy_distance_id"), "distance_label": t.get("distance_label"), "distance_mm": t.get("distance_mm"),
        "distance_16th": int(t.get("distance_16th") or 0), "minimum_hrc": t.get("minimum_hrc"), "maximum_hrc": t.get("maximum_hrc"),
        "actual_hrc": None, "applicability": "NOT_APPLICABLE", "remarks": "Section not applicable for this RMTC",
    } for t in templates]


def na_requirement_rows(templates: Sequence[Mapping[str, Any]], existing: Mapping[str, Mapping[str, Any]] | None = None) -> list[dict]:
    existing = existing or {}
    return [{
        "source_requirement_id": t.get("id"), "requirement_name": t.get("parameter_name"), "requirement_value": t.get("requirement_value"),
        "actual_value": (existing.get(str(t.get("id"))) or {}).get("actual_value"), "result": "NOT_APPLICABLE",
        "sequence_no": t.get("sequence_no"),
    } for t in templates]


def split_requirement_templates(templates: Sequence[Mapping[str, Any]], mapping: Mapping[str, Any] | None) -> tuple[list[dict], list[dict]]:
    """(shown, not_applicable) Part requirement templates for the RMTC worksheet."""
    shown, hidden = [], []
    for t in templates:
        (shown if requirement_applicable(t.get("parameter_name"), mapping) else hidden).append(dict(t))
    return shown, hidden


# ----------------------------------------------------------------------------- MetLAB / other report hook
def metlab_group_applicable(part_row: Mapping[str, Any] | None, group: str) -> bool:
    """True unless the Part marks the requirement group Not Applicable (unknown group -> True)."""
    values = applicable_from_row(part_row)
    return bool(values.get(str(group or ""), True))


__all__ = [
    "RMTC_SECTIONS", "RMTC_SECTION_KEYS", "RMTC_SECTION_LABELS", "PART_DEFAULT_KEYS", "MECHANICAL_TOKENS",
    "normalize_rmtc_sections", "stored_rmtc_sections", "default_rmtc_sections", "rmtc_sections", "rmtc_not_applicable_labels",
    "is_mechanical_requirement", "requirement_applicable", "na_chemistry_rows", "na_jominy_rows", "na_requirement_rows",
    "split_requirement_templates", "metlab_group_applicable",
]
