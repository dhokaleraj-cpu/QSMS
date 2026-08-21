from __future__ import annotations

import pandas as pd
import streamlit as st
from core.ui import portal_table

from core.inspection_queue import pending_count
from core.inspection_service import InspectionService
from core.osp_service import OSPService
from core.repository import Repository
from core.ui import dashboard_card, kpi_grid, page_header, section_bar, stage_section, style_status_dataframe, subpage_navigation


def _count(repo: Repository, table: str, eq: dict | None = None) -> int:
    try:
        return repo.count(table, eq=eq or {})
    except Exception:
        return 0


def _worklist_frame(rows: list[dict], parts: dict[str, dict], parties: dict[str, dict]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Inward": row.get("inward_number"),
            "Date": row.get("inward_date"),
            "Supplier": (parties.get(str(row.get("supplier_id"))) or {}).get("party_name"),
            "Part Number": (parts.get(str(row.get("part_id"))) or {}).get("part_number"),
            "Part Description": (parts.get(str(row.get("part_id"))) or {}).get("part_name"),
            "Heat Number": row.get("heat_number"),
            "Steel kg": row.get("steel_quantity_kg") or row.get("quantity_received"),
            "Production pcs": row.get("production_quantity_pcs"),
            "Dimensional": row.get("dimensional_queue_status"),
            "MetLAB": row.get("metlab_queue_status"),
            "Inward Status": row.get("status"),
        }
        for row in rows
    ])


def render() -> None:
    subpage_navigation(("dashboard", "Dashboard", ":material/dashboard:"), ("masters", "Masters", ":material/dataset:"), ("inward-records", "Material Inward", ":material/input:"))
    page_header("Inspection & Validation", context="Post-inward quality gate")

    repo = Repository()
    service = InspectionService()
    osp_service = OSPService()
    queue = service.inspection_queue()
    parts = {str(row["id"]): row for row in service.parts()}
    parties = {str(row["id"]): row for row in service.parties()}

    plans = _count(repo, "inspection_plans")
    dim_pending = pending_count(queue, "DIMENSIONAL")
    met_pending = pending_count(queue, "METLAB")
    released = _count(repo, "inward_lots", {"status": "RELEASED"})
    osp_rows = osp_service.register()
    osp_sample_pending = sum(bool(row.get("sample_received_date")) and str(row.get("sample_gate_status")) in {"PENDING", "ON_HOLD"} for row in osp_rows)
    osp_receipt_pending = sum(float(row.get("quantity_received") or 0) > 0 and str(row.get("receipt_quality_disposition")) in {"PENDING", "ON_HOLD"} for row in osp_rows)

    kpi_grid([
        {"label": "Layouts", "value": plans, "foot": "Part / process / stage", "color": "#7C3AED", "background": "#F5F3FF"},
        {"label": "Dimensional Pending", "value": dim_pending, "foot": "Inward lots requiring action", "color": "#D97706", "background": "#FFF7ED"},
        {"label": "MetLAB Pending", "value": met_pending, "foot": "Inward lots requiring action", "color": "#D97706", "background": "#FFF7ED"},
        {"label": "OSP Sample Pending", "value": osp_sample_pending, "foot": "Pre-inward gate", "color": "#D97706", "background": "#FFF7ED"},
        {"label": "OSP Receipt Pending", "value": osp_receipt_pending, "foot": "Production release gate", "color": "#D97706", "background": "#FFF7ED"},
        {"label": "Released Heats", "value": released, "foot": "Eligible for next process", "color": "#15803D", "background": "#F0FDF4"},
    ])

    with stage_section("A", "PENDING INSPECTION WORKLIST", key="inspection_home_render_a"):
        pending = [row for row in queue if row.get("dimensional_pending") or row.get("metlab_pending")]
        if not pending:
            st.success("No Material Inward records are pending Dimensional or MetLAB inspection.")
        else:
            portal_table(
                style_status_dataframe(_worklist_frame(pending, parts, parties)),
                hide_index=True,
                width="stretch",
                height=min(360, 84 + 38 * len(pending)),
            )
            options = {str(row["id"]): row for row in pending}
            selected_id = st.selectbox(
                "Select Pending Material Inward",
                list(options),
                format_func=lambda value: (
                    f"{options[value].get('inward_number')} · "
                    f"{(parts.get(str(options[value].get('part_id'))) or {}).get('part_number')} · "
                    f"Heat {options[value].get('heat_number')}"
                ),
                key="inspection_pending_inward_select",
            )
            selected = options[selected_id]
            st.session_state["inspection_inward_id"] = selected_id

            if selected.get("dimensional_report_id"):
                st.session_state["edit_dimensional_id"] = str(selected.get("dimensional_report_id"))
            else:
                st.session_state.pop("edit_dimensional_id", None)
            if selected.get("metlab_report_id"):
                st.session_state["edit_metlab_id"] = str(selected.get("metlab_report_id"))
            else:
                st.session_state.pop("edit_metlab_id", None)

            c1, c2 = st.columns(2, gap="small")
            with c1:
                st.page_link(
                    st.session_state["_qsms_pages"]["dimensional-entry"],
                    label=f"Open Dimensional · {selected.get('dimensional_queue_status')}",
                    icon=":material/straighten:",
                    width="stretch",
                    disabled=not bool(selected.get("dimensional_pending")),
                )
            with c2:
                st.page_link(
                    st.session_state["_qsms_pages"]["metlab-entry"],
                    label=f"Open MetLAB · {selected.get('metlab_queue_status')}",
                    icon=":material/science:",
                    width="stretch",
                    disabled=not bool(selected.get("metlab_pending")),
                )

    with stage_section("B", "WORKSPACES", key="inspection_home_render_b"):
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            dashboard_card(title="Inspection Layouts", description="", count_text=f"{plans} layouts", color="#7C3AED", page_path="inspection-layout-entry", button_label="Open Layout Master")
        with c2:
            dashboard_card(title="Dimensional Report", description="", count_text=f"{dim_pending} pending", color="#1469A8", page_path="dimensional-entry", button_label="Open Dimensional")
        with c3:
            dashboard_card(title="MetLAB Report", description="", count_text=f"{met_pending} pending", color="#0F8B6D", page_path="metlab-entry", button_label="Open MetLAB")

    with stage_section("C", "OSP INSPECTION WORKSPACES", key="inspection_home_render_c"):
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            dashboard_card(title="OSP Transactions", description="", count_text=f"{osp_sample_pending + osp_receipt_pending} quality gates pending", color="#DC2626", page_path="osp-home", button_label="Open OSP Home")
        with c2:
            dashboard_card(title="OSP Dimensional", description="", count_text="Sample and full-batch inspection", color="#0284C7", page_path="osp-dimensional", button_label="Open OSP Dimensional")
        with c3:
            dashboard_card(title="OSP MetLAB", description="", count_text="Process-specific inspection", color="#16A34A", page_path="osp-metlab", button_label="Open OSP MetLAB")
