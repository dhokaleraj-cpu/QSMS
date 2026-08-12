from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_and_migration():
    assert (ROOT / "VERSION").read_text().strip() in {"4.10.0", "4.10.1", "4.10.2", "4.10.3", "4.10.4"}
    migration = ROOT / "supabase/migrations/20260812113000_qcms_universal_delete_account_import_print_v4100.sql"
    text = migration.read_text()
    assert "rmtc_jominy_results" in text
    assert "npd_order_step_points" in text
    assert "current_app_role" in text and "can_archive" in text


def test_login_has_no_first_administrator_field_and_account_password_change():
    auth = (ROOT / "core/auth.py").read_text()
    login = auth[auth.index("def render_login"):auth.index("def render_first_admin_claim")]
    assert "First administrator" not in login
    account = (ROOT / "app_pages/my_account.py").read_text()
    assert "Current Password" in account
    assert "Confirm New Password" in account
    assert 'auth.update_user({"password": new_password})' in account


def test_master_import_upload_is_available_from_master_templates():
    ui = (ROOT / "core/ui.py").read_text()
    importer = (ROOT / "app_pages/master_import.py").read_text()
    assert "Import / Upload Master File" in ui
    assert 'st.file_uploader("Upload completed master file"' in importer
    assert '"parts", "Part Master"' in importer
    assert '"employees", "Employee Master"' in importer


def test_pending_order_status_is_one_screen_matrix_with_pdf():
    page = (ROOT / "app_pages/npd_apqp.py").read_text()
    assert "ORDER PROCESS STATUS · ALL PENDING PARTS" in page
    assert "npd-order-status-row" in page
    assert "npd_pending_status_pdf_bytes" in page
    assert "Print / Download Pending Order Process Status PDF" in page


def test_metlab_and_rmtc_microstructure_photo_titles():
    standard = (ROOT / "app_pages/metlab_report.py").read_text()
    osp = (ROOT / "app_pages/osp_inspections.py").read_text()
    rmtc = (ROOT / "app_pages/rmtc_pages.py").read_text()
    assert 'f"Photo {slot} Title"' in standard
    assert 'f"Photo {slot} Title"' in osp
    assert "microstructure_caption_" in osp
    assert "Photo {slot} Title" in rmtc
    assert "microstructure_titles" in rmtc


def test_viewer_friendly_record_register_pdf_and_entry_delete_panels():
    records = (ROOT / "app_pages/records_center.py").read_text()
    assert "Print / Download PDF" in records
    assert "controlled_record_pdf_bytes" in records
    for filename in ("rmtc_pages.py", "material_inward.py", "metlab_report.py", "dimensional_report.py", "employee_master.py"):
        text = (ROOT / "app_pages" / filename).read_text()
        assert "password_delete_panel" in text
