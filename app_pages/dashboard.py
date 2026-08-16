from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from core.inspection_queue import build_inspection_queue, pending_count
from core.repository import Repository
from core.ui import dashboard_card, kpi_grid, page_header, section_bar, stage_section, style_status_dataframe


def _count(repo: Repository, table: str, eq: dict | None = None, contains: dict | None = None) -> int:
    try:
        return repo.count(table, eq=eq or {}, contains=contains or {})
    except Exception:
        return 0


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _sum(rows: list[dict], column: str) -> float:
    return round(sum(_number(row.get(column)) for row in rows), 2)


def _label(value: Any) -> str:
    return str(value or "NOT_EVALUATED").replace("_", " ").title()


def _donut(title: str, values: list[Any], color_map: dict[str, str]) -> None:
    counts = Counter(_label(value) for value in values)
    if not counts:
        st.info(f"No {title.casefold()} data yet.")
        return
    frame = pd.DataFrame({"Status": list(counts), "Count": list(counts.values())})
    fig = px.pie(
        frame, names="Status", values="Count", hole=.58, color="Status",
        color_discrete_map=color_map,
    )
    fig.update_traces(textposition="inside", textinfo="percent+value", hovertemplate="%{label}: %{value}<extra></extra>")
    fig.update_layout(
        title=dict(text=title, x=.02, y=.98, font=dict(size=13)),
        height=265, margin=dict(l=5, r=5, t=38, b=5),
        legend=dict(orientation="h", y=-.08, x=0, font=dict(size=9)),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def render() -> None:
    page_header("Quality Dashboard", context="Live Supabase")
    repo = Repository()

    rmtc_rows = repo.select("rmtc_approvals", order_by="created_at", desc=True, limit=2000)
    inward_rows = repo.select("v_qsms_inward_register", order_by="created_at", desc=True, limit=2000)
    recent_inwards = inward_rows[:30]
    heat_summary_rows = repo.select("v_qsms_heat_summary", order_by="last_activity_at", desc=True, limit=3000)
    heat_summary = {str(row.get("normalized_heat_number") or ""): row for row in heat_summary_rows}
    osp_rows = repo.select("v_qsms_osp_register", order_by="created_at", desc=True, limit=3000)
    inspection_queue = build_inspection_queue(
        inward_rows,
        repo.select("inspection_reports", eq={"report_type": "DIMENSIONAL"}, order_by="created_at", desc=True, limit=4000),
        repo.select("lab_tests", eq={"test_type": "METLAB"}, order_by="created_at", desc=True, limit=4000),
    )

    counts = {
        "rmtc_pending": _count(repo, "rmtc_approvals", {"status": "APPROVAL_PENDING"}),
        "rmtc_draft": _count(repo, "rmtc_approvals", {"status": "DRAFT"}),
        "rmtc_accepted": _count(repo, "rmtc_approvals", {"disposition": "ACCEPTED"}),
        "rmtc_reserve": _count(repo, "rmtc_approvals", {"disposition": "ACCEPTED_UNDER_RESERVE"}),
        "rmtc_hold": _count(repo, "rmtc_approvals", {"disposition": "ON_HOLD"}),
        "inward": len(inward_rows),
        "quality_hold": _count(repo, "inward_lots", {"status": "HOLD_PENDING_INSPECTION"}),
        "released": _count(repo, "inward_lots", {"status": "RELEASED"}),
        "dim_pending": pending_count(inspection_queue, "DIMENSIONAL"),
        "met_pending": pending_count(inspection_queue, "METLAB"),
        "dim_hold": _count(repo, "inspection_reports", {"report_type": "DIMENSIONAL", "disposition": "ON_HOLD"}),
        "met_hold": _count(repo, "lab_tests", {"test_type": "METLAB", "disposition": "ON_HOLD"}),
        "osp_at_vendor": sum(str(row.get("status")) == "AT_VENDOR" for row in osp_rows),
        "osp_sample_pending": sum(str(row.get("sample_gate_status")) in ("PENDING", "ON_HOLD") for row in osp_rows),
        "osp_receipt_pending": sum(float(row.get("quantity_received") or 0) > 0 and str(row.get("receipt_quality_disposition")) in ("PENDING", "ON_HOLD") for row in osp_rows),
    }

    rmtc_steel = _sum(rmtc_rows, "certificate_quantity")
    inward_steel = _sum(inward_rows, "steel_quantity_kg")
    planned_pcs = _sum(inward_rows, "production_quantity_pcs")
    accepted_pcs = _sum(inward_rows, "accepted_production_quantity_pcs")
    rejected_pcs = _sum(inward_rows, "rejected_production_quantity_pcs")
    hold_pcs = sum(float(row.get("on_hold_production_quantity_pcs") or row.get("hold_production_quantity_pcs") or 0) for row in inward_rows)

    kpi_grid([
        {"label": "RMTC Draft", "value": counts["rmtc_draft"], "foot": "Entry", "color": "#64748B", "background": "#F8FAFC"},
        {"label": "RMTC Pending", "value": counts["rmtc_pending"], "foot": "Validation", "color": "#D97706", "background": "#FFF7ED"},
        {"label": "RMTC Accepted", "value": counts["rmtc_accepted"], "foot": "Inward eligible", "color": "#15803D", "background": "#F0FDF4"},
        {"label": "Under Reserve", "value": counts["rmtc_reserve"], "foot": "Controlled", "color": "#C2410C", "background": "#FFF7ED"},
        {"label": "RMTC Steel kg", "value": f"{rmtc_steel:,.2f}", "foot": "All heats", "color": "#2563EB", "background": "#EFF6FF"},
        {"label": "Inward Steel kg", "value": f"{inward_steel:,.2f}", "foot": "Received", "color": "#0F766E", "background": "#F0FDFA"},
        {"label": "Planned Production", "value": f"{planned_pcs:,.0f}", "foot": "Pieces", "color": "#7C3AED", "background": "#F5F3FF"},
        {"label": "Accepted Production", "value": f"{accepted_pcs:,.0f}", "foot": "Pieces", "color": "#15803D", "background": "#F0FDF4"},
        {"label": "Rejected Production", "value": f"{rejected_pcs:,.0f}", "foot": "Pieces", "color": "#B91C1C", "background": "#FEF2F2"},
        {"label": "On Hold Production", "value": f"{hold_pcs:,.0f}", "foot": "Pieces", "color": "#D97706", "background": "#FFF7ED"},
        {"label": "Quality Holds", "value": counts["quality_hold"], "foot": "Awaiting reports", "color": "#D97706", "background": "#FFF7ED"},
        {"label": "Released Heats", "value": counts["released"], "foot": "Next process", "color": "#15803D", "background": "#F0FDF4"},
    ])

    with stage_section("A", "QUICK ACTIONS", key="dashboard_render_a"):
        cards = [
            ("Masters", "Controlled master data", "#0F4C81", "masters", "Open Masters"),
            ("RMTC", f"{counts['rmtc_draft']} drafts", "#7C3AED", "rmtc-records", "Open RMTC"),
            ("Material Inward", f"{counts['inward']} records", "#00897B", "inward-records", "Open Inward"),
            ("OSP Transactions", f"{counts['osp_at_vendor']} at vendor · {counts['osp_sample_pending']} sample pending", "#DC2626", "osp-home", "Open OSP"),
            ("Inspection Layouts", "Part / process / stage", "#F59E0B", "inspection-layout-records", "Open Layouts"),
            ("Dimensional", f"{counts['dim_pending']} pending", "#0284C7", "dimensional-entry", "Open Dimensional"),
            ("MetLAB", f"{counts['met_pending']} pending", "#16A34A", "metlab-entry", "Open MetLAB"),
            ("Records Centre", "All module registers", "#C026D3", "records-center", "Open Records"),
            ("Templates", "Excel downloads", "#475569", "templates", "Open Templates"),
        ]
        for start in range(0, len(cards), 3):
            cols = st.columns(3, gap="small")
            for col, card in zip(cols, cards[start:start + 3]):
                with col:
                    dashboard_card(title=card[0], description="", count_text=card[1], color=card[2], page_path=card[3], button_label=card[4])

    with stage_section("B", "STATUS PIE CHARTS", key="dashboard_render_b"):
        color_map = {
            "Accepted": "#087443", "Accepted Under Reserve": "#EA580C", "On Hold": "#D97706",
            "Pending": "#1469A8", "Draft": "#64748B", "Rejected": "#B42318",
            "Pass": "#087443", "Fail": "#B42318", "Not Evaluated": "#64748B",
            "Released": "#087443", "Hold Pending Inspection": "#D97706", "Closed": "#475569",
        }
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            _donut("Recent Inwards", [row.get("receipt_disposition") or row.get("quality_disposition") for row in recent_inwards], color_map)
        with c2:
            _donut("RMTC Validation Status", [row.get("validation_result") for row in rmtc_rows], color_map)
        with c3:
            _donut("Inward Status", [row.get("status") for row in inward_rows], color_map)

    with stage_section("C", "STATUS BAR CHARTS", key="dashboard_render_c"):
        c1, c2 = st.columns(2, gap="small")
        with c1:
            chart_data = pd.DataFrame({"Status": ["Draft", "Approval Pending", "On Hold", "Under Reserve", "Accepted"], "Count": [counts["rmtc_draft"], counts["rmtc_pending"], counts["rmtc_hold"], counts["rmtc_reserve"], counts["rmtc_accepted"]]})
            fig = px.bar(chart_data, y="Status", x="Count", orientation="h", color="Status", text="Count", color_discrete_map={"Draft":"#64748B","Approval Pending":"#1469A8","On Hold":"#B45309","Under Reserve":"#D17A00","Accepted":"#087443"})
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_layout(height=235, margin=dict(l=5, r=35, t=5, b=5), showlegend=False, xaxis_title=None, yaxis_title=None, bargap=.28)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        with c2:
            steel_data = pd.DataFrame({"Quantity": ["RMTC Steel", "Inward Steel", "Required Steel", "Accepted Steel", "Rejected Steel", "On Hold Steel"], "kg": [rmtc_steel, inward_steel, _sum(inward_rows, "required_steel_quantity_kg"), _sum(inward_rows, "accepted_steel_quantity_kg"), _sum(inward_rows, "rejected_steel_quantity_kg"), sum(float(row.get("on_hold_steel_quantity_kg") or row.get("hold_steel_quantity_kg") or 0) for row in inward_rows)]})
            fig = px.bar(steel_data, y="Quantity", x="kg", orientation="h", text="kg")
            fig.update_traces(texttemplate="%{text:,.2f}", textposition="outside", cliponaxis=False)
            fig.update_layout(height=235, margin=dict(l=5, r=50, t=5, b=5), showlegend=False, xaxis_title="kg", yaxis_title=None, bargap=.28)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with stage_section("D", "RECENT HEAT STATUS", key="dashboard_render_d"):
        recent_heat_rows = []
        for row in recent_inwards[:10]:
            key = "".join(ch for ch in str(row.get("heat_number") or "").upper() if ch.isalnum())
            heat = heat_summary.get(key) or {}
            recent_heat_rows.append({
                "Inward": row.get("inward_number"), "Supplier": row.get("supplier_name") or row.get("supplier_id"),
                "Heat": row.get("heat_number"), "Global Heat Qty kg": heat.get("global_steel_quantity_kg"),
                "Global Heat Balance kg": heat.get("available_unallocated_steel_quantity_kg"),
                "Inward Steel kg": row.get("steel_quantity_kg"), "Production pcs": row.get("production_quantity_pcs"),
                "MetLAB": row.get("metallurgical_status"), "Dimensional": row.get("dimensional_status"),
                "Quality Decision": row.get("quality_disposition"), "Status": row.get("status"),
            })
        st.dataframe(style_status_dataframe(pd.DataFrame(recent_heat_rows)), hide_index=True, width="stretch", height=230)
