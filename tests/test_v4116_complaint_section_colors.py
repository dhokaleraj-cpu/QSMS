from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v4116_release_and_build():
    assert (ROOT / "VERSION").read_text().strip() == "4.11.6"
    assert "4116-COMPLAINT-SECTION-COLORS" in (ROOT / "core/ui.py").read_text()
    assert "4116-COMPLAINT-SECTION-COLORS" in (ROOT / "core/auth.py").read_text()


def test_customer_complaint_has_five_distinct_visible_section_palettes():
    text = (ROOT / "app_pages/complaints.py").read_text()
    for key in ("complaint_customer_details", "complaint_customer_responsibility", "complaint_customer_evidence", "complaint_customer_action", "complaint_customer_commercial"):
        assert key in text
    for color in ("#E7F3FF", "#E7F8F3", "#F0EBFF", "#FFF1D6", "#FCE9EE"):
        assert color in text


def test_supplier_complaint_has_five_distinct_visible_section_palettes():
    text = (ROOT / "app_pages/complaints.py").read_text()
    for key in ("complaint_supplier_details", "complaint_supplier_responsibility", "complaint_supplier_evidence", "complaint_supplier_action", "complaint_supplier_commercial"):
        assert key in text
    for color in ("#EEE9FF", "#E8F7EC", "#E6F5FA", "#FFEBD9", "#EAF0F5"):
        assert color in text
    assert 'background:transparent!important;border:0!important' in text
