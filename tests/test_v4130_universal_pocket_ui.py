from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_v4130_ui_contract():
    ui=(ROOT/'core/ui.py').read_text()
    npd=(ROOT/'app_pages/npd_apqp.py').read_text()
    assert '4130-UNIVERSAL-POCKET-CARD-FIELD-SYSTEM' in ui
    for token in ['npd-order-status-row','npd-row-process-card','qcms-pocket-grid','stVerticalBlockBorderWrapper','stWidgetLabel']:
        assert token in ui or token in npd
    assert 'border:1.35px solid #AEB7BF' in ui
    assert 'font-weight:900!important' in ui
