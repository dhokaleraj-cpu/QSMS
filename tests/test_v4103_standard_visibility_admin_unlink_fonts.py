from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_4103():
    assert (ROOT / "VERSION").read_text().strip() in {"4.10.3", "4.10.5", "4.10.6", "4.10.7", "4.10.8", "4.10.9", "4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5"}


def test_part_standard_download_shows_required_details_and_admin_unlink():
    text = (ROOT / "app_pages" / "part_master.py").read_text()
    assert "standard_name_text" in text
    assert "author_text" in text
    assert "process_text" in text
    assert "ADMIN APPROVAL — Unlink Standard from Part" in text
    assert "is_admin(current_profile())" in text
    assert 'table="part_standard_links"' in text
    assert "Add Selected Standards" in text
    # ordinary linking must no longer delete links as a side effect of multiselect save
    link_block = text.split("part_master_render_entry_d", 1)[1].split("part_master_render_entry_e", 1)[0]
    assert 'repo.delete("part_standard_links"' not in link_block


def test_database_enforces_admin_only_unlink():
    text = (ROOT / "supabase" / "migrations" / "20260812184500_qcms_admin_standard_unlink_readability_v4103.sql").read_text()
    assert "qcms_admin_only_part_standard_unlink" in text
    assert "current_app_role()='ADMIN'" in text
    assert "before delete on public.part_standard_links" in text


def test_readability_layer_is_present():
    text = (ROOT / "core" / "ui.py").read_text()
    assert "readability" in text
    assert "font-weight:450!important" in text
    assert "font-weight:880!important" in text
    assert "font-weight:900!important" in text
