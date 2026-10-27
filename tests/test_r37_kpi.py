"""R37: KPI drill-down (every card -> records -> open record), module infographic cards, header "＋" quick add."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261024100000_qcms_r37_kpi_drilldown.sql"


# ----------------------------------------------------------------------------- database contract
def test_migration_is_additive_security_invoker_and_listed():
    sql = MIGRATION.read_text()
    lowered = sql.lower()
    for token in ("create or replace function public.qcms_kpi_records(p_card_key text, p_department text default null, p_limit integer default 500)",
                  "returns table(source_table text, record_id uuid, reference text, part text, party text, status text, record_date date, detail text)",
                  "create or replace function public.qcms_module_cards(p_department text default 'QUALITY')",
                  "create or replace function public.qcms_kpi_card_k(", "pg_get_functiondef('public.qcms_kpi_dashboard(text)'::regprocedure)",
                  "'route', p_route", "'key', p_key", "grant execute on function public.qcms_kpi_records(text, text, integer) to authenticated",
                  "revoke all on function public.qcms_module_cards(text) from public, anon"):
        assert token in sql, token
    assert "security definer" not in lowered
    for forbidden in ("drop table", "drop function", "delete from", "truncate", "update public."):
        assert forbidden not in lowered, forbidden
    files = json.loads((ROOT / "supabase/auto_apply.json").read_text())["files"]
    assert files[-1].endswith("20261024100000_qcms_r37_kpi_drilldown.sql") or "supabase/migrations/20261024100000_qcms_r37_kpi_drilldown.sql" in files


def test_every_dashboard_card_label_has_a_drill_key_in_sql_and_python():
    from core.kpi_service import CARD_CATALOG, CARD_KEYS_BY_LABEL
    sql = MIGRATION.read_text()
    for label, key in CARD_KEYS_BY_LABEL.items():
        assert f"('{label}', '{key}')" in sql, label
        assert key in CARD_CATALOG, key
        assert f"'{key}'" in sql.split("create or replace function public.qcms_kpi_base", 1)[1], key
    # module cards: every key used by qcms_module_cards is understood by qcms_kpi_base
    cards_sql = sql.split("create or replace function public.qcms_module_cards", 1)[1]
    base_sql = sql.split("create or replace function public.qcms_kpi_base", 1)[1].split("create or replace function public.qcms_kpi_records", 1)[0]
    import re
    for key in re.findall(r"qcms_module_card\('([a-z0-9_]+)'", cards_sql):
        assert f"'{key}'" in base_sql, key
        assert key in CARD_CATALOG, key


# ----------------------------------------------------------------------------- pure helpers
def test_card_key_route_and_drill_frame():
    from core.kpi_service import card_key, card_route, drill_frame, DRILL_COLUMNS
    assert card_key({"key": "po_open", "label": "x"}) == "po_open"
    assert card_key({"label": "MetLAB pending"}) == "metlab_pending"  # older database without "key"
    assert card_key({"label": "unknown"}) == ""
    assert card_route({"label": "PO pending approval"}) == "supply-po-approval"
    assert card_route({"key": "x", "web_route": "apqp"}) == "apqp"
    frame = drill_frame([{"source_table": "lab_tests", "record_id": "1", "reference": "MLAB-1", "part": "P1", "party": "S1",
                          "status": "DRAFT", "record_date": "2026-10-01", "detail": "Heat H1"}])
    assert list(frame.columns) == list(DRILL_COLUMNS)
    assert frame.iloc[0].to_dict() == {"Type": "MetLAB / Bend Test", "Reference": "MLAB-1", "Part": "P1", "Customer / supplier": "S1",
                                       "Status": "Draft", "Date": "01-Oct-2026", "Detail": "Heat H1"}
    assert drill_frame([]).empty


def test_custom_widget_drill_rows_match_the_number():
    from core import dashboard_builder as db
    rows = [{"id": "a", "status": "OPEN", "complaint_number": "C-1", "party_id": "p1", "part_id": "x1", "complaint_date": "2026-10-01"},
            {"id": "b", "status": "CLOSED", "complaint_number": "C-2", "party_id": "p1", "complaint_date": "2026-10-02"},
            {"id": "c", "status": "OPEN", "complaint_number": "C-3", "complaint_date": "2026-10-03"}]
    widget = db.new_widget(type="kpi", source="quality_complaints", filter_field="status", filter_value="OPEN")
    labels = {"parts": {"x1": "40256626"}, "parties": {"p1": "ACME"}}
    value, _ = db.compute(rows, widget, labels=labels)
    drill = db.drill_rows(rows, widget, labels=labels)
    assert value == len(drill) == 2
    assert [r["reference"] for r in drill] == ["C-1", "C-3"] and drill[0]["party"] == "ACME" and drill[0]["part"] == "40256626"
    assert drill[0]["source_table"] == "quality_complaints" and drill[0]["record_id"] == "a"


def test_quick_add_permissions_and_new_mode():
    from core.quick_add import QUICK_ACTIONS, allowed_actions, grouped, prepare_new_mode
    routes = {a.route for a in QUICK_ACTIONS} - {"indirect-po"}
    allowed = allowed_actions(routes, lambda module, right: module == "RMTC_ENTRY" and right == "can_create")
    labels = [a.label for a in allowed]
    assert "RMTC" in labels and "Purchase Order" not in labels and "Indirect PO" not in labels
    assert "New e-mail" in labels and "Search & AI query" in labels  # no module permission needed
    assert list(grouped(allowed)) == ["New transaction", "New e-mail", "New query", "New dashboard"]  # R37: + New dashboard
    everything = allowed_actions(routes | {"indirect-po"}, lambda m, r: True)
    assert "Indirect PO" in [a.label for a in everything]
    state = {"edit_rmtc_id": "r1", "rmtc_entry_mode": "edit"}
    prepare_new_mode(state, next(a for a in QUICK_ACTIONS if a.label == "RMTC"))
    assert state == {"rmtc_entry_mode": "new"}


def test_routes_registered_and_header_has_quick_add():
    app = (ROOT / "streamlit_app.py").read_text()
    for token in ('("kpi-details", st.Page(kpi_drilldown.render, title="KPI Details"', '"KPI Details": "kpi-details"',
                  '"kpi-details": "KPI Dashboards"', '("kpi-details", "KPI Details", ":material/table_rows:")'):
        assert token in app, token
    assert '"kpi-details"' in (ROOT / "scripts/verify_phase1.py").read_text()
    ui = (ROOT / "core/ui.py").read_text()
    header = ui.split("def render_shell_header", 1)[1].split("def render_left_navigation", 1)[0]
    assert "render_quick_add(profile)" in header and 'key="qcms_header_quick_add"' in header
    assert "def clickable_cards(" in ui and "def kpi_grid_clickable(" in ui
    page = (ROOT / "app_pages/kpi_dashboards.py").read_text()
    for token in ("qcms_module_cards", "_render_modules", "clickable_cards(tiles", "open_kpi_details", "_open_task(repo, tasks[clicked])"):
        assert token in page, token
    assert "kpi_grid_clickable(kpi_items" in (ROOT / "app_pages/dashboard.py").read_text()
    drill = (ROOT / "app_pages/kpi_drilldown.py").read_text()
    assert "qcms_kpi_records" in drill and "selectable_table(" in drill and "_open_record" in drill and "Open full register" in drill


# ----------------------------------------------------------------------------- AppTest
_MODULE = {"key": "mod_metlab", "title": "MetLAB", "icon": "🔬", "route": "metlab-records", "module_key": "METLAB_REPORT", "value": 4,
           "value_label": "reports pending", "overdue": 1, "overdue_label": "> 3 days", "month": 9, "done": 12, "done_label": "finalized",
           "progress": 75.0, "spark": [1, 2, 3, 2, 5, 4], "tone": "critical"}


def _fake_rpc(self, name, params=None):
    params = params or {}
    if name == "qcms_module_cards":
        return {"department": params.get("p_department"), "modules": [_MODULE]}
    if name == "qcms_kpi_records":
        return [{"source_table": "lab_tests", "record_id": "11111111-1111-1111-1111-111111111111", "reference": "MLAB-77",
                 "part": "40256626", "party": "ACME", "status": "DRAFT", "record_date": "2026-10-20", "detail": "Heat H1"}]
    dept = params.get("p_department")
    return {"department": dept, "cards": [{"key": "metlab_pending", "label": f"{dept} MetLAB card", "value": 5, "unit": "reports", "tone": "warning",
                                           "route": "metlab-records"}],
            "charts": [], "pending_tasks": [{"title": "Approve Purchase Order PO-9", "category": "APPROVAL", "web_route": "supply-po-approval"}],
            "unread_notifications": 0}


_SCRIPT = '''
import streamlit as st
from core.auth import PREVIEW_PROFILE
st.session_state["_qsms_preview"] = True
st.session_state["profile"] = PREVIEW_PROFILE.copy()
st.session_state["kpi_auto_rotate"] = False
from app_pages import kpi_dashboards
kpi_dashboards.render()
'''


def test_start_dashboard_cards_and_modules_open_kpi_details(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from core.repository import Repository
    from app_pages import kpi_dashboards
    from core.kpi_service import DRILL_STATE_KEY
    monkeypatch.setattr(Repository, "rpc", _fake_rpc)
    kpi_dashboards._cached_payload.clear(); kpi_dashboards._cached_modules.clear()
    try:
        app = AppTest.from_string(_SCRIPT).run(timeout=60)
        assert not app.exception
        html = " ".join(str(m.value) for m in app.markdown)
        assert "QUALITY MetLAB card" in html and "qcms-mod-card" in html and "reports pending" in html and "<svg" in html
        keys = [b.key for b in app.button]
        assert "kpi_cards_quality_open_0" in keys and "kpi_modules_quality_open_0" in keys and "kpi_tasks_quality_open_0" in keys
        app.button(key="kpi_cards_quality_open_0").click().run(timeout=60)
        assert not app.exception
        request = app.session_state[DRILL_STATE_KEY]
        assert request["key"] == "metlab_pending" and request["department"] == "QUALITY" and request["route"] == "metlab-records"
        app.button(key="kpi_modules_quality_open_0").click().run(timeout=60)
        assert app.session_state[DRILL_STATE_KEY]["key"] == "mod_metlab"
    finally:
        kpi_dashboards._cached_payload.clear(); kpi_dashboards._cached_modules.clear()


def test_quick_add_popover_lists_allowed_actions():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
import streamlit as st
from core.auth import PREVIEW_PROFILE
st.session_state["_qsms_preview"] = True
st.session_state["_qsms_pages"] = {"email-send": "x", "global-search": "y"}
from core.quick_add import render_quick_add
render_quick_add(PREVIEW_PROFILE.copy())
''').run(timeout=60)
    assert not app.exception
    labels = [b.label for b in app.button]
    assert "New e-mail" in labels and "Search & AI query" in labels and "RMTC" not in labels


def test_kpi_details_page_lists_records(monkeypatch):
    pytest.importorskip("pyarrow")
    from streamlit.testing.v1 import AppTest
    from core.repository import Repository
    monkeypatch.setattr(Repository, "rpc", _fake_rpc)
    app = AppTest.from_string('''
import streamlit as st
from core.auth import PREVIEW_PROFILE
from core.kpi_service import DRILL_STATE_KEY
st.session_state["_qsms_preview"] = True
st.session_state["profile"] = PREVIEW_PROFILE.copy()
st.session_state.setdefault(DRILL_STATE_KEY, {"key": "metlab_pending", "label": "MetLAB pending", "value": "1", "department": "QUALITY",
                                              "route": "metlab-records", "origin": "kpi-dashboards", "rows": None})
from app_pages import kpi_drilldown
kpi_drilldown._records.clear()
kpi_drilldown.render()
''').run(timeout=60)
    assert not app.exception
    assert any("MLAB-77" in df.value.to_csv() for df in app.dataframe)
