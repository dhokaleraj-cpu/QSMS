from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def text(path): return (ROOT/path).read_text(encoding='utf-8')

def test_release_identity_and_source_only_schema_baseline():
    assert text('VERSION').strip() in {'4.14.23','4.14.24','4.14.25','4.14.26','4.14.27'}
    manifest=json.loads(text('DEPLOYMENT_MANIFEST.json'))
    assert manifest['version'] in {'4.14.23','4.14.24','4.14.25','4.14.26','4.14.27'}
    assert manifest['build'] in {'41423-SOURCE-ONLY-DEPLOY-RMTC-MASTER-DELETE','41424-PO-TECH-GRID-LIVE-IMPORT-APQP-DATE', '41425-PO-EDIT-MASTER-STATE-TRANSACTION-EDIT-PERFORMANCE', '41426-COMPLAINT-MEDIA-CALIBRATION-STANDARD-ROOM-NPD-CARDS', '41427-FINAL-METLAB-LAYOUT-PO-EMAIL-FIELDS'}
    assert manifest['database_schema_required'] in {'4.14.22','4.14.26','4.14.27'}
    assert manifest['database_migration_required'] is False
    assert manifest['supabase_release_contract'] in {'QCMS_V41422_FULL_READY','QCMS v4.14.26 live migration applied and verified during controlled release packaging','QCMS v4.14.27 live migration applied and verified during controlled release packaging'}

def test_same_heat_new_rmtc_uses_fresh_selector_nonce_and_blank_certificate_state():
    page=text('app_pages/rmtc_pages.py')
    assert "selector_key=f'rmtc_direct_edit_selector_{selector_nonce}'" in page
    assert "rmtc_same_heat_create_mode" in page
    assert "New RMTC / TC Certified Quantity (kg)" in page
    assert "BLANK NEW certificate" in page
    assert "str(key).startswith(('rmtc_direct_edit_selector_'" in page

def test_master_cards_request_blank_new_record_and_entries_consume_it():
    ui=text('core/ui.py')
    assert 'st.session_state["_qcms_master_blank_request"] = entry_path' in ui
    assert 'def consume_master_blank_request' in ui
    required=[
        'app_pages/company_branch.py','app_pages/part_master.py','app_pages/process_master.py',
        'app_pages/material_grade.py','app_pages/reference_master.py','app_pages/employee_master.py',
        'app_pages/inspection_layouts.py','app_pages/standards_bank.py',
    ]
    for path in required:
        assert 'consume_master_blank_request' in text(path), path

def test_transaction_delete_router_never_sends_known_transactions_to_master_delete():
    delete=text('core/delete_service.py')
    assert 'TRANSACTION_DELETE_TABLES' in delete
    assert '"osp_jobs"' in delete and '"inspection_reports"' in delete and '"lab_tests"' in delete
    assert 'repo.rpc("qcms_delete_transaction_row"' in delete
    assert 'else:\n        repo.rpc("qsms_delete_master_row"' in delete

def test_source_only_guard_can_be_nonblocking_without_cli_login():
    guard=text('scripts/qcms_remote_schema_guard.py')
    assert '--source-only-nonblocking' in guard
    assert 'SOURCE-ONLY RELEASE: online Supabase recheck unavailable/incomplete' in guard
