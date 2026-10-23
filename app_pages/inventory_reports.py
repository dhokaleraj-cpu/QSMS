"""QCMS R36b · Inventory & Stock Reports.

Five report tabs, each with filters (core.report_filters), KPI cards, a totals row,
responsive grids and Excel / PDF export of the filtered rows:

a) Stock by stage per part   – public.qcms_stock_by_stage() (same formulas as qcms_part_stage_stock, all parts at once)
b) Raw material stock by heat / grade / section – v_qcms_rm_stock_by_heat
c) Forging / OSP stock by supplier – v_qcms_forging_stock_by_supplier + v_qsms_osp_register
d) FG stock & customer dispatch summary
e) Date-wise stock movement ledger – v_qcms_stock_movement_ledger
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd
import streamlit as st

from core.report_filters import render_filters, report_exports, totals_row
from core.repository import Repository
from core.ui import kpi_grid, page_header, portal_table, section_bar, subpage_navigation

ROW_LIMIT = 20000

STAGE_COLUMNS: dict[str, str] = {
    "Part Number": "part_number",
    "FSI Part Number": "fsi_part_number",
    "Part Description": "part_name",
    "Customer": "customer_name",
    "Material Grade": "material_grade",
    "Open Orders": "open_orders",
    "Open Order Qty pcs": "open_order_qty_pcs",
    "Pending Order pcs": "pending_order_pcs",
    "RM Required kg": "rm_required_kg",
    "RM Ordered kg": "rm_ordered_kg",
    "RM Received kg": "rm_received_kg",
    "RM Pending Receipt kg": "rm_pending_receipt_kg",
    "RM at FSI kg": "rm_at_fsi_kg",
    "RM Sent to Forger kg": "rm_sent_to_forger_kg",
    "RM at Forger kg": "rm_at_forger_kg",
    "Forgings Ordered pcs": "forging_ordered_pcs",
    "Forgings Pending at Forger pcs": "forging_pending_at_forger_pcs",
    "Forgings Received pcs": "forging_received_pcs",
    "Forgings Rejected pcs": "forging_rejected_pcs",
    "Machining WIP pcs": "machining_wip_pcs",
    "Machined pcs": "machined_pcs",
    "Machined Pending FG pcs": "machined_pending_fg_pcs",
    "FG Produced pcs": "fg_produced_pcs",
    "FG Stock pcs": "fg_stock_pcs",
    "Dispatched pcs": "dispatched_pcs",
    "Opening RM kg": "opening_rm_kg",
    "Opening Forging pcs": "opening_forging_pcs",
    "Opening Machining pcs": "opening_machining_pcs",
    "Opening FG pcs": "opening_fg_pcs",
    "Last Activity": "last_activity_date",
}
STAGE_SEQUENCE: tuple[tuple[str, str, str], ...] = (
    ("Open customer orders", "Pending Order pcs", "pcs"),
    ("RM ordered", "RM Ordered kg", "kg"),
    ("RM pending receipt", "RM Pending Receipt kg", "kg"),
    ("RM at FSI", "RM at FSI kg", "kg"),
    ("RM at forger", "RM at Forger kg", "kg"),
    ("Forging pending at forger", "Forgings Pending at Forger pcs", "pcs"),
    ("Forgings received", "Forgings Received pcs", "pcs"),
    ("Machining WIP", "Machining WIP pcs", "pcs"),
    ("Machined, pending FG", "Machined Pending FG pcs", "pcs"),
    ("Finished goods stock", "FG Stock pcs", "pcs"),
    ("Dispatched to customer", "Dispatched pcs", "pcs"),
)
ACTIVITY_COLUMNS = tuple(label for label in STAGE_COLUMNS if label.endswith((" kg", " pcs")) or label == "Open Orders")

RM_COLUMNS: dict[str, str] = {
    "Heat Number": "heat_number", "Heat Code": "heat_code", "Material Grade": "material_grade", "RM Section": "rm_section",
    "Supplier": "supplier_name", "RMTC": "rmtc_number", "Part Number(s)": "part_numbers", "FSI Part Number(s)": "fsi_part_numbers",
    "Opening kg": "opening_kg", "Received kg": "received_kg", "Dispatched to Forger kg": "dispatched_kg", "Balance kg": "balance_kg",
    "Last Movement": "last_movement_date",
}
FORGING_COLUMNS: dict[str, str] = {
    "Forging Supplier": "supplier_name", "Supplier Code": "supplier_code", "Part Number": "part_number", "FSI Part Number": "fsi_part_number",
    "Part Description": "part_name", "Customer": "customer_name", "Material Grade": "material_grade",
    "RM Sent kg": "rm_sent_kg", "RM Consumed kg": "rm_consumed_kg", "RM at Forger kg": "rm_at_forger_kg",
    "Forgings Ordered pcs": "forging_ordered_pcs", "Forgings Received pcs": "forging_received_pcs",
    "Forgings Rejected pcs": "forging_rejected_pcs", "Forgings Pending pcs": "forging_pending_pcs", "Last Movement": "last_movement_date",
}
OSP_COLUMNS: dict[str, str] = {
    "OSP Vendor": "vendor_name", "OSP Job": "osp_job_number", "Part Number": "part_number", "Heat Number": "heat_number",
    "OSP Process": "process_name", "Material Out Date": "dispatch_date", "Out Challan": "dispatch_challan",
    "Out Qty pcs": "quantity_dispatched", "Received pcs": "quantity_received", "Pending Return pcs": "quantity_outstanding",
    "Expected Return": "expected_return_date", "Status": "status",
}
LEDGER_COLUMNS: dict[str, str] = {
    "Date": "movement_date", "Movement": "movement_type", "Stage": "stage", "Direction": "direction",
    "Part Number": "part_number", "FSI Part Number": "fsi_part_number", "Part Description": "part_name", "Customer": "customer_name",
    "Material Grade": "material_grade", "Heat Number": "heat_number", "Supplier / Party": "party_name", "Reference": "reference_no",
    "Customer Order": "customer_order_no", "Qty kg": "qty_kg", "Qty pcs": "qty_pcs",
    "kg In": "kg_in", "kg Out": "kg_out", "pcs In": "pcs_in", "pcs Out": "pcs_out",
}


# ----------------------------------------------------------------------------- data helpers
def _frame(rows: Sequence[Mapping[str, Any]] | None, columns: Mapping[str, str]) -> pd.DataFrame:
    frame = pd.DataFrame([{label: (row or {}).get(source) for label, source in columns.items()} for row in rows or []], columns=list(columns))
    for label in frame.columns:
        if label.endswith((" kg", " pcs")) or label in {"Open Orders"}:
            frame[label] = pd.to_numeric(frame[label], errors="coerce").fillna(0.0)
    return frame


def _total(frame: pd.DataFrame, column: str) -> float:
    if frame is None or frame.empty or column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


def _select(repo: Repository, table: str, **kwargs: Any) -> list[dict]:
    try:
        return list(repo.select(table, limit=ROW_LIMIT, **kwargs) or [])
    except Exception as exc:
        st.warning(f"{table} could not be read: {exc}. Apply the R36b inventory migration if this is a new installation.")
        return []


def stock_by_stage_rows(repo: Repository) -> list[dict]:
    """All parts at once: the security-invoker view first, the set-returning RPC as a fallback."""
    try:
        rows = repo.select("v_qcms_stock_by_stage", limit=ROW_LIMIT)
        if rows is not None:
            return list(rows)
    except Exception:
        pass
    try:
        return list(repo.rpc("qcms_stock_by_stage", {"p_part_id": None}) or [])
    except Exception as exc:
        st.warning(f"Stock by stage is unavailable: {exc}")
        return []


def stage_totals(frame: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([
        {"Stage": stage, "Quantity": round(_total(frame, column), 3), "Unit": unit, "Parts with stock": int((pd.to_numeric(frame[column], errors="coerce").fillna(0) > 0).sum()) if column in frame.columns else 0}
        for stage, column, unit in STAGE_SEQUENCE
    ])


def _grid(frame: pd.DataFrame, label_column: str, height: int = 560) -> None:
    shown = totals_row(frame, label_column) if not frame.empty else frame
    portal_table(shown, hide_index=True, width="stretch", height=min(height, 90 + 36 * max(len(shown), 1)))


# ----------------------------------------------------------------------------- tabs
def _tab_stock_by_stage(repo: Repository, stage_frame: pd.DataFrame) -> None:
    section_bar("STOCK BY STAGE · PER PART", "RM kg at FSI and at forger, forgings, machining WIP, FG stock, dispatched and open order quantity")
    hide_zero = st.toggle("Only parts with stock, orders or movements", value=True, key="inv_stage_hide_zero")
    frame = stage_frame
    if hide_zero and not frame.empty:
        activity = frame[[c for c in ACTIVITY_COLUMNS if c in frame.columns]].abs().sum(axis=1)
        frame = frame[activity > 0]
    frame = render_filters(frame, "inv_stock_by_stage", default_cols=["Customer", "Part Number", "FSI Part Number", "Material Grade", "Last Activity"])
    kpi_grid([
        {"label": "Parts", "value": f"{len(frame):,}", "foot": "matching the filters", "color": "#1469A8"},
        {"label": "RM at FSI", "value": f"{_total(frame, 'RM at FSI kg'):,.3f} kg", "foot": "received − sent + opening", "color": "#0F766E"},
        {"label": "RM at Forger", "value": f"{_total(frame, 'RM at Forger kg'):,.3f} kg", "foot": "sent − consumed", "color": "#B45309"},
        {"label": "Forgings at Forger", "value": f"{_total(frame, 'Forgings Pending at Forger pcs'):,.0f} pcs", "foot": "ordered − received − rejected", "color": "#C2410C"},
        {"label": "Machining WIP", "value": f"{_total(frame, 'Machining WIP pcs'):,.0f} pcs", "foot": "forgings in machining", "color": "#7C3AED"},
        {"label": "FG Stock", "value": f"{_total(frame, 'FG Stock pcs'):,.0f} pcs", "foot": "available to dispatch", "color": "#15803D"},
        {"label": "Pending Orders", "value": f"{_total(frame, 'Pending Order pcs'):,.0f} pcs", "foot": "open order − dispatched", "color": "#DC2626"},
    ])
    _grid(frame, "Part Number")
    section_bar("STAGE TOTALS", "Quantities of the filtered parts at every stage")
    totals = stage_totals(frame)
    stage_pick = st.multiselect("Stage", [s for s, _, _ in STAGE_SEQUENCE], key="inv_stage_pick", placeholder="All stages")
    if stage_pick:
        totals = totals[totals["Stage"].isin(stage_pick)]
    portal_table(totals, hide_index=True, width="stretch", height=min(460, 90 + 36 * max(len(totals), 1)))
    report_exports({"Stock by Stage": totals_row(frame, "Part Number"), "Stage Totals": totals}, "Stock by Stage Report", "inv_stock_by_stage")


def _tab_rm_by_heat(repo: Repository) -> None:
    section_bar("RAW MATERIAL STOCK BY HEAT / GRADE / SECTION", "Opening + received − dispatched to forger, in kg, with supplier, RMTC and parts")
    frame = _frame(_select(repo, "v_qcms_rm_stock_by_heat", order_by="last_movement_date", desc=True), RM_COLUMNS)
    if st.toggle("Only heats with balance", value=False, key="inv_rm_balance_only") and not frame.empty:
        frame = frame[frame["Balance kg"].abs() > 0.0005]
    frame = render_filters(frame, "inv_rm_by_heat", default_cols=["Heat Number", "Material Grade", "RM Section", "Supplier", "Last Movement"])
    kpi_grid([
        {"label": "Heats", "value": f"{frame['Heat Number'].nunique() if not frame.empty else 0:,}", "foot": "heat / grade / section rows", "color": "#1469A8"},
        {"label": "Opening", "value": f"{_total(frame, 'Opening kg'):,.3f} kg", "foot": "opening RM stock", "color": "#475569"},
        {"label": "Received", "value": f"{_total(frame, 'Received kg'):,.3f} kg", "foot": "RM receipts", "color": "#0F766E"},
        {"label": "Sent to Forger", "value": f"{_total(frame, 'Dispatched to Forger kg'):,.3f} kg", "foot": "RM issued", "color": "#B45309"},
        {"label": "Balance", "value": f"{_total(frame, 'Balance kg'):,.3f} kg", "foot": "RM stock at FSI", "color": "#15803D"},
    ])
    _grid(frame, "Heat Number")
    if not frame.empty:
        section_bar("GRADE / SECTION SUMMARY")
        grade = frame.groupby(["Material Grade", "RM Section"], dropna=False, as_index=False)[["Opening kg", "Received kg", "Dispatched to Forger kg", "Balance kg"]].sum()
        _grid(grade, "Material Grade", height=380)
    else:
        grade = pd.DataFrame()
    report_exports({"RM Stock by Heat": totals_row(frame, "Heat Number"), "Grade Section Summary": totals_row(grade, "Material Grade") if not grade.empty else grade},
                   "Raw Material Stock by Heat", "inv_rm_by_heat")


def _tab_forging_osp(repo: Repository) -> None:
    section_bar("FORGING STOCK AT FORGING SUPPLIERS", "RM sent / consumed / at forger and forgings ordered, received and pending, by supplier and part")
    forging = _frame(_select(repo, "v_qcms_forging_stock_by_supplier"), FORGING_COLUMNS)
    forging = render_filters(forging, "inv_forging_stock", default_cols=["Forging Supplier", "Customer", "Part Number", "Material Grade"])
    osp = _frame(_select(repo, "v_qsms_osp_register", order_by="created_at", desc=True), OSP_COLUMNS)
    pending_only = st.toggle("OSP: only jobs pending return", value=True, key="inv_osp_pending_only")
    if pending_only and not osp.empty:
        osp = osp[osp["Pending Return pcs"] > 0]
    kpi_grid([
        {"label": "Forging Suppliers", "value": f"{forging['Forging Supplier'].nunique() if not forging.empty else 0:,}", "foot": "with movements", "color": "#1469A8"},
        {"label": "RM at Forgers", "value": f"{_total(forging, 'RM at Forger kg'):,.3f} kg", "foot": "sent − consumed", "color": "#B45309"},
        {"label": "Forgings Pending", "value": f"{_total(forging, 'Forgings Pending pcs'):,.0f} pcs", "foot": "at forging suppliers", "color": "#C2410C"},
        {"label": "At OSP Vendors", "value": f"{_total(osp, 'Pending Return pcs'):,.0f} pcs", "foot": "pending return", "color": "#7C3AED"},
    ])
    _grid(forging, "Forging Supplier")
    section_bar("MATERIAL AT OSP VENDORS · PENDING RETURN", "OSP jobs: material out, received back and balance at vendor")
    osp = render_filters(osp, "inv_osp_stock", default_cols=["OSP Vendor", "OSP Process", "Part Number", "Status", "Material Out Date"])
    _grid(osp, "OSP Vendor", height=480)
    supplier = pd.DataFrame()
    if not forging.empty or not osp.empty:
        section_bar("SUPPLIER SUMMARY")
        parts_summary = []
        if not forging.empty:
            f = forging.groupby("Forging Supplier", as_index=False)[["RM at Forger kg", "Forgings Pending pcs"]].sum().rename(columns={"Forging Supplier": "Supplier"})
            f["Type"] = "Forging"
            parts_summary.append(f)
        if not osp.empty:
            o = osp.groupby("OSP Vendor", as_index=False)[["Pending Return pcs"]].sum().rename(columns={"OSP Vendor": "Supplier", "Pending Return pcs": "OSP Pending Return pcs"})
            o["Type"] = "OSP"
            parts_summary.append(o)
        supplier = pd.concat(parts_summary, ignore_index=True).fillna(0)
        supplier = supplier[["Supplier", "Type"] + [c for c in supplier.columns if c not in {"Supplier", "Type"}]]
        _grid(supplier, "Supplier", height=380)
    report_exports({"Forging Stock": totals_row(forging, "Forging Supplier"), "OSP Pending": totals_row(osp, "OSP Vendor"), "Supplier Summary": supplier},
                   "Forging and OSP Stock by Supplier", "inv_forging_osp")


def _tab_fg(repo: Repository, stage_frame: pd.DataFrame, ledger: pd.DataFrame) -> None:
    section_bar("FINISHED GOODS STOCK", "FG produced, FG stock, dispatched and pending customer orders per part")
    columns = ["Part Number", "FSI Part Number", "Part Description", "Customer", "Material Grade", "Open Orders", "Open Order Qty pcs",
               "Machined Pending FG pcs", "FG Produced pcs", "Opening FG pcs", "FG Stock pcs", "Dispatched pcs", "Pending Order pcs", "Last Activity"]
    fg = stage_frame[[c for c in columns if c in stage_frame.columns]] if not stage_frame.empty else pd.DataFrame(columns=columns)
    if not fg.empty:
        fg = fg[(fg[["FG Produced pcs", "Opening FG pcs", "FG Stock pcs", "Dispatched pcs", "Pending Order pcs"]].sum(axis=1)) > 0]
    fg = render_filters(fg, "inv_fg_stock", default_cols=["Customer", "Part Number", "FSI Part Number", "Last Activity"])
    fg = fg.assign(**{"Short vs Pending pcs": (fg["Pending Order pcs"] - fg["FG Stock pcs"]).clip(lower=0)}) if not fg.empty else fg
    kpi_grid([
        {"label": "FG Stock", "value": f"{_total(fg, 'FG Stock pcs'):,.0f} pcs", "foot": "available", "color": "#15803D"},
        {"label": "Dispatched", "value": f"{_total(fg, 'Dispatched pcs'):,.0f} pcs", "foot": "to customers", "color": "#1469A8"},
        {"label": "Pending Orders", "value": f"{_total(fg, 'Pending Order pcs'):,.0f} pcs", "foot": "open order − dispatched", "color": "#DC2626"},
        {"label": "FG Shortfall", "value": f"{_total(fg, 'Short vs Pending pcs'):,.0f} pcs", "foot": "pending − FG stock", "color": "#B45309"},
    ])
    _grid(fg, "Part Number", height=480)
    section_bar("CUSTOMER DISPATCH REGISTER", "Every customer dispatch with invoice / reference")
    dispatch = ledger[ledger["Movement"] == "CUSTOMER DISPATCH"] if not ledger.empty else ledger
    dispatch = dispatch[[c for c in ("Date", "Customer", "Part Number", "FSI Part Number", "Part Description", "Heat Number", "Reference", "Customer Order", "Qty pcs") if c in dispatch.columns]] if not dispatch.empty else pd.DataFrame()
    dispatch = render_filters(dispatch, "inv_fg_dispatch", default_cols=["Customer", "Part Number", "Date"])
    _grid(dispatch, "Date", height=420)
    if not dispatch.empty:
        section_bar("DISPATCH SUMMARY BY CUSTOMER / MONTH")
        summary = dispatch.assign(Month=pd.to_datetime(dispatch["Date"], errors="coerce").dt.strftime("%Y-%m")).groupby(["Month", "Customer", "Part Number"], dropna=False, as_index=False)[["Qty pcs"]].sum()
        _grid(summary, "Month", height=380)
    else:
        summary = pd.DataFrame()
    report_exports({"FG Stock": totals_row(fg, "Part Number"), "Customer Dispatches": totals_row(dispatch, "Date"), "Dispatch Summary": summary},
                   "FG Stock and Dispatch Summary", "inv_fg")


def _tab_ledger(ledger: pd.DataFrame) -> None:
    section_bar("STOCK MOVEMENT LEDGER", "Date-wise receipts and issues: opening, RM receipt / issue, forging receipt, machining, FG, dispatch, OSP out / in")
    frame = render_filters(ledger, "inv_movement_ledger", default_cols=["Part Number", "Heat Number", "Movement", "Stage", "Date"])
    if not frame.empty:
        frame = frame.assign(_d=pd.to_datetime(frame["Date"], errors="coerce")).sort_values(["_d", "Movement"], kind="stable").drop(columns="_d")
        frame = frame.assign(**{
            "Running Net kg": (frame["kg In"] - frame["kg Out"]).cumsum().round(3),
            "Running Net pcs": (frame["pcs In"] - frame["pcs Out"]).cumsum().round(0),
        })
    kpi_grid([
        {"label": "Movements", "value": f"{len(frame):,}", "foot": "matching the filters", "color": "#1469A8"},
        {"label": "kg In / Out", "value": f"{_total(frame, 'kg In'):,.3f} / {_total(frame, 'kg Out'):,.3f}", "foot": "RM receipts / issues", "color": "#0F766E"},
        {"label": "pcs In / Out", "value": f"{_total(frame, 'pcs In'):,.0f} / {_total(frame, 'pcs Out'):,.0f}", "foot": "receipts / issues", "color": "#7C3AED"},
    ])
    st.caption("Running Net columns add up the filtered rows in date order – filter one part or heat for a true stock card.")
    shown = totals_row(frame, "Date", skip=("Running Net kg", "Running Net pcs")) if not frame.empty else frame
    portal_table(shown, hide_index=True, width="stretch", height=min(620, 90 + 36 * max(len(shown), 1)))
    report_exports({"Stock Movement Ledger": shown}, "Stock Movement Ledger", "inv_movement_ledger")


# ----------------------------------------------------------------------------- page
def render() -> None:
    subpage_navigation(
        ("reports-home", "Reports", ":material/arrow_back:"),
        ("report-builder", "Report Builder", ":material/query_stats:"),
        ("supply-opening-stock", "Opening Stock", ":material/inventory_2:"),
    )
    page_header("Inventory & Stock Reports", "Stock by stage, RM by heat, forging / OSP stock, FG & dispatch and the stock movement ledger", "Reports")
    repo = Repository()
    with st.spinner("Loading stock…"):
        stage_frame = _frame(stock_by_stage_rows(repo), STAGE_COLUMNS)
        ledger = _frame(_select(repo, "v_qcms_stock_movement_ledger", order_by="movement_date"), LEDGER_COLUMNS)
    tabs = st.tabs(["Stock by Stage", "RM Stock by Heat", "Forging / OSP Stock", "FG Stock & Dispatch", "Stock Movement Ledger"])
    with tabs[0]:
        _tab_stock_by_stage(repo, stage_frame)
    with tabs[1]:
        _tab_rm_by_heat(repo)
    with tabs[2]:
        _tab_forging_osp(repo)
    with tabs[3]:
        _tab_fg(repo, stage_frame, ledger)
    with tabs[4]:
        _tab_ledger(ledger)
