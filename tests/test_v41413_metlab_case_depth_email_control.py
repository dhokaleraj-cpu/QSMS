from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from core.reporting import metlab_record_pdf_bytes

ROOT = Path(__file__).resolve().parents[1]
BUILD = "41413-METLAB-CASE-DEPTH-RECORD-EMAIL-TEMPLATE-TEST-CONFIRM"


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v41413_version_and_live_build_marker() -> None:
    assert (ROOT / "VERSION").read_text().strip() in {"4.14.13", "4.14.14", "4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.24"}
    app = _text("streamlit_app.py")
    assert BUILD in app
    assert f"# BUILD {BUILD}" in app


def test_v41413_metlab_case_depth_locations_and_persistence() -> None:
    metlab = _text("app_pages/metlab_report.py")
    service = _text("core/inspection_service.py")
    assert "CASE_DEPTH_DEFAULT_DISTANCES = [0.05" in metlab
    assert "CASE_DEPTH_DEFAULT_LOCATIONS" in metlab
    assert "Ground Face" in metlab and '"ID"' in metlab and '"OD"' in metlab
    assert "Case Depth Locations" in metlab
    assert "CASE DEPTH / MICROHARDNESS TRAVERSE" in metlab
    assert "must start at 0.05 mm" in metlab
    assert '"case_depth_locations"' in service
    assert '"case_depth_traverse"' in service
    assert '"case_depth_applicable"' in service


def test_v41413_metlab_pdf_contains_multi_location_traverse() -> None:
    pdf = metlab_record_pdf_bytes({
        "record": {
            "report_number": "MLAB-D9-26-00008",
            "test_date": "2026-08-26",
            "sample_reference": "Random actual part cut after grinding.",
            "inspection_scope": "MATERIAL_INWARD",
            "overall_result": "PASS",
            "disposition": "ACCEPTED",
        },
        "results": {
                "rows": [
                    {"sequence_no": 1, "characteristic": "Surface Hardness After Grinding", "specification": "55-60 HRC", "observations": [58, 58, 59], "unit": "HRC", "result": "PASS"},
                    {"sequence_no": 2, "characteristic": "Effective Case Depth at Ground Face", "specification": "0.20-0.55 mm at 513 HV1", "observations": [0.50], "unit": "mm", "result": "PASS"},
                ],
                "case_depth_applicable": True,
                "case_depth_locations": [
                    {"location": "Ground Face", "remark": ""},
                    {"location": "ID", "remark": ""},
                    {"location": "OD", "remark": ""},
                ],
                "case_depth_traverse": [
                    {"distance_mm": 0.05, "readings": {"Ground Face": 760, "ID": 775, "OD": 768}},
                    {"distance_mm": 0.10, "readings": {"Ground Face": 715, "ID": 746, "OD": 728}},
                    {"distance_mm": 0.20, "readings": {"Ground Face": 680, "ID": 690, "OD": 716}},
                    {"distance_mm": 0.30, "readings": {"Ground Face": 632, "ID": 601, "OD": 664}},
                    {"distance_mm": 0.40, "readings": {"Ground Face": 578, "ID": 577, "OD": 582}},
                    {"distance_mm": 0.50, "readings": {"Ground Face": 513, "ID": 527, "OD": 524}},
                    {"distance_mm": 0.60, "readings": {"Ground Face": 475, "ID": 481, "OD": 483}},
                ],
            },
        "part": {"part_number": "2731", "part_name": "Bush"},
        "customer": {"party_name": "K Drive"},
        "supplier": {"party_name": "PM"},
        "material_grade": {"grade_code": "16MnCr5"},
        "inward": {"heat_number": "H4588", "heat_code": "4588", "production_quantity_pcs": 4000},
        "app_version": "4.14.13",
    })
    assert pdf.startswith(b"%PDF")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)
    assert "CASE DEPTH / MICROHARDNESS TRAVERSE" in text
    assert "CASE DEPTH TRAVERSE" in text
    assert "Ground Face" in text and "ID" in text and "OD" in text
    assert "0.05" in text


def test_v41413_record_email_template_test_and_modal_confirmation() -> None:
    ui = _text("core/notification_ui.py")
    settings = _text("app_pages/email_settings.py")
    assert "@st.dialog" in ui
    assert "Notification To" in ui and "Notification CC" in ui
    assert "Review & Confirm Email Recipients" in ui
    assert "def record_email_sender" in ui and "Review & Send Email" in ui
    assert "def template_test_sender" in ui
    assert "Manual Test Recipient" in ui and "Manual Test CC" in ui
    assert "Confirm Template Test Email" in ui
    assert "template_test_sender(" in settings


def test_v41413_saved_record_email_available_across_controlled_modules() -> None:
    for path in (
        "app_pages/metlab_report.py",
        "app_pages/dimensional_report.py",
        "app_pages/rmtc_pages.py",
        "app_pages/supply_chain.py",
        "app_pages/osp_transactions.py",
    ):
        text = _text(path)
        assert "record_email_sender(" in text, path
        assert "notification_overrides(" in text, path
