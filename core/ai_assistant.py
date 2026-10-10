"""QCMS AI Assistant for Global Search (R11).

Natural-language questions, analysis and reports over QCMS data using Claude, or a free provider (Google Gemini / Groq) - R15.

Security contract
-----------------
* READ-ONLY: the model can only call the three query tools below; there is no tool
  that inserts, updates or deletes anything.
* Same data rights as the user: every query goes through the user's tenant/RLS-scoped
  ``Repository`` and only datasets whose QCMS module the user can VIEW are exposed.
* Only the rows a tool returns (trimmed) are sent to the Claude API, never the whole
  database. Configure ``ANTHROPIC_API_KEY`` (and optionally ``QCMS_AI_MODEL``) in
  ``.streamlit/secrets.toml`` / Streamlit Cloud secrets.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5-5"

# R15 · pluggable providers. "gemini" and "groq" have free API tiers (rate-limited, and the
# provider may use free-tier prompts to improve its products). Both speak the OpenAI
# chat-completions format with tool calling, so one adapter serves them all.
PROVIDERS: dict[str, dict[str, str]] = {
    "claude": {"label": "Claude (Anthropic) · paid API", "key": "ANTHROPIC_API_KEY", "model": DEFAULT_MODEL, "url": API_URL, "style": "anthropic"},
    "gemini": {"label": "Google Gemini · FREE tier available", "key": "GEMINI_API_KEY", "model": "gemini-flash-latest", "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "style": "openai"},
    "groq": {"label": "Groq (open models) · FREE tier available", "key": "GROQ_API_KEY", "model": "openai/gpt-oss-120b", "url": "https://api.groq.com/openai/v1/chat/completions", "style": "openai"},
    "openai": {"label": "OpenAI (ChatGPT API) · paid API", "key": "OPENAI_API_KEY", "model": "gpt-5-mini", "url": "https://api.openai.com/v1/chat/completions", "style": "openai"},
}


def resolve_provider(secret: Callable[[str, str], str]) -> tuple[str, str, str]:
    """Return (provider, api_key, model) from secrets.

    ``QCMS_AI_PROVIDER`` picks the provider explicitly; otherwise the first provider that
    has a key wins, free providers first so a free key is used before a paid one.
    """
    wanted = str(secret("QCMS_AI_PROVIDER", "") or "").strip().lower()
    order = [wanted] if wanted in PROVIDERS else ["gemini", "groq", "claude", "openai"]
    for name in order:
        key = str(secret(PROVIDERS[name]["key"], "") or "").strip()
        if key or wanted == name:
            model = str(secret("QCMS_AI_MODEL", "") or "").strip()
            if not model or (name != "claude" and model.startswith("claude")):
                model = PROVIDERS[name]["model"]
            return name, key, model
    return "gemini", "", PROVIDERS["gemini"]["model"]


def openai_tools(tools: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t.get("input_schema") or {"type": "object", "properties": {}}}} for t in tools]
MAX_FETCH_ROWS = 5000          # rows read from Supabase per tool call
MAX_ROWS_TO_MODEL = 60         # rows sent back to the model per tool call
MAX_CELL_CHARS = 240
MAX_TOOL_ROUNDS = 10
REPORT_ROW_LIMIT = 5000

LABEL_LOOKUPS: dict[str, tuple[str, tuple[str, ...]]] = {
    # foreign-key column -> (master table, label fields)
    "part_id": ("parts", ("part_number", "fsi_part_number", "part_name")),
    "customer_id": ("parties", ("party_code", "party_name")),
    "supplier_id": ("parties", ("party_code", "party_name")),
    "party_id": ("parties", ("party_code", "party_name")),
    "vendor_id": ("parties", ("party_code", "party_name")),
    "steel_mill_id": ("parties", ("party_code", "party_name")),
    "rm_supplier_id": ("parties", ("party_code", "party_name")),
    "forging_supplier_id": ("parties", ("party_code", "party_name")),
    "material_grade_id": ("material_grades", ("grade_code",)),
    "process_id": ("processes", ("process_code", "process_name")),
}
LABEL_MASTER_MODULE = {"parts": "PART_MASTER", "parties": "REFERENCE_MASTERS", "material_grades": "MATERIAL_GRADE", "processes": "REFERENCE_MASTERS"}

FILTER_OPS = ("eq", "neq", "contains", "gt", "gte", "lt", "lte", "in", "is_null", "not_null")

_FILTER_SCHEMA = {
    "type": "array",
    "description": "Optional row filters, all must match (AND). Use describe_dataset first if unsure of column names. Dates are ISO yyyy-mm-dd. For a part/party column you may filter on its readable '<column>_label' (e.g. part_id_label contains '40256626').",
    "items": {
        "type": "object",
        "properties": {
            "column": {"type": "string"},
            "op": {"type": "string", "enum": list(FILTER_OPS)},
            "value": {"description": "Value to compare. A list for op 'in'. Omit for is_null / not_null."},
        },
        "required": ["column", "op"],
    },
}
_REPORT_PROPS = {
    "show_as_report": {"type": "boolean", "description": "true to show the full result as a downloadable table (Excel/CSV) in the user's screen. Use when the user asks for a list, report, register or export."},
    "report_title": {"type": "string", "description": "Short title for the report table."},
    "chart": {
        "type": "object",
        "description": "Optional chart for the report: type bar | line | pie, x = category/date column, y = numeric column.",
        "properties": {"type": {"type": "string", "enum": ["bar", "line", "pie"]}, "x": {"type": "string"}, "y": {"type": "string"}},
    },
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "describe_dataset",
        "description": "Return the columns, row count (up to 5000) and two sample rows of one permitted QCMS dataset. Call this before querying a dataset whose columns you do not know.",
        "input_schema": {"type": "object", "properties": {"dataset": {"type": "string"}}, "required": ["dataset"]},
    },
    {
        "name": "query_records",
        "description": "Read matching rows from one permitted QCMS dataset (read-only). Returns the matched count and up to 60 rows. Part/party/grade/process id columns are given readable '<column>_label' values.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset": {"type": "string"},
                "filters": _FILTER_SCHEMA,
                "search_text": {"type": "string", "description": "Optional free-text search across the dataset's main text columns (part no., heat, RMTC, PO no., names...)."},
                "columns": {"type": "array", "items": {"type": "string"}, "description": "Columns to return (default: all)."},
                "order_by": {"type": "string"},
                "descending": {"type": "boolean"},
                "limit": {"type": "integer", "description": "Max rows to keep after filtering (default 500, max 5000)."},
                **_REPORT_PROPS,
            },
            "required": ["dataset"],
        },
    },
    {
        "name": "aggregate_records",
        "description": "Group and summarise one permitted QCMS dataset (count / sum / avg / min / max), e.g. rejections by part, PO value by supplier, complaints by month. Use group_by '<date column>:month' or ':year' for time trends.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset": {"type": "string"},
                "filters": _FILTER_SCHEMA,
                "search_text": {"type": "string"},
                "group_by": {"type": "array", "items": {"type": "string"}, "description": "Columns to group by (may use '<col>_label' or '<date col>:month')."},
                "metric": {"type": "string", "enum": ["count", "sum", "avg", "min", "max"]},
                "value_column": {"type": "string", "description": "Numeric column for sum/avg/min/max."},
                "top_n": {"type": "integer", "description": "Keep the top N groups by the metric (default all, max 200)."},
                **_REPORT_PROPS,
            },
            "required": ["dataset", "metric"],
        },
    },
]


@dataclass
class AIReport:
    title: str
    frame: pd.DataFrame
    chart: dict[str, Any] | None = None
    dataset: str = ""


@dataclass
class AIAnswer:
    text: str
    reports: list[AIReport] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""
    error: str = ""


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return str(value)


def _trim(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, default=_json_default, ensure_ascii=False)
        return text if len(text) <= MAX_CELL_CHARS else text[:MAX_CELL_CHARS] + "…"
    if isinstance(value, str) and len(value) > MAX_CELL_CHARS:
        return value[:MAX_CELL_CHARS] + "…"
    return value


def _clean_frame_for_model(frame: pd.DataFrame, limit: int) -> list[dict[str, Any]]:
    rows = frame.head(limit).to_dict(orient="records")
    clean = []
    for row in rows:
        out = {}
        for key, value in row.items():
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                value = None
            elif value is not None and not isinstance(value, (str, int, float, bool, dict, list)):
                value = _json_default(value)
            out[str(key)] = _trim(value)
        clean.append(out)
    return clean


class QCMSAIAssistant:
    """Tool-using Claude assistant restricted to permitted, read-only QCMS data."""

    def __init__(
        self,
        repo: Any,
        sources: Sequence[Mapping[str, Any]],
        can_view: Callable[[str], bool],
        *,
        api_key: str,
        model: str | None = None,
        post: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        provider: str = "claude",
        today: date | None = None,
        user_label: str = "",
    ) -> None:
        self.repo = repo
        self.can_view = can_view
        self.api_key = str(api_key or "").strip()
        self.provider = provider if provider in PROVIDERS else "claude"
        self.model = str(model or PROVIDERS[self.provider]["model"]).strip() or PROVIDERS[self.provider]["model"]
        self._post = post
        self.today = today or date.today()
        self.user_label = user_label
        self.datasets: dict[str, dict[str, Any]] = {}
        for source in sources:
            table = str(source.get("table") or "")
            if table and self.can_view(str(source.get("module_key") or "")):
                self.datasets[table] = dict(source)
        self._label_maps: dict[str, dict[str, str]] = {}
        self.reports: list[AIReport] = []

    # ------------------------------------------------------------------ data access
    def _label_map(self, master: str) -> dict[str, str]:
        if master not in self._label_maps:
            mapping: dict[str, str] = {}
            module = LABEL_MASTER_MODULE.get(master, "")
            if not module or self.can_view(module):
                fields = next((f for t, f in LABEL_LOOKUPS.values() if t == master), ())
                try:
                    for row in self.repo.select(master, limit=10000):
                        rid = str(row.get("id") or "")
                        if rid:
                            mapping[rid] = " · ".join(str(row.get(f) or "").strip() for f in fields if str(row.get(f) or "").strip())
                except Exception:
                    mapping = {}
            self._label_maps[master] = mapping
        return self._label_maps[master]

    def _columns(self, dataset: str) -> set[str] | None:
        """Known columns of a dataset (from one sample row) plus derived label columns."""
        cache = self.__dict__.setdefault("_column_cache", {})
        if dataset not in cache:
            try:
                sample = self.repo.select(dataset, limit=1)
            except Exception:
                sample = []
            if sample:
                cols = {str(c) for c in sample[0]}
                cols |= {f"{c}_label" for c in cols if c in LABEL_LOOKUPS}
                cache[dataset] = cols
            else:
                cache[dataset] = None
        return cache[dataset]

    def _validate_columns(self, dataset: str, names: Sequence[str]) -> None:
        known = self._columns(dataset)
        if known is None:
            return
        for name in names:
            base = str(name).split(":", 1)[0]
            if base and base not in known:
                raise ValueError(f"Column '{base}' does not exist in {dataset}. Columns: {', '.join(sorted(known))}")

    def _frame(self, dataset: str, *, search_text: str = "", eq: Mapping[str, Any] | None = None, order_by: str | None = None, descending: bool = False) -> pd.DataFrame:
        if dataset not in self.datasets:
            raise ValueError(f"Dataset '{dataset}' is not available to this user. Available: {', '.join(sorted(self.datasets))}")
        source = self.datasets[dataset]
        kwargs: dict[str, Any] = {"limit": MAX_FETCH_ROWS}
        if eq:
            kwargs["eq"] = dict(eq)
        if search_text and str(search_text).strip():
            kwargs["search_columns"] = tuple(source.get("columns") or ())
            kwargs["search_term"] = str(search_text).strip()
        if order_by:
            kwargs["order_by"] = order_by; kwargs["desc"] = bool(descending)
        try:
            rows = self.repo.select(dataset, **kwargs)
        except Exception:
            # Unknown order/eq column on the server: retry plain and filter locally.
            kwargs.pop("order_by", None); kwargs.pop("desc", None); kwargs.pop("eq", None)
            rows = self.repo.select(dataset, **kwargs)
            if eq:
                rows = [r for r in rows if all(str(r.get(k)) == str(v) for k, v in eq.items())]
        frame = pd.DataFrame(rows)
        for column in list(frame.columns):
            if column in LABEL_LOOKUPS:
                labels = self._label_map(LABEL_LOOKUPS[column][0])
                if labels:
                    frame[f"{column}_label"] = frame[column].map(lambda v: labels.get(str(v), "") if v is not None else "")
        if order_by and order_by in frame.columns:
            try:
                frame = frame.sort_values(order_by, ascending=not descending, na_position="last")
            except Exception:
                pass
        return frame

    @staticmethod
    def _apply_filters(frame: pd.DataFrame, filters: Sequence[Mapping[str, Any]] | None) -> pd.DataFrame:
        for flt in filters or ():
            column = str(flt.get("column") or "")
            op = str(flt.get("op") or "eq")
            value = flt.get("value")
            if op not in FILTER_OPS:
                raise ValueError(f"Unsupported filter op '{op}'.")
            if column not in frame.columns:
                if frame.empty:
                    continue
                raise ValueError(f"Column '{column}' does not exist. Columns: {', '.join(map(str, frame.columns))}")
            series = frame[column]
            if op == "is_null":
                mask = series.isna() | (series.astype(str).str.strip() == "")
            elif op == "not_null":
                mask = ~(series.isna() | (series.astype(str).str.strip() == ""))
            elif op == "contains":
                mask = series.astype(str).str.contains(str(value or ""), case=False, regex=False, na=False)
            elif op == "in":
                values = {str(v).casefold() for v in (value if isinstance(value, (list, tuple, set)) else [value])}
                mask = series.astype(str).str.casefold().isin(values)
            elif op in {"eq", "neq"}:
                mask = series.astype(str).str.casefold() == str(value).casefold()
                if op == "neq":
                    mask = ~mask
            else:
                numeric = pd.to_numeric(series, errors="coerce")
                target = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
                if numeric.notna().any() and not pd.isna(target):
                    left, right = numeric, target
                else:
                    left, right = series.astype(str), str(value)
                mask = {"gt": left > right, "gte": left >= right, "lt": left < right, "lte": left <= right}[op]
                mask = mask.fillna(False) if hasattr(mask, "fillna") else mask
            frame = frame[mask.astype(bool)]
        return frame

    def _record_report(self, args: Mapping[str, Any], frame: pd.DataFrame, dataset: str, default_title: str) -> str:
        if not args.get("show_as_report"):
            return ""
        chart = args.get("chart") if isinstance(args.get("chart"), dict) else None
        title = str(args.get("report_title") or default_title)
        self.reports.append(AIReport(title=title, frame=frame.head(REPORT_ROW_LIMIT).reset_index(drop=True), chart=chart, dataset=dataset))
        return f"Report '{title}' with {min(len(frame), REPORT_ROW_LIMIT)} row(s) is displayed to the user with Excel/CSV download."

    # ------------------------------------------------------------------ tools
    def tool_describe_dataset(self, args: Mapping[str, Any]) -> dict[str, Any]:
        dataset = str(args.get("dataset") or "")
        frame = self._frame(dataset)
        return {
            "dataset": dataset,
            "record_type": self.datasets[dataset].get("record_type"),
            "rows_available": int(len(frame)),
            "rows_capped_at": MAX_FETCH_ROWS,
            "columns": [str(c) for c in frame.columns],
            "sample_rows": _clean_frame_for_model(frame, 2),
        }

    def tool_query_records(self, args: Mapping[str, Any]) -> dict[str, Any]:
        dataset = str(args.get("dataset") or "")
        filters = list(args.get("filters") or [])
        if dataset in self.datasets:
            self._validate_columns(dataset, [str(f.get("column") or "") for f in filters])
        eq = {str(f["column"]): f.get("value") for f in filters if f.get("op") == "eq" and (str(f.get("column", "")) == "id" or str(f.get("column", "")).endswith("_id")) and isinstance(f.get("value"), str)}
        # Only exact id filters are pushed to Supabase; text filters stay case-insensitive locally.
        frame = self._frame(dataset, search_text=str(args.get("search_text") or ""), eq=eq or None, order_by=args.get("order_by"), descending=bool(args.get("descending")))
        frame = self._apply_filters(frame, filters)
        limit = max(1, min(int(args.get("limit") or 500), MAX_FETCH_ROWS))
        matched = int(len(frame))
        frame = frame.head(limit)
        columns = [c for c in (args.get("columns") or []) if c in frame.columns]
        if columns:
            frame = frame[columns]
        note = self._record_report(args, frame, dataset, self.datasets[dataset].get("record_type") or dataset)
        return {
            "dataset": dataset,
            "matched_rows": matched,
            "fetch_capped": matched >= MAX_FETCH_ROWS,
            "rows_returned_to_you": min(len(frame), MAX_ROWS_TO_MODEL),
            "rows": _clean_frame_for_model(frame, MAX_ROWS_TO_MODEL),
            "report": note,
        }

    def tool_aggregate_records(self, args: Mapping[str, Any]) -> dict[str, Any]:
        dataset = str(args.get("dataset") or "")
        filters = list(args.get("filters") or [])
        if dataset in self.datasets:
            self._validate_columns(dataset, [str(f.get("column") or "") for f in filters] + [str(c) for c in args.get("group_by") or []] + ([str(args.get("value_column"))] if args.get("value_column") else []))
        frame = self._frame(dataset, search_text=str(args.get("search_text") or ""))
        frame = self._apply_filters(frame, filters)
        metric = str(args.get("metric") or "count")
        value_column = str(args.get("value_column") or "")
        group_cols: list[str] = []
        for raw in args.get("group_by") or []:
            name = str(raw)
            if ":" in name:
                base, period = name.split(":", 1)
                if base not in frame.columns:
                    raise ValueError(f"Column '{base}' does not exist.")
                dates = pd.to_datetime(frame[base], errors="coerce", utc=True)
                fmt = "%Y" if period.strip().lower() == "year" else "%Y-%m"
                frame = frame.assign(**{name: dates.dt.strftime(fmt)})
            elif name not in frame.columns:
                raise ValueError(f"Column '{name}' does not exist. Columns: {', '.join(map(str, frame.columns))}")
            group_cols.append(name)
        if metric != "count":
            if value_column not in frame.columns:
                raise ValueError(f"value_column '{value_column}' is required for {metric} and must exist.")
            frame = frame.assign(**{value_column: pd.to_numeric(frame[value_column], errors="coerce")})
        result_col = "count" if metric == "count" else f"{metric}_{value_column}"
        if group_cols:
            grouped = frame.groupby([frame[c].astype(str) for c in group_cols], dropna=False)
            if metric == "count":
                result = grouped.size().reset_index(name=result_col)
            else:
                fn = {"sum": "sum", "avg": "mean", "min": "min", "max": "max"}[metric]
                result = grouped[value_column].agg(fn).reset_index(name=result_col)
            result = result.sort_values(result_col, ascending=False)
            top_n = args.get("top_n")
            if top_n:
                result = result.head(max(1, min(int(top_n), 200)))
        else:
            if metric == "count":
                value = int(len(frame))
            else:
                fn = {"sum": "sum", "avg": "mean", "min": "min", "max": "max"}[metric]
                value = getattr(frame[value_column], fn)()
            result = pd.DataFrame([{result_col: value}])
        result = result.reset_index(drop=True)
        args = dict(args)
        if args.get("chart") and not (args["chart"] or {}).get("y"):
            args["chart"] = {**args["chart"], "y": result_col}
        note = self._record_report(args, result, dataset, f"{self.datasets[dataset].get('record_type') or dataset} summary")
        return {"dataset": dataset, "rows_considered": int(len(frame)), "fetch_capped": len(frame) >= MAX_FETCH_ROWS, "result_column": result_col, "groups": _clean_frame_for_model(result, 200), "report": note}

    def run_tool(self, name: str, args: Mapping[str, Any]) -> dict[str, Any]:
        handler = {"describe_dataset": self.tool_describe_dataset, "query_records": self.tool_query_records, "aggregate_records": self.tool_aggregate_records}.get(name)
        if handler is None:
            return {"error": f"Unknown tool {name}. Only read-only query tools exist."}
        try:
            return handler(args or {})
        except Exception as exc:  # returned to the model so it can correct itself
            return {"error": str(exc)}

    # ------------------------------------------------------------------ model loop
    def system_prompt(self) -> str:
        catalog = "\n".join(
            f"- {table}: {src.get('record_type')} (module {src.get('module')}); key text columns: {', '.join(src.get('columns') or ())}"
            for table, src in sorted(self.datasets.items())
        )
        return (
            "You are the QCMS AI Assistant for Four Star Industries' Quality & Supply Chain Management System "
            "(precision forged/machined automotive parts). Answer questions, analyse data and build reports "
            "using ONLY the read-only tools. Never invent records, numbers or column names: if data is missing, say so.\n"
            f"Today is {self.today.isoformat()}. User: {self.user_label or 'QCMS user'}.\n"
            "Datasets this user is permitted to view (use these names exactly):\n"
            f"{catalog}\n\n"
            "Rules:\n"
            "1. Call describe_dataset before filtering a dataset whose columns you have not seen.\n"
            "2. Prefer aggregate_records for counts/totals/trends; query_records for lists.\n"
            "3. When the user asks for a list, register, report, export or chart, set show_as_report=true with a clear report_title (and chart when useful).\n"
            "4. Results are capped at 5000 fetched rows per call; mention it if fetch_capped is true.\n"
            "5. You cannot create, edit, approve or delete anything. If asked, explain the QCMS screen to use instead.\n"
            "6. Reply concisely in business English with key figures, short bullets and a one-line conclusion. Use part numbers, heat numbers and document numbers exactly as stored."
        )

    def _call_api(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._post is not None:
            return self._post(payload)
        import httpx
        spec = PROVIDERS[self.provider]
        if spec["style"] == "anthropic":
            headers = {"x-api-key": self.api_key, "anthropic-version": API_VERSION, "content-type": "application/json"}
        else:
            headers = {"Authorization": f"Bearer {self.api_key}", "content-type": "application/json"}
        response = httpx.post(spec["url"], headers=headers, json=payload, timeout=120.0)
        if response.status_code >= 400:
            try:
                body = response.json()
                body = body[0] if isinstance(body, list) and body else body
                detail = (body.get("error") or {}).get("message") if isinstance(body.get("error"), dict) else body.get("error")
            except Exception:
                detail = response.text[:300]
            hint = " (free-tier limit reached — wait a minute and try again)" if response.status_code == 429 else ""
            raise RuntimeError(f"{spec['label'].split(' ·')[0]} API error {response.status_code}: {detail}{hint}")
        return response.json()

    def _ask_openai(self, messages_in: list[dict[str, Any]], calls: list[dict[str, Any]]) -> str:
        """Tool loop for OpenAI-compatible providers (Gemini, Groq, OpenAI)."""
        messages: list[dict[str, Any]] = [{"role": "system", "content": self.system_prompt()}, *messages_in]
        tools = openai_tools(TOOLS)
        final_text = ""
        for _ in range(MAX_TOOL_ROUNDS):
            response = self._call_api({"model": self.model, "messages": messages, "tools": tools, "tool_choice": "auto"})
            choice = (response.get("choices") or [{}])[0]
            message = dict(choice.get("message") or {})
            text = str(message.get("content") or "")
            if text.strip():
                final_text = text
            tool_calls = list(message.get("tool_calls") or [])
            if not tool_calls:
                return final_text
            messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": tool_calls})
            for call in tool_calls:
                fn = call.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}") if isinstance(fn.get("arguments"), str) else dict(fn.get("arguments") or {})
                except Exception:
                    args = {}
                output = self.run_tool(str(fn.get("name") or ""), args)
                calls.append({"tool": fn.get("name"), "input": args, "error": output.get("error")})
                messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": json.dumps(output, default=_json_default, ensure_ascii=False)})
        return (final_text + "\n\n" if final_text else "") + "_Stopped after the maximum number of analysis steps; refine the question for a more specific answer._"

    def ask(self, prompt: str, history: Sequence[Mapping[str, str]] | None = None) -> AIAnswer:
        prompt = str(prompt or "").strip()
        if not prompt:
            return AIAnswer(text="", error="Enter a question or report request.")
        if not self.api_key:
            return AIAnswer(text="", error=f"AI Assistant is not configured. Add {PROVIDERS[self.provider]['key']} to Streamlit secrets (run scripts/set_ai_key.sh).")
        if not self.datasets:
            return AIAnswer(text="", error="You do not have View permission on any QCMS dataset.")
        self.reports = []
        messages: list[dict[str, Any]] = []
        for turn in list(history or [])[-4:]:
            if turn.get("prompt") and turn.get("answer"):
                messages.append({"role": "user", "content": str(turn["prompt"])})
                messages.append({"role": "assistant", "content": str(turn["answer"])})
        messages.append({"role": "user", "content": prompt})
        calls: list[dict[str, Any]] = []
        final_text = ""
        if PROVIDERS[self.provider]["style"] == "openai":
            try:
                final_text = self._ask_openai(messages, calls)
            except Exception as exc:
                return AIAnswer(text=final_text, reports=list(self.reports), tool_calls=calls, model=self.model, error=str(exc))
            return AIAnswer(text=final_text or "No answer was returned.", reports=list(self.reports), tool_calls=calls, model=self.model)
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                response = self._call_api({"model": self.model, "max_tokens": 4096, "system": self.system_prompt(), "tools": TOOLS, "messages": messages})
                content = list(response.get("content") or [])
                texts = [str(block.get("text") or "") for block in content if block.get("type") == "text"]
                tool_uses = [block for block in content if block.get("type") == "tool_use"]
                if texts:
                    final_text = "\n".join(t for t in texts if t.strip())
                if not tool_uses or response.get("stop_reason") != "tool_use":
                    break
                messages.append({"role": "assistant", "content": content})
                results = []
                for block in tool_uses:
                    args = dict(block.get("input") or {})
                    output = self.run_tool(str(block.get("name") or ""), args)
                    calls.append({"tool": block.get("name"), "input": args, "error": output.get("error")})
                    results.append({"type": "tool_result", "tool_use_id": block.get("id"), "content": json.dumps(output, default=_json_default, ensure_ascii=False), "is_error": bool(output.get("error"))})
                messages.append({"role": "user", "content": results})
            else:
                final_text = (final_text + "\n\n" if final_text else "") + "_Stopped after the maximum number of analysis steps; refine the question for a more specific answer._"
        except Exception as exc:
            return AIAnswer(text=final_text, reports=list(self.reports), tool_calls=calls, model=self.model, error=str(exc))
        return AIAnswer(text=final_text or "No answer was returned.", reports=list(self.reports), tool_calls=calls, model=self.model)


def report_excel_bytes(report: AIReport) -> bytes:
    from io import BytesIO
    buffer = BytesIO()
    frame = report.frame.copy()
    for column in frame.columns:
        if frame[column].map(lambda v: isinstance(v, (dict, list))).any():
            frame[column] = frame[column].map(lambda v: json.dumps(v, default=_json_default, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
        if isinstance(frame[column].dtype, pd.DatetimeTZDtype):
            frame[column] = frame[column].dt.tz_localize(None)
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        sheet = "".join(ch for ch in report.title if ch not in '[]:*?/\\')[:31] or "Report"
        frame.to_excel(writer, index=False, sheet_name=sheet)
    return buffer.getvalue()
