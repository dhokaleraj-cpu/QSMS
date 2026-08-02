from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_part_master_has_supplier_input_weight():
    text = (ROOT / "app_pages/part_master.py").read_text()
    assert "Input Weight kg/part" in text
    assert '"input_weight_kg"' in text


def test_material_inward_uses_steel_and_production_formula():
    text = (ROOT / "app_pages/material_inward.py").read_text()
    for token in ["Accepted Production Quantity (pcs)", "Rejected Production Quantity (pcs)", "On Hold Production Quantity (pcs)", "Total Steel Quantity (kg)"]:
        assert token in text
    assert "production_qty = float(accepted_pcs) + float(rejected_pcs) + float(hold_pcs)" in text
    assert "required_steel = round(production_qty * input_weight, 3)" in text


def test_layout_is_automatic_with_manual_override():
    dimensional = (ROOT / "app_pages/dimensional_report.py").read_text()
    metlab = (ROOT / "app_pages/metlab_report.py").read_text()
    for text in [dimensional, metlab]:
        assert '"Automatic", "Manual"' in text
        assert "Layout Name" in text
        assert "Section / Layout Type" in text
    assert "ranked_plans" in (ROOT / "core/inspection_service.py").read_text()


def test_metlab_matches_rmtc_part_worksheet_sections():
    text = (ROOT / "app_pages/metlab_report.py").read_text()
    for token in ["CHEMICAL COMPOSITION", "JOMINY HARDENABILITY", "HEAT TREATMENT / MECHANICAL REQUIREMENTS", "RMTC Actual"]:
        assert token in text
    service = (ROOT / "core/inspection_service.py").read_text()
    assert "rmtc_material_snapshot" in service
    assert "chemistry_rows" in service


def test_bulk_upsert_reduces_report_save_round_trips():
    repo = (ROOT / "core/repository.py").read_text()
    service = (ROOT / "core/inspection_service.py").read_text()
    assert "def bulk_upsert" in repo
    assert 'bulk_upsert("inspection_results"' in service
    assert 'bulk_upsert("inspection_plan_characteristics"' in service


def test_v480_database_guards_are_packaged():
    sql = (ROOT / "supabase/migrations/20260802133000_qsms_steel_production_layout_v480.sql").read_text()
    for token in ["steel_quantity_kg", "production_quantity_pcs", "input_weight_kg", "required_steel_quantity_kg", "v_qsms_accepted_rmtc_parts"]:
        assert token in sql
    guard = (ROOT / "supabase/migrations/20260802133100_qsms_steel_production_allocation_guard_v480.sql").read_text()
    assert "allocated_to_batches>production_qty" in guard
