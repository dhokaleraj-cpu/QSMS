from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')


def test_v41428_release_identity_and_manifest():
    assert text('VERSION').strip() == '4.14.28'
    app = text('streamlit_app.py')
    assert '41428-OSP-BATCH-GENEALOGY-TWO-DAY-EXCEL' in app
    manifest = json.loads(text('DEPLOYMENT_MANIFEST.json'))
    assert manifest['version'] == '4.14.28'
    assert manifest['build'] == '41428-OSP-BATCH-GENEALOGY-TWO-DAY-EXCEL'
    assert manifest['database_schema_required'] == '4.14.28'


def test_osp_selectors_show_part_fsi_and_vendor_batch_and_material_out_remarks():
    tx = text('app_pages/osp_transactions.py')
    insp = text('app_pages/osp_inspections.py')
    for marker in ('FSI Batch Number', 'Vendor Batch Number', 'Material Out Remarks'):
        assert marker in tx
    assert 'FSI Batch {fsi_batch}' in tx
    assert 'FSI Batch {row.get(\'osp_batch_code\') or \'-\'}' in insp
    assert '"batch_number": job.get("osp_batch_code")' in insp
    assert 'Material Out Remarks' in insp


def test_osp_dimensional_queue_uses_approved_layout_as_authoritative_requirement():
    service = text('core/osp_service.py')
    assert 'approved_layout_specs' in service
    assert 'required_by_approved_layout' in service
    assert 'source_process_specification_id' in service
    sql = text('supabase/migrations/20260903103000_qcms_v41428_osp_batch_two_day_excel_digest.sql')
    assert "layout_type='DIMENSIONAL'" in sql
    assert "dimensional_required=true" in sql
    assert "required_tests" in sql
    assert 'trg_qcms_sync_osp_requirement_from_approved_layout' in sql


def test_two_day_internal_excel_schedules_and_edge_export_are_present():
    initial_sql = text('supabase/migrations/20260903103000_qcms_v41428_osp_batch_two_day_excel_digest.sql')
    sql = text('supabase/migrations/20260903105000_qcms_v41428_supply_digest_consolidation.sql')
    edge = text('supabase/functions/qcms-supply-digest-notifier/index.ts')
    # The initial *_2DAY schedules were consolidated into one dedicated notifier to avoid
    # duplicate delivery with the general overdue-notifier. Historical rows are disabled.
    for key in ('CUSTOMER_ORDER_OVERDUE_2DAY','RM_ORDER_PENDING_2DAY','PURCHASE_ORDER_PENDING_2DAY','FORGING_RECEIPT_OVERDUE_2DAY'):
        assert key in initial_sql
        assert key in sql
    for key in ('CUSTOMER_ORDER_OVERDUE_BIENNIAL','RM_PENDING_BIENNIAL','PO_PENDING_BIENNIAL','FORGING_RECEIPT_OVERDUE_BIENNIAL'):
        assert key in sql
        assert key in edge
    assert "set enabled=false" in sql
    assert "qcms-supply-digest-notifier-hourly" in sql
    assert 'run_every_days=2' in sql.replace(' ', '')
    assert "'XLSX'" in sql
    assert "array['Supply Chain','Marketing','Management','Procurement']" in sql
    assert 'import * as XLSX from "npm:xlsx@0.18.5"' in edge
    assert 'function workbook' in edge
    assert 'schedule.run_every_days' in edge
    assert 'schedule.recipient_departments' in edge


def test_email_schedule_admin_can_edit_cadence_departments_and_export_format():
    src = text('app_pages/email_settings.py')
    assert 'Run every (days)' in src
    assert 'Recipient Departments' in src
    assert 'Attachment Format' in src
    assert 'run_every_days' in src
    assert 'recipient_departments' in src
    assert 'export_format' in src
    assert 'CUSTOMER_ORDER_OVERDUE_BIENNIAL' in src
    assert 'PO_PENDING_BIENNIAL' in src
