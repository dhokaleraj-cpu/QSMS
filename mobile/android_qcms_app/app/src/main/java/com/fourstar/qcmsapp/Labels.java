package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/** Turns foreign-key ids into readable labels (Part number, supplier name, employee …) in batches. */
public final class Labels {
    private Labels() { }

    private static final Map<String, Map<String, String>> CACHE = new HashMap<>();

    public static String refTable(String table, String column) {
        Map<String, String> fk = Schema.FK.get(table);
        String ref = fk == null ? null : fk.get(column);
        if (ref != null) return ref;
        // common names used by views and older tables
        switch (column) {
            case "part_id": case "source_part_id": return "parts";
            case "supplier_id": case "customer_id": case "steel_mill_id": case "vendor_id": case "party_id": case "osp_vendor_id":
            case "forging_supplier_id": case "rm_supplier_id": case "location_party_id": case "ship_to_party_id": return "parties";
            case "process_id": return "processes";
            case "material_grade_id": return "material_grades";
            case "inspection_stage_id": return "inspection_stages";
            case "customer_order_id": return "supply_customer_orders";
            case "purchase_order_id": return "supply_purchase_orders";
            case "inward_lot_id": return "inward_lots";
            case "asset_id": case "instrument_asset_id": return "quality_assets";
            case "company_branch_id": return "company_branches";
            default:
                if (column.endsWith("employee_id")) return "employees";
                return null;
        }
    }

    public static String label(String refTable, JSONObject row) {
        String[] cols = Schema.LABEL.get(refTable);
        if (cols == null) cols = new String[]{"name"};
        StringBuilder b = new StringBuilder();
        for (String c : cols) {
            String v = Lookups.j(row, c);
            if (v.isEmpty() || "id".equals(c)) continue;
            if (b.length() > 0) b.append(" · ");
            b.append(v);
        }
        return b.length() == 0 ? Lookups.j(row, "id") : b.toString();
    }

    /** Load labels for ids of one referenced table (background thread). */
    public static Map<String, String> load(Api api, String refTable, Set<String> ids) throws Exception {
        Map<String, String> cache = CACHE.get(refTable);
        if (cache == null) { cache = new HashMap<>(); CACHE.put(refTable, cache); }
        List<String> missing = new ArrayList<>();
        for (String id : ids) if (id != null && !id.isEmpty() && !"null".equals(id) && !cache.containsKey(id)) missing.add(id);
        String[] cols = Schema.LABEL.get(refTable);
        StringBuilder select = new StringBuilder("id");
        if (cols != null) for (String c : cols) if (!"id".equals(c)) select.append(',').append(c);
        for (int start = 0; start < missing.size(); start += 80) {
            List<String> part = missing.subList(start, Math.min(missing.size(), start + 80));
            JSONArray rows;
            try {
                rows = api.rows(refTable + "?select=" + select + "&id=in.(" + String.join(",", part) + ")");
            } catch (Exception e) {
                rows = new JSONArray();
            }
            for (int i = 0; i < rows.length(); i++) {
                JSONObject r = rows.optJSONObject(i);
                if (r != null) cache.put(r.optString("id"), label(refTable, r));
            }
        }
        return cache;
    }

    /** Resolve every FK column of these rows; returns column -> (id -> label). */
    public static Map<String, Map<String, String>> resolve(Api api, String table, JSONArray rows, List<String> columns) throws Exception {
        Map<String, Map<String, String>> out = new HashMap<>();
        Map<String, Set<String>> wanted = new HashMap<>();
        for (String col : columns) {
            String ref = refTable(table, col);
            if (ref == null) continue;
            Set<String> ids = new HashSet<>();
            for (int i = 0; i < rows.length(); i++) {
                JSONObject r = rows.optJSONObject(i);
                if (r != null) ids.add(Lookups.j(r, col));
            }
            wanted.put(col, ids);
        }
        for (Map.Entry<String, Set<String>> e : wanted.entrySet()) {
            out.put(e.getKey(), load(api, refTable(table, e.getKey()), e.getValue()));
        }
        return out;
    }

    public static void clear() { CACHE.clear(); }

    /** Display text for one cell. */
    public static String cell(String column, Object value, Map<String, String> fk) {
        if (value == null || value == JSONObject.NULL) return "";
        String s = String.valueOf(value);
        if ("null".equals(s)) return "";
        if (fk != null) {
            String l = fk.get(s);
            return l == null ? s : l;
        }
        String c = column.toLowerCase(Locale.ROOT);
        if (value instanceof Boolean) return (Boolean) value ? "Yes" : "No";
        if (value instanceof JSONArray) {
            JSONArray a = (JSONArray) value;
            StringBuilder b = new StringBuilder();
            for (int i = 0; i < a.length(); i++) {
                Object o = a.opt(i);
                if (o instanceof JSONObject) continue;
                if (b.length() > 0) b.append(", ");
                b.append(Ui.pretty(String.valueOf(o)));
            }
            return b.length() == 0 ? (a.length() + " item(s)") : b.toString();
        }
        if (value instanceof JSONObject) return ((JSONObject) value).length() + " field(s)";
        if ((c.endsWith("_date") || c.endsWith("_at") || c.equals("date")) && s.length() >= 10 && s.charAt(4) == '-') return Ui.date(s);
        if (value instanceof Number) return Ui.num(((Number) value).doubleValue(), 3);
        if (c.contains("status") || c.contains("disposition") || c.equals("result") || c.endsWith("_type") || c.endsWith("_result")) return Ui.pretty(s);
        return s;
    }

    /** Readable column name: part_id -> Part, inward_date -> Inward Date. */
    public static String header(String column) {
        String c = column;
        if (c.endsWith("_employee_id")) c = c.substring(0, c.length() - "_employee_id".length());
        else if (c.endsWith("_id")) c = c.substring(0, c.length() - 3);
        String p = Ui.pretty(c);
        return p.replace("Qty", "Qty").replace("Kg", "kg").replace("Pcs", "pcs").replace("Fsi", "FSI").replace("Rm ", "RM ").replace("Po ", "PO ").replace("Hsn", "HSN").replace("Osp", "OSP").replace("Rmtc", "RMTC").replace("Grn", "GRN");
    }
}
