"""QCMS R30 · Excel-style grids for the website.

* Display grids (portal_table) render in a small HTML component with:
  frozen header row + frozen first column, always-visible scroll bars, drag-to-slide with the
  mouse (like a touch swipe), finger swipe on phone / tablet, wheel / Shift+wheel, arrow keys,
  ◀ ▶ ▲ ▼ page buttons and a quick filter box.
* Editing grids (st.data_editor) and st.dataframe keep Streamlit's native grid but always get a
  fixed height (rows scroll inside the grid, not the page) and a pinned first column.
"""
from __future__ import annotations

import html as _html
import json
from typing import Any

ROW_PX = 34
HEAD_PX = 40
BAR_PX = 40
MAX_BODY_PX = 520
EDITOR_ROW_PX = 35
EDITOR_MAX_PX = 520
SCROLLBAR_PX = 14   # always-visible Excel-style scroll bar (height reserved so no row hides under it)

STATUS_STYLE = {
    "PASS": ("#166534", "#DCFCE7"), "ACCEPTED": ("#166534", "#DCFCE7"), "APPROVED": ("#166534", "#DCFCE7"), "ACTIVE": ("#166534", "#DCFCE7"),
    "COMPLETED": ("#166534", "#DCFCE7"), "CLOSED": ("#166534", "#DCFCE7"), "CONFIRMED": ("#166534", "#DCFCE7"), "FINAL": ("#166534", "#DCFCE7"), "VALID": ("#166534", "#DCFCE7"),
    "FAIL": ("#991B1B", "#FEE2E2"), "REJECTED": ("#991B1B", "#FEE2E2"), "CANCELLED": ("#991B1B", "#FEE2E2"), "OVERDUE": ("#991B1B", "#FEE2E2"), "INACTIVE": ("#475569", "#E2E8F0"),
    "PENDING": ("#92400E", "#FEF3C7"), "PENDING_APPROVAL": ("#92400E", "#FEF3C7"), "DRAFT": ("#92400E", "#FEF3C7"), "ON_HOLD": ("#92400E", "#FEF3C7"), "IN_PROGRESS": ("#92400E", "#FEF3C7"),
    "OPEN": ("#0B6E70", "#E3F2F2"),
}
STATUS_TOKENS = ("status", "result", "decision", "disposition", "validation", "workflow", "recommendation", "action")


def _show(value: Any) -> str:
    import math
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return ""
    except Exception:
        pass
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        if abs(value - round(value)) < 1e-9:
            return f"{int(round(value)):,}"
        return f"{value:,.3f}".rstrip("0").rstrip(".")
    text = str(value)
    return "" if text in {"None", "nan", "NaT"} else text


def grid_height(rows: int, height: int | None = None) -> int:
    body = min(max(rows, 1) * ROW_PX + 2, height or MAX_BODY_PX)
    return HEAD_PX + BAR_PX + body + SCROLLBAR_PX + 8


def grid_html(frame: Any, *, hide_index: bool = True, height: int | None = None) -> str:
    """Self-contained HTML document (CSS + JS) for one Excel-style grid."""
    columns = [str(c) for c in frame.columns]
    if not hide_index:
        columns = ["#"] + columns
    head = "".join(f"<th>{_html.escape(c)}</th>" for c in columns)
    body_rows: list[str] = []
    for index, row in frame.iterrows():
        cells: list[str] = []
        if not hide_index:
            cells.append(f"<td>{_html.escape(_show(index))}</td>")
        for col in frame.columns:
            raw = row.get(col)
            text = _show(raw)
            key = str(col).casefold()
            canonical = text.strip().upper().replace(" ", "_")
            numeric = isinstance(raw, (int, float)) and not isinstance(raw, bool)
            if text and (any(t in key for t in STATUS_TOKENS) or canonical in STATUS_STYLE) and canonical in STATUS_STYLE:
                fg, bg = STATUS_STYLE[canonical]
                cells.append(f'<td><span class="chip" style="color:{fg};background:{bg}">{_html.escape(text.replace("_", " ").title())}</span></td>')
            else:
                cells.append(f'<td class="{"num" if numeric else ""}" title="{_html.escape(text)}">{_html.escape(text)}</td>')
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    body_px = min(max(len(body_rows), 1) * ROW_PX + 2, height or MAX_BODY_PX)
    info = f"{len(body_rows):,} row(s) × {len(columns)} column(s)"
    table = (f'<table><thead><tr>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table>'
             if body_rows else '<div class="empty">No records available.</div>')
    return """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}html,body{margin:0;padding:0;background:transparent;font-family:Roboto,"Segoe UI",Arial,sans-serif;color:#173233}
.bar{display:flex;align-items:center;gap:6px;height:%(bar)dpx;padding:0 2px}
.bar input{flex:1;min-width:60px;height:30px;border:1px solid #B5CFCF;border-radius:8px;padding:0 10px;font-size:12px}
.bar button{height:30px;min-width:32px;border:1px solid #B5CFCF;background:#fff;border-radius:8px;color:#0B6E70;font-weight:700;cursor:pointer}
.bar button:active{background:#E3F2F2}.info{font-size:11px;color:#5C7778;white-space:nowrap}
.wrap{position:relative;overflow:auto;height:%(h)dpx;max-width:100%%;border:1px solid #B5CFCF;border-radius:8px;background:#fff;
  cursor:grab;touch-action:pan-x pan-y;-webkit-overflow-scrolling:touch;overscroll-behavior:contain}
.wrap.drag{cursor:grabbing;user-select:none}
/* R30: a standard scrollbar-color/width value turns OFF ::-webkit-scrollbar styling in Chrome/Edge 121+
   (bars then become thin overlays on macOS / Android). WebKit/Blink get the always-visible styled bar,
   Firefox gets scrollbar-color. */
@supports not selector(::-webkit-scrollbar){.wrap{scrollbar-width:auto;scrollbar-color:#7E8B92 #EEF3F3}}
.wrap::-webkit-scrollbar{width:%(sb)dpx;height:%(sb)dpx;background:#EEF3F3;-webkit-appearance:none}
.wrap::-webkit-scrollbar-thumb{background:#7E8B92;border-radius:8px;border:3px solid #EEF3F3;min-width:36px;min-height:36px}
.wrap::-webkit-scrollbar-thumb:hover{background:#0F8B8D}
.wrap::-webkit-scrollbar-track{background:#EEF3F3}.wrap::-webkit-scrollbar-corner{background:#EEF3F3}
table{border-collapse:separate;border-spacing:0;width:max-content;min-width:100%%;font-size:12px}
th,td{height:%(row)dpx;padding:0 10px;white-space:nowrap;max-width:340px;overflow:hidden;text-overflow:ellipsis;border-right:1px solid #DDE7E7;border-bottom:1px solid #E3EAEA;text-align:left}
th{position:sticky;top:0;z-index:2;background:#E3F2F2;color:#0B6E70;font-weight:800;height:%(head)dpx;border-bottom:1px solid #B5CFCF}
td:first-child,th:first-child{position:sticky;left:0;z-index:1;background:#fff;font-weight:700;box-shadow:1px 0 0 #B5CFCF}
th:first-child{z-index:3;background:#E3F2F2}tbody tr:nth-child(even) td{background:#F8FBFB}tbody tr:nth-child(even) td:first-child{background:#F3F8F8}
tbody tr:hover td{background:#EAF5F5}td.num{text-align:right;font-variant-numeric:tabular-nums}
.chip{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700}.empty{padding:22px;color:#5C7778;font-size:13px}
</style></head><body>
<div class="bar"><input id="q" placeholder="Filter rows…" aria-label="Filter rows"><span class="info" id="info">%(info)s</span>
<button data-d="l" title="Scroll left">◀</button><button data-d="r" title="Scroll right">▶</button><button data-d="u" title="Scroll up">▲</button><button data-d="d" title="Scroll down">▼</button></div>
<div class="wrap" id="w" tabindex="0">%(table)s</div>
<script>
(function(){var w=document.getElementById('w'),q=document.getElementById('q'),info=document.getElementById('info'),total=%(total)d;
var down=false,moved=false,sx=0,sy=0,sl=0,st=0;
function onBar(e){var r=w.getBoundingClientRect();return e.clientX-r.left-w.clientLeft>=w.clientWidth||e.clientY-r.top-w.clientTop>=w.clientHeight;}
w.addEventListener('pointerdown',function(e){if(e.pointerType!=='mouse'||e.button!==0||onBar(e))return;down=true;moved=false;sx=e.clientX;sy=e.clientY;sl=w.scrollLeft;st=w.scrollTop;});
window.addEventListener('pointermove',function(e){if(!down)return;var dx=e.clientX-sx,dy=e.clientY-sy;if(!moved&&Math.abs(dx)+Math.abs(dy)>4){moved=true;w.classList.add('drag');}
 if(moved){w.scrollLeft=sl-dx;w.scrollTop=st-dy;e.preventDefault();}});
window.addEventListener('pointerup',function(){down=false;setTimeout(function(){w.classList.remove('drag');},0);});
w.addEventListener('click',function(e){if(moved){e.stopPropagation();e.preventDefault();moved=false;}},true);
document.querySelectorAll('.bar button').forEach(function(b){b.addEventListener('click',function(){var d=b.getAttribute('data-d'),px=w.clientWidth*0.8,py=w.clientHeight*0.8;
 w.scrollBy({left:d==='l'?-px:d==='r'?px:0,top:d==='u'?-py:d==='d'?py:0,behavior:'smooth'});});});
w.addEventListener('keydown',function(e){var m={ArrowLeft:[-60,0],ArrowRight:[60,0],ArrowUp:[0,-%(row)d],ArrowDown:[0,%(row)d],PageDown:[0,w.clientHeight],PageUp:[0,-w.clientHeight]}[e.key];
 if(m){w.scrollBy(m[0],m[1]);e.preventDefault();}});
q.addEventListener('input',function(){var t=q.value.toLowerCase(),n=0;document.querySelectorAll('tbody tr').forEach(function(r){var ok=!t||r.textContent.toLowerCase().indexOf(t)>=0;r.style.display=ok?'':'none';if(ok)n++;});
 info.textContent=(t?n+' of ':'')+total+' row(s)';});
})();
</script></body></html>""" % {"bar": BAR_PX, "h": body_px + HEAD_PX + SCROLLBAR_PX, "sb": SCROLLBAR_PX, "row": ROW_PX, "head": HEAD_PX, "info": _html.escape(info),
                              "table": table, "total": len(body_rows)}


def render_grid(frame: Any, *, hide_index: bool = True, height: int | None = None) -> None:
    import streamlit as st
    doc = grid_html(frame, hide_index=hide_index, height=height)
    px = grid_height(len(frame.index), height)
    if hasattr(st, "iframe"):          # Streamlit 1.60+: st.components.v1.html is being removed
        st.iframe(doc, height=px)
        return
    import streamlit.components.v1 as components
    components.html(doc, height=px, scrolling=False)


# ------------------------------------------------------------------ native Streamlit grids
def editor_height(rows: int, dynamic: bool = False) -> int:
    """Header + rows (max ~14 visible, the rest scroll inside the grid) + room for the
    always-visible horizontal scroll bar, so the last row is never hidden under it."""
    shown = rows + (1 if dynamic else 0) + 1
    return int(min(max(shown, 3) * EDITOR_ROW_PX + 3 + SCROLLBAR_PX, EDITOR_MAX_PX))


def _pin_first_column(data: Any, column_config: Any) -> Any:
    try:
        columns = [str(c) for c in getattr(data, "columns", [])]
    except Exception:
        return column_config
    config = dict(column_config or {})
    for col in columns:
        if col in config and config[col] is None:
            continue   # hidden column
        current = config.get(col)
        if current is None:
            config[col] = {"pinned": True}
        elif isinstance(current, dict) and "pinned" not in current:
            current = dict(current)
            current["pinned"] = True
            config[col] = current
        break
    return config


def install_streamlit_grid_defaults() -> None:
    """Patch st.data_editor / st.dataframe once: fixed height (scroll inside the grid) and a
    pinned first column, so every editable grid scrolls like a spreadsheet with frozen panes."""
    import streamlit as st
    if getattr(st, "_qcms_excel_grids", False):
        return
    original_editor, original_frame = st.data_editor, st.dataframe

    def data_editor(data: Any, *args: Any, **kwargs: Any):
        rows = len(data.index) if hasattr(data, "index") else 0
        if kwargs.get("height") in (None, "auto"):
            kwargs["height"] = editor_height(rows, str(kwargs.get("num_rows") or "") == "dynamic")
        try:
            kwargs["column_config"] = _pin_first_column(data, kwargs.get("column_config"))
        except Exception:
            pass
        return original_editor(data, *args, **kwargs)

    def dataframe(data: Any = None, *args: Any, **kwargs: Any):
        rows = len(data.index) if hasattr(data, "index") else 0
        if kwargs.get("height") in (None, "auto"):
            kwargs["height"] = editor_height(rows)
        try:
            kwargs["column_config"] = _pin_first_column(data, kwargs.get("column_config"))
        except Exception:
            pass
        return original_frame(data, *args, **kwargs)

    st.data_editor = data_editor
    st.dataframe = dataframe
    st._qcms_excel_grids = True


def grid_contract() -> str:
    return json.dumps({"row_px": ROW_PX, "max_body_px": MAX_BODY_PX, "drag_to_slide": True, "frozen": ["header", "first_column"]})
