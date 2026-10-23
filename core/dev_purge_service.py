"""R36 · STAWN developer purge of TRIAL / TEST data.

Only the STAWN developer login may use this. The database functions
public.qcms_dev_purge_preview / public.qcms_dev_purge_execute enforce that on the server;
this module only wraps them, builds the Excel backup and removes the stored files afterwards.
"""
from __future__ import annotations

import io
import json
from datetime import date, datetime
from typing import Any, Iterable, Mapping, Sequence

from core.repository import Repository

CONFIRM_PHRASE = "DELETE TRIAL DATA"
STORAGE_BUCKET = "quality-documents"

# Friendly module name -> (table, date column, party column, search / reference columns)
MODULES: dict[str, tuple[str, str, str | None, tuple[str, ...]]] = {
    "Customer Orders / Schedules": ("supply_customer_orders", "order_date", "customer_id", ("master_reference_no", "customer_order_no")),
    "Purchase Orders": ("supply_purchase_orders", "order_date", "supplier_id", ("po_number", "quotation_reference", "old_po_reference")),
    "PO Confirmations": ("supply_po_confirmations", "confirmation_date", "supplier_id", ("confirmation_reference",)),
    "RM Procurement Stage": ("supply_rm_purchase_orders", "order_date", "rm_supplier_id", ("supplier_order_no",)),
    "RM Receipts": ("supply_rm_receipts", "receipt_date", None, ("receipt_number", "heat_number", "rmtc_number")),
    "RM to Forging (RM Dispatch)": ("supply_rm_dispatches", "dispatch_date", "forging_supplier_id", ("dispatch_number", "challan_number", "heat_number")),
    "Forging Orders": ("supply_forging_orders", "order_date", "forging_supplier_id", ("supplier_order_no", "heat_number")),
    "Forging Receipts": ("supply_forging_receipts", "receipt_date", "forging_supplier_id", ("receipt_number", "heat_number")),
    "Production / Dispatch Events": ("supply_downstream_events", "event_date", None, ("reference_no", "invoice_no", "asn_no", "event_type")),
    "Opening Stock": ("supply_opening_stock", "created_at", "supplier_id", ("lot_reference", "heat_number")),
    "Material Inward": ("inward_lots", "inward_date", "supplier_id", ("inward_number", "grn_number", "invoice_number", "heat_number")),
    "RMTC": ("rmtc_approvals", "certificate_date", "supplier_id", ("rmtc_number", "certificate_reference", "heat_number")),
    "MetLAB / Bend Reports": ("lab_tests", "test_date", "supplier_id", ("report_number", "test_type", "heat_number")),
    "Dimensional Reports": ("inspection_reports", "inspection_date", "supplier_id", ("report_number", "report_type", "heat_number")),
    "Production Batches": ("production_batches", "created_at", None, ("vendor_batch_number", "heat_number")),
    "OSP Jobs": ("osp_jobs", "dispatch_date", "vendor_id", ("osp_job_number", "receipt_number", "vendor_batch_number")),
    "OSP Receipts": ("osp_receipts", "receipt_date", None, ("receipt_number", "vendor_invoice_number", "tc_number")),
    "OSP Material Outs": ("osp_material_outs", "created_at", None, ("material_out_number",)),
    "Customer Dispatches": ("dispatches", "dispatch_date", "customer_id", ("dispatch_number", "invoice_number")),
    "Quality Complaints": ("quality_complaints", "complaint_date", "party_id", ("complaint_number", "external_reference")),
    "NPD Orders": ("npd_orders", "order_date", "customer_id", ("order_number",)),
    "QC Calculations": ("qc_calculation_records", "calculation_date", None, ("calculation_number", "calculation_type", "heat_number")),
    "Calibration Records": ("quality_asset_calibration_records", "service_date", None, ("report_number", "certificate_number")),
    "Standard Room Inspections": ("standard_room_inspection_records", "inspection_date", None, ("report_number", "program_reference")),
}
ROOT_TABLES = frozenset(spec[0] for spec in MODULES.values())

# Never offered as purge roots (master / system data). Mirrors qcms_private.qcms_dev_purge_protected().
MASTER_TABLES = frozenset({
    "tenants", "profiles", "employees", "parts", "parties", "processes", "material_grades", "material_grade_elements",
    "company_branches", "quality_assets", "standard_room_instruments", "customer_standards", "standards_register",
    "inspection_stages", "inspection_plans", "inspection_plan_characteristics", "test_plans", "calculation_rules",
    "jominy_distances", "master_value_catalog", "number_sequences", "heat_code_sequences",
})

STATUS_FIELDS = ("approval_status", "status", "confirmation_status", "receipt_status", "inspection_status")


def module_table(module: str) -> str:
    return MODULES[module][0]


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _date_of(row: Mapping[str, Any], column: str) -> date | None:
    raw = _text(row.get(column)) or _text(row.get("created_at"))
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None


def record_reference(row: Mapping[str, Any], columns: Sequence[str]) -> str:
    for column in columns:
        value = _text(row.get(column))
        if value:
            return value
    return _text(row.get("id"))[:8]


def record_status(row: Mapping[str, Any]) -> str:
    for column in STATUS_FIELDS:
        value = _text(row.get(column))
        if value:
            return value.replace("_", " ")
    return ""


def _labels(repo: Repository, table: str, ids: Iterable[str], fields: Sequence[str]) -> dict[str, str]:
    wanted = sorted({_text(i) for i in ids if _text(i)})
    if not wanted:
        return {}
    try:
        rows = repo.select(table, in_={"id": wanted}, limit=len(wanted) + 10)
    except Exception:
        rows = []
    out: dict[str, str] = {}
    for row in rows:
        label = next((_text(row.get(f)) for f in fields if _text(row.get(f))), "")
        out[_text(row.get("id"))] = label or _text(row.get("id"))[:8]
    return out


def list_records(
    repo: Repository,
    module: str,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    created_by: str = "",
    text: str = "",
    limit: int = 2000,
) -> list[dict[str, Any]]:
    """Records of one transaction module in the current company, newest first, as display rows."""
    table, date_column, party_column, ref_columns = MODULES[module]
    eq = {"tenant_id": repo.tenant_id} if _text(getattr(repo, "tenant_id", "")) else None
    try:
        rows = repo.select(table, eq=eq, order_by="created_at", desc=True, limit=limit)
    except Exception:
        rows = repo.select(table, limit=limit)
    parts = _labels(repo, "parts", [r.get("part_id") for r in rows], ("fsi_part_number", "part_number", "customer_part_number"))
    parties = _labels(repo, "parties", [r.get(party_column) for r in rows] if party_column else [], ("party_name", "party_code"))
    people = _labels(repo, "profiles", [r.get("created_by") for r in rows], ("full_name", "email"))
    needle = text.strip().lower()
    out: list[dict[str, Any]] = []
    for row in rows:
        when = _date_of(row, date_column)
        if date_from and (when is None or when < date_from):
            continue
        if date_to and (when is None or when > date_to):
            continue
        creator = people.get(_text(row.get("created_by")), "System / Legacy" if not row.get("created_by") else _text(row.get("created_by"))[:8])
        if created_by and creator != created_by:
            continue
        display = {
            "id": _text(row.get("id")),
            "Reference": record_reference(row, ref_columns),
            "Date": when.strftime("%d-%b-%Y") if when else "",
            "Part": parts.get(_text(row.get("part_id")), ""),
            "Party": parties.get(_text(row.get(party_column)), "") if party_column else "",
            "Status": record_status(row),
            "Created By": creator,
        }
        if needle:
            haystack = " ".join([*(str(v) for v in display.values()), *(_text(row.get(c)) for c in ref_columns)]).lower()
            if needle not in haystack:
                continue
        out.append(display)
    return out


def record_label(row: Mapping[str, Any]) -> str:
    bits = [row.get("Reference"), row.get("Date"), row.get("Part"), row.get("Party"), row.get("Status"), row.get("Created By")]
    return " · ".join(_text(b) for b in bits if _text(b)) + f"  [{_text(row.get('id'))[:8]}]"


def _as_dict(data: Any) -> dict[str, Any]:
    if isinstance(data, list):
        data = data[0] if data else {}
    if isinstance(data, str):
        data = json.loads(data or "{}")
    return dict(data or {})


def preview(repo: Repository, table: str, ids: Sequence[str], *, include_rows: bool = False) -> dict[str, Any]:
    """Everything that would be purged (server computed, current company only)."""
    if table not in ROOT_TABLES:
        raise ValueError(f"{table} is not a transaction module that can be purged.")
    clean = [i for i in dict.fromkeys(_text(x) for x in ids) if i]
    if not clean:
        raise ValueError("Select at least one record.")
    return _as_dict(repo.rpc("qcms_dev_purge_preview", {"p_table": table, "p_ids": clean, "p_include_rows": bool(include_rows)}))


def summary_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    from core.record_history import table_label

    rows = []
    for item in result.get("tables") or []:
        rows.append({
            "Table": item.get("table"),
            "Transaction": table_label(str(item.get("table") or "")),
            "Rows": int(item.get("count") or 0),
            "Selected root": "Yes" if item.get("is_root_table") else "",
            "Level": f"{item.get('min_depth')}–{item.get('max_depth')}" if item.get("min_depth") != item.get("max_depth") else str(item.get("max_depth")),
        })
    return rows


def sample_rows(result: Mapping[str, Any], table: str) -> list[dict[str, Any]]:
    for item in result.get("tables") or []:
        if item.get("table") == table:
            return [{"Record": s.get("label"), "Status": s.get("status") or "", "Created": _text(s.get("created_at"))[:16].replace("T", " "),
                     "Level": s.get("depth"), "id": s.get("id")} for s in item.get("samples") or []]
    return []


def _cell(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


def backup_workbook(result: Mapping[str, Any]) -> bytes:
    """Excel backup of every row in the preview: a Summary sheet plus one sheet per table."""
    import pandas as pd

    buffer = io.BytesIO()
    used: set[str] = set()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        head = [
            {"Item": "Root table", "Value": result.get("root_table")},
            {"Item": "Root records", "Value": result.get("root_count")},
            {"Item": "Total rows", "Value": result.get("total_rows")},
            {"Item": "Company (tenant)", "Value": result.get("tenant_id")},
            {"Item": "Backup taken", "Value": datetime.now().strftime("%d-%b-%Y %H:%M:%S")},
            {"Item": "Storage files", "Value": "\n".join(result.get("storage_paths") or [])},
        ]
        pd.DataFrame(head).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(summary_rows(result) or [{"Table": "", "Rows": 0}]).to_excel(writer, sheet_name="Summary", index=False, startrow=len(head) + 2)
        for item in result.get("tables") or []:
            name = str(item.get("table") or "table")[:31]
            base, n = name, 1
            while name in used:
                n += 1
                name = f"{base[:28]}_{n}"
            used.add(name)
            rows = item.get("rows")
            if rows is None:
                rows = item.get("samples") or []
            frame = pd.DataFrame([{k: _cell(v) for k, v in dict(r).items()} for r in rows])
            if frame.empty:
                frame = pd.DataFrame([{"id": ""}])
            frame.to_excel(writer, sheet_name=name, index=False)
    return buffer.getvalue()


def remove_storage_files(paths: Sequence[str]) -> tuple[int, list[str]]:
    """Remove purged files from the quality-documents bucket. Missing files are ignored."""
    clean = [p for p in dict.fromkeys(_text(x) for x in paths or []) if p]
    if not clean:
        return 0, []
    try:
        from core.database import get_session_client

        client = get_session_client()
    except Exception as exc:  # pragma: no cover - no live session
        return 0, [f"storage unavailable: {exc}"]
    if client is None:
        return 0, ["storage unavailable in preview mode"]
    removed, problems = 0, []
    for start in range(0, len(clean), 100):
        chunk = clean[start:start + 100]
        try:
            client.storage.from_(STORAGE_BUCKET).remove(chunk)
            removed += len(chunk)
        except Exception as exc:
            text = str(exc).lower()
            if "not found" in text or "404" in text:
                continue
            problems.append(f"{len(chunk)} file(s): {exc}")
    return removed, problems


def execute(repo: Repository, table: str, ids: Sequence[str], *, confirm: str, reason: str, password: str) -> dict[str, Any]:
    """Re-check password, purge on the server (one transaction), then delete the stored files."""
    from core.auth import verify_current_password

    if _text(confirm) != CONFIRM_PHRASE:
        raise ValueError(f"Type {CONFIRM_PHRASE} exactly to confirm.")
    if len(_text(reason)) < 5:
        raise ValueError("Enter the reason for this purge (at least 5 characters).")
    if table not in ROOT_TABLES:
        raise ValueError(f"{table} is not a transaction module that can be purged.")
    clean = [i for i in dict.fromkeys(_text(x) for x in ids) if i]
    if not clean:
        raise ValueError("Select at least one record.")
    verify_current_password(password)
    result = _as_dict(repo.rpc("qcms_dev_purge_execute", {
        "p_table": table, "p_ids": clean, "p_confirm": CONFIRM_PHRASE, "p_reason": _text(reason),
    }))
    removed, problems = remove_storage_files(result.get("storage_paths") or [])
    result["storage_removed"] = removed
    result["storage_problems"] = problems
    return result


def recent_runs(repo: Repository, limit: int = 50) -> list[dict[str, Any]]:
    try:
        rows = repo.select("qcms_purge_runs", order_by="executed_at", desc=True, limit=limit)
    except Exception:
        return []
    people = _labels(repo, "profiles", [r.get("executed_by") for r in rows], ("full_name", "email"))
    out = []
    for row in rows:
        counts = row.get("deleted_counts") or {}
        if isinstance(counts, str):
            try:
                counts = json.loads(counts)
            except ValueError:
                counts = {}
        out.append({
            "When": _text(row.get("executed_at"))[:16].replace("T", " "),
            "Module": next((m for m, spec in MODULES.items() if spec[0] == row.get("root_table")), row.get("root_table")),
            "Records selected": len(row.get("root_ids") or []),
            "Rows deleted": sum(int(v or 0) for v in dict(counts).values()),
            "Files": len(row.get("storage_paths") or []),
            "Reason": row.get("reason"),
            "By": people.get(_text(row.get("executed_by")), _text(row.get("executed_by"))[:8]),
        })
    return out
