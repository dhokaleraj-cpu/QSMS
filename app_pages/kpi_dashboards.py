"""QCMS R13 · KPI Dashboards page (Top-10 management dashboards)."""
from __future__ import annotations

import time
from datetime import date, timedelta
from html import escape
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from core.access import module_permissions
from core.auth import current_profile
from core.kpi_service import DASHBOARDS, SERIES, STATUS, Chart, Dashboard, KPIContext
from core.repository import Repository
from core.ui import page_header, portal_table, section_bar

PERIODS = {
    "Last 30 days": 30, "Last 90 days": 90, "Last 6 months": 182, "Last 12 months": 365,
    "This year": "ytd", "All time": None,
}
STATUS_ICON = {"good": "✔", "warning": "!", "serious": "▲", "critical": "✖", "neutral": "•"}
STATUS_WORD = {"good": "On target", "warning": "Watch", "serious": "Attention", "critical": "Action needed", "neutral": ""}


def _period(choice: str, today: date) -> tuple[date | None, date | None]:
    value = PERIODS.get(choice)
    if value is None:
        return None, None
    if value == "ytd":
        return today.replace(month=1, day=1), today
    return today - timedelta(days=int(value)), today


def _css() -> None:
    # R20: number-first tiles - big value, short label, status dot; descriptive text removed.
    st.markdown(
        """<style>
        .kpi-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:6px 0 14px}
        .kpi-overview{grid-template-columns:repeat(5,minmax(0,1fr))}
        .kpi-tile{position:relative;background:#fff;border:1px solid #D5E4E4;border-radius:14px;padding:12px 14px 12px 16px;min-width:0;border-left:5px solid var(--kc,#8AA3A4)}
        .kpi-tile .l{font-size:11.5px;font-weight:700;color:#5C7778;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .kpi-tile .v{font-size:34px;font-weight:800;color:#173233;margin:2px 0 0;font-variant-numeric:tabular-nums;line-height:1.1;overflow-wrap:anywhere}
        .kpi-tile .f{font-size:11.5px;color:#7A9091;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .kpi-tile .d{position:absolute;top:12px;right:12px;width:10px;height:10px;border-radius:50%}
        .kpi-tile.ov .t{font-size:11px;font-weight:800;color:#0B6E70;margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .kpi-tile.ov .v{font-size:30px}
        @media(max-width:1100px){.kpi-grid,.kpi-overview{grid-template-columns:repeat(2,minmax(0,1fr))}}
        </style>""",
        unsafe_allow_html=True,
    )


def _short(text: str, limit: int = 34) -> str:
    text = str(text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _tile_html(label: str, value: str, foot: str, status: str, title: str = "") -> str:
    color = STATUS.get(status, STATUS["neutral"])
    word = STATUS_WORD.get(status, "")
    dot = f'<span class="d" style="background:{color}" title="{escape(word)}"></span>' if word else ""
    head = f'<div class="t">{escape(title)}</div>' if title else ""
    return (f'<div class="kpi-tile{" ov" if title else ""}" style="--kc:{color}">{dot}{head}'
            f'<div class="l">{escape(label)}</div><div class="v">{escape(value)}</div>'
            f'<div class="f">{escape(_short(foot))}</div></div>')


def _figure(chart: Chart):
    import plotly.express as px
    import plotly.graph_objects as go
    df = chart.frame.copy()
    if df.empty or chart.x not in df.columns or chart.y not in df.columns:
        return None
    color_map = None
    if chart.color and chart.color in df.columns:
        keys = list(dict.fromkeys(df[chart.color].astype(str)))
        color_map = {k: SERIES[i % len(SERIES)] for i, k in enumerate(keys[:len(SERIES)])}
    if chart.kind == "hbar":
        fig = px.bar(df, x=chart.x, y=chart.y, orientation="h", text=chart.x, color_discrete_sequence=[SERIES[0]])
        fig.update_traces(texttemplate="%{x:,.4~g}", textposition="outside", cliponaxis=False)
    elif chart.kind in {"bar", "stacked"}:
        fig = px.bar(df, x=chart.x, y=chart.y, color=chart.color if color_map else None, color_discrete_map=color_map, color_discrete_sequence=[SERIES[0]], text=chart.y if not color_map else None)
        if not color_map:
            fig.update_traces(texttemplate="%{y:,.4~g}", textposition="outside", cliponaxis=False)
        fig.update_layout(barmode="stack")
    elif chart.kind == "line":
        fig = px.line(df, x=chart.x, y=chart.y, color=chart.color if color_map else None, color_discrete_map=color_map, color_discrete_sequence=[SERIES[0]], markers=True)
        fig.update_traces(line=dict(width=2), marker=dict(size=8, line=dict(width=2, color="#fcfcfb")))
        fig.update_layout(hovermode="x unified")
    else:
        fig = go.Figure()
    fig.update_traces(marker_line_width=0) if chart.kind != "line" else None
    fig.update_layout(
        height=330, margin=dict(l=8, r=24, t=10, b=8), paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb",
        font=dict(family="Roboto, Arial, sans-serif", size=12, color="#52514e"), bargap=0.35,
        showlegend=bool(color_map), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text=""),
        xaxis_title=None, yaxis_title=None,
    )
    fig.update_xaxes(showgrid=chart.kind == "hbar", gridcolor="#e1e0d9", linecolor="#c3c2b7", zeroline=False)
    fig.update_yaxes(showgrid=chart.kind != "hbar", gridcolor="#e1e0d9", linecolor="#c3c2b7", zeroline=False)
    return fig


def _excel(board: Dashboard) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame([{"KPI": t.label, "Value": t.value, "Detail": t.foot, "Status": STATUS_WORD.get(t.status, "")} for t in board.tiles]).to_excel(writer, index=False, sheet_name="KPIs")
        for index, (title, frame) in enumerate(board.tables + [(c.title, c.frame) for c in board.charts]):
            name = (f"{index + 1} " + "".join(ch for ch in title if ch not in '[]:*?/\\'))[:31]
            frame.to_excel(writer, index=False, sheet_name=name)
    return buffer.getvalue()


def _load(repo: Repository, tables: set[str]) -> dict[str, list[dict]]:
    data: dict[str, list[dict]] = {}
    for table in sorted(tables):
        try:
            data[table] = repo.select(table, limit=10000)
        except Exception:
            data[table] = []
    return data


def _render_detailed(repo: Repository, profile: dict) -> None:
    """R13 Top-10 management KPI dashboards (period selectable, Excel export)."""
    cache: dict[str, bool] = {}

    def can_view(module_key: str) -> bool:
        if module_key not in cache:
            cache[module_key] = bool(module_permissions(profile, module_key, repo).get("can_view"))
        return cache[module_key]

    allowed = [d for d in DASHBOARDS if can_view(d[2])]
    if not allowed:
        st.info("You do not have View permission for any module used by the KPI dashboards.")
        return
    c1, c2 = st.columns([3, 7], gap="small")
    period = c1.selectbox("Period", list(PERIODS), index=1, key="kpi_period")
    today = date.today()
    start, end = _period(period, today)
    c2.caption(f"{start.strftime('%d-%b-%Y') if start else 'Start'} → {(end or today).strftime('%d-%b-%Y')}")

    tables = {t for d in allowed for t in d[3]} | {"parties", "parts"}
    with st.spinner("Calculating KPIs..."):
        data = _load(repo, tables)
    parties = {str(r.get("id")): str(r.get("party_name") or r.get("party_code") or "") for r in data.get("parties", [])}
    parts = {str(r.get("id")): " · ".join(v for v in (str(r.get("part_number") or ""), str(r.get("part_name") or "")) if v) for r in data.get("parts", [])}
    ctx = KPIContext(today=today, start=start, end=end, parties=parties, parts=parts)
    boards: list[Dashboard] = []
    for key, title, module_key, _tables, builder in allowed:
        try:
            boards.append(builder(data, ctx))
        except Exception as exc:  # one broken dashboard must not hide the others
            boards.append(Dashboard(key, title, module_key, f"Could not be calculated: {exc}", empty=True))

    section_bar("KPI OVERVIEW")
    cards = "".join(_tile_html(b.tiles[0].label, b.tiles[0].value, b.tiles[0].foot, b.tiles[0].status, b.title) if b.tiles else "" for b in boards)
    st.markdown(f'<div class="kpi-grid kpi-overview">{cards}</div>', unsafe_allow_html=True)

    titles = [b.title for b in boards]
    chosen = st.pills("Dashboard", titles, selection_mode="single", default=titles[0], key="kpi_dashboard_choice", label_visibility="collapsed") or titles[0]
    board = next(b for b in boards if b.title == chosen)
    section_bar(board.title.upper())
    st.markdown(f'<div class="kpi-grid">{"".join(_tile_html(t.label, t.value, t.foot, t.status) for t in board.tiles)}</div>', unsafe_allow_html=True)
    if board.empty:
        st.info("No records in this period.")
        return
    for start_index in range(0, len(board.charts), 2):
        cols = st.columns(2, gap="medium")
        for col, chart in zip(cols, board.charts[start_index:start_index + 2]):
            with col:
                st.markdown(f"**{chart.title}**")
                fig = _figure(chart)
                if fig is None:
                    st.caption("No data")
                else:
                    st.plotly_chart(fig, width="stretch", key=f"kpi_{board.key}_{start_index}_{chart.title}", config={"displayModeBar": False})
                with st.expander("Data", expanded=False):
                    portal_table(chart.frame, hide_index=True, width="stretch")
    for title, frame in board.tables:
        with st.expander(f"{title} · {len(frame):,}", expanded=False):
            if frame.empty:
                st.caption("0")
            else:
                portal_table(frame, hide_index=True, width="stretch", height=min(420, 40 + 35 * len(frame)))
    st.download_button("Excel", icon=":material/download:", data=lambda: _excel(board), file_name=f"QCMS_KPI_{board.key}_{today.isoformat()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"kpi_xlsx_{board.key}", on_click="ignore")


# =============================================================================================
# R35 · STAWN QCMS start dashboard: department tabs (Quality first), my pending tasks first,
# automatic animated department switching, and personal custom dashboards.
# =============================================================================================
DEPARTMENTS: tuple[tuple[str, str], ...] = (
    ("QUALITY", "Quality"), ("SUPPLY_CHAIN", "Supply Chain"), ("PRODUCTION", "Production"),
    ("NPD", "NPD / APQP"), ("MANAGEMENT", "Management"),
)
VIEWS: tuple[str, ...] = ("Live KPI", "My Dashboards", "Detailed KPIs")
ROTATE_SECONDS: tuple[int, ...] = (10, 20, 30, 60)
TONE_TO_STATUS = {"good": "good", "warning": "warning", "critical": "critical", "serious": "serious", "neutral": "neutral"}
CATEGORY_ICON = {"APPROVAL": "✅", "TASK": "📌", "UPDATE": "🔔", "INFO": "ℹ️", "ALERT": "⚠️"}


def _anim_css() -> None:
    st.markdown(
        """<style>
        @keyframes qcmsKpiIn{0%{opacity:0;transform:translateX(42px) scale(.985)}60%{opacity:1}100%{opacity:1;transform:none}}
        @keyframes qcmsKpiTimer{from{width:0}to{width:100%}}
        .st-key-kpi_anim_0,.st-key-kpi_anim_1{animation:qcmsKpiIn .7s cubic-bezier(.22,.8,.3,1) both}
        .kpi-timer-wrap{height:3px;background:#E3EEEE;border-radius:3px;overflow:hidden;margin:0 0 10px}
        .kpi-timer{height:3px;background:linear-gradient(90deg,#0B6E70,#2FB3AE);animation-name:qcmsKpiTimer;animation-timing-function:linear;animation-fill-mode:forwards}
        .kpi-dept-title{font-size:13px;font-weight:800;letter-spacing:.06em;color:#0B6E70;text-transform:uppercase;margin:2px 0 6px}
        .kpi-task{display:flex;gap:8px;align-items:flex-start;padding:7px 10px;border:1px solid #D5E4E4;border-left:4px solid #EDA100;border-radius:10px;background:#FFFDF7;margin:0 0 6px}
        .kpi-task .tt{font-weight:700;color:#173233;font-size:13px}.kpi-task .td{font-size:11.5px;color:#5C7778}
        .kpi-bignum{font-size:46px;font-weight:800;color:#0B6E70;line-height:1.05;font-variant-numeric:tabular-nums}
        .kpi-bigsub{font-size:12px;color:#5C7778}
        @media (prefers-reduced-motion: reduce){.st-key-kpi_anim_0,.st-key-kpi_anim_1,.kpi-timer{animation:none!important}}
        </style>""",
        unsafe_allow_html=True,
    )


def _user_key(profile: dict) -> str:
    return f"{profile.get('tenant_id') or ''}:{profile.get('id') or profile.get('email') or ''}"


@st.cache_data(ttl=60, show_spinner=False)
def _cached_payload(user_key: str, department: str, _repo: Repository) -> dict | None:
    """One RPC per department (qcms_kpi_dashboard). None = RPC unavailable (preview / older database)."""
    try:
        data = _repo.rpc("qcms_kpi_dashboard", {"p_department": department})
    except Exception as exc:  # noqa: BLE001 - shown to the user below
        text = str(exc)
        if "preview" in text.casefold() or "qcms_kpi_dashboard" in text or "PGRST202" in text or "unavailable" in text.casefold():
            return None
        return {"error": text, "cards": [], "charts": [], "pending_tasks": []}
    if isinstance(data, list):
        data = data[0] if data else {}
    return data if isinstance(data, dict) else None


def _fmt_value(value: Any, unit: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value or "0")
    if unit == "%":
        return f"{number:,.1f}%"
    if unit == "INR":
        return f"₹{number:,.0f}"
    return f"{number:,.0f}" if abs(number - round(number)) < 1e-9 else f"{number:,.2f}"


def _chart_figure(chart: dict, height: int = 320):
    import plotly.graph_objects as go
    labels = list(chart.get("labels") or [])
    series = list(chart.get("series") or [])
    kind = str(chart.get("type") or "bar")
    fig = go.Figure()
    if not labels or not series:
        return None
    if kind == "donut":
        values = list(series[0].get("values") or [])
        fig.add_trace(go.Pie(labels=labels, values=values, hole=.55, marker=dict(colors=SERIES * 4), textinfo="value+percent",
                             hovertemplate="%{label}: %{value}<extra></extra>"))
    else:
        for index, item in enumerate(series):
            color = SERIES[index % len(SERIES)]
            if kind == "line":
                fig.add_trace(go.Scatter(x=labels, y=item.get("values") or [], name=str(item.get("name") or ""), mode="lines+markers",
                                         line=dict(width=2.4, color=color), marker=dict(size=7)))
            else:
                fig.add_trace(go.Bar(x=labels, y=item.get("values") or [], name=str(item.get("name") or ""), marker_color=color,
                                     texttemplate="%{y:,.4~g}", textposition="outside" if len(series) == 1 else "inside", cliponaxis=False))
        fig.update_layout(barmode="stack" if len(series) > 1 and "decision" in str(chart.get("title") or "").casefold() else "group")
    fig.update_layout(height=height, margin=dict(l=8, r=12, t=8, b=8), paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb",
                      font=dict(family="Roboto, Arial, sans-serif", size=12, color="#52514e"), bargap=.3,
                      showlegend=len(series) > 1 or kind == "donut",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text=""))
    fig.update_xaxes(showgrid=False, linecolor="#c3c2b7")
    fig.update_yaxes(gridcolor="#e1e0d9", zeroline=False)
    return fig


def _open_task(repo: Repository, task: dict) -> None:
    pages = st.session_state.get("_qsms_pages") or {}
    table = str(task.get("related_table") or "")
    related = str(task.get("related_id") or "")
    if table and related and table not in {"qcms_delete_requests", "npd_order_steps"}:
        try:
            rows = repo.select(table, eq={"id": related}, limit=1)
        except Exception:
            rows = []
        if rows:
            from app_pages.records_center import _open_selected_record_for_edit
            _open_selected_record_for_edit(table, rows[0])
            return
    route = str(task.get("web_route") or "")
    if route in pages:
        st.switch_page(pages[route])


def _render_tasks(repo: Repository, tasks: list[dict], unread: int, *, expanded: bool) -> None:
    head = f"MY PENDING TASKS · {len(tasks)}" + (f" · 🔔 {unread} unread notification(s)" if unread else "")
    with st.expander(head, expanded=expanded):
        if not tasks:
            st.caption("Nothing is waiting for you. Approvals, validations and work assigned to you appear here first.")
            return
        for index, task in enumerate(tasks[:12]):
            c1, c2 = st.columns([10, 1.6], gap="small", vertical_alignment="center")
            due = str(task.get("due") or "")
            c1.markdown(
                f'<div class="kpi-task"><div>{CATEGORY_ICON.get(str(task.get("category") or "").upper(), "📌")}</div>'
                f'<div><div class="tt">{escape(str(task.get("title") or ""))}</div>'
                f'<div class="td">{escape(str(task.get("category") or "").title())}{" · due " + escape(due) if due else ""}</div></div></div>',
                unsafe_allow_html=True,
            )
            if c2.button("Open", key=f"kpi_task_open_{index}_{task.get('related_id')}", width="stretch", icon=":material/open_in_new:"):
                _open_task(repo, task)
        if len(tasks) > 12:
            portal_table(pd.DataFrame([{"Task": t.get("title"), "Type": t.get("category"), "Due": t.get("due")} for t in tasks[12:]]),
                         hide_index=True, width="stretch", height=min(360, 80 + 35 * (len(tasks) - 12)))


def _render_department(repo: Repository, payload: dict, code: str) -> None:
    if payload.get("error"):
        st.warning(f"Some KPIs could not be calculated: {payload['error']}")
    _render_tasks(repo, list(payload.get("pending_tasks") or []), int(payload.get("unread_notifications") or 0), expanded=code == "QUALITY")
    cards = list(payload.get("cards") or [])
    if cards:
        tiles = "".join(_tile_html(str(c.get("label") or ""), _fmt_value(c.get("value"), str(c.get("unit") or "")),
                                   str(c.get("unit") or "") if c.get("unit") not in ("%", "INR") else "",
                                   TONE_TO_STATUS.get(str(c.get("tone") or "neutral"), "neutral")) for c in cards)
        st.markdown(f'<div class="kpi-grid">{tiles}</div>', unsafe_allow_html=True)
    charts = list(payload.get("charts") or [])
    for start in range(0, len(charts), 2):
        cols = st.columns(2, gap="medium")
        for col, chart in zip(cols, charts[start:start + 2]):
            with col:
                st.markdown(f"**{chart.get('title') or ''}**")
                fig = _chart_figure(chart)
                if fig is None:
                    st.caption("No data yet")
                else:
                    st.plotly_chart(fig, width="stretch", key=f"kpi_live_{code}_{start}_{chart.get('title')}", config={"displayModeBar": False})


def _live_fragment(repo: Repository, profile: dict, auto: bool, interval: int) -> None:
    labels = [label for _code, label in DEPARTMENTS]
    state = st.session_state
    now = time.time()
    current = state.get("_kpi_dept_current") if state.get("_kpi_dept_current") in labels else labels[0]
    picked = state.get("kpi_dept_pill")
    if "_kpi_dept_switched_at" not in state:
        state["_kpi_dept_switched_at"] = now
    if picked in labels and picked != current:
        current = picked
        state["_kpi_dept_switched_at"] = now
        state["_kpi_anim"] = int(state.get("_kpi_anim", 0)) + 1
    elif auto and now - float(state.get("_kpi_dept_switched_at") or now) >= interval - 0.5:
        current = labels[(labels.index(current) + 1) % len(labels)]
        state["_kpi_dept_switched_at"] = now
        state["_kpi_anim"] = int(state.get("_kpi_anim", 0)) + 1
    state["_kpi_dept_current"] = current
    state["kpi_dept_pill"] = current
    st.pills("Department", labels, selection_mode="single", key="kpi_dept_pill", label_visibility="collapsed")
    code = dict((label, c) for c, label in DEPARTMENTS)[current]
    with st.container(border=False, key=f"kpi_anim_{int(state.get('_kpi_anim', 0)) % 2}"):
        if auto:
            st.markdown(f'<div class="kpi-timer-wrap"><div class="kpi-timer" style="animation-duration:{interval}s"></div></div>', unsafe_allow_html=True)
        payload = _cached_payload(_user_key(profile), code, repo)
        if payload is None:
            st.info("Live department KPIs are not available yet.")
            return
        st.markdown(f'<div class="kpi-dept-title">{escape(current)} dashboard</div>', unsafe_allow_html=True)
        _render_department(repo, payload, code)


def _render_live(repo: Repository, profile: dict, auto: bool, interval: int) -> None:
    if _cached_payload(_user_key(profile), "QUALITY", repo) is None:
        # Preview mode or a database without the R35 update: the classic dashboards still work.
        st.caption("Live department KPIs need the R35 database update - showing the detailed KPI dashboards.")
        _render_detailed(repo, profile)
        return
    st.fragment(run_every=interval if auto else None)(_live_fragment)(repo, profile, auto, interval)


def render() -> None:
    page_header("STAWN QCMS · KPI Dashboard", "Quality first · your pending tasks · every department", "Start")
    _css()
    _anim_css()
    repo = Repository()
    profile = current_profile() or {}
    c1, c2, c3 = st.columns([5.2, 2.4, 1.4], gap="small", vertical_alignment="center")
    view = c1.segmented_control("View", list(VIEWS), default=VIEWS[0], key="kpi_view", label_visibility="collapsed") or VIEWS[0]
    if view == VIEWS[0]:
        auto = c2.toggle("Auto switch departments", value=True, key="kpi_auto_rotate",
                         help="Cycles Quality → Supply Chain → Production → NPD / APQP → Management with an animated transition.")
        interval = c3.selectbox("Switch every", list(ROTATE_SECONDS), index=1, format_func=lambda s: f"every {s} s",
                                key="kpi_rotate_seconds", label_visibility="collapsed", disabled=not auto)
        _render_live(repo, profile, bool(auto), int(interval or 20))
    elif view == VIEWS[1]:
        _render_my_dashboards(repo, profile)
    else:
        _render_detailed(repo, profile)


# ---------------------------------------------------------------------------------------------
# My Dashboards (custom, per user, multiple; KPI cards / charts / tables; width, height, order)
# ---------------------------------------------------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def _source_rows(user_key: str, table: str, _repo: Repository) -> list[dict]:
    try:
        return _repo.select(table, limit=5000)
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def _fk_labels(user_key: str, _repo: Repository) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {"parts": {}, "parties": {}}
    try:
        out["parts"] = {str(r.get("id")): str(r.get("part_number") or r.get("part_name") or "") for r in _repo.select("parts", limit=5000)}
    except Exception:
        pass
    try:
        out["parties"] = {str(r.get("id")): str(r.get("party_name") or r.get("party_code") or "") for r in _repo.select("parties", limit=5000)}
    except Exception:
        pass
    return out


def _widget_editor(prefix: str, widget: dict) -> dict | None:
    from core import dashboard_builder as db
    w = db.normalize_widget(widget)
    c1, c2, c3 = st.columns([2.2, 2, 1.4], gap="small")
    title = c1.text_input("Title", value=w["title"], key=f"{prefix}_title")
    kinds = list(db.WIDGET_TYPES)
    kind = c2.selectbox("Type", kinds, index=kinds.index(w["type"]), format_func=db.WIDGET_TYPES.get, key=f"{prefix}_type")
    sources = list(db.DATA_SOURCES)
    source = c3.selectbox("Data", sources, index=sources.index(w["source"]), format_func=lambda k: db.DATA_SOURCES[k]["label"], key=f"{prefix}_source")
    spec = db.DATA_SOURCES[source]
    fields = [""] + list(spec["fields"])
    numbers = [""] + list(spec["numbers"])
    d1, d2, d3, d4 = st.columns(4, gap="small")
    aggs = list(db.AGGREGATES)
    agg = d1.selectbox("Calculate", aggs, index=aggs.index(w["agg"]), format_func=db.AGGREGATES.get, key=f"{prefix}_agg")
    value_field = d2.selectbox("Of value", numbers, index=numbers.index(w["value_field"]) if w["value_field"] in numbers else 0,
                               format_func=lambda k: spec["numbers"].get(k, "— (count records)"), key=f"{prefix}_value", disabled=agg == "count")
    buckets = list(db.TIME_BUCKETS)
    bucket = d3.selectbox("Time grouping", buckets, index=buckets.index(w["time_bucket"]), format_func=db.TIME_BUCKETS.get, key=f"{prefix}_bucket")
    group_by = d4.selectbox("Group by", fields, index=fields.index(w["group_by"]) if w["group_by"] in fields else 0,
                            format_func=lambda k: spec["fields"].get(k, "— none"), key=f"{prefix}_group", disabled=bool(bucket) or kind == "kpi")
    e1, e2, e3, e4 = st.columns(4, gap="small")
    series_by = e1.selectbox("Split series by", fields, index=fields.index(w["series_by"]) if w["series_by"] in fields else 0,
                             format_func=lambda k: spec["fields"].get(k, "— none"), key=f"{prefix}_series", disabled=kind in {"kpi", "pie"})
    filter_field = e2.selectbox("Filter field", fields, index=fields.index(w["filter_field"]) if w["filter_field"] in fields else 0,
                                format_func=lambda k: spec["fields"].get(k, "— no filter"), key=f"{prefix}_ffield")
    filter_value = e3.text_input("Filter contains", value=w["filter_value"], key=f"{prefix}_fvalue", disabled=not filter_field)
    periods = list(db.PERIODS)
    period = e4.selectbox("Period", periods, index=periods.index(w["period_days"]) if w["period_days"] in periods else 0, format_func=db.PERIODS.get, key=f"{prefix}_period")
    f1, f2, f3 = st.columns(3, gap="small")
    width = f1.select_slider("Width", options=list(db.WIDTHS), value=w["width"], format_func=db.WIDTHS.get, key=f"{prefix}_width")
    height = f2.select_slider("Height", options=list(db.HEIGHTS), value=w["height"], format_func={"S": "Small", "M": "Medium", "L": "Large"}.get, key=f"{prefix}_height")
    top = f3.selectbox("Show top", [0, 5, 10, 20], index=[0, 5, 10, 20].index(w["top"]) if w["top"] in (0, 5, 10, 20) else 0,
                       format_func=lambda n: "All groups" if not n else f"Top {n}", key=f"{prefix}_top")
    if st.button("Save widget", key=f"{prefix}_save", type="primary", icon=":material/save:"):
        return db.normalize_widget({**w, "title": title or spec["label"], "type": kind, "source": source, "agg": agg,
                                    "value_field": "" if agg == "count" else value_field, "time_bucket": bucket,
                                    "group_by": "" if bucket or kind == "kpi" else group_by, "series_by": "" if kind in {"kpi", "pie"} else series_by,
                                    "filter_field": filter_field, "filter_value": filter_value if filter_field else "", "period_days": period,
                                    "width": width, "height": height, "top": top})
    return None


def _render_widget(widget: dict, rows: list[dict], labels: dict, *, allowed: bool) -> None:
    import plotly.express as px
    from core import dashboard_builder as db
    height = db.HEIGHTS[widget["height"]]
    with st.container(border=True, height=height):
        st.markdown(f"**{escape(widget['title'])}**")
        if not allowed:
            st.caption("You do not have View permission for this data.")
            return
        value, frame = db.compute(rows, widget, labels=labels)
        kind = widget["type"]
        if kind == "kpi":
            unit = db.DATA_SOURCES[widget["source"]]["numbers"].get(widget["value_field"], "records") if widget["agg"] != "count" else "records"
            st.markdown(f'<div class="kpi-bignum">{_fmt_value(value, "")}</div><div class="kpi-bigsub">{escape(db.AGGREGATES[widget["agg"]])} · {escape(unit)} · '
                        f'{escape(db.PERIODS.get(widget["period_days"], ""))}</div>', unsafe_allow_html=True)
            return
        if frame.empty:
            st.caption("No data for this selection.")
            return
        chart_h = max(150, height - 78)
        color = "Series" if "Series" in frame.columns else None
        if kind == "table":
            portal_table(frame.rename(columns={"Group": "Group", "Value": db.AGGREGATES[widget["agg"]]}), hide_index=True, width="stretch", height=chart_h)
            return
        if kind == "pie":
            fig = px.pie(frame, names="Group", values="Value", hole=.5, color_discrete_sequence=SERIES)
        elif kind == "line":
            fig = px.line(frame, x="Group", y="Value", color=color, markers=True, color_discrete_sequence=SERIES)
        elif kind == "area":
            fig = px.area(frame, x="Group", y="Value", color=color, color_discrete_sequence=SERIES)
        else:
            fig = px.bar(frame, x="Group", y="Value", color=color, barmode="group", color_discrete_sequence=SERIES, text_auto=".4~s" if not color else False)
        fig.update_layout(height=chart_h, margin=dict(l=6, r=6, t=6, b=6), paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb",
                          xaxis_title=None, yaxis_title=None, legend=dict(orientation="h", y=1.08, x=0, title_text=""))
        st.plotly_chart(fig, width="stretch", key=f"mydash_{widget['id']}", config={"displayModeBar": False})


def _render_my_dashboards(repo: Repository, profile: dict) -> None:
    from core import dashboard_builder as db
    profile_id = str(profile.get("id") or "")
    try:
        boards = db.list_dashboards(repo, profile_id)
    except Exception as exc:
        st.info(f"Custom dashboards need the R35 database update ({exc}).")
        return
    top1, top2 = st.columns([6, 4], gap="small", vertical_alignment="bottom")
    with top2.popover("New dashboard", icon=":material/add:", width="stretch"):
        name = st.text_input("Dashboard name", key="mydash_new_name", placeholder="e.g. My Quality Review")
        starter = st.checkbox("Start with suggested widgets", value=True, key="mydash_new_starter")
        if st.button("Create dashboard", key="mydash_create", type="primary"):
            created = db.create_dashboard(repo, profile_id, name or "My dashboard", widgets=db.starter_widgets() if starter else [], sort_order=len(boards))
            st.session_state["mydash_selected"] = str(created.get("id") or "")
            st.rerun()
    if not boards:
        top1.info("You have no personal dashboards yet. Create one with **New dashboard** - add KPI cards, charts and tables from any QCMS data, "
                  "then size and arrange them. You can make several dashboards and share one with your company.")
        return
    ids = [str(b.get("id")) for b in boards]
    by_id = {str(b.get("id")): b for b in boards}
    selected_default = st.session_state.get("mydash_selected") if st.session_state.get("mydash_selected") in ids else ids[0]
    if st.session_state.get("mydash_selected") not in ids:
        st.session_state["mydash_selected"] = selected_default
    chosen = top1.selectbox("Dashboard", ids, key="mydash_selected", label_visibility="collapsed",
                            format_func=lambda i: (("⭐ " if by_id[i].get("is_default") else "") + str(by_id[i].get("name") or "Dashboard")
                                                   + ("" if str(by_id[i].get("owner_profile_id")) == profile_id else " · shared by a colleague")))
    board = by_id[chosen]
    owner = str(board.get("owner_profile_id") or "") == profile_id
    widgets = db.layout_widgets(board.get("layout"))
    edit = False
    if owner:
        b1, b2 = st.columns([6, 4], gap="small", vertical_alignment="center")
        edit = b1.toggle("Edit layout (add · size · move · duplicate · delete)", key=f"mydash_edit_{chosen}")
        with b2.popover("Dashboard settings", icon=":material/settings:", width="stretch"):
            new_name = st.text_input("Name", value=str(board.get("name") or ""), key=f"mydash_rename_{chosen}")
            is_default = st.checkbox("Open this dashboard first", value=bool(board.get("is_default")), key=f"mydash_default_{chosen}")
            shared = st.checkbox("Share read-only with everyone in my company", value=bool(board.get("shared_with_tenant")), key=f"mydash_share_{chosen}")
            if st.button("Save settings", key=f"mydash_settings_save_{chosen}", type="primary"):
                if is_default:
                    for other in boards:
                        if str(other.get("id")) != chosen and other.get("is_default") and str(other.get("owner_profile_id")) == profile_id:
                            db.update_dashboard(repo, str(other.get("id")), is_default=False)
                db.update_dashboard(repo, chosen, name=new_name or board.get("name"), is_default=is_default, shared_with_tenant=shared)
                st.rerun()
            st.divider()
            confirm = st.checkbox("I want to delete this dashboard", key=f"mydash_del_confirm_{chosen}")
            if st.button("Delete dashboard", key=f"mydash_delete_{chosen}", disabled=not confirm, icon=":material/delete:"):
                db.delete_dashboard(repo, chosen)
                st.session_state.pop("mydash_selected", None)
                st.rerun()
    if edit:
        with st.expander("➕ Add a widget", expanded=not widgets):
            added = _widget_editor(f"mydash_add_{chosen}", db.new_widget())
            if added:
                db.save_widgets(repo, chosen, widgets + [added]); st.rerun()
        editing = st.session_state.get(f"mydash_editing_{chosen}")
        target = next((w for w in widgets if w["id"] == editing), None)
        if target:
            with st.container(border=True):
                st.markdown(f"**Edit widget · {escape(target['title'])}**")
                saved = _widget_editor(f"mydash_edit_{chosen}_{target['id']}", target)
                if saved:
                    db.save_widgets(repo, chosen, [saved if w["id"] == target["id"] else w for w in widgets])
                    st.session_state.pop(f"mydash_editing_{chosen}", None); st.rerun()
                if st.button("Close editor", key=f"mydash_edit_close_{chosen}"):
                    st.session_state.pop(f"mydash_editing_{chosen}", None); st.rerun()
    if not widgets:
        st.caption("This dashboard is empty. Turn on **Edit layout** and add a widget.")
        return
    user_key = _user_key(profile)
    labels = _fk_labels(user_key, repo)
    permission_cache: dict[str, bool] = {}
    for row in db.pack_rows(widgets):
        widths = [w["width"] for w in row]
        filler = 4 - sum(widths)
        cols = st.columns(widths + ([filler] if filler > 0 else []), gap="small")
        for col, widget in zip(cols, row):
            with col:
                module = db.DATA_SOURCES[widget["source"]]["module"]
                if module not in permission_cache:
                    try:
                        permission_cache[module] = bool(module_permissions(profile, module, repo).get("can_view"))
                    except Exception:
                        permission_cache[module] = True
                allowed = permission_cache[module]
                rows = _source_rows(user_key, db.DATA_SOURCES[widget["source"]]["table"], repo) if allowed else []
                _render_widget(widget, rows, labels, allowed=allowed)
                if edit:
                    k = f"mydash_{chosen}_{widget['id']}"
                    a1, a2, a3, a4, a5 = st.columns(5, gap="small")
                    if a1.button("", key=f"{k}_left", icon=":material/arrow_back:", help="Move earlier", width="stretch"):
                        db.save_widgets(repo, chosen, db.move_widget(widgets, widget["id"], -1)); st.rerun()
                    if a2.button("", key=f"{k}_right", icon=":material/arrow_forward:", help="Move later", width="stretch"):
                        db.save_widgets(repo, chosen, db.move_widget(widgets, widget["id"], 1)); st.rerun()
                    if a3.button("", key=f"{k}_edit", icon=":material/tune:", help="Edit / resize", width="stretch"):
                        st.session_state[f"mydash_editing_{chosen}"] = widget["id"]; st.rerun()
                    if a4.button("", key=f"{k}_dup", icon=":material/content_copy:", help="Duplicate", width="stretch"):
                        db.save_widgets(repo, chosen, db.duplicate_widget(widgets, widget["id"])); st.rerun()
                    if a5.button("", key=f"{k}_del", icon=":material/delete:", help="Delete widget", width="stretch"):
                        db.save_widgets(repo, chosen, [w for w in widgets if w["id"] != widget["id"]]); st.rerun()
