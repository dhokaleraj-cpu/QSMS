package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/**
 * R39 (website R35 KPI Dashboards · "My Dashboards", core/dashboard_builder.py): personal KPI dashboards - several per user,
 * stored in public.qcms_user_dashboards (RLS: owner, or shared within the company). Widgets (KPI card, bar, line, area,
 * pie, table) are computed on the phone with the same maths as the website (period, filter, group / series, time bucket,
 * count / sum / avg / min / max, top N). Tap a widget for the records behind it. Owners can create dashboards (empty or
 * with the starter widgets), rename, share, make default, delete, and add / edit / move / duplicate / remove widgets.
 * Data sources need View permission on their module (core.access), like the website.
 */
final class GenDashScreen extends Screen {
    static final String TABLE = "qcms_user_dashboards";

    // ------------------------------------------------------------------ data sources (dashboard_builder.DATA_SOURCES)
    static final class Source {
        final String key, label, table, date, module;
        final LinkedHashMap<String, String> fields = new LinkedHashMap<>(), numbers = new LinkedHashMap<>();
        Source(String key, String label, String date, String module, String[] fields, String[] numbers) {
            this.key = key; this.label = label; this.table = key; this.date = date; this.module = module;
            for (int i = 0; i + 1 < fields.length; i += 2) this.fields.put(fields[i], fields[i + 1]);
            for (int i = 0; i + 1 < numbers.length; i += 2) this.numbers.put(numbers[i], numbers[i + 1]);
        }
    }

    private static String[] a(String... v) { return v; }

    static final LinkedHashMap<String, Source> SOURCES = new LinkedHashMap<>();
    static {
        List<Source> l = Arrays.asList(
            new Source("inward_lots", "Material Inward", "inward_date", "MATERIAL_INWARD",
                a("status", "Status", "quality_disposition", "Quality decision", "receipt_disposition", "Receipt decision", "supplier_id", "Supplier",
                  "part_id", "Part", "metallurgical_status", "MetLAB status", "dimensional_status", "Dimensional status", "heat_number", "Heat number"),
                a("steel_quantity_kg", "Steel kg", "production_quantity_pcs", "Production pcs", "accepted_production_quantity_pcs", "Accepted pcs",
                  "rejected_production_quantity_pcs", "Rejected pcs", "quantity_received", "Quantity received")),
            new Source("lab_tests", "MetLAB / Bend Test reports", "test_date", "METLAB_REPORT",
                a("status", "Status", "disposition", "Decision", "overall_result", "Result", "part_id", "Part", "supplier_id", "Supplier",
                  "customer_id", "Customer", "layout_type_name", "Layout type", "metlab_subcategory", "MetLAB sub-category"),
                a("steel_quantity_kg", "Steel kg", "production_quantity_pcs", "Production pcs")),
            new Source("inspection_reports", "Dimensional reports", "inspection_date", "DIMENSIONAL_REPORT",
                a("status", "Status", "disposition", "Decision", "overall_result", "Result", "part_id", "Part", "supplier_id", "Supplier",
                  "customer_id", "Customer", "inspection_scope", "Inspection scope", "inspector", "Inspector"),
                a("accepted_quantity", "Accepted qty", "rejected_quantity", "Rejected qty", "lot_quantity", "Lot qty", "sample_size", "Sample size")),
            new Source("rmtc_approvals", "RMTC", "certificate_date", "RMTC_ENTRY",
                a("status", "Status", "disposition", "Decision", "validation_result", "Validation result", "supplier_id", "Supplier",
                  "steel_mill_id", "Steel mill", "part_id", "Part", "rm_section", "RM section", "chemistry_compliance", "Chemistry"),
                a("certificate_quantity", "Certificate qty kg", "actual_di", "Actual DI", "grain_size", "Grain size")),
            new Source("quality_complaints", "Complaints", "complaint_date", "COMPLAINT_MANAGEMENT",
                a("status", "Status", "complaint_type", "Complaint type", "severity", "Severity", "party_id", "Customer / supplier",
                  "part_id", "Part", "defect_mode", "Defect mode", "debit_note_status", "Debit note status"),
                a("affected_quantity", "Affected qty", "debit_note_amount", "Debit note amount")),
            new Source("quality_assets", "Gauges / instruments", "next_due_date", "CALIBRATION_VALIDATION",
                a("status", "Status", "asset_type", "Asset type", "location", "Location", "service_type", "Service type", "manufacturer", "Manufacturer"),
                a("calibration_frequency_days", "Calibration frequency days")),
            new Source("supply_customer_orders", "Customer orders / schedules", "schedule_month", "SUPPLY_CHAIN",
                a("status", "Status", "customer_id", "Customer", "part_id", "Part", "order_type", "Order type", "supply_flow", "Supply flow",
                  "procurement_decision", "Procurement decision", "forging_supplier_id", "Forging supplier"),
                a("order_qty_pcs", "Order qty pcs", "required_rm_kg", "Required RM kg")),
            new Source("supply_purchase_orders", "Purchase orders", "order_date", "SUPPLY_CHAIN",
                a("status", "Status", "approval_status", "Approval", "supplier_id", "Supplier", "po_type", "PO type", "currency", "Currency"),
                a("grand_total", "Grand total", "subtotal", "Sub total")),
            new Source("supply_rm_purchase_orders", "RM orders", "order_date", "SUPPLY_CHAIN",
                a("status", "Status", "rm_supplier_id", "RM supplier"), a("ordered_qty_kg", "Ordered kg")),
            new Source("supply_rm_receipts", "RM receipts", "receipt_date", "SUPPLY_CHAIN",
                a("heat_number", "Heat number"), a("received_qty_kg", "Received kg")),
            new Source("supply_forging_orders", "Forging orders", "order_date", "SUPPLY_CHAIN",
                a("status", "Status", "forging_supplier_id", "Forging supplier"), a("order_qty_pcs", "Order pcs", "required_rm_kg", "Required RM kg")),
            new Source("supply_forging_receipts", "Forging receipts", "receipt_date", "SUPPLY_CHAIN",
                a("forging_supplier_id", "Forging supplier", "heat_number", "Heat number"),
                a("received_qty_pcs", "Received pcs", "rejected_qty_pcs", "Rejected pcs", "actual_rm_consumed_kg", "RM consumed kg")),
            new Source("supply_downstream_events", "Machining / FG / dispatch", "event_date", "SUPPLY_CHAIN",
                a("event_type", "Stage", "heat_number", "Heat number"), a("qty_pcs", "Quantity pcs", "rejected_qty_pcs", "Rejected pcs")),
            new Source("osp_jobs", "OSP jobs", "dispatch_date", "OSP_TRANSACTIONS",
                a("status", "Status", "vendor_id", "OSP vendor", "part_id", "Part", "sample_gate_status", "Sample gate", "receipt_quality_disposition", "Receipt decision"),
                a("quantity_dispatched", "Dispatched qty", "quantity_received", "Received qty", "quantity_rejected_at_receipt", "Rejected at receipt")),
            new Source("production_batches", "Production batches", "created_at", "OSP_TRANSACTIONS",
                a("status", "Status", "part_id", "Part", "heat_number", "Heat number"), a("quantity_available", "Available qty", "quantity_started", "Started qty")),
            new Source("npd_orders", "NPD orders", "order_date", "NPD_APQP",
                a("status", "Status", "customer_id", "Customer", "part_id", "Part"), a("order_qty", "Order qty")),
            new Source("ppap_projects", "APQP / PPAP projects", "target_submission_date", "NPD_APQP",
                a("status", "Status", "customer_id", "Customer", "submission_level", "Submission level", "coordinator", "Coordinator"),
                a("completion_percent", "Completion %")));
        for (Source s : l) SOURCES.put(s.key, s);
    }

    static final String[][] TYPES = {{"kpi", "KPI card"}, {"bar", "Bar chart"}, {"line", "Line chart"}, {"area", "Area chart"}, {"pie", "Pie / donut chart"}, {"table", "Table"}};
    static final String[][] AGGS = {{"count", "Count of records"}, {"sum", "Sum"}, {"avg", "Average"}, {"min", "Minimum"}, {"max", "Maximum"}};
    static final int[] PERIODS = {0, 7, 30, 90, 180, 365};
    static final String[] PERIOD_NAMES = {"All time", "Last 7 days", "Last 30 days", "Last 90 days", "Last 6 months", "Last 12 months"};
    static final String[][] BUCKETS = {{"", "No time grouping"}, {"day", "Per day"}, {"week", "Per week"}, {"month", "Per month"}};
    static final Map<String, String> FK_LABELS = new HashMap<>();
    static {
        FK_LABELS.put("part_id", "parts");
        for (String k : new String[]{"customer_id", "supplier_id", "party_id", "vendor_id", "forging_supplier_id", "rm_supplier_id", "steel_mill_id", "osp_vendor_id"}) FK_LABELS.put(k, "parties");
    }

    static String s(JSONObject o, String k) { return o == null || o.isNull(k) ? "" : o.optString(k, ""); }
    static String name(String[][] pairs, String key) { for (String[] p : pairs) if (p[0].equals(key)) return p[1]; return key; }
    static boolean has(String[][] pairs, String key) { for (String[] p : pairs) if (p[0].equals(key)) return true; return false; }

    // ------------------------------------------------------------------ widget maths (dashboard_builder.normalize_widget / compute)
    static JSONObject normalize(JSONObject in) {
        JSONObject w = new JSONObject();
        try {
            w.put("id", s(in, "id").isEmpty() ? UUID.randomUUID().toString().replace("-", "").substring(0, 10) : s(in, "id"));
            w.put("type", has(TYPES, s(in, "type")) ? s(in, "type") : "bar");
            w.put("source", SOURCES.containsKey(s(in, "source")) ? s(in, "source") : "lab_tests");
            w.put("agg", has(AGGS, s(in, "agg")) ? s(in, "agg") : "count");
            w.put("width", Math.min(4, Math.max(1, in == null ? 2 : in.optInt("width", 2))));
            String h = s(in, "height");
            w.put("height", "S".equals(h) || "L".equals(h) ? h : "M");
            w.put("period_days", in == null ? 0 : in.optInt("period_days", 0));
            w.put("top", Math.max(0, in == null ? 0 : in.optInt("top", 0)));
            w.put("time_bucket", has(BUCKETS, s(in, "time_bucket")) ? s(in, "time_bucket") : "");
            for (String k : new String[]{"title", "group_by", "series_by", "value_field", "filter_field", "filter_value"}) w.put(k, s(in, k));
        } catch (Exception ignored) { }
        return w;
    }

    static JSONObject widget(String type, String title, String source, String... kv) {
        JSONObject w = new JSONObject();
        try {
            w.put("type", type).put("title", title).put("source", source).put("group_by", "status").put("width", 2).put("height", "M");
            for (int i = 0; i + 1 < kv.length; i += 2) {
                String k = kv[i], v = kv[i + 1];
                if (k.equals("period_days") || k.equals("top") || k.equals("width")) w.put(k, Integer.parseInt(v)); else w.put(k, v);
            }
        } catch (Exception ignored) { }
        return normalize(w);
    }

    /** dashboard_builder.starter_widgets */
    static JSONArray starter() {
        JSONArray out = new JSONArray();
        out.put(widget("kpi", "MetLAB / Bend reports (30 days)", "lab_tests", "period_days", "30", "width", "1", "height", "S"));
        out.put(widget("kpi", "Dimensional reports (30 days)", "inspection_reports", "period_days", "30", "width", "1", "height", "S"));
        out.put(widget("kpi", "Open complaints", "quality_complaints", "filter_field", "status", "filter_value", "OPEN", "width", "1", "height", "S"));
        out.put(widget("kpi", "Open PO value", "supply_purchase_orders", "agg", "sum", "value_field", "grand_total", "filter_field", "status", "filter_value", "OPEN", "width", "1", "height", "S"));
        out.put(widget("bar", "Reports per month by decision", "lab_tests", "time_bucket", "month", "series_by", "disposition", "period_days", "180"));
        out.put(widget("pie", "Complaints by customer / supplier", "quality_complaints", "group_by", "party_id", "top", "8"));
        out.put(widget("line", "RM received kg per month", "supply_rm_receipts", "agg", "sum", "value_field", "received_qty_kg", "time_bucket", "month", "period_days", "365"));
        out.put(widget("table", "Open orders by customer", "supply_customer_orders", "group_by", "customer_id", "agg", "sum", "value_field", "order_qty_pcs", "filter_field", "status", "filter_value", "OPEN"));
        return out;
    }

    static String label(Object value, String field, Map<String, Map<String, String>> labels) {
        String text = value == null || value == JSONObject.NULL ? "" : String.valueOf(value).trim();
        if (text.isEmpty()) return "Not set";
        String table = FK_LABELS.get(field);
        if (table != null) {
            Map<String, String> m = labels.get(table);
            String hit = m == null ? null : m.get(text);
            return hit != null && !hit.isEmpty() ? hit : text.substring(0, Math.min(8, text.length()));
        }
        return text.equals(text.toUpperCase(Locale.ROOT)) && !text.equals(text.toLowerCase(Locale.ROOT)) ? GenUtil.title(text.replace('_', ' ').toLowerCase(Locale.ROOT)) : text;
    }

    static String bucket(Object value, String b) {
        LocalDate d = GenUtil.d(value);
        if (d == null) return "No date";
        if ("month".equals(b)) return d.toString().substring(0, 7);
        if ("week".equals(b)) return d.minusDays(d.getDayOfWeek().getValue() - 1).toString();
        return d.toString();
    }

    static List<JSONObject> filterRows(List<JSONObject> rows, JSONObject w, Map<String, Map<String, String>> labels) {
        Source src = SOURCES.get(s(w, "source"));
        List<JSONObject> out = new ArrayList<>();
        int days = w.optInt("period_days", 0);
        LocalDate start = days > 0 ? LocalDate.now().minusDays(days) : null;
        String field = s(w, "filter_field"), wanted = s(w, "filter_value").trim().toLowerCase(Locale.ROOT);
        for (JSONObject r : rows) {
            if (start != null) {
                LocalDate d = GenUtil.d(r.opt(src.date));
                if (d == null) d = GenUtil.d(r.opt("created_at"));
                if (d == null || d.isBefore(start)) continue;
            }
            if (!field.isEmpty() && !wanted.isEmpty()) {
                String hay = (s(r, field) + " " + label(r.opt(field), field, labels)).toLowerCase(Locale.ROOT);
                if (!hay.contains(wanted)) continue;
            }
            out.add(r);
        }
        return out;
    }

    static double aggregate(String agg, List<Object> values) {
        if ("count".equals(agg)) return values.size();
        List<Double> nums = new ArrayList<>();
        for (Object v : values) {
            if (v == null || v == JSONObject.NULL) continue;
            try { nums.add(Double.parseDouble(String.valueOf(v))); } catch (Exception ignored) { }
        }
        if (nums.isEmpty()) return 0;
        double r = "min".equals(agg) ? Double.MAX_VALUE : "max".equals(agg) ? -Double.MAX_VALUE : 0;
        for (double n : nums) {
            if ("min".equals(agg)) r = Math.min(r, n); else if ("max".equals(agg)) r = Math.max(r, n); else r += n;
        }
        return "avg".equals(agg) ? r / nums.size() : r;
    }

    /** Computed widget: total + rows {group, series, value} in display order. */
    static final class Result {
        double total;
        final List<String[]> rows = new ArrayList<>();   // group, series, value
        boolean series;
    }

    static Result compute(List<JSONObject> rows, JSONObject w, Map<String, Map<String, String>> labels) {
        Result res = new Result();
        List<JSONObject> data = filterRows(rows, w, labels);
        String agg = s(w, "agg"), vf = s(w, "value_field");
        List<Object> all = new ArrayList<>();
        for (JSONObject r : data) all.add(vf.isEmpty() ? (Object) 1 : r.opt(vf));
        res.total = GenUtil.round(aggregate(agg, all), 2);
        if ("kpi".equals(s(w, "type"))) { res.rows.add(new String[]{"Total", "", GenUtil.cell(res.total)}); return res; }
        String gf = s(w, "group_by"), sf = s(w, "series_by"), b = s(w, "time_bucket");
        String dateField = SOURCES.get(s(w, "source")).date;
        LinkedHashMap<String, List<Object>> groups = new LinkedHashMap<>();
        for (JSONObject r : data) {
            String g;
            if (!b.isEmpty()) { Object dv = r.opt(dateField); g = bucket(dv == null || dv == JSONObject.NULL ? r.opt("created_at") : dv, b); }
            else g = gf.isEmpty() ? "Total" : label(r.opt(gf), gf, labels);
            String se = sf.isEmpty() ? "" : label(r.opt(sf), sf, labels);
            groups.computeIfAbsent(g + "\u0000" + se, k -> new ArrayList<>()).add(vf.isEmpty() ? (Object) 1 : r.opt(vf));
        }
        List<String[]> recs = new ArrayList<>();
        for (Map.Entry<String, List<Object>> e : groups.entrySet()) {
            String[] k = e.getKey().split("\u0000", -1);
            recs.add(new String[]{k[0], k.length > 1 ? k[1] : "", String.valueOf(GenUtil.round(aggregate(agg, e.getValue()), 2))});
        }
        if (!b.isEmpty()) {
            recs.sort((x, y) -> x[0].equals(y[0]) ? x[1].compareTo(y[1]) : x[0].compareTo(y[0]));
        } else {
            LinkedHashMap<String, Double> sums = new LinkedHashMap<>();
            for (String[] r : recs) sums.merge(r[0], Double.parseDouble(r[2]), Double::sum);
            List<String> order = new ArrayList<>(sums.keySet());
            order.sort((x, y) -> Double.compare(sums.get(y), sums.get(x)));
            int top = w.optInt("top", 0);
            if (top > 0 && order.size() > top) order = order.subList(0, top);
            final List<String> ord = order;
            List<String[]> kept = new ArrayList<>();
            for (String[] r : recs) if (ord.contains(r[0])) kept.add(r);
            kept.sort((x, y) -> ord.indexOf(x[0]) != ord.indexOf(y[0]) ? ord.indexOf(x[0]) - ord.indexOf(y[0]) : x[1].compareTo(y[1]));
            recs = kept;
        }
        res.rows.addAll(recs);
        res.series = !sf.isEmpty();
        return res;
    }

    static GenKpi.Chart chart(JSONObject w, Result r) {
        String type = s(w, "type");
        String kind = "pie".equals(type) ? "pie" : ("line".equals(type) || "area".equals(type)) ? "line" : r.series ? "stacked" : "bar";
        GenKpi.Chart c = new GenKpi.Chart(s(w, "title"), kind, "");
        List<String> series = new ArrayList<>();
        for (String[] row : r.rows) {
            if (!c.cats.contains(row[0])) c.cats.add(row[0]);
            if (!series.contains(row[1])) series.add(row[1]);
        }
        for (String se : series) c.series.put(se, new double[c.cats.size()]);
        for (String[] row : r.rows) c.series.get(row[1])[c.cats.indexOf(row[0])] += Double.parseDouble(row[2]);
        return c;
    }

    // ================================================================== screen
    private JSONArray boards;
    private static String selectedId = "";
    private final Map<String, List<JSONObject>> data = new HashMap<>();
    private final Map<String, Map<String, String>> labels = new HashMap<>();
    private final java.util.Set<String> denied = new java.util.HashSet<>();

    GenDashScreen(MainActivity a) { super(a); }

    @Override public String title() { return "My Dashboards"; }
    @Override public String subtitle() { return "Your own KPI cards, charts and tables · tap a widget for its records"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONArray rows = api.rows(TABLE + "?select=*&order=sort_order.asc,name.asc&limit=200");
            List<JSONObject> mine = new ArrayList<>(), shared = new ArrayList<>();
            for (JSONObject r : GenUtil.list(rows)) {
                if (api.userId.equals(s(r, "owner_profile_id"))) mine.add(r);
                else if (r.optBoolean("shared_with_tenant", false)) shared.add(r);
            }
            mine.sort((x, y) -> x.optBoolean("is_default") != y.optBoolean("is_default") ? (x.optBoolean("is_default") ? -1 : 1)
                : x.optInt("sort_order", 0) != y.optInt("sort_order", 0) ? x.optInt("sort_order", 0) - y.optInt("sort_order", 0) : s(x, "name").compareTo(s(y, "name")));
            JSONArray out = new JSONArray();
            for (JSONObject r : mine) out.put(r);
            for (JSONObject r : shared) out.put(r);
            return out;
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            boards = res;
            render();
        });
        return scroll;
    }

    private JSONObject current() {
        if (boards == null || boards.length() == 0) return null;
        for (int i = 0; i < boards.length(); i++) if (s(boards.optJSONObject(i), "id").equals(selectedId)) return boards.optJSONObject(i);
        selectedId = s(boards.optJSONObject(0), "id");
        return boards.optJSONObject(0);
    }

    private boolean owner(JSONObject b) { return b != null && api.userId.equals(s(b, "owner_profile_id")); }

    private static List<JSONObject> widgets(JSONObject board) {
        List<JSONObject> out = new ArrayList<>();
        JSONObject layout = board == null ? null : board.optJSONObject("layout");
        JSONArray ws = layout == null ? null : layout.optJSONArray("widgets");
        for (int i = 0; ws != null && i < ws.length(); i++) if (ws.optJSONObject(i) != null) out.add(normalize(ws.optJSONObject(i)));
        return out;
    }

    private void render() {
        page.removeAllViews();
        LinearLayout bar = Ui.hbox(a);
        Button create = Ui.outline(a, "＋ New dashboard", Ui.TEAL);
        create.setOnClickListener(v -> newDashboard());
        bar.addView(create, Ui.weight(1));
        add(bar, 0);
        JSONObject board = current();
        if (board == null) {
            add(Ui.empty(a, "No dashboards yet. Create your first dashboard - start with the ready-made widgets or an empty one."), 10);
            return;
        }
        List<String> names = new ArrayList<>();
        int sel = 0;
        for (int i = 0; i < boards.length(); i++) {
            JSONObject b = boards.optJSONObject(i);
            names.add(s(b, "name") + (b.optBoolean("is_default") && owner(b) ? " ★" : "") + (owner(b) ? "" : " · shared"));
            if (s(b, "id").equals(selectedId)) sel = i;
        }
        add(GenUtil.chips(a, names, sel, i -> { selectedId = s(boards.optJSONObject(i), "id"); render(); }), 8);
        boolean mine = owner(board);
        LinearLayout tools = Ui.hbox(a);
        if (mine) {
            Button addW = Ui.outline(a, "＋ Add widget", Ui.TEAL_DARK);
            addW.setOnClickListener(v -> a.push(new WidgetScreen(a, this, board, null)));
            LinearLayout.LayoutParams lp = Ui.weight(1);
            lp.rightMargin = dp(6);
            tools.addView(addW, lp);
            Button more = Ui.outline(a, "Dashboard ⋯", Ui.TEAL_DARK);
            more.setOnClickListener(v -> boardMenu(board));
            tools.addView(more, Ui.weight(1));
            add(tools, 6);
        } else {
            add(Ui.text(a, "Shared by a colleague · view only", 11.5f, Ui.MUTED, false), 6);
        }
        String desc = s(board, "description");
        if (!desc.isEmpty()) add(Ui.text(a, desc, 12, Ui.MUTED, false), 4);
        List<JSONObject> ws = widgets(board);
        if (ws.isEmpty()) { add(Ui.empty(a, "This dashboard has no widgets yet." + (mine ? " Tap ＋ Add widget." : "")), 10); return; }
        LinearLayout holder = Ui.vbox(a);
        add(holder, 10);
        holder.addView(loading());
        Api.async(() -> { loadData(ws); return Boolean.TRUE; }, (ok, err) -> {
            holder.removeAllViews();
            if (err != null) { holder.addView(error(err, this::reload)); return; }
            List<View> kpis = new ArrayList<>();
            for (int i = 0; i < ws.size(); i++) {
                JSONObject w = ws.get(i);
                if ("kpi".equals(s(w, "type"))) { kpis.add(kpiTile(board, w, i)); continue; }
                if (!kpis.isEmpty()) { GenUtil.grid2(a, holder, new ArrayList<>(kpis), 8); kpis.clear(); }
                holder.addView(widgetCard(board, w, i), Ui.matchWrap(a, 10));
            }
            if (!kpis.isEmpty()) GenUtil.grid2(a, holder, kpis, 8);
        });
    }

    /** Rows of every source used (View permission checked per module), part / party labels. Background thread. */
    private void loadData(List<JSONObject> ws) throws Exception {
        for (JSONObject w : ws) {
            Source src = SOURCES.get(s(w, "source"));
            if (src == null || data.containsKey(src.key) || denied.contains(src.key)) continue;
            if (!GenUtil.canView(api, src.module)) { denied.add(src.key); continue; }
            try { data.put(src.key, GenUtil.big(api, src.table + "?select=*&limit=5000")); }
            catch (Exception e) { data.put(src.key, new ArrayList<>()); }
        }
        if (!labels.containsKey("parts")) {
            Map<String, String> parts = new HashMap<>(), parties = new HashMap<>();
            try { for (JSONObject p : GenUtil.big(api, "parts?select=id,part_number,part_name&limit=5000")) parts.put(s(p, "id"), s(p, "part_number").isEmpty() ? s(p, "part_name") : s(p, "part_number")); } catch (Exception ignored) { }
            try { for (JSONObject p : GenUtil.big(api, "parties?select=id,party_name,party_code&limit=5000")) parties.put(s(p, "id"), s(p, "party_name").isEmpty() ? s(p, "party_code") : s(p, "party_name")); } catch (Exception ignored) { }
            labels.put("parts", parts);
            labels.put("parties", parties);
        }
    }

    private List<JSONObject> rowsOf(JSONObject w) {
        List<JSONObject> r = data.get(s(w, "source"));
        return r == null ? new ArrayList<>() : r;
    }

    private View kpiTile(JSONObject board, JSONObject w, int index) {
        String src = s(w, "source");
        if (denied.contains(src)) return GenUtil.tile(a, "", s(w, "title"), "—", "No View permission on " + SOURCES.get(src).label, "neutral");
        Result r = compute(rowsOf(w), w, labels);
        String foot = SOURCES.get(src).label + (w.optInt("period_days", 0) > 0 ? " · " + periodName(w.optInt("period_days", 0)) : "");
        View tile = GenUtil.tile(a, "", s(w, "title"), GenChart.fmt(r.total), foot, "neutral");
        tile.setOnClickListener(v -> drill(w));
        tile.setOnLongClickListener(v -> { widgetMenu(board, index); return true; });
        return tile;
    }

    private View widgetCard(JSONObject board, JSONObject w, int index) {
        LinearLayout card = Ui.card(a);
        LinearLayout head = Ui.hbox(a);
        head.setGravity(Gravity.CENTER_VERTICAL);
        head.addView(Ui.text(a, s(w, "title"), 13.5f, Ui.TEXT, true), Ui.weight(1));
        if (owner(board)) {
            TextView menu = Ui.text(a, "⋯", 20, Ui.TEAL_DARK, true);
            menu.setPadding(dp(10), 0, dp(4), 0);
            menu.setOnClickListener(v -> widgetMenu(board, index));
            head.addView(menu);
        }
        card.addView(head);
        String src = s(w, "source");
        card.addView(Ui.text(a, SOURCES.get(src).label + " · " + name(AGGS, s(w, "agg")) + (s(w, "value_field").isEmpty() ? "" : " of " + SOURCES.get(src).numbers.getOrDefault(s(w, "value_field"), s(w, "value_field")))
            + (w.optInt("period_days", 0) > 0 ? " · " + periodName(w.optInt("period_days", 0)) : ""), 11, Ui.MUTED, false));
        if (denied.contains(src)) { card.addView(Ui.text(a, "You do not have View permission on this data.", 12, Ui.AMBER_FG, false), Ui.matchWrap(a, 6)); return card; }
        Result r = compute(rowsOf(w), w, labels);
        if (r.rows.isEmpty()) {
            card.addView(Ui.text(a, "No data", 12, Ui.MUTED, false), Ui.matchWrap(a, 6));
        } else if ("table".equals(s(w, "type"))) {
            List<String> cols = r.series ? GenUtil.listOf("Group", "Series", "Value") : GenUtil.listOf("Group", "Value");
            List<List<String>> rows = new ArrayList<>();
            for (String[] row : r.rows) rows.add(r.series ? GenUtil.listOf(row[0], row[1], GenChart.fmt(Double.parseDouble(row[2]))) : GenUtil.listOf(row[0], GenChart.fmt(Double.parseDouble(row[2]))));
            int h = "S".equals(s(w, "height")) ? 200 : "L".equals(s(w, "height")) ? 420 : 300;
            card.addView(new DataGrid(a, s(w, "title"), cols, rows, h, null), Ui.matchWrap(a, 6));
        } else {
            card.addView(new GenChart(a, chart(w, r)), Ui.matchWrap(a, 8));
        }
        TextView open = Ui.text(a, "View records ›", 12, Ui.TEAL_DARK, true);
        open.setPadding(0, dp(6), 0, 0);
        open.setOnClickListener(v -> drill(w));
        card.addView(open);
        return card;
    }

    static String periodName(int days) {
        for (int i = 0; i < PERIODS.length; i++) if (PERIODS[i] == days) return PERIOD_NAMES[i];
        return "Last " + days + " days";
    }

    /** Records behind a widget (dashboard_builder.drill_rows): same period + filter, KPI Details row shape. */
    private void drill(JSONObject w) {
        Source src = SOURCES.get(s(w, "source"));
        JSONArray out = new JSONArray();
        try {
            for (JSONObject r : filterRows(rowsOf(w), w, labels)) {
                JSONObject d = KpiDetails.drillRow(src.table, r);
                Map<String, String> parts = labels.get("parts");
                if (parts != null && s(d, "part").isEmpty() && parts.containsKey(s(r, "part_id"))) d.put("part", parts.get(s(r, "part_id")));
                out.put(d);
            }
        } catch (Exception e) { a.toast(Api.message(e)); return; }
        KpiDetails.KpiRecordsScreen screen = new KpiDetails.KpiRecordsScreen(a, "", "", s(w, "title"), "");
        screen.preset = out;
        a.push(screen);
    }

    // ------------------------------------------------------------------ dashboard actions
    private void newDashboard() {
        LinearLayout box = Ui.vbox(a);
        box.setPadding(dp(16), dp(8), dp(16), 0);
        EditText name = Ui.input(a, "Dashboard name", false);
        name.setText("My dashboard");
        box.addView(name);
        android.widget.CheckBox starter = new android.widget.CheckBox(a);
        starter.setText("Start with the ready-made widgets");
        starter.setChecked(true);
        box.addView(starter, Ui.matchWrap(a, 8));
        new AlertDialog.Builder(a).setTitle("New dashboard").setView(box)
            .setPositiveButton("Create", (d, w) -> {
                String n = name.getText().toString().trim();
                boolean st = starter.isChecked();
                Api.async(() -> {
                    JSONObject values = new JSONObject().put("owner_profile_id", api.userId).put("name", (n.isEmpty() ? "My dashboard" : n).substring(0, Math.min(80, n.isEmpty() ? 12 : n.length())))
                        .put("layout", new JSONObject().put("widgets", st ? starter() : new JSONArray()))
                        .put("sort_order", boards == null ? 0 : boards.length()).put("is_default", false).put("shared_with_tenant", false);
                    return api.insert(TABLE, values);
                }, (row, err) -> {
                    if (err != null) { a.toast("Could not create: " + Api.message(err)); return; }
                    selectedId = s(row, "id");
                    reload();
                });
            })
            .setNegativeButton("Cancel", null).show();
    }

    private void boardMenu(JSONObject board) {
        boolean shared = board.optBoolean("shared_with_tenant", false);
        String[] items = {"Rename / description", shared ? "Stop sharing with the company" : "Share with my company (view only)",
            board.optBoolean("is_default", false) ? "Default dashboard ✓" : "Make my default dashboard", "Delete dashboard"};
        new AlertDialog.Builder(a).setTitle(s(board, "name")).setItems(items, (d, which) -> {
            switch (which) {
                case 0: rename(board); break;
                case 1: patch(board, "shared_with_tenant", !shared); break;
                case 2: makeDefault(board); break;
                default:
                    a.confirm("Delete dashboard?", "\"" + s(board, "name") + "\" and its widgets are removed. Shared copies disappear for colleagues too.", "Delete",
                        () -> Api.async(() -> { api.delete(TABLE, s(board, "id")); return Boolean.TRUE; }, (ok, err) -> {
                            if (err != null) { a.toast(Api.message(err)); return; }
                            selectedId = "";
                            reload();
                        }));
            }
        }).setNegativeButton("Close", null).show();
    }

    private void rename(JSONObject board) {
        LinearLayout box = Ui.vbox(a);
        box.setPadding(dp(16), dp(8), dp(16), 0);
        EditText name = Ui.input(a, "Name", false);
        name.setText(s(board, "name"));
        EditText desc = Ui.input(a, "Description (optional)", false);
        desc.setText(s(board, "description"));
        box.addView(name);
        box.addView(desc, Ui.matchWrap(a, 8));
        new AlertDialog.Builder(a).setTitle("Rename dashboard").setView(box)
            .setPositiveButton("Save", (d, w) -> {
                String n = name.getText().toString().trim();
                if (n.isEmpty()) { a.toast("Enter a name."); return; }
                save(board, values -> values.put("name", n.length() > 80 ? n.substring(0, 80) : n).put("description", desc.getText().toString().trim()));
            }).setNegativeButton("Cancel", null).show();
    }

    private void makeDefault(JSONObject board) {
        Api.async(() -> {
            for (int i = 0; i < boards.length(); i++) {
                JSONObject other = boards.optJSONObject(i);
                if (other != board && owner(other) && other.optBoolean("is_default", false))
                    api.update(TABLE, s(other, "id"), new JSONObject().put("is_default", false).put("updated_at", java.time.OffsetDateTime.now().toString()));
            }
            api.update(TABLE, s(board, "id"), new JSONObject().put("is_default", true).put("updated_at", java.time.OffsetDateTime.now().toString()));
            return Boolean.TRUE;
        }, (ok, err) -> { if (err != null) a.toast(Api.message(err)); else reload(); });
    }

    private void patch(JSONObject board, String field, Object value) { save(board, values -> values.put(field, value)); }

    interface Change { void apply(JSONObject values) throws Exception; }

    private void save(JSONObject board, Change change) {
        Api.async(() -> {
            JSONObject values = new JSONObject();
            change.apply(values);
            values.put("updated_at", java.time.OffsetDateTime.now().toString());
            return api.update(TABLE, s(board, "id"), values);
        }, (row, err) -> {
            if (err != null) { a.toast("Could not save: " + Api.message(err)); return; }
            reload();
        });
    }

    void saveWidgets(JSONObject board, List<JSONObject> ws) {
        JSONArray arr = new JSONArray();
        for (JSONObject w : ws) arr.put(normalize(w));
        save(board, values -> values.put("layout", new JSONObject().put("widgets", arr)));
    }

    private void widgetMenu(JSONObject board, int index) {
        if (!owner(board)) return;
        List<JSONObject> ws = widgets(board);
        if (index < 0 || index >= ws.size()) return;
        String[] items = {"Edit widget", "Move up", "Move down", "Duplicate", "Remove widget"};
        new AlertDialog.Builder(a).setTitle(s(ws.get(index), "title")).setItems(items, (d, which) -> {
            switch (which) {
                case 0: a.push(new WidgetScreen(a, this, board, ws.get(index))); return;
                case 1: if (index > 0) { ws.add(index - 1, ws.remove(index)); saveWidgets(board, ws); } return;
                case 2: if (index < ws.size() - 1) { ws.add(index + 1, ws.remove(index)); saveWidgets(board, ws); } return;
                case 3: {
                    JSONObject copy = normalize(ws.get(index));
                    try { copy.put("id", UUID.randomUUID().toString().replace("-", "").substring(0, 10)).put("title", s(copy, "title") + " (copy)"); } catch (Exception ignored) { }
                    ws.add(index + 1, copy);
                    saveWidgets(board, ws);
                    return;
                }
                default:
                    a.confirm("Remove widget?", s(ws.get(index), "title"), "Remove", () -> { ws.remove(index); saveWidgets(board, ws); });
            }
        }).setNegativeButton("Close", null).show();
    }

    @Override public void reload() { data.clear(); denied.clear(); a.rebuild(); }

    // ================================================================== widget editor
    static final class WidgetScreen extends Screen {
        private final GenDashScreen parent;
        private final JSONObject board;
        private final JSONObject w;
        private final boolean isNew;
        private EditText titleIn, filterIn;

        WidgetScreen(MainActivity a, GenDashScreen parent, JSONObject board, JSONObject widget) {
            super(a);
            this.parent = parent;
            this.board = board;
            this.isNew = widget == null;
            this.w = widget == null ? widget("bar", "New widget", "lab_tests") : normalize(widget);
        }

        @Override public String title() { return isNew ? "Add widget" : "Edit widget"; }
        @Override public String subtitle() { return s(board, "name"); }
        @Override public int tab() { return Catalog.MORE; }

        private void put(String k, Object v) { try { w.put(k, v); } catch (Exception ignored) { } }

        @Override
        public View build() {
            newPage();
            Source src = SOURCES.get(s(w, "source"));
            add(Ui.label(a, "Title"), 0);
            titleIn = Ui.input(a, "Widget title", false);
            titleIn.setText(s(w, "title"));
            add(titleIn, 2);
            selector("Type", name(TYPES, s(w, "type")), pairsNames(TYPES), i -> put("type", TYPES[i][0]));
            List<String> srcNames = new ArrayList<>();
            List<String> srcKeys = new ArrayList<>(SOURCES.keySet());
            for (String k : srcKeys) srcNames.add(SOURCES.get(k).label);
            selector("Data", src.label, srcNames, i -> {
                put("source", srcKeys.get(i));
                Source ns = SOURCES.get(srcKeys.get(i));
                if (!ns.fields.containsKey(s(w, "group_by"))) put("group_by", "");
                if (!ns.fields.containsKey(s(w, "series_by"))) put("series_by", "");
                if (!ns.numbers.containsKey(s(w, "value_field"))) put("value_field", "");
                if (!ns.fields.containsKey(s(w, "filter_field"))) put("filter_field", "");
            });
            if (!"kpi".equals(s(w, "type"))) {
                fieldSelector("Group by", "group_by", src.fields, "(none)");
                fieldSelector("Colour / series by", "series_by", src.fields, "(none)");
                selector("Time grouping", name(BUCKETS, s(w, "time_bucket")), pairsNames(BUCKETS), i -> put("time_bucket", BUCKETS[i][0]));
            }
            selector("Measure", name(AGGS, s(w, "agg")), pairsNames(AGGS), i -> put("agg", AGGS[i][0]));
            if (!"count".equals(s(w, "agg"))) fieldSelector("Value field", "value_field", src.numbers, "(choose a number)");
            selector("Period", periodName(w.optInt("period_days", 0)), Arrays.asList(PERIOD_NAMES), i -> put("period_days", PERIODS[i]));
            fieldSelector("Filter field", "filter_field", src.fields, "(no filter)");
            add(Ui.label(a, "Filter value (contains)"), 10);
            filterIn = Ui.input(a, "e.g. OPEN, a supplier or part", false);
            filterIn.setText(s(w, "filter_value"));
            add(filterIn, 2);
            if (!"kpi".equals(s(w, "type"))) {
                List<String> tops = GenUtil.listOf("All groups", "Top 5", "Top 10", "Top 20");
                int[] topVals = {0, 5, 10, 20};
                int t = w.optInt("top", 0);
                selector("Show", t == 0 ? "All groups" : "Top " + t, tops, i -> put("top", topVals[i]));
                selector("Height", "S".equals(s(w, "height")) ? "Small" : "L".equals(s(w, "height")) ? "Large" : "Medium",
                    GenUtil.listOf("Small", "Medium", "Large"), i -> put("height", new String[]{"S", "M", "L"}[i]));
            }
            Button save = Ui.primary(a, isNew ? "Add to dashboard" : "Save widget");
            save.setOnClickListener(v -> {
                put("title", titleIn.getText().toString().trim().isEmpty() ? "Widget" : titleIn.getText().toString().trim());
                put("filter_value", filterIn.getText().toString().trim());
                if (!"count".equals(s(w, "agg")) && s(w, "value_field").isEmpty()) { a.toast("Choose the value field for " + name(AGGS, s(w, "agg")) + "."); return; }
                List<JSONObject> ws = widgets(board);
                if (isNew) ws.add(w);
                else for (int i = 0; i < ws.size(); i++) if (s(ws.get(i), "id").equals(s(w, "id"))) ws.set(i, w);
                a.back();
                parent.saveWidgets(board, ws);
            });
            add(save, 16);
            return scroll;
        }

        private static List<String> pairsNames(String[][] pairs) {
            List<String> out = new ArrayList<>();
            for (String[] p : pairs) out.add(p[1]);
            return out;
        }

        private void keepText() {
            if (titleIn != null) put("title", titleIn.getText().toString());
            if (filterIn != null) put("filter_value", filterIn.getText().toString());
        }

        private void selector(String label, String value, List<String> names, GenUtil.Picked picked) {
            add(Ui.label(a, label), 10);
            TextView t = GenUtil.selector(a, value);
            t.setOnClickListener(v -> GenUtil.pick(a, label, names, i -> { keepText(); picked.picked(i); a.rebuild(); }));
            add(t, 2);
        }

        private void fieldSelector(String label, String key, LinkedHashMap<String, String> options, String none) {
            List<String> keys = new ArrayList<>(options.keySet());
            List<String> names = new ArrayList<>();
            names.add(none);
            for (String k : keys) names.add(options.get(k));
            String cur = s(w, key);
            selector(label, cur.isEmpty() ? none : options.getOrDefault(cur, cur), names, i -> put(key, i == 0 ? "" : keys.get(i - 1)));
        }
    }
}
