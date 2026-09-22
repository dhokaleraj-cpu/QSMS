from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_release_identity_and_public_contract():
    assert text("VERSION").strip() in {"4.14.21", "4.14.22", "4.14.23", "4.14.24", "4.14.25", "4.14.26", "4.14.27", "4.14.28", "4.14.29", "4.14.30", "4.14.31", "4.14.32", "4.14.33", '4.14.34', '4.14.35', '4.14.36', '4.14.37', '4.14.38', '4.14.39'}
    assert any(marker in text("streamlit_app.py") for marker in ("41421-DEPLOY-RESUME-DELETE-ROUTING", "41422-PUBLIC-VERIFY-BLANK-MASTER-RMTC-RESET", "41423-SOURCE-ONLY-DEPLOY-RMTC-MASTER-DELETE", "41424-PO-TECH-GRID-LIVE-IMPORT-APQP-DATE", "41425-PO-EDIT-MASTER-STATE-TRANSACTION-EDIT-PERFORMANCE", "41426-COMPLAINT-MEDIA-CALIBRATION-STANDARD-ROOM-NPD-CARDS", "41427-FINAL-METLAB-LAYOUT-PO-EMAIL-FIELDS", "41428-OSP-BATCH-GENEALOGY-TWO-DAY-EXCEL", "41429-RMTC-BEND-CHEM-CASEDEPTH-PERMISSIONS", "41430-RMTC-SUPPLIER-DEDUP-BEND-GLOBAL-SEARCH", "41431-PO-WORKSPACE-PREAPPROVAL-EDIT-CUSTOMER-REF-PDF", "41432-PO-PRINT-COMPACT-RM-TYPES-ANDROID-TEST", "41433-PO-PORTRAIT-TERMS-BATCH-PRINT-EMAIL-ANDROID-SDK", '41434-INDIVIDUAL-PO-PDF-ZIP-ANDROID-APK-BUILD', '41438-ANDROID-NAV-SESSION-BRIDGE-FOOTER-REMOVE', '41439-ANDROID-CI-SIGNATURE-PERMANENT-FIX'))
    manifest = text("DEPLOYMENT_MANIFEST.json")
    assert any(marker in manifest for marker in ('"version": "4.14.21"', '"version": "4.14.22"', '"version": "4.14.23"', '"version": "4.14.24"', '"version": "4.14.25"', '"version": "4.14.26"', '"version": "4.14.27"', '"version": "4.14.28"', '"version": "4.14.29"', '"version": "4.14.30"', '"version": "4.14.31"', '"version": "4.14.32"', '"version": "4.14.33"' , '"version": "4.14.34"', '"version": "4.14.35"', '"version": "4.14.36"', '"version": "4.14.37"', '"version": "4.14.38"', '"version": "4.14.39"'))
    migration = text("supabase/migrations/20260902002000_qcms_v41421_deploy_resume_delete_routing.sql")
    assert "qcms_release_contract_v41421" in migration
    assert "QCMS_V41421_FULL_READY" in migration
    assert "qcms_release_schema_version" in migration


def test_delete_service_routes_transactions_not_master_rpc():
    delete_service = text("core/delete_service.py")
    assert "TRANSACTION_DELETE_TABLES" in delete_service
    assert '"inspection_reports"' in delete_service
    assert '"lab_tests"' in delete_service
    assert '"osp_jobs"' in delete_service
    assert 'repo.rpc("qcms_delete_transaction_row"' in delete_service
    assert 'repo.rpc("qsms_delete_master_row"' in delete_service
    assert 'st.error(f"Deletion blocked: {exc}")' in delete_service


def test_schema_guard_can_verify_without_management_token():
    guard = text("scripts/qcms_remote_schema_guard.py")
    assert "_data_api_v41421_contract_marker" in guard
    assert "QCMS_V41421_FULL_READY" in guard
    assert "public full release contract verified" in guard
    assert "V41421_MIGRATION" in guard
