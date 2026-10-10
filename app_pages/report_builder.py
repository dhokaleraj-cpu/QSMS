"""QCMS R16 · Report Builder and Master List Excel exports."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core.access import module_permissions
from core.auth import current_profile
from core.repository import Repository
from core.ui import page_header, portal_table, save_success_dialog, section_bar, stage_section
from core import report_builder as rb

ROW_LIMIT = 10000


def _sources():
    from app_pages.global_search import SEARCH_SOURCES
    return SEARCH_SOURCES


def _can_view_factory(profile: dict, repo: Repository):
    cache: dict[str, bool] = {}

    def can_view(module_key: str) -> bool:
        if module_key not in cache:
            try:
                cache[module_key] = bool(module_permissions(profile, module_key, repo).get("can_view"))
            except Exception:
                cache[module_key] = False
        return cache[module_key]
    return can_view


def _loader(repo: Repository):
    def load(table: str) -> list[dict]:
        return repo.select(table, limit=ROW_LIMIT)
    return load


# ----------------------------------------------------------------------------- Report Builder
def render() -> None:
    page_header("Report Builder", "Build any report from the QCMS data you are allowed to see: pick a dataset, columns and filters, group and total, chart it, then download Excel / CSV or save it for next time.", "Reports")
    repo = Repository(); profile = current_profile() or {}
    can_view = _can_view_factory(profile, repo)
    sources = [s for s in _sources() if can_view(str(s.get("module_key") or ""))]
    if not sources:
        st.info("You do not have View permission on any QCMS dataset.")
        return
    by_table = {str(s["table"]): s for s in sources}
    saved = [r for r in rb.saved_reports(repo) if r["spec"].dataset in by_table]
    owner = str(profile.get("full_name") or profile.get("email") or "QCMS user")

    with stage_section("A", "SAVED REPORTS", "Open a report saved earlier, or start a new one.", key="rb_saved"):
        labels = {"": "＋ New report", **{str(r["id"]): f"{r['name']} · {by_table[r['spec'].dataset]['record_type']} · by {r['owner'] or '-'}" for r in saved}}
        chosen = st.selectbox("Report", list(labels), format_func=labels.get, key="rb_pick")
    base = next((r for r in saved if str(r["id"]) == chosen), None)
    spec0: rb.ReportSpec = base["spec"] if base else rb.ReportSpec(dataset=next(iter(by_table)))
    token = chosen or "new"

    with stage_section("B", "DATA & COLUMNS", "Choose what the report is about and which columns to show.", key="rb_data"):
        tables = list(by_table)
        dataset = st.selectbox("Dataset", tables, index=tables.index(spec0.dataset) if spec0.dataset in tables else 0, format_func=lambda t: f"{by_table[t]['record_type']} · {by_table[t]['module']}", key=f"rb_dataset_{token}")
        with st.spinner("Loading data..."):
            try:
                rows = repo.select(dataset, limit=ROW_LIMIT)
            except Exception as exc:
                st.error(f"Could not read {by_table[dataset]['record_type']}: {exc}")
                return
            frame = rb.readable_frame(rows, _loader(repo))
        if frame.empty:
            st.info("No records in this dataset yet.")
            return
        st.caption(f"{len(frame):,} record(s) loaded" + (" (first 10,000)" if len(rows) >= ROW_LIMIT else "") + ". Linked IDs are shown as part numbers, party names, employees, etc.")
        all_cols = list(frame.columns)
        default_cols = [c for c in (spec0.columns if spec0.dataset == dataset else []) if c in all_cols] or [c for c in by_table[dataset].get("columns", ()) if c in all_cols][:8] or all_cols[:8]
        columns = st.multiselect("Columns (in this order)", all_cols, default=default_cols, format_func=rb.pretty, key=f"rb_cols_{token}_{dataset}")

    with stage_section("C", "FILTERS", "Narrow the records. All filters must match.", key="rb_filters"):
        start = [f for f in (spec0.filters if spec0.dataset == dataset else []) if f.get("column") in all_cols]
        n = int(st.number_input("Number of filters", min_value=0, max_value=8, value=len(start), step=1, key=f"rb_nf_{token}_{dataset}"))
        filters: list[dict] = []
        ops = list(rb.OPERATORS)
        for i in range(n):
            f0 = start[i] if i < len(start) else {}
            c = st.columns([3, 2, 3, 3], gap="small")
            col = c[0].selectbox(f"Column {i + 1}", all_cols, index=all_cols.index(f0["column"]) if f0.get("column") in all_cols else 0, format_func=rb.pretty, key=f"rb_fc_{token}_{dataset}_{i}")
            op = c[1].selectbox("Condition", ops, index=ops.index(f0.get("op", "contains")) if f0.get("op") in ops else 0, format_func=rb.OPERATORS.get, key=f"rb_fo_{token}_{dataset}_{i}")
            v1 = c[2].text_input("Value", value=str(f0.get("value") or ""), key=f"rb_fv_{token}_{dataset}_{i}", disabled=op in {"is_empty", "not_empty"}, help="Dates as YYYY-MM-DD")
            v2 = c[3].text_input("To (for between)", value=str(f0.get("value2") or ""), key=f"rb_fv2_{token}_{dataset}_{i}", disabled=op != "between")
            filters.append({"column": col, "op": op, "value": v1, "value2": v2})

    with stage_section("D", "GROUP, TOTAL & SORT", "Optional: group rows (e.g. by Supplier) and add totals / averages.", key="rb_group"):
        c = st.columns(2, gap="small")
        group_by = c[0].multiselect("Group by", all_cols, default=[g for g in (spec0.group_by if spec0.dataset == dataset else []) if g in all_cols], format_func=rb.pretty, key=f"rb_gb_{token}_{dataset}")
        measure_cols = c[1].multiselect("Totals for columns", all_cols, default=[m["column"] for m in (spec0.measures if spec0.dataset == dataset else []) if m.get("column") in all_cols], format_func=rb.pretty, key=f"rb_mc_{token}_{dataset}", disabled=not group_by)
        measures = []
        if group_by and measure_cols:
            cols = st.columns(min(4, len(measure_cols)), gap="small")
            prior = {m["column"]: m.get("agg", "sum") for m in spec0.measures}
            aggs = list(rb.AGGREGATES)
            for i, mc in enumerate(measure_cols):
                agg = cols[i % len(cols)].selectbox(f"{rb.pretty(mc)}", aggs, index=aggs.index(prior.get(mc, "sum")) if prior.get(mc, "sum") in aggs else 1, format_func=rb.AGGREGATES.get, key=f"rb_agg_{token}_{dataset}_{mc}")
                measures.append({"column": mc, "agg": agg})
        c = st.columns([3, 2, 2, 2], gap="small")
        sort_options = [""] + all_cols
        sort_by = c[0].selectbox("Sort by", sort_options, index=sort_options.index(spec0.sort_by) if spec0.sort_by in sort_options else 0, format_func=lambda v: rb.pretty(v) if v else "— None —", key=f"rb_sort_{token}_{dataset}")
        descending = c[1].toggle("Highest first", value=spec0.descending, key=f"rb_desc_{token}_{dataset}")
        limit = int(c[2].number_input("Max rows (0 = all)", min_value=0, max_value=ROW_LIMIT, value=int(spec0.limit or 0), step=50, key=f"rb_lim_{token}_{dataset}"))
        charts = ["", "bar", "line", "pie"]
        chart = c[3].selectbox("Chart", charts, index=charts.index(spec0.chart) if spec0.chart in charts else 0, format_func=lambda v: {"": "No chart", "bar": "Bar", "line": "Line", "pie": "Pie"}[v], key=f"rb_chart_{token}_{dataset}")

    title = st.text_input("Report title", value=spec0.title or (base["name"] if base else f"{by_table[dataset]['record_type']} report"), key=f"rb_title_{token}")
    spec = rb.ReportSpec(dataset=dataset, columns=columns, filters=filters, group_by=group_by, measures=measures, sort_by=sort_by, descending=descending, limit=limit, title=title, chart=chart)
    try:
        result = rb.build_report(frame, spec)
    except Exception as exc:
        st.error(str(exc))
        return

    section_bar("RESULT", f"{len(result):,} row(s)")
    if result.empty:
        st.info("No records match these filters.")
    else:
        portal_table(result, hide_index=True, width="stretch", height=min(560, 60 + 34 * len(result)))
        if chart and len(result.columns) >= 2:
            import plotly.express as px
            x = result.columns[0]
            numeric = [col for col in result.columns[1:] if pd.to_numeric(result[col], errors="coerce").notna().any()]
            y = numeric[-1] if numeric else None
            if y:
                data = result.head(40).assign(**{y: pd.to_numeric(result[y].head(40), errors="coerce")})
                fig = px.pie(data, names=x, values=y) if chart == "pie" else (px.line(data, x=x, y=y, markers=True) if chart == "line" else px.bar(data, x=x, y=y, text=y))
                fig.update_layout(height=380, margin=dict(l=8, r=8, t=10, b=8), paper_bgcolor="white", plot_bgcolor="white")
                st.plotly_chart(fig, width="stretch", key=f"rb_fig_{token}")
            else:
                st.caption("Add a Group by and a Total to draw a chart.")
    stamp = date.today().isoformat()
    safe = "".join(ch if ch.isalnum() else "_" for ch in title)[:60] or "QCMS_Report"
    c = st.columns(4, gap="small")
    c[0].download_button("Download Excel", data=lambda: rb.excel_bytes([(title[:31], result)], title=title), file_name=f"{safe}_{stamp}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch", key=f"rb_xlsx_{token}", on_click="ignore", disabled=result.empty)
    c[1].download_button("Download CSV", data=result.to_csv(index=False).encode("utf-8"), file_name=f"{safe}_{stamp}.csv", mime="text/csv", width="stretch", key=f"rb_csv_{token}", on_click="ignore", disabled=result.empty)
    name = c[2].text_input("Save as", value=base["name"] if base else title, key=f"rb_name_{token}", label_visibility="collapsed", placeholder="Report name")
    if c[3].button("Update saved report" if base else "Save report", type="primary", width="stretch", key=f"rb_save_{token}"):
        try:
            rb.save_report(repo, name, spec, owner, existing_id=str(base["id"]) if base else None)
            save_success_dialog("Report saved", f"**{name}** is saved. Anyone who can view {by_table[dataset]['record_type']} can open it from Saved Reports.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if base and st.button("Delete this saved report", key=f"rb_del_{token}"):
        try:
            rb.delete_report(repo, str(base["id"])); st.session_state.pop("rb_pick", None); st.rerun()
        except Exception as exc:
            st.error(str(exc))


# ----------------------------------------------------------------------------- Master List Excel
def master_catalog() -> list[dict]:
    """Every master list QCMS can export: (key, label, group, table, filter, module)."""
    from core.master_definitions import DEFINITIONS
    items = []
    for d in DEFINITIONS:
        items.append({"key": d.key, "label": d.label, "group": d.group, "table": d.table, "array_filter": dict(d.array_filter),
                      "columns": [f.name for f in d.fields], "labels": {f.name: f.label for f in d.fields},
                      "module": rb.MASTER_MODULE.get(d.table, "REFERENCE_MASTERS"), "order_by": d.order_by})
    items.append({"key": "employees", "label": "Employees", "group": "People", "table": "employees", "array_filter": {},
                  "columns": ["employee_code", "first_name", "last_name", "email", "department", "designation", "phone", "status"], "labels": {},
                  "module": "EMPLOYEE_MASTER", "order_by": "employee_code"})
    return items


def master_frame(item: dict, rows: list[dict], load) -> pd.DataFrame:
    for field, values in (item.get("array_filter") or {}).items():
        wanted = {str(v).upper() for v in values}
        rows = [r for r in rows if wanted & {str(v).upper() for v in (r.get(field) or [])}]
    frame = rb.readable_frame(rows, load)
    if frame.empty:
        return pd.DataFrame(columns=[item["labels"].get(c, rb.pretty(c)) for c in item["columns"]])
    first = [c for c in item["columns"] if c in frame.columns]
    rest = [c for c in frame.columns if c not in first and c not in {"created_at", "updated_at"}]
    frame = frame[first + rest + [c for c in ("created_at", "updated_at") if c in frame.columns]]
    if item.get("order_by") in frame.columns:
        frame = frame.sort_values(item["order_by"], key=lambda s: s.astype(str).str.lower())
    frame.columns = [item["labels"].get(c, rb.pretty(c)) for c in frame.columns]
    return frame.reset_index(drop=True)


def render_master_lists() -> None:
    page_header("Master List Excel", "Download clean Excel lists of every master: Part Master, Customers, Suppliers, Steel Mills, OSP Vendors, Grades, Processes, Stages, Quality Assets, Layouts, Employees and more.", "Reports")
    repo = Repository(); profile = current_profile() or {}
    can_view = _can_view_factory(profile, repo)
    items = [i for i in master_catalog() if can_view(i["module"])]
    if not items:
        st.info("You do not have View permission on any master.")
        return
    load = _loader(repo)
    groups = sorted({i["group"] for i in items})
    with stage_section("A", "CHOOSE MASTERS", "Pick one or many. Each master becomes its own sheet in one workbook.", key="ml_pick"):
        chosen: list[dict] = []
        cols = st.columns(len(groups), gap="small")
        for col, group in zip(cols, groups):
            with col:
                st.markdown(f"**{group}**")
                for item in [i for i in items if i["group"] == group]:
                    if st.checkbox(item["label"], value=item["key"] in {"parts", "customers", "suppliers"}, key=f"ml_{item['key']}"):
                        chosen.append(item)
        active_only = st.toggle("Active records only", value=False, key="ml_active")
    if not chosen:
        st.info("Select at least one master.")
        return
    sheets: list[tuple[str, pd.DataFrame]] = []
    table_cache: dict[str, list[dict]] = {}
    with st.spinner("Preparing master lists..."):
        for item in chosen:
            if item["table"] not in table_cache:
                try:
                    table_cache[item["table"]] = repo.select(item["table"], limit=ROW_LIMIT)
                except Exception as exc:
                    st.warning(f"{item['label']}: {exc}")
                    table_cache[item["table"]] = []
            rows = table_cache[item["table"]]
            if active_only:
                rows = [r for r in rows if str(r.get("status") or "ACTIVE").upper() == "ACTIVE"]
            sheets.append((item["label"], master_frame(item, rows, load)))
    section_bar("PREVIEW", " · ".join(f"{name}: {len(frame):,}" for name, frame in sheets))
    tabs = st.tabs([name for name, _ in sheets])
    for tab, (name, frame) in zip(tabs, sheets):
        with tab:
            portal_table(frame.head(200), hide_index=True, width="stretch", height=min(480, 60 + 34 * min(len(frame), 200)))
            if len(frame) > 200:
                st.caption(f"Showing first 200 of {len(frame):,}. The Excel file contains all rows.")
    stamp = date.today().isoformat()
    st.download_button(f"Download {len(sheets)} master list(s) as one Excel workbook", data=lambda: rb.excel_bytes(sheets, title="Master List", subtitle="Active only" if active_only else "All statuses"),
                       file_name=f"QCMS_Master_Lists_{stamp}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", width="stretch", key="ml_xlsx", on_click="ignore")
