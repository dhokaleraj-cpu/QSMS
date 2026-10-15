package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.HashMap;
import java.util.Map;

/** Standard dropdown sources with the same labels as core/selection_labels.py. */
public final class Lookups {
    private Lookups() { }

    private static final Map<String, JSONArray> CACHE = new HashMap<>();
    private static final Map<String, Long> CACHED_AT = new HashMap<>();

    static String j(JSONObject r, String key) {
        String v = r.optString(key, "");
        return "null".equals(v) ? "" : v;
    }

    static String join(String... parts) {
        StringBuilder b = new StringBuilder();
        for (String p : parts) {
            if (p == null || p.trim().isEmpty() || "null".equals(p)) continue;
            if (b.length() > 0) b.append(" · ");
            b.append(p.trim());
        }
        return b.toString();
    }

    public static final Field.Label PART = r -> join(j(r, "part_number"), j(r, "fsi_part_number").isEmpty() ? "" : "FSI " + j(r, "fsi_part_number"), j(r, "part_name"));
    public static final Field.Label PARTY = r -> join(j(r, "party_code"), j(r, "party_name"), j(r, "city"));
    public static final Field.Label EMPLOYEE = r -> join(j(r, "employee_code"), (j(r, "first_name") + " " + j(r, "last_name")).trim(), j(r, "designation"));
    public static final Field.Label PROCESS = r -> join(j(r, "process_code"), j(r, "process_name"), Ui.pretty(j(r, "process_type")));
    public static final Field.Label GRADE = r -> join(j(r, "material_number"), j(r, "grade_code"), j(r, "standard"));
    public static final Field.Label STAGE = r -> join(j(r, "stage_code"), j(r, "stage_name"));
    public static final Field.Label BRANCH = r -> join(j(r, "branch_code"), j(r, "branch_name"), j(r, "city"));
    public static final Field.Label ASSET = r -> join(j(r, "asset_number").isEmpty() ? j(r, "asset_code") : j(r, "asset_number"), j(r, "asset_name"), Ui.pretty(j(r, "asset_type")), j(r, "range_text"));
    public static final Field.Label JOMINY = r -> j(r, "distance_label");
    public static final Field.Label STANDARD = r -> join(j(r, "standard_code"), j(r, "standard_name"), "Rev " + j(r, "revision_number"));

    public static Field.Lookup parts() { return new Field.Lookup("parts", "id,part_number,fsi_part_number,part_name,customer_id,material_grade_id,drawing_number,drawing_revision", "&status=eq.ACTIVE", "part_number.asc", PART); }
    public static Field.Lookup parties(String type) {
        return new Field.Lookup("parties", "id,party_code,party_name,city,state,party_types,email", "&status=eq.ACTIVE" + (type == null ? "" : "&party_types=cs.%7B" + type + "%7D"), "party_name.asc", PARTY);
    }
    public static Field.Lookup customers() { return parties("CUSTOMER"); }
    public static Field.Lookup suppliers() { return parties("SUPPLIER"); }
    public static Field.Lookup steelMills() { return parties("STEEL_MILL"); }
    public static Field.Lookup ospVendors() { return parties("OSP_VENDOR"); }
    public static Field.Lookup employees() { return new Field.Lookup("employees", "id,employee_code,first_name,last_name,designation,department,approval_authorities", "&status=eq.ACTIVE", "employee_code.asc", EMPLOYEE); }
    public static Field.Lookup processes() { return new Field.Lookup("processes", "id,process_code,process_name,process_type", "&status=eq.ACTIVE", "process_code.asc", PROCESS); }
    public static Field.Lookup outsourcedProcesses() { return processes().where("&process_type=eq.OUTSOURCED"); }
    public static Field.Lookup grades() { return new Field.Lookup("material_grades", "id,material_number,grade_code,standard,revision", "&status=eq.ACTIVE", "grade_code.asc", GRADE); }
    public static Field.Lookup stages() { return new Field.Lookup("inspection_stages", "id,stage_code,stage_name,sequence_no", "&status=eq.ACTIVE", "sequence_no.asc", STAGE); }
    public static Field.Lookup branches() { return new Field.Lookup("company_branches", "id,branch_code,branch_name,city", "&status=eq.ACTIVE", "branch_code.asc", BRANCH); }
    public static Field.Lookup assets() { return new Field.Lookup("quality_assets", "id,asset_code,asset_number,asset_name,asset_type,range_text,calibration_frequency_days,validation_frequency_days", "&status=eq.ACTIVE", "asset_name.asc", ASSET); }
    public static Field.Lookup jominy() { return new Field.Lookup("jominy_distances", "id,distance_label,distance_16th", "&status=eq.ACTIVE", "distance_16th.asc", JOMINY); }
    public static Field.Lookup standards() { return new Field.Lookup("customer_standards", "id,standard_code,standard_name,revision_number", "&status=eq.ACTIVE", "standard_code.asc", STANDARD); }

    /** Rows of a lookup (cached for 5 minutes; call on a background thread). */
    public static JSONArray rows(Api api, Field.Lookup l) throws Exception {
        String key = l.key();
        Long at = CACHED_AT.get(key);
        if (at != null && System.currentTimeMillis() - at < 300_000L && CACHE.containsKey(key)) return CACHE.get(key);
        JSONArray data = api.rows(l.table + "?select=" + l.select + l.filter + "&order=" + l.order + "&limit=5000");
        CACHE.put(key, data);
        CACHED_AT.put(key, System.currentTimeMillis());
        return data;
    }

    public static void invalidate() {
        CACHE.clear();
        CACHED_AT.clear();
    }

    /** Label of one id (from cache, else "-"). */
    public static String labelOf(Field.Lookup l, String id) {
        JSONArray data = CACHE.get(l.key());
        if (data == null || id == null) return id == null ? "" : id;
        for (int i = 0; i < data.length(); i++) {
            JSONObject r = data.optJSONObject(i);
            if (r != null && id.equals(r.optString("id"))) return l.label.of(r);
        }
        return id;
    }

    public static JSONObject rowOf(Field.Lookup l, String id) {
        JSONArray data = CACHE.get(l.key());
        if (data == null || id == null) return null;
        for (int i = 0; i < data.length(); i++) {
            JSONObject r = data.optJSONObject(i);
            if (r != null && id.equals(r.optString("id"))) return r;
        }
        return null;
    }
}
