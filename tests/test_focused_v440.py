from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_password_delete_service_and_rpc_are_present():
    assert "verify_current_password" in (ROOT / "core/delete_service.py").read_text()
    sql = (ROOT / "supabase/migrations/20260802050000_qsms_password_protected_delete.sql").read_text()
    assert "qsms_delete_master_row" in sql
    assert "can_archive" in sql


def test_master_grids_do_not_silently_delete_missing_rows():
    part = (ROOT / "app_pages/part_master.py").read_text()
    grade = (ROOT / "app_pages/material_grade.py").read_text()
    assert "Missing rows are preserved until password deletion" in part
    assert 'repo.delete("material_grade_elements"' not in grade
    assert "Delete Chemical Composition row" in grade


def test_subpages_have_backward_navigation():
    for file_name in ["part_master.py", "material_grade.py", "reference_master.py", "employee_master.py", "rmtc_pages.py", "user_access.py", "inspection_layouts.py", "dimensional_report.py", "metlab_report.py"]:
        assert "subpage_navigation" in (ROOT / "app_pages" / file_name).read_text()
    assert "Back to Masters" in (ROOT / "app_pages/part_master.py").read_text()


def test_export_shipment_style_theme_and_cards():
    ui = (ROOT / "core/ui.py").read_text()
    assert "#1469A8" in ui
    assert "#EEF2F5" in ui
    assert "master_card_" in ui
    assert "taglines and context" in ui
    home = (ROOT / "app_pages/master_home.py").read_text()
    assert "Master Data Centre" in home
    assert "Inspection Layouts" in home


def test_user_permission_label_is_delete():
    text = (ROOT / "app_pages/user_access.py").read_text()
    assert ("'Delete':bool(row.get('can_archive'" in text or '"Delete/Archive"' in text)
    assert "row['Delete']" in text or 'row["Delete/Archive"]' in text
