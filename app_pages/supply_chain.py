# QCMS downstream notification route keys retained for receipt stages: RM_RECEIPT_PENDING / FORGING_RECEIPT_PENDING
from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from typing import Any, Mapping, Sequence

import pandas as pd
import streamlit as st
from core.ui import portal_table

from core.access import current_permissions
from core.auth import current_profile
from core.attachments import AttachmentSlot, render_attachment_manager
from core.delete_service import password_delete_panel
from core.reporting import controlled_record_pdf_bytes, safe_excel_sheet_name
from core.purchase_order_reporting import purchase_order_pdf_bytes, DEFAULT_SPECIAL_INSTRUCTIONS
from core.notification_service import NotificationService
from core.notification_ui import notification_confirmation
from core.selection_labels import part_label, party_label
from core.supply_chain_service import (
    FLOW_DIRECT_FORGING,
    FLOW_FSI_RM,
    FLOW_LABELS,
    MONTHS,
    SupplyChainService,
    monthly_reference,
    normalize_match,
    number,
)
from core.ui import (
    kpi_grid,
    page_header,
    safe,
    save_success_popup,
    section_bar,
    stage_section,
    workflow_progress,
)

STATUS_ROW_STYLE = {
    "COMPLETED": "background-color:#ECFDF3;color:#14532D;",
    "CLOSED": "background-color:#ECFDF3;color:#14532D;",
    "ACCEPTED": "background-color:#ECFDF3;color:#14532D;",
    "POSTED": "background-color:#ECFDF3;color:#14532D;",
    "RECEIVED": "background-color:#ECFDF3;color:#14532D;",
    "DISPATCHED": "background-color:#ECFDF3;color:#14532D;",
    "IN_PROGRESS": "background-color:#EFF6FF;color:#1E3A8A;",
    "OPEN": "background-color:#FFF7ED;color:#9A3412;",
    "PENDING": "background-color:#FFF7ED;color:#9A3412;",
    "OVERDUE": "background-color:#FEE2E2;color:#991B1B;font-weight:700;",
    "REJECTED": "background-color:#FEE2E2;color:#991B1B;font-weight:700;",
    "CANCELLED": "background-color:#E2E8F0;color:#475569;",
}


def _maps(service: SupplyChainService):
    parts = {str(r["id"]): r for r in service.parts()}
    parties = {str(r["id"]): r for r in service.parties()}
    grades = {str(r["id"]): r for r in service.material_grades()}
    return parts, parties, grades


SHIP_TO_SOURCE_LABELS = {
    "CUSTOMER": "Customer Master",
    "SUPPLIER": "Supplier Master",
    "VENDOR": "Vendor / OSP Master",
}


def _ship_to_candidates(parties: Mapping[str, Mapping[str, Any]], source_type: str) -> dict[str, Mapping[str, Any]]:
    source = str(source_type or "").upper()
    result: dict[str, Mapping[str, Any]] = {}
    for party_id, row in parties.items():
        types = {str(v).upper() for v in (row.get("party_types") or [])}
        if source == "CUSTOMER":
            match = "CUSTOMER" in types
        elif source == "SUPPLIER":
            match = bool(types & {"SUPPLIER", "STEEL_MILL"})
        else:
            match = bool(types & {"OSP_VENDOR", "FORGING_SUPPLIER"})
        if match:
            result[str(party_id)] = row
    return dict(sorted(result.items(), key=lambda kv: str((kv[1] or {}).get("party_name") or "").casefold()))


def _party_address_preview(row: Mapping[str, Any] | None) -> str:
    r = dict(row or {})
    locality = ", ".join(v for v in (str(r.get("city") or "").strip(), str(r.get("state") or "").strip(), str(r.get("country") or "").strip()) if v)
    lines = [
        str(r.get("party_name") or "").strip(),
        str(r.get("address") or "").strip(),
        locality,
        f"GST / Tax ID: {str(r.get('tax_identifier') or '').strip()}" if r.get("tax_identifier") else "",
        f"Contact: {str(r.get('contact_person') or '').strip()}" if r.get("contact_person") else "",
        f"Phone: {str(r.get('phone') or '').strip()}" if r.get("phone") else "",
        f"Email: {str(r.get('email') or '').strip()}" if r.get("email") else "",
    ]
    return "\n".join(v for v in lines if v)


def _iso_date(value: Any) -> date:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return date.today()


def _due_status(status: Any, due: Any) -> str:
    base = str(status or "PENDING").upper()
    if base in {"COMPLETED", "CLOSED", "CANCELLED", "REJECTED"}:
        return base
    due_text = str(due or "")[:10]
    return "OVERDUE" if due_text and due_text < date.today().isoformat() else base


def _global_filter(frame: pd.DataFrame, term: str) -> pd.DataFrame:
    if frame.empty or not str(term or "").strip():
        return frame
    needle = str(term).strip().casefold()
    mask = frame.fillna("").astype(str).apply(lambda row: needle in " ".join(row.tolist()).casefold(), axis=1)
    return frame.loc[mask].copy()


def _style_supply_dataframe(frame: pd.DataFrame):
    if frame.empty:
        return frame
    def row_style(row):
        value = ""
        for key in ("Display Status", "Status", "Decision", "Disposition", "Result"):
            if key in row.index and str(row.get(key) or ""):
                value = str(row.get(key) or "").upper(); break
        css = STATUS_ROW_STYLE.get(value, "")
        return [css] * len(row)
    return frame.style.apply(row_style, axis=1)


def _excel_bytes(frame: pd.DataFrame, sheet_name: str) -> bytes:
    output = BytesIO()
    safe_name = safe_excel_sheet_name(sheet_name)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=safe_name)
        ws = writer.sheets[safe_name]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for cells in ws.columns:
            width = min(max(len(str(cell.value or "")) for cell in cells) + 2, 38)
            ws.column_dimensions[cells[0].column_letter].width = max(width, 11)
    return output.getvalue()


def _exports(frame: pd.DataFrame, title: str, key: str, *, header: Mapping[str, Any] | None = None) -> None:
    if frame.empty:
        return
    c1, c2 = st.columns(2, gap="small")
    pdf = controlled_record_pdf_bytes(title, dict(header or {"Record Count": len(frame)}), {title: frame})
    c1.download_button(
        "PDF Export", data=pdf, file_name=f"{key}.pdf", mime="application/pdf",
        icon=":material/picture_as_pdf:", width="stretch", key=f"supply_pdf_{key}",
    )
    c2.download_button(
        "Excel Export", data=_excel_bytes(frame, title), file_name=f"{key}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/table_view:", width="stretch", key=f"supply_excel_{key}",
    )


def _searchable_grid(frame: pd.DataFrame, *, title: str, key: str, height: int = 420, header: Mapping[str, Any] | None = None) -> pd.DataFrame:
    search = st.text_input("Global Search", placeholder="Search any field in this section", key=f"{key}_global_search")
    filtered = _global_filter(frame, search)
    if filtered.empty:
        st.info("No records match the global search." if search else "No records are available.")
    else:
        portal_table(_style_supply_dataframe(filtered), hide_index=True, width="stretch", height=min(height, 82 + 36 * max(len(filtered), 1)))
        _exports(filtered, title, key, header=header)
    return filtered


def _order_display_rows(service: SupplyChainService, orders: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    parts, parties, grades = _maps(service)
    rows=[]
    for r in orders:
        part=parts.get(str(r.get("part_id"))) or {}; customer=parties.get(str(r.get("customer_id"))) or {}; grade=grades.get(str(part.get("material_grade_id"))) or {}
        flow=service.flow_for_order(r)
        rows.append({
            "Customer Ref":r.get("master_reference_no"), "Order No":r.get("customer_order_no"), "PosNr":r.get("order_position"),
            "Supply Flow":FLOW_LABELS.get(flow,flow),
            "Customer":party_label(customer), "Part Number":part.get("part_number"), "FSI Part Number":part.get("fsi_part_number"), "Part Description":part.get("part_name"),
            "Material Grade":grade.get("grade_code"), "Order Qty pcs":r.get("order_qty_pcs"),
            "RM Required kg":r.get("required_rm_kg") if flow==FLOW_FSI_RM else None,
            "RM Ordered kg":r.get("rm_ordered_kg") if flow==FLOW_FSI_RM else None,
            "RM Balance kg":r.get("rm_balance_kg") if flow==FLOW_FSI_RM else None, "Available Stock pcs":r.get("available_stock_pcs_snapshot"), "3 Month Schedule pcs":r.get("three_month_schedule_pcs_snapshot"), "RM Procurement Required":r.get("rm_procurement_required"), "Procurement Decision":r.get("procurement_decision"), "Delivery Date":r.get("customer_delivery_date"),
            "Display Status":_due_status(r.get("status"),r.get("customer_delivery_date")), "_id":str(r.get("id")),
        })
    return pd.DataFrame(rows)


def _order_cards(frame: pd.DataFrame, *, key: str) -> None:
    if frame.empty:
        return
    cards=[]
    for _, r in frame.head(36).iterrows():
        status=str(r.get("Display Status") or r.get("Status") or "OPEN").upper()
        tone={"COMPLETED":"complete","CLOSED":"complete","OVERDUE":"overdue","REJECTED":"rejected","IN_PROGRESS":"current"}.get(status,"pending")
        icon="✓" if tone=="complete" else ("!" if tone in {"overdue","rejected"} else "○")
        cards.append(
            f'<div class="supply-order-card supply-card-{tone}"><div class="supply-card-top"><span class="supply-card-icon">{icon}</span>'
            f'<span class="supply-card-status">{safe(status.replace("_"," "))}</span></div>'
            f'<div class="supply-card-ref">{safe(r.get("Customer Ref") or r.get("Stage Reference") or "-")}</div>'
            f'<div class="supply-card-part">{safe(r.get("Part Number") or "")} · {safe(r.get("Part Description") or "")}</div>'
            f'<div class="supply-card-meta">{safe(r.get("Supply Flow") or "")} · {safe(r.get("Customer") or "")} · Qty {safe(r.get("Order Qty pcs") or r.get("Stage Qty") or "-")} · Due {safe(r.get("Delivery Date") or r.get("Expected") or "-")}</div></div>'
        )
    st.markdown(f'<div class="supply-order-grid" id="{safe(key)}">{"".join(cards)}</div>',unsafe_allow_html=True)


def _order_progress(service: SupplyChainService, order: dict) -> list[dict]:
    totals=service.totals(str(order["id"])); qty=number(order.get("order_qty_pcs")); required=number(order.get("required_rm_kg"))
    flow=service.flow_for_order(order)
    def state(value: float, target: float) -> str:
        if target > 0 and value >= target - .0001: return "complete"
        if value > 0: return "current"
        return "pending"
    part_production=max(totals["finished_goods_pcs"],totals["machined_pcs"] if totals["finished_goods_pcs"]<=0 else 0)
    common_tail=[
        {"label":"Forging Order", "state":state(totals["forging_ordered_pcs"],qty), "detail":f"{totals['forging_ordered_pcs']:,.0f}/{qty:,.0f} pcs"},
        {"label":"Forging Receipt", "state":state(totals["forging_received_pcs"],qty), "detail":f"{totals['forging_received_pcs']:,.0f}/{qty:,.0f} pcs"},
        {"label":"Part Production", "state":state(part_production,qty), "detail":f"{part_production:,.0f}/{qty:,.0f} pcs"},
        {"label":"Dispatch", "state":state(totals["customer_dispatched_pcs"],qty), "detail":f"{totals['customer_dispatched_pcs']:,.0f}/{qty:,.0f} pcs"},
    ]
    if flow==FLOW_DIRECT_FORGING:
        return [{"label":"Customer Order", "state":"complete", "detail":str(order.get("master_reference_no"))}, *common_tail]
    return [
        {"label":"Customer Order", "state":"complete", "detail":str(order.get("master_reference_no"))},
        {"label":"RM Procurement", "state":state(totals["rm_ordered_kg"],required), "detail":f"{totals['rm_ordered_kg']:,.1f}/{required:,.1f} kg"},
        {"label":"RM Receipt", "state":state(totals["rm_received_kg"],min(totals["rm_ordered_kg"],required) if totals["rm_ordered_kg"] else required), "detail":f"{totals['rm_received_kg']:,.1f} kg"},
        {"label":"RM to Forger", "state":state(totals["rm_dispatched_kg"],min(totals["rm_received_kg"],required) if totals["rm_received_kg"] else required), "detail":f"{totals['rm_dispatched_kg']:,.1f} kg"},
        *common_tail,
    ]


def _show_order_context(service: SupplyChainService, order_id: str, *, key: str, export: bool = False) -> dict:
    order=service.order(order_id) or {}; ctx=service.order_context(order); frame=pd.DataFrame([ctx])
    portal_table(_style_supply_dataframe(frame),hide_index=True,width="stretch")
    if export: _exports(frame,"Selected Supply Chain Entry",f"{key}_selected",header={"Customer Reference":ctx.get("Customer Ref")})
    return order


def _edit_delete_panel(
    service: SupplyChainService, *, table: str, rows: Sequence[Mapping[str,Any]], title: str, stage: str, key: str,
    labeler, fields: Sequence[tuple], perms: Mapping[str,bool],
) -> None:
    with stage_section(stage,title,"Edit controlled fields or permanently delete with current QCMS password.",key=f"{key}_controls"):
        if not rows:
            st.info("No entries are available for edit/delete."); return
        labels={str(r["id"]):labeler(r) for r in rows if r.get("id")}
        selected=st.selectbox("Select Entry",list(labels),format_func=lambda v:labels[v],key=f"{key}_edit_select")
        row=next(r for r in rows if str(r.get("id"))==selected)
        with st.form(f"{key}_edit_form"):
            values={}; columns=st.columns(3,gap="small")
            for index,spec in enumerate(fields):
                name,label,kind,*extra=spec; col=columns[index%3]; current=row.get(name)
                if kind=="date": values[name]=col.date_input(label,value=_iso_date(current),format="DD-MM-YYYY",key=f"{key}_{name}").isoformat()
                elif kind=="number": values[name]=col.number_input(label,min_value=0.0,value=float(number(current)),step=1.0,key=f"{key}_{name}")
                elif kind=="select":
                    opts=list(extra[0]); cur=str(current or opts[0]); values[name]=col.selectbox(label,opts,index=opts.index(cur) if cur in opts else 0,key=f"{key}_{name}")
                elif kind=="lookup":
                    mapping=dict(extra[0]); opts=list(mapping); cur=str(current or ""); values[name]=col.selectbox(label,opts,index=opts.index(cur) if cur in opts else 0,format_func=lambda v:mapping[v],key=f"{key}_{name}") if opts else current
                else: values[name]=col.text_input(label,value=str(current or ""),key=f"{key}_{name}")
            submitted=st.form_submit_button("Save Edited Entry",type="primary",width="stretch",disabled=not perms.get("can_edit",False))
        if submitted:
            try:
                service.save_transaction(table,values,record_id=selected)
                order_id=str((service.repo.get(table,selected) or {}).get("customer_order_id") or (selected if table=="supply_customer_orders" else ""))
                if order_id: service.sync_order_status(order_id)
                save_success_popup("Supply Chain entry updated successfully.",queue_for_rerun=True); st.rerun()
            except Exception as exc: st.error(str(exc))
        _exports(pd.DataFrame([{k:v for k,v in row.items() if not str(k).startswith("_")}]),f"Selected {title}",f"{key}_{selected}")
        if password_delete_panel(repo=service.repo,table=table,rows=[row],labeler=labeler,key=f"{key}_delete_{selected}",can_delete=perms.get("can_archive",False),title="Delete Selected Entry",help_text="Permanent deletion requires your current QCMS password. Linked downstream records will block deletion."):
            st.rerun()


def render_home() -> None:
    page_header("Supply Chain", "Master-linked Customer Order to final dispatch genealogy", "Supply Chain")
    service=SupplyChainService(); orders=service.customer_orders(); active=[r for r in orders if str(r.get("status")) not in {"COMPLETED","CANCELLED"}]
    overdue=[r for r in active if _due_status(r.get("status"),r.get("customer_delivery_date"))=="OVERDUE"]
    dispatched=sum(service.totals(str(r["id"]))["customer_dispatched_pcs"] for r in orders)
    kpi_grid([
        {"label":"Open Customer Orders","value":len(active),"foot":"Purchase Orders + Monthly Schedules","color":"#0B6FAE","background":"#EFF7FD"},
        {"label":"Overdue Orders","value":len(overdue),"foot":"Customer delivery date exceeded","color":"#B91C1C","background":"#FEF2F2"},
        {"label":"Orders Completed","value":sum(str(r.get("status"))=="COMPLETED" for r in orders),"foot":"Completed flow cards are green + ticked","color":"#15803D","background":"#F0FDF4"},
        {"label":"Customer Dispatch pcs","value":f"{dispatched:,.0f}","foot":"All linked Customer References","color":"#075985","background":"#F0F9FF"},
    ])
    with stage_section("0","OPENING STOCK & IMPORT","Load existing stock by supply-chain stage before evaluating new procurement. Finished Goods contributes to customer available stock; eligible WIP can feed OSP.",key="supply_home_opening_stock_quick"):
        q1,q2=st.columns(2,gap="small")
        q1.info("Manual opening balance, stage-controlled inventory, Excel template/import and current-stock export are available in one dedicated module.")
        if q2.button("Open Opening Stock & Import",type="primary",width="stretch",key="supply_home_opening_stock_button"):
            st.switch_page(st.session_state["_qsms_pages"]["supply-opening-stock"])
    with stage_section("A","OPEN ORDER STATUS","Colour order cards are sorted by upcoming delivery date; completed cards turn green with a tick.",key="supply_home_status"):
        frame=_order_display_rows(service,sorted(active,key=lambda r:str(r.get("customer_delivery_date") or "9999-12-31")))
        filtered=_searchable_grid(frame.drop(columns=["_id"],errors="ignore"),title="Open Customer Order Status",key="supply_home_open",height=360)
        _order_cards(filtered,key="supply_home_cards")
    with stage_section("B","SELECTED ORDER FLOW","Select one open order to see the complete linked stage flow.",key="supply_home_flow"):
        if active:
            parts,parties,_=_maps(service); labels={str(r["id"]):service.order_label(r,parts,parties) for r in active}
            selected=st.selectbox("Customer Order Master Reference",list(labels),format_func=lambda v:labels[v],key="supply_home_order")
            order=next(r for r in active if str(r["id"])==selected); workflow_progress(_order_progress(service,order))
            balances=pd.DataFrame(service.supplier_balances(selected));
            if not balances.empty: _searchable_grid(balances,title="Forging Supplier RM Balance",key="supply_home_balance",height=260)
        else: st.success("All current Customer Orders are completed.")


def render_customer_orders() -> None:
    page_header("Customer Orders / Schedules", "Customer, Part, Grade, weights and sources are controlled by Masters", "Supply Chain")
    service=SupplyChainService(); perms=current_permissions("SUPPLY_CHAIN"); parts=service.parts(); customers=service.customers(); parties={str(r["id"]):r for r in service.parties()}
    part_map={str(r["id"]):part_label(r,customer_name=party_label(parties.get(str(r.get("customer_id"))) or {})) for r in parts}; customer_map={str(r["id"]):party_label(r) for r in customers}
    with stage_section("A","CUSTOMER ORDER / SCHEDULE ENTRY","Monthly Schedule shows six months horizontally in one row. Part/customer/supplier/weight data comes from Masters.",key="supply_customer_order_entry"):
        order_type=st.radio("Order Source",["PURCHASE_ORDER","MONTHLY_SCHEDULE"],horizontal=True,format_func=lambda v:"Customer Purchase Order" if v=="PURCHASE_ORDER" else "Monthly Schedule · 6 Months")
        supply_flow=st.radio(
            "Supply Chain Flow", [FLOW_FSI_RM,FLOW_DIRECT_FORGING], horizontal=True,
            format_func=lambda v: FLOW_LABELS[v], key="supply_customer_flow",
            help="Flow 1 follows Customer Order → RM Procurement → RM Receipt → RM to Forger → Forging Order → Forging Receipt → Part Production → Dispatch. Flow 2 is RM Responsible Forger / Supplier: it starts directly from Forging Order and bypasses FSI RM Procurement, RM Receipt and RM-to-Forger."
        )
        c1,c2=st.columns(2,gap="small"); customer_id=c1.selectbox("Customer",list(customer_map),format_func=lambda v:customer_map[v]) if customer_map else None
        filtered_parts=[r for r in parts if not customer_id or str(r.get("customer_id") or "") in {"",str(customer_id)}]; fp_map={str(r["id"]):part_map[str(r["id"])] for r in filtered_parts}; part_id=c2.selectbox("Part Number",list(fp_map),format_func=lambda v:fp_map[v]) if fp_map else None
        raw_rows=service.raw_material_options(str(part_id or "")) if part_id else []; raw_labels={}
        for r in raw_rows:
            supplier=parties.get(str(r.get("supplier_id"))) or {}; gross=number(r.get("gross_weight_kg") or r.get("input_weight_kg") or r.get("forging_weight_kg")); grade=(service.repo.get("material_grades",str(r.get("material_grade_id") or "")) or {}).get("grade_code") or "-"; raw_labels[str(r["id"])]=f"{r.get('material_section_name') or 'Raw Material'} · Grade {grade} · {party_label(supplier)} · Gross {gross:.3f} kg/pc · {r.get('section_size') or '-'} · Lead {int(r.get('lead_time_days') or 0)}d"
        raw_id=st.selectbox("Part Master Raw Material / Forging Source",list(raw_labels),format_func=lambda v:raw_labels[v]) if raw_labels else None
        selected_raw=next((r for r in raw_rows if str(r["id"])==str(raw_id)),{}) if raw_id else {}; gross=number(selected_raw.get("gross_weight_kg") or selected_raw.get("input_weight_kg") or selected_raw.get("forging_weight_kg"))
        if part_id: _show_order_context(service,str(next((r.get("id") for r in service.customer_orders() if False),"")),key="dummy") if False else None
        if not raw_labels: st.warning("Part Master E - Raw Material Details requires an active raw material / forging source and gross/input weight.")
        if order_type=="PURCHASE_ORDER":
            c=st.columns(5,gap="small"); order_no=c[0].text_input("Customer Order No."); position=c[1].text_input("PosNr / Position"); qty=c[2].number_input("Order Qty pcs",min_value=1.0,step=1.0); order_date=c[3].date_input("Order Date",value=date.today(),format="DD-MM-YYYY"); delivery=c[4].date_input("Delivery / Arrival Date",value=date.today(),format="DD-MM-YYYY")
            remarks=st.text_input("Order Remarks")
            procurement_check = service.procurement_check(str(part_id or ""), str(customer_id or ""), anchor=delivery, proposed_three_month_qty=qty) if part_id else {"available_stock_pcs":0,"three_month_schedule_pcs":qty,"shortage_pcs":qty,"rm_procurement_allowed":True}
            if supply_flow==FLOW_FSI_RM:
                kpi_grid([
                    {"label":"System Available Qty","value":f"{number(procurement_check.get('available_stock_pcs')):,.0f} pcs","color":"#0B6FAE","background":"#FFFFFF"},
                    {"label":"3-Month Schedule / Demand","value":f"{number(procurement_check.get('three_month_schedule_pcs')):,.0f} pcs","color":"#B0003A","background":"#FFFFFF"},
                    {"label":"Shortage","value":f"{number(procurement_check.get('shortage_pcs')):,.0f} pcs","color":"#B45309" if procurement_check.get('rm_procurement_allowed') else "#15803D","background":"#FFFFFF"},
                    {"label":"RM Reference","value":f"{qty*gross:,.3f} kg","color":"#334155","background":"#FFFFFF"},
                ])
                if procurement_check.get("rm_procurement_allowed"):
                    rm_procurement_required=st.checkbox("RM Procurement Required",value=True,key="customer_po_rm_required",help="Available system stock is lower than the rolling three-month schedule / demand. You may untick this only when procurement is intentionally not required.")
                else:
                    rm_procurement_required=st.checkbox("RM Procurement Required",value=False,disabled=True,key="customer_po_rm_required_stock",help="RM procurement cannot be raised because available system stock is equal to or higher than the saved rolling three-month schedule / demand.")
                    st.success("Available system quantity covers the rolling three-month demand. RM Procurement is not required for this Customer Order.")
            else:
                rm_procurement_required=False
                st.metric("Estimated RM at Forging Supplier",f"{qty*gross:,.3f} kg",help="Reference only. FSI RM Procurement / Receipt / RM-to-Forger stages are bypassed for this flow.")
            order_notify_pref = notification_confirmation(
                NotificationService(service.repo), "RM_PROCUREMENT_PENDING", key="customer_po_rm_notification",
                context={"customer_name":customer_map.get(str(customer_id),"-"),"part_number":fp_map.get(str(part_id),"-"),"next_task":"RM Procurement"},
                default_send=bool(rm_procurement_required),
            ) if rm_procurement_required else {"send":False,"confirmed":True,"preview":{}}
            if st.button("Create Customer Purchase Order",type="primary",width="stretch",disabled=not perms["can_create"] or not customer_id or not part_id or not raw_id or gross<=0 or not order_no.strip() or not position.strip() or (order_notify_pref["send"] and not order_notify_pref["confirmed"])):
                try:
                    saved_order=service.create_customer_order({"order_type":"PURCHASE_ORDER","customer_id":customer_id,"part_id":part_id,"customer_order_no":order_no.strip(),"order_position":position.strip(),"order_date":order_date.isoformat(),"customer_delivery_date":delivery.isoformat(),"order_qty_pcs":qty,"forging_supplier_id":selected_raw.get("supplier_id"),"raw_material_detail_id":raw_id,"gross_weight_kg_snapshot":gross,"status":"OPEN","remarks":remarks.strip() or None,"supply_flow":supply_flow,"rm_procurement_required":rm_procurement_required,"_procurement_check":procurement_check})
                    if bool(saved_order.get("rm_procurement_required")) and order_notify_pref["send"] and order_notify_pref["confirmed"]:
                        NotificationService(service.repo).notify(
                            "RM_PROCUREMENT_PENDING",
                            subject=f"QCMS · RM procurement pending · {saved_order.get('master_reference_no')}",
                            body_text=(
                                f"Raw Material procurement is pending for Customer Order {saved_order.get('master_reference_no')} / Pos {saved_order.get('order_position') or '-'}.\n"
                                f"Order Qty: {number(saved_order.get('order_qty_pcs')):,.0f} pcs\n"
                                f"Required RM: {number(saved_order.get('required_rm_kg')):,.3f} kg\n"
                                f"Delivery: {saved_order.get('customer_delivery_date') or '-'}"
                            ),
                            related_table="supply_customer_orders", related_id=str(saved_order.get("id")),
                            context={"customer_order_id":str(saved_order.get("id")),"next_task":"RM Procurement"},
                        )
                    st.session_state["last_supply_customer_order_id"] = str(saved_order.get("id") or "")
                    save_success_popup(f"Customer Order {order_no} / Pos {position} created.",queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))
        else:
            c=st.columns(3,gap="small"); start_month=c[0].selectbox("Start Month",list(MONTHS),format_func=lambda v:MONTHS[v],index=date.today().month-1); start_year=c[1].selectbox("Start Year",list(range(date.today().year-1,date.today().year+7)),index=1); receipt_date=c[2].date_input("Schedule Receipt Date",value=date.today(),format="DD-MM-YYYY")
            st.caption("Six-month schedule entry · all six months are visible at once")
            month_data=[]; cols=st.columns(6,gap="small")
            for offset,col in enumerate(cols):
                total=int(start_year)*12+(int(start_month)-1)+offset; yy=total//12; mm=total%12+1
                with col:
                    st.markdown(f"**{MONTHS[mm][:3]} {yy}**")
                    q=st.number_input("Qty pcs",min_value=0.0,step=1.0,key=f"six_month_qty_{part_id}_{yy}_{mm}")
                    d=st.date_input("Delivery",value=date(yy,mm,1),format="DD-MM-YYYY",key=f"six_month_delivery_{part_id}_{yy}_{mm}")
                    st.caption(monthly_reference(str((next((r for r in parts if str(r["id"])==str(part_id)),{}) or {}).get("part_number") or "PART"),mm,yy) if part_id else "Select Part")
                    month_data.append((mm,yy,q,d))
            remarks=st.text_input("Schedule Remarks")
            proposed_three_month=sum(number(row[2]) for row in month_data[:3])
            schedule_check=service.procurement_check(str(part_id or ""),str(customer_id or ""),anchor=date(int(start_year),int(start_month),1),proposed_three_month_qty=proposed_three_month) if part_id else {"available_stock_pcs":0,"three_month_schedule_pcs":proposed_three_month,"shortage_pcs":proposed_three_month,"rm_procurement_allowed":True}
            if supply_flow==FLOW_FSI_RM:
                kpi_grid([
                    {"label":"System Available Qty","value":f"{number(schedule_check.get('available_stock_pcs')):,.0f} pcs","color":"#0B6FAE","background":"#FFFFFF"},
                    {"label":"3-Month Schedule","value":f"{number(schedule_check.get('three_month_schedule_pcs')):,.0f} pcs","color":"#B0003A","background":"#FFFFFF"},
                    {"label":"3-Month Shortage","value":f"{number(schedule_check.get('shortage_pcs')):,.0f} pcs","color":"#B45309" if schedule_check.get('rm_procurement_allowed') else "#15803D","background":"#FFFFFF"},
                ])
                if schedule_check.get("rm_procurement_allowed"):
                    schedule_rm_required=st.checkbox("RM Procurement Required for this schedule",value=True,key="monthly_schedule_rm_required")
                else:
                    schedule_rm_required=st.checkbox("RM Procurement Required for this schedule",value=False,disabled=True,key="monthly_schedule_rm_stock")
                    st.success("Available system quantity is equal to or greater than the first three months of schedule. RM Procurement cannot be raised for this schedule until a shortage exists.")
            else:
                schedule_rm_required=False
            schedule_notify_pref = notification_confirmation(
                NotificationService(service.repo), "RM_PROCUREMENT_PENDING", key="monthly_schedule_rm_notification",
                context={"customer_name":customer_map.get(str(customer_id),"-"),"part_number":fp_map.get(str(part_id),"-"),"next_task":"RM Procurement"},
                default_send=bool(schedule_rm_required),
            ) if schedule_rm_required else {"send":False,"confirmed":True,"preview":{}}
            if st.button("Create / Add Six-Month Schedule",type="primary",width="stretch",disabled=not perms["can_create"] or not customer_id or not part_id or not raw_id or gross<=0 or (schedule_notify_pref["send"] and not schedule_notify_pref["confirmed"])):
                try:
                    created=[]; created_ids=[]
                    for mm,yy,q,d in month_data:
                        if q<=0: continue
                        saved=service.create_customer_order({"order_type":"MONTHLY_SCHEDULE","customer_id":customer_id,"part_id":part_id,"order_position":f"{mm:02d}-{yy}","schedule_month":date(yy,mm,1).isoformat(),"order_date":receipt_date.isoformat(),"customer_delivery_date":d.isoformat(),"order_qty_pcs":q,"forging_supplier_id":selected_raw.get("supplier_id"),"raw_material_detail_id":raw_id,"gross_weight_kg_snapshot":gross,"status":"OPEN","remarks":remarks.strip() or None,"supply_flow":supply_flow,"rm_procurement_required":schedule_rm_required,"_procurement_check":schedule_check}); created.append(saved.get("master_reference_no")); created_ids.append(str(saved.get("id") or ""))
                    if not created: raise ValueError("Enter quantity for at least one of the six months.")
                    if schedule_rm_required and schedule_notify_pref["send"] and schedule_notify_pref["confirmed"]:
                        NotificationService(service.repo).notify(
                            "RM_PROCUREMENT_PENDING",
                            subject=f"QCMS · RM procurement pending · {len(created)} monthly schedule(s)",
                            body_text=(f"{len(created)} monthly schedule record(s) were created with RM Procurement Required.\n"
                                       f"Customer: {customer_map.get(str(customer_id), '-')}\n"
                                       f"Part: {fp_map.get(str(part_id), '-')}\n"
                                       f"First 3-month demand: {number(schedule_check.get('three_month_schedule_pcs')):,.0f} pcs"),
                            context={"customer_order_refs":created,"next_task":"RM Procurement"},
                        )
                    if created_ids: st.session_state["last_supply_customer_order_id"] = created_ids[-1]
                    save_success_popup(f"{len(created)} monthly schedule record(s) created.",queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))
    with stage_section("B","CUSTOMER ORDER IMPORT · COLUMNS A TO F","Reads rows after the detected header. Existing Item / Order No. / PosNr combinations are skipped; only database-missing orders are imported.",key="supply_customer_import"):
        c_import=st.columns(2,gap="small")
        import_customer=c_import[0].selectbox("Import Customer",list(customer_map),format_func=lambda v:customer_map[v],key="supply_import_customer") if customer_map else None
        import_flow=c_import[1].selectbox("Imported Order Supply Flow",[FLOW_FSI_RM,FLOW_DIRECT_FORGING],format_func=lambda v:FLOW_LABELS[v],key="supply_import_flow")
        uploaded=st.file_uploader("Customer Order / Schedule Excel",type=["xlsx","xlsm","xls"],key="supply_order_import_file")
        if uploaded is not None and import_customer:
            try:
                raw=pd.read_excel(uploaded,header=None,usecols="A:F",dtype=object)
                header_index=next((i for i,row in raw.iterrows() if normalize_match(row.iloc[0])=="item" and normalize_match(row.iloc[2]) in {"orderno","ordernumber"}),None)
                if header_index is None: raise ValueError("Could not find the header row containing Item / Description / Order no. / PosNr / Quantity / Delivery date in columns A-F.")
                data=raw.iloc[header_index+1:,:6].copy(); data.columns=["Item","Description","Order no.","PosNr","Quantity","Delivery date"]; data=data.dropna(how="all")
                preview=service.import_preview(str(import_customer),data.to_dict("records")); visible=pd.DataFrame([{k:v for k,v in r.items() if not k.startswith("_")} for r in preview])
                portal_table(_style_supply_dataframe(visible.rename(columns={"Action":"Status"})),hide_index=True,width="stretch",height=min(520,90+34*len(visible))); _exports(visible,"Customer Order Import Preview","supply_customer_import_preview")
                duplicate_count=sum(str(r.get("Action"))=="SKIP_DUPLICATE" for r in preview)
                if duplicate_count:
                    st.info(f"{duplicate_count} existing Order No. + PosNr row(s) will be skipped. Import never changes existing database orders.")
                if st.button("Import New Orders Only",type="primary",width="stretch",disabled=not perms["can_create"] or any(str(r.get("Action"))=="ERROR" for r in preview)):
                    result=service.apply_customer_order_import(str(import_customer),preview,confirm_updates=False,supply_flow=import_flow); save_success_popup(f"Import complete · New {result['created']} · Duplicates skipped {result['skipped']}",queue_for_rerun=True); st.rerun()
            except Exception as exc: st.error(str(exc))
    with stage_section("C","CUSTOMER ORDER REGISTER","Global search covers all displayed fields.",key="supply_customer_order_register"):
        rows=service.customer_orders(); frame=_order_display_rows(service,rows); _searchable_grid(frame.drop(columns=["_id"],errors="ignore"),title="Customer Order Register",key="supply_customer_order_register_grid",height=520); _order_cards(frame,key="customer_register_cards")
    with stage_section("D","CUSTOMER ORDER ATTACHMENT","Attach the customer PO, schedule, amendment or other supporting document to any saved Customer Order / Schedule.",key="supply_customer_order_attachment"):
        attachment_rows=service.customer_orders()
        if attachment_rows:
            attachment_labels={str(r["id"]):f"{r.get('master_reference_no')} · Pos {r.get('order_position') or '-'} · {r.get('customer_delivery_date') or '-'}" for r in attachment_rows}
            last_order_id=str(st.session_state.get("last_supply_customer_order_id") or "")
            attachment_ids=list(attachment_labels)
            attachment_index=attachment_ids.index(last_order_id) if last_order_id in attachment_ids else 0
            attachment_order_id=st.selectbox("Customer Order / Schedule",attachment_ids,index=attachment_index,format_func=lambda v:attachment_labels[v],key="supply_customer_attachment_order")
            render_attachment_manager(
                repo=service.repo,entity_type="SUPPLY_CUSTOMER_ORDER",entity_id=attachment_order_id,folder="supply_customer_orders",
                slots=(AttachmentSlot("CUSTOMER_ORDER_ATTACHMENT","Customer Order / Schedule Attachment","Customer PO, schedule, amendment or supporting file."),),
                key_prefix=f"supply_customer_order_{attachment_order_id}",can_add_or_replace=perms["can_edit"] or perms["can_create"],can_delete=perms["can_archive"],title="ATTACHMENT FILE",
            )
        else: st.info("Create a Customer Order / Schedule before adding an attachment.")
    _edit_delete_panel(service,table="supply_customer_orders",rows=service.customer_orders(),title="CUSTOMER ORDER EDIT / DELETE",stage="E",key="supply_customer_order",labeler=lambda r:f"{r.get('master_reference_no')} · Pos {r.get('order_position') or '-'}",fields=(("supply_flow","Supply Chain Flow","select",(FLOW_FSI_RM,FLOW_DIRECT_FORGING)),("customer_order_no","Customer Order No.","text"),("order_position","PosNr / Position","text"),("order_date","Order Date","date"),("customer_delivery_date","Delivery Date","date"),("order_qty_pcs","Order Qty pcs","number"),("status","Status","select",("OPEN","IN_PROGRESS","COMPLETED","CANCELLED")),("remarks","Remarks","text")),perms=perms)



OPENING_STOCK_STAGES = {
    "RAW_MATERIAL": "Raw Material",
    "FORGING": "Forging",
    "MACHINING": "Machining / WIP",
    "OSP_READY": "OSP Ready",
    "AT_OSP": "At OSP",
    "FINAL_INSPECTION": "Final Inspection",
    "FINISHED_GOODS": "Finished Goods",
}


def render_opening_stock() -> None:
    page_header("Supply Chain Opening Stock", "Load existing stock by Part and current process stage without resetting live transactions", "Supply Chain")
    service=SupplyChainService(); perms=current_permissions("SUPPLY_CHAIN")
    parts,parties,grades=_maps(service)
    part_labels={pid:part_label(row,customer_name=party_label(parties.get(str(row.get("customer_id"))) or {})) for pid,row in parts.items()}
    grade_labels={gid:str(row.get("grade_code") or gid) for gid,row in grades.items()}
    supplier_labels={pid:party_label(row) for pid,row in parties.items()}

    with stage_section("A","ADD OPENING STOCK","Opening quantities are added separately from historical QCMS transactions. Finished Goods counts toward customer-order stock; eligible WIP stages can be selected in OSP Material Out.",key="supply_opening_stock_add"):
        if not part_labels:
            st.warning("Create an active Part Master before adding Opening Stock.")
        else:
            part_id=st.selectbox("Part Number",list(part_labels),format_func=lambda v:part_labels[v],key="opening_stock_part")
            grade_links=service.material_grade_links(part_id)
            grade_ids=[str(r.get("material_grade_id")) for r in grade_links if str(r.get("material_grade_id") or "") in grade_labels]
            primary_grade=str((parts.get(part_id) or {}).get("material_grade_id") or "")
            if primary_grade and primary_grade in grade_labels and primary_grade not in grade_ids: grade_ids.insert(0,primary_grade)
            raw_rows=service.raw_material_options(part_id)
            raw_labels={str(r["id"]):f"{r.get('material_section_name') or 'Raw Material'} · Grade {grade_labels.get(str(r.get('material_grade_id')),'-')} · {supplier_labels.get(str(r.get('supplier_id')),'Supplier')} · {r.get('section_size') or '-'}" for r in raw_rows}
            with st.form("supply_opening_stock_form"):
                c=st.columns(4,gap="small")
                stage=c[0].selectbox("Supply Chain Stage",list(OPENING_STOCK_STAGES),format_func=lambda v:OPENING_STOCK_STAGES[v])
                grade_id=c[1].selectbox("Material Grade",[""]+grade_ids,format_func=lambda v:"Not Applicable / Unknown" if not v else grade_labels.get(v,v))
                raw_id=c[2].selectbox("Raw Material / Supplier Section",[""]+list(raw_labels),format_func=lambda v:"Not Linked" if not v else raw_labels[v])
                supplier_id=str((next((r for r in raw_rows if str(r.get("id"))==str(raw_id)),{}) or {}).get("supplier_id") or "") if raw_id else ""
                c[3].text_input("Supplier",value=supplier_labels.get(supplier_id,"-"),disabled=True)
                c=st.columns(4,gap="small")
                lot_reference=c[0].text_input("Opening Lot / Reference")
                heat_number=c[1].text_input("Heat Number")
                heat_code=c[2].text_input("Heat Code")
                qty_pcs=c[3].number_input("Opening Qty (pcs)",min_value=0.0,value=0.0,step=1.0)
                c=st.columns(3,gap="small")
                available_pcs=c[0].number_input("Available Qty (pcs)",min_value=0.0,value=float(qty_pcs),step=1.0,help="Quantity currently available at the selected stage. This may be lower than the original opening quantity.")
                qty_kg=c[1].number_input("Opening Qty (kg)",min_value=0.0,value=0.0,step=1.0)
                remarks=c[2].text_input("Remarks")
                submitted=st.form_submit_button("Add Opening Stock",type="primary",width="stretch",disabled=not perms["can_create"])
            if submitted:
                try:
                    raw=next((r for r in raw_rows if str(r.get("id"))==str(raw_id)),{}) if raw_id else {}
                    selected_grade=grade_id or str(raw.get("material_grade_id") or primary_grade or "") or None
                    service.save_opening_stock({
                        "part_id":part_id,"stage":stage,"material_grade_id":selected_grade,"raw_material_detail_id":raw_id or None,"supplier_id":supplier_id or None,
                        "lot_reference":lot_reference.strip() or None,"heat_number":heat_number.strip() or None,"heat_code":heat_code.strip() or None,
                        "quantity_pcs":qty_pcs,"available_quantity_pcs":available_pcs,"quantity_kg":qty_kg,"remarks":remarks.strip() or None,"status":"ACTIVE",
                    })
                    save_success_popup("Opening Stock added successfully and is now available to the relevant Supply Chain / OSP stage.",queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))

    rows=service.opening_stock()
    def display_rows():
        data=[]
        for r in rows:
            part=parts.get(str(r.get("part_id"))) or {}
            raw=next((x for x in service.raw_material_options(str(r.get("part_id"))) if str(x.get("id"))==str(r.get("raw_material_detail_id"))),{}) if r.get("raw_material_detail_id") else {}
            data.append({
                "Part Number":part.get("part_number"),"FSI Part Number":part.get("fsi_part_number"),"Part Description":part.get("part_name"),
                "Stage":OPENING_STOCK_STAGES.get(str(r.get("stage")),str(r.get("stage"))),"Material Grade":grade_labels.get(str(r.get("material_grade_id")),"-"),
                "Raw Material Section":raw.get("material_section_name") or "-","Supplier":supplier_labels.get(str(r.get("supplier_id")),"-"),
                "Opening Reference":r.get("lot_reference"),"Heat Number":r.get("heat_number"),"Heat Code":r.get("heat_code"),
                "Opening Qty pcs":r.get("quantity_pcs"),"Available Qty pcs":r.get("available_quantity_pcs"),"Opening Qty kg":r.get("quantity_kg"),
                "Status":r.get("status"),"Remarks":r.get("remarks"),"_id":str(r.get("id")),
            })
        return data
    frame=pd.DataFrame(display_rows())

    with stage_section("B","OPENING STOCK IMPORT / EXPORT UTILITY","Download a controlled template, preview the import, skip exact duplicate Opening References, and export the complete current register.",key="supply_opening_stock_import_export"):
        template=pd.DataFrame([{
            "Part Number":"","FSI Part Number":"","Stage":"FINISHED_GOODS","Material Grade":"","Supplier Code":"",
            "Raw Material Section":"","Section Size":"","Opening Reference":"OPEN-001","Heat Number":"","Heat Code":"",
            "Opening Qty pcs":0,"Available Qty pcs":0,"Opening Qty kg":0,"Remarks":"",
        }])
        c1,c2=st.columns(2,gap="small")
        c1.download_button(
            "Download Opening Stock Import Template", data=_excel_bytes(template,"Opening Stock Template"),
            file_name="QCMS_Opening_Stock_Import_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch",
            key="opening_stock_template_download",
        )
        current_export=frame.drop(columns=["_id"],errors="ignore") if not frame.empty else pd.DataFrame(columns=template.columns)
        c2.download_button(
            "Export Current Opening Stock", data=_excel_bytes(current_export,"Opening Stock Register"),
            file_name="QCMS_Opening_Stock_Register.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/table_view:", width="stretch",
            key="opening_stock_register_export",
        )
        st.caption("Import Stage values: RAW_MATERIAL, FORGING, MACHINING, OSP_READY, AT_OSP, FINAL_INSPECTION, FINISHED_GOODS. Opening Reference is mandatory for duplicate-safe import.")
        uploaded=st.file_uploader("Opening Stock Excel Import",type=["xlsx","xlsm","xls"],key="opening_stock_import_file")
        if uploaded is not None:
            try:
                imported=pd.read_excel(uploaded,dtype=object).dropna(how="all")
                preview=service.opening_stock_import_preview(imported.to_dict("records"))
                visible=pd.DataFrame([{k:v for k,v in row.items() if not k.startswith("_")} for row in preview])
                portal_table(_style_supply_dataframe(visible.rename(columns={"Action":"Status"})),hide_index=True,width="stretch",height=min(520,90+34*max(len(visible),1)))
                errors=sum(str(row.get("Action"))=="ERROR" for row in preview)
                duplicates=sum(str(row.get("Action"))=="SKIP_DUPLICATE" for row in preview)
                st.caption(f"Preview: New {sum(str(row.get('Action'))=='CREATE' for row in preview)} · Duplicates skipped {duplicates} · Errors {errors}")
                if st.button("Import Opening Stock · New Rows Only",type="primary",width="stretch",disabled=not perms["can_create"] or errors>0,key="opening_stock_import_apply"):
                    result=service.apply_opening_stock_import(preview)
                    save_success_popup(f"Opening Stock import complete · New {result['created']} · Duplicates skipped {result['skipped']}",queue_for_rerun=True); st.rerun()
            except Exception as exc:
                st.error(str(exc))

    with stage_section("C","OPENING STOCK REGISTER","Stage-wise opening stock remains traceable. Only Finished Goods is included in customer-order available stock; eligible WIP stages are available to OSP.",key="supply_opening_stock_register"):
        _searchable_grid(frame.drop(columns=["_id"],errors="ignore"),title="Opening Stock Register",key="supply_opening_stock_register_grid",height=520)

    with stage_section("D","OPENING STOCK EDIT / DELETE","Edit quantities/stage with Supply Chain edit rights. Permanent deletion additionally requires the current QCMS password.",key="supply_opening_stock_edit"):
        if not rows:
            st.info("No Opening Stock records are available.")
        else:
            labels={str(r["id"]):f"{part_labels.get(str(r.get('part_id')),'Part')} · {OPENING_STOCK_STAGES.get(str(r.get('stage')),r.get('stage'))} · {number(r.get('available_quantity_pcs')):,.0f} pcs" for r in rows}
            selected_id=st.selectbox("Opening Stock Record",list(labels),format_func=lambda v:labels[v],key="opening_stock_edit_select")
            record=next(r for r in rows if str(r.get("id"))==selected_id)
            with st.form("opening_stock_edit_form"):
                c=st.columns(4,gap="small")
                e_stage=c[0].selectbox("Stage",list(OPENING_STOCK_STAGES),index=list(OPENING_STOCK_STAGES).index(str(record.get("stage"))) if str(record.get("stage")) in OPENING_STOCK_STAGES else 0,format_func=lambda v:OPENING_STOCK_STAGES[v])
                e_qty=c[1].number_input("Opening Qty pcs",min_value=0.0,value=float(number(record.get("quantity_pcs"))),step=1.0)
                e_available=c[2].number_input("Available Qty pcs",min_value=0.0,value=float(number(record.get("available_quantity_pcs"))),step=1.0)
                e_kg=c[3].number_input("Opening Qty kg",min_value=0.0,value=float(number(record.get("quantity_kg"))),step=1.0)
                c=st.columns(4,gap="small")
                e_lot=c[0].text_input("Opening Reference",value=str(record.get("lot_reference") or ""))
                e_heat=c[1].text_input("Heat Number",value=str(record.get("heat_number") or ""))
                e_heat_code=c[2].text_input("Heat Code",value=str(record.get("heat_code") or ""))
                e_status=c[3].selectbox("Status",["ACTIVE","CONSUMED","INACTIVE"],index=["ACTIVE","CONSUMED","INACTIVE"].index(str(record.get("status") or "ACTIVE")) if str(record.get("status") or "ACTIVE") in ["ACTIVE","CONSUMED","INACTIVE"] else 0)
                e_remarks=st.text_input("Remarks",value=str(record.get("remarks") or ""))
                edit_submit=st.form_submit_button("Save Opening Stock Changes",type="primary",width="stretch",disabled=not perms["can_edit"])
            if edit_submit:
                try:
                    service.save_opening_stock({
                        "part_id":record.get("part_id"),"stage":e_stage,"material_grade_id":record.get("material_grade_id"),"raw_material_detail_id":record.get("raw_material_detail_id"),"supplier_id":record.get("supplier_id"),
                        "lot_reference":e_lot.strip() or None,"heat_number":e_heat.strip() or None,"heat_code":e_heat_code.strip() or None,
                        "quantity_pcs":e_qty,"available_quantity_pcs":e_available,"quantity_kg":e_kg,"remarks":e_remarks.strip() or None,"status":e_status,
                    },record_id=selected_id)
                    save_success_popup("Opening Stock updated successfully.",queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))
            if password_delete_panel(repo=service.repo,table="supply_opening_stock",rows=[record],labeler=lambda r:labels[str(r["id"])],key=f"delete_opening_stock_{selected_id}",can_delete=perms["can_edit"],title="Delete Opening Stock Record",help_text="Permanent deletion requires your current QCMS password. Delete is blocked if the record has already been used for OSP genealogy."):
                st.rerun()

def render_rm_procurement() -> None:
    page_header("Raw Material Procurement","Pending Customer Orders first · sorted by upcoming customer delivery date","Supply Chain")
    service=SupplyChainService(); perms=current_permissions("SUPPLY_CHAIN"); supplier_map={str(r["id"]):party_label(r) for r in service.suppliers()}; pending=service.pending_customer_orders_for_rm()
    with stage_section("A","CUSTOMER ORDERS PENDING RM PROCUREMENT","Only Customer Orders still requiring Raw Material are shown; upcoming delivery dates are first.",key="supply_rm_pending_orders"):
        frame=_order_display_rows(service,pending); filtered=_searchable_grid(frame.drop(columns=["_id"],errors="ignore"),title="Pending RM Procurement",key="supply_rm_pending",height=420); _order_cards(filtered,key="rm_pending_cards")
        ids={str(r["id"]):r for r in pending}; labels={rid:f"{r.get('master_reference_no')} · Due {r.get('customer_delivery_date')} · Balance {number(r.get('rm_balance_kg')):,.3f} kg" for rid,r in ids.items()}; selected=st.selectbox("Select Pending Customer Order",list(labels),format_func=lambda v:labels[v],key="supply_rm_pending_select") if labels else None
    with stage_section("B","CONTROLLED PURCHASE ORDER","Create the RM Purchase Order in the controlled PO module. The PO is linked back to this Customer Order and Material Inward will be tracked against it.",key="supply_rm_procurement_entry"):
        if not selected:
            st.info("No pending Customer Order requires RM Procurement.")
        else:
            _show_order_context(service,selected,key="rm_proc_context",export=True)
            st.session_state["supply_po_source_order_id"]=selected
            st.session_state["supply_po_type"]="RAW_MATERIAL"
            if st.button("Open RM Purchase Order Module",type="primary",width="stretch",disabled=not perms["can_create"]):
                st.switch_page(st.session_state["_qsms_pages"]["supply-purchase-orders"])
    with stage_section("C","RAW MATERIAL ORDER REGISTER","Global search includes Customer Ref, supplier, order, dates, quantity and status.",key="supply_rm_procurement_register"):
        orders={str(r["id"]):r for r in service.customer_orders()}; parts,parties,grades=_maps(service); rows=service.rm_purchase_orders(); data=[]
        for r in rows:
            order=orders.get(str(r.get("customer_order_id"))) or {}; ctx=service.order_context(order); data.append({**ctx,"RM Supplier":supplier_map.get(str(r.get("rm_supplier_id")),str(r.get("rm_supplier_id"))),"Supplier Order No":r.get("supplier_order_no"),"RM Order Date":r.get("order_date"),"RM Qty kg":r.get("ordered_qty_kg"),"Expected":r.get("expected_date"),"Display Status":_due_status(r.get("status"),r.get("expected_date"))})
        _searchable_grid(pd.DataFrame(data),title="Raw Material Order Register",key="supply_rm_order_register",height=520)
    _edit_delete_panel(service,table="supply_rm_purchase_orders",rows=service.rm_purchase_orders(),title="RAW MATERIAL ORDER EDIT / DELETE",stage="D",key="supply_rm_po",labeler=lambda r:f"{r.get('supplier_order_no')} · {number(r.get('ordered_qty_kg')):,.3f} kg",fields=(("rm_supplier_id","RM Supplier","lookup",supplier_map),("supplier_order_no","Supplier Order No.","text"),("order_date","Order Date","date"),("expected_date","Expected Receipt","date"),("ordered_qty_kg","Ordered Qty kg","number"),("status","Status","select",("OPEN","PART_RECEIVED","CLOSED","CANCELLED")),("remarks","Remarks","text")),perms=perms)



def render_purchase_orders() -> None:
    page_header("Purchase Orders · Raw Material / Forging", "Controlled supplier Purchase Orders with multi-order RM consolidation, FSI Part confidentiality, supplier price history and Part Master technical data", "Supply Chain")
    service=SupplyChainService(); perms=current_permissions("SUPPLY_CHAIN")
    parts,parties,grades=_maps(service)
    supplier_rows=service.suppliers(); supplier_labels={str(r["id"]):party_label(r) for r in supplier_rows}
    pre_type=str(st.session_state.pop("supply_po_type", "RAW_MATERIAL") or "RAW_MATERIAL")
    po_type=st.radio("Purchase Order Type",["RAW_MATERIAL","FORGING"],index=0 if pre_type=="RAW_MATERIAL" else 1,horizontal=True,format_func=lambda v:"Raw Material Purchase Order" if v=="RAW_MATERIAL" else "Forging Purchase Order",key="supply_controlled_po_type")

    source_order_ids: list[str]=[]; source_order_id=None; rm_dispatch={}; selected_forging_source=None
    with stage_section("A","CUSTOMER ORDER / SCHEDULE PURCHASE ORDER ELIGIBILITY","Every open Customer Order remains visible here. Eligible sources can be selected; waiting/not-required rows show the exact reason instead of disappearing.",key="supply_po_source"):
        eligibility=service.purchase_order_source_status(po_type)
        eligibility_rows=[]
        for r in eligibility:
            ctx=service.order_context(r)
            eligibility_rows.append({**ctx,"PO Eligibility":"ELIGIBLE" if r.get("_po_eligible") else "WAITING / NOT REQUIRED","Reason":r.get("_po_reason"),"_id":r.get("id")})
        if eligibility_rows:
            _searchable_grid(pd.DataFrame(eligibility_rows).drop(columns=["_id"],errors="ignore"),title="Customer Orders / Schedules · Purchase Order Source Status",key=f"supply_po_eligibility_{po_type}",height=390)
        else:
            st.info("No open Customer Order / Schedule is available.")

        if po_type=="RAW_MATERIAL":
            # v4.14.2: one source of truth for both visibility and selection. The old page
            # rendered one all-order grid but built the selector from a second pending list;
            # any divergence made valid Customer Orders look as if they had disappeared.
            eligible_orders=[dict(r) for r in eligibility if bool(r.get("_po_eligible"))]
            pending_by_id={str(r.get("id")):r for r in service.pending_customer_orders_for_rm()}
            for row in eligible_orders:
                pending=pending_by_id.get(str(row.get("id"))) or {}
                row["rm_ordered_kg"]=number(pending.get("rm_ordered_kg"))
                row["rm_balance_kg"]=number(pending.get("rm_balance_kg") or max(number(row.get("required_rm_kg"))-number(pending.get("rm_ordered_kg")),0.0))
            labels={str(r["id"]):f"{r.get('master_reference_no')} · Customer {(parties.get(str(r.get('customer_id'))) or {}).get('party_name') or '-'} · Part {(parts.get(str(r.get('part_id'))) or {}).get('part_number') or '-'} · FSI {(parts.get(str(r.get('part_id'))) or {}).get('fsi_part_number') or 'ENTER AT PO'} · Pos {r.get('order_position') or '-'} · RM Balance {number(r.get('rm_balance_kg')):,.3f} kg · Due {r.get('customer_delivery_date') or '-'}" for r in eligible_orders}
            pre=str(st.session_state.pop("supply_po_source_order_id","") or "")
            defaults=[pre] if pre in labels else []
            source_order_ids=st.multiselect("Select ELIGIBLE Customer Orders / Schedules for this RM Purchase Order",list(labels),default=defaults,format_func=lambda v:labels[v],key="supply_po_rm_sources") if labels else []
            st.caption(f"Open Customer Orders / Schedules: {len(eligibility):,} · Eligible for RM PO: {len(eligible_orders):,}. Every open order remains visible in the status table above.")
            if source_order_ids:
                selected=[next(r for r in eligible_orders if str(r.get("id"))==oid) for oid in source_order_ids]
                selected_frame=_order_display_rows(service,selected)
                portal_table(selected_frame.drop(columns=["_id"],errors="ignore"),hide_index=True,width="stretch",height=min(300,80+len(selected)*38))
            elif labels:
                st.info("Select one or more eligible Customer Orders / Schedules. Multiple compatible sources can be combined into one supplier PO.")
            else:
                st.warning("No Customer Order is currently eligible for an RM Purchase Order. Review the eligibility/reason grid above.")
        else:
            # v4.14.2: forging selection also comes from the same all-order eligibility
            # result that drives the visible status grid.  This removes the second UI-only
            # source interpretation that could leave an eligible Customer Order visible in
            # one table but unavailable in the PO selector.
            forging_eligible=[dict(r) for r in eligibility if bool(r.get("_po_eligible")) and r.get("_po_source")]
            pending=[dict(r.get("_po_source") or {}) for r in forging_eligible]
            data=[]
            for r in pending:
                order=service.order(str(r.get("_customer_order_id") or "")) or {}
                data.append({**service.order_context(order),"Source":r.get("_source_type"),"Forging Balance pcs":r.get("_balance_pcs"),"RM Dispatch":(r.get("_rm_dispatch") or {}).get("dispatch_number"),"Heat Number":(r.get("_rm_dispatch") or {}).get("heat_number"),"Status":"ELIGIBLE","_source_id":r.get("_source_id")})
            if data:
                _searchable_grid(pd.DataFrame(data).drop(columns=["_source_id"],errors="ignore"),title="Eligible Forging Purchase Order Sources",key="supply_po_forging_pending",height=320)
            labels={}
            for i,r in enumerate(pending):
                src_order=service.order(str(r.get('_customer_order_id') or '')) or {}
                src_part=parts.get(str(src_order.get('part_id'))) or {}
                src_customer=parties.get(str(src_order.get('customer_id'))) or {}
                labels[str(i)]=f"{src_order.get('master_reference_no')} · Customer {src_customer.get('party_name') or '-'} · Part {src_part.get('part_number') or '-'} · {r.get('_source_type')} · Balance {number(r.get('_balance_pcs')):,.0f} pcs"
            chosen=st.selectbox("Select ELIGIBLE Forging PO Source",list(labels),format_func=lambda v:labels[v],key="supply_po_forging_source") if labels else None
            if chosen is not None:
                selected_forging_source=pending[int(chosen)]; source_order_id=str(selected_forging_source.get("_customer_order_id") or ""); source_order_ids=[source_order_id]; rm_dispatch=selected_forging_source.get("_rm_dispatch") or {}
            st.caption(f"Open Customer Orders / Schedules: {len(eligibility):,} · Eligible for Forging PO: {len(pending):,}. Every open order remains visible in the status table above.")
            if not labels: st.warning("No Customer Order / Supply Chain source is currently eligible for a Forging Purchase Order. Review the reason grid above.")

    with stage_section("B","PURCHASE ORDER ENTRY","Supplier-facing Item # uses the FSI Part Number. Current Price and HSN/SAC are inherited directly from the selected supplier-specific Part Master record; normal entry fields are submitted as one form to avoid a full page rerun on every edit.",key="supply_po_entry"):
        if not source_order_ids:
            st.info("Select the pending source(s) above.")
        else:
            selected_orders=[service.order(oid) or {} for oid in source_order_ids]
            if po_type=="RAW_MATERIAL":
                compatible_sets=[]
                for order in selected_orders:
                    part_id=str(order.get("part_id") or "")
                    compatible_sets.append({str(r.get("supplier_id")) for r in service.raw_material_options(part_id) if str(r.get("status") or "ACTIVE")=="ACTIVE"})
                compatible=set.intersection(*compatible_sets) if compatible_sets else set()
                supplier_options=[sid for sid in supplier_labels if sid in compatible]
                if not supplier_options:
                    st.error("The selected Customer Orders / Schedules do not share one common supplier-specific Raw Material record in Part Master. Split them into separate POs or add the same approved supplier to each Part Raw Material Detail.")
            else:
                supplier_options=list(supplier_labels)
            default_supplier=str(selected_orders[0].get("forging_supplier_id") or "") if po_type=="FORGING" and selected_orders else ""
            profile=current_profile() or {}
            login_employee_id=str(profile.get("employee_id") or "")
            login_employee=service.repo.get("employees",login_employee_id) if login_employee_id else {}
            requisitioner_name=" ".join(v for v in (str((login_employee or {}).get("first_name") or "").strip(),str((login_employee or {}).get("last_name") or "").strip()) if v).strip()
            if not requisitioner_name:
                requisitioner_name=str(profile.get("full_name") or "").strip()

            # Only the three driver controls below rerun the page because they change
            # the available master-driven values. All normal PO fields are inside the
            # form below and therefore do not refresh the page on every edit.
            driver=st.columns(3,gap="small")
            supplier_id=driver[0].selectbox("Supplier",supplier_options,index=supplier_options.index(default_supplier) if default_supplier in supplier_options else 0,format_func=lambda v:supplier_labels[v],key="controlled_po_supplier") if supplier_options else None
            order_date=driver[1].date_input("PO Date",value=date.today(),format="DD-MM-YYYY",key="controlled_po_date")
            ship_to_source=driver[2].selectbox("Ship-To Source",["CUSTOMER","SUPPLIER","VENDOR"],format_func=lambda v:SHIP_TO_SOURCE_LABELS[v],key="controlled_po_ship_to_source",help="Driver selection: changing it refreshes the controlled address list. Other PO entry fields are submitted together without per-field refresh.")

            due_dates=[_iso_date(o.get("customer_delivery_date")) for o in selected_orders if o.get("customer_delivery_date")]
            lead_days=0
            if supplier_id:
                lead_values=[]
                for source_order in selected_orders:
                    source_part_id=str(source_order.get("part_id") or "")
                    source_raw=service.raw_material_for_supplier(source_part_id,str(supplier_id),str(source_order.get("raw_material_detail_id") or "")) or {}
                    lead_values.append(int(source_raw.get("lead_time_days") or 0))
                lead_days=max(lead_values or [0])
            delivery_default=(order_date+timedelta(days=lead_days)) if lead_days>0 else (min(due_dates) if due_dates else order_date)
            if lead_days>0:
                st.caption(f"Delivery default calculated from Part Master supplier lead time: {lead_days} day(s) from PO Date. Delivery Date remains editable inside the form.")
            if not login_employee_id:
                st.error("Your login is not linked to an ACTIVE Employee Master record. Link the user to Employee Master before creating a Purchase Order so Requisitioner is controlled.")

            ship_candidates=_ship_to_candidates(parties,ship_to_source)
            ship_labels={pid:f"{row.get('party_code') or '-'} · {row.get('party_name') or '-'} · {row.get('city') or '-'}" for pid,row in ship_candidates.items()}
            default_ship_to=""
            if ship_to_source=="CUSTOMER" and selected_orders:
                candidate_customer=str(selected_orders[0].get("customer_id") or "")
                if candidate_customer in ship_labels: default_ship_to=candidate_customer
            if ship_to_source=="SUPPLIER" and str(supplier_id or "") in ship_labels: default_ship_to=str(supplier_id)
            ship_ids=list(ship_labels)
            ship_index=ship_ids.index(default_ship_to) if default_ship_to in ship_ids else 0

            allocations: dict[str,float]={}; line_prices: dict[str,float]={}; line_hsn: dict[str,str]={}; line_fsi: dict[str,str]={}; all_lines_valid=bool(supplier_id)
            po_event="RM_PO_CREATED" if po_type=="RAW_MATERIAL" else "FORGING_PO_CREATED"
            form_key=f"controlled_po_form_{po_type}_{str(supplier_id or 'none')[:8]}_{ship_to_source}_{'_'.join(str(v)[:6] for v in source_order_ids)}"
            with st.form(form_key):
                c=st.columns(2,gap="small")
                delivery_date=c[0].date_input("Delivery Date",value=delivery_default,format="DD-MM-YYYY",help="Automatically defaults from supplier lead time; editable before PO creation.")
                c[1].text_input("Requisitioner (Logged-in Employee)",value=requisitioner_name or "Employee link required",disabled=True)

                section_bar("SHIP-TO ADDRESS · MASTER CONTROLLED")
                ship_to_party_id=st.selectbox("Ship-To Party / Address",ship_ids,index=ship_index if ship_ids else 0,format_func=lambda v:ship_labels[v]) if ship_ids else None
                selected_ship_to=ship_candidates.get(str(ship_to_party_id or "")) or {}
                if selected_ship_to:
                    st.text_area("Selected Ship-To Address Preview",value=_party_address_preview(selected_ship_to),height=125,disabled=True)
                else:
                    st.warning(f"No ACTIVE records are available in {SHIP_TO_SOURCE_LABELS[ship_to_source]}. Add the address in the corresponding master before creating the PO.")

                c=st.columns(4,gap="small")
                ship_via=c[0].text_input("Ship Via",value="Road"); incoterm=c[1].text_input("Incoterm",value="DAP, CHAKAN"); payment=c[2].text_input("Payment Term",value="NET 30 DAYS AFTER GRN"); quote_date=c[3].date_input("Quotation Date",value=date.today(),format="DD-MM-YYYY")
                c=st.columns(2,gap="small"); quote_ref=c[0].text_input("Quotation Reference"); old_po=c[1].text_input("Old PO Details")
                gst=st.number_input("GST %",min_value=0.0,value=18.0,step=1.0)

                if po_type=="RAW_MATERIAL" and supplier_id:
                    allocation_rows=[]; raw_for_order={}; group_order_ids={}
                    for order in selected_orders:
                        oid=str(order.get("id") or ""); part=parts.get(str(order.get("part_id"))) or {}; totals=service.totals(oid); balance=max(number(order.get("required_rm_kg"))-totals["rm_ordered_kg"],0.0)
                        raw=service.raw_material_for_supplier(str(part.get("id") or ""),supplier_id,str(order.get("raw_material_detail_id") or "")); raw_for_order[oid]=raw
                        group_key=f"{part.get('id')}|{(raw or {}).get('id') or ''}"; group_order_ids.setdefault(group_key,[]).append(oid)
                        customer=parties.get(str(order.get("customer_id"))) or {}
                        allocation_rows.append({"Order ID":oid,"Customer Order / Schedule":order.get("master_reference_no"),"Customer":customer.get("party_name"),"Part Number":part.get("part_number"),"Position":order.get("order_position"),"FSI Part Number":part.get("fsi_part_number") or "ENTER IN ITEM GRID","Part Description":part.get("part_name"),"RM Section":(raw or {}).get("section_size") or "NO SUPPLIER RM DETAIL","Pending RM kg":balance,"PO Allocation kg":balance})
                        if not raw: all_lines_valid=False
                    alloc_df=pd.DataFrame(allocation_rows)
                    alloc_edit=st.data_editor(alloc_df,hide_index=True,width="stretch",height=min(360,90+len(alloc_df)*38),key="controlled_po_allocations_form",disabled=["Order ID","Customer Order / Schedule","Customer","Part Number","Position","FSI Part Number","Part Description","RM Section","Pending RM kg"],column_config={"Order ID":None,"Pending RM kg":st.column_config.NumberColumn(format="%.3f"),"PO Allocation kg":st.column_config.NumberColumn(min_value=0.001,format="%.3f",required=True)})
                    for _,row in alloc_edit.iterrows(): allocations[str(row.get("Order ID"))]=number(row.get("PO Allocation kg"))

                    line_rows=[]; group_data={}
                    for order in selected_orders:
                        oid=str(order.get("id")); part=parts.get(str(order.get("part_id"))) or {}; raw=raw_for_order.get(oid) or {}; key=f"{part.get('id')}|{raw.get('id') or ''}"
                        group=group_data.setdefault(key,{"part":part,"raw":raw,"qty":0.0}); group["qty"]+=allocations.get(oid,0.0)
                    for key,group in group_data.items():
                        part,raw=group["part"],group["raw"]; current=service.current_price(str(part.get("id") or ""),supplier_id,on_date=order_date,uom="KGS"); master_hsn=str(raw.get("hsn_sac_code") or part.get("hsn_sac_code") or "").strip()
                        line_rows.append({"Line Key":key,"FSI Part Number":part.get("fsi_part_number"),"HSN / SAC":master_hsn,"Part Description":part.get("part_name"),"Raw Material Section":raw.get("material_section_name"),"Section Size":raw.get("section_size"),"PO Qty kg":round(group["qty"],3),"Current Price":current})
                        if current<=0 or not master_hsn: all_lines_valid=False
                    line_df=pd.DataFrame(line_rows)
                    line_edit=st.data_editor(line_df,hide_index=True,width="stretch",height=min(330,90+len(line_df)*38),key="controlled_po_lines_form",disabled=["Line Key","HSN / SAC","Part Description","Raw Material Section","Section Size","PO Qty kg","Current Price"],column_config={"Line Key":None,"FSI Part Number":st.column_config.TextColumn(required=True,help="Supplier-facing FSI identity. If Part Master is blank, enter it here; the original Customer Part Number is never printed."),"HSN / SAC":st.column_config.TextColumn(help="Read-only supplier/raw-material HSN from Part Master."),"PO Qty kg":st.column_config.NumberColumn(format="%.3f"),"Current Price":st.column_config.NumberColumn(format="%.2f",help="Read-only current supplier price from Part Master price history.")})
                    for _,row in line_edit.iterrows():
                        key=str(row.get("Line Key")); line_prices[key]=number(row.get("Current Price")); line_hsn[key]=str(row.get("HSN / SAC") or "").strip(); line_fsi[key]=str(row.get("FSI Part Number") or "").strip()
                        if not line_fsi[key] or line_prices[key]<=0 or not line_hsn[key]: all_lines_valid=False
                    if any(number(r.get("Current Price"))<=0 for _,r in line_edit.iterrows()): st.warning("Current Price is missing in Part Master price history for one or more items. Add the current supplier price before creating the PO.")
                    if any(not str(r.get("HSN / SAC") or "").strip() for _,r in line_edit.iterrows()): st.warning("HSN / SAC is missing in Part Master Raw Material Details for one or more items. Add it in Part Master before creating the PO.")

                    section_bar("PART MASTER TECHNICAL DATA & PRICE HISTORY","Read-only PO source data. Current Price and HSN/SAC are master-controlled.")
                    for key,group in group_data.items():
                        part,raw=group["part"],group["raw"]
                        with st.container(border=True):
                            st.markdown(f"**FSI {part.get('fsi_part_number') or '-'} · {part.get('part_name') or '-'} · {supplier_labels.get(supplier_id,'Supplier')}**")
                            tech=service.technical_data_snapshot(raw,part)
                            if tech: portal_table(pd.DataFrame([{"Heading":r.get("heading"),"Value":r.get("value")} for r in tech]),hide_index=True,width="stretch",height=min(300,70+len(tech)*34))
                            hist=service.price_history(str(part.get("id") or ""),supplier_id,uom="KGS")
                            if hist: portal_table(pd.DataFrame([{"Start Date":r.get("start_date"),"End Date":r.get("end_date") or "Current","Basic Rate":r.get("price"),"Freight":r.get("freight"),"Tool Cost":r.get("tool_cost"),"P&F":r.get("packing_forwarding"),"Profit":r.get("profit"),"ICC/Rej.":r.get("icc_rejection"),"Currency":r.get("currency"),"UOM":r.get("uom"),"Remark":r.get("remarks") or "","Status":r.get("status") or "ACTIVE"} for r in reversed(hist)]),hide_index=True,width="stretch",height=min(320,70+len(hist)*34))
                elif po_type=="FORGING" and supplier_id:
                    order=selected_orders[0]; source_order_id=str(order.get("id") or ""); part=parts.get(str(order.get("part_id"))) or {}; raw=service.raw_material_for_supplier(str(part.get("id") or ""),supplier_id,str(order.get("raw_material_detail_id") or "")) or {}
                    customer=parties.get(str(order.get("customer_id"))) or {}
                    st.info(f"Customer: **{customer.get('party_name') or '-'}** · Part Number: **{part.get('part_number') or '-'}** · Customer Ref: **{order.get('master_reference_no') or '-'}**")
                    totals=service.totals(source_order_id); default_qty=max(number(order.get("order_qty_pcs"))-totals["forging_ordered_pcs"],1.0)
                    current_price=service.current_price(str(part.get("id") or ""),supplier_id,on_date=order_date,uom="NOS"); hsn_sac_code=str(raw.get("hsn_sac_code") or part.get("hsn_sac_code") or "").strip(); fsi_default=str(part.get("fsi_part_number") or "")
                    c=st.columns(5,gap="small"); qty=c[0].number_input("Order Quantity",min_value=0.001,value=float(default_qty),step=1.0); c[1].text_input("UOM",value="NOS",disabled=True); unit_price=c[2].number_input("Current Price",min_value=0.0,value=float(current_price),step=0.01,disabled=True,help="Read-only current supplier price from Part Master price history."); c[3].text_input("HSN / SAC Code",value=hsn_sac_code,disabled=True,help="Read-only HSN/SAC from supplier Raw Material Detail; Part Master header HSN is fallback."); fsi_part_number=c[4].text_input("FSI Part Number",value=fsi_default,help="Required supplier-facing identity; Customer Part Number is not printed.")
                    section_bar("PART MASTER TECHNICAL DATA & PRICE HISTORY")
                    tech=service.technical_data_snapshot(raw,part); hist=service.price_history(str(part.get("id") or ""),supplier_id,uom="NOS")
                    if tech: portal_table(pd.DataFrame([{"Heading":r.get("heading"),"Value":r.get("value")} for r in tech]),hide_index=True,width="stretch")
                    if hist: portal_table(pd.DataFrame([{"Start Date":r.get("start_date"),"End Date":r.get("end_date") or "Current","Basic Rate":r.get("price"),"Freight":r.get("freight"),"Tool Cost":r.get("tool_cost"),"P&F":r.get("packing_forwarding"),"Profit":r.get("profit"),"ICC/Rej.":r.get("icc_rejection"),"Currency":r.get("currency"),"UOM":r.get("uom"),"Remark":r.get("remarks") or "","Status":r.get("status") or "ACTIVE"} for r in reversed(hist)]),hide_index=True,width="stretch")
                    all_lines_valid=bool(str(fsi_part_number or "").strip()) and current_price>0 and bool(hsn_sac_code)
                    if current_price<=0: st.warning("Current Price is missing in Part Master price history. Add the current supplier price before creating the PO.")
                    if not hsn_sac_code: st.warning("HSN / SAC is missing in Part Master Raw Material Details. Add it before creating the PO.")

                remarks=st.text_area("Remarks",value="PART WILL BE SUPPLIED AS PER DRAWING.",height=70)
                instructions=st.text_area("Comments / Special Instructions",value=DEFAULT_SPECIAL_INSTRUCTIONS,height=135)
                notify_pref=notification_confirmation(
                    NotificationService(service.repo), po_event, key=f"po_entry_notify_{po_type}_{str(supplier_id or 'none')[:8]}",
                    context={"supplier_id":str(supplier_id or ""),"supplier_name":supplier_labels.get(str(supplier_id),"Supplier"),"next_task":"Raw Material Receipt / Material Inward" if po_type=="RAW_MATERIAL" else "Forging Receipt"},
                    include_supplier=True, default_send=True,
                )
                create_disabled=not perms["can_create"] or not supplier_id or not all_lines_valid or not ship_to_party_id or not login_employee_id or (notify_pref["send"] and not notify_pref["confirmed"])
                create_po=st.form_submit_button("Create Controlled Purchase Order",type="primary",width="stretch",disabled=create_disabled)

            if create_po:
                try:
                    payload={"po_type":po_type,"supplier_id":supplier_id,"order_date":order_date.isoformat(),"delivery_date":delivery_date.isoformat(),"requisitioner":requisitioner_name or None,"requisitioner_employee_id":login_employee_id or None,"ship_to_party_id":str(ship_to_party_id or "") or None,"ship_to_source_type":ship_to_source,"ship_via":ship_via.strip(),"incoterm":incoterm.strip(),"payment_term":payment.strip(),"quotation_reference":quote_ref.strip() or None,"quotation_date":quote_date.isoformat(),"old_po_reference":old_po.strip() or None,"gst_percent":gst,"remarks":remarks.strip() or None,"special_instructions":instructions.strip() or None}
                    if po_type=="RAW_MATERIAL": payload.update({"customer_order_ids":source_order_ids,"allocations":allocations,"line_prices":line_prices,"line_hsn_sac":line_hsn,"line_fsi_part_numbers":line_fsi})
                    else: payload.update({"customer_order_id":source_order_id,"quantity":qty,"uom":"NOS","unit_price":unit_price,"hsn_sac_code":hsn_sac_code or None,"fsi_part_number":str(fsi_part_number or "").strip(),"rm_dispatch":rm_dispatch})
                    result=service.create_purchase_order(payload)
                    st.session_state["last_supply_purchase_order_id"]=str((result.get("header") or {}).get("id") or "")
                    header_result=result.get("header") or {}
                    if notify_pref["send"] and notify_pref["confirmed"]:
                        NotificationService(service.repo).notify(po_event,related_table="supply_purchase_orders",related_id=str(header_result.get("id") or ""),context={"po_number":header_result.get("po_number"),"po_type":po_type,"customer_order_ids":source_order_ids,"supplier_id":str(supplier_id or ""),"supplier_name":supplier_labels.get(str(supplier_id),"Supplier"),"entry_email_confirmed":True,"next_task":"Raw Material Receipt / Material Inward" if po_type=="RAW_MATERIAL" else "Forging Receipt"})
                    save_success_popup(f"Purchase Order {header_result.get('po_number')} created with {len(result.get('items') or [])} vendor line(s) and {len(result.get('stages') or [])} linked Supply Chain allocation(s).",queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))

            last_id=str(st.session_state.get("last_supply_purchase_order_id") or "")
            if last_id:
                header=service.purchase_order(last_id) or {}; items=service.purchase_order_items_for_print(last_id)
                if header and items:
                    try: st.download_button("Download / Print Purchase Order PDF",purchase_order_pdf_bytes(header,items),file_name=f"{header.get('po_number')}.pdf",mime="application/pdf",icon=":material/picture_as_pdf:",width="stretch",key=f"download_supply_po_{last_id}")
                    except Exception as exc: st.error(f"Purchase Order PDF could not be generated: {exc}")

    with stage_section("C","PURCHASE ORDER REGISTER","All RM and Forging POs with item-level receipt progress, linked Customer Orders / Schedules, internal original Part Number and supplier-facing FSI Part Number.",key="supply_po_register"):
        rows=service.purchase_order_rows(); frame=pd.DataFrame(rows)
        _searchable_grid(frame.drop(columns=["_po_id","_item_id","_part_id","_supplier_id"],errors="ignore"),title="Purchase Order Register",key="supply_purchase_order_register",height=560)
        headers={str(r.get("id")):r for r in service.purchase_orders()}
        labels={pid:f"{h.get('po_number')} · {str(h.get('po_type') or '').replace('_',' ').title()} · {supplier_labels.get(str(h.get('supplier_id')),'Supplier')} · {len(service.purchase_order_items(pid))} line(s) · {h.get('status')}" for pid,h in headers.items()}
        selected_po=st.selectbox("Purchase Order for PDF / Status",list(labels),format_func=lambda v:labels[v],key="supply_po_register_select") if labels else None
        if selected_po:
            service.sync_purchase_order_status(selected_po); header=service.purchase_order(selected_po) or {}; items=service.purchase_order_items_for_print(selected_po); c=st.columns(2,gap="small")
            try: c[0].download_button("Download / Print Selected PO",purchase_order_pdf_bytes(header,items),file_name=f"{header.get('po_number')}.pdf",mime="application/pdf",width="stretch",key=f"selected_po_pdf_{selected_po}")
            except Exception as exc: c[0].error(str(exc))
            if c[1].button("Cancel Selected PO",width="stretch",disabled=not perms["can_edit"] or str(header.get("status"))=="CLOSED"):
                service.repo.update("supply_purchase_orders",selected_po,{"status":"CANCELLED"}); save_success_popup("Purchase Order cancelled.",queue_for_rerun=True); st.rerun()

    rows=service.purchase_order_rows(); all_frame=pd.DataFrame(rows)
    with stage_section("D","PURCHASE ORDER REPORTS","Pending Purchase Orders, RM Orders, RM Section Orders, Supplier Orders and RM-for-Part-Number Orders.",key="supply_po_reports"):
        report_name=st.selectbox("Purchase Order Report",["Pending Purchase Orders","Raw Material Orders","RM Section Orders","Supplier Orders","RM for Part Number Orders"],key="supply_po_report_name")
        report=all_frame.copy()
        if not report.empty:
            if report_name=="Pending Purchase Orders": report=report[~report["Status"].astype(str).isin(["CLOSED","CANCELLED"])]
            elif report_name=="Raw Material Orders": report=report[report["PO Type"]=="Raw Material"]
            elif report_name=="RM Section Orders": report=report[report["PO Type"]=="Raw Material"].sort_values(["RM Section","Delivery Date"],na_position="last")
            elif report_name=="Supplier Orders": report=report.sort_values(["Supplier","Delivery Date"],na_position="last")
            elif report_name=="RM for Part Number Orders": report=report[report["PO Type"]=="Raw Material"].sort_values(["Part Number","FSI Part Number","Delivery Date"],na_position="last")
        _searchable_grid(report.drop(columns=["_po_id","_item_id","_part_id","_supplier_id"],errors="ignore"),title=report_name,key="supply_po_management_report",height=520)

def render_rm_receipt() -> None:
    page_header("Raw Material Receipt · Material Inward Link","Material Inward is the source of truth; no duplicate RM receipt entry","Supply Chain")
    service=SupplyChainService(); perms=current_permissions("SUPPLY_CHAIN"); pending=service.pending_rm_purchase_orders(); orders={str(r["id"]):r for r in service.customer_orders()}; supplier_map={str(r["id"]):party_label(r) for r in service.suppliers()}
    with stage_section("A","PENDING RM PROCUREMENT FOR MATERIAL INWARD","Only RM Procurement balances pending receipt are shown. Overdue expected dates are red.",key="supply_rm_receipt_pending"):
        data=[]
        for po in pending:
            ctx=service.order_context(orders.get(str(po.get("customer_order_id"))) or {}); data.append({**ctx,"RM Supplier":supplier_map.get(str(po.get("rm_supplier_id")),str(po.get("rm_supplier_id"))),"RM PO":po.get("supplier_order_no"),"Ordered kg":po.get("ordered_qty_kg"),"Received kg":po.get("received_qty_kg"),"Balance kg":po.get("balance_qty_kg"),"Expected":po.get("expected_date"),"Display Status":_due_status(po.get("status"),po.get("expected_date")),"_id":str(po.get("id"))})
        frame=pd.DataFrame(data); filtered=_searchable_grid(frame.drop(columns=["_id"],errors="ignore"),title="Pending RM Procurement for Material Inward",key="supply_rm_receipt_pending_grid",height=420)
        labels={str(po["id"]):f"{po.get('supplier_order_no')} · Expected {po.get('expected_date')} · Balance {number(po.get('balance_qty_kg')):,.3f} kg" for po in pending}; po_id=st.selectbox("Select Pending RM Procurement",list(labels),format_func=lambda v:labels[v],key="supply_rm_receipt_po") if labels else None
    with stage_section("B","LINK MATERIAL INWARD TO RM PROCUREMENT","Use the existing Material Inward module. Heat, Heat Code, RMTC Number, RMTC Date and RMTC Quantity are inherited from that record.",key="supply_rm_receipt_link"):
        if not po_id: st.info("No pending RM Procurement is waiting for Material Inward.")
        else:
            po=service.repo.get("supply_rm_purchase_orders",po_id) or {}; order_id=str(po.get("customer_order_id") or ""); _show_order_context(service,order_id,key="rm_receipt_context",export=True)
            eligible=service.eligible_inwards_for_po(po_id)
            eligible_frame=pd.DataFrame([{
                "Material Inward":r.get("inward_number"),"Inward Date":r.get("inward_date"),"GRN":r.get("grn_number"),
                "Supplier":r.get("supplier_name"),"Part Number":r.get("part_number"),"Material Grade":r.get("material_grade"),
                "Heat Number":r.get("heat_number"),"Heat Code":r.get("heat_code"),"RMTC Number":r.get("rmtc_number"),
                "RMTC Date":r.get("rmtc_date"),"RMTC Qty kg":r.get("rmtc_steel_quantity_kg"),
                "Inward Qty kg":r.get("steel_quantity_kg") or r.get("quantity_received"),"Status":r.get("status")
            } for r in eligible])
            _searchable_grid(eligible_frame,title="Eligible Material Inward Records",key="supply_eligible_inwards",height=300,header={"RM Procurement":po.get("supplier_order_no")})
            inward_labels={str(r["id"]):f"{r.get('inward_number')} · {r.get('part_number')} · Heat {r.get('heat_number')} · {number(r.get('steel_quantity_kg') or r.get('quantity_received')):,.3f} kg · RMTC {r.get('rmtc_number') or '-'}" for r in eligible}
            c1,c2=st.columns([3,1],gap="small"); inward_id=c1.selectbox("Existing Material Inward",[""]+list(inward_labels),format_func=lambda v:inward_labels.get(v,"— Select existing Material Inward —"),key="supply_link_inward")
            if c2.button("Open New Material Inward",icon=":material/input:",width="stretch"):
                st.session_state["supply_rm_po_link_id"]=po_id; st.session_state["supply_customer_order_link_id"]=order_id; st.session_state.pop("edit_inward_id",None); st.switch_page(st.session_state["_qsms_pages"]["inward-entry"])
            if inward_id:
                selected_inward=next(r for r in eligible if str(r["id"])==inward_id); detail=pd.DataFrame([{k:selected_inward.get(k) for k in ("inward_number","inward_date","grn_number","supplier_name","part_number","material_grade","heat_number","heat_code","rmtc_number","rmtc_date","rmtc_steel_quantity_kg","steel_quantity_kg","quality_disposition","status") if k in selected_inward}]); portal_table(_style_supply_dataframe(detail.rename(columns={"rmtc_date":"RMTC Date","rmtc_steel_quantity_kg":"RMTC Qty kg"})),hide_index=True,width="stretch")
                if st.button("Link Selected Material Inward to RM Procurement",type="primary",width="stretch",disabled=not perms["can_edit"]):
                    try: service.link_inward_to_rm_po(po_id,inward_id); save_success_popup("Material Inward linked to RM Procurement; RM Receipt genealogy updated.",queue_for_rerun=True); st.rerun()
                    except Exception as exc: st.error(str(exc))
    with stage_section("C","RAW MATERIAL RECEIPT / MATERIAL INWARD REGISTER","Linked receipt view includes Heat and RMTC details; global search covers every displayed field.",key="supply_rm_receipt_register"):
        rows=service.rm_receipts(); data=[]
        for r in rows:
            order=orders.get(str(r.get("customer_order_id"))) or {}; ctx=service.order_context(order); data.append({**ctx,"Material Inward":r.get("receipt_number"),"Inward Date":r.get("receipt_date"),"Heat Number":r.get("heat_number"),"Heat Code":r.get("heat_code"),"RMTC Number":r.get("rmtc_number"),"RMTC Date":r.get("rmtc_date"),"RMTC Qty kg":r.get("rmtc_qty_kg"),"Received Qty kg":r.get("received_qty_kg"),"GRN / Challan":r.get("supplier_challan"),"Status":"RECEIVED"})
        _searchable_grid(pd.DataFrame(data),title="Material Inward Linked RM Receipt Register",key="supply_rm_receipt_register_grid",height=540)
        if rows:
            linked={str(r["id"]):r for r in rows}; opts={rid:f"{r.get('receipt_number')} · Heat {r.get('heat_number')}" for rid,r in linked.items()}; chosen=st.selectbox("Open Linked Material Inward",list(opts),format_func=lambda v:opts[v],key="supply_open_linked_inward"); inward_id=str(linked[chosen].get("inward_lot_id") or "")
            if st.button("Edit Selected in Material Inward Module",width="stretch",disabled=not inward_id): st.session_state["edit_inward_id"]=inward_id; st.switch_page(st.session_state["_qsms_pages"]["inward-entry"])
            if password_delete_panel(repo=service.repo,table="supply_rm_receipts",rows=[linked[chosen]],labeler=lambda r:f"{r.get('receipt_number')} · Heat {r.get('heat_number')}",key=f"supply_rm_receipt_delete_{chosen}",can_delete=perms["can_archive"],title="Delete Supply Chain RM Receipt Link",help_text="This removes the Supply Chain link only after password confirmation. The original Material Inward record remains controlled in Material Inward."): st.rerun()


def render_rm_dispatch() -> None:
    page_header("Raw Material to Forging","Select from pending RM Receipt / Material Inward balances; Heat follows automatically","Supply Chain")
    service=SupplyChainService(); perms=current_permissions("SUPPLY_CHAIN"); parties={str(r["id"]):r for r in service.parties()}; pending=service.pending_rm_receipts_for_dispatch(); orders={str(r["id"]):r for r in service.customer_orders()}
    with stage_section("A","RM RECEIPTS PENDING DISPATCH TO FORGING","Only received material with remaining dispatch balance is shown.",key="supply_rm_dispatch_pending"):
        data=[]
        for r in pending:
            ctx=service.order_context(orders.get(str(r.get("customer_order_id"))) or {}); data.append({**ctx,"Material Inward":r.get("receipt_number"),"Heat Number":r.get("heat_number"),"Heat Code":r.get("heat_code"),"RMTC Number":r.get("rmtc_number"),"Received kg":r.get("received_qty_kg"),"Dispatched kg":r.get("dispatched_qty_kg"),"Balance kg":r.get("balance_qty_kg"),"Status":"PENDING","_id":str(r.get("id"))})
        frame=pd.DataFrame(data); _searchable_grid(frame.drop(columns=["_id"],errors="ignore"),title="RM Receipt Pending Dispatch",key="supply_rm_dispatch_pending_grid",height=420)
        labels={str(r["id"]):f"{r.get('receipt_number')} · Heat {r.get('heat_number')} · Balance {number(r.get('balance_qty_kg')):,.3f} kg" for r in pending}; rec_id=st.selectbox("Select RM Receipt / Material Inward",list(labels),format_func=lambda v:labels[v],key="supply_rm_dispatch_receipt") if labels else None
    with stage_section("B","RM DISPATCH TO FORGING SUPPLIER","Customer, Part, forging supplier, Heat and RMTC context are inherited; only dispatch-specific data is entered.",key="supply_rm_dispatch_entry"):
        if not rec_id: st.info("No RM Receipt balance is pending dispatch.")
        else:
            rec=next(r for r in pending if str(r["id"])==rec_id); order_id=str(rec.get("customer_order_id")); order=_show_order_context(service,order_id,key="rm_dispatch_context",export=True); supplier_id=str(order.get("forging_supplier_id")); st.info(f"Forging Supplier: **{party_label(parties.get(supplier_id) or {})}** · Heat **{rec.get('heat_number') or '-'}** · Available **{number(rec.get('balance_qty_kg')):,.3f} kg**")
            c=st.columns(4,gap="small"); dispatch=c[0].text_input("RM Dispatch No."); d=c[1].date_input("Dispatch Date",value=date.today(),format="DD-MM-YYYY"); qty=c[2].number_input("Dispatch Qty kg",min_value=.001,max_value=float(max(number(rec.get("balance_qty_kg")),.001)),value=float(max(min(number(rec.get("balance_qty_kg")),number(rec.get("balance_qty_kg"))),.001)),step=1.0); challan=c[3].text_input("Challan No.")
            vehicle=st.text_input("Vehicle No."); remarks=st.text_input("Dispatch Remarks")
            if st.button("Post RM Dispatch to Forging",type="primary",width="stretch",disabled=not perms["can_create"] or not dispatch.strip()):
                try: service.save_transaction("supply_rm_dispatches",{"customer_order_id":order_id,"rm_receipt_id":rec_id,"inward_lot_id":rec.get("inward_lot_id"),"forging_supplier_id":supplier_id,"dispatch_number":dispatch.strip(),"dispatch_date":d.isoformat(),"heat_number":rec.get("heat_number"),"heat_code":rec.get("heat_code"),"qty_kg":qty,"challan_number":challan.strip() or None,"vehicle_number":vehicle.strip() or None,"remarks":remarks.strip() or None}); service.sync_order_status(order_id); save_success_popup("RM dispatched with inherited Heat traceability.",queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))
    with stage_section("C","RM TO FORGING REGISTER","Global searchable and exportable genealogy register.",key="supply_rm_dispatch_register"):
        rows=service.rm_dispatches(); data=[]
        for r in rows:
            ctx=service.order_context(orders.get(str(r.get("customer_order_id"))) or {}); data.append({**ctx,"Dispatch No":r.get("dispatch_number"),"Dispatch Date":r.get("dispatch_date"),"Forging Supplier":party_label(parties.get(str(r.get("forging_supplier_id"))) or {}),"Heat Number":r.get("heat_number"),"Heat Code":r.get("heat_code"),"Qty kg":r.get("qty_kg"),"Challan":r.get("challan_number"),"Vehicle":r.get("vehicle_number"),"Status":"DISPATCHED"})
        _searchable_grid(pd.DataFrame(data),title="RM to Forging Register",key="supply_rm_dispatch_register_grid",height=520)
    _edit_delete_panel(service,table="supply_rm_dispatches",rows=service.rm_dispatches(),title="RM TO FORGING EDIT / DELETE",stage="D",key="supply_rm_dispatch",labeler=lambda r:f"{r.get('dispatch_number')} · Heat {r.get('heat_number')}",fields=(("dispatch_number","Dispatch No.","text"),("dispatch_date","Dispatch Date","date"),("qty_kg","Qty kg","number"),("challan_number","Challan No.","text"),("vehicle_number","Vehicle No.","text"),("remarks","Remarks","text")),perms=perms)


def render_forging() -> None:
    page_header("Forging Order & Receipt","Supports both Supply Chain flows: FSI-RM linked forging and RM-responsible-forger flow from Customer Order","Supply Chain")
    service=SupplyChainService(); perms=current_permissions("SUPPLY_CHAIN"); parties={str(r["id"]):r for r in service.parties()}; orders={str(r["id"]):r for r in service.customer_orders()}
    pending_dispatch=service.pending_rm_dispatches_for_forging_order(); pending_direct=service.pending_direct_forging_orders()
    if st.button("Open Controlled Forging Purchase Order Module",type="primary",width="stretch",key="open_forging_po_module"):
        st.session_state["supply_po_type"]="FORGING"; st.switch_page(st.session_state["_qsms_pages"]["supply-purchase-orders"])

    with stage_section("A","FORGING ORDER SOURCE","Flow 1 selects pending RM-to-Forger dispatch. Flow 2 selects the Customer Order directly and bypasses FSI RM stages.",key="supply_forging_source"):
        source_flow=st.radio("Supply Chain Flow",[FLOW_FSI_RM,FLOW_DIRECT_FORGING],horizontal=True,format_func=lambda v:FLOW_LABELS[v],key="supply_forging_source_flow")
        dispatch_id=None; direct_order_id=None
        if source_flow==FLOW_FSI_RM:
            data=[]
            for r in pending_dispatch:
                order=orders.get(str(r.get("customer_order_id"))) or {}
                if service.flow_for_order(order)!=FLOW_FSI_RM: continue
                ctx=service.order_context(order); data.append({**ctx,"RM Dispatch":r.get("dispatch_number"),"Dispatch Date":r.get("dispatch_date"),"Heat Number":r.get("heat_number"),"Heat Code":r.get("heat_code"),"RM Qty kg":r.get("qty_kg"),"Status":"PENDING","_id":str(r.get("id"))})
            frame=pd.DataFrame(data); _searchable_grid(frame.drop(columns=["_id"],errors="ignore"),title="Flow 1 · RM Dispatch Pending Forging Order",key="supply_forging_pending_rm",height=360)
            ids={str(r["id"]):r for r in pending_dispatch if service.flow_for_order(orders.get(str(r.get("customer_order_id"))) or {})==FLOW_FSI_RM}
            labels={rid:f"{r.get('dispatch_number')} · Heat {r.get('heat_number') or '-'} · {number(r.get('qty_kg')):,.3f} kg" for rid,r in ids.items()}
            dispatch_id=st.selectbox("Select RM-to-Forger Dispatch",list(labels),format_func=lambda v:labels[v],key="supply_forging_dispatch") if labels else None
            if not labels: st.info("No Flow 1 RM dispatch is waiting for a Forging Order.")
        else:
            frame=_order_display_rows(service,pending_direct); filtered=_searchable_grid(frame.drop(columns=["_id"],errors="ignore"),title="Flow 2 · Customer Orders Pending Forging Order",key="supply_forging_pending_direct",height=380); _order_cards(filtered,key="supply_forging_direct_cards")
            labels={str(r["id"]):f"{r.get('master_reference_no')} · {r.get('order_position') or '-'} · Balance {number(r.get('forging_balance_pcs')):,.0f} pcs · Due {r.get('customer_delivery_date') or '-'}" for r in pending_direct}
            direct_order_id=st.selectbox("Select Customer Order for Forging Order",list(labels),format_func=lambda v:labels[v],key="supply_forging_direct_order") if labels else None
            if not labels: st.info("No Flow 2 Customer Order is waiting for a Forging Order.")

    with stage_section("B","FORGING SUPPLIER ORDER","All Customer, Part, supplier and quantity context is inherited from the selected flow source.",key="supply_forging_order"):
        order_id=""; source={}; inherited_heat=""; inherited_code=""; inward_lot_id=None; rm_dispatch_id=None
        if source_flow==FLOW_FSI_RM and dispatch_id:
            source=next(r for r in pending_dispatch if str(r["id"])==dispatch_id); order_id=str(source.get("customer_order_id") or ""); inherited_heat=str(source.get("heat_number") or ""); inherited_code=str(source.get("heat_code") or ""); inward_lot_id=source.get("inward_lot_id"); rm_dispatch_id=dispatch_id
        elif source_flow==FLOW_DIRECT_FORGING and direct_order_id:
            order_id=str(direct_order_id); source=service.order(order_id) or {}
        if order_id:
            order=_show_order_context(service,order_id,key="forging_order_context",export=True); sid=str(order.get("forging_supplier_id") or ""); gross=number(order.get("gross_weight_kg_snapshot")); totals=service.totals(order_id); balance=max(number(order.get("order_qty_pcs"))-totals["forging_ordered_pcs"],0) if source_flow==FLOW_DIRECT_FORGING else number(order.get("order_qty_pcs"))
            c=st.columns(4,gap="small"); c[0].text_input("Forging Supplier",value=party_label(parties.get(sid) or {}),disabled=True); supplier_order=c[1].text_input("Forging Supplier Order No."); od=c[2].date_input("Order Date",value=date.today(),format="DD-MM-YYYY"); expected=c[3].date_input("Expected Forging Receipt",value=date.today(),format="DD-MM-YYYY")
            qty=st.number_input("Forging Order Qty pcs",min_value=1.0,max_value=float(max(balance,1)),value=float(max(balance,1)),step=1.0,disabled=source_flow==FLOW_DIRECT_FORGING,help="Flow 2 uses the full pending Customer Order quantity because the controlled database allows one active forging order per Customer Order / forging supplier.")
            c=st.columns(2,gap="small")
            if source_flow==FLOW_FSI_RM:
                heat_number=c[0].text_input("Heat Number",value=inherited_heat,disabled=True); heat_code=c[1].text_input("Heat Code",value=inherited_code,disabled=True)
            else:
                heat_number=c[0].text_input("Supplier Heat Number (if known)",value="",help="For Flow 2, Heat may be entered now or before Forging Receipt once the forging supplier confirms it."); heat_code=c[1].text_input("Supplier Heat Code (if known)",value="")
            remarks=st.text_input("Forging Order Remarks")
            st.metric("Forging RM Reference",f"{qty*gross:,.3f} kg",help="Master gross/input weight reference. In Flow 2 this is not an FSI RM procurement transaction.")
            if st.button("Create Forging Supplier Order",type="primary",width="stretch",disabled=not perms["can_create"] or not supplier_order.strip()):
                try:
                    service.save_transaction("supply_forging_orders",{"customer_order_id":order_id,"rm_dispatch_id":rm_dispatch_id,"inward_lot_id":inward_lot_id,"forging_supplier_id":sid,"supplier_order_no":supplier_order.strip(),"order_date":od.isoformat(),"order_qty_pcs":qty,"required_rm_kg":qty*gross,"expected_date":expected.isoformat(),"heat_number":heat_number.strip() or None,"heat_code":heat_code.strip() or None,"status":"OPEN","remarks":remarks.strip() or None}); service.sync_order_status(order_id); save_success_popup("Forging Order created and linked to the selected Supply Chain flow.",queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))
        else:
            st.info("Select a pending Flow 1 RM Dispatch or Flow 2 Customer Order above.")

    pending_fo=service.pending_forging_orders()
    with stage_section("C","FORGING ORDERS PENDING RECEIPT","Upcoming expected receipt date is first; overdue records are red. Flow 2 may capture supplier Heat here if it was not known at order creation.",key="supply_forging_receipt"):
        data=[]
        for fo in pending_fo:
            order=orders.get(str(fo.get("customer_order_id"))) or {}; ctx=service.order_context(order); data.append({**ctx,"Forging Order":fo.get("supplier_order_no"),"Heat Number":fo.get("heat_number"),"Heat Code":fo.get("heat_code"),"Ordered pcs":fo.get("order_qty_pcs"),"Received pcs":fo.get("received_qty_pcs"),"Balance pcs":fo.get("balance_qty_pcs"),"Expected":fo.get("expected_date"),"Display Status":_due_status(fo.get("status"),fo.get("expected_date")),"_id":str(fo.get("id"))})
        _searchable_grid(pd.DataFrame(data).drop(columns=["_id"],errors="ignore"),title="Forging Orders Pending Receipt",key="supply_forging_pending_receipt",height=380); labels={str(r["id"]):f"{r.get('supplier_order_no')} · Heat {r.get('heat_number') or '-'} · Balance {number(r.get('balance_qty_pcs')):,.0f} pcs" for r in pending_fo}; fo_id=st.selectbox("Select Forging Order",list(labels),format_func=lambda v:labels[v],key="supply_forging_receipt_order") if labels else None
        if fo_id:
            fo=next(r for r in pending_fo if str(r["id"])==fo_id); order=orders.get(str(fo.get("customer_order_id"))) or {}; gross=number(order.get("gross_weight_kg_snapshot")); direct=service.flow_for_order(order)==FLOW_DIRECT_FORGING
            c=st.columns(4,gap="small"); receipt=c[0].text_input("Forging Receipt No."); rd=c[1].date_input("Receipt Date",value=date.today(),format="DD-MM-YYYY"); qty=c[2].number_input("Received Forging Qty pcs",min_value=1.0,max_value=float(max(number(fo.get("balance_qty_pcs")),1)),step=1.0); rej=c[3].number_input("Rejected Qty pcs",min_value=0.0,step=1.0)
            h=st.columns(2,gap="small"); receipt_heat=h[0].text_input("Heat Number",value=str(fo.get("heat_number") or ""),disabled=not direct and bool(fo.get("heat_number")),key=f"forging_receipt_heat_{fo_id}"); receipt_code=h[1].text_input("Heat Code",value=str(fo.get("heat_code") or ""),disabled=not direct and bool(fo.get("heat_code")),key=f"forging_receipt_heat_code_{fo_id}")
            actual=st.number_input("Actual RM Consumed kg (0 = auto)",min_value=0.0,value=0.0,step=1.0); remarks=st.text_input("Forging Receipt Remarks")
            if st.button("Post Forging Receipt",type="primary",width="stretch",disabled=not perms["can_create"] or not receipt.strip()):
                try:
                    if direct and (receipt_heat.strip()!=str(fo.get("heat_number") or "").strip() or receipt_code.strip()!=str(fo.get("heat_code") or "").strip()):
                        service.save_transaction("supply_forging_orders",{"heat_number":receipt_heat.strip() or None,"heat_code":receipt_code.strip() or None},record_id=fo_id); fo=service.repo.get("supply_forging_orders",fo_id) or fo
                    service.save_transaction("supply_forging_receipts",{"customer_order_id":fo.get("customer_order_id"),"forging_order_id":fo_id,"rm_dispatch_id":fo.get("rm_dispatch_id"),"inward_lot_id":fo.get("inward_lot_id"),"forging_supplier_id":fo.get("forging_supplier_id"),"receipt_number":receipt.strip(),"receipt_date":rd.isoformat(),"received_qty_pcs":qty,"rejected_qty_pcs":rej,"actual_rm_consumed_kg":actual if actual>0 else None,"gross_weight_kg_snapshot":gross,"heat_number":fo.get("heat_number"),"heat_code":fo.get("heat_code"),"remarks":remarks.strip() or None}); service.sync_order_status(str(fo.get("customer_order_id"))); service.sync_purchase_order_status(str(fo.get("purchase_order_id") or "")); save_success_popup("Forging Receipt posted with linked genealogy.",queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))

    with stage_section("D","FORGING REGISTER / EXPORT","All forging orders and receipts with global search; Supply Flow is shown for every record.",key="supply_forging_register"):
        order_frame=pd.DataFrame([{**service.order_context(orders.get(str(r.get("customer_order_id"))) or {}),"Record Type":"FORGING ORDER","Reference":r.get("supplier_order_no"),"Date":r.get("order_date"),"Expected":r.get("expected_date"),"Heat Number":r.get("heat_number"),"Heat Code":r.get("heat_code"),"Qty pcs":r.get("order_qty_pcs"),"Status":r.get("status")} for r in service.forging_orders()]); receipt_frame=pd.DataFrame([{**service.order_context(orders.get(str(r.get("customer_order_id"))) or {}),"Record Type":"FORGING RECEIPT","Reference":r.get("receipt_number"),"Date":r.get("receipt_date"),"Expected":None,"Heat Number":r.get("heat_number"),"Heat Code":r.get("heat_code"),"Qty pcs":r.get("received_qty_pcs"),"Status":"RECEIVED"} for r in service.forging_receipts()]); _searchable_grid(pd.concat([order_frame,receipt_frame],ignore_index=True),title="Forging Order and Receipt Register",key="supply_forging_register_grid",height=520)
    _edit_delete_panel(service,table="supply_forging_orders",rows=service.forging_orders(),title="FORGING ORDER EDIT / DELETE",stage="E",key="supply_forging_order_edit",labeler=lambda r:f"{r.get('supplier_order_no')} · Heat {r.get('heat_number') or '-'}",fields=(("supplier_order_no","Supplier Order No.","text"),("order_date","Order Date","date"),("expected_date","Expected Receipt","date"),("order_qty_pcs","Order Qty pcs","number"),("heat_number","Heat Number","text"),("heat_code","Heat Code","text"),("status","Status","select",("OPEN","PART_RECEIVED","CLOSED","CANCELLED")),("remarks","Remarks","text")),perms=perms)
    _edit_delete_panel(service,table="supply_forging_receipts",rows=service.forging_receipts(),title="FORGING RECEIPT EDIT / DELETE",stage="F",key="supply_forging_receipt_edit",labeler=lambda r:f"{r.get('receipt_number')} · Heat {r.get('heat_number') or '-'}",fields=(("receipt_number","Receipt No.","text"),("receipt_date","Receipt Date","date"),("received_qty_pcs","Received pcs","number"),("rejected_qty_pcs","Rejected pcs","number"),("remarks","Remarks","text")),perms=perms)


def render_downstream() -> None:
    page_header("Part Production / Customer Dispatch","Machining and Finished Goods remain controlled production sub-stages; the Supply Chain flow reports them together as Part Production","Supply Chain")
    service=SupplyChainService(); perms=current_permissions("SUPPLY_CHAIN"); orders={str(r["id"]):r for r in service.customer_orders()}
    stages=[("A","MACHINING","MACHINING"),("B","FINISHED GOODS","FINISHED_GOODS"),("C","CUSTOMER DISPATCH / INVOICE / ASN","CUSTOMER_DISPATCH")]
    for letter,title,event_type in stages:
        with stage_section(letter,title,f"Pending source records from the immediately previous Supply Chain stage. Global search + PDF/Excel export are included.",key=f"supply_downstream_{event_type.lower()}"):
            sources=service.pending_sources_for_downstream(event_type); data=[]
            for s in sources:
                order=orders.get(str(s.get("customer_order_id"))) or {}; ctx=service.order_context(order); ref=s.get("receipt_number") if event_type=="MACHINING" else s.get("reference_no"); qty=number(s.get("received_qty_pcs") if event_type=="MACHINING" else s.get("qty_pcs")); data.append({**ctx,"Previous Stage Reference":ref,"Heat Number":s.get("heat_number"),"Heat Code":s.get("heat_code"),"Available Qty pcs":qty,"Status":"PENDING","_id":str(s.get("id"))})
            _searchable_grid(pd.DataFrame(data).drop(columns=["_id"],errors="ignore"),title=f"Pending {title.title()}",key=f"supply_pending_{event_type.lower()}",height=330)
            labels={str(s["id"]):f"{(s.get('receipt_number') if event_type=='MACHINING' else s.get('reference_no'))} · Heat {s.get('heat_number') or '-'} · {number(s.get('received_qty_pcs') if event_type=='MACHINING' else s.get('qty_pcs')):,.0f} pcs" for s in sources}; source_id=st.selectbox("Select Previous Stage Record",list(labels),format_func=lambda v:labels[v],key=f"supply_source_{event_type}") if labels else None
            if not source_id: st.info(f"No record is pending for {title.title()}."); continue
            source=next(s for s in sources if str(s["id"])==source_id); order_id=str(source.get("customer_order_id")); _show_order_context(service,order_id,key=f"down_context_{event_type}",export=True); max_qty=number(source.get("received_qty_pcs") if event_type=="MACHINING" else source.get("qty_pcs")); c=st.columns(4,gap="small"); ref=c[0].text_input("Reference No.",key=f"down_ref_{event_type}"); ed=c[1].date_input("Date",value=date.today(),format="DD-MM-YYYY",key=f"down_date_{event_type}"); qty=c[2].number_input("Quantity pcs",min_value=1.0,max_value=float(max(max_qty,1)),value=float(max(max_qty,1)),step=1.0,key=f"down_qty_{event_type}"); rej=c[3].number_input("Rejected Qty pcs",min_value=0.0,step=1.0,key=f"down_rej_{event_type}")
            invoice=None; invoice_date=None; asn=None
            if event_type=="CUSTOMER_DISPATCH":
                c=st.columns(3,gap="small"); invoice=c[0].text_input("Invoice No.",key="supply_invoice"); invoice_date=c[1].date_input("Invoice Date",value=date.today(),format="DD-MM-YYYY",key="supply_invoice_date"); asn=c[2].text_input("ASN No.",key="supply_asn")
            remarks=st.text_input("Remarks",key=f"down_rem_{event_type}")
            if st.button(f"Post {title.title()}",type="primary",width="stretch",key=f"down_save_{event_type}",disabled=not perms["can_create"] or not ref.strip()):
                payload={"customer_order_id":order_id,"event_type":event_type,"reference_no":ref.strip(),"event_date":ed.isoformat(),"qty_pcs":qty,"rejected_qty_pcs":rej,"inward_lot_id":source.get("inward_lot_id"),"heat_number":source.get("heat_number"),"heat_code":source.get("heat_code"),"invoice_no":invoice.strip() if invoice else None,"invoice_date":invoice_date.isoformat() if invoice_date else None,"asn_no":asn.strip() if asn else None,"remarks":remarks.strip() or None}
                if event_type=="MACHINING": payload["source_forging_receipt_id"]=source_id
                else: payload["source_event_id"]=source_id
                try: service.save_transaction("supply_downstream_events",payload); service.sync_order_status(order_id); save_success_popup(f"{title.title()} linked to previous stage with Heat traceability.",queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))
    with stage_section("D","DOWNSTREAM EVENT REGISTER","All Machining / Finished Goods / Customer Dispatch records are globally searchable and exportable.",key="supply_downstream_register"):
        rows=service.downstream_events(); frame=pd.DataFrame([{**service.order_context(orders.get(str(r.get("customer_order_id"))) or {}),"Stage":str(r.get("event_type") or "").replace("_"," ").title(),"Reference":r.get("reference_no"),"Date":r.get("event_date"),"Heat Number":r.get("heat_number"),"Heat Code":r.get("heat_code"),"Qty pcs":r.get("qty_pcs"),"Rejected pcs":r.get("rejected_qty_pcs"),"Invoice":r.get("invoice_no"),"Invoice Date":r.get("invoice_date"),"ASN":r.get("asn_no"),"Status":"POSTED"} for r in rows]); _searchable_grid(frame,title="Supply Downstream Event Register",key="supply_downstream_register_grid",height=560)
    _edit_delete_panel(service,table="supply_downstream_events",rows=service.downstream_events(),title="DOWNSTREAM ENTRY EDIT / DELETE",stage="E",key="supply_downstream_edit",labeler=lambda r:f"{str(r.get('event_type')).replace('_',' ').title()} · {r.get('reference_no')} · Heat {r.get('heat_number') or '-'}",fields=(("reference_no","Reference No.","text"),("event_date","Date","date"),("qty_pcs","Qty pcs","number"),("rejected_qty_pcs","Rejected pcs","number"),("invoice_no","Invoice No.","text"),("asn_no","ASN No.","text"),("remarks","Remarks","text")),perms=perms)


def render_traceability() -> None:
    page_header("Supply Chain Traceability","Global search across Customer, Part, Material, RMTC, Heat, supplier and every linked stage reference","Supply Chain")
    service=SupplyChainService(); orders=service.customer_orders(); tables=[service.rm_purchase_orders(),service.rm_receipts(),service.rm_dispatches(),service.forging_orders(),service.forging_receipts(),service.downstream_events()]
    linked:dict[str,list[dict]]={str(o["id"]):[] for o in orders}
    for group in tables:
        for row in group: linked.setdefault(str(row.get("customer_order_id") or ""),[]).append(row)
    search=st.text_input("Global Search · All Supply Chain Fields",placeholder="Order, PosNr, customer, part, grade, supplier, RMTC, Heat, GRN, dispatch, invoice, ASN…",key="supply_trace_global")
    matches=[]
    for order in orders:
        ctx=service.order_context(order); blob=" ".join(str(v or "") for v in ctx.values())+" "+" ".join(str(v or "") for r in linked.get(str(order["id"]),[]) for v in r.values())
        if not search or search.casefold() in blob.casefold(): matches.append(order)
    with stage_section("A","GLOBAL ORDER SEARCH RESULTS","Matching orders are shown as colour status cards.",key="supply_trace_search"):
        frame=_order_display_rows(service,matches); _order_cards(frame,key="trace_cards"); _exports(frame.drop(columns=["_id"],errors="ignore"),"Supply Chain Global Search Results","supply_trace_search_results") if not frame.empty else st.info("No matching Supply Chain record found.")
        parts,parties,_=_maps(service); labels={str(r["id"]):service.order_label(r,parts,parties) for r in matches}; selected=st.selectbox("Matched Customer Order",list(labels),format_func=lambda v:labels[v],key="supply_trace_selected") if labels else None
        if selected: order=next(r for r in matches if str(r["id"])==selected); workflow_progress(_order_progress(service,order))
    if selected:
        with stage_section("B","COMPLETE SUPPLY CHAIN HISTORY","Heat and references remain visible from RM receipt through final customer dispatch.",key="supply_trace_history"):
            timeline=pd.DataFrame(service.timeline(selected)); _searchable_grid(timeline,title="Complete Supply Chain History",key=f"supply_trace_history_{selected}",height=560,header={"Customer Reference":(service.order(selected) or {}).get("master_reference_no")})
        with stage_section("C","COMPLETE GENEALOGY DATA","Flattened linked data for PDF / Excel export and audit traceability.",key="supply_trace_genealogy"):
            genealogy=pd.DataFrame(service.genealogy_context(selected)); _searchable_grid(genealogy,title="Complete Supply Chain Genealogy",key=f"supply_trace_genealogy_{selected}",height=620)
        with stage_section("D","FORGING SUPPLIER RAW MATERIAL BALANCE",key="supply_trace_balance"):
            balance=pd.DataFrame(service.supplier_balances(selected)); _searchable_grid(balance,title="Forging Supplier RM Balance",key=f"supply_trace_balance_{selected}",height=300)

def render_order_mis() -> None:
    page_header("Monthly Schedule / Order MIS","Customer Order / Schedule vs Customer Dispatch · monthly, customer and part visibility","Supply Chain")
    service=SupplyChainService(); rows=service.order_mis_rows(); frame=pd.DataFrame(rows)
    if frame.empty:
        st.info("No Customer Order / Monthly Schedule data is available for MIS reporting.")
        return

    with stage_section("A","MIS FILTERS","Filter by month, customer, part, order type, supply flow and status. All report grids remain globally searchable and exportable.",key="supply_mis_filters"):
        months=sorted(v for v in frame["Month"].dropna().astype(str).unique().tolist() if v)
        customers=sorted(v for v in frame["Customer"].dropna().astype(str).unique().tolist() if v)
        parts=sorted(v for v in frame["Part Number"].dropna().astype(str).unique().tolist() if v)
        types=sorted(v for v in frame["Order Type"].dropna().astype(str).unique().tolist() if v)
        flows=sorted(v for v in frame["Supply Flow"].dropna().astype(str).unique().tolist() if v)
        statuses=sorted(v for v in frame["Status"].dropna().astype(str).unique().tolist() if v)
        c=st.columns(3,gap="small")
        selected_months=c[0].multiselect("Month(s)",months,default=months,key="supply_mis_months")
        selected_customers=c[1].multiselect("Customer(s)",customers,key="supply_mis_customers")
        selected_parts=c[2].multiselect("Part Number(s)",parts,key="supply_mis_parts")
        c=st.columns(3,gap="small")
        selected_types=c[0].multiselect("Order Type",types,key="supply_mis_types")
        selected_flows=c[1].multiselect("Supply Flow",flows,key="supply_mis_flows")
        selected_status=c[2].multiselect("Status",statuses,key="supply_mis_status")
        filtered=frame.copy()
        if selected_months: filtered=filtered[filtered["Month"].astype(str).isin(selected_months)]
        if selected_customers: filtered=filtered[filtered["Customer"].astype(str).isin(selected_customers)]
        if selected_parts: filtered=filtered[filtered["Part Number"].astype(str).isin(selected_parts)]
        if selected_types: filtered=filtered[filtered["Order Type"].astype(str).isin(selected_types)]
        if selected_flows: filtered=filtered[filtered["Supply Flow"].astype(str).isin(selected_flows)]
        if selected_status: filtered=filtered[filtered["Status"].astype(str).isin(selected_status)]
        ordered=float(filtered["Order / Schedule Qty pcs"].fillna(0).sum()) if not filtered.empty else 0.0
        dispatched=float(filtered["Dispatched pcs"].fillna(0).sum()) if not filtered.empty else 0.0
        pending=max(ordered-dispatched,0)
        achievement=(dispatched/ordered*100) if ordered else 0.0
        kpi_grid([
            {"label":"Order / Schedule Qty","value":f"{ordered:,.0f} pcs","color":"#0B6FAE","background":"#EFF7FD"},
            {"label":"Customer Dispatch","value":f"{dispatched:,.0f} pcs","color":"#15803D","background":"#F0FDF4"},
            {"label":"Pending Dispatch","value":f"{pending:,.0f} pcs","color":"#B45309","background":"#FFF7ED"},
            {"label":"Dispatch Achievement","value":f"{achievement:,.1f}%","color":"#075985","background":"#F0F9FF"},
        ])

    with stage_section("B","MONTHLY ORDER / DISPATCH SUMMARY","Monthly schedule and purchase-order demand compared with actual dispatch to customers.",key="supply_mis_monthly"):
        summary=pd.DataFrame(service.monthly_mis_summary(filtered.to_dict("records"))) if not filtered.empty else pd.DataFrame()
        _searchable_grid(summary,title="Monthly Order and Dispatch MIS",key="supply_monthly_order_dispatch_mis",height=420,header={"Report":"Monthly Schedule / Order MIS"})

    with stage_section("C","ORDER / SCHEDULE MIS WITH CUSTOMER DISPATCH","One row per Customer Order / monthly schedule with dispatch quantity, pending quantity, latest dispatch, invoice and ASN.",key="supply_mis_detail"):
        _searchable_grid(filtered,title="Customer Order Schedule MIS with Dispatch",key="supply_order_schedule_dispatch_mis",height=620,header={"Report":"Order / Schedule MIS with Customer Dispatch"})

    with stage_section("D","CUSTOMER / PART MONTHLY DISPATCH SUMMARY","Aggregated management view by month, customer and part.",key="supply_mis_customer_part"):
        if filtered.empty:
            st.info("No rows match the selected MIS filters.")
        else:
            grouped=(filtered.groupby(["Month","Customer","Part Number","FSI Part Number","Part Description"],dropna=False,as_index=False)[["Order / Schedule Qty pcs","Dispatched pcs","Pending Dispatch pcs"]].sum())
            grouped["Dispatch Achievement %"]=grouped.apply(lambda r: round(number(r.get("Dispatched pcs"))/number(r.get("Order / Schedule Qty pcs"))*100,1) if number(r.get("Order / Schedule Qty pcs")) else 0.0,axis=1)
            _searchable_grid(grouped,title="Customer Part Monthly Dispatch Summary",key="supply_customer_part_monthly_mis",height=560)

