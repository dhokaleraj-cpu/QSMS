from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_jominy_mm_is_derived_from_inches_in_ui_and_database():
    page = (ROOT / "app_pages" / "part_master.py").read_text()
    service = (ROOT / "core" / "rmtc_service.py").read_text()
    migration = (ROOT / "supabase" / "migrations" / "20260802074100_qsms_jominy_catalog_dispositions_v471.sql").read_text()
    assert '"Distance (inch)"' in page
    assert '"MM (Auto)"' in page
    assert "25.4 / 16" in page
    assert "25.4/16" in service
    assert "new.distance_mm := round" in migration
    assert "trg_sync_jominy_distance" in migration


def test_reusable_section_route_and_simplified_metlab_requirements():
    page = (ROOT / "app_pages" / "part_master.py").read_text()
    for token in [
        "part.rm_section", "part.forging_route",
        "Manage reusable Raw Material Type, Section Size and Forging Route lists",
        "OSP INSPECTION FOR METLAB", "METALLURGICAL REQUIREMENTS",
        "Minimum Specification", "Maximum Specification",
    ]:
        assert token in page
    assert "HEAT TREATMENT DETAILS" not in page
    assert "OSP PROCESS & INWARD SPECIFICATIONS" not in page


def test_complete_disposition_lists_include_on_hold():
    rmtc = (ROOT / "app_pages" / "rmtc_pages.py").read_text()
    inward = (ROOT / "app_pages" / "material_inward.py").read_text()
    inspection = (ROOT / "core" / "inspection_service.py").read_text()
    migration = (ROOT / "supabase" / "migrations" / "20260802074100_qsms_jominy_catalog_dispositions_v471.sql").read_text()
    for text in [rmtc, inward, inspection, migration]:
        assert "ON_HOLD" in text
        assert "ACCEPTED_UNDER_RESERVE" in text
        assert "REJECTED" in text
    for text in [rmtc, inward, migration]:
        assert "PENDING" in text


def test_dashboard_keeps_horizontal_bars_and_adds_requested_pies():
    dashboard = (ROOT / "app_pages" / "dashboard.py").read_text()
    assert dashboard.count('orientation="h"') >= 2
    assert "px.pie" in dashboard
    assert "Recent Inwards" in dashboard
    assert "RMTC Validation Status" in dashboard
    assert "Inward Status" in dashboard


def test_menu_and_submenu_text_is_forced_visible():
    ui = (ROOT / "core" / "ui.py").read_text()
    assert '[class*="st-key-menu_active_"] div[data-testid="stPageLink"] a *' in ui and 'color:#fff!important' in ui
    assert '.st-key-fsi_subnav div[data-testid="stPageLink"] a *{color:inherit!important' in ui
    assert '[class*="st-key-master_card_"] div[data-testid="stPageLink"] a *{color:#fff!important' in ui
