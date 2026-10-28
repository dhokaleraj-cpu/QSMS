"""QCMS R38 · Part Processes (Part Master section "Part Processes & Drawings").

An ordered list of processes per Part (``part_process_routes``): operation no, process (Process Master), mandatory
Yes / No, in-house / OSP (optional OSP vendor note in remarks), remarks, ACTIVE / INACTIVE. Every process can carry
optional, revision-controlled process drawings and specifications (``document_attachments`` entity_type
PART_PROCESS, document_type PROCESS_DRAWING | PROCESS_SPEC); releasing a new revision makes the previous revision of the
same document number INACTIVE (shown as OBSOLETE, still downloadable) - the same pattern as the Part finish drawing.

Public contract (other modules may use these without touching Part Master):
* ``mandatory_processes(part_id, repo=None) -> list[dict]``  ACTIVE + mandatory processes of a Part, in Op No. order:
  ``{"route_id", "operation_no", "process_id", "process_code", "process_name", "source_type", "remarks"}``
* ``PartProcessService(repo)``: ``routes``, ``active_routes``, ``mandatory_processes``, ``documents``,
  ``current_documents``, ``save_routes``, ``copy_from_npd``, ``route_text``, ``print_rows``
* ``part_process_payloads(grid, label_to_process, process_by_id)``  validate the Part Master grid
* ``save_process_document_revision(...)`` / ``save_part_drawing_revision(...)``  storage upload + server RPC
* ``process_change_defaults(part, before, after)``  PCN form defaults for a process list change
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PROCESS_DOCUMENT_TYPES: tuple[tuple[str, str], ...] = (
    ("PROCESS_DRAWING", "Process Drawing"),
    ("PROCESS_SPEC", "Process Specification"),
)
PROCESS_SOURCE_TYPES: tuple[str, ...] = ("IN_HOUSE", "OSP")
ROUTE_TABLE = "part_process_routes"
DOC_ENTITY = "PART_PROCESS"


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:  # NaN
        return ""
    return str(value).strip()


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and value != value:
        return True
    try:
        import pandas as pd
        return bool(pd.isna(value)) if not isinstance(value, (list, dict, tuple, set)) else False
    except Exception:
        return False


def revision_status(row: Mapping[str, Any]) -> str:
    """Controlled revision status shown to users: ACTIVE = CURRENT, anything else = OBSOLETE."""
    return "CURRENT" if _clean(row.get("status")).upper() == "ACTIVE" else "OBSOLETE"


def storage_token(value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", _clean(value)).strip("._-") or "document"


def process_display(route: Mapping[str, Any], processes: Mapping[str, Mapping[str, Any]] | None = None) -> str:
    process = (processes or {}).get(_clean(route.get("process_id"))) or {}
    code = _clean(process.get("process_code"))
    name = _clean(process.get("process_name")) or _clean(route.get("process_name_snapshot")) or "-"
    return f"{code} · {name}" if code else name


def part_process_payloads(grid: Any, label_to_process: Mapping[str, str], process_by_id: Mapping[str, Mapping[str, Any]]) -> list[dict]:
    """Validate the Part process grid -> ``part_process_routes`` payloads (``_id`` kept for updates)."""
    payloads: list[dict] = []
    active_ops: set[int] = set()
    for index, row in grid.iterrows():
        label = _clean(row.get("Process"))
        op_value = row.get("Op No.")
        if not label and _is_missing(op_value):
            continue
        process_id = label_to_process.get(label)
        if not process_id:
            raise ValueError(f"Row {index + 1}: select a valid Process from Process Master.")
        if _is_missing(op_value) or int(op_value) <= 0:
            raise ValueError(f"Row {index + 1}: Op No. must be a positive number.")
        op_no = int(op_value)
        status = (_clean(row.get("Status")) or "ACTIVE").upper()
        if status == "ACTIVE":
            if op_no in active_ops:
                raise ValueError(f"Duplicate Op No. {op_no}. Each ACTIVE process needs its own operation number.")
            active_ops.add(op_no)
        source = _clean(row.get("Source")).upper().replace("-", "_")
        if source not in PROCESS_SOURCE_TYPES:
            source = "OSP" if _clean((process_by_id.get(process_id) or {}).get("process_type")).upper() == "OUTSOURCED" else "IN_HOUSE"
        mandatory = row.get("Mandatory")
        if isinstance(mandatory, str):
            mandatory_flag = mandatory.strip().casefold() not in {"no", "n", "false", "0", "optional"}
        else:
            mandatory_flag = True if _is_missing(mandatory) else bool(mandatory)
        raw_id = row.get("_id")
        payloads.append({
            "_id": _clean(raw_id) or None,
            "operation_no": op_no,
            "process_id": process_id,
            "process_name_snapshot": (process_by_id.get(process_id) or {}).get("process_name"),
            "is_mandatory": mandatory_flag,
            "source_type": source,
            "remarks": _clean(row.get("Remarks")) or None,
            "sequence_no": op_no,
            "status": status if status in {"ACTIVE", "INACTIVE"} else "ACTIVE",
        })
    return payloads


def route_text(routes: Sequence[Mapping[str, Any]], processes: Mapping[str, Mapping[str, Any]] | None = None) -> str:
    """Numbered process list (used as PCN previous description / revision requested)."""
    lines = []
    for index, route in enumerate(sorted(routes, key=lambda r: int(r.get("operation_no") or 0)), start=1):
        flags = ["Mandatory" if route.get("is_mandatory", True) else "Optional",
                 "OSP" if _clean(route.get("source_type")).upper() == "OSP" else "In-house"]
        remarks = _clean(route.get("remarks"))
        lines.append(f"{index}) Op {route.get('operation_no')} {process_display(route, processes)} ({', '.join(flags)})"
                     + (f" - {remarks}" if remarks else ""))
    return "\n".join(lines) or "-"


def process_change_defaults(part: Mapping[str, Any] | None, before: str, after: str, *, plant_code: str = "") -> dict[str, Any]:
    """PCN form defaults for a Part process list change (PCN sheet of FSI/806/F05)."""
    part = part or {}
    return {
        "change_type": "PCN",
        "document_scope": "PROCESS_FLOW",
        "part_id": _clean(part.get("id")) or None,
        "part_number": _clean(part.get("part_number")),
        "part_name": _clean(part.get("part_name")),
        "drawing_number": _clean(part.get("drawing_number")),
        "previous_revision": _clean(part.get("drawing_revision")),
        "previous_description": f"Previous process flow:\n{before or '-'}",
        "revision_requested": f"Revision requested - new process flow:\n{after or '-'}",
        "supporting_documents": {"purchase_order": True, "ppap": True, "pfd": True, "control_plan": True, "pfmea": True},
        "customer_approval": "PENDING",
        "drawing_change_mode": "AS_SUGGESTED",
        **({"plant_code": plant_code} if plant_code else {}),
    }


class PartProcessService:
    def __init__(self, repo: Any | None = None) -> None:
        if repo is None:
            from core.repository import Repository
            repo = Repository()
        self.repo = repo

    # ---------------------------------------------------------------- reads
    def processes(self, *, active_only: bool = True) -> list[dict]:
        eq = {"status": "ACTIVE"} if active_only else None
        return [dict(r) for r in (self.repo.select("processes", eq=eq, order_by="process_name", limit=3000) or [])]

    def routes(self, part_id: Any) -> list[dict]:
        if not _clean(part_id):
            return []
        rows = self.repo.select(ROUTE_TABLE, eq={"part_id": _clean(part_id)}, order_by="operation_no", limit=500) or []
        return sorted((dict(r) for r in rows), key=lambda r: (int(r.get("operation_no") or 0), _clean(r.get("status"))))

    def active_routes(self, part_id: Any) -> list[dict]:
        return [r for r in self.routes(part_id) if (_clean(r.get("status")) or "ACTIVE").upper() == "ACTIVE"]

    def mandatory_processes(self, part_id: Any) -> list[dict]:
        processes = {_clean(p.get("id")): p for p in self.processes(active_only=False)}
        out = []
        for route in self.active_routes(part_id):
            if not route.get("is_mandatory", True):
                continue
            process = processes.get(_clean(route.get("process_id"))) or {}
            out.append({
                "route_id": _clean(route.get("id")),
                "operation_no": route.get("operation_no"),
                "process_id": _clean(route.get("process_id")) or None,
                "process_code": _clean(process.get("process_code")),
                "process_name": _clean(process.get("process_name")) or _clean(route.get("process_name_snapshot")),
                "source_type": (_clean(route.get("source_type")) or "IN_HOUSE").upper(),
                "remarks": _clean(route.get("remarks")),
            })
        return out

    def documents(self, route_id: Any) -> list[dict]:
        if not _clean(route_id):
            return []
        rows = self.repo.select("document_attachments", eq={"entity_type": DOC_ENTITY, "entity_id": _clean(route_id)},
                                order_by="created_at", desc=True, limit=500) or []
        return [dict(r) for r in rows if _clean(r.get("document_type")) in dict(PROCESS_DOCUMENT_TYPES)]

    def current_documents(self, route_id: Any) -> list[dict]:
        return [d for d in self.documents(route_id) if _clean(d.get("status")).upper() == "ACTIVE"]

    # ---------------------------------------------------------------- writes
    def save_routes(self, part_id: Any, payloads: Iterable[Mapping[str, Any]]) -> int:
        existing_ids = {_clean(r.get("id")) for r in self.routes(part_id)}
        count = 0
        for payload in payloads:
            data = dict(payload)
            row_id = data.pop("_id", None)
            data["part_id"] = _clean(part_id)
            if row_id and row_id in existing_ids:
                self.repo.update(ROUTE_TABLE, row_id, data)
            else:
                self.repo.insert(ROUTE_TABLE, data)
            count += 1
        return count

    def copy_from_npd(self, part_id: Any, flow_id: Any) -> int:
        processes = {_clean(p.get("id")): p for p in self.processes(active_only=False)}
        steps = self.repo.select("npd_process_flow_steps", eq={"flow_id": _clean(flow_id)}, order_by="operation_no", limit=500) or []
        for index, step in enumerate(steps, start=1):
            process = processes.get(_clean(step.get("process_id"))) or {}
            self.repo.insert(ROUTE_TABLE, {
                "part_id": _clean(part_id), "operation_no": int(step.get("operation_no") or index * 10),
                "process_id": _clean(step.get("process_id")) or None,
                "process_name_snapshot": process.get("process_name") or step.get("process_name_snapshot"),
                "is_mandatory": True,
                "source_type": "OSP" if _clean(process.get("process_type")).upper() == "OUTSOURCED" else "IN_HOUSE",
                "remarks": step.get("remarks"), "sequence_no": index * 10, "status": "ACTIVE",
            })
        return len(steps)

    def print_rows(self, part_id: Any, processes: Mapping[str, Mapping[str, Any]] | None = None) -> list[dict]:
        """Part Master print rows: process routing with the CURRENT process drawing / spec revisions."""
        rows: list[dict] = []
        try:
            routes = self.active_routes(part_id)
        except Exception:
            return rows
        for route in routes:
            try:
                docs = self.current_documents(route.get("id"))
            except Exception:
                docs = []
            rows.append({
                "Op No.": route.get("operation_no"),
                "Process": process_display(route, processes),
                "Mandatory": "Yes" if route.get("is_mandatory", True) else "No",
                "Source": (_clean(route.get("source_type")) or "IN_HOUSE").replace("_", "-"),
                "Current Drawings / Specs": "; ".join(f"{d.get('drawing_number')} Rev {d.get('revision')}" for d in docs) or "-",
                "Remarks": route.get("remarks") or "",
            })
        return rows


def mandatory_processes(part_id: Any, repo: Any | None = None) -> list[dict]:
    """ACTIVE mandatory processes of a Part in Op No. order (for RMTC, OSP, inspections, PPAP ...)."""
    try:
        return PartProcessService(repo).mandatory_processes(part_id)
    except Exception:
        return []


class StoredUpload:
    """File-like copy of an uploaded file kept in session state while the ECN is completed."""

    def __init__(self, name: str, content: bytes, mime: str | None) -> None:
        self.name = name
        self.type = mime or "application/octet-stream"
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


def _rpc_row(result: Any) -> dict:
    if isinstance(result, list):
        return dict(result[0]) if result else {}
    return dict(result or {})


def _upload_and_activate(repo: Any, object_path: str, file: Any, rpc: str, params: dict, client: Any = None) -> dict:
    if client is None:
        from core.database import get_session_client
        client = get_session_client()
    if client is None:
        raise RuntimeError("Live Supabase session is required for controlled document upload.")
    content = file.getvalue()
    if not content:
        raise ValueError("The selected file is empty.")
    mime = getattr(file, "type", None) or "application/octet-stream"
    client.storage.from_("quality-documents").upload(object_path, content, {"content-type": mime, "upsert": "false"})
    try:
        result = repo.rpc(rpc, {**params, "p_file_name": str(file.name), "p_object_path": object_path, "p_mime_type": mime,
                                "p_size_bytes": len(content), "p_checksum": hashlib.sha256(content).hexdigest()})
    except Exception:
        try:
            client.storage.from_("quality-documents").remove([object_path])
        except Exception:
            pass
        raise
    return _rpc_row(result)


def _require(document_number: Any, revision: Any, revision_date: Any, file: Any, *, what: str) -> None:
    if not _clean(document_number):
        raise ValueError(f"{what} Number is mandatory.")
    if not _clean(revision):
        raise ValueError("Revision Number is mandatory.")
    if revision_date in (None, ""):
        raise ValueError("Revision Date is mandatory.")
    if file is None:
        raise ValueError("Select the controlled file.")


def _iso(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else _clean(value)[:10]


def save_process_document_revision(repo: Any, route: Mapping[str, Any], document_type: str, document_number: str, title: str,
                                   revision_number: str, revision_date: date | str, file: Any, *, client: Any = None) -> dict:
    """Store a new process drawing / specification revision (previous revision of the same number -> INACTIVE)."""
    _require(document_number, revision_number, revision_date, file, what="Drawing / Specification")
    ext = Path(str(file.name)).suffix.lower() or ".bin"
    object_path = (
        f"{repo.tenant_id}/parts/{route.get('part_id')}/process_documents/{route.get('id')}/{document_type.lower()}/"
        f"{storage_token(document_number)}/{storage_token(revision_number)}_{uuid.uuid4().hex[:10]}{ext}"
    )
    return _upload_and_activate(repo, object_path, file, "qcms_activate_part_process_document_revision", {
        "p_process_route_id": _clean(route.get("id")), "p_document_type": document_type,
        "p_document_number": _clean(document_number), "p_document_title": _clean(title) or None,
        "p_revision": _clean(revision_number), "p_revision_date": _iso(revision_date),
    }, client)


def save_part_drawing_revision(repo: Any, part_id: str, document_type: str, drawing_number: str, revision_number: str,
                               revision_date: date | str, file: Any, *, client: Any = None) -> dict:
    """Store a new Part controlled drawing revision (finish / forging / heat treatment) through the existing RPC."""
    _require(drawing_number, revision_number, revision_date, file, what="Drawing")
    ext = Path(str(file.name)).suffix.lower() or ".bin"
    object_path = (
        f"{repo.tenant_id}/parts/{part_id}/controlled_drawings/{document_type.lower()}/"
        f"{storage_token(drawing_number)}/{storage_token(revision_number)}_{uuid.uuid4().hex[:10]}{ext}"
    )
    return _upload_and_activate(repo, object_path, file, "qcms_activate_part_drawing_revision", {
        "p_part_id": part_id, "p_document_type": document_type, "p_drawing_number": _clean(drawing_number),
        "p_revision": _clean(revision_number), "p_revision_date": _iso(revision_date),
    }, client)



# =============================================================================================================== R38 sections
# Applicable sections of a Part (``parts.applicable_sections`` text[] = APPLICABLE keys, NULL = all applicable).
# Each key may mirror a key of the older jsonb ``parts.section_applicability`` (core.part_sections); the Part Master
# screen writes both so RMTC / MetLAB code reading either source sees the same choice.
#   key, label, group, legacy core.part_sections key (None = new key)
PART_SECTION_REGISTRY: tuple[tuple[str, str, str, str | None], ...] = (
    ("DRAWINGS", "Controlled Drawings (Finish / Forging / Heat Treatment)", "PART", "controlled_drawings"),
    ("STANDARDS", "Customer Standards & Specifications", "PART", "customer_standards"),
    ("APPROVED_SOURCES", "Approved Sources (Suppliers / Steel Mills)", "PART", "approved_sources"),
    ("RAW_MATERIAL", "Raw Material Details / Forging Parameters", "PART", "raw_material"),
    ("SUPPLIER_TECHNICAL_DATA", "Supplier Technical Data (RM technical rows)", "PART", "supplier_technical_data"),
    ("PRICE_HISTORY", "Supplier / FSI Part Price History", "PART", "price_history"),
    ("PROCESS_SPECIFICATIONS", "OSP / Process Inspection Requirements (MetLAB)", "PART", "osp_metlab"),
    ("FINAL_METALLURGICAL", "Final Dispatch Metallurgical Requirements", "PART", "final_metallurgical"),
    ("PROCESSES", "Part Processes & Drawings (routing, process drawings / specs)", "PART", "process_routing"),
    ("CHEMISTRY", "Chemical Composition", "METALLURGICAL", "chemistry"),
    ("MECHANICAL", "Mechanical Properties (tensile / yield / elongation / impact)", "METALLURGICAL", None),
    ("JOMINY", "Jominy / Hardenability", "METALLURGICAL", "jominy"),
    ("DI_VALUE", "DI Value", "METALLURGICAL", "di_value"),
    ("GRAIN_SIZE", "Grain Size", "METALLURGICAL", None),
    ("INCLUSION", "Inclusion Rating", "METALLURGICAL", None),
    ("MICROSTRUCTURE", "Microstructure", "METALLURGICAL", "microstructure"),
    ("HARDNESS", "Hardness", "METALLURGICAL", None),
    ("CASE_DEPTH", "Case Depth", "METALLURGICAL", None),
    ("HEAT_TREATMENT", "Heat Treatment", "METALLURGICAL", "heat_treatment"),
    ("ULTRASONIC", "Ultrasonic Testing", "METALLURGICAL", None),
    ("MACRO", "Macro Etch / Macro Structure", "METALLURGICAL", None),
)
PART_SECTION_KEYS: tuple[str, ...] = tuple(row[0] for row in PART_SECTION_REGISTRY)
PART_SECTION_LABELS: dict[str, str] = {row[0]: row[1] for row in PART_SECTION_REGISTRY}
PART_ONLY_SECTION_KEYS: tuple[str, ...] = tuple(row[0] for row in PART_SECTION_REGISTRY if row[2] == "PART")
METALLURGICAL_SECTION_KEYS: tuple[str, ...] = tuple(row[0] for row in PART_SECTION_REGISTRY if row[2] == "METALLURGICAL")
LEGACY_SECTION_KEY: dict[str, str] = {row[0]: row[3] for row in PART_SECTION_REGISTRY if row[3]}
# Part Master print table title -> section key (tables without a key are always printed)
PRINT_TABLE_SECTION: dict[str, str] = {
    "Linked Customer Standards / Specifications": "STANDARDS",
    "Raw Material Details": "RAW_MATERIAL",
    "Jominy Requirements": "JOMINY",
    "OSP / Process Inspection Requirements": "PROCESS_SPECIFICATIONS",
    "Metallurgical Requirements": "FINAL_METALLURGICAL",
    "Part Processes & Drawings": "PROCESSES",
    "Controlled Drawings": "DRAWINGS",
}
# Part child table -> section key (generic record print / preview of a Part skips tables of N/A sections)
CHILD_TABLE_SECTION: dict[str, str] = {
    "part_raw_material_details": "RAW_MATERIAL",
    "part_raw_material_technical_data": "SUPPLIER_TECHNICAL_DATA",
    "part_supplier_links": "APPROVED_SOURCES",
    "part_supplier_price_history": "PRICE_HISTORY",
    "part_process_specifications": "PROCESSES",
    "part_process_parameter_specifications": "PROCESS_SPECIFICATIONS",
    "part_metallurgical_requirements": "FINAL_METALLURGICAL",
    "part_heat_treatment_details": "HEAT_TREATMENT",
    "part_jominy_requirements": "JOMINY",
    "part_standard_links": "STANDARDS",
    "part_process_routes": "PROCESSES",
}
# requirement parameter name -> metallurgical key (first match wins; order matters: case depth before hardness)
_REQUIREMENT_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("JOMINY", ("jominy", "hardenability")),
    ("CASE_DEPTH", ("case depth", "ecd", "effective case", "case thickness", "total case")),
    ("GRAIN_SIZE", ("grain",)),
    ("INCLUSION", ("inclusion",)),
    ("MICROSTRUCTURE", ("microstructure", "micro structure", "micro-structure", "decarb")),
    ("MACRO", ("macro",)),
    ("ULTRASONIC", ("ultrasonic", "ut test", "u.t", "ut ")),
    ("MECHANICAL", ("tensile", "yield", "elongation", "reduction of area", "impact", "proof", "uts", "charpy", "mechanical")),
    ("HARDNESS", ("hardness", "hrc", "hrb", "hbw", "bhn", "hv", " hb", "brinell", "rockwell", "vickers")),
    ("HEAT_TREATMENT", ("heat treat", "quench", "temper", "normali", "anneal", "carburi", "induction")),
    ("DI_VALUE", ("di value", "ideal diameter", " di ")),
    ("CHEMISTRY", ("chemistry", "chemical", "carbon", "manganese", "chromium", "sulphur", "sulfur", "phosph", "silicon",
                   "nickel", "molybd", "boron", "aluminium", "aluminum")),
)


def _section_list(value: Any) -> list[str] | None:
    """Stored text[] (list / tuple / set / Postgres literal "{A,B}" / JSON list) -> list of keys; None = not chosen."""
    if value is None:
        return None
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
    else:
        text = _clean(value)
        if not text:
            return None
        if text.startswith("["):
            import json
            try:
                items = list(json.loads(text))
            except (TypeError, ValueError):
                items = []
        else:
            items = [v.strip().strip('"') for v in text.strip("{}").split(",")]
    return [_clean(v).upper() for v in items if _clean(v)]


def _load_part(part: Any, repo: Any | None) -> Mapping[str, Any]:
    if isinstance(part, Mapping):
        return part
    pid = _clean(part)
    if not pid:
        return {}
    try:
        if repo is None:
            from core.repository import Repository
            repo = Repository()
        return repo.get("parts", pid) or {}
    except Exception:
        return {}


def part_applicable_sections(part: Any, repo: Any | None = None) -> set[str]:
    """Applicable section keys of a Part (upper case, see ``PART_SECTION_REGISTRY``).

    ``part`` is a ``parts`` row (dict) or a Part id. Resolution:
    1. ``parts.applicable_sections`` (text[]) when it is not NULL - exactly those known keys;
    2. else the older jsonb ``parts.section_applicability`` (``core.part_sections``; a missing key = applicable) mapped
       through ``LEGACY_SECTION_KEY`` - keys without a legacy twin are applicable;
    3. unknown Part / no data -> every key.

    Keys - metallurgical (shared with RMTC / MetLAB): CHEMISTRY, MECHANICAL, JOMINY, DI_VALUE, GRAIN_SIZE, INCLUSION,
    MICROSTRUCTURE, HARDNESS, CASE_DEPTH, HEAT_TREATMENT, ULTRASONIC, MACRO.
    Part-only: DRAWINGS, STANDARDS, APPROVED_SOURCES, RAW_MATERIAL, SUPPLIER_TECHNICAL_DATA, PRICE_HISTORY,
    PROCESS_SPECIFICATIONS (OSP / process MetLAB requirements), FINAL_METALLURGICAL, PROCESSES.
    """
    row = _load_part(part, repo)
    stored = _section_list(row.get("applicable_sections")) if row else None
    if stored is not None:
        return {key for key in stored if key in PART_SECTION_LABELS}
    legacy = row.get("section_applicability") if row else None
    try:
        from core.part_sections import normalize_applicability
        mapping = normalize_applicability(legacy)
    except Exception:
        mapping = {}
    return {key for key in PART_SECTION_KEYS if mapping.get(LEGACY_SECTION_KEY.get(key, ""), True)}


def section_is_applicable(part: Any, key: str, repo: Any | None = None) -> bool:
    """True unless the Part marks ``key`` Not Applicable (unknown keys are applicable)."""
    k = _clean(key).upper()
    return k not in PART_SECTION_LABELS or k in part_applicable_sections(part, repo)


def sections_storage(selected: Iterable[str]) -> dict[str, Any]:
    """Columns written by the Part Master: ``applicable_sections`` (registry order) + the mirrored legacy jsonb."""
    chosen = {_clean(v).upper() for v in (selected or [])}
    keys = [key for key in PART_SECTION_KEYS if key in chosen]
    legacy: dict[str, bool] = {}
    try:
        from core.part_sections import SECTION_KEYS as LEGACY_KEYS
    except Exception:
        LEGACY_KEYS = tuple(LEGACY_SECTION_KEY.values())
    reverse = {legacy_key: key for key, legacy_key in LEGACY_SECTION_KEY.items()}
    for legacy_key in LEGACY_KEYS:
        new_key = reverse.get(legacy_key)
        legacy[legacy_key] = (new_key in chosen) if new_key else True
    return {"applicable_sections": keys, "section_applicability": legacy}


def legacy_applicability(applicable: Iterable[str]) -> dict[str, bool]:
    """``core.part_sections`` style mapping (lower-case keys) for screens still keyed on the jsonb column."""
    return dict(sections_storage(applicable)["section_applicability"])


def requirement_section_key(name: Any) -> str | None:
    """Metallurgical section key of a requirement / parameter name (None when it cannot be classified)."""
    text = f" {_clean(name).casefold()} "
    if not text.strip():
        return None
    for key, tokens in _REQUIREMENT_TOKENS:
        if any(token in text for token in tokens):
            return key
    return None


def filter_requirement_rows(rows: Iterable[Mapping[str, Any]], applicable: Iterable[str],
                            name_field: str = "parameter_name") -> list[dict]:
    """Drop requirement rows whose metallurgical key is Not Applicable (unclassified rows are kept)."""
    allowed = {_clean(v).upper() for v in applicable}
    out = []
    for row in rows or []:
        key = requirement_section_key(row.get(name_field))
        if key is None or key in allowed:
            out.append(dict(row))
    return out


def filter_print_tables(tables: Mapping[str, Any], applicable: Iterable[str]) -> dict[str, Any]:
    """Part Master print: omit tables of Not Applicable sections and requirement rows of N/A metallurgical keys."""
    allowed = {_clean(v).upper() for v in applicable}
    out: dict[str, Any] = {}
    for title, rows in tables.items():
        key = PRINT_TABLE_SECTION.get(title)
        if key and key not in allowed:
            continue
        if title in {"Metallurgical Requirements", "OSP / Process Inspection Requirements"} and isinstance(rows, list):
            rows = filter_requirement_rows(rows, allowed)
        out[title] = rows
    return out


def not_applicable_section_labels(applicable: Iterable[str]) -> list[str]:
    allowed = {_clean(v).upper() for v in applicable}
    return [PART_SECTION_LABELS[key] for key in PART_SECTION_KEYS if key not in allowed]

__all__ = [
    "PROCESS_DOCUMENT_TYPES", "PROCESS_SOURCE_TYPES", "PartProcessService", "mandatory_processes", "part_process_payloads",
    "route_text", "process_change_defaults", "revision_status", "process_display", "save_process_document_revision",
    "save_part_drawing_revision", "StoredUpload", "storage_token",
    "PART_SECTION_REGISTRY", "PART_SECTION_KEYS", "PART_SECTION_LABELS", "PART_ONLY_SECTION_KEYS", "METALLURGICAL_SECTION_KEYS",
    "LEGACY_SECTION_KEY", "PRINT_TABLE_SECTION", "CHILD_TABLE_SECTION", "part_applicable_sections", "section_is_applicable", "sections_storage",
    "legacy_applicability", "requirement_section_key", "filter_requirement_rows", "filter_print_tables",
    "not_applicable_section_labels",
]
