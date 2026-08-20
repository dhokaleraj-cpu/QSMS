from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v4116_release_continuity():
    assert (ROOT / "VERSION").read_text().strip() in {"4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4"}
    ui = (ROOT / "core/ui.py").read_text()
    assert any(marker in ui for marker in ("4116-COMPLAINT-SECTION-COLORS", "4117-COMPLAINT-STAGE-EXPANDERS", "4118-GLOBAL-STAGED-SECTIONS"))


def test_v4118_replaces_unrelated_complaint_palettes_with_one_blue_family():
    ui = (ROOT / "core/ui.py").read_text()
    complaints = (ROOT / "app_pages/complaints.py").read_text()
    for token in ("st-key-fsi_stage_a_", "st-key-fsi_stage_b_", "st-key-fsi_stage_c_", "st-key-fsi_stage_d_", "st-key-fsi_stage_e_"):
        assert token in ui
    # complaint stages must now use the same global stage framework rather than separate customer/supplier colour families
    for label in ("COMPLAINT DETAILS", "RESPONSIBILITY", "PHOTOGRAPHS & MULTIPLE ATTACHMENTS", "CONTAINMENT / ROOT CAUSE / CORRECTIVE ACTION", "DEBIT NOTE / COMMERCIAL SETTLEMENT"):
        assert f'stage_section(' in complaints and label in complaints
    assert "global QCMS staged-section CSS" in complaints
