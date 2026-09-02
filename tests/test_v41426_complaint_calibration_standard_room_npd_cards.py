from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41426_release_identity_and_manifest():
    assert text("VERSION").strip() == "4.14.26"
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] == "4.14.26"
    assert manifest["build"] == "41426-COMPLAINT-MEDIA-CALIBRATION-STANDARD-ROOM-NPD-CARDS"
    assert manifest["database_schema_required"] == "4.14.26"
    assert manifest["database_migration_required"] is False
    assert manifest["registered_pages"] == 83
    assert "41426-COMPLAINT-MEDIA-CALIBRATION-STANDARD-ROOM-NPD-CARDS" in text("streamlit_app.py")


def test_complaints_capture_heat_batch_and_embed_photos_in_pdf_excel():
    source = text("app_pages/complaints.py")
    reporting = text("core/reporting.py")
    for marker in (
        'text_input("Heat Number"', 'text_input("Batch Code / Lot Number"',
        '"heat_number"', '"lot_batch_number"', '"Heat Number": row.get("heat_number")',
        '"Batch Code / Lot Number": row.get("lot_batch_number")',
        'Download Excel + Photos', '_complaint_excel', 'images_title="COMPLAINT PHOTOGRAPHS"',
    ):
        assert marker in source
    for ext in ('"png"','"jpg"','"jpeg"','"bmp"','"tif"','"tiff"','"webp"','"gif"'):
        assert ext in source
    assert "def _photo_grid_table" in reporting
    assert "images_title" in reporting


def test_supply_chain_home_prioritizes_overdue_orders_with_red_cards():
    source = text("app_pages/supply_chain.py")
    assert "PRIORITY · OVERDUE CUSTOMER ORDERS" in source
    assert "#FEF2F2" in source
    assert "#B91C1C" in source
    assert "day(s) overdue" in source


def test_calibration_validation_module_and_navigation_are_registered():
    access = text("core/access.py")
    app = text("streamlit_app.py")
    page = text("app_pages/calibration_validation.py")
    assert '("CALIBRATION_VALIDATION", "Calibration & Validation")' in access
    assert '"calibration-validation"' in app
    assert '"standard-room-inspection"' in app
    assert "Calibration & Validation" in app
    for marker in (
        '"1 Month": 30', '"6 Months": 180', '"1 Year": 365',
        'Gauge / Fixture Drawing', 'Gauge / Fixture Photograph', 'CALIBRATION_RECORD',
        'Download Calibration / Validation PDF', 'Download Calibration / Validation Excel',
    ):
        assert marker in page


def test_standard_room_supports_controlled_instruments_part_heat_batch_and_exports():
    page = text("app_pages/calibration_validation.py")
    for instrument in ("CMM", "COUNTER", "VMM", "ROUGHNESS TESTER", "HEIGHT GAUGE", "PROFILE PROJECTOR"):
        assert instrument in page
    for marker in (
        'text_input("Heat Number"', 'text_input("Batch Code"',
        'STANDARD_ROOM_INSPECTION', 'Download Standard Room Inspection PDF',
        'Download Standard Room Inspection Excel', 'STANDARD_ROOM_PHOTOGRAPH',
    ):
        assert marker in page


def test_v41426_migration_is_additive_permissioned_and_schedules_30_day_quality_reminders():
    sql = text("supabase/migrations/20260902120000_qcms_v41426_calibration_standard_room_complaint_npd_cards.sql")
    for table in ("quality_asset_part_process_links", "quality_asset_calibration_records", "standard_room_inspection_records"):
        assert f"create table if not exists public.{table}" in sql.lower()
        assert table in sql
    assert "CALIBRATION_VALIDATION_DUE" in sql
    assert "days_ahead=30" in sql.replace(" ", "")
    assert "recipient_department='Quality'" in sql
    assert "qcms_effective_module_permission(''CALIBRATION_VALIDATION''" in sql
    assert "QUALITY_ASSET" in sql and "CALIBRATION_RECORD" in sql and "STANDARD_ROOM_INSPECTION" in sql
    assert "select '4.14.26'::text" in sql


def test_npd_overdue_email_contains_stage_cards_and_green_completed_status():
    edge = text("supabase/functions/qcms-overdue-notifier/index.ts")
    assert "async function npdCardsHtml" in edge
    assert 'status === "COMPLETED"' in edge
    assert '#DCFCE7' in edge and '#166534' in edge
    assert '#FEE2E2' in edge and '! Overdue' in edge
    assert 'schedule.schedule_key === "NPD_PROCESS_OPEN_OVERDUE"' in edge
    assert 'schedule.schedule_key === "CALIBRATION_VALIDATION_DUE"' in edge
    assert "bodyHtml += await npdCardsHtml" in edge


def test_calibration_and_standard_room_transactions_use_controlled_delete_routing():
    delete_service = text("core/delete_service.py")
    for table in ("quality_asset_part_process_links", "quality_asset_calibration_records", "standard_room_inspection_records"):
        assert f'"{table}"' in delete_service
