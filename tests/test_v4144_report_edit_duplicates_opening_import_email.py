from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = "4144-METLAB-EDIT-MASTER-DUPLICATE-OPENING-IMPORT-SMTP-GUIDE"

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def test_release_identity_and_prior_builds_preserved():
    assert (ROOT / "VERSION").read_text().strip() in {"4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15"}
    for path in ("streamlit_app.py", "core/auth.py", "core/ui.py"):
        text = read(path)
        assert BUILD in text
        assert "4143-PART-GRADES-LEADTIME-OPENING-STOCK-PASSWORD-EDIT-O365" in text
        assert "4142-PO-ORDER-VISIBILITY-FULL-PRICE-HISTORY" in text

def test_metlab_and_dimensional_stopiteration_is_removed_and_historic_context_is_recoverable():
    for path in ("app_pages/metlab_report.py", "app_pages/dimensional_report.py"):
        text = read(path)
        assert "next(row for row in all_plans" not in text
        assert "historic_plan" in text
        assert "historic_inward" in text
        assert "loaded that saved layout for controlled editing" in text
    assert "Edit Selected MetLAB Report with Password" in read("app_pages/metlab_report.py")
    assert "Edit Selected Dimensional Report with Password" in read("app_pages/dimensional_report.py")

def test_rmtc_report_edit_is_prominent_and_not_admin_only():
    text = read("app_pages/rmtc_pages.py")
    helper = read("core/password_edit.py")
    assert "EDIT SELECTED RMTC" in text
    assert "Edit Approved / Final RMTC with Password" in text
    assert "Administrator access is not required" in helper
    assert "verify_current_password" in helper

def test_duplicate_word_validation_is_identity_only():
    masters = read("core/master_service.py")
    identity = masters.split("_IDENTITY_DUPLICATE_FIELDS", 1)[1].split("}", 1)[0]
    for token in ("party_name", "standard_code", "standard_name", "process_name", "stage_name", "asset_name"):
        assert token in identity
    assert '"parts": ("fsi_part_number",)' in identity
    assert "part_name" not in identity
    # The former catch-all fuzzy-field selector must be gone. Reusable values such as revision,
    # manufacturer, method, designation, parameter, remarks and address may repeat.
    assert 'any(token in name for token in ("name", "description", "standard", "parameter", "designation"))' not in masters
    assert "auto_fuzzy" not in masters
    assert "Duplicate Material Grade code is not allowed" in read("app_pages/material_grade.py")

def test_opening_stock_is_separate_module_with_import_export_and_duplicate_safe_preview():
    supply = read("app_pages/supply_chain.py")
    service = read("core/supply_chain_service.py")
    app = read("streamlit_app.py")
    assert "Opening Stock & Import" in app
    assert "OPENING STOCK IMPORT / EXPORT UTILITY" in supply
    assert "Download Opening Stock Import Template" in supply
    assert "Export Current Opening Stock" in supply
    assert "Import Opening Stock · New Rows Only" in supply
    assert "opening_stock_import_preview" in service
    assert "SKIP_DUPLICATE" in service
    assert "Opening Reference is mandatory for duplicate-safe import" in service

def test_microsoft_365_auth_error_is_actionable_without_secret_in_source():
    page = read("app_pages/email_settings.py")
    edge = read("supabase/functions/qcms-send-email/index.ts")
    assert "535 5.7.139" in page
    assert "Authenticated SMTP" in page
    assert "smtp.office365.com" in page and "587" in page
    assert "SmtpClientAuthentication is disabled" in edge
    assert "enable Authenticated SMTP" in edge
    forbidden = "Rajesh" + "@2011"
    suffixes = {".py", ".sql", ".md", ".toml", ".json", ".ts", ".command", ".txt"}
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in suffixes:
            assert forbidden not in path.read_text(encoding="utf-8", errors="ignore")
