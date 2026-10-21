"""R22 · Turn raw Supabase / PostgREST errors into plain messages.

R35 · Field-level translation: not-null, unique, foreign key, check constraint, row-level security,
invalid number / date / uuid input and statement timeouts are explained in plain words with the
field label, so a user always knows which field or step to correct.
"""
from __future__ import annotations

import ast
import re
from typing import Any, Mapping

# Friendly labels for common column names (fallback: "snake_case" -> "Snake Case").
FIELD_LABELS: dict[str, str] = {
    "part_id": "Part Number", "inward_lot_id": "Material Inward", "layout_plan_id": "Layout",
    "inspection_plan_id": "Layout", "inspection_stage_id": "Inspection Stage", "process_id": "Process",
    "prepared_by_employee_id": "Prepared By", "validated_by_employee_id": "Validated By",
    "approved_by_employee_id": "Approved By", "supplier_id": "Supplier", "customer_id": "Customer",
    "material_grade_id": "Material Grade", "report_number": "Report Number", "test_date": "Test Date",
    "inspection_date": "Inspection Date", "heat_number": "Heat Number", "heat_code": "Heat Code",
    "sample_reference": "Sample Reference", "osp_job_id": "OSP Batch", "rmtc_approval_id": "RMTC",
    "grn_number": "GRN Number", "object_path": "Attachment file", "employee_id": "Employee",
    "profile_id": "Login User", "plan_number": "Plan Number", "layout_name": "Layout Name",
    "disposition": "Final Decision", "status": "Status", "results": "Results",
}

_TABLE_LABELS: dict[str, str] = {
    "lab_tests": "MetLAB / Bend Test report", "inspection_reports": "Dimensional report",
    "inspection_results": "Dimensional results", "inspection_plans": "Inspection Layout",
    "inspection_plan_characteristics": "Layout characteristics", "document_attachments": "Attachment",
    "inward_lots": "Material Inward", "osp_jobs": "OSP batch", "osp_receipts": "OSP receipt",
    "quality_asset_part_process_links": "Gauge / fixture part-process link", "employees": "Employee Master",
}


def field_label(column: str) -> str:
    column = str(column or "").strip().strip('"')
    if column in FIELD_LABELS:
        return FIELD_LABELS[column]
    clean = re.sub(r"_id$", "", column)
    return clean.replace("_", " ").strip().title() or column


def _table_label(table: str) -> str:
    table = str(table or "").strip().strip('"')
    return _TABLE_LABELS.get(table, table.replace("_", " "))


def _parse(exc: object) -> dict[str, Any]:
    """Return {'message','code','details','hint'} from any PostgREST / Python error."""
    out: dict[str, Any] = {"message": "", "code": "", "details": "", "hint": ""}
    for attr in ("message", "code", "details", "hint"):
        value = getattr(exc, attr, None)
        if isinstance(value, str):
            out[attr] = value
    text = str(exc or "").strip()
    if isinstance(exc, Mapping):
        for attr in out:
            out[attr] = str(exc.get(attr) or out[attr] or "")
    elif text.startswith("{") and "message" in text:
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, dict):
                for attr in out:
                    if parsed.get(attr):
                        out[attr] = str(parsed[attr])
        except Exception:
            match = re.search(r"""['"]message['"]\s*:\s*(['"])(.*?)\1\s*,\s*['"]code['"]""", text, flags=re.S)
            if match:
                out["message"] = match.group(2)
    if out["message"].strip().startswith("{"):
        nested = _parse(out["message"].strip())
        if nested["message"]:
            out.update({k: v for k, v in nested.items() if v})
    if not out["message"]:
        out["message"] = text
    return out


def explain_db_error(exc: object) -> str:
    """Plain, field-level explanation of a database error (falls back to the raw message)."""
    info = _parse(exc)
    msg = str(info["message"]).strip()
    code = str(info["code"]).strip()
    details = str(info["details"] or "").strip()

    m = re.search(r'null value in column "([^"]+)"(?: of relation "([^"]+)")? violates not-null constraint', msg)
    if m or code == "23502":
        column = m.group(1) if m else ""
        table = m.group(2) if m and m.group(2) else ""
        where = f" in {_table_label(table)}" if table else ""
        return f"'{field_label(column)}' is required{where}. Fill it in and save again." if column else "A required field is empty. Fill all mandatory (*) fields and save again."

    m = re.search(r'duplicate key value violates unique constraint "([^"]+)"', msg)
    if m or code == "23505":
        key = re.search(r"Key \(([^)]*)\)=\(([^)]*)\)", details)
        if key:
            names = [c.strip() for c in key.group(1).split(",")]
            values = [v.strip() for v in key.group(2).split(",")]
            pairs = [(n, values[i] if i < len(values) else "") for i, n in enumerate(names) if n != "tenant_id"]
            cols = ", ".join(field_label(n) for n, _ in pairs)
            vals = ", ".join(v for _, v in pairs)
            return f"A record with the same {cols} already exists ({vals}). Open the existing record or change these values."
        constraint = m.group(1) if m else ""
        if "object_path" in constraint:
            return "This attachment was already uploaded for this record. Refresh the page; the existing file is kept."
        if "grn_number" in constraint:
            return "This GRN Number / Part / Heat Number combination is already recorded in Material Inward. Open the existing inward record instead of saving it again."
        return "A record with the same unique values already exists. Open the existing record or change the number / reference."

    m = re.search(r'violates foreign key constraint "([^"]+)"', msg)
    if m or code == "23503":
        key = re.search(r"Key \(([^)]*)\)=\(([^)]*)\)", details)
        if "still referenced" in details or "is still referenced" in msg:
            return "This record is used by other records and cannot be removed. Delete or change the linked records first."
        if key:
            return f"The selected {field_label(key.group(1))} is not valid any more (it may have been deleted). Select it again."
        return "A selected value (master record) is not valid any more. Re-select the master values and save again."

    m = re.search(r'violates check constraint "([^"]+)"', msg)
    if m or code == "23514":
        constraint = (m.group(1) if m else "").replace("_check", "").replace("_chk", "")
        parts = [p for p in constraint.split("_") if p]
        label = " ".join(parts[1:] if len(parts) > 2 else parts).title()
        return f"The value entered for '{label or 'a field'}' is not allowed. Check the allowed range / options and save again."

    m = re.search(r'row-level security policy for table "([^"]+)"', msg)
    if m or code == "42501":
        table = m.group(1) if m else ""
        return (f"You are not allowed to save {_table_label(table) or 'this record'} with this login (company / permission check). "
                "Ask the administrator to give the module permission or check that you are working in your own company.")

    m = re.search(r'invalid input syntax for type (\w+(?: \w+)?): "([^"]*)"', msg)
    if m or code == "22P02":
        kind = m.group(1) if m else "value"
        value = m.group(2) if m else ""
        friendly = {"numeric": "a number", "integer": "a whole number", "uuid": "a selection from the list", "date": "a date", "boolean": "Yes / No"}.get(kind, kind)
        return f"'{value}' is not valid here – enter {friendly}."
    if code in {"22007", "22008"} or "date/time field value out of range" in msg:
        return "A date is not valid. Use the date picker (DD-MM-YYYY)."
    if code == "57014" or "statement timeout" in msg:
        return "The database took too long to answer. Narrow the filter / date range and try again."
    m = re.search(r'column "?([\w.]+)"? (?:of relation "[^"]+" )?does not exist', msg)
    if m or code in {"42703", "PGRST204"}:
        return f"The database is missing field '{m.group(1) if m else ''}'. Run the latest QCMS updater (database step) and try again."
    return msg


def db_message(exc: object) -> str:
    """Return only the human message of a PostgREST error ({'message': ..., 'code': ...})."""
    text = str(exc or "").strip()
    data = getattr(exc, "message", None)
    if isinstance(data, str) and data.strip() and not data.strip().startswith("{") and not getattr(exc, "code", None):
        return explain_db_error({"message": data.strip()})
    if text.startswith("{") and "message" in text or getattr(exc, "code", None):
        return explain_db_error(exc)
    return explain_db_error({"message": text})


def missing_fields_message(missing: list[str]) -> str:
    """'Cannot save yet – complete: A, B, C.' used by entry pages for up-front validation."""
    items = [str(m) for m in missing if str(m).strip()]
    if not items:
        return ""
    return "Cannot save yet. Complete these field(s):\n" + "\n".join(f"- {item}" for item in items)


def report_generation_error(exc: object, report: str = "Report") -> str:
    """R35: tell the user which field / step stopped PDF / Excel report generation."""
    name = type(exc).__name__
    text = str(exc or "").strip()
    if name in {"UnidentifiedImageError", "DecompressionBombError"} or "cannot identify image" in text.lower():
        return f"{report} could not be generated: one of the uploaded photographs is not a readable image. Replace that photograph (PNG / JPG) and try again."
    if name == "KeyError":
        field = field_label(text.strip("'\""))
        return f"{report} could not be generated: the report has no value for '{field}'. Open the report, complete '{field}' and save the draft again."
    if name in {"TypeError", "AttributeError"} and ("NoneType" in text or "None" in text):
        return (f"{report} could not be generated: a required report value is empty ({text}). Check Layout, Prepared By, "
                "Test / Inspection Date, Part and the result rows, save the draft again and retry.")
    if name in {"ZeroDivisionError"}:
        return f"{report} could not be generated: a quantity used in a calculation is zero. Check the quantity / sample size fields."
    return f"{report} could not be generated: {db_message(exc)}"
