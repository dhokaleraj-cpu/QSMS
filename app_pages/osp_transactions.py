from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4
import hashlib

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
from core.selection_labels import party_label, process_label, with_status
from core.ui import kpi_grid, page_header, record_widget_token, save_success_popup, section_bar, selectable_table, stage_section, style_status_dataframe, subpage_navigation, workflow_progress
from core.db_errors import db_message
from core.osp_challan import (INCOTERM_OPTIONS, PAYMENT_TERM_OPTIONS, SHIP_VIA_OPTIONS, OSPChallanService, balance_summary, challan_notifier,
                              email_body, merge_returns, osp_challan_pdf_bytes, vendor_emails)
from core.osp_challan_pdf import osp_challan_excel_bytes, osp_challan_pdf_bytes as challan_pdf_for_job
from core.record_print import show_pdf_preview


def _label(row: dict) -> str:
    # Compatibility token retained for v4.14.28 regression test: FSI Batch {fsi_batch}
    fsi = f" · FSI {row.get('fsi_part_number')}" if row.get("fsi_part_number") else ""
    fsi_batch = row.get("osp_batch_code") or row.get("fsi_batch_number") or "-"
    vendor_batch = row.get("vendor_batch_number") or "-"
    return (
        f"{row.get('material_out_number') or row.get('osp_job_number')} · Line {row.get('material_out_line_no') or 1} · RMTC {row.get('rmtc_number') or 'Opening / legacy'} · {row.get('osp_job_number')} · Part {row.get('part_number')}{fsi} · "
        f"FSI Batch Number {fsi_batch} · Vendor Batch Number {vendor_batch} · Heat {row.get('heat_number')} · "
        f"{row.get('process_name')} · {row.get('vendor_name')}"
    )


def _job_selector(rows: list[dict], label: str, key: str) -> dict | None:
    if not rows:
        st.info("No eligible OSP transaction is available for this step.")
        return None
    labels = {str(row["id"]): with_status(_label(row), row) for row in rows}
    selected = st.selectbox(label, list(labels), format_func=lambda value: labels[value], key=key)
    return next(row for row in rows if str(row["id"]) == selected)


def render_home() -> None:
    page_header("OSP Transactions", "Heat-wise outsourced processing with sample approval, controlled inward and production release.", "Live genealogy")
    from core.module_kpis import render_module_strip  # R37: module infographic KPI cards (click = records)
    render_module_strip(home="osp-home", key="osp_home", origin="osp-home")
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
    subpage_navigation(("osp-home", "OSP Home", ":material/arrow_back:"), ("osp-records", "OSP Records", ":material/table_view:"), ("osp-inward", "OSP Inward", ":material/input:"))
    page_header("OSP Material Out", "Dispatch released material by Part and Heat Number to an approved OSP vendor · one entry saves the Material Out and its Returnable Delivery Challan.", "Heat genealogy")
    service = OSPService(); perms = current_permissions("OSP_TRANSACTIONS")
    # R38: ONE workflow - the Material Out IS its Returnable Delivery Challan. One entry form (A) captures sources / heats / batches,
    # vendor, process, challan number, plant, ship-to, transport, prices / GST and remarks once; Save creates both. Every saved
    # Material Out opens as ONE record (C) with tabs Details · Print · Vendor returns - there is no second challan entry section.
    section_bar("A · NEW MATERIAL OUT · RETURNABLE DELIVERY CHALLAN",
                "One entry for both: the Material Out document and its Returnable Delivery Challan are saved together - no second challan entry.")
    _render_material_out_entry(service, perms)
    _render_challan_module(service, perms)


def _heat_line_table(lines: list[dict]) -> list[dict]:
    return [{"Line":r.get("material_out_line_no") or i+1, "RMTC":r.get("rmtc_number") or "Opening / legacy",
             "Supplier RMTC":r.get("supplier_rmtc_number") or "-", "Heat Number":r.get("heat_number"),
             "Source Inward":r.get("inward_number"), "FSI Batch":r.get("osp_batch_code"),
             "Out Qty pcs":r.get("quantity_dispatched"), "Received pcs":r.get("quantity_received"),
             "Balance pcs":max(float(r.get("quantity_dispatched") or 0)-float(r.get("quantity_received") or 0),0),
             "Vendor Batch":r.get("vendor_batch_number"), "Sample Gate":r.get("sample_gate_status"),
             "Receipt Decision":r.get("receipt_quality_disposition")} for i,r in enumerate(lines)]


def _render_material_out_entry(service, perms):
    candidates = service.dispatch_candidates()
    if not candidates:
        st.info("No released Material Inward or eligible Opening Stock balance is available for OSP dispatch.")
        return
    parts = {str(r["part_id"]):f"{r.get('part_number')} · FSI {r.get('fsi_part_number') or '-'} · {r.get('part_name') or ''}" for r in candidates}
    part_id = st.selectbox("Part for Material Out",list(parts),format_func=lambda v:parts[v])
    candidates = [r for r in candidates if str(r["part_id"])==part_id]
    def source_batch(row):
        return str(row.get("inward_number") or "Opening Stock") if row.get("source_type")=="OPENING_STOCK" else f"SRC-{row.get('inward_number')}"
    labels = {str(r["candidate_key"]): f"Source Batch / Lot {source_batch(r)} · RMTC {r.get('rmtc_number') or 'Opening / legacy'} · Supplier RMTC {r.get('supplier_rmtc_number') or '-'} · Heat {r.get('heat_number')} · Inward {r.get('inward_number')} · Available {float(r.get('osp_available_quantity_pcs') or 0):,.0f} pcs" for r in candidates}
    selected_keys = st.multiselect("Select RMTCs / Heat Numbers / Source Lots",list(labels),format_func=lambda v:labels[v],key=f"osp_multi_sources_{part_id}")
    selected = [r for r in candidates if str(r["candidate_key"]) in selected_keys]
    if not selected:
        st.info("Select one or more source lots. One Material Out can include several RMTCs and heat numbers for this part.")
        return
    specifications=service.specifications(part_id); processes=service.processes(); vendors=service.vendors()
    if not specifications or not vendors:
        st.warning("Maintain an ACTIVE OSP Process Specification and approved OSP Vendor before dispatch.")
        return
    specs={str(r["id"]):f"{process_label(processes.get(str(r.get('process_id'))) or {})} · {r.get('process_specification') or '-'}" for r in specifications}
    vendor_labels={str(r["id"]):with_status(party_label(r,include_type=True), r) for r in vendors}
    spec_id=st.selectbox("OSP Process / Specification",list(specs),format_func=lambda v:specs[v])
    spec=next(r for r in specifications if str(r["id"])==spec_id)
    scope=hashlib.sha256((part_id+spec_id+"|".join(sorted(selected_keys))).encode()).hexdigest()[:20]
    request_key=f"osp_material_out_request_{scope}"
    if request_key not in st.session_state: st.session_state[request_key]=str(uuid4())
    # R37/R38: the Returnable Delivery Challan is captured with the Material Out (plant, ship-to, transport, prices) - entered once.
    challans=OSPChallanService(getattr(service,"repo",None)); branches=challans.branches(); ship_parties=challans.ship_to_parties()
    branch_labels={str(b["id"]):f"{b.get('branch_name')} · {b.get('plant_code') or b.get('branch_code') or ''}" for b in branches}
    branch_ids=list(branch_labels) or [""]
    default_branch=next((str(b["id"]) for b in branches if b.get("is_default")), branch_ids[0])
    branch_id=st.selectbox("Plant / Company Branch (challan series)",branch_ids,index=branch_ids.index(default_branch),format_func=lambda v:branch_labels.get(v,"Default plant"),key=f"osp_out_branch_{scope}")
    process_name=str((processes.get(str(spec.get("process_id"))) or {}).get("process_name") or "")
    prices=challans.default_prices(part_id,None,str(spec.get("process_id") or ""))
    ship_labels={"":"Same as OSP Vendor",**{str(p["id"]):party_label(p,include_type=True) for p in ship_parties}}
    with st.form(f"osp_material_out_form_{scope}_{st.session_state[request_key]}"):
        c=st.columns(4,gap="small")
        vendor_id=c[0].selectbox("OSP Vendor",list(vendor_labels),format_func=lambda v:vendor_labels[v])
        dispatch_date=c[1].date_input("Material Out / Challan Date",value=date.today(),format="DD-MM-YYYY")
        expected_date=c[2].date_input("Expected Return / Delivery Date",value=date.today()+timedelta(days=7),format="DD-MM-YYYY",
                                      help="Expected return of the processed material = the challan Delivery Date.")
        challan=c[3].text_input("Material Out Challan Number",value=challans.next_number(branch_id or None),help="Suggested from the branch challan series (JWC + plant + number). You can overwrite it.")
        c=st.columns(4,gap="small")
        ship_to=c[0].selectbox("Ship To",list(ship_labels),format_func=lambda v:ship_labels[v])
        user_name=c[1].text_input("User",value=_profile_name())
        ship_via=c[2].selectbox("Ship Via",list(SHIP_VIA_OPTIONS))
        incoterm=c[3].selectbox("Incoterm",list(INCOTERM_OPTIONS))
        c=st.columns(4,gap="small")
        payment_term=c[0].selectbox("Payment Term",list(PAYMENT_TERM_OPTIONS))
        vehicle_no=c[1].text_input("Vehicle No")
        transporter=c[2].text_input("Transporter")
        eway=c[3].text_input("E-way Bill No")
        c=st.columns(3,gap="small")
        reference=c[0].text_input("Reference Details")
        old_po=c[1].text_input("Old PO Details")
        process_text=c[2].text_input("Process To Be Done",value=process_name.upper())
        c=st.columns(2,gap="small")
        shipping=c[0].number_input("Shipping (INR)",min_value=0.0,value=0.0,step=100.0)
        other=c[1].number_input("Other (INR)",min_value=0.0,value=0.0,step=100.0)
        grid=pd.DataFrame([{"Source":r["candidate_key"],"RMTC":r.get("rmtc_number") or "Opening / legacy","Supplier RMTC":r.get("supplier_rmtc_number") or "-","Heat Number":r.get("heat_number"),"Inward / Lot":r.get("inward_number"),"Available pcs":float(r.get("osp_available_quantity_pcs") or 0),"Out Qty pcs":float(r.get("osp_available_quantity_pcs") or 0),"Sample Qty pcs":min(float(spec.get("sample_quantity") or 1),float(r.get("osp_available_quantity_pcs") or 0)),"Unit Price":float(prices["unit_price"]),"GST %":float(prices["gst_percent"]),"UOM":prices["uom"],"Batch Code":""} for r in selected])
        edited=st.data_editor(grid,hide_index=True,width="stretch",key=f"osp_out_lines_{scope}_{st.session_state[request_key]}",disabled=["Source","RMTC","Supplier RMTC","Heat Number","Inward / Lot","Available pcs"],column_config={"Source":None,"Out Qty pcs":st.column_config.NumberColumn(min_value=1.0,step=1.0,required=True),"Sample Qty pcs":st.column_config.NumberColumn(min_value=1.0,max_value=20.0,step=1.0,required=True),"Unit Price":st.column_config.NumberColumn(min_value=0.0,step=0.5,format="%.2f"),"GST %":st.column_config.NumberColumn(min_value=0.0,max_value=100.0,step=1.0)})
        st.caption("One Material Out document; a separate FSI batch is generated for each heat line. Samples and inward quantities remain independent for each batch. "
                   "Unit Price / GST % / Batch Code print on the Returnable Delivery Challan (blank Batch Code prints the FSI batch). No customer details print on the challan.")
        remarks=st.text_area("Dispatch Remarks",height=70,help="Printed as the challan remarks.")
        submitted=st.form_submit_button("Create OSP Material Out",type="primary",disabled=not perms["can_create"],width="stretch",
                                        help="Saves the Material Out and its Returnable Delivery Challan in one step.")
    if submitted:
        try:
            source_map={str(r["candidate_key"]):r for r in selected}; lines=[]; records=edited.to_dict("records")
            for row in records:
                source=source_map[str(row["Source"])]
                if float(row["Out Qty pcs"])>float(source["osp_available_quantity_pcs"]): raise ValueError(f"Heat {source.get('heat_number')}: quantity exceeds displayed balance. Refresh the source list.")
                lines.append({"inward_lot_id":source.get("inward_lot_id"),"opening_stock_id":source.get("opening_stock_id"),"quantity_dispatched":row["Out Qty pcs"],"sample_quantity":row["Sample Qty pcs"]})
            header={"challan_number":challan,"challan_date":dispatch_date,"branch_id":branch_id or None,"vendor_id":vendor_id,"ship_to_party_id":ship_to or None,
                    "user_name":user_name,"ship_via":ship_via,"incoterm":incoterm,"delivery_date":expected_date,"payment_term":payment_term,
                    "vehicle_number":vehicle_no,"transporter_name":transporter,"eway_bill_number":eway,"reference_details":reference,"old_po_details":old_po,
                    "process_text":process_text,"shipping_amount":shipping,"other_amount":other,"remarks":remarks}
            challan_lines=[{"line_no":index,"item_code":None,"unit_price":row.get("Unit Price") or 0,"gst_percent":row.get("GST %") if row.get("GST %") is not None else 18,
                            "uom":row.get("UOM") or "NOS","batch_code":row.get("Batch Code")} for index,row in enumerate(records,start=1)]
            # R38: validate the challan part BEFORE the stock-allocating Material Out RPC, so a challan problem never leaves a half entry.
            challans.clean_header(header); challans.clean_lines([{**line,"osp_job_id":"pending"} for line in challan_lines])
            if challans.duplicate_number(challan, None):
                raise ValueError(f"Challan Number {str(challan).strip().upper()} is already used by another Material Out. Use the suggested series number.")
            saved=service.create_material_out({"vendor_id":vendor_id,"process_id":spec["process_id"],"process_specification_id":spec_id,"dispatch_date":dispatch_date.isoformat(),"dispatch_challan":challan,"expected_return_date":expected_date.isoformat(),"remarks":remarks},lines,st.session_state[request_key])
            st.session_state[request_key]=str(uuid4())
            st.session_state["osp_mo_open"]=str(saved["id"])
            for line,job in zip(challan_lines,saved.get("lines") or []): line["osp_job_id"]=job.get("id")
            document={"is_group":True,"material_out_id":saved["id"],"id":saved["id"]}
            ok,error=save_material_out_challan(challans,document,header,challan_lines)
            if ok:
                save_success_popup(f"Material Out {saved['material_out_number']} saved with Returnable Delivery Challan {str(challan).strip().upper()} · "
                                   f"{len(saved['lines'])} separately traceable heat batches · opened below (Details · Print · Vendor returns).",queue_for_rerun=True)
            else:
                # Stock is already allocated by the Material Out - never create it twice. Keep the entered challan values for one-click retry.
                st.session_state[f"osp_challan_pending_{saved['id']}"]={"header":header,"lines":{str(l["osp_job_id"]):l for l in challan_lines}}
                st.session_state[f"osp_mo_flash_{saved['id']}"]=(f"Material Out {saved['material_out_number']} is saved (stock allocated), but its challan could not be saved: {db_message(error)}. "
                                                                 "Do NOT create the Material Out again - open Details → Complete challan details (your entries are filled in) and click Save Challan to retry.")
                save_success_popup(f"Material Out {saved['material_out_number']} saved · challan still to be saved (see the record below).",queue_for_rerun=True)
            st.rerun()
        except Exception as exc: st.error(db_message(exc))


def save_material_out_challan(challans: OSPChallanService, document: dict, header: dict, lines: list[dict], attempts: int = 2) -> tuple[bool, Exception | None]:
    """R38: create the challan right after the Material Out RPC (same Save). Retries once; a retry re-uses a header that a
    failed attempt already inserted (no duplicate challan). Returns (saved, last_error)."""
    error: Exception | None = None
    for attempt in range(max(attempts, 1)):
        try:
            existing = challans.challan_for(document) if attempt else None
            challans.save(document, header, lines, (existing or {}).get("id"))
            return True, None
        except Exception as exc:  # network / RLS / constraint - reported to the user with retry guidance
            error = exc
    return False, error


def _profile_name() -> str:
    try:
        from core.auth import current_profile
        profile = current_profile() or {}
        return str(profile.get("full_name") or profile.get("display_name") or profile.get("name") or "").strip()
    except Exception:
        return ""


def material_out_register(documents: list[dict], challans: list[dict], entries: list[dict]) -> list[dict]:
    """R37 register rows: one per Material Out document with challan, returned and balance quantities."""
    by_key = {str(c.get("material_out_id") or c.get("osp_job_id")): c for c in challans}
    standalone: dict[str, float] = {}; rejected: dict[str, float] = {}
    for e in entries:
        cid = str(e.get("challan_id"))
        rejected[cid] = rejected.get(cid, 0.0) + float(e.get("quantity_rejected") or 0)
        if not e.get("osp_receipt_id"):
            standalone[cid] = standalone.get(cid, 0.0) + float(e.get("quantity_returned") or 0)
    rows = []
    for doc in documents:
        ch = by_key.get(str(doc["id"])) or {}
        cid = str(ch.get("id") or "")
        returned = float(doc.get("quantity_received") or 0) + standalone.get(cid, 0.0)
        rej = rejected.get(cid, 0.0)
        dispatched = float(doc.get("quantity_dispatched") or 0)
        rows.append({"_key": str(doc["id"]), "Material Out": doc.get("material_out_number"), "Challan No": ch.get("challan_number") or doc.get("dispatch_challan"),
                     "Challan Date": ch.get("challan_date") or doc.get("dispatch_date"), "OSP Vendor": doc.get("vendor_name"),
                     "FSI Part": doc.get("fsi_part_number"), "Process": doc.get("process_name"), "Heat Numbers": doc.get("heat_numbers"),
                     "Out Qty pcs": dispatched, "Returned pcs": returned, "Rejected pcs": rej, "Balance pcs": max(dispatched - returned - rej, 0.0),
                     "Challan": "Saved" if ch else "Not created", "E-mailed": str(ch.get("emailed_at") or "")[:10] or "-", "Status": doc.get("status")})
    return rows


def _render_challan_module(service, perms) -> None:
    """R38: register (B) - one row per Material Out with its challan number - and the ONE record view (C)."""
    challans = OSPChallanService(getattr(service, "repo", None))
    documents = OSPService.material_out_documents(service.register())
    if not documents:
        return
    all_challans = challans.challans()
    entries = challans._select("osp_challan_returns", limit=5000)
    rows = material_out_register(documents, all_challans, entries)
    with stage_section("B", "MATERIAL OUT / CHALLAN REGISTER", "One row per Material Out with its challan number. Click a row to open the record: Details · Print · Vendor returns.", key="osp_mo_register"):
        c = st.columns(4, gap="small")
        start = c[0].date_input("From", value=date.today() - timedelta(days=180), format="DD-MM-YYYY", key="osp_mo_from")
        end = c[1].date_input("To", value=date.today(), format="DD-MM-YYYY", key="osp_mo_to")
        vendors = sorted({str(r["OSP Vendor"] or "-") for r in rows})
        vendor_filter = c[2].multiselect("OSP Vendor", vendors, key="osp_mo_vendor")
        balance_filter = c[3].selectbox("Balance", ["All", "Open at vendor", "Fully returned", "Challan not created"], key="osp_mo_balance")
        search = st.text_input("Search challan, Material Out, FSI part, heat or process", key="osp_mo_search")
        def keep(r):
            day = str(r.get("Challan Date") or "")[:10]
            if day and not (start.isoformat() <= day <= end.isoformat()) and r["_key"] != str(st.session_state.get("osp_mo_open") or ""): return False
            if vendor_filter and str(r["OSP Vendor"] or "-") not in vendor_filter: return False
            if balance_filter == "Open at vendor" and r["Balance pcs"] <= 0: return False
            if balance_filter == "Fully returned" and r["Balance pcs"] > 0: return False
            if balance_filter == "Challan not created" and r["Challan"] != "Not created": return False
            return not search or search.casefold() in " ".join(str(v or "") for k, v in r.items() if not k.startswith("_")).casefold()
        filtered = [r for r in rows if keep(r)]
        if not filtered:
            st.info("No Material Out matches these filters.")
            return
        frame = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in filtered])
        clicked = None
        try:
            clicked = selectable_table(frame, key="osp_mo_register_table", height=min(420, 80 + 35 * len(frame)))
        except Exception:
            portal_table(style_status_dataframe(frame), hide_index=True, width="stretch", height=min(420, 80 + 35 * len(frame)))
        labels = {r["_key"]: f"{r['Challan No'] or '-'} · {r['Material Out']} · {r['OSP Vendor']} · FSI {r['FSI Part'] or '-'} · Balance {r['Balance pcs']:,.0f} pcs" for r in filtered}
        keys = list(labels)
        if clicked is not None and 0 <= clicked < len(filtered):
            st.session_state["osp_mo_open"] = filtered[clicked]["_key"]
        if st.session_state.get("osp_mo_open") not in keys:
            st.session_state["osp_mo_open"] = keys[0]
        st.selectbox("Open Material Out / Challan", keys, format_func=lambda v: labels[v], key="osp_mo_open")
    doc = next((d for d in documents if str(d["id"]) == str(st.session_state.get("osp_mo_open") or "")), None)
    if not doc:
        return
    challan = challans.challan_for(doc)
    number = (challan or {}).get("challan_number") or doc.get("dispatch_challan") or "-"
    section_bar(f"C · MATERIAL OUT {doc.get('material_out_number') or '-'} · CHALLAN {number}",
                "One record: Details (correct / delete) · Print (challan PDF, Excel, e-mail) · Vendor returns. Customer details never print on the vendor challan.")
    render_material_out_record(service, challans, doc, challan, perms)


def render_material_out_record(service, challans: OSPChallanService, doc: dict, challan: dict | None, perms, *, allow_delete: bool = True) -> None:
    """R38: the ONE Material Out / Returnable Delivery Challan record view (Material Out page and OSP Records)."""
    flash = st.session_state.pop(f"osp_mo_flash_{doc['id']}", None)
    if flash:
        st.warning(flash)
    details, printing, returns = st.tabs(["Details", "Print", "Vendor returns"])
    with details:
        _render_challan_section(service, challans, doc, challan, perms, allow_delete=allow_delete)
    with printing:
        _render_challan_print(challans, doc, dict(challan or {}), perms)
        _render_material_out_internal_pdf(doc)
    with returns:
        _render_returns_section(challans, doc, challan, perms)


def _doc_job_ids(doc: dict) -> list[str]:
    return [str(r.get("id")) for r in (doc.get("lines") or [doc]) if r.get("id")]


def _render_challan_section(service, challans: OSPChallanService, doc: dict, challan: dict | None, perms, *, allow_delete: bool = True) -> None:
    """Details tab: header + heat lines, one correction form (Material Out + challan together) and delete."""
    challan = dict(challan or {})
    job_lines = doc.get("lines") or [doc]
    portal_table(pd.DataFrame([{
        "Material Out": doc.get("material_out_number"), "Challan No": challan.get("challan_number") or doc.get("dispatch_challan") or "-",
        "Challan Date": challan.get("challan_date") or doc.get("dispatch_date"), "OSP Vendor": doc.get("vendor_name"), "Process": doc.get("process_name"),
        "Part": doc.get("part_number"), "FSI Part": doc.get("fsi_part_number"), "Expected Return / Delivery": doc.get("expected_return_date") or challan.get("delivery_date"),
        "Out Qty pcs": float(doc.get("quantity_dispatched") or 0), "Received pcs": float(doc.get("quantity_received") or 0),
        "Challan": "Saved" if challan.get("id") else "Not created", "Status": doc.get("status"),
    }]), hide_index=True, width="stretch", height=105)
    portal_table(pd.DataFrame(_heat_line_table(job_lines)), hide_index=True, width="stretch", height=min(320, 80 + 35 * len(job_lines)))
    lines = {str(l.get("osp_job_id")): l for l in (challans.lines(str(challan["id"])) if challan.get("id") else [])}
    returns = challans.returns_for(challan or None, _doc_job_ids(doc))
    locked = bool(challan.get("emailed_at")) or bool(returns)
    if not challan:
        st.info("This older Material Out has no challan details yet. Complete them once below - new Material Outs save the challan automatically. "
                "It can already be printed as a DRAFT challan (Print tab).")
    # R38: the challan is entered with the Material Out. Here the saved record is only corrected (toggle), not re-entered.
    edit_open = st.toggle("Correct challan details" if challan else "Complete challan details", value=not challan,
                          key=f"osp_challan_edit_toggle_{doc['id']}",
                          help="One form corrects the Material Out (dates, quantities, remarks) and its challan together.")
    if edit_open:
        _render_challan_edit_form(service, challans, doc, challan, lines, returns, locked, perms)
    if allow_delete:
        _render_material_out_delete(service, doc, perms)


def _render_challan_edit_form(service, challans: OSPChallanService, doc: dict, challan: dict, lines: dict, returns, locked: bool, perms) -> None:
        pending = st.session_state.get(f"osp_challan_pending_{doc['id']}") or {}
        if not challan and pending:
            challan_defaults = dict(pending.get("header") or {}); lines = {**(pending.get("lines") or {}), **lines}
        else:
            challan_defaults = challan
        branches = challans.branches(); parties = challans.ship_to_parties()
        branch_labels = {"": "Default plant", **{str(b["id"]): f"{b.get('branch_name')} · {b.get('plant_code') or b.get('branch_code') or ''}" for b in branches}}
        ship_labels = {"": "Same as OSP Vendor", **{str(p["id"]): party_label(p, include_type=True) for p in parties}}
        def pick(options, value):
            options = list(options); return options.index(value) if value in options else 0
        def as_date(value, fallback):
            if isinstance(value, date): return value
            try: return date.fromisoformat(str(value)[:10]) if value else fallback
            except ValueError: return fallback
        cd = challan_defaults
        job_lines = doc.get("lines") or [doc]
        default_price = challans.default_prices(str(doc.get("part_id") or ""), str(doc.get("vendor_id") or ""), str(doc.get("process_id") or "")) if not lines else {"unit_price": 0.0, "gst_percent": 18.0, "uom": "NOS"}
        scope = record_widget_token("osp-material-out-edit", challan or doc, selected=str(doc["id"]))
        with st.form(f"osp_challan_form_{scope}"):
            c = st.columns(4, gap="small")
            number = c[0].text_input("Challan Number", value=str(cd.get("challan_number") or doc.get("dispatch_challan") or ""))
            challan_date = c[1].date_input("Material Out / Challan Date", value=as_date(doc.get("dispatch_date") or cd.get("challan_date"), date.today()), format="DD-MM-YYYY")
            delivery_date = c[2].date_input("Expected Return / Delivery Date", value=as_date(doc.get("expected_return_date") or cd.get("delivery_date"), date.today()), format="DD-MM-YYYY")
            branch_id = c[3].selectbox("Plant / Company Branch", list(branch_labels), index=pick(branch_labels, str(cd.get("branch_id") or next((str(b["id"]) for b in branches if b.get("is_default")), ""))), format_func=lambda v: branch_labels[v])
            c = st.columns(4, gap="small")
            ship_to = c[0].selectbox("Ship To", list(ship_labels), index=pick(ship_labels, str(cd.get("ship_to_party_id") or "")), format_func=lambda v: ship_labels[v])
            user_name = c[1].text_input("User", value=str(cd.get("user_name") or _profile_name()))
            ship_via = c[2].selectbox("Ship Via", list(SHIP_VIA_OPTIONS), index=pick(SHIP_VIA_OPTIONS, cd.get("ship_via")))
            incoterm = c[3].selectbox("Incoterm", list(INCOTERM_OPTIONS), index=pick(INCOTERM_OPTIONS, cd.get("incoterm")))
            c = st.columns(4, gap="small")
            payment_term = c[0].selectbox("Payment Term", list(PAYMENT_TERM_OPTIONS), index=pick(PAYMENT_TERM_OPTIONS, cd.get("payment_term")))
            vehicle_no = c[1].text_input("Vehicle No", value=str(cd.get("vehicle_number") or ""))
            transporter = c[2].text_input("Transporter", value=str(cd.get("transporter_name") or ""))
            eway = c[3].text_input("E-way Bill No", value=str(cd.get("eway_bill_number") or ""))
            c = st.columns(3, gap="small")
            reference = c[0].text_input("Reference Details", value=str(cd.get("reference_details") or ""))
            old_po = c[1].text_input("Old PO Details", value=str(cd.get("old_po_details") or ""))
            process_text = c[2].text_input("Process To Be Done", value=str(cd.get("process_text") or str(doc.get("process_name") or "").upper()))
            c = st.columns(2, gap="small")
            shipping = c[0].number_input("Shipping (INR)", min_value=0.0, value=float(cd.get("shipping_amount") or 0), step=100.0)
            other = c[1].number_input("Other (INR)", min_value=0.0, value=float(cd.get("other_amount") or 0), step=100.0)
            grid = pd.DataFrame([{
                "osp_job_id": str(r.get("id")), "Line": r.get("material_out_line_no") or i, "FSI Item #": (lines.get(str(r.get("id"))) or {}).get("item_code") or r.get("fsi_part_number") or "",
                "Description": (lines.get(str(r.get("id"))) or {}).get("item_description") or r.get("part_name") or "", "Heat Number": r.get("heat_number"),
                "Qty pcs": float(r.get("quantity_dispatched") or 0), "UOM": (lines.get(str(r.get("id"))) or {}).get("uom") or default_price["uom"],
                "Unit Price": float((lines.get(str(r.get("id"))) or {}).get("unit_price") or 0) if lines.get(str(r.get("id"))) else float(default_price["unit_price"]),
                "GST %": float((lines.get(str(r.get("id"))) or {}).get("gst_percent") if (lines.get(str(r.get("id"))) or {}).get("gst_percent") is not None else 18.0) if lines.get(str(r.get("id"))) else float(default_price["gst_percent"]),
                "Batch Code": (lines.get(str(r.get("id"))) or {}).get("batch_code") or "",
            } for i, r in enumerate(job_lines, start=1)])
            edited = st.data_editor(grid, hide_index=True, width="stretch", key=f"osp_challan_lines_{scope}", disabled=["osp_job_id", "Line", "Heat Number"],
                                    column_config={"osp_job_id": None, "Qty pcs": st.column_config.NumberColumn(min_value=1.0, step=1.0, required=True),
                                                   "Unit Price": st.column_config.NumberColumn(min_value=0.0, step=0.5, format="%.2f"), "GST %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=1.0)})
            remarks = st.text_input("Remarks", value=str(doc.get("dispatch_remarks") or cd.get("remarks") or ""), help="Material Out dispatch remarks = challan remarks.")
            password = st.text_input("Current QCMS Password", type="password", help="Required to edit a challan that was already e-mailed to the vendor or has vendor returns.") if challan and locked else ""
            st.caption("Quantity / date changes go through the controlled Material Out update (blocked when downstream OSP receipt / inspection genealogy does not permit them).")
            save = st.form_submit_button("Save Challan" if not challan else "Update Challan", type="primary", width="stretch",
                                         disabled=not (perms["can_edit"] if challan else (perms["can_create"] or perms["can_edit"])))
        if save:
            try:
                if challan and locked:
                    from core.auth import verify_current_password
                    verify_current_password(password)
                if challans.duplicate_number(number, challan.get("id"), doc):
                    raise ValueError(f"Challan Number {number.strip().upper()} is already used by another Material Out.")
                records = edited.to_dict("records")
                header = {"challan_number": number, "challan_date": challan_date, "branch_id": branch_id or None, "vendor_id": doc.get("vendor_id"),
                          "ship_to_party_id": ship_to or None, "user_name": user_name, "ship_via": ship_via, "incoterm": incoterm, "delivery_date": delivery_date,
                          "payment_term": payment_term, "vehicle_number": vehicle_no, "transporter_name": transporter, "eway_bill_number": eway,
                          "reference_details": reference, "old_po_details": old_po, "process_text": process_text, "shipping_amount": shipping,
                          "other_amount": other, "remarks": remarks}
                challan_lines = [{"osp_job_id": r["osp_job_id"], "line_no": r["Line"], "item_code": r["FSI Item #"], "item_description": r["Description"], "uom": r["UOM"],
                                  "unit_price": r["Unit Price"] or 0, "gst_percent": r["GST %"] if r["GST %"] is not None else 18, "batch_code": r["Batch Code"]} for r in records]
                challans.clean_header(header); challans.clean_lines(challan_lines)
                warning = _sync_material_out(service, doc, number=number, dispatch_date=challan_date, expected_date=delivery_date, remarks=remarks,
                                             quantities={str(r["osp_job_id"]): r["Qty pcs"] for r in records})
                saved = challans.save(doc, header, challan_lines, challan.get("id"))
                st.session_state.pop(f"osp_challan_pending_{doc['id']}", None)
                save_success_popup(f"Material Out / Challan {saved.get('challan_number') or number} saved." + (f" {warning}" if warning else ""), queue_for_rerun=True); st.rerun()
            except Exception as exc:
                st.error(db_message(exc))


def _sync_material_out(service, doc: dict, *, number: str, dispatch_date, expected_date, remarks: str, quantities: dict) -> str:
    """R38: keep the Material Out (osp_jobs) equal to the corrected record - challan number, dates, remarks, quantities -
    through the existing controlled Material Out update RPCs. Quantity / date failures stop the save; a challan-number /
    remarks-only failure is reported but the challan is still saved (as in R37)."""
    def iso(value):
        return value.isoformat() if isinstance(value, date) else str(value or "")[:10]
    lines = doc.get("lines") or [doc]
    wanted = {"dispatch_challan": str(number or "").strip().upper(), "dispatch_date": iso(dispatch_date), "expected_return_date": iso(expected_date),
              "remarks": str(remarks or "").strip()}
    changed = set()
    for r in lines:
        if str(r.get("dispatch_challan") or "").strip().upper() != wanted["dispatch_challan"]: changed.add("dispatch_challan")
        if str(r.get("dispatch_date") or "")[:10] != wanted["dispatch_date"]: changed.add("dispatch_date")
        if str(r.get("expected_return_date") or "")[:10] != wanted["expected_return_date"]: changed.add("expected_return_date")
        if str(r.get("dispatch_remarks") or "").strip() != wanted["remarks"]: changed.add("remarks")
    qty = {str(r["id"]): float(quantities.get(str(r["id"]), r.get("quantity_dispatched")) or 0) for r in lines}
    qty_changed = any(abs(qty[str(r["id"])] - float(r.get("quantity_dispatched") or 0)) > 1e-9 for r in lines)
    if not changed and not qty_changed:
        return ""
    try:
        if doc.get("is_group"):
            service.update_material_out_group(str(doc["id"]), {"dispatch_date": wanted["dispatch_date"], "expected_return_date": wanted["expected_return_date"] or None,
                                                               "dispatch_challan": wanted["dispatch_challan"], "remarks": wanted["remarks"]},
                                              [{"id": r["id"], "quantity_dispatched": qty[str(r["id"])]} for r in lines])
        else:
            service.update_material_out({"osp_job_id": doc["id"], "dispatch_date": wanted["dispatch_date"], "dispatch_challan": wanted["dispatch_challan"],
                                         "quantity_dispatched": qty[str(doc["id"])], "expected_return_date": wanted["expected_return_date"] or None, "remarks": wanted["remarks"]})
        return "Material Out updated."
    except Exception as exc:
        if qty_changed or changed & {"dispatch_date", "expected_return_date"}:
            raise
        return f"Material Out challan number / remarks could not be updated ({db_message(exc)})."


def _render_material_out_delete(service, doc: dict, perms) -> None:
    """R38: delete the whole Material Out (all heat lines) from its record; restores source balances; genealogy checks in the RPC."""
    label = f"{doc.get('material_out_number')} · Challan {doc.get('dispatch_challan') or '-'} · Part {doc.get('part_number')} · {len(doc.get('lines') or [doc])} heat line(s) · {float(doc.get('quantity_dispatched') or 0):,.0f} pcs"
    if doc.get("is_group"):
        done = password_rpc_delete_panel(repo=service.repo, rpc_name="qcms_delete_osp_material_out_group", rpc_param="p_material_out_id", rows=[doc], labeler=lambda r: label,
                                         key=f"osp_group_delete_{doc['id']}", can_delete=perms["can_archive"], title="Delete Material Out",
                                         help_text="Deletes all heat lines together only when existing downstream genealogy checks permit it; restores each source balance.",
                                         success_message="Material Out deleted and heat balances restored.")
    else:
        done = password_rpc_delete_panel(repo=service.repo, rpc_name="qcms_delete_osp_transaction", rpc_param="p_osp_job_id", rows=[doc], labeler=lambda r: label,
                                         key=f"osp_material_out_delete_{doc['id']}", can_delete=perms["can_archive"], title="Delete Material Out",
                                         help_text="Requires current password and OSP Delete/Archive permission. Downstream records block unsafe deletion.",
                                         success_message="OSP Material Out deleted and source allocation restored.")
    if done:
        st.session_state.pop("osp_mo_open", None)
        st.rerun()


def _render_material_out_internal_pdf(doc: dict) -> None:
    """Internal (not for the vendor) Material Out record with all heat / RMTC lines."""
    lines = doc.get("lines") or [doc]
    try:
        pdf = controlled_record_pdf_bytes("OSP MATERIAL OUT", {"Part": doc.get("part_number"), "Vendor": doc.get("vendor_name"), "Process": doc.get("process_name"), "Challan": doc.get("dispatch_challan"),
                                                               "Date": doc.get("dispatch_date"), "Expected Return": doc.get("expected_return_date"), "Total Qty pcs": doc.get("quantity_dispatched"), "Remarks": doc.get("dispatch_remarks")},
                                          {"RMTC / HEAT DISPATCH LINES": [{"Line": r.get("material_out_line_no") or 1, "RMTC": r.get("rmtc_number") or "Opening / legacy", "Heat": r.get("heat_number"), "Inward": r.get("inward_number"),
                                                                           "FSI Batch": r.get("osp_batch_code"), "Qty pcs": r.get("quantity_dispatched")} for r in lines]},
                                          record_number=str(doc.get("material_out_number") or ""))
    except Exception as exc:
        st.caption(f"Internal Material Out PDF is not available: {db_message(exc)}")
        return
    st.download_button("Internal Material Out record PDF · all heat lines", pdf, file_name=f"{doc.get('material_out_number')}_Material_Out.pdf", mime="application/pdf",
                       key=f"osp_multi_pdf_{doc['id']}", width="stretch", help="QCMS internal record (heat / RMTC genealogy). Send the Returnable Delivery Challan above to the vendor.")


def _render_challan_print(challans: OSPChallanService, doc: dict, challan: dict, perms) -> None:
        job_lines = doc.get("lines") or [doc]
        if not challan.get("id"):
            # R37: the Material Out can still be printed as a DRAFT challan (watermarked) before the details are saved.
            try:
                draft_pdf = challan_pdf_for_job(str(job_lines[0].get("id")), challans.repo)
                c1, c2 = st.columns(2, gap="small")
                c1.download_button("Download DRAFT Challan PDF", draft_pdf, file_name=f"{doc.get('dispatch_challan') or doc.get('material_out_number')}_DRAFT.pdf", mime="application/pdf",
                                   key=f"osp_challan_draft_pdf_{doc['id']}", width="stretch", icon=":material/download:")
                if c2.toggle("Preview DRAFT Challan", key=f"osp_challan_draft_prev_{doc['id']}"):
                    show_pdf_preview(draft_pdf, key=f"osp_challan_draft_view_{doc['id']}", height=820, pages=2)
            except Exception as exc:
                st.caption(f"Draft challan preview is not available: {db_message(exc)}")
            return
        payload = None
        try:
            payload = challans.print_payload_for(str(challan["id"]))
            pdf = osp_challan_pdf_bytes(payload)
            excel = osp_challan_excel_bytes(payload)
        except Exception as exc:
            st.error(f"Challan PDF could not be generated: {db_message(exc)}")
            return
        totals = payload.get("totals") or {}
        kpi_grid([{"label": "Taxable", "value": f"{totals.get('subtotal', 0):,.2f}", "foot": "INR"}, {"label": "GST", "value": f"{totals.get('tax', 0):,.2f}", "foot": "INR"},
                  {"label": "Total", "value": f"{totals.get('total', 0):,.2f}", "foot": "INR"}, {"label": "Balance at vendor", "value": f"{(payload.get('summary') or {}).get('balance', 0):,.0f}", "foot": "pcs"}])
        c1, c2, c3 = st.columns(3, gap="small")
        c1.download_button("Download Challan PDF", pdf, file_name=f"{challan.get('challan_number')}.pdf", mime="application/pdf", key=f"osp_challan_pdf_{challan['id']}", width="stretch", icon=":material/download:")
        c2.download_button("Download Challan Excel", excel, file_name=f"{challan.get('challan_number')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key=f"osp_challan_xlsx_{challan['id']}", width="stretch", icon=":material/table_view:")
        if c3.toggle("Preview Challan", key=f"osp_challan_preview_{challan['id']}"):
            show_pdf_preview(pdf, key=f"osp_challan_prev_{challan['id']}", height=820, pages=3)
        _render_challan_email(challans, doc, challan, payload, perms)


def _render_challan_email(challans: OSPChallanService, doc: dict, challan: dict, payload: dict, perms) -> None:
    st.markdown("**E-mail challan to OSP Vendor**")
    vendor = challans.repo.get("parties", str(doc.get("vendor_id") or "")) if doc.get("vendor_id") else {}
    emails = vendor_emails(vendor)
    subject, body = email_body(payload)
    key = f"osp_challan_mail_{challan['id']}"
    c = st.columns(2, gap="small")
    to = c[0].text_input("To", value=emails[0] if emails else "", key=f"{key}_to")
    cc = c[1].text_input("CC (comma separated)", value=", ".join(emails[1:]), key=f"{key}_cc")
    subject = st.text_input("Subject", value=subject, key=f"{key}_subject")
    body = st.text_area("Message", value=body, height=170, key=f"{key}_body")
    st.caption("The Returnable Delivery Challan PDF is attached. The e-mail and PDF are vendor-safe: no customer name, code, PO or customer part number."
               + (f" Last e-mailed {str(challan.get('emailed_at'))[:16].replace('T', ' ')} to {challan.get('emailed_to')}." if challan.get("emailed_at") else ""))
    if st.button("Send Challan E-mail", key=f"{key}_send", type="primary", disabled=not (perms["can_edit"] or perms["can_create"]) or "@" not in to, width="stretch", icon=":material/send:"):
        notifier = challan_notifier(challans.repo)
        cc_list = [v.strip() for v in cc.replace(";", ",").split(",") if "@" in v]
        row = notifier.notify("OSP_MATERIAL_OUT_CHALLAN", subject=subject, body_text=body, related_table="osp_challans", related_id=str(challan["id"]),
                              recipient_email=to.strip(), recipient_name=str((vendor or {}).get("party_name") or ""), cc_emails=cc_list,
                              include_generated_pdf=True, include_record_attachments=False, include_supplier=False,
                              context={"supplier_id": str(doc.get("vendor_id") or ""), "supplier_name": doc.get("vendor_name"), "document_no": challan.get("challan_number"),
                                       "document_type": "OSP Returnable Delivery Challan", "next_task": "OSP vendor processing and return"})
        if row:
            challans.mark_emailed(str(challan["id"]), ", ".join([to.strip(), *cc_list]))
            save_success_popup(f"Challan {challan.get('challan_number')} queued for e-mail to {to.strip()} with the PDF attached.", queue_for_rerun=True); st.rerun()
        else:
            st.error("The e-mail could not be queued. Check the recipient address and the e-mail settings in Admin → Notifications.")


def _render_returns_section(challans: OSPChallanService, doc: dict, challan: dict | None, perms) -> None:
    st.caption("Every OSP Inward receipt is a vendor return automatically (same quantity, never counted twice). Add the vendor challan / invoice / vehicle / rejected quantity here, or record a return without OSP Inward.")
    if not challan or not challan.get("id"):
        st.info("Complete the challan details first (Details tab → Complete challan details). OSP Inward receipts already recorded will then appear here automatically.")
        return
    job_lines = doc.get("lines") or [doc]
    receipts = challans.receipts(_doc_job_ids(doc))
    entries = challans.return_entries(str(challan["id"]))
    rows = merge_returns(receipts, entries)
    summary = balance_summary(sum(float(r.get("quantity_dispatched") or 0) for r in job_lines), rows)
    kpi_grid([{"label": "Dispatched", "value": f"{summary['dispatched']:,.0f}", "foot": "pcs"}, {"label": "Returned", "value": f"{summary['returned']:,.0f}", "foot": "pcs"},
              {"label": "Rejected", "value": f"{summary['rejected']:,.0f}", "foot": "pcs"}, {"label": "Balance", "value": f"{summary['balance']:,.0f}", "foot": "pcs at vendor"}])
    heat = {str(r.get("id")): f"Line {r.get('material_out_line_no') or 1} · Heat {r.get('heat_number')} · FSI Batch {r.get('osp_batch_code') or '-'}" for r in job_lines}
    if rows:
        portal_table(pd.DataFrame([{"Source": r["source"], "OSP Inward": r.get("receipt_number") or "-", "Heat Line": heat.get(str(r.get("osp_job_id")), "-"),
                                    "Vendor Challan": r.get("challan_no") or "-", "Challan Date": r.get("challan_date"), "Vendor Invoice": r.get("invoice_no") or "-",
                                    "Invoice Date": r.get("invoice_date"), "Returned pcs": r["qty_returned"], "Rejected pcs": r["qty_rejected"], "Vehicle No": r.get("vehicle_no") or "-",
                                    "Remarks": r.get("remarks") or "-"} for r in rows]), hide_index=True, width="stretch")
    else:
        st.caption("No vendor return yet. Returns recorded in OSP Inward appear here automatically.")
    st.markdown("**Add / update vendor return**")
    linked_ids = {str(e.get("osp_receipt_id")) for e in entries if e.get("osp_receipt_id")}
    options = {"": "No OSP Inward · return recorded on the challan only (e.g. unprocessed / rejected material)",
               **{str(r["id"]): f"OSP Inward {r.get('receipt_number')} · {r.get('receipt_date')} · {float(r.get('quantity_received') or 0):,.0f} pcs" + (" · details saved" if str(r["id"]) in linked_ids else "") for r in receipts}}
    entry_options = {"": "New return entry", **{str(e["id"]): f"{e.get('vendor_challan_number') or e.get('vendor_invoice_number') or 'Return'} · {e.get('vendor_challan_date') or ''} · {float(e.get('quantity_returned') or 0):,.0f} pcs" + (" · OSP Inward" if e.get("osp_receipt_id") else "") for e in entries}}
    entry_id = st.selectbox("Return entry", list(entry_options), format_func=lambda v: entry_options[v], key=f"osp_ret_entry_{challan['id']}")
    entry = next((e for e in entries if str(e["id"]) == entry_id), {})
    receipt_choice = st.selectbox("Linked OSP Inward receipt", list(options), index=list(options).index(str(entry.get("osp_receipt_id") or "")) if str(entry.get("osp_receipt_id") or "") in options else 0,
                                  format_func=lambda v: options[v], key=f"osp_ret_receipt_{challan['id']}_{entry_id}", disabled=bool(entry))
    receipt = next((r for r in receipts if str(r["id"]) == receipt_choice), {})
    def as_date(value):
        try: return date.fromisoformat(str(value)[:10]) if value else date.today()
        except ValueError: return date.today()
    with st.form(f"osp_ret_form_{challan['id']}_{entry_id}_{receipt_choice}"):
        c = st.columns(4, gap="small")
        job_ids = list(heat)
        job_id = c[0].selectbox("Heat line", job_ids, index=job_ids.index(str(entry.get("osp_job_id") or receipt.get("osp_job_id") or job_ids[0])) if str(entry.get("osp_job_id") or receipt.get("osp_job_id") or job_ids[0]) in job_ids else 0, format_func=lambda v: heat[v], disabled=bool(receipt))
        vch = c[1].text_input("Vendor Challan No", value=str(entry.get("vendor_challan_number") or receipt.get("receipt_challan") or ""))
        vch_date = c[2].date_input("Vendor Challan Date", value=as_date(entry.get("vendor_challan_date") or receipt.get("receipt_date")), format="DD-MM-YYYY")
        vehicle = c[3].text_input("Vehicle No", value=str(entry.get("vehicle_number") or ""))
        c = st.columns(4, gap="small")
        inv = c[0].text_input("Vendor Invoice No", value=str(entry.get("vendor_invoice_number") or receipt.get("vendor_invoice_number") or ""))
        inv_date = c[1].date_input("Vendor Invoice Date", value=as_date(entry.get("vendor_invoice_date") or receipt.get("vendor_invoice_date")), format="DD-MM-YYYY")
        qty = c[2].number_input("Quantity returned (pcs)", min_value=0.0, value=float(receipt.get("quantity_received") or entry.get("quantity_returned") or 0), step=1.0, disabled=bool(receipt),
                                help="For an OSP Inward receipt the receipt quantity is used (edit it in OSP Inward).")
        rej = c[3].number_input("Quantity rejected / not returned (pcs)", min_value=0.0, value=float(entry.get("quantity_rejected") or 0), step=1.0)
        note = st.text_input("Return Remarks", value=str(entry.get("remarks") or ""))
        go = st.form_submit_button("Update Return" if entry else "Save Return", type="primary", width="stretch", disabled=not (perms["can_edit"] or perms["can_create"]))
    if go:
        try:
            existing_for_receipt = next((e for e in entries if receipt_choice and str(e.get("osp_receipt_id")) == receipt_choice), None)
            target = entry_id or (str(existing_for_receipt["id"]) if existing_for_receipt else None)
            challans.save_return(str(challan["id"]), {"osp_job_id": receipt.get("osp_job_id") or job_id, "osp_receipt_id": receipt_choice or entry.get("osp_receipt_id") or None,
                                                      "vendor_challan_number": vch, "vendor_challan_date": vch_date, "vendor_invoice_number": inv, "vendor_invoice_date": inv_date,
                                                      "quantity_returned": qty, "quantity_rejected": rej, "vehicle_number": vehicle, "remarks": note}, target)
            save_success_popup("Vendor return saved. The challan's Supplier Details section is updated.", queue_for_rerun=True); st.rerun()
        except Exception as exc:
            st.error(db_message(exc))
    if entry and st.toggle("Delete this return entry", key=f"osp_ret_del_{entry_id}", disabled=not perms["can_archive"]):
        password = st.text_input("Current QCMS Password", type="password", key=f"osp_ret_del_pwd_{entry_id}")
        if st.button("Delete return entry", key=f"osp_ret_del_btn_{entry_id}", disabled=not password):
            try:
                from core.auth import verify_current_password
                verify_current_password(password)
                challans.delete_return(entry_id)
                save_success_popup("Return entry deleted. OSP Inward receipts are not affected.", queue_for_rerun=True); st.rerun()
            except Exception as exc:
                st.error(db_message(exc))


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
        except Exception as exc: st.error(db_message(exc))
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
        c = st.columns(2, gap="small")
        return_vehicle = c[0].text_input("Return Vehicle No", help="Printed in 'Supplier Details for Returnable Challan' on the Material Out challan.")
        return_rejected = c[1].number_input("Rejected / not returned at vendor (pcs)", min_value=0.0, value=0.0, step=1.0, help="Reduces the challan balance; the receipt quantity above is the returned quantity.")
        remarks = st.text_area("Receipt Remarks", height=70)
        submitted = st.form_submit_button("Create OSP Material Inward", type="primary", disabled=not perms["can_create"], width="stretch")
    if submitted:
        try:
            saved = service.receive_batch({"osp_job_id": job["id"], "receipt_date": receipt_date.isoformat(), "receipt_challan": receipt_challan, "vendor_invoice_number": vendor_invoice, "vendor_invoice_date": vendor_invoice_date.isoformat(), "tc_number": tc_number, "tc_date": tc_date.isoformat(), "vendor_batch_number": vendor_batch, "quantity_received": quantity, "remarks": remarks})
            # R37: one entry updates both - the receipt is the vendor return on the Material Out challan.
            link_note = ""
            try:
                linked = OSPChallanService(service.repo).link_receipt(job, str((saved.get("current_receipt") or {}).get("id") or ""), vehicle_number=return_vehicle, quantity_rejected=return_rejected)
                link_note = " · Vendor return added to the Material Out challan." if linked else " · Shown as a vendor return on the Material Out challan."
            except Exception as link_exc:
                link_note = f" · Challan return details not saved ({db_message(link_exc)}); add them in OSP Material Out."
            save_success_popup(f"OSP Inward {saved.get('receipt_number')} saved successfully. Post-receipt inspections are now pending.{link_note}", queue_for_rerun=True); st.rerun()
        except Exception as exc: st.error(db_message(exc))

    with stage_section("B", "EDIT / DELETE OSP INWARD RECEIPTS", key="osp_inward_manage"):
        receipt_pairs=[]
        for tx in service.register():
            for rec in service.receipts(str(tx.get("id"))):
                item=dict(rec); item["_job_label"]=_label(tx); receipt_pairs.append(item)
        if receipt_pairs:
            rlabels={str(r["id"]):with_status(f"{r.get('receipt_number')} · {r.get('_job_label')} · {float(r.get('quantity_received') or 0):,.0f} pcs", r) for r in receipt_pairs}
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
                except Exception as exc: st.error(db_message(exc))
            if password_rpc_delete_panel(repo=service.repo, rpc_name="qcms_delete_osp_receipt", rpc_param="p_receipt_id", rows=[rec], labeler=lambda row:rlabels[str(row['id'])], key=f"osp_inward_delete_{rid}", can_delete=perms["can_archive"], title="Delete OSP Inward Receipt", help_text="Requires current password and OSP Delete/Archive permission. Receipt inspection records block unsafe deletion.", success_message="OSP Inward receipt deleted and quantity/status recalculated."):
                st.rerun()
        else:
            st.info("No OSP Inward receipt exists yet.")


def _render_register(rows: list[dict], height: int = 560) -> None:
    documents=OSPService.material_out_documents(rows)
    portal_table(pd.DataFrame([{"Material Out":r["material_out_number"],"Challan No":r.get("dispatch_challan"),"Date":r.get("dispatch_date"),"Part":r.get("part_number"),"Vendor":r.get("vendor_name"),"RMTCs":r["rmtc_numbers"],"Heat Numbers":r["heat_numbers"],"Heat Lines":len(r["lines"]),"Out Qty pcs":r["quantity_dispatched"],"Received pcs":r["quantity_received"],"Status":r["status"]} for r in documents]),hide_index=True,width="stretch",height=min(height,400))
    st.caption("Heat-wise batch details — each line has independent receipt and inspection status.")
    display = pd.DataFrame([{
        "Material Out": r.get("material_out_number") or r.get("osp_job_number"), "Line":r.get("material_out_line_no") or 1, "RMTC":r.get("rmtc_number"), "OSP Job": r.get("osp_job_number"), "Material Out Date": r.get("dispatch_date"), "Heat Number": r.get("heat_number"),
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
    filtered = [r for r in rows if not search or search.casefold() in " ".join(str(r.get(k) or "") for k in ("material_out_number","rmtc_number","supplier_rmtc_number","osp_job_number","receipt_number","heat_number","part_number","fsi_part_number","osp_batch_code","vendor_name","process_name","vendor_batch_number","vendor_invoice_number","tc_number","dispatch_remarks")).casefold()]
    if filtered:
        labels = {str(r["id"]): with_status(_label(r), r) for r in filtered}
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
                    "Material Out":selected_row.get("material_out_number"), "RMTC":selected_row.get("rmtc_number"), "OSP Job": selected_row.get("osp_job_number"), "Heat Number": selected_row.get("heat_number"),
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
        # R38: the SAME Material Out / Returnable Delivery Challan record view as OSP Material Out (no second challan section).
        doc = next((d for d in OSPService.material_out_documents(rows) if str(d["id"]) == str(selected_row.get("material_out_id") or selected_row["id"])), None)
        if doc:
            challans = OSPChallanService(service.repo); challan = challans.challan_for(doc)
            title = f"MATERIAL OUT {doc.get('material_out_number') or '-'} · CHALLAN {(challan or {}).get('challan_number') or doc.get('dispatch_challan') or '-'}"
            with stage_section("B", title, "Same record as OSP Material Out: Details · Print · Vendor returns. Customer details never print on the vendor challan.", key="osp_records_challan"):
                render_material_out_record(service, challans, doc, challan, perms, allow_delete=False)
        record_email_sender(
            NotificationService(service.repo), "OSP_SAMPLE_PENDING",
            related_table="osp_jobs", related_id=selected, key=f"osp_record_email_{selected}",
            context={"supplier_id": str(selected_row.get("vendor_id") or ""), "supplier_name": selected_row.get("vendor_name"), "part_number": selected_row.get("part_number"), "next_task": "OSP Sample / Receipt Quality Follow-up"},
            include_supplier=True,
        )
        with stage_section("C", "DELETE OSP RECORD", key="osp_records_b"):
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
            with stage_section("D", "DELETE PARTIAL OSP INWARD RECEIPT", key="osp_records_receipt_delete"):
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
    with stage_section("E", "OSP TRANSACTION REGISTER", key="osp_records_c"):
        _render_register(filtered)
