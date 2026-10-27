"""QCMS R37 · KPI Details (routes "kpi-details" and "kpi-drilldown"): the records behind a KPI card.

Opened from every KPI card (start dashboard department cards, module infographic cards on the KPI
dashboard and on every module home page, Quality Dashboard, My Dashboards) and from the mobile apps.
The rows come from the security-invoker RPC ``public.qcms_kpi_drilldown(p_card_key, p_limit)`` - the same
JSON filter that produced the number on the card - with ``qcms_kpi_records`` (older database) and the
Python engine of ``core.module_kpis`` as fallbacks. Personal dashboard widgets pass their own rows.

Page: title + card value, filters (core.report_filters), the records grid (click a row = open the record in
its own entry screen, or select it for its print layout PDF), Excel / PDF export of the list, Back and
"Open full register" (module page).

Deep link (web + mobile WebView): ``/kpi-drilldown?card=<key>&dept=<DEPARTMENT>`` (``/kpi-details`` too).
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import streamlit as st

from core.kpi_service import CARD_CATALOG, DRILL_ROUTE, DRILL_STATE_KEY, SOURCE_TABLES, drill_frame
from core.repository import Repository
from core.ui import disposition_cards, page_header, section_bar, selectable_table

ROW_LIMIT = 500
ROW_ACTIONS: tuple[str, ...] = ("Open record", "Select for print")


def catalog() -> dict[str, tuple[str, str]]:
    """Every drillable key -> (title, register route): start-dashboard keys + module infographic metrics."""
    out = dict(CARD_CATALOG)
    try:
        from core.module_kpis import MODULE_GROUPS
        for group in MODULE_GROUPS:
            for metric in group.metrics:
                out[metric.key] = (f"{group.title} · {metric.label}", group.route)
    except Exception:
        pass
    return out


def open_kpi_details(*, key: str = "", label: str = "", value: Any = "", department: str = "", route: str = "",
                     rows: Sequence[Mapping[str, Any]] | None = None, origin: str = "kpi-dashboards") -> None:
    """Remember what was clicked and switch to the KPI Details page."""
    known = catalog().get(str(key or ""), ("", ""))
    request = {"key": str(key or ""), "label": str(label or known[0] or "KPI"), "value": value, "department": str(department or ""),
               "route": str(route or known[1] or ""), "origin": origin, "rows": [dict(r) for r in rows] if rows is not None else None}
    st.session_state[DRILL_STATE_KEY] = request
    st.session_state["_kpi_drill_nonce"] = int(st.session_state.get("_kpi_drill_nonce", 0)) + 1
    pages = st.session_state.get("_qsms_pages") or {}
    target = DRILL_ROUTE if DRILL_ROUTE in pages else ("kpi-drilldown" if "kpi-drilldown" in pages else "")
    if target:
        params = {"card": request["key"], "dept": request["department"]} if request["key"] and rows is None else None
        st.switch_page(pages[target], query_params=params)
    else:  # preview / tests without the router
        st.rerun()


@st.cache_data(ttl=60, show_spinner=False)
def _records(user_key: str, card_key: str, department: str, _repo: Repository) -> list[dict] | None:
    """Rows behind a card (qcms_kpi_drilldown → qcms_kpi_records → Python engine). None = not available."""
    from core.module_kpis import load_drill
    try:
        return load_drill(_repo, card_key, limit=ROW_LIMIT)
    except Exception as exc:  # noqa: BLE001 - shown on the page
        return [{"_error": str(exc)}]


def _request() -> dict:
    request = dict(st.session_state.get(DRILL_STATE_KEY) or {})
    card = str(st.query_params.get("card", "") or "").strip()
    dept = str(st.query_params.get("dept", "") or "").strip().upper()
    if card and card != request.get("key"):
        title, route = catalog().get(card, (card.replace("_", " ").title(), ""))
        request = {"key": card, "label": title, "value": "", "department": dept, "route": route, "origin": "kpi-dashboards", "rows": None}
        st.session_state[DRILL_STATE_KEY] = request
    return request


def _open_row(repo: Repository, row: Mapping[str, Any], fallback_route: str) -> None:
    from app_pages.global_search import _open_record
    table = str(row.get("source_table") or "")
    record_type, register = SOURCE_TABLES.get(table, (table, fallback_route))
    st.session_state["_kpi_drill_nonce"] = int(st.session_state.get("_kpi_drill_nonce", 0)) + 1  # fresh grid when coming back
    _open_record(repo, {"table": table, "id": str(row.get("record_id") or ""), "route": register or fallback_route or "records-center",
                        "record_type": record_type})


def _picker(request: dict) -> dict:
    known = catalog()
    keys = list(known)
    current = request.get("key") if request.get("key") in keys else None
    choice = st.selectbox("KPI", keys, index=keys.index(current) if current else None, format_func=lambda k: known[k][0],
                          placeholder="Choose a KPI to see its records",
                          key=f"kpi_drill_picker_{int(st.session_state.get('_kpi_drill_nonce', 0))}")
    if choice and choice != request.get("key"):
        try:
            st.query_params["card"] = choice
        except Exception:
            pass
        request = {"key": choice, "label": known[choice][0], "value": "", "department": request.get("department") or "",
                   "route": known[choice][1], "origin": request.get("origin") or "kpi-dashboards", "rows": None}
        st.session_state[DRILL_STATE_KEY] = request
    return request


def _print_panel(repo: Repository, row: Mapping[str, Any], register: str, key: str) -> None:
    """Selected row: open it, or preview / download its print-layout PDF (core.pdf_preview)."""
    table, record_id = str(row.get("source_table") or ""), str(row.get("record_id") or "")
    with st.container(border=True, key=f"kpi_drill_selected_{key}"):
        st.markdown(f"**{row.get('reference') or record_id[:8]}** · {SOURCE_TABLES.get(table, (table, ''))[0]} · {row.get('status') or ''}")
        if st.button("Open record", icon=":material/open_in_new:", key=f"kpi_drill_open_{key}", type="primary"):
            _open_row(repo, row, register)
        try:
            from core.pdf_preview import pdf_actions
        except Exception:  # print layouts not available in this build
            return
        pdf_actions(table, record_id, key=f"kpi_drill_{key}", label="Print layout", repo=repo, customer_safe=None)


def render() -> None:
    request = _request()
    page_header("KPI Details", str(request.get("label") or "Records behind a KPI card"), "KPI Dashboards")
    pages = st.session_state.get("_qsms_pages") or {}
    repo = Repository()
    origin = str(request.get("origin") or "kpi-dashboards")
    register = str(request.get("route") or "")
    top1, top2, top3 = st.columns([1.4, 1.8, 6.8], gap="small", vertical_alignment="center")
    if top1.button("Back", icon=":material/arrow_back:", key="kpi_drill_back", width="stretch") and origin in pages:
        st.switch_page(pages[origin])
    if register in pages and top2.button("Open full register", icon=":material/table_view:", key="kpi_drill_register", width="stretch"):
        st.switch_page(pages[register])
    with top3:
        request = _picker(request)
    register = str(request.get("route") or register)
    key = str(request.get("key") or "")
    local_rows = request.get("rows")
    if local_rows is None and not key:
        st.info("Click any KPI card on the dashboards or module pages to see the records behind it here, or choose a KPI above.")
        return
    if local_rows is not None:
        rows = [dict(r) for r in local_rows]
    else:
        from core.auth import current_profile
        profile = current_profile() or {}
        user_key = f"{profile.get('tenant_id') or ''}:{profile.get('id') or profile.get('email') or ''}"
        # server side: qcms_kpi_drilldown (module metrics) / qcms_kpi_records (start-dashboard keys)
        rows = _records(user_key, key, str(request.get("department") or ""), repo)
        if rows is None:
            st.info("KPI details need the R37 database update (qcms_kpi_drilldown). The full register is available with **Open full register**.")
            return
        if rows and rows[0].get("_error"):
            from core.db_errors import db_message
            st.warning(f"The records could not be loaded: {db_message(Exception(rows[0]['_error']))}")
            return
    value = request.get("value")
    disposition_cards([
        {"label": "KPI", "value": request.get("label") or catalog().get(key, (key, ""))[0], "foot": str(request.get("department") or "").replace("_", " ").title() or "Dashboard"},
        {"label": "Value on the card", "value": value if value not in (None, "") else len(rows), "foot": "Live"},
        {"label": "Records", "value": f"{len(rows):,}" + ("+" if local_rows is None and len(rows) >= ROW_LIMIT else ""), "foot": "Click a row to open it"},
    ])
    if not rows:
        st.success("No records behind this KPI right now.")
        return
    from core.report_filters import render_filters, report_exports
    frame = drill_frame(rows)
    frame.index = range(len(rows))           # position in ``rows`` survives filtering
    view = render_filters(frame, f"kpi_drill_{key or 'local'}", date_cols=["Date"], default_cols=["Status"], title="Filter these records")
    positions = [int(i) for i in view.index]
    view = view.reset_index(drop=True)
    head1, head2 = st.columns([6, 3], gap="small", vertical_alignment="bottom")
    with head1:
        section_bar(f"RECORDS · {len(view):,}", "Click a row to open the record in its own entry screen")
    mode = head2.segmented_control("Row click", list(ROW_ACTIONS), default=ROW_ACTIONS[0], key="kpi_drill_row_mode",
                                   label_visibility="collapsed") or ROW_ACTIONS[0]
    grid_key = f"kpi_drill_grid_{key or 'local'}_{int(st.session_state.get('_kpi_drill_nonce', 0))}"
    clicked = selectable_table(view, key=grid_key, height=min(620, 42 + 35 * max(1, len(view))))
    if clicked is not None and 0 <= clicked < len(positions):
        row = rows[positions[clicked]]
        if row.get("record_id"):
            if mode == ROW_ACTIONS[0]:
                _open_row(repo, row, register)
            else:
                _print_panel(repo, row, register, f"{key or 'local'}_{positions[clicked]}")
    report_exports(view, f"KPI · {request.get('label') or key or 'details'}", f"kpi_drill_{key or 'local'}")


__all__ = ["render", "open_kpi_details", "catalog"]
