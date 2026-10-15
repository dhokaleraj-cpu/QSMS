package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Part Master section F · Jominy requirement (part_jominy_requirements): distance from jominy_distances
 * (label shows the mm value = distance_16th × 25.4 / 16, display only), minimum ≤ maximum HRC,
 * match key {part_id, jominy_distance_id}.
 */
public final class MstPartJominyScreen extends MstPartGrid {
    static final Field.Lookup DISTANCES = new Field.Lookup("jominy_distances", "id,distance_label,distance_16th", "&status=eq.ACTIVE", "distance_16th.asc",
        r -> Lookups.j(r, "distance_label") + " · " + Ui.num(r.optDouble("distance_16th", 0) * 25.4 / 16, 2) + " mm");

    public MstPartJominyScreen(MainActivity a, JSONObject part) { super(a, part); }

    @Override protected String heading() { return "Jominy requirements"; }
    @Override protected String table() { return "part_jominy_requirements"; }
    @Override protected String note() { return "Controlled 1/16 inch to millimetre conversion and HRC requirement band."; }

    @Override
    protected List<JSONObject> load() throws Exception {
        JSONArray distances = Lookups.rows(api, DISTANCES);
        List<JSONObject> rows = list(api.rows("part_jominy_requirements?select=*&part_id=eq." + Api.enc(partId) + "&order=sequence_no.asc&limit=100"));
        for (JSONObject r : rows) {
            if (Lookups.j(r, "jominy_distance_id").isEmpty()) {
                for (int i = 0; i < distances.length(); i++) {
                    JSONObject d = distances.optJSONObject(i);
                    if (Lookups.j(d, "distance_label").equals(Lookups.j(r, "distance_label"))) r.put("jominy_distance_id", Lookups.j(d, "id"));
                }
            }
            if (Lookups.j(r, "status").isEmpty()) r.put("status", "ACTIVE");
        }
        return rows;
    }

    @Override
    protected List<Field> fields() {
        List<Field> f = new ArrayList<>();
        f.add(Field.lookup("jominy_distance_id", "Distance (inch)", DISTANCES).req());
        f.add(Field.number("minimum_hrc", "Minimum HRC"));
        f.add(Field.number("maximum_hrc", "Maximum HRC"));
        f.add(Field.select("status", "Status", "ACTIVE", "INACTIVE").req().def("ACTIVE"));
        return f;
    }

    @Override
    protected List<String[]> columns() {
        return cols("jominy_distance_id", "Distance (inch) · MM", "minimum_hrc", "Minimum HRC", "maximum_hrc", "Maximum HRC", "status", "Status");
    }

    @Override
    protected String check(JSONObject row) {
        Double lo = MstSave.dbl(row.opt("minimum_hrc")), hi = MstSave.dbl(row.opt("maximum_hrc"));
        if (lo != null && hi != null && lo > hi) return "Jominy: minimum exceeds maximum.";
        return null;
    }

    @Override
    protected String store(List<JSONObject> rows) throws Exception {
        JSONArray distances = Lookups.rows(api, DISTANCES);
        List<JSONObject> payloads = new ArrayList<>();
        for (int index = 0; index < rows.size(); index++) {
            JSONObject row = rows.get(index);
            String did = Lookups.j(row, "jominy_distance_id");
            if (did.isEmpty()) continue;
            JSONObject distance = null;
            for (int i = 0; i < distances.length(); i++) if (did.equals(Lookups.j(distances.optJSONObject(i), "id"))) distance = distances.optJSONObject(i);
            String label = distance == null ? Lookups.j(row, "distance_label") : Lookups.j(distance, "distance_label");
            if (distance == null) throw new Api.ApiException(422, "Select a valid Jominy distance for " + (label.isEmpty() ? "row " + (index + 1) : label) + ".");
            Double lo = MstSave.dbl(row.opt("minimum_hrc")), hi = MstSave.dbl(row.opt("maximum_hrc"));
            if (lo != null && hi != null && lo > hi) throw new Api.ApiException(422, "Jominy " + label + ": minimum exceeds maximum.");
            JSONObject p = new JSONObject();
            p.put("jominy_distance_id", did);
            p.put("distance_label", label);
            p.put("minimum_hrc", lo == null ? JSONObject.NULL : lo);
            p.put("maximum_hrc", hi == null ? JSONObject.NULL : hi);
            p.put("sequence_no", 10 * (index + 1));
            p.put("status", Lookups.j(row, "status").isEmpty() ? "ACTIVE" : Lookups.j(row, "status"));
            payloads.add(p);
        }
        MstSave.saveRows(api, "part_jominy_requirements", partId, payloads, "jominy_distance_id");
        return "Jominy Requirements saved successfully.";
    }
}
