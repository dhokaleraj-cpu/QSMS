from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_499_contract():
    assert (ROOT / "VERSION").read_text().strip() == "4.9.9"
    assert (ROOT / "docs" / "RELEASE_4_9_9.md").exists()
    assert (ROOT / "supabase" / "migrations" / "20260811125500_qcms_delete_save_jominy_cleanup_v499.sql").exists()


def test_save_and_delete_popup_contract():
    ui = (ROOT / "core" / "ui.py").read_text()
    delete = (ROOT / "core" / "delete_service.py").read_text()
    app = (ROOT / "streamlit_app.py").read_text()
    assert "save_success_popup" in ui and "st.toast" in ui
    assert "delete_success_popup" in ui
    assert "verify_current_password" in delete
    assert "Current QCMS password" in delete
    assert "render_pending_popups" in app


def test_new_module_delete_controls():
    npd = (ROOT / "app_pages" / "npd_apqp.py").read_text()
    osp = (ROOT / "app_pages" / "osp_transactions.py").read_text()
    osp_i = (ROOT / "app_pages" / "osp_inspections.py").read_text()
    qc = (ROOT / "app_pages" / "qc_calculation_tools.py").read_text()
    for token in ("npd_process_flows", "npd_orders", "ppap_projects"):
        assert token in npd and "password_delete_panel" in npd
    assert 'table="osp_jobs"' in osp and 'table="lab_tests"' in osp and 'table="inspection_reports"' in osp
    assert "password_delete_panel" in osp_i
    assert 'table="qc_calculation_records"' in qc


def test_material_number_and_jominy_mm_contract():
    migration = (ROOT / "supabase" / "migrations" / "20260811125500_qcms_delete_save_jominy_cleanup_v499.sql").read_text()
    material = (ROOT / "app_pages" / "material_grade.py").read_text()
    rmtc = (ROOT / "core" / "rmtc_service.py").read_text()
    page = (ROOT / "app_pages" / "rmtc_pages.py").read_text()
    assert "MASTER_MATERIAL_GRADE" in migration and "qcms_next_material_number" in migration
    assert "qcms_next_material_number" in material
    assert "jominy_distance_id" in rmtc and "25.4/16" in rmtc.replace(" ", "")
    assert "'MM':t.get('distance_mm')" in page
