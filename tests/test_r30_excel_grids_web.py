"""R30: website grids slide like a spreadsheet (drag / swipe, frozen panes, filter)."""
import pandas as pd


def test_grid_html_has_frozen_panes_drag_and_filter():
    from core.excel_grid import grid_html, grid_height
    frame = pd.DataFrame([{"PO": f"P{r}", **{f"C{c}": r * c for c in range(15)}, "Status": "APPROVED"} for r in range(80)])
    html = grid_html(frame)
    assert "position:sticky;top:0" in html and "position:sticky;left:0" in html
    assert "pointerdown" in html and "scrollLeft=sl-dx" in html and "touch-action:pan-x pan-y" in html
    assert 'id="q"' in html and "80 row(s) × 17 column(s)" in html
    assert 'data-d="l"' in html and 'data-d="d"' in html and "ArrowDown" in html
    assert ">Approved<" in html
    assert grid_height(80) < grid_height(80, 900)


def test_portal_table_uses_component(monkeypatch):
    import core.ui as ui
    import core.excel_grid as eg
    seen = {}
    monkeypatch.setattr(eg, "render_grid", lambda frame, **k: seen.update(rows=len(frame.index), **k))
    ui.portal_table(pd.DataFrame([{"a": 1}, {"a": 2}]), height=300)
    assert seen == {"rows": 2, "hide_index": True, "height": 300}


def test_streamlit_editors_get_height_and_pinned_column(monkeypatch):
    import streamlit as st
    from core import excel_grid as eg
    calls = []
    monkeypatch.setattr(st, "data_editor", lambda data, *a, **k: calls.append(k) or data, raising=False)
    monkeypatch.setattr(st, "dataframe", lambda data=None, *a, **k: calls.append(k), raising=False)
    monkeypatch.setattr(st, "_qcms_excel_grids", False, raising=False)
    eg.install_streamlit_grid_defaults()
    frame = pd.DataFrame([{"Id": 1, "Part": "K1", "Qty": 2}] * 30)
    st.data_editor(frame, column_config={"Id": None, "Qty": {"type_config": {}}}, num_rows="dynamic")
    k = calls[-1]
    assert k["height"] == eg.EDITOR_MAX_PX and k["column_config"]["Part"] == {"pinned": True} and k["column_config"]["Id"] is None
    st.dataframe(pd.DataFrame([{"x": 1}]))
    assert calls[-1]["height"] == eg.editor_height(1) and calls[-1]["column_config"]["x"]["pinned"] is True


def test_app_installs_grid_defaults():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "streamlit_app.py").read_text()
    assert "install_streamlit_grid_defaults()" in src
