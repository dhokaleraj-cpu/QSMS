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
    {"table": "quality_assets", "record_type": "Gauge / Fixture / Quality Asset", "module": "Calibration & Validation", "module_key": "CALIBRATION_VALIDATION", "columns": ("asset_code", "asset_number", "asset_name", "asset_type", "manufacturer", "model", "serial_number", "range_text", "least_count", "location", "status", "remarks")},
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


AI_EXAMPLE_PROMPTS: tuple[str, ...] = (
    "Show all open Purchase Orders by supplier with total value",
    "Which parts have the most quality complaints this year? Chart it",
    "List Material Inward received in the last 30 days with heat numbers",
    "Monthly trend of MetLAB reports by result for 2026",
    "Overdue Forging Orders with expected date and supplier",
    "Everything about Part 40256626",
)


def _ai_settings() -> tuple[str, str, str]:
    """R15: (provider, api_key, model) — Gemini/Groq free tiers or Claude/OpenAI."""
    from core.config import _secret
    from core.ai_assistant import resolve_provider
    return resolve_provider(lambda name, default="": _secret(name, default))


def _render_ai_report(report, index: int) -> None:
    import plotly.express as px
    from core.ai_assistant import report_excel_bytes
    section_bar(report.title.upper(), f"{len(report.frame):,} row(s) · source: {report.dataset}")
    frame = report.frame
    chart = report.chart or {}
    x, y, kind = chart.get("x"), chart.get("y"), str(chart.get("type") or "bar")
    if x in frame.columns and y in frame.columns and not frame.empty:
        try:
            data = frame.copy(); data[y] = pd.to_numeric(data[y], errors="coerce")
            fig = px.pie(data, names=x, values=y) if kind == "pie" else (px.line(data.sort_values(x), x=x, y=y, markers=True) if kind == "line" else px.bar(data, x=x, y=y))
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10), title=report.title)
            st.plotly_chart(fig, width="stretch", key=f"qcms_ai_chart_{index}")
        except Exception as exc:
            st.caption(f"Chart could not be drawn: {exc}")
    display = frame.copy()
    for column in display.columns:
        if display[column].map(lambda v: isinstance(v, (dict, list))).any():
            display[column] = display[column].astype(str)
    portal_table(display, hide_index=True, width="stretch", height=min(520, 90 + max(1, len(display)) * 35))
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in report.title)[:60] or "QCMS_AI_Report"
    c1, c2 = st.columns(2, gap="small")
    try:
        c1.download_button("Download Excel", report_excel_bytes(report), file_name=f"{safe_name}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch", key=f"qcms_ai_xlsx_{index}")
    except Exception as exc:
        c1.caption(f"Excel export unavailable: {exc}")
    c2.download_button("Download CSV", display.to_csv(index=False).encode("utf-8"), file_name=f"{safe_name}.csv", mime="text/csv", width="stretch", key=f"qcms_ai_csv_{index}")


def _render_ai_assistant(repo: Repository, profile: dict) -> None:
    from core.ai_assistant import QCMSAIAssistant
    provider, api_key, model = _ai_settings()
    st.caption("Ask in plain English for any information, analysis or report. The assistant is read-only and uses only the modules you are permitted to view.")
    if not api_key:
        st.info(
            "**AI Assistant is not switched on yet.** FREE option (about 3 minutes, no credit card):\n\n"
            "1. Open **aistudio.google.com**, sign in with a Google account, click **Get API key → Create API key** and copy it (starts with `AIza`).\n"
            "2. On the Mac, open **Terminal** and run:  `bash /Users/dhokaleraj/QSMS/scripts/set_ai_key.sh`  — choose **1 (Gemini FREE)**, paste the key and press Enter.\n"
            "3. Restart QCMS (Ctrl+C in the Terminal running it, then start it again).\n"
            "4. For the online app: Streamlit Cloud → your app → **⋮ → Settings → Secrets** → paste the lines the script printed → **Save**.\n\n"
            "Other choices in the same script: Groq (free, open models), Claude or OpenAI (paid). Keyword Search (next tab) works without a key."
        )
        return
    from core.ai_assistant import PROVIDERS
    st.caption(f"Engine: {PROVIDERS[provider]['label']} · model `{model}`" + (" · free tiers are rate-limited and Google/Groq may use free-tier prompts to improve their services — avoid asking about confidential customer pricing." if provider in {"gemini", "groq"} else ""))
    history: list[dict] = st.session_state.setdefault("_qcms_ai_history", [])
    pick = st.pills("Examples", list(AI_EXAMPLE_PROMPTS), selection_mode="single", key="qcms_ai_example", label_visibility="collapsed")
    if pick and st.session_state.get("_qcms_ai_last_pick") != pick:
        st.session_state["_qcms_ai_last_pick"] = pick
        st.session_state["qcms_ai_prompt"] = pick
    with st.form("qcms_ai_form", border=False):
        prompt = st.text_area("Ask QCMS AI", key="qcms_ai_prompt", height=90, placeholder="e.g. Rejection quantity by supplier for forging receipts in Q3 2026 with a bar chart", label_visibility="collapsed")
        c1, c2 = st.columns([8, 2], gap="small")
        asked = c1.form_submit_button("Ask AI", icon=":material/auto_awesome:", type="primary", width="stretch")
        cleared = c2.form_submit_button("Clear", icon=":material/delete_sweep:", width="stretch")
    if cleared:
        st.session_state["_qcms_ai_history"] = []; history = []
    if asked and str(prompt or "").strip():
        permission_cache: dict[str, bool] = {}
        def can_view(module_key: str) -> bool:
            if module_key not in permission_cache:
                permission_cache[module_key] = bool(module_permissions(profile, module_key, repo).get("can_view"))
            return permission_cache[module_key]
        user_label = " ".join(v for v in (str(profile.get("full_name") or ""), str(profile.get("role") or "")) if v).strip()
        assistant = QCMSAIAssistant(repo, SEARCH_SOURCES, can_view, api_key=api_key, model=model, provider=provider, user_label=user_label)
        with st.spinner("QCMS AI is reading your permitted data and preparing the answer..."):
            answer = assistant.ask(str(prompt), history=[{"prompt": h["prompt"], "answer": h["answer"]} for h in history])
        history.append({"prompt": str(prompt).strip(), "answer": answer.text, "reports": answer.reports, "error": answer.error, "steps": answer.tool_calls, "model": answer.model})
        st.session_state["_qcms_ai_history"] = history[-10:]
    for index, turn in reversed(list(enumerate(st.session_state.get("_qcms_ai_history") or []))):
        with st.container(border=True):
            st.markdown(f"**You:** {turn['prompt']}")
            if turn.get("error"):
                st.error(turn["error"])
            if turn.get("answer"):
                st.markdown(turn["answer"])
            for r_index, report in enumerate(turn.get("reports") or []):
                _render_ai_report(report, index * 100 + r_index)
            if turn.get("steps"):
                with st.expander(f"How this answer was built ({len(turn['steps'])} data step(s) · {turn.get('model')})", expanded=False):
                    st.json(turn["steps"], expanded=False)


def render() -> None:
    subpage_navigation(("dashboard", "Dashboard", ":material/arrow_back:"), ("records-center", "Records Centre", ":material/table_view:"))
    page_header("Global Search", "Search everything: modules and screens, fields, and every record in the database (part, heat, PO, RMTC, batch, supplier, report...). Or ask QCMS AI.", "Everything · Permission-aware")

    repo = Repository()
    profile = current_profile() or {}
    from core.system_settings import ai_allowed, get_ai_mode
    ai_mode, _source = get_ai_mode(repo)
    if not ai_allowed(ai_mode, profile):
        # R13: System Administrator has disabled the AI Assistant (or limited it to admins).
        st.caption("AI Assistant is switched off by the System Administrator. Keyword Search is available below.")
        _render_keyword_search(repo, profile)
        return
    keyword_tab, ai_tab = st.tabs(["🔎 Search Everything", "✨ AI Assistant"])
    with keyword_tab:
        _render_keyword_search(repo, profile)
    with ai_tab:
        if ai_mode == "ADMIN_ONLY":
            st.caption("AI Assistant is currently enabled for System Administrators only (Admin → System Settings).")
        _render_ai_assistant(repo, profile)


def _render_keyword_search(repo: Repository, profile: dict) -> None:
    incoming = str(st.session_state.pop("_qcms_global_search_pending_query", "") or "").strip()
    if incoming:
        st.session_state["qcms_global_search_page_query"] = incoming

    with st.form("qcms_global_search_page_form", border=False):
        c1, c2 = st.columns([8.6, 1.4], gap="small")
        query = c1.text_input(
            "Search QCMS",
            key="qcms_global_search_page_query",
            placeholder="Anything: bend test, heat code, J5/16, part no, PO, RMTC, batch, supplier, customer, report...",
            label_visibility="collapsed",
        )
        submitted = c2.form_submit_button("Search", icon=":material/search:", type="primary", width="stretch")

    auto_search = bool(incoming)
    if submitted or auto_search:
        cleaned = str(query or "").strip()
        if len(cleaned) < 2:
            st.warning("Enter at least 2 characters to search QCMS.")
            st.session_state["_qcms_global_search_results"] = []
            st.session_state["_qcms_global_search_everything"] = None
        else:
            with st.spinner("Searching modules, fields and every permitted database record..."):
                st.session_state["_qcms_global_search_everything"] = _search_everything(repo, profile, cleaned)
                st.session_state["_qcms_global_search_last_query"] = cleaned
                if st.session_state["_qcms_global_search_everything"].get("records") is None:
                    st.session_state["_qcms_global_search_results"] = search_everywhere(repo, profile, cleaned)

    last_query = str(st.session_state.get("_qcms_global_search_last_query") or "").strip()
    if not last_query:
        st.info("Search anything: a module (\"bend test\"), a field (\"heat code\"), or any value stored in QCMS (part, heat, PO, RMTC, batch, supplier, report...). "
                "Results respect your module View permissions and Supabase tenant / row-level security.")
        return
    everything = st.session_state.get("_qcms_global_search_everything") or {}
    if everything.get("records") is None:
        _render_classic_results(last_query)
        return
    _render_everything(repo, last_query, everything)


def _search_everything(repo: Repository, profile: dict, query: str) -> dict:
    from core.global_search_service import search_fields, search_modules, search_records
    cache: dict[str, bool] = {}

    def can_view(module_key: str) -> bool:
        if module_key not in cache:
            cache[module_key] = bool(module_permissions(profile, module_key, repo).get("can_view"))
        return cache[module_key]

    pages = st.session_state.get("_qsms_pages") or {}
    try:
        records = search_records(repo, query, limit=400, can_view=can_view)
    except Exception as exc:
        st.warning(f"Database search could not finish: {exc}")
        records = []
    return {"modules": search_modules(query, pages), "fields": search_fields(query), "records": records}


def _open_route(route: str) -> None:
    pages = st.session_state.get("_qsms_pages") or {}
    if route in pages:
        st.switch_page(pages[route])
    else:
        st.warning("This screen is not available for your login.")


_EDIT_ROUTED_TABLES = {
    "parts", "part_raw_material_details", "part_raw_material_technical_data", "part_supplier_price_history", "material_grades", "parties",
    "processes", "inspection_stages", "company_branches", "employees", "inspection_plans", "rmtc_approvals", "rmtc_part_approvals",
    "inward_lots", "osp_jobs", "osp_receipts", "production_batches", "inspection_reports", "lab_tests", "npd_orders", "npd_process_flows",
    "ppap_projects", "qc_calculation_records", "quality_complaints", "quality_assets", "quality_asset_calibration_records",
    "standard_room_inspection_records", "supply_customer_orders", "supply_purchase_orders", "supply_purchase_order_items",
    "supply_po_confirmations", "supply_opening_stock", "supply_rm_purchase_orders", "supply_rm_receipts", "supply_rm_dispatches",
    "supply_forging_orders", "supply_forging_receipts", "supply_downstream_events",
}

# R36: detail / child rows open their parent record (child table -> (parent table, link column)).
_CHILD_PARENT: dict[str, tuple[str, str]] = {
    "part_supplier_links": ("parts", "part_id"), "part_process_specifications": ("parts", "part_id"),
    "part_process_parameter_specifications": ("parts", "part_id"), "part_metallurgical_requirements": ("parts", "part_id"),
    "part_heat_treatment_details": ("parts", "part_id"), "part_rmtc_requirements": ("parts", "part_id"),
    "part_material_grade_links": ("parts", "part_id"), "part_jominy_requirements": ("parts", "part_id"),
    "part_standard_links": ("parts", "part_id"), "material_grade_elements": ("material_grades", "material_grade_id"),
    "inspection_plan_characteristics": ("inspection_plans", "inspection_plan_id"),
    "inspection_results": ("inspection_reports", "inspection_report_id"),
    "quality_complaint_actions": ("quality_complaints", "complaint_id"), "quality_complaint_followups": ("quality_complaints", "complaint_id"),
    "npd_order_steps": ("npd_orders", "npd_order_id"), "npd_process_flow_steps": ("npd_process_flows", "flow_id"),
    "ppap_documents": ("ppap_projects", "ppap_project_id"), "control_plan_headers": ("ppap_projects", "ppap_project_id"),
    "pfd_headers": ("ppap_projects", "ppap_project_id"), "pfmea_headers": ("ppap_projects", "ppap_project_id"),
    "msa_plans": ("ppap_projects", "ppap_project_id"), "spc_plans": ("ppap_projects", "ppap_project_id"),
    "capacity_studies": ("ppap_projects", "ppap_project_id"), "balloon_characteristics": ("ppap_projects", "ppap_project_id"),
    "rmtc_chemistry_results": ("rmtc_approvals", "rmtc_approval_id"), "rmtc_requirement_results": ("rmtc_approvals", "rmtc_approval_id"),
    "rmtc_jominy_results": ("rmtc_approvals", "rmtc_approval_id"), "rmtc_decision_revisions": ("rmtc_approvals", "rmtc_approval_id"),
    "osp_material_outs": ("osp_jobs", "osp_job_id"), "supply_purchase_order_sources": ("supply_purchase_orders", "purchase_order_id"),
    "calibration_events": ("quality_assets", "asset_id"), "quality_asset_part_process_links": ("quality_assets", "asset_id"),
}
# document_attachments.entity_type -> owning table
_ATTACHMENT_OWNER = {
    "METLAB_REPORT": "lab_tests", "QUALITY_COMPLAINT": "quality_complaints", "PO_CONFIRMATION": "supply_po_confirmations",
    "PART_MASTER": "parts", "RMTC": "rmtc_approvals", "CUSTOMER_STANDARD": "customer_standards", "MATERIAL_INWARD": "inward_lots",
    "PART_PROCESS_SPEC": "part_process_specifications", "SUPPLY_CUSTOMER_ORDER": "supply_customer_orders",
    "DIMENSIONAL_REPORT": "inspection_reports", "OSP_JOB": "osp_jobs", "NPD_ORDER": "npd_orders",
}
_HIDDEN_VIEW_FIELDS = {"tenant_id", "created_by", "updated_by", "checksum", "smtp_password"}


def _fetch_row(repo: Repository, table: str, record_id: str) -> dict:
    if not table or not record_id:
        return {}
    try:
        rows = repo.select(table, eq={"id": record_id}, limit=1)
    except Exception:
        rows = []
    return dict(rows[0]) if rows else {}


def _resolve_target(repo: Repository, table: str, row: dict, depth: int = 0) -> tuple[str, dict]:
    """Walk from a search hit to the record that has its own screen (detail row -> parent)."""
    if depth > 3 or not row:
        return table, row
    if table in _EDIT_ROUTED_TABLES or table == "customer_standards":
        return table, row
    if table in _CHILD_PARENT:
        parent, column = _CHILD_PARENT[table]
        parent_row = _fetch_row(repo, parent, str(row.get(column) or ""))
        if parent_row:
            return _resolve_target(repo, parent, parent_row, depth + 1)
    if table == "document_attachments":
        owner = _ATTACHMENT_OWNER.get(str(row.get("entity_type") or "").upper())
        owner_row = _fetch_row(repo, owner or "", str(row.get("entity_id") or ""))
        if owner_row:
            return _resolve_target(repo, str(owner), owner_row, depth + 1)
    if table == "qcms_delete_requests":
        target_row = _fetch_row(repo, str(row.get("table_name") or ""), str(row.get("record_id") or ""))
        if target_row:
            return _resolve_target(repo, str(row.get("table_name")), target_row, depth + 1)
    return table, row


@st.dialog("Record details", width="large")
def _record_viewer(table: str, row: dict, record_type: str, route: str) -> None:
    """R36: every search hit can be opened - records without their own entry screen are shown here in full."""
    st.markdown(f"**{record_type}** · `{table}`")
    items = [{"Field": str(k).replace("_", " ").title(), "Value": ("" if v is None else str(v))[:500]}
             for k, v in row.items() if k not in _HIDDEN_VIEW_FIELDS and v not in (None, "", [], {})]
    portal_table(pd.DataFrame(items), hide_index=True, width="stretch", height=min(560, 60 + 35 * len(items)))
    if table == "document_attachments" and row.get("object_path"):
        try:
            from core.attachments import AttachmentService
            data = AttachmentService().download(row)
            st.download_button("Download file", data=data, file_name=str(row.get("file_name") or "attachment"),
                               mime=str(row.get("mime_type") or "application/octet-stream"), icon=":material/download:")
        except Exception as exc:
            st.caption(f"File not available: {exc}")
    pages = st.session_state.get("_qsms_pages") or {}
    if route and route in pages and st.button("Open the module screen", icon=":material/open_in_new:", type="primary"):
        st.switch_page(pages[route])


def _open_record(repo: Repository, item: dict) -> None:
    table = str(item.get("table") or "")
    row = _fetch_row(repo, table, str(item.get("id") or ""))
    if not row:
        _open_route(str(item.get("route") or "records-center"))
        return
    target_table, target_row = _resolve_target(repo, table, row)
    if target_table == "customer_standards":
        st.session_state["edit_customer_standard_id"] = str(target_row.get("id") or "")
        _open_route("standards-entry")
        return
    if target_table in _EDIT_ROUTED_TABLES:
        _open_result({"table": target_table, "record": target_row})
        return
    _record_viewer(table, row, str(item.get("record_type") or table), str(item.get("route") or ""))


def _render_everything(repo: Repository, query: str, everything: dict) -> None:
    from core.global_search_service import group_records
    modules = list(everything.get("modules") or [])
    fields = list(everything.get("fields") or [])
    records = list(everything.get("records") or [])
    disposition_cards([
        {"label": "Search", "value": query, "foot": "Current query"},
        {"label": "Modules & screens", "value": len(modules), "foot": "Open directly"},
        {"label": "Fields", "value": len(fields), "foot": "Where this is captured"},
        {"label": "Records", "value": len(records), "foot": "Whole database, permission aware"},
    ])
    if not (modules or fields or records):
        st.warning(f"Nothing in QCMS matched **{query}**. Try part of the value (e.g. the first characters of a heat or part number).")
        return
    tab_labels = [f"All ({len(modules) + len(fields) + len(records)})", f"Modules & screens ({len(modules)})", f"Fields ({len(fields)})", f"Records ({len(records)})"]
    t_all, t_mod, t_fld, t_rec = st.tabs(tab_labels)
    with t_all:
        if modules:
            section_bar("MODULES & SCREENS", "Open the matching module, entry screen, register or report")
            _module_buttons(modules[:8], "all")
        if records:
            section_bar("RECORDS", f"{len(records)} matching record(s) across the database")
            _record_table(repo, records[:60], "all")
        if fields:
            section_bar("FIELDS", "Screens where a matching field is captured")
            _field_table(fields[:12], "all")
    with t_mod:
        _module_buttons(modules, "mod") if modules else st.caption("No module or screen matched.")
    with t_fld:
        _field_table(fields, "fld") if fields else st.caption("No field label matched.")
    with t_rec:
        if not records:
            st.caption("No stored record matched.")
        for record_type, items in group_records(records).items():
            with st.expander(f"{record_type} · {len(items)}", expanded=len(records) <= 30):
                _record_table(repo, list(items), f"rec_{record_type}")


def _module_buttons(modules: list[dict], key: str) -> None:
    cols = st.columns(4, gap="small")
    for index, item in enumerate(modules):
        with cols[index % 4]:
            label = str(item.get("title") or item.get("route"))
            route = str(item.get("route") or "")
            if st.button(label, key=f"gs_mod_{key}_{index}_{route}", icon=":material/open_in_new:", width="stretch", disabled=not route,
                         help=str(item.get("keywords") or "")[:160] or None):
                _open_route(route)


def _field_table(fields: list[dict], key: str) -> None:
    portal_table(pd.DataFrame([{"Field": f["label"], "Screen / Module": f["module"], "Column": f["field"]} for f in fields]),
                 hide_index=True, width="stretch", height=min(420, 80 + 35 * len(fields)))
    routes = [f for f in fields if f.get("route")]
    if routes:
        choice = st.selectbox("Open the screen for a field", range(len(routes)), format_func=lambda i: f"{routes[i]['label']} · {routes[i]['module']}", key=f"gs_fld_pick_{key}")
        if st.button("Open screen", key=f"gs_fld_open_{key}", icon=":material/open_in_new:"):
            _open_route(str(routes[choice]["route"]))


def _record_table(repo: Repository, items: list[dict], key: str) -> None:
    """R36: click any row to open that record (its entry screen, its parent record, or the full record view)."""
    frame = pd.DataFrame([{
        "Type": item["record_type"], "Reference": item["title"], "Details": item["subtitle"],
        "Found in": item["matched_field"], "Matched text": item["snippet"],
    } for item in items])
    st.caption("Click a row to open the record.")
    from core.ui import selectable_table
    clicked = selectable_table(frame, key=f"gs_rec_grid_{key}", height=min(520, 80 + 35 * len(items)))
    rows = [clicked] if clicked is not None else []
    if rows and 0 <= rows[0] < len(items):
        picked = f"{key}:{items[rows[0]].get('table')}:{items[rows[0]].get('id')}"
        if st.session_state.get("_gs_last_opened") != picked:  # a closed record view must not re-open on every rerun
            st.session_state["_gs_last_opened"] = picked
            _open_record(repo, items[rows[0]])
    else:
        st.session_state.pop("_gs_last_opened", None)


def _render_classic_results(last_query: str) -> None:
    results = list(st.session_state.get("_qcms_global_search_results") or [])
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
