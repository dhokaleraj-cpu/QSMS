from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v4117_release_continuity_and_v4118_build():
    assert (ROOT / "VERSION").read_text().strip() in {"4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6"}
    ui = (ROOT / "core/ui.py").read_text()
    auth = (ROOT / "core/auth.py").read_text()
    assert "4118-GLOBAL-STAGED-SECTIONS" in ui
    assert "4118-GLOBAL-STAGED-SECTIONS" in auth


def test_complaint_entry_has_a_to_g_collapsed_stage_sequence():
    text = (ROOT / "app_pages/complaints.py").read_text()
    expected = (
        ("A", "COMPLAINT DETAILS"),
        ("B", "RESPONSIBILITY"),
        ("C", "PHOTOGRAPHS & MULTIPLE ATTACHMENTS"),
        ("D", "CONTAINMENT / ROOT CAUSE / CORRECTIVE ACTION"),
        ("E", "DEBIT NOTE / COMMERCIAL SETTLEMENT"),
        ("F", "COMPLAINT FOLLOW-UP & CLOSURE TRACKING"),
        ("G", "PRINT / DELETE"),
    )
    for stage, label in expected:
        assert f'stage_section("{stage}", "{label}"' in text


def test_global_stage_heading_is_100_percent_larger_bold_and_collapsed():
    ui = (ROOT / "core/ui.py").read_text()
    assert 'with st.expander(f"{letter} - {title}", expanded=False)' in ui
    assert "font-size:26px!important" in ui
    assert "font-weight:900!important" in ui
    assert "min-height:64px!important" in ui
