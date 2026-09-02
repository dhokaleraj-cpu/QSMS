from __future__ import annotations

from datetime import date, datetime, timedelta
from math import ceil
from typing import Any

import pandas as pd
import streamlit as st
from core.ui import portal_table

from core.access import current_permissions
from core.delete_service import password_delete_panel
from core.reporting import controlled_record_pdf_bytes, npd_pending_status_pdf_bytes
from core.selection_labels import employee_label, part_label, party_label, process_label
from core.ui import safe
from core.repository import Repository
from core.record_audit import annotate_transaction_rows
from core.ui import kpi_grid, page_header, save_success_popup, section_bar, stage_section, status_chip


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
        except (TypeError, ValueError, OverflowError):
            pass
    return fallback or date.today()


def _optional_date(value: Any) -> date | None:
    """Parse an optional APQP date without substituting today on bad/blank data."""
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        text = str(value).strip()
        return date.fromisoformat(text[:10]) if text else None
    except (TypeError, ValueError, OverflowError):
        return None


def _part_rows(repo: Repository) -> list[dict]:
    return repo.select("parts", eq={"status": "ACTIVE"}, order_by="part_number", limit=4000)


def _customer_rows(repo: Repository) -> list[dict]:
    return repo.select("parties", contains={"party_types": ["CUSTOMER"]}, eq={"status": "ACTIVE"}, order_by="party_name", limit=2000)


def _process_rows(repo: Repository) -> list[dict]:
    return repo.select("processes", eq={"status": "ACTIVE"}, order_by="process_code", limit=2000)


def _employee_rows(repo: Repository) -> list[dict]:
    return repo.select("employees", eq={"status": "ACTIVE"}, order_by="first_name", limit=2000)


def _employee_labels(rows: list[dict]) -> dict[str, str]:
    return {str(row["id"]): employee_label(row) for row in rows}


def _employee_option_maps(rows: list[dict], legacy_values: list[str] | None = None) -> tuple[list[str], dict[str, str | None]]:
    labels = _employee_labels(rows)
    option_to_id: dict[str, str | None] = {"— Not assigned —": None}
    for employee_id, label in labels.items():
        option_to_id[label] = employee_id
    for value in legacy_values or []:
        value = str(value or "").strip()
        if value and value not in option_to_id:
            option_to_id[f"Legacy · {value}"] = None
    return list(option_to_id), option_to_id


def _labels(rows: list[dict], *fields: str) -> dict[str, str]:
    return {str(row["id"]): " · ".join(str(row.get(field) or "").strip() for field in fields if str(row.get(field) or "").strip()) for row in rows}


def _process_label(row: dict) -> str:
    return process_label(row)


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


def _render_process_cards(steps: list[dict], point_progress: dict[str, tuple[int, int]] | None = None, *, clickable: bool = False, key_prefix: str = "npd") -> None:
    if not steps:
        st.info("No process sequence is available for this order.")
        return
    point_progress = point_progress or {}
    if not clickable:
        cards = []
        for row in steps:
            state, detail = _step_realtime_state(row)
            process_name = str(row.get("process_name") or row.get("process_name_snapshot") or "Process")
            operation_no = row.get("operation_no"); status = str(row.get("status") or "PENDING").replace("_", " ").title()
            completed_points, total_points = point_progress.get(str(row.get("id")), (0, 0))
            checkpoint_line = f'<div class="npd-process-date">Checkpoints {completed_points}/{total_points}</div>' if total_points else ''
            remarks = str(row.get("remarks") or "").strip(); remark_line = f'<div class="npd-process-remarks">{remarks}</div>' if remarks else ''
            cards.append(f'<div class="npd-process-card npd-{state}"><div class="npd-op">OP {operation_no}</div><div class="npd-process-name">{process_name}</div><div class="npd-process-status">{status}</div><div class="npd-process-date">{detail}</div>{checkpoint_line}{remark_line}</div>')
        st.markdown(f'<div class="npd-process-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
        return
    # Clickable process cards: the whole Streamlit button is the card surface.
    for row_start in range(0, len(steps), 4):
        batch = steps[row_start:row_start+4]
        cols = st.columns(4, gap="small")
        for col, row in zip(cols, batch):
            state, detail = _step_realtime_state(row); step_id = str(row.get("id")); process_name = str(row.get("process_name") or "Process")
            status = str(row.get("status") or "PENDING").replace("_", " ").title(); remarks = str(row.get("remarks") or "").strip()
            done,total = point_progress.get(step_id,(0,0)); checkpoint = f" · Points {done}/{total}" if total else ""
            label = f"OP {row.get('operation_no')} · {process_name}\n{status} · {detail}{checkpoint}"
            if remarks: label += f"\nRemarks: {remarks}"
            with col:
                with st.container(key=f"npd_click_card_{state}_{step_id}"):
                    if st.button(label, key=f"{key_prefix}_card_{step_id}", width="stretch"):
                        st.session_state["npd_selected_step_id"] = step_id



def render_process_flow() -> None:
    page_header("Process Flow Designer")
    repo = Repository(); perms = current_permissions("NPD_APQP")
    parts = _part_rows(repo); processes = _process_rows(repo); employees = _employee_rows(repo)
    if not parts:
        st.info("Create an active Part Master record before defining a Process Flow.")
        return
    if not processes:
        st.info("Create Process Master records before defining a Process Flow.")
        return

    part_labels = {str(row["id"]): part_label(row) for row in parts}
    part_id = st.selectbox("Select Part Number", list(part_labels), format_func=lambda value: part_labels[value], key="npd_flow_part")
    part = next(row for row in parts if str(row["id"]) == part_id)
    flow = _flow_for_part(repo, part_id)
    existing_steps = _flow_steps(repo, str(flow["id"]) if flow else None)

    with stage_section("A", 'PROCESS FLOW HEADER', key="npd_apqp_render_process_flow_a"):
        c = st.columns(4, gap="small")
        revision = c[0].text_input("Revision", value=str((flow or {}).get("revision") or "A"), disabled=not perms["can_edit"])
        effective_date = c[1].date_input("Effective Date", value=_parse_date((flow or {}).get("effective_date")), format="DD-MM-YYYY", disabled=not perms["can_edit"])
        flow_status = c[2].selectbox("Flow Status", ["ACTIVE", "DRAFT", "INACTIVE"], index=["ACTIVE", "DRAFT", "INACTIVE"].index(str((flow or {}).get("status") or "ACTIVE")) if str((flow or {}).get("status") or "ACTIVE") in ["ACTIVE", "DRAFT", "INACTIVE"] else 0, disabled=not perms["can_edit"])
        c[3].text_input("Part", value=f"{part.get('part_number')} · {part.get('part_name')}", disabled=True)
        remarks = st.text_area("Flow Remarks", value=str((flow or {}).get("remarks") or ""), height=70, disabled=not perms["can_edit"])

    with stage_section("B", 'OPERATIONAL SEQUENCE', key="npd_apqp_render_process_flow_b"):
        process_by_id = {str(row["id"]): row for row in processes}
        process_label_to_id = {_process_label(row): str(row["id"]) for row in processes}
        employee_labels = _employee_labels(employees)
        legacy_values = [str(row.get("responsible") or "") for row in existing_steps if not row.get("responsible_employee_id")]
        employee_options, employee_option_to_id = _employee_option_maps(employees, legacy_values)
        employee_id_to_option = {employee_id: label for label, employee_id in employee_option_to_id.items() if employee_id}

        initial = []
        for row in existing_steps:
            proc = process_by_id.get(str(row.get("process_id")))
            responsible_option = employee_id_to_option.get(str(row.get("responsible_employee_id") or ""))
            if not responsible_option and row.get("responsible"):
                responsible_option = f"Legacy · {row.get('responsible')}"
            initial.append({
                "Operation No.": int(row.get("operation_no") or 0),
                "Process": _process_label(proc) if proc else str(row.get("process_name_snapshot") or ""),
                "Target Lead Days": int(row.get("target_lead_days") or 0),
                "Responsible Employee": responsible_option or "— Not assigned —",
                "Remarks": str(row.get("remarks") or ""),
            })
        if not initial:
            initial = [{"Operation No.": 0, "Process": next(iter(process_label_to_id)), "Target Lead Days": 0, "Responsible Employee": "— Not assigned —", "Remarks": ""}]
        edited = st.data_editor(
            pd.DataFrame(initial), num_rows="dynamic", hide_index=True, width="stretch", height=390,
            key=f"npd_flow_grid_{part_id}", disabled=not perms["can_edit"],
            column_config={
                "Operation No.": st.column_config.NumberColumn(min_value=0, step=10, required=True, width="small"),
                "Process": st.column_config.SelectboxColumn(options=list(process_label_to_id), required=True, width="large"),
                "Target Lead Days": st.column_config.NumberColumn(min_value=0, step=1, help="Optional default lead-time allocation for this process."),
                "Responsible Employee": st.column_config.SelectboxColumn(options=employee_options, width="large"),
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
                old_steps = _flow_steps(repo, str(saved["id"]))
                old_by_op = {int(row.get("operation_no") or 0): row for row in old_steps}
                retained_ids: set[str] = set()
                for operation_no, process_id, process, source in clean:
                    responsible_option = str(source.get("Responsible Employee") or "— Not assigned —")
                    employee_id = employee_option_to_id.get(responsible_option)
                    snapshot = employee_labels.get(str(employee_id)) if employee_id else (responsible_option.removeprefix("Legacy · ").strip() if responsible_option.startswith("Legacy · ") else None)
                    step_payload = {
                        "flow_id": str(saved["id"]), "process_id": process_id, "operation_no": operation_no,
                        "process_name_snapshot": str(process.get("process_name") or ""),
                        "target_lead_days": int(float(source.get("Target Lead Days") or 0)),
                        "responsible_employee_id": employee_id,
                        "responsible": snapshot,
                        "remarks": str(source.get("Remarks") or "").strip() or None,
                    }
                    existing_step = old_by_op.get(operation_no)
                    if existing_step:
                        repo.update("npd_process_flow_steps", str(existing_step["id"]), step_payload)
                        retained_ids.add(str(existing_step["id"]))
                    else:
                        created = repo.insert("npd_process_flow_steps", step_payload)
                        retained_ids.add(str(created["id"]))
                for old_step in old_steps:
                    if str(old_step["id"]) not in retained_ids:
                        repo.delete("npd_process_flow_steps", str(old_step["id"]))
                save_success_popup("Part Process Flow saved in operational sequence.", queue_for_rerun=True)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

        if not flow:
            st.info("Save the Process Flow first. Checkpoints / bullet points can then be added under each process.")
            return

        # Refresh after any saved flow so checkpoint rows are always tied to stable step IDs.
        flow = _flow_for_part(repo, part_id)
        existing_steps = _flow_steps(repo, str(flow["id"]) if flow else None)
    with stage_section("C", 'PROCESS CHECKPOINTS / BULLET POINTS', 'Add the quality, development or completion points that must be closed under each process.', key="npd_apqp_render_process_flow_c"):
        all_point_rows: list[dict] = []
        for step in existing_steps:
            step_id = str(step["id"])
            points = repo.select("npd_process_flow_points", eq={"flow_step_id": step_id}, order_by="sequence_no", limit=300)
            all_point_rows.extend([{**point, "_operation_no": step.get("operation_no"), "_process_name": step.get("process_name_snapshot")} for point in points])
            with st.expander(f"OP {step.get('operation_no')} - {step.get('process_name_snapshot')} · {len(points)} checkpoint(s)", expanded=False):
                legacy_point_values = [str(point.get("responsible_snapshot") or "") for point in points if not point.get("responsible_employee_id")]
                point_options, point_option_to_id = _employee_option_maps(employees, legacy_point_values)
                point_id_to_option = {employee_id: label for label, employee_id in point_option_to_id.items() if employee_id}
                point_frame = pd.DataFrame([{
                    "ID": str(point["id"]),
                    "Seq": int(point.get("sequence_no") or 10),
                    "Checkpoint / Bullet Point": point.get("point_text") or "",
                    "Responsible Employee": point_id_to_option.get(str(point.get("responsible_employee_id") or "")) or (f"Legacy · {point.get('responsible_snapshot')}" if point.get("responsible_snapshot") else "— Not assigned —"),
                    "Status": point.get("status") or "ACTIVE",
                    "Remarks": point.get("remarks") or "",
                } for point in points], columns=["ID", "Seq", "Checkpoint / Bullet Point", "Responsible Employee", "Status", "Remarks"])
                point_edit = st.data_editor(
                    point_frame, num_rows="dynamic", hide_index=True, width="stretch", height=max(180, min(420, 110 + 38 * max(1, len(point_frame)))),
                    key=f"npd_flow_points_{step_id}", disabled=not perms["can_edit"],
                    column_config={
                        "ID": None,
                        "Seq": st.column_config.NumberColumn(min_value=0, step=10, required=True, width="small"),
                        "Checkpoint / Bullet Point": st.column_config.TextColumn(required=True, width="large"),
                        "Responsible Employee": st.column_config.SelectboxColumn(options=point_options, width="large"),
                        "Status": st.column_config.SelectboxColumn(options=["ACTIVE", "INACTIVE"], required=True),
                        "Remarks": st.column_config.TextColumn(width="large"),
                    },
                )
                if st.button(f"Save Checkpoints - OP {step.get('operation_no')}", key=f"save_points_{step_id}", type="primary", width="stretch", disabled=not perms["can_edit"]):
                    try:
                        existing_ids = {str(point["id"]) for point in points}
                        retained: set[str] = set()
                        seen_seq: set[int] = set()
                        for row in point_edit.fillna("").to_dict("records"):
                            point_text = str(row.get("Checkpoint / Bullet Point") or "").strip()
                            if not point_text:
                                continue
                            sequence_no = int(float(row.get("Seq") or 0))
                            if sequence_no in seen_seq:
                                raise ValueError(f"Checkpoint sequence {sequence_no} is duplicated in OP {step.get('operation_no')}.")
                            seen_seq.add(sequence_no)
                            resp_option = str(row.get("Responsible Employee") or "— Not assigned —")
                            resp_id = point_option_to_id.get(resp_option)
                            resp_snapshot = employee_labels.get(str(resp_id)) if resp_id else (resp_option.removeprefix("Legacy · ").strip() if resp_option.startswith("Legacy · ") else None)
                            payload = {
                                "flow_step_id": step_id, "sequence_no": sequence_no, "point_text": point_text,
                                "responsible_employee_id": resp_id, "responsible_snapshot": resp_snapshot,
                                "status": str(row.get("Status") or "ACTIVE"), "remarks": str(row.get("Remarks") or "").strip() or None,
                            }
                            record_id = str(row.get("ID") or "").strip()
                            if record_id in existing_ids:
                                repo.update("npd_process_flow_points", record_id, payload); retained.add(record_id)
                            else:
                                created = repo.insert("npd_process_flow_points", payload); retained.add(str(created["id"]))
                        for record_id in existing_ids - retained:
                            repo.delete("npd_process_flow_points", record_id)
                        save_success_popup(f"Checkpoints saved for OP {step.get('operation_no')}.", queue_for_rerun=True)
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

        if existing_steps:
            st.markdown("**Current Process Flow**")
            preview_steps = [{"operation_no": row.get("operation_no"), "process_name": row.get("process_name_snapshot"), "status": "PENDING", "target_date": None} for row in existing_steps]
            _render_process_cards(preview_steps)
            step_rows = [{
                "Operation No.": row.get("operation_no"), "Process": row.get("process_name_snapshot"),
                "Target Lead Days": row.get("target_lead_days"), "Responsible": row.get("responsible"), "Remarks": row.get("remarks")
            } for row in existing_steps]
            point_rows = [{
                "Operation No.": row.get("_operation_no"), "Process": row.get("_process_name"), "Seq": row.get("sequence_no"),
                "Checkpoint": row.get("point_text"), "Responsible": row.get("responsible_snapshot"), "Status": row.get("status"), "Remarks": row.get("remarks")
            } for row in all_point_rows]
            pdf = controlled_record_pdf_bytes(
                "NPD PROCESS FLOW",
                {"Part Number": part.get("part_number"), "FSI Part Number": part.get("fsi_part_number"), "Part Description": part.get("part_name"), "Revision": flow.get("revision"), "Effective Date": flow.get("effective_date"), "Status": flow.get("status"), "Remarks": flow.get("remarks")},
                {"Operational Sequence": step_rows, "Process Checkpoints / Bullet Points": point_rows},
                record_number=f"{part.get('part_number')}-REV-{flow.get('revision')}",
            )
            c_pdf, c_del = st.columns([2, 1], gap="small")
            with c_pdf:
                st.download_button("Download Process Flow PDF", pdf, file_name=f"Process_Flow_{part.get('part_number')}_Rev_{flow.get('revision')}.pdf", mime="application/pdf", width="stretch")
            with c_del:
                if password_delete_panel(
                    repo=repo, table="npd_process_flows", rows=[flow],
                    labeler=lambda row: f"{part.get('part_number')} · Rev {row.get('revision')}",
                    key=f"npd_flow_delete_{flow.get('id')}", can_delete=perms["can_archive"],
                    title="Delete Process Flow",
                    help_text="Deletes the selected Process Flow revision and its linked process/checkpoint rows. Current QCMS password is required.",
                ):
                    st.rerun()


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


def _render_pending_order_matrix(repo: Repository, orders: list[dict], part_by_id: dict[str, dict], customer_by_id: dict[str, dict]) -> None:
    """Show every pending Part / Order as one horizontal card row with process cards beside it."""
    pending = [row for row in orders if str(row.get("status") or "OPEN").upper() not in {"COMPLETED", "CANCELLED"}]
    section_bar("ORDER PROCESS STATUS · ALL PENDING PARTS", "Each pending Part is one horizontal card row. Process cards are color coded for real-time status and target date.")
    if not pending:
        st.success("No pending NPD orders are open.")
        return
    today = date.today()
    pdf_rows: list[dict[str, Any]] = []
    legend = {
        "completed": ("Completed", "✓"), "completed_late": ("Completed Late", "✓"),
        "in_progress": ("In Process", "●"), "pending": ("Pending", "○"),
        "overdue": ("Overdue", "!"), "hold": ("On Hold", "Ⅱ"), "not_planned": ("Not Planned", "○"),
    }
    for order in pending:
        steps = repo.select("npd_order_steps", eq={"npd_order_id": str(order.get("id"))}, order_by="operation_no", limit=500)
        part = part_by_id.get(str(order.get("part_id"))) or {}
        customer = customer_by_id.get(str(order.get("customer_id"))) or {}
        done = sum(str(step.get("status") or "").upper() == "COMPLETED" for step in steps)
        delivery = _parse_date(order.get("delivery_date")).strftime("%d-%m-%Y")
        summary_html = (
            f'<div class="npd-order-summary-card">'
            f'<div class="npd-order-part">{safe(part.get("part_number"))}</div>'
            f'<div class="npd-order-name">{safe(part.get("part_name"))}</div>'
            f'<div class="npd-order-meta"><b>Order:</b> {safe(order.get("order_number"))}</div>'
            f'<div class="npd-order-meta"><b>Customer:</b> {safe(customer.get("party_code"))} · {safe(customer.get("party_name"))}</div>'
            f'<div class="npd-order-meta"><b>Delivery:</b> {delivery}</div>'
            f'<div class="npd-order-meta"><b>User:</b> {safe(order.get("Created By User"))}</div>'
            f'<div class="npd-order-meta"><b>Entry Status:</b> {safe(order.get("Data Entry Status"))}</div>'
            f'<div class="npd-order-progress">Progress {done}/{len(steps)}</div>'
            f'</div>'
        )
        cards: list[str] = []
        pdf_steps: list[dict[str, Any]] = []
        for step in steps:
            state, detail = _step_realtime_state(step, today)
            label, symbol = legend.get(state, (state.replace("_", " ").title(), "○"))
            target = _parse_date(step.get("target_date")).strftime("%d-%m-%Y") if step.get("target_date") else "Not set"
            process_name = str(step.get("process_name") or "Process")
            cards.append(
                f'<div class="npd-row-process-card npd-{state}">'
                f'<div class="npd-op">OP {safe(step.get("operation_no"))}</div>'
                f'<div class="npd-process-name">{safe(process_name)}</div>'
                f'<div class="npd-process-status">{symbol} {safe(label)}</div>'
                f'<div class="npd-process-date">Target {target}</div>'
                f'<div class="npd-process-date">{safe(detail)}</div>'
                f'</div>'
            )
            pdf_steps.append({"operation_no": step.get("operation_no"), "process_name": process_name, "state": state, "status": label, "target_date": target, "detail": detail})
        st.markdown(
            f'<div class="npd-order-status-row">{summary_html}<div class="npd-row-process-strip">{"".join(cards) or "<div class=\"npd-empty-process\">No process sequence</div>"}</div></div>',
            unsafe_allow_html=True,
        )
        pdf_rows.append({
            "part_number": part.get("part_number"), "part_name": part.get("part_name"),
            "order_number": order.get("order_number"), "customer": f"{customer.get('party_code') or ''} · {customer.get('party_name') or ''}".strip(" ·"),
            "delivery_date": delivery, "progress": f"{done}/{len(steps)}", "steps": pdf_steps,
        })
    st.download_button(
        "Print / Download Pending Order Process Status PDF",
        data=npd_pending_status_pdf_bytes(pdf_rows),
        file_name="QCMS_NPD_Pending_Order_Process_Status.pdf", mime="application/pdf",
        icon=":material/picture_as_pdf:", width="stretch", key="npd_pending_process_cards_pdf",
    )
    st.caption("Legend: ✓ Completed · ● In Process · ○ Pending · ! Overdue · Ⅱ On Hold")

def render_npd_status() -> None:
    page_header("NPD Status")
    repo = Repository(); perms = current_permissions("NPD_APQP")
    parts = _part_rows(repo); customers = _customer_rows(repo); employees = _employee_rows(repo)
    if not parts or not customers:
        st.info("Active Part Master and Customer Master records are required for NPD order tracking.")
        return
    part_by_id = {str(row["id"]): row for row in parts}; customer_by_id = {str(row["id"]): row for row in customers}
    part_labels = {str(row["id"]): part_label(row) for row in parts}; customer_labels = {str(row["id"]): party_label(row) for row in customers}
    employee_labels = _employee_labels(employees)
    employee_options, employee_option_to_id = _employee_option_maps(employees)
    employee_id_to_option = {employee_id: label for label, employee_id in employee_option_to_id.items() if employee_id}
    orders = annotate_transaction_rows(repo, repo.select("npd_orders", order_by="delivery_date", limit=3000))

    tab1, tab2 = st.tabs(["Order Entry", "Order Status"])
    with tab1:
        with stage_section("A", "NPD ORDER / PART STATUS ENTRY", key="npd_status_entry_a"):
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
                    # Case-insensitive duplicate order-number protection on both create and edit.
                    for row in orders:
                        if existing and str(row.get("id")) == str(existing.get("id")):
                            continue
                        if str(row.get("order_number") or "").strip().casefold() == order_number.strip().casefold():
                            raise ValueError("Duplicate NPD Order Number is not allowed.")
                    flow = _flow_for_part(repo, part_id)
                    flow_steps = _flow_steps(repo, str(flow["id"]) if flow else None)
                    if not flow_steps and not existing:
                        raise ValueError("Create and save the Part Process Flow before creating this NPD Order.")
                    payload = {"order_number": order_number.strip(), "part_id": part_id, "customer_id": customer_id, "order_qty": qty, "order_date": order_date.isoformat(), "start_date": start_date.isoformat(), "delivery_date": delivery_date.isoformat(), "remarks": remarks.strip() or None}
                    saved = repo.update("npd_orders", str(existing["id"]), payload) if existing else repo.insert("npd_orders", {**payload, "status": "OPEN"})
                    if not existing:
                        suggested = _suggested_target_dates(start_date, delivery_date, len(flow_steps))
                        for index, step in enumerate(flow_steps):
                            order_step = repo.insert("npd_order_steps", {
                                "npd_order_id": str(saved["id"]), "flow_step_id": str(step["id"]), "operation_no": int(step.get("operation_no") or 0),
                                "process_id": step.get("process_id"), "process_name": str(step.get("process_name_snapshot") or ""),
                                "target_date": suggested[index].isoformat(), "status": "PENDING", "completed_date": None,
                                "responsible_employee_id": step.get("responsible_employee_id"), "responsible": step.get("responsible"), "remarks": None,
                            })
                            flow_points = repo.select("npd_process_flow_points", eq={"flow_step_id": str(step["id"]), "status": "ACTIVE"}, order_by="sequence_no", limit=300)
                            for point in flow_points:
                                repo.insert("npd_order_step_points", {
                                    "npd_order_step_id": str(order_step["id"]), "flow_point_id": str(point["id"]),
                                    "sequence_no": int(point.get("sequence_no") or 10), "point_text": point.get("point_text"),
                                    "responsible_employee_id": point.get("responsible_employee_id"), "responsible_snapshot": point.get("responsible_snapshot"),
                                    "target_date": suggested[index].isoformat(), "status": "PENDING", "completed_date": None,
                                    "remarks": point.get("remarks"),
                                })
                    save_success_popup("NPD Order saved and process/checkpoint status cards created from the Part Process Flow.", queue_for_rerun=True)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

            if existing:
                if password_delete_panel(
                    repo=repo, table="npd_orders", rows=[existing],
                    labeler=lambda row: f"{row.get('order_number')} · {(part_by_id.get(str(row.get('part_id'))) or {}).get('part_number')}",
                    key=f"npd_order_entry_delete_{existing.get('id')}", can_delete=perms["can_archive"],
                    title="Delete Selected NPD Order",
                    help_text="Permanently deletes the selected order entry and its process/checkpoint history after verifying your current QCMS password.",
                ):
                    st.rerun()

        if orders:
            with stage_section("B", "ORDER REGISTER", key="npd_status_entry_b"):
                frame = pd.DataFrame([{
                    "Order": row.get("order_number"), "Part": (part_by_id.get(str(row.get("part_id"))) or {}).get("part_number"),
                    "Customer": (customer_by_id.get(str(row.get("customer_id"))) or {}).get("party_name"), "Order Qty": row.get("order_qty"),
                    "Start Date": row.get("start_date"), "Delivery Date": row.get("delivery_date"), "User": row.get("Created By User"), "Data Entry Status": row.get("Data Entry Status"), "Status": str(row.get("status") or "").replace("_", " ").title(),
                } for row in orders])
                portal_table(frame, hide_index=True, width="stretch", height=330)

    with tab2:
        if not orders:
            st.info("Create an NPD Order to open the real-time Process Status view.")
            return
        with stage_section("A", "PENDING ORDER PROCESS STATUS", key="npd_status_detail_a"):
            _render_pending_order_matrix(repo, orders, part_by_id, customer_by_id)
        with stage_section("B", "SELECTED ORDER DETAIL", "Open one order below to review the current process status and target dates.", key="npd_status_detail_b"):
            order_labels = {str(row["id"]): _order_label(row, part_by_id, customer_by_id) for row in orders}
            order_id = st.selectbox("Open Order Status", list(order_labels), format_func=lambda value: order_labels[value], key="npd_status_order")
            order = next(row for row in orders if str(row["id"]) == order_id)
            steps = repo.select("npd_order_steps", eq={"npd_order_id": order_id}, order_by="operation_no", limit=500)
            points_by_step: dict[str, list[dict]] = {}
            for step in steps:
                points_by_step[str(step["id"])] = repo.select("npd_order_step_points", eq={"npd_order_step_id": str(step["id"])}, order_by="sequence_no", limit=500)
            point_progress = {
                step_id: (
                    sum(str(point.get("status") or "") in {"COMPLETED", "NOT_APPLICABLE"} for point in points),
                    len(points),
                )
                for step_id, points in points_by_step.items()
            }
            today = date.today()
            overdue_count = sum(_step_realtime_state(row, today)[0] == "overdue" for row in steps)
            completed_count = sum(str(row.get("status") or "") == "COMPLETED" for row in steps)
            in_progress_count = sum(str(row.get("status") or "") == "IN_PROGRESS" for row in steps)
            all_points = [point for points in points_by_step.values() for point in points]
            completed_points = sum(str(point.get("status") or "") in {"COMPLETED", "NOT_APPLICABLE"} for point in all_points)
            due = _parse_date(order.get("delivery_date"))
            days_to_delivery = (due - today).days
            overall = "COMPLETED" if steps and completed_count == len(steps) else ("DELAYED" if overdue_count else "ON TRACK")
            kpi_grid([
                {"label": "Order Qty", "value": f"{float(order.get('order_qty') or 0):,.0f}", "foot": "pcs", "color": "#1469A8", "background": "#EFF6FF"},
                {"label": "Processes Complete", "value": f"{completed_count}/{len(steps)}", "foot": "Operational sequence", "color": "#15803D", "background": "#F0FDF4"},
                {"label": "Checkpoints Complete", "value": f"{completed_points}/{len(all_points)}", "foot": "Bullet-point closure", "color": "#0F766E", "background": "#F0FDFA"},
                {"label": "Overdue Processes", "value": overdue_count, "foot": "Target date exceeded", "color": "#B91C1C", "background": "#FEF2F2"},
                {"label": "Days to Delivery", "value": days_to_delivery, "foot": due.strftime("%d-%m-%Y"), "color": "#D97706" if days_to_delivery < 7 else "#0F766E", "background": "#FFF7ED" if days_to_delivery < 7 else "#F0FDFA"},
                {"label": "Real-time Status", "value": overall, "foot": "Date-driven evaluation", "color": "#B91C1C" if overall == "DELAYED" else "#15803D", "background": "#FEF2F2" if overall == "DELAYED" else "#F0FDF4"},
            ])
        with stage_section("C", "ORDER PROCESS STATUS", "Click any process card to update its Status, Completed Date and Remarks. Overdue cards pulse red until action is taken.", key="npd_status_detail_c"):
            _render_process_cards(steps, point_progress, clickable=True, key_prefix=f"npd_order_{order_id}")
            selected_step_id = str(st.session_state.get("npd_selected_step_id") or "")
            selected_step = next((row for row in steps if str(row.get("id")) == selected_step_id), None)
            if selected_step:
                st.markdown(f"**Update OP {selected_step.get('operation_no')} · {selected_step.get('process_name')}**")
                e1,e2 = st.columns(2, gap="small")
                current_status = str(selected_step.get("status") or "PENDING")
                card_status = e1.selectbox("Status", STEP_STATUSES, index=STEP_STATUSES.index(current_status) if current_status in STEP_STATUSES else 0, key=f"npd_card_status_{selected_step_id}")
                existing_completed = _parse_date(selected_step.get("completed_date")) if selected_step.get("completed_date") else date.today()
                card_completed = e2.date_input("Completed Date", value=existing_completed, format="DD-MM-YYYY", disabled=card_status != "COMPLETED", key=f"npd_card_completed_{selected_step_id}")
                card_remarks = st.text_area("Remarks shown on the card", value=str(selected_step.get("remarks") or ""), height=68, key=f"npd_card_remarks_{selected_step_id}")
                if st.button("Update Selected NPD Card", type="primary", width="stretch", disabled=not perms["can_edit"], key=f"npd_card_save_{selected_step_id}"):
                    try:
                        repo.update("npd_order_steps", selected_step_id, {"status":card_status, "completed_date":card_completed.isoformat() if card_status=="COMPLETED" else None, "remarks":card_remarks.strip() or None})
                        refreshed=repo.select("npd_order_steps",eq={"npd_order_id":order_id},order_by="operation_no",limit=500);_sync_order_overall_status(repo,order,refreshed)
                        save_success_popup("NPD process card updated.",queue_for_rerun=True);st.rerun()
                    except Exception as exc: st.error(str(exc))

        with stage_section("D", "UPDATE PROCESS TARGETS & STATUS", key="npd_status_detail_d"):
            legacy_values = [str(row.get("responsible") or "") for row in steps if not row.get("responsible_employee_id")]
            process_employee_options, process_option_to_id = _employee_option_maps(employees, legacy_values)
            process_id_to_option = {employee_id: label for label, employee_id in process_option_to_id.items() if employee_id}
            process_frame = pd.DataFrame([{
                "ID": str(row["id"]), "Operation No.": int(row.get("operation_no") or 0), "Process": row.get("process_name"),
                "Target Date": _parse_date(row.get("target_date")) if row.get("target_date") else None,
                "Status": str(row.get("status") or "PENDING"), "Completed Date": _parse_date(row.get("completed_date")) if row.get("completed_date") else None,
                "Responsible Employee": process_id_to_option.get(str(row.get("responsible_employee_id") or "")) or (f"Legacy · {row.get('responsible')}" if row.get("responsible") else "— Not assigned —"),
                "Remarks": row.get("remarks") or "",
            } for row in steps])
            edited = st.data_editor(
                process_frame, hide_index=True, width="stretch", height=max(260, min(560, 92 + 38 * max(1, len(process_frame)))), key=f"npd_order_step_editor_{order_id}", disabled=not perms["can_edit"],
                column_config={
                    "ID": None, "Operation No.": st.column_config.NumberColumn(disabled=True, width="small"), "Process": st.column_config.TextColumn(disabled=True, width="large"),
                    "Target Date": st.column_config.DateColumn(format="DD-MM-YYYY", required=True), "Status": st.column_config.SelectboxColumn(options=STEP_STATUSES, required=True),
                    "Completed Date": st.column_config.DateColumn(format="DD-MM-YYYY"), "Responsible Employee": st.column_config.SelectboxColumn(options=process_employee_options, width="large"), "Remarks": st.column_config.TextColumn(width="large"),
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
                        resp_option = str(row.get("Responsible Employee") or "— Not assigned —")
                        resp_id = process_option_to_id.get(resp_option)
                        resp_snapshot = employee_labels.get(str(resp_id)) if resp_id else (resp_option.removeprefix("Legacy · ").strip() if resp_option.startswith("Legacy · ") else None)
                        repo.update("npd_order_steps", str(row["ID"]), {
                            "target_date": target.isoformat() if isinstance(target, date) else str(target)[:10], "status": status,
                            "completed_date": completed.isoformat() if isinstance(completed, date) else (str(completed)[:10] if completed else None),
                            "responsible_employee_id": resp_id, "responsible": resp_snapshot,
                            "remarks": str(row.get("Remarks") or "").strip() or None,
                        })
                    refreshed = repo.select("npd_order_steps", eq={"npd_order_id": order_id}, order_by="operation_no", limit=500)
                    _sync_order_overall_status(repo, order, refreshed)
                    save_success_popup("Process target dates and real-time status updated.", queue_for_rerun=True)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

        with stage_section("E", "PROCESS CHECKPOINTS / BULLET POINTS", "Update each point as Pending, In Progress, Completed, On Hold or Not Applicable, with responsible employee and remarks.", key="npd_status_detail_e"):
            for step in steps:
                step_id = str(step["id"])
                points = points_by_step.get(step_id, [])
                done, total = point_progress.get(step_id, (0, 0))
                with st.expander(f"OP {step.get('operation_no')} - {step.get('process_name')} · Checkpoints {done}/{total}", expanded=False):
                    if not points:
                        st.caption("No checkpoints were defined in the Process Flow for this operation.")
                        continue
                    legacy_point_values = [str(point.get("responsible_snapshot") or "") for point in points if not point.get("responsible_employee_id")]
                    point_employee_options, point_option_to_id = _employee_option_maps(employees, legacy_point_values)
                    point_id_to_option = {employee_id: label for label, employee_id in point_option_to_id.items() if employee_id}
                    point_frame = pd.DataFrame([{
                        "ID": str(point["id"]), "Seq": int(point.get("sequence_no") or 10), "Checkpoint / Bullet Point": point.get("point_text"),
                        "Target Date": _parse_date(point.get("target_date")) if point.get("target_date") else None,
                        "Status": point.get("status") or "PENDING", "Completed Date": _parse_date(point.get("completed_date")) if point.get("completed_date") else None,
                        "Responsible Employee": point_id_to_option.get(str(point.get("responsible_employee_id") or "")) or (f"Legacy · {point.get('responsible_snapshot')}" if point.get("responsible_snapshot") else "— Not assigned —"),
                        "Remarks": point.get("remarks") or "",
                    } for point in points])
                    point_edit = st.data_editor(
                        point_frame, hide_index=True, width="stretch", height=max(180, min(430, 110 + 38 * len(point_frame))), key=f"npd_order_points_{step_id}", disabled=not perms["can_edit"],
                        column_config={
                            "ID": None, "Seq": st.column_config.NumberColumn(disabled=True, width="small"), "Checkpoint / Bullet Point": st.column_config.TextColumn(disabled=True, width="large"),
                            "Target Date": st.column_config.DateColumn(format="DD-MM-YYYY"), "Status": st.column_config.SelectboxColumn(options=["PENDING","IN_PROGRESS","ON_HOLD","COMPLETED","NOT_APPLICABLE"], required=True),
                            "Completed Date": st.column_config.DateColumn(format="DD-MM-YYYY"), "Responsible Employee": st.column_config.SelectboxColumn(options=point_employee_options, width="large"),
                            "Remarks": st.column_config.TextColumn(width="large"),
                        },
                    )
                    if st.button(f"Update Checkpoints - OP {step.get('operation_no')}", key=f"update_order_points_{step_id}", type="primary", width="stretch", disabled=not perms["can_edit"]):
                        try:
                            for row in point_edit.to_dict("records"):
                                point_status = str(row.get("Status") or "PENDING")
                                completed = row.get("Completed Date")
                                if point_status == "COMPLETED" and (completed is None or pd.isna(completed)):
                                    completed = date.today()
                                if point_status != "COMPLETED":
                                    completed = None
                                target = row.get("Target Date")
                                resp_option = str(row.get("Responsible Employee") or "— Not assigned —")
                                resp_id = point_option_to_id.get(resp_option)
                                resp_snapshot = employee_labels.get(str(resp_id)) if resp_id else (resp_option.removeprefix("Legacy · ").strip() if resp_option.startswith("Legacy · ") else None)
                                repo.update("npd_order_step_points", str(row["ID"]), {
                                    "target_date": target.isoformat() if isinstance(target, date) else (str(target)[:10] if target else None),
                                    "status": point_status,
                                    "completed_date": completed.isoformat() if isinstance(completed, date) else (str(completed)[:10] if completed else None),
                                    "responsible_employee_id": resp_id, "responsible_snapshot": resp_snapshot,
                                    "remarks": str(row.get("Remarks") or "").strip() or None,
                                })
                            save_success_popup(f"Checkpoint status updated for OP {step.get('operation_no')}.", queue_for_rerun=True)
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

            part = part_by_id.get(str(order.get("part_id"))) or {}
            customer = customer_by_id.get(str(order.get("customer_id"))) or {}
            process_pdf_rows = [{
                "Operation No.": row.get("operation_no"), "Process": row.get("process_name"), "Target Date": row.get("target_date"),
                "Status": row.get("status"), "Completed Date": row.get("completed_date"), "Responsible": row.get("responsible"), "Remarks": row.get("remarks")
            } for row in steps]
            point_pdf_rows = []
            for step in steps:
                for point in points_by_step.get(str(step["id"]), []):
                    point_pdf_rows.append({
                        "Operation No.": step.get("operation_no"), "Process": step.get("process_name"), "Seq": point.get("sequence_no"),
                        "Checkpoint": point.get("point_text"), "Target Date": point.get("target_date"), "Status": point.get("status"),
                        "Completed Date": point.get("completed_date"), "Responsible": point.get("responsible_snapshot"), "Remarks": point.get("remarks"),
                    })
            pdf = controlled_record_pdf_bytes(
                "NPD ORDER STATUS",
                {"Order Number": order.get("order_number"), "Part Number": part.get("part_number"), "FSI Part Number": part.get("fsi_part_number"), "Part Description": part.get("part_name"), "Customer": customer.get("party_name"), "Order Qty": order.get("order_qty"), "Order Date": order.get("order_date"), "Start Date": order.get("start_date"), "Delivery Date": order.get("delivery_date"), "Overall Status": overall, "Order Remarks": order.get("remarks")},
                {"Process Status": process_pdf_rows, "Process Checkpoints / Bullet Points": point_pdf_rows},
                record_number=str(order.get("order_number") or ""),
            )
            c_pdf, c_del = st.columns([2, 1], gap="small")
            with c_pdf:
                st.download_button("Download NPD Order Status PDF", pdf, file_name=f"NPD_Order_Status_{order.get('order_number')}.pdf", mime="application/pdf", width="stretch")
            with c_del:
                if password_delete_panel(
                    repo=repo, table="npd_orders", rows=[order],
                    labeler=lambda row: f"{row.get('order_number')} · {part.get('part_number')}",
                    key=f"npd_order_delete_{order.get('id')}", can_delete=perms["can_archive"],
                    title="Delete NPD Order",
                    help_text="Deletes this NPD Order and its process/checkpoint status history. Current QCMS password is required.",
                ):
                    st.rerun()


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
    parts = _part_rows(repo); customers = _customer_rows(repo); employees = _employee_rows(repo)
    if not parts or not customers:
        st.info("Active Part and Customer records are required for APQP project tracking.")
        return
    part_labels = {str(row["id"]): part_label(row) for row in parts}; customer_labels = {str(row["id"]): party_label(row) for row in customers}
    projects = repo.select("ppap_projects", order_by="target_submission_date", limit=2000)
    project_options = [""] + [str(row["id"]) for row in projects]
    project_labels = {str(row["id"]): f"{row.get('project_code')} · {part_labels.get(str(row.get('part_id')), '')}" for row in projects}
    selected_id = st.selectbox("Open / Edit APQP Project", project_options, format_func=lambda value: "New APQP Project" if not value else project_labels[value])
    existing = next((row for row in projects if str(row["id"]) == selected_id), None)
    default_part_id = str((existing or {}).get("part_id") or parts[0]["id"])
    linked_customer = str((next((row for row in parts if str(row["id"]) == default_part_id), {}) or {}).get("customer_id") or "")
    default_customer_id = str((existing or {}).get("customer_id") or linked_customer or customers[0]["id"])
    employee_labels = _employee_labels(employees)
    coordinator_options, coordinator_option_to_id = _employee_option_maps(employees, [str((existing or {}).get("coordinator") or "")])
    coordinator_id_to_option = {employee_id: label for label, employee_id in coordinator_option_to_id.items() if employee_id}
    existing_coordinator_option = coordinator_id_to_option.get(str((existing or {}).get("coordinator_employee_id") or "")) or (f"Legacy · {(existing or {}).get('coordinator')}" if (existing or {}).get("coordinator") else "— Not assigned —")

    with stage_section("A", 'APQP PROJECT HEADER', key="npd_apqp_render_apqp_a"):
        with st.form("apqp_project_form"):
            c = st.columns(4, gap="small")
            project_code = c[0].text_input("Project / NPD Number", value=str((existing or {}).get("project_code") or ""))
            part_id = c[1].selectbox("Part Number", list(part_labels), index=list(part_labels).index(default_part_id) if default_part_id in part_labels else 0, format_func=lambda value: part_labels[value])
            customer_id = c[2].selectbox("Customer", list(customer_labels), index=list(customer_labels).index(default_customer_id) if default_customer_id in customer_labels else 0, format_func=lambda value: customer_labels[value])
            submission_level = c[3].selectbox("PPAP Submission Level", ["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"], index=max(0, ["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"].index(str((existing or {}).get("submission_level") or "Level 3"))) if str((existing or {}).get("submission_level") or "Level 3") in ["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"] else 2)
            c = st.columns(4, gap="small")
            target_date = c[0].date_input("Target PPAP Submission", value=_parse_date((existing or {}).get("target_submission_date"), date.today() + timedelta(days=60)), format="DD-MM-YYYY")
            coordinator_option = c[1].selectbox("APQP Coordinator", coordinator_options, index=coordinator_options.index(existing_coordinator_option) if existing_coordinator_option in coordinator_options else 0)
            reason = c[2].text_input("Reason / Program", value=str((existing or {}).get("reason") or "New Product Development"))
            status = c[3].selectbox("Project Status", ["IN_PROGRESS", "ON_HOLD", "COMPLETED", "CANCELLED"], index=["IN_PROGRESS", "ON_HOLD", "COMPLETED", "CANCELLED"].index(str((existing or {}).get("status") or "IN_PROGRESS")) if str((existing or {}).get("status") or "IN_PROGRESS") in ["IN_PROGRESS", "ON_HOLD", "COMPLETED", "CANCELLED"] else 0)
            remarks = st.text_area("APQP Remarks", value=str((existing or {}).get("remarks") or ""), height=70)
            save = st.form_submit_button("Save APQP Project", type="primary", width="stretch", disabled=not (perms["can_create"] or perms["can_edit"]))
        if save:
            try:
                if not project_code.strip():
                    raise ValueError("Project / NPD Number is required.")
                coordinator_employee_id = coordinator_option_to_id.get(coordinator_option)
                coordinator_snapshot = employee_labels.get(str(coordinator_employee_id)) if coordinator_employee_id else (coordinator_option.removeprefix("Legacy · ").strip() if coordinator_option.startswith("Legacy · ") else None)
                payload = {"project_code": project_code.strip(), "part_id": part_id, "customer_id": customer_id, "submission_level": submission_level, "reason": reason.strip() or None, "target_submission_date": target_date.isoformat(), "coordinator_employee_id": coordinator_employee_id, "coordinator": coordinator_snapshot, "status": status, "remarks": remarks.strip() or None}
                saved = repo.update("ppap_projects", str(existing["id"]), payload) if existing else repo.insert("ppap_projects", {**payload, "completion_percent": 0})
                save_success_popup("APQP Project saved successfully.", queue_for_rerun=True)
                st.session_state["apqp_selected_project"] = str(saved["id"])
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

        project_id = str((existing or {}).get("id") or st.session_state.get("apqp_selected_project") or "")
        if not project_id:
            return
        project = repo.get("ppap_projects", project_id) or existing
        tasks = repo.select("ppap_documents", eq={"ppap_project_id": project_id}, order_by="sequence_no", limit=500)
    with stage_section("B", 'APQP PHASE STATUS', key="npd_apqp_render_apqp_b"):
        if not tasks and st.button("Load Standard APQP Gates", width="stretch", disabled=not perms["can_create"]):
            for sequence_no, phase, activity in _default_apqp_tasks():
                repo.insert("ppap_documents", {"ppap_project_id": project_id, "sequence_no": sequence_no, "apqp_phase": phase, "document_type": activity, "status": "NOT_STARTED"})
            save_success_popup("Standard APQP gates loaded successfully.", queue_for_rerun=True)
            st.rerun()
        if tasks:
            completed = sum(str(row.get("status") or "") in {"COMPLETED", "APPROVED", "NOT_APPLICABLE"} for row in tasks)
            completion = round(completed * 100 / len(tasks)) if tasks else 0
            due = _parse_date((project or {}).get("target_submission_date"))
            overdue = 0
            for row in tasks:
                if not isinstance(row, dict) or str(row.get("status") or "") in {"COMPLETED", "APPROVED", "NOT_APPLICABLE"}:
                    continue
                task_due = _optional_date(row.get("due_date"))
                if task_due is not None and task_due < date.today():
                    overdue += 1
            kpi_grid([
                {"label": "APQP Completion", "value": f"{completion}%", "foot": f"{completed}/{len(tasks)} gates closed", "color": "#15803D", "background": "#F0FDF4"},
                {"label": "Open Gates", "value": len(tasks)-completed, "foot": "Pending / in progress", "color": "#D97706", "background": "#FFF7ED"},
                {"label": "Overdue Gates", "value": overdue, "foot": "Target dates exceeded", "color": "#B91C1C", "background": "#FEF2F2"},
                {"label": "PPAP Target", "value": due.strftime("%d-%m-%Y"), "foot": f"{(due-date.today()).days} day(s)", "color": "#1469A8", "background": "#EFF6FF"},
            ])
            task_frame = pd.DataFrame([{
                "ID": str(row["id"]), "Seq": int(row.get("sequence_no") or 0), "APQP Phase": row.get("apqp_phase") or "", "Activity / Deliverable": row.get("document_type") or "",
                "Evidence / Document No.": row.get("document_number") or "", "Revision": row.get("revision") or "",
                "Owner": ({str(emp["id"]): label for emp, label in [(emp, employee_labels.get(str(emp["id"]), "")) for emp in employees]}.get(str(row.get("owner_employee_id"))) or (f"Legacy · {row.get('owner')}" if row.get("owner") else "— Not assigned —")),
                "Due Date": _parse_date(row.get("due_date")) if row.get("due_date") else None, "Status": str(row.get("status") or "NOT_STARTED"),
                "Approved Date": _parse_date(row.get("approved_date")) if row.get("approved_date") else None, "Remarks": row.get("remarks") or "",
            } for row in tasks])
            task_owner_options, task_owner_option_to_id = _employee_option_maps(employees, [str(row.get("owner") or "") for row in tasks if not row.get("owner_employee_id")])
            edited = st.data_editor(
                task_frame, num_rows="dynamic", hide_index=True, width="stretch", height=430, key=f"apqp_tasks_{project_id}", disabled=not perms["can_edit"],
                column_config={
                    "ID": None, "Seq": st.column_config.NumberColumn(min_value=0, step=10, required=True), "APQP Phase": st.column_config.TextColumn(required=True, width="large"),
                    "Activity / Deliverable": st.column_config.TextColumn(required=True, width="large"), "Due Date": st.column_config.DateColumn(format="DD-MM-YYYY"),
                    "Owner": st.column_config.SelectboxColumn(options=task_owner_options, width="large"),
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
                            "revision": str(row.get("Revision") or "").strip() or None,
                            "owner_employee_id": task_owner_option_to_id.get(str(row.get("Owner") or "")),
                            "owner": (employee_labels.get(str(task_owner_option_to_id.get(str(row.get("Owner") or "")))) if task_owner_option_to_id.get(str(row.get("Owner") or "")) else (str(row.get("Owner") or "").removeprefix("Legacy · ").strip() or None)),
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
                    save_success_popup("APQP gates updated successfully.", queue_for_rerun=True)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

        project = repo.get("ppap_projects", project_id) or project or {}
        part_row = next((row for row in parts if str(row.get("id")) == str(project.get("part_id"))), {})
        customer_row = next((row for row in customers if str(row.get("id")) == str(project.get("customer_id"))), {})
        pdf_tasks = [{
            "Seq": row.get("sequence_no"), "APQP Phase": row.get("apqp_phase"), "Activity / Deliverable": row.get("document_type"),
            "Evidence / Document No.": row.get("document_number"), "Revision": row.get("revision"), "Owner": row.get("owner"),
            "Due Date": row.get("due_date"), "Status": row.get("status"), "Approved Date": row.get("approved_date"), "Remarks": row.get("remarks"),
        } for row in tasks]
        pdf = controlled_record_pdf_bytes(
            "APQP PROJECT STATUS",
            {"Project / NPD Number": project.get("project_code"), "Part Number": part_row.get("part_number"), "FSI Part Number": part_row.get("fsi_part_number"), "Part Description": part_row.get("part_name"), "Customer": customer_row.get("party_name"), "PPAP Submission Level": project.get("submission_level"), "Target Submission": project.get("target_submission_date"), "Coordinator": project.get("coordinator"), "Completion %": project.get("completion_percent"), "Status": project.get("status"), "Remarks": project.get("remarks")},
            {"APQP Gates / Deliverables": pdf_tasks},
            record_number=str(project.get("project_code") or ""),
        )
        c_pdf, c_del = st.columns([2, 1], gap="small")
        with c_pdf:
            st.download_button("Download APQP Project PDF", pdf, file_name=f"APQP_{project.get('project_code')}.pdf", mime="application/pdf", width="stretch")
        with c_del:
            if password_delete_panel(
                repo=repo, table="ppap_projects", rows=[project],
                labeler=lambda row: f"{row.get('project_code')} · {part_row.get('part_number')}",
                key=f"apqp_project_delete_{project.get('id')}", can_delete=perms["can_archive"],
                title="Delete APQP Project",
                help_text="Deletes the selected APQP project and its linked APQP gates/documents. Current QCMS password is required.",
            ):
                st.rerun()
