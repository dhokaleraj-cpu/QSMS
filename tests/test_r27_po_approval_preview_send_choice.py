"""R27: PO preview with print sections before approval and a choice to send / not send to the supplier."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_both_approval_places_use_release_panel():
    sc = (ROOT / "app_pages/supply_chain.py").read_text()
    assert sc.count("_po_approval_release_panel(service,") == 2
    for token in ("PREVIEW BEFORE APPROVAL", "Send the approved PO to the supplier by email now", "(do not send)",
                  "notifier.po_print_options = dict(options)", "service.set_purchase_order_print_options(po_id, options)",
                  "SEND APPROVED PO TO SUPPLIER (preview, sections, To = supplier)"):
        assert token in sc, token
    assert "notification.notify(\n                            release_event" not in sc
