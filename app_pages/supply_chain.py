from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.selection_labels import part_label, party_label
from core.supply_chain_service import MONTHS, SupplyChainService, monthly_reference, number
from core.ui import kpi_grid, page_header, save_success_popup, stage_section, style_status_dataframe, workflow_progress


def _maps(service: SupplyChainService):
    parts = {str(r["id"]): r for r in service.parts()}
    parties = {str(r["id"]): r for r in service.parties()}
    return parts, parties


def _order_selector(service: SupplyChainService, key: str) -> tuple[str | None, dict | None]:
    rows = [r for r in service.customer_orders() if str(r.get("status")) != "CANCELLED"]
    if not rows:
        st.info("Create a Customer Order / Schedule first.")
        return None, None
    parts, parties = _maps(service)
    labels = {str(r["id"]): service.order_label(r, parts, parties) for r in rows}
    selected = st.selectbox("Customer Order Master Reference", list(labels), format_func=lambda v: labels[v], key=key)
    return selected, next(r for r in rows if str(r["id"]) == selected)


def _order_progress(service: SupplyChainService, order: dict) -> list[dict]:
    totals = service.totals(str(order["id"])); qty = number(order.get("order_qty_pcs"))
    return [
        {"label":"Order", "status":"COMPLETED", "detail":str(order.get("master_reference_no"))},
        {"label":"RM Procurement", "status":"COMPLETED" if totals["rm_ordered_kg"] > 0 else "PENDING", "detail":f"{totals['rm_ordered_kg']:,.1f} kg"},
        {"label":"RM Receipt", "status":"COMPLETED" if totals["rm_received_kg"] > 0 else "PENDING", "detail":f"{totals['rm_received_kg']:,.1f} kg"},
        {"label":"RM to Forging", "status":"COMPLETED" if totals["rm_dispatched_kg"] > 0 else "PENDING", "detail":f"{totals['rm_dispatched_kg']:,.1f} kg"},
        {"label":"Forging Receipt", "status":"COMPLETED" if totals["forging_received_pcs"] > 0 else "PENDING", "detail":f"{totals['forging_received_pcs']:,.0f} pcs"},
        {"label":"Machining", "status":"COMPLETED" if totals["machined_pcs"] > 0 else "PENDING", "detail":f"{totals['machined_pcs']:,.0f} pcs"},
        {"label":"Finished Goods", "status":"COMPLETED" if totals["finished_goods_pcs"] > 0 else "PENDING", "detail":f"{totals['finished_goods_pcs']:,.0f} pcs"},
        {"label":"Customer Dispatch", "status":"COMPLETED" if qty > 0 and totals["customer_dispatched_pcs"] >= qty else ("IN_PROGRESS" if totals["customer_dispatched_pcs"] > 0 else "PENDING"), "detail":f"{totals['customer_dispatched_pcs']:,.0f}/{qty:,.0f} pcs"},
    ]


def render_home() -> None:
    page_header("Supply Chain", "Customer Order to final customer dispatch", "Supply Chain")
    service = SupplyChainService(); orders = service.customer_orders()
    active = [r for r in orders if str(r.get("status")) not in {"COMPLETED","CANCELLED"}]
    overdue = [r for r in active if r.get("customer_delivery_date") and str(r.get("customer_delivery_date"))[:10] < date.today().isoformat()]
    dispatched = sum(service.totals(str(r["id"]))["customer_dispatched_pcs"] for r in orders)
    kpi_grid([
        {"label":"Open Customer Orders", "value":len(active), "foot":"PO and monthly schedules", "color":"#0B6FAE", "background":"#EFF7FD"},
        {"label":"Overdue Orders", "value":len(overdue), "foot":"Customer delivery date exceeded", "color":"#B91C1C", "background":"#FEF2F2"},
        {"label":"Orders Completed", "value":sum(str(r.get("status"))=="COMPLETED" for r in orders), "foot":"Closed supply-chain references", "color":"#15803D", "background":"#F0FDF4"},
        {"label":"Customer Dispatch pcs", "value":f"{dispatched:,.0f}", "foot":"All linked customer references", "color":"#075985", "background":"#F0F9FF"},
    ])
    with stage_section("A", "OPEN ORDER STATUS", "Select a Master Reference to view the entire customer-order supply-chain stage status.", key="supply_home_status"):
        selected, order = _order_selector(service, "supply_home_order")
        if selected and order:
            workflow_progress(_order_progress(service, order))
            st.dataframe(pd.DataFrame(service.supplier_balances(selected)), hide_index=True, width="stretch")


def render_customer_orders() -> None:
    page_header("Customer Orders / Schedules", "Master reference for the complete supply chain", "Supply Chain")
    service = SupplyChainService(); perms = current_permissions("SUPPLY_CHAIN")
    parts = service.parts(); customers = service.customers(); parties = {str(r["id"]):r for r in service.parties()}
    part_map = {str(r["id"]): part_label(r, customer_name=party_label(parties.get(str(r.get("customer_id"))) or {})) for r in parts}
    customer_map = {str(r["id"]): party_label(r) for r in customers}
    with stage_section("A", "CUSTOMER ORDER / SCHEDULE ENTRY", "Purchase Orders retain the Customer Order Number. Monthly schedules generate Part_MM_YYYY automatically and cannot repeat for the same month.", key="supply_customer_order_entry"):
        order_type = st.radio("Order Source", ["PURCHASE_ORDER","MONTHLY_SCHEDULE"], horizontal=True, format_func=lambda v: "Customer Purchase Order" if v=="PURCHASE_ORDER" else "Monthly Schedule")
        c1,c2,c3 = st.columns(3,gap="small")
        customer_id = c1.selectbox("Customer", list(customer_map), format_func=lambda v: customer_map[v]) if customer_map else None
        filtered_parts = [r for r in parts if not customer_id or str(r.get("customer_id") or "") in {"",customer_id}]
        fp_map = {str(r["id"]):part_map[str(r["id"])] for r in filtered_parts}
        part_id = c2.selectbox("Part Number", list(fp_map), format_func=lambda v: fp_map[v]) if fp_map else None
        order_qty = c3.number_input("Customer Order Qty (pcs)", min_value=1.0, step=1.0)
        order_no = ""; position = ""; schedule_month = None
        if order_type == "PURCHASE_ORDER":
            c1,c2,c3,c4 = st.columns(4,gap="small")
            order_no = c1.text_input("Customer Order No.")
            position = c2.text_input("Order Position")
            order_date = c3.date_input("Order Date", value=date.today(), format="DD-MM-YYYY")
            delivery_date = c4.date_input("Customer Delivery / Arrival Date", value=date.today(), format="DD-MM-YYYY")
            master_ref = order_no.strip()
        else:
            c1,c2,c3,c4 = st.columns(4,gap="small")
            month = c1.selectbox("Schedule Month", list(MONTHS), format_func=lambda v: MONTHS[v], index=date.today().month-1)
            year = c2.selectbox("Schedule Year", list(range(date.today().year-1,date.today().year+6)), index=1)
            order_date = c3.date_input("Schedule Receipt Date", value=date.today(), format="DD-MM-YYYY")
            delivery_date = c4.date_input("Customer Delivery / Arrival Date", value=date.today(), format="DD-MM-YYYY")
            schedule_month = date(int(year),int(month),1)
            master_ref = monthly_reference(str((next((r for r in parts if str(r["id"])==str(part_id)),{}) or {}).get("part_number") or "PART"), month, year) if part_id else ""
            position = f"{month:02d}-{year}"
            st.info(f"Auto Master Reference: **{master_ref or 'Select Part'}**")
        raw_rows = service.raw_material_options(str(part_id or "")) if part_id else []
        raw_labels = {}
        for r in raw_rows:
            supplier = parties.get(str(r.get("supplier_id"))) or {}
            gross = number(r.get("gross_weight_kg") or r.get("input_weight_kg") or r.get("forging_weight_kg"))
            raw_labels[str(r["id"])] = f"{r.get('material_section_name') or 'Primary Raw Material'} · {party_label(supplier)} · Gross {gross:.3f} kg/pc · {r.get('section_size') or '-'}"
        if not raw_labels:
            st.warning("Part Master E - Raw Material Details must contain at least one active Forging Supplier / Gross Weight row before this order can be created.")
            raw_id = None
        else:
            raw_id = st.selectbox("Forging Supplier / Raw Material Section / Gross Weight", list(raw_labels), format_func=lambda v:raw_labels[v])
        selected_raw = next((r for r in raw_rows if str(r["id"])==str(raw_id)),{}) if raw_id else {}
        gross = number(selected_raw.get("gross_weight_kg") or selected_raw.get("input_weight_kg") or selected_raw.get("forging_weight_kg"))
        st.metric("Calculated Raw Material Requirement", f"{order_qty*gross:,.3f} kg", help="Customer order pcs × Forging Supplier Gross Weight")
        remarks = st.text_input("Order Remarks")
        if st.button("Create Customer Order Master Reference", type="primary", width="stretch", disabled=not perms["can_create"] or not customer_id or not part_id or not raw_id or gross<=0):
            try:
                service.create_customer_order({"order_type":order_type,"customer_id":customer_id,"part_id":part_id,"customer_order_no":order_no.strip() or None,"order_position":position.strip() or None,"schedule_month":schedule_month.isoformat() if schedule_month else None,"order_date":order_date.isoformat(),"customer_delivery_date":delivery_date.isoformat(),"order_qty_pcs":order_qty,"forging_supplier_id":selected_raw.get("supplier_id"),"raw_material_detail_id":raw_id,"gross_weight_kg_snapshot":gross,"status":"OPEN","remarks":remarks.strip() or None})
                save_success_popup(f"Customer Order {master_ref} created and locked as the Supply Chain Master Reference.", queue_for_rerun=True); st.rerun()
            except Exception as exc: st.error(str(exc))
    if order_type == "MONTHLY_SCHEDULE" and part_id and raw_id:
        with stage_section("B", "MULTI-MONTH SCHEDULE ENTRY", "Enter up to six consecutive customer schedule months in one controlled batch. Existing Customer + Part + Month combinations are rejected.", key="supply_monthly_schedule_batch"):
            month_count = st.number_input("Months in Schedule", min_value=1, max_value=6, value=6, step=1)
            batch_rows=[]
            for offset in range(int(month_count)):
                total_month=(int(year)*12+(int(month)-1))+offset; yy=total_month//12; mm=total_month%12+1
                ref=monthly_reference(str((next((r for r in parts if str(r["id"])==str(part_id)),{}) or {}).get("part_number") or "PART"),mm,yy)
                batch_rows.append({"Master Reference":ref,"Month":MONTHS[mm],"Year":yy,"Order Qty pcs":float(order_qty),"Customer Delivery Date":date(yy,mm,1)})
            schedule_edit=st.data_editor(pd.DataFrame(batch_rows),hide_index=True,width="stretch",disabled=["Master Reference","Month","Year"],column_config={"Order Qty pcs":st.column_config.NumberColumn(min_value=1.0,required=True),"Customer Delivery Date":st.column_config.DateColumn(format="DD-MM-YYYY",required=True)},key=f"monthly_schedule_batch_{part_id}_{month}_{year}")
            if st.button("Create Multi-Month Customer Schedule",type="primary",width="stretch",disabled=not perms["can_create"]):
                try:
                    created=[]
                    for row in schedule_edit.to_dict("records"):
                        month_name=str(row.get("Month") or "");mm=next((k for k,v in MONTHS.items() if v==month_name),None);yy=int(row.get("Year"));qty=float(row.get("Order Qty pcs") or 0);delivery=row.get("Customer Delivery Date")
                        if not mm or qty<=0:continue
                        saved=service.create_customer_order({"order_type":"MONTHLY_SCHEDULE","customer_id":customer_id,"part_id":part_id,"order_position":f"{mm:02d}-{yy}","schedule_month":date(yy,mm,1).isoformat(),"order_date":order_date.isoformat(),"customer_delivery_date":delivery.isoformat() if isinstance(delivery,date) else str(delivery)[:10],"order_qty_pcs":qty,"forging_supplier_id":selected_raw.get("supplier_id"),"raw_material_detail_id":raw_id,"gross_weight_kg_snapshot":gross,"status":"OPEN","remarks":remarks.strip() or None});created.append(saved.get("master_reference_no"))
                    save_success_popup(f"{len(created)} monthly schedule order(s) created: {', '.join(str(v) for v in created)}",queue_for_rerun=True);st.rerun()
                except Exception as exc:st.error(str(exc))
    with stage_section("C", "CUSTOMER ORDER REGISTER", key="supply_customer_order_register"):
        rows = service.customer_orders()
        frame = pd.DataFrame([{"Master Reference":r.get("master_reference_no"),"Type":str(r.get("order_type") or "").replace("_"," ").title(),"Customer":customer_map.get(str(r.get("customer_id")),party_label(parties.get(str(r.get("customer_id"))) or {})),"Part":(next((p for p in parts if str(p["id"])==str(r.get("part_id"))),{}) or {}).get("part_number"),"Position":r.get("order_position"),"Order Qty pcs":r.get("order_qty_pcs"),"Gross kg/pc":r.get("gross_weight_kg_snapshot"),"RM Required kg":r.get("required_rm_kg"),"Delivery Date":r.get("customer_delivery_date"),"Status":r.get("status")} for r in rows])
        st.dataframe(style_status_dataframe(frame),hide_index=True,width="stretch",height=min(520,80+35*len(frame)))


def render_rm_procurement() -> None:
    page_header("Raw Material Procurement", "Procurement capped at 125% of the customer-order requirement", "Supply Chain")
    service=SupplyChainService(); perms=current_permissions("SUPPLY_CHAIN"); suppliers=service.suppliers(); supplier_map={str(r["id"]):party_label(r) for r in suppliers}
    with stage_section("A","RAW MATERIAL PURCHASE ORDER", key="supply_rm_procurement_entry"):
        order_id,order=_order_selector(service,"supply_rm_po_order")
        if not order_id:return
        totals=service.totals(order_id); required=number(order.get("required_rm_kg")); cap=required*1.25; available=max(0,cap-totals["rm_ordered_kg"])
        kpi_grid([{"label":"Required RM kg","value":f"{required:,.3f}","foot":"Customer order × gross weight"},{"label":"125% Maximum kg","value":f"{cap:,.3f}","foot":"Hard procurement ceiling"},{"label":"Already Ordered kg","value":f"{totals['rm_ordered_kg']:,.3f}","foot":"Non-cancelled RM orders"},{"label":"Balance to Order kg","value":f"{available:,.3f}","foot":"Remaining permitted quantity"}])
        c1,c2,c3,c4=st.columns(4,gap="small")
        supplier_id=c1.selectbox("Steel Mill / Trader",list(supplier_map),format_func=lambda v:supplier_map[v]) if supplier_map else None
        supplier_order=c2.text_input("Supplier Order No.")
        order_date=c3.date_input("Order Date",value=date.today(),format="DD-MM-YYYY")
        expected=c4.date_input("Expected Receipt Date",value=date.today(),format="DD-MM-YYYY")
        qty=st.number_input("Raw Material Order Quantity (kg)",min_value=0.001,max_value=float(max(available,0.001)),value=float(min(max(available,0.001),max(required,0.001))),step=1.0)
        remarks=st.text_input("RM Purchase Remarks")
        if st.button("Create Raw Material Purchase Order",type="primary",width="stretch",disabled=not perms["can_create"] or not supplier_id or not supplier_order.strip() or available<=0):
            try:
                service.repo.insert("supply_rm_purchase_orders",{"customer_order_id":order_id,"rm_supplier_id":supplier_id,"supplier_order_no":supplier_order.strip(),"order_date":order_date.isoformat(),"ordered_qty_kg":qty,"expected_date":expected.isoformat(),"status":"OPEN","remarks":remarks.strip() or None}); service.sync_order_status(order_id); save_success_popup("Raw Material Purchase Order linked to Customer Order.",queue_for_rerun=True); st.rerun()
            except Exception as exc:st.error(str(exc))
    with stage_section("B","RAW MATERIAL ORDER REGISTER",key="supply_rm_procurement_register"):
        rows=service.repo.select("supply_rm_purchase_orders",order_by="created_at",desc=True,limit=10000); orders={str(r["id"]):r for r in service.customer_orders()}
        st.dataframe(style_status_dataframe(pd.DataFrame([{"Customer Ref":(orders.get(str(r.get("customer_order_id"))) or {}).get("master_reference_no"),"Supplier":supplier_map.get(str(r.get("rm_supplier_id")),str(r.get("rm_supplier_id"))),"Supplier Order No":r.get("supplier_order_no"),"Order Date":r.get("order_date"),"Qty kg":r.get("ordered_qty_kg"),"Expected":r.get("expected_date"),"Status":r.get("status")} for r in rows])),hide_index=True,width="stretch")


def render_rm_receipt() -> None:
    page_header("Raw Material Receipt", "Receive steel against the same customer-order reference", "Supply Chain")
    service=SupplyChainService();perms=current_permissions("SUPPLY_CHAIN")
    with stage_section("A","RAW MATERIAL RECEIPT ENTRY",key="supply_rm_receipt_entry"):
        order_id,order=_order_selector(service,"supply_rm_receipt_order")
        if not order_id:return
        pos=[r for r in service.repo.select("supply_rm_purchase_orders",eq={"customer_order_id":order_id},limit=1000) if r.get("status")!="CANCELLED"]
        po_map={str(r["id"]):f"{r.get('supplier_order_no')} · {number(r.get('ordered_qty_kg')):,.3f} kg" for r in pos}
        if not po_map:st.warning("Create a Raw Material Purchase Order first.");return
        c1,c2,c3,c4=st.columns(4,gap="small")
        po_id=c1.selectbox("RM Purchase Order",list(po_map),format_func=lambda v:po_map[v]);receipt=c2.text_input("RM Receipt / GRN No.");receipt_date=c3.date_input("Receipt Date",value=date.today(),format="DD-MM-YYYY");heat=c4.text_input("Heat Number")
        qty=st.number_input("Received Quantity (kg)",min_value=0.001,step=1.0);challan=st.text_input("Supplier Challan No.");remarks=st.text_input("Receipt Remarks")
        if st.button("Post Raw Material Receipt",type="primary",width="stretch",disabled=not perms["can_create"] or not receipt.strip()):
            try:service.repo.insert("supply_rm_receipts",{"customer_order_id":order_id,"rm_purchase_order_id":po_id,"receipt_number":receipt.strip(),"receipt_date":receipt_date.isoformat(),"heat_number":heat.strip() or None,"received_qty_kg":qty,"supplier_challan":challan.strip() or None,"remarks":remarks.strip() or None});service.sync_order_status(order_id);save_success_popup("Raw Material Receipt posted against Customer Order.",queue_for_rerun=True);st.rerun()
            except Exception as exc:st.error(str(exc))
    with stage_section("B","RAW MATERIAL RECEIPT REGISTER",key="supply_rm_receipt_register"):
        orders={str(r["id"]):r for r in service.customer_orders()};rows=service.repo.select("supply_rm_receipts",order_by="created_at",desc=True,limit=10000)
        st.dataframe(pd.DataFrame([{"Customer Ref":(orders.get(str(r.get("customer_order_id"))) or {}).get("master_reference_no"),"Receipt":r.get("receipt_number"),"Date":r.get("receipt_date"),"Heat":r.get("heat_number"),"Qty kg":r.get("received_qty_kg"),"Challan":r.get("supplier_challan")} for r in rows]),hide_index=True,width="stretch")


def render_rm_dispatch() -> None:
    page_header("Raw Material Dispatch to Forging", "Track steel physically available with each forging supplier", "Supply Chain")
    service=SupplyChainService();perms=current_permissions("SUPPLY_CHAIN");parties={str(r["id"]):r for r in service.parties()}
    with stage_section("A","RM DISPATCH TO FORGING SUPPLIER",key="supply_rm_dispatch_entry"):
        order_id,order=_order_selector(service,"supply_rm_dispatch_order")
        if not order_id:return
        totals=service.totals(order_id);available=max(0,totals["rm_received_kg"]-totals["rm_dispatched_kg"]);supplier_id=str(order.get("forging_supplier_id"));st.info(f"Forging Supplier: **{party_label(parties.get(supplier_id) or {})}** · RM available to dispatch: **{available:,.3f} kg**")
        c1,c2,c3,c4=st.columns(4,gap="small");dispatch=c1.text_input("RM Dispatch No.");d=c2.date_input("Dispatch Date",value=date.today(),format="DD-MM-YYYY");heat=c3.text_input("Heat Number");qty=c4.number_input("Dispatch Qty kg",min_value=0.001,max_value=float(max(available,0.001)),step=1.0)
        c1,c2=st.columns(2,gap="small");challan=c1.text_input("Challan No.");vehicle=c2.text_input("Vehicle No.");remarks=st.text_input("Dispatch Remarks")
        if st.button("Post RM Dispatch to Forging Supplier",type="primary",width="stretch",disabled=not perms["can_create"] or not dispatch.strip() or available<=0):
            try:service.repo.insert("supply_rm_dispatches",{"customer_order_id":order_id,"forging_supplier_id":supplier_id,"dispatch_number":dispatch.strip(),"dispatch_date":d.isoformat(),"heat_number":heat.strip() or None,"qty_kg":qty,"challan_number":challan.strip() or None,"vehicle_number":vehicle.strip() or None,"remarks":remarks.strip() or None});service.sync_order_status(order_id);save_success_popup("Raw Material dispatched and linked to Customer Order.",queue_for_rerun=True);st.rerun()
            except Exception as exc:st.error(str(exc))
    with stage_section("B","FORGING SUPPLIER RAW MATERIAL BALANCE",key="supply_supplier_rm_balance"):
        order_id,order=_order_selector(service,"supply_balance_order")
        if order_id:st.dataframe(style_status_dataframe(pd.DataFrame(service.supplier_balances(order_id))),hide_index=True,width="stretch")


def render_forging() -> None:
    page_header("Forging Order & Receipt", "Supplier order and forging receipt linked to Customer Order", "Supply Chain")
    service=SupplyChainService();perms=current_permissions("SUPPLY_CHAIN");parties={str(r["id"]):r for r in service.parties()}
    with stage_section("A","FORGING SUPPLIER ORDER",key="supply_forging_order"):
        order_id,order=_order_selector(service,"supply_forg_order_ref")
        if not order_id:return
        sid=str(order.get("forging_supplier_id"));gross=number(order.get("gross_weight_kg_snapshot"));c1,c2,c3,c4=st.columns(4,gap="small");c1.text_input("Forging Supplier",value=party_label(parties.get(sid) or {}),disabled=True);supplier_order=c2.text_input("Forging Supplier Order No.");od=c3.date_input("Order Date",value=date.today(),format="DD-MM-YYYY");expected=c4.date_input("Expected Forging Receipt",value=date.today(),format="DD-MM-YYYY")
        qty=st.number_input("Forging Order Qty pcs",min_value=1.0,value=float(max(number(order.get("order_qty_pcs")),1)),step=1.0);st.metric("RM Requirement for Forging Order",f"{qty*gross:,.3f} kg")
        if st.button("Create Forging Supplier Order",type="primary",width="stretch",disabled=not perms["can_create"] or not supplier_order.strip()):
            try:service.repo.insert("supply_forging_orders",{"customer_order_id":order_id,"forging_supplier_id":sid,"supplier_order_no":supplier_order.strip(),"order_date":od.isoformat(),"order_qty_pcs":qty,"required_rm_kg":qty*gross,"expected_date":expected.isoformat(),"status":"OPEN"});service.sync_order_status(order_id);save_success_popup("Forging Order linked to Customer Order.",queue_for_rerun=True);st.rerun()
            except Exception as exc:st.error(str(exc))
    with stage_section("B","FORGING RECEIPT",key="supply_forging_receipt"):
        order_id,order=_order_selector(service,"supply_forg_receipt_ref")
        if not order_id:return
        fos=[r for r in service.repo.select("supply_forging_orders",eq={"customer_order_id":order_id},limit=1000) if r.get("status")!="CANCELLED"];fo_map={str(r["id"]):f"{r.get('supplier_order_no')} · {number(r.get('order_qty_pcs')):,.0f} pcs" for r in fos}
        if not fo_map:st.warning("Create the Forging Supplier Order first.");return
        fo_id=st.selectbox("Forging Supplier Order",list(fo_map),format_func=lambda v:fo_map[v]);fo=next(r for r in fos if str(r["id"])==fo_id);gross=number((order or {}).get("gross_weight_kg_snapshot"));c1,c2,c3,c4=st.columns(4,gap="small");receipt=c1.text_input("Forging Receipt No.");rd=c2.date_input("Receipt Date",value=date.today(),format="DD-MM-YYYY");qty=c3.number_input("Received Forging Qty pcs",min_value=1.0,step=1.0);rej=c4.number_input("Rejected Qty pcs",min_value=0.0,step=1.0)
        calculated=qty*gross;actual=st.number_input("Actual RM Consumed kg (optional override)",min_value=0.0,value=0.0,step=1.0,help=f"Leave 0 to calculate from received pcs × gross weight = {calculated:,.3f} kg")
        remarks=st.text_input("Forging Receipt Remarks")
        if st.button("Post Forging Receipt",type="primary",width="stretch",disabled=not perms["can_create"] or not receipt.strip()):
            try:service.repo.insert("supply_forging_receipts",{"customer_order_id":order_id,"forging_order_id":fo_id,"forging_supplier_id":fo.get("forging_supplier_id"),"receipt_number":receipt.strip(),"receipt_date":rd.isoformat(),"received_qty_pcs":qty,"rejected_qty_pcs":rej,"actual_rm_consumed_kg":actual if actual>0 else None,"gross_weight_kg_snapshot":gross,"remarks":remarks.strip() or None});service.sync_order_status(order_id);save_success_popup("Forging Receipt linked to Customer Order and supplier RM balance updated.",queue_for_rerun=True);st.rerun()
            except Exception as exc:st.error(str(exc))
    with stage_section("C","FORGING SUPPLIER RM BALANCE",key="supply_forging_balance"):
        order_id,order=_order_selector(service,"supply_forg_balance_ref")
        if order_id:st.dataframe(style_status_dataframe(pd.DataFrame(service.supplier_balances(order_id))),hide_index=True,width="stretch")


def render_downstream() -> None:
    page_header("Machining / Finished Goods / Customer Dispatch", "Downstream events retain the same Master Reference", "Supply Chain")
    service=SupplyChainService();perms=current_permissions("SUPPLY_CHAIN")
    stages=[("A","MACHINING","MACHINING"),("B","FINISHED GOODS","FINISHED_GOODS"),("C","CUSTOMER DISPATCH / INVOICE / ASN","CUSTOMER_DISPATCH")]
    for letter,title,event_type in stages:
        with stage_section(letter,title,key=f"supply_downstream_{event_type.lower()}"):
            order_id,order=_order_selector(service,f"supply_downstream_order_{event_type}")
            if not order_id:continue
            c1,c2,c3,c4=st.columns(4,gap="small");ref=c1.text_input("Reference No.",key=f"down_ref_{event_type}");ed=c2.date_input("Date",value=date.today(),format="DD-MM-YYYY",key=f"down_date_{event_type}");qty=c3.number_input("Quantity pcs",min_value=1.0,step=1.0,key=f"down_qty_{event_type}");rej=c4.number_input("Rejected Qty pcs",min_value=0.0,step=1.0,key=f"down_rej_{event_type}")
            invoice=None;invoice_date=None;asn=None
            if event_type=="CUSTOMER_DISPATCH":
                c1,c2,c3=st.columns(3,gap="small");invoice=c1.text_input("Invoice No.");invoice_date=c2.date_input("Invoice Date",value=date.today(),format="DD-MM-YYYY");asn=c3.text_input("ASN No.")
            remarks=st.text_input("Remarks",key=f"down_rem_{event_type}")
            if st.button(f"Post {title.title()}",type="primary",width="stretch",key=f"down_save_{event_type}",disabled=not perms["can_create"] or not ref.strip()):
                try:service.repo.insert("supply_downstream_events",{"customer_order_id":order_id,"event_type":event_type,"reference_no":ref.strip(),"event_date":ed.isoformat(),"qty_pcs":qty,"rejected_qty_pcs":rej,"invoice_no":invoice.strip() if invoice else None,"invoice_date":invoice_date.isoformat() if invoice_date else None,"asn_no":asn.strip() if asn else None,"remarks":remarks.strip() or None});service.sync_order_status(order_id);save_success_popup(f"{title.title()} linked to Customer Order.",queue_for_rerun=True);st.rerun()
                except Exception as exc:st.error(str(exc))


def render_traceability() -> None:
    page_header("Supply Chain Traceability", "Search one Customer Order Master Reference and see the complete genealogy", "Supply Chain")
    service=SupplyChainService();parts,parties=_maps(service);orders=service.customer_orders();search=st.text_input("Search Master Reference / Customer Order No.",placeholder="Example: 10101618")
    matches=[r for r in orders if not search or search.casefold() in " ".join([str(r.get("master_reference_no") or ""),str(r.get("customer_order_no") or ""),str((parts.get(str(r.get("part_id"))) or {}).get("part_number") or "")]).casefold()]
    with stage_section("A","ORDER SEARCH RESULTS",key="supply_trace_search"):
        if not matches:st.info("No matching Customer Order reference found.")
        else:
            labels={str(r["id"]):service.order_label(r,parts,parties) for r in matches};selected=st.selectbox("Matched Customer Order",list(labels),format_func=lambda v:labels[v]);order=next(r for r in matches if str(r["id"])==selected);workflow_progress(_order_progress(service,order))
    if matches:
        with stage_section("B","COMPLETE SUPPLY CHAIN HISTORY",key="supply_trace_history"):
            st.dataframe(style_status_dataframe(pd.DataFrame(service.timeline(selected))),hide_index=True,width="stretch",height=520)
        with stage_section("C","FORGING SUPPLIER RAW MATERIAL BALANCE",key="supply_trace_balance"):
            st.dataframe(style_status_dataframe(pd.DataFrame(service.supplier_balances(selected))),hide_index=True,width="stretch")
