from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v4117_release_and_build():
    assert (ROOT / "VERSION").read_text().strip() == "4.11.7"
    assert "4117-COMPLAINT-STAGE-EXPANDERS" in (ROOT / "core/ui.py").read_text()
    assert "4117-COMPLAINT-STAGE-EXPANDERS" in (ROOT / "core/auth.py").read_text()


def test_complaint_entry_has_a_to_e_collapsible_stage_sequence():
    text = (ROOT / "app_pages/complaints.py").read_text()
    for label in (
        "A - COMPLAINT DETAILS",
        "B - RESPONSIBILITY",
        "C - PHOTOGRAPHS & MULTIPLE ATTACHMENTS",
        "D - CONTAINMENT / ROOT CAUSE / CORRECTIVE ACTION",
        "E - DEBIT NOTE / COMMERCIAL SETTLEMENT",
    ):
        assert f'st.expander("{label}"' in text
    assert 'st.expander("A - COMPLAINT DETAILS", expanded=True)' in text
    for label in (
        "B - RESPONSIBILITY",
        "C - PHOTOGRAPHS & MULTIPLE ATTACHMENTS",
        "D - CONTAINMENT / ROOT CAUSE / CORRECTIVE ACTION",
        "E - DEBIT NOTE / COMMERCIAL SETTLEMENT",
    ):
        assert f'st.expander("{label}", expanded=False)' in text


def test_stage_heading_is_100_percent_larger_and_bold():
    text = (ROOT / "app_pages/complaints.py").read_text()
    assert "font-size:26px!important" in text
    assert "font-weight:900!important" in text
    assert "min-height:64px!important" in text


def test_existing_customer_and_supplier_palettes_remain_on_expandable_stages():
    text = (ROOT / "app_pages/complaints.py").read_text()
    for color in ("#D7EAFA", "#D7F0E8", "#E3DBFA", "#F8E5B9", "#F6D9E0", "#E0D7F6", "#D9EFDE", "#D5EDF4", "#F7DEC7", "#DDE6EC"):
        assert color in text
    assert "show_heading=False" in text
