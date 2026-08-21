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
    assert (ROOT / "VERSION").read_text().strip() in {"4.10.2", "4.10.3", "4.10.5", "4.10.6", "4.10.7", "4.10.8", "4.10.9", "4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2"}
