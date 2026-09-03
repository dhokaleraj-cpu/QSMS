from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st
from core.ui import portal_table

from core.access import current_permissions
from core.delete_service import password_delete_panel, password_rpc_delete_panel
from core.osp_service import OSPService
from core.notification_service import NotificationService
from core.notification_ui import notification_confirmation, notification_overrides, record_email_sender
from core.inspection_service import InspectionService
from core.reporting import controlled_record_pdf_bytes, dimensional_record_pdf_bytes, metlab_record_pdf_bytes
from core.selection_labels import party_label, process_label
from core.ui import kpi_grid, page_header, record_widget_token, save_success_popup, section_bar, stage_section, style_status_dataframe, subpage_navigation, workflow_progress


def _label(row: dict) -> str:
    fsi = f" · FSI {row.get('fsi_part_number')}" if row.get("fsi_part_number") else ""
    fsi_batch = row.get("osp_batch_code") or row.get("fsi_batch_number") or "-"
    vendor_batch = row.get("vendor_batch_number") or "-"
    return (
        f"{row.get('osp_job_number')} · Part {row.get('part_number')}{fsi} · "
        f"FSI Batch {fsi_batch} · Vendor Batch {vendor_batch} · Heat {row.get('heat_number')} · "
        f"{row.get('process_name')} · {row.get('vendor_name')}"
    )


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
        {"label": "OSP Inward Ready", "value": sum(str(r.get("sample_gate_status")) in {"ACCEPTED", "ACCEPTED_UNDER_RESERVE"} and float(r.get("quantity_received") or 0) < float(r.get("quantity_dispatched") or 0) for r in rows), "foot": "Sample gate passed · full/partial", "color": "#0F766E", "background": "#F0FDFA"},
        {"label": "Receipt Inspection", "value": sum(float(r.get("quantity_received") or 0) >= float(r.get("quantity_dispatched") or 0) > 0 and str(r.get("receipt_quality_disposition")) in {"PENDING", "ON_HOLD"} for r in rows), "foot": "Final receipt · production blocked", "color": "#D97706", "background": "#FFF7ED"},
        {"label": "Released to Production", "value": sum(str(r.get("status")) == "COMPLETED" for r in rows), "foot": "Both reports accepted", "color": "#15803D", "background": "#F0FDF4"},
        {"label": "Rejected", "value": sum(str(r.get("status")) == "REJECTED" for r in rows), "foot": "OSP quality rejected", "color": "#B91C1C", "background": "#FEF2F2"},
    ])
    section_bar("OSP WORKFLOW")
    workflow_progress([
        {"label": "Material Out", "state": "current", "detail": "Dispatch to approved OSP vendor"},
        {"label": "Sample Receipt", "state": "pending", "detail": "Receive pre-inward sample"},
        {"label": "OSP Dimensional", "state": "pending", "detail": "Validate dimensional sample"},
        {"label": "OSP MetLAB", "state": "pending", "detail": "Validate metallurgical sample"},
        {"label": "OSP Inward", "state": "pending", "detail": "Receive full accepted batch"},
        {"label": "Production Release", "state": "pending", "detail": "Release after both inspections"},
    ])
    _render_register(rows, 430)


def render_material_out() -> None:
    subpage_navigation(("osp-home", "OSP Home", ":material/arrow_back:"), ("osp-records", "OSP Records", ":material/table_view:"))
    page_header("OSP Material Out", "Dispatch released material by Part and Heat Number to an approved OSP vendor.", "Heat genealogy")
    service = OSPService(); perms = current_permissions("OSP_TRANSACTIONS")
    candidates = service.dispatch_candidates()
    if not candidates:
        st.info("No released Material Inward or eligible Opening Stock balance is available for OSP dispatch.")
        return
    labels = {
        str(row["candidate_key"]):
        f"{'Opening Stock' if row.get('source_type') == 'OPENING_STOCK' else 'Material Inward'} · {row.get('inward_number')} · "
        f"{row.get('part_number')} · FSI {row.get('fsi_part_number') or '-'} · Heat {row.get('heat_number')} · "
        f"Stage {str(row.get('supply_chain_stage') or 'Released').replace('_',' ').title()} · Available {float(row.get('osp_available_quantity_pcs') or 0):,.0f} pcs"
        for row in candidates
    }
    selected_key = st.selectbox("OSP Source · Released Inward / Opening Stock", list(labels), format_func=lambda value: labels[value])
    candidate = next(row for row in candidates if str(row["candidate_key"]) == selected_key)
    inward_id = candidate.get("inward_lot_id")
    specifications = service.specifications(str(candidate.get("part_id")))
    processes = service.processes(); vendors = service.vendors()
    if not specifications:
        st.warning("Create an active OSP Process Specification for this Part in Part Master before Material Out.")
        return
    spec_labels = {str(row["id"]): f"{process_label(processes.get(str(row.get('process_id'))) or {})} · {row.get('process_specification') or '-'}" for row in specifications}
    vendor_labels = {str(row["id"]): party_label(row, include_type=True) for row in vendors}
    new_scope = record_widget_token("osp-material-out-new", candidate, selected=selected_key)
    with st.form(f"osp_material_out_form_{new_scope}"):
        c = st.columns(4, gap="small")
        spec_id = c[0].selectbox("OSP Process / Specification", list(spec_labels), format_func=lambda value: spec_labels[value])
        vendor_id = c[1].selectbox("OSP Vendor", list(vendor_labels), format_func=lambda value: vendor_labels[value]) if vendor_labels else None
        dispatch_date = c[2].date_input("Material Out Date", value=date.today(), format="DD-MM-YYYY")
        expected_date = c[3].date_input("Expected Return Date", value=date.today() + timedelta(days=7), format="DD-MM-YYYY")
        c = st.columns(5, gap="small")
        challan = c[0].text_input("Material Out Challan Number")
        quantity = c[1].number_input("Material Out Quantity (pcs)", min_value=1.0, max_value=float(candidate.get("osp_available_quantity_pcs") or 1), value=float(candidate.get("osp_available_quantity_pcs") or 1), step=1.0)
        selected_spec = next(row for row in specifications if str(row["id"]) == spec_id)
        sample_qty = c[2].number_input("Pre-inward Sample Quantity (pcs)", min_value=1, max_value=20, value=int(selected_spec.get("sample_quantity") or 1), step=1)
        c[3].text_input("Heat Number", value=str(candidate.get("heat_number") or ""), disabled=True)
        c[4].text_input("FSI Batch Number", value="Auto-generated on save", disabled=True, help="QCMS generates one controlled Four Star Industries batch number for this OSP Material Out and carries it through Sample, OSP inspection and OSP Inward.")
        remarks = st.text_area("Dispatch Remarks", height=70)
        submitted = st.form_submit_button("Create OSP Material Out", type="primary", disabled=not perms["can_create"] or not vendor_id, width="stretch")
    if submitted:
        try:
            process_id = str(selected_spec.get("process_id"))
            saved = service.create_dispatch({"inward_lot_id": inward_id, "opening_stock_id": candidate.get("opening_stock_id"), "vendor_id": vendor_id, "process_id": process_id, "process_specification_id": spec_id, "dispatch_date": dispatch_date.isoformat(), "dispatch_challan": challan, "quantity_dispatched": quantity, "expected_return_date": expected_date.isoformat(), "sample_quantity": sample_qty, "remarks": remarks})
            batch = service.repo.get("production_batches", str(saved.get("osp_batch_id") or "")) or {}
            batch_code = batch.get("batch_code") or "generated"
            save_success_popup(f"OSP Material Out {saved.get('osp_job_number')} saved successfully · FSI Batch {batch_code}.", queue_for_rerun=True)
            st.rerun()
        except Exception as exc: st.error(str(exc))

    with stage_section("B", "EDIT / DELETE MATERIAL OUT", "Controlled changes are allowed only while downstream OSP receipt/inspection genealogy permits them.", key="osp_material_out_manage"):
        managed = service.register()
        if managed:
            mlabels = {str(r["id"]): _label(r) for r in managed}
            mid = st.selectbox("Existing Material Out", list(mlabels), format_func=lambda value: mlabels[value], key="osp_material_out_manage_id")
            mrow = next(r for r in managed if str(r["id"]) == mid)
            portal_table(pd.DataFrame([{
                "Part Number": mrow.get("part_number"),
                "FSI Part Number": mrow.get("fsi_part_number"),
                "FSI Batch Number": mrow.get("osp_batch_code") or "-",
                "Vendor Batch Number": mrow.get("vendor_batch_number") or "-",
                "Heat Number": mrow.get("heat_number"),
                "Material Out Remarks": mrow.get("dispatch_remarks") or "-",
            }]), hide_index=True, width="stretch", height=105)
            edit_scope = record_widget_token("osp-material-out-edit", mrow, selected=mid)
            with st.form(f"osp_material_out_edit_form_{edit_scope}"):
                c=st.columns(4,gap="small")
                mdate=c[0].date_input("Material Out Date", value=date.fromisoformat(str(mrow.get("dispatch_date"))[:10]), format="DD-MM-YYYY")
                mexpected=c[1].date_input("Expected Return Date", value=date.fromisoformat(str(mrow.get("expected_return_date"))[:10]) if mrow.get("expected_return_date") else date.today()+timedelta(days=7), format="DD-MM-YYYY")
                mch=c[2].text_input("Material Out Challan Number", value=str(mrow.get("dispatch_challan") or ""))
                mqty=c[3].number_input("Material Out Quantity (pcs)", min_value=1.0, value=float(mrow.get("quantity_dispatched") or 1), step=1.0)
                mremarks=st.text_area("Dispatch Remarks", value=str(mrow.get("dispatch_remarks") or ""), height=70)
                update_clicked=st.form_submit_button("Update Material Out", type="primary", disabled=not perms["can_edit"], width="stretch")
            if update_clicked:
                try:
                    service.update_material_out({"osp_job_id":mid,"dispatch_date":mdate.isoformat(),"dispatch_challan":mch,"quantity_dispatched":mqty,"expected_return_date":mexpected.isoformat(),"remarks":mremarks})
                    save_success_popup("OSP Material Out updated successfully.", queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))
            if password_rpc_delete_panel(repo=service.repo, rpc_name="qcms_delete_osp_transaction", rpc_param="p_osp_job_id", rows=[mrow], labeler=lambda row:_label(row), key=f"osp_material_out_delete_{mid}", can_delete=perms["can_archive"], title="Delete Material Out", help_text="Requires current password and OSP Delete/Archive permission. Downstream records block unsafe deletion.", success_message="OSP Material Out deleted and source allocation restored."):
                st.rerun()
        else:
            st.info("No OSP Material Out transaction exists yet.")


def render_sample_receipt() -> None:
    subpage_navigation(("osp-home", "OSP Home", ":material/arrow_back:"), ("osp-dimensional", "OSP Dimensional", ":material/straighten:"), ("osp-metlab", "OSP MetLAB", ":material/science:"))
    page_header("OSP Pre-inward Sample Receipt", "Record the vendor batch sample before accepting the full processed batch.", "Sample gate")
    service = OSPService(); perms = current_permissions("OSP_TRANSACTIONS")
    job = _job_selector(service.jobs_for_sample_receipt(), "OSP Material Out · Part / FSI Batch", "osp_sample_job")
    if not job: return
    portal_table(pd.DataFrame([{
        "Part Number": job.get("part_number"),
        "FSI Part Number": job.get("fsi_part_number"),
        "FSI Batch Number": job.get("osp_batch_code") or "-",
        "Vendor Batch Number": job.get("vendor_batch_number") or "-",
        "Material Out Challan": job.get("dispatch_challan") or "-",
        "Material Out Remarks": job.get("dispatch_remarks") or "-",
    }]), hide_index=True, width="stretch", height=105)
    osp_notify_pref = notification_confirmation(NotificationService(service.repo), "OSP_SAMPLE_PENDING", key=f"osp_sample_notify_{job.get('id')}", context={"supplier_id":str(job.get("vendor_id") or ""),"supplier_name":job.get("vendor_name"),"part_number":job.get("part_number"),"next_task":"OSP Sample Dimensional / MetLAB"}, include_supplier=True, default_send=True)
    sample_scope = record_widget_token("osp-sample-receipt", job, selected=job.get("id"))
    with st.form(f"osp_sample_receipt_form_{sample_scope}"):
        c = st.columns(4, gap="small")
        received_date = c[0].date_input("Sample Received Date", value=date.today(), format="DD-MM-YYYY")
        reference = c[1].text_input("Sample Reference", value=str(job.get("sample_reference") or ""))
        vendor_batch = c[2].text_input("OSP Vendor Batch Number", value=str(job.get("vendor_batch_number") or ""))
        sample_qty = c[3].number_input("Sample Quantity (pcs)", min_value=1, max_value=int(float(job.get("quantity_dispatched") or 1)), value=int(float(job.get("sample_quantity") or 1)), step=1)
        submitted = st.form_submit_button("Save Sample Receipt", type="primary", disabled=not perms["can_edit"] or (osp_notify_pref["send"] and not osp_notify_pref["confirmed"]), width="stretch")
    if submitted:
        try:
            service.record_sample({"osp_job_id": job["id"], "sample_received_date": received_date.isoformat(), "sample_reference": reference, "vendor_batch_number": vendor_batch, "sample_quantity": sample_qty})
            if osp_notify_pref["send"] and osp_notify_pref["confirmed"]:
                NotificationService(service.repo).notify(
                    "OSP_SAMPLE_PENDING",
                subject=f"QCMS · OSP sample inspection pending · {job.get('osp_job_number')}",
                body_text=(f"OSP sample receipt is recorded for {job.get('osp_job_number')}.\n"
                           f"Part: {job.get('part_number') or '-'} · FSI {job.get('fsi_part_number') or '-'}\n"
                           f"Vendor: {job.get('vendor_name') or '-'}\n"
                           f"FSI Batch: {job.get('osp_batch_code') or '-'}\n"
                           f"Vendor Batch: {vendor_batch or '-'}\n"
                           f"Material Out Remarks: {job.get('dispatch_remarks') or '-'}\n"
                           "Complete the required OSP sample inspections shown in QCMS."),
                related_table="osp_jobs",related_id=str(job.get("id")),
                context={"osp_job_id":str(job.get("id")),"next_task":"OSP Sample Dimensional / MetLAB"},
                **notification_overrides(osp_notify_pref),
            )
            save_success_popup("OSP sample receipt saved successfully. Required OSP inspection queues are now available.", queue_for_rerun=True); st.rerun()
        except Exception as exc: st.error(str(exc))
    if job.get("sample_received_date"):
        st.session_state["osp_inspection_job_id"] = str(job["id"]); st.session_state["osp_inspection_scope"] = "OSP_SAMPLE"
        c1, c2 = st.columns(2, gap="small")
        with c1: st.page_link(st.session_state["_qsms_pages"]["osp-dimensional"], label="Open Sample Dimensional", icon=":material/straighten:", width="stretch")
        with c2: st.page_link(st.session_state["_qsms_pages"]["osp-metlab"], label="Open Sample MetLAB", icon=":material/science:", width="stretch")
        with stage_section("B", "EDIT / DELETE SAMPLE RECEIPT", key="osp_sample_manage"):
            st.caption("The form above edits the selected Sample Receipt. Delete is allowed only before linked Sample Dimensional/MetLAB records exist.")
            if password_rpc_delete_panel(repo=service.repo, rpc_name="qcms_clear_osp_sample", rpc_param="p_osp_job_id", rows=[job], labeler=lambda row:_label(row), key=f"osp_sample_delete_{job.get('id')}", can_delete=perms["can_archive"], title="Delete Sample Receipt", help_text="Requires current password and OSP Delete/Archive permission.", success_message="OSP Sample Receipt cleared successfully."):
                st.rerun()


def render_inward() -> None:
    subpage_navigation(("osp-home", "OSP Home", ":material/arrow_back:"), ("osp-records", "OSP Records", ":material/table_view:"))
    page_header("OSP Material Inward", "OSP receipt is enabled after the pre-inward sample passes Dimensional and MetLAB. Partial vendor receipts are allowed against the remaining dispatched quantity.", "Controlled receipt")
    service = OSPService(); perms = current_permissions("OSP_TRANSACTIONS")
    job = _job_selector(service.jobs_for_full_receipt(), "Sample-approved OSP Batch · Part / FSI Batch", "osp_inward_job")
    if not job: return
    portal_table(pd.DataFrame([{
        "Part Number": job.get("part_number"),
        "FSI Part Number": job.get("fsi_part_number"),
        "FSI Batch Number": job.get("osp_batch_code") or "-",
        "Vendor Batch Number": job.get("vendor_batch_number") or "-",
        "Material Out Challan": job.get("dispatch_challan") or "-",
        "Material Out Remarks": job.get("dispatch_remarks") or "-",
    }]), hide_index=True, width="stretch", height=105)
    inward_scope = record_widget_token("osp-inward-new", job, selected=job.get("id"))
    with st.form(f"osp_full_inward_form_{inward_scope}"):
        c = st.columns(4, gap="small")
        receipt_date = c[0].date_input("OSP Inward Date", value=date.today(), format="DD-MM-YYYY")
        receipt_challan = c[1].text_input("Vendor Delivery Challan")
        vendor_invoice = c[2].text_input("Vendor Invoice Number")
        vendor_invoice_date = c[3].date_input("Vendor Invoice Date", value=date.today(), format="DD-MM-YYYY")
        c = st.columns(4, gap="small")
        tc_number = c[0].text_input("TC Number")
        tc_date = c[1].date_input("TC Date", value=date.today(), format="DD-MM-YYYY")
        vendor_batch = c[2].text_input("OSP Vendor Batch Number", value=str(job.get("vendor_batch_number") or ""))
        dispatched = float(job.get("quantity_dispatched") or 0); already_received = float(job.get("quantity_received") or 0); remaining = max(dispatched - already_received, 0)
        quantity = c[3].number_input("Receipt Batch Qty (pcs)", min_value=1.0, max_value=max(float(remaining), 1.0), value=max(float(remaining), 1.0), step=1.0, help="Override with the actual partial quantity received from the OSP Vendor. The remaining dispatched quantity stays open for another inward.")
        portal_table(pd.DataFrame([{"FSI Batch Number": job.get("osp_batch_code") or "-", "OSP Out Qty pcs": dispatched, "Already Received pcs": already_received, "Balance at Vendor pcs": remaining, "OSP Vendor Batch": job.get("vendor_batch_number") or vendor_batch or "-", "Material Out Remarks": job.get("dispatch_remarks") or "-"}]), hide_index=True, width="stretch", height=105)
        remarks = st.text_area("Receipt Remarks", height=70)
        submitted = st.form_submit_button("Create OSP Material Inward", type="primary", disabled=not perms["can_create"], width="stretch")
    if submitted:
        try:
            saved = service.receive_batch({"osp_job_id": job["id"], "receipt_date": receipt_date.isoformat(), "receipt_challan": receipt_challan, "vendor_invoice_number": vendor_invoice, "vendor_invoice_date": vendor_invoice_date.isoformat(), "tc_number": tc_number, "tc_date": tc_date.isoformat(), "vendor_batch_number": vendor_batch, "quantity_received": quantity, "remarks": remarks})
            save_success_popup(f"OSP Inward {saved.get('receipt_number')} saved successfully. Post-receipt inspections are now pending.", queue_for_rerun=True); st.rerun()
        except Exception as exc: st.error(str(exc))

    with stage_section("B", "EDIT / DELETE OSP INWARD RECEIPTS", key="osp_inward_manage"):
        receipt_pairs=[]
        for tx in service.register():
            for rec in service.receipts(str(tx.get("id"))):
                item=dict(rec); item["_job_label"]=_label(tx); receipt_pairs.append(item)
        if receipt_pairs:
            rlabels={str(r["id"]):f"{r.get('receipt_number')} · {r.get('_job_label')} · {float(r.get('quantity_received') or 0):,.0f} pcs" for r in receipt_pairs}
            rid=st.selectbox("OSP Inward Receipt", list(rlabels), format_func=lambda value:rlabels[value], key="osp_inward_manage_id")
            rec=next(r for r in receipt_pairs if str(r["id"])==rid)
            receipt_scope = record_widget_token("osp-inward-edit", rec, selected=rid)
            with st.form(f"osp_inward_edit_form_{receipt_scope}"):
                c=st.columns(4,gap="small")
                rdate=c[0].date_input("OSP Inward Date", value=date.fromisoformat(str(rec.get("receipt_date"))[:10]), format="DD-MM-YYYY")
                rchallan=c[1].text_input("Vendor Delivery Challan", value=str(rec.get("receipt_challan") or ""))
                rinvoice=c[2].text_input("Vendor Invoice Number", value=str(rec.get("vendor_invoice_number") or ""))
                rinvoice_date=c[3].date_input("Vendor Invoice Date", value=date.fromisoformat(str(rec.get("vendor_invoice_date"))[:10]), format="DD-MM-YYYY")
                c=st.columns(4,gap="small")
                rtc=c[0].text_input("TC Number", value=str(rec.get("tc_number") or ""))
                rtc_date=c[1].date_input("TC Date", value=date.fromisoformat(str(rec.get("tc_date"))[:10]), format="DD-MM-YYYY")
                rvbatch=c[2].text_input("OSP Vendor Batch Number", value=str(rec.get("vendor_batch_number") or ""))
                rqty=c[3].number_input("Receipt Batch Qty (pcs)", min_value=1.0, value=float(rec.get("quantity_received") or 1), step=1.0)
                rremarks=st.text_area("Receipt Remarks", value=str(rec.get("remarks") or ""), height=70)
                rupd=st.form_submit_button("Update OSP Inward Receipt", type="primary", disabled=not perms["can_edit"], width="stretch")
            if rupd:
                try:
                    service.update_receipt({"receipt_id":rid,"receipt_date":rdate.isoformat(),"receipt_challan":rchallan,"vendor_invoice_number":rinvoice,"vendor_invoice_date":rinvoice_date.isoformat(),"tc_number":rtc,"tc_date":rtc_date.isoformat(),"vendor_batch_number":rvbatch,"quantity_received":rqty,"remarks":rremarks})
                    save_success_popup("OSP Inward receipt updated successfully.", queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))
            if password_rpc_delete_panel(repo=service.repo, rpc_name="qcms_delete_osp_receipt", rpc_param="p_receipt_id", rows=[rec], labeler=lambda row:rlabels[str(row['id'])], key=f"osp_inward_delete_{rid}", can_delete=perms["can_archive"], title="Delete OSP Inward Receipt", help_text="Requires current password and OSP Delete/Archive permission. Receipt inspection records block unsafe deletion.", success_message="OSP Inward receipt deleted and quantity/status recalculated."):
                st.rerun()
        else:
            st.info("No OSP Inward receipt exists yet.")


def _render_register(rows: list[dict], height: int = 560) -> None:
    display = pd.DataFrame([{
        "OSP Job": r.get("osp_job_number"), "Material Out Date": r.get("dispatch_date"), "Heat Number": r.get("heat_number"),
        "Part Number": r.get("part_number"), "FSI Part Number": r.get("fsi_part_number"), "FSI Batch Number": r.get("osp_batch_code"), "OSP Vendor": r.get("vendor_name"), "Process": r.get("process_name"),
        "Out Qty pcs": r.get("quantity_dispatched"), "Vendor Batch": r.get("vendor_batch_number"), "Material Out Remarks": r.get("dispatch_remarks"), "Sample Gate": r.get("sample_gate_status"),
        "OSP Inward": r.get("receipt_number"), "Inward Qty pcs": r.get("quantity_received"), "Receipt Decision": r.get("receipt_quality_disposition"),
        "Production Qty Available": r.get("production_available_quantity"), "Data Entry Status": r.get("Data Entry Status") or r.get("status"),
        "Created By User": r.get("Created By User"), "Last Modified By User": r.get("Last Modified By User"), "Status": r.get("status"),
    } for r in rows])
    portal_table(style_status_dataframe(display), hide_index=True, width="stretch", height=height)


def render_records() -> None:
    subpage_navigation(("osp-home", "OSP Home", ":material/arrow_back:"), ("osp-material-out", "Material Out", ":material/output:"), ("osp-inward", "OSP Inward", ":material/input:"))
    page_header("OSP Transaction Records", context="Heat · Part · Vendor Batch")
    service = OSPService(); perms = current_permissions("OSP_TRANSACTIONS"); rows = service.register(); search = st.text_input("Search OSP Job, Heat, Part, Vendor, Process or Vendor Batch")
    filtered = [r for r in rows if not search or search.casefold() in " ".join(str(r.get(k) or "") for k in ("osp_job_number","receipt_number","heat_number","part_number","fsi_part_number","osp_batch_code","vendor_name","process_name","vendor_batch_number","vendor_invoice_number","tc_number","dispatch_remarks")).casefold()]
    if filtered:
        labels = {str(r["id"]): _label(r) for r in filtered}
        selected = st.selectbox("Select OSP record for controlled reports", list(labels), format_func=lambda value: labels[value], key="osp_record_print_selection")
        selected_row = next(r for r in filtered if str(r["id"]) == selected)
        inspection = InspectionService()
        metlab_rows = inspection.repo.select("lab_tests", eq={"osp_job_id": selected, "test_type": "METLAB"}, order_by="updated_at", desc=True, limit=20)
        receipt_rows = service.receipts(selected)
        if receipt_rows:
            section_bar("PARTIAL OSP RECEIPT HISTORY")
            portal_table(style_status_dataframe(pd.DataFrame([{
                "Receipt No.":r.get("receipt_number"),"Receipt Date":r.get("receipt_date"),"Vendor Challan":r.get("receipt_challan"),
                "Vendor Invoice":r.get("vendor_invoice_number"),"TC Number":r.get("tc_number"),"OSP Vendor Batch":r.get("vendor_batch_number"),
                "Receipt Qty pcs":r.get("quantity_received"),"Remarks":r.get("remarks")
            } for r in receipt_rows])),hide_index=True,width="stretch",height=min(300,80+len(receipt_rows)*35))
        dimensional_rows = inspection.repo.select("inspection_reports", eq={"osp_job_id": selected, "report_type": "DIMENSIONAL"}, order_by="updated_at", desc=True, limit=20)
        with stage_section("A", "OSP CONTROLLED PDF REPORTS", key="osp_records_a"):
            transaction_pdf = controlled_record_pdf_bytes(
                "OSP TRANSACTION RECORD",
                {
                    "OSP Job": selected_row.get("osp_job_number"), "Heat Number": selected_row.get("heat_number"),
                    "Part Number": selected_row.get("part_number"), "FSI Part Number": selected_row.get("fsi_part_number"), "OSP Vendor": selected_row.get("vendor_name"),
                    "Process": selected_row.get("process_name"), "Material Out Date": selected_row.get("dispatch_date"),
                    "Out Qty pcs": selected_row.get("quantity_dispatched"), "Expected Return": selected_row.get("expected_return_date"),
                    "Vendor Batch": selected_row.get("vendor_batch_number"), "Sample Gate": selected_row.get("sample_gate_status"),
                    "OSP Inward": selected_row.get("receipt_number"), "Inward Qty pcs": selected_row.get("quantity_received"),
                    "Receipt Decision": selected_row.get("receipt_quality_disposition"), "Production Qty Available": selected_row.get("production_available_quantity"),
                    "Status": selected_row.get("status"),
                },
                record_number=str(selected_row.get("osp_job_number") or ""),
            )
            st.download_button("OSP Transaction PDF", transaction_pdf, file_name=f"{selected_row.get('osp_job_number')}_OSP_Transaction.pdf", mime="application/pdf", key=f"osp_txn_pdf_{selected}", width="stretch")
            if not metlab_rows and not dimensional_rows:
                st.info("No completed OSP MetLAB or Dimensional report is linked to the selected OSP record yet.")
            else:
                cols = st.columns(2, gap="small")
                with cols[0]:
                    for report in metlab_rows:
                        try:
                            pdf = metlab_record_pdf_bytes(inspection.metlab_report_payload(str(report["id"])))
                            st.download_button(f"MetLAB PDF · {report.get('report_number')}", pdf, file_name=f"{report.get('report_number') or selected_row.get('osp_job_number')}_MetLAB.pdf", mime="application/pdf", key=f"osp_metlab_pdf_{report['id']}", width="stretch")
                        except Exception as exc:
                            st.error(f"MetLAB PDF could not be generated: {exc}")
                with cols[1]:
                    for report in dimensional_rows:
                        try:
                            pdf = dimensional_record_pdf_bytes(inspection.dimensional_report_payload(str(report["id"])))
                            st.download_button(f"Dimensional PDF · {report.get('report_number')}", pdf, file_name=f"{report.get('report_number') or selected_row.get('osp_job_number')}_Dimensional.pdf", mime="application/pdf", key=f"osp_dim_pdf_{report['id']}", width="stretch")
                        except Exception as exc:
                            st.error(f"Dimensional PDF could not be generated: {exc}")
        record_email_sender(
            NotificationService(service.repo), "OSP_SAMPLE_PENDING",
            related_table="osp_jobs", related_id=selected, key=f"osp_record_email_{selected}",
            context={"supplier_id": str(selected_row.get("vendor_id") or ""), "supplier_name": selected_row.get("vendor_name"), "part_number": selected_row.get("part_number"), "next_task": "OSP Sample / Receipt Quality Follow-up"},
            include_supplier=True,
        )
        with stage_section("B", "DELETE OSP RECORD", key="osp_records_b"):
            if metlab_rows or dimensional_rows:
                st.caption("Delete linked OSP MetLAB / Dimensional inspection records first; then delete the parent OSP transaction.")
            linked_rows = [*metlab_rows, *dimensional_rows]
            if linked_rows:
                report_labels = lambda row: f"{row.get('report_number')} · {row.get('test_type') or row.get('report_type')}"
                # MetLAB and Dimensional use different physical tables, so expose a separate password panel for each.
                if metlab_rows and password_delete_panel(
                    repo=inspection.repo, table="lab_tests", rows=metlab_rows, labeler=report_labels,
                    key=f"osp_metlab_delete_{selected}", can_delete=perms["can_archive"], title="Delete linked OSP MetLAB report",
                ):
                    st.rerun()
                if dimensional_rows and password_delete_panel(
                    repo=inspection.repo, table="inspection_reports", rows=dimensional_rows, labeler=report_labels,
                    key=f"osp_dim_delete_{selected}", can_delete=perms["can_archive"], title="Delete linked OSP Dimensional report",
                ):
                    st.rerun()
            if not metlab_rows and not dimensional_rows:
                if password_rpc_delete_panel(
                    repo=service.repo, rpc_name="qcms_delete_osp_transaction", rpc_param="p_osp_job_id",
                    rows=[selected_row], labeler=lambda row: _label(row),
                    key=f"osp_job_delete_{selected}", can_delete=perms["can_archive"], title="Delete OSP transaction",
                    help_text=(
                        "Permanent OSP transaction deletion requires your current QCMS password and OSP Delete/Archive permission. "
                        "QCMS restores the Material Out allocation before deleting the OSP child batch. Linked quality/downstream records block deletion."
                    ),
                    success_message="OSP transaction deleted and source quantity restored successfully.",
                ):
                    st.rerun()
        if receipt_rows:
            with stage_section("C", "DELETE PARTIAL OSP INWARD RECEIPT", key="osp_records_receipt_delete"):
                st.caption(
                    "Delete/Archive permission is controlled in Admin → Users & Access → OSP Transactions. "
                    "Deleting a receipt recalculates the OSP inward balance and is blocked while receipt-level inspection reports exist."
                )
                if password_rpc_delete_panel(
                    repo=service.repo, rpc_name="qcms_delete_osp_receipt", rpc_param="p_receipt_id",
                    rows=receipt_rows,
                    labeler=lambda row: f"{row.get('receipt_number')} · {row.get('receipt_date')} · {float(row.get('quantity_received') or 0):,.0f} pcs",
                    key=f"osp_receipt_delete_{selected}", can_delete=perms["can_archive"], title="Delete selected OSP inward receipt",
                    help_text="Current QCMS password is required. Receipt-level Dimensional/MetLAB records must be deleted first.",
                    success_message="OSP inward receipt deleted and OSP quantity/status recalculated successfully.",
                ):
                    st.rerun()
    with stage_section("D", "OSP TRANSACTION REGISTER", key="osp_records_c"):
        _render_register(filtered)
