from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from core.repository import Repository
from core.ui import disposition_cards, page_header, section_bar, style_status_dataframe, subpage_navigation


def _rows(repo: Repository, table: str, **kwargs) -> list[dict]:
    try:
        return repo.select(table, limit=3000, **kwargs)
    except Exception as exc:
        st.error(f"Could not load {table}: {exc}")
        return []


def _map(rows: list[dict], key: str, value: str) -> dict[str, str]:
    return {str(row.get(key)): str(row.get(value) or "") for row in rows}


def _table(frame: pd.DataFrame, *, height: int = 560) -> None:
    if frame.empty:
        st.info("No records are available for this register.")
        return
    st.dataframe(style_status_dataframe(frame), hide_index=True, width="stretch", height=height)



def _excel_bytes(frame: pd.DataFrame, sheet_name: str) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=sheet_name[:31])
        worksheet = writer.sheets[sheet_name[:31]]
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        for column_cells in worksheet.columns:
            width = min(max(len(str(cell.value or "")) for cell in column_cells) + 2, 36)
            worksheet.column_dimensions[column_cells[0].column_letter].width = max(width, 12)
    return output.getvalue()


def _normalize_heat(value: object) -> str:
    return "".join(character for character in str(value or "").upper() if character.isalnum())


def render_heat_ledger(*, embedded: bool = False) -> None:
    if not embedded:
        subpage_navigation(
            ("dashboard", "Dashboard", ":material/arrow_back:"),
            ("rmtc-entry", "RMTC Entry", ":material/fact_check:"),
            ("rmtc-records", "RMTC Records", ":material/table_view:"),
            ("records-center", "Records Centre", ":material/dataset:"),
        )
        page_header("Heat Steel Ledger", context="Heat-wise RMTC plans, inward steel consumption and global balance")

    repo = Repository()
    summary_rows = _rows(repo, "v_qsms_heat_summary", order_by="last_activity_at", desc=True)
    ledger_rows = _rows(repo, "v_qsms_heat_steel_ledger", order_by="updated_at", desc=True)

    requested = str(st.session_state.get("heat_ledger_filter") or "").strip()
    heat_values = sorted({str(row.get("heat_number") or "").strip() for row in summary_rows if row.get("heat_number")})
    options = ["All Heat Numbers"] + heat_values
    default_index = 0
    requested_key = _normalize_heat(requested)
    for index, value in enumerate(options):
        if requested_key and _normalize_heat(value) == requested_key:
            default_index = index
            break

    c1, c2 = st.columns([3, 1], gap="small")
    selected_heat = c1.selectbox(
        "Heat Number", options, index=default_index, key=f"heat_ledger_select_{'embedded' if embedded else 'page'}"
    )
    search = c2.text_input("Search", placeholder="RMTC, supplier, part")

    selected_key = "" if selected_heat == "All Heat Numbers" else _normalize_heat(selected_heat)
    filtered = [
        row for row in ledger_rows
        if (not selected_key or str(row.get("normalized_heat_number") or "") == selected_key)
        and (not search or search.casefold() in " ".join(str(row.get(key) or "") for key in (
            "heat_number", "rmtc_number", "supplier_rmtc_number", "supplier_name", "part_number", "part_name",
            "rmtc_status", "rmtc_disposition", "part_disposition"
        )).casefold())
    ]

    selected_summary = next((row for row in summary_rows if str(row.get("normalized_heat_number") or "") == selected_key), None) if selected_key else None
    if selected_summary:
        disposition_cards([
            {"label": "Global Heat Steel kg", "value": f"{float(selected_summary.get('global_steel_quantity_kg') or 0):,.3f}"},
            {"label": "Planned Steel kg", "value": f"{float(selected_summary.get('active_planned_steel_quantity_kg') or 0):,.3f}"},
            {"label": "Inward Steel kg", "value": f"{float(selected_summary.get('inward_steel_quantity_kg') or 0):,.3f}"},
            {"label": "Balance Steel kg", "value": f"{float(selected_summary.get('available_unallocated_steel_quantity_kg') or 0):,.3f}"},
        ])
    else:
        disposition_cards([
            {"label": "Heat Numbers", "value": len(summary_rows)},
            {"label": "Global Steel kg", "value": f"{sum(float(row.get('global_steel_quantity_kg') or 0) for row in summary_rows):,.3f}"},
            {"label": "Inward Steel kg", "value": f"{sum(float(row.get('inward_steel_quantity_kg') or 0) for row in summary_rows):,.3f}"},
            {"label": "Balance Steel kg", "value": f"{sum(float(row.get('available_unallocated_steel_quantity_kg') or 0) for row in summary_rows):,.3f}"},
        ])

    frame = pd.DataFrame([{
        "Heat Number": row.get("heat_number"),
        "Global Heat Qty kg": row.get("global_steel_quantity_kg"),
        "QSMS RMTC": row.get("rmtc_number"),
        "Supplier RMTC Number": row.get("supplier_rmtc_number"),
        "Supplier": row.get("supplier_name"),
        "Part Number": row.get("part_number"),
        "Part Description": row.get("part_name"),
        "Planned Qty pcs": row.get("planned_production_quantity_pcs"),
        "Input Wt kg/part": row.get("input_weight_kg"),
        "Planned Steel kg": row.get("planned_steel_quantity_kg"),
        "Inward Qty pcs": row.get("inward_production_quantity_pcs"),
        "Inward Steel kg": row.get("inward_steel_quantity_kg"),
        "Remaining Planned kg": row.get("remaining_planned_steel_quantity_kg"),
        "Heat Inward Total kg": row.get("heat_inward_steel_quantity_kg"),
        "Heat Remaining Plan kg": row.get("heat_remaining_planned_steel_quantity_kg"),
        "Heat Committed kg": row.get("committed_steel_quantity_kg"),
        "Heat Balance kg": row.get("heat_balance_quantity_kg"),
        "Heat Validation": row.get("heat_balance_status"),
        "RMTC Workflow": row.get("rmtc_status"),
        "RMTC Decision": row.get("rmtc_disposition"),
        "Automated Validation": row.get("automated_validation"),
        "Part Decision": row.get("part_disposition"),
    } for row in filtered])

    section_bar("HEAT NUMBER STEEL LEDGER", "One row per RMTC Part Number with global Heat quantity, plan, inward and balance validation.")
    _table(frame, height=620)
    if not frame.empty:
        file_suffix = selected_key or "ALL_HEATS"
        st.download_button(
            "Download Heat Steel Ledger",
            data=_excel_bytes(frame, "Heat Steel Ledger"),
            file_name=f"QSMS_Heat_Steel_Ledger_{file_suffix}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            width="stretch",
            key=f"download_heat_ledger_{file_suffix}_{'embedded' if embedded else 'page'}",
        )


def render() -> None:
    subpage_navigation(
        ("dashboard", "Dashboard", ":material/arrow_back:"),
        ("rmtc-records", "RMTC Records", ":material/fact_check:"),
        ("inward-records", "Inward Records", ":material/input:"),
        ("inspection-home", "Inspections", ":material/biotech:"),
    )
    page_header("Records Centre", context="One status register for every operational module")
    repo = Repository()

    parts = _rows(repo, "parts", order_by="part_number")
    parties = _rows(repo, "parties", order_by="party_name")
    part_map = _map(parts, "id", "part_number")
    part_name_map = _map(parts, "id", "part_name")
    party_map = _map(parties, "id", "party_name")

    tabs = st.tabs(["RMTC", "Material Inward", "OSP Transactions", "Dimensional", "MetLAB", "Layouts", "Masters", "Heat Steel Ledger"])

    with tabs[0]:
        rows = _rows(repo, "rmtc_approvals", order_by="created_at", desc=True)
        disposition_cards([
            {"label": "Total RMTC", "value": len(rows)},
            {"label": "Draft", "value": sum(str(r.get("status")) == "DRAFT" for r in rows)},
            {"label": "Approval Pending", "value": sum(str(r.get("status")) == "APPROVAL_PENDING" for r in rows)},
            {"label": "Accepted", "value": sum(str(r.get("disposition")) == "ACCEPTED" for r in rows)},
        ])
        section_bar("RMTC REGISTER")
        _table(pd.DataFrame([{
            "RMTC Number": r.get("rmtc_number"),
            "Supplier RMTC": r.get("certificate_reference"),
            "Heat Number": r.get("heat_number"),
            "Primary Part": part_map.get(str(r.get("part_id"))),
            "Supplier": party_map.get(str(r.get("supplier_id"))),
            "Steel Mill": party_map.get(str(r.get("steel_mill_id"))),
            "Steel Qty kg": r.get("certificate_quantity"),
            "Validation": r.get("validation_result"),
            "Workflow": r.get("status"),
            "Final Decision": r.get("disposition"),
            "Created": r.get("created_at"),
        } for r in rows]))
        st.page_link(st.session_state["_qsms_pages"]["rmtc-records"], label="Open RMTC Records and Actions", icon=":material/open_in_new:", width="stretch")

    with tabs[1]:
        rows = _rows(repo, "v_qsms_inward_register", order_by="created_at", desc=True)
        disposition_cards([
            {"label": "Total Inwards", "value": len(rows)},
            {"label": "Pending / Hold", "value": sum(str(r.get("status")) == "HOLD_PENDING_INSPECTION" for r in rows)},
            {"label": "Released", "value": sum(str(r.get("status")) == "RELEASED" for r in rows)},
            {"label": "Rejected", "value": sum(str(r.get("status")) == "REJECTED" for r in rows)},
        ])
        section_bar("MATERIAL INWARD REGISTER")
        _table(pd.DataFrame([{
            "Inward": r.get("inward_number"),
            "Date": r.get("inward_date"),
            "Supplier": r.get("supplier_name"),
            "Part Number": r.get("part_number"),
            "Part Description": r.get("part_name"),
            "Heat Number": r.get("heat_number"),
            "Steel kg": r.get("steel_quantity_kg") or r.get("quantity_received"),
            "Production pcs": r.get("production_quantity_pcs"),
            "Receipt Decision": r.get("receipt_disposition"),
            "MetLAB": r.get("metallurgical_status"),
            "Dimensional": r.get("dimensional_status"),
            "Quality Decision": r.get("quality_disposition"),
            "Status": r.get("status"),
        } for r in rows]))
        st.page_link(st.session_state["_qsms_pages"]["inward-records"], label="Open Material Inward Records and Actions", icon=":material/open_in_new:", width="stretch")


    with tabs[2]:
        rows = _rows(repo, "v_qsms_osp_register", order_by="created_at", desc=True)
        disposition_cards([
            {"label": "Total OSP Jobs", "value": len(rows)},
            {"label": "At Vendor", "value": sum(str(r.get("status")) == "AT_VENDOR" for r in rows)},
            {"label": "Inspection Pending", "value": sum(str(r.get("status")) == "PART_RECEIVED" for r in rows)},
            {"label": "Released", "value": sum(str(r.get("status")) == "COMPLETED" for r in rows)},
        ])
        section_bar("OSP TRANSACTION REGISTER")
        _table(pd.DataFrame([{
            "OSP Job": r.get("osp_job_number"), "Material Out Date": r.get("dispatch_date"),
            "Heat Number": r.get("heat_number"), "Part Number": r.get("part_number"),
            "OSP Vendor": r.get("vendor_name"), "Process": r.get("process_name"),
            "Out Qty pcs": r.get("quantity_dispatched"), "Vendor Batch": r.get("vendor_batch_number"),
            "Sample Gate": r.get("sample_gate_status"), "OSP Inward": r.get("receipt_number"),
            "Inward Qty pcs": r.get("quantity_received"), "Receipt Decision": r.get("receipt_quality_disposition"),
            "Production Available pcs": r.get("production_available_quantity"), "Status": r.get("status"),
        } for r in rows]))
        st.page_link(st.session_state["_qsms_pages"]["osp-records"], label="Open OSP Records and Actions", icon=":material/open_in_new:", width="stretch")

    with tabs[3]:
        rows = _rows(repo, "inspection_reports", eq={"report_type": "DIMENSIONAL"}, order_by="created_at", desc=True)
        section_bar("DIMENSIONAL INSPECTION REGISTER")
        _table(pd.DataFrame([{
            "Report Number": r.get("report_number"),
            "Date": r.get("inspection_date"),
            "Part Number": part_map.get(str(r.get("part_id"))),
            "Heat Number": r.get("heat_number"),
            "Sample Size": r.get("sample_size"),
            "Result": r.get("overall_result"),
            "Disposition": r.get("disposition"),
            "Workflow": r.get("status"),
            "Reason": r.get("disposition_reason"),
        } for r in rows]))
        st.page_link(st.session_state["_qsms_pages"]["dimensional-records"], label="Open Dimensional Records and Actions", icon=":material/open_in_new:", width="stretch")

    with tabs[4]:
        rows = _rows(repo, "lab_tests", eq={"test_type": "METLAB"}, order_by="created_at", desc=True)
        section_bar("METLAB REGISTER")
        _table(pd.DataFrame([{
            "Report Number": r.get("report_number"),
            "Date": r.get("test_date"),
            "Part Number": part_map.get(str(r.get("part_id"))),
            "Heat Number": r.get("heat_number"),
            "Sample Reference": r.get("sample_reference"),
            "Result": r.get("overall_result"),
            "Disposition": r.get("disposition"),
            "Workflow": r.get("status"),
            "Reason": r.get("disposition_reason"),
        } for r in rows]))
        st.page_link(st.session_state["_qsms_pages"]["metlab-records"], label="Open MetLAB Records and Actions", icon=":material/open_in_new:", width="stretch")

    with tabs[5]:
        rows = _rows(repo, "inspection_plans", order_by="updated_at", desc=True)
        section_bar("INSPECTION LAYOUT REGISTER")
        _table(pd.DataFrame([{
            "Layout Name": r.get("layout_name"),
            "Layout Type": r.get("layout_type"),
            "Plan Number": r.get("plan_number"),
            "Revision": r.get("revision"),
            "Part Number": part_map.get(str(r.get("part_id"))),
            "Status": r.get("status"),
            "Effective Date": r.get("effective_date"),
        } for r in rows]))
        st.page_link(st.session_state["_qsms_pages"]["inspection-layout-records"], label="Open Inspection Layout Records and Actions", icon=":material/open_in_new:", width="stretch")

    with tabs[6]:
        grade_rows = _rows(repo, "material_grades", order_by="grade_code")
        employee_rows = _rows(repo, "employees", order_by="employee_code")
        reference_rows = parties
        section_bar("MASTER RECORD STATUS")
        _table(pd.DataFrame([
            {"Module": "Part Master", "Code / Number": r.get("part_number"), "Name": r.get("part_name"), "Status": r.get("status")} for r in parts
        ] + [
            {"Module": "Material Grade", "Code / Number": r.get("grade_code"), "Name": r.get("material_number"), "Status": r.get("status")} for r in grade_rows
        ] + [
            {"Module": "Reference Master", "Code / Number": r.get("party_code"), "Name": r.get("party_name"), "Status": r.get("status")} for r in reference_rows
        ] + [
            {"Module": "Employee Master", "Code / Number": r.get("employee_code"), "Name": f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip(), "Status": r.get("status")} for r in employee_rows
        ]), height=620)
        c1, c2, c3, c4 = st.columns(4, gap="small")
        with c1: st.page_link(st.session_state["_qsms_pages"]["part-records"], label="Part Records", width="stretch")
        with c2: st.page_link(st.session_state["_qsms_pages"]["grade-records"], label="Grade Records", width="stretch")
        with c3: st.page_link(st.session_state["_qsms_pages"]["reference-records"], label="Reference Records", width="stretch")
        with c4: st.page_link(st.session_state["_qsms_pages"]["employee-records"], label="Employee Records", width="stretch")

    with tabs[7]:
        render_heat_ledger(embedded=True)

