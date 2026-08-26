from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_and_build():
    assert (ROOT / "VERSION").read_text().strip() in {"4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9"}
    assert "DRAWING REVISION HISTORY" in (ROOT / "app_pages/part_master.py").read_text()


def test_part_master_controlled_drawing_fields_and_history():
    text = (ROOT / "app_pages/part_master.py").read_text()
    for token in (
        "CONTROLLED DRAWINGS",
        "Drawing Number",
        "Revision Number",
        "Revision Date",
        "DRAWING REVISION HISTORY",
        "Download Selected Drawing Revision",
        "qcms_activate_part_drawing_revision",
        "Previous revision is now INACTIVE",
    ):
        assert token in text
    assert "upsert\": \"false" in text


def test_database_enforces_one_active_revision_and_preserves_history():
    sql = (ROOT / "supabase/migrations/20260814102000_qcms_controlled_drawing_revision_history_v4113.sql").read_text()
    for token in (
        "drawing_number",
        "revision_date",
        "superseded_at",
        "superseded_by",
        "ux_document_attachments_one_active_part_drawing",
        "ux_document_attachments_part_drawing_revision",
        "qcms_activate_part_drawing_revision",
        "status='INACTIVE'",
        "status, created_by, updated_by",
    ):
        assert token in sql
    assert "delete from public.document_attachments" not in sql.lower()
    assert "truncate" not in sql.lower()


def test_part_summary_is_derived_from_active_finish_drawing():
    text = (ROOT / "app_pages/part_master.py").read_text()
    assert '"Current Finish Drawing No."' in text
    assert '"Current Finish Revision"' in text
    assert "drawing_number=drawing_no, drawing_revision=rev_no" in (ROOT / "supabase/migrations/20260814102000_qcms_controlled_drawing_revision_history_v4113.sql").read_text()
