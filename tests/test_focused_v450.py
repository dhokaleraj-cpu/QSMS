from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_and_material_inward_pages_are_registered():
    app = (ROOT / "streamlit_app.py").read_text()
    assert 'url_path="dashboard"' in app
    assert 'url_path="inward-entry"' in app
    assert 'url_path="inward-records"' in app
    dashboard_decl = app[app.index('st.Page(dashboard.render'):app.index('st.Page(master_home.render')]
    assert 'default=True' in dashboard_decl


def test_rmtc_workflow_has_controlled_dispositions():
    page = (ROOT / "app_pages" / "rmtc_pages.py").read_text()
    assert "ACCEPTED_UNDER_RESERVE" in page
    assert "qsms_decide_rmtc" in page
    assert "Submit for Validation" in page
    assert "Validate Against Masters" in page


def test_material_inward_uses_accepted_rmtc_parts():
    service = (ROOT / "core" / "inward_service.py").read_text()
    page = (ROOT / "app_pages" / "material_inward.py").read_text()
    assert "v_qsms_accepted_rmtc_parts" in service
    assert "rmtc_part_approval_id" in page
    assert "ACCEPTED_UNDER_RESERVE" in page


def test_record_selectors_are_before_master_grids():
    checks = [
        ("part_master.py", "Select Part Master record", "PART MASTER REGISTER"),
        ("material_grade.py", "Select Material Grade record", "MATERIAL GRADE REGISTER"),
        ("reference_master.py", "Select reference record", "REFERENCE REGISTER"),
        ("employee_master.py", "Select Employee record", "EMPLOYEE REGISTER"),
        ("rmtc_pages.py", "Select RMTC record", "RMTC REGISTER"),
        ("material_inward.py", "Select Material Inward record", "MATERIAL INWARD REGISTER"),
    ]
    for file_name, selector, grid in checks:
        text = (ROOT / "app_pages" / file_name).read_text()
        assert text.index(selector) < text.index(grid), file_name


def test_disposition_cards_have_distinct_colours():
    ui = (ROOT / "core" / "ui.py").read_text()
    assert "fsi-status-accepted" in ui
    assert "fsi-status-reserve" in ui
    assert "fsi-status-rejected" in ui
    assert "fsi-status-pending" in ui


def test_new_database_migrations_are_packaged():
    migration = (ROOT / "supabase" / "migrations" / "20260802054000_qsms_dashboard_inward_dispositions.sql").read_text()
    assert "qsms_decide_rmtc" in migration
    assert "v_qsms_accepted_rmtc_parts" in migration
    assert "enforce_inward_rmtc_link" in migration
