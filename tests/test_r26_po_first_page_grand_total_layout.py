"""R26: wide register PDFs never raise LayoutError, PO lines fill the first page, GRAND TOTAL row after all lines."""
import copy
from io import BytesIO

import pandas as pd
from pypdf import PdfReader


def test_wide_register_pdf_no_layout_error():
    from core.reporting import controlled_record_pdf_bytes
    cols = [f"Column Name {i} Long Header" for i in range(34)]
    frame = pd.DataFrame([{c: ("Some long value text " * 8 if j % 5 == 0 else f"V{i}-{j}") for j, c in enumerate(cols)} for i in range(40)])
    pdf = controlled_record_pdf_bytes("Purchase Order Register", {"Record Count": 40}, {"Purchase Order Register": frame})
    text = PdfReader(BytesIO(pdf)).pages[0].extract_text()
    assert "columns 1 of" in text


def _items(n, src=1):
    from core.print_samples import po_sample
    header, items = po_sample()
    out = []
    for i in range(n):
        it = copy.deepcopy(items[0]); it["item_no"] = f"RM-{i + 1}"; it["quantity"] = 1000
        it["customer_source_rows"] = it["customer_source_rows"][:src]; it["price_history_snapshot"] = it["price_history_snapshot"][:1]
        out.append(it)
    return header, out


def test_lines_fill_first_page_when_sections_hidden_and_grand_total():
    from core.purchase_order_reporting import purchase_order_pdf_bytes
    header, items = _items(2)
    header["print_options"] = {"show_technical": False, "show_price_history": False}
    pages = [p.extract_text() for p in PdfReader(BytesIO(purchase_order_pdf_bytes(header, items, terms_path="/x.pdf"))).pages]
    assert len(pages) == 1 and all(f"{i}/2" in pages[0] for i in (1, 2))
    assert "GRAND TOTAL · ALL PO LINES" in pages[0] and "2,000 KGS" in pages[0]


def test_grand_total_after_last_line_on_continuation():
    from core.purchase_order_reporting import purchase_order_pdf_bytes
    header, items = _items(4, src=3)
    pages = [p.extract_text() for p in PdfReader(BytesIO(purchase_order_pdf_bytes(header, items, terms_path="/x.pdf"))).pages]
    joined = "".join(pages)
    assert joined.count("GRAND TOTAL · ALL PO LINES") == 1 and joined.index("4/4") < joined.index("GRAND TOTAL · ALL PO LINES")
    single_header, single = _items(1)
    assert "GRAND TOTAL · ALL PO LINES" not in PdfReader(BytesIO(purchase_order_pdf_bytes(single_header, single, terms_path="/x.pdf"))).pages[0].extract_text()
