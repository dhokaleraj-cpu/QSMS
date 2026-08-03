from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.osp_service import OSPService
from core.ui import kpi_grid, page_header, section_bar, style_status_dataframe, subpage_navigation


def _label(row: dict) -> str:
    return f"{row.get('osp_job_number')} · {row.get('part_number')} · Heat {row.get('heat_number')} · {row.get('process_name')} · {row.get('vendor_name')}"


def _job_selector(rows: list[dict], label: str, key: str) -> dict | None:
    if not rows:
        st.info("No eligible OSP transaction is available for this step.")
        return None
    labels = {str(row["id"]): _label(row) for row in rows}
    selected = st.selectbox(label, list(labels), format_func=lambda value: labels[value], key=key)
    return next(row for row in rows if str(row["id"]) == selected)


def render_home() -> None:
    page_header("OSP Transactions", "Heat-wise outsourced processing with sample approval, controlled inward and production release.", "Live genealogy")
    service = OSPService(); rows = service.register()
    kpi_grid([
        {"label": "At OSP Vendor", "value": sum(str(r.get("status")) == "AT_VENDOR" for r in rows), "foot": "Material dispatched", "color": "#2563EB", "background": "#EFF6FF"},
        {"label": "Sample Pending", "value": sum(bool(r.get("sample_received_date")) and str(r.get("sample_gate_status")) in {"PENDING", "ON_HOLD"} for r in rows), "foot": "Dimensional + MetLAB", "color": "#D97706", "background": "#FFF7ED"},
        {"label": "Full Inward Ready", "value": sum(str(r.get("sample_gate_status")) in {"ACCEPTED", "ACCEPTED_UNDER_RESERVE"} and float(r.get("quantity_received") or 0) == 0 for r in rows), "foot": "Sample gate passed", "color": "#0F766E", "background": "#F0FDFA"},
        {"label": "Receipt Inspection", "value": sum(float(r.get("quantity_received") or 0) > 0 and str(r.get("receipt_quality_disposition")) in {"PENDING", "ON_HOLD"} for r in rows), "foot": "Production blocked", "color": "#D97706", "background": "#FFF7ED"},
        {"label": "Released to Production", "value": sum(str(r.get("status")) == "COMPLETED" for r in rows), "foot": "Both reports accepted", "color": "#15803D", "background": "#F0FDF4"},
        {"label": "Rejected", "value": sum(str(r.get("status")) == "REJECTED" for r in rows), "foot": "OSP quality rejected", "color": "#B91C1C", "background": "#FEF2F2"},
    ])
    section_bar("OSP WORKFLOW")
    cols = st.columns(6, gap="small")
    links = [
        ("osp-material-out", "Material Out", ":material/output:"),
        ("osp-sample-receipt", "Sample Receipt", ":material/experiment:"),
        ("osp-dimensional", "OSP Dimensional", ":material/straighten:"),
        ("osp-metlab", "OSP MetLAB", ":material/science:"),
        ("osp-inward", "OSP Inward", ":material/input:"),
        ("osp-records", "OSP Records", ":material/table_view:"),
    ]
    for col, (path, label, icon) in zip(cols, links):
        with col: st.page_link(st.session_state["_qsms_pages"][path], label=label, icon=icon, width="stretch")
    _render_register(rows, 430)


def render_material_out() -> None:
    subpage_navigation(("osp-home", "OSP Home", ":material/arrow_back:"), ("osp-records", "OSP Records", ":material/table_view:"))
    page_header("OSP Material Out", "Dispatch released material by Part and Heat Number to an approved OSP vendor.", "Heat genealogy")
    service = OSPService(); perms = current_permissions("OSP_TRANSACTIONS")
    candidates = service.dispatch_candidates()
    if not candidates:
        st.info("No released Material Inward production balance is available for OSP dispatch.")
        return
    labels = {str(row["inward_lot_id"]): f"{row.get('inward_number')} · {row.get('part_number')} · Heat {row.get('heat_number')} · Available {float(row.get('osp_available_quantity_pcs') or 0):,.0f} pcs" for row in candidates}
    inward_id = st.selectbox("Released Material Inward", list(labels), format_func=lambda value: labels[value])
    candidate = next(row for row in candidates if str(row["inward_lot_id"]) == inward_id)
    specifications = service.specifications(str(candidate.get("part_id")))
    processes = service.processes(); vendors = service.vendors()
    if not specifications:
        st.warning("Create an active OSP Process Specification for this Part in Part Master before Material Out.")
        return
    spec_labels = {str(row["id"]): f"{(processes.get(str(row.get('process_id'))) or {}).get('process_name','Process')} · {row.get('process_specification')}" for row in specifications}
    vendor_labels = {str(row["id"]): f"{row.get('party_code')} · {row.get('party_name')}" for row in vendors}
    with st.form("osp_material_out_form"):
        c = st.columns(4, gap="small")
        spec_id = c[0].selectbox("OSP Process / Specification", list(spec_labels), format_func=lambda value: spec_labels[value])
        vendor_id = c[1].selectbox("OSP Vendor", list(vendor_labels), format_func=lambda value: vendor_labels[value]) if vendor_labels else None
        dispatch_date = c[2].date_input("Material Out Date", value=date.today(), format="DD-MM-YYYY")
        expected_date = c[3].date_input("Expected Return Date", value=date.today() + timedelta(days=7), format="DD-MM-YYYY")
        c = st.columns(4, gap="small")
        challan = c[0].text_input("Material Out Challan Number")
        quantity = c[1].number_input("Material Out Quantity (pcs)", min_value=1.0, max_value=float(candidate.get("osp_available_quantity_pcs") or 1), value=float(candidate.get("osp_available_quantity_pcs") or 1), step=1.0)
        selected_spec = next(row for row in specifications if str(row["id"]) == spec_id)
        sample_qty = c[2].number_input("Pre-inward Sample Quantity (pcs)", min_value=1, max_value=20, value=int(selected_spec.get("sample_quantity") or 1), step=1)
        c[3].text_input("Heat Number", value=str(candidate.get("heat_number") or ""), disabled=True)
        remarks = st.text_area("Dispatch Remarks", height=70)
        submitted = st.form_submit_button("Create OSP Material Out", type="primary", disabled=not perms["can_create"] or not vendor_id, width="stretch")
    if submitted:
        try:
            process_id = str(selected_spec.get("process_id"))
            saved = service.create_dispatch({"inward_lot_id": inward_id, "vendor_id": vendor_id, "process_id": process_id, "process_specification_id": spec_id, "dispatch_date": dispatch_date.isoformat(), "dispatch_challan": challan, "quantity_dispatched": quantity, "expected_return_date": expected_date.isoformat(), "sample_quantity": sample_qty, "remarks": remarks})
            st.success(f"OSP Material Out {saved.get('osp_job_number')} created.")
            st.rerun()
        except Exception as exc: st.error(str(exc))


def render_sample_receipt() -> None:
    subpage_navigation(("osp-home", "OSP Home", ":material/arrow_back:"), ("osp-dimensional", "OSP Dimensional", ":material/straighten:"), ("osp-metlab", "OSP MetLAB", ":material/science:"))
    page_header("OSP Pre-inward Sample Receipt", "Record the vendor batch sample before accepting the full processed batch.", "Sample gate")
    service = OSPService(); perms = current_permissions("OSP_TRANSACTIONS")
    job = _job_selector(service.jobs_for_sample_receipt(), "OSP Material Out", "osp_sample_job")
    if not job: return
    with st.form("osp_sample_receipt_form"):
        c = st.columns(4, gap="small")
        received_date = c[0].date_input("Sample Received Date", value=date.today(), format="DD-MM-YYYY")
        reference = c[1].text_input("Sample Reference", value=str(job.get("sample_reference") or ""))
        vendor_batch = c[2].text_input("OSP Vendor Batch Number", value=str(job.get("vendor_batch_number") or ""))
        sample_qty = c[3].number_input("Sample Quantity (pcs)", min_value=1, max_value=int(float(job.get("quantity_dispatched") or 1)), value=int(float(job.get("sample_quantity") or 1)), step=1)
        submitted = st.form_submit_button("Save Sample Receipt", type="primary", disabled=not perms["can_edit"], width="stretch")
    if submitted:
        try:
            service.record_sample({"osp_job_id": job["id"], "sample_received_date": received_date.isoformat(), "sample_reference": reference, "vendor_batch_number": vendor_batch, "sample_quantity": sample_qty})
            st.success("OSP sample recorded. Complete both OSP Dimensional and MetLAB inspections."); st.rerun()
        except Exception as exc: st.error(str(exc))
    if job.get("sample_received_date"):
        st.session_state["osp_inspection_job_id"] = str(job["id"]); st.session_state["osp_inspection_scope"] = "OSP_SAMPLE"
        c1, c2 = st.columns(2, gap="small")
        with c1: st.page_link(st.session_state["_qsms_pages"]["osp-dimensional"], label="Open Sample Dimensional", icon=":material/straighten:", width="stretch")
        with c2: st.page_link(st.session_state["_qsms_pages"]["osp-metlab"], label="Open Sample MetLAB", icon=":material/science:", width="stretch")


def render_inward() -> None:
    subpage_navigation(("osp-home", "OSP Home", ":material/arrow_back:"), ("osp-records", "OSP Records", ":material/table_view:"))
    page_header("OSP Material Inward", "Full OSP receipt is enabled only after the pre-inward sample passes Dimensional and MetLAB.", "Controlled receipt")
    service = OSPService(); perms = current_permissions("OSP_TRANSACTIONS")
    job = _job_selector(service.jobs_for_full_receipt(), "Sample-approved OSP Batch", "osp_inward_job")
    if not job: return
    with st.form("osp_full_inward_form"):
        c = st.columns(4, gap="small")
        receipt_date = c[0].date_input("OSP Inward Date", value=date.today(), format="DD-MM-YYYY")
        receipt_challan = c[1].text_input("Vendor Delivery Challan")
        vendor_invoice = c[2].text_input("Vendor Invoice Number")
        vendor_invoice_date = c[3].date_input("Vendor Invoice Date", value=date.today(), format="DD-MM-YYYY")
        c = st.columns(4, gap="small")
        tc_number = c[0].text_input("TC Number")
        tc_date = c[1].date_input("TC Date", value=date.today(), format="DD-MM-YYYY")
        vendor_batch = c[2].text_input("OSP Vendor Batch Number", value=str(job.get("vendor_batch_number") or ""))
        quantity = c[3].number_input("Full Batch Quantity (pcs)", min_value=1.0, value=float(job.get("quantity_dispatched") or 1), step=1.0, disabled=True)
        remarks = st.text_area("Receipt Remarks", height=70)
        submitted = st.form_submit_button("Create OSP Material Inward", type="primary", disabled=not perms["can_create"], width="stretch")
    if submitted:
        try:
            saved = service.receive_batch({"osp_job_id": job["id"], "receipt_date": receipt_date.isoformat(), "receipt_challan": receipt_challan, "vendor_invoice_number": vendor_invoice, "vendor_invoice_date": vendor_invoice_date.isoformat(), "tc_number": tc_number, "tc_date": tc_date.isoformat(), "vendor_batch_number": vendor_batch, "quantity_received": quantity, "remarks": remarks})
            st.success(f"OSP Inward {saved.get('receipt_number')} created. Post-receipt inspections are now pending."); st.rerun()
        except Exception as exc: st.error(str(exc))


def _render_register(rows: list[dict], height: int = 560) -> None:
    section_bar("OSP TRANSACTION REGISTER")
    display = pd.DataFrame([{
        "OSP Job": r.get("osp_job_number"), "Material Out Date": r.get("dispatch_date"), "Heat Number": r.get("heat_number"),
        "Part Number": r.get("part_number"), "OSP Vendor": r.get("vendor_name"), "Process": r.get("process_name"),
        "Out Qty pcs": r.get("quantity_dispatched"), "Vendor Batch": r.get("vendor_batch_number"), "Sample Gate": r.get("sample_gate_status"),
        "OSP Inward": r.get("receipt_number"), "Inward Qty pcs": r.get("quantity_received"), "Receipt Decision": r.get("receipt_quality_disposition"),
        "Production Qty Available": r.get("production_available_quantity"), "Status": r.get("status"),
    } for r in rows])
    st.dataframe(style_status_dataframe(display), hide_index=True, width="stretch", height=height)


def render_records() -> None:
    subpage_navigation(("osp-home", "OSP Home", ":material/arrow_back:"), ("osp-material-out", "Material Out", ":material/output:"), ("osp-inward", "OSP Inward", ":material/input:"))
    page_header("OSP Transaction Records", context="Heat · Part · Vendor Batch")
    service = OSPService(); rows = service.register(); search = st.text_input("Search OSP Job, Heat, Part, Vendor, Process or Vendor Batch")
    filtered = [r for r in rows if not search or search.casefold() in " ".join(str(r.get(k) or "") for k in ("osp_job_number","receipt_number","heat_number","part_number","vendor_name","process_name","vendor_batch_number","vendor_invoice_number","tc_number")).casefold()]
    _render_register(filtered)
