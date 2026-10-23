"""R36b: customer details are internal - never sent to a supplier / vendor / outside address."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class _Repo:
    tenant_id = "t"

    def select(self, table, **kwargs):
        if table == "employees":
            return [{"email": "qa@fourstarindustries.com"}, {"email": "boss@gmail.com"}]
        if table == "qcms_email_settings":
            return [{"sender_email": "qcms@fourstarindustries.com"}]
        return []


def test_internal_vs_external_recipients():
    from core.customer_privacy import external_recipients, internal_directory
    d = internal_directory(_Repo())
    out = external_recipients(["qa@fourstarindustries.com", "new.joiner@fourstarindustries.com", "boss@gmail.com",
                               "sales@forgingsupplier.com", "x@gmail.com"], d)
    assert out == ["sales@forgingsupplier.com", "x@gmail.com"]  # company domain + known employees are internal


def test_scrub_and_strip():
    from core.customer_privacy import scrub_context, strip_customer, supplier_safe_po
    ctx = scrub_context({"customer_name": "Kessler", "customer_order_no": "2424017", "supplier_name": "MTF", "po_number": "PD9"})
    assert ctx["customer_name"] == "—" and ctx["customer_order_no"] == "—" and ctx["supplier_name"] == "MTF"
    payload = strip_customer({"customer": {"party_name": "Kessler"}, "details": {"customer_name": "Kessler", "heat": "A1"}})
    assert payload["customer"] == {} and payload["details"]["customer_name"] == "" and payload["details"]["heat"] == "A1"
    header, items = supplier_safe_po({"po_number": "PD9", "print_options": {"show_source_reference": True}},
                                     [{"item_no": "K160", "customer_source_rows": [{"customer_po_number": "2423729"}]}])
    assert header["print_options"]["show_source_reference"] is False and items[0]["customer_source_rows"] == []


def test_wired_everywhere():
    ns = (ROOT / "core/notification_service.py").read_text()
    assert "external_recipients([email, *final_cc]" in ns and "scrub_context(enriched)" in ns and "supplier_safe_po" in ns
    assert "CUSTOMER_ONLY_ENTITY_TYPES" in ns
    snap = (ROOT / "core/document_snapshots.py").read_text()
    assert 'DOC_KIND = "PDF_SAFE"' in snap and "service.customer_safe = True" in snap
    for fn in ("qcms-overdue-notifier", "qcms-po-approval-overdue", "qcms-po-confirmation-reminder", "qcms-supply-digest-notifier"):
        kit = (ROOT / "supabase/functions" / fn / "reminder_kit.ts").read_text()
        assert '"PDF_SAFE"' in kit and "supplierSafeLine" in kit and '"Part Number"' in kit.split("SUPPLIER_SAFE_HIDDEN")[1][:80]
    conf = (ROOT / "supabase/functions/qcms-po-confirmation-reminder/index.ts").read_text()
    assert ".map(supplierSafeLine)" in conf and "SUPPLIER_SAFE_HIDDEN" in conf
    od = (ROOT / "supabase/functions/qcms-overdue-notifier/index.ts").read_text()
    assert "recipient.external ? supplierSafeLine(l) : l" in od and "digestCells(recipient.rows, Boolean(recipient.external))" in od
    po = (ROOT / "core/purchase_order_reporting.py").read_text()
    assert "INTERNAL COPY - CUSTOMER DETAILS - NOT FOR SUPPLIER" in po
    assert 'flag != "show_source_reference"' in (ROOT / "core/po_print_ui.py").read_text()
    assert "External recipient(s)" in (ROOT / "app_pages/email_center.py").read_text()
