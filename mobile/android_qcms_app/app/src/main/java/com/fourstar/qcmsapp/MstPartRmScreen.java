package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Part Master section E · Raw material details / forging parameters (part_raw_material_details) with the
 * website rules: controlled Raw Material Type list, input weight > 0, linked source part (Forging / Casting
 * only, not this part, ACTIVE, own Section E, current supplier approval) whose INHERITED_FIELDS come from the
 * source's newest ACTIVE row, and the R28 match key {part_id, supplier, grade, type, section, route}.
 */
public final class MstPartRmScreen extends MstPartGrid {
    static final String[] TYPES = {"Forging", "Round Black Bar", "Casting", "Bright Bar", "Ground Bar"};
    /** core/raw_source.py INHERITED_FIELDS. */
    static final String[] INHERITED = {"supplier_id", "material_grade_id", "supplier_rm_item_code", "supplier_forging_part_number", "hsn_sac_code",
        "lead_time_days", "forging_weight_kg", "gross_weight_kg", "input_weight_kg", "section_size", "forging_route"};

    private final Field.Lookup sourceParts;
    private String[] typeOptions = TYPES;
    private Set<String> ownIds = new HashSet<>();

    public MstPartRmScreen(MainActivity a, JSONObject part) {
        super(a, part);
        sourceParts = Lookups.parts().where("&id=neq." + partId);
    }

    @Override protected String heading() { return "Raw material details"; }
    @Override protected String table() { return "part_raw_material_details"; }
    @Override protected String note() {
        return "Raw Material Type is controlled to: Forging, Round Black Bar, Casting, Bright Bar and Ground Bar. For Forging/Casting you may link another "
            + "Part Master as the common raw forging/casting source; linked rows inherit the current Section E values of that raw part when you save.";
    }

    @Override
    protected List<JSONObject> load() throws Exception {
        Lookups.rows(api, SUPPLIERS);
        Lookups.rows(api, GRADES);
        Lookups.rows(api, sourceParts);
        JSONArray raw = api.rows("part_raw_material_details?select=*&part_id=eq." + Api.enc(partId) + "&order=sequence_no.asc&limit=200");
        LinkedHashSet<String> types = new LinkedHashSet<>(Arrays.asList(TYPES));
        ownIds = new HashSet<>();
        List<JSONObject> rows = list(raw);
        for (JSONObject r : rows) {
            ownIds.add(Lookups.j(r, "id"));
            String t = Lookups.j(r, "material_section_name").trim();
            if (!t.isEmpty()) types.add(t);
            if (t.isEmpty()) r.put("material_section_name", "Round Black Bar");
            if (Lookups.j(r, "material_grade_id").isEmpty() && !Lookups.j(part, "material_grade_id").isEmpty()) r.put("material_grade_id", Lookups.j(part, "material_grade_id"));
            if (Lookups.j(r, "hsn_sac_code").isEmpty() && !Lookups.j(part, "hsn_sac_code").isEmpty()) r.put("hsn_sac_code", Lookups.j(part, "hsn_sac_code"));
            if (r.isNull("input_weight_kg")) r.put("input_weight_kg", !r.isNull("gross_weight_kg") ? r.opt("gross_weight_kg") : r.opt("forging_weight_kg"));
            if (Lookups.j(r, "status").isEmpty()) r.put("status", "ACTIVE");
        }
        typeOptions = types.toArray(new String[0]);
        return rows;
    }

    @Override
    protected List<Field> fields() {
        List<Field> f = new ArrayList<>();
        f.add(Field.select("material_section_name", "Raw Material Type", typeOptions).req().def("Round Black Bar"));
        f.add(Field.lookup("source_part_id", "Source Raw Forging / Casting Part", sourceParts)
            .hint("Forging or Casting only: another Part Master whose common raw forging/casting makes this finished Part. Leave blank for this Part's own source."));
        f.add(Field.lookup("supplier_id", "Supplier Name / Location", SUPPLIERS).req());
        f.add(Field.lookup("material_grade_id", "Material Grade", GRADES).hint("Required unless the row is linked to a source part."));
        f.add(Field.text("supplier_rm_item_code", "Supplier RM Item Code"));
        f.add(Field.text("supplier_forging_part_number", "Supplier Forging Part No."));
        f.add(Field.text("hsn_sac_code", "HSN / SAC Code").hint("Purchase Orders inherit this value; the Part header HSN is only the fallback."));
        f.add(Field.integer("lead_time_days", "Lead Time (Days)").range(0, 100000).def(0));
        f.add(Field.number("forging_weight_kg", "Forging Weight").range(0, 1e9));
        f.add(Field.number("gross_weight_kg", "Gross Weight").range(0, 1e9));
        f.add(Field.number("input_weight_kg", "Input Weight kg/part").hint("Steel input required for one production part (> 0)."));
        f.add(Field.text("section_size", "Section Size"));
        f.add(Field.text("forging_route", "Forging Route"));
        f.add(Field.select("status", "Status", "ACTIVE", "INACTIVE").req().def("ACTIVE"));
        return f;
    }

    @Override
    protected List<String[]> columns() {
        return cols("material_section_name", "Raw Material Type", "source_part_id", "Source Part", "supplier_id", "Supplier",
            "material_grade_id", "Grade", "supplier_rm_item_code", "Supplier RM Item Code", "supplier_forging_part_number", "Supplier Forging Part No.",
            "hsn_sac_code", "HSN / SAC", "lead_time_days", "Lead Time (Days)", "forging_weight_kg", "Forging Weight", "gross_weight_kg", "Gross Weight",
            "input_weight_kg", "Input Weight kg/part", "section_size", "Section Size", "forging_route", "Forging Route", "status", "Status");
    }

    @Override
    protected String check(JSONObject row) {
        String type = Lookups.j(row, "material_section_name").trim();
        String source = Lookups.j(row, "source_part_id");
        if (!source.isEmpty()) {
            if (source.equals(partId)) return "Source Raw Forging / Casting Part must be another Part Master record, not the same finished Part.";
            String k = type.toLowerCase(Locale.ROOT);
            if (!k.equals("forging") && !k.equals("casting")) return "Source Raw Forging / Casting Part can be selected only when Raw Material Type is Forging or Casting.";
            return null;
        }
        if (Lookups.j(row, "material_grade_id").isEmpty()) return "Material Grade is required.";
        Double w = MstSave.dbl(row.opt("input_weight_kg"));
        if (w == null || w <= 0) return "Input Weight kg/part is required (greater than 0).";
        return null;
    }

    /** resolve_raw_source + effective_link (fail closed). */
    static JSONObject resolveSource(Api api, String partId, String sourceId, String supplierId, String type) throws Exception {
        JSONObject source = MstSave.first(new JSONArray(api.get("parts?select=id,part_number,status&id=eq." + Api.enc(sourceId) + "&limit=1", false).body));
        String label = source == null || Lookups.j(source, "part_number").isEmpty() ? sourceId : Lookups.j(source, "part_number");
        if (source == null || !"ACTIVE".equals(Lookups.j(source, "status"))) throw new Api.ApiException(422, "Linked raw part " + label + " must be ACTIVE.");
        if (sourceId.equals(partId)) throw new Api.ApiException(422, "A raw source cannot link to itself.");
        String kind = type == null ? "" : type.trim().toLowerCase(Locale.ROOT);
        if (!kind.equals("forging") && !kind.equals("casting")) throw new Api.ApiException(422, "Linked raw sources require Forging or Casting material type.");
        JSONArray rows = new JSONArray(api.get("part_raw_material_details?select=*&part_id=eq." + Api.enc(sourceId) + "&status=eq.ACTIVE&limit=5000", false).body);
        List<JSONObject> match = new ArrayList<>();
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.getJSONObject(i);
            if (!"ACTIVE".equals(Lookups.j(r, "status"))) continue;
            if (supplierId != null && !supplierId.isEmpty() && !supplierId.equals(Lookups.j(r, "supplier_id"))) continue;
            match.add(r);
        }
        if (match.isEmpty()) throw new Api.ApiException(422, "Linked raw part " + label + ": add an ACTIVE Section E row for the selected supplier.");
        match.sort((x, y) -> {
            String ux = Lookups.j(x, "updated_at").isEmpty() ? Lookups.j(x, "created_at") : Lookups.j(x, "updated_at");
            String uy = Lookups.j(y, "updated_at").isEmpty() ? Lookups.j(y, "created_at") : Lookups.j(y, "updated_at");
            int c = uy.compareTo(ux);
            if (c != 0) return c;
            c = Lookups.j(y, "created_at").compareTo(Lookups.j(x, "created_at"));
            return c != 0 ? c : Lookups.j(y, "id").compareTo(Lookups.j(x, "id"));
        });
        JSONObject selected = match.get(0);
        if (!Lookups.j(selected, "source_part_id").isEmpty())
            throw new Api.ApiException(422, "Linked raw part " + label + " must own its Section E details; nested raw-part links are not supported.");
        String today = LocalDate.now().toString();
        JSONArray links = new JSONArray(api.get("part_supplier_links?select=*&part_id=eq." + Api.enc(sourceId) + "&approved=is.true&limit=5000", false).body);
        boolean approved = false;
        for (int i = 0; i < links.length(); i++) {
            JSONObject l = links.getJSONObject(i);
            if (!l.optBoolean("approved", false)) continue;
            String sid = Lookups.j(selected, "supplier_id");
            if (!sid.isEmpty() && !sid.equals(Lookups.j(l, "supplier_id"))) continue;
            String from = Lookups.j(l, "valid_from"), to = Lookups.j(l, "valid_to");
            if (!from.isEmpty() && from.substring(0, Math.min(10, from.length())).compareTo(today) > 0) continue;
            if (!to.isEmpty() && to.substring(0, Math.min(10, to.length())).compareTo(today) < 0) continue;
            approved = true;
        }
        if (!approved) throw new Api.ApiException(422, "Linked raw part " + label + ": supplier approval is missing, expired or not yet valid in Section E.");
        return selected;
    }

    @Override
    protected String store(List<JSONObject> rows) throws Exception {
        // 1) validate + resolve every row first (the website stops on the first problem)
        List<JSONObject> payloads = new ArrayList<>();
        for (int index = 0; index < rows.size(); index++) {
            JSONObject row = rows.get(index);
            String sid = Lookups.j(row, "supplier_id");
            String name = sid.isEmpty() ? "row " + (index + 1) : Lookups.labelOf(SUPPLIERS, sid);
            if (sid.isEmpty()) continue;
            String material = Lookups.j(row, "material_section_name").trim();
            if (material.isEmpty()) material = "Round Black Bar";
            String source = Lookups.j(row, "source_part_id");
            String status = Lookups.j(row, "status").isEmpty() ? "ACTIVE" : Lookups.j(row, "status");
            if (!source.isEmpty()) {
                if (source.equals(partId)) throw new Api.ApiException(422, "Source Raw Forging / Casting Part must be another Part Master record, not the same finished Part.");
                String k = material.toLowerCase(Locale.ROOT);
                if (!k.equals("forging") && !k.equals("casting")) throw new Api.ApiException(422, "Source Raw Forging / Casting Part can be selected only when Raw Material Type is Forging or Casting.");
                JSONObject live = resolveSource(api, partId, source, sid, material);
                JSONObject p = new JSONObject();
                String rowId = Lookups.j(row, "id");
                if (!rowId.isEmpty() && ownIds.contains(rowId)) p.put("id", rowId);
                for (String f : INHERITED) p.put(f, live.has(f) ? live.opt(f) : JSONObject.NULL);
                if (Lookups.j(p, "material_grade_id").isEmpty()) throw new Api.ApiException(422, "Material Grade is required for " + name + ".");
                Double w = MstSave.dbl(p.opt("input_weight_kg"));
                if (w == null || w <= 0) throw new Api.ApiException(422, "Input Weight kg/part is required for " + name + ".");
                p.put("material_section_name", material);
                p.put("source_part_id", source);
                p.put("sequence_no", 10 * (index + 1));
                p.put("status", status);
                payloads.add(p);
                continue;
            }
            String grade = Lookups.j(row, "material_grade_id");
            if (grade.isEmpty()) throw new Api.ApiException(422, "Material Grade is required for " + name + ".");
            Double input = MstSave.dbl(row.opt("input_weight_kg"));
            if (input == null || input <= 0) throw new Api.ApiException(422, "Input Weight kg/part is required for " + name + ".");
            Double forging = MstSave.dbl(row.opt("forging_weight_kg")), gross = MstSave.dbl(row.opt("gross_weight_kg"));
            Long lead = MstSave.lng(row.opt("lead_time_days"));
            JSONObject p = new JSONObject();          // own-source rows never send id: match key decides (website)
            p.put("supplier_id", sid);
            p.put("material_grade_id", grade);
            p.put("source_part_id", JSONObject.NULL);
            p.put("supplier_rm_item_code", MstSave.orNull(Lookups.j(row, "supplier_rm_item_code")));
            p.put("supplier_forging_part_number", MstSave.orNull(Lookups.j(row, "supplier_forging_part_number")));
            p.put("hsn_sac_code", MstSave.orNull(Lookups.j(row, "hsn_sac_code")));
            p.put("lead_time_days", lead == null ? 0 : lead);
            p.put("material_section_name", material);
            p.put("forging_weight_kg", forging == null ? JSONObject.NULL : forging);
            p.put("gross_weight_kg", gross == null ? JSONObject.NULL : gross);
            p.put("input_weight_kg", input);
            p.put("section_size", MstSave.orNull(Lookups.j(row, "section_size")));
            p.put("forging_route", MstSave.orNull(Lookups.j(row, "forging_route")));
            p.put("sequence_no", 10 * (index + 1));
            p.put("status", status);
            payloads.add(p);
        }
        // 2) write (R28: lookups always scoped to this part)
        int n = MstSave.saveRows(api, "part_raw_material_details", partId, payloads,
            "supplier_id", "material_grade_id", "material_section_name", "section_size", "forging_route");
        return "Raw Material Details saved successfully (" + n + " row(s)).";
    }
}
