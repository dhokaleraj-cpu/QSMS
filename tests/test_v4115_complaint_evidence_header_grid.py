from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_build_and_header_grid():
    assert (ROOT / "VERSION").read_text().strip() in {"4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12"}
    ui = (ROOT / "core/ui.py").read_text()
    auth = (ROOT / "core/auth.py").read_text()
    assert any(marker in ui for marker in ("4115-COMPLAINT-EVIDENCE-HEADER-GRID", "4116-COMPLAINT-SECTION-COLORS", "4117-COMPLAINT-STAGE-EXPANDERS", "4118-GLOBAL-STAGED-SECTIONS"))
    assert any(marker in auth for marker in ("4115-COMPLAINT-EVIDENCE-HEADER-GRID", "4116-COMPLAINT-SECTION-COLORS", "4117-COMPLAINT-STAGE-EXPANDERS", "4118-GLOBAL-STAGED-SECTIONS"))
    assert "st.columns([3.0, 5.4, 3.2]" in ui
    assert 'key="fsi_header_actions_row"' in ui
    assert "a1, a2 = st.columns(2" in ui
    assert "height:31px!important" in ui
    assert "flex-wrap:nowrap!important" in ui


def test_new_and_existing_complaints_show_evidence_on_entry():
    text = (ROOT / "app_pages/complaints.py").read_text()
    assert "_stage_new_complaint_media(complaint_type, writable" in text
    assert "_upload_staged_complaint_media(repo, saved_id, staged_media)" in text
    assert "Select one or multiple photographs" in text
    assert "Photograph {index} Title" in text
    assert "Add Selected Photographs" in text
    assert "accept_multiple_files=True" in text
    assert '_render_complaint_media(repo, existing, perms, allow_upload=True, title="PHOTOGRAPHS & MULTIPLE ATTACHMENTS"' in text


def test_customer_supplier_sections_use_global_blue_stage_grading():
    complaints = (ROOT / "app_pages/complaints.py").read_text()
    ui = (ROOT / "core/ui.py").read_text()
    # Customer and Supplier entries use the same global A→G stage framework.
    for token in (
        'key=f"{complaint_type.lower()}_complaint_details"',
        'key=f"{complaint_type.lower()}_complaint_responsibility"',
        'key=f"{complaint_type.lower()}_complaint_evidence"',
        'key=f"{complaint_type.lower()}_complaint_action"',
        'key=f"{complaint_type.lower()}_complaint_commercial"',
        'key=f"{complaint_type.lower()}_complaint_followup"',
    ):
        assert token in complaints
    # v4.11.8 deliberately replaces customer/supplier multicolor palettes with one QCMS blue family.
    for color in ("#E3F1FD", "#DAECFB", "#D1E7F9", "#C8E2F7", "#BFDCF5"):
        assert color in ui
    assert 'with st.expander(f"{letter} - {title}", expanded=False)' in ui


def test_complaint_media_schema_remains_additive():
    sql = (ROOT / "supabase/migrations/20260816160000_qcms_complaint_media_v4114.sql").read_text().lower()
    assert "document_title" in sql
    assert "truncate" not in sql
    assert "delete from public.quality_complaints" not in sql
