# QCMS 4.14.48 — PO 5% WATERMARK + APPROVER NAME + SESSION STABILITY + ANDROID EVERY RELEASE
# BUILD 41448-PO-WATERMARK05-APPROVER-SESSION-STABILITY-ANDROID-EVERY-RELEASE
# PRESERVED PREVIOUS BUILD MARKER: 41447-PO-WATERMARK-20-APPROVER-STAMP
# PRESERVED PREVIOUS BUILD MARKER: 41446-ANDROID-V12-DRAWER-PERSISTENT-AUTH
# PRESERVED PREVIOUS BUILD MARKER: 41445-SHARED-RAW-SOURCE-LAYOUT-CONTROL
# PRESERVED PREVIOUS BUILD MARKER: 41444-ANDROID-NATIVE-MENU-SUBMENU-RESTORE
# PRESERVED PREVIOUS BUILD MARKER: 41443-ANDROID-STREAMLIT-SIDEBAR-NAV
# PRESERVED PREVIOUS BUILD MARKER: 41441-ANDROID-LAMBDA-COMPILE-PERMANENT-FIX
# PRESERVED PREVIOUS BUILD MARKER: 41439-ANDROID-CI-SIGNATURE-PERMANENT-FIX
# QCMS 4.14.19 — PO-LIVE-EMPLOYEE-DELETE-USER-STATUS-SAME-HEAT-CONFIRMATION-IMAGES
# BUILD 41434-INDIVIDUAL-PO-PDF-ZIP-ANDROID-APK-BUILD
# QCMS 4.14.15 — DIRECT-PRODUCTION-FLOW-EMAIL-TEMPLATE-TEST
# BUILD 41415-DIRECT-PRODUCTION-FLOW-EMAIL-TEMPLATE-TEST
# QCMS 4.14.13 — METLAB-CASE-DEPTH-RECORD-EMAIL-TEMPLATE-TEST-CONFIRM
# BUILD 41413-METLAB-CASE-DEPTH-RECORD-EMAIL-TEMPLATE-TEST-CONFIRM
# QCMS 4.14.12 — RM-TYPE-PO-RM-DETAILS-FORGING-FILTER-DUPLICATE-GUARD
# BUILD 41412-RM-TYPE-PO-RM-DETAILS-FORGING-FILTER-DUPLICATE-GUARD
# QCMS 4.14.6 — LIVE-RUNTIME-DIAGNOSTICS-FORCE-REDEPLOY
# BUILD 4146-LIVE-RUNTIME-DIAGNOSTICS-FORCE-REDEPLOY
# QCMS 4.14.5 — DEPLOY-VERIFY-DIRECT-REPORT-EDIT-SMTP-TENANT-GUIDE
# BUILD 4145-DEPLOY-VERIFY-DIRECT-REPORT-EDIT-SMTP-TENANT-GUIDE
# QCMS 4.14.4 — METLAB-EDIT-MASTER-DUPLICATE-OPENING-IMPORT-SMTP-GUIDE
# BUILD 4144-METLAB-EDIT-MASTER-DUPLICATE-OPENING-IMPORT-SMTP-GUIDE
# QCMS 4.14.3 — PART-GRADES-LEADTIME-OPENING-STOCK-PASSWORD-EDIT-O365
# BUILD 4143-PART-GRADES-LEADTIME-OPENING-STOCK-PASSWORD-EDIT-O365
# QCMS 4.14.2 — PO-ORDER-VISIBILITY-FULL-PRICE-HISTORY
# BUILD 4142-PO-ORDER-VISIBILITY-FULL-PRICE-HISTORY
# COMPAT BUILD 4140-PO-SOURCE-RMTC-VALIDATION-HSN-EMAIL
# QCMS 4.13.8 — SUPPLY-PO-FSI-PART-RMTC-WORKSHEET
# BUILD 4138-MULTI-RM-PO-PRICE-HISTORY-TECH-DATA
# QCMS 4.13.5 — MAROON-SECTIONS-WHITE-FIELDS-KPI-ICON-FIX
# BUILD 4135-MAROON-SECTIONS-WHITE-FIELDS-KPI-ICON-FIX
# COMPAT BUILD 4134-PRIORITY-UI-RMTC-REUSE-DUPLICATE-SAFE-IMPORT
from __future__ import annotations

import streamlit as st

from app_pages import (
    dashboard,
    deployment_diagnostics,
    complaints,
    calibration_validation,
    company_branch,
    dimensional_report,
    employee_master,
    email_settings,
    global_search,
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
from core.auth import (
    current_profile,
    is_logged_in,
    logout,
    render_login,
    restore_persistent_login,
    service_persistent_auth_bridge,
    sync_persistent_login_browser,
)
from core.access import module_permissions
from core.activity import log_route_view
from core.config import get_settings
from core.ui import app_footer, apply_global_style, module_submenu, render_left_navigation, render_pending_popups, render_shell_header

settings = get_settings()
st.set_page_config(
    page_title=f"{settings.app_name} · {settings.company_name}", page_icon="✅", layout="wide",
    initial_sidebar_state="collapsed", menu_items=None,
)
apply_global_style()

# QCMS v4.14.46 persistent-login contract. A browser refresh or Android direct
# route creates a fresh Streamlit WebSocket/Python session. Restore from the
# origin-scoped Components-v2 localStorage bridge before showing Login; secure
# same-origin cookies remain as a fast fallback for WebView/browser refreshes.
_auth_clearing = service_persistent_auth_bridge()
if not is_logged_in() and not _auth_clearing:
    restore_persistent_login()
if not is_logged_in() and st.session_state.pop("_qcms_auth_restore_pending", False):
    # First Components-v2 mount returns asynchronously and triggers an immediate
    # rerun. Do not flash the Login screen while persistent auth is being read.
    st.caption("Restoring QCMS session…")
    st.stop()
if not is_logged_in():
    # A failed restore queues localStorage + cookie deletion to prevent invalid
    # token loops, then falls back to normal interactive login.
    service_persistent_auth_bridge()
    render_login(); st.stop()
profile = current_profile() or {}
sync_persistent_login_browser()
service_persistent_auth_bridge()

# Native Android / iPhone / iPad wrappers own the navigation chrome. Once the
# wrapper marks the session, never render the long desktop rail/module submenu or
# Streamlit footer inside the WebView. This survives Streamlit page switches even
# if the query string is later normalized by the framework.
_native_value = str(st.query_params.get("native_mobile", "") or "").strip().casefold()
_native_nav_value = str(st.query_params.get("native_nav", "") or "").strip().casefold()
try:
    _native_user_agent = str(st.context.headers.get("User-Agent", "") or "")
except Exception:
    _native_user_agent = ""
_native_android = "QCMSMobile/" in _native_user_agent
_native_ios = "QCMSMobileIOS/" in _native_user_agent
if _native_value in {"1", "true", "yes", "native"} or _native_android or _native_ios:
    st.session_state["_qcms_native_mobile"] = True
native_mobile = bool(st.session_state.get("_qcms_native_mobile"))
# Android v0.2.1 uses a compact native top bar only to open Streamlit's official sidebar; page navigation itself remains owned by Streamlit.
# This removes route-click timing bridges from the active Android path while preserving the authenticated WebView session and the iPhone/iPad native drawer.
android_native_drawer = bool(
    native_mobile
    and _native_android
    and (_native_nav_value in {"native", "drawer", "v12"} or "QCMSMobile/0.2.2" in _native_user_agent)
)
android_streamlit_nav = bool(
    native_mobile
    and _native_android
    and not android_native_drawer
    and (_native_nav_value in {"streamlit", "sidebar", "web"} or "QCMSMobile/0.2.0" in _native_user_agent or "QCMSMobile/0.2.1" in _native_user_agent)
)

# Keep an explicit route-to-Page registry. Streamlit may expose the default
# page at the root URL even when a url_path was supplied, so deriving this
# mapping from page.url_path can drop the "dashboard" key.
PAGE_ITEMS = (
    ("dashboard", st.Page(dashboard.render, title="Dashboard", icon=":material/dashboard:", url_path="dashboard", default=True)),
    ("deployment-diagnostics", st.Page(deployment_diagnostics.render, title="Deployment Diagnostics", icon=":material/verified:", url_path="deployment-diagnostics")),
    ("masters", st.Page(master_home.render, title="Masters", icon=":material/dataset:", url_path="masters")),
    ("company-branch-entry", st.Page(company_branch.render_entry, title="Company Branch Master", icon=":material/account_balance:", url_path="company-branch-entry")),
    ("company-branch-records", st.Page(company_branch.render_records, title="Company Branch Records", icon=":material/table_view:", url_path="company-branch-records")),
    ("rmtc-entry", st.Page(rmtc_pages.render_entry, title="RMTC Entry", icon=":material/fact_check:", url_path="rmtc-entry")),
    ("rmtc-approved-worksheet", st.Page(rmtc_pages.render_approved_part_worksheet, title="Approved RMTC Part Worksheet", icon=":material/add_task:", url_path="rmtc-approved-worksheet")),
    ("inward-entry", st.Page(material_inward.render_entry, title="Material Inward", icon=":material/input:", url_path="inward-entry")),
    ("osp-home", st.Page(osp_transactions.render_home, title="OSP Transactions", icon=":material/factory:", url_path="osp-home")),
    ("supply-chain-home", st.Page(supply_chain.render_home, title="Supply Chain", icon=":material/local_shipping:", url_path="supply-chain-home")),
    ("supply-customer-orders", st.Page(supply_chain.render_customer_orders, title="Supply Customer Orders", icon=":material/receipt_long:", url_path="supply-customer-orders")),
    ("supply-opening-stock", st.Page(supply_chain.render_opening_stock, title="Opening Stock & Import", icon=":material/inventory_2:", url_path="supply-opening-stock")),
    ("supply-rm-procurement", st.Page(supply_chain.render_rm_procurement, title="Supply RM Procurement", icon=":material/shopping_cart:", url_path="supply-rm-procurement")),
    ("supply-purchase-orders", st.Page(supply_chain.render_purchase_orders, title="Supply Purchase Orders", icon=":material/request_quote:", url_path="supply-purchase-orders")),
    ("supply-po-order-list", st.Page(supply_chain.render_purchase_order_list, title="Purchase Order List", icon=":material/list_alt:", url_path="supply-po-order-list")),
    ("supply-po-edit", st.Page(supply_chain.render_purchase_order_edit_page, title="Edit Purchase Order", icon=":material/edit_note:", url_path="supply-po-edit")),
    ("supply-po-pdf", st.Page(supply_chain.render_purchase_order_pdf_page, title="Purchase Order PDF", icon=":material/picture_as_pdf:", url_path="supply-po-pdf")),
    ("supply-po-approval", st.Page(supply_chain.render_purchase_order_approval_page, title="Purchase Order Approval", icon=":material/approval:", url_path="supply-po-approval")),
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
    ("customer-complaint-register", st.Page(complaints.render_customer_register, title="Customer Complaint Register", icon=":material/table_view:", url_path="customer-complaint-register")),
    ("supplier-complaint-register", st.Page(complaints.render_supplier_register, title="Supplier Complaint Register", icon=":material/table_view:", url_path="supplier-complaint-register")),
    ("complaint-email-settings", st.Page(complaints.render_email_configuration, title="Complaint Email Configuration", icon=":material/forward_to_inbox:", url_path="complaint-email-settings")),
    ("calibration-validation", st.Page(calibration_validation.render_calibration_validation, title="Calibration & Validation", icon=":material/straighten:", url_path="calibration-validation")),
    ("standard-room-inspection", st.Page(calibration_validation.render_standard_room, title="Standard Room Inspection", icon=":material/biotech:", url_path="standard-room-inspection")),
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
    ("email-settings", st.Page(email_settings.render, title="Email Server & Notifications", icon=":material/forward_to_inbox:", url_path="email-settings")),
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
    ("bend-test-entry", st.Page(metlab_report.render_bend_test_entry, title="Bend Test Report", icon=":material/architecture:", url_path="bend-test-entry")),
    ("bend-test-records", st.Page(metlab_report.render_bend_test_records, title="Bend Test Records", icon=":material/table_view:", url_path="bend-test-records")),
    ("bend-test-report", st.Page(metlab_report.render_bend_test_records, title="Bend Test Reports", icon=":material/assessment:", url_path="bend-test-report")),
    ("global-search", st.Page(global_search.render, title="Global Search", icon=":material/search:", url_path="global-search")),
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
        ("company-branch-entry", "Company Branch", ":material/account_balance:"),
        ("part-entry", "Part Entry", ":material/edit_note:"),
        ("process-entry", "Process Entry", ":material/settings:"),
        ("grade-entry", "Grade Entry", ":material/science:"),
        ("reference-entry", "Reference Entry", ":material/edit_note:"),
        ("employee-entry", "Employee Entry", ":material/person_add:"),
        ("user-access", "Users & Access", ":material/admin_panel_settings:"),
        ("standards-entry", "Standards Bank", ":material/library_books:"),
        ("master-import", "Master Import", ":material/upload_file:"),
    ),
    "Admin": (
        ("user-access", "Users & Access", ":material/admin_panel_settings:"),
        ("email-settings", "Email Server & Notifications", ":material/forward_to_inbox:"),
        ("deployment-diagnostics", "Deployment Diagnostics", ":material/verified:"),
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
        ("supply-opening-stock", "Opening Stock & Import", ":material/inventory_2:"),
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
        ("customer-complaint-register", "Customer Register", ":material/table_view:"),
        ("supplier-complaint-register", "Supplier Register", ":material/table_view:"),
        ("complaint-analysis", "Analysis & CAPA", ":material/troubleshoot:"),
        ("complaint-email-settings", "Email / Reminders", ":material/forward_to_inbox:"),
        ("complaints-report", "Complaint Reports", ":material/assessment:"),
    ),
    "Calibration & Validation": (
        ("calibration-validation", "Gauges / Fixtures", ":material/straighten:"),
        ("standard-room-inspection", "Standard Room Inspection", ":material/biotech:"),
    ),
    "Inspections": (
        ("inspection-home", "Inspection Home", ":material/biotech:"),
        ("inspection-layout-entry", "Layout Entry", ":material/edit_document:"),
        ("dimensional-entry", "Dimensional Entry", ":material/straighten:"),
        ("metlab-entry", "MetLAB Entry", ":material/science:"),
        ("bend-test-entry", "Bend Test Entry", ":material/architecture:"),
        ("dimensional-report", "Dimensional Reports", ":material/assessment:"),
        ("metlab-report", "MetLAB Reports", ":material/assessment:"),
        ("bend-test-report", "Bend Test Reports", ":material/assessment:"),
    ),
    "Records": (
        ("records-center", "Records Centre", ":material/table_view:"),
        ("rmtc-records", "RMTC", ":material/fact_check:"),
        ("inward-records", "Material Inward", ":material/input:"),
        ("osp-records", "OSP", ":material/factory:"),
        ("dimensional-records", "Dimensional", ":material/straighten:"),
        ("metlab-records", "MetLAB", ":material/science:"),
        ("bend-test-records", "Bend Test", ":material/architecture:"),
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
        ("bend-test-report", "Bend Test", ":material/architecture:"),
        ("complaints-report", "Complaints", ":material/support_agent:"),
        ("traceability-report", "Traceability", ":material/account_tree:"),
        ("npd-report", "NPD Status", ":material/timeline:"),
        ("apqp-report", "APQP", ":material/assignment_turned_in:"),
        ("qc-report", "QC Calculations", ":material/calculate:"),
        ("inspection-layout-report", "Inspection Layouts", ":material/view_list:"),
        ("standards-report", "Customer Standards", ":material/menu_book:"),
    ),
    "Search": (
        ("global-search", "Global Search", ":material/search:"),
    ),
    "Templates": (
        ("templates", "Download Templates", ":material/download:"),
    ),
}

# Every register / records route belongs to the Records top-level module.
# Entry and workflow pages remain under their operational modules.
RECORD_ROUTES = {
    "records-center", "heat-ledger", "rmtc-records", "inward-records", "osp-records",
    "dimensional-records", "metlab-records", "bend-test-records", "inspection-layout-records",
    "complaint-records", "qc-calculation-records", "part-records", "process-records",
    "grade-records", "reference-records", "employee-records", "standards-records",
}
ROUTE_MODULE = {
    "dashboard": "Dashboard", "my-account": "Dashboard",
    "masters": "Masters", "company-branch-entry": "Masters", "company-branch-records": "Masters", "part-entry": "Masters", "process-entry": "Masters",
    "grade-entry": "Masters", "reference-entry": "Masters", "employee-entry": "Masters",
    "user-access": "Admin", "email-settings": "Admin", "deployment-diagnostics": "Admin", "master-import": "Masters", "standards-entry": "Masters",
    "rmtc-entry": "RMTC", "rmtc-approved-worksheet": "RMTC", "rmtc-part": "RMTC", "rmtc-approval": "RMTC",
    "inward-entry": "Inward",
    "osp-home": "OSP", "osp-material-out": "OSP", "osp-sample-receipt": "OSP",
    "osp-inward": "OSP", "osp-dimensional": "OSP", "osp-metlab": "OSP",
    "supply-chain-home": "Supply Chain", "supply-customer-orders": "Supply Chain", "supply-opening-stock": "Supply Chain", "supply-rm-procurement": "Supply Chain", "supply-purchase-orders": "Supply Chain", "supply-po-order-list": "Supply Chain", "supply-po-edit": "Supply Chain", "supply-po-pdf": "Supply Chain", "supply-po-approval": "Supply Chain", "supply-rm-receipt": "Supply Chain", "supply-rm-dispatch": "Supply Chain", "supply-forging": "Supply Chain", "supply-downstream": "Supply Chain", "supply-traceability": "Supply Chain", "supply-order-mis": "Supply Chain",
    "npd-process-flow": "NPD & APQP", "npd-status": "NPD & APQP", "apqp": "NPD & APQP",
    "qc-tools": "QC Calculation Tools",
    "complaints-home": "Complaints", "customer-complaint": "Complaints",
    "supplier-complaint": "Complaints", "customer-complaint-register": "Complaints", "supplier-complaint-register": "Complaints",
    "complaint-analysis": "Complaints", "complaint-email-settings": "Complaints",
    "calibration-validation": "Calibration & Validation", "standard-room-inspection": "Calibration & Validation",
    "inspection-home": "Inspections", "inspection-layout-entry": "Inspections",
    "dimensional-entry": "Inspections", "metlab-entry": "Inspections", "bend-test-entry": "Inspections",
    "global-search": "Search",
    "reports-home": "Reports", "heat-transaction-report": "Reports", "osp-balance-report": "Reports", "supply-chain-report": "Reports", "rmtc-report": "Reports", "inward-report": "Reports", "dimensional-report": "Reports", "metlab-report": "Reports", "bend-test-report": "Reports", "complaints-report": "Reports", "traceability-report": "Reports", "npd-report": "Reports", "apqp-report": "Reports", "qc-report": "Reports", "inspection-layout-report": "Reports", "standards-report": "Reports",
    "templates": "Templates",
    **{path: "Records" for path in RECORD_ROUTES},
}

PAGE_TITLE_TO_PATH = {
    "Dashboard": "dashboard", "Masters": "masters", "Company Branch Master": "company-branch-entry", "Company Branch Records": "company-branch-records", "RMTC Entry": "rmtc-entry",
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
    "Employee Records": "employee-records", "Users & Access": "user-access", "Email Server & Notifications": "email-settings", "Deployment Diagnostics": "deployment-diagnostics", "Master Import": "master-import", "Customer Standards Entry": "standards-entry", "Customer Standards Records": "standards-records", "My Account": "my-account",
    "Approved RMTC Part Worksheet": "rmtc-approved-worksheet", "RMTC Part Worksheet": "rmtc-part", "RMTC Records": "rmtc-records",
    "RMTC Approval": "rmtc-approval", "Material Inward Records": "inward-records",
    "OSP Material Out": "osp-material-out", "OSP Sample Receipt": "osp-sample-receipt",
    "OSP Material Inward": "osp-inward", "OSP Dimensional": "osp-dimensional",
    "OSP MetLAB": "osp-metlab", "OSP Records": "osp-records",
    "Supply Chain": "supply-chain-home", "Supply Customer Orders": "supply-customer-orders", "Supply Opening Stock": "supply-opening-stock", "Opening Stock & Import": "supply-opening-stock", "Supply RM Procurement": "supply-rm-procurement", "Supply Purchase Orders": "supply-purchase-orders", "Purchase Order List": "supply-po-order-list", "Edit Purchase Order": "supply-po-edit", "Purchase Order PDF": "supply-po-pdf", "Purchase Order Approval": "supply-po-approval", "Supply RM Receipt": "supply-rm-receipt", "Supply RM to Forging": "supply-rm-dispatch", "Supply Forging": "supply-forging", "Supply Downstream": "supply-downstream", "Supply Traceability": "supply-traceability", "Supply Order MIS": "supply-order-mis",
    "Process Flow Designer": "npd-process-flow", "NPD Status": "npd-status", "APQP": "apqp",
    "QC Calculation Tools": "qc-tools", "QC Calculation Records": "qc-calculation-records",
    "Complaint Management": "complaints-home", "Customer Complaint": "customer-complaint", "Supplier Complaint": "supplier-complaint", "Customer Complaint Register": "customer-complaint-register", "Supplier Complaint Register": "supplier-complaint-register", "Complaint Email Configuration": "complaint-email-settings", "Complaint Analysis & CAPA": "complaint-analysis", "Complaint Records": "complaint-records",
    "Inspection Layout Entry": "inspection-layout-entry",
    "Inspection Layout Records": "inspection-layout-records",
    "Dimensional Report": "dimensional-entry", "Dimensional Records": "dimensional-records",
    "MetLAB Report": "metlab-entry", "MetLAB Records": "metlab-records",
    "Bend Test Report": "bend-test-entry", "Bend Test Records": "bend-test-records", "Bend Test Reports": "bend-test-report",
    "Global Search": "global-search",
}


# Legacy navigation-test continuity tokens (superseded by the v4.12.7 header + rail):
# PAGE_BY_PATH.get(path)
# menu_active_{slug}
# menu_{slug}
# top_menu_new_rmtc
# st.columns(13

ROUTE_PERMISSION_MODULE = {
    "part-entry":"PART_MASTER","part-records":"PART_MASTER","company-branch-entry":"REFERENCE_MASTERS","company-branch-records":"REFERENCE_MASTERS",
    "process-entry":"REFERENCE_MASTERS","process-records":"REFERENCE_MASTERS","grade-entry":"MATERIAL_GRADE","grade-records":"MATERIAL_GRADE",
    "reference-entry":"REFERENCE_MASTERS","reference-records":"REFERENCE_MASTERS","employee-entry":"EMPLOYEE_MASTER","employee-records":"EMPLOYEE_MASTER",
    "standards-entry":"REFERENCE_MASTERS","standards-records":"REFERENCE_MASTERS","master-import":"REFERENCE_MASTERS",
    "rmtc-entry":"RMTC_ENTRY","rmtc-approved-worksheet":"RMTC_ENTRY","rmtc-part":"RMTC_ENTRY","rmtc-approval":"RMTC_ENTRY","rmtc-records":"RMTC_ENTRY",
    "inward-entry":"MATERIAL_INWARD","inward-records":"MATERIAL_INWARD",
    "osp-home":"OSP_TRANSACTIONS","osp-material-out":"OSP_TRANSACTIONS","osp-sample-receipt":"OSP_TRANSACTIONS","osp-inward":"OSP_TRANSACTIONS","osp-records":"OSP_TRANSACTIONS",
    "osp-dimensional":"DIMENSIONAL_REPORT","osp-metlab":"METLAB_REPORT",
    "dimensional-entry":"DIMENSIONAL_REPORT","dimensional-records":"DIMENSIONAL_REPORT","metlab-entry":"METLAB_REPORT","metlab-records":"METLAB_REPORT","bend-test-entry":"METLAB_REPORT","bend-test-records":"METLAB_REPORT","bend-test-report":"METLAB_REPORT",
    "inspection-layout-entry":"INSPECTION_LAYOUTS","inspection-layout-records":"INSPECTION_LAYOUTS",
    "supply-chain-home":"SUPPLY_CHAIN","supply-customer-orders":"SUPPLY_CHAIN","supply-opening-stock":"SUPPLY_CHAIN","supply-rm-procurement":"SUPPLY_CHAIN","supply-purchase-orders":"SUPPLY_CHAIN","supply-po-order-list":"SUPPLY_CHAIN","supply-po-edit":"SUPPLY_CHAIN","supply-po-pdf":"SUPPLY_CHAIN","supply-po-approval":"SUPPLY_CHAIN","supply-rm-receipt":"SUPPLY_CHAIN","supply-rm-dispatch":"SUPPLY_CHAIN","supply-forging":"SUPPLY_CHAIN","supply-downstream":"SUPPLY_CHAIN","supply-traceability":"SUPPLY_CHAIN","supply-order-mis":"SUPPLY_CHAIN",
    "npd-process-flow":"NPD_APQP","npd-status":"NPD_APQP","apqp":"NPD_APQP","qc-tools":"QC_CALCULATION_TOOLS","qc-calculation-records":"QC_CALCULATION_TOOLS",
    "complaints-home":"COMPLAINT_MANAGEMENT","customer-complaint":"COMPLAINT_MANAGEMENT","supplier-complaint":"COMPLAINT_MANAGEMENT","customer-complaint-register":"COMPLAINT_MANAGEMENT","supplier-complaint-register":"COMPLAINT_MANAGEMENT","complaint-email-settings":"COMPLAINT_MANAGEMENT","complaint-analysis":"COMPLAINT_MANAGEMENT","complaint-records":"COMPLAINT_MANAGEMENT",
    "calibration-validation":"CALIBRATION_VALIDATION","standard-room-inspection":"CALIBRATION_VALIDATION",
    "user-access":"USER_ACCESS","email-settings":"USER_ACCESS","deployment-diagnostics":"USER_ACCESS",
}
# Android stable-navigation mode uses Streamlit's own page router and sidebar.
# The sidebar is collapsed by default on phones and page changes remain inside
# the same authenticated Streamlit session. No JavaScript click bridge is used.
if android_streamlit_nav:
    _mobile_group_order = (
        "Dashboard", "Masters", "Supply Chain", "RMTC", "Inward", "OSP",
        "Inspections", "NPD & APQP", "QC Calculation Tools", "Complaints",
        "Calibration & Validation", "Records", "Reports", "Search", "Templates", "Admin",
    )
    _mobile_page_groups = {}
    for _group in _mobile_group_order:
        _group_pages = [_page for _route, _page in PAGE_ITEMS if ROUTE_MODULE.get(_route, "Dashboard") == _group]
        if _group_pages:
            _mobile_page_groups[_group] = _group_pages
    nav = st.navigation(_mobile_page_groups, position="sidebar", expanded=True)
else:
    nav = st.navigation(PAGES, position="hidden")
current_path = PAGE_TITLE_TO_PATH.get(nav.title, "dashboard")
current_module = ROUTE_MODULE.get(current_path, "Dashboard")

current_permission_module = ROUTE_PERMISSION_MODULE.get(current_path)
current_route_permission = module_permissions(profile, current_permission_module) if current_permission_module else {"can_view": True}
log_route_view(current_path, current_permission_module, nav.title)

# QCMS v4.12.9 — hardened responsive enterprise navigation contract.
# Legacy v4.12.8 marker: QCMS v4.12.8 — responsive enterprise navigation contract.
# The red header stays intentionally concise while the charcoal rail preserves
# direct access to every operational module from the previous releases.
QUALITY_HEADER_MODULES = {"RMTC", "Inward", "OSP", "QC Calculation Tools", "Complaints", "Calibration & Validation", "Inspections"}
quality_active_module = current_module if current_module in QUALITY_HEADER_MODULES else "Inspections"
HEADER_NAV = (
    (PAGE_BY_PATH["dashboard"], "Dashboard", "Dashboard"),
    (PAGE_BY_PATH["masters"], "Masters", "Masters"),
    (PAGE_BY_PATH["supply-chain-home"], "Supply Chain", "Supply Chain"),
    (PAGE_BY_PATH["inspection-home"], "Quality", quality_active_module),
    (PAGE_BY_PATH["global-search"], "Search", "Search"),
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
    (PAGE_BY_PATH["calibration-validation"], "Calibration", "Calibration & Validation", ":material/straighten:"),
    (PAGE_BY_PATH["global-search"], "Search", "Search", ":material/search:"),
    (PAGE_BY_PATH["records-center"], "Records", "Records", ":material/description:"),
    (PAGE_BY_PATH["reports-home"], "Reports", "Reports", ":material/assessment:"),
    (PAGE_BY_PATH["templates"], "Templates", "Templates", ":material/download:"),
    (PAGE_BY_PATH["user-access"], "Admin", "Admin", ":material/groups:"),
)

if not native_mobile:
    if render_shell_header(profile, nav.title, current_module=current_module, nav_items=HEADER_NAV):
        logout()

    st.caption(f"LIVE BUILD · QCMS v{settings.version} · 41446-ANDROID-V12-DRAWER-PERSISTENT-AUTH")

    # Persistent permission-aware Global Search launcher for desktop/web.
    with st.form("qcms_shell_global_search_form", border=False):
        gs1, gs2 = st.columns([8.75, 1.25], gap="small")
        shell_global_query = gs1.text_input(
            "Global Search",
            key="qcms_shell_global_search_query",
            placeholder="Global Search · Part, Heat, RMTC, Batch, Supplier, Customer, PO, Report...",
            label_visibility="collapsed",
        )
        shell_global_submit = gs2.form_submit_button("Search", icon=":material/search:", width="stretch")
    if shell_global_submit:
        cleaned_global_query = str(shell_global_query or "").strip()
        if len(cleaned_global_query) < 2:
            st.warning("Enter at least 2 characters for Global Search.")
        else:
            st.session_state["_qcms_global_search_pending_query"] = cleaned_global_query
            st.switch_page(PAGE_BY_PATH["global-search"])

    with st.container(border=False, key="qcms_workspace"):
        rail_col, content_col = st.columns([1.22, 8.78], gap="small", vertical_alignment="top")
        with rail_col:
            render_left_navigation(current_module, RAIL_NAV)
        with content_col:
            with st.container(border=False, key="qcms_content"):
                if not bool(current_route_permission.get("can_view", True)):
                    st.error("You do not have View permission for this module. Ask the QCMS administrator to enable the module or department default in Admin → Users & Access.")
                else:
                    module_submenu(current_module, *MODULE_SUBMENUS[current_module], max_columns=8)
                    nav.run()
                app_footer()
elif android_native_drawer:
    # Android v0.2.2 restores the proven v1.2-style native hamburger drawer.
    # The drawer owns module + submenu presentation and auto-hides after a page
    # selection. Direct route loads are now safe because authentication is
    # reconstructed from the persistent Supabase browser/WebView localStorage bridge.
    st.markdown(
        """<style>
        header[data-testid="stHeader"],div[data-testid="stToolbar"],div[data-testid="stDecoration"],
        section[data-testid="stSidebar"],.st-key-fsi_shell,[class~="st-key-fsi_shell"],
        .st-key-fsi_left_rail,[class~="st-key-fsi_left_rail"],[class*="st-key-fsi_module_subnav_"]{display:none!important}
        div[data-testid="stMainBlockContainer"],.block-container{padding:.45rem .55rem .8rem!important;max-width:100%!important}
        .st-key-qcms_content,[class~="st-key-qcms_content"]{width:100%!important;max-width:100%!important;margin:0!important}
        .fsi-page-head{margin-top:0!important}
        @media(max-width:900px){.qcms-enterprise-table-wrap{max-height:72vh!important}.fsi-kpi-grid,.fsi-status-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}}
        </style>""",
        unsafe_allow_html=True,
    )
    with st.container(border=False, key="qcms_workspace"):
        with st.container(border=False, key="qcms_content"):
            if not bool(current_route_permission.get("can_view", True)):
                st.error("You do not have View permission for this module. Ask the QCMS administrator to enable the module or department default in Admin → Users & Access.")
            else:
                nav.run()
elif android_streamlit_nav:
    # Android v0.2.0/v0.2.1 compatibility: the native bar opens Streamlit's sidebar.
    # Streamlit owns every page link in the official grouped sidebar. The hidden
    # collapsed-control stays mounted off-screen so the native Menu button can
    # open/close it without hard URL loads or a route-click timing bridge.
    st.markdown(
        """<style>
        .st-key-fsi_shell,[class~="st-key-fsi_shell"],
        .st-key-fsi_left_rail,[class~="st-key-fsi_left_rail"]{display:none!important}
        header[data-testid="stHeader"]{display:block!important;height:0!important;min-height:0!important;overflow:visible!important;background:transparent!important}
        div[data-testid="stToolbar"],div[data-testid="stDecoration"],#MainMenu{display:none!important}
        section[data-testid="stSidebar"]{display:block!important;visibility:visible!important}
        [data-testid="collapsedControl"]{display:flex!important;visibility:visible!important;position:fixed!important;left:-10000px!important;top:0!important;width:2px!important;height:2px!important;opacity:.01!important;overflow:hidden!important;pointer-events:auto!important;z-index:2147483647!important}
        [class*="st-key-fsi_module_subnav_"]{display:block!important;margin:0 0 .45rem!important;padding:.18rem!important;background:#fff!important;border:1px solid #d7dadd!important;border-radius:8px!important}
        [class*="st-key-fsi_module_subnav_"] [data-testid="stHorizontalBlock"]{gap:6px!important}
        [class*="st-key-fsi_module_subnav_"] [data-testid="stPageLink"] a{min-height:38px!important;font-size:12px!important;padding:.35rem .45rem!important}
        div[data-testid="stMainBlockContainer"],.block-container{padding:.45rem .5rem .9rem!important;max-width:100%!important}
        .st-key-qcms_content,[class~="st-key-qcms_content"]{width:100%!important;max-width:100%!important;margin:0!important}
        .fsi-page-head{margin-top:0!important}
        @media(max-width:900px){
          .qcms-enterprise-table-wrap{max-height:70vh!important}
          .fsi-kpi-grid,.fsi-status-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}
          section[data-testid="stSidebar"]{max-width:min(90vw,380px)!important}
        }
        </style>""",
        unsafe_allow_html=True,
    )
    with st.container(border=False, key="qcms_workspace"):
        with st.container(border=False, key="qcms_content"):
            if not bool(current_route_permission.get("can_view", True)):
                st.error("You do not have View permission for this module. Ask the QCMS administrator to enable the module or department default in Admin → Users & Access.")
            else:
                # Always show the current module's second-level menu on Android.
                # Two columns keeps touch targets readable on narrow phone screens.
                module_submenu(current_module, *MODULE_SUBMENUS[current_module], max_columns=2)
                nav.run()
else:
    # Native-mobile content mode for iPhone/iPad keeps the existing native drawer bridge.
    st.markdown(
        """<style>
        header[data-testid="stHeader"],div[data-testid="stToolbar"],div[data-testid="stDecoration"],
        section[data-testid="stSidebar"],.st-key-fsi_shell,[class~="st-key-fsi_shell"],
        .st-key-fsi_left_rail,[class~="st-key-fsi_left_rail"],[class*="st-key-fsi_module_subnav_"]{display:none!important}
        .st-key-qcms_native_nav_bridge,[class~="st-key-qcms_native_nav_bridge"]{position:fixed!important;left:-200vw!important;top:0!important;width:1px!important;height:1px!important;overflow:hidden!important;opacity:.001!important;z-index:-1!important}
        div[data-testid="stMainBlockContainer"],.block-container{padding:.45rem .55rem .8rem!important;max-width:100%!important}
        .st-key-qcms_content,[class~="st-key-qcms_content"]{width:100%!important;max-width:100%!important;margin:0!important}
        .fsi-page-head{margin-top:0!important}
        @media(max-width:900px){.qcms-enterprise-table-wrap{max-height:67vh!important}.fsi-kpi-grid,.fsi-status-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}}
        </style>""",
        unsafe_allow_html=True,
    )
    # Native wrappers must navigate inside the current Streamlit session. A hard
    # WebView.loadUrl("/route") starts a new browser session and can lose the
    # in-memory QCMS login. The native app therefore clicks one of these hidden
    # Streamlit buttons; the button callback performs st.switch_page server-side.
    # This is intentionally a widget bridge (not a DOM-only page-link bridge) so
    # slow React rendering can be queued safely by Android without showing a false
    # "navigation is still loading" error.
    with st.container(border=False, key="qcms_native_nav_bridge"):
        st.markdown('<span id="qcms-native-nav-ready" data-qcms-native-nav-ready="1"></span>', unsafe_allow_html=True)
        for _native_route, _native_page in PAGE_ITEMS:
            if st.button(f"QCMS_NAV::{_native_route}", key=f"qcms_native_nav_{_native_route}"):
                st.session_state["_qcms_native_last_route"] = _native_route
                st.switch_page(_native_page)

    with st.container(border=False, key="qcms_workspace"):
        with st.container(border=False, key="qcms_content"):
            if not bool(current_route_permission.get("can_view", True)):
                st.error("You do not have View permission for this module. Ask the QCMS administrator to enable the module or department default in Admin → Users & Access.")
            else:
                nav.run()
