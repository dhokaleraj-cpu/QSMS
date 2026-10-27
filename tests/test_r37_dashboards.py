"""R37 dashboards: module infographic KPIs, one drill-down contract per card, count == drill rows, "+" quick add."""
from __future__ import annotations

import json
import random
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261024120000_qcms_r37_module_kpis.sql"

_NUMERIC_HINTS = ("qty", "quantity", "_kg", "total", "count", "value", "percent", "pcs", "weight", "_no")
_BOOL_COLUMNS = {"rm_procurement_required", "debit_note_required", "root_cause_confirmed"}


def _filter_values(node, out: dict[str, set]) -> None:
    if isinstance(node, (list, tuple)):
        for n in node:
            _filter_values(n, out)
    elif isinstance(node, dict):
        for key in ("any", "all", "not"):
            if key in node:
                _filter_values(node[key], out)
        for key in ("exists", "not_exists"):
            if key in node:
                _filter_values(node[key].get("where"), out)
        if "col" in node:
            cols = node["col"] if isinstance(node["col"], list) else [node["col"]]
            for col in cols:
                bucket = out.setdefault(col, set())
                value = node.get("value")
                if isinstance(value, list):
                    bucket.update(str(v) for v in value)
                elif isinstance(value, str):
                    bucket.add(value)


def make_fake_data(seed: int, today: date, rows_per_table: int = 60) -> dict[str, list[dict]]:
    """Random rows for every module table: statuses from the filters (+ others + null), dates around today."""
    from core.module_kpis import MODULE_GROUPS, related_tables
    rnd = random.Random(seed)
    tables: dict[str, dict[str, set]] = {}
    for group in MODULE_GROUPS:
        cols = tables.setdefault(group.table, {})
        _filter_values(list(group.base), cols)
        for metric in group.metrics:
            _filter_values(list(metric.filter), cols)
            _filter_values(list(metric.den_filter), cols)
        for name in (*group.ref, group.date, group.status, group.spark, *group.party, *(c for _p, c in group.detail)):
            cols.setdefault(name, set())
        if group.part:
            cols.setdefault(group.part, set())
    for table in related_tables(MODULE_GROUPS):
        tables.setdefault(table, {}).update({"part_id": set(), "status": {"APPROVED", "DRAFT"}})
    part_ids = [str(uuid.UUID(int=rnd.getrandbits(128))) for _ in range(rows_per_table)]

    def value(col: str, seen: set):
        if rnd.random() < 0.12:
            return None
        base = col.split(".")[0]
        if base == "results":
            return None
        if col in _BOOL_COLUMNS:
            return rnd.random() < 0.5
        if col.endswith("_date") or col in {"next_due_date", "next_validation_due_date"}:
            return (today + timedelta(days=rnd.randint(-120, 45))).isoformat()
        if col.endswith("_at"):
            moment = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=rnd.randint(-120 * 24, 20 * 24))
            return moment.isoformat()
        if col == "part_id":
            return rnd.choice(part_ids)
        if col == "id" or col.endswith("_id"):
            return str(uuid.UUID(int=rnd.getrandbits(128)))
        if any(h in col for h in _NUMERIC_HINTS) and not seen:
            return rnd.choice([0, 0, 1, 2, 10, 250])
        options = sorted(seen) + ["OTHER", ""]
        return rnd.choice(options)

    data: dict[str, list[dict]] = {}
    for table, cols in tables.items():
        rows = []
        for index in range(rows_per_table):
            row = {"id": part_ids[index] if table == "parts" else str(uuid.UUID(int=rnd.getrandbits(128)))}
            for col, seen in cols.items():
                if col == "id":
                    continue
                if "." in col:
                    head, key = col.split(".", 1)
                    row[head] = {key: rnd.choice(sorted(seen) + ["OTHER"])} if rnd.random() < 0.85 else None
                    continue
                row[col] = value(col, seen)
            row.setdefault("created_at", value("created_at", set()))
            rows.append(row)
        data[table] = rows
    return data


# ----------------------------------------------------------------------------- definitions / migration
def test_definitions_shape_and_unique_keys():
    from core.module_kpis import DEPARTMENTS, MODULE_GROUPS, METRICS_BY_KEY
    from core.kpi_service import CARD_CATALOG
    departments = {code for code, _ in DEPARTMENTS}
    keys = [m.key for g in MODULE_GROUPS for m in g.metrics]
    assert len(keys) == len(set(keys)) == len(METRICS_BY_KEY)
    assert not set(keys) & set(CARD_CATALOG)  # no clash with the start-dashboard keys
    for group in MODULE_GROUPS:
        assert 3 <= len(group.metrics) <= 6, group.key
        assert group.department in departments, group.key
        assert all(m.key.startswith("mk_") and m.tone in {"watch", "alert", "done", "info", "rate"} for m in group.metrics)
    titles = {g.title for g in MODULE_GROUPS}
    for wanted in ("MetLAB", "Dimensional", "Bend Test", "RMTC", "Material Inward", "OSP", "Customer complaints", "Supplier complaints",
                   "Calibration & validation", "Standard room", "QC calculations", "Customer orders", "Purchase orders", "PO confirmations",
                   "RM procurement", "RM receipt", "RM to forging", "Forging", "Production / dispatch", "Opening stock", "NPD orders",
                   "APQP / PPAP", "Part master", "Indirect purchase"):
        assert wanted in titles, wanted


def test_group_routes_exist_in_the_app():
    from core.module_kpis import MODULE_GROUPS
    app = (ROOT / "streamlit_app.py").read_text()
    for group in MODULE_GROUPS:
        for route in {group.route, group.entry_route} - {""}:
            if route.startswith("indirect-"):
                continue  # agent B's module; hidden while its route is missing
            assert f'("{route}", st.Page' in app, (group.key, route)


def test_migration_embeds_the_python_definitions_and_is_safe():
    from core.module_kpis import definitions_json
    sql = MIGRATION.read_text()
    literal = sql.split("$qcmsdefs$", 2)[1]
    assert json.loads(literal) == json.loads(definitions_json()), "regenerate the migration from core/module_kpis.py"
    lowered = sql.lower()
    assert "security definer" not in lowered
    for name in ("qcms_module_kpis(p_department text default null, p_modules text[] default null)",
                 "qcms_kpi_drilldown(p_card_key text, p_limit integer default 500)"):
        head = sql.split(f"create or replace function public.{name}", 1)[1].split("$$", 1)[0]
        assert "security invoker" in head, name
    for forbidden in ("drop ", "delete ", "truncate", "update public.", "insert into"):
        assert forbidden not in lowered.replace(literal.lower(), ""), forbidden
    assert "'drill', public.qcms_kpi_drill_spec(p_key)" in sql  # dashboard + module-strip cards
    assert "grant execute on function public.qcms_kpi_drilldown(text, integer) to authenticated" in sql
    assert "revoke all on function public.qcms_module_kpis(text, text[]) from public, anon" in sql
    files = json.loads((ROOT / "supabase/auto_apply.json").read_text())["files"]
    assert "supabase/migrations/20261024120000_qcms_r37_module_kpis.sql" in files
    assert files.index("supabase/migrations/20261024120000_qcms_r37_module_kpis.sql") > files.index(
        "supabase/migrations/20261024100000_qcms_r37_kpi_drilldown.sql")


# ----------------------------------------------------------------------------- filter semantics
def test_filter_semantics_are_two_valued_and_null_safe():
    from core.module_kpis import ANY, C, MONTH, NOT, TODAY, matches
    today = date(2026, 10, 23)
    row = {"id": "p1", "status": None, "a": "2026-10-01", "b": None, "ts": "2026-09-30T23:30:00+00:00", "n": "5",
           "flag": True, "results": {"inspection_method": "BEND_TEST"}}
    assert matches(row, [C("status", "neq", "FINAL")], today=today)          # null <> 'FINAL'
    assert not matches(row, [C("status", "eq", "FINAL")], today=today)
    assert not matches(row, [C("status", "in", ["X"])], today=today) and matches(row, [C("status", "not_in", ["X"])], today=today)
    assert matches(row, [C("status", "blank"), C("b", "blank")], today=today)
    assert matches(row, [C("a", "gte", MONTH(0))], today=today) and not matches(row, [C("ts", "gte", MONTH(0))], today=today)
    assert matches(row, [C(["b", "a"], "lt", TODAY(0))], today=today)      # coalesce of columns
    assert not matches(row, [C("b", "lt", TODAY(0))], today=today) and not matches(row, [NOT(C("a", "lt", TODAY(0)))], today=today)
    assert matches(row, [ANY(C("b", "lt", TODAY(0)), C("a", "lt", TODAY(0)))], today=today)
    assert matches(row, [C("n", "gt", 4)], today=today) and not matches(row, [C("n", "gt", 5)], today=today)
    assert matches(row, [C("flag", "true")], today=today) and matches({"flag": None}, [C("flag", "not_true")], today=today)
    assert matches(row, [C("results.inspection_method", "eq", "BEND_TEST")], today=today)
    assert matches({"results": None}, [C("results.inspection_method", "neq", "BEND_TEST")], today=today)
    rel = {"inspection_plans": [{"part_id": "p1", "status": "DRAFT"}]}
    spec = {"not_exists": {"table": "inspection_plans", "fk": "part_id", "where": [C("status", "eq", "APPROVED")]}}
    assert matches(row, [spec], today=today, related=rel)
    rel["inspection_plans"].append({"part_id": "p1", "status": "APPROVED"})
    assert not matches(row, [spec], today=today, related=rel)
    assert matches(row, [{"exists": spec["not_exists"]}], today=today, related=rel)
    assert matches({"d": "2026-01-15"}, [C("d", "gte", MONTH(-1)), C("d", "lt", MONTH(0))], today=date(2026, 2, 3))  # year roll-over


# ----------------------------------------------------------------------------- card value == drill rows
@pytest.mark.parametrize("seed,today", [(1, date(2026, 10, 23)), (7, date(2026, 1, 1)), (42, date(2026, 3, 31)), (99, date(2025, 12, 31))])
def test_every_module_card_value_equals_its_drill_row_count(seed, today):
    from core.module_kpis import METRICS_BY_KEY, compute_groups, drill_rows
    data = make_fake_data(seed, today)
    groups = compute_groups(data, today=today)
    seen = 0
    for group in groups:
        for card in group["cards"]:
            _g, metric = METRICS_BY_KEY[card["key"]]
            rows = drill_rows(card["key"], data[_g.table], today=today, related=data, limit=100000)
            assert card["count"] == len(rows), card["key"]
            if metric.measure == "count":
                assert card["value"] == len(rows), card["key"]
                assert card["drill"]["count_matches"] is True
            else:
                assert 0 <= card["value"] <= 100 and card["drill"]["measure"] == "percent"
            assert {r["source_table"] for r in rows} <= {_g.table}
            seen += 1
    assert seen == len(METRICS_BY_KEY)
    assert any(card["value"] for group in groups for card in group["cards"])  # the fake data is not trivially empty


def test_card_json_carries_key_route_and_drill_contract():
    from core.module_kpis import DRILL_ROW_COLUMNS, LEGACY_DRILL, compute_groups, drill_spec
    from core.kpi_service import CARD_CATALOG, CARD_KEYS_BY_LABEL
    today = date(2026, 10, 23)
    for group in compute_groups(make_fake_data(3, today), today=today):
        assert {"key", "title", "department", "icon", "route", "module_key", "cards", "spark", "metrics"} <= set(group)
        assert "base" not in group and len(group["spark"]) == 6
        for card in group["cards"]:
            assert {"key", "label", "value", "unit", "tone", "route", "count", "drill"} <= set(card)
            drill = card["drill"]
            assert drill["rpc"] == "qcms_kpi_drilldown" and drill["args"] == {"p_card_key": card["key"]}
            assert drill["source"] and isinstance(drill["filter"], list) and drill["columns"] == list(DRILL_ROW_COLUMNS)
            assert drill["title"] and drill["open_route"] == card["route"]
    assert set(CARD_KEYS_BY_LABEL.values()) <= set(LEGACY_DRILL) and set(LEGACY_DRILL) <= set(CARD_CATALOG)
    legacy = drill_spec("metlab_pending")
    assert legacy["source"] == "lab_tests" and legacy["filter"] == {"card_key": "metlab_pending", "server": "qcms_kpi_base"}
    assert legacy["open_route"] == "metlab-records" and legacy["count_matches"] is True
    assert drill_spec("po_open_value")["count_matches"] is False and drill_spec("nope") == {}


def test_python_fallback_loads_from_repository_when_rpc_is_missing():
    from core import module_kpis as mk
    today = date.today()
    data = make_fake_data(5, today)

    class FakeRepo:
        def rpc(self, name, params=None):
            raise RuntimeError("PGRST202 function not found")

        def select(self, table, limit=None, **_):
            return data.get(table, [])

    groups = mk.load_groups(FakeRepo(), department="QUALITY")
    assert groups and all(g["department"] == "QUALITY" for g in groups)
    card = groups[0]["cards"][0]
    rows = mk.load_drill(FakeRepo(), card["key"], limit=100000)
    assert rows is not None and len(rows) == card["count"]
    assert mk.load_drill(FakeRepo(), "metlab_pending") is None  # legacy key needs the database


def test_pending_tasks_are_assigned_to_their_module():
    from core.module_kpis import GROUPS_BY_KEY, tasks_for_group
    tasks = [{"title": "Approve PO", "related_table": "supply_purchase_orders", "web_route": "supply-po-approval"},
             {"title": "MetLAB R1", "related_table": "lab_tests", "web_route": "metlab-entry"},
             {"title": "Bend B1", "related_table": "lab_tests", "web_route": "bend-test-entry"},
             {"title": "RMTC", "related_table": "rmtc_approvals", "web_route": "rmtc-approval"}]
    assert [t["title"] for t in tasks_for_group(GROUPS_BY_KEY["purchase_orders"], tasks)] == ["Approve PO"]
    assert [t["title"] for t in tasks_for_group(GROUPS_BY_KEY["metlab"], tasks)] == ["MetLAB R1"]
    assert [t["title"] for t in tasks_for_group(GROUPS_BY_KEY["bend"], tasks)] == ["Bend B1"]
    assert [t["title"] for t in tasks_for_group(GROUPS_BY_KEY["rmtc"], tasks)] == ["RMTC"]


# ----------------------------------------------------------------------------- wiring
def test_module_home_pages_show_the_infographic_row():
    expected = {
        "app_pages/inspection_home.py": 'render_module_strip(home="inspection-home"',
        "app_pages/master_home.py": 'render_module_strip(home="masters"',
        "app_pages/supply_chain.py": 'render_module_strip(home="supply-chain-home"',
        "app_pages/osp_transactions.py": 'render_module_strip(home="osp-home"',
        "app_pages/complaints.py": 'render_module_strip(home="complaints-home"',
        "app_pages/reports.py": "render_module_strip(",
        "app_pages/npd_apqp.py": 'render_module_strip(home="npd-status"',
    }
    for path, token in expected.items():
        assert token in (ROOT / path).read_text(), path


def test_routes_quick_add_and_contract_doc():
    app = (ROOT / "streamlit_app.py").read_text()
    assert '("kpi-drilldown", st.Page(kpi_drilldown.render' in app and '"kpi-drilldown": "KPI Dashboards"' in app
    assert '"kpi-drilldown"' in (ROOT / "scripts/verify_phase1.py").read_text()
    from core.quick_add import GROUPS, QUICK_ACTIONS
    labels = {a.label: a for a in QUICK_ACTIONS}
    assert "New dashboard" in labels and labels["New dashboard"].route == "kpi-dashboards"
    assert "RM Receipt" in labels and "Material Inward" in labels and "OSP Material Out" in labels
    assert labels["Search & AI query"].route == "global-search"
    assert "New dashboard" in GROUPS
    doc = (ROOT / "mobile/KPI_DRILL_CONTRACT.md").read_text()
    for token in ("qcms_kpi_drilldown", "qcms_module_kpis", '"drill"', "count_matches", "open_route", "kpi-drilldown"):
        assert token in doc, token
    page = (ROOT / "app_pages/kpi_drilldown.py").read_text()
    for token in ("render_filters(", "pdf_actions", "report_exports(", "load_drill("):
        assert token in page, token
    assert "render_modules_view" in (ROOT / "app_pages/kpi_dashboards.py").read_text()


# ----------------------------------------------------------------------------- AppTest
def _fake_rpc_factory(today: date):
    from core.module_kpis import compute_groups, drill_rows, METRICS_BY_KEY
    data = make_fake_data(11, today)

    def fake(self, name, params=None):
        params = params or {}
        if name == "qcms_module_kpis":
            return {"groups": compute_groups(data, department=params.get("p_department"), modules=params.get("p_modules"), today=today)}
        if name == "qcms_kpi_drilldown":
            key = params["p_card_key"]
            group, _m = METRICS_BY_KEY[key]
            return drill_rows(key, data[group.table], today=today, related=data, limit=params.get("p_limit") or 500)
        if name == "qcms_my_pending_tasks":
            return [{"title": "MetLAB R9 · approve", "category": "APPROVAL", "related_table": "lab_tests", "web_route": "metlab-entry"}]
        raise RuntimeError("PGRST202")
    return fake


def test_modules_view_cards_open_the_drilldown(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from core.repository import Repository
    from core.kpi_service import DRILL_STATE_KEY
    from core import module_kpis
    monkeypatch.setattr(Repository, "rpc", _fake_rpc_factory(date.today()))
    module_kpis._cached_groups.clear(); module_kpis._cached_tasks.clear()
    try:
        app = AppTest.from_string('''
import streamlit as st
from core.auth import PREVIEW_PROFILE
st.session_state["_qsms_preview"] = True
st.session_state["profile"] = PREVIEW_PROFILE.copy()
from core.repository import Repository
from core.module_kpis import render_modules_view
render_modules_view(Repository(), PREVIEW_PROFILE.copy())
''').run(timeout=60)
        assert not app.exception
        html = " ".join(str(m.value) for m in app.markdown)
        assert "qcms-mk-card" in html and "MetLAB" in html and "My pending tasks" in html
        key = next(b.key for b in app.button if b.key and b.key.startswith("mk_kpi_modules_view_quality_metlab_open_"))
        app.button(key=key).click().run(timeout=60)
        assert not app.exception
        request = app.session_state[DRILL_STATE_KEY]
        assert request["key"].startswith("mk_metlab_") and request["route"] == "metlab-records" and "MetLAB" in request["label"]
    finally:
        module_kpis._cached_groups.clear(); module_kpis._cached_tasks.clear()


def test_drilldown_page_lists_module_metric_rows(monkeypatch):
    pytest.importorskip("pyarrow")
    from streamlit.testing.v1 import AppTest
    from core.repository import Repository
    monkeypatch.setattr(Repository, "rpc", _fake_rpc_factory(date.today()))
    app = AppTest.from_string('''
import streamlit as st
from core.auth import PREVIEW_PROFILE
from core.kpi_service import DRILL_STATE_KEY
st.session_state["_qsms_preview"] = True
st.session_state["profile"] = PREVIEW_PROFILE.copy()
st.session_state.setdefault(DRILL_STATE_KEY, {"key": "mk_metlab_pending", "label": "MetLAB · Pending", "value": "", "department": "QUALITY",
                                              "route": "metlab-records", "origin": "kpi-dashboards", "rows": None})
from app_pages import kpi_drilldown
kpi_drilldown._records.clear()
kpi_drilldown.render()
''').run(timeout=60)
    assert not app.exception
    assert app.dataframe
