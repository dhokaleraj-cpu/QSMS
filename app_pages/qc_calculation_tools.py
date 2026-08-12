from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.delete_service import password_delete_panel
from core.calculations import calculate_di, calculate_jominy_curve
from core.hardness_conversion import SCALE_LABELS, convert_hardness
from core.reporting import qc_calculation_pdf_bytes
from core.selection_labels import employee_label, part_label
from core.repository import Repository
from core.ui import page_header, save_success_popup, section_bar


def _employee_rows(repo: Repository) -> list[dict]:
    return repo.select("employees", eq={"status": "ACTIVE"}, order_by="first_name", limit=2000)


def _employee_labels(rows: list[dict]) -> dict[str, str]:
    return {str(row["id"]): employee_label(row) for row in rows}


def _part_rows(repo: Repository) -> list[dict]:
    return repo.select("parts", eq={"status": "ACTIVE"}, order_by="part_number", limit=4000)


def _calc_number(kind: str) -> str:
    prefix = {"JOMINY": "JOM", "DI_VALUE": "DI", "HARDNESS_CONVERSION": "HCV"}.get(kind, "QCT")
    return f"QCT-{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:4].upper()}"


def _context(repo: Repository, key_prefix: str) -> tuple[str | None, str | None, str | None, str]:
    parts = _part_rows(repo)
    employees = _employee_rows(repo)
    part_labels = {"": "— Not linked to a Part —", **{str(row["id"]): part_label(row) for row in parts}}
    employee_labels = _employee_labels(employees)
    c1, c2, c3 = st.columns(3, gap="small")
    part_id = c1.selectbox("Part Number (optional)", list(part_labels), format_func=lambda value: part_labels[value], key=f"{key_prefix}_part")
    heat_number = c2.text_input("Heat Number (optional)", key=f"{key_prefix}_heat")
    employee_id = c3.selectbox("Calculated / Performed By", list(employee_labels), format_func=lambda value: employee_labels[value], key=f"{key_prefix}_employee") if employee_labels else None
    part = next((row for row in parts if str(row["id"]) == part_id), None)
    grade_id = str((part or {}).get("material_grade_id") or "") or None
    return part_id or None, grade_id, employee_id, heat_number.strip()


def _save_record(repo: Repository, perms: dict[str, bool], *, calculation_type: str, part_id: str | None, grade_id: str | None, heat_number: str, employee_id: str | None, inputs: dict, results: dict, standard: str, primary_unit: str | None = None, primary_value: float | None = None, conversion_unit: str | None = None, result_value: float | None = None, remarks: str = "") -> dict | None:
    if not perms["can_create"]:
        st.error("You do not have Create permission for QC Calculation Tools.")
        return None
    payload = {
        "calculation_number": _calc_number(calculation_type),
        "calculation_type": calculation_type,
        "calculation_date": date.today().isoformat(),
        "part_id": part_id,
        "material_grade_id": grade_id,
        "heat_number": heat_number or None,
        "primary_unit": primary_unit,
        "primary_value": primary_value,
        "conversion_unit": conversion_unit,
        "result_value": result_value,
        "input_payload": inputs,
        "result_payload": results,
        "standard_reference": standard,
        "performed_by_employee_id": employee_id,
        "remarks": remarks.strip() or None,
        "status": "ACTIVE",
    }
    saved = repo.insert("qc_calculation_records", payload)
    save_success_popup(f"Calculation saved as {saved.get('calculation_number')}.")
    return saved


def _chemistry_inputs(prefix: str, symbols: list[str], defaults: dict[str, float] | None = None) -> dict[str, float]:
    defaults = defaults or {}
    columns = st.columns(4, gap="small")
    values: dict[str, float] = {}
    for index, symbol in enumerate(symbols):
        values[symbol] = columns[index % 4].number_input(
            f"{symbol} %", min_value=0.0, value=float(defaults.get(symbol, 0.0)), step=0.001, format="%.4f", key=f"{prefix}_{symbol}"
        )
    return values


def render_tools() -> None:
    page_header("QC Calculation Tools", "Jominy, DI and controlled hardness conversion calculations with stored records.", "Calculation")
    repo = Repository(); perms = current_permissions("QC_CALCULATION_TOOLS")
    tabs = st.tabs(["Jominy Calculator", "DI Value Calculator", "Hardness Conversion", "Calculation Records"])

    with tabs[0]:
        section_bar("JOMINY CALCULATOR", "Calculated from entered chemical composition using the existing QCMS Jominy calculation logic.")
        part_id, grade_id, employee_id, heat_number = _context(repo, "qct_jom")
        chemistry = _chemistry_inputs("qct_jom_chem", ["C", "MN", "CR", "NI", "MO"])
        remarks = st.text_area("Calculation Remarks", key="qct_jom_remarks", height=70)
        if st.button("Calculate Jominy Curve", type="primary", width="stretch", key="calculate_jominy"):
            st.session_state["qct_jom_result"] = calculate_jominy_curve(chemistry)
            st.session_state["qct_jom_inputs"] = chemistry
        curve = st.session_state.get("qct_jom_result")
        if curve:
            frame = pd.DataFrame([{"Distance (1/16 in.)": distance, "Calculated HRC": value} for distance, value in curve.items()])
            st.dataframe(frame, hide_index=True, width="stretch")
            if st.button("Save Jominy Calculation Record", width="stretch", key="save_jominy", disabled=not perms["can_create"]):
                _save_record(repo, perms, calculation_type="JOMINY", part_id=part_id, grade_id=grade_id, heat_number=heat_number, employee_id=employee_id, inputs=dict(st.session_state.get("qct_jom_inputs") or chemistry), results={"curve": curve}, standard="QCMS controlled Jominy calculation logic", remarks=remarks)

    with tabs[1]:
        section_bar("DI VALUE CALCULATOR", "Ideal diameter calculation using the QCMS DI factor table and chemical composition.")
        part_id, grade_id, employee_id, heat_number = _context(repo, "qct_di")
        chemistry = _chemistry_inputs("qct_di_chem", ["C", "MN", "SI", "NI", "CR", "MO", "CU", "V"])
        grain_size = st.selectbox("ASTM Grain Size", [4, 5, 6, 7, 8], index=3, key="qct_di_grain")
        remarks = st.text_area("Calculation Remarks", key="qct_di_remarks", height=70)
        if st.button("Calculate DI Value", type="primary", width="stretch", key="calculate_di"):
            st.session_state["qct_di_result"] = calculate_di(chemistry, int(grain_size))
            st.session_state["qct_di_inputs"] = {**chemistry, "grain_size": int(grain_size)}
        result = st.session_state.get("qct_di_result")
        if result:
            if result.get("error"):
                st.error(str(result["error"]))
            else:
                st.metric("Calculated DI", result.get("value"))
                st.dataframe(pd.DataFrame([{"Factor": key, "Value": value} for key, value in dict(result.get("factors") or {}).items()]), hide_index=True, width="stretch")
                if st.button("Save DI Calculation Record", width="stretch", key="save_di", disabled=not perms["can_create"]):
                    _save_record(repo, perms, calculation_type="DI_VALUE", part_id=part_id, grade_id=grade_id, heat_number=heat_number, employee_id=employee_id, inputs=dict(st.session_state.get("qct_di_inputs") or {}), results=dict(result), standard="QCMS DI Hardenability factor table", result_value=float(result.get("value")), remarks=remarks)

    with tabs[2]:
        section_bar("HARDNESS VALUE CONVERSION", "ASTM E 140-02 Table 1 - non-austenitic steels, Rockwell C hardness range.")
        st.warning("Hardness conversions are approximate and material-specific. QCMS does not extrapolate outside the values supported by the supplied ASTM E140 Table 1.")
        part_id, grade_id, employee_id, heat_number = _context(repo, "qct_hard")
        c1, c2, c3 = st.columns(3, gap="small")
        source_scale = c1.selectbox("Primary Hardness Unit", list(SCALE_LABELS), format_func=lambda value: SCALE_LABELS[value], key="qct_hard_source")
        source_value = c2.number_input("Primary Hardness Value", value=50.0, step=0.1, key="qct_hard_value")
        targets = [value for value in SCALE_LABELS if value != source_scale]
        target_scale = c3.selectbox("Conversion Unit", targets, format_func=lambda value: SCALE_LABELS[value], key="qct_hard_target")
        remarks = st.text_area("Calculation Remarks", key="qct_hard_remarks", height=70)
        if st.button("Convert Hardness", type="primary", width="stretch", key="convert_hardness"):
            try:
                st.session_state["qct_hard_result"] = convert_hardness(float(source_value), source_scale, target_scale)
            except Exception as exc:
                st.session_state.pop("qct_hard_result", None)
                st.error(str(exc))
        result = st.session_state.get("qct_hard_result")
        if result:
            st.metric("Converted Hardness", f"{float(result.get('target_value')):.3f} {result.get('target_scale')}")
            st.caption(str(result.get("method") or ""))
            st.info(str(result.get("warning") or ""))
            if st.button("Save Hardness Conversion Record", width="stretch", key="save_hardness", disabled=not perms["can_create"]):
                _save_record(repo, perms, calculation_type="HARDNESS_CONVERSION", part_id=part_id, grade_id=grade_id, heat_number=heat_number, employee_id=employee_id, inputs={"primary_unit": source_scale, "primary_value": source_value, "conversion_unit": target_scale}, results=dict(result), standard="ASTM E 140-02 Table 1", primary_unit=source_scale, primary_value=float(source_value), conversion_unit=target_scale, result_value=float(result.get("target_value")), remarks=remarks)

    with tabs[3]:
        _render_records(repo)


def _render_records(repo: Repository | None = None) -> None:
    repo = repo or Repository()
    section_bar("QC CALCULATION RECORDS")
    c1, c2 = st.columns([2, 1], gap="small")
    search = c1.text_input("Search Calculation No., Heat or Type", key="qct_records_search")
    calc_type = c2.selectbox("Calculation Type", ["ALL", "JOMINY", "DI_VALUE", "HARDNESS_CONVERSION"], key="qct_records_type")
    rows = repo.select("qc_calculation_records", order_by="created_at", desc=True, limit=5000)
    filtered = [row for row in rows if (calc_type == "ALL" or str(row.get("calculation_type")) == calc_type) and (not search or search.casefold() in " ".join(str(row.get(key) or "") for key in ("calculation_number", "heat_number", "calculation_type", "standard_reference")).casefold())]
    if not filtered:
        st.info("No QC Calculation records match the selected filters.")
        return
    labels = {str(row["id"]): f"{row.get('calculation_number')} · {str(row.get('calculation_type') or '').replace('_',' ').title()} · {row.get('calculation_date')}" for row in filtered}
    selected_id = st.selectbox("Select Calculation Record", list(labels), format_func=lambda value: labels[value], key="qct_record_selected")
    record = next(row for row in filtered if str(row["id"]) == selected_id)
    employees = {str(row["id"]): row for row in repo.select("employees", limit=3000)}
    parts = {str(row["id"]): row for row in repo.select("parts", limit=4000)}
    grades = {str(row["id"]): row for row in repo.select("material_grades", limit=3000)}
    pdf = qc_calculation_pdf_bytes({"record": record, "employee": employees.get(str(record.get("performed_by_employee_id"))) or {}, "part": parts.get(str(record.get("part_id"))) or {}, "grade": grades.get(str(record.get("material_grade_id"))) or {}})
    perms = current_permissions("QC_CALCULATION_TOOLS")
    c_pdf, c_delete = st.columns(2, gap="small")
    with c_pdf:
        st.download_button("Download Selected Calculation PDF", pdf, file_name=f"{record.get('calculation_number')}.pdf", mime="application/pdf", width="stretch")
    with c_delete:
        if password_delete_panel(
            repo=repo, table="qc_calculation_records", rows=[record],
            labeler=lambda row: f"{row.get('calculation_number')} · {row.get('calculation_type')}",
            key=f"delete_qc_calculation_{selected_id}", can_delete=perms["can_archive"],
            title="Delete Selected Calculation Record",
            help_text="Permanent deletion requires your current QCMS password.",
        ):
            st.rerun()
    display = pd.DataFrame([{
        "Calculation No.": row.get("calculation_number"), "Date": row.get("calculation_date"), "Type": row.get("calculation_type"),
        "Heat Number": row.get("heat_number"), "Primary": f"{row.get('primary_value') or ''} {row.get('primary_unit') or ''}".strip(),
        "Result": f"{row.get('result_value') or ''} {row.get('conversion_unit') or ''}".strip(), "Standard": row.get("standard_reference"), "Status": row.get("status")
    } for row in filtered])
    st.dataframe(display, hide_index=True, width="stretch", height=500)


def render_records() -> None:
    page_header("QC Calculation Records", "Stored Jominy, DI and hardness-conversion calculations with PDF traceability.", "Records")
    _render_records()
