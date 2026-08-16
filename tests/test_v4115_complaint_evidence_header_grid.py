from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_build_and_header_grid():
    assert (ROOT / "VERSION").read_text().strip() == "4.11.5"
    ui = (ROOT / "core/ui.py").read_text()
    auth = (ROOT / "core/auth.py").read_text()
    assert "4115-COMPLAINT-EVIDENCE-HEADER-GRID" in ui
    assert "4115-COMPLAINT-EVIDENCE-HEADER-GRID" in auth
    assert "st.columns([3.0, 5.4, 3.2]" in ui
    assert 'key="fsi_header_actions_row"' in ui
    assert "a1, a2 = st.columns(2" in ui
    assert "height:31px!important" in ui
    assert "flex-wrap:nowrap!important" in ui


def test_new_and_existing_complaints_show_evidence_on_entry():
    text = (ROOT / "app_pages/complaints.py").read_text()
    assert "_stage_new_complaint_media(complaint_type, writable)" in text
    assert "_upload_staged_complaint_media(repo, saved_id, staged_media)" in text
    assert "Select one or multiple photographs" in text
    assert "Photograph {index} Title" in text
    assert "Add Selected Photographs" in text
    assert "accept_multiple_files=True" in text
    assert '_render_complaint_media(repo, existing, perms, allow_upload=True, title="PHOTOGRAPHS & MULTIPLE ATTACHMENTS")' in text


def test_customer_supplier_sections_have_distinct_color_grades():
    text = (ROOT / "app_pages/complaints.py").read_text()
    for token in (
        "complaint_customer_details", "complaint_customer_responsibility", "complaint_customer_evidence",
        "complaint_customer_action", "complaint_customer_commercial", "complaint_customer_followup",
        "complaint_supplier_details", "complaint_supplier_responsibility", "complaint_supplier_evidence",
        "complaint_supplier_action", "complaint_supplier_commercial", "complaint_supplier_followup",
        "#2F80C7", "#159A8B", "#6C55C4", "#D59616", "#C94D6A",
        "#8056C7", "#348D59", "#2A90B1", "#D4742C", "#657B8B",
    ):
        assert token in text


def test_complaint_media_schema_remains_additive():
    sql = (ROOT / "supabase/migrations/20260816160000_qcms_complaint_media_v4114.sql").read_text().lower()
    assert "document_title" in sql
    assert "truncate" not in sql
    assert "delete from public.quality_complaints" not in sql
