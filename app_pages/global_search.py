from __future__ import annotations

from collections import OrderedDict
from typing import Any

import pandas as pd
import streamlit as st

from core.access import module_permissions
from core.auth import current_profile
from core.repository import Repository
from core.ui import disposition_cards, page_header, portal_table, section_bar, subpage_navigation


# Global Search intentionally uses the same tenant/RLS-scoped Repository and the
# effective QCMS permission engine.  A user never receives search results from a
# module they cannot View.
SEARCH_SOURCES: tuple[dict[str, Any], ...] = (
    {"table": "parts", "record_type": "Part Master", "module": "Masters", "module_key": "PART_MASTER", "columns": ("part_number", "fsi_part_number", "part_name", "drawing_number", "drawing_revision", "section_size", "manufacturing_route", "remarks")},
    {"table": "parties", "record_type": "Customer / Supplier / OSP Vendor", "module": "Masters", "module_key": "REFERENCE_MASTERS", "columns": ("party_code", "party_name", "country", "state", "city", "address", "contact_person", "email", "phone", "tax_identifier", "approval_status", "status", "remarks")},
    {"table": "material_grades", "record_type": "Material Grade", "module": "Masters", "module_key": "MATERIAL_GRADE", "columns": ("grade_code", "standard", "revision", "status", "remarks")},
    {"table": "processes", "record_type": "Process Master", "module": "Masters", "module_key": "REFERENCE_MASTERS", "columns": ("process_code", "process_name", "process_type", "cqi_standard", "status", "remarks")},
    {"table": "employees", "record_type": "Employee", "module": "Masters", "module_key": "EMPLOYEE_MASTER", "columns": ("employee_code", "first_name", "last_name", "email", "department", "designation", "plant", "mobile_number", "status")},
    {"table": "inspection_plans", "record_type": "Inspection Layout", "module": "Inspections", "module_key": "INSPECTION_LAYOUTS", "columns": ("plan_number", "revision", "layout_type", "layout_name", "report_title", "status")},
    {"table": "rmtc_approvals", "record_type": "RMTC", "module": "RMTC", "module_key": "RMTC_ENTRY", "columns": ("rmtc_number", "certificate_reference", "heat_number", "heat_code", "rm_section", "forging_route", "status", "remarks"), "part_fields": ("part_id",), "party_fields": ("supplier_id", "steel_mill_id")},
    {"table": "inward_lots", "record_type": "Material Inward", "module": "Inward", "module_key": "MATERIAL_INWARD", "columns": ("inward_number", "grn_number", "invoice_number", "heat_number", "heat_code", "metallurgical_status", "dimensional_status", "status", "remarks"), "part_fields": ("part_id",), "party_fields": ("supplier_id",)},
    {"table": "production_batches", "record_type": "Production / FSI Batch", "module": "OSP", "module_key": "OSP_TRANSACTIONS", "columns": ("batch_code", "heat_number", "heat_code", "vendor_batch_number", "work_order", "status", "remarks"), "part_fields": ("part_id",)},
    {"table": "osp_jobs", "record_type": "OSP Job / Material Out", "module": "OSP", "module_key": "OSP_TRANSACTIONS", "columns": ("osp_job_number", "dispatch_challan", "process_specification", "receipt_challan", "vendor_batch_number", "receipt_status", "inspection_status", "status", "receipt_remarks"), "part_fields": ("part_id",), "party_fields": ("vendor_id",)},
    {"table": "osp_receipts", "record_type": "OSP Inward Receipt", "module": "OSP", "module_key": "OSP_TRANSACTIONS", "columns": ("receipt_number", "receipt_challan", "vendor_invoice_number", "tc_number", "vendor_batch_number", "remarks")},
    {"table": "inspection_reports", "record_type": "Dimensional Report", "module": "Inspections", "module_key": "DIMENSIONAL_REPORT", "columns": ("report_number", "report_type", "inspector", "overall_result", "status", "remarks"), "part_fields": ("part_id",)},
    {"table": "lab_tests", "record_type": "MetLAB / Bend Test Report", "module": "Inspections", "module_key": "METLAB_REPORT", "columns": ("report_number", "test_type", "sample_reference", "specification_reference", "overall_result", "status", "remarks"), "part_fields": ("part_id",)},
    {"table": "quality_complaints", "record_type": "Quality Complaint", "module": "Complaints", "module_key": "COMPLAINT_MANAGEMENT", "columns": ("complaint_number", "complaint_type", "external_reference", "subject", "description", "severity", "status", "containment_action", "root_cause", "corrective_action", "verification_result", "closure_remarks", "debit_note_number", "commercial_remarks"), "part_fields": ("part_id",), "party_fields": ("party_id",)},
    {"table": "supply_customer_orders", "record_type": "Customer Order / Schedule", "module": "Supply Chain", "module_key": "SUPPLY_CHAIN", "columns": ("master_reference_no", "order_type", "customer_order_no", "order_position", "status", "remarks"), "part_fields": ("part_id",), "party_fields": ("customer_id", "forging_supplier_id")},
    {"table": "supply_purchase_orders", "record_type": "Purchase Order", "module": "Supply Chain", "module_key": "SUPPLY_CHAIN", "columns": ("po_number", "po_type", "requisitioner", "ship_via", "incoterm", "payment_term", "quotation_reference", "old_po_reference", "currency", "remarks", "special_instructions", "status"), "party_fields": ("supplier_id",)},
    {"table": "supply_rm_purchase_orders", "record_type": "RM Procurement Order", "module": "Supply Chain", "module_key": "SUPPLY_CHAIN", "columns": ("supplier_order_no", "status", "remarks"), "party_fields": ("rm_supplier_id",)},
    {"table": "supply_rm_receipts", "record_type": "RM Receipt", "module": "Supply Chain", "module_key": "SUPPLY_CHAIN", "columns": ("receipt_number", "heat_number", "supplier_challan", "remarks")},
    {"table": "supply_rm_dispatches", "record_type": "RM to Forging", "module": "Supply Chain", "module_key": "SUPPLY_CHAIN", "columns": ("dispatch_number", "heat_number", "challan_number", "vehicle_number", "remarks"), "party_fields": ("forging_supplier_id",)},
    {"table": "supply_forging_orders", "record_type": "Forging Order", "module": "Supply Chain", "module_key": "SUPPLY_CHAIN", "columns": ("supplier_order_no", "status", "remarks"), "party_fields": ("forging_supplier_id",)},
    {"table": "supply_forging_receipts", "record_type": "Forging Receipt", "module": "Supply Chain", "module_key": "SUPPLY_CHAIN", "columns": ("receipt_number", "remarks"), "party_fields": ("forging_supplier_id",)},
    {"table": "supply_downstream_events", "record_type": "Machining / FG / Dispatch", "module": "Supply Chain", "module_key": "SUPPLY_CHAIN", "columns": ("event_type", "reference_no", "invoice_no", "asn_no", "remarks")},
    {"table": "npd_orders", "record_type": "NPD Order / Status", "module": "NPD & APQP", "module_key": "NPD_APQP", "columns": ("order_number", "status", "remarks"), "part_fields": ("part_id",), "party_fields": ("customer_id",)},
    {"table": "ppap_projects", "record_type": "PPAP / APQP Project", "module": "NPD & APQP", "module_key": "NPD_APQP", "columns": ("project_code", "submission_level", "reason", "coordinator", "status", "remarks"), "part_fields": ("part_id",), "party_fields": ("customer_id",)},
    {"table": "quality_assets", "record_type": "Gauge / Fixture / Quality Asset", "module": "Calibration & Validation", "module_key": "CALIBRATION_VALIDATION", "columns": ("asset_code", "asset_name", "asset_type", "manufacturer", "model", "serial_number", "range_text", "least_count", "location", "status", "remarks")},
    {"table": "quality_asset_calibration_records", "record_type": "Calibration / Validation Record", "module": "Calibration & Validation", "module_key": "CALIBRATION_VALIDATION", "columns": ("record_type", "result", "report_number", "certificate_number", "calibration_agency", "status", "remarks")},
    {"table": "standard_room_inspection_records", "record_type": "Standard Room Inspection", "module": "Calibration & Validation", "module_key": "CALIBRATION_VALIDATION", "columns": ("instrument_type", "heat_number", "batch_code", "report_number", "inspection_status", "program_reference", "status", "remarks"), "part_fields": ("part_id",)},
)


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(item) for item in value)
    return str(value or "")


def _reference(row: dict) -> str:
    for key in (
        "part_number", "fsi_part_number", "party_code", "grade_code", "process_code", "employee_code",
        "plan_number", "rmtc_number", "inward_number", "batch_code", "osp_job_number", "receipt_number",
        "report_number", "complaint_number", "master_reference_no", "customer_order_no", "po_number",
        "supplier_order_no", "dispatch_number", "reference_no", "order_number", "project_code", "asset_code",
        "certificate_number", "tc_number", "heat_number",
    ):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return str(row.get("id") or "Record")


def _status(row: dict) -> str:
    for key in ("status", "disposition", "overall_result", "inspection_status", "receipt_status", "result", "approval_status"):
        value = str(row.get(key) or "").strip()
        if value:
            return value.replace("_", " ").title()
    return ""


def _detail(row: dict, *, part_map: dict[str, str], party_map: dict[str, str]) -> str:
    values: list[str] = []
    for key in ("part_id", "customer_id", "supplier_id", "party_id", "vendor_id", "forging_supplier_id", "rm_supplier_id", "steel_mill_id"):
        raw = str(row.get(key) or "")
        label = part_map.get(raw) if key == "part_id" else party_map.get(raw)
        if label and label not in values:
            values.append(label)
    for key in (
        "part_name", "party_name", "subject", "heat_number", "heat_code", "vendor_batch_number", "batch_code",
        "sample_reference", "certificate_reference", "grn_number", "invoice_number", "invoice_no", "asn_no",
        "drawing_number", "layout_name", "report_title", "remarks",
    ):
        value = str(row.get(key) or "").strip()
        if value and value not in values:
            values.append(value)
        if len(values) >= 4:
            break
    return " · ".join(values[:4])


def _merge_rows(target: OrderedDict[str, dict], rows: list[dict]) -> None:
    for row in rows:
        record_id = str(row.get("id") or "")
        if record_id:
            target[record_id] = row


def _relationship_rows(repo: Repository, source: dict, part_ids: list[str], party_ids: list[str], limit: int) -> list[dict]:
    gathered: OrderedDict[str, dict] = OrderedDict()
    for field in source.get("part_fields") or ():
        if part_ids:
            _merge_rows(gathered, repo.select(source["table"], in_={field: part_ids[:50]}, limit=limit))
    for field in source.get("party_fields") or ():
        if party_ids:
            _merge_rows(gathered, repo.select(source["table"], in_={field: party_ids[:50]}, limit=limit))
    return list(gathered.values())


def search_everywhere(repo: Repository, profile: dict, query: str, *, per_source_limit: int = 40) -> list[dict]:
    """Search all major QCMS registers allowed by the current user's View rights.

    Direct text search is performed by Supabase for scale.  Part/party matches are
    also expanded through controlled foreign-key relationships, so a search for a
    Part Number, Customer or Supplier returns linked RMTC / Inward / OSP / Supply
    Chain / Quality records even where that human-readable text is stored only in
    the master table.
    """
    query = str(query or "").strip()
    if len(query) < 2:
        return []

    permission_cache: dict[str, bool] = {}
    def can_view(module_key: str) -> bool:
        if module_key not in permission_cache:
            permission_cache[module_key] = bool(module_permissions(profile, module_key, repo).get("can_view"))
        return permission_cache[module_key]

    # Resolve master matches once for relationship-aware search.
    part_rows = repo.select(
        "parts", search_columns=("part_number", "fsi_part_number", "part_name", "drawing_number", "drawing_revision", "remarks"),
        search_term=query, limit=50,
    ) if can_view("PART_MASTER") else []
    party_rows = repo.select(
        "parties", search_columns=("party_code", "party_name", "country", "state", "city", "contact_person", "email", "remarks"),
        search_term=query, limit=50,
    ) if can_view("REFERENCE_MASTERS") else []
    part_ids = [str(row.get("id")) for row in part_rows if row.get("id")]
    party_ids = [str(row.get("id")) for row in party_rows if row.get("id")]

    # Compact lookup labels enrich transaction results and make them searchable/readable.
    all_parts = repo.select("parts", limit=5000) if any(source.get("part_fields") for source in SEARCH_SOURCES) and can_view("PART_MASTER") else []
    all_parties = repo.select("parties", limit=5000) if any(source.get("party_fields") for source in SEARCH_SOURCES) and can_view("REFERENCE_MASTERS") else []
    part_map = {
        str(row.get("id")): " · ".join(v for v in (str(row.get("part_number") or "").strip(), str(row.get("fsi_part_number") or "").strip(), str(row.get("part_name") or "").strip()) if v)
        for row in all_parts if row.get("id")
    }
    party_map = {
        str(row.get("id")): " · ".join(v for v in (str(row.get("party_code") or "").strip(), str(row.get("party_name") or "").strip()) if v)
        for row in all_parties if row.get("id")
    }

    found: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for source in SEARCH_SOURCES:
        if not can_view(str(source["module_key"])):
            continue
        table = str(source["table"])
        rows_by_id: OrderedDict[str, dict] = OrderedDict()
        try:
            _merge_rows(rows_by_id, repo.select(table, search_columns=source["columns"], search_term=query, limit=per_source_limit))
            _merge_rows(rows_by_id, _relationship_rows(repo, source, part_ids, party_ids, per_source_limit))
        except Exception:
            # One optional register must never break Global Search. RLS/schema
            # protections remain authoritative; unavailable sources are skipped.
            continue

        for row in rows_by_id.values():
            row_id = str(row.get("id") or "")
            token = (table, row_id)
            if not row_id or token in seen:
                continue
            seen.add(token)
            relation_text = " ".join(
                [part_map.get(str(row.get(field) or ""), "") for field in source.get("part_fields") or ()]
                + [party_map.get(str(row.get(field) or ""), "") for field in source.get("party_fields") or ()]
            )
            # Direct Supabase matches are already valid. Relationship-expanded
            # rows are valid when the matched part/party name/id was the reason.
            direct_haystack = _text(row).casefold()
            if query.casefold() not in direct_haystack and query.casefold() not in relation_text.casefold():
                continue
            found.append({
                "key": f"{table}:{row_id}",
                "module": source["module"],
                "record_type": source["record_type"],
                "reference": _reference(row),
                "detail": _detail(row, part_map=part_map, party_map=party_map),
                "status": _status(row),
                "table": table,
                "record": row,
            })

    found.sort(key=lambda item: (str(item["module"]), str(item["record_type"]), str(item["reference"]).casefold()))
    return found


def _open_result(result: dict) -> None:
    # Records Centre keeps the controlled edit routing for every supported source
    # table; Bend Test is routed explicitly to its dedicated report entry page.
    table = str(result.get("table") or "")
    row = dict(result.get("record") or {})
    pages = st.session_state.get("_qsms_pages") or {}
    if table == "lab_tests":
        results = row.get("results") or {}
        method = str(results.get("inspection_method") or "").upper() if isinstance(results, dict) else ""
        fallback = " ".join(str(row.get(key) or "") for key in ("test_type", "remarks", "layout_name_snapshot")).upper()
        if method == "BEND_TEST" or "BEND TEST" in fallback:
            st.session_state["edit_metlab_id"] = str(row.get("id") or "")
            if "bend-test-entry" in pages:
                st.switch_page(pages["bend-test-entry"])
                return
    from app_pages.records_center import _open_selected_record_for_edit
    _open_selected_record_for_edit(table, row)


def render() -> None:
    subpage_navigation(("dashboard", "Dashboard", ":material/arrow_back:"), ("records-center", "Records Centre", ":material/table_view:"))
    page_header("Global Search", "Search Part, Heat, RMTC, Batch, Supplier, Customer, PO, Report and other QCMS records from one place.", "Permission-aware")

    repo = Repository()
    profile = current_profile() or {}
    incoming = str(st.session_state.pop("_qcms_global_search_pending_query", "") or "").strip()
    if incoming:
        st.session_state["qcms_global_search_page_query"] = incoming

    with st.form("qcms_global_search_page_form", border=False):
        c1, c2 = st.columns([8.6, 1.4], gap="small")
        query = c1.text_input(
            "Search QCMS",
            key="qcms_global_search_page_query",
            placeholder="Part No, FSI Part No, Heat, RMTC, FSI Batch, vendor batch, supplier, customer, PO, report...",
            label_visibility="collapsed",
        )
        submitted = c2.form_submit_button("Search", icon=":material/search:", type="primary", width="stretch")

    auto_search = bool(incoming)
    if submitted or auto_search:
        if len(str(query).strip()) < 2:
            st.warning("Enter at least 2 characters to search QCMS.")
            st.session_state["_qcms_global_search_results"] = []
        else:
            with st.spinner("Searching permitted QCMS masters and transactions..."):
                st.session_state["_qcms_global_search_results"] = search_everywhere(repo, profile, query)
                st.session_state["_qcms_global_search_last_query"] = str(query).strip()

    results = list(st.session_state.get("_qcms_global_search_results") or [])
    last_query = str(st.session_state.get("_qcms_global_search_last_query") or "").strip()
    if not last_query:
        st.info("Enter a search value. Global Search respects the employee's current module View permissions and Supabase tenant/RLS controls.")
        return

    module_count = len({str(item.get("module")) for item in results})
    disposition_cards([
        {"label": "Search", "value": last_query, "foot": "Current query"},
        {"label": "Matches", "value": len(results), "foot": "Across permitted registers"},
        {"label": "Modules", "value": module_count, "foot": "With matching records"},
        {"label": "Security", "value": "Permission Aware", "foot": "View rights + tenant RLS"},
    ])

    if not results:
        st.warning(f"No permitted QCMS records matched **{last_query}**. Try a Part Number, Heat Number, RMTC, Batch, PO, Supplier/Customer name or Report Number.")
        return

    modules = sorted({str(item["module"]) for item in results})
    selected_modules = st.multiselect("Filter Results by Module", modules, default=modules, key="qcms_global_search_module_filter")
    visible = [item for item in results if str(item["module"]) in selected_modules]

    section_bar("GLOBAL SEARCH RESULTS", f"{len(visible)} matching record(s). Select a result below to open its controlled source module.")
    display = pd.DataFrame([{
        "Module": item["module"],
        "Record Type": item["record_type"],
        "Reference": item["reference"],
        "Details": item["detail"],
        "Status / Result": item["status"],
    } for item in visible])
    portal_table(display, hide_index=True, width="stretch", height=min(620, 105 + max(1, len(display)) * 35))

    if visible:
        by_key = {str(item["key"]): item for item in visible}
        selected = st.selectbox(
            "Selected Search Result",
            list(by_key),
            format_func=lambda key: f"{by_key[key]['record_type']} · {by_key[key]['reference']} · {by_key[key]['detail']}",
            key="qcms_global_search_selected_result",
        )
        if st.button("Open Selected Record", icon=":material/open_in_new:", type="primary", width="stretch"):
            _open_result(by_key[selected])
