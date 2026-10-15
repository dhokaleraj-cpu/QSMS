package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

/**
 * Exact port of core/kpi_service.py (QCMS R13 top-10 KPI dashboards): same tables, same
 * period filters, same formulas, tiles, charts and tables. Pure calculation, no UI.
 */
final class GenKpi {
    private GenKpi() { }

    static final Set<String> CLOSED_WORDS = new HashSet<>(Arrays.asList("CLOSED", "COMPLETED", "CANCELLED", "REJECTED", "SUPERSEDED", "INACTIVE"));
    static final Set<String> PASS_WORDS = new HashSet<>(Arrays.asList("PASS", "PASSED", "ACCEPTED", "APPROVED", "OK", "CONFORMING", "RELEASED", "ACCEPTED_UNDER_RESERVE"));
    static final Set<String> FAIL_WORDS = new HashSet<>(Arrays.asList("FAIL", "FAILED", "REJECTED", "NOT_OK", "NONCONFORMING", "NON_CONFORMING"));

    /** Periods of app_pages/kpi_dashboards.py (days; -1 = this year; 0 = all time). */
    static final String[] PERIODS = {"Last 30 days", "Last 90 days", "Last 6 months", "Last 12 months", "This year", "All time"};
    static final int[] PERIOD_DAYS = {30, 90, 182, 365, -1, 0};
    static final int DEFAULT_PERIOD = 1;
    static final Map<String, String> STATUS_WORD = new HashMap<>();
    static {
        STATUS_WORD.put("good", "On target"); STATUS_WORD.put("warning", "Watch"); STATUS_WORD.put("serious", "Attention");
        STATUS_WORD.put("critical", "Action needed"); STATUS_WORD.put("neutral", "");
    }

    static final class Tile {
        final String label, value, foot, status;
        Tile(String label, String value, String foot, String status) { this.label = label; this.value = value; this.foot = foot; this.status = status; }
    }

    static final class Chart {
        final String title, kind, note;
        final List<String> cats = new ArrayList<>();
        final LinkedHashMap<String, double[]> series = new LinkedHashMap<>();
        final List<String> dataHeaders = new ArrayList<>();
        final List<String[]> dataRows = new ArrayList<>();
        Chart(String title, String kind, String note) { this.title = title; this.kind = kind; this.note = note == null ? "" : note; }
        boolean multi() { return series.size() > 1 || (series.size() == 1 && !series.containsKey("")); }
        boolean isEmpty() { return cats.isEmpty(); }
    }

    static final class Table {
        final String title; final List<String> headers; final List<String[]> rows;
        Table(String title, List<String> headers, List<String[]> rows) { this.title = title; this.headers = headers; this.rows = rows; }
    }

    static final class Board {
        final String key, title, moduleKey, question;
        final List<Tile> tiles = new ArrayList<>();
        final List<Chart> charts = new ArrayList<>();
        final List<Table> tables = new ArrayList<>();
        boolean empty = false;
        Board(String key, String title, String moduleKey, String question) { this.key = key; this.title = title; this.moduleKey = moduleKey; this.question = question; }
    }

    static final class Ctx {
        final LocalDate today, start, end;
        final Map<String, String> parties, parts;
        Ctx(LocalDate today, LocalDate start, LocalDate end, Map<String, String> parties, Map<String, String> parts) {
            this.today = today; this.start = start; this.end = end; this.parties = parties; this.parts = parts;
        }
    }

    interface Builder { Board build(Map<String, List<JSONObject>> data, Ctx ctx); }

    static final class Def {
        final String key, title, moduleKey; final String[] tables; final Builder builder;
        Def(String key, String title, String moduleKey, String[] tables, Builder builder) { this.key = key; this.title = title; this.moduleKey = moduleKey; this.tables = tables; this.builder = builder; }
    }

    static final List<Def> DASHBOARDS = Arrays.asList(
        new Def("supplier-otd", "Supplier On-Time Delivery", "SUPPLY_CHAIN", new String[]{"supply_rm_purchase_orders", "supply_rm_receipts", "supply_forging_orders", "supply_forging_receipts"}, GenKpi::supplierDelivery),
        new Def("po-pipeline", "Purchase Order Pipeline", "SUPPLY_CHAIN", new String[]{"supply_purchase_orders"}, GenKpi::poPipeline),
        new Def("fulfilment", "Customer Order Fulfilment", "SUPPLY_CHAIN", new String[]{"supply_customer_orders", "supply_downstream_events"}, GenKpi::orderFulfilment),
        new Def("incoming-quality", "Incoming Material Quality", "MATERIAL_INWARD", new String[]{"inward_lots"}, GenKpi::incomingQuality),
        new Def("rmtc", "RMTC Approval & Compliance", "RMTC_ENTRY", new String[]{"rmtc_approvals"}, GenKpi::rmtcCompliance),
        new Def("lab-inspection", "Lab & Inspection First-Pass Yield", "METLAB_REPORT", new String[]{"lab_tests", "inspection_reports"}, GenKpi::labInspection),
        new Def("osp", "OSP Vendor Performance", "OSP_TRANSACTIONS", new String[]{"osp_jobs"}, GenKpi::ospVendor),
        new Def("complaints", "Complaints & CAPA (8D)", "COMPLAINT_MANAGEMENT", new String[]{"quality_complaints"}, GenKpi::complaintsCapa),
        new Def("calibration", "Gauge Calibration Compliance", "CALIBRATION_VALIDATION", new String[]{"quality_assets"}, GenKpi::calibration),
        new Def("npd", "NPD & APQP Health", "NPD_APQP", new String[]{"npd_orders", "ppap_projects"}, GenKpi::npdApqp));

    // ------------------------------------------------------------------ period
    static LocalDate[] period(int index, LocalDate today) {
        int v = PERIOD_DAYS[index];
        if (v == 0) return new LocalDate[]{null, null};
        if (v == -1) return new LocalDate[]{today.withDayOfYear(1), today};
        return new LocalDate[]{today.minusDays(v), today};
    }

    // ------------------------------------------------------------------ loading (kpi_dashboards._load)
    /** Loads every table the permitted dashboards need (+ parties, parts) and builds the boards. Background thread. */
    static List<Board> compute(Api api, int periodIndex) throws Exception {
        List<Def> allowed = new ArrayList<>();
        for (Def d : DASHBOARDS) if (GenUtil.canView(api, d.moduleKey)) allowed.add(d);
        if (allowed.isEmpty()) return new ArrayList<>();
        Set<String> tables = new java.util.TreeSet<>();
        for (Def d : allowed) tables.addAll(Arrays.asList(d.tables));
        tables.add("parties"); tables.add("parts");
        Map<String, List<JSONObject>> data = new HashMap<>();
        int failed = 0; Exception last = null;
        for (String t : tables) {
            try { data.put(t, GenUtil.big(api, t + "?select=*&limit=10000")); }
            catch (Exception e) { data.put(t, new ArrayList<>()); failed++; last = e; }   // like kpi_dashboards._load
        }
        if (failed == tables.size() && last != null) throw last;   // nothing readable (offline / session) - say so instead of showing zeros
        LocalDate today = LocalDate.now();
        LocalDate[] range = period(periodIndex, today);
        Map<String, String> parties = new HashMap<>();
        for (JSONObject r : data.get("parties")) parties.put(GenUtil.str(r.opt("id")), GenUtil.str(GenUtil.or(r, "party_name", "party_code")));
        Map<String, String> parts = new HashMap<>();
        for (JSONObject r : data.get("parts")) {
            List<String> v = new ArrayList<>();
            for (String k : new String[]{"part_number", "part_name"}) { String s = GenUtil.str(r.opt(k)); if (!s.isEmpty()) v.add(s); }
            parts.put(GenUtil.str(r.opt("id")), String.join(" · ", v));
        }
        Ctx ctx = new Ctx(today, range[0], range[1], parties, parts);
        List<Board> boards = new ArrayList<>();
        for (Def d : allowed) {
            try { boards.add(d.builder.build(data, ctx)); }
            catch (Exception e) {
                Board b = new Board(d.key, d.title, d.moduleKey, "Could not be calculated: " + Api.message(e));
                b.empty = true;
                boards.add(b);
            }
        }
        return boards;
    }

    // ------------------------------------------------------------------ helpers (kpi_service)
    static List<JSONObject> rows(Map<String, List<JSONObject>> data, String table) {
        List<JSONObject> r = data.get(table);
        return r == null ? new ArrayList<>() : r;
    }

    static LocalDate d(Object v) { return GenUtil.d(v); }
    static double n(Object v) { return GenUtil.n(v); }
    static String s(Object v) { return GenUtil.up(v); }
    static Object g(JSONObject r, String k) { Object v = r.opt(k); return v == JSONObject.NULL ? null : v; }
    static Object or(JSONObject r, String... k) { return GenUtil.or(r, k); }

    static Double pct(double part, double whole) { return whole != 0 ? GenUtil.round(100.0 * part / whole, 1) : null; }
    static String fmtPct(Double v) { return v == null ? "—" : GenUtil.fixed(v, 1) + "%"; }
    static String fmtNum(double v) { return GenUtil.fmt(v, 0); }
    static String f1(double v) { return GenUtil.fixed(v, 1); }

    static String statusFor(Double value, double good, double warn, boolean higherIsBetter) {
        if (value == null) return "neutral";
        if (higherIsBetter) return value >= good ? "good" : (value >= warn ? "warning" : "critical");
        return value <= good ? "good" : (value <= warn ? "warning" : "critical");
    }

    static boolean inRange(Object value, LocalDate start, LocalDate end) {
        LocalDate day = d(value);
        if (day == null) return start == null && end == null;
        return (start == null || !day.isBefore(start)) && (end == null || !day.isAfter(end));
    }

    static String month(Object value) {
        LocalDate day = d(value);
        return day == null ? "No date" : String.format(Locale.ROOT, "%04d-%02d", day.getYear(), day.getMonthValue());
    }

    static String label(Map<String, String> m, Object key, String dflt) {
        String v = m.get(GenUtil.str(key));
        return v == null || v.isEmpty() ? dflt : v;
    }

    static String label(Map<String, String> m, Object key) { return label(m, key, "Unassigned"); }

    static boolean isOpen(JSONObject r) { return !CLOSED_WORDS.contains(s(g(r, "status"))); }

    static long days(LocalDate a, LocalDate b) { return ChronoUnit.DAYS.between(b, a); }

    static String dstr(LocalDate d) { return d == null ? "" : d.toString(); }

    /** str(date or None) as pandas/python shows it ("None" when missing). */
    static String dnone(LocalDate d) { return d == null ? "None" : d.toString(); }

    static String c(double v) { return GenUtil.cell(v); }

    static double mean(List<? extends Number> v) {
        double s = 0; for (Number x : v) s += x.doubleValue();
        return v.isEmpty() ? 0 : s / v.size();
    }

    // ------------------------------------------------------------------ chart builders
    /** One series: categories (x for bar/line, y for hbar) and values. */
    static Chart single(String title, String kind, String catName, String valName, List<String> cats, List<Double> vals, String note) {
        Chart ch = new Chart(title, kind, note);
        double[] v = new double[cats.size()];
        for (int i = 0; i < cats.size(); i++) { ch.cats.add(cats.get(i)); v[i] = vals.get(i); }
        ch.series.put("", v);
        ch.dataHeaders.add(catName); ch.dataHeaders.add(valName);
        for (int i = 0; i < cats.size(); i++) ch.dataRows.add(new String[]{cats.get(i), c(vals.get(i))});
        return ch;
    }

    /** Several series from long rows (x, series, value) in row order. */
    static Chart multi(String title, String kind, String xName, String sName, String yName, List<Object[]> longRows, String note) {
        Chart ch = new Chart(title, kind, note);
        List<String> series = new ArrayList<>();
        for (Object[] r : longRows) {
            if (!ch.cats.contains((String) r[0])) ch.cats.add((String) r[0]);
            if (!series.contains((String) r[1])) series.add((String) r[1]);
        }
        for (String sname : series) {
            double[] v = new double[ch.cats.size()];
            Arrays.fill(v, Double.NaN);
            ch.series.put(sname, v);
        }
        for (Object[] r : longRows) {
            double[] v = ch.series.get((String) r[1]);
            v[ch.cats.indexOf((String) r[0])] = (Double) r[2];
        }
        ch.dataHeaders.add(xName); ch.dataHeaders.add(sName); ch.dataHeaders.add(yName);
        for (Object[] r : longRows) ch.dataRows.add(new String[]{(String) r[0], (String) r[1], c((Double) r[2])});
        return ch;
    }

    /** Stable sort of indices by key. */
    static <T> void sortBy(List<T> list, Comparator<T> cmp) { list.sort(cmp); }

    static <T> List<T> head(List<T> l, int n) { return new ArrayList<>(l.subList(0, Math.min(n, l.size()))); }
    static <T> List<T> tail(List<T> l, int n) { return new ArrayList<>(l.subList(Math.max(0, l.size() - n), l.size())); }

    // ================================================================== 1
    static Board supplierDelivery(Map<String, List<JSONObject>> data, Ctx ctx) {
        Board board = new Board("supplier-otd", "Supplier On-Time Delivery", "SUPPLY_CHAIN", "Are RM and forging suppliers delivering on the promised date?");
        Map<String, JSONObject> rmPo = new LinkedHashMap<>();
        for (JSONObject r : rows(data, "supply_rm_purchase_orders")) rmPo.put(GenUtil.str(g(r, "id")), r);
        Map<String, JSONObject> fo = new LinkedHashMap<>();
        for (JSONObject r : rows(data, "supply_forging_orders")) fo.put(GenUtil.str(g(r, "id")), r);
        final class Ev { String supplier; LocalDate expected, actual; long delay; boolean onTime; String month; }
        List<Ev> events = new ArrayList<>();
        for (JSONObject rec : rows(data, "supply_rm_receipts")) {
            JSONObject po = rmPo.get(GenUtil.str(g(rec, "rm_purchase_order_id")));
            if (po != null && inRange(g(rec, "receipt_date"), ctx.start, ctx.end)) {
                Ev e = new Ev(); e.supplier = label(ctx.parties, g(po, "rm_supplier_id")); e.expected = d(g(po, "expected_date")); e.actual = d(g(rec, "receipt_date"));
                events.add(e);
            }
        }
        for (JSONObject rec : rows(data, "supply_forging_receipts")) {
            JSONObject order = fo.get(GenUtil.str(g(rec, "forging_order_id")));
            if (order != null && inRange(g(rec, "receipt_date"), ctx.start, ctx.end)) {
                Object sup = GenUtil.truthy(g(rec, "forging_supplier_id")) ? g(rec, "forging_supplier_id") : g(order, "forging_supplier_id");
                Ev e = new Ev(); e.supplier = label(ctx.parties, sup); e.expected = d(g(order, "expected_date")); e.actual = d(g(rec, "receipt_date"));
                events.add(e);
            }
        }
        events.removeIf(e -> e.expected == null || e.actual == null);
        for (Ev e : events) {
            e.delay = days(e.actual, e.expected);
            e.onTime = e.delay <= 0;
            e.month = String.format(Locale.ROOT, "%04d-%02d", e.actual.getYear(), e.actual.getMonthValue());
        }
        int total = events.size(); int onTime = 0; List<Ev> late = new ArrayList<>();
        for (Ev e : events) { if (e.onTime) onTime++; else late.add(e); }
        Double otd = pct(onTime, total);
        double avgDelay = 0; for (Ev e : late) avgDelay += e.delay; avgDelay = late.isEmpty() ? 0.0 : avgDelay / late.size();
        int overdueOpen = 0;
        List<JSONObject> all = new ArrayList<>(rmPo.values()); all.addAll(fo.values());
        for (JSONObject r : all) {
            LocalDate exp = d(g(r, "expected_date"));
            if (isOpen(r) && !s(g(r, "status")).equals("PENDING_APPROVAL") && exp != null && exp.isBefore(ctx.today)) overdueOpen++;
        }
        board.tiles.add(new Tile("On-time delivery", fmtPct(otd), onTime + " of " + total + " receipts on/before date", statusFor(otd, 95, 85, true)));
        board.tiles.add(new Tile("Late receipts", fmtNum(late.size()), "Received after expected date", late.isEmpty() ? "good" : "warning"));
        board.tiles.add(new Tile("Avg delay (late only)", f1(avgDelay) + " d", "Days after expected date", statusFor(avgDelay, 2, 7, false)));
        board.tiles.add(new Tile("Open orders overdue", fmtNum(overdueOpen), "Expected date passed, not closed", overdueOpen == 0 ? "good" : "critical"));
        if (events.isEmpty()) { board.empty = true; return board; }
        TreeMap<String, List<Ev>> bySupMap = new TreeMap<>();
        for (Ev e : events) bySupMap.computeIfAbsent(e.supplier, k -> new ArrayList<>()).add(e);
        final class Sup { String supplier; int receipts, onTime; double avgDelay, otdPct; }
        List<Sup> bySup = new ArrayList<>();
        for (Map.Entry<String, List<Ev>> en : bySupMap.entrySet()) {
            Sup s = new Sup(); s.supplier = en.getKey(); s.receipts = en.getValue().size();
            List<Long> pos = new ArrayList<>();
            for (Ev e : en.getValue()) { if (e.onTime) s.onTime++; if (e.delay > 0) pos.add(e.delay); }
            s.avgDelay = pos.isEmpty() ? 0.0 : GenUtil.round(mean(pos), 1);
            s.otdPct = GenUtil.round(100.0 * s.onTime / s.receipts, 1);
            bySup.add(s);
        }
        bySup.sort((x, y) -> x.otdPct != y.otdPct ? Double.compare(x.otdPct, y.otdPct) : Integer.compare(y.receipts, x.receipts));
        TreeMap<String, int[]> trend = new TreeMap<>();
        for (Ev e : events) { int[] t = trend.computeIfAbsent(e.month, k -> new int[2]); t[0]++; if (e.onTime) t[1]++; }
        List<Sup> top = head(bySup, 15);
        List<String> cats = new ArrayList<>(); List<Double> vals = new ArrayList<>();
        for (Sup s : top) { cats.add(s.supplier); vals.add(s.otdPct); }
        board.charts.add(single("On-time delivery % by supplier (worst first)", "hbar", "supplier", "otd_pct", cats, vals, "Target ≥ 95%"));
        List<String> mc = new ArrayList<>(); List<Double> mv = new ArrayList<>();
        for (Map.Entry<String, int[]> en : trend.entrySet()) { mc.add(en.getKey()); mv.add(GenUtil.round(100.0 * en.getValue()[1] / en.getValue()[0], 1)); }
        board.charts.add(single("Monthly on-time delivery %", "line", "month", "otd_pct", mc, mv, ""));
        List<String[]> t = new ArrayList<>();
        for (Sup s : bySup) t.add(new String[]{s.supplier, c(s.receipts), c(s.onTime), c(s.avgDelay), c(s.otdPct)});
        board.tables.add(new Table("Supplier delivery scorecard", GenUtil.listOf("Supplier", "Receipts", "On time", "Avg delay (late) d", "OTD %"), t));
        return board;
    }

    // ================================================================== 2
    static Board poPipeline(Map<String, List<JSONObject>> data, Ctx ctx) {
        Board board = new Board("po-pipeline", "Purchase Order Pipeline", "SUPPLY_CHAIN", "How much is on order, what is waiting for approval and what is overdue?");
        List<JSONObject> pos = new ArrayList<>();
        for (JSONObject r : rows(data, "supply_purchase_orders")) if (!s(g(r, "status")).equals("CANCELLED")) pos.add(r);
        List<JSONObject> inPeriod = new ArrayList<>(), openPos = new ArrayList<>(), pending = new ArrayList<>(), overdue = new ArrayList<>();
        Set<String> openSet = new HashSet<>(Arrays.asList("OPEN", "PARTIAL", "PART_RECEIVED", "PENDING_APPROVAL", "DRAFT"));
        for (JSONObject r : pos) {
            if (inRange(g(r, "order_date"), ctx.start, ctx.end)) inPeriod.add(r);
            if (openSet.contains(s(g(r, "status")))) openPos.add(r);
            String ap = s(or(r, "approval_status", "status"));
            if (ap.equals("PENDING_APPROVAL") || ap.equals("APPROVAL_PENDING")) pending.add(r);
        }
        IdentityHashMap<JSONObject, Long> ages = new IdentityHashMap<>();
        List<Long> ageList = new ArrayList<>();
        for (JSONObject r : pending) {
            LocalDate base = d(g(r, "submitted_at"));
            if (base == null) base = d(g(r, "order_date"));
            if (base == null) base = ctx.today;
            long age = days(ctx.today, base);
            ages.put(r, age); ageList.add(age);
        }
        for (JSONObject r : openPos) {
            LocalDate dd = d(g(r, "delivery_date"));
            if (!s(g(r, "status")).equals("PENDING_APPROVAL") && dd != null && dd.isBefore(ctx.today)) overdue.add(r);
        }
        double openValue = 0; for (JSONObject r : openPos) openValue += n(g(r, "grand_total"));
        double avgAge = ageList.isEmpty() ? 0.0 : mean(ageList);
        double periodValue = 0; for (JSONObject r : inPeriod) periodValue += n(g(r, "grand_total"));
        board.tiles.add(new Tile("Open PO value", "₹ " + fmtNum(openValue), openPos.size() + " open POs", "neutral"));
        board.tiles.add(new Tile("Waiting for approval", fmtNum(pending.size()), "Avg age " + f1(avgAge) + " days", pending.isEmpty() ? "good" : statusFor(avgAge, 1, 3, false)));
        board.tiles.add(new Tile("Overdue open POs", fmtNum(overdue.size()), "Delivery date passed", overdue.isEmpty() ? "good" : "critical"));
        board.tiles.add(new Tile("POs raised in period", fmtNum(inPeriod.size()), "₹ " + fmtNum(periodValue), "neutral"));
        if (pos.isEmpty()) { board.empty = true; return board; }
        TreeMap<String, Double> byStatus = new TreeMap<>();
        TreeMap<String, TreeMap<String, Double>> trend = new TreeMap<>();
        for (JSONObject r : pos) {
            String st = GenUtil.title(s(g(r, "status")).replace("_", " "));
            if (st.isEmpty()) st = "Unknown";
            byStatus.merge(st, n(g(r, "grand_total")), Double::sum);
            String m = month(g(r, "order_date"));
            if (m.equals("No date")) continue;
            String type = GenUtil.title(s(g(r, "po_type")).replace("_", " "));
            trend.computeIfAbsent(m, k -> new TreeMap<>()).merge(type, n(g(r, "grand_total")), Double::sum);
        }
        List<Map.Entry<String, Double>> st = new ArrayList<>(byStatus.entrySet());
        st.sort((x, y) -> Double.compare(y.getValue(), x.getValue()));
        List<String> cats = new ArrayList<>(); List<Double> vals = new ArrayList<>();
        for (Map.Entry<String, Double> e : st) { cats.add(e.getKey()); vals.add(e.getValue()); }
        board.charts.add(single("PO value by status (₹)", "bar", "status", "value", cats, vals, ""));
        TreeMap<String, Double> openBySup = new TreeMap<>();
        for (JSONObject r : openPos) openBySup.merge(label(ctx.parties, g(r, "supplier_id")), n(g(r, "grand_total")), Double::sum);
        List<Map.Entry<String, Double>> top = new ArrayList<>(openBySup.entrySet());
        top.sort((x, y) -> Double.compare(y.getValue(), x.getValue()));
        top = head(top, 10);
        top.sort((x, y) -> Double.compare(x.getValue(), y.getValue()));
        cats = new ArrayList<>(); vals = new ArrayList<>();
        for (Map.Entry<String, Double> e : top) { cats.add(e.getKey()); vals.add(e.getValue()); }
        board.charts.add(single("Top 10 suppliers by open PO value (₹)", "hbar", "supplier", "value", cats, vals, ""));
        List<Object[]> longRows = new ArrayList<>();
        for (Map.Entry<String, TreeMap<String, Double>> m : trend.entrySet()) for (Map.Entry<String, Double> e : m.getValue().entrySet()) longRows.add(new Object[]{m.getKey(), e.getKey(), e.getValue()});
        board.charts.add(multi("Monthly PO value by type (₹)", "stacked", "month", "type", "value", longRows, ""));
        List<JSONObject> queue = new ArrayList<>(pending);
        queue.sort((x, y) -> Long.compare(ages.get(y), ages.get(x)));
        List<String[]> q = new ArrayList<>();
        for (JSONObject r : queue) {
            LocalDate sub = d(g(r, "submitted_at")); if (sub == null) sub = d(g(r, "order_date"));
            q.add(new String[]{GenUtil.j(r, "po_number"), label(ctx.parties, g(r, "supplier_id")), c(GenUtil.round(n(g(r, "grand_total")), 2)), dstr(sub), c(ages.get(r))});
        }
        board.tables.add(new Table("Approval queue (oldest first)", GenUtil.listOf("PO Number", "Supplier", "Value ₹", "Submitted", "Age days"), q));
        List<JSONObject> lateList = new ArrayList<>(overdue);
        lateList.sort((x, y) -> Long.compare(days(ctx.today, d(g(y, "delivery_date"))), days(ctx.today, d(g(x, "delivery_date")))));
        List<String[]> l = new ArrayList<>();
        for (JSONObject r : lateList) {
            LocalDate dd = d(g(r, "delivery_date"));
            l.add(new String[]{GenUtil.j(r, "po_number"), label(ctx.parties, g(r, "supplier_id")), dstr(dd), c(days(ctx.today, dd)), c(GenUtil.round(n(g(r, "grand_total")), 2))});
        }
        board.tables.add(new Table("Overdue open POs", GenUtil.listOf("PO Number", "Supplier", "Delivery date", "Days late", "Value ₹"), l));
        return board;
    }

    // ================================================================== 3
    static Board incomingQuality(Map<String, List<JSONObject>> data, Ctx ctx) {
        Board board = new Board("incoming-quality", "Incoming Material Quality", "MATERIAL_INWARD", "How good is the steel / forgings we receive, by supplier?");
        List<JSONObject> lots = new ArrayList<>();
        for (JSONObject r : rows(data, "inward_lots")) if (inRange(or(r, "inward_date", "created_at"), ctx.start, ctx.end)) lots.add(r);
        double recv = 0, rej = 0, hold = 0, accepted = 0; int pending = 0;
        for (JSONObject r : lots) {
            recv += n(or(r, "steel_quantity_kg", "quantity_received"));
            rej += n(or(r, "rejected_steel_quantity_kg", "quantity_rejected"));
            hold += n(g(r, "hold_steel_quantity_kg"));
            accepted += n(or(r, "accepted_steel_quantity_kg", "quantity_accepted"));
            if (s(g(r, "metallurgical_status")).contains("PENDING") || s(g(r, "dimensional_status")).contains("PENDING") || s(g(r, "status")).contains("HOLD")) pending++;
        }
        Double ppm = recv != 0 ? rej / recv * 1_000_000 : null;
        Double acc = pct(accepted, recv);
        board.tiles.add(new Tile("Lots received", fmtNum(lots.size()), fmtNum(recv) + " kg received", "neutral"));
        board.tiles.add(new Tile("Acceptance rate", fmtPct(acc), fmtNum(accepted) + " kg accepted", statusFor(acc, 98, 95, true)));
        board.tiles.add(new Tile("Rejection PPM", ppm == null ? "—" : fmtNum(ppm), fmtNum(rej) + " kg rejected", statusFor(ppm, 1000, 5000, false)));
        board.tiles.add(new Tile("On hold / pending", fmtNum(pending), fmtNum(hold) + " kg on hold", pending == 0 ? "good" : "warning"));
        if (lots.isEmpty()) { board.empty = true; return board; }
        TreeMap<String, double[]> sup = new TreeMap<>();   // lots, received, rejected, hold
        TreeMap<String, double[]> trend = new TreeMap<>(); // received, rejected
        for (JSONObject r : lots) {
            double rc = n(or(r, "steel_quantity_kg", "quantity_received")), rj = n(or(r, "rejected_steel_quantity_kg", "quantity_rejected")), h = n(g(r, "hold_steel_quantity_kg"));
            double[] sv = sup.computeIfAbsent(label(ctx.parties, g(r, "supplier_id")), k -> new double[4]);
            sv[0]++; sv[1] += rc; sv[2] += rj; sv[3] += h;
            double[] tv = trend.computeIfAbsent(month(or(r, "inward_date", "created_at")), k -> new double[2]);
            tv[0] += rc; tv[1] += rj;
        }
        final class Row { String sup; double lots, received, rejected, hold, rejPct, ppm; }
        List<Row> rowsList = new ArrayList<>();
        for (Map.Entry<String, double[]> e : sup.entrySet()) {
            Row r = new Row(); double[] v = e.getValue();
            r.sup = e.getKey(); r.lots = v[0]; r.received = v[1]; r.rejected = v[2]; r.hold = v[3];
            r.rejPct = r.received > 0 ? GenUtil.round(100 * r.rejected / r.received, 2) : 0.0;
            r.ppm = r.received > 0 ? GenUtil.round(1_000_000 * r.rejected / r.received, 0) : 0.0;
            rowsList.add(r);
        }
        List<Row> asc = new ArrayList<>(rowsList);
        asc.sort((x, y) -> Double.compare(x.ppm, y.ppm));
        asc = tail(asc, 15);
        List<String> cats = new ArrayList<>(); List<Double> vals = new ArrayList<>();
        for (Row r : asc) { cats.add(r.sup); vals.add(r.ppm); }
        board.charts.add(single("Rejection PPM by supplier (worst first)", "hbar", "supplier", "ppm", cats, vals, "Lower is better"));
        List<String> mc = new ArrayList<>(); List<Double> mv = new ArrayList<>();
        for (Map.Entry<String, double[]> e : trend.entrySet()) { mc.add(e.getKey()); mv.add(e.getValue()[0] > 0 ? GenUtil.round(1_000_000 * e.getValue()[1] / e.getValue()[0], 0) : 0.0); }
        board.charts.add(single("Monthly rejection PPM", "line", "month", "ppm", mc, mv, ""));
        List<Row> desc = new ArrayList<>(rowsList);
        desc.sort((x, y) -> Double.compare(y.ppm, x.ppm));
        List<String[]> t = new ArrayList<>();
        for (Row r : desc) t.add(new String[]{r.sup, c(r.lots), c(r.received), c(r.rejected), c(r.hold), c(r.rejPct), c(r.ppm)});
        board.tables.add(new Table("Supplier quality scorecard", GenUtil.listOf("Supplier", "Lots", "Received kg", "Rejected kg", "On hold kg", "Rejection %", "PPM"), t));
        return board;
    }

    // ================================================================== 4
    static Board rmtcCompliance(Map<String, List<JSONObject>> data, Ctx ctx) {
        Board board = new Board("rmtc", "RMTC Approval & Compliance", "RMTC_ENTRY", "Are mill certificates approved fast and right first time?");
        List<JSONObject> rs = new ArrayList<>();
        for (JSONObject r : rows(data, "rmtc_approvals")) if (inRange(or(r, "certificate_date", "created_at"), ctx.start, ctx.end)) rs.add(r);
        Set<JSONObject> approved = java.util.Collections.newSetFromMap(new IdentityHashMap<>());
        Set<JSONObject> rejected = java.util.Collections.newSetFromMap(new IdentityHashMap<>());
        List<JSONObject> decided = new ArrayList<>(), pending = new ArrayList<>();
        List<Long> cycle = new ArrayList<>();
        int chemFail = 0; double certQty = 0;
        for (JSONObject r : rs) {
            if (d(or(r, "decision_at", "approved_at")) != null) decided.add(r);
            if (PASS_WORDS.contains(s(or(r, "status", "disposition"))) || PASS_WORDS.contains(s(g(r, "disposition")))) approved.add(r);
            if (FAIL_WORDS.contains(s(g(r, "status"))) || FAIL_WORDS.contains(s(g(r, "disposition")))) rejected.add(r);
            Object cc = g(r, "chemistry_compliance");
            if (Boolean.FALSE.equals(cc) || Arrays.asList("FALSE", "FAIL", "NON_COMPLIANT").contains(s(cc))) chemFail++;
            certQty += n(g(r, "certificate_quantity"));
        }
        for (JSONObject r : rs) if (!approved.contains(r) && !rejected.contains(r) && !CLOSED_WORDS.contains(s(g(r, "status")))) pending.add(r);
        for (JSONObject r : decided) {
            LocalDate created = d(g(r, "created_at"));
            if (created != null) cycle.add(days(d(or(r, "decision_at", "approved_at")), created));
        }
        Double avgCycle = cycle.isEmpty() ? null : mean(cycle);
        Double rate = pct(approved.size(), approved.size() + rejected.size());
        board.tiles.add(new Tile("Certificates", fmtNum(rs.size()), fmtNum(certQty) + " kg certified", "neutral"));
        board.tiles.add(new Tile("Approval rate", fmtPct(rate), rejected.size() + " rejected", statusFor(rate, 97, 90, true)));
        board.tiles.add(new Tile("Pending decision", fmtNum(pending.size()), "Awaiting validation", pending.isEmpty() ? "good" : "warning"));
        board.tiles.add(new Tile("Avg decision time", avgCycle == null ? "—" : f1(avgCycle) + " d", "Chemistry non-compliance: " + chemFail, statusFor(avgCycle, 1, 3, false)));
        if (rs.isEmpty()) { board.empty = true; return board; }
        TreeMap<String, Integer> status = new TreeMap<>();
        TreeMap<String, int[]> mill = new TreeMap<>();
        for (JSONObject r : rs) {
            String st = s(g(r, "status")); if (st.isEmpty()) st = "UNKNOWN";
            status.merge(GenUtil.title(st.replace("_", " ")), 1, Integer::sum);
            Object millId = GenUtil.truthy(g(r, "steel_mill_id")) ? g(r, "steel_mill_id") : g(r, "supplier_id");
            int[] m = mill.computeIfAbsent(label(ctx.parties, millId), k -> new int[3]);
            m[0]++; if (approved.contains(r)) m[1]++; if (rejected.contains(r)) m[2]++;
        }
        List<Map.Entry<String, Integer>> st = new ArrayList<>(status.entrySet());
        st.sort((x, y) -> Integer.compare(y.getValue(), x.getValue()));
        List<String> cats = new ArrayList<>(); List<Double> vals = new ArrayList<>();
        for (Map.Entry<String, Integer> e : st) { cats.add(e.getKey()); vals.add((double) e.getValue()); }
        board.charts.add(single("Certificates by status", "bar", "status", "certificates", cats, vals, ""));
        final class M { String mill; int certs, appr, rej; double pct; }
        List<M> ms = new ArrayList<>();
        for (Map.Entry<String, int[]> e : mill.entrySet()) {
            M m = new M(); m.mill = e.getKey(); m.certs = e.getValue()[0]; m.appr = e.getValue()[1]; m.rej = e.getValue()[2];
            m.pct = (m.appr + m.rej) > 0 ? GenUtil.round(100.0 * m.appr / (m.appr + m.rej), 1) : 0.0;
            ms.add(m);
        }
        List<M> asc = new ArrayList<>(ms);
        asc.sort((x, y) -> Double.compare(x.pct, y.pct));
        asc = tail(asc, 15);
        cats = new ArrayList<>(); vals = new ArrayList<>();
        for (M m : asc) { cats.add(m.mill); vals.add(m.pct); }
        board.charts.add(single("Approval % by steel mill / supplier", "hbar", "mill", "approval_pct", cats, vals, ""));
        List<M> desc = new ArrayList<>(ms);
        desc.sort((x, y) -> Integer.compare(y.certs, x.certs));
        List<String[]> t = new ArrayList<>();
        for (M m : desc) t.add(new String[]{m.mill, c(m.certs), c(m.appr), c(m.rej), c(m.pct)});
        board.tables.add(new Table("Mill scorecard", GenUtil.listOf("Steel mill / supplier", "Certificates", "Approved", "Rejected", "Approval %"), t));
        return board;
    }

    // ================================================================== 5
    static Board labInspection(Map<String, List<JSONObject>> data, Ctx ctx) {
        Board board = new Board("lab-inspection", "Lab & Inspection First-Pass Yield", "METLAB_REPORT", "How many MetLAB / dimensional reports pass first time, and how fast are they released?");
        final class Rep { String source, result, month, part; boolean pass, fail; Long tat; }
        List<Rep> reports = new ArrayList<>();
        String[][] sources = {{"MetLAB / Bend", "lab_tests", "test_date"}, {"Dimensional", "inspection_reports", "inspection_date"}};
        for (String[] src : sources) {
            for (JSONObject r : rows(data, src[1])) {
                Object when = or(r, src[2], "created_at");
                if (!inRange(when, ctx.start, ctx.end)) continue;
                Rep p = new Rep();
                p.source = src[0]; p.result = s(or(r, "overall_result", "disposition"));
                p.pass = PASS_WORDS.contains(p.result); p.fail = FAIL_WORDS.contains(p.result);
                p.month = month(when); p.part = label(ctx.parts, g(r, "part_id"), "No part");
                LocalDate v = d(or(r, "validated_at", "decision_at")), cr = d(g(r, "created_at"));
                p.tat = v != null && cr != null ? days(v, cr) : null;
                reports.add(p);
            }
        }
        List<Rep> evaluated = new ArrayList<>();
        int passN = 0, failN = 0, pending = 0, met = 0, dim = 0;
        List<Long> tats = new ArrayList<>();
        for (Rep r : reports) {
            if (r.pass || r.fail) { evaluated.add(r); if (r.pass) passN++; if (r.fail) failN++; }
            else pending++;
            if (r.tat != null) tats.add(r.tat);
            if (r.source.equals("MetLAB / Bend")) met++; else dim++;
        }
        Double fpy = pct(passN, evaluated.size());
        Double avgTat = tats.isEmpty() ? null : mean(tats);
        board.tiles.add(new Tile("Reports", fmtNum(reports.size()), met + " MetLAB · " + dim + " dimensional", "neutral"));
        board.tiles.add(new Tile("First-pass yield", fmtPct(fpy), failN + " failed", statusFor(fpy, 98, 95, true)));
        board.tiles.add(new Tile("Not yet evaluated", fmtNum(pending), "Pending / hold / not evaluated", pending == 0 ? "good" : "warning"));
        board.tiles.add(new Tile("Avg release time", avgTat == null ? "—" : f1(avgTat) + " d", "Created → validated", statusFor(avgTat, 1, 3, false)));
        if (reports.isEmpty()) { board.empty = true; return board; }
        TreeMap<String, TreeMap<String, int[]>> trend = new TreeMap<>();
        TreeMap<String, int[]> worstMap = new TreeMap<>();
        for (Rep r : evaluated) {
            int[] t = trend.computeIfAbsent(r.month, k -> new TreeMap<>()).computeIfAbsent(r.source, k -> new int[2]);
            t[0]++; if (r.pass) t[1]++;
            int[] w = worstMap.computeIfAbsent(r.part, k -> new int[2]);
            w[0]++; if (r.fail) w[1]++;
        }
        List<Object[]> longRows = new ArrayList<>();
        for (Map.Entry<String, TreeMap<String, int[]>> m : trend.entrySet())
            for (Map.Entry<String, int[]> e : m.getValue().entrySet()) longRows.add(new Object[]{m.getKey(), e.getKey(), GenUtil.round(100.0 * e.getValue()[1] / e.getValue()[0], 1)});
        board.charts.add(multi("Monthly first-pass yield %", "line", "month", "source", "fpy_pct", longRows, ""));
        List<Map.Entry<String, int[]>> worst = new ArrayList<>(worstMap.entrySet());
        worst.sort((x, y) -> x.getValue()[1] != y.getValue()[1] ? Integer.compare(y.getValue()[1], x.getValue()[1]) : Integer.compare(y.getValue()[0], x.getValue()[0]));
        worst.removeIf(e -> e.getValue()[1] <= 0);
        worst = head(worst, 10);
        if (!worst.isEmpty()) {
            List<Map.Entry<String, int[]>> asc = new ArrayList<>(worst);
            asc.sort((x, y) -> Integer.compare(x.getValue()[1], y.getValue()[1]));
            List<String> cats = new ArrayList<>(); List<Double> vals = new ArrayList<>();
            for (Map.Entry<String, int[]> e : asc) { cats.add(e.getKey()); vals.add((double) e.getValue()[1]); }
            board.charts.add(single("Parts with most failed reports", "hbar", "part", "failed", cats, vals, ""));
        }
        List<String[]> t = new ArrayList<>();
        for (Map.Entry<String, int[]> e : worst) t.add(new String[]{e.getKey(), c(e.getValue()[0]), c(e.getValue()[1])});
        board.tables.add(new Table("Failed reports by part", GenUtil.listOf("Part", "Reports", "Failed"), t));
        return board;
    }

    // ================================================================== 6
    static Board complaintsCapa(Map<String, List<JSONObject>> data, Ctx ctx) {
        Board board = new Board("complaints", "Complaints & CAPA (8D)", "COMPLAINT_MANAGEMENT", "How many complaints are open, overdue and how fast do we close them?");
        List<JSONObject> allrows = rows(data, "quality_complaints");
        List<JSONObject> rs = new ArrayList<>(), open = new ArrayList<>(), overdue = new ArrayList<>(), closed = new ArrayList<>();
        for (JSONObject r : allrows) {
            if (inRange(or(r, "complaint_date", "created_at"), ctx.start, ctx.end)) rs.add(r);
            if (isOpen(r)) {
                open.add(r);
                LocalDate t = d(g(r, "target_closure_date"));
                if (t != null && t.isBefore(ctx.today)) overdue.add(r);
            }
        }
        List<Long> days = new ArrayList<>();
        for (JSONObject r : rs) {
            if (s(g(r, "status")).equals("CLOSED") && d(g(r, "closure_date")) != null && d(or(r, "complaint_date", "created_at")) != null) {
                closed.add(r);
                days.add(days(d(g(r, "closure_date")), d(or(r, "complaint_date", "created_at"))));
            }
        }
        double debitOpen = 0;
        for (JSONObject r : allrows) if (GenUtil.truthy(g(r, "debit_note_required"))) debitOpen += Math.max(n(g(r, "debit_note_amount")) - n(g(r, "debit_note_settled_amount")), 0);
        int cust = 0, supp = 0, high = 0;
        for (JSONObject r : rs) { String t = s(g(r, "complaint_type")); if (t.startsWith("CUSTOMER")) cust++; if (t.startsWith("SUPPLIER")) supp++; }
        for (JSONObject r : open) { String sv = s(g(r, "severity")); if (sv.equals("HIGH") || sv.equals("CRITICAL")) high++; }
        Double avg = days.isEmpty() ? null : mean(days);
        board.tiles.add(new Tile("Complaints in period", fmtNum(rs.size()), cust + " customer · " + supp + " supplier", "neutral"));
        board.tiles.add(new Tile("Open complaints", fmtNum(open.size()), high + " high / critical", open.isEmpty() ? "good" : "warning"));
        board.tiles.add(new Tile("Overdue CAPA", fmtNum(overdue.size()), "Target closure date passed", overdue.isEmpty() ? "good" : "critical"));
        board.tiles.add(new Tile("Avg closure time", avg == null ? "—" : GenUtil.fixed(avg, 0) + " d", "Open debit notes ₹ " + fmtNum(debitOpen), statusFor(avg, 30, 60, false)));
        if (allrows.isEmpty()) { board.empty = true; return board; }
        TreeMap<String, Integer> sev = new TreeMap<>();
        for (JSONObject r : open) { String sv = s(g(r, "severity")); sev.merge(GenUtil.title(sv.isEmpty() ? "UNSET" : sv), 1, Integer::sum); }
        Map<String, Integer> order = new HashMap<>();
        order.put("Critical", 0); order.put("High", 1); order.put("Medium", 2); order.put("Low", 3);
        List<Map.Entry<String, Integer>> sevList = new ArrayList<>(sev.entrySet());
        sevList.sort((x, y) -> Integer.compare(order.getOrDefault(x.getKey(), 9), order.getOrDefault(y.getKey(), 9)));
        List<String> cats = new ArrayList<>(); List<Double> vals = new ArrayList<>();
        for (Map.Entry<String, Integer> e : sevList) { cats.add(e.getKey()); vals.add((double) e.getValue()); }
        board.charts.add(single("Open complaints by severity", "bar", "severity", "open", cats, vals, ""));
        TreeMap<String, TreeMap<String, Integer>> flow = new TreeMap<>();
        for (JSONObject r : rs) flow.computeIfAbsent(month(or(r, "complaint_date", "created_at")), k -> new TreeMap<>()).merge("Opened", 1, Integer::sum);
        for (JSONObject r : closed) flow.computeIfAbsent(month(g(r, "closure_date")), k -> new TreeMap<>()).merge("Closed", 1, Integer::sum);
        List<Object[]> longRows = new ArrayList<>();
        for (Map.Entry<String, TreeMap<String, Integer>> m : flow.entrySet())
            for (Map.Entry<String, Integer> e : m.getValue().entrySet()) longRows.add(new Object[]{m.getKey(), e.getKey(), (double) e.getValue()});
        board.charts.add(multi("Complaints opened vs closed per month", "line", "month", "series", "complaints", longRows, ""));
        TreeMap<String, Integer> parts = new TreeMap<>();
        for (JSONObject r : rs) parts.merge(label(ctx.parts, g(r, "part_id"), "No part"), 1, Integer::sum);
        if (!parts.isEmpty()) {
            List<Map.Entry<String, Integer>> top = new ArrayList<>(parts.entrySet());
            top.sort((x, y) -> Integer.compare(y.getValue(), x.getValue()));
            top = head(top, 10);
            top.sort((x, y) -> Integer.compare(x.getValue(), y.getValue()));
            cats = new ArrayList<>(); vals = new ArrayList<>();
            for (Map.Entry<String, Integer> e : top) { cats.add(e.getKey()); vals.add((double) e.getValue()); }
            board.charts.add(single("Top parts by complaints", "hbar", "part", "complaints", cats, vals, ""));
        }
        List<String[]> t = new ArrayList<>();
        for (JSONObject r : overdue) {
            LocalDate tg = d(g(r, "target_closure_date"));
            t.add(new String[]{GenUtil.j(r, "complaint_number"), GenUtil.j(r, "subject"), GenUtil.j(r, "severity"), GenUtil.j(r, "status"), dstr(tg), c(days(ctx.today, tg))});
        }
        board.tables.add(new Table("Overdue CAPA", GenUtil.listOf("Complaint", "Subject", "Severity", "Status", "Target", "Days overdue"), t));
        return board;
    }

    // ================================================================== 7
    static Board ospVendor(Map<String, List<JSONObject>> data, Ctx ctx) {
        Board board = new Board("osp", "OSP Vendor Performance", "OSP_TRANSACTIONS", "What is at OSP vendors, what is late back and how long do vendors take?");
        List<JSONObject> jobs = new ArrayList<>();
        for (JSONObject r : rows(data, "osp_jobs")) if (!s(g(r, "status")).equals("CANCELLED")) jobs.add(r);
        List<JSONObject> period = new ArrayList<>(), atVendor = new ArrayList<>(), late = new ArrayList<>();
        for (JSONObject r : jobs) {
            if (inRange(or(r, "dispatch_date", "created_at"), ctx.start, ctx.end)) period.add(r);
            if (n(g(r, "quantity_dispatched")) > n(g(r, "quantity_received")) && !CLOSED_WORDS.contains(s(g(r, "status")))) {
                atVendor.add(r);
                LocalDate e = d(g(r, "expected_return_date"));
                if (e != null && e.isBefore(ctx.today)) late.add(r);
            }
        }
        List<Long> tat = new ArrayList<>();
        double sent = 0, rej = 0, pcs = 0;
        for (JSONObject r : period) {
            LocalDate rc = d(g(r, "receipt_date")), dp = d(g(r, "dispatch_date"));
            if (rc != null && dp != null) tat.add(days(rc, dp));
            sent += n(g(r, "quantity_dispatched")); rej += n(g(r, "quantity_rejected_at_receipt"));
        }
        for (JSONObject r : atVendor) pcs += n(g(r, "quantity_dispatched")) - n(g(r, "quantity_received"));
        Double avgTat = tat.isEmpty() ? null : mean(tat);
        Double rejPct = pct(rej, sent);
        board.tiles.add(new Tile("Pcs at vendors", fmtNum(pcs), atVendor.size() + " open jobs", "neutral"));
        board.tiles.add(new Tile("Late returns", fmtNum(late.size()), "Expected return date passed", late.isEmpty() ? "good" : "critical"));
        board.tiles.add(new Tile("Avg turnaround", avgTat == null ? "—" : f1(avgTat) + " d", "Dispatch → receipt", statusFor(avgTat, 5, 10, false)));
        board.tiles.add(new Tile("Receipt rejection", fmtPct(rejPct), fmtNum(rej) + " of " + fmtNum(sent) + " pcs", statusFor(rejPct, 0.5, 2, false)));
        if (jobs.isEmpty()) { board.empty = true; return board; }
        TreeMap<String, Double> pend = new TreeMap<>();
        for (JSONObject r : atVendor) pend.merge(label(ctx.parties, g(r, "vendor_id")), n(g(r, "quantity_dispatched")) - n(g(r, "quantity_received")), Double::sum);
        List<Map.Entry<String, Double>> pl = new ArrayList<>(pend.entrySet());
        pl.sort((x, y) -> Double.compare(x.getValue(), y.getValue()));
        pl = tail(pl, 15);
        List<String> cats = new ArrayList<>(); List<Double> vals = new ArrayList<>();
        for (Map.Entry<String, Double> e : pl) { cats.add(e.getKey()); vals.add(e.getValue()); }
        board.charts.add(single("Pieces currently at each vendor", "hbar", "vendor", "pcs", cats, vals, ""));
        TreeMap<String, List<Long>> tv = new TreeMap<>();
        for (JSONObject r : period) {
            LocalDate rc = d(g(r, "receipt_date")), dp = d(g(r, "dispatch_date"));
            if (rc != null && dp != null) tv.computeIfAbsent(label(ctx.parties, g(r, "vendor_id")), k -> new ArrayList<>()).add(days(rc, dp));
        }
        if (!tv.isEmpty()) {
            List<Map.Entry<String, Double>> tl = new ArrayList<>();
            for (Map.Entry<String, List<Long>> e : tv.entrySet()) tl.add(new java.util.AbstractMap.SimpleEntry<>(e.getKey(), GenUtil.round(mean(e.getValue()), 1)));
            tl.sort((x, y) -> Double.compare(x.getValue(), y.getValue()));
            tl = tail(tl, 15);
            cats = new ArrayList<>(); vals = new ArrayList<>();
            for (Map.Entry<String, Double> e : tl) { cats.add(e.getKey()); vals.add(e.getValue()); }
            board.charts.add(single("Average turnaround days by vendor", "hbar", "vendor", "days", cats, vals, ""));
        }
        List<String[]> t = new ArrayList<>();
        for (JSONObject r : late) {
            LocalDate e = d(g(r, "expected_return_date"));
            t.add(new String[]{GenUtil.j(r, "osp_job_number"), label(ctx.parties, g(r, "vendor_id")), label(ctx.parts, g(r, "part_id"), "-"), dstr(d(g(r, "dispatch_date"))),
                dstr(e), c(n(g(r, "quantity_dispatched")) - n(g(r, "quantity_received"))), c(days(ctx.today, e))});
        }
        board.tables.add(new Table("Late OSP returns", GenUtil.listOf("OSP Job", "Vendor", "Part", "Dispatched", "Expected", "Pending pcs", "Days late"), t));
        return board;
    }

    // ================================================================== 8
    static Board orderFulfilment(Map<String, List<JSONObject>> data, Ctx ctx) {
        Board board = new Board("fulfilment", "Customer Order Fulfilment", "SUPPLY_CHAIN", "Are we shipping customer schedules complete and on time?");
        List<JSONObject> orders = new ArrayList<>();
        for (JSONObject r : rows(data, "supply_customer_orders")) if (!s(g(r, "status")).equals("CANCELLED")) orders.add(r);
        Map<String, Double> shipped = new HashMap<>();
        for (JSONObject e : rows(data, "supply_downstream_events"))
            if (s(g(e, "event_type")).equals("CUSTOMER_DISPATCH")) shipped.merge(GenUtil.str(g(e, "customer_order_id")), n(g(e, "qty_pcs")), Double::sum);
        List<JSONObject> period = new ArrayList<>(), due = new ArrayList<>();
        double ordered = 0, sent = 0, backlog = 0; int complete = 0, openCount = 0;
        for (JSONObject r : orders) {
            double qty = n(g(r, "order_qty_pcs"));
            double sh = shipped.getOrDefault(GenUtil.str(g(r, "id")), 0.0);
            if (inRange(or(r, "customer_delivery_date", "order_date"), ctx.start, ctx.end)) {
                period.add(r);
                ordered += qty; sent += Math.min(sh, qty);
                if (sh + 0.0001 >= qty && qty > 0) complete++;
            }
            LocalDate dd = d(g(r, "customer_delivery_date"));
            if (dd != null && dd.isBefore(ctx.today) && sh + 0.0001 < qty) due.add(r);
            if (isOpen(r)) { backlog += Math.max(qty - sh, 0); openCount++; }
        }
        Double fill = pct(sent, ordered);
        Double comp = pct(complete, period.size());
        board.tiles.add(new Tile("Fill rate", fmtPct(fill), fmtNum(sent) + " of " + fmtNum(ordered) + " pcs shipped", statusFor(fill, 98, 90, true)));
        board.tiles.add(new Tile("Orders complete", fmtPct(comp), complete + " of " + period.size() + " schedules", statusFor(comp, 95, 85, true)));
        board.tiles.add(new Tile("Past-due schedules", fmtNum(due.size()), "Delivery date passed, not fully shipped", due.isEmpty() ? "good" : "critical"));
        board.tiles.add(new Tile("Open backlog", fmtNum(backlog) + " pcs", openCount + " open orders", "neutral"));
        if (orders.isEmpty()) { board.empty = true; return board; }
        TreeMap<String, double[]> monthly = new TreeMap<>();
        for (JSONObject r : period) {
            double qty = n(g(r, "order_qty_pcs"));
            double[] m = monthly.computeIfAbsent(month(g(r, "customer_delivery_date")), k -> new double[2]);
            m[0] += qty; m[1] += Math.min(shipped.getOrDefault(GenUtil.str(g(r, "id")), 0.0), qty);
        }
        List<Object[]> longRows = new ArrayList<>();
        for (Map.Entry<String, double[]> e : monthly.entrySet()) longRows.add(new Object[]{e.getKey(), "Ordered", e.getValue()[0]});
        for (Map.Entry<String, double[]> e : monthly.entrySet()) longRows.add(new Object[]{e.getKey(), "Shipped", e.getValue()[1]});
        longRows.sort((x, y) -> ((String) x[0]).compareTo((String) y[0]));
        board.charts.add(multi("Ordered vs shipped pcs by delivery month", "line", "month", "series", "pcs", longRows, ""));
        TreeMap<String, Double> back = new TreeMap<>();
        for (JSONObject r : orders) if (isOpen(r)) back.merge(label(ctx.parties, g(r, "customer_id")), Math.max(n(g(r, "order_qty_pcs")) - shipped.getOrDefault(GenUtil.str(g(r, "id")), 0.0), 0), Double::sum);
        List<Map.Entry<String, Double>> bl = new ArrayList<>(back.entrySet());
        bl.sort((x, y) -> Double.compare(x.getValue(), y.getValue()));
        bl = tail(bl, 15);
        List<String> cats = new ArrayList<>(); List<Double> vals = new ArrayList<>();
        for (Map.Entry<String, Double> e : bl) { cats.add(e.getKey()); vals.add(e.getValue()); }
        board.charts.add(single("Open backlog pcs by customer", "hbar", "customer", "backlog", cats, vals, ""));
        List<String[]> t = new ArrayList<>();
        for (JSONObject r : due) {
            LocalDate dd = d(g(r, "customer_delivery_date"));
            t.add(new String[]{GenUtil.str(or(r, "master_reference_no", "customer_order_no")), label(ctx.parties, g(r, "customer_id")), label(ctx.parts, g(r, "part_id"), "-"),
                dstr(dd), c(n(g(r, "order_qty_pcs"))), c(shipped.getOrDefault(GenUtil.str(g(r, "id")), 0.0)), c(days(ctx.today, dd))});
        }
        board.tables.add(new Table("Past-due schedules", GenUtil.listOf("Order", "Customer", "Part", "Delivery date", "Ordered", "Shipped", "Days late"), t));
        return board;
    }

    // ================================================================== 9
    static Board calibration(Map<String, List<JSONObject>> data, Ctx ctx) {
        Board board = new Board("calibration", "Gauge Calibration Compliance", "CALIBRATION_VALIDATION", "Are all gauges, fixtures and instruments calibrated and validated in time?");
        List<JSONObject> assets = new ArrayList<>();
        for (JSONObject r : rows(data, "quality_assets")) {
            Object st = GenUtil.truthy(g(r, "status")) ? g(r, "status") : "ACTIVE";
            if (s(st).equals("ACTIVE")) assets.add(r);
        }
        List<JSONObject> overdue = new ArrayList<>(), soon = new ArrayList<>(), valOver = new ArrayList<>(), noDate = new ArrayList<>();
        for (JSONObject r : assets) {
            LocalDate nd = d(g(r, "next_due_date")), vd = d(g(r, "next_validation_due_date"));
            if (nd != null && nd.isBefore(ctx.today)) overdue.add(r);
            if (nd != null && !ctx.today.isAfter(nd) && !nd.isAfter(ctx.today.plusDays(30))) soon.add(r);
            if (vd != null && vd.isBefore(ctx.today)) valOver.add(r);
            if (nd == null) noDate.add(r);
        }
        Double compliance = pct(assets.size() - overdue.size(), assets.size());
        board.tiles.add(new Tile("Calibration compliance", fmtPct(compliance), assets.size() + " active assets", statusFor(compliance, 100, 95, true)));
        board.tiles.add(new Tile("Overdue calibration", fmtNum(overdue.size()), "Next due date passed", overdue.isEmpty() ? "good" : "critical"));
        board.tiles.add(new Tile("Due in 30 days", fmtNum(soon.size()), "Plan these now", soon.isEmpty() ? "good" : "warning"));
        board.tiles.add(new Tile("Validation overdue", fmtNum(valOver.size()), noDate.size() + " assets without due date", valOver.isEmpty() ? "good" : "serious"));
        if (assets.isEmpty()) { board.empty = true; return board; }
        List<String> months = new ArrayList<>();
        LocalDate first = ctx.today.withDayOfMonth(1);
        for (int i = 0; i < 6; i++) { LocalDate m = first.plusDays(32L * i).withDayOfMonth(1); months.add(String.format(Locale.ROOT, "%04d-%02d", m.getYear(), m.getMonthValue())); }
        Map<String, Integer> dueCount = new HashMap<>();
        for (JSONObject r : assets) { if (d(g(r, "next_due_date")) != null) dueCount.merge(month(g(r, "next_due_date")), 1, Integer::sum); }
        List<Double> dv = new ArrayList<>();
        for (String m : months) dv.add((double) dueCount.getOrDefault(m, 0));
        board.charts.add(single("Calibrations falling due — next 6 months", "bar", "month", "assets", months, dv, ""));
        TreeMap<String, int[]> types = new TreeMap<>();
        for (JSONObject r : assets) {
            String t = s(g(r, "asset_type")); if (t.isEmpty()) t = "OTHER";
            LocalDate nd = d(g(r, "next_due_date"));
            boolean ok = !(nd != null && nd.isBefore(ctx.today));
            int[] v = types.computeIfAbsent(GenUtil.title(t.replace("_", " ")), k -> new int[2]);
            v[0]++; if (ok) v[1]++;
        }
        List<Map.Entry<String, Double>> tl = new ArrayList<>();
        for (Map.Entry<String, int[]> e : types.entrySet()) tl.add(new java.util.AbstractMap.SimpleEntry<>(e.getKey(), GenUtil.round(100.0 * e.getValue()[1] / e.getValue()[0], 1)));
        tl.sort((x, y) -> Double.compare(x.getValue(), y.getValue()));
        List<String> cats = new ArrayList<>(); List<Double> vals = new ArrayList<>();
        for (Map.Entry<String, Double> e : tl) { cats.add(e.getKey()); vals.add(e.getValue()); }
        board.charts.add(single("Compliance % by asset type", "hbar", "type", "compliance_pct", cats, vals, ""));
        List<JSONObject> od = new ArrayList<>(overdue);
        od.sort((x, y) -> d(g(x, "next_due_date")).compareTo(d(g(y, "next_due_date"))));
        List<String[]> t = new ArrayList<>();
        for (JSONObject r : od) {
            LocalDate nd = d(g(r, "next_due_date"));
            t.add(new String[]{GenUtil.j(r, "asset_code"), GenUtil.j(r, "asset_number"), GenUtil.j(r, "asset_name"), GenUtil.j(r, "asset_type"), GenUtil.j(r, "location"), dstr(nd), c(days(ctx.today, nd))});
        }
        board.tables.add(new Table("Overdue gauges", GenUtil.listOf("Asset", "Asset No.", "Name", "Type", "Location", "Due date", "Days overdue"), t));
        return board;
    }

    // ================================================================== 10
    static Board npdApqp(Map<String, List<JSONObject>> data, Ctx ctx) {
        Board board = new Board("npd", "NPD & APQP Health", "NPD_APQP", "Are new parts and PPAP submissions on track?");
        List<JSONObject> orders = new ArrayList<>(), projects = new ArrayList<>();
        for (JSONObject r : rows(data, "npd_orders")) if (!s(g(r, "status")).equals("CANCELLED")) orders.add(r);
        for (JSONObject r : rows(data, "ppap_projects")) if (!s(g(r, "status")).equals("CANCELLED")) projects.add(r);
        List<JSONObject> openO = new ArrayList<>(), lateO = new ArrayList<>(), openP = new ArrayList<>(), lateP = new ArrayList<>();
        for (JSONObject r : orders) if (isOpen(r)) { openO.add(r); LocalDate dd = d(g(r, "delivery_date")); if (dd != null && dd.isBefore(ctx.today)) lateO.add(r); }
        for (JSONObject r : projects) if (isOpen(r)) { openP.add(r); LocalDate dd = d(g(r, "target_submission_date")); if (dd != null && dd.isBefore(ctx.today)) lateP.add(r); }
        Double avgDone = null;
        if (!openP.isEmpty()) { double s = 0; for (JSONObject r : openP) s += n(g(r, "completion_percent")); avgDone = s / openP.size(); }
        board.tiles.add(new Tile("Open NPD orders", fmtNum(openO.size()), orders.size() + " in register", "neutral"));
        board.tiles.add(new Tile("NPD orders late", fmtNum(lateO.size()), "Delivery date passed", lateO.isEmpty() ? "good" : "critical"));
        board.tiles.add(new Tile("PPAP avg completion", avgDone == null ? "—" : GenUtil.fixed(avgDone, 0) + "%", openP.size() + " open projects", statusFor(avgDone, 80, 50, true)));
        board.tiles.add(new Tile("PPAP past target", fmtNum(lateP.size()), "Target submission date passed", lateP.isEmpty() ? "good" : "critical"));
        if (orders.isEmpty() && projects.isEmpty()) { board.empty = true; return board; }
        TreeMap<String, TreeMap<String, Integer>> st = new TreeMap<>();
        for (JSONObject r : orders) { String v = s(g(r, "status")); st.computeIfAbsent(GenUtil.title((v.isEmpty() ? "UNKNOWN" : v).replace("_", " ")), k -> new TreeMap<>()).merge("NPD order", 1, Integer::sum); }
        for (JSONObject r : projects) { String v = s(g(r, "status")); st.computeIfAbsent(GenUtil.title((v.isEmpty() ? "UNKNOWN" : v).replace("_", " ")), k -> new TreeMap<>()).merge("PPAP project", 1, Integer::sum); }
        List<Object[]> longRows = new ArrayList<>();
        for (Map.Entry<String, TreeMap<String, Integer>> m : st.entrySet()) for (Map.Entry<String, Integer> e : m.getValue().entrySet()) longRows.add(new Object[]{m.getKey(), e.getKey(), (double) e.getValue()});
        board.charts.add(multi("Status of NPD orders and PPAP projects", "stacked", "status", "kind", "count", longRows, ""));
        if (!openP.isEmpty()) {
            List<JSONObject> prog = new ArrayList<>(openP);
            prog.sort((x, y) -> Double.compare(n(g(x, "completion_percent")), n(g(y, "completion_percent"))));
            prog = head(prog, 15);
            List<String> cats = new ArrayList<>(); List<Double> vals = new ArrayList<>();
            for (JSONObject r : prog) { String code = GenUtil.str(g(r, "project_code")); cats.add(code.isEmpty() ? "-" : code); vals.add(n(g(r, "completion_percent"))); }
            board.charts.add(single("Least-complete open PPAP projects (%)", "hbar", "project", "completion", cats, vals, ""));
        }
        List<String[]> t = new ArrayList<>();
        for (JSONObject r : lateO) { LocalDate dd = d(g(r, "delivery_date")); t.add(new String[]{GenUtil.j(r, "order_number"), "NPD order", label(ctx.parts, g(r, "part_id"), "-"), dstr(dd), c(days(ctx.today, dd))}); }
        for (JSONObject r : lateP) { LocalDate dd = d(g(r, "target_submission_date")); t.add(new String[]{GenUtil.j(r, "project_code"), "PPAP", label(ctx.parts, g(r, "part_id"), "-"), dstr(dd), c(days(ctx.today, dd))}); }
        board.tables.add(new Table("Late NPD orders / PPAP projects", GenUtil.listOf("Reference", "Type", "Part", "Due", "Days late"), t));
        return board;
    }

    /** One CSV with the KPI tiles, every table and every chart's data (website Excel export, as CSV). */
    static String csv(Board b, String periodLabel) {
        StringBuilder out = new StringBuilder();
        out.append(GenUtil.q("QCMS KPI · " + b.title)).append(',').append(GenUtil.q(periodLabel)).append("\n\n");
        List<String[]> kpis = new ArrayList<>();
        for (Tile t : b.tiles) kpis.add(new String[]{t.label, t.value, t.foot, STATUS_WORD.getOrDefault(t.status, "")});
        out.append("KPIs\n");
        GenUtil.appendCsv(out, GenUtil.listOf("KPI", "Value", "Detail", "Status"), kpis);
        for (Table t : b.tables) { out.append('\n').append(GenUtil.q(t.title)).append('\n'); GenUtil.appendCsv(out, t.headers, t.rows); }
        for (Chart c : b.charts) { out.append('\n').append(GenUtil.q(c.title)).append('\n'); GenUtil.appendCsv(out, c.dataHeaders, c.dataRows); }
        return out.toString();
    }

    /** "dd-MMM-yyyy → dd-MMM-yyyy" caption of the period selector (website c2.caption). */
    static String periodCaption(int index, LocalDate today) {
        LocalDate[] r = period(index, today);
        java.time.format.DateTimeFormatter f = java.time.format.DateTimeFormatter.ofPattern("dd-MMM-yyyy", Locale.ENGLISH);
        return (r[0] == null ? "Start" : r[0].format(f)) + " → " + (r[1] == null ? today : r[1]).format(f);
    }

    @SuppressWarnings("unused")
    private static JSONArray unused() { return null; }
}
