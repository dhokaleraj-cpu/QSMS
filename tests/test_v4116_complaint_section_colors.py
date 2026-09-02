from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v4116_release_continuity():
    assert (ROOT / "VERSION").read_text().strip() in {"4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.24", "4.14.25"}
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
