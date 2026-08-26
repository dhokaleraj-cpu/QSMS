from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v4134_release_and_build_marker():
    assert (ROOT / "VERSION").read_text().strip() in {"4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13"}
    marker = "4134-PRIORITY-UI-RMTC-REUSE-DUPLICATE-SAFE-IMPORT"
    assert marker in text("core/ui.py")
    assert marker in text("core/auth.py")


def test_v4134_deterministic_enterprise_grid_and_priority_css():
    ui = text("core/ui.py")
    assert "def portal_table" in ui
    assert "qcms-enterprise-table" in ui
    assert "FINAL PRIORITY UI CONTRACT" in ui
    assert "--qcms-field:#FFFDF0" in ui
    assert "text-transform:uppercase!important" in ui
    combined = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "app_pages").glob("*.py"))
    assert "st.dataframe(" not in combined


def test_v4134_company_login_image_is_cropped_reference_ratio():
    auth = text("core/auth.py")
    assert "Welcome to Four Star Industries" in auth
    assert "height:410px!important" in auth
    image = ROOT / "assets" / "login_factory.jpeg"
    assert image.exists() and image.stat().st_size > 10_000
    from PIL import Image
    with Image.open(image) as im:
        ratio = im.width / im.height
    assert 1.60 <= ratio <= 1.70


def test_v4134_rmtc_reuses_global_balance_not_part_plan_cap():
    inward = text("app_pages/material_inward.py")
    migration = text("supabase/migrations/20260821142000_qcms_rmtc_reusable_global_balance_v4134.sql").casefold()
    assert "Reusable Production" in inward
    assert "RMTC Balance" in inward
    assert "Available Production from RMTC Balance" in inward
    assert "global rmtc certificate quantity is the only cumulative consumption ceiling" in migration
    assert "cumulative production % pieces exceeds rmtc planned production" not in migration
    assert "heat_allocated_steel+required_steel>cert.certificate_quantity" in migration


def test_v4134_imports_are_duplicate_safe_insert_only():
    master_import = text("app_pages/master_import.py")
    supply = text("core/supply_chain_service.py")
    reference = text("core/reference_import.py")
    layout = text("app_pages/inspection_layouts.py")
    assert "duplicate/existing row(s) skipped" in master_import
    assert "SKIP_DUPLICATE" in supply
    assert "never update existing records" in reference
    assert "duplicate" in layout.casefold()
