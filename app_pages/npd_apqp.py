from __future__ import annotations

from datetime import date, datetime, timedelta
from math import ceil
from typing import Any

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.repository import Repository
from core.ui import kpi_grid, page_header, section_bar, status_chip


ORDER_STATUSES = ["OPEN", "IN_PROGRESS", "ON_HOLD", "COMPLETED", "CANCELLED"]
STEP_STATUSES = ["PENDING", "IN_PROGRESS", "ON_HOLD", "COMPLETED"]
APQP_STATUSES = ["NOT_STARTED", "IN_PROGRESS", "ON_HOLD", "COMPLETED", "APPROVED", "NOT_APPLICABLE"]


def _parse_date(value: Any, fallback: date | None = None) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value or "").strip()
    if text:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
    return fallback or date.today()


def _part_rows(repo: Repository) -> list[dict]:
    return repo.select("parts", eq={"status": "ACTIVE"}, order_by="part_number", limit=4000)


def _customer_rows(repo: Repository) -> list[dict]:
    return repo.select("parties", contains={"party_types": ["CUSTOMER"]}, eq={"status": "ACTIVE"}, order_by="party_name", limit=2000)


def _process_rows(repo: Repository) -> list[dict]:
    return repo.select("processes", eq={"status": "ACTIVE"}, order_by="process_code", limit=2000)


def _labels(rows: list[dict], *fields: str) -> dict[str, str]:
    return {str(row["id"]): " · ".join(str(row.get(field) or "").strip() for field in fields if str(row.get(field) or "").strip()) for row in rows}


def _process_label(row: dict) -> str:
    code = str(row.get("process_code") or "").strip()
    name = str(row.get("process_name") or "").strip()
    return f"{code} · {name}" if code else name


def _flow_for_part(repo: Repository, part_id: str) -> dict | None:
    return repo.find_one("npd_process_flows", eq={"part_id": part_id})


def _flow_steps(repo: Repository, flow_id: str | None) -> list[dict]:
    if not flow_id:
        return []
    return repo.select("npd_process_flow_steps", eq={"flow_id": flow_id}, order_by="operation_no", limit=500)


def _delete_rows(repo: Repository, table: str, rows: list[dict]) -> None:
    for row in rows:
        repo.delete(table, str(row["id"]))


def _step_realtime_state(step: dict, today: date | None = None) -> tuple[str, str]:
    today = today or date.today()
    status = str(step.get("status") or "PENDING").upper()
    target_raw = step.get("target_date")
    target = _parse_date(target_raw) if target_raw else None
    completed_raw = step.get("completed_date")
    completed = _parse_date(completed_raw) if completed_raw else None
    if status == "COMPLETED":
        if target and completed and completed > target:
            return "completed_late", f"Completed {completed.strftime('%d-%m-%Y')} · {(completed-target).days} day(s) late"
        return "completed", f"Completed {completed.strftime('%d-%m-%Y') if completed else ''}".strip()
    if status == "ON_HOLD":
        return "hold", f"Target {target.strftime('%d-%m-%Y') if target else 'not set'}"
    if target and target < today:
        return "overdue", f"Target {target.strftime('%d-%m-%Y')} · {(today-target).days} day(s) overdue"
    if status == "IN_PROGRESS":
        if target:
            return "in_progress", f"Target {target.strftime('%d-%m-%Y')} · {(target-today).days} day(s) remaining"
        return "in_progress", "Target date not set"
    if target:
        return "pending", f"Target {target.strftime('%d-%m-%Y')} · {(target-today).days} day(s) remaining"
    return "not_planned", "Target date not set"


def _render_process_cards(steps: list[dict]) -> None:
    if not steps:
        st.info("No process sequence is available for this order.")
        return
    cards = []
    for row in steps:
        state, detail = _step_realtime_state(row)
        process_name = str(row.get("process_name") or "Process")
        operation_no = row.get("operation_no")
        status = str(row.get("status") or "PENDING").replace("_", " ").title()
        cards.append(
            f'<div class="npd-process-card npd-{state}">'
            f'<div class="npd-op">OP {operation_no}</div>'
            f'<div class="npd-process-name">{process_name}</div>'
            f'<div class="npd-process-status">{status}</div>'
            f'<div class="npd-process-date">{detail}</div>'
            f'</div>'
        )
    st.markdown(f'<div class="npd-process-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_process_flow() -> None:
    page_header("Process Flow Designer")
    repo = Repository(); perms = current_permissions("NPD_APQP")
    parts = _part_rows(repo); processes = _process_rows(repo)
    if not parts:
        st.info("Create an active Part Master record before defining a Process Flow.")
        return
    if not processes:
        st.info("Create Process Master records before defining a Process Flow.")
        return

    part_labels = _labels(parts, "part_number", "part_name")
    part_id = st.selectbox("Select Part Number", list(part_labels), format_func=lambda value: part_labels[value], key="npd_flow_part")
    part = next(row for row in parts if str(row["id"]) == part_id)
    flow = _flow_for_part(repo, part_id)
    existing_steps = _flow_steps(repo, str(flow["id"]) if flow else None)

    section_bar("PROCESS FLOW HEADER")
    c = st.columns(4, gap="small")
    revision = c[0].text_input("Revision", value=str((flow or {}).get("revision") or "A"), disabled=not perms["can_edit"])
    effective_date = c[1].date_input("Effective Date", value=_parse_date((flow or {}).get("effective_date")), format="DD-MM-YYYY", disabled=not perms["can_edit"])
    flow_status = c[2].selectbox("Flow Status", ["ACTIVE", "DRAFT", "INACTIVE"], index=["ACTIVE", "DRAFT", "INACTIVE"].index(str((flow or {}).get("status") or "ACTIVE")) if str((flow or {}).get("status") or "ACTIVE") in ["ACTIVE", "DRAFT", "INACTIVE"] else 0, disabled=not perms["can_edit"])
    c[3].text_input("Part", value=f"{part.get('part_number')} · {part.get('part_name')}", disabled=True)
    remarks = st.text_area("Flow Remarks", value=str((flow or {}).get("remarks") or ""), height=70, disabled=not perms["can_edit"])

    section_bar("OPERATIONAL SEQUENCE")
    process_by_id = {str(row["id"]): row for row in processes}
    process_label_to_id = {_process_label(row): str(row["id"]) for row in processes}
    initial = []
    for row in existing_steps:
        proc = process_by_id.get(str(row.get("process_id")))
        initial.append({
            "Operation No.": int(row.get("operation_no") or 0),
            "Process": _process_label(proc) if proc else str(row.get("process_name_snapshot") or ""),
            "Target Lead Days": int(row.get("target_lead_days") or 0),
            "Responsible": str(row.get("responsible") or ""),
            "Remarks": str(row.get("remarks") or ""),
        })
    if not initial:
        initial = [{"Operation No.": 0, "Process": next(iter(process_label_to_id)), "Target Lead Days": 0, "Responsible": "", "Remarks": ""}]
    edited = st.data_editor(
        pd.DataFrame(initial), num_rows="dynamic", hide_index=True, width="stretch", height=390,
        key=f"npd_flow_grid_{part_id}", disabled=not perms["can_edit"],
        column_config={
            "Operation No.": st.column_config.NumberColumn(min_value=0, step=10, required=True, width="small"),
            "Process": st.column_config.SelectboxColumn(options=list(process_label_to_id), required=True, width="large"),
            "Target Lead Days": st.column_config.NumberColumn(min_value=0, step=1, help="Optional default lead-time allocation for this process."),
            "Responsible": st.column_config.TextColumn(width="medium"),
            "Remarks": st.column_config.TextColumn(width="large"),
        },
    )

    if st.button("Save Process Flow", type="primary", width="stretch", disabled=not (perms["can_edit"] or perms["can_create"])):
        try:
            rows = edited.fillna("").to_dict("records")
            clean = []
            seen = set()
            for row in rows:
                process_label = str(row.get("Process") or "").strip()
                if not process_label:
                    continue
                operation_no = int(float(row.get("Operation No.") or 0))
                if operation_no in seen:
                    raise ValueError(f"Operation Number {operation_no} is duplicated. Each operation number must be unique.")
                seen.add(operation_no)
                process_id = process_label_to_id.get(process_label)
                if not process_id:
                    raise ValueError(f"Process '{process_label}' is not an active Process Master record.")
                clean.append((operation_no, process_id, process_by_id[process_id], row))
            if not clean:
                raise ValueError("Add at least one process step before saving the Process Flow.")
            clean.sort(key=lambda item: item[0])
            payload = {"part_id": part_id, "revision": revision.strip() or "A", "effective_date": effective_date.isoformat(), "status": flow_status, "remarks": remarks.strip() or None}
            saved = repo.update("npd_process_flows", str(flow["id"]), payload) if flow else repo.insert("npd_process_flows", payload)
            old = _flow_steps(repo, str(saved["id"]))
            _delete_rows(repo, "npd_process_flow_steps", old)
            for operation_no, process_id, process, source in clean:
                repo.insert("npd_process_flow_steps", {
                    "flow_id": str(saved["id"]), "process_id": process_id, "operation_no": operation_no,
                    "process_name_snapshot": str(process.get("process_name") or ""),
                    "target_lead_days": int(float(source.get("Target Lead Days") or 0)),
                    "responsible": str(source.get("Responsible") or "").strip() or None,
                    "remarks": str(source.get("Remarks") or "").strip() or None,
                })
            st.success("Part Process Flow saved in operational sequence.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    if existing_steps:
        section_bar("CURRENT PROCESS FLOW")
        preview_steps = []
        for index, row in enumerate(existing_steps):
            preview_steps.append({"operation_no": row.get("operation_no"), "process_name": row.get("process_name_snapshot"), "status": "PENDING", "target_date": None})
        _render_process_cards(preview_steps)


def _suggested_target_dates(start: date, delivery: date, count: int) -> list[date]:
    if count <= 0:
        return []
    total_days = max(0, (delivery - start).days)
    if count == 1:
        return [delivery]
    return [start + timedelta(days=round((index + 1) * total_days / count)) for index in range(count)]


def _order_label(row: dict, part_by_id: dict[str, dict], customer_by_id: dict[str, dict]) -> str:
    part = part_by_id.get(str(row.get("part_id"))) or {}
    customer = customer_by_id.get(str(row.get("customer_id"))) or {}
    return f"{row.get('order_number')} · {part.get('part_number','')} · {customer.get('party_name','')} · Due {_parse_date(row.get('delivery_date')).strftime('%d-%m-%Y')}"


def _sync_order_overall_status(repo: Repository, order: dict, steps: list[dict]) -> None:
    statuses = [str(row.get("status") or "PENDING").upper() for row in steps]
    if statuses and all(value == "COMPLETED" for value in statuses):
        status = "COMPLETED"
    elif any(value == "ON_HOLD" for value in statuses):
        status = "ON_HOLD"
    elif any(value in {"IN_PROGRESS", "COMPLETED"} for value in statuses):
        status = "IN_PROGRESS"
    else:
        status = "OPEN"
    if str(order.get("status") or "") != status:
        repo.update("npd_orders", str(order["id"]), {"status": status})


def render_npd_status() -> None:
    page_header("NPD Status")
    repo = Repository(); perms = current_permissions("NPD_APQP")
    parts = _part_rows(repo); customers = _customer_rows(repo)
    if not parts or not customers:
        st.info("Active Part Master and Customer Master records are required for NPD order tracking.")
        return
    part_by_id = {str(row["id"]): row for row in parts}; customer_by_id = {str(row["id"]): row for row in customers}
    part_labels = _labels(parts, "part_number", "part_name"); customer_labels = _labels(customers, "party_code", "party_name")
    orders = repo.select("npd_orders", order_by="delivery_date", limit=3000)

    tab1, tab2 = st.tabs(["Order Entry", "Order Status"])
    with tab1:
        section_bar("NPD ORDER / PART STATUS ENTRY")
        edit_options = [""] + [str(row["id"]) for row in orders]
        edit_id = st.selectbox("Edit Existing Order (optional)", edit_options, format_func=lambda value: "New Order" if not value else _order_label(next(row for row in orders if str(row["id"]) == value), part_by_id, customer_by_id), key="npd_order_edit")
        existing = next((row for row in orders if str(row["id"]) == edit_id), None)
        default_part_id = str((existing or {}).get("part_id") or parts[0]["id"])
        default_part = part_by_id.get(default_part_id) or parts[0]
        linked_customer = str(default_part.get("customer_id") or "")
        default_customer_id = str((existing or {}).get("customer_id") or linked_customer or customers[0]["id"])
        with st.form("npd_order_form"):
            c = st.columns(4, gap="small")
            order_number = c[0].text_input("Customer / Internal Order Number", value=str((existing or {}).get("order_number") or ""))
            part_id = c[1].selectbox("Part Number", list(part_labels), index=list(part_labels).index(default_part_id) if default_part_id in part_labels else 0, format_func=lambda value: part_labels[value], disabled=bool(existing))
            customer_id = c[2].selectbox("Customer", list(customer_labels), index=list(customer_labels).index(default_customer_id) if default_customer_id in customer_labels else 0, format_func=lambda value: customer_labels[value])
            qty = c[3].number_input("Order Qty (pcs)", min_value=1.0, value=float((existing or {}).get("order_qty") or 1), step=1.0)
            c = st.columns(4, gap="small")
            order_date = c[0].date_input("Order Date", value=_parse_date((existing or {}).get("order_date")), format="DD-MM-YYYY")
            start_date = c[1].date_input("NPD Start Date", value=_parse_date((existing or {}).get("start_date")), format="DD-MM-YYYY")
            delivery_date = c[2].date_input("Customer Delivery Date", value=_parse_date((existing or {}).get("delivery_date"), date.today() + timedelta(days=30)), format="DD-MM-YYYY")
            c[3].selectbox("Order Status", ORDER_STATUSES, index=ORDER_STATUSES.index(str((existing or {}).get("status") or "OPEN")) if str((existing or {}).get("status") or "OPEN") in ORDER_STATUSES else 0, disabled=True)
            remarks = st.text_area("Order / Development Remarks", value=str((existing or {}).get("remarks") or ""), height=70)
            submitted = st.form_submit_button("Save NPD Order", type="primary", width="stretch", disabled=not (perms["can_create"] or perms["can_edit"]))
        if submitted:
            try:
                if not order_number.strip():
                    raise ValueError("Order Number is required.")
                if delivery_date < start_date:
                    raise ValueError("Customer Delivery Date cannot be before the NPD Start Date.")
                flow = _flow_for_part(repo, part_id)
                flow_steps = _flow_steps(repo, str(flow["id"]) if flow else None)
                if not flow_steps and not existing:
                    raise ValueError("Create and save the Part Process Flow before creating this NPD Order.")
                payload = {"order_number": order_number.strip(), "part_id": part_id, "customer_id": customer_id, "order_qty": qty, "order_date": order_date.isoformat(), "start_date": start_date.isoformat(), "delivery_date": delivery_date.isoformat(), "remarks": remarks.strip() or None}
                saved = repo.update("npd_orders", str(existing["id"]), payload) if existing else repo.insert("npd_orders", {**payload, "status": "OPEN"})
                if not existing:
                    suggested = _suggested_target_dates(start_date, delivery_date, len(flow_steps))
                    for index, step in enumerate(flow_steps):
                        repo.insert("npd_order_steps", {
                            "npd_order_id": str(saved["id"]), "flow_step_id": str(step["id"]), "operation_no": int(step.get("operation_no") or 0),
                            "process_id": step.get("process_id"), "process_name": str(step.get("process_name_snapshot") or ""),
                            "target_date": suggested[index].isoformat(), "status": "PENDING", "completed_date": None,
                            "responsible": step.get("responsible"), "remarks": None,
                        })
                st.success("NPD Order saved and process-status cards created from the Part Process Flow.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

        if orders:
            section_bar("ORDER REGISTER")
            frame = pd.DataFrame([{
                "Order": row.get("order_number"), "Part": (part_by_id.get(str(row.get("part_id"))) or {}).get("part_number"),
                "Customer": (customer_by_id.get(str(row.get("customer_id"))) or {}).get("party_name"), "Order Qty": row.get("order_qty"),
                "Start Date": row.get("start_date"), "Delivery Date": row.get("delivery_date"), "Status": str(row.get("status") or "").replace("_", " ").title(),
            } for row in orders])
            st.dataframe(frame, hide_index=True, width="stretch", height=330)

    with tab2:
        if not orders:
            st.info("Create an NPD Order to open the real-time Process Status view.")
            return
        order_labels = {str(row["id"]): _order_label(row, part_by_id, customer_by_id) for row in orders}
        order_id = st.selectbox("Open Order Status", list(order_labels), format_func=lambda value: order_labels[value], key="npd_status_order")
        order = next(row for row in orders if str(row["id"]) == order_id)
        steps = repo.select("npd_order_steps", eq={"npd_order_id": order_id}, order_by="operation_no", limit=500)
        today = date.today()
        overdue_count = sum(_step_realtime_state(row, today)[0] == "overdue" for row in steps)
        completed_count = sum(str(row.get("status") or "") == "COMPLETED" for row in steps)
        in_progress_count = sum(str(row.get("status") or "") == "IN_PROGRESS" for row in steps)
        due = _parse_date(order.get("delivery_date"))
        days_to_delivery = (due - today).days
        overall = "COMPLETED" if steps and completed_count == len(steps) else ("DELAYED" if overdue_count else "ON TRACK")
        kpi_grid([
            {"label": "Order Qty", "value": f"{float(order.get('order_qty') or 0):,.0f}", "foot": "pcs", "color": "#1469A8", "background": "#EFF6FF"},
            {"label": "Processes Complete", "value": f"{completed_count}/{len(steps)}", "foot": "Operational sequence", "color": "#15803D", "background": "#F0FDF4"},
            {"label": "In Progress", "value": in_progress_count, "foot": "Current active operations", "color": "#6D28D9", "background": "#F5F3FF"},
            {"label": "Overdue Processes", "value": overdue_count, "foot": "Target date exceeded", "color": "#B91C1C", "background": "#FEF2F2"},
            {"label": "Days to Delivery", "value": days_to_delivery, "foot": due.strftime("%d-%m-%Y"), "color": "#D97706" if days_to_delivery < 7 else "#0F766E", "background": "#FFF7ED" if days_to_delivery < 7 else "#F0FDFA"},
            {"label": "Real-time Status", "value": overall, "foot": "Date-driven evaluation", "color": "#B91C1C" if overall == "DELAYED" else "#15803D", "background": "#FEF2F2" if overall == "DELAYED" else "#F0FDF4"},
        ])
        section_bar("ORDER PROCESS STATUS")
        _render_process_cards(steps)
        section_bar("UPDATE PROCESS TARGETS & STATUS")
        process_frame = pd.DataFrame([{
            "ID": str(row["id"]), "Operation No.": int(row.get("operation_no") or 0), "Process": row.get("process_name"),
            "Target Date": _parse_date(row.get("target_date")) if row.get("target_date") else None,
            "Status": str(row.get("status") or "PENDING"), "Completed Date": _parse_date(row.get("completed_date")) if row.get("completed_date") else None,
            "Responsible": row.get("responsible") or "", "Remarks": row.get("remarks") or "",
        } for row in steps])
        edited = st.data_editor(
            process_frame, hide_index=True, width="stretch", height=max(260, min(560, 92 + 38 * max(1, len(process_frame)))), key=f"npd_order_step_editor_{order_id}", disabled=not perms["can_edit"],
            column_config={
                "ID": None, "Operation No.": st.column_config.NumberColumn(disabled=True, width="small"), "Process": st.column_config.TextColumn(disabled=True, width="large"),
                "Target Date": st.column_config.DateColumn(format="DD-MM-YYYY", required=True), "Status": st.column_config.SelectboxColumn(options=STEP_STATUSES, required=True),
                "Completed Date": st.column_config.DateColumn(format="DD-MM-YYYY"), "Responsible": st.column_config.TextColumn(width="medium"), "Remarks": st.column_config.TextColumn(width="large"),
            },
        )
        if st.button("Update Order Process Status", type="primary", width="stretch", disabled=not perms["can_edit"]):
            try:
                for row in edited.to_dict("records"):
                    status = str(row.get("Status") or "PENDING")
                    completed = row.get("Completed Date")
                    if status == "COMPLETED" and (completed is None or pd.isna(completed)):
                        completed = date.today()
                    if status != "COMPLETED":
                        completed = None
                    target = row.get("Target Date")
                    repo.update("npd_order_steps", str(row["ID"]), {
                        "target_date": target.isoformat() if isinstance(target, date) else str(target)[:10], "status": status,
                        "completed_date": completed.isoformat() if isinstance(completed, date) else (str(completed)[:10] if completed else None),
                        "responsible": str(row.get("Responsible") or "").strip() or None, "remarks": str(row.get("Remarks") or "").strip() or None,
                    })
                refreshed = repo.select("npd_order_steps", eq={"npd_order_id": order_id}, order_by="operation_no", limit=500)
                _sync_order_overall_status(repo, order, refreshed)
                st.success("Process target dates and real-time status updated.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _default_apqp_tasks() -> list[tuple[int, str, str]]:
    return [
        (10, "Phase 1 - Plan & Define", "Customer Requirements / Feasibility Review"),
        (20, "Phase 2 - Product Design", "Drawing / Technical Specification Review"),
        (30, "Phase 3 - Process Design", "Process Flow Diagram"),
        (40, "Phase 3 - Process Design", "PFMEA"),
        (50, "Phase 3 - Process Design", "Control Plan"),
        (60, "Phase 4 - Validation", "Tooling / Gauge / Process Validation"),
        (70, "Phase 4 - Validation", "MSA / Capability / Dimensional / Material Validation"),
        (80, "Phase 5 - Launch & Feedback", "PPAP Submission / Customer Approval"),
    ]


def render_apqp() -> None:
    page_header("APQP")
    repo = Repository(); perms = current_permissions("NPD_APQP")
    parts = _part_rows(repo); customers = _customer_rows(repo)
    if not parts or not customers:
        st.info("Active Part and Customer records are required for APQP project tracking.")
        return
    part_labels = _labels(parts, "part_number", "part_name"); customer_labels = _labels(customers, "party_code", "party_name")
    projects = repo.select("ppap_projects", order_by="target_submission_date", limit=2000)
    project_options = [""] + [str(row["id"]) for row in projects]
    project_labels = {str(row["id"]): f"{row.get('project_code')} · {part_labels.get(str(row.get('part_id')), '')}" for row in projects}
    selected_id = st.selectbox("Open / Edit APQP Project", project_options, format_func=lambda value: "New APQP Project" if not value else project_labels[value])
    existing = next((row for row in projects if str(row["id"]) == selected_id), None)
    default_part_id = str((existing or {}).get("part_id") or parts[0]["id"])
    linked_customer = str((next((row for row in parts if str(row["id"]) == default_part_id), {}) or {}).get("customer_id") or "")
    default_customer_id = str((existing or {}).get("customer_id") or linked_customer or customers[0]["id"])

    section_bar("APQP PROJECT HEADER")
    with st.form("apqp_project_form"):
        c = st.columns(4, gap="small")
        project_code = c[0].text_input("Project / NPD Number", value=str((existing or {}).get("project_code") or ""))
        part_id = c[1].selectbox("Part Number", list(part_labels), index=list(part_labels).index(default_part_id) if default_part_id in part_labels else 0, format_func=lambda value: part_labels[value])
        customer_id = c[2].selectbox("Customer", list(customer_labels), index=list(customer_labels).index(default_customer_id) if default_customer_id in customer_labels else 0, format_func=lambda value: customer_labels[value])
        submission_level = c[3].selectbox("PPAP Submission Level", ["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"], index=max(0, ["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"].index(str((existing or {}).get("submission_level") or "Level 3"))) if str((existing or {}).get("submission_level") or "Level 3") in ["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"] else 2)
        c = st.columns(4, gap="small")
        target_date = c[0].date_input("Target PPAP Submission", value=_parse_date((existing or {}).get("target_submission_date"), date.today() + timedelta(days=60)), format="DD-MM-YYYY")
        coordinator = c[1].text_input("APQP Coordinator", value=str((existing or {}).get("coordinator") or ""))
        reason = c[2].text_input("Reason / Program", value=str((existing or {}).get("reason") or "New Product Development"))
        status = c[3].selectbox("Project Status", ["IN_PROGRESS", "ON_HOLD", "COMPLETED", "CANCELLED"], index=["IN_PROGRESS", "ON_HOLD", "COMPLETED", "CANCELLED"].index(str((existing or {}).get("status") or "IN_PROGRESS")) if str((existing or {}).get("status") or "IN_PROGRESS") in ["IN_PROGRESS", "ON_HOLD", "COMPLETED", "CANCELLED"] else 0)
        remarks = st.text_area("APQP Remarks", value=str((existing or {}).get("remarks") or ""), height=70)
        save = st.form_submit_button("Save APQP Project", type="primary", width="stretch", disabled=not (perms["can_create"] or perms["can_edit"]))
    if save:
        try:
            if not project_code.strip():
                raise ValueError("Project / NPD Number is required.")
            payload = {"project_code": project_code.strip(), "part_id": part_id, "customer_id": customer_id, "submission_level": submission_level, "reason": reason.strip() or None, "target_submission_date": target_date.isoformat(), "coordinator": coordinator.strip() or None, "status": status, "remarks": remarks.strip() or None}
            saved = repo.update("ppap_projects", str(existing["id"]), payload) if existing else repo.insert("ppap_projects", {**payload, "completion_percent": 0})
            st.success("APQP Project saved.")
            st.session_state["apqp_selected_project"] = str(saved["id"])
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    project_id = str((existing or {}).get("id") or st.session_state.get("apqp_selected_project") or "")
    if not project_id:
        return
    project = repo.get("ppap_projects", project_id) or existing
    tasks = repo.select("ppap_documents", eq={"ppap_project_id": project_id}, order_by="sequence_no", limit=500)
    section_bar("APQP PHASE STATUS")
    if not tasks and st.button("Load Standard APQP Gates", width="stretch", disabled=not perms["can_create"]):
        for sequence_no, phase, activity in _default_apqp_tasks():
            repo.insert("ppap_documents", {"ppap_project_id": project_id, "sequence_no": sequence_no, "apqp_phase": phase, "document_type": activity, "status": "NOT_STARTED"})
        st.success("Standard APQP gates loaded.")
        st.rerun()
    if tasks:
        completed = sum(str(row.get("status") or "") in {"COMPLETED", "APPROVED", "NOT_APPLICABLE"} for row in tasks)
        completion = round(completed * 100 / len(tasks)) if tasks else 0
        due = _parse_date((project or {}).get("target_submission_date"))
        overdue = sum(str(row.get("status") or "") not in {"COMPLETED", "APPROVED", "NOT_APPLICABLE"} and row.get("due_date") and _parse_date(row.get("due_date")) < date.today() for row in tasks)
        kpi_grid([
            {"label": "APQP Completion", "value": f"{completion}%", "foot": f"{completed}/{len(tasks)} gates closed", "color": "#15803D", "background": "#F0FDF4"},
            {"label": "Open Gates", "value": len(tasks)-completed, "foot": "Pending / in progress", "color": "#D97706", "background": "#FFF7ED"},
            {"label": "Overdue Gates", "value": overdue, "foot": "Target dates exceeded", "color": "#B91C1C", "background": "#FEF2F2"},
            {"label": "PPAP Target", "value": due.strftime("%d-%m-%Y"), "foot": f"{(due-date.today()).days} day(s)", "color": "#1469A8", "background": "#EFF6FF"},
        ])
        task_frame = pd.DataFrame([{
            "ID": str(row["id"]), "Seq": int(row.get("sequence_no") or 0), "APQP Phase": row.get("apqp_phase") or "", "Activity / Deliverable": row.get("document_type") or "",
            "Evidence / Document No.": row.get("document_number") or "", "Revision": row.get("revision") or "", "Owner": row.get("owner") or "",
            "Due Date": _parse_date(row.get("due_date")) if row.get("due_date") else None, "Status": str(row.get("status") or "NOT_STARTED"),
            "Approved Date": _parse_date(row.get("approved_date")) if row.get("approved_date") else None, "Remarks": row.get("remarks") or "",
        } for row in tasks])
        edited = st.data_editor(
            task_frame, num_rows="dynamic", hide_index=True, width="stretch", height=430, key=f"apqp_tasks_{project_id}", disabled=not perms["can_edit"],
            column_config={
                "ID": None, "Seq": st.column_config.NumberColumn(min_value=0, step=10, required=True), "APQP Phase": st.column_config.TextColumn(required=True, width="large"),
                "Activity / Deliverable": st.column_config.TextColumn(required=True, width="large"), "Due Date": st.column_config.DateColumn(format="DD-MM-YYYY"),
                "Status": st.column_config.SelectboxColumn(options=APQP_STATUSES, required=True), "Approved Date": st.column_config.DateColumn(format="DD-MM-YYYY"),
            },
        )
        if st.button("Update APQP Gates", type="primary", width="stretch", disabled=not perms["can_edit"]):
            try:
                existing_ids = {str(row["id"]) for row in tasks}
                retained_ids = set()
                for row in edited.fillna("").to_dict("records"):
                    activity = str(row.get("Activity / Deliverable") or "").strip()
                    if not activity:
                        continue
                    record_id = str(row.get("ID") or "").strip()
                    due_date = row.get("Due Date")
                    approved_date = row.get("Approved Date")
                    payload = {
                        "ppap_project_id": project_id, "sequence_no": int(float(row.get("Seq") or 0)), "apqp_phase": str(row.get("APQP Phase") or "").strip() or None,
                        "document_type": activity, "document_number": str(row.get("Evidence / Document No.") or "").strip() or None,
                        "revision": str(row.get("Revision") or "").strip() or None, "owner": str(row.get("Owner") or "").strip() or None,
                        "due_date": due_date.isoformat() if isinstance(due_date, date) else (str(due_date)[:10] if due_date else None),
                        "status": str(row.get("Status") or "NOT_STARTED"), "approved_date": approved_date.isoformat() if isinstance(approved_date, date) else (str(approved_date)[:10] if approved_date else None),
                        "remarks": str(row.get("Remarks") or "").strip() or None,
                    }
                    if record_id in existing_ids:
                        repo.update("ppap_documents", record_id, payload); retained_ids.add(record_id)
                    else:
                        saved = repo.insert("ppap_documents", payload); retained_ids.add(str(saved["id"]))
                for record_id in existing_ids - retained_ids:
                    repo.delete("ppap_documents", record_id)
                refreshed = repo.select("ppap_documents", eq={"ppap_project_id": project_id}, limit=500)
                closed = sum(str(row.get("status") or "") in {"COMPLETED", "APPROVED", "NOT_APPLICABLE"} for row in refreshed)
                percent = round(closed * 100 / len(refreshed)) if refreshed else 0
                repo.update("ppap_projects", project_id, {"completion_percent": percent})
                st.success("APQP gates updated.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
