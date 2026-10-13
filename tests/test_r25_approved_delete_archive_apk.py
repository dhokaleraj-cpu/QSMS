"""R25: approved transactions need Admin approval to delete, Deleted Records archive (view / PDF), APK 1.2.0."""
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def test_is_approved_mirror():
    from core.delete_approval import is_approved
    assert is_approved({"approval_status": "APPROVED", "status": "OPEN"})
    assert is_approved({"status": "RELEASED"}) and is_approved({"status": "FINAL"}) and is_approved({"confirmation_status": "CONFIRMED"})
    assert not is_approved({"status": "PENDING_APPROVAL", "approval_status": "PENDING_APPROVAL"}) and not is_approved({"status": "CANCELLED"})


def test_sql_guard_requests_archive():
    sql = (ROOT / "supabase/migrations/20261016100000_qcms_r25_approved_delete_archive.sql").read_text()
    for token in ("create table if not exists public.qcms_delete_requests", "trg_qcms_guard_approved_delete", "APPROVED_DELETE_BLOCKED",
                  "function public.qcms_request_delete(", "function public.qcms_decide_delete_request(", "current_app_role() <> 'ADMIN'",
                  "set_config('qcms.approved_delete', 'on', true)", "function public.qcms_deleted_records(", "a.operation = 'DELETE'",
                  "'supply_purchase_orders','supply_po_confirmations'"):
        assert token in sql, token


def test_delete_panels_route_approved_rows_to_request():
    ds = (ROOT / "core/delete_service.py").read_text()
    assert ds.count("if is_approved(selected_row):") == 2 and "APPROVED_DELETE_BLOCKED" in ds
    rc = (ROOT / "app_pages/records_center.py").read_text()
    assert '"Deletion Requests", "Deleted Records"' in rc and "def render_deletion_requests" in rc and "def render_deleted_records" in rc


def test_deleted_record_pdfs():
    from core.delete_approval import deleted_record_pdf, deleted_register_pdf, deleted_summary
    row = {"table_name": "supply_purchase_orders", "record_id": "x", "deleted_at": "2026-10-13T10:00:00+00:00", "deleted_by_name": "Admin",
           "old_data": {"id": "x", "po_number": "PD9121000079", "status": "OPEN", "approval_status": "APPROVED", "grand_total": 100},
           "delete_reason": "Duplicate PO", "approved_by_name": "Admin"}
    s = deleted_summary(row)
    assert s["Reference"] == "PD9121000079" and s["Status When Deleted"] == "APPROVED" and s["Delete Reason"] == "Duplicate PO"
    text = "".join(p.extract_text() for p in PdfReader(BytesIO(deleted_record_pdf(row))).pages)
    assert "DELETED RECORD" in text and "PD9121000079" in text and "Duplicate PO" in text
    assert deleted_register_pdf([row]).startswith(b"%PDF")


def test_apk_version_1_2_0():
    gradle = (ROOT / "mobile/android_first_app/app/build.gradle").read_text()
    assert "versionName '1.2.0'" in gradle and "versionCode 20" in gradle
    assert "QCMSApp/1.2.0" in (ROOT / "mobile/android_first_app/app/src/main/java/com/fourstar/qcms/MainActivity.java").read_text()
