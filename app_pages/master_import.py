from __future__ import annotations

import io
import re
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st
from core.ui import portal_table

from core.access import current_permissions
from core.employee_service import AUTHORITIES, EmployeeService
from core.master_definitions import MASTER_BY_KEY, MasterDef
from core.master_service import MasterService
from core.repository import Repository
from core.ui import page_header, save_success_popup, section_bar, template_catalog, template_download_row


IMPORTABLE = (
    ("parts", "Part Master", "PART_MASTER", "Part_Master_Template.xlsx"),
    ("material_grades", "Material Grade", "MATERIAL_GRADE", "Material_Grade_Template.xlsx"),
    ("chemical_composition", "Chemical Composition", "MATERIAL_GRADE", "Material_Grade_Template.xlsx"),
    ("customers", "Customers", "REFERENCE_MASTERS", "Reference_Masters_Template.xlsx"),
    ("suppliers", "Suppliers", "REFERENCE_MASTERS", "Reference_Masters_Template.xlsx"),
    ("steel_mills", "Steel Mills", "REFERENCE_MASTERS", "Reference_Masters_Template.xlsx"),
    ("osp_vendors", "OSP Vendors", "REFERENCE_MASTERS", "Reference_Masters_Template.xlsx"),
    ("processes", "Processes", "REFERENCE_MASTERS", "Reference_Masters_Template.xlsx"),
    ("customer_standards", "Customer Standards & Specifications", "REFERENCE_MASTERS", "Customer_Standards_Template.xlsx"),
    ("inspection_stages", "Inspection Stages", "REFERENCE_MASTERS", "Reference_Masters_Template.xlsx"),
    ("quality_assets", "Quality Assets", "REFERENCE_MASTERS", "Reference_Masters_Template.xlsx"),
    ("inspection_plans", "Inspection Plans", "INSPECTION_LAYOUTS", "Inspection_Layout_Template.xlsx"),
    ("inspection_characteristics", "Inspection Characteristics", "INSPECTION_LAYOUTS", "Inspection_Layout_Template.xlsx"),
    ("test_plans", "Test Plans", "INSPECTION_LAYOUTS", "MetLAB_Report_Layout_Template.xlsx"),
    ("employees", "Employee Master", "EMPLOYEE_MASTER", "Employee_Master_Template.xlsx"),
)

SHEET_HINTS = {
    "parts": ("Part Header", "Parts", "Part Master"),
    "material_grades": ("Material Grade", "Material Grades"),
    "chemical_composition": ("Chemical Composition", "Chemistry"),
    "customers": ("Customers", "Parties", "Customer Master"),
    "suppliers": ("Suppliers", "Parties", "Vendor Supplier Master"),
    "steel_mills": ("Steel Mills", "Parties"),
    "osp_vendors": ("OSP Vendors", "Parties"),
    "processes": ("Processes", "Process Master"),
    "customer_standards": ("Customer Standards", "Standards Bank", "Customer Standards & Specifications"),
    "inspection_stages": ("Inspection Stages", "Stages"),
    "quality_assets": ("Quality Assets", "Assets", "Gauges"),
    "inspection_plans": ("Layout Header", "Inspection Plans"),
    "inspection_characteristics": ("Characteristics", "Inspection Characteristics"),
    "test_plans": ("Test Plans", "Layout Header"),
    "employees": ("Employees", "Employee Master"),
}

COMMON_SYNONYMS = {
    "part description": "part_name", "part name": "part_name", "fsi part number": "fsi_part_number", "fsi part no": "fsi_part_number", "customer": "customer_id",
    "material grade": "material_grade_id", "grade": "grade_code", "material number": "material_number",
    "drawing": "drawing_number", "revision": "revision", "drawing revision": "drawing_revision",
    "finished weight kg": "finished_weight_kg", "finish weight kg": "finished_weight_kg",
    "forging weight kg": "forging_weight_kg", "gross weight kg": "gross_weight_kg",
    "raw material section": "section_size", "section size": "section_size",
    "process code": "process_code", "process name": "process_name", "process type": "process_type",
    "standard code": "standard_code", "standard name": "standard_name", "specification name": "standard_name",
    "author name": "author_name", "author": "author_name", "issuing authority": "author_name",
    "revision number": "revision_number", "revision date": "revision_date", "related process": "process_id",
    "special process": "special_process", "cqi standard": "cqi_standard",
    "stage code": "stage_code", "stage name": "stage_name", "sequence no": "sequence_no", "sequence": "sequence_no",
    "employee code": "employee_code", "first name": "first_name", "last name": "last_name",
    "mobile number": "mobile_number", "approval authorities": "approval_authorities",
    "reports to employee code": "reports_to_employee_id", "experience start date": "experience_start_date",
    "party code": "party_code", "party name": "party_name", "party type": "party_types",
    "approval status": "approval_status", "record status": "status",
    "standard / specification": "standard", "standard": "standard",
    "element": "element", "minimum %": "minimum", "maximum %": "maximum", "minimum": "minimum", "maximum": "maximum",
    "test method": "test_method", "supplier": "supplier_id", "steel mill": "steel_mill_id",
    "supplier part number": "supplier_part_number", "approval reference": "approval_reference",
    "valid from": "valid_from", "valid to": "valid_to", "approved": "approved",
    "asset code": "asset_code", "asset name": "asset_name", "asset type": "asset_type",
    "calibration frequency days": "calibration_frequency_days", "last calibration date": "last_calibration_date", "next due date": "next_due_date",
    "inspection plan": "inspection_plan_id", "plan number": "plan_number", "inspection stage": "inspection_stage_id",
    "characteristic number": "characteristic_no", "parameter": "characteristic", "characteristic": "characteristic",
    "lower specification": "lower_spec", "upper specification": "upper_spec", "checking aid": "checking_aid_id",
    "checking method": "checking_method", "sample size": "sample_size", "reaction plan": "reaction_plan",
    "test type": "test_type", "specification reference": "specification_reference", "acceptance criteria": "acceptance_criteria",
}


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().casefold()).strip()


def _read_frames(file: Any) -> dict[str, pd.DataFrame]:
    content = file.getvalue()
    name = str(file.name or "").lower()
    if name.endswith(".csv"):
        return {"CSV": pd.read_csv(io.BytesIO(content), dtype=object)}
    return {str(k): v for k, v in pd.read_excel(io.BytesIO(content), sheet_name=None, dtype=object).items()}


def _select_sheet(frames: dict[str, pd.DataFrame], key: str) -> tuple[str, pd.DataFrame]:
    hints = [_norm(value) for value in SHEET_HINTS.get(key, ())]
    for sheet, frame in frames.items():
        if _norm(sheet) in hints and not frame.dropna(how="all").empty:
            return sheet, frame.dropna(how="all").copy()
    for sheet, frame in frames.items():
        clean = frame.dropna(how="all").copy()
        if not clean.empty:
            return sheet, clean
    first = next(iter(frames))
    return first, frames[first]


def _field_map(definition: MasterDef) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for field in definition.fields:
        mapping[_norm(field.name)] = field.name
        mapping[_norm(field.label)] = field.name
    mapping.update({_norm(k): v for k, v in COMMON_SYNONYMS.items()})
    return mapping


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        return None if not text else text
    return value


def _truthy(value: Any) -> bool:
    return _norm(value) in {"1", "true", "yes", "y", "approved", "active"}


def _lookup_candidates(service: MasterService, lookup: str) -> list[tuple[str, str, list[str]]]:
    rows = service.list_records(service.definition(lookup), status="All")
    out: list[tuple[str, str, list[str]]] = []
    for row in rows:
        rid = str(row.get("id"))
        if lookup in {"customers", "suppliers", "steel_mills", "osp_vendors"}:
            keys = [row.get("party_code"), row.get("party_name")]
            label = f"{row.get('party_code') or ''} · {row.get('party_name') or ''}".strip(" ·")
        elif lookup == "material_grades":
            keys = [row.get("material_number"), row.get("grade_code")]
            label = f"{row.get('material_number') or ''} · {row.get('grade_code') or ''}".strip(" ·")
        elif lookup == "parts":
            keys = [row.get("part_number"), row.get("fsi_part_number"), row.get("part_name")]
            label = f"{row.get('part_number') or ''} · FSI {row.get('fsi_part_number') or '-'} · {row.get('part_name') or ''}".strip(" ·")
        elif lookup == "processes":
            keys = [row.get("process_code"), row.get("process_name")]
            label = f"{row.get('process_code') or ''} · {row.get('process_name') or ''}".strip(" ·")
        elif lookup == "customer_standards":
            keys = [row.get("standard_code"), row.get("standard_name"), row.get("revision_number")]
            label = f"{row.get('standard_code') or ''} · {row.get('standard_name') or ''} · Rev {row.get('revision_number') or ''}".strip(" ·")
        elif lookup == "inspection_stages":
            keys = [row.get("stage_code"), row.get("stage_name")]
            label = f"{row.get('stage_code') or ''} · {row.get('stage_name') or ''}".strip(" ·")
        elif lookup == "quality_assets":
            keys = [row.get("asset_code"), row.get("asset_name"), row.get("serial_number")]
            label = f"{row.get('asset_code') or ''} · {row.get('asset_name') or ''}".strip(" ·")
        elif lookup == "inspection_plans":
            keys = [row.get("plan_number"), f"{row.get('plan_number') or ''} Rev {row.get('revision') or ''}"]
            label = keys[-1]
        else:
            keys = [rid]
            label = rid
        out.append((rid, label, [_norm(k) for k in keys if k not in (None, "")]))
    return out


def _resolve_lookup(service: MasterService, lookup: str, value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    needle = _norm(text)
    for rid, label, keys in _lookup_candidates(service, lookup):
        if text == rid or needle in keys or needle == _norm(label):
            return rid
    # Permit the common "CODE · Name" display form by comparing each segment.
    for segment in re.split(r"[·|]", text):
        seg = _norm(segment)
        if not seg:
            continue
        for rid, _label, keys in _lookup_candidates(service, lookup):
            if seg in keys:
                return rid
    raise ValueError(f"Could not resolve {lookup.replace('_',' ')} value: {text}")


def _existing_id(service: MasterService, definition: MasterDef, payload: dict[str, Any]) -> str | None:
    expected = tuple(service._normalized_key_value(payload.get(field)) for field in definition.natural_key)
    if not any(expected):
        return None
    for row in service.list_records(definition, status="All"):
        actual = tuple(service._normalized_key_value(row.get(field)) for field in definition.natural_key)
        if actual == expected:
            return str(row.get("id"))
    return None


def _row_payload(service: MasterService, definition: MasterDef, source: dict[str, Any]) -> dict[str, Any]:
    mapping = _field_map(definition)
    raw: dict[str, Any] = {}
    for source_key, value in source.items():
        field_name = mapping.get(_norm(source_key))
        if not field_name:
            continue
        raw[field_name] = _clean_value(value)
    fields = {field.name: field for field in definition.fields}
    for name, field in fields.items():
        if name not in raw:
            continue
        value = raw.get(name)
        if field.kind == "lookup":
            raw[name] = _resolve_lookup(service, field.lookup, value)
        elif field.kind == "boolean":
            raw[name] = _truthy(value)
        elif field.kind == "select" and value is not None:
            raw[name] = str(value).strip().upper().replace(" ", "_")
    # Template marker means "let the controlled auto-number generator supply the code".
    if definition.auto_code_field and _norm(raw.get(definition.auto_code_field)) in {"auto", "automatic", "auto generated"}:
        raw[definition.auto_code_field] = None
    return raw


def _import_definition(service: MasterService, definition: MasterDef, frame: pd.DataFrame) -> tuple[int, int, list[str]]:
    """Insert only database-missing master rows; silently skip duplicate natural keys."""
    created = skipped = 0
    errors: list[str] = []
    seen_keys: set[str] = set()
    for row_no, record in enumerate(frame.to_dict("records"), start=2):
        if not any(_clean_value(v) is not None for v in record.values()):
            continue
        try:
            raw = _row_payload(service, definition, record)
            normalized = service.normalize_payload(definition, raw)
            existing_id = _existing_id(service, definition, normalized)
            natural_signature = "|".join(str(normalized.get(field) or "").strip().casefold() for field in definition.natural_key)
            extra_unique_fields: tuple[str, ...] = ()
            if definition.key in {"customers", "suppliers", "steel_mills", "osp_vendors"}:
                extra_unique_fields = ("party_name",)
            elif definition.key == "processes":
                extra_unique_fields = ("process_name",)
            elif definition.key == "inspection_stages":
                extra_unique_fields = ("stage_name",)
            elif definition.key == "quality_assets":
                extra_unique_fields = ("asset_name",)
            fuzzy_duplicate = service.duplicate_match(definition, normalized, extra_unique_fields=extra_unique_fields)
            if existing_id or fuzzy_duplicate or (natural_signature and natural_signature in seen_keys):
                skipped += 1
                continue
            _saved, action = service.save(definition, raw, record_id=None)
            if action == "created":
                created += 1
                if natural_signature:
                    seen_keys.add(natural_signature)
            else:
                # Defensive guard: generic service should not update during import-only mode.
                skipped += 1
        except Exception as exc:
            errors.append(f"Row {row_no}: {exc}")
    return created, skipped, errors


def _import_employees(repo: Repository, frame: pd.DataFrame) -> tuple[int, int, list[str]]:
    service = EmployeeService(); service.repo = repo
    existing = service.list(False)
    by_code = {_norm(row.get("employee_code")): row for row in existing if row.get("employee_code")}
    by_email = {_norm(row.get("email")): row for row in existing if row.get("email")}
    created = skipped = 0
    errors: list[str] = []
    pending_manager: list[tuple[str, str]] = []
    for row_no, source in enumerate(frame.to_dict("records"), start=2):
        if not any(_clean_value(v) is not None for v in source.values()):
            continue
        values = {_norm(k): _clean_value(v) for k, v in source.items()}
        try:
            code = str(values.get("employee code") or "").strip()
            if _norm(code) in {"", "auto", "automatic"}:
                code = str(repo.rpc("qsms_next_employee_code") or "")
            email = str(values.get("email") or "").strip().lower()
            authorities_text = values.get("approval authorities")
            if isinstance(authorities_text, str):
                authorities = [item.strip().upper() for item in re.split(r"[,;|]", authorities_text) if item.strip()]
            elif isinstance(authorities_text, (list, tuple)):
                authorities = [str(item).strip().upper() for item in authorities_text if str(item).strip()]
            else:
                authorities = []
            authorities = [item for item in authorities if item in AUTHORITIES]
            manager_code = str(values.get("reports to employee code") or "").strip()
            existing_row = by_code.get(_norm(code)) or by_email.get(_norm(email))
            if existing_row:
                skipped += 1
                continue
            payload = {
                "employee_code": code,
                "first_name": str(values.get("first name") or "").strip(),
                "last_name": str(values.get("last name") or "").strip(),
                "email": email,
                "department": str(values.get("department") or "").strip(),
                "designation": str(values.get("designation") or "").strip(),
                "plant": str(values.get("plant") or "D9").strip(),
                "mobile_number": str(values.get("mobile number") or "").strip() or None,
                "approval_authorities": authorities,
                "reports_to_employee_id": None,
                "experience_start_date": str(values.get("experience start date") or date.today().isoformat())[:10],
                "status": str(values.get("status") or "ACTIVE").strip().upper(),
                "remarks": str(values.get("remarks") or "").strip() or None,
                "source_system": "QCMS_IMPORT",
            }
            saved = service.save(payload, None)
            created += 1
            by_code[_norm(saved.get("employee_code"))] = saved
            by_email[_norm(saved.get("email"))] = saved
            if manager_code:
                pending_manager.append((str(saved["id"]), manager_code))
        except Exception as exc:
            errors.append(f"Row {row_no}: {exc}")
    for employee_id, manager_code in pending_manager:
        manager = by_code.get(_norm(manager_code))
        if manager and str(manager.get("id")) != employee_id:
            repo.update("employees", employee_id, {"reports_to_employee_id": str(manager["id"])})
    return created, skipped, errors


def _prepare_material_grade_frame(frame: pd.DataFrame) -> pd.DataFrame:
    # Normalize the official template's Material Number field into the custom database column after MasterService save.
    return frame


def render() -> None:
    page_header("Master Import", "Upload completed Excel/CSV templates. Existing duplicate natural keys are skipped; only database-missing records are created.", "Import")
    labels = {key: label for key, label, _module, _template in IMPORTABLE}
    keys = [row[0] for row in IMPORTABLE]
    requested = str(st.session_state.pop("master_import_selected_key", "") or "")
    default_index = keys.index(requested) if requested in keys else 0
    selected_key = st.selectbox("Master to Import", keys, index=default_index, format_func=lambda value: labels[value])
    _key, _label, module_key, template_name = next(row for row in IMPORTABLE if row[0] == selected_key)
    perms = current_permissions(module_key)
    if not (perms["can_create"] or perms["can_edit"]):
        st.warning("Create or Edit permission is required for this master import.")

    section_bar("TEMPLATE & UPLOAD")
    template_download_row([(template_name, f"Download {_label} Template")], key_prefix=f"master_import_{selected_key}")
    uploaded = st.file_uploader("Upload completed master file", type=["xlsx", "xls", "csv"], key=f"master_import_file_{selected_key}")
    if uploaded is None:
        st.caption("Complete the template and upload it here. Existing matching database records are skipped; only new natural keys are imported.")
        return

    try:
        frames = _read_frames(uploaded)
        sheet_name, frame = _select_sheet(frames, selected_key)
    except Exception as exc:
        st.error(f"Could not read the uploaded master file: {exc}")
        return

    # The combined Parties worksheet can contain several master types.  When a
    # specific party master is selected, import only rows belonging to that type.
    party_expected = {
        "customers": "CUSTOMER",
        "suppliers": "SUPPLIER",
        "steel_mills": "STEEL_MILL",
        "osp_vendors": "OSP_VENDOR",
    }
    if selected_key in party_expected:
        party_type_column = next((c for c in frame.columns if _norm(c) in {"party type", "party types", "type"}), None)
        if party_type_column:
            expected = party_expected[selected_key]
            def _party_match(value: Any) -> bool:
                tokens = {token for token in re.split(r"[,;|/]+", str(value or "").upper()) if token.strip()}
                tokens = {token.strip().replace(" ", "_") for token in tokens}
                return expected in tokens or _norm(value) == _norm(expected)
            frame = frame[frame[party_type_column].map(_party_match)].copy()

    st.caption(f"Detected worksheet: {sheet_name} · {len(frame)} applicable data row(s)")
    portal_table(frame.head(30), hide_index=True, width="stretch", height=min(520, 100 + 35 * min(len(frame), 12)))
    st.info("Duplicate-safe import: existing matching master keys and duplicate rows inside the uploaded file are skipped. Only missing database records are created.")

    if st.button("Import Selected Master", type="primary", width="stretch", disabled=not (perms["can_create"] or perms["can_edit"])):
        try:
            repo = Repository(); service = MasterService(repo)
            if selected_key == "employees":
                created, skipped, errors = _import_employees(repo, frame)
            else:
                definition = MASTER_BY_KEY[selected_key]
                preexisting_grade_codes = {_norm(r.get("grade_code")) for r in repo.select("material_grades", limit=5000)} if selected_key == "material_grades" else set()
                created, skipped, errors = _import_definition(service, definition, frame)
                if selected_key == "material_grades":
                    # Preserve / assign Material Number, which is a controlled field outside the generic MasterDef form.
                    normalized_headers = {_norm(c): c for c in frame.columns}
                    mat_col = normalized_headers.get("material number")
                    grade_col = normalized_headers.get("material grade") or normalized_headers.get("grade") or normalized_headers.get("grade code")
                    if grade_col:
                        for source in frame.to_dict("records"):
                            grade_code = str(_clean_value(source.get(grade_col)) or "").strip()
                            if not grade_code or _norm(grade_code) in preexisting_grade_codes:
                                continue
                            grade_row = next((r for r in repo.select("material_grades", order_by="grade_code", limit=3000) if _norm(r.get("grade_code")) == _norm(grade_code)), None)
                            if not grade_row:
                                continue
                            material_no = str(_clean_value(source.get(mat_col)) or "").strip() if mat_col else ""
                            if _norm(material_no) in {"", "auto", "automatic"}:
                                material_no = str(grade_row.get("material_number") or repo.rpc("qcms_next_material_number") or "")
                            if material_no and str(grade_row.get("material_number") or "") != material_no:
                                repo.update("material_grades", str(grade_row["id"]), {"material_number": material_no})
            if errors:
                st.error("Import completed with validation errors:\n\n" + "\n".join(errors[:30]))
                if len(errors) > 30:
                    st.caption(f"{len(errors)-30} additional row error(s) were not displayed.")
            if created or skipped:
                save_success_popup(f"Master import completed: {created} created, {skipped} duplicate/existing row(s) skipped, {len(errors)} rejected.", queue_for_rerun=False)
            elif not errors:
                st.info("No new database-missing rows were available to import.")
        except Exception as exc:
            st.error(str(exc))
