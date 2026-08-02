from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_rmtc_part_worksheet_has_production_plan():
    page = (ROOT / "app_pages/rmtc_pages.py").read_text()
    service = (ROOT / "core/rmtc_service.py").read_text()
    for token in ["Part Production Quantity (pcs)", "Planned Steel Quantity (kg)"]:
        assert token in page
    assert "RMTC Steel Balance after Plan (kg)" in page or "Heat Steel Balance after Plan (kg)" in page
    assert "planned_production_quantity_pcs" in service
    assert "planned_steel_quantity_kg" in service


def test_inward_breakdown_is_piece_driven():
    page = (ROOT / "app_pages/material_inward.py").read_text()
    for token in ["accepted_production_quantity_pcs", "rejected_production_quantity_pcs", "hold_production_quantity_pcs", "accepted_steel_quantity_kg", "rejected_steel_quantity_kg", "hold_steel_quantity_kg"]:
        assert token in page
    assert "Total Production Quantity (pcs)" in page
    assert "Total Steel Quantity (kg)" in page


def test_heat_and_part_limits_are_database_enforced():
    sql = (ROOT / "supabase/migrations/20260802150000_qsms_heat_production_microstructure_v481.sql").read_text()
    for token in ["Cumulative heat production steel", "Cumulative production", "planned_production_quantity_pcs", "v_qsms_heat_production_summary", "qsms_submit_rmtc"]:
        assert token in sql


def test_metlab_supports_four_microstructure_images():
    page = (ROOT / "app_pages/metlab_report.py").read_text()
    sql = (ROOT / "supabase/migrations/20260802150000_qsms_heat_production_microstructure_v481.sql").read_text()
    assert "MICROSTRUCTURE PHOTOS" in page
    assert "range(1,5)" in page.replace(" ", "") or "range(1, 5)" in page
    for slot in range(1,5):
        assert f"microstructure_image_{slot}_path" in sql
        assert f"microstructure_caption_{slot}" in sql


def test_rmtc_part_save_uses_bulk_upsert():
    service = (ROOT / "core/rmtc_service.py").read_text()
    assert "bulk_upsert('rmtc_chemistry_results'" in service
    assert "bulk_upsert('rmtc_jominy_results'" in service
    assert "bulk_upsert('rmtc_requirement_results'" in service
