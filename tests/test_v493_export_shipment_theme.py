from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_release_note():
    assert (ROOT / "VERSION").read_text().strip() in {"4.9.3", "4.9.4"}
    assert (ROOT / "docs/RELEASE_4_9_3.md").exists()


def test_high_contrast_export_shipment_theme_is_streamlit_wrapper_safe():
    ui = (ROOT / "core" / "ui.py").read_text()
    for token in (
        '[class*="st-key-fsi_shell"] div[data-testid="stVerticalBlockBorderWrapper"]',
        'linear-gradient(110deg,#073462 0%,#073E78 46%,#0A68AC 100%)',
        '[class*="st-key-fsi_top_nav"] div[data-testid="stVerticalBlockBorderWrapper"]',
        'background:#F3F8FC!important',
        '[class*="st-key-menu_active_"]',
        '.stApp [data-stale="true"]{opacity:1!important;}',
        '--erp-font:Aptos',
    ):
        assert token in ui


def test_streamlit_theme_matches_export_shipment_background():
    config = (ROOT / ".streamlit" / "config.toml").read_text()
    assert 'primaryColor = "#0B6FA4"' in config
    assert 'backgroundColor = "#EEF5FB"' in config
    assert 'textColor = "#14283A"' in config
