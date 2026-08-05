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
    assert 'menu_active_{slug}' in app and 'menu_{slug}' in app
    for file_name in ["part_master.py", "material_grade.py", "reference_master.py", "employee_master.py", "rmtc_pages.py", "material_inward.py", "inspection_layouts.py", "dimensional_report.py", "metlab_report.py"]:
        assert "template_download_row" in (ROOT / "app_pages" / file_name).read_text()


def test_collision_safe_erp_css_and_unique_menu_colours():
    ui = (ROOT / "core" / "ui.py").read_text()
    assert ".fsi-page-head" in ui and "overflow:visible" in ui
    assert ".fsi-section-bar" in ui and "line-height:1.3" in ui
    assert '[class*="st-key-menu_"]' in ui
    assert '[class*="st-key-menu_active_"]' in ui
    assert 'linear-gradient(100deg,#08477D,#0D78C7)' in ui
