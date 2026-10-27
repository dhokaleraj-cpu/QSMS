"""R37 · Print-layout PDF for every QCMS record, report and search result.

``print_pdf(table, record_id)`` returns ``(file_name, pdf_bytes)``:

* records that already have a controlled print (RMTC, Material Inward, MetLAB / Bend Test, Dimensional / OSP
  inspection, Purchase Order / PO confirmation, Quality Complaint, QC Calculation, Calibration / Validation,
  Standard Room inspection) reuse exactly that layout;
* every other table gets the generic PO-style "Design B" transaction print
  (``core.reporting.transaction_record_pdf_bytes``): company block, document title, number / date boxes,
  all meaningful fields with human labels (foreign keys resolved to part / party / grade / employee / process /
  branch names), child tables as ruled grids, attachments, status / approval stamp and "Page x of y".

``external=True`` produces the customer-safe copy (R36b): customer name / code / PO / order no / customer part no /
delivery date never print on anything that leaves the company.

``print_panel`` is the reusable Streamlit control (Preview print PDF · Download print PDF · Download Excel) and
``register_pdf`` / ``register_print_panel`` print any filtered report / register table.
"""
from __future__ import annotations

import re
from io import BytesIO
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

from core.dependency_map import FOREIGN_KEYS

# ----------------------------------------------------------------------------- catalogue
DOC_TITLES: dict[str, str] = {
    "supply_customer_orders": "CUSTOMER ORDER / SCHEDULE",
    "supply_purchase_orders": "PURCHASE ORDER",
    "supply_purchase_order_items": "PURCHASE ORDER",
    "supply_po_confirmations": "SUPPLIER PO CONFIRMATION",
    "supply_rm_purchase_orders": "RM PROCUREMENT ORDER",
    "supply_rm_receipts": "RM RECEIPT",
    "supply_rm_dispatches": "RM DISPATCH TO FORGING",
    "supply_forging_orders": "FORGING ORDER",
    "supply_forging_receipts": "FORGING RECEIPT",
    "supply_downstream_events": "MACHINING / FG / DISPATCH",
    "supply_opening_stock": "OPENING STOCK",
    "osp_jobs": "OSP MATERIAL OUT",
    "osp_material_outs": "OSP MATERIAL OUT",
    "osp_receipts": "OSP INWARD RECEIPT",
    "production_batches": "PRODUCTION / FSI BATCH",
    "rmtc_approvals": "RMTC",
    "rmtc_part_approvals": "RMTC PART WORKSHEET",
    "inward_lots": "MATERIAL INWARD",
    "inspection_reports": "INSPECTION REPORT",
    "lab_tests": "METLAB TEST REPORT",
    "quality_complaints": "QUALITY COMPLAINT",
    "qc_calculation_records": "QC CALCULATION",
    "npd_orders": "NPD ORDER / STATUS",
    "npd_process_flows": "NPD PROCESS FLOW",
    "ppap_projects": "PPAP / APQP PROJECT",
    "pfd_headers": "PROCESS FLOW DIAGRAM",
    "pfmea_headers": "PFMEA",
    "control_plan_headers": "CONTROL PLAN",
    "spc_studies": "SPC STUDY",
    "msa_studies": "MSA STUDY",
    "capacity_studies": "CAPACITY STUDY",
    "quality_assets": "GAUGE / FIXTURE / QUALITY ASSET",
    "quality_asset_calibration_records": "CALIBRATION / VALIDATION RECORD",
    "standard_room_inspection_records": "STANDARD ROOM INSPECTION",
    "parts": "PART MASTER",
    "parties": "PARTY MASTER",
    "material_grades": "MATERIAL GRADE",
    "processes": "PROCESS MASTER",
    "employees": "EMPLOYEE",
    "company_branches": "COMPANY BRANCH",
    "inspection_plans": "INSPECTION LAYOUT",
    "inspection_stages": "INSPECTION STAGE",
    "customer_standards": "CUSTOMER STANDARD",
    "document_attachments": "DOCUMENT ATTACHMENT",
    "part_raw_material_details": "PART RAW MATERIAL DETAIL",
    "part_raw_material_technical_data": "PART SUPPLIER TECHNICAL DATA",
    "part_supplier_price_history": "PART SUPPLIER PRICE HISTORY",
    "osp_challans": "OSP DELIVERY CHALLAN",
    "indirect_purchase_requisitions": "INDIRECT PURCHASE REQUISITION",
    "indirect_purchase_orders": "INDIRECT PURCHASE ORDER",
    "indirect_grns": "INDIRECT GOODS RECEIPT NOTE",
    "indirect_items": "INDIRECT ITEM MASTER",
    "supply_purchase_order_sources": "PO SOURCE REFERENCE",
}

NUMBER_FIELDS: tuple[str, ...] = (
    "po_number", "challan_number", "grn_number", "pr_number", "item_code", "material_out_number", "osp_job_number", "inward_number", "rmtc_number", "receipt_number", "receipt_no",
    "dispatch_number", "dispatch_no", "report_number", "complaint_number", "calculation_number", "order_number",
    "master_reference_no", "supplier_order_no", "confirmation_number", "document_number", "project_code", "flow_number",
    "batch_code", "reference_no", "certificate_number", "asset_code", "plan_number", "part_number", "party_code",
    "grade_code", "process_code", "employee_code", "branch_code", "stage_code", "standard_number", "file_name", "heat_number",
)
DATE_FIELDS: tuple[str, ...] = (
    "order_date", "po_date", "challan_date", "grn_date", "pr_date", "receipt_date", "dispatch_date", "inward_date", "inspection_date", "test_date",
    "complaint_date", "calculation_date", "service_date", "event_date", "confirmation_date", "schedule_date",
    "start_date", "created_at",
)
STATUS_FIELDS: tuple[str, ...] = ("status", "approval_status", "disposition", "overall_result", "inspection_status", "receipt_status", "result")

# parent table -> [(child table, child column, parent column, section title)]
CHILD_SECTIONS: dict[str, tuple[tuple[str, str, str, str], ...]] = {
    "supply_purchase_orders": (("supply_purchase_order_items", "purchase_order_id", "id", "PO ITEMS"),),
    "supply_customer_orders": (("supply_downstream_events", "customer_order_id", "id", "MACHINING / FG / DISPATCH"),),
    "supply_rm_purchase_orders": (("supply_rm_receipts", "rm_purchase_order_id", "id", "RM RECEIPTS"),),
    "supply_forging_orders": (("supply_forging_receipts", "forging_order_id", "id", "FORGING RECEIPTS"),),
    "quality_complaints": (("quality_complaint_actions", "complaint_id", "id", "COMPLAINT ACTIONS"),
                           ("quality_complaint_followups", "complaint_id", "id", "FOLLOW-UPS")),
    "inspection_reports": (("inspection_results", "inspection_report_id", "id", "INSPECTION RESULTS"),),
    "npd_orders": (("npd_order_steps", "npd_order_id", "id", "NPD STEPS"),),
    "npd_process_flows": (("npd_process_flow_steps", "flow_id", "id", "PROCESS FLOW STEPS"),),
    "rmtc_approvals": (("rmtc_part_approvals", "rmtc_approval_id", "id", "PART WORKSHEETS"),
                       ("rmtc_chemistry_results", "rmtc_approval_id", "id", "CHEMISTRY RESULTS")),
    "material_grades": (("material_grade_elements", "material_grade_id", "id", "CHEMICAL ELEMENTS"),),
    "inspection_plans": (("inspection_plan_characteristics", "inspection_plan_id", "id", "CHARACTERISTICS"),),
    "osp_jobs": (("osp_jobs", "material_out_id", "material_out_id", "MATERIAL OUT LINES"),
                 ("osp_receipts", "osp_job_id", "id", "OSP INWARD RECEIPTS")),
    "osp_material_outs": (("osp_jobs", "material_out_id", "id", "MATERIAL OUT LINES"),),
    "ppap_projects": (("ppap_documents", "ppap_project_id", "id", "PPAP DOCUMENTS"),),
    "pfd_headers": (("pfd_steps", "pfd_header_id", "id", "PFD STEPS"),),
    "pfmea_headers": (("pfmea_items", "pfmea_header_id", "id", "PFMEA ITEMS"),),
    "control_plan_headers": (("control_plan_items", "control_plan_header_id", "id", "CONTROL PLAN ITEMS"),),
    "spc_studies": (("spc_readings", "spc_study_id", "id", "READINGS"),),
    "msa_studies": (("msa_readings", "msa_study_id", "id", "READINGS"),),
    "quality_assets": (("quality_asset_part_process_links", "asset_id", "id", "PART / PROCESS LINKS"),
                       ("quality_asset_calibration_records", "asset_id", "id", "CALIBRATION HISTORY")),
    "parts": (("part_raw_material_details", "part_id", "id", "RAW MATERIAL DETAILS"),
              ("part_raw_material_technical_data", "part_id", "id", "SUPPLIER TECHNICAL DATA"),
              ("part_supplier_links", "part_id", "id", "SUPPLIERS / STEEL MILLS"),
              ("part_supplier_price_history", "part_id", "id", "SUPPLIER PRICE HISTORY"),
              ("part_material_grade_links", "part_id", "id", "MATERIAL GRADES"),
              ("part_process_specifications", "part_id", "id", "PROCESS SPECIFICATIONS"),
              ("part_process_parameter_specifications", "part_id", "id", "PROCESS PARAMETERS"),
              ("part_metallurgical_requirements", "part_id", "id", "METALLURGICAL REQUIREMENTS"),
              ("part_heat_treatment_details", "part_id", "id", "HEAT TREATMENT"),
              ("part_rmtc_requirements", "part_id", "id", "RMTC REQUIREMENTS"),
              ("part_jominy_requirements", "part_id", "id", "JOMINY REQUIREMENTS"),
              ("part_standard_links", "part_id", "id", "LINKED STANDARDS")),
    "parties": (("parts", "customer_id", "id", "PARTS (CUSTOMER)"),
                ("part_supplier_links", "supplier_id", "id", "PARTS SUPPLIED")),
    "employees": (("employees", "reports_to_employee_id", "id", "TEAM MEMBERS"),),
    "processes": (("part_process_specifications", "process_id", "id", "PART PROCESS SPECIFICATIONS"),),
    "supply_rm_dispatches": (("supply_forging_orders", "rm_dispatch_id", "id", "FORGING ORDERS"),),
    "production_batches": (("osp_jobs", "osp_batch_id", "id", "OSP JOBS"),),
    "osp_challans": (("osp_challan_lines", "challan_id", "id", "CHALLAN LINES"),
                     ("osp_challan_returns", "challan_id", "id", "VENDOR RETURNS")),
    "indirect_purchase_requisitions": (("indirect_purchase_requisition_items", "requisition_id", "id", "REQUISITION ITEMS"),),
    "indirect_purchase_orders": (("indirect_purchase_order_items", "purchase_order_id", "id", "PO ITEMS"),
                                 ("indirect_grns", "purchase_order_id", "id", "GOODS RECEIPTS")),
    "indirect_grns": (("indirect_grn_items", "grn_id", "id", "GRN ITEMS"),),
}

# document_attachments.entity_type of each owning table
ATTACHMENT_ENTITY: dict[str, str] = {
    "rmtc_approvals": "RMTC", "inspection_reports": "DIMENSIONAL_REPORT", "lab_tests": "METLAB_REPORT",
    "inward_lots": "MATERIAL_INWARD", "supply_customer_orders": "SUPPLY_CUSTOMER_ORDER",
    "supply_purchase_orders": "SUPPLY_PURCHASE_ORDER", "supply_po_confirmations": "PO_CONFIRMATION",
    "osp_jobs": "OSP_JOB", "quality_complaints": "QUALITY_COMPLAINT", "parts": "PART_MASTER", "npd_orders": "NPD_ORDER",
    "customer_standards": "CUSTOMER_STANDARD", "part_process_specifications": "PART_PROCESS_SPEC",
}

# Tables whose dedicated controlled print is produced by NotificationService._generated_report.
_NOTIFICATION_PRINTS = {"rmtc_approvals", "inspection_reports", "lab_tests", "supply_purchase_orders",
                        "supply_po_confirmations", "quality_complaints", "inward_lots"}
# ... of those, the ones that honour customer_safe (all but the complaint print).
_CUSTOMER_SAFE_PRINTS = _NOTIFICATION_PRINTS - {"quality_complaints"}

_HIDDEN = {"id", "tenant_id", "created_by", "updated_by", "checksum", "smtp_password", "search_vector", "password", "token",
           "object_path", "bucket", "storage_path", "print_options"}
_SKIP_SUFFIX = ("_snapshot", "_payload", "_json", "_hash", "_token", "_path")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_ORDER_KEYS = ("line_no", "item_no", "sequence_no", "step_no", "sort_order", "material_out_line_no", "characteristic_no", "created_at")

# column -> referenced table (generic rules on top of the live FK map)
_FK_MAP: dict[tuple[str, str], str] = {(child, column): parent for child, column, parent in FOREIGN_KEYS}


def _fk_target(table: str, column: str) -> str | None:
    hit = _FK_MAP.get((table, column))
    if hit:
        return hit
    col = column.lower()
    if not col.endswith("_id") or col in {"tenant_id", "id"}:
        return None
    if col.endswith("employee_id"):
        return "employees"
    if col in {"part_id", "source_part_id"}:
        return "parts"
    if col in {"customer_id", "supplier_id", "vendor_id", "party_id", "steel_mill_id", "rm_supplier_id", "forging_supplier_id",
               "osp_vendor_id", "ship_to_party_id"}:
        return "parties"
    if col == "material_grade_id":
        return "material_grades"
    if col in {"process_id", "current_process_id", "from_process_id", "to_process_id"}:
        return "processes"
    if col in {"company_branch_id", "branch_id", "ship_to_branch_id"}:
        return "company_branches"
    if col == "item_id" and table.startswith("indirect_"):
        return "indirect_items"
    if col in {"osp_job_id"}:
        return "osp_jobs"
    if col in {"purchase_order_id"} and table.startswith("indirect_"):
        return "indirect_purchase_orders"
    return None


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _join(*values: Any) -> str:
    return " · ".join(v for v in (_clean(x) for x in values) if v)


def label_for(table: str, row: Mapping[str, Any] | None) -> str:
    """Human label of a referenced record (part number / FSI / description, party name, grade...)."""
    row = dict(row or {})
    if not row:
        return ""
    if table == "parts":
        fsi = _clean(row.get("fsi_part_number"))
        return _join(row.get("part_number"), f"FSI {fsi}" if fsi else "", row.get("part_name"))
    if table == "parties":
        return _join(row.get("party_code"), row.get("party_name"))
    if table == "employees":
        name = " ".join(v for v in (_clean(row.get("first_name")), _clean(row.get("last_name"))) if v)
        return _join(row.get("employee_code"), name)
    if table == "material_grades":
        return _join(row.get("grade_code"), row.get("standard"))
    if table == "processes":
        return _join(row.get("process_code"), row.get("process_name"))
    if table == "company_branches":
        return _join(row.get("branch_code"), row.get("branch_name"))
    if table == "quality_assets":
        return _join(row.get("asset_code"), row.get("asset_name"))
    if table == "inspection_stages":
        return _join(row.get("stage_code"), row.get("stage_name"))
    if table == "indirect_items":
        return _join(row.get("item_code"), row.get("item_name"))
    return reference_of(row)


def reference_of(row: Mapping[str, Any]) -> str:
    for key in NUMBER_FIELDS:
        value = _clean(row.get(key))
        if value:
            return value
    return ""


def human_label(column: str) -> str:
    text = re.sub(r"_id$", "", str(column)).replace("_", " ").strip()
    words = []
    for word in text.split():
        low = word.lower()
        words.append({"po": "PO", "rm": "RM", "osp": "OSP", "fsi": "FSI", "qty": "Qty", "kg": "kg", "pcs": "pcs", "gstin": "GSTIN",
                      "rmtc": "RMTC", "npd": "NPD", "ppap": "PPAP", "asn": "ASN", "grn": "GRN", "tc": "TC", "no": "No.",
                      "fg": "FG", "spc": "SPC", "msa": "MSA", "cqi": "CQI", "hsn": "HSN", "uom": "UOM"}.get(low, word.capitalize()))
    return " ".join(words) or str(column)


def _value_text(value: Any) -> str:
    if isinstance(value, Mapping):
        return "; ".join(f"{human_label(k)}: {_value_text(v)}" for k, v in value.items() if v not in (None, "", [], {}))[:400]
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_value_text(v) for v in value)[:400]
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


class _Resolver:
    """Cached FK label lookups for one print."""

    def __init__(self, repo: Any) -> None:
        self.repo = repo
        self.cache: dict[tuple[str, str], dict] = {}

    def row(self, table: str, record_id: Any) -> dict:
        rid = str(record_id or "").strip()
        if not rid or not table:
            return {}
        key = (table, rid)
        if key not in self.cache:
            try:
                rows = self.repo.select(table, eq={"id": rid}, limit=1) or []
            except Exception:
                rows = []
            self.cache[key] = dict(rows[0]) if rows else {}
        return self.cache[key]

    def label(self, table: str, column: str, value: Any) -> str:
        target = _fk_target(table, column)
        if not target:
            return ""
        return label_for(target, self.row(target, value))

    def children(self, table: str, column: str, value: Any) -> list[dict]:
        if value in (None, ""):
            return []
        try:
            return [dict(r) for r in (self.repo.select(table, eq={column: value}, limit=500) or [])]
        except Exception:
            return []


def _keep(column: str, value: Any) -> bool:
    low = column.lower()
    if low in _HIDDEN or low.endswith(_SKIP_SUFFIX) or value in (None, "", [], {}):
        return False
    return True


def _record_fields(table: str, record: Mapping[str, Any], resolver: _Resolver) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    seen: set[str] = set()
    for column, value in record.items():
        column = str(column)
        if not _keep(column, value):
            continue
        if column.lower().endswith("_id"):
            text = resolver.label(table, column, value)
            if not text:
                continue  # an unresolved uuid is not meaningful on paper
        else:
            text = _value_text(value)
            if _UUID.match(text.strip()):
                continue
            if column in STATUS_FIELDS or column.endswith(("_status", "_disposition", "_type")):
                text = text.replace("_", " ")
        label = human_label(column)
        if label in seen:
            label = f"{label} ({column})"
        seen.add(label)
        fields.append((label, text))
    return fields


def _child_frame(table: str, rows: list[dict], resolver: _Resolver, *, link_column: str, max_columns: int = 12) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    for key in _ORDER_KEYS:
        if any(r.get(key) not in (None, "") for r in rows):
            rows = sorted(rows, key=lambda r: (r.get(key) is None, str(r.get(key) if not isinstance(r.get(key), (int, float)) else f"{float(r.get(key)):015.4f}")))
            break
    columns: list[str] = []
    for row in rows:
        for column, value in row.items():
            column = str(column)
            if column in columns or column == link_column or column.lower() in {"created_at", "updated_at"} or not _keep(column, value):
                continue
            if column.lower().endswith("_id") and not _fk_target(table, column):
                continue
            columns.append(column)
    columns = columns[:max_columns]
    out = []
    for row in rows:
        item = {}
        for column in columns:
            value = row.get(column)
            if value in (None, "", [], {}):
                item[human_label(column)] = ""
            elif column.lower().endswith("_id"):
                item[human_label(column)] = resolver.label(table, column, value)
            else:
                text = _value_text(value)
                item[human_label(column)] = "" if _UUID.match(text.strip()) else text
        out.append(item)
    frame = pd.DataFrame(out)
    # drop columns that ended up completely empty
    return frame.loc[:, [c for c in frame.columns if frame[c].astype(str).str.strip().ne("").any()]] if not frame.empty else frame


def _company(record: Mapping[str, Any], resolver: _Resolver) -> dict[str, Any]:
    from core.supply_chain_service import SupplyChainService
    snap = record.get("plant_snapshot")
    if isinstance(snap, Mapping) and (snap.get("name") or snap.get("branch_name")):
        return dict(snap)
    branch_id = record.get("company_branch_id") or record.get("branch_id")
    branch = resolver.row("company_branches", branch_id) if branch_id else {}
    if not branch:
        try:
            rows = resolver.repo.select("company_branches", eq={"status": "ACTIVE"}, limit=1) or []
        except Exception:
            rows = []
        branch = dict(rows[0]) if rows else {}
    if branch:
        return SupplyChainService._branch_snapshot(branch)
    try:
        from core.purchase_order_reporting import PLANT
        return dict(PLANT)
    except Exception:
        return {}


def _approval(record: Mapping[str, Any], resolver: _Resolver, table: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for label, column in (("Prepared by", "prepared_by_employee_id"), ("Submitted by", "submitted_by_employee_id"),
                          ("Validated by", "validated_by_employee_id"), ("Approved by", "approved_by_employee_id"),
                          ("Approved by", "approver_employee_id"), ("Decision by", "decision_by_employee_id")):
        if record.get(column) and label not in out:
            text = resolver.label(table, column, record.get(column))
            if text:
                out[label] = text
    if record.get("approved_by") and "Approved by" not in out and not _UUID.match(str(record.get("approved_by"))):
        out["Approved by"] = str(record.get("approved_by"))
    for label, column in (("Approved on", "approved_at"), ("Decision on", "decision_at")):
        if record.get(column):
            out[label] = str(record.get(column))
    return out


def _attachments(table: str, record_id: str, resolver: _Resolver, external: bool) -> list[dict]:
    entity = ATTACHMENT_ENTITY.get(table)
    if not entity:
        return []
    if external:
        from core.customer_privacy import CUSTOMER_ONLY_ENTITY_TYPES
        if entity in CUSTOMER_ONLY_ENTITY_TYPES:
            return []
    try:
        rows = resolver.repo.select("document_attachments", eq={"entity_type": entity, "entity_id": record_id}, limit=50) or []
    except Exception:
        return []
    return [{"file_name": r.get("file_name"), "document_title": r.get("document_title") or r.get("document_type"), "created_at": r.get("created_at")}
            for r in rows if str(r.get("status") or "ACTIVE").upper() == "ACTIVE"]


def _first(record: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = _clean(record.get(key))
        if value:
            return value
    return ""


def doc_title(table: str, record: Mapping[str, Any] | None = None) -> str:
    record = dict(record or {})
    if table == "inspection_reports":
        kind = str(record.get("report_type") or "").upper()
        return "OSP INSPECTION REPORT" if "OSP" in kind else ("DIMENSIONAL INSPECTION REPORT" if kind else "INSPECTION REPORT")
    if table == "lab_tests":
        method = str((record.get("results") or {}).get("inspection_method") if isinstance(record.get("results"), Mapping) else "").upper()
        text = " ".join(str(record.get(k) or "") for k in ("test_type", "layout_name_snapshot")).upper()
        return "BEND TEST REPORT" if method == "BEND_TEST" or "BEND TEST" in text else "METLAB TEST REPORT"
    if table == "quality_complaints":
        kind = str(record.get("complaint_type") or "").upper()
        return f"{kind} QUALITY COMPLAINT".strip() if kind else "QUALITY COMPLAINT"
    if table == "supply_purchase_orders":
        kind = str(record.get("po_type") or "").upper().replace("_", " ")
        return f"{kind} PURCHASE ORDER".strip() if kind else "PURCHASE ORDER"
    if table == "supply_downstream_events" and record.get("event_type"):
        return str(record.get("event_type")).replace("_", " ").upper()
    return DOC_TITLES.get(table) or table.replace("supply_", "").replace("_", " ").upper()


def fetch_record(repo: Any, table: str, record_id: str) -> dict:
    try:
        rows = repo.select(table, eq={"id": str(record_id)}, limit=1) or []
    except Exception:
        rows = []
    return dict(rows[0]) if rows else {}


def record_print_data(table: str, record_id: str, repo: Any = None, *, external: bool = False, record: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Everything the generic print needs: title, number, date, fields, child sections, attachments, status, approval."""
    if repo is None:
        from core.repository import Repository
        repo = Repository()
    resolver = _Resolver(repo)
    row = dict(record or {}) or fetch_record(repo, table, record_id)
    if external:
        from core.customer_privacy import strip_customer
        row = strip_customer(row)
    sections: dict[str, pd.DataFrame] = {}
    for child_table, child_column, parent_column, title in CHILD_SECTIONS.get(table, ()):
        if external and child_column == "customer_id":
            continue  # R36b: a customer's own parts / orders never print on a customer-safe copy
        rows = resolver.children(child_table, child_column, row.get(parent_column))
        if child_table == table:
            rows = [r for r in rows if str(r.get("id")) != str(row.get("id"))]  # never list the record itself
        if external:
            from core.customer_privacy import strip_customer
            rows = [strip_customer(r) for r in rows]
        frame = _child_frame(child_table, rows, resolver, link_column=child_column)
        if not frame.empty:
            sections[title] = frame
    status = _first(row, STATUS_FIELDS).replace("_", " ")
    return {
        "table": table,
        "record": row,
        "title": doc_title(table, row),
        "number": reference_of(row) or str(record_id or "")[:8].upper(),
        "date": _first(row, DATE_FIELDS),
        "fields": _record_fields(table, row, resolver),
        "sections": sections,
        "attachments": _attachments(table, str(row.get("id") or record_id), resolver, external),
        "status": status,
        "approval": _approval(row, resolver, table),
        "company": _company(row, resolver),
        "external": external,
    }


def generic_pdf(data: Mapping[str, Any]) -> bytes:
    from core.reporting import transaction_record_pdf_bytes
    return transaction_record_pdf_bytes(
        str(data["title"]), tuple(data["fields"]), dict(data["sections"]),
        document_number=str(data["number"]), document_date=data["date"], company=dict(data["company"]),
        status=str(data["status"]), approval=dict(data["approval"]), attachments=tuple(data["attachments"]),
        subtitle="Customer-safe copy · customer details removed" if data.get("external") else "",
    )


def _safe_name(text: Any) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9.-]+", "_", str(text or ""))).strip("_")[:80] or "QCMS_Record"


def _specific_pdf(table: str, record_id: str, repo: Any, external: bool) -> tuple[str, bytes] | None:
    """Dedicated controlled layouts that already exist in QCMS."""
    if table in _NOTIFICATION_PRINTS and (not external or table in _CUSTOMER_SAFE_PRINTS):
        from core.notification_service import NotificationService
        service = NotificationService(repo)
        service.customer_safe = bool(external)
        return service._generated_report(table, record_id)
    if table == "qc_calculation_records":
        from core.reporting import qc_calculation_pdf_bytes
        record = fetch_record(repo, table, record_id)
        if not record:
            return None
        resolver = _Resolver(repo)
        payload = {"record": record, "employee": resolver.row("employees", record.get("performed_by_employee_id")),
                   "part": resolver.row("parts", record.get("part_id")), "grade": resolver.row("material_grades", record.get("material_grade_id"))}
        return f"{record.get('calculation_number') or 'QC_Calculation'}.pdf", qc_calculation_pdf_bytes(payload)
    if table in {"quality_asset_calibration_records", "standard_room_inspection_records"}:
        from app_pages import calibration_validation as cv
        record = fetch_record(repo, table, record_id)
        if not record:
            return None
        resolver = _Resolver(repo)
        if table == "quality_asset_calibration_records":
            link = resolver.row("quality_asset_part_process_links", record.get("link_id"))
            pdf = cv._calibration_pdf(record, asset=resolver.row("quality_assets", record.get("asset_id")),
                                      part=resolver.row("parts", link.get("part_id")) or None,
                                      process=resolver.row("processes", link.get("process_id")) or None,
                                      employee=resolver.row("employees", record.get("performed_by_employee_id")) or None)
            return f"{record.get('report_number') or record.get('certificate_number') or 'Calibration_Record'}.pdf", pdf
        pdf = cv._standard_room_pdf(record, asset=resolver.row("quality_assets", record.get("instrument_asset_id")) or None,
                                    part=resolver.row("parts", record.get("part_id")) or None,
                                    process=resolver.row("processes", record.get("process_id")) or None,
                                    employee=resolver.row("employees", record.get("operator_employee_id")) or None)
        return f"{record.get('report_number') or 'Standard_Room_Inspection'}.pdf", pdf
    return None


def print_pdf(table: str, record_id: str, repo: Any = None, *, external: bool = False, record: Mapping[str, Any] | None = None) -> tuple[str, bytes]:
    """(file_name, pdf_bytes) of the record's print layout - dedicated layout where one exists, else the generic print."""
    if repo is None:
        from core.repository import Repository
        repo = Repository()
    table = str(table or "")
    record_id = str(record_id or (record or {}).get("id") or "")
    # Supplier documents of the OSP / Indirect Purchase modules (vendor challan, indirect PO / GRN): always customer-safe.
    from core.universal_pdf import partner_pdf
    partner = partner_pdf(table, record_id, repo)
    if partner:
        return _safe_name(partner[0][:-4]) + ".pdf", partner[1]
    if table == "supply_purchase_order_items":
        parent = (dict(record or {}) or fetch_record(repo, table, record_id)).get("purchase_order_id")
        if parent:
            table, record_id, record = "supply_purchase_orders", str(parent), None
    try:
        specific = _specific_pdf(table, record_id, repo, external)
    except Exception:
        specific = None
    if specific and specific[1]:
        name = specific[0] if str(specific[0]).lower().endswith(".pdf") else f"{specific[0]}.pdf"
        return _safe_name(name[:-4]) + ("_customer_safe" if external else "") + ".pdf", specific[1]
    data = record_print_data(table, record_id, repo, external=external, record=record)
    name = f"{_safe_name(data['title'].title())}_{_safe_name(data['number'])}"
    return name + ("_customer_safe" if external else "") + ".pdf", generic_pdf(data)


def record_excel_bytes(table: str, record_id: str, repo: Any = None, *, external: bool = False, record: Mapping[str, Any] | None = None) -> tuple[str, bytes]:
    """Excel workbook of the record's fields (sheet 1) and child tables (one sheet each)."""
    from core.reporting import safe_excel_sheet_name
    data = record_print_data(table, record_id, repo, external=external, record=record)
    buffer = BytesIO()
    used: set[str] = set()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        head = pd.DataFrame([{"Field": "Document", "Value": data["title"]}, {"Field": "Number", "Value": data["number"]},
                             {"Field": "Date", "Value": data["date"]}, {"Field": "Status", "Value": data["status"]}]
                            + [{"Field": k, "Value": v} for k, v in data["fields"]])
        name = safe_excel_sheet_name("Record", used_names=used)
        head.to_excel(writer, index=False, sheet_name=name)
        writer.sheets[name].column_dimensions["A"].width = 32
        writer.sheets[name].column_dimensions["B"].width = 70
        for title, frame in data["sections"].items():
            frame.to_excel(writer, index=False, sheet_name=safe_excel_sheet_name(title.title(), used_names=used))
        if data["attachments"]:
            pd.DataFrame(data["attachments"]).to_excel(writer, index=False, sheet_name=safe_excel_sheet_name("Attachments", used_names=used))
    file_name = f"{_safe_name(data['title'].title())}_{_safe_name(data['number'])}" + ("_customer_safe" if external else "") + ".xlsx"
    return file_name, buffer.getvalue()


# ----------------------------------------------------------------------------- registers / reports
def register_pdf(title: str, frame: pd.DataFrame | Mapping[str, pd.DataFrame], filters_text: str = "", *, totals: bool = True) -> bytes:
    """Landscape ruled-grid PDF of any (filtered) report / register table with a totals row."""
    from core.report_filters import totals_row
    from core.reporting import report_pdf_bytes
    sections = {str(title)[:60] or "Register": frame} if isinstance(frame, pd.DataFrame) else dict(frame or {})
    prepared: dict[str, pd.DataFrame] = {}
    for name, part in sections.items():
        part = part.copy() if part is not None else pd.DataFrame()
        for column in part.columns:
            if part[column].map(lambda v: isinstance(v, (dict, list, tuple, set))).any():
                part[column] = part[column].map(_value_text)
        if totals and not part.empty:
            try:
                part = totals_row(part)
            except Exception:
                pass
        prepared[str(name)] = part
    note = filters_text or "All records"
    try:
        return report_pdf_bytes(str(title).upper(), prepared, subtitle=note)
    except Exception as exc:  # very wide registers: trimmed layout instead of a crash
        trimmed = {n: f.head(300).iloc[:, :14].astype(str).apply(lambda c: c.str.slice(0, 40)) for n, f in prepared.items()}
        return report_pdf_bytes(str(title).upper(), trimmed, subtitle=f"{note} · trimmed layout ({type(exc).__name__}); use Excel for every column")


# ----------------------------------------------------------------------------- Streamlit UI
def show_pdf_preview(pdf: bytes, *, key: str, height: int = 760, pages: int = 6) -> None:
    """Inline preview: st.pdf when the streamlit-pdf component is installed, else page images (PyMuPDF)."""
    import importlib.util
    import streamlit as st
    if hasattr(st, "pdf") and importlib.util.find_spec("streamlit_pdf") is not None:
        try:
            st.pdf(pdf, height=height, key=f"{key}_pdfview")
            return
        except Exception:
            pass
    from core.po_print_ui import show_pdf
    show_pdf(pdf, pages=pages)


def print_panel(table: str, record_id: str, *, key: str, repo: Any = None, record: Mapping[str, Any] | None = None,
                allow_customer_safe: bool = True, excel: bool = True, pdf_label: str = "Download print PDF") -> None:
    """Preview print PDF · Download print PDF · Download Excel for one record (inline, safe inside st.dialog)."""
    import streamlit as st
    if not table or not (record_id or (record or {}).get("id")):
        return
    record_id = str(record_id or (record or {}).get("id"))
    if repo is None:
        from core.repository import Repository
        repo = Repository()
    slot = f"_rp_{key}_{table}_{record_id}"
    external = False
    if allow_customer_safe:
        external = bool(st.toggle("Customer-safe copy (for supplier / vendor)", value=False, key=f"{slot}_ext",
                                  help="Removes customer name / code / PO / order no / customer part no / delivery date."))

    def _pdf() -> tuple[str, bytes]:
        # Short per-session cache: reruns (preview toggle, dialog widgets) do not re-query the record each time.
        import time
        cache = st.session_state.setdefault("_rp_pdf_cache", {})
        token = f"{table}:{record_id}:{int(external)}"
        hit = cache.get(token)
        if not hit or time.time() - hit[0] > 60:
            if len(cache) > 12:
                cache.clear()
            hit = cache[token] = (time.time(), print_pdf(table, record_id, repo, external=external, record=record if not external else None))
        return hit[1]

    cols = st.columns(3 if excel else 2, gap="small")
    c1, c2, c3 = cols[0], cols[1], (cols[2] if excel else None)
    preview_key = f"{slot}_show"
    if c1.button("Preview print PDF", key=f"{slot}_preview", icon=":material/preview:", width="stretch"):
        st.session_state[preview_key] = not st.session_state.get(preview_key, False)
    try:
        file_name, pdf = _pdf()
    except Exception as exc:
        from core.db_errors import db_message
        st.error(f"Print PDF could not be prepared: {db_message(exc)}")
        return
    c2.download_button(pdf_label, data=pdf, file_name=file_name, mime="application/pdf",
                       icon=":material/picture_as_pdf:", width="stretch", key=f"{slot}_pdf", on_click="ignore")
    if c3 is not None:
        def _xlsx() -> bytes:
            return record_excel_bytes(table, record_id, repo, external=external, record=record if not external else None)[1]
        c3.download_button("Download Excel", data=_xlsx, file_name=file_name[:-4] + ".xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           icon=":material/table_view:", width="stretch", key=f"{slot}_xlsx", on_click="ignore")
    if st.session_state.get(preview_key):
        show_pdf_preview(pdf, key=slot)


def preview_toggle(pdf: bytes | Callable[[], bytes], *, key: str, label: str = "Preview PDF", container: Any = None) -> None:
    """A "Preview PDF" button that shows / hides the inline preview of an already-built PDF."""
    import streamlit as st
    host = container if container is not None else st
    show_key = f"_rp_prev_{key}_show"
    if host.button(label, key=f"_rp_prev_{key}", icon=":material/preview:", width="stretch"):
        st.session_state[show_key] = not st.session_state.get(show_key, False)
    if st.session_state.get(show_key):
        show_pdf_preview(pdf() if callable(pdf) else pdf, key=f"_rp_prev_{key}")


def register_print_panel(frame: pd.DataFrame | Mapping[str, pd.DataFrame], title: str, *, key: str, filters_text: str = "",
                         pdf_label: str = "Download PDF", preview_label: str = "Preview PDF") -> None:
    """Preview PDF + Download PDF of a (filtered) report / register frame."""
    import streamlit as st
    from datetime import date
    sections = frame if not isinstance(frame, pd.DataFrame) else {title: frame}
    if not sections or all(f is None or f.empty for f in sections.values()):
        return
    c1, c2 = st.columns(2, gap="small")
    show_key = f"_rp_reg_{key}_show"
    if c1.button(preview_label, key=f"_rp_reg_{key}_preview", icon=":material/preview:", width="stretch"):
        st.session_state[show_key] = not st.session_state.get(show_key, False)
    pdf = register_pdf(title, sections, filters_text)
    c2.download_button(pdf_label, data=pdf, file_name=f"{_safe_name(title)}_{date.today().isoformat()}.pdf", mime="application/pdf",
                       icon=":material/picture_as_pdf:", width="stretch", key=f"_rp_reg_{key}_pdf", on_click="ignore")
    if st.session_state.get(show_key):
        show_pdf_preview(pdf, key=f"_rp_reg_{key}")


__all__ = [
    "DOC_TITLES", "CHILD_SECTIONS", "print_pdf", "record_print_data", "record_excel_bytes", "register_pdf",
    "print_panel", "register_print_panel", "show_pdf_preview", "preview_toggle", "label_for", "human_label", "doc_title",
]
