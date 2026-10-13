"""R23: PO line numbers, combined quantity, per-PO hidden sections, preview before save, email preview."""
from io import BytesIO
from pathlib import Path
import copy

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def _pdf_text(pdf: bytes) -> str:
    return "".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)


def test_line_numbers_total_qty_and_per_po_hidden_sections():
    from core.print_samples import po_sample
    from core.purchase_order_reporting import purchase_order_pdf_bytes, po_quantity_totals
    header, items = po_sample()
    second = copy.deepcopy(items[0]); second["item_no"] = "RM-2"; second["quantity"] = 2000
    header["print_options"] = {"show_price_history": False, "show_source_reference": False}
    text = _pdf_text(purchase_order_pdf_bytes(header, [items[0], second], terms_path="/__none__.pdf"))
    assert "LINE" in text and "1/2" in text and "2/2" in text
    assert "PO LINES" in text and "TOTAL QTY" in text and "5,800 KGS" in text
    assert "PRICE REVISION HISTORY" not in text and "PO SOURCE REFERENCE" not in text
    assert "SUPPLIER TECHNICAL DATA · LINE 1 OF 2" in text
    assert po_quantity_totals([{"quantity": 10, "uom": "KGS"}, {"quantity": 5, "uom": "NOS"}]) == "10 KGS + 5 NOS"


def test_preview_runs_full_validation_without_saving():
    import sys
    sys.path.insert(0, str(ROOT / "tests"))
    from test_r9_rm_bend_approval import rm_service
    from test_r7_linked_raw_flow import po_payload
    svc = rm_service("FSI_RM")
    before = {t: len(rows) for t, rows in svc.repo.tables.items()}
    header, items = svc.preview_purchase_order({**po_payload(), "po_type": "RAW_MATERIAL", "customer_order_ids": ["one", "two"], "allocations": {"one": 70, "two": 160}, "print_options": {"show_price_history": False}})
    assert header["po_number"] == "PREVIEW (not saved)" and header["print_options"] == {"show_price_history": False}
    assert len(items) == 1 and sum(r["quantity"] for r in items) == 230
    after = {t: len(rows) for t, rows in svc.repo.tables.items()}
    for table in ("supply_purchase_orders", "supply_purchase_order_items", "supply_purchase_order_sources"):
        assert after.get(table, 0) == before.get(table, 0)   # nothing saved (fixture's own save_transaction lambda aside)


def test_po_entry_and_pdf_page_controls():
    sc = (ROOT / "app_pages/supply_chain.py").read_text()
    for token in ("SECTIONS SHOWN ON PRINT", "Preview PO PDF (not saved)", "PO PREVIEW · NOT SAVED",
                  "po_sections_panel", "Email preview · "):
        assert token in sc
    sql = (ROOT / "supabase/migrations/20261015100000_qcms_r23_po_print_options.sql").read_text()
    assert "add column if not exists print_options jsonb" in sql
    from core.supply_chain_service import clean_print_options
    assert clean_print_options({"show_technical": 0, "junk": 1}) == {"show_technical": False} and clean_print_options({}) is None


def test_email_previews():
    ui = (ROOT / "core/notification_ui.py").read_text()
    assert ui.count('st.popover("Preview email"') == 2
    ec = (ROOT / "app_pages/email_center.py").read_text()
    assert "Email preview (as the recipient will see it)" in ec and "st.html(ms.body_html(" in ec
