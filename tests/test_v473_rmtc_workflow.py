from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v473_atomic_rmtc_save_and_admin_override() -> None:
    service = (ROOT / "core" / "rmtc_service.py").read_text()
    pages = (ROOT / "app_pages" / "rmtc_pages.py").read_text()
    assert "qsms_save_rmtc_header" in service
    assert "worksheet_completed_at" in service
    assert "Manual acceptance reason is mandatory" in pages
    assert "Admin · Reopen Decision for Change" in pages


def test_v473_blank_new_entry_and_explicit_edit() -> None:
    pages = (ROOT / "app_pages" / "rmtc_pages.py").read_text()
    app = (ROOT / "streamlit_app.py").read_text()
    assert "rmtc_entry_mode" in pages
    assert "Start New RMTC" in pages
    assert "_open_rmtc_header_for_edit" in pages
    assert "top_menu_new_rmtc" in app


def test_v473_workflow_and_status_colors() -> None:
    ui = (ROOT / "core" / "ui.py").read_text()
    pages = (ROOT / "app_pages" / "rmtc_pages.py").read_text()
    assert "def workflow_progress" in ui
    assert "fsi-flow-complete" in ui
    assert "fsi-flow-rejected" in ui
    assert "DISPOSITION_EDITOR_OPTIONS" in ui
    assert "workflow_progress(_workflow_steps" in pages
    assert "style_status_dataframe" in pages


def test_v473_default_material_elements_remain_available() -> None:
    grade = (ROOT / "app_pages" / "material_grade.py").read_text()
    for element in ("C", "Si", "Mn", "P", "S", "Cr", "Mo", "Ni"):
        assert repr(element) in grade or f'"{element}"' in grade
