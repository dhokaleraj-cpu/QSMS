from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_release_note():
    assert (ROOT / "VERSION").read_text().strip() in {"4.9.3", "4.9.4", "4.9.5", "4.9.6", "4.9.7", "4.9.8", "4.9.9", "4.10.0", "4.10.1", "4.10.2", "4.10.3", "4.10.5", "4.10.6", "4.10.7", "4.10.8", "4.10.9", "4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2"}
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
    assert any(token in config for token in ('primaryColor = "#315F79"', 'primaryColor = "#1884D8"', 'primaryColor = "#0A68AC"'))
    assert 'backgroundColor = "#F1F3F5"' in config or 'backgroundColor = "#F8FBFE"' in config
    assert 'textColor = "#1E2A33"' in config or 'textColor = "#121820"' in config
