from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_release_identity_and_required_schema_migration():
    version = text("VERSION").strip()
    assert version in {"4.14.45", "4.14.46"}
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] == version
    if version == "4.14.45":
        assert manifest["build"] == "41445-SHARED-RAW-SOURCE-LAYOUT-CONTROL"
        assert manifest["previous_controlled_release"] == "4.14.44"
        assert manifest["database_migration_required"] is True
    else:
        assert manifest["build"] == "41446-ANDROID-V12-DRAWER-PERSISTENT-AUTH"
        assert manifest["previous_controlled_release"] == "4.14.45"
        assert manifest["database_migration_required"] is False
    assert manifest["database_schema_required"] == "4.14.45"
    assert manifest["schema_change_for_v41445"] is True


def test_same_numeric_price_is_allowed_across_different_part_masters():
    migration = text("supabase/migrations/20260822213000_qcms_multi_rm_po_price_history_technical_data_v4138.sql")
    unique_start = migration.index("create unique index if not exists uq_qcms_part_supplier_price_start")
    unique_end = migration.index(";", unique_start)
    unique_clause = migration[unique_start:unique_end]
    assert "tenant_id,part_id,supplier_id,upper(uom),start_date" in unique_clause
    columns = unique_clause.split("on public.part_supplier_price_history(", 1)[1]
    assert "price" not in columns.lower()
    guard_start = migration.index("create or replace function public.qcms_guard_part_supplier_price_history")
    guard_end = migration.index("drop trigger if exists trg_qcms_guard_part_supplier_price_history", guard_start)
    guard = migration[guard_start:guard_end]
    assert "h.part_id=new.part_id" in guard
    assert "h.price=new.price" not in guard
    part_ui = text("app_pages/part_master.py")
    assert "The same commercial rate is intentionally allowed on different Part Master records." in part_ui


def test_raw_forging_casting_can_link_another_part_master():
    part_ui = text("app_pages/part_master.py")
    migration = text("supabase/migrations/20260922070000_qcms_v41445_shared_raw_source_layout_scope.sql")
    for token in (
        "Source Raw Forging / Casting Part",
        'source_part_id',
        'material_section.casefold() not in {"forging", "casting"}',
    ):
        assert token in part_ui
    for token in (
        "add column if not exists source_part_id uuid references public.parts(id) on delete restrict",
        "qcms_guard_raw_source_part",
        "Source Raw Forging / Casting Part creates a circular Part genealogy",
        "('forging','casting')",
    ):
        assert token in migration


def test_shared_source_part_is_used_by_forging_po_and_price_history_fallback():
    service = text("core/supply_chain_service.py")
    for token in (
        "def raw_source_context",
        "def effective_current_price",
        "def effective_price_history",
        '"SOURCE_PART_FORGING"',
        "Source Raw Forging / Casting Part",
        "current supplier price is missing in Part Master Price History",
    ):
        assert token in service
    assert "self.effective_current_price" in service
    assert "self.effective_price_history" in service


def test_layout_plan_number_is_stage_process_part_name():
    service = text("core/inspection_service.py")
    start = service.index("def auto_plan_number")
    end = service.index("def scope_plan", start)
    block = service[start:end]
    stage_pos = block.index('stage.get("stage_code")')
    process_pos = block.index('process.get("process_code")')
    part_pos = block.index('part.get("part_number")')
    layout_pos = block.index('_layout_token(layout_name')
    assert stage_pos < process_pos < part_pos < layout_pos
    assert 'return "-".join' in block
    assert '"STAGE"' in block and '"NOPROCESS"' in block and '"PART"' in block and '"LAYOUT"' in block


def test_one_current_layout_per_controlled_part_stage_process_scope():
    service = text("core/inspection_service.py")
    ui = text("app_pages/inspection_layouts.py")
    migration = text("supabase/migrations/20260922070000_qcms_v41445_shared_raw_source_layout_scope.sql")
    for token in (
        "def scope_plan",
        "Only one current inspection layout is allowed for the same Part + Inspection Stage + Process + Layout Type.",
        '{"DRAFT", "APPROVAL_PENDING", "APPROVED"}',
    ):
        assert token in service
    for token in (
        "Plan Number (Auto)",
        "Inspection Stage is required",
        "Only one current layout is permitted for each Part + Inspection Stage + Process + Layout Type scope",
    ):
        assert token in ui
    assert "uq_qcms_inspection_plan_current_scope" in migration
    assert "FINAL_METALLURGICAL" in migration
    assert "('DRAFT','APPROVAL_PENDING','APPROVED')" in migration


def test_v41445_schema_guard_can_auto_apply_without_manual_sql_step():
    guard = text("scripts/qcms_remote_schema_guard.py")
    for token in (
        "V41445_MIGRATION",
        "QCMS_V41445_READY",
        "qcms_release_contract_v41445",
        "Applying additive v4.14.45 shared raw-source/layout migration automatically",
        "apply_sql(project_ref, V41445_MIGRATION)",
    ):
        assert token in guard
