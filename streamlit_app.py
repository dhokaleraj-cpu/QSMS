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
    npd_apqp,
    material_inward,
    metlab_report,
    osp_inspections,
    osp_transactions,
    part_master,
    process_master,
    qc_calculation_tools,
    reference_master,
    records_center,
    reports,
    rmtc_pages,
    user_access,
    template_center,
)
from core.auth import current_profile, is_logged_in, logout, needs_first_admin_claim, render_first_admin_claim, render_login
from core.config import get_settings
from core.ui import app_footer, apply_global_style, module_submenu, render_shell_header

settings = get_settings()
st.set_page_config(
    page_title=f"{settings.app_name} · {settings.company_name}", page_icon="✅", layout="wide",
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
    ("osp-home", st.Page(osp_transactions.render_home, title="OSP Transactions", icon=":material/factory:", url_path="osp-home")),
    ("npd-process-flow", st.Page(npd_apqp.render_process_flow, title="Process Flow Designer", icon=":material/account_tree:", url_path="npd-process-flow")),
    ("npd-status", st.Page(npd_apqp.render_npd_status, title="NPD Status", icon=":material/timeline:", url_path="npd-status")),
    ("apqp", st.Page(npd_apqp.render_apqp, title="APQP", icon=":material/assignment_turned_in:", url_path="apqp")),
    ("qc-tools", st.Page(qc_calculation_tools.render_tools, title="QC Calculation Tools", icon=":material/calculate:", url_path="qc-tools")),
    ("qc-calculation-records", st.Page(qc_calculation_tools.render_records, title="QC Calculation Records", icon=":material/receipt_long:", url_path="qc-calculation-records")),
    ("inspection-home", st.Page(inspection_home.render, title="Inspections", icon=":material/biotech:", url_path="inspection-home")),
    ("records-center", st.Page(records_center.render, title="Records Centre", icon=":material/table_view:", url_path="records-center")),
    ("heat-ledger", st.Page(records_center.render_heat_ledger, title="Heat Steel Ledger", icon=":material/table_view:", url_path="heat-ledger")),
    ("reports-home", st.Page(reports.render_home, title="Reports", icon=":material/assessment:", url_path="reports-home")),
    ("heat-transaction-report", st.Page(reports.render_heat_transactions, title="Heat Transaction Report", icon=":material/monitoring:", url_path="heat-transaction-report")),
    ("osp-balance-report", st.Page(reports.render_osp_balance, title="OSP Heat Balance Report", icon=":material/factory:", url_path="osp-balance-report")),
    ("templates", st.Page(template_center.render, title="Templates", icon=":material/download:", url_path="templates")),

    ("part-entry", st.Page(part_master.render_entry, title="Part Master Entry", icon=":material/edit_note:", url_path="part-entry")),
    ("part-records", st.Page(part_master.render_records, title="Part Master Records", icon=":material/table_view:", url_path="part-records")),
    ("process-entry", st.Page(process_master.render_entry, title="Process Master Entry", icon=":material/settings:", url_path="process-entry")),
    ("process-records", st.Page(process_master.render_records, title="Process Master Records", icon=":material/table_view:", url_path="process-records")),
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
    ("osp-material-out", st.Page(osp_transactions.render_material_out, title="OSP Material Out", icon=":material/output:", url_path="osp-material-out")),
    ("osp-sample-receipt", st.Page(osp_transactions.render_sample_receipt, title="OSP Sample Receipt", icon=":material/experiment:", url_path="osp-sample-receipt")),
    ("osp-inward", st.Page(osp_transactions.render_inward, title="OSP Material Inward", icon=":material/input:", url_path="osp-inward")),
    ("osp-dimensional", st.Page(osp_inspections.render_dimensional, title="OSP Dimensional", icon=":material/straighten:", url_path="osp-dimensional")),
    ("osp-metlab", st.Page(osp_inspections.render_metlab, title="OSP MetLAB", icon=":material/science:", url_path="osp-metlab")),
    ("osp-records", st.Page(osp_transactions.render_records, title="OSP Records", icon=":material/table_view:", url_path="osp-records")),

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

MODULE_SUBMENUS = {
    "Dashboard": (
        ("dashboard", "Quality Dashboard", ":material/dashboard:"),
        ("records-center", "Records Centre", ":material/table_view:"),
        ("heat-ledger", "Heat Steel Ledger", ":material/monitoring:"),
    ),
    "Masters": (
        ("masters", "Masters Home", ":material/dataset:"),
        ("part-entry", "Part Entry", ":material/edit_note:"),
        ("part-records", "Part Records", ":material/table_view:"),
        ("process-entry", "Process Entry", ":material/settings:"),
        ("process-records", "Process Records", ":material/table_view:"),
        ("grade-entry", "Grade Entry", ":material/science:"),
        ("grade-records", "Grade Records", ":material/table_view:"),
        ("reference-entry", "Reference Entry", ":material/edit_note:"),
        ("reference-records", "Reference Records", ":material/table_view:"),
        ("employee-entry", "Employee Entry", ":material/person_add:"),
        ("employee-records", "Employee Records", ":material/groups:"),
        ("user-access", "Users & Access", ":material/admin_panel_settings:"),
    ),
    "RMTC": (
        ("rmtc-entry", "RMTC Entry", ":material/fact_check:"),
        ("rmtc-part", "Part Worksheet", ":material/format_list_bulleted:"),
        ("rmtc-approval", "Validation & Decision", ":material/approval:"),
        ("rmtc-records", "RMTC Records", ":material/table_view:"),
        ("heat-ledger", "Heat Steel Ledger", ":material/monitoring:"),
    ),
    "Inward": (
        ("inward-entry", "Material Inward Entry", ":material/input:"),
        ("inward-records", "Material Inward Records", ":material/table_view:"),
        ("metlab-entry", "MetLAB Report", ":material/science:"),
        ("dimensional-entry", "Dimensional Report", ":material/straighten:"),
    ),
    "OSP": (
        ("osp-home", "OSP Home", ":material/factory:"),
        ("osp-material-out", "Material Out", ":material/output:"),
        ("osp-sample-receipt", "Sample Receipt", ":material/experiment:"),
        ("osp-dimensional", "OSP Dimensional", ":material/straighten:"),
        ("osp-metlab", "OSP MetLAB", ":material/science:"),
        ("osp-inward", "OSP Inward", ":material/input:"),
        ("osp-records", "OSP Records", ":material/table_view:"),
    ),
    "NPD & APQP": (
        ("npd-process-flow", "Process Flow Designer", ":material/account_tree:"),
        ("npd-status", "NPD Status", ":material/timeline:"),
        ("apqp", "APQP", ":material/assignment_turned_in:"),
    ),
    "QC Calculation Tools": (
        ("qc-tools", "Calculation Tools", ":material/calculate:"),
        ("qc-calculation-records", "Calculation Records", ":material/receipt_long:"),
    ),
    "Inspections": (
        ("inspection-home", "Inspection Home", ":material/biotech:"),
        ("inspection-layout-entry", "Layout Entry", ":material/edit_document:"),
        ("inspection-layout-records", "Layout Records", ":material/table_view:"),
        ("dimensional-entry", "Dimensional Entry", ":material/straighten:"),
        ("dimensional-records", "Dimensional Records", ":material/table_view:"),
        ("metlab-entry", "MetLAB Entry", ":material/science:"),
        ("metlab-records", "MetLAB Records", ":material/table_view:"),
    ),
    "Records": (
        ("records-center", "Records Centre", ":material/table_view:"),
        ("heat-ledger", "Heat Steel Ledger", ":material/monitoring:"),
        ("rmtc-records", "RMTC Records", ":material/fact_check:"),
        ("inward-records", "Inward Records", ":material/input:"),
        ("osp-records", "OSP Records", ":material/factory:"),
        ("dimensional-records", "Dimensional Records", ":material/straighten:"),
        ("metlab-records", "MetLAB Records", ":material/science:"),
    ),
    "Reports": (
        ("reports-home", "Reports Home", ":material/assessment:"),
        ("heat-transaction-report", "Heat Global Balance", ":material/monitoring:"),
        ("osp-balance-report", "OSP Heat Balance", ":material/factory:"),
        ("heat-ledger", "Heat Steel Ledger", ":material/table_view:"),
    ),
    "Templates": (
        ("templates", "Download Templates", ":material/download:"),
        ("masters", "Masters", ":material/dataset:"),
        ("inspection-home", "Inspections", ":material/biotech:"),
    ),
}
ROUTE_MODULE = {
    "dashboard": "Dashboard",
    "masters": "Masters", "part-entry": "Masters", "part-records": "Masters",
    "process-entry": "Masters", "process-records": "Masters",
    "grade-entry": "Masters", "grade-records": "Masters",
    "reference-entry": "Masters", "reference-records": "Masters",
    "employee-entry": "Masters", "employee-records": "Masters", "user-access": "Masters",
    "rmtc-entry": "RMTC", "rmtc-part": "RMTC", "rmtc-records": "RMTC", "rmtc-approval": "RMTC",
    "inward-entry": "Inward", "inward-records": "Inward",
    "osp-home": "OSP", "osp-material-out": "OSP", "osp-sample-receipt": "OSP", "osp-inward": "OSP",
    "osp-dimensional": "OSP", "osp-metlab": "OSP", "osp-records": "OSP",
    "npd-process-flow": "NPD & APQP", "npd-status": "NPD & APQP", "apqp": "NPD & APQP",
    "qc-tools": "QC Calculation Tools", "qc-calculation-records": "QC Calculation Tools",
    "inspection-home": "Inspections", "inspection-layout-entry": "Inspections",
    "inspection-layout-records": "Inspections", "dimensional-entry": "Inspections",
    "dimensional-records": "Inspections", "metlab-entry": "Inspections", "metlab-records": "Inspections",
    "records-center": "Records", "heat-ledger": "Records",
    "reports-home": "Reports", "heat-transaction-report": "Reports", "osp-balance-report": "Reports",
    "templates": "Templates",
}

PAGE_TITLE_TO_PATH = {
    "Dashboard": "dashboard", "Masters": "masters", "RMTC Entry": "rmtc-entry",
    "Material Inward": "inward-entry", "OSP Transactions": "osp-home", "Inspections": "inspection-home",
    "Records Centre": "records-center", "Heat Steel Ledger": "heat-ledger",
    "Reports": "reports-home", "Heat Transaction Report": "heat-transaction-report",
    "OSP Heat Balance Report": "osp-balance-report",
    "Templates": "templates", "Part Master Entry": "part-entry",
    "Part Master Records": "part-records", "Process Master Entry": "process-entry",
    "Process Master Records": "process-records", "Material Grade Entry": "grade-entry",
    "Material Grade Records": "grade-records", "Reference Master Entry": "reference-entry",
    "Reference Master Records": "reference-records", "Employee Entry": "employee-entry",
    "Employee Records": "employee-records", "Users & Access": "user-access",
    "RMTC Part Worksheet": "rmtc-part", "RMTC Records": "rmtc-records",
    "RMTC Approval": "rmtc-approval", "Material Inward Records": "inward-records",
    "OSP Material Out": "osp-material-out", "OSP Sample Receipt": "osp-sample-receipt",
    "OSP Material Inward": "osp-inward", "OSP Dimensional": "osp-dimensional",
    "OSP MetLAB": "osp-metlab", "OSP Records": "osp-records",
    "Process Flow Designer": "npd-process-flow", "NPD Status": "npd-status", "APQP": "apqp",
    "QC Calculation Tools": "qc-tools", "QC Calculation Records": "qc-calculation-records",
    "Inspection Layout Entry": "inspection-layout-entry",
    "Inspection Layout Records": "inspection-layout-records",
    "Dimensional Report": "dimensional-entry", "Dimensional Records": "dimensional-records",
    "MetLAB Report": "metlab-entry", "MetLAB Records": "metlab-records",
}


nav = st.navigation(PAGES, position="hidden")
if render_shell_header(profile, nav.title):
    logout()

current_path = PAGE_TITLE_TO_PATH.get(nav.title, "dashboard")
current_module = ROUTE_MODULE.get(current_path, "Dashboard")

with st.container(border=True, key="fsi_top_nav"):
    st.markdown('<div class="fsi-top-menu-title">MODULES</div>', unsafe_allow_html=True)
    cols = st.columns(11, gap="small")
    labels = (
        ("dashboard", "Dashboard", "Dashboard"),
        ("masters", "Masters", "Masters"),
        ("rmtc-entry", "RMTC", "RMTC"),
        ("inward-entry", "Inward", "Inward"),
        ("osp-home", "OSP", "OSP"),
        ("npd-status", "NPD / APQP", "NPD & APQP"),
        ("qc-tools", "QC Tools", "QC Calculation Tools"),
        ("inspection-home", "Inspections", "Inspections"),
        ("records-center", "Records", "Records"),
        ("reports-home", "Reports", "Reports"),
        ("templates", "Templates", "Templates"),
    )
    for col, (path, label, module_name) in zip(cols, labels):
        page = PAGE_BY_PATH.get(path)
        if page is None:
            continue
        slug = path.replace('-', '_')
        container_key = f"menu_active_{slug}" if module_name == current_module else f"menu_{slug}"
        with col:
            with st.container(key=container_key):
                if path == "rmtc-entry":
                    if st.button(label, width="stretch", key="top_menu_new_rmtc"):
                        st.session_state["rmtc_entry_mode"] = "new"
                        st.session_state.pop("edit_rmtc_id", None)
                        st.session_state.pop("part_rmtc_id", None)
                        st.session_state.pop("new_rmtc_number", None)
                        st.switch_page(page)
                else:
                    st.page_link(page, label=label, width="stretch")

module_submenu(current_module, *MODULE_SUBMENUS[current_module])

nav.run()
app_footer()
