# KPI drill-down contract (R37) - web, Android, iOS

Every KPI card in QCMS can be clicked/tapped. It opens the list of records behind its number, and each row opens
its record. The web app and both mobile apps use the same contract. All RPCs are `SECURITY INVOKER`, so the
signed-in user's RLS (tenant isolation) applies.

## 1. Card JSON

Cards come from three RPCs:

* `qcms_kpi_dashboard(p_department)` returns `cards[]`.
* `qcms_module_cards(p_department)` returns `modules[]`. This is the older one-card-per-module strip.
* `qcms_module_kpis(p_department, p_modules)` returns `groups[].cards[]`. These are the module infographic cards.

All three card types carry the same keys:

```json
{
  "key": "mk_metlab_pending",            // stable card key (start-dashboard keys look like "metlab_pending")
  "label": "Pending",                    // module cards: label is the metric; the group has the title
  "value": 4, "unit": "reports", "tone": "warning",   // tone: good | warning | critical | serious | neutral
  "route": "metlab-records",             // web route of the module / register page
  "count": 4,                            // module KPIs only: rows matching the filter
  "drill": {
    "key": "mk_metlab_pending",
    "rpc": "qcms_kpi_drilldown",
    "args": {"p_card_key": "mk_metlab_pending"},
    "source": "lab_tests",               // table ("lab_tests+inspection_reports" for combined legacy cards)
    "filter": [ {"col": "results.inspection_method", "op": "neq", "value": "BEND_TEST"},
                {"col": "osp_job_id", "op": "blank"},
                {"col": "status", "op": "neq", "value": "FINAL"} ],
    "columns": ["source_table","record_id","reference","part","party","status","record_date","detail"],
    "title": "MetLAB · Pending",
    "open_route": "metlab-records",
    "measure": "count",                  // count | percent | sum
    "count_matches": true                // true: drill row count == card value
  }
}
```

On start-dashboard cards (keys without the `mk_` prefix), `drill.filter` is `{"card_key": "<key>", "server": "qcms_kpi_base"}`.
The server-side filter of R37 `qcms_kpi_base` applies to those cards. On `percent` and `sum` cards (for example "Open PO value",
"First-pass yield" or "RM on order kg"), the drill lists the records the number is calculated from, so `count_matches` is `false`.

`qcms_module_kpis` group JSON:
`{"key","title","department","icon","route","module_key","table","entry_route","metrics","ref","date","part","party",
"status","detail","spark":[6 monthly counts, oldest first],"cards":[...]}` (`entry_route` = web route of the "new" screen).
The departments are QUALITY, SUPPLY_CHAIN, PRODUCTION, NPD and MASTERS. Use `module_key` with `can_view` to hide modules the user cannot open.

## 2. Records behind a card

```
rpc qcms_kpi_drilldown(p_card_key text, p_limit int default 500)
 -> table(source_table text, record_id uuid, reference text, part text, party text, status text, record_date date, detail text)
```

This works for every key: module metric keys (`mk_*`) and start-dashboard / module-strip keys (it delegates to
`qcms_kpi_records`). Rows are newest first. Tap a row to open `source_table` + `record_id` natively. If no native
screen exists, open the web route from `open_route`. On a database older than R37 (function missing, PGRST202), call
`qcms_kpi_records(p_card_key, p_department, p_limit)`. If that is missing too, open `route`.

## 3. Filter language (`drill.filter`)

A list is AND. A condition is `{"col", "op", "value"}`, with these options:

* `op`: `eq`, `neq`, `in`, `not_in`, `lt`, `lte`, `gt`, `gte`, `blank`, `not_blank`, `true`, `not_true`.
* Groups: `{"any": [...]}` (OR), `{"not": {...}}`, and `{"not_exists": {"table", "fk", "where"}}` (also `exists`).
* `col` can be a list, which means coalesce, or `"results.inspection_method"`, which means jsonb `->>`.
* `value` can be `{"today": n}`, meaning the current date + n days, or `{"month_start": n}`, meaning the first day of the month + n months.

Text comparisons are null-safe: null is treated as `''`. Every condition is true or false, never null.
The SQL engine (`qcms_kpi_where`) and the Python engine (`core/module_kpis.matches`) apply the same rules.

## 4. Web deep links

`/kpi-drilldown?card=<key>&dept=<DEPARTMENT>`. The older `/kpi-details?card=...` link works the same way.
Clicking a row opens the record. The page also has filters, Excel/PDF export of the list, and a print-layout PDF for a selected row.
