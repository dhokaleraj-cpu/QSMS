"""QCMS R36b · reusable report filters.

``render_filters(frame, key)`` shows one compact filter panel above any report table and
returns the filtered frame (exports must use the returned frame):

* free-text search across every column (all words must match),
* multiselect for low-cardinality text columns (status, customer, supplier, part, grade, heat…),
* date range for date / timestamp columns,
* number range (min / max) for numeric columns,
* "Clear filters", and per-report memory in ``st.session_state`` (survives page switches).

The pure helpers ``detect_columns`` and ``apply_filters`` hold all filtering logic and are
unit-tested without Streamlit.
"""
from __future__ import annotations

import re
import zlib
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

MAX_CHOICES = 60
PRIORITY_WORDS = (
    "status", "customer", "supplier", "vendor", "party", "part", "fsi", "grade", "heat", "stage", "module",
    "type", "process", "decision", "result", "disposition", "movement", "direction", "section", "plant", "department",
)
DATE_PATTERN = re.compile(r"(date|month|created|updated|activity|timestamp|(^|[ _])at$|[ _]on$)")
ID_PATTERN = re.compile(r"\b(number|no|code|invoice|challan|phone|heat|batch|lot|reference|ref)\b")
QTY_PATTERN = re.compile(r"\b(qty|quantity|kg|pcs|balance|total|count|amount|value|weight|rate|price|stock|jobs|orders)\b")
STORE_PREFIX = "_qcms_rf_store_"


# ----------------------------------------------------------------------------- pure helpers
def _text_series(series: pd.Series) -> pd.Series:
    return series.map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))


def _is_date_name(name: str) -> bool:
    return bool(DATE_PATTERN.search(str(name).casefold().strip()))


def _is_identifier_name(name: str) -> bool:
    low = str(name).casefold().replace("_", " ")
    return bool(ID_PATTERN.search(low)) and not QTY_PATTERN.search(low)


def _as_dates(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        out = series
        try:
            if getattr(out.dt, "tz", None) is not None:
                out = out.dt.tz_convert(None)
        except Exception:
            pass
        return out.dt.normalize()
    text = _text_series(series).str.strip()
    parsed = pd.to_datetime(text.where(text != "", None), errors="coerce", utc=True, format="mixed")
    return parsed.dt.tz_convert(None).dt.normalize()


def _as_numbers(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return pd.Series(float("nan"), index=series.index)
    return pd.to_numeric(series, errors="coerce")


def detect_columns(frame: pd.DataFrame, *, date_cols: Sequence[str] | None = None, max_choices: int = MAX_CHOICES) -> dict[str, str]:
    """Return {column: kind} with kind in {"date", "number", "choice", "text"}."""
    kinds: dict[str, str] = {}
    forced_dates = set(date_cols or ())
    for column in frame.columns:
        series = frame[column]
        non_null = series.dropna()
        non_blank = non_null[_text_series(non_null).str.strip() != ""] if len(non_null) else non_null
        if column in forced_dates or pd.api.types.is_datetime64_any_dtype(series):
            kinds[column] = "date"
            continue
        if len(non_blank) and not pd.api.types.is_bool_dtype(series) and not _is_identifier_name(column):
            if _as_numbers(non_blank).notna().mean() >= 0.95:
                kinds[column] = "number"
                continue
        if len(non_blank) and _is_date_name(column) and not pd.api.types.is_numeric_dtype(series):
            if _as_dates(non_blank.head(200)).notna().mean() >= 0.8:
                kinds[column] = "date"
                continue
        try:
            unique = _text_series(non_blank).str.strip().nunique()
        except Exception:
            unique = max_choices + 1
        kinds[column] = "choice" if 0 < unique <= max_choices else "text"
    return kinds


def choice_options(series: pd.Series) -> list[str]:
    values = _text_series(series).str.strip()
    return sorted({v for v in values if v}, key=str.casefold)


def default_filter_columns(frame: pd.DataFrame, kinds: Mapping[str, str], limit: int = 6) -> list[str]:
    """Pick the most useful choice columns first (status, customer, supplier, part, grade, heat…)."""
    def rank(column: str) -> tuple[int, int]:
        low = str(column).casefold()
        for index, word in enumerate(PRIORITY_WORDS):
            if word in low:
                return (0, index)
        return (1, 0)
    choices = [c for c, k in kinds.items() if k == "choice"]
    choices.sort(key=rank)
    picked = [c for c in choices if rank(c)[0] == 0][:limit]
    dates = [c for c, k in kinds.items() if k == "date"][:1]
    return picked + dates


def apply_filters(frame: pd.DataFrame, spec: Mapping[str, Any] | None) -> pd.DataFrame:
    """Filter ``frame`` with spec = {"search": str, "values": {col: [..]}, "dates": {col: (from, to)},
    "numbers": {col: (min, max)}}. Missing columns and empty values are ignored."""
    spec = spec or {}
    if frame is None or frame.empty:
        return frame
    mask = pd.Series(True, index=frame.index)
    for column, wanted in (spec.get("values") or {}).items():
        if column not in frame.columns or not wanted:
            continue
        wanted_set = {str(v).strip().casefold() for v in wanted}
        mask &= _text_series(frame[column]).str.strip().str.casefold().isin(wanted_set)
    for column, bounds in (spec.get("dates") or {}).items():
        if column not in frame.columns or not bounds:
            continue
        bounds = list(bounds) + [None, None]
        start, end = bounds[0], bounds[1]
        if start in (None, "") and end in (None, ""):
            continue
        values = _as_dates(frame[column])
        if start not in (None, ""):
            mask &= (values >= pd.Timestamp(start)).fillna(False)
        if end not in (None, ""):
            mask &= (values <= pd.Timestamp(end)).fillna(False)
    for column, bounds in (spec.get("numbers") or {}).items():
        if column not in frame.columns or not bounds:
            continue
        bounds = list(bounds) + [None, None]
        low, high = bounds[0], bounds[1]
        values = _as_numbers(frame[column])
        if low not in (None, ""):
            mask &= (values >= float(low)).fillna(False)
        if high not in (None, ""):
            mask &= (values <= float(high)).fillna(False)
    for column, text in (spec.get("contains") or {}).items():
        if column in frame.columns and str(text or "").strip():
            mask &= _text_series(frame[column]).str.casefold().str.contains(str(text).strip().casefold(), regex=False)
    search = str(spec.get("search") or "").strip().casefold()
    if search:
        haystack = pd.Series("", index=frame.index)
        for column in frame.columns:
            haystack = haystack + " " + _text_series(frame[column])
        haystack = haystack.str.casefold()
        for word in [w for w in re.split(r"\s+", search) if w]:
            mask &= haystack.str.contains(word, regex=False)
    return frame[mask]


def describe_spec(spec: Mapping[str, Any] | None) -> str:
    spec = spec or {}
    parts: list[str] = []
    if spec.get("search"):
        parts.append(f"Search: {spec['search']}")
    for column, wanted in (spec.get("values") or {}).items():
        if wanted:
            parts.append(f"{column}: {', '.join(str(v) for v in list(wanted)[:6])}{'…' if len(wanted) > 6 else ''}")
    for column, bounds in (spec.get("dates") or {}).items():
        b = list(bounds or []) + [None, None]
        if b[0] or b[1]:
            parts.append(f"{column}: {b[0] or '…'} to {b[1] or '…'}")
    for column, bounds in (spec.get("numbers") or {}).items():
        b = list(bounds or []) + [None, None]
        if b[0] not in (None, "") or b[1] not in (None, ""):
            parts.append(f"{column}: {b[0] if b[0] not in (None, '') else '…'} to {b[1] if b[1] not in (None, '') else '…'}")
    return " · ".join(parts)


def totals_row(frame: pd.DataFrame, label_column: str | None = None, *, label: str = "TOTAL", skip: Iterable[str] = ()) -> pd.DataFrame:
    """Return ``frame`` plus one totals row (sums of numeric columns)."""
    if frame is None or frame.empty:
        return frame
    skip = set(skip)
    total: dict[str, Any] = {c: None for c in frame.columns}
    for column in frame.columns:
        if column in skip:
            continue
        series = frame[column]
        if pd.api.types.is_bool_dtype(series) or _is_identifier_name(column) or _is_date_name(column):
            continue
        numeric = pd.to_numeric(series, errors="coerce")
        present = series.notna() & (_text_series(series).str.strip() != "")
        if pd.api.types.is_numeric_dtype(series) or (present.any() and numeric[present].notna().mean() >= 0.95):
            if any(word in str(column).casefold() for word in ("%", "percent", "achievement")):
                continue
            total[column] = round(float(numeric.fillna(0).sum()), 3)
    first = label_column if label_column in frame.columns else frame.columns[0]
    total[first] = label
    return pd.concat([frame, pd.DataFrame([total])], ignore_index=True)


# ----------------------------------------------------------------------------- Streamlit panel
def _state():
    import streamlit as st
    return st.session_state


def active_filter_text(key: str) -> str:
    try:
        return describe_spec(_state().get(f"{STORE_PREFIX}{key}", {}).get("spec"))
    except Exception:
        return ""


def _clear(key: str) -> None:
    state = _state()
    prefix = f"rf_{key}::"
    for name in [k for k in list(state.keys()) if str(k).startswith(prefix)]:
        del state[name]
    state.pop(f"{STORE_PREFIX}{key}", None)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).casefold()).strip("_")[:40] or "col"


def render_filters(
    frame: pd.DataFrame,
    key: str,
    *,
    date_cols: Sequence[str] | None = None,
    default_cols: Sequence[str] | None = None,
    exclude: Sequence[str] = (),
    title: str = "Filters",
) -> pd.DataFrame:
    """Render the filter panel for one report and return the filtered frame."""
    import streamlit as st

    if frame is None:
        return frame
    if not isinstance(frame, pd.DataFrame):
        frame = pd.DataFrame(frame)
    state = st.session_state
    store_key = f"{STORE_PREFIX}{key}"
    store: dict = dict(state.get(store_key) or {})
    widgets: dict = dict(store.get("widgets") or {})

    def remember(widget_key: str, fallback: Any = None) -> None:
        # Restore a value from the per-report memory after a page switch removed the widget state.
        if widget_key not in state and widget_key in widgets:
            state[widget_key] = widgets[widget_key]
        elif widget_key not in state and fallback is not None:
            state[widget_key] = fallback

    columns = [c for c in frame.columns if c not in set(exclude)]
    kinds = detect_columns(frame[columns], date_cols=date_cols) if columns else {}
    preset = [c for c in (default_cols or []) if c in kinds] or default_filter_columns(frame[columns], kinds)

    spec: dict[str, Any] = {"search": "", "values": {}, "dates": {}, "numbers": {}}
    with st.container(border=True, key=f"qcms_report_filters_{_slug(key)}"):
        c1, c2, c3 = st.columns([5, 4, 1.4], gap="small", vertical_alignment="bottom")
        search_key = f"rf_{key}::search"
        remember(search_key)
        spec["search"] = c1.text_input(f"{title} · search all columns", key=search_key, placeholder="Type any part, heat, supplier, number, status…")
        cols_key = f"rf_{key}::columns"
        if cols_key in widgets:
            widgets[cols_key] = [c for c in widgets[cols_key] if c in kinds]
        remember(cols_key, preset)
        if cols_key in state:
            state[cols_key] = [c for c in state[cols_key] if c in kinds]
        chosen = c2.multiselect("Filter by columns", list(kinds), key=cols_key, placeholder="Add filter columns")
        c3.button("Clear filters", key=f"rf_clear_{key}", on_click=_clear, args=(key,), width="stretch", icon=":material/filter_alt_off:")

        if chosen:
            grid = st.columns(min(4, len(chosen)), gap="small")
            for index, column in enumerate(chosen):
                holder = grid[index % len(grid)]
                kind = kinds.get(column, "text")
                wkey = f"rf_{key}::{_slug(column)}_{zlib.crc32(str(column).encode()) % 100000}"
                if kind == "date":
                    values = _as_dates(frame[column]).dropna()
                    wkey_from, wkey_to = wkey + "_from", wkey + "_to"
                    remember(wkey_from); remember(wkey_to)
                    lo = values.min().date() if len(values) else None
                    hi = values.max().date() if len(values) else None
                    d1, d2 = holder.columns(2, gap="small")
                    start = d1.date_input(f"{column} from", key=wkey_from, format="DD-MM-YYYY", help=f"Data from {lo or '-'} to {hi or '-'}",
                                          **({} if wkey_from in state else {"value": None}))
                    end = d2.date_input(f"{column} to", key=wkey_to, format="DD-MM-YYYY", **({} if wkey_to in state else {"value": None}))
                    spec["dates"][column] = (start, end)
                elif kind == "number":
                    wkey_lo, wkey_hi = wkey + "_min", wkey + "_max"
                    remember(wkey_lo); remember(wkey_hi)
                    n1, n2 = holder.columns(2, gap="small")
                    low = n1.number_input(f"{column} min", key=wkey_lo, format="%g", **({} if wkey_lo in state else {"value": None}))
                    high = n2.number_input(f"{column} max", key=wkey_hi, format="%g", **({} if wkey_hi in state else {"value": None}))
                    spec["numbers"][column] = (low, high)
                elif kind == "choice":
                    options = choice_options(frame[column])
                    if wkey in widgets:
                        widgets[wkey] = [v for v in widgets[wkey] if v in options]
                    remember(wkey)
                    if wkey in state:
                        state[wkey] = [v for v in state[wkey] if v in options]
                    spec["values"][column] = holder.multiselect(column, options, key=wkey, placeholder="All")
                else:
                    remember(wkey)
                    contains = holder.text_input(f"{column} contains", key=wkey)
                    if contains:
                        spec.setdefault("contains", {})[column] = contains

        filtered = apply_filters(frame, spec)
        summary = describe_spec(spec)
        st.caption(f"Showing {len(filtered):,} of {len(frame):,} row(s)" + (f" · {summary}" if summary else " · no filters applied"))

    saved_widgets = {k: state[k] for k in list(state.keys()) if str(k).startswith(f"rf_{key}::")}
    state[store_key] = {"widgets": saved_widgets, "spec": spec}
    return filtered


def _safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(text or "QCMS_Report")).strip("_")[:60] or "QCMS_Report"


def report_exports(sections: pd.DataFrame | Mapping[str, pd.DataFrame], title: str, key: str, *, subtitle: str = "") -> None:
    """Excel + PDF download buttons for the (already filtered) report frame(s)."""
    import streamlit as st
    from datetime import date as _date

    if isinstance(sections, pd.DataFrame):
        sections = {title[:31] or "Report": sections}
    sections = {name: frame for name, frame in sections.items() if frame is not None}
    if not sections or all(frame.empty for frame in sections.values()):
        return
    note = subtitle or active_filter_text(key)
    stamp = _date.today().isoformat()

    def _excel() -> bytes:
        from core.report_builder import excel_bytes
        return excel_bytes([(name, frame) for name, frame in sections.items()], title=title, subtitle=note)

    def _pdf() -> bytes:
        from core.reporting import report_pdf_bytes
        try:
            return report_pdf_bytes(title.upper(), sections, subtitle=note or "All records")
        except Exception as exc:  # very wide tables: fall back to a trimmed layout, never crash the page
            trimmed = {name: frame.head(300).iloc[:, :14].astype(str).apply(lambda col: col.str.slice(0, 40)) for name, frame in sections.items()}
            return report_pdf_bytes(title.upper(), trimmed, subtitle=f"{note} · trimmed layout ({type(exc).__name__}); use Excel for every column")

    c1, c2 = st.columns(2, gap="small")
    c1.download_button("Download Excel", data=_excel, file_name=f"{_safe_name(title)}_{stamp}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/table_view:",
                       width="stretch", key=f"rf_export_xlsx_{key}", on_click="ignore")
    c2.download_button("Download PDF", data=_pdf, file_name=f"{_safe_name(title)}_{stamp}.pdf", mime="application/pdf",
                       icon=":material/picture_as_pdf:", width="stretch", key=f"rf_export_pdf_{key}", on_click="ignore")


def report_register(
    frame: pd.DataFrame,
    key: str,
    title: str,
    *,
    height: int = 520,
    style: Any = None,
    date_cols: Sequence[str] | None = None,
    default_cols: Sequence[str] | None = None,
    exclude: Sequence[str] = (),
    exports: bool = True,
) -> pd.DataFrame:
    """Filters → table → Excel/PDF export of the filtered rows. Returns the filtered frame."""
    from core.ui import portal_table

    filtered = render_filters(frame, key, date_cols=date_cols, default_cols=default_cols, exclude=exclude)
    shown = filtered.drop(columns=[c for c in exclude if c in filtered.columns]) if exclude else filtered
    portal_table(style(shown) if style is not None and not shown.empty else shown, hide_index=True, width="stretch", height=height)
    if exports:
        report_exports(shown, title, key)
    return filtered


__all__ = [
    "apply_filters", "detect_columns", "default_filter_columns", "choice_options", "describe_spec", "totals_row",
    "render_filters", "active_filter_text", "report_exports", "report_register",
]
