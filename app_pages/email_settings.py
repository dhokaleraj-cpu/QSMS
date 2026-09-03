from __future__ import annotations

import pandas as pd
import streamlit as st

from core.notification_service import NotificationService
from core.notification_ui import template_test_sender
from core.permissions import is_admin
from core.repository import Repository
from core.ui import page_header, portal_table, save_success_popup, stage_section, subpage_navigation

EVENTS = (
    ("RMTC_APPROVAL_PENDING", "RMTC approval pending", "RMTC_ENTRY"),
    ("DIMENSIONAL_APPROVAL_PENDING", "Dimensional approval pending", "DIMENSIONAL_REPORT"),
    ("METLAB_APPROVAL_PENDING", "MetLAB approval pending", "METLAB_REPORT"),
    ("RM_PROCUREMENT_PENDING", "Raw Material procurement pending", "SUPPLY_CHAIN"),
    ("RM_PO_CREATED", "Raw Material PO released", "SUPPLY_CHAIN"),
    ("RM_RECEIPT_PENDING", "Raw Material receipt pending", "SUPPLY_CHAIN"),
    ("FORGING_ORDER_PENDING", "Forging order pending", "SUPPLY_CHAIN"),
    ("FORGING_PO_CREATED", "Forging PO released", "SUPPLY_CHAIN"),
    ("FORGING_RECEIPT_PENDING", "Forging receipt pending", "SUPPLY_CHAIN"),
    ("OSP_SAMPLE_PENDING", "OSP sample inspection pending", "OSP_TRANSACTIONS"),
    ("CUSTOMER_ORDER_OPEN_OVERDUE_DIGEST", "Customer Orders · Open / Overdue digest", "SUPPLY_CHAIN"),
    ("RM_PO_OPEN_OVERDUE_DIGEST", "Raw Material PO · Open / Overdue digest", "SUPPLY_CHAIN"),
    ("FORGING_ORDER_OPEN_OVERDUE_DIGEST", "Forging Orders · Open / Overdue digest", "SUPPLY_CHAIN"),
    ("OSP_RETURN_OPEN_OVERDUE_DIGEST", "OSP Returns · Open / Overdue digest", "OSP_TRANSACTIONS"),
    ("NPD_PROCESS_OPEN_OVERDUE_DIGEST", "NPD Process Steps · Open / Overdue digest", "NPD_APQP"),
    ("CUSTOMER_ORDER_OVERDUE_BIENNIAL", "Customer Orders · Overdue · Every 2 Days · Excel", "SUPPLY_CHAIN"),
    ("RM_PENDING_BIENNIAL", "RM Procurement · Pending · Every 2 Days · Excel", "SUPPLY_CHAIN"),
    ("PO_PENDING_BIENNIAL", "Purchase Orders · Pending · Every 2 Days · Excel", "SUPPLY_CHAIN"),
    ("FORGING_RECEIPT_OVERDUE_BIENNIAL", "Forging Receipts · Overdue · Every 2 Days · Excel", "SUPPLY_CHAIN"),
)
EVENT_LABEL = {k: label for k, label, _module in EVENTS}
EVENT_MODULE = {k: module for k, _label, module in EVENTS}
TEMPLATE_VARIABLES = (
    "{{document_no}}  {{document_type}}  {{part_number}}  {{fsi_part_number}}  {{part_description}}  "
    "{{heat_number}}  {{supplier_name}}  {{customer_name}}  {{due_date}}  {{next_stage}}  {{department}}  "
    "{{report_date}}  {{open_count}}  {{overdue_count}}"
)

# Database-backed context fields available to controlled notification templates.
# The source label tells the administrator exactly which QCMS table/relationship supplies the value.
COMMON_TEMPLATE_FIELDS = (
    ("document_no", "Document Number", "Related transaction · controlled document number"),
    ("document_type", "Document Type", "Related transaction"),
    ("part_number", "Part Number", "Part Master / related transaction item"),
    ("fsi_part_number", "FSI / Supplier-facing Part Number", "Part Master / PO Item"),
    ("part_description", "Part Description", "Part Master / PO Item"),
    ("heat_number", "Heat Number", "Related quality transaction"),
    ("supplier_name", "Supplier Name", "Party Master · Supplier"),
    ("supplier_code", "Supplier Code", "Party Master · Supplier"),
    ("customer_name", "Customer Name", "Party Master · Customer"),
    ("due_date", "Due / Delivery Date", "Related transaction"),
    ("next_stage", "Next Stage", "Notification route / workflow context"),
    ("department", "Responsible Department", "Notification route"),
)
PO_TEMPLATE_FIELDS = (
    ("po_number", "Purchase Order Number", "supply_purchase_orders.po_number"),
    ("order_date", "PO Date", "supply_purchase_orders.order_date"),
    ("delivery_date", "Delivery Date", "supply_purchase_orders.delivery_date"),
    ("quantity", "Total PO Quantity + UOM", "supply_purchase_order_items.quantity + uom"),
    ("quantity_value", "Total PO Quantity", "supply_purchase_order_items.quantity"),
    ("uom", "PO UOM", "supply_purchase_order_items.uom"),
    ("original_part_number", "Original / Finished Part Number(s)", "supply_purchase_order_items.original_part_number_snapshot"),
    ("item_description", "PO Item Description(s)", "supply_purchase_order_items.item_description"),
    ("line_count", "PO Line Count", "supply_purchase_order_items"),
    ("requisitioner", "Requisitioner", "supply_purchase_orders.requisitioner"),
    ("payment_term", "Payment Term", "supply_purchase_orders.payment_term"),
    ("incoterm", "Incoterm", "supply_purchase_orders.incoterm"),
    ("quotation_reference", "Quotation Reference", "supply_purchase_orders.quotation_reference"),
)
RMTC_TEMPLATE_FIELDS = (
    ("rmtc_number", "QCMS RMTC Number", "rmtc_approvals.rmtc_number"),
    ("certificate_reference", "Supplier RMTC Number", "rmtc_approvals.certificate_reference"),
    ("certificate_date", "RMTC Date", "rmtc_approvals.certificate_date"),
    ("heat_code", "Internal Heat Code", "rmtc_approvals.heat_code"),
)
REPORT_TEMPLATE_FIELDS = (
    ("report_number", "Report Number", "inspection_reports / lab_tests.report_number"),
    ("test_date", "MetLAB Test Date", "lab_tests.test_date"),
    ("inspection_date", "Dimensional Inspection Date", "inspection_reports.inspection_date"),
    ("sample_reference", "Sample Reference", "quality report.sample_reference"),
)

def _template_field_catalog(event_key: str) -> list[tuple[str, str, str]]:
    event = str(event_key or "").upper()
    rows = list(COMMON_TEMPLATE_FIELDS)
    if event in {"RM_PO_CREATED", "FORGING_PO_CREATED", "PO_APPROVED", "PO_APPROVAL_PENDING", "PO_CONFIRMATION_REQUIRED", "PO_CONFIRMATION_RECEIVED"}:
        rows.extend(PO_TEMPLATE_FIELDS)
    if event.startswith("RMTC"):
        rows.extend(RMTC_TEMPLATE_FIELDS)
    if "METLAB" in event or "DIMENSIONAL" in event:
        rows.extend(REPORT_TEMPLATE_FIELDS)
    seen = set(); output = []
    for item in rows:
        if item[0] not in seen:
            seen.add(item[0]); output.append(item)
    return output

def _append_template_placeholder(widget_key: str, placeholder: str, *, newline: bool = False) -> None:
    token = "{{" + str(placeholder) + "}}"
    current = str(st.session_state.get(widget_key) or "")
    spacer = "\n" if newline and current else (" " if current and not current.endswith((" ", "\n")) else "")
    st.session_state[widget_key] = current + spacer + token


def _departments(repo: Repository) -> list[str]:
    rows = repo.select("employees", eq={"status": "ACTIVE"}, order_by="department", limit=5000)
    values: list[str] = []
    for row in rows:
        value = str(row.get("department") or "").strip()
        if value and value.casefold() not in {v.casefold() for v in values}:
            values.append(value)
    return values


def render() -> None:
    subpage_navigation(("user-access", "Users & Access", ":material/admin_panel_settings:"), ("masters", "Masters Home", ":material/database:"))
    page_header(
        "Email Server, Templates & Automatic Notifications",
        "Server settings, next-stage department/employee routing, supplier copies, PDF/document attachments, module templates and automatic open/overdue reports.",
        "Administrator",
    )
    profile = st.session_state.get("profile") or {}
    if not is_admin(profile):
        st.error("Administrator access is required.")
        return

    repo = Repository(); notifier = NotificationService(repo)
    existing_rows = repo.select("qcms_email_settings", limit=1); existing = existing_rows[0] if existing_rows else {}
    departments = _departments(repo)
    employees = [e for e in repo.select("employees", order_by="first_name", limit=5000) if str(e.get("status") or "ACTIVE") == "ACTIVE"]
    employee_options = {str(e.get("id")): f"{e.get('employee_code')} · {e.get('first_name')} {e.get('last_name')} · {e.get('department')} · {e.get('email') or 'NO EMAIL'}" for e in employees}

    with stage_section("A", "EMAIL SERVER SETTINGS", "SMTP password is write-only in the UI. Leave Password blank to keep the saved password.", key="email_settings_server"):
        if str(existing.get("smtp_host") or "").casefold() in {"smtp.office365.com", "smtp-mail.outlook.com"}:
            st.success("Microsoft 365 email is configured in QCMS. TENANT SMTP AUTH BLOCK CHECK: if a future 535 5.7.139 occurs, verify Authenticated SMTP / tenant policy before changing QCMS credentials. QCMS cannot override this from application code.")
        c = st.columns(4, gap="small")
        enabled = c[0].toggle("Enable Email Notifications", value=bool(existing.get("enabled", False)))
        host = c[1].text_input("SMTP Host", value=str(existing.get("smtp_host") or ""), placeholder="smtp.office365.com")
        port = c[2].number_input("SMTP Port", min_value=1, max_value=65535, value=int(existing.get("smtp_port") or 587), step=1)
        sender_name = c[3].text_input("Sender Name", value=str(existing.get("sender_name") or "QCMS"))
        c = st.columns(4, gap="small")
        username = c[0].text_input("SMTP Username", value=str(existing.get("smtp_username") or ""))
        password = c[1].text_input("SMTP Password / App Password", type="password", value="", placeholder="Leave blank to keep saved password")
        sender_email = c[2].text_input("Sender Email", value=str(existing.get("sender_email") or ""))
        reply_to = c[3].text_input("Reply-To", value=str(existing.get("reply_to") or ""))
        c = st.columns(3, gap="small")
        use_tls = c[0].toggle("STARTTLS", value=bool(existing.get("use_tls", True)))
        use_ssl = c[1].toggle("SMTP SSL", value=bool(existing.get("use_ssl", False)))
        timeout = c[2].number_input("Timeout seconds", min_value=5, max_value=120, value=int(existing.get("timeout_seconds") or 20), step=1)
        if st.button("Save Email Server Settings", type="primary", width="stretch"):
            payload = {"enabled": enabled, "smtp_host": host.strip() or None, "smtp_port": int(port), "smtp_username": username.strip() or None, "sender_email": sender_email.strip() or None, "sender_name": sender_name.strip() or "QCMS", "reply_to": reply_to.strip() or None, "use_tls": use_tls, "use_ssl": use_ssl, "timeout_seconds": int(timeout)}
            if password.strip(): payload["smtp_password"] = password
            elif existing.get("smtp_password") is not None: payload["smtp_password"] = existing.get("smtp_password")
            try:
                saved, _ = repo.upsert_by("qcms_email_settings", payload, natural_key={"tenant_id": repo.tenant_id}); existing = saved
                save_success_popup("Email server settings saved.", queue_for_rerun=True); st.rerun()
            except Exception as exc: st.error(str(exc))

    with stage_section("B", "NEXT-STAGE RESPONSIBILITY ROUTING", "Each event can target one responsible employee, a responsible department, CC the department and optionally copy the linked Supplier / OSP Vendor. Supplier email is taken from Party Master Primary Email + Notification Email(s).", key="email_settings_routes"):
        routes = {str(r.get("event_key")): r for r in repo.select("qcms_notification_routes", limit=500)}
        event = st.selectbox("Workflow Event", [k for k, _label, _module in EVENTS], format_func=lambda k: f"{EVENT_LABEL.get(k,k)} · {EVENT_MODULE.get(k,'')}", key="email_route_event")
        row = routes.get(event) or {}
        c = st.columns(4, gap="small")
        dept_values = [""] + departments; current_dept = str(row.get("department") or "")
        department = c[0].selectbox("Responsible Department", dept_values, index=dept_values.index(current_dept) if current_dept in dept_values else 0, format_func=lambda v: v or "— Not assigned —")
        filtered = [e for e in employees if not department or str(e.get("department") or "").casefold() == department.casefold()]
        filtered_ids = [""] + [str(e.get("id")) for e in filtered]; current_emp = str(row.get("employee_id") or "")
        employee_id = c[1].selectbox("Responsible Employee", filtered_ids, index=filtered_ids.index(current_emp) if current_emp in filtered_ids else 0, format_func=lambda v: employee_options.get(v, "— Department fallback —"))
        department_cc = c[2].toggle("CC Responsible Department", value=bool(row.get("department_cc", False)))
        supplier_copy = c[3].toggle("Copy linked Supplier / Vendor", value=bool(row.get("send_to_supplier", False)))
        c = st.columns(3, gap="small")
        fallback = c[0].text_input("Fallback Email", value=str(row.get("fallback_email") or ""))
        next_stage = c[1].text_input("Next Stage / Action", value=str(row.get("next_stage") or ""))
        route_enabled = c[2].toggle("Route Enabled", value=bool(row.get("enabled", False)))
        template_key = st.selectbox("Email Template", [k for k, _l, _m in EVENTS], index=[k for k,_l,_m in EVENTS].index(str(row.get("template_key") or event)) if str(row.get("template_key") or event) in [k for k,_l,_m in EVENTS] else 0, format_func=lambda k: EVENT_LABEL.get(k,k))
        if st.button("Save Responsibility Route", type="primary", width="stretch"):
            payload = {"event_key": event, "route_label": EVENT_LABEL.get(event,event), "employee_id": employee_id or None, "department": department or None, "department_cc": department_cc, "send_to_supplier": supplier_copy, "fallback_email": fallback.strip() or None, "template_key": template_key, "next_stage": next_stage.strip() or None, "subject_template": None, "enabled": route_enabled}
            try:
                repo.upsert_by("qcms_notification_routes", payload, natural_key={"tenant_id": repo.tenant_id, "event_key": event})
                save_success_popup("Next-stage notification route saved.", queue_for_rerun=True); st.rerun()
            except Exception as exc: st.error(str(exc))
        route_frame = []
        for key, label, module in EVENTS:
            r = routes.get(key) or {}; emp = next((e for e in employees if str(e.get("id")) == str(r.get("employee_id"))), {})
            route_frame.append({"Module": module, "Event": label, "Department": r.get("department"), "Employee": " ".join(v for v in (str(emp.get("first_name") or ""), str(emp.get("last_name") or "")) if v), "Email": emp.get("email") or r.get("fallback_email"), "Department CC": bool(r.get("department_cc", False)), "Supplier Copy": bool(r.get("send_to_supplier", False)), "Enabled": bool(r.get("enabled", False))})
        portal_table(pd.DataFrame(route_frame), hide_index=True, width="stretch", height=390)

    with stage_section("C", "MODULE EMAIL TEMPLATES", "Maintain the controlled subject/body format for every QCMS workflow and digest. Generated PDFs and controlled record documents may be attached automatically.", key="email_template_editor"):
        templates = {str(r.get("template_key")): r for r in repo.select("qcms_email_templates", order_by="template_key", limit=500)}
        template_event = st.selectbox("Template", [k for k, _l, _m in EVENTS], format_func=lambda k: f"{EVENT_LABEL.get(k,k)} · {EVENT_MODULE.get(k,'')}", key="template_event")
        template = templates.get(template_event) or {}
        st.caption(f"Available placeholders: {TEMPLATE_VARIABLES}")
        subject_key = f"email_template_subject_{template_event}"
        body_key = f"email_template_body_{template_event}"
        name_key = f"email_template_name_{template_event}"
        if subject_key not in st.session_state:
            st.session_state[subject_key] = str(template.get("subject_template") or f"QCMS · {EVENT_LABEL.get(template_event, template_event)} · {{{{document_no}}}}")
        if body_key not in st.session_state:
            default_body = "Dear {{department}},\n\nQCMS action is pending for {{document_no}}.\nNext Stage: {{next_stage}}\n\nRegards,\nQCMS"
            st.session_state[body_key] = str(template.get("body_template") or default_body)
        if name_key not in st.session_state:
            st.session_state[name_key] = str(template.get("template_name") or EVENT_LABEL.get(template_event, template_event))

        field_rows = _template_field_catalog(template_event)
        field_labels = {field: f"{label} · {source} · {{{{{field}}}}}" for field, label, source in field_rows}
        field_choice = st.selectbox("Add Database Field to Template", list(field_labels), format_func=lambda value: field_labels[value], key=f"email_template_field_{template_event}")
        fc = st.columns(2, gap="small")
        fc[0].button("Add Field to Subject", icon=":material/add:", width="stretch", key=f"email_field_subject_{template_event}", on_click=_append_template_placeholder, args=(subject_key, field_choice))
        fc[1].button("Add Field to Email Body", icon=":material/add:", width="stretch", key=f"email_field_body_{template_event}", on_click=_append_template_placeholder, args=(body_key, field_choice), kwargs={"newline": True})
        st.caption("The field picker is limited to database fields/context related to the selected QCMS section. Unknown or empty values render as '-'.")
        c = st.columns(2, gap="small")
        subject_template = c[0].text_input("Subject Template", key=subject_key)
        template_name = c[1].text_input("Template Name", key=name_key)
        body_template = st.text_area("Email Body Template", key=body_key, height=260)
        c = st.columns(4, gap="small")
        include_pdf = c[0].toggle("Attach generated QCMS PDF", value=bool(template.get("include_generated_pdf", True)))
        include_docs = c[1].toggle("Attach controlled documents", value=bool(template.get("include_record_attachments", True)))
        include_supplier = c[2].toggle("Allow Supplier / Vendor copy", value=bool(template.get("include_supplier", False)))
        template_enabled = c[3].toggle("Template Enabled", value=bool(template.get("enabled", True)))
        if st.button("Save Email Template", type="primary", width="stretch"):
            try:
                repo.upsert_by("qcms_email_templates", {"template_key": template_event, "module_key": EVENT_MODULE.get(template_event,"QCMS"), "template_name": template_name.strip() or EVENT_LABEL.get(template_event,template_event), "subject_template": subject_template.strip(), "body_template": body_template.strip(), "include_generated_pdf": include_pdf, "include_record_attachments": include_docs, "include_supplier": include_supplier, "enabled": template_enabled}, natural_key={"tenant_id": repo.tenant_id, "template_key": template_event})
                save_success_popup("Email template saved.", queue_for_rerun=True); st.rerun()
            except Exception as exc: st.error(str(exc))

    with stage_section("D", "TEST EMAIL TEMPLATE", "Select the template above, enter any manual To / CC recipient and send a controlled test. QCMS shows the confirmation popup before releasing the email.", key="email_template_test"):
        st.info(f"Testing template: {EVENT_LABEL.get(template_event, template_event)} · {EVENT_MODULE.get(template_event,'')}")
        template_test_sender(
            notifier, template_event, key=f"email_template_manual_test_{template_event}",
            default_recipient=str(profile.get("email") or ""),
        )

    with stage_section("E", "AUTOMATIC OPEN / OVERDUE REPORT EMAILS", "Supabase Cron checks every hour. Each schedule follows its configured cadence (for example every 2 days), local hour, recipient departments and PDF/Excel export format. Supplier/vendor copies are sent only when Party Master contains an email address.", key="email_auto_schedules"):
        schedules = repo.select("qcms_notification_schedules", order_by="schedule_key", limit=100)
        if schedules:
            schedule_labels = {str(r.get("id")): f"{r.get('schedule_label')} · {r.get('module_key')}" for r in schedules}
            sid = st.selectbox("Automatic Schedule", list(schedule_labels), format_func=lambda v: schedule_labels[v])
            schedule = next(r for r in schedules if str(r.get("id")) == sid)
            c = st.columns(5, gap="small")
            schedule_enabled = c[0].toggle("Enabled", value=bool(schedule.get("enabled", True)), key=f"schedule_enabled_{sid}")
            hour = c[1].number_input("Local send hour", min_value=0, max_value=23, value=int(schedule.get("hour_local") or 8), step=1, key=f"schedule_hour_{sid}")
            run_every_days = c[2].number_input("Run every (days)", min_value=1, max_value=30, value=max(int(schedule.get("run_every_days") or 1), 1), step=1, key=f"schedule_cadence_{sid}")
            days_ahead = c[3].number_input("Include due within days", min_value=0, max_value=365, value=int(schedule.get("days_ahead") or 7), step=1, key=f"schedule_days_{sid}")
            include_suppliers = c[4].toggle("Send supplier/vendor copies", value=bool(schedule.get("include_suppliers", False)), key=f"schedule_suppliers_{sid}")
            c = st.columns(4, gap="small")
            tz = c[0].text_input("Time Zone", value=str(schedule.get("timezone") or "Asia/Kolkata"), key=f"schedule_tz_{sid}")
            dept_values = [""] + departments; current_dept = str(schedule.get("recipient_department") or "")
            recipient_department = c[1].selectbox("Primary Department", dept_values, index=dept_values.index(current_dept) if current_dept in dept_values else 0, format_func=lambda v: v or "— None —", key=f"schedule_dept_{sid}")
            existing_multi = [str(x) for x in (schedule.get("recipient_departments") or []) if str(x)]
            extra_depts = ["Marketing", "Procurement", "Business Development"]
            multi_options = sorted(set(departments + extra_depts))
            recipient_departments = c[2].multiselect("Recipient Departments", multi_options, default=[x for x in existing_multi if x in multi_options], key=f"schedule_depts_{sid}", help="Every active employee in these departments receives the digest. Marketing and Procurement also match the equivalent QCMS user roles when configured.")
            export_format = c[3].selectbox("Attachment Format", ["PDF","XLSX","BOTH"], index=["PDF","XLSX","BOTH"].index(str(schedule.get("export_format") or "PDF").upper()) if str(schedule.get("export_format") or "PDF").upper() in {"PDF","XLSX","BOTH"} else 0, key=f"schedule_export_{sid}")
            c = st.columns(3, gap="small")
            emp_ids = [""] + list(employee_options); current_emp = str(schedule.get("employee_id") or "")
            responsible_employee = c[0].selectbox("Specific Employee (optional)", emp_ids, index=emp_ids.index(current_emp) if current_emp in emp_ids else 0, format_func=lambda v: employee_options.get(v,"— Department / record responsibility —"), key=f"schedule_emp_{sid}")
            template_key = c[1].selectbox("Template", [k for k,_l,_m in EVENTS], index=[k for k,_l,_m in EVENTS].index(str(schedule.get("template_key") or schedule.get("event_key"))) if str(schedule.get("template_key") or schedule.get("event_key")) in [k for k,_l,_m in EVENTS] else 0, format_func=lambda k: EVENT_LABEL.get(k,k), key=f"schedule_template_{sid}")
            include_overdue = c[2].toggle("Include overdue", value=bool(schedule.get("include_overdue", True)), key=f"schedule_overdue_{sid}")
            include_open = st.toggle("Include open / due-soon", value=bool(schedule.get("include_open", True)), key=f"schedule_open_{sid}")
            if st.button("Save Automatic Email Schedule", type="primary", width="stretch"):
                try:
                    repo.update("qcms_notification_schedules", sid, {"enabled": schedule_enabled, "hour_local": int(hour), "run_every_days": int(run_every_days), "days_ahead": int(days_ahead), "include_suppliers": include_suppliers, "timezone": tz.strip() or "Asia/Kolkata", "recipient_department": recipient_department or None, "recipient_departments": recipient_departments, "employee_id": responsible_employee or None, "template_key": template_key, "export_format": export_format, "include_overdue": include_overdue, "include_open": include_open})
                    save_success_popup("Automatic email schedule saved.", queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))
            portal_table(pd.DataFrame([{ "Schedule": r.get("schedule_label"), "Module": r.get("module_key"), "Hour": r.get("hour_local"), "Every Days": r.get("run_every_days") or 1, "Time Zone": r.get("timezone"), "Days Ahead": r.get("days_ahead"), "Departments": ", ".join(r.get("recipient_departments") or []) or r.get("recipient_department"), "Export": r.get("export_format") or "PDF", "Supplier Copy": bool(r.get("include_suppliers")), "Enabled": bool(r.get("enabled")), "Last Run": r.get("last_run_at") } for r in schedules]), hide_index=True, width="stretch", height=300)
        else:
            st.warning("Automatic notification schedules are not available. Apply the QCMS v4.14.7 database migration.")

    with stage_section("E", "TEST & NOTIFICATION OUTBOX", "Send a test message or retry failed/pending notifications. Business transactions are never rolled back if email delivery fails.", key="email_settings_test"):
        test_email = st.text_input("Test Recipient Email", value=str(profile.get("email") or ""))
        c = st.columns(2, gap="small")
        if c[0].button("Send Test Email", type="primary", width="stretch"):
            try:
                row = notifier.enqueue("EMAIL_SERVER_TEST", subject="QCMS · Email server test", body_text="QCMS email server test completed successfully from Email Server, Templates & Automatic Notifications.", recipient_email=test_email, recipient_name="QCMS Administrator", context={"test": True}, include_generated_pdf=False, include_record_attachments=False)
                result = notifier.dispatch([row] if row else [])
                if result.get("error"): st.warning(f"Test queued but delivery returned: {result.get('error')}")
                else: save_success_popup("Test email queued/delivery requested.", queue_for_rerun=True); st.rerun()
            except Exception as exc: st.error(str(exc))
        if c[1].button("Retry Pending / Failed Email", width="stretch"):
            result = notifier.retry_pending(limit=50)
            if result.get("error"): st.warning(str(result.get("error")))
            else: save_success_popup(f"Retry requested for {result.get('processed',0)} notification(s).", queue_for_rerun=True); st.rerun()
        outbox = repo.select("qcms_notification_outbox", order_by="created_at", desc=True, limit=300)
        if outbox:
            frame = pd.DataFrame([{ "Created": r.get("created_at"), "Event": r.get("event_key"), "Recipient": r.get("recipient_email"), "CC": "; ".join(r.get("cc_emails") or []), "Subject": r.get("subject"), "Attachments": len(r.get("attachment_manifest") or []), "Automatic": bool(r.get("is_automatic", False)), "Status": r.get("status"), "Attempts": r.get("attempts"), "Sent": r.get("sent_at"), "Last Error": r.get("last_error") } for r in outbox])
            portal_table(frame, hide_index=True, width="stretch", height=460)
        else: st.info("No notification outbox records yet.")
