"""R35: KPI start dashboard (department tabs, auto switch), custom dashboards, Global Search everywhere."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261021130000_qcms_r35_dashboards_search.sql"


def test_migration_is_additive_and_secured():
    sql = MIGRATION.read_text()
    for token in ("create table if not exists public.qcms_user_dashboards", "enable row level security",
                  "create or replace function public.qcms_kpi_dashboard(p_department text default 'QUALITY')",
                  "create or replace function public.qcms_global_search(p_query text, p_limit integer default 200)",
                  "create or replace function public.qcms_my_pending_tasks", "security invoker",
                  "grant execute on function public.qcms_global_search(text, integer) to authenticated",
                  "owner_profile_id = (select auth.uid())", "shared_with_tenant"):
        assert token in sql, token
    lowered = sql.lower()
    assert "drop table" not in lowered and "drop column" not in lowered and "delete from" not in lowered and "truncate" not in lowered
    assert "security definer" not in lowered  # RLS must decide what each user sees
    # secrets / credentials never searched
    for excluded in ("qcms_user_mail_accounts", "qcms_email_settings", "%password%", "%secret%", "%token%"):
        assert excluded in sql
    for dept in ("QUALITY", "SUPPLY_CHAIN", "PRODUCTION", "NPD", "MANAGEMENT"):
        assert f"'{dept}'" in sql


def test_dashboard_builder_compute_and_layout():
    from core import dashboard_builder as db
    rows = [
        {"status": "FINAL", "disposition": "ACCEPTED", "test_date": "2026-10-01", "part_id": "p1"},
        {"status": "FINAL", "disposition": "REJECTED", "test_date": "2026-10-05", "part_id": "p1"},
        {"status": "DRAFT", "disposition": "PENDING", "test_date": "2026-09-02", "part_id": "p2"},
        {"status": "FINAL", "disposition": "ACCEPTED", "test_date": "2025-01-01", "part_id": "p2"},
    ]
    labels = {"parts": {"p1": "40256626", "p2": "J5/16"}}
    value, _ = db.compute(rows, db.new_widget(type="kpi", source="lab_tests", period_days=90), today=date(2026, 10, 21), labels=labels)
    assert value == 3
    _, frame = db.compute(rows, db.new_widget(type="bar", source="lab_tests", group_by="part_id"), labels=labels)
    assert dict(zip(frame["Group"], frame["Value"])) == {"40256626": 2, "J5/16": 2}
    _, frame = db.compute(rows, db.new_widget(type="bar", source="lab_tests", time_bucket="month", series_by="disposition", period_days=60),
                          today=date(2026, 10, 21))
    assert set(frame.columns) == {"Group", "Series", "Value"} and set(frame["Group"]) == {"2026-09", "2026-10"}
    _, frame = db.compute(rows, db.new_widget(type="table", source="lab_tests", group_by="status", filter_field="disposition", filter_value="accep"))
    assert dict(zip(frame["Group"], frame["Value"])) == {"Final": 2}
    num_rows = [{"order_qty_pcs": 100, "status": "OPEN"}, {"order_qty_pcs": "50", "status": "OPEN"}, {"order_qty_pcs": None, "status": "OPEN"}]
    value, _ = db.compute(num_rows, db.new_widget(type="kpi", source="supply_customer_orders", agg="sum", value_field="order_qty_pcs"))
    assert value == 150
    value, _ = db.compute(num_rows, db.new_widget(type="kpi", source="supply_customer_orders", agg="avg", value_field="order_qty_pcs"))
    assert value == 75
    widgets = [db.new_widget(width=w) for w in (1, 1, 2, 3, 4, 2)]
    assert [len(r) for r in db.pack_rows(widgets)] == [3, 1, 1, 1]
    ids = [w["id"] for w in widgets]
    moved = db.move_widget(widgets, ids[2], -1)
    assert [w["id"] for w in moved][:3] == [ids[0], ids[2], ids[1]]
    dup = db.duplicate_widget(widgets, ids[0])
    assert len(dup) == 7 and dup[1]["title"].endswith("(copy)") and dup[1]["id"] != ids[0]
    bad = db.normalize_widget({"type": "x", "source": "nope", "width": 9, "height": "XL", "agg": "median"})
    assert (bad["type"], bad["source"], bad["width"], bad["height"], bad["agg"]) == ("bar", "lab_tests", 4, "M", "count")
    assert len(db.starter_widgets()) >= 6 and all(w["source"] in db.DATA_SOURCES for w in db.starter_widgets())


class _Page:
    def __init__(self, title):
        self.title = title


def test_global_search_finds_modules_fields_and_records():
    from core import global_search_service as gs
    pages = {"bend-test-entry": _Page("Bend Test Report"), "bend-test-records": _Page("Bend Test Records"),
             "bend-layout-entry": _Page("Bend Test Layout Master"), "metlab-entry": _Page("MetLAB Report"), "dashboard": _Page("Dashboard")}
    routes = [m["route"] for m in gs.search_modules("bend test", pages)]
    assert {"bend-test-entry", "bend-test-records", "bend-layout-entry"} <= set(routes)
    assert "dashboard" not in routes
    fields = gs.search_fields("heat number")
    assert fields and all("heat" in f["label"].lower() for f in fields[:3])

    class Repo:
        def rpc(self, name, params):
            assert name == "qcms_global_search" and params["p_query"] == "J5/16"
            return [{"source_table": "parts", "record_id": "11111111-1111-1111-1111-111111111111", "module_key": "PART_MASTER", "title": "J5/16",
                     "subtitle": "Shaft", "matched_field": "part_number", "snippet": "J5/16", "web_route": "part-records", "record_type": "Part Master"},
                    {"source_table": "supply_purchase_orders", "record_id": "22222222-2222-2222-2222-222222222222", "module_key": "SUPPLY_CHAIN",
                     "title": "PO-1", "subtitle": "", "matched_field": "remarks", "snippet": "for J5/16", "web_route": "supply-po-order-list",
                     "record_type": "Purchase Order"}]
    results = gs.search_records(Repo(), "J5/16", can_view=lambda key: key != "SUPPLY_CHAIN")
    assert [r["table"] for r in results] == ["parts"] and results[0]["route"] == "part-records"
    assert gs.search_records(Repo(), "J") == []

    class Missing:
        def rpc(self, name, params):
            raise RuntimeError("Could not find the function public.qcms_global_search(p_limit, p_query) in the schema cache (PGRST202)")
    assert gs.search_records(Missing(), "abc") is None
    grouped = gs.group_records(results)
    assert list(grouped) == ["Part Master"]


def test_pages_wiring():
    page = (ROOT / "app_pages/kpi_dashboards.py").read_text()
    for token in ("qcms_kpi_dashboard", "Auto switch departments", "st.fragment(run_every=", "kpi_anim_", "@keyframes qcmsKpiIn",
                  '"QUALITY", "Quality"', "MY PENDING TASKS", "_render_my_dashboards", "_render_detailed", "prefers-reduced-motion"):
        assert token in page, token
    search = (ROOT / "app_pages/global_search.py").read_text()
    assert '"🔎 Search Everything"' in search and "search_records(repo, query" in search and "_render_classic_results" in search
    app = (ROOT / "streamlit_app.py").read_text()
    line = next(l for l in app.splitlines() if "st.Page(kpi_dashboards.render" in l)
    assert "default=True" in line


def _fake_rpc(self, name, params=None):
    dept = (params or {}).get("p_department")
    return {"department": dept, "cards": [{"label": f"{dept} card", "value": 5, "unit": "pcs", "tone": "warning"}],
            "charts": [{"title": "Trend", "type": "bar", "labels": ["Sep", "Oct"], "series": [{"name": "A", "values": [1, 2]}]}],
            "pending_tasks": [{"title": "Approve Purchase Order PO-9", "category": "APPROVAL", "web_route": "supply-po-approval"}],
            "unread_notifications": 2}


def test_live_dashboard_renders_and_rotates(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from core.repository import Repository
    from app_pages import kpi_dashboards
    monkeypatch.setattr(Repository, "rpc", _fake_rpc)
    kpi_dashboards._cached_payload.clear()
    app = AppTest.from_string('''
import streamlit as st, time
from core.auth import PREVIEW_PROFILE
st.session_state["_qsms_preview"] = True
st.session_state["profile"] = PREVIEW_PROFILE.copy()
if st.session_state.get("_force_old"):
    st.session_state["_kpi_dept_switched_at"] = time.time() - 999
from app_pages import kpi_dashboards
kpi_dashboards.render()
''').run(timeout=60)
    assert not app.exception
    html = " ".join(str(m.value) for m in app.markdown)
    assert "QUALITY card" in html and "Approve Purchase Order PO-9" in html
    app.session_state["_force_old"] = True
    app.run(timeout=60)
    assert not app.exception
    html = " ".join(str(m.value) for m in app.markdown)
    assert "SUPPLY_CHAIN card" in html
    kpi_dashboards._cached_payload.clear()  # fake payloads must not leak into other tests


def test_live_dashboard_falls_back_in_preview():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
import streamlit as st
from app_pages import kpi_dashboards as _k
_k._cached_payload.clear()
from core.auth import PREVIEW_PROFILE
st.session_state["_qsms_preview"] = True
st.session_state["profile"] = PREVIEW_PROFILE.copy()
from app_pages import kpi_dashboards
kpi_dashboards.render()
''').run(timeout=60)
    assert not app.exception
    assert any("KPI OVERVIEW" in str(m.value) for m in app.markdown)


def test_global_search_page_renders_everything(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from core.repository import Repository

    def fake(self, name, params=None):
        if name == "qcms_global_search":
            return [{"source_table": "lab_tests", "record_id": "33333333-3333-3333-3333-333333333333", "module_key": "METLAB_REPORT",
                     "title": "MLAB-D9-26-00219", "subtitle": "A42540 · FINAL", "matched_field": "layout_name_snapshot",
                     "snippet": "Bend test", "web_route": "metlab-records", "record_type": "MetLAB / Bend Test Report"}]
        raise RuntimeError("RPC functions are unavailable in controlled preview mode.")
    monkeypatch.setattr(Repository, "rpc", fake)
    app = AppTest.from_string('''
import streamlit as st
from core.auth import PREVIEW_PROFILE
st.session_state["_qsms_preview"] = True
st.session_state["profile"] = PREVIEW_PROFILE.copy()
class P:
    def __init__(self, t): self.title = t
st.session_state["_qsms_pages"] = {"bend-test-entry": P("Bend Test Report"), "bend-test-records": P("Bend Test Records")}
st.session_state["_qcms_global_search_pending_query"] = "bend test"
from app_pages import global_search
global_search.render()
''').run(timeout=60)
    assert not app.exception
    labels = [b.label for b in app.button]
    assert "Bend Test Report" in labels and "Bend Test Records" in labels
    picker = app.selectbox(key="gs_rec_pick_all")
    assert any("MLAB-D9-26-00219" in str(option) for option in picker.options)
    assert any("RECORDS" in str(m.value) for m in app.markdown)
