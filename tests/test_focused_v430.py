from pathlib import Path
from core.calculations import calculate_di, calculate_jominy_curve

ROOT = Path(__file__).resolve().parents[1]


def test_five_compact_top_navigation_workspaces():
    text = (ROOT / "streamlit_app.py").read_text()
    for label in ["Dashboard", "Masters", "RMTC", "Inward", "Inspections"]:
        assert f'"{label}"' in text
    assert "supply-traceability" in text
    assert "Supply Chain" in text


def test_record_pages_are_separate():
    text = (ROOT / "streamlit_app.py").read_text()
    for path in [
        "part-records", "grade-records", "reference-records", "employee-records",
        "rmtc-records", "inward-records", "inspection-layout-records",
        "dimensional-records", "metlab-records",
    ]:
        assert f'url_path="{path}"' in text


def test_material_grade_embeds_chemistry():
    text = (ROOT / "app_pages/material_grade.py").read_text()
    assert "CHEMICAL COMPOSITION" in text
    assert "material_grade_elements" in text


def test_employee_code_is_auto_and_editable():
    text = (ROOT / "app_pages/employee_master.py").read_text()
    assert "Auto on save" in text
    assert "qsms_next_employee_code" in text


def test_jominy_and_di_formulas_match_workbooks():
    curve = calculate_jominy_curve({"C": 0.1912, "MN": 0.7805, "CR": 0.509, "NI": 0.419, "MO": 0.158})
    assert round(curve[1], 3) == 43.672
    assert round(curve[4], 3) == 31.03
    di = calculate_di({"C": 0.22, "MN": 0.85, "SI": 0.25, "NI": 0.018, "CR": 1.18, "MO": 0.004, "CU": 0.012, "V": 0.005}, 6)
    assert abs(di["value"] - 2.1082) < 0.001


def test_rmtc_has_single_combined_jominy_grid_and_multi_part_pages():
    text = (ROOT / "app_pages/rmtc_pages.py").read_text()
    for token in ["Actual Jominy", "Actual Jominy Status", "Calculated Jominy", "Calculated Jominy Status", "Part Worksheet", "NOT_APPLICABLE", "RMTC Certificate / Copy"]:
        assert token in text


def test_module_permission_control_is_present():
    assert "user_module_permissions" in (ROOT / "app_pages/user_access.py").read_text()
    assert "qsms_has_module_write" in (ROOT / "supabase/migrations/20260802043000_qsms_focused_v430.sql").read_text()
