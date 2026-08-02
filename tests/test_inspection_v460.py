from pathlib import Path

from core.dimensional_import import parse_dimensional_workbook_bytes

ROOT = Path(__file__).resolve().parents[1]


def test_uploaded_dimensional_layout_is_parsed():
    parsed = parse_dimensional_workbook_bytes((ROOT / "data/Dimensional Report.xlsx").read_bytes(), "Dimensional Report.xlsx")
    assert parsed["metadata"]["report_title"] == "PRE-DISPATCH INSPECTION REPORT"
    assert parsed["metadata"]["format_number"] == "FSI/804/F03"
    assert parsed["metadata"]["default_sample_size"] == 6
    assert parsed["metadata"]["part_number"] == "40256626"
    assert len(parsed["characteristics"]) == 34
    assert parsed["characteristics"][0]["checking_aid_text"] == "AIR GAUGE"


def test_rmtc_draft_can_be_submitted_to_pending_from_entry():
    text = (ROOT / "app_pages/rmtc_pages.py").read_text()
    assert "Submit Draft → Pending" in text
    assert "qsms_submit_rmtc" in text
    assert "Validator" in text and "Approver" in text


def test_inspection_layout_and_report_pages_are_registered():
    text = (ROOT / "streamlit_app.py").read_text()
    for path in ["inspection-home", "inspection-layout-entry", "inspection-layout-records", "dimensional-entry", "dimensional-records", "metlab-entry", "metlab-records"]:
        assert f'url_path="{path}"' in text


def test_post_inward_gate_is_packaged():
    sql = (ROOT / "supabase/migrations/20260802065000_qsms_inspection_workflow_v460.sql").read_text()
    for token in ["qsms_refresh_inward_quality_gate", "qsms_finalize_dimensional_report", "qsms_finalize_metlab_report", "ACCEPTED_UNDER_RESERVE", "quality_disposition"]:
        assert token in sql


def test_layouts_are_linked_to_part_process_and_stage():
    page = (ROOT / "app_pages/inspection_layouts.py").read_text()
    for token in ["Part Number", "Process", "Inspection Stage", "Import Dimensional Layout"]:
        assert token in page


def test_material_inward_links_both_required_validations():
    page = (ROOT / "app_pages/material_inward.py").read_text()
    assert "Open MetLAB Report" in page
    assert "Open Dimensional Report" in page
    assert "metallurgical_status" in page
    assert "dimensional_status" in page
