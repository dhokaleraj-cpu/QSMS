from __future__ import annotations

import streamlit as st

from app_pages import (
    dashboard,
    dimensional_report,
    employee_master,
    inspection_home,
    inspection_layouts,
    master_home,
    material_grade,
    material_inward,
    metlab_report,
    part_master,
    reference_master,
    records_center,
    rmtc_pages,
    user_access,
    template_center,
)
from core.auth import current_profile, is_logged_in, logout, needs_first_admin_claim, render_first_admin_claim, render_login
from core.config import get_settings
from core.ui import app_footer, apply_global_style, render_shell_header

settings = get_settings()
st.set_page_config(
    page_title=f"QSMS · {settings.company_name}", page_icon="✅", layout="wide",
    initial_sidebar_state="collapsed", menu_items=None,
)
apply_global_style()

if not is_logged_in():
    render_login(); app_footer(); st.stop()
profile = current_profile() or {}
if needs_first_admin_claim(profile):
    render_first_admin_claim(); app_footer(); st.stop()

# Keep an explicit route-to-Page registry. Streamlit may expose the default
# page at the root URL even when a url_path was supplied, so deriving this
# mapping from page.url_path can drop the "dashboard" key.
PAGE_ITEMS = (
    ("dashboard", st.Page(dashboard.render, title="Dashboard", icon=":material/dashboard:", url_path="dashboard", default=True)),
    ("masters", st.Page(master_home.render, title="Masters", icon=":material/dataset:", url_path="masters")),
    ("rmtc-entry", st.Page(rmtc_pages.render_entry, title="RMTC Entry", icon=":material/fact_check:", url_path="rmtc-entry")),
    ("inward-entry", st.Page(material_inward.render_entry, title="Material Inward", icon=":material/input:", url_path="inward-entry")),
    ("inspection-home", st.Page(inspection_home.render, title="Inspections", icon=":material/biotech:", url_path="inspection-home")),
    ("records-center", st.Page(records_center.render, title="Records Centre", icon=":material/table_view:", url_path="records-center")),
    ("heat-ledger", st.Page(records_center.render_heat_ledger, title="Heat Steel Ledger", icon=":material/table_view:", url_path="heat-ledger")),
    ("templates", st.Page(template_center.render, title="Templates", icon=":material/download:", url_path="templates")),

    ("part-entry", st.Page(part_master.render_entry, title="Part Master Entry", icon=":material/edit_note:", url_path="part-entry")),
    ("part-records", st.Page(part_master.render_records, title="Part Master Records", icon=":material/table_view:", url_path="part-records")),
    ("grade-entry", st.Page(material_grade.render_entry, title="Material Grade Entry", icon=":material/science:", url_path="grade-entry")),
    ("grade-records", st.Page(material_grade.render_records, title="Material Grade Records", icon=":material/table_view:", url_path="grade-records")),
    ("reference-entry", st.Page(reference_master.render_entry, title="Reference Master Entry", icon=":material/edit_note:", url_path="reference-entry")),
    ("reference-records", st.Page(reference_master.render_records, title="Reference Master Records", icon=":material/table_view:", url_path="reference-records")),
    ("employee-entry", st.Page(employee_master.render_entry, title="Employee Entry", icon=":material/person_add:", url_path="employee-entry")),
    ("employee-records", st.Page(employee_master.render_records, title="Employee Records", icon=":material/groups:", url_path="employee-records")),
    ("user-access", st.Page(user_access.render, title="Users & Access", icon=":material/admin_panel_settings:", url_path="user-access")),

    ("rmtc-part", st.Page(rmtc_pages.render_part, title="RMTC Part Worksheet", icon=":material/format_list_bulleted:", url_path="rmtc-part")),
    ("rmtc-records", st.Page(rmtc_pages.render_records, title="RMTC Records", icon=":material/table_view:", url_path="rmtc-records")),
    ("rmtc-approval", st.Page(rmtc_pages.render_approval, title="RMTC Approval", icon=":material/approval:", url_path="rmtc-approval")),
    ("inward-records", st.Page(material_inward.render_records, title="Material Inward Records", icon=":material/table_view:", url_path="inward-records")),

    ("inspection-layout-entry", st.Page(inspection_layouts.render_entry, title="Inspection Layout Entry", icon=":material/edit_document:", url_path="inspection-layout-entry")),
    ("inspection-layout-records", st.Page(inspection_layouts.render_records, title="Inspection Layout Records", icon=":material/table_view:", url_path="inspection-layout-records")),
    ("dimensional-entry", st.Page(dimensional_report.render_entry, title="Dimensional Report", icon=":material/straighten:", url_path="dimensional-entry")),
    ("dimensional-records", st.Page(dimensional_report.render_records, title="Dimensional Records", icon=":material/table_view:", url_path="dimensional-records")),
    ("metlab-entry", st.Page(metlab_report.render_entry, title="MetLAB Report", icon=":material/science:", url_path="metlab-entry")),
    ("metlab-records", st.Page(metlab_report.render_records, title="MetLAB Records", icon=":material/table_view:", url_path="metlab-records")),
)
PAGES = tuple(page for _, page in PAGE_ITEMS)
PAGE_BY_PATH = dict(PAGE_ITEMS)
st.session_state["_qsms_pages"] = PAGE_BY_PATH

nav = st.navigation(PAGES, position="hidden")
if render_shell_header(profile, nav.title):
    logout()

with st.container(border=True, key="fsi_top_nav"):
    cols = st.columns(7, gap="small")
    labels = (
        ("dashboard", "Dashboard", ":material/dashboard:"),
        ("masters", "Masters", ":material/dataset:"),
        ("rmtc-entry", "RMTC", ":material/fact_check:"),
        ("inward-entry", "Inward", ":material/input:"),
        ("inspection-home", "Inspections", ":material/biotech:"),
        ("records-center", "Records", ":material/table_view:"),
        ("templates", "Templates", ":material/download:"),
    )
    for col, (path, label, icon) in zip(cols, labels):
        page = PAGE_BY_PATH.get(path)
        if page is None:
            continue
        with col:
            with st.container(key=f"menu_{path.replace('-', '_')}"):
                if path == "rmtc-entry":
                    if st.button(label, icon=icon, width="stretch", key="top_menu_new_rmtc"):
                        st.session_state["rmtc_entry_mode"] = "new"
                        st.session_state.pop("edit_rmtc_id", None)
                        st.session_state.pop("part_rmtc_id", None)
                        st.session_state.pop("new_rmtc_number", None)
                        st.switch_page(page)
                else:
                    st.page_link(page, label=label, icon=icon, width="stretch")

nav.run()
app_footer()
