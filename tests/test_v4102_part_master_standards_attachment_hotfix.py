from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_part_master_imports_part_label():
    text = (ROOT / "app_pages" / "part_master.py").read_text()
    assert "part_label" in text.split("from core.selection_labels import", 1)[1].split("\n", 1)[0]
    assert "part_label(row)" in text


def test_standards_bank_has_first_save_attachment_uploader():
    text = (ROOT / "app_pages" / "standards_bank.py").read_text()
    assert "Upload Standard / Specification File" in text
    assert "new_standard_attachment" in text
    assert 'entity_type="CUSTOMER_STANDARD"' in text
    assert "render_attachment_manager" in text


def test_patch_version():
    assert (ROOT / "VERSION").read_text().strip() in {"4.10.2", "4.10.3", "4.10.5", "4.10.6", "4.10.7", "4.10.8", "4.10.9"}
