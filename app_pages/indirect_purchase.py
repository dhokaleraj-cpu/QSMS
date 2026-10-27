"""QCMS R37 · Indirect Purchase module (website).

Separate from the Direct Purchase Order (Supply Chain → Direct Purchase Orders, which buys raw material / forgings
against customer orders). Indirect Purchase buys consumables, tools, spares, stationery, IT, services, capital items,
packing and PPE: Item Master → Purchase Requisition → Indirect PO (approval) → Indirect Inward (GRN) → Stock / Issue.
"""
from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from typing import Any, Mapping, Sequence

import pandas as pd
import streamlit as st

from core.access import module_permissions_with_source
from core.auth import current_employee_id, current_profile
from core.branch_context import branch_label, resolve_current_branch
from core.db_errors import db_message
from core.indirect_po_pdf import DEFAULT_INDIRECT_INSTRUCTIONS, build_indirect_po_pdf, indirect_grn_pdf_bytes
from core.indirect_purchase_service import (
    DEFAULT_TERMS, GST_RATES, MODULE_KEY, OPEN_PO_STATUSES, STATUS_LABELS, UOMS, IndirectPurchaseService,
    clean, employee_name, indirect_notifier, number, po_email_text,
)
from core.report_filters import render_filters, report_exports
from core.selection_labels import party_label, with_status
from core.ui import kpi_grid, page_header, portal_table, save_success_popup, section_bar, selectable_table, stage_section

CONTEXT = "Indirect Purchase"
FULL_ROLES = {"MANAGEMENT", "PROCUREMENT", "SUPPLY_CHAIN"}


# ------------------------------------------------------------------------------------------------ common helpers
def _perms() -> dict[str, bool]:
    profile = current_profile() or {}
    try:
        perms, source = module_permissions_with_source(profile, MODULE_KEY)
    except Exception:
        perms, source = {"can_view": True}, "LEGACY"
    role = str(profile.get("role") or "").upper().replace(" ", "_")
    if str(source).startswith("LEGACY") and role in FULL_ROLES:
        perms = {"can_view": True, "can_create": True, "can_edit": True, "can_archive": False, "can_validate": True, "can_approve": True}
    return dict(perms)


def _is_admin() -> bool:
    return str((current_profile() or {}).get("role") or "").upper() == "ADMIN"


def _go(route: str, **state: Any) -> None:
    for key, value in state.items():
        st.session_state[key] = value
    page = (st.session_state.get("_qsms_pages") or {}).get(route)
    if page is not None:
        st.switch_page(page)
    else:
        st.rerun()


def _money(value: Any, currency: str = "INR") -> str:
    return f"{currency} {number(value):,.2f}"


def _excel(frame: pd.DataFrame, sheet: str) -> bytes:
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=sheet[:31])
    return out.getvalue()


def _show_pdf(pdf: bytes) -> None:
    try:
        from core.po_print_ui import show_pdf
        show_pdf(pdf)
    except Exception:
        st.caption("Inline preview unavailable – use the download button.")


def _clickable(frame: pd.DataFrame, *, key: str, height: int = 420) -> int | None:
    """Grid with click-to-open rows; falls back to a plain grid where the native grid is unavailable."""
    if frame.empty:
        st.info("No records match the filters.")
        return None
    try:
        return selectable_table(frame, key=key, height=height)
    except Exception:
        portal_table(frame, hide_index=True, width="stretch", height=height)
        return None


def _supplier_labels(service: IndirectPurchaseService) -> dict[str, str]:
    return {str(r["id"]): with_status(party_label(r), r) for r in service.suppliers()}


def _branch_options(service: IndirectPurchaseService) -> tuple[dict[str, str], str]:
    labels = {str(r.get("id")): branch_label(r) for r in service.branches()}
    try:
        current = str(resolve_current_branch(service.repo, current_profile() or {}).get("id") or "")
    except Exception:
        current = ""
    if current not in labels:
        current = next(iter(labels), "")
    return labels, current


def _item_labels(service: IndirectPurchaseService) -> dict[str, str]:
    return {str(r["id"]): f"{r.get('item_code')} · {r.get('item_name')} · {r.get('uom')}" for r in service.items(active_only=True)}


def _employee_labels(service: IndirectPurchaseService) -> dict[str, str]:
    return {str(r["id"]): f"{employee_name(r)} · {r.get('employee_code') or '-'} · {r.get('department') or '-'}" for r in service.employees()}


def _department_input(service: IndirectPurchaseService, label: str, *, key: str, default: str = "") -> str:
    options = service.departments()
    if default and default not in options:
        options = [default, *options]
    if options:
        choice = st.selectbox(label, [*options, "Other…"], index=options.index(default) if default in options else 0, key=key)
        if choice == "Other…":
            return st.text_input(f"{label} (other)", key=f"{key}_other")
        return choice
    return st.text_input(label, value=default, key=key)


def _status_text(value: Any) -> str:
    return STATUS_LABELS.get(str(value or "").upper(), str(value or "-").replace("_", " ").title())


def _email_panel(service: IndirectPurchaseService, *, related_table: str, related_id: str, header: Mapping[str, Any], purpose: str,
                 key: str, to_default: str = "", title: str = "E-MAIL", disabled: bool = False) -> None:
    """Editable To / CC / Subject / Body; the controlled PDF is attached by the QCMS outbox."""
    from core.notification_ui import _split_emails
    if not st.toggle(title, value=False, key=f"{key}_open"):
        return
    with st.container(border=True):
        subject, body = po_email_text(header, purpose=purpose) if related_table == "indirect_purchase_orders" else (
            f"Indirect GRN {header.get('grn_number')}", f"Indirect Goods Receipt Note {header.get('grn_number')} is attached.\n\nRegards,\nSTAWN QCMS")
        c1, c2 = st.columns(2, gap="small")
        to_email = c1.text_input("To", value=to_default, key=f"{key}_to").strip()
        cc = _split_emails(c2.text_input("CC", value="", key=f"{key}_cc"))
        subject = st.text_input("Subject", value=subject, key=f"{key}_subject")
        body = st.text_area("Message", value=body, height=150, key=f"{key}_body")
        st.caption(f"Attachment: {header.get('po_number') or header.get('grn_number')}.pdf (controlled print with the current approval watermark)")
        if st.button("Send e-mail", type="primary", icon=":material/send:", width="stretch", key=f"{key}_send", disabled=disabled or "@" not in to_email):
            try:
                notifier = indirect_notifier(service.repo)
                event = {"SUPPLIER": "INDIRECT_PO_RELEASED", "APPROVAL": "INDIRECT_PO_APPROVAL_PENDING"}.get(purpose, "INDIRECT_GRN")
                row = notifier.enqueue(event, subject=subject, body_text=body, related_table=related_table, related_id=related_id,
                                       recipient_email=to_email, cc_emails=cc, include_supplier=False, include_generated_pdf=True,
                                       include_record_attachments=False)
                result = notifier.dispatch([row] if row else [])
                if not row:
                    st.error("The e-mail could not be queued.")
                elif result.get("error"):
                    st.warning(f"E-mail queued; delivery returned: {result.get('error')}. It is retried from My Sent Emails / outbox.")
                else:
                    save_success_popup(f"E-mail sent to {to_email} with the controlled PDF.")
            except Exception as exc:
                st.error(db_message(exc))
        if "@" not in to_email:
            st.caption("Enter a valid To address (the supplier e-mail comes from Party Master).")


def _po_key_info(service: IndirectPurchaseService, po: Mapping[str, Any]) -> None:
    currency = po.get("currency") or "INR"
    kpi_grid([
        {"label": "IPO Number", "value": po.get("po_number"), "foot": f"Date {po.get('po_date') or '-'} · Rev {int(number(po.get('revision_no')))}", "color": "#0B6E70", "background": "#E3F2F2"},
        {"label": "Supplier", "value": (po.get("vendor_snapshot") or {}).get("party_name") or "-", "foot": (po.get("vendor_snapshot") or {}).get("email") or "no e-mail", "color": "#2563EB", "background": "#EFF6FF"},
        {"label": "Grand Total", "value": _money(po.get("grand_total"), currency), "foot": f"Taxable {_money(po.get('subtotal'), currency)}", "color": "#7C3AED", "background": "#F5F3FF"},
        {"label": "Status", "value": _status_text(po.get("status")), "foot": f"Approval: {_status_text(po.get('approval_status'))}", "color": "#B45309", "background": "#FFFBEB"},
    ])
    lines = service.po_items(str(po.get("id")))
    if lines:
        portal_table(pd.DataFrame([{
            "#": l.get("line_no"), "Item Code": l.get("item_code") or "-", "Item": l.get("item_name"), "HSN/SAC": l.get("hsn_sac") or "-",
            "Qty": number(l.get("quantity")), "UOM": l.get("uom"), "Rate": number(l.get("rate")), "Disc %": number(l.get("discount_percent")),
            "Taxable": number(l.get("taxable_amount")), "GST %": number(l.get("gst_percent")), "Amount": number(l.get("line_total")),
            "Received": number(l.get("received_qty")), "Accepted": number(l.get("accepted_qty")), "Rejected": number(l.get("rejected_qty")),
        } for l in lines]), hide_index=True, width="stretch", height=min(380, 90 + 36 * len(lines)))


def _pdf_buttons(service: IndirectPurchaseService, po: Mapping[str, Any], *, key: str, preview: bool = True) -> bytes | None:
    items = service.po_items(str(po.get("id")))
    if not items:
        st.info("This Indirect PO has no lines.")
        return None
    try:
        pdf = build_indirect_po_pdf(po, items)
    except Exception as exc:
        st.error(f"Indirect PO PDF could not be generated: {db_message(exc)}")
        return None
    c1, c2 = st.columns(2, gap="small")
    c1.download_button("Download / Print Indirect PO", pdf, file_name=f"{po.get('po_number')}.pdf", mime="application/pdf",
                       icon=":material/picture_as_pdf:", type="primary", width="stretch", key=f"{key}_pdf")
    show = c2.toggle("Preview PDF", value=False, key=f"{key}_preview") if preview else False
    if show:
        _show_pdf(pdf)
    return pdf


# ------------------------------------------------------------------------------------------------ 1. dashboard
def render_home() -> None:
    page_header("Indirect Purchase", "Consumables, tools, spares, stationery, IT, services, capital items, packing and PPE – separate from the Direct (RM / forging) Purchase Orders", CONTEXT)
    service = IndirectPurchaseService()
    data = service.dashboard()
    kpi_grid([
        {"label": "Pending Approval", "value": data["pending_approval"], "foot": f"Value INR {data['pending_value']:,.0f}", "color": "#B45309", "background": "#FFFBEB"},
        {"label": "Open Indirect POs", "value": data["open"], "foot": f"Value INR {data['open_value']:,.0f}", "color": "#0B6E70", "background": "#E3F2F2"},
        {"label": "Overdue Delivery", "value": data["overdue"], "foot": "Open POs past the delivery date", "color": "#B91C1C", "background": "#FEF2F2"},
        {"label": "Received This Month", "value": data["received_month"], "foot": f"GRN value INR {data['received_month_value']:,.0f}", "color": "#2563EB", "background": "#EFF6FF"},
        {"label": "Spend This Month", "value": f"INR {data['spend_month']:,.0f}", "foot": "Approved Indirect POs (taxable value)", "color": "#7C3AED", "background": "#F5F3FF"},
        {"label": "Open Requisitions", "value": data["requisitions_open"], "foot": f"GRNs awaiting approval: {data['grn_pending_approval']}", "color": "#475569", "background": "#F1F5F9"},
    ])
    c1, c2 = st.columns([1.1, 1], gap="medium")
    with c1:
        section_bar("SPEND THIS MONTH BY CATEGORY")
        spend = data["spend_by_category"]
        if spend:
            top = max(spend.values()) or 1
            rows = "".join(
                f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0"><div style="width:42%;font-size:12px">{cat}</div>'
                f'<div style="flex:1;background:#E3F2F2;border-radius:4px"><div style="width:{max(2, 100 * val / top):.0f}%;background:#0B6E70;height:14px;border-radius:4px"></div></div>'
                f'<div style="width:24%;text-align:right;font-size:12px">INR {val:,.0f}</div></div>' for cat, val in spend.items())
            st.markdown(rows, unsafe_allow_html=True)
        else:
            st.caption("No approved Indirect PO this month yet.")
        section_bar("SPEND THIS MONTH BY SUPPLIER (TOP 10)")
        by_supplier = data.get("spend_by_supplier") or {}
        if by_supplier:
            portal_table(pd.DataFrame([{"Supplier": k, "Taxable Value (INR)": round(v, 2)} for k, v in by_supplier.items()]), hide_index=True, width="stretch", height=260)
        else:
            st.caption("No approved Indirect PO this month yet.")
    with c2:
        section_bar("OVERDUE DELIVERIES")
        overdue = data["overdue_rows"]
        if overdue:
            portal_table(pd.DataFrame([{"IPO Number": p.get("po_number"), "Supplier": (p.get("vendor_snapshot") or {}).get("party_name"),
                                        "Delivery Date": p.get("delivery_date"), "Status": p.get("status")} for p in overdue]), hide_index=True, width="stretch", height=260)
        else:
            st.caption("No overdue Indirect PO.")
    section_bar("QUICK ACTIONS")
    pages = st.session_state.get("_qsms_pages") or {}
    links = (("indirect-requisition", "New Requisition", ":material/playlist_add:"), ("indirect-po", "New Indirect PO", ":material/add_shopping_cart:"),
             ("indirect-po-approval", "Approve POs", ":material/approval:"), ("indirect-inward", "Indirect Inward (GRN)", ":material/input:"),
             ("indirect-stock", "Stock & Issue", ":material/inventory_2:"), ("indirect-items", "Item Master", ":material/category:"))
    cols = st.columns(len(links), gap="small")
    for col, (route, label, icon) in zip(cols, links):
        if route in pages:
            col.page_link(pages[route], label=label, icon=icon, width="stretch")


# ------------------------------------------------------------------------------------------------ 2. item master
def render_items() -> None:
    page_header("Indirect Item Master", "Item code series, category, UOM, HSN/SAC, GST %, default supplier, last price and stock levels", CONTEXT)
    service = IndirectPurchaseService(); perms = _perms()
    can_write = bool(perms.get("can_create") or perms.get("can_edit"))
    categories = service.category_labels()
    supplier_labels = _supplier_labels(service)
    items = service.items()
    item_by_id = {str(r["id"]): r for r in items}

    with stage_section("A", "ITEM ENTRY / EDIT", "Leave Item Code blank to take the next number from the item series. Duplicate active item names (same UOM) are blocked.", key="indirect_item_entry"):
        edit_labels = {"": "➕ New item", **{k: f"{v.get('item_code')} · {v.get('item_name')}" for k, v in item_by_id.items()}}
        requested = str(st.session_state.pop("indirect_item_edit_id", "") or "")
        if requested in edit_labels:
            st.session_state["indirect_item_select"] = requested
        selected = st.selectbox("Item", list(edit_labels), format_func=lambda v: edit_labels[v], key="indirect_item_select")
        current = item_by_id.get(selected, {})
        token = selected or "new"
        with st.form(f"indirect_item_form_{token}"):
            c = st.columns(3, gap="small")
            code = c[0].text_input("Item Code", value=str(current.get("item_code") or ""), placeholder="auto (IND-#####)", disabled=bool(current))
            name = c[1].text_input("Item Name *", value=str(current.get("item_name") or ""))
            cat_keys = list(categories)
            category = c[2].selectbox("Category", cat_keys, index=cat_keys.index(str(current.get("category"))) if str(current.get("category")) in cat_keys else len(cat_keys) - 1, format_func=lambda v: categories[v])
            description = st.text_input("Description", value=str(current.get("description") or ""))
            specification = st.text_area("Specification / Make / Model", value=str(current.get("specification") or ""), height=70)
            c = st.columns(4, gap="small")
            uom_options = list(UOMS) if str(current.get("uom") or "NOS") in UOMS else [str(current.get("uom")), *UOMS]
            uom = c[0].selectbox("UOM", uom_options, index=uom_options.index(str(current.get("uom") or "NOS")))
            hsn = c[1].text_input("HSN / SAC", value=str(current.get("hsn_sac") or ""))
            gst = c[2].selectbox("GST %", list(GST_RATES), index=list(GST_RATES).index(number(current.get("gst_percent"))) if number(current.get("gst_percent")) in GST_RATES else 3)
            sup_keys = ["", *supplier_labels]
            supplier = c[3].selectbox("Default Supplier", sup_keys, index=sup_keys.index(str(current.get("default_supplier_id") or "")) if str(current.get("default_supplier_id") or "") in sup_keys else 0, format_func=lambda v: supplier_labels.get(v, "— none —"))
            c = st.columns(5, gap="small")
            last_price = c[0].number_input("Last Price", min_value=0.0, value=number(current.get("last_price")), step=1.0, format="%.2f")
            reorder = c[1].number_input("Reorder Level", min_value=0.0, value=number(current.get("reorder_level")), step=1.0)
            min_stock = c[2].number_input("Min Stock", min_value=0.0, value=number(current.get("min_stock")), step=1.0)
            max_stock = c[3].number_input("Max Stock", min_value=0.0, value=number(current.get("max_stock")), step=1.0)
            location = c[4].text_input("Storage Location", value=str(current.get("storage_location") or ""))
            c = st.columns(3, gap="small")
            stock_item = c[0].toggle("Stock item (kept in store / stock ledger)", value=bool(current.get("is_stock_item", True)))
            status = c[1].selectbox("Status", ["ACTIVE", "INACTIVE"], index=0 if str(current.get("status") or "ACTIVE") == "ACTIVE" else 1)
            remarks = c[2].text_input("Remarks", value=str(current.get("remarks") or ""))
            saved = st.form_submit_button("Save Item", type="primary", width="stretch", disabled=not can_write)
        if saved:
            try:
                row = service.save_item({"item_code": code, "item_name": name, "category": category, "description": description, "specification": specification,
                                         "uom": uom, "hsn_sac": hsn, "gst_percent": gst, "default_supplier_id": supplier, "last_price": last_price or None,
                                         "reorder_level": reorder or None, "min_stock": min_stock or None, "max_stock": max_stock or None,
                                         "storage_location": location, "is_stock_item": stock_item, "status": status, "remarks": remarks},
                                        record_id=selected or None)
                save_success_popup(f"Indirect item {row.get('item_code')} saved.", queue_for_rerun=True); st.rerun()
            except Exception as exc:
                st.error(db_message(exc))
        if not can_write:
            st.caption("You have view-only rights for Indirect Purchase.")

    with stage_section("B", "ITEM REGISTER", "Click a row to edit the item.", key="indirect_item_register"):
        c = st.columns([2, 1, 1], gap="small")
        query = c[0].text_input("Search", key="indirect_item_search", placeholder="code, name, HSN, description…").strip().casefold()
        cat_filter = c[1].selectbox("Category", ["ALL", *categories], format_func=lambda v: "All categories" if v == "ALL" else categories[v], key="indirect_item_cat")
        status_filter = c[2].selectbox("Status", ["ACTIVE", "INACTIVE", "ALL"], key="indirect_item_status")
        rows = []
        for r in items:
            if cat_filter != "ALL" and str(r.get("category")) != cat_filter:
                continue
            if status_filter != "ALL" and str(r.get("status") or "ACTIVE") != status_filter:
                continue
            text = " ".join(str(r.get(k) or "") for k in ("item_code", "item_name", "description", "hsn_sac", "specification")).casefold()
            if query and query not in text:
                continue
            rows.append({"Item Code": r.get("item_code"), "Item Name": r.get("item_name"), "Category": categories.get(str(r.get("category")), r.get("category")),
                         "UOM": r.get("uom"), "HSN/SAC": r.get("hsn_sac") or "-", "GST %": number(r.get("gst_percent")),
                         "Last Price": number(r.get("last_price")), "Last Price Date": r.get("last_price_date") or "-",
                         "Default Supplier": supplier_labels.get(str(r.get("default_supplier_id") or ""), "-"), "Reorder": r.get("reorder_level"),
                         "Stock Item": "Yes" if r.get("is_stock_item", True) else "No", "Status": r.get("status") or "ACTIVE", "_id": r.get("id")})
        frame = pd.DataFrame(rows)
        picked = _clickable(frame.drop(columns=["_id"], errors="ignore") if not frame.empty else frame, key="indirect_item_grid")
        if picked is not None and picked < len(rows):
            _go("indirect-items", indirect_item_edit_id=str(rows[picked]["_id"]))
        if not frame.empty:
            st.download_button("Download item register (Excel)", _excel(frame.drop(columns=["_id"]), "Indirect Items"), file_name="Indirect_Item_Master.xlsx",
                               icon=":material/table_view:", width="stretch", key="indirect_item_excel")

    with stage_section("C", "CATEGORIES", "Default categories are always available; add your own or rename / deactivate here.", key="indirect_item_categories"):
        portal_table(pd.DataFrame([{"Code": r.get("category_code"), "Name": r.get("category_name"), "Source": "Default" if r.get("_default") else "Company"} for r in service.categories()]),
                     hide_index=True, width="stretch", height=300)
        with st.form("indirect_category_form"):
            c = st.columns([1, 2, 1], gap="small")
            cat_code = c[0].text_input("Category Code", placeholder="e.g. ELECTRICAL")
            cat_name = c[1].text_input("Category Name", placeholder="e.g. Electrical Spares")
            cat_status = c[2].selectbox("Status", ["ACTIVE", "INACTIVE"])
            if st.form_submit_button("Save Category", width="stretch", disabled=not can_write):
                try:
                    service.save_category(cat_code, cat_name, status=cat_status)
                    save_success_popup("Category saved.", queue_for_rerun=True); st.rerun()
                except Exception as exc:
                    st.error(db_message(exc))

    with stage_section("D", "IMPORT ITEMS FROM EXCEL", "Download the template, fill it and upload. Existing item codes are updated; blank codes get the next number.", key="indirect_item_import"):
        st.download_button("Download Indirect Item import template", service.import_template_bytes(), file_name="Indirect_Item_Master_Template.xlsx",
                           icon=":material/download:", width="stretch", key="indirect_item_template")
        upload = st.file_uploader("Upload filled template (.xlsx)", type=["xlsx"], key="indirect_item_upload", disabled=not can_write)
        if upload is not None:
            try:
                frame = pd.read_excel(upload, sheet_name=0, dtype=object)
                preview = service.import_preview(frame.to_dict("records"))
                portal_table(pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in preview]), hide_index=True, width="stretch", height=320)
                ok = sum(1 for r in preview if r["Action"] != "ERROR")
                if st.button(f"Import {ok} valid row(s)", type="primary", width="stretch", disabled=not ok, key="indirect_item_import_go"):
                    counts = service.apply_import(preview)
                    save_success_popup(f"Items imported · created {counts['created']} · updated {counts['updated']} · skipped {counts['skipped']}.", queue_for_rerun=True); st.rerun()
            except Exception as exc:
                st.error(db_message(exc))

    if _is_admin() or perms.get("can_approve"):
        with stage_section("E", "NUMBER SERIES", "Format: PREFIX-BRANCH-YY-SEQUENCE (e.g. IPO-D9-26-0001). Year = Indian financial year (April) or calendar year.", key="indirect_number_series"):
            settings = service.series_settings()
            for key, cfg in settings.items():
                with st.form(f"indirect_series_{key}"):
                    st.markdown(f"**{cfg['label']}** · series `{key}`")
                    c = st.columns(6, gap="small")
                    prefix = c[0].text_input("Prefix", value=str(cfg.get("prefix")), key=f"ser_{key}_prefix")
                    inc_branch = c[1].toggle("Branch code", value=bool(cfg.get("include_branch")), key=f"ser_{key}_branch")
                    inc_year = c[2].toggle("Year", value=bool(cfg.get("include_year")), key=f"ser_{key}_year")
                    year_mode = c[3].selectbox("Year mode", ["FY", "CALENDAR"], index=0 if str(cfg.get("year_mode")) != "CALENDAR" else 1, key=f"ser_{key}_ym")
                    digits = c[4].number_input("Digits", min_value=3, max_value=8, value=int(number(cfg.get("digits")) or 4), key=f"ser_{key}_digits")
                    separator = c[5].text_input("Separator", value=str(cfg.get("separator") or "-"), max_chars=2, key=f"ser_{key}_sep")
                    if st.form_submit_button("Save series", width="stretch", disabled=not can_write):
                        try:
                            service.save_series(key, {"prefix": prefix, "include_branch": inc_branch, "include_year": inc_year, "year_mode": year_mode, "digits": digits, "separator": separator})
                            save_success_popup(f"{cfg['label']} series saved.", queue_for_rerun=True); st.rerun()
                        except Exception as exc:
                            st.error(db_message(exc))


# ------------------------------------------------------------------------------------------------ 3. requisition
def render_requisition() -> None:
    page_header("Indirect Purchase Requisition", "Departments request indirect items; Purchase converts approved requisitions into an Indirect PO", CONTEXT)
    service = IndirectPurchaseService(); perms = _perms()
    profile = current_profile() or {}
    login_employee_id = current_employee_id(refresh=True)
    login_employee = service.employee(login_employee_id)
    branch_labels, default_branch = _branch_options(service)
    item_labels = _item_labels(service)
    reverse_items = {v: k for k, v in item_labels.items()}

    with stage_section("A", "NEW REQUISITION", "Select items from the master or type a free description; quantities and required date are mandatory.", key="indirect_pr_new"):
        c = st.columns(4, gap="small")
        branch = c[0].selectbox("Company Branch / Plant", list(branch_labels) or [""], format_func=lambda v: branch_labels.get(v, "-"),
                                index=list(branch_labels).index(default_branch) if default_branch in branch_labels else 0, key="indirect_pr_branch")
        with c[1]:
            department = _department_input(service, "Department *", key="indirect_pr_dept", default=clean(login_employee.get("department")))
        cost_centre = c[2].text_input("Cost Centre", key="indirect_pr_cc")
        required = c[3].date_input("Required Date", value=date.today() + timedelta(days=7), format="DD-MM-YYYY", key="indirect_pr_required")
        c = st.columns([2, 1], gap="small")
        purpose = c[0].text_input("Purpose / Justification", key="indirect_pr_purpose")
        priority = c[1].selectbox("Priority", ["NORMAL", "URGENT", "BREAKDOWN"], key="indirect_pr_priority")
        st.caption(f"Requested by: **{employee_name(login_employee) or profile.get('full_name') or '-'}**")
        blank = pd.DataFrame([{"Item": None, "Description": "", "Qty": 1.0, "UOM": "NOS", "Est. Rate": 0.0, "Remarks": ""} for _ in range(3)])
        editor = st.data_editor(blank, num_rows="dynamic", hide_index=True, width="stretch", key="indirect_pr_lines", column_config={
            "Item": st.column_config.SelectboxColumn("Item (master)", options=list(item_labels.values()), width="large"),
            "Qty": st.column_config.NumberColumn(min_value=0.0, format="%.3f"),
            "UOM": st.column_config.SelectboxColumn(options=list(UOMS)),
            "Est. Rate": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
        })
        if st.button("Submit Requisition", type="primary", width="stretch", key="indirect_pr_submit", disabled=not perms.get("can_view")):
            lines = []
            for _, r in editor.iterrows():
                item_id = reverse_items.get(str(r.get("Item") or ""))
                item = service.item(item_id) if item_id else {}
                lines.append({"item_id": item_id, "item_name": item.get("item_name") or clean(r.get("Description")), "description": clean(r.get("Description")),
                              "quantity": number(r.get("Qty")), "uom": item.get("uom") or r.get("UOM"), "estimated_rate": number(r.get("Est. Rate")) or item.get("last_price"),
                              "remarks": clean(r.get("Remarks"))})
            try:
                pr = service.create_requisition({"company_branch_id": branch or None, "department": department, "cost_centre": cost_centre, "required_date": required,
                                                 "purpose": purpose, "priority": priority, "requested_by_employee_id": login_employee_id or None,
                                                 "requested_by_name": employee_name(login_employee) or profile.get("full_name")}, lines)
                save_success_popup(f"Requisition {pr.get('pr_number')} submitted.", queue_for_rerun=True); st.rerun()
            except Exception as exc:
                st.error(db_message(exc))

    with stage_section("B", "REQUISITION REGISTER · APPROVE / CONVERT TO PO", "Approve or reject submitted requisitions; convert approved ones into an Indirect PO.", key="indirect_pr_register"):
        reqs = service.requisitions()
        status_filter = st.selectbox("Status", ["OPEN", "ALL", "SUBMITTED", "APPROVED", "PARTIALLY_ORDERED", "CONVERTED", "REJECTED"], key="indirect_pr_status")
        shown = [r for r in reqs if status_filter == "ALL" or (status_filter == "OPEN" and str(r.get("status")) in {"SUBMITTED", "APPROVED", "PARTIALLY_ORDERED"}) or str(r.get("status")) == status_filter]
        frame = pd.DataFrame([{"PR Number": r.get("pr_number"), "PR Date": r.get("pr_date"), "Department": r.get("department"), "Cost Centre": r.get("cost_centre") or "-",
                               "Requested By": r.get("requested_by_name") or "-", "Required Date": r.get("required_date"), "Priority": r.get("priority"),
                               "Purpose": r.get("purpose") or "-", "Status": r.get("status")} for r in shown])
        picked = _clickable(frame, key="indirect_pr_grid", height=320)
        labels = {str(r["id"]): f"{r.get('pr_number')} · {r.get('department')} · {r.get('status')}" for r in shown}
        if picked is not None and picked < len(shown):
            st.session_state["indirect_pr_select"] = str(shown[picked]["id"])
        if labels:
            if st.session_state.get("indirect_pr_select") not in labels:
                st.session_state["indirect_pr_select"] = next(iter(labels))
            pr_id = st.selectbox("Requisition", list(labels), format_func=lambda v: labels[v], key="indirect_pr_select")
            pr = service.requisition(pr_id)
            lines = service.requisition_items(pr_id)
            portal_table(pd.DataFrame([{"#": l.get("line_no"), "Item Code": l.get("item_code") or "-", "Item": l.get("item_name"), "Qty": number(l.get("quantity")),
                                        "Ordered": number(l.get("ordered_qty")), "UOM": l.get("uom"), "Est. Rate": number(l.get("estimated_rate")),
                                        "Remarks": l.get("remarks") or ""} for l in lines]), hide_index=True, width="stretch", height=min(300, 90 + 36 * len(lines)))
            status = str(pr.get("status") or "").upper()
            if status == "SUBMITTED":
                remark = st.text_input("Approval / rejection remarks", key=f"indirect_pr_remark_{pr_id}")
                c = st.columns(2, gap="small")
                if c[0].button("Approve Requisition", type="primary", width="stretch", disabled=not perms.get("can_approve"), key=f"indirect_pr_approve_{pr_id}"):
                    try:
                        service.decide_requisition(pr_id, True, remark, login_employee_id)
                        save_success_popup("Requisition approved.", queue_for_rerun=True); st.rerun()
                    except Exception as exc:
                        st.error(db_message(exc))
                if c[1].button("Reject Requisition", width="stretch", disabled=not perms.get("can_approve"), key=f"indirect_pr_reject_{pr_id}"):
                    try:
                        service.decide_requisition(pr_id, False, remark, login_employee_id)
                        save_success_popup("Requisition rejected.", queue_for_rerun=True); st.rerun()
                    except Exception as exc:
                        st.error(db_message(exc))
            if status in {"APPROVED", "PARTIALLY_ORDERED"}:
                if st.button("Convert to Indirect PO", type="primary", icon=":material/add_shopping_cart:", width="stretch",
                             disabled=not (perms.get("can_create") or perms.get("can_edit")), key=f"indirect_pr_convert_{pr_id}"):
                    prefill = {"requisition_id": pr_id, "department": pr.get("department"), "cost_centre": pr.get("cost_centre"), "company_branch_id": pr.get("company_branch_id"),
                               "delivery_date": pr.get("required_date"), "requisitioner": pr.get("requested_by_name"), "requisitioner_employee_id": pr.get("requested_by_employee_id"),
                               "lines": [{"item_id": l.get("item_id"), "item_name": l.get("item_name"), "description": l.get("description"), "uom": l.get("uom"),
                                          "quantity": max(number(l.get("quantity")) - number(l.get("ordered_qty")), 0.0), "rate": number(l.get("estimated_rate")),
                                          "requisition_item_id": l.get("id")} for l in lines if number(l.get("quantity")) - number(l.get("ordered_qty")) > 0]}
                    _go("indirect-po", indirect_po_prefill=prefill, indirect_po_edit_id="")


# ------------------------------------------------------------------------------------------------ 4. PO entry / edit
_LINE_COLUMNS = ["Item", "Description", "Qty", "UOM", "Rate", "Disc %", "GST %", "HSN/SAC", "_req_item_id"]


def _lines_frame(service: IndirectPurchaseService, lines: Sequence[Mapping[str, Any]], item_labels: Mapping[str, str]) -> pd.DataFrame:
    rows = []
    for line in lines:
        item = service.item(line.get("item_id")) if line.get("item_id") else {}
        rows.append({"Item": item_labels.get(str(line.get("item_id") or "")), "Description": clean(line.get("description")) or ("" if item else clean(line.get("item_name"))),
                     "Qty": number(line.get("quantity")) or 1.0, "UOM": clean(line.get("uom")).upper() or item.get("uom") or "NOS",
                     "Rate": number(line.get("rate")) or number(item.get("last_price")), "Disc %": number(line.get("discount_percent")),
                     "GST %": number(line.get("gst_percent")) if line.get("gst_percent") not in (None, "") else number(item.get("gst_percent") if item else 18),
                     "HSN/SAC": clean(line.get("hsn_sac")) or clean(item.get("hsn_sac")), "_req_item_id": str(line.get("requisition_item_id") or "")})
    if not rows:
        rows = [{"Item": None, "Description": "", "Qty": 1.0, "UOM": "NOS", "Rate": 0.0, "Disc %": 0.0, "GST %": 18.0, "HSN/SAC": "", "_req_item_id": ""}]
    return pd.DataFrame(rows, columns=_LINE_COLUMNS)


def _editor_lines(service: IndirectPurchaseService, frame: pd.DataFrame, reverse_items: Mapping[str, str]) -> list[dict[str, Any]]:
    lines = []
    for _, r in frame.iterrows():
        item_id = reverse_items.get(str(r.get("Item") or ""))
        item = service.item(item_id) if item_id else {}
        desc = clean(r.get("Description")) if not pd.isna(r.get("Description")) else ""
        if not item_id and not desc and number(r.get("Qty")) <= 0:
            continue
        if not item_id and not desc:
            continue
        rate = r.get("Rate"); gst = r.get("GST %")
        lines.append({"item_id": item_id, "item_name": item.get("item_name") or desc, "description": desc if item_id else None,
                      "quantity": number(r.get("Qty")), "uom": (clean(r.get("UOM")) if not pd.isna(r.get("UOM")) else "") or item.get("uom") or "NOS",
                      "rate": number(rate) if not pd.isna(rate) and number(rate) > 0 else number(item.get("last_price")),
                      "discount_percent": number(r.get("Disc %")), "gst_percent": number(gst) if not pd.isna(gst) else number(item.get("gst_percent") or 18),
                      "hsn_sac": (clean(r.get("HSN/SAC")) if not pd.isna(r.get("HSN/SAC")) else "") or item.get("hsn_sac"),
                      "category": item.get("category"), "requisition_item_id": (str(r.get("_req_item_id") or "") if not pd.isna(r.get("_req_item_id")) else "") or None})
    return lines


def render_po() -> None:
    page_header("Indirect Purchase Order · Entry / Edit", "Own IPO number series, GST split by state, value-based approval, print in the Direct PO style", CONTEXT)
    service = IndirectPurchaseService(); perms = _perms()
    profile = current_profile() or {}
    login_employee_id = current_employee_id(refresh=True)
    login_employee = service.employee(login_employee_id)
    can_write = bool(perms.get("can_create") or perms.get("can_edit"))
    supplier_labels = _supplier_labels(service)
    branch_labels, default_branch = _branch_options(service)
    item_labels = _item_labels(service)
    reverse_items = {v: k for k, v in item_labels.items()}

    editable = {str(p["id"]): p for p in service.purchase_orders() if str(p.get("status") or "").upper() in {"DRAFT", "PENDING_APPROVAL", "REJECTED", "APPROVED"}}
    mode_labels = {"": "➕ New Indirect Purchase Order", **{k: f"Edit {v.get('po_number')} · {(v.get('vendor_snapshot') or {}).get('party_name') or '-'} · {_status_text(v.get('status'))}" for k, v in editable.items()}}
    requested = st.session_state.pop("indirect_po_edit_id", None)
    if requested is not None:
        st.session_state["indirect_po_mode"] = str(requested) if str(requested) in mode_labels else ""
    po_id = st.selectbox("Create or edit", list(mode_labels), format_func=lambda v: mode_labels[v], key="indirect_po_mode")
    current = service.purchase_order(po_id) if po_id else {}
    prefill = st.session_state.get("indirect_po_prefill") if not po_id else None
    source: Mapping[str, Any] = current or prefill or {}
    token = po_id or (f"pr{str((prefill or {}).get('requisition_id'))[:8]}" if prefill else "new")
    if current:
        if service.has_receipts(po_id):
            st.error("Material has been received against this PO – it can no longer be revised.")
            return
        if str(current.get("status")).upper() == "APPROVED":
            st.warning("This PO is approved. Saving a revision increases the revision number and sends it back for approval.")
    if prefill:
        st.info(f"Converting requisition into an Indirect PO · {len(prefill.get('lines') or [])} line(s) pre-filled. Choose the supplier and rates.")
        if st.button("Discard requisition pre-fill", key="indirect_po_discard_prefill"):
            st.session_state.pop("indirect_po_prefill", None); st.rerun()

    with stage_section("A", "SUPPLIER, PLANT & SHIP-TO", "Supplier comes from Party Master (supplier types). GST is CGST + SGST when the supplier is in the plant state, else IGST.", key="indirect_po_header"):
        c = st.columns(4, gap="small")
        sup_keys = list(supplier_labels)
        sup_default = str(source.get("supplier_id") or "")
        supplier_id = c[0].selectbox("Supplier *", sup_keys or [""], index=sup_keys.index(sup_default) if sup_default in sup_keys else 0,
                                     format_func=lambda v: supplier_labels.get(v, "— no supplier in Party Master —"), key=f"ipo_supplier_{token}")
        po_date = c[1].date_input("PO Date", value=date.fromisoformat(str(source.get("po_date"))[:10]) if source.get("po_date") else date.today(), format="DD-MM-YYYY", key=f"ipo_date_{token}")
        br_keys = list(branch_labels)
        br_default = str(source.get("company_branch_id") or default_branch)
        branch_id = c[2].selectbox("Company Branch / Plant *", br_keys or [""], index=br_keys.index(br_default) if br_default in br_keys else 0,
                                   format_func=lambda v: branch_labels.get(v, "-"), key=f"ipo_branch_{token}")
        ship_src_default = str(source.get("ship_to_source_type") or "BRANCH")
        ship_source = c[3].selectbox("Ship-To", ["BRANCH", "PARTY"], index=0 if ship_src_default == "BRANCH" else 1,
                                     format_func=lambda v: "Company Branch" if v == "BRANCH" else "Other party (supplier / vendor)", key=f"ipo_shipsrc_{token}")
        if ship_source == "BRANCH":
            ship_default = str(source.get("ship_to_branch_id") or branch_id)
            ship_to = st.selectbox("Ship-To Branch", br_keys or [""], index=br_keys.index(ship_default) if ship_default in br_keys else 0, format_func=lambda v: branch_labels.get(v, "-"), key=f"ipo_shipbr_{token}")
        else:
            ship_default = str(source.get("ship_to_party_id") or "")
            ship_to = st.selectbox("Ship-To Party", sup_keys or [""], index=sup_keys.index(ship_default) if ship_default in sup_keys else 0, format_func=lambda v: supplier_labels.get(v, "-"), key=f"ipo_shipparty_{token}")
        supplier = service.party(supplier_id)
        if supplier:
            st.caption(f"Supplier: {supplier.get('party_name')} · {supplier.get('city') or '-'}, {supplier.get('state') or '-'} · GSTIN {supplier.get('tax_identifier') or '-'} · {supplier.get('email') or 'no e-mail'}")

    with stage_section("B", "ORDER DETAILS", "Department / cost centre, requisitioner, delivery, commercial terms and quotation reference.", key="indirect_po_details"):
        c = st.columns(4, gap="small")
        with c[0]:
            department = _department_input(service, "Department", key=f"ipo_dept_{token}", default=clean(source.get("department") or login_employee.get("department")))
        cost_centre = c[1].text_input("Cost Centre", value=str(source.get("cost_centre") or ""), key=f"ipo_cc_{token}")
        requisitioner = c[2].text_input("Requisitioner", value=str(source.get("requisitioner") or employee_name(login_employee) or profile.get("full_name") or ""), key=f"ipo_req_{token}")
        delivery = c[3].date_input("Delivery Date", value=date.fromisoformat(str(source.get("delivery_date"))[:10]) if source.get("delivery_date") else date.today() + timedelta(days=7), format="DD-MM-YYYY", key=f"ipo_delivery_{token}")
        c = st.columns(4, gap="small")
        payment = c[0].text_input("Payment Term", value=str(source.get("payment_term") or "NET 30 DAYS AFTER GRN"), key=f"ipo_payment_{token}")
        incoterm = c[1].text_input("Incoterm", value=str(source.get("incoterm") or "DAP, PLANT"), key=f"ipo_incoterm_{token}")
        ship_via = c[2].text_input("Ship Via", value=str(source.get("ship_via") or "Road"), key=f"ipo_shipvia_{token}")
        currency = c[3].selectbox("Currency", ["INR", "USD", "EUR"], index=["INR", "USD", "EUR"].index(str(source.get("currency") or "INR")) if str(source.get("currency") or "INR") in ("INR", "USD", "EUR") else 0, key=f"ipo_currency_{token}")
        c = st.columns(2, gap="small")
        quote_ref = c[0].text_input("Quotation Reference", value=str(source.get("quotation_reference") or ""), key=f"ipo_qref_{token}")
        quote_date = c[1].date_input("Quotation Date", value=date.fromisoformat(str(source.get("quotation_date"))[:10]) if source.get("quotation_date") else date.today(), format="DD-MM-YYYY", key=f"ipo_qdate_{token}")

    with stage_section("C", "PO LINES", "Pick a master item (UOM, GST %, HSN and last price fill automatically when left blank / zero) or type a free description for a one-off purchase.", key="indirect_po_lines"):
        initial = _lines_frame(service, service.po_items(po_id) if po_id else list((prefill or {}).get("lines") or []), item_labels)
        edited = st.data_editor(initial, num_rows="dynamic", hide_index=True, width="stretch", key=f"ipo_lines_{token}", column_config={
            "Item": st.column_config.SelectboxColumn("Item (master)", options=list(item_labels.values()), width="large"),
            "Description": st.column_config.TextColumn("Description / free item", width="medium"),
            "Qty": st.column_config.NumberColumn(min_value=0.0, format="%.3f", required=True),
            "UOM": st.column_config.SelectboxColumn(options=list(UOMS)),
            "Rate": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
            "Disc %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, format="%.2f"),
            "GST %": st.column_config.SelectboxColumn(options=list(GST_RATES)),
            "HSN/SAC": st.column_config.TextColumn(),
            "_req_item_id": None,
        })
        c = st.columns(4, gap="small")
        freight = c[0].number_input("Freight / Packing", min_value=0.0, value=number(source.get("freight_amount")), step=10.0, format="%.2f", key=f"ipo_freight_{token}")
        other = c[1].number_input("Other charges (+/−)", value=number(source.get("other_amount")), step=10.0, format="%.2f", key=f"ipo_other_{token}")
        tolerance = c[2].number_input("Over-receipt tolerance %", min_value=0.0, max_value=50.0, value=number(source.get("over_receipt_tolerance_percent")), step=1.0,
                                      format="%.1f", key=f"ipo_tol_{token}", help="Indirect Inward may receive up to ordered quantity × (1 + tolerance %). 0 = no over-receipt.")
        round_rupee = c[3].toggle("Round grand total to rupee", value=True, key=f"ipo_round_{token}")
        lines = _editor_lines(service, edited, reverse_items)
        payload = {"supplier_id": supplier_id, "po_date": po_date, "company_branch_id": branch_id, "ship_to_source_type": ship_source,
                   "ship_to_branch_id": ship_to if ship_source == "BRANCH" else None, "ship_to_party_id": ship_to if ship_source != "BRANCH" else None,
                   "department": department, "cost_centre": cost_centre, "requisitioner": requisitioner,
                   "requisitioner_employee_id": source.get("requisitioner_employee_id") or login_employee_id or None,
                   "requisition_id": (prefill or {}).get("requisition_id"), "delivery_date": delivery, "payment_term": payment, "incoterm": incoterm,
                   "ship_via": ship_via, "currency": currency, "quotation_reference": quote_ref, "quotation_date": quote_date,
                   "freight_amount": freight, "other_amount": other, "round_to_rupee": round_rupee, "over_receipt_tolerance_percent": tolerance}
        header = items = None
        if lines and supplier:
            try:
                header, items = service.build_po(payload, lines)
            except Exception as exc:
                st.warning(db_message(exc))
        if header and items:
            portal_table(pd.DataFrame([{"#": i["line_no"], "Item": i["item_name"], "Qty": i["quantity"], "UOM": i["uom"], "Rate": i["rate"], "Disc %": i["discount_percent"],
                                        "Taxable": i["taxable_amount"], "GST %": i["gst_percent"], "GST": i["gst_amount"], "Amount": i["line_total"]} for i in items]),
                         hide_index=True, width="stretch", height=min(320, 90 + 36 * len(items)))
            gst_text = f"IGST {header['igst_amount']:,.2f}" if header["gst_mode"] == "INTER" else f"CGST {header['cgst_amount']:,.2f} + SGST {header['sgst_amount']:,.2f}"
            kpi_grid([
                {"label": "Taxable", "value": f"{currency} {header['subtotal']:,.2f}", "foot": f"Gross {header['gross_amount']:,.2f} − discount {header['discount_amount']:,.2f}", "color": "#0B6E70", "background": "#E3F2F2"},
                {"label": "GST", "value": f"{currency} {header['cgst_amount'] + header['sgst_amount'] + header['igst_amount']:,.2f}", "foot": gst_text + (" (intra-state)" if header["gst_mode"] == "INTRA" else " (inter-state)"), "color": "#2563EB", "background": "#EFF6FF"},
                {"label": "Grand Total", "value": f"{currency} {header['grand_total']:,.2f}", "foot": header["amount_in_words"], "color": "#7C3AED", "background": "#F5F3FF"},
            ])

    with stage_section("D", "TERMS, INSTRUCTIONS & PRINT SECTIONS", "Printed on the PO. Untick sections that must not print.", key="indirect_po_terms"):
        remarks = st.text_input("Remarks (printed)", value=str(source.get("remarks") or ""), key=f"ipo_remarks_{token}")
        terms = st.text_area("Terms", value=str(source.get("terms") or DEFAULT_TERMS), height=70, key=f"ipo_terms_{token}")
        instructions = st.text_area("Special Instructions", value=str(source.get("special_instructions") or DEFAULT_INDIRECT_INSTRUCTIONS), height=130, key=f"ipo_instr_{token}")
        try:
            from core.po_print_ui import effective_options, section_checkboxes
            print_options = section_checkboxes(f"ipo_sections_{token}", effective_options(source if source.get("print_options") else {}))
        except Exception:
            print_options = {}
        payload.update({"remarks": remarks, "terms": terms, "special_instructions": instructions, "print_options": print_options})

    blockers = []
    if not can_write:
        blockers.append("Indirect Purchase Create / Edit permission is not assigned")
    if not supplier:
        blockers.append("supplier is not selected")
    if not lines:
        blockers.append("no PO line")
    if not login_employee_id:
        blockers.append("your login is not linked to an ACTIVE Employee Master (needed to submit for approval)")
    revision_reason = revision_password = ""
    if current and str(current.get("status")).upper() == "APPROVED":
        section_bar("CONTROLLED REVISION OF AN APPROVED PO")
        c = st.columns(2, gap="small")
        revision_reason = c[0].text_input("Revision reason *", key=f"ipo_rev_reason_{token}")
        revision_password = c[1].text_input("Current QCMS password *", type="password", key=f"ipo_rev_pwd_{token}")
        if not (revision_reason.strip() and revision_password):
            blockers.append("revision reason and your current QCMS password (approved PO)")
    if blockers:
        st.warning("Waiting for: " + "; ".join(blockers) + ".")
    c = st.columns(3, gap="small")
    preview = c[0].button("Preview PDF (not saved)", icon=":material/preview:", width="stretch", disabled=not (supplier and lines), key=f"ipo_preview_{token}")
    revision_ok = not (current and str(current.get("status")).upper() == "APPROVED") or bool(revision_reason.strip() and revision_password)
    save_draft = c[1].button("Save as Draft", icon=":material/save:", width="stretch", disabled=not (can_write and supplier and lines and revision_ok), key=f"ipo_draft_{token}")
    submit = c[2].button("Save & Submit for Approval", type="primary", icon=":material/send:", width="stretch", disabled=bool(blockers), key=f"ipo_submit_{token}")
    if preview:
        try:
            ph, pi = service.preview_po(payload, lines)
            st.session_state["indirect_po_preview_pdf"] = build_indirect_po_pdf(ph, pi, include_terms=False)
        except Exception as exc:
            st.error(db_message(exc))
    if save_draft or submit:
        try:
            if po_id and str(current.get("status")).upper() == "APPROVED":
                from core.auth import verify_current_password
                verify_current_password(revision_password)
                service.repo.insert("qcms_password_edit_audit", {"entity_type": "INDIRECT_PO", "entity_id": po_id,
                                                                 "reason": f"Revision {int(number(current.get('revision_no'))) + 1}: {revision_reason.strip()}",
                                                                 "status_before": current.get("status")})
            if po_id:
                service.update_po(po_id, payload, lines, submit=bool(submit), submitted_by_employee_id=login_employee_id or None)
                saved = service.purchase_order(po_id)
            else:
                saved = service.create_po(payload, lines, submit=bool(submit), submitted_by_employee_id=login_employee_id or None)
                st.session_state.pop("indirect_po_prefill", None)
            st.session_state.pop("indirect_po_preview_pdf", None)
            message = f"Indirect PO {saved.get('po_number')} " + ("submitted for approval." if submit else "saved as draft.")
            if submit:
                target = service.approval_target(str(saved.get("id")))
                message += f" Approver: {target.get('employee_name') or 'any employee with Indirect Purchase Approve permission'} ({target.get('level_name')})."
            save_success_popup(message, queue_for_rerun=True)
            _go("indirect-po-list", indirect_po_open_id=str(saved.get("id")))
        except Exception as exc:
            st.error(db_message(exc))
    preview_pdf = st.session_state.get("indirect_po_preview_pdf")
    if preview_pdf:
        with st.container(border=True):
            section_bar("INDIRECT PO PREVIEW · NOT SAVED")
            _show_pdf(preview_pdf)
            c = st.columns(2, gap="small")
            c[0].download_button("Download preview PDF", preview_pdf, file_name="INDIRECT_PO_PREVIEW_NOT_SAVED.pdf", mime="application/pdf", width="stretch", key="ipo_preview_download")
            if c[1].button("Close preview", width="stretch", key="ipo_preview_close"):
                st.session_state.pop("indirect_po_preview_pdf", None); st.rerun()


# ------------------------------------------------------------------------------------------------ 5. PO register
def render_po_list() -> None:
    page_header("Indirect Purchase Order Register", "Filter, click a row to open, print / e-mail, submit, cancel or edit", CONTEXT)
    service = IndirectPurchaseService(); perms = _perms()
    login_employee_id = current_employee_id(refresh=True)
    rows = service.po_register_rows()
    frame = pd.DataFrame(rows)
    with stage_section("A", "REGISTER & FILTERS", "Click a row to open the PO below.", key="indirect_po_register"):
        if frame.empty:
            st.info("No Indirect Purchase Orders yet. Create one in Indirect PO.")
        else:
            f = render_filters(frame, "indirect_po_register", date_cols=["PO Date", "Delivery Date"],
                               default_cols=["Status", "Supplier", "Department", "PO Date"], exclude=["_id"], title="Indirect PO Register")
            f = f.reset_index(drop=True)
            st.caption(f"{len(f):,} PO(s) · value INR {f['Grand Total'].sum() if not f.empty else 0:,.2f} · overdue {int((f['Delivery'] == 'OVERDUE').sum()) if not f.empty else 0}")
            picked = _clickable(f.drop(columns=["_id"]), key="ipo_list_grid", height=460)
            if picked is not None and picked < len(f):
                st.session_state["indirect_po_open_id"] = str(f.iloc[picked]["_id"])
            report_exports(f.drop(columns=["_id"]), "Indirect Purchase Order Register", "indirect_po_register")

    headers = {str(p["id"]): p for p in service.purchase_orders()}
    if not headers:
        return
    labels = {k: f"{v.get('po_number')} · {(v.get('vendor_snapshot') or {}).get('party_name') or '-'} · {_status_text(v.get('status'))}" for k, v in headers.items()}
    requested = str(st.session_state.pop("indirect_po_open_id", "") or "")
    try:
        linked = str(st.query_params.get("ipo") or "")
    except Exception:
        linked = ""
    if linked in labels and st.session_state.get("_ipo_linked") != linked:
        st.session_state["_ipo_linked"] = linked; requested = linked
    if requested in labels:
        st.session_state["ipo_list_select"] = requested
    elif st.session_state.get("ipo_list_select") not in labels:
        st.session_state["ipo_list_select"] = next(iter(labels))
    with stage_section("B", "OPEN INDIRECT PO", "Print, e-mail, submit, cancel, attachments and history of the selected PO.", key="indirect_po_open"):
        po_id = st.selectbox("Indirect Purchase Order", list(labels), format_func=lambda v: labels[v], key="ipo_list_select")
        po = service.purchase_order(po_id)
        _po_key_info(service, po)
        status = str(po.get("status") or "").upper()
        if po.get("approval_remarks"):
            st.caption(f"Approval remarks: {po.get('approval_remarks')}")
        if status == "CANCELLED":
            st.caption(f"Cancelled: {po.get('cancellation_reason') or '-'}")
        _pdf_buttons(service, po, key=f"ipo_list_{po_id}")
        c = st.columns(4, gap="small")
        can_write = bool(perms.get("can_create") or perms.get("can_edit"))
        if c[0].button("Edit / Revise", icon=":material/edit_note:", width="stretch", key=f"ipo_list_edit_{po_id}",
                       disabled=not can_write or status not in {"DRAFT", "PENDING_APPROVAL", "REJECTED", "APPROVED"}):
            _go("indirect-po", indirect_po_edit_id=po_id)
        if c[1].button("Submit for Approval", icon=":material/send:", width="stretch", key=f"ipo_list_submit_{po_id}",
                       disabled=not can_write or status not in {"DRAFT", "REJECTED"}):
            try:
                service.submit_po(po_id, login_employee_id)
                save_success_popup("Indirect PO submitted for approval.", queue_for_rerun=True); st.rerun()
            except Exception as exc:
                st.error(db_message(exc))
        if c[2].button("Open Approval", icon=":material/approval:", width="stretch", key=f"ipo_list_appr_{po_id}", disabled=status != "PENDING_APPROVAL"):
            _go("indirect-po-approval", indirect_po_approval_id=po_id)
        if c[3].button("Receive (GRN)", icon=":material/input:", width="stretch", key=f"ipo_list_grn_{po_id}", disabled=status not in OPEN_PO_STATUSES):
            _go("indirect-inward", indirect_grn_po_id=po_id)
        if str(po.get("approval_status")).upper() == "APPROVED":
            _email_panel(service, related_table="indirect_purchase_orders", related_id=po_id, header=po, purpose="SUPPLIER", key=f"ipo_mail_{po_id}",
                         to_default=str((po.get("vendor_snapshot") or {}).get("email") or service.party(po.get("supplier_id")).get("email") or ""),
                         title="E-MAIL APPROVED PO TO SUPPLIER", disabled=not can_write)
        if st.toggle("Cancel this PO", value=False, key=f"ipo_cancel_open_{po_id}"):
            reason = st.text_input("Cancellation reason", key=f"ipo_cancel_reason_{po_id}")
            if st.button("Cancel Indirect PO", width="stretch", key=f"ipo_cancel_{po_id}", disabled=not can_write or status in {"CLOSED", "CANCELLED"}):
                try:
                    service.cancel_po(po_id, reason, login_employee_id)
                    save_success_popup("Indirect PO cancelled.", queue_for_rerun=True); st.rerun()
                except Exception as exc:
                    st.error(db_message(exc))
        log = service.approval_log(po_id)
        if log:
            section_bar("APPROVAL HISTORY")
            portal_table(pd.DataFrame([{"When": str(r.get("created_at") or "")[:19].replace("T", " "), "Level": r.get("level_name") or r.get("level_no"),
                                        "Action": r.get("action"), "By": employee_name(service.employee(r.get("employee_id"))), "Remarks": r.get("remarks") or ""} for r in log]),
                         hide_index=True, width="stretch", height=min(260, 90 + 36 * len(log)))
        try:
            from core.attachments import AttachmentSlot, render_attachment_manager
            render_attachment_manager(repo=service.repo, entity_type="INDIRECT_PO", entity_id=po_id, folder="indirect-po",
                                      slots=(AttachmentSlot("SUPPLIER_QUOTATION", "Supplier Quotation", "Quotation / offer"),
                                             AttachmentSlot("COMPARISON", "Comparison / Approval Note", "Quotation comparison or approval note"),
                                             AttachmentSlot("PO_ACKNOWLEDGEMENT", "Supplier Acknowledgement", "Supplier order confirmation")),
                                      key_prefix=f"ipo_att_{po_id}", can_add_or_replace=can_write, can_delete=bool(perms.get("can_archive")), title="ATTACHMENTS")
        except Exception:
            pass
        try:
            from core.record_history import record_history_panel
            record_history_panel(service.repo, "indirect_purchase_orders", po, key=f"ipo_history_{po_id}")
        except Exception:
            pass


# ------------------------------------------------------------------------------------------------ 6. approval
def render_po_approval() -> None:
    page_header("Indirect PO Approval", "Approve or reject with remarks; levels by value from the INDIRECT_PURCHASE approval route, else the Reports-To manager", CONTEXT)
    service = IndirectPurchaseService(); perms = _perms()
    profile = current_profile() or {}
    login_employee_id = current_employee_id(refresh=True)
    pending = service.pending_approval_rows()
    mine = [r for r in pending if login_employee_id and str(service.approval_target(str(r["_id"])).get("employee_id") or "") == str(login_employee_id)]
    kpi_grid([
        {"label": "Pending Approval", "value": len(pending), "foot": f"Value INR {sum(number(r['Grand Total']) for r in pending):,.0f}", "color": "#B45309", "background": "#FFFBEB"},
        {"label": "Waiting for Me", "value": len(mine), "foot": "Route / Reports-To resolves to you", "color": "#2563EB", "background": "#EFF6FF"},
        {"label": "Overdue (> 1 day)", "value": sum(1 for r in pending if r["Pending Days"] >= 1), "foot": "Submitted more than a day ago", "color": "#B91C1C", "background": "#FEF2F2"},
    ])
    with stage_section("A", "PENDING APPROVAL WORKLIST", "Click a row to open it below.", key="indirect_po_worklist"):
        frame = pd.DataFrame(pending)
        picked = _clickable(frame.drop(columns=["_id"]) if not frame.empty else frame, key="ipo_appr_grid", height=360)
        if picked is not None and picked < len(pending):
            st.session_state["indirect_po_approval_id"] = str(pending[picked]["_id"])
    if pending:
        labels = {str(r["_id"]): f"{r['IPO Number']} · {r['Supplier']} · INR {r['Grand Total']:,.2f} · {r['Approval Level']}" for r in pending}
        requested = str(st.session_state.pop("indirect_po_approval_id", "") or "")
        try:
            linked = str(st.query_params.get("ipo") or "")
        except Exception:
            linked = ""
        if linked in labels and st.session_state.get("_ipo_appr_linked") != linked:
            st.session_state["_ipo_appr_linked"] = linked; requested = linked
        if requested in labels:
            st.session_state["ipo_appr_select"] = requested
        elif st.session_state.get("ipo_appr_select") not in labels:
            st.session_state["ipo_appr_select"] = next(iter(labels))
        with stage_section("B", "REVIEW & DECIDE", "Check the PO as the supplier will receive it, then approve or reject with remarks.", key="indirect_po_decide"):
            po_id = st.selectbox("Indirect PO", list(labels), format_func=lambda v: labels[v], key="ipo_appr_select")
            po = service.purchase_order(po_id)
            _po_key_info(service, po)
            target = service.approval_target(po_id)
            levels = target.get("levels") or [1]
            st.info(f"Required approver: **{target.get('employee_name') or 'any employee with Indirect Purchase Approve permission (not the submitter)'}** · "
                    f"{target.get('level_name')} · route {str(target.get('source') or '').replace('_', ' ').title()} · levels for this value: {', '.join(str(v) for v in levels)}")
            allowed = _is_admin() or (bool(target.get("employee_id")) and str(target.get("employee_id")) == str(login_employee_id)) or (
                not target.get("employee_id") and bool(login_employee_id) and str(login_employee_id) != str(po.get("submitted_by_employee_id") or ""))
            _pdf_buttons(service, po, key=f"ipo_appr_{po_id}")
            remarks = st.text_input("Approval / rejection remarks", key=f"ipo_appr_remarks_{po_id}")
            send_now = st.toggle("After final approval, e-mail the PO to the supplier", value=False, key=f"ipo_appr_send_{po_id}")
            c = st.columns(2, gap="small")
            if c[0].button("Approve", type="primary", icon=":material/verified:", width="stretch", key=f"ipo_appr_go_{po_id}", disabled=not (perms.get("can_approve") and allowed)):
                try:
                    result = service.approve_po(po_id, remarks)
                    if result.get("next_level"):
                        save_success_popup(f"Level approved. The PO moves to approval level {result.get('next_level')}.", queue_for_rerun=True)
                    else:
                        message = f"Indirect PO {result.get('po_number')} approved."
                        email = str((po.get("vendor_snapshot") or {}).get("email") or service.party(po.get("supplier_id")).get("email") or "").strip()
                        if send_now and "@" in email:
                            approved = service.purchase_order(po_id)
                            subject, body = po_email_text(approved)
                            notifier = indirect_notifier(service.repo)
                            row = notifier.enqueue("INDIRECT_PO_RELEASED", subject=subject, body_text=body, related_table="indirect_purchase_orders", related_id=po_id,
                                                   recipient_email=email, include_supplier=False, include_generated_pdf=True, include_record_attachments=False)
                            notifier.dispatch([row] if row else [])
                            message += f" E-mailed to {email}."
                        elif send_now:
                            message += " Supplier e-mail is not configured – send it later from the register."
                        save_success_popup(message, queue_for_rerun=True)
                    st.rerun()
                except Exception as exc:
                    st.error(db_message(exc))
            if c[1].button("Reject", icon=":material/block:", width="stretch", key=f"ipo_appr_reject_{po_id}", disabled=not (perms.get("can_approve") and allowed)):
                try:
                    service.reject_po(po_id, remarks)
                    save_success_popup("Indirect PO rejected; the requisitioner can revise and resubmit it.", queue_for_rerun=True); st.rerun()
                except Exception as exc:
                    st.error(db_message(exc))
            if not allowed:
                st.caption("You are not the resolved approver for this level.")
            _email_panel(service, related_table="indirect_purchase_orders", related_id=po_id, header=po, purpose="APPROVAL", key=f"ipo_appr_mail_{po_id}",
                         to_default=str(target.get("email") or ""), title="E-MAIL DRAFT PO TO APPROVER (PENDING APPROVAL watermark)")
    else:
        st.success("No Indirect Purchase Order is pending approval.")

    if _is_admin() or str(profile.get("role") or "").upper() == "MANAGEMENT":
        with stage_section("C", "APPROVAL ROUTE · INDIRECT_PURCHASE", "Up to 3 levels. A level applies when the PO grand total ≥ its minimum amount; department-specific rows win over all-department rows.", key="indirect_po_routes"):
            routes = service.approval_routes()
            emp_labels = _employee_labels(service)
            if routes:
                portal_table(pd.DataFrame([{"Level": r.get("level_no"), "Level Name": r.get("level_name"), "Department": r.get("department") or "All",
                                            "Min Amount": number(r.get("min_amount")), "Approver": emp_labels.get(str(r.get("employee_id")), "-"),
                                            "Overdue After (h)": r.get("overdue_after_hours") or 24, "Status": r.get("status")} for r in routes]), hide_index=True, width="stretch", height=260)
            else:
                st.caption("No route configured – the submitter's Reports-To manager approves; else any different employee with Approve permission.")
            with st.form("ipo_route_form"):
                c = st.columns(3, gap="small")
                level = c[0].selectbox("Level", [1, 2, 3])
                level_name = c[1].text_input("Level name", value="Purchase Head Approval")
                min_amount = c[2].number_input("Applies from amount (INR)", min_value=0.0, value=0.0, step=1000.0)
                c = st.columns(3, gap="small")
                emp_keys = list(emp_labels)
                employee = c[0].selectbox("Approver", emp_keys or [""], format_func=lambda v: emp_labels.get(v, "-"))
                dept = c[1].selectbox("Department", ["", *service.departments()], format_func=lambda v: v or "All departments")
                hours = c[2].number_input("Overdue after (hours)", min_value=1, max_value=720, value=24)
                if st.form_submit_button("Save route level", type="primary", width="stretch"):
                    try:
                        service.save_route(level_no=int(level), employee_id=employee, level_name=level_name, department=dept, min_amount=min_amount, overdue_after_hours=int(hours))
                        save_success_popup("Approval route saved.", queue_for_rerun=True); st.rerun()
                    except Exception as exc:
                        st.error(db_message(exc))
            if routes:
                route_labels = {str(r["id"]): f"L{r.get('level_no')} · {r.get('department') or 'All'} · {emp_labels.get(str(r.get('employee_id')), '-')}" for r in routes}
                drop = st.selectbox("Deactivate a route level", ["", *route_labels], format_func=lambda v: route_labels.get(v, "—"), key="ipo_route_drop")
                if st.button("Deactivate", width="stretch", disabled=not drop, key="ipo_route_drop_go"):
                    try:
                        service.deactivate_route(drop)
                        save_success_popup("Route level deactivated.", queue_for_rerun=True); st.rerun()
                    except Exception as exc:
                        st.error(db_message(exc))


# ------------------------------------------------------------------------------------------------ 7. inward (GRN)
def _grn_header_inputs(service: IndirectPurchaseService, *, key: str, login_employee: Mapping[str, Any], department: str = "") -> dict[str, Any]:
    c = st.columns(4, gap="small")
    grn_date = c[0].date_input("Receipt Date", value=date.today(), format="DD-MM-YYYY", key=f"{key}_date")
    invoice = c[1].text_input("Supplier Invoice No.", key=f"{key}_inv")
    invoice_date = c[2].date_input("Invoice Date", value=date.today(), format="DD-MM-YYYY", key=f"{key}_invdate")
    vehicle = c[3].text_input("Vehicle No.", key=f"{key}_vehicle")
    c = st.columns(4, gap="small")
    challan = c[0].text_input("Delivery Challan No.", key=f"{key}_dc")
    challan_date = c[1].date_input("Challan Date", value=date.today(), format="DD-MM-YYYY", key=f"{key}_dcdate")
    location = c[2].text_input("Storage Location", key=f"{key}_loc")
    received_by = c[3].text_input("Received By", value=employee_name(login_employee), key=f"{key}_rcvd")
    c = st.columns([1, 1, 2], gap="small")
    gate_no = c[0].text_input("Gate Entry No.", key=f"{key}_gate")
    gate_date = c[1].date_input("Gate Entry Date", value=date.today(), format="DD-MM-YYYY", key=f"{key}_gatedate")
    remarks = c[2].text_input("Remarks", key=f"{key}_remarks")
    return {"gate_entry_no": gate_no, "gate_entry_date": gate_date if gate_no else None,"grn_date": grn_date, "supplier_invoice_no": invoice, "supplier_invoice_date": invoice_date if invoice else None, "vehicle_no": vehicle,
            "challan_no": challan, "challan_date": challan_date if challan else None, "storage_location": location, "received_by_name": received_by,
            "received_by_employee_id": login_employee.get("id"), "remarks": remarks, "department": department}


def render_inward() -> None:
    page_header("Indirect Inward (GRN)", "Receive against an approved Indirect PO, or petty-cash / without-PO receipts with approval; posts the indirect stock ledger", CONTEXT)
    service = IndirectPurchaseService(); perms = _perms()
    login_employee_id = current_employee_id(refresh=True)
    login_employee = service.employee(login_employee_id)
    can_write = bool(perms.get("can_create") or perms.get("can_edit"))

    with stage_section("A", "GRN AGAINST INDIRECT PO", "Received = Accepted + Rejected (reason required). Received cannot exceed the pending PO quantity plus the PO's over-receipt tolerance.", key="indirect_grn_po"):
        open_pos = {str(p["id"]): p for p in service.open_pos_for_grn()}
        if not open_pos:
            st.info("No approved, open Indirect PO is waiting for receipt.")
        else:
            labels = {k: f"{v.get('po_number')} · {(v.get('vendor_snapshot') or {}).get('party_name') or '-'} · delivery {v.get('delivery_date') or '-'} · {_status_text(v.get('status'))}" for k, v in open_pos.items()}
            requested = str(st.session_state.pop("indirect_grn_po_id", "") or "")
            if requested in labels:
                st.session_state["igrn_po_select"] = requested
            po_id = st.selectbox("Approved Indirect PO", list(labels), format_func=lambda v: labels[v], key="igrn_po_select")
            po = service.purchase_order(po_id)
            pending = service.po_pending_lines(po_id)
            frame = pd.DataFrame([{"Line": l.get("line_no"), "Item": f"{l.get('item_code') or ''} {l.get('item_name')}".strip(), "UOM": l.get("uom"),
                                   "Ordered": number(l.get("quantity")), "Accepted so far": number(l.get("po_accepted_qty")), "Pending": l["pending_qty"], "Max Receivable": l["max_receivable_qty"],
                                   "Received": l["pending_qty"], "Accepted": l["pending_qty"], "Rejected": 0.0, "Rejection Reason": "", "Location": "", "_id": str(l["id"])} for l in pending])
            edited = st.data_editor(frame, hide_index=True, width="stretch", key=f"igrn_lines_{po_id}",
                                    disabled=["Line", "Item", "UOM", "Ordered", "Accepted so far", "Pending", "Max Receivable"],
                                    column_config={"_id": None, "Received": st.column_config.NumberColumn(min_value=0.0, format="%.3f"),
                                                   "Accepted": st.column_config.NumberColumn(min_value=0.0, format="%.3f"),
                                                   "Rejected": st.column_config.NumberColumn(min_value=0.0, format="%.3f")})
            header = _grn_header_inputs(service, key=f"igrn_{po_id}", login_employee=login_employee, department=str(po.get("department") or ""))
            if st.button("Post GRN", type="primary", icon=":material/inventory:", width="stretch", key=f"igrn_post_{po_id}", disabled=not can_write):
                by_id = {str(l["id"]): l for l in pending}
                lines = []
                for _, r in edited.iterrows():
                    src = by_id.get(str(r.get("_id"))) or {}
                    lines.append({**src, "po_item_id": src.get("id"), "received_qty": number(r.get("Received")), "accepted_qty": number(r.get("Accepted")),
                                  "rejected_qty": number(r.get("Rejected")), "rejection_reason": clean(r.get("Rejection Reason")) if not pd.isna(r.get("Rejection Reason")) else "",
                                  "storage_location": clean(r.get("Location")) if not pd.isna(r.get("Location")) else ""})
                try:
                    grn = service.create_grn({**header, "grn_type": "AGAINST_PO", "purchase_order_id": po_id}, lines)
                    save_success_popup(f"GRN {grn.get('grn_number')} posted · PO status {_status_text(grn.get('po_status'))}. Stock updated.", queue_for_rerun=True)
                    st.session_state["igrn_open_id"] = str(grn.get("id")); st.rerun()
                except Exception as exc:
                    st.error(db_message(exc))

    with stage_section("B", "GRN WITHOUT PO · PETTY CASH / CASH PURCHASE", "Saved as Pending Approval; stock is posted when another employee with Approve permission approves it.", key="indirect_grn_nopo"):
        supplier_labels = _supplier_labels(service)
        item_labels = _item_labels(service)
        reverse_items = {v: k for k, v in item_labels.items()}
        c = st.columns(3, gap="small")
        sup = c[0].selectbox("Supplier (Party Master)", ["", *supplier_labels], format_func=lambda v: supplier_labels.get(v, "— not in master —"), key="igrn_np_supplier")
        shop = c[1].text_input("Shop / supplier name (if not in master)", key="igrn_np_shop")
        payment_mode = c[2].selectbox("Payment", ["PETTY_CASH", "CASH", "CREDIT", "CARD / UPI"], key="igrn_np_payment")
        branch_labels, default_branch = _branch_options(service)
        c = st.columns(2, gap="small")
        branch = c[0].selectbox("Company Branch / Plant", list(branch_labels) or [""], format_func=lambda v: branch_labels.get(v, "-"),
                                index=list(branch_labels).index(default_branch) if default_branch in branch_labels else 0, key="igrn_np_branch")
        with c[1]:
            department = _department_input(service, "Department", key="igrn_np_dept", default=clean(login_employee.get("department")))
        blank = pd.DataFrame([{"Item": None, "Description": "", "UOM": "NOS", "Received": 1.0, "Accepted": 1.0, "Rejected": 0.0, "Rejection Reason": "", "Rate": 0.0, "GST %": 18.0} for _ in range(2)])
        edited = st.data_editor(blank, num_rows="dynamic", hide_index=True, width="stretch", key="igrn_np_lines", column_config={
            "Item": st.column_config.SelectboxColumn("Item (master)", options=list(item_labels.values()), width="large"),
            "UOM": st.column_config.SelectboxColumn(options=list(UOMS)), "GST %": st.column_config.SelectboxColumn(options=list(GST_RATES)),
            "Received": st.column_config.NumberColumn(min_value=0.0, format="%.3f"), "Accepted": st.column_config.NumberColumn(min_value=0.0, format="%.3f"),
            "Rejected": st.column_config.NumberColumn(min_value=0.0, format="%.3f"), "Rate": st.column_config.NumberColumn(min_value=0.0, format="%.2f")})
        header = _grn_header_inputs(service, key="igrn_np", login_employee=login_employee, department=department)
        if st.button("Save GRN for Approval", type="primary", width="stretch", key="igrn_np_save", disabled=not can_write):
            lines = []
            for _, r in edited.iterrows():
                item_id = reverse_items.get(str(r.get("Item") or ""))
                item = service.item(item_id) if item_id else {}
                desc = clean(r.get("Description")) if not pd.isna(r.get("Description")) else ""
                if not item_id and not desc:
                    continue
                lines.append({"item_id": item_id, "item_code": item.get("item_code"), "item_name": item.get("item_name") or desc, "description": desc or None,
                              "uom": item.get("uom") or r.get("UOM"), "received_qty": number(r.get("Received")), "accepted_qty": number(r.get("Accepted")),
                              "rejected_qty": number(r.get("Rejected")), "rejection_reason": clean(r.get("Rejection Reason")) if not pd.isna(r.get("Rejection Reason")) else "",
                              "rate": number(r.get("Rate")), "gst_percent": number(r.get("GST %"))})
            try:
                grn = service.create_grn({**header, "grn_type": "WITHOUT_PO", "supplier_id": sup or None, "supplier_name": shop, "payment_mode": payment_mode,
                                          "company_branch_id": branch or None}, lines)
                save_success_popup(f"GRN {grn.get('grn_number')} saved and sent for approval.", queue_for_rerun=True); st.rerun()
            except Exception as exc:
                st.error(db_message(exc))

    with stage_section("C", "GRN APPROVAL (WITHOUT PO)", "Self-approval is blocked.", key="indirect_grn_approval"):
        waiting = [g for g in service.grns() if str(g.get("status") or "").upper() == "PENDING_APPROVAL"]
        if not waiting:
            st.caption("No GRN is waiting for approval.")
        for g in waiting:
            with st.container(border=True):
                st.markdown(f"**{g.get('grn_number')}** · {g.get('supplier_name') or '-'} · INR {number(g.get('grand_total')):,.2f} · {g.get('department') or '-'} · received by {g.get('received_by_name') or '-'}")
                items = service.grn_items(g["id"])
                portal_table(pd.DataFrame([{"Item": i.get("item_name"), "UOM": i.get("uom"), "Accepted": number(i.get("accepted_qty")), "Rejected": number(i.get("rejected_qty")),
                                            "Rate": number(i.get("rate")), "Amount": number(i.get("amount"))} for i in items]), hide_index=True, width="stretch", height=min(240, 90 + 36 * len(items)))
                remark = st.text_input("Remarks", key=f"igrn_dec_rem_{g['id']}")
                c = st.columns(2, gap="small")
                for col, approve in ((c[0], True), (c[1], False)):
                    if col.button("Approve & post stock" if approve else "Reject", type="primary" if approve else "secondary", width="stretch",
                                  key=f"igrn_dec_{'a' if approve else 'r'}_{g['id']}", disabled=not perms.get("can_approve")):
                        try:
                            service.decide_grn(str(g["id"]), approve, remark)
                            save_success_popup("GRN approved and stock posted." if approve else "GRN rejected.", queue_for_rerun=True); st.rerun()
                        except Exception as exc:
                            st.error(db_message(exc))

    with stage_section("D", "GRN REGISTER & PRINT", "Click a row to print the GRN.", key="indirect_grn_register"):
        rows = service.grn_register_rows()
        frame = pd.DataFrame(rows)
        if not frame.empty:
            frame = render_filters(frame, "indirect_grn_register", date_cols=["GRN Date"], default_cols=["Status", "Supplier", "GRN Date"],
                                   exclude=["_id"], title="Indirect GRN Register").reset_index(drop=True)
        rows = frame.to_dict("records") if not frame.empty else []
        picked = _clickable(frame.drop(columns=["_id"]) if not frame.empty else frame, key="igrn_grid", height=360)
        if picked is not None and picked < len(rows):
            st.session_state["igrn_open_id"] = str(rows[picked]["_id"])
        if not frame.empty:
            report_exports(frame.drop(columns=["_id"]), "Indirect GRN Register", "indirect_grn_register")
        if rows:
            labels = {str(r["_id"]): f"{r['GRN Number']} · {r['Supplier']} · {r['Status']}" for r in rows}
            if st.session_state.get("igrn_open_id") in labels:
                st.session_state["igrn_print_select"] = st.session_state.pop("igrn_open_id")
            gid = st.selectbox("GRN", list(labels), format_func=lambda v: labels[v], key="igrn_print_select")
            grn = service.grn(gid)
            try:
                pdf = indirect_grn_pdf_bytes(gid, service.repo)
                st.download_button("Download / Print GRN", pdf, file_name=f"{grn.get('grn_number')}.pdf", mime="application/pdf", icon=":material/picture_as_pdf:",
                                   type="primary", width="stretch", key=f"igrn_pdf_{gid}")
            except Exception as exc:
                st.error(db_message(exc))
            try:
                from core.attachments import AttachmentSlot, render_attachment_manager
                render_attachment_manager(repo=service.repo, entity_type="INDIRECT_GRN", entity_id=gid, folder="indirect-grn",
                                          slots=(AttachmentSlot("SUPPLIER_INVOICE", "Supplier Invoice / Bill", "Invoice or cash bill"),
                                                 AttachmentSlot("DELIVERY_CHALLAN", "Delivery Challan", "Supplier challan")),
                                          key_prefix=f"igrn_att_{gid}", can_add_or_replace=can_write, can_delete=bool(perms.get("can_archive")), title="GRN ATTACHMENTS")
            except Exception:
                pass


# ------------------------------------------------------------------------------------------------ 8. stock
def render_stock() -> None:
    page_header("Indirect Stock & Issue", "Store balance of indirect stock items, item ledger with running balance, and issue to departments", CONTEXT)
    service = IndirectPurchaseService(); perms = _perms()
    login_employee_id = current_employee_id(refresh=True)
    can_write = bool(perms.get("can_create") or perms.get("can_edit"))
    branch_labels, default_branch = _branch_options(service)
    branch_keys = ["", *branch_labels]
    branch = st.selectbox("Company Branch / Plant", branch_keys, index=branch_keys.index(default_branch) if default_branch in branch_keys else 0,
                          format_func=lambda v: branch_labels.get(v, "All branches"), key="istock_branch")
    rows = service.stock_rows(branch_id=branch or None)
    alerts = [r for r in rows if r["Stock Alert"]]
    kpi_grid([
        {"label": "Stock Items", "value": len(rows), "foot": "Active + inactive stock items", "color": "#0B6E70", "background": "#E3F2F2"},
        {"label": "Stock Value", "value": f"INR {sum(r['Stock Value'] for r in rows):,.0f}", "foot": "Balance × last price", "color": "#7C3AED", "background": "#F5F3FF"},
        {"label": "Reorder / Min Alerts", "value": len(alerts), "foot": "At or below reorder / minimum", "color": "#B91C1C", "background": "#FEF2F2"},
    ])
    with stage_section("A", "STOCK SUMMARY", "Click a row to open the item ledger.", key="indirect_stock_summary"):
        alerts_only = st.toggle("Alerts only (reorder / below min / above max)", key="istock_alerts")
        frame = pd.DataFrame([r for r in rows if not alerts_only or r["Stock Alert"]])
        if not frame.empty:
            frame = render_filters(frame, "indirect_stock_summary", default_cols=["Category", "Stock Alert"], exclude=["_id"],
                                   title="Indirect Stock").reset_index(drop=True)
        shown = frame.to_dict("records") if not frame.empty else []
        picked = _clickable(frame.drop(columns=["_id"]) if not frame.empty else frame, key="istock_grid", height=420)
        if picked is not None and picked < len(shown):
            st.session_state["istock_item"] = str(shown[picked]["_id"])
        if not frame.empty:
            report_exports(frame.drop(columns=["_id"]), "Indirect Item Stock", "indirect_stock_summary")
    item_labels = {str(r["id"]): f"{r.get('item_code')} · {r.get('item_name')} · {r.get('uom')}" for r in service.items() if r.get("is_stock_item", True)}
    with stage_section("B", "ITEM LEDGER", "Every receipt (GRN), issue, return and adjustment with the running balance.", key="indirect_stock_ledger"):
        if item_labels:
            if st.session_state.get("istock_item") not in item_labels:
                st.session_state["istock_item"] = next(iter(item_labels))
            item_id = st.selectbox("Item", list(item_labels), format_func=lambda v: item_labels[v], key="istock_item")
            ledger = service.ledger(item_id=item_id, branch_id=branch or None)
            balance = 0.0; data = []
            for r in ledger:
                balance += number(r.get("qty_in")) - number(r.get("qty_out"))
                data.append({"Date": r.get("txn_date"), "Type": r.get("txn_type"), "Reference": r.get("reference_no") or "-", "In": number(r.get("qty_in")),
                             "Out": number(r.get("qty_out")), "Balance": round(balance, 4), "Department": r.get("department") or "-",
                             "Cost Centre": r.get("cost_centre") or "-", "Issued To": employee_name(service.employee(r.get("issued_to_employee_id"))) or "-",
                             "Remarks": r.get("remarks") or ""})
            portal_table(pd.DataFrame(list(reversed(data))), hide_index=True, width="stretch", height=380)
        else:
            st.info("No stock item in the Indirect Item Master.")
    with stage_section("C", "ISSUE TO DEPARTMENT / RETURN", "Issue consumes stock (cannot go below zero); Return brings unused material back to store.", key="indirect_stock_issue"):
        if item_labels:
            emp_labels = _employee_labels(service)
            with st.form("istock_issue_form"):
                c = st.columns(3, gap="small")
                item_id = c[0].selectbox("Item", list(item_labels), format_func=lambda v: item_labels[v])
                txn = c[1].selectbox("Transaction", ["ISSUE", "RETURN"])
                qty = c[2].number_input("Quantity", min_value=0.0, value=1.0, step=1.0, format="%.3f")
                c = st.columns(4, gap="small")
                departments = service.departments() or [""]
                dept = c[0].selectbox("Department", departments)
                cost_centre = c[1].text_input("Cost Centre")
                emp_keys = ["", *emp_labels]
                issued_to = c[2].selectbox("Issued to (employee)", emp_keys, format_func=lambda v: emp_labels.get(v, "—"))
                issue_date = c[3].date_input("Date", value=date.today(), format="DD-MM-YYYY")
                remarks = st.text_input("Remarks / purpose")
                if st.form_submit_button("Post Issue / Return", type="primary", width="stretch", disabled=not can_write):
                    try:
                        row = service.issue_stock(item_id=item_id, qty=qty, branch_id=branch or default_branch or None, department=dept, cost_centre=cost_centre,
                                                  employee_id=issued_to or None, issue_date=issue_date, remarks=remarks, txn_type=txn)
                        save_success_popup(f"{txn.title()} {row.get('reference_no')} posted · balance {number(row.get('balance_after')):g}.", queue_for_rerun=True); st.rerun()
                    except Exception as exc:
                        st.error(db_message(exc))
    if perms.get("can_edit") or _is_admin():
        with stage_section("D", "OPENING STOCK / ADJUSTMENT", "Opening balance when the module starts; adjustment (+/−) after a physical stock count.", key="indirect_stock_adjust"):
            if item_labels:
                with st.form("istock_adjust_form"):
                    c = st.columns(3, gap="small")
                    item_id = c[0].selectbox("Item", list(item_labels), format_func=lambda v: item_labels[v])
                    txn = c[1].selectbox("Type", ["OPENING", "ADJUSTMENT"])
                    qty = c[2].number_input("Quantity (adjustment may be negative)", value=0.0, step=1.0, format="%.3f")
                    remarks = st.text_input("Reason / stock count reference")
                    if st.form_submit_button("Post", type="primary", width="stretch"):
                        try:
                            row = service.issue_stock(item_id=item_id, qty=qty, branch_id=branch or default_branch or None, department="", employee_id=login_employee_id or None,
                                                      remarks=remarks, txn_type=txn)
                            save_success_popup(f"{txn.title()} posted · balance {number(row.get('balance_after')):g}.", queue_for_rerun=True); st.rerun()
                        except Exception as exc:
                            st.error(db_message(exc))
