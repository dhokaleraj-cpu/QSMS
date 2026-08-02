from __future__ import annotations

import streamlit as st

from core.access import current_permissions
from core.repository import Repository
from core.ui import kpi_grid, master_card, page_header, section_bar, subpage_navigation


def _count(repo: Repository, table: str) -> int:
    try: return repo.count(table)
    except Exception: return 0


def render() -> None:
    subpage_navigation(("dashboard", "Dashboard", ":material/dashboard:"))
    page_header("Master Data Centre", context="Controlled data")
    repo = Repository()
    counts = {
        "parts": _count(repo, "parts"), "grades": _count(repo, "material_grades"),
        "employees": _count(repo, "employees"),
        "references": sum(_count(repo, table) for table in ("parties", "processes", "inspection_stages", "quality_assets")),
        "users": _count(repo, "profiles"), "layouts": _count(repo, "inspection_plans"),
    }
    kpi_grid([
        {"label": "Parts", "value": counts["parts"], "foot": "Controlled"},
        {"label": "Material Grades", "value": counts["grades"], "foot": "Chemistry included"},
        {"label": "Employees", "value": counts["employees"], "foot": "Approval authorities"},
        {"label": "Reference Records", "value": counts["references"], "foot": "Reusable values"},
        {"label": "Inspection Layouts", "value": counts["layouts"], "foot": "Part / process / stage"},
    ])
    section_bar("MASTER WORKSPACES")
    cards = [
        ("Part Master", counts["parts"], "⚙", "#1469A8", "part-entry", "part-records", "PART_MASTER"),
        ("Material Grade", counts["grades"], "◈", "#7C3AED", "grade-entry", "grade-records", "MATERIAL_GRADE"),
        ("Reference Masters", counts["references"], "▦", "#0369A1", "reference-entry", "reference-records", "REFERENCE_MASTERS"),
        ("Employee Master", counts["employees"], "👥", "#087443", "employee-entry", "employee-records", "EMPLOYEE_MASTER"),
        ("Inspection Layouts", counts["layouts"], "▤", "#C56B00", "inspection-layout-entry", "inspection-layout-records", "INSPECTION_LAYOUTS"),
        ("Users & Access", counts["users"], "🔐", "#B42318", "user-access", "user-access", "USER_ACCESS"),
    ]
    for row_start in range(0, len(cards), 3):
        cols = st.columns(3, gap="small")
        for col, card in zip(cols, cards[row_start:row_start + 3]):
            title, count, icon, color, entry, records, module = card
            with col:
                perms = current_permissions(module)
                master_card(title=title, description="", count_text=f"{count} records", icon=icon, color=color, entry_path=entry, records_path=records, can_view=perms["can_view"])
