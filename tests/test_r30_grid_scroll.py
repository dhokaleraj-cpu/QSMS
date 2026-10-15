"""R30: every grid scrolls left/right and up/down like an Excel sheet with visible scroll bars.

Root cause fixed here: Streamlit's global stylesheet sets
``*{scrollbar-width:thin;scrollbar-color:transparent transparent}``. In Chrome/Edge 121+ and the
Android WebView any standard ``scrollbar-*`` value disables ``::-webkit-scrollbar`` styling, so grid
scroll bars were transparent / overlay-only (macOS, Android) and could not be grabbed.
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_grid_scrollers_reset_standard_scrollbar_props_in_webkit_blink():
    import core.ui as ui
    css = ui.GRID_SCROLL_CSS
    assert "@@" not in css
    blink = re.search(r"@supports selector\(::-webkit-scrollbar\)\{(.*?)\}\}", css, re.S)
    assert blink, "WebKit/Blink branch missing"
    body = blink.group(1)
    for sel in (".qcms-enterprise-table-wrap", ".qcms-scroll-grid", 'div[data-testid="stDataFrame"] .dvn-scroller'):
        assert sel in body
    assert "scrollbar-width:auto!important" in body and "scrollbar-color:auto!important" in body
    # Firefox (no ::-webkit-scrollbar) still gets coloured, normal-width bars
    assert re.search(r"@supports not selector\(::-webkit-scrollbar\)\{.*scrollbar-color:#7E8B92 #EEF3F3!important", css, re.S)
    # no unconditional scrollbar-color left on grid scrollers (it would switch the styled bars off again)
    outside = re.sub(r"@supports[^{]*\{.*?\}\}", "", css, flags=re.S)
    assert "scrollbar-color" not in outside and "scrollbar-width" not in outside


def test_grid_scrollbars_are_visible_and_at_least_12px():
    import core.ui as ui
    css = ui.GRID_SCROLL_CSS
    assert ui.GRID_SCROLLBAR_PX >= 12
    assert f"::-webkit-scrollbar{{width:{ui.GRID_SCROLLBAR_PX}px!important;height:{ui.GRID_SCROLLBAR_PX}px!important" in css
    assert 'div[data-testid="stDataFrame"] .dvn-scroller::-webkit-scrollbar-thumb' in css
    assert "::-webkit-scrollbar-corner" in css and "::-webkit-scrollbar-track" in css
    assert "overflow:auto!important" in css and "touch-action:pan-x pan-y!important" in css
    # sticky header + first column for the HTML fallback grid
    assert "thead th{position:sticky!important;top:0" in css and "td:first-child{position:sticky!important;left:0" in css
    # applied on every page through the theme
    assert "st.markdown(grid_scroll_css(), unsafe_allow_html=True)" in (ROOT / "core/ui.py").read_text()


def test_native_grid_frames_never_wider_than_page():
    import core.ui as ui
    css = ui.GRID_SCROLL_CSS
    assert 'html body div[data-testid="stDataFrame"],html body div[data-testid="stDataEditor"]{max-width:100%!important;}' in css
    assert ':has(> [data-testid="stIFrame"]){max-width:100%!important;min-width:0!important;}' in css


def test_excel_grid_component_uses_styled_always_visible_bars():
    from core import excel_grid as eg
    frame = pd.DataFrame([{f"C{c}": f"r{r}c{c}" for c in range(25)} for r in range(40)])
    html = eg.grid_html(frame)
    wrap_rule = re.search(r"\.wrap\{[^}]*\}", html).group(0)
    assert "overflow:auto" in wrap_rule and "scrollbar-color" not in wrap_rule and "scrollbar-width" not in wrap_rule
    assert "@supports not selector(::-webkit-scrollbar){.wrap{scrollbar-width:auto;scrollbar-color:#7E8B92 #EEF3F3}}" in html
    assert f".wrap::-webkit-scrollbar{{width:{eg.SCROLLBAR_PX}px;height:{eg.SCROLLBAR_PX}px" in html
    assert eg.SCROLLBAR_PX >= 12
    # frozen header + first column, drag / swipe / keys
    assert "th{position:sticky;top:0" in html and "td:first-child,th:first-child{position:sticky;left:0" in html
    assert "touch-action:pan-x pan-y" in html and "ArrowRight" in html
    # pressing on the scroll bar drags the bar, not the sheet
    assert "onBar(e)" in html


def test_grid_heights_reserve_room_for_the_horizontal_bar():
    from core import excel_grid as eg
    # one-row grid: frame = filter bar + header + row + scroll bar (the row is never hidden under the bar)
    assert eg.grid_height(1) >= eg.BAR_PX + eg.HEAD_PX + eg.ROW_PX + eg.SCROLLBAR_PX
    html = eg.grid_html(pd.DataFrame([{"a": 1, "b": 2}]))
    wrap_h = int(re.search(r"\.wrap\{[^}]*height:(\d+)px", html).group(1))
    assert wrap_h == eg.ROW_PX + 2 + eg.HEAD_PX + eg.SCROLLBAR_PX
    # native grids: ~14 rows visible, rest scroll inside; bar space added; capped
    assert eg.editor_height(3) == 4 * eg.EDITOR_ROW_PX + 3 + eg.SCROLLBAR_PX
    assert eg.editor_height(200) == eg.EDITOR_MAX_PX
    assert eg.EDITOR_MAX_PX // eg.EDITOR_ROW_PX >= 14


def test_fallback_html_grid_still_scrolls_and_drag_ignores_scrollbar(monkeypatch):
    import core.ui as ui
    import core.excel_grid as eg
    captured = []
    monkeypatch.setattr(ui.st, "markdown", lambda html, **_: captured.append(html))
    monkeypatch.setattr(eg, "render_grid", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no components")))
    ui.portal_table(pd.DataFrame([{f"Col {c}": r for c in range(25)} for r in range(40)]))
    html = captured[-1]
    assert 'class="qcms-enterprise-table-wrap qcms-scroll-grid"' in html and "max-height:" in html
    assert "g.clientWidth" in ui.GRID_DRAG_SCRIPT and "g.clientHeight" in ui.GRID_DRAG_SCRIPT
