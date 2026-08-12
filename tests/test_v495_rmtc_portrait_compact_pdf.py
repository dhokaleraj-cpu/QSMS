import re
from pathlib import Path

from reportlab.lib.pagesizes import A4

from core.reporting import rmtc_record_pdf_bytes

ROOT = Path(__file__).resolve().parents[1]


def _payload():
    chemistry = []
    for element, minimum, maximum, actual in [
        ("C", 0.17, 0.22, 0.19), ("Si", 0.15, 0.40, 0.25), ("Mn", 1.10, 1.40, 1.25),
        ("P", 0, 0.025, 0.012), ("S", 0, 0.035, 0.015), ("Cr", 1.0, 1.3, 1.12),
        ("Mo", 0, 0.1, 0.03), ("Ni", 0, 0.4, 0.18), ("Al", 0.02, 0.05, 0.03),
    ]:
        chemistry.append({"part_id": "p1", "element": element, "minimum_value": minimum, "maximum_value": maximum, "actual_value": actual, "unit": "%", "result": "ACCEPTED"})
    jominy = []
    for index in range(10):
        jominy.append({
            "part_id": "p1", "distance_label": f"J{index + 1}", "distance_mm": 1.5 * (index + 1),
            "minimum_hrc": 35, "maximum_hrc": 58, "actual_hrc": 52 - index, "result": "ACCEPTED",
            "calculated_hrc": 51 - index, "calculated_result": "ACCEPTED", "applicability": "APPLICABLE",
        })
    return {
        "record": {
            "rmtc_number": "RMTC-D9-20260802195348", "entry_date": "2026-08-11", "certificate_reference": "SUP-1543",
            "certificate_date": "2026-08-10", "heat_number": "b12345", "heat_code": "A-0007",
            "certificate_quantity": 2250, "rm_section": "60 mm Bar", "forging_route": "Bar + Forging",
            "status": "APPROVAL_PENDING", "validation_result": "APPROVED", "disposition": "ACCEPTED",
            "decision_at": "2026-08-11 10:00", "mechanical_results": {"tensile_strength_mpa": 910},
            "prepared_by_employee_id": "e1", "validated_by_employee_id": "e2", "approved_by_employee_id": "e3",
        },
        "supplier": {"party_name": "Steel Supplier"}, "steel_mill": {"party_name": "Steel Mill"},
        "employees": {
            "e1": {"employee_code": "E001", "first_name": "Prepared", "last_name": "User"},
            "e2": {"employee_code": "E002", "first_name": "Validation", "last_name": "User"},
            "e3": {"employee_code": "E003", "first_name": "Approval", "last_name": "User"},
        },
        "parts": {"p1": {"id": "p1", "part_number": "71.784.3", "part_name": "Differential Spider", "material_grade_id": "g1"}},
        "material_grades": {"g1": {"id": "g1", "grade_code": "20MnCr5"}},
        "part_approvals": [{
            "part_id": "p1", "planned_production_quantity_pcs": 200, "input_weight_kg": 3.05,
            "planned_steel_quantity_kg": 610, "worksheet_completed_at": "2026-08-11", "grain_size": "7-8",
            "actual_di": 2.1, "actual_di_status": "ACCEPTED", "calculated_di": 2.0, "calculated_di_status": "ACCEPTED",
            "source_status": "ACCEPTED", "material_grade_status": "ACCEPTED", "raw_material_status": "ACCEPTED",
            "chemistry_status": "ACCEPTED", "jominy_status": "ACCEPTED", "requirement_status": "ACCEPTED",
            "approval_status": "ACCEPTED", "disposition": "ACCEPTED", "decision_reason": "PASS",
        }],
        "chemistry": chemistry,
        "jominy": jominy,
        "requirements": [
            {"part_id": "p1", "requirement_name": "Tensile Strength", "requirement_value": "850 MPa Min", "actual_value": "910", "unit": "MPa", "result": "ACCEPTED", "remarks": ""},
            {"part_id": "p1", "requirement_name": "Case Depth", "requirement_value": "0.95-1.35 mm", "actual_value": "1.236", "unit": "mm", "result": "ACCEPTED", "remarks": ""},
        ],
    }


def test_release_version_and_notes():
    assert (ROOT / "VERSION").read_text().strip() in {"4.9.5", "4.9.6", "4.9.7", "4.9.8", "4.9.9", "4.10.0", "4.10.1", "4.10.2", "4.10.3"}
    assert (ROOT / "docs" / "RELEASE_4_9_5.md").exists()


def test_rmtc_source_is_a4_portrait_and_has_common_edges():
    source = (ROOT / "core" / "reporting.py").read_text()
    start = source.index("def rmtc_record_pdf_bytes")
    rmtc_source = source[start:]
    assert "pagesize=A4" in rmtc_source
    assert "leftMargin=edge" in rmtc_source
    assert "rightMargin=edge" in rmtc_source
    assert "content_width = page_width - (2 * edge)" in rmtc_source
    assert "PageBreak()" not in rmtc_source
    assert "CondPageBreak" in rmtc_source


def test_rmtc_generated_pdf_is_portrait_and_compact():
    pdf = rmtc_record_pdf_bytes(_payload())
    assert pdf.startswith(b"%PDF")
    # ReportLab writes A4 portrait as approximately 595 x 842 points.
    match = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]", pdf)
    assert match, "PDF MediaBox missing"
    width = float(match.group(1))
    height = float(match.group(2))
    assert width < height
    assert abs(width - A4[0]) < 1.0
    assert abs(height - A4[1]) < 1.0
    # A representative one-part record should remain within two pages.
    page_objects = len(re.findall(rb"/Type\s*/Page(?!s)", pdf))
    assert 1 <= page_objects <= 2
