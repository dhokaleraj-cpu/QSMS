from pathlib import Path

from core.steel_balance import (
    available_for_selected_inward,
    committed_heat_steel,
    projected_part_plan_commitment,
    remaining_planned_steel,
)

ROOT = Path(__file__).resolve().parents[1]


def test_v485_version_and_packaged_migration():
    assert (ROOT / "VERSION").read_text().strip() in {"4.8.5", "4.8.6", "4.8.7", "4.8.8", "4.9.0", "4.9.1", "4.9.2", "4.9.3", "4.9.4", "4.9.5", "4.9.6", "4.9.7", "4.9.8", "4.9.9", "4.10.0", "4.10.1", "4.10.2", "4.10.3", "4.10.5", "4.10.6", "4.10.7", "4.10.8", "4.10.9", "4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0"}
    sql = (ROOT / "supabase/migrations/20260802201500_qsms_combined_heat_balance_v485.sql").read_text()
    for token in [
        "remaining_planned_steel_quantity_kg",
        "committed_steel_quantity_kg",
        "available_steel_for_selected_entry_kg",
        "Inward % kg + Remaining planned % kg",
        "trg_global_heat_inward_limit",
    ]:
        assert token in sql


def test_heat_commitment_avoids_double_counting_inward_against_plan():
    rows = [
        {"planned_steel_quantity_kg": 235, "inward_steel_quantity_kg": 235},
        {"planned_steel_quantity_kg": 610, "inward_steel_quantity_kg": 0},
    ]
    assert committed_heat_steel(235, rows) == 845
    assert remaining_planned_steel(235, 235) == 0
    assert remaining_planned_steel(610, 0) == 610


def test_selected_inward_can_consume_its_reserved_plan():
    # Global 1000, inward 235, another plan reserves 0: selected 610 kg plan can be inwarded.
    assert available_for_selected_inward(1000, 235, 0) == 765
    # When another part still reserves 200 kg, the selected entry is limited to 565 kg.
    assert available_for_selected_inward(1000, 235, 200) == 565


def test_projected_rmtc_plan_checks_inward_plus_remaining_plans():
    assert projected_part_plan_commitment(235, 100, 610, 0) == 945
    assert projected_part_plan_commitment(235, 100, 610, 200) == 745


def test_material_inward_ui_uses_before_and_after_heat_balance():
    page = (ROOT / "app_pages/material_inward.py").read_text()
    for token in [
        "Heat Steel Available Before Entry (kg)",
        "Heat Steel Balance After Entry (kg)",
        "available_steel_for_selected_entry_kg",
        "Total production steel",
    ]:
        assert token in page


def test_rmtc_ui_uses_combined_heat_commitment():
    page = (ROOT / "app_pages/rmtc_pages.py").read_text()
    for token in [
        "Remaining Planned Steel",
        "Committed Heat steel",
        "projected_commitment",
        "Heat Steel Balance after Plan (kg)",
    ]:
        assert token in page
