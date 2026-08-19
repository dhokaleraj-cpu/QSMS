from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from typing import Any, Mapping, Sequence

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.delete_service import password_delete_panel
from core.reporting import controlled_record_pdf_bytes
from core.selection_labels import part_label, party_label
from core.supply_chain_service import (
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
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=sheet_name[:31])
        ws = writer.sheets[sheet_name[:31]]
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
        st.dataframe(_style_supply_dataframe(filtered), hide_index=True, width="stretch", height=min(height, 82 + 36 * max(len(filtered), 1)))
        _exports(filtered, title, key, header=header)
    return filtered


def _order_display_rows(service: SupplyChainService, orders: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    parts, parties, grades = _maps(service)
    rows=[]
    for r in orders:
        part=parts.get(str(r.get("part_id"))) or {}; customer=parties.get(str(r.get("customer_id"))) or {}; grade=grades.get(str(part.get("material_grade_id"))) or {}
        rows.append({
            "Customer Ref":r.get("master_reference_no"), "Order No":r.get("customer_order_no"), "PosNr":r.get("order_position"),
            "Customer":party_label(customer), "Part Number":part.get("part_number"), "Part Description":part.get("part_name"),
            "Material Grade":grade.get("grade_code"), "Order Qty pcs":r.get("order_qty_pcs"), "RM Required kg":r.get("required_rm_kg"),
            "RM Ordered kg":r.get("rm_ordered_kg"), "RM Balance kg":r.get("rm_balance_kg"), "Delivery Date":r.get("customer_delivery_date"),
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
            f'<div class="supply-card-meta">{safe(r.get("Customer") or "")} · Qty {safe(r.get("Order Qty pcs") or r.get("Stage Qty") or "-")} · Due {safe(r.get("Delivery Date") or r.get("Expected") or "-")}</div></div>'
        )
    st.markdown(f'<div class="supply-order-grid" id="{safe(key)}">{"".join(cards)}</div>',unsafe_allow_html=True)


def _order_progress(service: SupplyChainService, order: dict) -> list[dict]:
    totals=service.totals(str(order["id"])); qty=number(order.get("order_qty_pcs")); required=number(order.get("required_rm_kg"))
    def state(value: float, target: float) -> str:
        if target > 0 and value >= target - .0001: return "complete"
        if value > 0: return "current"
        return "pending"
    return [
        {"label":"Order", "state":"complete", "detail":str(order.get("master_reference_no"))},
        {"label":"RM Procurement", "state":state(totals["rm_ordered_kg"],required), "detail":f"{totals['rm_ordered_kg']:,.1f}/{required:,.1f} kg"},
        {"label":"RM Receipt", "state":state(totals["rm_received_kg"],min(totals["rm_ordered_kg"],required) if totals["rm_ordered_kg"] else required), "detail":f"{totals['rm_received_kg']:,.1f} kg"},
        {"label":"RM to Forging", "state":state(totals["rm_dispatched_kg"],min(totals["rm_received_kg"],required) if totals["rm_received_kg"] else required), "detail":f"{totals['rm_dispatched_kg']:,.1f} kg"},
        {"label":"Forging Receipt", "state":state(totals["forging_received_pcs"],qty), "detail":f"{totals['forging_received_pcs']:,.0f}/{qty:,.0f} pcs"},
        {"label":"Machining", "state":state(totals["machined_pcs"],qty), "detail":f"{totals['machined_pcs']:,.0f}/{qty:,.0f} pcs"},
        {"label":"Finished Goods", "state":state(totals["finished_goods_pcs"],qty), "detail":f"{totals['finished_goods_pcs']:,.0f}/{qty:,.0f} pcs"},
        {"label":"Customer Dispatch", "state":state(totals["customer_dispatched_pcs"],qty), "detail":f"{totals['customer_dispatched_pcs']:,.0f}/{qty:,.0f} pcs"},
    ]


def _show_order_context(service: SupplyChainService, order_id: str, *, key: str, export: bool = False) -> dict:
    order=service.order(order_id) or {}; ctx=service.order_context(order); frame=pd.DataFrame([ctx])
    st.dataframe(_style_supply_dataframe(frame),hide_index=True,width="stretch")
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
        c1,c2=st.columns(2,gap="small"); customer_id=c1.selectbox("Customer",list(customer_map),format_func=lambda v:customer_map[v]) if customer_map else None
        filtered_parts=[r for r in parts if not customer_id or str(r.get("customer_id") or "") in {"",str(customer_id)}]; fp_map={str(r["id"]):part_map[str(r["id"])] for r in filtered_parts}; part_id=c2.selectbox("Part Number",list(fp_map),format_func=lambda v:fp_map[v]) if fp_map else None
        raw_rows=service.raw_material_options(str(part_id or "")) if part_id else []; raw_labels={}
        for r in raw_rows:
            supplier=parties.get(str(r.get("supplier_id"))) or {}; gross=number(r.get("gross_weight_kg") or r.get("input_weight_kg") or r.get("forging_weight_kg")); raw_labels[str(r["id"])]=f"{r.get('material_section_name') or 'Raw Material'} · {party_label(supplier)} · Gross {gross:.3f} kg/pc · {r.get('section_size') or '-'}"
        raw_id=st.selectbox("Part Master Raw Material / Forging Source",list(raw_labels),format_func=lambda v:raw_labels[v]) if raw_labels else None
        selected_raw=next((r for r in raw_rows if str(r["id"])==str(raw_id)),{}) if raw_id else {}; gross=number(selected_raw.get("gross_weight_kg") or selected_raw.get("input_weight_kg") or selected_raw.get("forging_weight_kg"))
        if part_id: _show_order_context(service,str(next((r.get("id") for r in service.customer_orders() if False),"")),key="dummy") if False else None
        if not raw_labels: st.warning("Part Master E - Raw Material Details requires an active raw material / forging source and gross/input weight.")
        if order_type=="PURCHASE_ORDER":
            c=st.columns(5,gap="small"); order_no=c[0].text_input("Customer Order No."); position=c[1].text_input("PosNr / Position"); qty=c[2].number_input("Order Qty pcs",min_value=1.0,step=1.0); order_date=c[3].date_input("Order Date",value=date.today(),format="DD-MM-YYYY"); delivery=c[4].date_input("Delivery / Arrival Date",value=date.today(),format="DD-MM-YYYY")
            remarks=st.text_input("Order Remarks")
            st.metric("Calculated RM Requirement",f"{qty*gross:,.3f} kg",help="Order pcs × Part Master gross/input weight")
            if st.button("Create Customer Purchase Order",type="primary",width="stretch",disabled=not perms["can_create"] or not customer_id or not part_id or not raw_id or gross<=0 or not order_no.strip() or not position.strip()):
                try:
                    service.create_customer_order({"order_type":"PURCHASE_ORDER","customer_id":customer_id,"part_id":part_id,"customer_order_no":order_no.strip(),"order_position":position.strip(),"order_date":order_date.isoformat(),"customer_delivery_date":delivery.isoformat(),"order_qty_pcs":qty,"forging_supplier_id":selected_raw.get("supplier_id"),"raw_material_detail_id":raw_id,"gross_weight_kg_snapshot":gross,"status":"OPEN","remarks":remarks.strip() or None})
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
            if st.button("Create / Add Six-Month Schedule",type="primary",width="stretch",disabled=not perms["can_create"] or not customer_id or not part_id or not raw_id or gross<=0):
                try:
                    created=[]
                    for mm,yy,q,d in month_data:
                        if q<=0: continue
                        saved=service.create_customer_order({"order_type":"MONTHLY_SCHEDULE","customer_id":customer_id,"part_id":part_id,"order_position":f"{mm:02d}-{yy}","schedule_month":date(yy,mm,1).isoformat(),"order_date":receipt_date.isoformat(),"customer_delivery_date":d.isoformat(),"order_qty_pcs":q,"forging_supplier_id":selected_raw.get("supplier_id"),"raw_material_detail_id":raw_id,"gross_weight_kg_snapshot":gross,"status":"OPEN","remarks":remarks.strip() or None}); created.append(saved.get("master_reference_no"))
                    if not created: raise ValueError("Enter quantity for at least one of the six months.")
                    save_success_popup(f"{len(created)} monthly schedule record(s) created.",queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))
    with stage_section("B","CUSTOMER ORDER IMPORT · COLUMNS A TO F","Reads rows after the detected header. Item, Order no. and PosNr are duplicate keys; existing changes update only after confirmation.",key="supply_customer_import"):
        import_customer=st.selectbox("Import Customer",list(customer_map),format_func=lambda v:customer_map[v],key="supply_import_customer") if customer_map else None
        uploaded=st.file_uploader("Customer Order / Schedule Excel",type=["xlsx","xlsm","xls"],key="supply_order_import_file")
        if uploaded is not None and import_customer:
            try:
                raw=pd.read_excel(uploaded,header=None,usecols="A:F",dtype=object)
                header_index=next((i for i,row in raw.iterrows() if normalize_match(row.iloc[0])=="item" and normalize_match(row.iloc[2]) in {"orderno","ordernumber"}),None)
                if header_index is None: raise ValueError("Could not find the header row containing Item / Description / Order no. / PosNr / Quantity / Delivery date in columns A-F.")
                data=raw.iloc[header_index+1:,:6].copy(); data.columns=["Item","Description","Order no.","PosNr","Quantity","Delivery date"]; data=data.dropna(how="all")
                preview=service.import_preview(str(import_customer),data.to_dict("records")); visible=pd.DataFrame([{k:v for k,v in r.items() if not k.startswith("_")} for r in preview])
                st.dataframe(_style_supply_dataframe(visible.rename(columns={"Action":"Status"})),hide_index=True,width="stretch",height=min(520,90+34*len(visible))); _exports(visible,"Customer Order Import Preview","supply_customer_import_preview")
                update_count=sum(str(r.get("Action"))=="UPDATE" for r in preview); confirm=st.checkbox(f"Confirm update of {update_count} existing matching Order No. + PosNr record(s)",disabled=update_count==0,key="supply_import_confirm_updates") if update_count else True
                if st.button("Import New / Confirmed Changed Orders",type="primary",width="stretch",disabled=not perms["can_create"] or any(str(r.get("Action"))=="ERROR" for r in preview) or (update_count>0 and not confirm)):
                    result=service.apply_customer_order_import(str(import_customer),preview,confirm_updates=bool(confirm)); save_success_popup(f"Import complete · New {result['created']} · Updated {result['updated']} · Unchanged {result['unchanged']}",queue_for_rerun=True); st.rerun()
            except Exception as exc: st.error(str(exc))
    with stage_section("C","CUSTOMER ORDER REGISTER","Global search covers all displayed fields.",key="supply_customer_order_register"):
        rows=service.customer_orders(); frame=_order_display_rows(service,rows); _searchable_grid(frame.drop(columns=["_id"],errors="ignore"),title="Customer Order Register",key="supply_customer_order_register_grid",height=520); _order_cards(frame,key="customer_register_cards")
    _edit_delete_panel(service,table="supply_customer_orders",rows=service.customer_orders(),title="CUSTOMER ORDER EDIT / DELETE",stage="D",key="supply_customer_order",labeler=lambda r:f"{r.get('master_reference_no')} · Pos {r.get('order_position') or '-'}",fields=(("customer_order_no","Customer Order No.","text"),("order_position","PosNr / Position","text"),("order_date","Order Date","date"),("customer_delivery_date","Delivery Date","date"),("order_qty_pcs","Order Qty pcs","number"),("status","Status","select",("OPEN","IN_PROGRESS","COMPLETED","CANCELLED")),("remarks","Remarks","text")),perms=perms)


def render_rm_procurement() -> None:
    page_header("Raw Material Procurement","Pending Customer Orders first · sorted by upcoming customer delivery date","Supply Chain")
    service=SupplyChainService(); perms=current_permissions("SUPPLY_CHAIN"); supplier_map={str(r["id"]):party_label(r) for r in service.suppliers()}; pending=service.pending_customer_orders_for_rm()
    with stage_section("A","CUSTOMER ORDERS PENDING RM PROCUREMENT","Only Customer Orders still requiring Raw Material are shown; upcoming delivery dates are first.",key="supply_rm_pending_orders"):
        frame=_order_display_rows(service,pending); filtered=_searchable_grid(frame.drop(columns=["_id"],errors="ignore"),title="Pending RM Procurement",key="supply_rm_pending",height=420); _order_cards(filtered,key="rm_pending_cards")
        ids={str(r["id"]):r for r in pending}; labels={rid:f"{r.get('master_reference_no')} · Due {r.get('customer_delivery_date')} · Balance {number(r.get('rm_balance_kg')):,.3f} kg" for rid,r in ids.items()}; selected=st.selectbox("Select Pending Customer Order",list(labels),format_func=lambda v:labels[v],key="supply_rm_pending_select") if labels else None
    with stage_section("B","RAW MATERIAL PURCHASE ORDER","Customer/Part/Material data is inherited from the selected pending Customer Order.",key="supply_rm_procurement_entry"):
        if not selected: st.info("No pending Customer Order requires RM Procurement.")
        else:
            order=ids[selected]; _show_order_context(service,selected,key="rm_proc_context",export=True); totals=service.totals(selected); required=number(order.get("required_rm_kg")); cap=required*1.25; available=max(0,cap-totals["rm_ordered_kg"])
            kpi_grid([{"label":"Required RM kg","value":f"{required:,.3f}"},{"label":"125% Maximum kg","value":f"{cap:,.3f}"},{"label":"Already Ordered kg","value":f"{totals['rm_ordered_kg']:,.3f}"},{"label":"Balance to Order kg","value":f"{available:,.3f}"}])
            c=st.columns(4,gap="small"); supplier_id=c[0].selectbox("Steel Mill / Trader",list(supplier_map),format_func=lambda v:supplier_map[v]) if supplier_map else None; supplier_order=c[1].text_input("Supplier Order No."); order_date=c[2].date_input("Order Date",value=date.today(),format="DD-MM-YYYY"); expected=c[3].date_input("Expected Receipt Date",value=date.today(),format="DD-MM-YYYY")
            qty=st.number_input("Raw Material Order Quantity kg",min_value=0.001,max_value=float(max(available,.001)),value=float(min(max(number(order.get("rm_balance_kg")),.001),max(available,.001))),step=1.0); remarks=st.text_input("RM Purchase Remarks")
            if st.button("Create Raw Material Purchase Order",type="primary",width="stretch",disabled=not perms["can_create"] or not supplier_id or not supplier_order.strip() or available<=0):
                try: service.save_transaction("supply_rm_purchase_orders",{"customer_order_id":selected,"rm_supplier_id":supplier_id,"supplier_order_no":supplier_order.strip(),"order_date":order_date.isoformat(),"ordered_qty_kg":qty,"expected_date":expected.isoformat(),"status":"OPEN","remarks":remarks.strip() or None}); service.sync_order_status(selected); save_success_popup("RM Purchase Order linked to Customer Order.",queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))
    with stage_section("C","RAW MATERIAL ORDER REGISTER","Global search includes Customer Ref, supplier, order, dates, quantity and status.",key="supply_rm_procurement_register"):
        orders={str(r["id"]):r for r in service.customer_orders()}; parts,parties,grades=_maps(service); rows=service.rm_purchase_orders(); data=[]
        for r in rows:
            order=orders.get(str(r.get("customer_order_id"))) or {}; ctx=service.order_context(order); data.append({**ctx,"RM Supplier":supplier_map.get(str(r.get("rm_supplier_id")),str(r.get("rm_supplier_id"))),"Supplier Order No":r.get("supplier_order_no"),"RM Order Date":r.get("order_date"),"RM Qty kg":r.get("ordered_qty_kg"),"Expected":r.get("expected_date"),"Display Status":_due_status(r.get("status"),r.get("expected_date"))})
        _searchable_grid(pd.DataFrame(data),title="Raw Material Order Register",key="supply_rm_order_register",height=520)
    _edit_delete_panel(service,table="supply_rm_purchase_orders",rows=service.rm_purchase_orders(),title="RAW MATERIAL ORDER EDIT / DELETE",stage="D",key="supply_rm_po",labeler=lambda r:f"{r.get('supplier_order_no')} · {number(r.get('ordered_qty_kg')):,.3f} kg",fields=(("rm_supplier_id","RM Supplier","lookup",supplier_map),("supplier_order_no","Supplier Order No.","text"),("order_date","Order Date","date"),("expected_date","Expected Receipt","date"),("ordered_qty_kg","Ordered Qty kg","number"),("status","Status","select",("OPEN","PART_RECEIVED","CLOSED","CANCELLED")),("remarks","Remarks","text")),perms=perms)


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
                selected_inward=next(r for r in eligible if str(r["id"])==inward_id); detail=pd.DataFrame([{k:selected_inward.get(k) for k in ("inward_number","inward_date","grn_number","supplier_name","part_number","material_grade","heat_number","heat_code","rmtc_number","rmtc_date","rmtc_steel_quantity_kg","steel_quantity_kg","quality_disposition","status") if k in selected_inward}]); st.dataframe(_style_supply_dataframe(detail.rename(columns={"rmtc_date":"RMTC Date","rmtc_steel_quantity_kg":"RMTC Qty kg"})),hide_index=True,width="stretch")
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
    page_header("Forging Order & Receipt","Sequentially linked to RM Dispatch; Heat / Inward genealogy is carried forward","Supply Chain")
    service=SupplyChainService(); perms=current_permissions("SUPPLY_CHAIN"); parties={str(r["id"]):r for r in service.parties()}; orders={str(r["id"]):r for r in service.customer_orders()}; pending_dispatch=service.pending_rm_dispatches_for_forging_order()
    with stage_section("A","RM DISPATCHES PENDING FORGING ORDER","Only unlinked RM dispatch records are shown.",key="supply_forging_pending_dispatch"):
        data=[]
        for r in pending_dispatch:
            ctx=service.order_context(orders.get(str(r.get("customer_order_id"))) or {}); data.append({**ctx,"RM Dispatch":r.get("dispatch_number"),"Dispatch Date":r.get("dispatch_date"),"Heat Number":r.get("heat_number"),"Heat Code":r.get("heat_code"),"RM Qty kg":r.get("qty_kg"),"Status":"PENDING","_id":str(r.get("id"))})
        _searchable_grid(pd.DataFrame(data).drop(columns=["_id"],errors="ignore"),title="RM Dispatch Pending Forging Order",key="supply_forging_pending_rm",height=360); labels={str(r["id"]):f"{r.get('dispatch_number')} · Heat {r.get('heat_number')} · {number(r.get('qty_kg')):,.3f} kg" for r in pending_dispatch}; dispatch_id=st.selectbox("Select RM Dispatch",list(labels),format_func=lambda v:labels[v],key="supply_forging_dispatch") if labels else None
    with stage_section("B","FORGING SUPPLIER ORDER","Part, supplier, Heat and raw material context are inherited from RM Dispatch.",key="supply_forging_order"):
        if dispatch_id:
            source=next(r for r in pending_dispatch if str(r["id"])==dispatch_id); order_id=str(source.get("customer_order_id")); order=_show_order_context(service,order_id,key="forging_order_context",export=True); sid=str(order.get("forging_supplier_id")); gross=number(order.get("gross_weight_kg_snapshot")); c=st.columns(4,gap="small"); c[0].text_input("Forging Supplier",value=party_label(parties.get(sid) or {}),disabled=True); supplier_order=c[1].text_input("Forging Supplier Order No."); od=c[2].date_input("Order Date",value=date.today(),format="DD-MM-YYYY"); expected=c[3].date_input("Expected Forging Receipt",value=date.today(),format="DD-MM-YYYY"); qty=st.number_input("Forging Order Qty pcs",min_value=1.0,value=float(max(number(order.get("order_qty_pcs")),1)),step=1.0); st.metric("RM Requirement",f"{qty*gross:,.3f} kg")
            if st.button("Create Forging Supplier Order",type="primary",width="stretch",disabled=not perms["can_create"] or not supplier_order.strip()):
                try: service.save_transaction("supply_forging_orders",{"customer_order_id":order_id,"rm_dispatch_id":dispatch_id,"inward_lot_id":source.get("inward_lot_id"),"forging_supplier_id":sid,"supplier_order_no":supplier_order.strip(),"order_date":od.isoformat(),"order_qty_pcs":qty,"required_rm_kg":qty*gross,"expected_date":expected.isoformat(),"heat_number":source.get("heat_number"),"heat_code":source.get("heat_code"),"status":"OPEN"}); service.sync_order_status(order_id); save_success_popup("Forging Order linked to RM Dispatch and Heat.",queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))
        else: st.info("No RM Dispatch is waiting for a Forging Order.")
    pending_fo=service.pending_forging_orders()
    with stage_section("C","FORGING ORDERS PENDING RECEIPT","Upcoming expected receipt date is first; overdue records are red.",key="supply_forging_receipt"):
        data=[]
        for fo in pending_fo:
            ctx=service.order_context(orders.get(str(fo.get("customer_order_id"))) or {}); data.append({**ctx,"Forging Order":fo.get("supplier_order_no"),"Heat Number":fo.get("heat_number"),"Ordered pcs":fo.get("order_qty_pcs"),"Received pcs":fo.get("received_qty_pcs"),"Balance pcs":fo.get("balance_qty_pcs"),"Expected":fo.get("expected_date"),"Display Status":_due_status(fo.get("status"),fo.get("expected_date")),"_id":str(fo.get("id"))})
        _searchable_grid(pd.DataFrame(data).drop(columns=["_id"],errors="ignore"),title="Forging Orders Pending Receipt",key="supply_forging_pending_receipt",height=380); labels={str(r["id"]):f"{r.get('supplier_order_no')} · Heat {r.get('heat_number') or '-'} · Balance {number(r.get('balance_qty_pcs')):,.0f} pcs" for r in pending_fo}; fo_id=st.selectbox("Select Forging Order",list(labels),format_func=lambda v:labels[v],key="supply_forging_receipt_order") if labels else None
        if fo_id:
            fo=next(r for r in pending_fo if str(r["id"])==fo_id); order=orders.get(str(fo.get("customer_order_id"))) or {}; gross=number(order.get("gross_weight_kg_snapshot")); c=st.columns(4,gap="small"); receipt=c[0].text_input("Forging Receipt No."); rd=c[1].date_input("Receipt Date",value=date.today(),format="DD-MM-YYYY"); qty=c[2].number_input("Received Forging Qty pcs",min_value=1.0,max_value=float(max(number(fo.get("balance_qty_pcs")),1)),step=1.0); rej=c[3].number_input("Rejected Qty pcs",min_value=0.0,step=1.0); actual=st.number_input("Actual RM Consumed kg (0 = auto)",min_value=0.0,value=0.0,step=1.0); remarks=st.text_input("Forging Receipt Remarks")
            if st.button("Post Forging Receipt",type="primary",width="stretch",disabled=not perms["can_create"] or not receipt.strip()):
                try: service.save_transaction("supply_forging_receipts",{"customer_order_id":fo.get("customer_order_id"),"forging_order_id":fo_id,"rm_dispatch_id":fo.get("rm_dispatch_id"),"inward_lot_id":fo.get("inward_lot_id"),"forging_supplier_id":fo.get("forging_supplier_id"),"receipt_number":receipt.strip(),"receipt_date":rd.isoformat(),"received_qty_pcs":qty,"rejected_qty_pcs":rej,"actual_rm_consumed_kg":actual if actual>0 else None,"gross_weight_kg_snapshot":gross,"heat_number":fo.get("heat_number"),"heat_code":fo.get("heat_code"),"remarks":remarks.strip() or None}); service.sync_order_status(str(fo.get("customer_order_id"))); save_success_popup("Forging Receipt posted with Heat genealogy.",queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))
    with stage_section("D","FORGING REGISTER / EXPORT","All forging orders and receipts with global search.",key="supply_forging_register"):
        order_frame=pd.DataFrame([{**service.order_context(orders.get(str(r.get("customer_order_id"))) or {}),"Record Type":"FORGING ORDER","Reference":r.get("supplier_order_no"),"Date":r.get("order_date"),"Expected":r.get("expected_date"),"Heat Number":r.get("heat_number"),"Heat Code":r.get("heat_code"),"Qty pcs":r.get("order_qty_pcs"),"Status":r.get("status")} for r in service.forging_orders()]); receipt_frame=pd.DataFrame([{**service.order_context(orders.get(str(r.get("customer_order_id"))) or {}),"Record Type":"FORGING RECEIPT","Reference":r.get("receipt_number"),"Date":r.get("receipt_date"),"Expected":None,"Heat Number":r.get("heat_number"),"Heat Code":r.get("heat_code"),"Qty pcs":r.get("received_qty_pcs"),"Status":"RECEIVED"} for r in service.forging_receipts()]); _searchable_grid(pd.concat([order_frame,receipt_frame],ignore_index=True),title="Forging Order and Receipt Register",key="supply_forging_register_grid",height=520)
    _edit_delete_panel(service,table="supply_forging_orders",rows=service.forging_orders(),title="FORGING ORDER EDIT / DELETE",stage="E",key="supply_forging_order_edit",labeler=lambda r:f"{r.get('supplier_order_no')} · Heat {r.get('heat_number') or '-'}",fields=(("supplier_order_no","Supplier Order No.","text"),("order_date","Order Date","date"),("expected_date","Expected Receipt","date"),("order_qty_pcs","Order Qty pcs","number"),("status","Status","select",("OPEN","PART_RECEIVED","CLOSED","CANCELLED")),("remarks","Remarks","text")),perms=perms)
    _edit_delete_panel(service,table="supply_forging_receipts",rows=service.forging_receipts(),title="FORGING RECEIPT EDIT / DELETE",stage="F",key="supply_forging_receipt_edit",labeler=lambda r:f"{r.get('receipt_number')} · Heat {r.get('heat_number') or '-'}",fields=(("receipt_number","Receipt No.","text"),("receipt_date","Receipt Date","date"),("received_qty_pcs","Received pcs","number"),("rejected_qty_pcs","Rejected pcs","number"),("remarks","Remarks","text")),perms=perms)


def render_downstream() -> None:
    page_header("Machining / Finished Goods / Customer Dispatch","Each stage selects only pending output from the previous stage; Heat follows automatically","Supply Chain")
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
