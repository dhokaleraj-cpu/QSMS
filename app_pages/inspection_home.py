from __future__ import annotations

import streamlit as st

from core.repository import Repository
from core.ui import dashboard_card, kpi_grid, page_header, section_bar, subpage_navigation


def _count(repo: Repository, table: str, eq: dict | None = None) -> int:
    try:
        return repo.count(table, eq=eq or {})
    except Exception:
        return 0


def render() -> None:
    subpage_navigation(("dashboard", "Dashboard", ":material/dashboard:"), ("masters", "Masters", ":material/dataset:"), ("inward-records", "Material Inward", ":material/input:"))
    page_header("Inspection & Validation", context="Post-inward quality gate")
    repo = Repository()
    plans = _count(repo, "inspection_plans")
    dim_pending = _count(repo, "inspection_reports", {"report_type": "DIMENSIONAL", "disposition": "PENDING"})
    met_pending = _count(repo, "lab_tests", {"test_type": "METLAB", "disposition": "PENDING"})
    released = _count(repo, "inward_lots", {"status": "RELEASED"})
    kpi_grid([
        {"label": "Layouts", "value": plans, "foot": "Part / process / stage"},
        {"label": "Dimensional Pending", "value": dim_pending, "foot": "Awaiting decision"},
        {"label": "MetLAB Pending", "value": met_pending, "foot": "Awaiting decision"},
        {"label": "Released Heats", "value": released, "foot": "Eligible for next process"},
    ])
    section_bar("WORKSPACES")
    c1, c2, c3 = st.columns(3, gap="small")
    with c1:
        dashboard_card(title="Inspection Layouts", description="", count_text=f"{plans} layouts", color="#7C3AED", page_path="inspection-layout-entry", button_label="Open Layout Master")
    with c2:
        dashboard_card(title="Dimensional Report", description="", count_text=f"{dim_pending} pending", color="#1469A8", page_path="dimensional-entry", button_label="Open Dimensional")
    with c3:
        dashboard_card(title="MetLAB Report", description="", count_text=f"{met_pending} pending", color="#0F8B6D", page_path="metlab-entry", button_label="Open MetLAB")
