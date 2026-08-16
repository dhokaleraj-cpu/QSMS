from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_and_build():
    assert (ROOT / "VERSION").read_text().strip() == "4.11.4"
    assert "4114-COMPLAINT-MEDIA-HEADER-FIX" in (ROOT / "core/ui.py").read_text()
    assert "4114-COMPLAINT-MEDIA-HEADER-FIX" in (ROOT / "core/auth.py").read_text()


def test_customer_supplier_entries_have_titled_photos_and_repeatable_attachments():
    text = (ROOT / "app_pages/complaints.py").read_text()
    for token in (
        "Photograph Title",
        "Add Photograph",
        "accept_multiple_files=True",
        "Add Selected Attachments",
        "Photograph Register",
        "Attachment Register",
        "COMPLAINT_PHOTO",
        "COMPLAINT_ATTACHMENT",
        "PHOTOGRAPHS & MULTIPLE ATTACHMENTS",
        "PHOTOGRAPHS & ATTACHMENTS REGISTER",
    ):
        assert token in text
    assert "_render_complaint_media(repo, existing, perms, allow_upload=True)" in text


def test_additional_attachment_storage_is_unique_and_append_only():
    text = (ROOT / "core/attachments.py").read_text()
    assert "def upload_additional" in text
    assert "document_title" in text
    assert "uuid.uuid4().hex[:12]" in text
    assert '"upsert": "false"' in text


def test_complaint_media_migration_is_additive_and_permission_aware():
    sql = (ROOT / "supabase/migrations/20260816160000_qcms_complaint_media_v4114.sql").read_text()
    for token in (
        "document_title",
        "idx_document_attachments_complaint_media",
        "QUALITY_COMPLAINT",
        "COMPLAINT_MANAGEMENT",
        "COMPLAINT_PHOTO",
        "COMPLAINT_ATTACHMENT",
        "(storage.foldername(name))[2]='complaints'",
    ):
        assert token in sql
    lowered = sql.lower()
    assert "truncate" not in lowered
    assert "delete from public.quality_complaints" not in lowered


def test_header_actions_have_dedicated_non_overlapping_column():
    text = (ROOT / "core/ui.py").read_text()
    assert "st.columns([2.8, 4.8, 2.25, 1.25]" in text
    assert 'key="fsi_header_actions"' in text
    assert "dedicated header action rail" in text
    assert 'account, exit_col = st.columns' not in text
