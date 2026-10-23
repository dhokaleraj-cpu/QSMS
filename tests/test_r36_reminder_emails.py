"""R36: scheduled reminder e-mails carry a detail table, an Excel sheet and the record PDFs."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS = ROOT / "supabase" / "functions"
REMINDER_FUNCTIONS = (
    "qcms-po-confirmation-reminder",
    "qcms-po-approval-overdue",
    "qcms-overdue-notifier",
    "qcms-supply-digest-notifier",
)
MIGRATION = ROOT / "supabase" / "migrations" / "20261022110000_qcms_r36_reminder_attachments.sql"


def text(path: Path | str) -> str:
    return (ROOT / path if isinstance(path, str) else path).read_text(encoding="utf-8")


# ----------------------------------------------------------------------------- edge functions
def test_reminder_kit_present_and_identical_in_all_four_functions():
    kits = {name: text(FUNCTIONS / name / "reminder_kit.ts") for name in REMINDER_FUNCTIONS}
    first = next(iter(kits.values()))
    for name, source in kits.items():
        assert source == first, f"{name}/reminder_kit.ts differs"
        assert 'from "./reminder_kit.ts"' in text(FUNCTIONS / name / "index.ts"), name
    for token in ("export function esc", "export function htmlTable", "export function textTable", "export function emailShell",
                  "export function xlsxAttachment", "export async function snapshotAttachments", "export async function poLineRows",
                  "#0F6E6E", "en-IN", 'npm:xlsx@0.18.5', "qcms_document_snapshots", "supply_purchase_order_sources",
                  "original_part_number_snapshot", "generated: false", "MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024"):
        assert token in first, token
    assert "service_role" not in first.lower() and "SUPABASE_SERVICE_ROLE_KEY" not in first


def test_table_headers_cover_part_customer_supplier_qty_price_delivery():
    kit = text(FUNCTIONS / "qcms-overdue-notifier" / "reminder_kit.ts")
    po_headers = kit[kit.index("PO_LINE_HEADERS"):kit.index("export function poLineCells")]
    for label in ("Part Number", "Customer", "Supplier", "Qty", "Price", "Delivery Date", "FSI Part No", "Customer Order No"):
        assert f'"{label}' in po_headers or f"label: \"{label}" in po_headers or label in po_headers, label
    for name in ("qcms-overdue-notifier", "qcms-supply-digest-notifier"):
        src = text(FUNCTIONS / name / "index.ts")
        headers = src[src.index("DIGEST_HEADERS"):src.index("DIGEST_KEEP")]
        for label in ("Part Number", "Customer", "Supplier", "Qty", "Price", "Delivery Date"):
            assert label in headers, (name, label)


def test_po_confirmation_reminder_has_line_table_pdf_and_excel():
    src = text(FUNCTIONS / "qcms-po-confirmation-reminder" / "index.ts")
    for token in ("poLineRows(admin,tenantId,[po.id])", "htmlTable(SUPPLIER_HEADERS", "textTable(SUPPLIER_HEADERS", "xlsxAttachment(",
                  ".map(supplierSafeLine)", "SUPPLIER_SAFE_HIDDEN",
                  "snapshotAttachments(admin,tenantId,[{source_table:\"supply_purchase_orders\"", "attachment_manifest:manifest",
                  "attachments:[...snaps.attachments", "html:bodyHtml", "removeGenerated(admin,manifest)",
                  # existing behaviour kept
                  "PRIORITY · Purchase Order confirmation pending", "PO_CONFIRMATION_DAILY", "reminder_count", "qcms_po_reminder_allowed",
                  "qcms_claim_notification_for_send", "qcms_notification_send_is_current", 'build:"4.14.35"', "X-QCMS-Scheduler"):
        assert token in src, token
    assert "Four Star Industries Pvt. Ltd. · QCMS" not in src  # company name now comes from settings / tenant


def test_po_approval_overdue_has_line_table_pdf_and_excel():
    src = text(FUNCTIONS / "qcms-po-approval-overdue" / "index.ts")
    for token in ("poLineRows(", "htmlTable(PO_LINE_HEADERS", "xlsxAttachment(", "snapshotAttachments(", "attachment_manifest:manifest",
                  "attachments:[...snaps.attachments", "PO_APPROVAL_OVERDUE:", "X-QCMS-Scheduler", "PO_PENDING_APPROVAL"):
        assert token in src, token


def test_overdue_notifier_every_schedule_gets_table_excel_and_snapshots():
    src = text(FUNCTIONS / "qcms-overdue-notifier" / "index.ts")
    for token in ("digestCells(recipient.rows, Boolean(recipient.external))", "htmlTable(table.headers, table.rows", "xlsxAttachment(", "snapshotAttachments(admin, tenantId",
                  "MAX_ATTACHMENT_BYTES - pdfBytes.byteLength - excel.bytes.byteLength", "...snaps.manifest", "...snaps.attachments",
                  "bodyHtml += await npdCardsHtml", "digestPdf(", "body_html: fullHtml", "removeGenerated(admin, [excelEntry])"):
        assert token in src, token
    # every schedule fills the new detail fields
    for key in ("CUSTOMER_ORDER_OPEN_OVERDUE", "PO_PENDING_APPROVAL", "RM_PROCUREMENT_PENDING_DUE", "RM_PO_OPEN_OVERDUE",
                "FORGING_ORDER_OPEN_OVERDUE", "OSP_RETURN_OPEN_OVERDUE", "CALIBRATION_VALIDATION_DUE", "COMPLAINT_FOLLOWUP_DUE",
                "NPD_PROCESS_OPEN_OVERDUE"):
        assert key in src, key
    assert src.count("part_number:") >= 6 and src.count("delivery_date:") >= 6
    assert 'refs: [{ source_table: "supply_purchase_orders"' in src and 'source_table: "quality_complaints"' in src
    # supplier / party copies never disclose the end customer (same rule as the PO print)
    assert "external: true" in src and "EXTERNAL_HIDDEN" in src


def test_supply_digest_has_html_table_and_attachments():
    src = text(FUNCTIONS / "qcms-supply-digest-notifier" / "index.ts")
    for token in ("digestTable(rows)", "htmlTable(table.headers,table.rows", "html:bodyHtml", "snapshotAttachments(admin,tenantId,refs,10",
                  "attachment_manifest:manifest", "SUPPLY_DIGEST:", "qcms_supply_digest_state", "export_format:\"XLSX\""):
        assert token in src, token


def test_deno_json_present_for_deploy():
    for name in REMINDER_FUNCTIONS:
        json.loads(text(FUNCTIONS / name / "deno.json"))


# ----------------------------------------------------------------------------- migration
def test_migration_table_rls_rpc_and_auto_apply():
    sql = text(MIGRATION)
    for token in ("create table if not exists public.qcms_document_snapshots", "default public.current_tenant_id()",
                  "unique (tenant_id, source_table, record_id, doc_kind)", "enable row level security",
                  "qcms_document_snapshots_read", "qcms_document_snapshots_insert", "qcms_document_snapshots_update",
                  "tenant_id = public.current_tenant_id()", "create or replace function public.qcms_reminder_snapshot_targets(p_limit integer default 20)",
                  "security invoker", "supply_po_confirmations", "PENDING_APPROVAL", "supply_rm_purchase_orders", "supply_forging_orders",
                  "rmtc_approvals", "lab_tests", "inspection_reports", "grant execute on function public.qcms_reminder_snapshot_targets(integer) to authenticated"):
        assert token in sql, token
    lowered = re.sub(r"--.*", "", sql).lower()
    assert not re.search(r"\b(drop|delete from|truncate)\b", lowered)
    assert not re.search(r"^\s*update\s", lowered, re.M)
    files = json.loads(text("supabase/auto_apply.json"))["files"]
    assert "supabase/migrations/20261022110000_qcms_r36_reminder_attachments.sql" in files


# ----------------------------------------------------------------------------- python side
def test_hooks_wired():
    notification = text("core/notification_service.py")
    assert "document_snapshots.refresh_async" in notification and "_last_rendered" in notification
    app = text("streamlit_app.py")
    assert "schedule_pending_refresh(20)" in app
    settings = text("app_pages/email_settings.py")
    assert "REMINDER ATTACHMENTS" in settings and "Prepare attachments now" in settings
    module = text("core/document_snapshots.py")
    for token in ("qcms_reminder_snapshot_targets", "document_snapshots/", "add_script_run_ctx", "REFRESH_INTERVAL_SECONDS = 30 * 60",
                  "on_conflict=\"tenant_id,source_table,record_id,doc_kind\"", "\"upsert\": \"true\""):
        assert token in module, token


def _live_repo(monkeypatch):
    from core.repository import Repository

    repo = Repository.__new__(Repository)
    repo.preview = False
    repo.client = object()
    repo.tenant_id = "00000000-0000-0000-0000-000000000001"

    def boom(*_a, **_k):
        raise RuntimeError("database down")

    monkeypatch.setattr(Repository, "rpc", boom)
    monkeypatch.setattr(Repository, "get", boom)
    monkeypatch.setattr(Repository, "select", boom)
    monkeypatch.setattr(Repository, "count", boom)
    return repo


def test_snapshot_module_never_raises(monkeypatch):
    from core import document_snapshots as ds

    repo = _live_repo(monkeypatch)
    assert ds.refresh_pending(20, repo=repo) == 0
    assert ds.refresh("supply_purchase_orders", "abc", repo=repo) is None
    assert ds.refresh("unknown_table", "abc", repo=repo) is None
    assert ds.refresh("", "", repo=repo) is None
    assert ds.snapshot_summary(repo) == {"count": 0, "last_generated_at": None, "pending": None}
    assert ds.schedule_pending_refresh(20) in (True, False)
    assert ds.refresh_async("supply_purchase_orders", "abc", repo=None) is False

    from core.notification_service import NotificationService

    service = NotificationService.__new__(NotificationService)
    service.repo = repo
    service._refresh_snapshot_async("supply_purchase_orders", "abc")  # background, must not raise


def test_snapshot_refresh_uploads_and_upserts(monkeypatch):
    from core import document_snapshots as ds

    calls: dict = {}

    class Bucket:
        def upload(self, path, content, options):
            calls["upload"] = (path, len(content), options)

    class Storage:
        def from_(self, bucket):
            calls["bucket"] = bucket
            return Bucket()

    class Query:
        def __init__(self, table):
            calls["table"] = table

        def upsert(self, row, on_conflict=None):
            calls["row"] = row; calls["on_conflict"] = on_conflict
            return self

        def execute(self):
            return type("R", (), {"data": [calls["row"]]})()

    class Client:
        storage = Storage()

        def table(self, name):
            return Query(name)

    class Repo:
        preview = False
        client = Client()
        tenant_id = "t1"

        def get(self, table, rid):
            return {"id": rid, "updated_at": "2026-10-20T10:00:00+00:00"}

        def select(self, *_a, **_k):
            return [{"updated_at": "2026-10-21T10:00:00+00:00"}]

    row = ds.refresh("supply_purchase_orders", "po-1", repo=Repo(), rendered=("PO/26 001.pdf", b"%PDF-1.4 test"))
    assert row and row["object_path"] == "t1/document_snapshots/supply_purchase_orders/po-1/PO_26_001.pdf"
    assert calls["bucket"] == "quality-documents" and calls["upload"][2]["upsert"] == "true"
    assert calls["table"] == "qcms_document_snapshots" and calls["on_conflict"] == "tenant_id,source_table,record_id,doc_kind"
    assert row["record_updated_at"] == "2026-10-21T10:00:00+00:00"  # latest of PO header and lines
    assert row["size_bytes"] == len(b"%PDF-1.4 test") and row["doc_kind"] == "PDF_SAFE"
