package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Shared helpers of the NPD / APQP, QC tools and Records area (labels like core/selection_labels.py, row delete). */
final class NpdUtil {
    private NpdUtil() { }

    // ------------------------------------------------------------------ labels (core/selection_labels.py)
    /** _clean(): str(value or "").strip() with inner whitespace collapsed. */
    static String clean(Object v) {
        if (v == null || v == JSONObject.NULL) return "";
        String s = String.valueOf(v).trim();
        if ("null".equals(s)) return "";
        return s.replaceAll("\\s+", " ");
    }

    static String join(Object... values) {
        StringBuilder b = new StringBuilder();
        for (Object v : values) {
            String s = clean(v);
            if (s.isEmpty()) continue;
            if (b.length() > 0) b.append(" · ");
            b.append(s);
        }
        return b.toString();
    }

    static String withStatus(String label, JSONObject row) {
        String st = clean(row.opt("status"));
        if (st.isEmpty()) st = clean(row.opt("record_status"));
        String tag = st.isEmpty() ? "" : "[" + st.replace('_', ' ').toUpperCase(Locale.ROOT) + "]";
        if (tag.isEmpty() || label.contains(tag)) return label;
        return label.isEmpty() ? tag : label + " " + tag;
    }

    /** employee_label(): the snapshot text the website stores next to responsible_employee_id. */
    static String employeeLabel(JSONObject r) {
        String name = (clean(r.opt("first_name")) + " " + clean(r.opt("last_name"))).trim();
        return withStatus(join(r.opt("employee_code"), name, r.opt("designation"), r.opt("department"), r.opt("plant")), r);
    }

    static final Field.Label EMPLOYEE = NpdUtil::employeeLabel;

    /** ACTIVE employees ordered by first name (as the NPD pages load them), labelled like the website. */
    static Field.Lookup employees() {
        return new Field.Lookup("employees", "id,employee_code,first_name,last_name,designation,department,plant,status",
            "&status=eq.ACTIVE", "first_name.asc", EMPLOYEE);
    }

    /** Active customers (party_types contains CUSTOMER) ordered by name. */
    static Field.Lookup customers() {
        return new Field.Lookup("parties", "id,party_code,party_name,city,state,country,approval_status,status",
            "&status=eq.ACTIVE&party_types=cs.%7BCUSTOMER%7D", "party_name.asc",
            r -> withStatus(join(r.opt("party_code"), r.opt("party_name"),
                join(r.opt("city"), r.opt("state"), r.opt("country")).replace(" · ", ", "), r.opt("approval_status")), r));
    }

    /** Snapshot for an employee id (label of the cached lookup row), or the legacy text when no employee is chosen. */
    static Object snapshot(Field.Lookup employees, Object employeeId, Object legacy) {
        String id = clean(employeeId);
        if (!id.isEmpty()) {
            JSONObject row = Lookups.rowOf(employees, id);
            return row == null ? (Object) Lookups.labelOf(employees, id) : employeeLabel(row);
        }
        String l = clean(legacy);
        return l.isEmpty() ? JSONObject.NULL : l;
    }

    // ------------------------------------------------------------------ values
    static String s(JSONObject r, String key) { return r == null ? "" : Lookups.j(r, key); }

    static Object orNull(String v) { return v == null || v.trim().isEmpty() ? JSONObject.NULL : v.trim(); }

    static int intOf(Object v, int def) {
        String s = clean(v);
        if (s.isEmpty()) return def;
        try { return (int) Math.round(Double.parseDouble(s.replace(",", ""))); } catch (NumberFormatException e) { return def; }
    }

    static LocalDate date(Object v) {
        String s = clean(v);
        if (s.length() < 10) return null;
        try { return LocalDate.parse(s.substring(0, 10)); } catch (Exception e) { return null; }
    }

    static List<JSONObject> list(JSONArray arr) {
        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; arr != null && i < arr.length(); i++) {
            JSONObject o = arr.optJSONObject(i);
            if (o != null) out.add(o);
        }
        return out;
    }

    static JSONObject copy(JSONObject o) {
        try { return new JSONObject(o.toString()); } catch (Exception e) { return new JSONObject(); }
    }

    // ------------------------------------------------------------------ delete one row (Repository.delete)
    /**
     * DELETE /rest/v1/{table}?id=eq.{id} with the user's token, exactly like Repository.delete on the website
     * (used for child rows the website removes directly: flow steps / checkpoints, APQP gates).
     * The shared Api has no public delete yet, so its authenticated request helper is used.
     */
    static void deleteRow(Api api, String table, String id) throws Exception {
        api.delete(table, id);   // logs the DELETE activity like the website
    }

}
