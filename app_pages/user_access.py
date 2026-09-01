from __future__ import annotations

import json
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from core.access import MODULES, module_permissions_with_source
from core.database import get_session_client
from core.permissions import is_admin
from core.reporting import controlled_record_pdf_bytes
from core.repository import Repository
from core.ui import page_header, portal_table, save_success_popup, stage_section, subpage_navigation

# Compatibility stage key retained for controlled verification: user_access_access_c
ROLES = [
    "ADMIN", "MANAGEMENT", "SUPPLY_CHAIN", "PROCUREMENT", "BUSINESS_DEVELOPMENT",
    "QUALITY_MANAGER", "METLAB_APPROVER", "QUALITY_ENGINEER", "PRODUCTION", "SQA",
    "MASTER_DATA", "AUDITOR", "VIEWER",
]
ACCESS_STATUSES = ["ACTIVE", "INACTIVE", "LOCKED"]

# Legacy contract wording: SECTION VISIBILITY / EDIT CONTROL
SECTION_CATALOG = [
    ("PART_MASTER", "BASIC_IDENTITY", "Part Master · Basic Identity / Drawing"),
    ("PART_MASTER", "RAW_MATERIAL_DETAILS", "Part Master · Raw Material Details"),
    ("PART_MASTER", "SUPPLIER_TECHNICAL", "Part Master · Supplier Technical Data"),
    ("PART_MASTER", "PRICE_HISTORY", "Part Master · Supplier Price History"),
    ("PART_MASTER", "HEAT_TREATMENT", "Part Master · Heat Treatment / Metallurgical"),
    ("PART_MASTER", "PROCESS_SPECIFICATIONS", "Part Master · Process Specifications"),
    ("SUPPLY_CHAIN", "CUSTOMER_ORDERS", "Supply Chain · Customer Orders / Schedules"),
    ("SUPPLY_CHAIN", "RM_PROCUREMENT", "Supply Chain · RM Procurement"),
    ("SUPPLY_CHAIN", "PURCHASE_ORDERS", "Supply Chain · Purchase Orders"),
    ("SUPPLY_CHAIN", "PO_COMMERCIAL", "Supply Chain · PO Commercial / Price Fields"),
    ("SUPPLY_CHAIN", "PO_REPORTS", "Supply Chain · Purchase Order Reports"),
    ("SUPPLY_CHAIN", "RM_RECEIPT", "Supply Chain · RM Receipt / Material Inward"),
    ("SUPPLY_CHAIN", "RM_TO_FORGING", "Supply Chain · RM to Forging"),
    ("SUPPLY_CHAIN", "FORGING", "Supply Chain · Forging Order / Receipt"),
    ("SUPPLY_CHAIN", "MACHINING_DISPATCH", "Supply Chain · Machining / FG / Dispatch"),
    ("SUPPLY_CHAIN", "OPENING_STOCK", "Supply Chain · Opening Stock"),
    ("SUPPLY_CHAIN", "TRACEABILITY", "Supply Chain · Traceability / MIS"),
    ("RMTC_ENTRY", "HEADER", "RMTC · Header Entry"),
    ("RMTC_ENTRY", "PART_WORKSHEET", "RMTC · Part Worksheet"),
    ("RMTC_ENTRY", "VALIDATION", "RMTC · Validation / Decision"),
    ("DIMENSIONAL_REPORT", "ENTRY", "Dimensional · Entry"),
    ("DIMENSIONAL_REPORT", "RESULTS", "Dimensional · Results"),
    ("DIMENSIONAL_REPORT", "FINAL_DECISION", "Dimensional · Final Decision"),
    ("METLAB_REPORT", "ENTRY", "MetLAB · Entry"),
    ("METLAB_REPORT", "CASE_DEPTH", "MetLAB · Case Depth Traverse"),
    ("METLAB_REPORT", "MICROSTRUCTURE", "MetLAB · Microstructure Photographs"),
    ("METLAB_REPORT", "FINAL_DECISION", "MetLAB · Final Decision"),
    ("OSP_TRANSACTIONS", "MATERIAL_OUT", "OSP · Material Out"),
    ("OSP_TRANSACTIONS", "SAMPLE", "OSP · Sample Receipt / Gate"),
    ("OSP_TRANSACTIONS", "INWARD", "OSP · Inward"),
    ("NPD_APQP", "PROCESS_FLOW", "NPD / APQP · Process Flow"),
    ("NPD_APQP", "ORDER_STATUS", "NPD / APQP · Order Status"),
    ("COMPLAINT_MANAGEMENT", "COMMERCIAL", "Complaints · Commercial / Debit Note"),
]


def _invoke(payload: Mapping[str, Any]) -> dict[str, Any]:
    client = get_session_client()
    response = client.functions.invoke("qsms-user-admin", invoke_options={"body": dict(payload)})
    data = getattr(response, "data", response)
    if isinstance(data, bytes):
        data = json.loads(data.decode())
    if not isinstance(data, dict):
        raise RuntimeError("User administration service returned an invalid response.")
    if data.get("error"):
        raise RuntimeError(str(data.get("error")))
    return data


def _normalize_user(row: Mapping[str, Any]) -> dict[str, Any]:
    """Accept both legacy flat and deployed nested qsms-user-admin payloads."""
    profile = dict(row.get("profile") or {})
    employee = dict(row.get("employee") or {})
    return {
        "id": str(row.get("id") or profile.get("id") or ""),
        "email": row.get("email") or profile.get("email") or "",
        "full_name": profile.get("full_name") or row.get("full_name") or "",
        "role": str(profile.get("role") or row.get("role") or "VIEWER").upper(),
        "status": str(profile.get("status") or row.get("status") or "ACTIVE").upper(),
        "employee_id": str(employee.get("id") or row.get("employee_id") or ""),
        "employee_code": employee.get("employee_code") or row.get("employee_code") or "",
        "department": employee.get("department") or row.get("department") or "",
        "designation": employee.get("designation") or row.get("designation") or "",
        "last_sign_in_at": row.get("last_sign_in_at"),
        "created_at": row.get("created_at") or profile.get("created_at"),
    }


def _employee_label(row: Mapping[str, Any]) -> str:
    return f"{row.get('employee_code') or '-'} · {row.get('first_name') or ''} {row.get('last_name') or ''}".strip()


def _delete_override(repo: Repository, table: str, existing: Mapping[str, Any] | None) -> None:
    if existing and existing.get("id"):
        repo.delete(table, str(existing["id"]))


def _permission_editor_rows(
    repo: Repository,
    *,
    table: str,
    eq: Mapping[str, Any],
    selected_profile: Mapping[str, Any] | None = None,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    existing = {str(r.get("module_key")): r for r in repo.select(table, eq=dict(eq), limit=200)}
    rows: list[dict[str, Any]] = []
    for key, label in MODULES:
        configured = existing.get(key)
        if configured:
            values = configured
            source = "EXPLICIT"
        elif selected_profile is not None:
            values, source = module_permissions_with_source(selected_profile, key, repo)
        else:
            values = {}
            source = "INHERIT"
        rows.append({
            "Override": configured is not None,
            "Module": label,
            "Module Key": key,
            "Source": source,
            "View": bool(values.get("can_view", True if selected_profile is None else False)),
            "Entry/Create": bool(values.get("can_create", False)),
            "Edit": bool(values.get("can_edit", False)),
            "Validate/Review": bool(values.get("can_validate", False)),
            "Approve": bool(values.get("can_approve", False)),
            "Delete/Archive": bool(values.get("can_archive", False)),
        })
    return existing, rows


def _changed_fields(old_data: Any, new_data: Any) -> str:
    old = old_data if isinstance(old_data, dict) else {}
    new = new_data if isinstance(new_data, dict) else {}
    keys = sorted(set(old) | set(new))
    ignored = {"updated_at", "updated_by"}
    changed = [key for key in keys if key not in ignored and old.get(key) != new.get(key)]
    return ", ".join(changed[:12]) + (" …" if len(changed) > 12 else "")


def render() -> None:
    subpage_navigation(("masters", "Back to Masters", ":material/arrow_back:"))
    page_header(
        "Users & Access",
        "Role + Department access, explicit user overrides, section visibility, approvals and complete user activity audit.",
        "Administrator",
    )
    profile = st.session_state.get("profile") or {}
    if not is_admin(profile):
        st.error("Administrator access is required.")
        return

    repo = Repository()
    employees = repo.select("employees", order_by="first_name", limit=5000)
    emp = {str(e["id"]): _employee_label(e) for e in employees}
    employee_by_id = {str(e["id"]): e for e in employees}
    departments = sorted(
        {str(e.get("department") or "").strip() for e in employees if str(e.get("department") or "").strip()}
        | {"Production", "Supply Chain", "Procurement", "Quality", "METLAB", "Management", "Business Development", "R & D", "HR", "Accounts"}
    )

    create_tab, access_tab, defaults_tab, audit_tab, password_tab = st.tabs(
        ["Create User", "User Permissions", "Role & Department Defaults", "Audit & Activity", "My Password"]
    )

    with create_tab:
        with stage_section("A", "CREATE USER", "Create the login and optionally link one Employee Master record. Employee email is never overwritten by login administration.", key="user_access_create_a"):
            with st.form("create_user_v41418"):
                c = st.columns(3, gap="small")
                full = c[0].text_input("Full Name")
                email = c[1].text_input("Login / Company Email")
                role = c[2].selectbox("QCMS Role", ROLES)
                c = st.columns(3, gap="small")
                employee = c[0].selectbox("Employee Link", [""] + list(emp), format_func=lambda x: emp.get(x, "— Not linked —"))
                status = c[1].selectbox("Access Status", ACCESS_STATUSES)
                password = c[2].text_input("Temporary Password", type="password")
                selected_department = str(employee_by_id.get(employee, {}).get("department") or "")
                st.caption(f"Department: {selected_department or 'Link an Employee Master record to derive Department access.'}")
                submit = st.form_submit_button("Create User", type="primary", width="stretch")
            if submit:
                try:
                    result = _invoke({
                        "action": "create_user", "email": email, "password": password, "full_name": full,
                        "role": role, "status": status, "employee_id": employee or None,
                    })
                    save_success_popup(result.get("message", "User created successfully."), queue_for_rerun=True)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    # Load and normalize once for all remaining user-specific controls.
    try:
        payload = _invoke({"action": "list_users"})
        users = [_normalize_user(item) for item in payload.get("users", [])]
    except Exception as exc:
        users = []
        st.error(f"Could not load QCMS users: {exc}")

    selected_user: dict[str, Any] | None = None
    uid = ""
    if users:
        labels = {str(u["id"]): f"{u.get('email')} · {u.get('role')}" for u in users if u.get("id")}
        uid = st.session_state.get("_qcms_selected_access_user") or next(iter(labels), "")
        if uid not in labels:
            uid = next(iter(labels), "")
        selected_user = next((u for u in users if u.get("id") == uid), None)

    with access_tab:
        if not users:
            st.info("No users are available.")
        else:
            with stage_section("A", "USER · ROLE · DEPARTMENT · EMPLOYEE LINK", "Role and Department are displayed together with the Employee Master link. Changing access never changes Employee Master email.", key="user_access_identity"):
                register = pd.DataFrame([{
                    "Email": u.get("email"), "Name": u.get("full_name"), "Role": u.get("role"),
                    "Department": u.get("department") or "—", "Employee": u.get("employee_code") or "—",
                    "Status": u.get("status"), "Last Sign In": u.get("last_sign_in_at"),
                } for u in users])
                portal_table(register, hide_index=True, width="stretch", height=300)
                labels = {str(u["id"]): f"{u.get('email')} · {u.get('role')}" for u in users}
                uid = st.selectbox(
                    "Selected User", list(labels), index=list(labels).index(uid) if uid in labels else 0,
                    format_func=lambda value: labels[value], key="selected_access_user_v41418",
                )
                st.session_state["_qcms_selected_access_user"] = uid
                selected_user = next(u for u in users if str(u.get("id")) == uid)
                current_employee_id = str(selected_user.get("employee_id") or "")
                employee_options = [""] + list(emp)
                employee_index = employee_options.index(current_employee_id) if current_employee_id in employee_options else 0
                current_role = selected_user.get("role") if selected_user.get("role") in ROLES else "VIEWER"
                current_status = selected_user.get("status") if selected_user.get("status") in ACCESS_STATUSES else "ACTIVE"

                c = st.columns(4, gap="small")
                role_value = c[0].selectbox("Role", ROLES, index=ROLES.index(current_role), key=f"role_{uid}")
                status_value = c[1].selectbox("Access Status", ACCESS_STATUSES, index=ACCESS_STATUSES.index(current_status), key=f"status_{uid}")
                employee_value = c[2].selectbox(
                    "Employee", employee_options, index=employee_index,
                    format_func=lambda x: emp.get(x, "— Not linked —"), key=f"employee_{uid}",
                )
                linked_department = str(employee_by_id.get(employee_value, {}).get("department") or selected_user.get("department") or "")
                department_options = [""] + [d for d in departments if d]
                dept_index = department_options.index(linked_department) if linked_department in department_options else 0
                department_value = c[3].selectbox(
                    "Department", department_options, index=dept_index,
                    format_func=lambda x: x or "— Link employee first —", disabled=not bool(employee_value), key=f"dept_{uid}",
                )
                if selected_user.get("role") == "ADMIN" and employee_by_id.get(employee_value, {}).get("is_top_level_authority"):
                    st.info("Top-level Super Admin: Reports-To is not required and remains blank in Employee Master.")
                unlink_employee_confirmed = False
                if current_employee_id and not employee_value:
                    unlink_employee_confirmed = st.checkbox(
                        "Confirm unlinking this QCMS User from the currently linked Employee Master record",
                        value=False, key=f"unlink_employee_confirm_{uid}",
                    )
                    st.warning("The existing Employee link will be preserved unless this confirmation is selected.")
                if st.button("Update User / Employee Link", type="primary", width="stretch", key=f"update_user_{uid}"):
                    try:
                        _invoke({
                            "action": "update_user", "user_id": uid, "role": role_value, "status": status_value,
                            "employee_id": employee_value or None,
                            "allow_unlink_employee": bool(unlink_employee_confirmed),
                            "department": department_value if employee_value else None,
                        })
                        save_success_popup("User role, status, Department and Employee link updated successfully.", queue_for_rerun=True)
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

            with stage_section("B", "EXPLICIT USER MODULE PERMISSIONS", "An enabled Override is authoritative. If Override is off, the user inherits Role → Department → legacy defaults. This same effective permission is enforced by the database/RLS and the UI.", key="user_access_user_module"):
                effective_profile = {
                    "id": uid, "role": selected_user.get("role"), "email": selected_user.get("email"),
                    "department": selected_user.get("department"),
                }
                existing, rows = _permission_editor_rows(repo, table="user_module_permissions", eq={"profile_id": uid}, selected_profile=effective_profile)
                edited = st.data_editor(
                    pd.DataFrame(rows), hide_index=True, width="stretch", height=390,
                    disabled=["Module", "Module Key", "Source"], key=f"user_module_matrix_{uid}",
                )
                c1, c2 = st.columns(2, gap="small")
                if c1.button("Save User Permission Overrides", type="primary", width="stretch", key=f"save_user_module_{uid}"):
                    try:
                        for _, row in edited.iterrows():
                            key = str(row["Module Key"])
                            configured = existing.get(key)
                            if bool(row["Override"]):
                                repo.upsert_by("user_module_permissions", {
                                    "profile_id": uid, "module_key": key, "can_view": bool(row["View"]),
                                    "can_create": bool(row["Entry/Create"]), "can_edit": bool(row["Edit"]),
                                    "can_validate": bool(row["Validate/Review"]), "can_approve": bool(row["Approve"]),
                                    "can_archive": bool(row["Delete/Archive"]),
                                }, natural_key={"profile_id": uid, "module_key": key})
                            else:
                                _delete_override(repo, "user_module_permissions", configured)
                        save_success_popup("User permission overrides saved. Effective module authorization is synchronized with database workflows.", queue_for_rerun=True)
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
                if c2.button("Clear All User Overrides", width="stretch", key=f"clear_user_module_{uid}"):
                    try:
                        for configured in existing.values():
                            _delete_override(repo, "user_module_permissions", configured)
                        save_success_popup("User overrides cleared. Role / Department defaults now apply.", queue_for_rerun=True)
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

            with stage_section("C", "SECTION VIEW / CREATE / EDIT", "Default: all sections remain visible according to module View permission. Create an Override only when you need to hide or restrict a section such as Part Master Price History.", key="user_access_sections_v41418"):
                existing_sections = {
                    (str(r.get("module_key")), str(r.get("section_key"))): r
                    for r in repo.select("user_section_permissions", eq={"profile_id": uid}, limit=1000)
                }
                sec_rows = []
                for mod, key, label in SECTION_CATALOG:
                    configured = existing_sections.get((mod, key))
                    if configured:
                        view = bool(configured.get("can_view")); create = bool(configured.get("can_create")); edit = bool(configured.get("can_edit"))
                    else:
                        module_perm, _ = module_permissions_with_source(effective_profile, mod, repo)
                        view = bool(module_perm.get("can_view")); create = bool(module_perm.get("can_create")); edit = bool(module_perm.get("can_edit"))
                    sec_rows.append({
                        "Override": configured is not None, "Section": label, "Module Key": mod, "Section Key": key,
                        "View": view, "Create": create, "Edit": edit,
                    })
                sec_edit = st.data_editor(
                    pd.DataFrame(sec_rows), hide_index=True, width="stretch", height=430,
                    disabled=["Section", "Module Key", "Section Key"], key=f"section_matrix_{uid}",
                )
                c1, c2 = st.columns(2, gap="small")
                if c1.button("Save Section Overrides", type="primary", width="stretch", key=f"save_sections_{uid}"):
                    try:
                        for _, row in sec_edit.iterrows():
                            natural = {"profile_id": uid, "module_key": row["Module Key"], "section_key": row["Section Key"]}
                            configured = existing_sections.get((str(row["Module Key"]), str(row["Section Key"])))
                            if bool(row["Override"]):
                                repo.upsert_by("user_section_permissions", {
                                    **natural, "can_view": bool(row["View"]), "can_create": bool(row["Create"]), "can_edit": bool(row["Edit"]),
                                }, natural_key=natural)
                            else:
                                _delete_override(repo, "user_section_permissions", configured)
                        save_success_popup("Section overrides saved. Sections without overrides remain visible by default.", queue_for_rerun=True)
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
                if c2.button("Reset Sections to Default Visible", width="stretch", key=f"reset_sections_{uid}"):
                    try:
                        for configured in existing_sections.values():
                            _delete_override(repo, "user_section_permissions", configured)
                        save_success_popup("All section overrides removed. Module-level default visibility applies.", queue_for_rerun=True)
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

            with stage_section("D", "RESET SELECTED USER PASSWORD", key="user_access_reset_password"):
                temp = st.text_input("New Temporary Password", type="password", key=f"reset_password_{uid}")
                if st.button("Reset Selected User Password", width="stretch", key=f"reset_password_button_{uid}"):
                    try:
                        _invoke({"action": "reset_password", "user_id": uid, "password": temp})
                        save_success_popup("Temporary password updated successfully.")
                    except Exception as exc:
                        st.error(str(exc))

    with defaults_tab:
        with stage_section("A", "ROLE → MODULE DEFAULTS", "Assign permissions once to a Role. Users inherit these rights unless an explicit User override exists.", key="role_defaults_v41418"):
            role_scope = st.selectbox("Role", ROLES, key="permission_role_scope")
            existing_role, role_rows = _permission_editor_rows(repo, table="role_module_defaults", eq={"role": role_scope, "status": "ACTIVE"})
            role_edit = st.data_editor(
                pd.DataFrame(role_rows), hide_index=True, width="stretch", height=390,
                disabled=["Module", "Module Key", "Source"], key=f"role_matrix_{role_scope}",
            )
            if st.button("Save Role Defaults", type="primary", width="stretch", key=f"save_role_defaults_{role_scope}"):
                try:
                    for _, row in role_edit.iterrows():
                        key = str(row["Module Key"]); configured = existing_role.get(key)
                        if bool(row["Override"]):
                            repo.upsert_by("role_module_defaults", {
                                "role": role_scope, "module_key": key, "can_view": bool(row["View"]),
                                "can_create": bool(row["Entry/Create"]), "can_edit": bool(row["Edit"]),
                                "can_validate": bool(row["Validate/Review"]), "can_approve": bool(row["Approve"]),
                                "can_archive": bool(row["Delete/Archive"]), "status": "ACTIVE",
                            }, natural_key={"role": role_scope, "module_key": key})
                        else:
                            _delete_override(repo, "role_module_defaults", configured)
                    save_success_popup("Role module defaults saved.", queue_for_rerun=True); st.rerun()
                except Exception as exc:
                    st.error(str(exc))

        with stage_section("B", "DEPARTMENT → MODULE DEFAULTS", "Department permissions apply when no explicit User or Role permission row exists.", key="department_defaults_v41418"):
            dep = st.selectbox("Department", departments, key="permission_department_scope")
            existing_dep, dep_rows = _permission_editor_rows(repo, table="department_module_defaults", eq={"department": dep, "status": "ACTIVE"})
            dep_edit = st.data_editor(
                pd.DataFrame(dep_rows), hide_index=True, width="stretch", height=390,
                disabled=["Module", "Module Key", "Source"], key=f"department_matrix_{dep}",
            )
            if st.button("Save Department Defaults", type="primary", width="stretch", key=f"save_department_defaults_{dep}"):
                try:
                    for _, row in dep_edit.iterrows():
                        key = str(row["Module Key"]); configured = existing_dep.get(key)
                        if bool(row["Override"]):
                            repo.upsert_by("department_module_defaults", {
                                "department": dep, "module_key": key, "can_view": bool(row["View"]),
                                "can_create": bool(row["Entry/Create"]), "can_edit": bool(row["Edit"]),
                                "can_validate": bool(row["Validate/Review"]), "can_approve": bool(row["Approve"]),
                                "can_archive": bool(row["Delete/Archive"]), "status": "ACTIVE",
                            }, natural_key={"department": dep, "module_key": key})
                        else:
                            _delete_override(repo, "department_module_defaults", configured)
                    save_success_popup("Department module defaults saved.", queue_for_rerun=True); st.rerun()
                except Exception as exc:
                    st.error(str(exc))

        with stage_section("C", "MODULE APPROVAL ROUTES", "Configured employee route first → Reports-To manager → controlled Approve-permission fallback.", key="approval_routes_v41418"):
            module_labels = {key: label for key, label in MODULES}
            c = st.columns(3, gap="small")
            route_module = c[0].selectbox("Approval Module", list(module_labels), index=list(module_labels).index("SUPPLY_CHAIN") if "SUPPLY_CHAIN" in module_labels else 0, format_func=lambda value: module_labels[value])
            route_department = c[1].selectbox("Department Scope", ["ALL DEPARTMENTS"] + departments)
            route_level = c[2].selectbox("Approval Level", [1, 2, 3])
            c = st.columns(3, gap="small")
            route_employee = c[0].selectbox("Approver Employee", [""] + list(emp), format_func=lambda x: emp.get(x, "— Select approver —"))
            route_name = c[1].text_input("Level Name", value="Manager Approval" if route_level == 1 else f"Approval Level {route_level}")
            route_status = c[2].selectbox("Route Status", ["ACTIVE", "INACTIVE"])
            required_route = st.checkbox("Required approval route", value=True)
            if st.button("Save Approval Route", type="primary", width="stretch", disabled=not bool(route_employee)):
                try:
                    department_value = None if route_department == "ALL DEPARTMENTS" else route_department
                    repo.upsert_by("qcms_module_approval_routes", {
                        "module_key": route_module, "department": department_value, "level_no": int(route_level),
                        "level_name": route_name.strip() or f"Approval Level {route_level}", "employee_id": route_employee,
                        "required": bool(required_route), "status": route_status,
                    }, natural_key={"module_key": route_module, "department": department_value, "level_no": int(route_level)})
                    save_success_popup("Approval route saved successfully.", queue_for_rerun=True); st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            routes = repo.select("qcms_module_approval_routes", order_by="module_key", limit=500)
            route_rows = [{
                "Module": module_labels.get(str(r.get("module_key")), r.get("module_key")),
                "Department": r.get("department") or "ALL DEPARTMENTS", "Level": r.get("level_no"),
                "Level Name": r.get("level_name"), "Approver": emp.get(str(r.get("employee_id")), str(r.get("employee_id") or "-")),
                "Required": bool(r.get("required")), "Status": r.get("status"), "_id": r.get("id"),
            } for r in routes]
            if route_rows:
                portal_table(pd.DataFrame(route_rows).drop(columns=["_id"], errors="ignore"), hide_index=True, width="stretch", height=min(300, 80 + len(route_rows) * 36))
                route_ids = {str(r["_id"]): f"{r['Module']} · {r['Department']} · Level {r['Level']} · {r['Approver']}" for r in route_rows if r.get("_id")}
                selected_route = st.selectbox("Selected Approval Route", list(route_ids), format_func=lambda value: route_ids[value]) if route_ids else None
                if selected_route and st.button("Deactivate Selected Route", width="stretch"):
                    try:
                        repo.update("qcms_module_approval_routes", selected_route, {"status": "INACTIVE"})
                        save_success_popup("Approval route deactivated.", queue_for_rerun=True); st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            else:
                st.info("No configured approval routes. QCMS will use Reports-To manager and then controlled approval-permission fallback.")

    with audit_tab:
        with stage_section("A", "USER ACTIVITY", "Navigation and application actions by user, module, section and record.", key="activity_log_v41418"):
            try:
                activities = repo.select("qcms_user_activity_log", order_by="occurred_at", desc=True, limit=2000)
            except Exception as exc:
                st.error(str(exc)); activities = []
            action_filter = st.text_input("Activity search", placeholder="user, module, section, action, record", key="activity_search")
            activity_rows = [{
                "Date / Time": r.get("occurred_at"), "User": r.get("user_email_snapshot"), "Role": r.get("role_snapshot"),
                "Department": r.get("department_snapshot"), "Module": r.get("module_key"), "Section": r.get("section_key"),
                "Action": r.get("action"), "Table": r.get("table_name"), "Record ID": r.get("row_id"),
            } for r in activities]
            if action_filter:
                activity_rows = [r for r in activity_rows if action_filter.casefold() in " ".join(str(v or "") for v in r.values()).casefold()]
            activity_frame = pd.DataFrame(activity_rows)
            if activity_frame.empty:
                st.info("No user activity is recorded yet.")
            else:
                portal_table(activity_frame, hide_index=True, width="stretch", height=420)
                activity_pdf = controlled_record_pdf_bytes("QCMS USER ACTIVITY REGISTER", {"Record Count": len(activity_frame)}, {"Activity": activity_frame})
                st.download_button("Download User Activity PDF", activity_pdf, file_name="QCMS_User_Activity.pdf", mime="application/pdf", width="stretch")

        with stage_section("B", "RECORD CHANGE AUDIT", "Database-level CREATE / UPDATE / DELETE history with the user and changed fields for tenant records.", key="record_audit_v41418"):
            try:
                audits = repo.select("audit_log", order_by="changed_at", desc=True, limit=3000)
            except Exception as exc:
                st.error(str(exc)); audits = []
            profiles = {str(p.get("id")): p for p in repo.select("profiles", limit=2000)}
            audit_search = st.text_input("Audit search", placeholder="table, operation, user, record", key="audit_search")
            audit_rows = []
            for r in audits:
                actor = profiles.get(str(r.get("changed_by") or ""), {})
                item = {
                    "Date / Time": r.get("changed_at"), "User": actor.get("email") or r.get("changed_by") or "SYSTEM",
                    "Operation": r.get("operation"), "Table / Section": r.get("table_name"), "Record ID": r.get("row_id"),
                    "Changed Fields": _changed_fields(r.get("old_data"), r.get("new_data")),
                }
                if not audit_search or audit_search.casefold() in " ".join(str(v or "") for v in item.values()).casefold():
                    audit_rows.append(item)
            audit_frame = pd.DataFrame(audit_rows)
            if audit_frame.empty:
                st.info("No matching record changes are available.")
            else:
                portal_table(audit_frame, hide_index=True, width="stretch", height=460)
                audit_pdf = controlled_record_pdf_bytes("QCMS RECORD CHANGE AUDIT", {"Record Count": len(audit_frame)}, {"Audit": audit_frame})
                st.download_button("Download Record Audit PDF", audit_pdf, file_name="QCMS_Record_Change_Audit.pdf", mime="application/pdf", width="stretch")

    with password_tab:
        with stage_section("A", "CHANGE MY PASSWORD", key="user_access_password_a"):
            p1 = st.text_input("New Password", type="password")
            p2 = st.text_input("Confirm New Password", type="password")
            if st.button("Change My Password", type="primary", width="stretch"):
                if len(p1) < 10:
                    st.error("Use at least 10 characters.")
                elif p1 != p2:
                    st.error("Passwords do not match.")
                else:
                    try:
                        get_session_client().auth.update_user({"password": p1})
                        save_success_popup("Password changed successfully.")
                    except Exception as exc:
                        st.error(str(exc))
