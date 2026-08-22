from __future__ import annotations

import json
import time
import uuid
from copy import deepcopy
from datetime import date, datetime
from typing import Any, Callable, Mapping, Sequence, TypeVar

import httpx
import streamlit as st

from core.config import is_preview_session
from core.database import get_session_client
from core.demo_data import DEMO_TENANT_ID, demo_store


TENANT_SCOPED_TABLES = {
    "parties", "material_grades", "material_grade_elements", "parts", "part_supplier_links",
    "processes", "inspection_stages", "quality_assets", "inspection_plans",
    "inspection_plan_characteristics", "test_plans", "rmtc_approvals", "inward_lots",
    "production_batches", "batch_movements", "osp_jobs", "inspection_reports",
    "inspection_results", "lab_tests", "dispatches", "dispatch_batches",
    "employees", "jominy_distances", "part_raw_material_details", "part_raw_material_technical_data", "part_supplier_price_history", "part_jominy_requirements",
    "part_heat_treatment_details", "part_process_specifications", "part_process_parameter_specifications", "part_metallurgical_requirements", "rmtc_part_approvals", "rmtc_chemistry_results",
    "rmtc_jominy_results", "rmtc_requirement_results", "document_attachments",
    "master_value_catalog", "user_module_permissions", "heat_code_sequences",
    "rmtc_decision_revisions",
    "npd_process_flows", "npd_process_flow_steps", "npd_process_flow_points", "npd_orders", "npd_order_steps", "npd_order_step_points",
    "qc_calculation_records", "customer_standards", "part_standard_links", "quality_complaints", "quality_complaint_followups", "quality_complaint_actions",
    "supply_customer_orders", "supply_purchase_orders", "supply_purchase_order_items", "supply_purchase_order_sources", "supply_rm_purchase_orders", "supply_rm_receipts", "supply_forging_orders", "supply_rm_dispatches", "supply_forging_receipts", "supply_downstream_events",
    "ppap_projects", "ppap_documents", "pfd_headers", "pfd_steps", "pfmea_headers", "pfmea_items",
    "control_plan_headers", "control_plan_items", "spc_plans", "spc_studies", "spc_readings",
    "msa_plans", "msa_studies", "msa_readings", "capacity_studies", "balloon_characteristics",
}

_TRANSIENT_ERRORS = (
    httpx.ReadError,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteError,
    httpx.PoolTimeout,
)
_T = TypeVar("_T")


def _json_ready(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(v) for v in value]
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _demo_database() -> dict[str, list[dict]]:
    if "_qsms_demo_store" not in st.session_state:
        st.session_state["_qsms_demo_store"] = demo_store()
    return st.session_state["_qsms_demo_store"]


def _contains_text(row: Mapping[str, Any], columns: Sequence[str], term: str) -> bool:
    needle = term.casefold()
    for column in columns:
        value = row.get(column)
        if isinstance(value, (dict, list, tuple)):
            value = str(value)
        if needle in str(value or "").casefold():
            return True
    return False


def _cache_key(kind: str, table: str, payload: Mapping[str, Any]) -> str:
    return f"{kind}:{table}:" + json.dumps(_json_ready(payload), sort_keys=True, default=str)


class Repository:
    """RLS-aware Supabase repository with retry and session cache for transient reads."""

    def __init__(self) -> None:
        self.preview = is_preview_session()
        self.client = None if self.preview else get_session_client()
        profile = st.session_state.get("profile") or {}
        self.tenant_id = DEMO_TENANT_ID if self.preview else str(profile.get("tenant_id") or "")

    @staticmethod
    def _retry(action: Callable[[], _T], *, attempts: int = 4, operation: str = "database request") -> _T:
        last: Exception | None = None
        for index in range(attempts):
            try:
                return action()
            except _TRANSIENT_ERRORS as exc:
                last = exc
                if index + 1 < attempts:
                    time.sleep(0.25 * (2 ** index))
        raise RuntimeError(
            f"Supabase connection was temporarily unavailable during {operation}. "
            "Please retry; no transaction was deleted or reset."
        ) from last

    @staticmethod
    def _read_cache() -> dict[str, Any]:
        return st.session_state.setdefault("_qsms_repository_read_cache", {})

    def select(
        self,
        table: str,
        *,
        eq: Mapping[str, Any] | None = None,
        in_: Mapping[str, Sequence[Any]] | None = None,
        contains: Mapping[str, Sequence[Any]] | None = None,
        search_columns: Sequence[str] | None = None,
        search_term: str = "",
        order_by: str | None = None,
        desc: bool = False,
        limit: int | None = 500,
    ) -> list[dict]:
        eq = eq or {}
        in_ = in_ or {}
        contains = contains or {}
        search_columns = tuple(search_columns or ())
        search_term = str(search_term or "").strip()

        if self.preview:
            rows = [deepcopy(row) for row in _demo_database().get(table, [])]
            for key, expected in eq.items():
                if expected is None:
                    rows = [row for row in rows if row.get(key) is None]
                else:
                    rows = [row for row in rows if str(row.get(key)) == str(expected)]
            for key, options in in_.items():
                expected = {str(v) for v in options}
                rows = [row for row in rows if str(row.get(key)) in expected]
            for key, required in contains.items():
                wanted = {str(v) for v in required}
                rows = [row for row in rows if wanted.issubset({str(v) for v in (row.get(key) or [])})]
            if search_term and search_columns:
                rows = [row for row in rows if _contains_text(row, search_columns, search_term)]
            if order_by:
                rows.sort(key=lambda row: (row.get(order_by) is None, str(row.get(order_by) or "")), reverse=desc)
            return rows[:limit] if limit else rows

        if self.client is None:
            return []

        params = {
            "eq": eq, "in": in_, "contains": contains, "search_columns": search_columns,
            "search_term": search_term, "order_by": order_by, "desc": desc, "limit": limit,
        }
        key = _cache_key("select", table, params)

        def execute() -> list[dict]:
            query = self.client.table(table).select("*")
            for column, expected in eq.items():
                query = query.is_(column, "null") if expected is None else query.eq(column, _json_ready(expected))
            for column, options in in_.items():
                values = [_json_ready(v) for v in options]
                if not values:
                    return []
                query = query.in_(column, values)
            for column, required in contains.items():
                query = query.contains(column, [_json_ready(v) for v in required])
            if search_term and search_columns:
                clean = search_term.replace(",", " ").replace("(", " ").replace(")", " ").strip()
                query = query.or_(",".join(f"{column}.ilike.%{clean}%" for column in search_columns))
            if order_by:
                query = query.order(order_by, desc=desc)
            if limit:
                query = query.limit(limit)
            response = query.execute()
            return [dict(row) for row in (response.data or [])]

        try:
            rows = self._retry(execute, operation=f"reading {table}")
            self._read_cache()[key] = deepcopy(rows)
            return rows
        except RuntimeError:
            cached = self._read_cache().get(key)
            if cached is not None:
                st.warning("Live connection was interrupted. Showing the last successfully loaded data.")
                return deepcopy(cached)
            st.warning("Live database connection is temporarily unavailable. Retry the page in a moment.")
            return []

    def get(self, table: str, record_id: str | None) -> dict | None:
        value = str(record_id or "").strip()
        if not value:
            return None
        try:
            uuid.UUID(value)
        except (ValueError, TypeError, AttributeError):
            return None
        rows = self.select(table, eq={"id": value}, limit=1)
        return rows[0] if rows else None

    def find_one(self, table: str, *, eq: Mapping[str, Any]) -> dict | None:
        rows = self.select(table, eq=eq, limit=1)
        return rows[0] if rows else None

    def insert(self, table: str, payload: Mapping[str, Any]) -> dict:
        row = {key: _json_ready(value) for key, value in payload.items()}
        row.setdefault("id", str(uuid.uuid4()))
        if table in TENANT_SCOPED_TABLES and self.tenant_id:
            row.setdefault("tenant_id", self.tenant_id)
        if self.preview:
            now = datetime.now().astimezone().isoformat()
            row.setdefault("created_at", now); row.setdefault("updated_at", now)
            _demo_database().setdefault(table, []).append(deepcopy(row))
            return row
        if self.client is None:
            raise RuntimeError("Supabase session is unavailable.")
        response = self._retry(lambda: self.client.table(table).insert(row).execute(), operation=f"inserting {table}")
        if not response.data:
            raise RuntimeError(f"Insert into {table} returned no data.")
        return dict(response.data[0])

    def update(self, table: str, record_id: str, payload: Mapping[str, Any]) -> dict:
        record_id = str(record_id or "").strip()
        if not record_id:
            raise ValueError(f"A valid {table} record must be selected before updating.")
        changes = {key: _json_ready(value) for key, value in payload.items()}
        if self.preview:
            changes["updated_at"] = datetime.now().astimezone().isoformat()
            for row in _demo_database().setdefault(table, []):
                if str(row.get("id")) == record_id:
                    row.update(deepcopy(changes)); return deepcopy(row)
            raise KeyError(f"{table} record {record_id} was not found.")
        if self.client is None:
            raise RuntimeError("Supabase session is unavailable.")
        response = self._retry(
            lambda: self.client.table(table).update(changes).eq("id", record_id).execute(),
            operation=f"updating {table}",
        )
        if not response.data:
            raise RuntimeError(f"Update of {table} returned no data.")
        return dict(response.data[0])

    def delete(self, table: str, record_id: str) -> None:
        if self.preview:
            rows = _demo_database().setdefault(table, [])
            _demo_database()[table] = [row for row in rows if str(row.get("id")) != str(record_id)]
            return
        if self.client is None:
            raise RuntimeError("Supabase session is unavailable.")
        self._retry(lambda: self.client.table(table).delete().eq("id", record_id).execute(), operation=f"deleting {table}")

    def upsert_by(self, table: str, payload: Mapping[str, Any], *, natural_key: Mapping[str, Any]) -> tuple[dict, str]:
        existing = self.find_one(table, eq=natural_key)
        if existing:
            return self.update(table, str(existing["id"]), payload), "updated"
        return self.insert(table, payload), "created"

    def bulk_upsert(self, table: str, rows: Sequence[Mapping[str, Any]], *, on_conflict: str = "id") -> list[dict]:
        """Upsert many rows in one Supabase request to keep inspection saves fast."""
        prepared: list[dict] = []
        for source in rows:
            row = {key: _json_ready(value) for key, value in source.items()}
            row.setdefault("id", str(uuid.uuid4()))
            if table in TENANT_SCOPED_TABLES and self.tenant_id:
                row.setdefault("tenant_id", self.tenant_id)
            prepared.append(row)
        if not prepared:
            return []
        if self.preview:
            database = _demo_database().setdefault(table, [])
            by_id = {str(row.get("id")): row for row in database}
            for row in prepared:
                existing = by_id.get(str(row.get("id")))
                if existing:
                    existing.update(deepcopy(row))
                else:
                    database.append(deepcopy(row))
            return deepcopy(prepared)
        if self.client is None:
            raise RuntimeError("Supabase session is unavailable.")
        response = self._retry(
            lambda: self.client.table(table).upsert(prepared, on_conflict=on_conflict).execute(),
            operation=f"bulk upserting {table}",
        )
        return [dict(row) for row in (response.data or [])]

    def count(self, table: str, **kwargs: Any) -> int:
        if self.preview:
            return len(self.select(table, limit=None, **kwargs))
        eq = kwargs.pop("eq", {}) or {}
        contains = kwargs.pop("contains", {}) or {}
        if kwargs:
            return len(self.select(table, limit=None, eq=eq, contains=contains, **kwargs))
        if self.client is None:
            return 0

        def execute() -> int:
            query = self.client.table(table).select("id", count="exact", head=True)
            for column, expected in eq.items():
                query = query.is_(column, "null") if expected is None else query.eq(column, _json_ready(expected))
            for column, required in contains.items():
                query = query.contains(column, [_json_ready(v) for v in required])
            response = query.execute()
            return int(response.count or 0)

        try:
            return self._retry(execute, operation=f"counting {table}")
        except RuntimeError:
            return len(self.select(table, limit=None, eq=eq, contains=contains))

    def rpc(self, function_name: str, params: Mapping[str, Any] | None = None) -> Any:
        if self.preview:
            raise RuntimeError("RPC functions are unavailable in controlled preview mode.")
        if self.client is None:
            raise RuntimeError("Supabase session is unavailable.")
        response = self._retry(
            lambda: self.client.rpc(function_name, _json_ready(params or {})).execute(),
            operation=f"running {function_name}",
        )
        return response.data

    def reset_preview(self) -> None:
        if self.preview:
            st.session_state["_qsms_demo_store"] = demo_store()
