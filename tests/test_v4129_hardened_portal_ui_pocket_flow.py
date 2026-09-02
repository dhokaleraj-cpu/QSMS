from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v4129_build_and_styles():
    assert (ROOT / "VERSION").read_text().strip() in {"4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.24"}
    ui = (ROOT / "core/ui.py").read_text()
    app = (ROOT / "streamlit_app.py").read_text()
    assert "4129-HARDENED-PORTAL-UI-POCKET-FLOW" in ui
    for token in ("div.st-key-fsi_left_rail", "background:var(--qcms-charcoal)!important", ".fsi-flow-wrap{display:grid!important", "border:1.25px solid var(--qcms-line-strong)!important", ".fsi-master-card-head{display:flex!important"):
        assert token in ui
    for token in ("supply-chain-report", "rmtc-report", "inward-report", "osp-balance-report", "dimensional-report", "metlab-report", "complaints-report", "npd-report", "apqp-report", "qc-report"):
        assert token in app

def test_workflow_has_card_markup():
    ui = (ROOT / "core/ui.py").read_text()
    assert 'class="fsi-flow-step fsi-flow-{state}"' in ui
    assert 'class="fsi-flow-index"' in ui
