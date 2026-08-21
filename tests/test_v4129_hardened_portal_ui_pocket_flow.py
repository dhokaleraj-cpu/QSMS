from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v4129_build_and_styles():
    assert (ROOT / "VERSION").read_text().strip() in {"4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6"}
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
