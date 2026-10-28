"""QCMS R38 · per-Part "Sections applicable" control.

A Part may not need every Part Master grid / RMTC worksheet section (for example a bought-out bright-bar part has no
Jominy band, an in-house part has no OSP MetLAB inspection). The choice is stored on ``parts.section_applicability``
(jsonb ``{"<key>": true|false}``); a key that is missing means APPLICABLE, so existing Parts keep every section.

Public contract (other modules - RMTC entry / reports / print layouts - import these):

* ``PART_SECTIONS``                         ordered registry ``(key, label, group, description)``
* ``SECTION_KEYS``                          tuple of every key
* ``applicable_sections(part_id, repo=None) -> dict[str, bool]``   every key, default True
* ``section_applicable(part_id, key, repo=None) -> bool``          default True (unknown part / key / no DB)
* ``applicable_from_row(part_row) -> dict[str, bool]``             same, from an already-loaded ``parts`` row
* ``normalize_applicability(value) -> dict[str, bool]``            clean a stored / edited mapping
* ``not_applicable_labels(mapping) -> list[str]``                  labels for a print note
* ``filter_print_sections(sections, mapping) -> dict``              drop print tables of not-applicable sections
* ``section_completeness(repo, part_id, mapping=None) -> list[dict]`` completeness check that skips N/A sections

Keys (group PART = Part Master entry, RMTC = RMTC Part Worksheet / report):
    controlled_drawings, customer_standards, approved_sources, raw_material, supplier_technical_data, price_history,
    jominy, osp_metlab, final_metallurgical, process_routing, chemistry, di_value, heat_treatment, microstructure
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

PART_SECTIONS: tuple[tuple[str, str, str, str], ...] = (
    ("controlled_drawings", "Controlled Drawings (Finish / Forging / Heat Treatment)", "PART",
     "Part Master B/C - controlled drawing revisions and revision history."),
    ("customer_standards", "Customer Standards & Specifications", "PART", "Part Master D - linked standards."),
    ("approved_sources", "Approved Sources (Suppliers / Steel Mills)", "PART", "Part Master E - approved sources."),
    ("raw_material", "Raw Material Details / Forging Parameters", "PART", "Part Master E - RM / forging grid."),
    ("supplier_technical_data", "Supplier Technical Data", "PART", "Part Master E - technical rows copied to the PO."),
    ("price_history", "Supplier / FSI Part Price History", "PART", "Part Master E - controlled supplier prices."),
    ("jominy", "Jominy Requirement / Jominy Results", "PART", "Part Master F and the RMTC Jominy Results section."),
    ("osp_metlab", "OSP Inspection for MetLAB", "PART", "Part Master G - OSP process MetLAB requirements."),
    ("final_metallurgical", "Final Dispatch Metallurgical Requirements", "PART", "Part Master H - final MetLAB."),
    ("process_routing", "Part Processes & Drawings", "PART", "Part Master I - process routing, process drawings / specs, ECN."),
    ("chemistry", "Chemical Composition (RMTC)", "RMTC", "RMTC Part Worksheet - chemical composition check."),
    ("di_value", "DI Value (RMTC)", "RMTC", "RMTC Part Worksheet - actual / calculated DI."),
    ("heat_treatment", "Heat Treatment & Other Requirements (RMTC)", "RMTC", "RMTC Part Worksheet - HT / other requirements."),
    ("microstructure", "Microstructure Photographs (RMTC)", "RMTC", "RMTC report - microstructure photographs."),
)
SECTION_KEYS: tuple[str, ...] = tuple(row[0] for row in PART_SECTIONS)
SECTION_LABELS: dict[str, str] = {row[0]: row[1] for row in PART_SECTIONS}

# Part Master record print (render_records PDF) table name -> section key.
PRINT_SECTION_KEYS: dict[str, str] = {
    "Linked Customer Standards / Specifications": "customer_standards",
    "Raw Material Details": "raw_material",
    "Jominy Requirements": "jominy",
    "OSP / Process Inspection Requirements": "osp_metlab",
    "Metallurgical Requirements": "final_metallurgical",
    "Part Processes & Drawings": "process_routing",
    "Controlled Drawings": "controlled_drawings",
}

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


def normalize_applicability(value: Any) -> dict[str, bool]:
    """Every known key -> bool (missing / unreadable = True). Unknown keys are ignored."""
    data: Any = value
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data or "{}")
        except (TypeError, ValueError):
            data = {}
    if not isinstance(data, Mapping):
        data = {}
    return {key: _bool(data.get(key), True) for key in SECTION_KEYS}


def stored_applicability(mapping: Mapping[str, Any]) -> dict[str, bool]:
    """Value written to ``parts.section_applicability`` (all keys, explicit bools)."""
    return normalize_applicability(mapping)


def applicable_from_row(part_row: Mapping[str, Any] | None) -> dict[str, bool]:
    return normalize_applicability((part_row or {}).get("section_applicability"))


def _repo(repo: Any | None) -> Any | None:
    if repo is not None:
        return repo
    try:
        from core.repository import Repository
        return Repository()
    except Exception:
        return None


def applicable_sections(part_id: Any, repo: Any | None = None) -> dict[str, bool]:
    """Applicability of every section for one Part; all True when the Part / column cannot be read."""
    pid = str(part_id or "").strip()
    if not pid:
        return normalize_applicability({})
    r = _repo(repo)
    if r is None:
        return normalize_applicability({})
    try:
        row = r.get("parts", pid) if hasattr(r, "get") else None
    except Exception:
        row = None
    return applicable_from_row(row)


def section_applicable(part_id: Any, section_key: str, repo: Any | None = None) -> bool:
    """True unless the Part explicitly marks ``section_key`` Not Applicable (unknown keys are applicable)."""
    key = str(section_key or "").strip()
    if key not in SECTION_LABELS:
        return True
    return bool(applicable_sections(part_id, repo).get(key, True))


def not_applicable_labels(mapping: Mapping[str, Any] | None) -> list[str]:
    values = normalize_applicability(mapping or {})
    return [SECTION_LABELS[key] for key in SECTION_KEYS if not values[key]]


def filter_print_sections(sections: Mapping[str, Any], mapping: Mapping[str, Any] | None) -> dict[str, Any]:
    """Drop print tables whose section is Not Applicable (tables without a mapped key are kept)."""
    values = normalize_applicability(mapping or {})
    return {name: rows for name, rows in sections.items() if values.get(PRINT_SECTION_KEYS.get(name, ""), True)}


# section key -> (table, extra eq filter) used by the completeness check
_COMPLETENESS_SOURCES: dict[str, tuple[str, dict[str, Any]]] = {
    "customer_standards": ("part_standard_links", {"status": "ACTIVE"}),
    "approved_sources": ("part_supplier_links", {}),
    "raw_material": ("part_raw_material_details", {}),
    "price_history": ("part_supplier_price_history", {}),
    "jominy": ("part_jominy_requirements", {}),
    "final_metallurgical": ("part_metallurgical_requirements", {"status": "ACTIVE"}),
    "process_routing": ("part_process_routes", {"status": "ACTIVE"}),
}


def section_completeness(repo: Any, part_id: Any, mapping: Mapping[str, Any] | None = None,
                         keys: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """Rows ``{key, label, applicable, status}``; status is N/A (skipped), COMPLETE, MISSING or UNKNOWN."""
    pid = str(part_id or "")
    values = normalize_applicability(mapping) if mapping is not None else applicable_sections(pid, repo)
    out: list[dict[str, Any]] = []
    for key in keys or SECTION_KEYS:
        if key not in SECTION_LABELS:
            continue
        row = {"key": key, "label": SECTION_LABELS[key], "applicable": values[key]}
        if not values[key]:
            row["status"] = "N/A"
        elif key == "controlled_drawings":
            try:
                rows = repo.select("document_attachments", eq={"entity_type": "PART_MASTER", "entity_id": pid, "status": "ACTIVE"}, limit=20)
                row["status"] = "COMPLETE" if any(str(r.get("document_type")) == "FINISH_DRAWING" for r in rows) else "MISSING"
            except Exception:
                row["status"] = "UNKNOWN"
        elif key in _COMPLETENESS_SOURCES:
            table, extra = _COMPLETENESS_SOURCES[key]
            try:
                rows = repo.select(table, eq={"part_id": pid, **extra}, limit=1)
                row["status"] = "COMPLETE" if rows else "MISSING"
            except Exception:
                row["status"] = "UNKNOWN"
        else:
            row["status"] = "OPTIONAL"
        out.append(row)
    return out


__all__ = [
    "PART_SECTIONS", "SECTION_KEYS", "SECTION_LABELS", "PRINT_SECTION_KEYS", "normalize_applicability", "stored_applicability",
    "applicable_from_row", "applicable_sections", "section_applicable", "not_applicable_labels", "filter_print_sections",
    "section_completeness",
]
