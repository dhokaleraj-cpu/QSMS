"""R37 · Universal print layout: one call gives the print-layout PDF of ANY QCMS record.

Public contract (website pages, Global Search, Records Centre, KPI drill-downs, mobile back-end):

* ``record_pdf(table, record_id, repo=None, *, customer_safe=False) -> (file_name, pdf_bytes)``
    - dedicated controlled layouts where they exist (RMTC, Material Inward, Dimensional / OSP inspection,
      MetLAB / Bend Test, Purchase Order / PO confirmation, Quality Complaint, QC Calculation, Calibration /
      Validation, Standard Room, OSP vendor challan, Indirect PO / GRN);
    - every other business table (transactions and masters) gets the Purchase-Order "Design B" controlled
      record print (``core.record_print``): company block, document title, number / date boxes, all fields with
      friendly labels and resolved look-ups (part, party, grade, process, employee, branch), child tables,
      attachments list, status stamp, signature block and "Page x of y".
    - ``customer_safe=True`` removes customer name / code / PO / order no / customer part no / delivery date (R36b);
      use it for anything that can reach a supplier / vendor.  Supplier documents (OSP challan, indirect PO / GRN)
      are always customer-safe.
* ``register_pdf(title, frame, filters_text="")`` - landscape register / report print with a totals row.
* ``WEB_ROUTES`` / ``record_route(table)`` - the website register route of each table (deep links for mobile / KPI).
* ``record_label(table)`` - record-type label (same wording as ``public.qcms_search_table_map``).
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, Mapping

import pandas as pd

# table -> (record type label, website register route) - mirrors public.qcms_search_table_map + R37 tables.
TABLE_MAP: dict[str, tuple[str, str]] = {
    "parts": ("Part Master", "part-records"),
    "part_raw_material_details": ("Part Raw Material", "part-records"),
    "part_raw_material_technical_data": ("Part RM Technical Data", "part-records"),
    "part_supplier_links": ("Part Supplier", "part-records"),
    "part_supplier_price_history": ("Part Supplier Price", "part-records"),
    "part_process_specifications": ("Part Process Specification", "part-records"),
    "part_process_parameter_specifications": ("Part Process Parameter", "part-records"),
    "part_metallurgical_requirements": ("Part Metallurgical Requirement", "part-records"),
    "part_heat_treatment_details": ("Part Heat Treatment", "part-records"),
    "part_rmtc_requirements": ("Part RMTC Requirement", "part-records"),
    "part_process_routes": ("Part Process", "part-records"),  # R38
    "part_ecns": ("Engineering / Process Change Note (ECN / PCN)", "ecn-register"),  # R38
    "part_ecn_actions": ("ECN Implementation Action", "ecn-register"),  # R38
    "parties": ("Customer / Supplier / Vendor", "reference-records"),
    "company_branches": ("Company Branch", "company-branch-records"),
    "material_grades": ("Material Grade", "grade-records"),
    "processes": ("Process Master", "process-records"),
    "inspection_stages": ("Inspection Stage", "reference-records"),
    "employees": ("Employee", "employee-records"),
    "inspection_plans": ("Inspection Layout", "inspection-layout-records"),
    "inspection_plan_characteristics": ("Layout Characteristic", "inspection-layout-records"),
    "rmtc_approvals": ("RMTC", "rmtc-records"),
    "rmtc_part_approvals": ("RMTC Part Approval", "rmtc-records"),
    "inward_lots": ("Material Inward", "inward-records"),
    "production_batches": ("Production / FSI Batch", "osp-records"),
    "osp_jobs": ("OSP Job / Material Out", "osp-records"),
    "osp_receipts": ("OSP Inward Receipt", "osp-records"),
    "osp_material_outs": ("OSP Material Out", "osp-records"),
    "osp_challans": ("OSP Delivery Challan", "osp-material-out"),
    "inspection_reports": ("Dimensional Report", "dimensional-records"),
    "inspection_results": ("Dimensional Result", "dimensional-records"),
    "lab_tests": ("MetLAB / Bend Test Report", "metlab-records"),
    "quality_complaints": ("Quality Complaint", "complaint-records"),
    "quality_complaint_actions": ("Complaint Action", "complaint-records"),
    "quality_complaint_followups": ("Complaint Follow-up", "complaint-records"),
    "supply_customer_orders": ("Customer Order / Schedule", "supply-customer-orders"),
    "supply_purchase_orders": ("Purchase Order", "supply-po-order-list"),
    "supply_purchase_order_items": ("Purchase Order Item", "supply-po-order-list"),
    "supply_rm_purchase_orders": ("RM Procurement Order", "supply-rm-procurement"),
    "supply_rm_receipts": ("RM Receipt", "supply-rm-receipt"),
    "supply_rm_dispatches": ("RM to Forging", "supply-rm-dispatch"),
    "supply_forging_orders": ("Forging Order", "supply-forging"),
    "supply_forging_receipts": ("Forging Receipt", "supply-forging"),
    "supply_downstream_events": ("Machining / FG / Dispatch", "supply-downstream"),
    "supply_opening_stock": ("Opening Stock", "supply-opening-stock"),
    "supply_po_confirmations": ("PO Confirmation", "supply-po-order-list"),
    "npd_orders": ("NPD Order", "npd-status"),
    "npd_order_steps": ("NPD Step", "npd-status"),
    "npd_process_flows": ("Process Flow", "npd-process-flow"),
    "npd_process_flow_steps": ("Process Flow Step", "npd-process-flow"),
    "ppap_projects": ("APQP / PPAP Project", "apqp"),
    "ppap_documents": ("PPAP Document", "apqp"),
    "quality_assets": ("Gauge / Fixture / Instrument", "calibration-validation"),
    "quality_asset_calibration_records": ("Calibration / Validation Record", "calibration-validation"),
    "standard_room_inspection_records": ("Standard Room Inspection", "standard-room-inspection"),
    "customer_standards": ("Customer Standard", "standards-records"),
    "qc_calculation_records": ("QC Calculation", "qc-calculation-records"),
    "indirect_purchase_requisitions": ("Indirect Purchase Requisition", "indirect-requisition"),
    "indirect_purchase_orders": ("Indirect Purchase Order", "indirect-po-list"),
    "indirect_grns": ("Indirect GRN", "indirect-inward"),
    "indirect_items": ("Indirect Item", "indirect-items"),
    "document_attachments": ("Attachment / Photo", "records-center"),
    "qcms_delete_requests": ("Deletion Request", "records-center"),
}
WEB_ROUTES: dict[str, str] = {table: route for table, (_label, route) in TABLE_MAP.items()}

# Documents that by nature go to a supplier / vendor: always printed customer-safe.
SUPPLIER_DOCUMENT_TABLES: frozenset[str] = frozenset({"osp_challans", "indirect_purchase_orders", "indirect_grns"})


def record_label(table: str) -> str:
    hit = TABLE_MAP.get(str(table or ""))
    if hit:
        return hit[0]
    return str(table or "Record").replace("supply_", "").replace("_", " ").title()


def record_route(table: str, pages: Mapping[str, Any] | None = None) -> str | None:
    """Website route of the table's register / entry screen (``None`` when the login has no such page)."""
    route = WEB_ROUTES.get(str(table or ""))
    if route and pages is not None and route not in pages:
        return None
    return route


# ----------------------------------------------------------------------------- partner layouts (agents A / B)
def _optional(module: str, name: str) -> Callable[..., Any] | None:
    """Function from an optional module (OSP challan / indirect purchase print) - None until it exists."""
    try:
        mod = __import__(module, fromlist=[name])
    except ImportError:
        return None
    fn = getattr(mod, name, None)
    return fn if callable(fn) else None


def _call_by_id(fn: Callable[..., Any], record_id: str, repo: Any) -> Any:
    """Call ``fn(record_id)`` passing ``repo`` when the function accepts it.

    A function that cannot take the caller's repository would read through its own default Repository; that is
    only done when the caller's repository *is* a real Repository (never with a test / preview double)."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        params = {}
    if "repo" in params:
        return fn(record_id, repo=repo)
    from core.repository import Repository
    if repo is not None and not isinstance(repo, Repository):
        return None
    return fn(record_id)


def _as_named_pdf(result: Any, fallback_name: str) -> tuple[str, bytes] | None:
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], (bytes, bytearray)):
        name, data = str(result[0] or fallback_name), bytes(result[1])
    elif isinstance(result, (bytes, bytearray)):
        name, data = fallback_name, bytes(result)
    else:
        return None
    if not data.startswith(b"%PDF"):
        return None
    return (name if name.lower().endswith(".pdf") else f"{name}.pdf"), data


def _number(repo: Any, table: str, record_id: str, *keys: str) -> str:
    try:
        rows = repo.select(table, eq={"id": record_id}, limit=1) or []
    except Exception:
        rows = []
    row = dict(rows[0]) if rows else {}
    for key in keys:
        if str(row.get(key) or "").strip():
            return str(row.get(key)).strip()
    return ""


def partner_pdf(table: str, record_id: str, repo: Any) -> tuple[str, bytes] | None:
    """Supplier-facing dedicated prints owned by the OSP / Indirect Purchase modules (always customer-safe).

    Returns ``None`` when the module's print is not available (older build) or fails - the caller then prints the
    generic controlled record instead."""
    table = str(table or "")
    record_id = str(record_id or "")
    if not record_id:
        return None
    try:
        if table == "osp_challans":
            from core.osp_challan import OSPChallanService, osp_challan_pdf_bytes
            payload = OSPChallanService(repo).print_payload_for(record_id)
            return _as_named_pdf(osp_challan_pdf_bytes(payload), f"{payload.get('challan_number') or 'OSP_Challan'}.pdf")
        if table == "osp_jobs":
            fn = _optional("core.osp_challan_pdf", "osp_challan_pdf_bytes")
            if fn is None:
                return None
            number = _number(repo, table, record_id, "osp_job_number", "dispatch_challan") or "OSP_Challan"
            return _as_named_pdf(_call_by_id(fn, record_id, repo), f"{number}_Challan.pdf")
        if table == "indirect_purchase_orders":
            fn = _optional("core.indirect_po_pdf", "indirect_po_pdf_bytes")
            if fn is None:
                return None
            number = _number(repo, table, record_id, "po_number") or "Indirect_PO"
            return _as_named_pdf(_call_by_id(fn, record_id, repo), f"{number}.pdf")
        if table == "indirect_grns":
            fn = _optional("core.indirect_po_pdf", "indirect_grn_pdf_bytes")
            if fn is None:
                return None
            number = _number(repo, table, record_id, "grn_number") or "Indirect_GRN"
            return _as_named_pdf(_call_by_id(fn, record_id, repo), f"{number}.pdf")
    except Exception:
        return None
    return None


# ----------------------------------------------------------------------------- public API
def record_pdf(table: str, record_id: str, repo: Any = None, *, customer_safe: bool = False,
               record: Mapping[str, Any] | None = None) -> tuple[str, bytes]:
    """``(file_name, pdf_bytes)`` - the print-layout PDF of one record of any business table."""
    from core.record_print import print_pdf
    if repo is None:
        from core.repository import Repository
        repo = Repository()
    table = str(table or "")
    if table in SUPPLIER_DOCUMENT_TABLES:
        customer_safe = True
    return print_pdf(table, str(record_id or (record or {}).get("id") or ""), repo, external=bool(customer_safe),
                     record=None if customer_safe else record)


def register_pdf(title: str, frame: pd.DataFrame | Mapping[str, pd.DataFrame], filters_text: str = "", *,
                 totals: bool = True) -> bytes:
    """Landscape print of any list / report table in the controlled look, with a totals row."""
    from core.record_print import register_pdf as _register_pdf
    return _register_pdf(title, frame, filters_text, totals=totals)


__all__ = ["TABLE_MAP", "WEB_ROUTES", "SUPPLIER_DOCUMENT_TABLES", "record_label", "record_route", "partner_pdf",
           "record_pdf", "register_pdf"]
