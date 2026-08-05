from __future__ import annotations

from io import BytesIO
from typing import Any, Iterable

import pandas as pd
import streamlit as st

from core.repository import Repository
from core.ui import disposition_cards, page_header, section_bar, subpage_navigation


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_heat(value: Any) -> str:
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def _frame(rows: Iterable[dict], columns: dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame([{label: row.get(source) for label, source in columns.items()} for row in rows])


def _excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            safe_name = name[:31] or "Report"
            frame.to_excel(writer, sheet_name=safe_name, index=False)
            sheet = writer.sheets[safe_name]
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for column in sheet.columns:
                max_length = max((len(str(cell.value or "")) for cell in column), default=8)
                sheet.column_dimensions[column[0].column_letter].width = min(max(max_length + 2, 10), 38)
    return buffer.getvalue()


def render_home() -> None:
    subpage_navigation(
        ("dashboard", "Dashboard", ":material/arrow_back:"),
        ("heat-transaction-report", "Heat Transactions", ":material/monitoring:"),
        ("osp-balance-report", "OSP Heat Balance", ":material/factory:"),
    )
    page_header("Reports", "Live operational reports with Heat and OSP genealogy", "Reports")
    repo = Repository()
    heat_rows = repo.select("v_qsms_heat_global_balance_report", limit=5000)
    osp_rows = repo.select("v_qsms_heat_osp_balance_report", limit=5000)
    disposition_cards([
        {
            "label": "Heat Numbers",
            "value": len(heat_rows),
            "foot": "Global steel control",
            "color": "#1D4ED8",
            "background": "#EFF6FF",
        },
        {
            "label": "Global Heat Balance kg",
            "value": f"{sum(_number(row.get('available_unallocated_steel_quantity_kg')) for row in heat_rows):,.3f}",
            "foot": "Unallocated steel",
            "color": "#15803D",
            "background": "#F0FDF4",
        },
        {
            "label": "OSP Out pcs",
            "value": f"{sum(_number(row.get('osp_out_quantity_pcs')) for row in heat_rows):,.0f}",
            "foot": "Material sent",
            "color": "#C2410C",
            "background": "#FFF7ED",
        },
        {
            "label": "Balance to Send OSP pcs",
            "value": f"{sum(_number(row.get('balance_to_send_osp_pcs')) for row in osp_rows):,.0f}",
            "foot": "Released and not dispatched",
            "color": "#7C3AED",
            "background": "#F5F3FF",
        },
    ])

    c1, c2 = st.columns(2, gap="large")
    with c1:
        with st.container(border=True):
            st.markdown("### Heat Number Global Balance")
            st.caption("Global Heat quantity, RMTC plan, Material Inward and complete transaction history.")
            st.page_link(
                st.session_state["_qsms_pages"]["heat-transaction-report"],
                label="Open Heat Global Balance Report", icon=":material/monitoring:", width="stretch",
            )
    with c2:
        with st.container(border=True):
            st.markdown("### Heat-wise OSP Movement")
            st.caption("OSP Material Out, OSP Inward, material at vendor and balance available to send.")
            st.page_link(
                st.session_state["_qsms_pages"]["osp-balance-report"],
                label="Open OSP Inward / Outward Report", icon=":material/factory:", width="stretch",
            )


def render_heat_transactions() -> None:
    subpage_navigation(
        ("reports-home", "Reports", ":material/arrow_back:"),
        ("osp-balance-report", "OSP Heat Balance", ":material/factory:"),
        ("heat-ledger", "Heat Steel Ledger", ":material/table_view:"),
    )
    page_header(
        "Heat Number Global Balance with Transactions",
        "RMTC plan, Material Inward, OSP movement and validated global Heat balance",
        "Live report",
    )
    repo = Repository()
    summary = repo.select("v_qsms_heat_global_balance_report", order_by="last_activity_at", desc=True, limit=5000)
    transactions = repo.select("v_qsms_heat_transaction_report", order_by="transaction_at", desc=True, limit=20000)
    heats = sorted({str(row.get("heat_number") or "").strip() for row in summary if str(row.get("heat_number") or "").strip()}, key=str.casefold)
    selected = st.selectbox("Heat Number", ["All Heat Numbers"] + heats)
    selected_key = "" if selected == "All Heat Numbers" else _normalize_heat(selected)
    summary_rows = [row for row in summary if not selected_key or str(row.get("normalized_heat_number")) == selected_key]
    transaction_rows = [row for row in transactions if not selected_key or str(row.get("normalized_heat_number")) == selected_key]

    disposition_cards([
        {
            "label": "Global Heat Qty kg",
            "value": f"{sum(_number(row.get('global_steel_quantity_kg')) for row in summary_rows):,.3f}",
            "color": "#1D4ED8", "background": "#EFF6FF",
        },
        {
            "label": "Committed Steel kg",
            "value": f"{sum(_number(row.get('committed_steel_quantity_kg')) for row in summary_rows):,.3f}",
            "color": "#C2410C", "background": "#FFF7ED",
        },
        {
            "label": "Global Heat Balance kg",
            "value": f"{sum(_number(row.get('available_unallocated_steel_quantity_kg')) for row in summary_rows):,.3f}",
            "color": "#15803D", "background": "#F0FDF4",
        },
        {
            "label": "Transactions",
            "value": len(transaction_rows),
            "color": "#7C3AED", "background": "#F5F3FF",
        },
    ])

    summary_frame = _frame(summary_rows, {
        "Heat Number": "heat_number",
        "Global Heat Qty kg": "global_steel_quantity_kg",
        "Active Planned Steel kg": "active_planned_steel_quantity_kg",
        "Material Inward Steel kg": "inward_steel_quantity_kg",
        "Remaining Planned Steel kg": "remaining_planned_steel_quantity_kg",
        "Committed Steel kg": "committed_steel_quantity_kg",
        "Global Heat Balance kg": "available_unallocated_steel_quantity_kg",
        "OSP Out pcs": "osp_out_quantity_pcs",
        "OSP Inward pcs": "osp_inward_quantity_pcs",
        "OSP At Vendor pcs": "osp_quantity_at_vendor_pcs",
        "OSP Jobs": "osp_job_count",
        "Last Activity": "last_activity_at",
    })
    transaction_frame = _frame(transaction_rows, {
        "Transaction Date": "transaction_at",
        "Heat Number": "heat_number",
        "Transaction Type": "transaction_type",
        "Transaction Number": "transaction_number",
        "Reference": "reference_number",
        "Part Number": "part_number",
        "Part Description": "part_name",
        "Supplier / OSP Vendor": "party_name",
        "OSP Process": "process_name",
        "Movement": "movement_direction",
        "Steel Qty kg": "steel_quantity_kg",
        "Production Qty pcs": "production_quantity_pcs",
        "Status": "transaction_status",
    })
    section_bar("HEAT GLOBAL BALANCE")
    st.dataframe(summary_frame, hide_index=True, width="stretch", height=min(400, 100 + max(len(summary_frame), 1) * 36))
    section_bar("HEAT TRANSACTION HISTORY", "Chronological genealogy from RMTC planning through Material Inward and OSP movement.")
    st.dataframe(transaction_frame, hide_index=True, width="stretch", height=560)
    suffix = selected_key or "ALL_HEATS"
    st.download_button(
        "Download Heat Balance and Transactions",
        data=_excel_bytes({"Heat Balance": summary_frame, "Transactions": transaction_frame}),
        file_name=f"QSMS_Heat_Global_Balance_{suffix}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:", width="stretch",
    )


def render_osp_balance() -> None:
    subpage_navigation(
        ("reports-home", "Reports", ":material/arrow_back:"),
        ("heat-transaction-report", "Heat Transactions", ":material/monitoring:"),
        ("osp-records", "OSP Records", ":material/table_view:"),
    )
    page_header(
        "Heat-wise OSP Inward, Outward and Balance",
        "Released material, OSP dispatch, OSP receipt, quantity at vendor and balance available to send",
        "Live report",
    )
    repo = Repository()
    balances = repo.select("v_qsms_heat_osp_balance_report", order_by="inward_date", desc=True, limit=10000)
    jobs = repo.select("v_qsms_osp_register", order_by="created_at", desc=True, limit=10000)
    heats = sorted({str(row.get("heat_number") or "").strip() for row in balances if str(row.get("heat_number") or "").strip()}, key=str.casefold)
    parts = sorted({str(row.get("part_number") or "").strip() for row in balances if str(row.get("part_number") or "").strip()}, key=str.casefold)
    c1, c2 = st.columns(2, gap="small")
    selected_heat = c1.selectbox("Heat Number", ["All Heat Numbers"] + heats)
    selected_part = c2.selectbox("Part Number", ["All Part Numbers"] + parts)
    heat_key = "" if selected_heat == "All Heat Numbers" else _normalize_heat(selected_heat)
    filtered_balances = [
        row for row in balances
        if (not heat_key or str(row.get("normalized_heat_number")) == heat_key)
        and (selected_part == "All Part Numbers" or str(row.get("part_number")) == selected_part)
    ]
    inward_ids = {str(row.get("inward_lot_id")) for row in filtered_balances}
    filtered_jobs = [row for row in jobs if str(row.get("source_inward_lot_id")) in inward_ids]

    disposition_cards([
        {
            "label": "Released Material pcs",
            "value": f"{sum(_number(row.get('released_quantity_pcs')) for row in filtered_balances):,.0f}",
            "color": "#1D4ED8", "background": "#EFF6FF",
        },
        {
            "label": "OSP Out pcs",
            "value": f"{sum(_number(row.get('osp_out_quantity_pcs')) for row in filtered_balances):,.0f}",
            "color": "#C2410C", "background": "#FFF7ED",
        },
        {
            "label": "OSP Inward pcs",
            "value": f"{sum(_number(row.get('osp_inward_quantity_pcs')) for row in filtered_balances):,.0f}",
            "color": "#15803D", "background": "#F0FDF4",
        },
        {
            "label": "Balance to Send OSP pcs",
            "value": f"{sum(_number(row.get('balance_to_send_osp_pcs')) for row in filtered_balances):,.0f}",
            "color": "#7C3AED", "background": "#F5F3FF",
        },
        {
            "label": "At OSP Vendor pcs",
            "value": f"{sum(_number(row.get('quantity_at_osp_vendor_pcs')) for row in filtered_balances):,.0f}",
            "color": "#B45309", "background": "#FFFBEB",
        },
    ])

    balance_frame = _frame(filtered_balances, {
        "Heat Number": "heat_number",
        "Part Number": "part_number",
        "Part Description": "part_name",
        "Source Inward": "inward_number",
        "Inward Date": "inward_date",
        "Released Qty pcs": "released_quantity_pcs",
        "OSP Out Qty pcs": "osp_out_quantity_pcs",
        "OSP Inward Qty pcs": "osp_inward_quantity_pcs",
        "Balance to Send OSP pcs": "balance_to_send_osp_pcs",
        "Qty at OSP Vendor pcs": "quantity_at_osp_vendor_pcs",
        "OSP Processes": "osp_processes",
        "OSP Vendors": "osp_vendors",
        "OSP Jobs": "osp_job_count",
        "Last OSP Activity": "last_osp_activity_at",
    })
    job_frame = _frame(filtered_jobs, {
        "OSP Job": "osp_job_number",
        "Heat Number": "heat_number",
        "Part Number": "part_number",
        "OSP Vendor": "vendor_name",
        "OSP Process": "process_name",
        "Material Out Date": "dispatch_date",
        "Out Challan": "dispatch_challan",
        "Out Qty pcs": "quantity_dispatched",
        "Vendor Batch": "vendor_batch_number",
        "OSP Inward Number": "receipt_number",
        "OSP Inward Date": "receipt_date",
        "Vendor Invoice": "vendor_invoice_number",
        "TC Number": "tc_number",
        "Inward Qty pcs": "quantity_received",
        "Balance at Vendor pcs": "quantity_outstanding",
        "Sample Gate": "sample_gate_status",
        "Final Quality Decision": "receipt_quality_disposition",
        "Status": "status",
    })
    section_bar("HEAT / PART OSP BALANCE")
    st.dataframe(balance_frame, hide_index=True, width="stretch", height=min(480, 100 + max(len(balance_frame), 1) * 36))
    section_bar("OSP TRANSACTION DETAILS")
    st.dataframe(job_frame, hide_index=True, width="stretch", height=540)
    suffix = (heat_key or "ALL_HEATS") + ("_" + selected_part.replace("/", "-") if selected_part != "All Part Numbers" else "")
    st.download_button(
        "Download OSP Inward / Outward and Balance",
        data=_excel_bytes({"OSP Balance": balance_frame, "OSP Transactions": job_frame}),
        file_name=f"QSMS_OSP_Heat_Balance_{suffix}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:", width="stretch",
    )
