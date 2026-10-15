package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

/**
 * Port of core/report_builder.py: readable_frame (system columns hidden, lists / dicts flattened,
 * linked ids shown as labels), apply_filter, build_report (columns / filters / group-by with
 * totals / sort / limit) and the saved report definitions in master_value_catalog.
 */
final class GenReport {
    private GenReport() { }

    static final String SAVED_KEY = "qcms.report_builder.saved";
    static final int ROW_LIMIT = 10000;
    static final Set<String> HIDDEN = new HashSet<>(Arrays.asList("tenant_id", "created_by", "updated_by", "search_vector", "password_hash"));
    static final String[] OPS = {"contains", "equals", "not_equals", "starts_with", "gt", "gte", "lt", "lte", "between", "is_empty", "not_empty"};
    static final String[] OP_LABELS = {"contains", "equals", "is not", "starts with", "greater than", "greater or equal", "less than", "less or equal", "between (dates / numbers)", "is empty", "is not empty"};
    static final String[] AGGS = {"count", "sum", "mean", "min", "max", "nunique"};
    static final String[] AGG_LABELS = {"Count", "Sum", "Average", "Minimum", "Maximum", "Distinct count"};
    static final String[] CHARTS = {"", "bar", "line", "pie"};
    static final String[] CHART_LABELS = {"No chart", "Bar", "Line", "Pie"};

    static final Map<String, String> MASTER_MODULE = new HashMap<>();
    static final Map<String, String[]> LABEL_FIELDS = new LinkedHashMap<>();
    static {
        MASTER_MODULE.put("parties", "REFERENCE_MASTERS"); MASTER_MODULE.put("parts", "PART_MASTER");
        MASTER_MODULE.put("material_grades", "MATERIAL_GRADE"); MASTER_MODULE.put("material_grade_elements", "MATERIAL_GRADE");
        MASTER_MODULE.put("employees", "EMPLOYEE_MASTER");
        String[] party = {"parties", "party_code", "party_name"}, emp = {"employees", "employee_code", "first_name", "last_name"};
        LABEL_FIELDS.put("part_id", new String[]{"parts", "part_number", "part_name"});
        for (String k : new String[]{"customer_id", "supplier_id", "party_id", "vendor_id", "osp_vendor_id", "steel_mill_id"}) LABEL_FIELDS.put(k, party);
        LABEL_FIELDS.put("process_id", new String[]{"processes", "process_code", "process_name"});
        LABEL_FIELDS.put("material_grade_id", new String[]{"material_grades", "grade_code"});
        LABEL_FIELDS.put("grade_id", new String[]{"material_grades", "grade_code"});
        LABEL_FIELDS.put("inspection_stage_id", new String[]{"inspection_stages", "stage_code", "stage_name"});
        LABEL_FIELDS.put("inspection_plan_id", new String[]{"inspection_plans", "plan_number"});
        LABEL_FIELDS.put("layout_plan_id", new String[]{"inspection_plans", "plan_number"});
        for (String k : new String[]{"prepared_by_employee_id", "validated_by_employee_id", "approved_by_employee_id"}) LABEL_FIELDS.put(k, emp);
    }

    static String opLabel(String op) { int i = Arrays.asList(OPS).indexOf(op); return i < 0 ? op : OP_LABELS[i]; }
    static String aggLabel(String agg) { int i = Arrays.asList(AGGS).indexOf(agg); return i < 0 ? agg : AGG_LABELS[i]; }

    private static final Set<String> UPPER = new HashSet<>(Arrays.asList("po", "osp", "rmtc", "fsi", "grn", "hsn", "id", "npd", "ppap", "uom"));

    /** report_builder.pretty */
    static String pretty(String column) {
        String text = String.valueOf(column).replace("_id", "").replace("_", " ").trim();
        StringBuilder b = new StringBuilder();
        for (String w : text.split("\\s+")) {
            if (w.isEmpty()) continue;
            if (b.length() > 0) b.append(' ');
            if (UPPER.contains(w)) b.append(w.toUpperCase(Locale.ROOT));
            else b.append(w.substring(0, 1).toUpperCase(Locale.ROOT)).append(w.substring(1).toLowerCase(Locale.ROOT));
        }
        return b.toString();
    }

    // ------------------------------------------------------------------ frame
    /** Table of plain values (null / String / Number / Boolean) + the id of each source row. */
    static final class Frame {
        final List<String> columns = new ArrayList<>();
        final List<Object[]> rows = new ArrayList<>();
        final List<String> ids = new ArrayList<>();
        final List<JSONObject> raw = new ArrayList<>();
        boolean[] floaty = new boolean[0];
        int col(String name) { return columns.indexOf(name); }
        boolean isEmpty() { return rows.isEmpty(); }

        /** pandas dtype effect: an int column with gaps is float64, so str() shows "5.0". */
        void computeTypes() {
            floaty = new boolean[columns.size()];
            for (int c = 0; c < columns.size(); c++) {
                boolean nums = true, any = false, nulls = false, dbl = false;
                for (Object[] r : rows) {
                    Object v = r[c];
                    if (v == null) { nulls = true; continue; }
                    any = true;
                    if (!(v instanceof Number)) { nums = false; break; }
                    if (v instanceof Double || v instanceof Float) dbl = true;
                }
                floaty[c] = any && nums && (nulls || dbl);
            }
        }

        String str(int c, Object v) {
            if (v == null) return "None";
            if (v instanceof Number && c >= 0 && c < floaty.length && floaty[c]) {
                double d = ((Number) v).doubleValue();
                return GenUtil.py(d);
            }
            return GenUtil.py(v);
        }
    }

    interface Loader { List<JSONObject> load(String table) throws Exception; }

    /** Python json.dumps(..., ensure_ascii=False) text (", " and ": " separators). */
    static String pyJson(Object v) {
        if (v == null || v == JSONObject.NULL) return "null";
        if (v instanceof JSONObject) {
            JSONObject o = (JSONObject) v;
            StringBuilder b = new StringBuilder("{");
            Iterator<String> it = o.keys();
            boolean first = true;
            while (it.hasNext()) {
                String k = it.next();
                if (!first) b.append(", ");
                first = false;
                b.append(JSONObject.quote(k)).append(": ").append(pyJson(o.opt(k)));
            }
            return b.append('}').toString();
        }
        if (v instanceof JSONArray) {
            JSONArray a = (JSONArray) v;
            StringBuilder b = new StringBuilder("[");
            for (int i = 0; i < a.length(); i++) { if (i > 0) b.append(", "); b.append(pyJson(a.opt(i))); }
            return b.append(']').toString();
        }
        if (v instanceof String) return JSONObject.quote((String) v);
        if (v instanceof Boolean) return ((Boolean) v) ? "true" : "false";
        return String.valueOf(v);
    }

    private static Object flatten(Object v) {
        if (v instanceof JSONArray) {
            JSONArray a = (JSONArray) v;
            List<String> parts = new ArrayList<>();
            for (int i = 0; i < a.length(); i++) {
                Object x = a.opt(i);
                if (x == null || x == JSONObject.NULL || "".equals(x)) continue;
                parts.add(x instanceof JSONObject || x instanceof JSONArray ? pyJson(x) : GenUtil.py(x));
            }
            return String.join(", ", parts);
        }
        if (v instanceof JSONObject) {
            String s = pyJson(v);
            return s.length() > 500 ? s.substring(0, 500) : s;
        }
        return v;
    }

    /** report_builder.label_maps */
    static Map<String, Map<String, String>> labelMaps(Loader load, List<String> columns) {
        Map<String, List<JSONObject>> cache = new HashMap<>();
        Map<String, Map<String, String>> out = new HashMap<>();
        for (String column : columns) {
            String[] spec = LABEL_FIELDS.get(column);
            if (spec == null) continue;
            String table = spec[0];
            if (!cache.containsKey(table)) {
                try { cache.put(table, load.load(table)); } catch (Exception e) { cache.put(table, new ArrayList<>()); }
            }
            Map<String, String> m = new HashMap<>();
            for (JSONObject r : cache.get(table)) {
                if (!GenUtil.truthy(r.opt("id"))) continue;
                List<String> parts = new ArrayList<>();
                for (int i = 1; i < spec.length; i++) { String s = GenUtil.str(r.opt(spec[i])).trim(); if (!s.isEmpty()) parts.add(s); }
                m.put(GenUtil.str(r.opt("id")), String.join(" · ", parts));
            }
            out.put(column, m);
        }
        return out;
    }

    /** report_builder.readable_frame(rows, load) (ids dropped from the columns but kept per row). */
    static Frame readable(List<JSONObject> rows, Loader load) {
        Frame f = new Frame();
        if (rows.isEmpty()) return f;
        LinkedHashSet<String> cols = new LinkedHashSet<>();
        for (JSONObject r : rows) cols.addAll(GenUtil.keys(r));
        List<String> all = new ArrayList<>();
        for (String c : cols) if (!HIDDEN.contains(c)) all.add(c);
        Set<String> flat = new HashSet<>();
        for (String c : all) for (JSONObject r : rows) { Object v = r.opt(c); if (v instanceof JSONArray || v instanceof JSONObject) { flat.add(c); break; } }
        Map<String, Map<String, String>> labels = load == null ? new HashMap<>() : labelMaps(load, all);
        for (String c : all) if (!c.equals("id")) f.columns.add(c);
        for (JSONObject r : rows) {
            Object[] line = new Object[f.columns.size()];
            for (int i = 0; i < f.columns.size(); i++) {
                String c = f.columns.get(i);
                Object v = r.opt(c);
                if (v == JSONObject.NULL) v = null;
                if (flat.contains(c)) v = flatten(v);
                Map<String, String> m = labels.get(c);
                if (m != null && v != null && !"".equals(v)) { String l = m.get(GenUtil.py(v)); if (l != null) v = l; }
                if (v instanceof Integer) v = ((Integer) v).longValue();
                line[i] = v;
            }
            f.rows.add(line);
            f.ids.add(GenUtil.str(r.opt("id")));
            f.raw.add(r);
        }
        f.computeTypes();
        return f;
    }

    // ------------------------------------------------------------------ values
    static Double number(Object v) {
        if (v == null) return null;
        if (v instanceof Boolean) return ((Boolean) v) ? 1.0 : 0.0;
        if (v instanceof Number) { double d = ((Number) v).doubleValue(); return Double.isNaN(d) ? null : d; }
        String s = String.valueOf(v).trim();
        if (s.isEmpty()) return null;
        try { double d = Double.parseDouble(s); return Double.isNaN(d) ? null : d; } catch (Exception e) { return null; }
    }

    private static final DateTimeFormatter[] DATE_FORMATS = {
        DateTimeFormatter.ofPattern("dd-MM-yyyy"), DateTimeFormatter.ofPattern("dd/MM/yyyy"), DateTimeFormatter.ofPattern("dd.MM.yyyy"),
        DateTimeFormatter.ofPattern("yyyy/MM/dd")};

    /** pd.to_datetime(value, utc=True).tz_localize(None) - naive UTC; null when not a date. */
    static LocalDateTime dateTime(Object v) {
        if (v == null || v instanceof Number || v instanceof Boolean) return null;
        String s = String.valueOf(v).trim();
        if (s.isEmpty()) return null;
        String t = s.replace(' ', 'T');
        try { return OffsetDateTime.parse(t).withOffsetSameInstant(ZoneOffset.UTC).toLocalDateTime(); } catch (Exception ignored) { }
        try { return OffsetDateTime.parse(t.replaceAll("([+-]\\d\\d)$", "$1:00")).withOffsetSameInstant(ZoneOffset.UTC).toLocalDateTime(); } catch (Exception ignored) { }
        try { return LocalDateTime.parse(t); } catch (Exception ignored) { }
        try { return LocalDateTime.parse(t + ":00"); } catch (Exception ignored) { }
        try { return LocalDate.parse(s).atStartOfDay(); } catch (Exception ignored) { }
        for (DateTimeFormatter f : DATE_FORMATS) { try { return LocalDate.parse(s, f).atStartOfDay(); } catch (Exception ignored) { } }
        return null;
    }

    // ------------------------------------------------------------------ spec
    static final class Filter {
        String column = "", op = "contains", value = "", value2 = "";
        JSONObject json() throws Exception { return new JSONObject().put("column", column).put("op", op).put("value", value).put("value2", value2); }
    }

    static final class Measure {
        String column = "", agg = "sum";
        Measure(String column, String agg) { this.column = column; this.agg = agg; }
    }

    static final class Spec {
        String dataset = "";
        List<String> columns = new ArrayList<>();
        List<Filter> filters = new ArrayList<>();
        List<String> groupBy = new ArrayList<>();
        List<Measure> measures = new ArrayList<>();
        String sortBy = "";
        boolean descending = false;
        int limit = 0;
        String title = "";
        String chart = "";

        JSONObject json() throws Exception {
            JSONObject o = new JSONObject();
            o.put("dataset", dataset);
            o.put("columns", new JSONArray(columns));
            JSONArray fs = new JSONArray(); for (Filter f : filters) fs.put(f.json());
            o.put("filters", fs);
            o.put("group_by", new JSONArray(groupBy));
            JSONArray ms = new JSONArray(); for (Measure m : measures) ms.put(new JSONObject().put("column", m.column).put("agg", m.agg));
            o.put("measures", ms);
            o.put("sort_by", sortBy); o.put("descending", descending); o.put("limit", limit); o.put("title", title); o.put("chart", chart);
            return o;
        }

        static Spec from(JSONObject o) {
            Spec s = new Spec();
            if (o == null) return s;
            s.dataset = GenUtil.str(o.opt("dataset"));
            JSONArray a = o.optJSONArray("columns");
            for (int i = 0; a != null && i < a.length(); i++) s.columns.add(a.optString(i));
            a = o.optJSONArray("filters");
            for (int i = 0; a != null && i < a.length(); i++) {
                JSONObject f = a.optJSONObject(i);
                if (f == null) continue;
                Filter x = new Filter();
                x.column = GenUtil.str(f.opt("column")); x.op = GenUtil.str(f.opt("op")); if (x.op.isEmpty()) x.op = "contains";
                x.value = GenUtil.str(f.opt("value")); x.value2 = GenUtil.str(f.opt("value2"));
                s.filters.add(x);
            }
            a = o.optJSONArray("group_by");
            for (int i = 0; a != null && i < a.length(); i++) s.groupBy.add(a.optString(i));
            a = o.optJSONArray("measures");
            for (int i = 0; a != null && i < a.length(); i++) {
                JSONObject m = a.optJSONObject(i);
                if (m != null) s.measures.add(new Measure(GenUtil.str(m.opt("column")), m.optString("agg", "sum")));
            }
            s.sortBy = GenUtil.str(o.opt("sort_by"));
            s.descending = o.optBoolean("descending", false);
            s.limit = o.optInt("limit", 0);
            s.title = GenUtil.str(o.opt("title"));
            s.chart = GenUtil.str(o.opt("chart"));
            return s;
        }
    }

    // ------------------------------------------------------------------ apply_filter
    static Frame filter(Frame in, Filter flt) throws Exception {
        int c = in.col(flt.column);
        if (c < 0) throw new Exception("Unknown column: " + flt.column);
        String op = flt.op == null || flt.op.isEmpty() ? "contains" : flt.op;
        Frame out = new Frame();
        out.columns.addAll(in.columns);
        out.floaty = in.floaty;
        String value = flt.value == null ? "" : flt.value, value2 = flt.value2 == null ? "" : flt.value2;
        boolean range = Arrays.asList("gt", "gte", "lt", "lte", "between").contains(op);
        if (!Arrays.asList(OPS).contains(op)) throw new Exception("Unknown filter operator: " + op);
        boolean useDates = false;
        Object a = null, b = null;
        if (range) {
            int numeric = 0;
            for (Object[] r : in.rows) if (number(r[c]) != null) numeric++;
            useDates = numeric == 0;
            try {
                if (useDates) {
                    if (!value.isEmpty()) { a = dateTime(value); if (a == null) throw new Exception(); }
                    if (!value2.isEmpty()) { b = dateTime(value2); if (b == null) throw new Exception(); }
                } else {
                    if (!value.isEmpty()) a = Double.parseDouble(value.trim());
                    if (!value2.isEmpty()) b = Double.parseDouble(value2.trim());
                }
            } catch (Exception e) {
                throw new Exception("Filter value for " + pretty(flt.column) + " is not a valid " + (useDates ? "date" : "number") + ".");
            }
            if (!op.equals("between") && a == null) return in;
        }
        String low = value.toLowerCase(Locale.ROOT), fold = value.trim().toLowerCase(Locale.ROOT);
        for (int i = 0; i < in.rows.size(); i++) {
            Object v = in.rows.get(i)[c];
            String text = v == null ? "" : in.str(c, v);
            boolean keep;
            switch (op) {
                case "is_empty": keep = text.trim().isEmpty(); break;
                case "not_empty": keep = !text.trim().isEmpty(); break;
                case "contains": keep = text.toLowerCase(Locale.ROOT).contains(low); break;
                case "starts_with": keep = text.toLowerCase(Locale.ROOT).startsWith(low); break;
                case "equals": keep = text.trim().toLowerCase(Locale.ROOT).equals(fold); break;
                case "not_equals": keep = !text.trim().toLowerCase(Locale.ROOT).equals(fold); break;
                default: keep = compare(op, useDates ? dateTime(v) : number(v), a, b);
            }
            if (keep) { out.rows.add(in.rows.get(i)); out.ids.add(in.ids.get(i)); out.raw.add(in.raw.get(i)); }
        }
        return out;
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static boolean compare(String op, Object left, Object a, Object b) {
        if (left == null) return false;
        Comparable l = (Comparable) left;
        switch (op) {
            case "between": return (a == null || l.compareTo(a) >= 0) && (b == null || l.compareTo(b) <= 0);
            case "gt": return l.compareTo(a) > 0;
            case "gte": return l.compareTo(a) >= 0;
            case "lt": return l.compareTo(a) < 0;
            case "lte": return l.compareTo(a) <= 0;
            default: return false;
        }
    }

    // ------------------------------------------------------------------ build_report
    static final class Result {
        final List<String> headers = new ArrayList<>();
        final List<Object[]> rows = new ArrayList<>();
        /** Source row id per result row (null for grouped results). */
        final List<String> ids = new ArrayList<>();
        final List<JSONObject> raw = new ArrayList<>();
        boolean grouped = false;
    }

    static Result build(Frame frame, Spec spec) throws Exception {
        Frame out = frame;
        for (Filter f : spec.filters) if (f.column != null && !f.column.isEmpty()) out = filter(out, f);
        Result res = new Result();
        if (!spec.groupBy.isEmpty()) {
            List<String> missing = new ArrayList<>();
            for (String g : spec.groupBy) if (out.col(g) < 0) missing.add(g);
            if (!missing.isEmpty()) throw new Exception("Unknown group column: " + String.join(", ", missing));
            res.grouped = true;
            int[] gi = new int[spec.groupBy.size()];
            for (int i = 0; i < gi.length; i++) gi[i] = out.col(spec.groupBy.get(i));
            TreeMap<List<String>, List<Integer>> groups = new TreeMap<>((x, y) -> {
                for (int i = 0; i < x.size(); i++) { int c = x.get(i).compareTo(y.get(i)); if (c != 0) return c; }
                return 0;
            });
            for (int r = 0; r < out.rows.size(); r++) {
                List<String> key = new ArrayList<>();
                for (int g : gi) { Object v = out.rows.get(r)[g]; key.add(v == null ? "(blank)" : out.str(g, v)); }
                groups.computeIfAbsent(key, k -> new ArrayList<>()).add(r);
            }
            for (String g : spec.groupBy) res.headers.add(pretty(g));
            res.headers.add("Records");
            List<Measure> ms = new ArrayList<>();
            for (Measure m : spec.measures) {
                if (m.column == null || m.column.isEmpty() || out.col(m.column) < 0 || !Arrays.asList(AGGS).contains(m.agg)) continue;
                ms.add(m);
                res.headers.add(aggLabel(m.agg) + " of " + pretty(m.column));
            }
            for (Map.Entry<List<String>, List<Integer>> e : groups.entrySet()) {
                Object[] line = new Object[res.headers.size()];
                int k = 0;
                for (String s : e.getKey()) line[k++] = s;
                line[k++] = (long) e.getValue().size();
                for (Measure m : ms) line[k++] = aggregate(out, out.col(m.column), m.agg, e.getValue());
                res.rows.add(line);
                res.ids.add(null);
                res.raw.add(null);
            }
        } else {
            List<String> cols = new ArrayList<>();
            for (String c : spec.columns.isEmpty() ? out.columns : spec.columns) if (out.col(c) >= 0) cols.add(c);
            for (String c : cols) res.headers.add(pretty(c));
            for (int r = 0; r < out.rows.size(); r++) {
                Object[] line = new Object[cols.size()];
                for (int i = 0; i < cols.size(); i++) line[i] = out.rows.get(r)[out.col(cols.get(i))];
                res.rows.add(line);
                res.ids.add(out.ids.get(r));
                res.raw.add(out.raw.get(r));
            }
        }
        if (!spec.sortBy.isEmpty()) {
            String key = res.headers.contains(spec.sortBy) ? spec.sortBy : pretty(spec.sortBy);
            int c = res.headers.indexOf(key);
            if (c >= 0) sort(res, c, spec.descending);
        }
        if (spec.limit > 0 && res.rows.size() > spec.limit) {
            res.rows.subList(spec.limit, res.rows.size()).clear();
            res.ids.subList(spec.limit, res.ids.size()).clear();
            res.raw.subList(spec.limit, res.raw.size()).clear();
        }
        return res;
    }

    private static Object aggregate(Frame f, int c, String agg, List<Integer> idx) {
        switch (agg) {
            case "count": { long n = 0; for (int i : idx) if (f.rows.get(i)[c] != null) n++; return n; }
            case "nunique": { Set<String> s = new HashSet<>(); for (int i : idx) { Object v = f.rows.get(i)[c]; if (v != null) s.add(f.str(c, v)); } return (long) s.size(); }
            default: {
                double sum = 0, min = Double.NaN, max = Double.NaN; int n = 0;
                for (int i : idx) {
                    Double v = number(f.rows.get(i)[c]);
                    if (v == null) continue;
                    sum += v; n++;
                    min = Double.isNaN(min) ? v : Math.min(min, v);
                    max = Double.isNaN(max) ? v : Math.max(max, v);
                }
                switch (agg) {
                    case "sum": return sum;
                    case "mean": return n == 0 ? null : sum / n;
                    case "min": return n == 0 ? null : min;
                    default: return n == 0 ? null : max;
                }
            }
        }
    }

    private static void sort(Result res, int c, boolean desc) {
        int n = res.rows.size(), numeric = 0;
        for (Object[] r : res.rows) if (number(r[c]) != null) numeric++;
        boolean byNumber = numeric >= Math.max(1, n / 2);
        Integer[] order = new Integer[n];
        for (int i = 0; i < n; i++) order[i] = i;
        Comparator<Integer> cmp;
        if (byNumber) {
            cmp = (x, y) -> {
                Double a = number(res.rows.get(x)[c]), b = number(res.rows.get(y)[c]);
                if (a == null && b == null) return 0;
                if (a == null) return 1;            // na_position="last"
                if (b == null) return -1;
                return desc ? Double.compare(b, a) : Double.compare(a, b);
            };
        } else {
            cmp = (x, y) -> {
                String a = GenUtil.py(res.rows.get(x)[c]).toLowerCase(Locale.ROOT), b = GenUtil.py(res.rows.get(y)[c]).toLowerCase(Locale.ROOT);
                return desc ? b.compareTo(a) : a.compareTo(b);
            };
        }
        Arrays.sort(order, cmp);
        List<Object[]> rows = new ArrayList<>(); List<String> ids = new ArrayList<>(); List<JSONObject> raw = new ArrayList<>();
        for (int i : order) { rows.add(res.rows.get(i)); ids.add(res.ids.get(i)); raw.add(res.raw.get(i)); }
        res.rows.clear(); res.rows.addAll(rows);
        res.ids.clear(); res.ids.addAll(ids);
        res.raw.clear(); res.raw.addAll(raw);
    }

    /** Text shown in a grid cell / CSV. */
    static String cell(Object v) {
        if (v == null) return "";
        if (v instanceof Double || v instanceof Float) { double d = ((Number) v).doubleValue(); return Double.isNaN(d) ? "" : GenUtil.cell(d); }
        if (v instanceof Boolean) return ((Boolean) v) ? "True" : "False";
        return String.valueOf(v);
    }

    static List<String[]> cells(List<Object[]> rows) {
        List<String[]> out = new ArrayList<>();
        for (Object[] r : rows) { String[] s = new String[r.length]; for (int i = 0; i < r.length; i++) s[i] = cell(r[i]); out.add(s); }
        return out;
    }

    /** Chart of the website: x = first column, y = last column with numbers, first 40 rows. Null when no numeric column. */
    static GenKpi.Chart chart(Result res, String kind, String title) {
        if (kind == null || kind.isEmpty() || res.headers.size() < 2 || res.rows.isEmpty()) return null;
        int y = -1;
        for (int c = 1; c < res.headers.size(); c++) for (Object[] r : res.rows) if (number(r[c]) != null) { y = c; break; }
        if (y < 0) return null;
        GenKpi.Chart ch = new GenKpi.Chart(title, kind, "");
        int n = Math.min(40, res.rows.size());
        double[] v = new double[n];
        for (int i = 0; i < n; i++) {
            ch.cats.add(cell(res.rows.get(i)[0]));
            Double d = number(res.rows.get(i)[y]);
            v[i] = d == null ? Double.NaN : d;
        }
        ch.series.put("", v);
        return ch;
    }

    // ------------------------------------------------------------------ saved reports (master_value_catalog)
    static final class Saved {
        final String id, name, owner; final Spec spec;
        Saved(String id, String name, String owner, Spec spec) { this.id = id; this.name = name; this.owner = owner; this.spec = spec; }
    }

    static List<Saved> saved(Api api) {
        List<Saved> out = new ArrayList<>();
        try {
            for (JSONObject row : GenUtil.big(api, "master_value_catalog?select=*&field_key=eq." + Api.enc(SAVED_KEY) + "&status=eq.ACTIVE&order=last_used_at.desc&limit=500")) {
                try {
                    String text = GenUtil.str(row.opt("value_text"));
                    JSONObject p = new JSONObject(text.isEmpty() ? "{}" : text);
                    String name = GenUtil.str(p.opt("name"));
                    out.add(new Saved(GenUtil.str(row.opt("id")), name.isEmpty() ? "Report" : name, GenUtil.str(p.opt("owner")), Spec.from(p.optJSONObject("spec"))));
                } catch (Exception ignored) { }
            }
        } catch (Exception ignored) { }
        return out;
    }

    static JSONObject save(Api api, String name, Spec spec, String owner, String existingId) throws Exception {
        String n = name == null ? "" : name.trim();
        if (n.isEmpty()) throw new Exception("Enter a report name.");
        String now = OffsetDateTime.now(ZoneOffset.UTC).toString();
        String norm = n.toLowerCase(Locale.ROOT);
        JSONObject payload = new JSONObject();
        payload.put("field_key", SAVED_KEY);
        payload.put("value_text", new JSONObject().put("name", n).put("owner", owner).put("spec", spec.json()).toString());
        payload.put("normalized_value", norm.length() > 200 ? norm.substring(0, 200) : norm);
        payload.put("status", "ACTIVE");
        payload.put("last_used_at", now);
        payload.put("updated_at", now);
        if (existingId != null && !existingId.isEmpty()) return api.update("master_value_catalog", existingId, payload);
        return api.insert("master_value_catalog", payload);
    }

    static void delete(Api api, String id) throws Exception {
        api.update("master_value_catalog", id, new JSONObject().put("status", "INACTIVE").put("updated_at", OffsetDateTime.now(ZoneOffset.UTC).toString()));
    }
}
