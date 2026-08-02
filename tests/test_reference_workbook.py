from __future__ import annotations

from pathlib import Path

from core.reference_import import parse_reference_workbook

ROOT = Path(__file__).resolve().parents[1]


def test_uploaded_reference_workbook_is_parsed() -> None:
    preview = parse_reference_workbook((ROOT / "data" / "Quality Monitoring System.xlsx").read_bytes())
    assert preview.part["part_number"] == "71.784.3"
    assert preview.part["part_name"] == "Differential Spider"
    assert preview.customer["party_name"]
    assert preview.suppliers
    assert preview.material_grade["grade_code"]
    assert preview.chemistry
    assert preview.processes


def test_reference_parser_retains_source_warnings() -> None:
    preview = parse_reference_workbook((ROOT / "data" / "Quality Monitoring System.xlsx").read_bytes())
    assert any("Steel-mill" in warning for warning in preview.warnings)
    assert any("drawing" in warning.lower() for warning in preview.warnings)
