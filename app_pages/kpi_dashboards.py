"""QCMS R13 · KPI Dashboards page (Top-10 management dashboards)."""
from __future__ import annotations

from datetime import date, timedelta
from html import escape
from io import BytesIO

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
    st.markdown(
        """<style>
        .kpi-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:6px 0 14px}
        .kpi-overview{grid-template-columns:repeat(5,minmax(0,1fr))}
        .kpi-tile{background:#fff;border:1px solid #D5E4E4;border-radius:16px;padding:14px 16px;box-shadow:0 1px 3px rgba(23,50,51,.06);min-width:0}
        .kpi-tile .l{font-size:12px;font-weight:700;color:#5C7778;text-transform:uppercase;letter-spacing:.03em}
        .kpi-tile .v{font-size:26px;font-weight:800;color:#173233;margin:4px 0 2px;font-variant-numeric:tabular-nums;line-height:1.15;overflow-wrap:anywhere}
        .kpi-tile .f{font-size:12px;color:#5C7778}
        .kpi-tile .s{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:700;margin-top:6px;color:#173233}
        .kpi-tile .s i{font-style:normal;width:16px;height:16px;border-radius:50%;display:inline-grid;place-items:center;color:#fff;font-size:10px}
        .kpi-tile.ov .t{font-size:11.5px;font-weight:800;color:#0B6E70;margin-bottom:2px}
        .kpi-q{color:#5C7778;font-size:13px;margin:-4px 0 8px}
        @media(max-width:1100px){.kpi-grid,.kpi-overview{grid-template-columns:repeat(2,minmax(0,1fr))}}
        </style>""",
        unsafe_allow_html=True,
    )


def _tile_html(label: str, value: str, foot: str, status: str, title: str = "") -> str:
    color = STATUS.get(status, STATUS["neutral"])
    word = STATUS_WORD.get(status, "")
    badge = f'<div class="s"><i style="background:{color}">{STATUS_ICON.get(status, "•")}</i>{escape(word)}</div>' if word else ""
    head = f'<div class="t">{escape(title)}</div>' if title else ""
    return f'<div class="kpi-tile{" ov" if title else ""}">{head}<div class="l">{escape(label)}</div><div class="v">{escape(value)}</div><div class="f">{escape(foot)}</div>{badge}</div>'


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


def render() -> None:
    page_header("KPI Dashboards", "Top-10 management dashboards across supply chain, quality, OSP, calibration and NPD. Every number is calculated live from QCMS records.", "Insights")
    _css()
    repo = Repository(); profile = current_profile() or {}
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
    c2.caption(f"Period: {start or 'beginning'} → {end or today}. Open items (overdue, backlog, at vendor) always show the current position.")

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

    section_bar("KPI OVERVIEW", "Headline KPI of each dashboard. Choose a dashboard below for detail.")
    cards = "".join(_tile_html(b.tiles[0].label, b.tiles[0].value, b.tiles[0].foot, b.tiles[0].status, b.title) if b.tiles else "" for b in boards)
    st.markdown(f'<div class="kpi-grid kpi-overview">{cards}</div>', unsafe_allow_html=True)

    titles = [b.title for b in boards]
    chosen = st.pills("Dashboard", titles, selection_mode="single", default=titles[0], key="kpi_dashboard_choice", label_visibility="collapsed") or titles[0]
    board = next(b for b in boards if b.title == chosen)
    section_bar(board.title.upper(), board.question)
    st.markdown(f'<div class="kpi-grid">{"".join(_tile_html(t.label, t.value, t.foot, t.status) for t in board.tiles)}</div>', unsafe_allow_html=True)
    if board.empty:
        st.info("No records in this period yet for this dashboard. Change the period or start recording transactions in the module.")
        return
    for start_index in range(0, len(board.charts), 2):
        cols = st.columns(2, gap="medium")
        for col, chart in zip(cols, board.charts[start_index:start_index + 2]):
            with col:
                st.markdown(f"**{chart.title}**" + (f"  ·  <span style='color:#5C7778;font-size:12px'>{escape(chart.note)}</span>" if chart.note else ""), unsafe_allow_html=True)
                fig = _figure(chart)
                if fig is None:
                    st.caption("No data for this chart in the selected period.")
                else:
                    st.plotly_chart(fig, width="stretch", key=f"kpi_{board.key}_{start_index}_{chart.title}", config={"displayModeBar": False})
                with st.expander("Data table", expanded=False):
                    portal_table(chart.frame, hide_index=True, width="stretch")
    for title, frame in board.tables:
        st.markdown(f"**{title}**")
        if frame.empty:
            st.caption("Nothing to show — all clear.")
        else:
            portal_table(frame, hide_index=True, width="stretch", height=min(420, 40 + 35 * len(frame)))
    st.download_button("Download this dashboard (Excel)", data=lambda: _excel(board), file_name=f"QCMS_KPI_{board.key}_{today.isoformat()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"kpi_xlsx_{board.key}", on_click="ignore")
