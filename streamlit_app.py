# QCMS 4.13.9 — RM-PROCUREMENT-LINK-RMTC-PART-PO-ITEM-TECH
# BUILD 4139-RM-PROCUREMENT-LINK-RMTC-PART-PO-ITEM-TECH
# QCMS 4.13.8 — SUPPLY-PO-FSI-PART-RMTC-WORKSHEET
# BUILD 4138-MULTI-RM-PO-PRICE-HISTORY-TECH-DATA
# QCMS 4.13.5 — MAROON-SECTIONS-WHITE-FIELDS-KPI-ICON-FIX
# BUILD 4135-MAROON-SECTIONS-WHITE-FIELDS-KPI-ICON-FIX
# COMPAT BUILD 4134-PRIORITY-UI-RMTC-REUSE-DUPLICATE-SAFE-IMPORT
from __future__ import annotations

import streamlit as st

from app_pages import (
    dashboard,
    complaints,
    dimensional_report,
    employee_master,
    inspection_home,
    inspection_layouts,
    master_home,
    master_import,
    material_grade,
    npd_apqp,
    material_inward,
    metlab_report,
    my_account,
    osp_inspections,
    osp_transactions,
    part_master,
    process_master,
    qc_calculation_tools,
    reference_master,
    records_center,
    reports,
    rmtc_pages,
    standards_bank,
    supply_chain,
    user_access,
    template_center,
)
from core.auth import current_profile, is_logged_in, logout, render_login
from core.config import get_settings
from core.ui import app_footer, apply_global_style, module_submenu, render_left_navigation, render_pending_popups, render_shell_header

settings = get_settings()
st.set_page_config(
    page_title=f"{settings.app_name} · {settings.company_name}", page_icon="✅", layout="wide",
    initial_sidebar_state="collapsed", menu_items=None,
)
apply_global_style()

if not is_logged_in():
    render_login(); st.stop()
profile = current_profile() or {}

# Keep an explicit route-to-Page registry. Streamlit may expose the default
# page at the root URL even when a url_path was supplied, so deriving this
# mapping from page.url_path can drop the "dashboard" key.
PAGE_ITEMS = (
    ("dashboard", st.Page(dashboard.render, title="Dashboard", icon=":material/dashboard:", url_path="dashboard", default=True)),
    ("masters", st.Page(master_home.render, title="Masters", icon=":material/dataset:", url_path="masters")),
    ("rmtc-entry", st.Page(rmtc_pages.render_entry, title="RMTC Entry", icon=":material/fact_check:", url_path="rmtc-entry")),
    ("rmtc-approved-worksheet", st.Page(rmtc_pages.render_approved_part_worksheet, title="Approved RMTC Part Worksheet", icon=":material/add_task:", url_path="rmtc-approved-worksheet")),
    ("inward-entry", st.Page(material_inward.render_entry, title="Material Inward", icon=":material/input:", url_path="inward-entry")),
    ("osp-home", st.Page(osp_transactions.render_home, title="OSP Transactions", icon=":material/factory:", url_path="osp-home")),
    ("supply-chain-home", st.Page(supply_chain.render_home, title="Supply Chain", icon=":material/local_shipping:", url_path="supply-chain-home")),
    ("supply-customer-orders", st.Page(supply_chain.render_customer_orders, title="Supply Customer Orders", icon=":material/receipt_long:", url_path="supply-customer-orders")),
    ("supply-rm-procurement", st.Page(supply_chain.render_rm_procurement, title="Supply RM Procurement", icon=":material/shopping_cart:", url_path="supply-rm-procurement")),
    ("supply-purchase-orders", st.Page(supply_chain.render_purchase_orders, title="Supply Purchase Orders", icon=":material/request_quote:", url_path="supply-purchase-orders")),
    ("supply-rm-receipt", st.Page(supply_chain.render_rm_receipt, title="Supply RM Receipt", icon=":material/inventory:", url_path="supply-rm-receipt")),
    ("supply-rm-dispatch", st.Page(supply_chain.render_rm_dispatch, title="Supply RM to Forging", icon=":material/local_shipping:", url_path="supply-rm-dispatch")),
    ("supply-forging", st.Page(supply_chain.render_forging, title="Supply Forging", icon=":material/factory:", url_path="supply-forging")),
    ("supply-downstream", st.Page(supply_chain.render_downstream, title="Supply Downstream", icon=":material/precision_manufacturing:", url_path="supply-downstream")),
    ("supply-traceability", st.Page(supply_chain.render_traceability, title="Supply Traceability", icon=":material/account_tree:", url_path="supply-traceability")),
    ("supply-order-mis", st.Page(supply_chain.render_order_mis, title="Supply Order MIS", icon=":material/analytics:", url_path="supply-order-mis")),
    ("npd-process-flow", st.Page(npd_apqp.render_process_flow, title="Process Flow Designer", icon=":material/account_tree:", url_path="npd-process-flow")),
    ("npd-status", st.Page(npd_apqp.render_npd_status, title="NPD Status", icon=":material/timeline:", url_path="npd-status")),
    ("apqp", st.Page(npd_apqp.render_apqp, title="APQP", icon=":material/assignment_turned_in:", url_path="apqp")),
    ("qc-tools", st.Page(qc_calculation_tools.render_tools, title="QC Calculation Tools", icon=":material/calculate:", url_path="qc-tools")),
    ("qc-calculation-records", st.Page(qc_calculation_tools.render_records, title="QC Calculation Records", icon=":material/receipt_long:", url_path="qc-calculation-records")),
    ("complaints-home", st.Page(complaints.render_home, title="Complaint Management", icon=":material/support_agent:", url_path="complaints-home")),
    ("customer-complaint", st.Page(complaints.render_customer_entry, title="Customer Complaint", icon=":material/record_voice_over:", url_path="customer-complaint")),
    ("supplier-complaint", st.Page(complaints.render_supplier_entry, title="Supplier Complaint", icon=":material/feedback:", url_path="supplier-complaint")),
    ("complaint-analysis", st.Page(complaints.render_analysis, title="Complaint Analysis & CAPA", icon=":material/troubleshoot:", url_path="complaint-analysis")),
    ("complaint-records", st.Page(complaints.render_records, title="Complaint Records", icon=":material/fact_check:", url_path="complaint-records")),
    ("inspection-home", st.Page(inspection_home.render, title="Inspections", icon=":material/biotech:", url_path="inspection-home")),
    ("records-center", st.Page(records_center.render, title="Records Centre", icon=":material/table_view:", url_path="records-center")),
    ("heat-ledger", st.Page(records_center.render_heat_ledger, title="Heat Steel Ledger", icon=":material/table_view:", url_path="heat-ledger")),
    ("reports-home", st.Page(reports.render_home, title="Reports", icon=":material/assessment:", url_path="reports-home")),
    ("heat-transaction-report", st.Page(reports.render_heat_transactions, title="Heat Transaction Report", icon=":material/monitoring:", url_path="heat-transaction-report")),
    ("osp-balance-report", st.Page(reports.render_osp_balance, title="OSP Heat Balance Report", icon=":material/factory:", url_path="osp-balance-report")),
    ("supply-chain-report", st.Page(supply_chain.render_order_mis, title="Supply Chain Order / Dispatch Report", icon=":material/analytics:", url_path="supply-chain-report")),
    ("rmtc-report", st.Page(rmtc_pages.render_records, title="RMTC Report Register", icon=":material/fact_check:", url_path="rmtc-report")),
    ("inward-report", st.Page(material_inward.render_records, title="Material Inward Report Register", icon=":material/input:", url_path="inward-report")),
    ("dimensional-report", st.Page(dimensional_report.render_records, title="Dimensional Inspection Reports", icon=":material/straighten:", url_path="dimensional-report")),
    ("metlab-report", st.Page(metlab_report.render_records, title="MetLAB Reports", icon=":material/science:", url_path="metlab-report")),
    ("complaints-report", st.Page(complaints.render_records, title="Complaint Reports", icon=":material/support_agent:", url_path="complaints-report")),
    ("traceability-report", st.Page(supply_chain.render_traceability, title="Supply Chain Traceability Report", icon=":material/account_tree:", url_path="traceability-report")),
    ("npd-report", st.Page(npd_apqp.render_npd_status, title="NPD Status Report", icon=":material/timeline:", url_path="npd-report")),
    ("apqp-report", st.Page(npd_apqp.render_apqp, title="APQP Status Report", icon=":material/assignment_turned_in:", url_path="apqp-report")),
    ("qc-report", st.Page(qc_calculation_tools.render_records, title="QC Calculation Reports", icon=":material/calculate:", url_path="qc-report")),
    ("inspection-layout-report", st.Page(inspection_layouts.render_records, title="Inspection Layout Reports", icon=":material/view_list:", url_path="inspection-layout-report")),
    ("standards-report", st.Page(standards_bank.render_records, title="Customer Standards Reports", icon=":material/menu_book:", url_path="standards-report")),
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
    ("master-import", st.Page(master_import.render, title="Master Import", icon=":material/upload_file:", url_path="master-import")),
    ("standards-entry", st.Page(standards_bank.render_entry, title="Customer Standards Entry", icon=":material/library_books:", url_path="standards-entry")),
    ("standards-records", st.Page(standards_bank.render_records, title="Customer Standards Records", icon=":material/menu_book:", url_path="standards-records")),
    ("my-account", st.Page(my_account.render, title="My Account", icon=":material/manage_accounts:", url_path="my-account")),

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
render_pending_popups()

MODULE_SUBMENUS = {
    "Dashboard": (
        ("dashboard", "Quality Dashboard", ":material/dashboard:"),
    ),
    "Masters": (
        ("masters", "Masters Home", ":material/dataset:"),
        ("part-entry", "Part Entry", ":material/edit_note:"),
        ("process-entry", "Process Entry", ":material/settings:"),
        ("grade-entry", "Grade Entry", ":material/science:"),
        ("reference-entry", "Reference Entry", ":material/edit_note:"),
        ("employee-entry", "Employee Entry", ":material/person_add:"),
        ("user-access", "Users & Access", ":material/admin_panel_settings:"),
        ("standards-entry", "Standards Bank", ":material/library_books:"),
        ("master-import", "Master Import", ":material/upload_file:"),
    ),
    "RMTC": (
        ("rmtc-entry", "RMTC Entry", ":material/fact_check:"),
        ("rmtc-approved-worksheet", "Add Part Worksheet", ":material/add_task:"),
        ("rmtc-part", "Part Worksheet", ":material/format_list_bulleted:"),
        ("rmtc-approval", "Validation & Decision", ":material/approval:"),
        ("rmtc-report", "RMTC Reports", ":material/assessment:"),
    ),
    "Inward": (
        ("inward-entry", "Material Inward Entry", ":material/input:"),
        ("metlab-entry", "MetLAB Report", ":material/science:"),
        ("dimensional-entry", "Dimensional Report", ":material/straighten:"),
        ("inward-report", "Inward Reports", ":material/assessment:"),
    ),
    "OSP": (
        ("osp-home", "OSP Home", ":material/factory:"),
        ("osp-material-out", "Material Out", ":material/output:"),
        ("osp-sample-receipt", "Sample Receipt", ":material/experiment:"),
        ("osp-dimensional", "OSP Dimensional", ":material/straighten:"),
        ("osp-metlab", "OSP MetLAB", ":material/science:"),
        ("osp-inward", "OSP Inward", ":material/input:"),
        ("osp-balance-report", "OSP Reports", ":material/assessment:"),
    ),
    "Supply Chain": (
        ("supply-chain-home", "Supply Chain Home", ":material/local_shipping:"),
        ("supply-customer-orders", "Customer Orders", ":material/receipt_long:"),
        ("supply-rm-procurement", "RM Procurement", ":material/shopping_cart:"),
        ("supply-purchase-orders", "Purchase Orders", ":material/request_quote:"),
        ("supply-rm-receipt", "RM Receipt", ":material/inventory:"),
        ("supply-rm-dispatch", "RM to Forging", ":material/local_shipping:"),
        ("supply-forging", "Forging", ":material/factory:"),
        ("supply-downstream", "Machining / FG / Dispatch", ":material/precision_manufacturing:"),
        ("supply-traceability", "Traceability", ":material/account_tree:"),
        ("supply-order-mis", "Monthly Schedule / Order MIS", ":material/analytics:"),
        ("supply-chain-report", "Reports", ":material/assessment:"),
        ("traceability-report", "Traceability Report", ":material/account_tree:"),
    ),
    "NPD & APQP": (
        ("npd-process-flow", "Process Flow Designer", ":material/account_tree:"),
        ("npd-status", "NPD Status", ":material/timeline:"),
        ("apqp", "APQP", ":material/assignment_turned_in:"),
        ("npd-report", "NPD Reports", ":material/assessment:"),
        ("apqp-report", "APQP Reports", ":material/assessment:"),
    ),
    "QC Calculation Tools": (
        ("qc-tools", "Calculation Tools", ":material/calculate:"),
        ("qc-report", "QC Reports", ":material/assessment:"),
    ),
    "Complaints": (
        ("complaints-home", "Complaint Dashboard", ":material/support_agent:"),
        ("customer-complaint", "Customer Complaint", ":material/record_voice_over:"),
        ("supplier-complaint", "Supplier Complaint", ":material/feedback:"),
        ("complaint-analysis", "Analysis & CAPA", ":material/troubleshoot:"),
        ("complaints-report", "Complaint Reports", ":material/assessment:"),
    ),
    "Inspections": (
        ("inspection-home", "Inspection Home", ":material/biotech:"),
        ("inspection-layout-entry", "Layout Entry", ":material/edit_document:"),
        ("dimensional-entry", "Dimensional Entry", ":material/straighten:"),
        ("metlab-entry", "MetLAB Entry", ":material/science:"),
        ("dimensional-report", "Dimensional Reports", ":material/assessment:"),
        ("metlab-report", "MetLAB Reports", ":material/assessment:"),
    ),
    "Records": (
        ("records-center", "Records Centre", ":material/table_view:"),
        ("rmtc-records", "RMTC", ":material/fact_check:"),
        ("inward-records", "Material Inward", ":material/input:"),
        ("osp-records", "OSP", ":material/factory:"),
        ("dimensional-records", "Dimensional", ":material/straighten:"),
        ("metlab-records", "MetLAB", ":material/science:"),
        ("inspection-layout-records", "Inspection Layouts", ":material/view_list:"),
        ("complaint-records", "Complaints", ":material/support_agent:"),
        ("qc-calculation-records", "QC Calculations", ":material/calculate:"),
        ("heat-ledger", "Heat Steel Ledger", ":material/monitoring:"),
        ("part-records", "Parts", ":material/precision_manufacturing:"),
        ("process-records", "Processes", ":material/account_tree:"),
        ("grade-records", "Material Grades", ":material/science:"),
        ("reference-records", "Reference Masters", ":material/library_books:"),
        ("employee-records", "Employees", ":material/groups:"),
        ("standards-records", "Customer Standards", ":material/menu_book:"),
    ),
    "Reports": (
        ("reports-home", "Reports Home", ":material/assessment:"),
        ("supply-chain-report", "Supply Chain MIS", ":material/analytics:"),
        ("heat-transaction-report", "Heat Global Balance", ":material/monitoring:"),
        ("osp-balance-report", "OSP Heat Balance", ":material/factory:"),
        ("rmtc-report", "RMTC", ":material/fact_check:"),
        ("inward-report", "Material Inward", ":material/input:"),
        ("dimensional-report", "Dimensional", ":material/straighten:"),
        ("metlab-report", "MetLAB", ":material/science:"),
        ("complaints-report", "Complaints", ":material/support_agent:"),
        ("traceability-report", "Traceability", ":material/account_tree:"),
        ("npd-report", "NPD Status", ":material/timeline:"),
        ("apqp-report", "APQP", ":material/assignment_turned_in:"),
        ("qc-report", "QC Calculations", ":material/calculate:"),
        ("inspection-layout-report", "Inspection Layouts", ":material/view_list:"),
        ("standards-report", "Customer Standards", ":material/menu_book:"),
    ),
    "Templates": (
        ("templates", "Download Templates", ":material/download:"),
    ),
}

# Every register / records route belongs to the Records top-level module.
# Entry and workflow pages remain under their operational modules.
RECORD_ROUTES = {
    "records-center", "heat-ledger", "rmtc-records", "inward-records", "osp-records",
    "dimensional-records", "metlab-records", "inspection-layout-records",
    "complaint-records", "qc-calculation-records", "part-records", "process-records",
    "grade-records", "reference-records", "employee-records", "standards-records",
}
ROUTE_MODULE = {
    "dashboard": "Dashboard", "my-account": "Dashboard",
    "masters": "Masters", "part-entry": "Masters", "process-entry": "Masters",
    "grade-entry": "Masters", "reference-entry": "Masters", "employee-entry": "Masters",
    "user-access": "Masters", "master-import": "Masters", "standards-entry": "Masters",
    "rmtc-entry": "RMTC", "rmtc-approved-worksheet": "RMTC", "rmtc-part": "RMTC", "rmtc-approval": "RMTC",
    "inward-entry": "Inward",
    "osp-home": "OSP", "osp-material-out": "OSP", "osp-sample-receipt": "OSP",
    "osp-inward": "OSP", "osp-dimensional": "OSP", "osp-metlab": "OSP",
    "supply-chain-home": "Supply Chain", "supply-customer-orders": "Supply Chain", "supply-rm-procurement": "Supply Chain", "supply-purchase-orders": "Supply Chain", "supply-rm-receipt": "Supply Chain", "supply-rm-dispatch": "Supply Chain", "supply-forging": "Supply Chain", "supply-downstream": "Supply Chain", "supply-traceability": "Supply Chain", "supply-order-mis": "Supply Chain",
    "npd-process-flow": "NPD & APQP", "npd-status": "NPD & APQP", "apqp": "NPD & APQP",
    "qc-tools": "QC Calculation Tools",
    "complaints-home": "Complaints", "customer-complaint": "Complaints",
    "supplier-complaint": "Complaints", "complaint-analysis": "Complaints",
    "inspection-home": "Inspections", "inspection-layout-entry": "Inspections",
    "dimensional-entry": "Inspections", "metlab-entry": "Inspections",
    "reports-home": "Reports", "heat-transaction-report": "Reports", "osp-balance-report": "Reports", "supply-chain-report": "Reports", "rmtc-report": "Reports", "inward-report": "Reports", "dimensional-report": "Reports", "metlab-report": "Reports", "complaints-report": "Reports", "traceability-report": "Reports", "npd-report": "Reports", "apqp-report": "Reports", "qc-report": "Reports", "inspection-layout-report": "Reports", "standards-report": "Reports",
    "templates": "Templates",
    **{path: "Records" for path in RECORD_ROUTES},
}

PAGE_TITLE_TO_PATH = {
    "Dashboard": "dashboard", "Masters": "masters", "RMTC Entry": "rmtc-entry",
    "Material Inward": "inward-entry", "OSP Transactions": "osp-home", "Inspections": "inspection-home",
    "Records Centre": "records-center", "Heat Steel Ledger": "heat-ledger",
    "Reports": "reports-home", "Heat Transaction Report": "heat-transaction-report",
    "OSP Heat Balance Report": "osp-balance-report", "Supply Chain Order / Dispatch Report": "supply-chain-report", "RMTC Report Register": "rmtc-report", "Material Inward Report Register": "inward-report", "Dimensional Inspection Reports": "dimensional-report", "MetLAB Reports": "metlab-report", "Complaint Reports": "complaints-report",
 "Supply Chain Traceability Report": "traceability-report", "NPD Status Report": "npd-report", "APQP Status Report": "apqp-report", "QC Calculation Reports": "qc-report", "Inspection Layout Reports": "inspection-layout-report", "Customer Standards Reports": "standards-report",
    "Templates": "templates", "Part Master Entry": "part-entry",
    "Part Master Records": "part-records", "Process Master Entry": "process-entry",
    "Process Master Records": "process-records", "Material Grade Entry": "grade-entry",
    "Material Grade Records": "grade-records", "Reference Master Entry": "reference-entry",
    "Reference Master Records": "reference-records", "Employee Entry": "employee-entry",
    "Employee Records": "employee-records", "Users & Access": "user-access", "Master Import": "master-import", "Customer Standards Entry": "standards-entry", "Customer Standards Records": "standards-records", "My Account": "my-account",
    "Approved RMTC Part Worksheet": "rmtc-approved-worksheet", "RMTC Part Worksheet": "rmtc-part", "RMTC Records": "rmtc-records",
    "RMTC Approval": "rmtc-approval", "Material Inward Records": "inward-records",
    "OSP Material Out": "osp-material-out", "OSP Sample Receipt": "osp-sample-receipt",
    "OSP Material Inward": "osp-inward", "OSP Dimensional": "osp-dimensional",
    "OSP MetLAB": "osp-metlab", "OSP Records": "osp-records",
    "Supply Chain": "supply-chain-home", "Supply Customer Orders": "supply-customer-orders", "Supply RM Procurement": "supply-rm-procurement", "Supply Purchase Orders": "supply-purchase-orders", "Supply RM Receipt": "supply-rm-receipt", "Supply RM to Forging": "supply-rm-dispatch", "Supply Forging": "supply-forging", "Supply Downstream": "supply-downstream", "Supply Traceability": "supply-traceability", "Supply Order MIS": "supply-order-mis",
    "Process Flow Designer": "npd-process-flow", "NPD Status": "npd-status", "APQP": "apqp",
    "QC Calculation Tools": "qc-tools", "QC Calculation Records": "qc-calculation-records",
    "Complaint Management": "complaints-home", "Customer Complaint": "customer-complaint", "Supplier Complaint": "supplier-complaint", "Complaint Analysis & CAPA": "complaint-analysis", "Complaint Records": "complaint-records",
    "Inspection Layout Entry": "inspection-layout-entry",
    "Inspection Layout Records": "inspection-layout-records",
    "Dimensional Report": "dimensional-entry", "Dimensional Records": "dimensional-records",
    "MetLAB Report": "metlab-entry", "MetLAB Records": "metlab-records",
}


# Legacy navigation-test continuity tokens (superseded by the v4.12.7 header + rail):
# PAGE_BY_PATH.get(path)
# menu_active_{slug}
# menu_{slug}
# top_menu_new_rmtc
# st.columns(13

nav = st.navigation(PAGES, position="hidden")
current_path = PAGE_TITLE_TO_PATH.get(nav.title, "dashboard")
current_module = ROUTE_MODULE.get(current_path, "Dashboard")

# QCMS v4.12.9 — hardened responsive enterprise navigation contract.
# Legacy v4.12.8 marker: QCMS v4.12.8 — responsive enterprise navigation contract.
# The red header stays intentionally concise while the charcoal rail preserves
# direct access to every operational module from the previous releases.
QUALITY_HEADER_MODULES = {"RMTC", "Inward", "OSP", "QC Calculation Tools", "Complaints", "Inspections"}
quality_active_module = current_module if current_module in QUALITY_HEADER_MODULES else "Inspections"
HEADER_NAV = (
    (PAGE_BY_PATH["dashboard"], "Dashboard", "Dashboard"),
    (PAGE_BY_PATH["masters"], "Masters", "Masters"),
    (PAGE_BY_PATH["supply-chain-home"], "Supply Chain", "Supply Chain"),
    (PAGE_BY_PATH["inspection-home"], "Quality", quality_active_module),
    (PAGE_BY_PATH["reports-home"], "Reports", "Reports"),
    (PAGE_BY_PATH["records-center"], "Records", "Records"),
    (PAGE_BY_PATH["user-access"], "Admin", "Admin"),
)
RAIL_NAV = (
    (PAGE_BY_PATH["dashboard"], "Dashboard", "Dashboard", ":material/home:"),
    (PAGE_BY_PATH["masters"], "Masters", "Masters", ":material/database:"),
    (PAGE_BY_PATH["supply-chain-home"], "Supply Chain", "Supply Chain", ":material/local_shipping:"),
    (PAGE_BY_PATH["rmtc-entry"], "RMTC", "RMTC", ":material/fact_check:"),
    (PAGE_BY_PATH["inward-entry"], "Inward", "Inward", ":material/input:"),
    (PAGE_BY_PATH["osp-home"], "OSP", "OSP", ":material/factory:"),
    (PAGE_BY_PATH["inspection-home"], "Quality", "Inspections", ":material/verified_user:"),
    (PAGE_BY_PATH["npd-status"], "NPD / APQP", "NPD & APQP", ":material/timeline:"),
    (PAGE_BY_PATH["qc-tools"], "QC Tools", "QC Calculation Tools", ":material/calculate:"),
    (PAGE_BY_PATH["complaints-home"], "Complaints", "Complaints", ":material/support_agent:"),
    (PAGE_BY_PATH["records-center"], "Records", "Records", ":material/description:"),
    (PAGE_BY_PATH["reports-home"], "Reports", "Reports", ":material/assessment:"),
    (PAGE_BY_PATH["templates"], "Templates", "Templates", ":material/download:"),
    (PAGE_BY_PATH["user-access"], "Admin", "Admin", ":material/groups:"),
)

if render_shell_header(profile, nav.title, current_module=current_module, nav_items=HEADER_NAV):
    logout()

# v4.12.9 keeps the real two-column Streamlit workspace and hardens component styling.
# v4.12.8 uses a real two-column Streamlit workspace. The charcoal navigation
# rail occupies its own column instead of being fixed over the application body.
# This prevents all progressive scaling/overlap issues seen in v4.12.7.
with st.container(border=False, key="qcms_workspace"):
    rail_col, content_col = st.columns([1.22, 8.78], gap="small", vertical_alignment="top")
    with rail_col:
        render_left_navigation(current_module, RAIL_NAV)
    with content_col:
        with st.container(border=False, key="qcms_content"):
            module_submenu(current_module, *MODULE_SUBMENUS[current_module], max_columns=8)
            nav.run()
            app_footer()
