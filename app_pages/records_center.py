from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st
from core.ui import portal_table

from core.access import current_permissions
from core.delete_service import password_delete_panel, password_transaction_delete_panel
from core.repository import Repository
from core.record_audit import annotate_transaction_rows
from core.reporting import controlled_record_pdf_bytes, safe_excel_sheet_name
from core.ui import disposition_cards, page_header, section_bar, style_status_dataframe, subpage_navigation


def _rows(repo: Repository, table: str, **kwargs) -> list[dict]:
    try:
        return repo.select(table, limit=3000, **kwargs)
    except Exception as exc:
        st.error(f"Could not load {table}: {exc}")
        return []


def _map(rows: list[dict], key: str, value: str) -> dict[str, str]:
    return {str(row.get(key)): str(row.get(value) or "") for row in rows}


def _table(frame: pd.DataFrame, *, height: int = 560, pdf_title: str = "QCMS Record Register", pdf_key: str = "register") -> None:
    if frame.empty:
        st.info("No records are available for this register.")
        return
    portal_table(style_status_dataframe(frame), hide_index=True, width="stretch", height=height)
    # PDF print is intentionally available to every user who can view the register.
    pdf_bytes = controlled_record_pdf_bytes(pdf_title, {"Record Count": len(frame)}, {pdf_title: frame})
    st.download_button(
        "Print / Download PDF", data=pdf_bytes, file_name=f"{pdf_key}.pdf",
        mime="application/pdf", icon=":material/picture_as_pdf:", width="stretch", key=f"records_pdf_{pdf_key}",
    )



def _excel_bytes(frame: pd.DataFrame, sheet_name: str) -> bytes:
    output = BytesIO()
    safe_name = safe_excel_sheet_name(sheet_name)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=safe_name)
        worksheet = writer.sheets[safe_name]
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
        "QCMS RMTC": row.get("rmtc_number"),
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
    _table(frame, height=620, pdf_title="Heat Steel Ledger", pdf_key=f"QCMS_Heat_Steel_Ledger_{selected_key or 'ALL_HEATS'}")
    if not frame.empty:
        file_suffix = selected_key or "ALL_HEATS"
        st.download_button(
            "Download Heat Steel Ledger",
            data=_excel_bytes(frame, "Heat Steel Ledger"),
            file_name=f"QCMS_Heat_Steel_Ledger_{file_suffix}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            width="stretch",
            key=f"download_heat_ledger_{file_suffix}_{'embedded' if embedded else 'page'}",
        )




UNIVERSAL_RECORD_TABLES: dict[str, tuple[str, str]] = {
    "Part Master": ("parts", "PART_MASTER"),
    "Part Raw Material Details": ("part_raw_material_details", "PART_MASTER"),
    "Part Supplier Technical Data": ("part_raw_material_technical_data", "PART_MASTER"),
    "Part Supplier Price History": ("part_supplier_price_history", "PART_MASTER"),
    "Material Grades": ("material_grades", "MATERIAL_GRADE"),
    "Reference Parties / Suppliers / Customers": ("parties", "REFERENCE_MASTERS"),
    "Processes": ("processes", "REFERENCE_MASTERS"),
    "Inspection Stages": ("inspection_stages", "REFERENCE_MASTERS"),
    "Company Branches": ("company_branches", "REFERENCE_MASTERS"),
    "Employees": ("employees", "EMPLOYEE_MASTER"),
    "Inspection Layouts": ("inspection_plans", "INSPECTION_LAYOUTS"),
    "RMTC": ("rmtc_approvals", "RMTC_ENTRY"),
    "RMTC Part Worksheets": ("rmtc_part_approvals", "RMTC_ENTRY"),
    "Material Inward": ("inward_lots", "MATERIAL_INWARD"),
    "OSP Jobs": ("osp_jobs", "OSP_TRANSACTIONS"),
    "OSP Inward Receipts": ("osp_receipts", "OSP_TRANSACTIONS"),
    "Production Batches": ("production_batches", "OSP_TRANSACTIONS"),
    "Dimensional Reports": ("inspection_reports", "DIMENSIONAL_REPORT"),
    "MetLAB Reports": ("lab_tests", "METLAB_REPORT"),
    "NPD Process Flows": ("npd_process_flows", "NPD_APQP"),
    "NPD Orders / Status": ("npd_orders", "NPD_APQP"),
    "PPAP Projects": ("ppap_projects", "NPD_APQP"),
    "QC Calculation Records": ("qc_calculation_records", "QC_CALCULATION_TOOLS"),
    "Quality Complaints": ("quality_complaints", "COMPLAINT_MANAGEMENT"),
    "Customer Orders / Schedules": ("supply_customer_orders", "SUPPLY_CHAIN"),
    "Purchase Orders": ("supply_purchase_orders", "SUPPLY_CHAIN"),
    "Purchase Order Items": ("supply_purchase_order_items", "SUPPLY_CHAIN"),
    "Supplier PO Confirmations": ("supply_po_confirmations", "SUPPLY_CHAIN"),
    "Opening Stock": ("supply_opening_stock", "SUPPLY_CHAIN"),
    "RM Purchase Orders": ("supply_rm_purchase_orders", "SUPPLY_CHAIN"),
    "RM Receipts": ("supply_rm_receipts", "SUPPLY_CHAIN"),
    "RM Dispatch to Forging": ("supply_rm_dispatches", "SUPPLY_CHAIN"),
    "Forging Orders": ("supply_forging_orders", "SUPPLY_CHAIN"),
    "Forging Receipts": ("supply_forging_receipts", "SUPPLY_CHAIN"),
    "Supply Chain Downstream Events": ("supply_downstream_events", "SUPPLY_CHAIN"),
}

MASTER_DELETE_TABLES: dict[str, tuple[str, str]] = {
    "Part Master": ("parts", "PART_MASTER"),
    "Material Grade": ("material_grades", "MATERIAL_GRADE"),
    "Reference Party": ("parties", "REFERENCE_MASTERS"),
    "Process": ("processes", "REFERENCE_MASTERS"),
    "Inspection Stage": ("inspection_stages", "REFERENCE_MASTERS"),
    "Company Branch": ("company_branches", "REFERENCE_MASTERS"),
    "Employee": ("employees", "EMPLOYEE_MASTER"),
    "Inspection Layout": ("inspection_plans", "INSPECTION_LAYOUTS"),
}

TRANSACTION_DELETE_TABLES: dict[str, tuple[str, str]] = {
    "Customer Order / Schedule": ("supply_customer_orders", "SUPPLY_CHAIN"),
    "Purchase Order": ("supply_purchase_orders", "SUPPLY_CHAIN"),
    "Supplier PO Confirmation": ("supply_po_confirmations", "SUPPLY_CHAIN"),
    "OSP Transaction / Job": ("osp_jobs", "OSP_TRANSACTIONS"),
    "OSP Inward Receipt": ("osp_receipts", "OSP_TRANSACTIONS"),
    "RM Purchase Order": ("supply_rm_purchase_orders", "SUPPLY_CHAIN"),
    "RM Receipt": ("supply_rm_receipts", "SUPPLY_CHAIN"),
    "RM Dispatch to Forging": ("supply_rm_dispatches", "SUPPLY_CHAIN"),
    "Forging Order": ("supply_forging_orders", "SUPPLY_CHAIN"),
    "Forging Receipt": ("supply_forging_receipts", "SUPPLY_CHAIN"),
    "Supply Chain Event": ("supply_downstream_events", "SUPPLY_CHAIN"),
    "RMTC": ("rmtc_approvals", "RMTC_ENTRY"),
    "Material Inward": ("inward_lots", "MATERIAL_INWARD"),
    "Dimensional Report": ("inspection_reports", "DIMENSIONAL_REPORT"),
    "MetLAB Report": ("lab_tests", "METLAB_REPORT"),
    "NPD Order": ("npd_orders", "NPD_APQP"),
    "NPD Process Flow": ("npd_process_flows", "NPD_APQP"),
    "PPAP Project": ("ppap_projects", "NPD_APQP"),
    "Process Flow Diagram": ("pfd_headers", "NPD_APQP"),
    "PFMEA": ("pfmea_headers", "NPD_APQP"),
    "Control Plan": ("control_plan_headers", "NPD_APQP"),
    "SPC Study": ("spc_studies", "NPD_APQP"),
    "MSA Study": ("msa_studies", "NPD_APQP"),
    "Capacity Study": ("capacity_studies", "NPD_APQP"),
    "QC Calculation": ("qc_calculation_records", "QC_CALCULATION_TOOLS"),
    "Quality Complaint": ("quality_complaints", "COMPLAINT_MANAGEMENT"),
}



def _reference_key_for_party(record: dict) -> str:
    raw = record.get("party_types") or record.get("party_type") or []
    if isinstance(raw, str):
        values = [piece.strip().upper() for piece in raw.replace(";", ",").split(",") if piece.strip()]
    else:
        values = [str(piece).strip().upper() for piece in (raw or []) if str(piece).strip()]
    mapping = {
        "CUSTOMER": "customers", "SUPPLIER": "suppliers", "STEEL_MILL": "steel_mills",
        "STEEL MILL": "steel_mills", "OSP_VENDOR": "osp_vendors", "OSP VENDOR": "osp_vendors",
    }
    return next((mapping[value] for value in values if value in mapping), "suppliers")


def _open_selected_record_for_edit(table: str, record: dict) -> None:
    """Route a Records Centre selection to its controlled source editor.

    This is deliberately navigation-only: each source module keeps its own workflow,
    approval and genealogy rules.  Records Centre therefore exposes one consistent
    Edit action without creating a dangerous generic database editor.
    """
    pages = st.session_state.get("_qsms_pages") or {}
    record_id = str(record.get("id") or "")
    route = None
    if table in {"parts", "part_raw_material_details", "part_raw_material_technical_data", "part_supplier_price_history"}:
        part_id = record_id if table == "parts" else str(record.get("part_id") or "")
        st.session_state["edit_part_id"] = part_id; route = "part-entry"
    elif table == "material_grades":
        st.session_state["edit_grade_id"] = record_id; route = "grade-entry"
    elif table == "parties":
        st.session_state["edit_reference_id"] = record_id
        st.session_state["edit_reference_key"] = _reference_key_for_party(record); route = "reference-entry"
    elif table == "processes":
        st.session_state["edit_process_id"] = record_id; route = "process-entry"
    elif table == "inspection_stages":
        st.session_state["edit_reference_id"] = record_id; st.session_state["edit_reference_key"] = "inspection_stages"; route = "reference-entry"
    elif table == "company_branches":
        st.session_state["company_branch_edit_select"] = record_id; route = "company-branch-entry"
    elif table == "employees":
        st.session_state["edit_employee_id"] = record_id; route = "employee-entry"
    elif table == "inspection_plans":
        st.session_state["edit_inspection_layout_id"] = record_id; route = "inspection-layout-entry"
    elif table in {"rmtc_approvals", "rmtc_part_approvals"}:
        rid = record_id if table == "rmtc_approvals" else str(record.get("rmtc_approval_id") or "")
        st.session_state["edit_rmtc_id"] = rid; st.session_state["rmtc_entry_mode"] = "edit"; route = "rmtc-entry"
    elif table == "inward_lots":
        st.session_state["edit_inward_id"] = record_id; route = "inward-entry"
    elif table == "osp_jobs":
        st.session_state["osp_material_out_manage_id"] = record_id; route = "osp-material-out"
    elif table == "osp_receipts":
        st.session_state["osp_inward_manage_id"] = record_id; route = "osp-inward"
    elif table == "production_batches":
        route = "osp-records"
    elif table == "inspection_reports":
        st.session_state["edit_dimensional_id"] = record_id; route = "dimensional-entry"
    elif table == "lab_tests":
        st.session_state["edit_metlab_id"] = record_id; route = "metlab-entry"
    elif table == "npd_orders":
        st.session_state["npd_order_edit"] = record_id; route = "npd-status"
    elif table == "npd_process_flows":
        if record.get("part_id"): st.session_state["npd_flow_part"] = str(record.get("part_id"))
        route = "npd-process-flow"
    elif table == "ppap_projects":
        st.session_state["apqp_project_edit_request_id"] = record_id; route = "apqp"
    elif table == "qc_calculation_records":
        route = "qc-calculation-records"
    elif table == "quality_complaints":
        complaint_type = str(record.get("complaint_type") or "CUSTOMER").upper()
        st.session_state[f"selected_{complaint_type.lower()}_complaint"] = record_id
        route = "supplier-complaint" if complaint_type == "SUPPLIER" else "customer-complaint"
    elif table == "supply_customer_orders":
        st.session_state["supply_customer_order_edit_select"] = record_id; route = "supply-customer-orders"
    elif table in {"supply_purchase_orders", "supply_purchase_order_items", "supply_po_confirmations"}:
        po_id = record_id if table == "supply_purchase_orders" else str(record.get("purchase_order_id") or "")
        st.session_state["supply_po_edit_request_id"] = po_id; route = "supply-purchase-orders"
    elif table == "supply_opening_stock":
        st.session_state["opening_stock_edit_select"] = record_id; route = "supply-opening-stock"
    elif table == "supply_rm_purchase_orders":
        st.session_state["supply_rm_po_edit_select"] = record_id; route = "supply-rm-procurement"
    elif table == "supply_rm_receipts":
        inward_id = str(record.get("inward_lot_id") or "")
        if inward_id:
            st.session_state["edit_inward_id"] = inward_id; route = "inward-entry"
        else:
            route = "supply-rm-receipt"
    elif table == "supply_rm_dispatches":
        st.session_state["supply_rm_dispatch_edit_select"] = record_id; route = "supply-rm-dispatch"
    elif table == "supply_forging_orders":
        st.session_state["supply_forging_order_edit_edit_select"] = record_id; route = "supply-forging"
    elif table == "supply_forging_receipts":
        st.session_state["supply_forging_receipt_edit_edit_select"] = record_id; route = "supply-forging"
    elif table == "supply_downstream_events":
        st.session_state["supply_downstream_edit_edit_select"] = record_id; route = "supply-downstream"
    if route and route in pages:
        st.switch_page(pages[route])
    else:
        st.warning("This child/detail record is edited through its parent source module. Open the related module from the main navigation.")


def _generic_record_label(row: dict) -> str:
    candidates = (
        "part_number", "fsi_part_number", "po_number", "order_number", "customer_order_no", "rmtc_number",
        "inward_number", "report_number", "osp_job_number", "employee_code", "grade_code", "party_code",
        "process_code", "plan_number", "complaint_number", "flow_number", "project_number", "supplier_order_no",
        "receipt_number", "event_reference", "name", "part_name", "party_name", "first_name",
    )
    values = [str(row.get(key) or "").strip() for key in candidates if str(row.get(key) or "").strip()]
    label = " · ".join(values[:3])
    return label or str(row.get("id") or "Record")


def _pdf_safe_value(value: object) -> object:
    if isinstance(value, dict):
        return "; ".join(f"{key}: {item}" for key, item in value.items())
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    return value


def render_universal_pdf_center(repo: Repository) -> None:
    section_bar("UNIVERSAL RECORD PDF DOWNLOAD", "Select any business module register and download the selected record or the full register as a controlled QCMS PDF.")
    names = list(UNIVERSAL_RECORD_TABLES)
    selected_name = st.selectbox("Record / Entry Type", names, key="universal_pdf_table")
    table, module_key = UNIVERSAL_RECORD_TABLES[selected_name]
    perms = current_permissions(module_key)
    if not perms.get("can_view", False):
        st.warning("You do not have View permission for this record type.")
        return
    rows = annotate_transaction_rows(repo, _rows(repo, table, order_by="created_at", desc=True))
    search = st.text_input("Search selected register", key=f"universal_search_{table}")
    if search:
        rows = [row for row in rows if search.casefold() in " ".join(str(value or "") for value in row.values()).casefold()]
    if not rows:
        st.info("No records are available for this selection.")
        return
    register = pd.DataFrame([{key: _pdf_safe_value(value) for key, value in row.items() if key not in {"tenant_id"}} for row in rows])
    portal_table(register, hide_index=True, width="stretch", height=420)
    register_pdf = controlled_record_pdf_bytes(
        f"{selected_name.upper()} REGISTER", {"Record Count": len(register)}, {selected_name: register}
    )
    st.download_button(
        "Download Full Register PDF", register_pdf, file_name=f"QCMS_{table}_Register.pdf",
        mime="application/pdf", width="stretch", key=f"universal_register_pdf_{table}",
    )
    labels = {str(row.get("id")): _generic_record_label(row) for row in rows if row.get("id")}
    if labels:
        selected_id = st.selectbox("Selected Record", list(labels), format_func=lambda value: labels[value], key=f"universal_record_{table}")
        record = next(row for row in rows if str(row.get("id")) == selected_id)
        header = {
            str(key).replace("_", " ").title(): _pdf_safe_value(value)
            for key, value in record.items()
            if key not in {"tenant_id"} and value not in (None, "", [], {})
        }
        record_pdf = controlled_record_pdf_bytes(
            f"{selected_name.upper()} RECORD", header, record_number=_generic_record_label(record)
        )
        st.download_button(
            "Download Selected Record PDF", record_pdf, file_name=f"QCMS_{table}_{selected_id}.pdf",
            mime="application/pdf", width="stretch", key=f"universal_record_pdf_{table}_{selected_id}",
        )
        if perms.get("can_edit", False):
            if st.button(
                "Open Selected Record for Controlled Edit", icon=":material/edit:", width="stretch",
                key=f"universal_edit_{table}_{selected_id}",
                help="Opens the source module so its approval, audit and genealogy rules remain enforced.",
            ):
                _open_selected_record_for_edit(table, record)


def render_master_delete_center(repo: Repository) -> None:
    section_bar("PASSWORD-PROTECTED MASTER DELETE", "Delete is available only when Delete/Archive permission is assigned. Current QCMS password and confirmation are always required.")
    selection = st.selectbox("Master Type", list(MASTER_DELETE_TABLES), key="master_delete_type")
    table, module_key = MASTER_DELETE_TABLES[selection]
    rows = _rows(repo, table, order_by="created_at", desc=True)
    perms = current_permissions(module_key)
    password_delete_panel(
        repo=repo, table=table, rows=rows, labeler=_generic_record_label,
        key=f"records_center_delete_{table}", can_delete=bool(perms.get("can_archive")),
        title=f"Delete {selection}",
        help_text="Permanent deletion requires your current QCMS password. Linked records are protected by database foreign-key controls.",
    )


def render_transaction_delete_center(repo: Repository) -> None:
    section_bar(
        "PASSWORD-PROTECTED TRANSACTION DELETE",
        "Delete/Archive permission is module-controlled. Deletion is audited and database genealogy prevents removal of a record that already has downstream usage.",
    )
    selection = st.selectbox("Transaction Type", list(TRANSACTION_DELETE_TABLES), key="transaction_delete_type")
    table, module_key = TRANSACTION_DELETE_TABLES[selection]
    rows = _rows(repo, table, order_by="created_at", desc=True)
    perms = current_permissions(module_key)
    password_transaction_delete_panel(
        repo=repo, table=table, rows=rows, labeler=_generic_record_label,
        key=f"records_center_transaction_delete_{table}", can_delete=bool(perms.get("can_archive")),
        title=f"Delete {selection}",
        help_text=(
            "Current QCMS password and Delete/Archive permission are mandatory. "
            "Records with dependent quality, receipt, production, dispatch or genealogy rows are not deleted; QCMS will tell you which linked stage must be handled first."
        ),
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
    fsi_part_map = _map(parts, "id", "fsi_part_number")
    part_name_map = _map(parts, "id", "part_name")
    party_map = _map(parties, "id", "party_name")

    tabs = st.tabs(["RMTC", "Material Inward", "OSP Transactions", "Dimensional", "MetLAB", "Layouts", "Masters", "Heat Steel Ledger", "Universal PDFs", "Delete Transactions"])

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
            "FSI Part Number": fsi_part_map.get(str(r.get("part_id"))),
            "Supplier": party_map.get(str(r.get("supplier_id"))),
            "Steel Mill": party_map.get(str(r.get("steel_mill_id"))),
            "Steel Qty kg": r.get("certificate_quantity"),
            "Validation": r.get("validation_result"),
            "Workflow": r.get("status"),
            "Final Decision": r.get("disposition"),
            "Created": r.get("created_at"),
        } for r in rows]), pdf_title="RMTC Register", pdf_key="QCMS_RMTC_Register")
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
            "Part Number": r.get("part_number"), "FSI Part Number": fsi_part_map.get(str(r.get("part_id"))),
            "Part Description": r.get("part_name"),
            "Heat Number": r.get("heat_number"),
            "Steel kg": r.get("steel_quantity_kg") or r.get("quantity_received"),
            "Production pcs": r.get("production_quantity_pcs"),
            "Receipt Decision": r.get("receipt_disposition"),
            "MetLAB": r.get("metallurgical_status"),
            "Dimensional": r.get("dimensional_status"),
            "Quality Decision": r.get("quality_disposition"),
            "Status": r.get("status"),
        } for r in rows]), pdf_title="Material Inward Register", pdf_key="QCMS_Material_Inward_Register")
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
            "Heat Number": r.get("heat_number"), "Part Number": r.get("part_number"), "FSI Part Number": fsi_part_map.get(str(r.get("part_id"))),
            "OSP Vendor": r.get("vendor_name"), "Process": r.get("process_name"),
            "Out Qty pcs": r.get("quantity_dispatched"), "Vendor Batch": r.get("vendor_batch_number"),
            "Sample Gate": r.get("sample_gate_status"), "OSP Inward": r.get("receipt_number"),
            "Inward Qty pcs": r.get("quantity_received"), "Receipt Decision": r.get("receipt_quality_disposition"),
            "Production Available pcs": r.get("production_available_quantity"), "Status": r.get("status"),
        } for r in rows]), pdf_title="OSP Transaction Register", pdf_key="QCMS_OSP_Transaction_Register")
        st.page_link(st.session_state["_qsms_pages"]["osp-records"], label="Open OSP Records and Actions", icon=":material/open_in_new:", width="stretch")

    with tabs[3]:
        rows = _rows(repo, "inspection_reports", eq={"report_type": "DIMENSIONAL"}, order_by="created_at", desc=True)
        section_bar("DIMENSIONAL INSPECTION REGISTER")
        _table(pd.DataFrame([{
            "Report Number": r.get("report_number"),
            "Date": r.get("inspection_date"),
            "Part Number": part_map.get(str(r.get("part_id"))), "FSI Part Number": fsi_part_map.get(str(r.get("part_id"))),
            "Heat Number": r.get("heat_number"),
            "Sample Size": r.get("sample_size"),
            "Result": r.get("overall_result"),
            "Disposition": r.get("disposition"),
            "Workflow": r.get("status"),
            "Reason": r.get("disposition_reason"),
        } for r in rows]), pdf_title="Dimensional Inspection Register", pdf_key="QCMS_Dimensional_Inspection_Register")
        st.page_link(st.session_state["_qsms_pages"]["dimensional-records"], label="Open Dimensional Records and Actions", icon=":material/open_in_new:", width="stretch")

    with tabs[4]:
        rows = _rows(repo, "lab_tests", eq={"test_type": "METLAB"}, order_by="created_at", desc=True)
        section_bar("METLAB REGISTER")
        _table(pd.DataFrame([{
            "Report Number": r.get("report_number"),
            "Date": r.get("test_date"),
            "Part Number": part_map.get(str(r.get("part_id"))), "FSI Part Number": fsi_part_map.get(str(r.get("part_id"))),
            "Heat Number": r.get("heat_number"),
            "Sample Reference": r.get("sample_reference"),
            "Result": r.get("overall_result"),
            "Disposition": r.get("disposition"),
            "Workflow": r.get("status"),
            "Reason": r.get("disposition_reason"),
        } for r in rows]), pdf_title="MetLAB Register", pdf_key="QCMS_MetLAB_Register")
        st.page_link(st.session_state["_qsms_pages"]["metlab-records"], label="Open MetLAB Records and Actions", icon=":material/open_in_new:", width="stretch")

    with tabs[5]:
        rows = _rows(repo, "inspection_plans", order_by="updated_at", desc=True)
        section_bar("INSPECTION LAYOUT REGISTER")
        _table(pd.DataFrame([{
            "Layout Name": r.get("layout_name"),
            "Layout Type": r.get("layout_type"),
            "Plan Number": r.get("plan_number"),
            "Revision": r.get("revision"),
            "Part Number": part_map.get(str(r.get("part_id"))), "FSI Part Number": fsi_part_map.get(str(r.get("part_id"))),
            "Status": r.get("status"),
            "Effective Date": r.get("effective_date"),
        } for r in rows]), pdf_title="Inspection Layout Register", pdf_key="QCMS_Inspection_Layout_Register")
        st.page_link(st.session_state["_qsms_pages"]["inspection-layout-records"], label="Open Inspection Layout Records and Actions", icon=":material/open_in_new:", width="stretch")

    with tabs[6]:
        grade_rows = _rows(repo, "material_grades", order_by="grade_code")
        employee_rows = _rows(repo, "employees", order_by="employee_code")
        reference_rows = parties
        section_bar("MASTER RECORD STATUS")
        _table(pd.DataFrame([
            {"Module": "Part Master", "Code / Number": r.get("part_number"), "FSI Part Number": r.get("fsi_part_number"), "Name": r.get("part_name"), "Status": r.get("status")} for r in parts
        ] + [
            {"Module": "Material Grade", "Code / Number": r.get("grade_code"), "Name": r.get("material_number"), "Status": r.get("status")} for r in grade_rows
        ] + [
            {"Module": "Reference Master", "Code / Number": r.get("party_code"), "Name": r.get("party_name"), "Status": r.get("status")} for r in reference_rows
        ] + [
            {"Module": "Employee Master", "Code / Number": r.get("employee_code"), "Name": f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip(), "Status": r.get("status")} for r in employee_rows
        ]), height=620, pdf_title="Master Record Status", pdf_key="QCMS_Master_Record_Status")
        c1, c2, c3, c4 = st.columns(4, gap="small")
        with c1: st.page_link(st.session_state["_qsms_pages"]["part-records"], label="Part Records", width="stretch")
        with c2: st.page_link(st.session_state["_qsms_pages"]["grade-records"], label="Grade Records", width="stretch")
        with c3: st.page_link(st.session_state["_qsms_pages"]["reference-records"], label="Reference Records", width="stretch")
        with c4: st.page_link(st.session_state["_qsms_pages"]["employee-records"], label="Employee Records", width="stretch")
        render_master_delete_center(repo)

    with tabs[7]:
        render_heat_ledger(embedded=True)

    with tabs[8]:
        render_universal_pdf_center(repo)

    with tabs[9]:
        render_transaction_delete_center(repo)

