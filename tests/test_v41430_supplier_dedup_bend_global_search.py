from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41430_release_identity_source_only_contract():
    version = text("VERSION").strip()
    assert version in {"4.14.30", "4.14.31", "4.14.32", "4.14.33", "4.14.34", "4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43", "4.14.44"}
    app = text("streamlit_app.py")
    assert any(marker in app for marker in (
        "41430-RMTC-SUPPLIER-DEDUP-BEND-GLOBAL-SEARCH",
        "41431-PO-WORKSPACE-PREAPPROVAL-EDIT-CUSTOMER-REF-PDF",
        "41433-PO-PORTRAIT-TERMS-BATCH-PRINT-EMAIL-ANDROID-SDK",
        "41434-INDIVIDUAL-PO-PDF-ZIP-ANDROID-APK-BUILD", "41435-PO-WATERMARK-REMINDER-MOBILE-IOS", "41437-MOBILE-FULL-NAV-COMPLAINT-CARDS-PO-APPROVAL-DRAFT-EMAIL", "41438-ANDROID-NAV-SESSION-BRIDGE-FOOTER-REMOVE", "41439-ANDROID-CI-SIGNATURE-PERMANENT-FIX", "41440-ANDROID-NAV-READY-QUEUE-BUTTON-BRIDGE", "41441-ANDROID-LAMBDA-COMPILE-PERMANENT-FIX",
    ))
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] in {"4.14.30", "4.14.31", "4.14.32", "4.14.33", "4.14.34", "4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43", "4.14.44"}
    assert manifest["build"] in {
        "41430-RMTC-SUPPLIER-DEDUP-BEND-GLOBAL-SEARCH",
        "41431-PO-WORKSPACE-PREAPPROVAL-EDIT-CUSTOMER-REF-PDF",
        "41432-PO-PRINT-COMPACT-RM-TYPES-ANDROID-TEST",
        "41433-PO-PORTRAIT-TERMS-BATCH-PRINT-EMAIL-ANDROID-SDK",
        "41434-INDIVIDUAL-PO-PDF-ZIP-ANDROID-APK-BUILD", "41435-PO-WATERMARK-REMINDER-MOBILE-IOS",
        "41436-COMPLAINT-EMAIL-REGISTERS-REMINDERS-MOBILE-DRAWER",
        "41437-MOBILE-FULL-NAV-COMPLAINT-CARDS-PO-APPROVAL-DRAFT-EMAIL", "41438-ANDROID-NAV-SESSION-BRIDGE-FOOTER-REMOVE", "41439-ANDROID-CI-SIGNATURE-PERMANENT-FIX", "41440-ANDROID-NAV-READY-QUEUE-BUTTON-BRIDGE", "41441-ANDROID-LAMBDA-COMPILE-PERMANENT-FIX", "41442-LOCAL-JAVAC-OPTIONAL-CI-COMPILE-GUARD", "41443-ANDROID-STREAMLIT-SIDEBAR-NAV", "41444-ANDROID-NATIVE-MENU-SUBMENU-RESTORE",
    }
    if manifest["version"] in {"4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43", "4.14.44"}:
        assert manifest["database_schema_required"] == ("4.14.36" if manifest["version"] in {"4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43", "4.14.44"} else manifest["version"])
        assert manifest["database_migration_required"] is True
        assert manifest["source_only_updater"] is False
    else:
        assert manifest["database_schema_required"] == "4.14.28"
        assert manifest["database_migration_required"] is False
        assert manifest["source_only_updater"] is True
    assert manifest["previous_controlled_release"] == {"4.14.30": "4.14.29", "4.14.31": "4.14.30", "4.14.32": "4.14.31", "4.14.33": "4.14.32", "4.14.34": "4.14.33", "4.14.35": "4.14.34", "4.14.36": "4.14.35", "4.14.37": "4.14.36", "4.14.38": "4.14.37", "4.14.39": "4.14.38", "4.14.40": "4.14.39", "4.14.41": "4.14.40", "4.14.42": "4.14.41", "4.14.43": "4.14.42", "4.14.44": "4.14.43"}[manifest["version"]]


def test_rmtc_approved_source_returns_one_option_per_supplier():
    service = text("core/rmtc_service.py")
    assert "raw_by_supplier.setdefault(supplier_id, []).append(row)" in service
    assert "links_by_supplier.setdefault(supplier_id, []).append(link)" in service
    assert "for supplier_id, supplier_links in links_by_supplier.items()" in service
    assert '\'option_key\': f"SUPPLIER:{supplier_id}"' in service
    assert "'raw_material_detail_id': selected.get('id') if len(details) == 1 else None" in service
    assert "'raw_material_details': details" in service


def test_rmtc_ui_has_unique_supplier_then_raw_detail_selector():
    page = text("app_pages/rmtc_pages.py")
    service = text("core/rmtc_service.py")
    assert "one RMTC-approved source option per Supplier" in service
    assert "links_by_supplier" in service and "raw_by_supplier" in service
    assert "Approved Raw Material Source" in page
    assert "Raw Material Detail" in page
    assert "one row per Supplier" in page
    assert "raw_material_details" in page
    assert "Select the exact Raw Material Detail once" in page


def test_bend_test_has_dedicated_discoverable_entry_records_and_report_routes():
    app = text("streamlit_app.py")
    report = text("app_pages/metlab_report.py")
    inspection_home = text("app_pages/inspection_home.py")
    reports = text("app_pages/reports.py")
    for route in ("bend-test-entry", "bend-test-records", "bend-test-report"):
        assert route in app
    assert "render_bend_test_entry" in report
    assert "render_bend_test_records" in report
    assert "BEND TEST REGISTER" in report
    assert "Bend Test Report" in inspection_home
    assert '"bend-test-report", "Bend Test"' in reports


def test_global_search_is_persistent_permission_aware_and_relationship_expanded():
    app = text("streamlit_app.py")
    search = text("app_pages/global_search.py")
    assert "qcms_shell_global_search_form" in app
    assert "_qcms_global_search_pending_query" in app
    assert '"global-search"' in app
    assert "SEARCH_SOURCES" in search
    assert "module_permissions(profile, module_key, repo)" in search
    assert "tenant/RLS" in search
    assert "_relationship_rows" in search
    for token in ("parts", "parties", "rmtc_approvals", "inward_lots", "osp_jobs", "lab_tests", "supply_purchase_orders", "quality_complaints"):
        assert token in search


def test_global_search_relationship_expansion_uses_master_ids_and_controlled_fk_fields():
    search = text("app_pages/global_search.py")
    assert 'part_ids = [str(row.get("id"))' in search
    assert 'party_ids = [str(row.get("id"))' in search
    assert 'repo.select(source["table"], in_={field: part_ids[:50]}' in search
    assert 'repo.select(source["table"], in_={field: party_ids[:50]}' in search
    assert 'query.casefold() not in relation_text.casefold()' in search

