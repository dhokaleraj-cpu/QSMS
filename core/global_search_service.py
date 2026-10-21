"""QCMS R35 · Global Search everywhere: modules / screens, fields and database records.

* Modules & screens: every registered website page (route + title) plus business keywords, so
  "bend test" returns the Bend Test entry, register, report and layout master pages.
* Fields: every field / column label of the 79 app modules (mobile catalog.json, the same
  catalogue the Android / iOS apps use) - "heat code" shows which screens hold a Heat Code.
* Records: Supabase RPC ``qcms_global_search`` scans every tenant table's text columns
  (security invoker → row-level security decides what the user may see) and expands part /
  customer / supplier matches to all linked transactions.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "mobile" / "ios_stawn_qcms" / "STAWNQCMS" / "Resources" / "catalog.json"

# Extra business words for website routes (title words are always searchable as well).
ROUTE_KEYWORDS: dict[str, str] = {
    "kpi-dashboards": "kpi dashboard home start charts graphs pending tasks quality supply production npd management my dashboards custom",
    "dashboard": "home quality dashboard overview",
    "global-search": "search find ai assistant ask",
    "bend-test-entry": "bend test bending report new entry angle crack",
    "bend-test-records": "bend test register records list",
    "bend-test-report": "bend test reports pdf print",
    "bend-layout-entry": "bend test layout master new layout",
    "metlab-entry": "metlab metallurgical lab report microstructure hardness chemistry case depth new entry",
    "metlab-records": "metlab metallurgical register records",
    "metlab-report": "metlab report pdf print",
    "dimensional-entry": "dimensional inspection report measurement new entry",
    "dimensional-records": "dimensional inspection register records",
    "dimensional-report": "dimensional report pdf print",
    "inspection-layout-entry": "inspection layout master new layout entry characteristics",
    "inspection-layout-records": "inspection layout register",
    "rmtc-entry": "rmtc mill test certificate raw material test certificate chemistry new entry",
    "rmtc-records": "rmtc register certificates",
    "rmtc-approval": "rmtc approval validation decision",
    "inward-entry": "material inward grn receipt heat new entry",
    "inward-records": "material inward register grn",
    "osp-home": "osp outside processing vendor heat treatment",
    "osp-material-out": "osp material out dispatch challan vendor",
    "osp-sample-receipt": "osp sample receipt",
    "osp-inward": "osp material inward receipt",
    "osp-dimensional": "osp dimensional inspection",
    "osp-metlab": "osp metlab inspection",
    "supply-customer-orders": "customer order schedule six month schedule sales order position",
    "supply-purchase-orders": "purchase order po new po raw material forging",
    "supply-po-order-list": "purchase order list po register",
    "supply-po-approval": "purchase order approval approve po",
    "supply-rm-procurement": "rm raw material procurement steel order",
    "supply-rm-receipt": "rm receipt raw material receipt",
    "supply-rm-dispatch": "rm to forging dispatch raw material issue",
    "supply-forging": "forging order forging receipt",
    "supply-downstream": "machining production finished goods fg customer dispatch invoice asn",
    "supply-traceability": "traceability genealogy heat order dispatch",
    "supply-order-mis": "monthly schedule order mis dispatch report",
    "supply-opening-stock": "opening stock import",
    "complaints-home": "complaint customer complaint supplier complaint 8d capa",
    "complaint-analysis": "complaint analysis rca root cause capa 8d",
    "calibration-validation": "calibration validation gauge fixture instrument due",
    "standard-room-inspection": "standard room inspection cmm instrument",
    "npd-status": "npd new product development status",
    "apqp": "apqp ppap advanced product quality planning",
    "npd-process-flow": "process flow designer npd",
    "qc-tools": "qc calculation tools cp cpk spc msa",
    "records-center": "records centre registers deletion requests history",
    "reports-home": "reports centre report",
    "report-builder": "report builder custom report",
    "part-entry": "part master new part drawing",
    "part-records": "part master register",
    "employee-entry": "employee master new employee",
    "user-access": "users access permissions admin roles",
    "email-send": "email send mail",
    "about": "about stawn developer copyright licence version",
    "my-account": "my account password profile",
    "templates": "templates excel download import",
}

# table -> website route used to open a record result (mirrors public.qcms_search_table_map()).
TABLE_ROUTES: dict[str, str] = {
    "parts": "part-records", "parties": "reference-records", "material_grades": "grade-records", "processes": "process-records",
    "employees": "employee-records", "company_branches": "company-branch-records", "inspection_plans": "inspection-layout-records",
    "rmtc_approvals": "rmtc-records", "inward_lots": "inward-records", "osp_jobs": "osp-records", "osp_receipts": "osp-records",
    "production_batches": "osp-records", "inspection_reports": "dimensional-records", "lab_tests": "metlab-records",
    "quality_complaints": "complaint-records", "supply_customer_orders": "supply-customer-orders",
    "supply_purchase_orders": "supply-po-order-list", "supply_rm_purchase_orders": "supply-rm-procurement",
    "supply_rm_receipts": "supply-rm-receipt", "supply_rm_dispatches": "supply-rm-dispatch", "supply_forging_orders": "supply-forging",
    "supply_forging_receipts": "supply-forging", "supply_downstream_events": "supply-downstream", "npd_orders": "npd-status",
    "ppap_projects": "apqp", "quality_assets": "calibration-validation", "quality_asset_calibration_records": "calibration-validation",
    "standard_room_inspection_records": "standard-room-inspection", "customer_standards": "standards-records",
    "qc_calculation_records": "qc-calculation-records",
}


# app-module key (catalog.json) -> website route, where the table alone is ambiguous
APP_MODULE_ROUTES: dict[str, str] = {
    "bend_tests": "bend-test-records", "metlab_reports": "metlab-records", "dimensional_reports": "dimensional-records",
    "inspection_layouts": "inspection-layout-records", "po_approval": "supply-po-approval", "purchase_orders": "supply-po-order-list",
    "customer_complaints": "customer-complaint-register", "supplier_complaints": "supplier-complaint-register",
    "osp_material_out": "osp-material-out", "osp_receipts": "osp-inward", "osp_register": "osp-records", "rmtc": "rmtc-records",
    "inward": "inward-records", "standard_room": "standard-room-inspection", "global_search": "global-search",
    "kpi_dashboards": "kpi-dashboards", "reports_centre": "reports-home", "records_centre": "records-center",
    "report_builder": "report-builder", "master_lists": "master-lists", "traceability": "supply-traceability", "my_account": "my-account",
    "about": "about", "email_send": "email-send", "email_sent": "email-sent", "email_groups": "email-groups", "user_access": "user-access",
    "system_settings": "system-settings", "email_server": "email-settings", "print_designer": "print-designer", "master_import": "master-import",
    "customers": "reference-records", "suppliers": "reference-records", "steel_mills": "reference-records", "osp_vendors": "reference-records",
    "npd_flows": "npd-process-flow", "npd_orders": "npd-status", "apqp_projects": "apqp", "qc_calculations": "qc-calculation-records",
    "rep_heat_transactions": "heat-transaction-report", "rep_osp_balance": "osp-balance-report", "heat_ledger": "heat-ledger",
    "rep_steel_ledger": "heat-ledger", "customer_orders": "supply-customer-orders", "downstream_events": "supply-downstream",
}


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("_", " ").replace("-", " ")).strip().casefold()


def _tokens(query: str) -> list[str]:
    return [t for t in _norm(query).split(" ") if t]


def _score(query: str, haystack: str, title: str) -> int:
    """0 = no match. Higher is better: exact title, title prefix, all words in title, all words anywhere."""
    q = _norm(query)
    tokens = _tokens(query)
    if not tokens:
        return 0
    t = _norm(title)
    h = _norm(haystack)
    if t == q:
        return 100
    if t.startswith(q):
        return 80
    if q in t:
        return 70
    if all(tok in t for tok in tokens):
        return 60
    if q in h:
        return 45
    if all(tok in h for tok in tokens):
        return 30
    return 0


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"modules": [], "moduleKeys": {}}


def table_module_key(table: str, fallback: str | None = None) -> str | None:
    keys = load_catalog().get("moduleKeys") or {}
    return str(keys.get(table) or fallback or "") or None


def search_modules(query: str, pages: Mapping[str, Any] | None, *, limit: int = 30) -> list[dict]:
    """Website pages / screens that match the query (title + business keywords)."""
    found: list[dict] = []
    for route, page in (pages or {}).items():
        title = str(getattr(page, "title", "") or route)
        keywords = ROUTE_KEYWORDS.get(route, "")
        score = _score(query, f"{title} {route} {keywords}", title)
        if score:
            found.append({"route": route, "title": title, "keywords": keywords, "score": score})
    # app modules from the catalogue (Android / iOS screens have the same names)
    for module in load_catalog().get("modules") or []:
        title = str(module.get("title") or "")
        hay = " ".join([title, str(module.get("description") or ""), str(module.get("section") or ""), str(module.get("table") or "")])
        score = _score(query, hay, title)
        if score:
            route = APP_MODULE_ROUTES.get(str(module.get("key") or ""), "") or TABLE_ROUTES.get(str(module.get("table") or ""), "")
            if route and any(item["route"] == route and _norm(item["title"]) == _norm(title) for item in found):
                continue
            found.append({"route": route, "title": title, "keywords": str(module.get("description") or ""), "score": score - 5,
                          "app_module": str(module.get("key") or "")})
    found.sort(key=lambda item: (-int(item["score"]), str(item["title"])))
    unique: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in found:
        token = (item["route"], _norm(item["title"]))
        if token in seen:
            continue
        seen.add(token)
        unique.append(item)
    return unique[:limit]


def search_fields(query: str, *, limit: int = 40) -> list[dict]:
    """Field / column labels of every app module that match the query."""
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for module in load_catalog().get("modules") or []:
        table = str(module.get("table") or "")
        labels: list[tuple[str, str]] = [(str(c[0]), str(c[1])) for c in module.get("cols") or [] if len(c) >= 2]
        labels += [(str(f.get("key") or ""), str(f.get("label") or "")) for f in module.get("form") or [] if isinstance(f, Mapping)]
        for key, label in labels:
            if not label:
                continue
            score = _score(query, f"{label} {key}", label)
            token = (str(module.get("key")), _norm(label))
            if score >= 30 and token not in seen:
                seen.add(token)
                found.append({"field": key, "label": label, "module": str(module.get("title") or ""), "table": table,
                              "route": APP_MODULE_ROUTES.get(str(module.get("key") or ""), "") or TABLE_ROUTES.get(table, ""), "score": score})
    found.sort(key=lambda item: (-int(item["score"]), item["label"], item["module"]))
    return found[:limit]


def search_records(repo: Any, query: str, *, limit: int = 300, can_view: Callable[[str], bool] | None = None) -> list[dict] | None:
    """Database-wide record search through the qcms_global_search RPC.

    Returns None when the RPC is not installed yet (caller falls back to the classic search)."""
    query = str(query or "").strip()
    if len(query) < 2:
        return []
    try:
        rows = repo.rpc("qcms_global_search", {"p_query": query, "p_limit": int(limit)}) or []
    except Exception as exc:  # RPC missing on an older database → classic search
        if "qcms_global_search" in str(exc) or "PGRST202" in str(exc) or "function" in str(exc).casefold():
            return None
        raise
    results: list[dict] = []
    cache: dict[str, bool] = {}
    for row in rows:
        table = str(row.get("source_table") or "")
        key = table_module_key(table, row.get("module_key"))
        if key and can_view is not None:
            if key not in cache:
                try:
                    cache[key] = bool(can_view(key))
                except Exception:
                    cache[key] = True
            if not cache[key]:
                continue
        results.append({
            "table": table, "id": str(row.get("record_id") or ""), "module_key": key or "",
            "record_type": str(row.get("record_type") or table.replace("_", " ").title()),
            "title": str(row.get("title") or ""), "subtitle": str(row.get("subtitle") or ""),
            "matched_field": str(row.get("matched_field") or "").replace("_", " "),
            "snippet": str(row.get("snippet") or ""), "route": str(row.get("web_route") or TABLE_ROUTES.get(table, "records-center")),
        })
    return results


def group_records(results: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for item in results:
        grouped.setdefault(str(item.get("record_type") or "Records"), []).append(item)
    return dict(sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0])))
