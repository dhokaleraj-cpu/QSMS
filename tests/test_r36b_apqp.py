"""R36b: APQP could not retrieve existing projects nor save them; Edit option per saved project."""
from __future__ import annotations

from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261023100000_qcms_r36b_apqp_fix.sql"

SCRIPT = '''
import streamlit as st
from core.auth import PREVIEW_PROFILE
st.session_state["_qsms_preview"] = True
st.session_state["profile"] = PREVIEW_PROFILE.copy()
st.data_editor = lambda data, **kwargs: data  # pyarrow-free test runtime
from app_pages import npd_apqp
npd_apqp.render_apqp()
'''


def _calls(monkeypatch):
    from core.repository import Repository
    calls: list[tuple[str, str]] = []
    original_insert, original_update = Repository.insert, Repository.update

    def insert(self, table, payload):
        calls.append(("insert", table))
        return original_insert(self, table, payload)

    def update(self, table, record_id, payload):
        calls.append(("update", table))
        return original_update(self, table, record_id, payload)

    monkeypatch.setattr(Repository, "insert", insert)
    monkeypatch.setattr(Repository, "update", update)
    return calls


def _app():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_string(SCRIPT).run(timeout=120)


def _button(app, label):
    return next(b for b in app.button if b.label == label)


def _projects(app):
    return list(app.session_state["_qsms_demo_store"].get("ppap_projects", []))


def test_selector_no_longer_resets_to_new_project():
    from app_pages.npd_apqp import apqp_resolve_selection
    options = ["", "p1", "p2"]
    # The R36 bug: an empty request ("" is the New option) overrode the user's choice every rerun.
    assert apqp_resolve_selection("", "p1", options) == "p1"
    assert apqp_resolve_selection(None, "p2", options) == "p2"
    assert apqp_resolve_selection("p2", "p1", options) == "p2"  # Records Centre / Global Search / Edit
    assert apqp_resolve_selection("gone", "p1", options) == "p1"
    assert apqp_resolve_selection("", "deleted", options) == ""


def test_field_wise_validation_and_duplicate_guard():
    from app_pages.npd_apqp import apqp_project_errors
    projects = [{"id": "p1", "project_code": "NPD0016"}]
    errors = apqp_project_errors(project_code="", part_id="", customer_id="", target_date=None, projects=projects)
    assert any(e.startswith("Project / NPD Number") for e in errors)
    assert any(e.startswith("Part Number") for e in errors) and any(e.startswith("Customer") for e in errors)
    assert any(e.startswith("Target PPAP Submission") for e in errors)
    dup = apqp_project_errors(project_code="npd0016", part_id="a", customer_id="b", target_date=date.today(), projects=projects)
    assert dup and "already exists" in dup[0]
    assert apqp_project_errors(project_code="NPD0016", part_id="a", customer_id="b", target_date=date.today(), projects=projects, existing_id="p1") == []


def test_search_filter():
    from app_pages.npd_apqp import apqp_filter_projects
    rows = [{"id": "1", "project_code": "NPD0016", "part_id": "x", "status": "IN_PROGRESS"},
            {"id": "2", "project_code": "0002", "part_id": "y", "status": "COMPLETED", "coordinator": "Rahul"}]
    labels = {"x": "40286128 · Differential Shaft", "y": "71.784.3 · Spider"}
    assert [r["id"] for r in apqp_filter_projects(rows, "shaft", labels, {})] == ["1"]
    assert [r["id"] for r in apqp_filter_projects(rows, "rahul", labels, {})] == ["2"]
    assert [r["id"] for r in apqp_filter_projects(rows, "", labels, {}, "COMPLETED")] == ["2"]


def test_static_contract():
    page = (ROOT / "app_pages/npd_apqp.py").read_text()
    assert 'if requested_project in project_options:' not in page
    assert "apqp_selected_project" not in page  # stale fallback removed
    for token in ("APQP PROJECT REGISTER", "Search APQP Projects", "Update APQP Project", "apqp_edit_", "missing_fields_message(errors)",
                  'perms["can_edit"]) if existing else bool(perms["can_create"])', "APQP_EDIT_REQUEST_KEY", "db_message(exc)"):
        assert token in page, token
    rc = (ROOT / "app_pages/records_center.py").read_text()
    assert '"ppap_projects", "ppap_documents"' in rc and 'st.session_state["apqp_project_edit_request_id"] = project_id' in rc


def test_migration_is_additive_and_registered():
    sql = MIGRATION.read_text().lower()
    assert "set default public.current_tenant_id()" in sql and "pg_policies" in sql
    import re
    assert not re.search(r"^\s*(delete\s+from|update\s+public\.|drop\s|truncate)", sql, re.M)
    assert "supabase/migrations/20261023100000_qcms_r36b_apqp_fix.sql" in (ROOT / "supabase/auto_apply.json").read_text()


def test_create_then_project_stays_open_and_save_updates(monkeypatch):
    calls = _calls(monkeypatch)
    app = _app()
    assert not app.exception
    assert app.selectbox(key="apqp_project_selector").value == ""
    app.text_input[1].input("APQP-R36B")  # [0] is the register search
    _button(app, "Save APQP Project").click().run(timeout=120)
    assert not app.exception, app.exception
    projects = [p for p in _projects(app) if p.get("project_code") == "APQP-R36B"]
    assert len(projects) == 1
    pid = str(projects[0]["id"])
    # Bug: selector bounced back to "New APQP Project"; now the saved project stays open for edit.
    assert app.selectbox(key="apqp_project_selector").value == pid
    labels = [b.label for b in app.button]
    assert "Update APQP Project" in labels and "Save APQP Project" not in labels
    app.run(timeout=120)
    assert app.selectbox(key="apqp_project_selector").value == pid
    # Edit + save updates the same record: no duplicate insert.
    app.text_input[1].input("APQP-R36B-REV1")
    _button(app, "Update APQP Project").click().run(timeout=120)
    assert not app.exception
    codes = [p.get("project_code") for p in _projects(app)]
    assert codes.count("APQP-R36B-REV1") == 1 and "APQP-R36B" not in codes
    assert calls.count(("insert", "ppap_projects")) == 1 and calls.count(("update", "ppap_projects")) == 1
    # Gates load for the open project.
    _button(app, "Load Standard APQP Gates").click().run(timeout=120)
    assert not app.exception
    assert len([d for d in app.session_state["_qsms_demo_store"].get("ppap_documents", []) if str(d.get("ppap_project_id")) == pid]) == 8
    assert "Update APQP Gates" in [b.label for b in app.button]


def test_duplicate_code_shows_field_error_and_does_not_insert(monkeypatch):
    calls = _calls(monkeypatch)
    app = _app()
    app.text_input[1].input("DUP-1")
    _button(app, "Save APQP Project").click().run(timeout=120)
    _button(app, "New APQP Project").click().run(timeout=120)
    assert app.selectbox(key="apqp_project_selector").value == ""
    app.text_input[1].input("dup-1")
    _button(app, "Save APQP Project").click().run(timeout=120)
    assert any("already exists" in str(e.value) and "Project / NPD Number" in str(e.value) for e in app.error)
    assert calls.count(("insert", "ppap_projects")) == 1


def test_records_centre_request_and_register_edit_button_open_project(monkeypatch):
    _calls(monkeypatch)
    app = _app()
    app.text_input[1].input("OPEN-1")
    _button(app, "Save APQP Project").click().run(timeout=120)
    pid = str(next(p for p in _projects(app) if p.get("project_code") == "OPEN-1")["id"])
    _button(app, "New APQP Project").click().run(timeout=120)
    assert app.selectbox(key="apqp_project_selector").value == ""
    app.session_state["apqp_project_edit_request_id"] = pid  # Records Centre / Global Search
    app.run(timeout=120)
    assert app.selectbox(key="apqp_project_selector").value == pid
    _button(app, "New APQP Project").click().run(timeout=120)
    next(b for b in app.button if b.key == f"apqp_edit_{pid}").click().run(timeout=120)
    assert app.selectbox(key="apqp_project_selector").value == pid
    assert app.text_input[1].value == "OPEN-1"
    # Register search filters the list.
    app.text_input(key="apqp_register_search").input("no-such-project").run(timeout=120)
    assert not [b for b in app.button if str(b.key or "").startswith("apqp_edit_")]
