from pathlib import Path

from core.reporting import rmtc_record_pdf_bytes


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_and_notes():
    assert (ROOT / "VERSION").read_text().strip() in {"4.9.4", "4.9.5", "4.9.6", "4.9.7", "4.9.8", "4.9.9", "4.10.0", "4.10.1", "4.10.2", "4.10.3", "4.10.5", "4.10.6", "4.10.7", "4.10.8", "4.10.9", "4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1"}
    assert (ROOT / "docs" / "RELEASE_4_9_4.md").exists()


def test_workflow_cards_are_spacious_and_colour_separated():
    ui = (ROOT / "core" / "ui.py").read_text()
    assert "fsi-flow-tone-0" in ui
    assert "fsi-flow-tone-7" in ui
    assert "min-height:84px" in ui
    assert "overflow-x:auto" in ui
    assert '"current": "●"' in ui
    assert '"pending": "○"' in ui


def test_osp_home_uses_progress_chart_not_repeated_workflow_links():
    source = (ROOT / "app_pages" / "osp_transactions.py").read_text()
    assert "workflow_progress([" in source
    assert '"Production Release"' in source
    assert 'section_bar("OSP WORKFLOW")' in source


def test_rmtc_records_exposes_pdf_download():
    source = (ROOT / "app_pages" / "rmtc_pages.py").read_text()
    assert "rmtc_record_pdf_bytes" in source
    assert "Download RMTC Record PDF" in source
    service = (ROOT / "core" / "rmtc_service.py").read_text()
    assert "def report_payload" in service


def test_rmtc_pdf_contains_all_major_grid_sections():
    payload = {
        "record": {
            "id": "r1",
            "rmtc_number": "QSMS-RMTC-2026-0001",
            "entry_date": "2026-08-11",
            "certificate_reference": "SUP-1543",
            "certificate_date": "2026-08-10",
            "heat_number": "A41489",
            "heat_code": "H-2862",
            "certificate_quantity": 2250,
            "rm_section": "Bar 60 mm",
            "forging_route": "Bar + Forging",
            "status": "APPROVAL_PENDING",
            "validation_result": "APPROVED",
            "disposition": "ACCEPTED",
            "decision_at": "2026-08-11 10:00",
            "decision_reason": "All requirements meet Part Master specification.",
            "mechanical_results": {"tensile_strength_mpa": 910, "elongation_percent": 13},
            "prepared_by_employee_id": "e1",
            "validated_by_employee_id": "e2",
            "approved_by_employee_id": "e3",
        },
        "supplier": {"party_code": "SUP01", "party_name": "Steel Supplier"},
        "steel_mill": {"party_code": "MILL01", "party_name": "Steel Mill"},
        "employees": {
            "e1": {"employee_code": "E001", "first_name": "Prepared", "last_name": "User"},
            "e2": {"employee_code": "E002", "first_name": "Validation", "last_name": "User"},
            "e3": {"employee_code": "E003", "first_name": "Approval", "last_name": "User"},
        },
        "parts": {
            "p1": {"id": "p1", "part_number": "7237", "part_name": "Diff Pin", "material_grade_id": "g1"},
        },
        "material_grades": {"g1": {"id": "g1", "grade_code": "SAE8620"}},
        "part_approvals": [{
            "part_id": "p1",
            "planned_production_quantity_pcs": 1500,
            "input_weight_kg": 1.5,
            "planned_steel_quantity_kg": 2250,
            "worksheet_completed_at": "2026-08-11",
            "grain_size": "7-8",
            "actual_di": 2.1,
            "actual_di_status": "ACCEPTED",
            "calculated_di": 2.0,
            "calculated_di_status": "ACCEPTED",
            "source_status": "ACCEPTED",
            "material_grade_status": "ACCEPTED",
            "raw_material_status": "ACCEPTED",
            "chemistry_status": "ACCEPTED",
            "jominy_status": "ACCEPTED",
            "requirement_status": "ACCEPTED",
            "approval_status": "ACCEPTED",
            "disposition": "ACCEPTED",
            "decision_reason": "Pass",
        }],
        "chemistry": [{
            "part_id": "p1", "element": "C", "minimum_value": 0.18, "maximum_value": 0.23,
            "actual_value": 0.20, "unit": "%", "result": "ACCEPTED",
        }],
        "jominy": [{
            "part_id": "p1", "distance_label": "J1", "distance_mm": 1.5,
            "minimum_hrc": 45, "maximum_hrc": 55, "actual_hrc": 50, "result": "ACCEPTED",
            "calculated_hrc": 49, "calculated_result": "ACCEPTED", "applicability": "APPLICABLE",
        }],
        "requirements": [
            {"part_id": "p1", "requirement_name": "Tensile Strength", "requirement_value": "850 MPa Min", "actual_value": "910", "unit": "MPa", "result": "ACCEPTED", "remarks": ""},
            {"part_id": "p1", "requirement_name": "Case Depth", "requirement_value": "0.95-1.35 mm", "actual_value": "1.236", "unit": "mm", "result": "ACCEPTED", "remarks": ""},
        ],
    }
    pdf = rmtc_record_pdf_bytes(payload)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 5000
