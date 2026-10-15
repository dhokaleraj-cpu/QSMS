package com.fourstar.qcmsapp;

import android.widget.Button;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Part Master section H · Metallurgical requirements, final dispatch only (part_metallurgical_requirements):
 * matched to the ACTIVE rows by parameter name (case ignored), TEXT needs a text spec (min / max cleared),
 * NUMBER needs min or max and min ≤ max, names unique in the grid; then
 * qsms_generate_final_metallurgical_layout(p_part_id) creates / updates the Final MetLAB layout.
 */
public final class MstPartMetScreen extends MstPartGrid {
    private List<JSONObject> activeRows = new ArrayList<>();

    public MstPartMetScreen(MainActivity a, JSONObject part) { super(a, part); }

    @Override protected String heading() { return "Metallurgical requirements"; }
    @Override protected String table() { return "part_metallurgical_requirements"; }
    @Override protected String saveLabel() { return "Save Metallurgical Requirements"; }
    @Override protected String note() {
        return "Controlled ONLY for the Final MetLAB report used for customer dispatch. Not used for Raw Material Inward MetLAB inspection "
            + "(that uses an approved Layout Master MetLAB layout).";
    }

    @Override
    protected List<JSONObject> load() throws Exception {
        activeRows = list(api.rows("part_metallurgical_requirements?select=*&part_id=eq." + Api.enc(partId) + "&status=eq.ACTIVE&order=sequence_no.asc&limit=500"));
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject r : activeRows) {
            JSONObject c = MstSave.copy(r);
            String t = Lookups.j(c, "characteristic_type").toUpperCase(Locale.ROOT);
            c.put("characteristic_type", t.equals("TEXT") || t.equals("ATTRIBUTE") ? "TEXT" : "NUMBER");
            rows.add(c);
        }
        return rows;
    }

    @Override protected JSONObject template() {
        try { return new JSONObject().put("characteristic_type", "NUMBER"); } catch (Exception e) { return null; }
    }

    @Override
    protected List<Field> fields() {
        List<Field> f = new ArrayList<>();
        f.add(Field.text("parameter_name", "Parameter").req());
        f.add(Field.select("characteristic_type", "Type", "NUMBER", "TEXT").req().def("NUMBER"));
        f.add(Field.text("specification_text", "Text Specification").hint("Required for TEXT parameters. Actual text passes at 75% or greater similarity."));
        f.add(Field.number("minimum_spec", "Minimum Specification"));
        f.add(Field.number("maximum_spec", "Maximum Specification"));
        return f;
    }

    @Override
    protected List<String[]> columns() {
        return cols("parameter_name", "Parameter", "characteristic_type", "Type", "specification_text", "Text Specification",
            "minimum_spec", "Minimum Specification", "maximum_spec", "Maximum Specification");
    }

    @Override
    protected String check(JSONObject row) { return problem(row); }

    static String problem(JSONObject row) {
        String parameter = Lookups.j(row, "parameter_name").trim();
        if (parameter.isEmpty()) return null;
        String type = Lookups.j(row, "characteristic_type").toUpperCase(Locale.ROOT);
        if ("TEXT".equals(type)) {
            if (Lookups.j(row, "specification_text").trim().isEmpty()) return "Enter Text Specification for " + parameter + ".";
            return null;
        }
        Double lo = MstSave.dbl(row.opt("minimum_spec")), hi = MstSave.dbl(row.opt("maximum_spec"));
        if (lo == null && hi == null) return "Enter Minimum or Maximum Specification for " + parameter + ".";
        if (lo != null && hi != null && lo > hi) return parameter + ": Minimum Specification exceeds Maximum Specification.";
        return null;
    }

    @Override
    protected String store(List<JSONObject> rows) throws Exception {
        Map<String, JSONObject> existing = new HashMap<>();
        for (JSONObject r : list(new JSONArray(api.get("part_metallurgical_requirements?select=*&part_id=eq." + Api.enc(partId) + "&status=eq.ACTIVE&limit=500", false).body)))
            existing.put(Lookups.j(r, "parameter_name").trim().toLowerCase(Locale.ROOT), r);
        Set<String> seen = new HashSet<>();
        List<Object[]> writes = new ArrayList<>();
        for (int index = 0; index < rows.size(); index++) {
            JSONObject row = rows.get(index);
            String parameter = Lookups.j(row, "parameter_name").trim();
            if (parameter.isEmpty()) continue;
            String key = parameter.toLowerCase(Locale.ROOT);
            if (!seen.add(key)) throw new Api.ApiException(422, "Duplicate Metallurgical Parameter: " + parameter);
            String p = problem(row);
            if (p != null) throw new Api.ApiException(422, p);
            String type = "TEXT".equalsIgnoreCase(Lookups.j(row, "characteristic_type")) ? "TEXT" : "NUMBER";
            String text = Lookups.j(row, "specification_text").trim();
            Double lo = MstSave.dbl(row.opt("minimum_spec")), hi = MstSave.dbl(row.opt("maximum_spec"));
            if ("TEXT".equals(type)) { lo = null; hi = null; }
            JSONObject payload = new JSONObject();
            payload.put("part_id", partId);
            payload.put("parameter_name", parameter);
            payload.put("characteristic_type", type);
            payload.put("specification_text", text.isEmpty() ? JSONObject.NULL : text);
            payload.put("minimum_spec", lo == null ? JSONObject.NULL : lo);
            payload.put("maximum_spec", hi == null ? JSONObject.NULL : hi);
            payload.put("sequence_no", 10 * (index + 1));
            payload.put("status", "ACTIVE");
            writes.add(new Object[]{existing.get(key), payload});
        }
        for (Object[] w : writes) {
            JSONObject match = (JSONObject) w[0];
            if (match != null) api.update("part_metallurgical_requirements", Lookups.j(match, "id"), (JSONObject) w[1]);
            else api.insert("part_metallurgical_requirements", (JSONObject) w[1]);
        }
        return writes.size() + " Metallurgical Requirement(s) saved successfully.";
    }

    @Override
    protected void addExtra(LinearLayout box) {
        Button gen = Ui.outline(a, "Create / Update Final Dispatch Metallurgical Inspection Layout", Ui.TEAL);
        gen.setEnabled(!activeRows.isEmpty());
        if (activeRows.isEmpty()) box.addView(Ui.text(a, "Save at least one requirement to generate the Final MetLAB layout.", 11.5f, Ui.MUTED, false));
        box.addView(gen, Ui.matchWrap(a, 6));
        gen.setOnClickListener(v -> {
            gen.setEnabled(false);
            Api.async(() -> api.rpcValue("qsms_generate_final_metallurgical_layout", new JSONObject().put("p_part_id", partId)), (res, err) -> {
                gen.setEnabled(true);
                if (err != null) { a.toast(Api.message(err)); return; }
                JSONObject r = res instanceof JSONObject ? (JSONObject) res : res instanceof JSONArray ? ((JSONArray) res).optJSONObject(0) : null;
                if (r == null) r = new JSONObject();
                a.toast("Final Metallurgical layout " + Lookups.j(r, "plan_number") + " Rev " + Lookups.j(r, "revision") + " generated with "
                    + r.optInt("characteristics", 0) + " parameter(s).");
            });
        });
    }
}
