from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_templates_are_packaged():
    expected = {
        "Part_Master_Template.xlsx", "Material_Grade_Template.xlsx",
        "Reference_Masters_Template.xlsx", "Employee_Master_Template.xlsx",
        "RMTC_Entry_Template.xlsx", "Material_Inward_Template.xlsx",
        "Inspection_Layout_Template.xlsx", "Dimensional_Inspection_Report_Template.xlsx",
        "MetLAB_Report_Layout_Template.xlsx",
    }
    assert expected <= {path.name for path in (ROOT / "templates").glob("*.xlsx")}


def test_template_center_and_local_downloads_are_registered():
    app = (ROOT / "streamlit_app.py").read_text()
    assert '("templates", st.Page(template_center.render' in app
    assert 'menu_{path.replace' in app
    for file_name in ["part_master.py", "material_grade.py", "reference_master.py", "employee_master.py", "rmtc_pages.py", "material_inward.py", "inspection_layouts.py", "dimensional_report.py", "metlab_report.py"]:
        assert "template_download_row" in (ROOT / "app_pages" / file_name).read_text()


def test_collision_safe_erp_css_and_unique_menu_colours():
    ui = (ROOT / "core" / "ui.py").read_text()
    assert ".fsi-page-head" in ui and "overflow:visible" in ui
    assert ".fsi-section-bar" in ui and "line-height:1.3" in ui
    for key in ["menu_dashboard", "menu_masters", "menu_rmtc_entry", "menu_inward_entry", "menu_inspection_home", "menu_templates"]:
        assert key in ui
