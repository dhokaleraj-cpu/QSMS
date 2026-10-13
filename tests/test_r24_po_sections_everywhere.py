"""R24: 'Sections shown on print' grid in PO Entry, Order List, Edit PO, PO PDF, batch print and every PO email."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_section_options_cover_all_flags_with_short_labels():
    from core.po_print_ui import SECTION_OPTIONS
    from core.supply_chain_service import PO_PRINT_FLAGS
    assert {f for f, _ in SECTION_OPTIONS} == set(PO_PRINT_FLAGS)
    assert max(len(label) for _, label in SECTION_OPTIONS) <= 32


def test_panels_wired_everywhere():
    sc = (ROOT / "app_pages/supply_chain.py").read_text()
    for key in ('key="po_register_sections"', 'key="po_list_sections"', 'key="po_edit_sections"', 'key="po_pdf_sections"',
                '"controlled_po_sections"', '"po_batch_sections"', '"po_batch_mail_sections"', '"po_approval_mail_sections"'):
        assert key in sc, key
    assert "_po_print_sections_editor" not in sc
    ui = (ROOT / "core/notification_ui.py").read_text()
    assert 'related_table == "supply_purchase_orders"' in ui and "notifier.po_print_options = dict(po_options)" in ui
    assert ui.count('getattr(self, "po_print_options", None)') == 0
    ns = (ROOT / "core/notification_service.py").read_text()
    assert ns.count('getattr(self, "po_print_options", None)') == 2
    assert "SECTION_OPTIONS" in (ROOT / "app_pages/print_designer.py").read_text()


def test_email_override_changes_generated_pdf():
    from core.po_print_ui import with_options
    assert with_options({"po_number": "X", "print_options": {"show_vendor": True}}, {"show_vendor": False})["print_options"] == {"show_vendor": False}
