from __future__ import annotations

from core.master_definitions import DEFINITIONS, MASTER_BY_KEY, MASTER_GROUPS


def test_controlled_master_views() -> None:
    assert len(DEFINITIONS) == 15
    assert len(MASTER_BY_KEY) == 15
    assert set(MASTER_GROUPS) == {"Parties", "Product & Material", "Process & Quality", "Standards & Specifications"}


def test_core_master_keys_are_present() -> None:
    required = {
        "customers", "suppliers", "steel_mills", "osp_vendors", "customer_standards", "parts",
        "material_grades", "chemical_composition", "approved_sources",
        "processes", "inspection_stages", "quality_assets", "inspection_plans",
        "inspection_characteristics", "test_plans",
    }
    assert set(MASTER_BY_KEY) == required


def test_every_master_has_controlled_key_and_fields() -> None:
    for definition in DEFINITIONS:
        assert definition.table
        assert definition.natural_key
        assert definition.fields
        names = {field.name for field in definition.fields}
        assert set(definition.natural_key).issubset(names)
