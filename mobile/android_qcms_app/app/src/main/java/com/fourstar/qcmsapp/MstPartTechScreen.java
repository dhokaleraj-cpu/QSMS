package com.fourstar.qcmsapp;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Part Master · Supplier technical data of one Raw Material record (part_raw_material_technical_data):
 * heading + value both required, match key {part_id, raw_material_detail_id, heading}. Active rows are copied
 * to Purchase Orders automatically. Section permission PART_MASTER / SUPPLIER_TECHNICAL is enforced by the server.
 */
public final class MstPartTechScreen extends MstPartGrid {
    private final JSONObject raw;
    private final String rawId;

    public MstPartTechScreen(MainActivity a, JSONObject part, JSONObject raw) {
        super(a, part);
        this.raw = raw;
        this.rawId = Lookups.j(raw, "id");
    }

    @Override protected String heading() { return "Supplier technical data"; }
    @Override protected String table() { return "part_raw_material_technical_data"; }
    @Override protected String saveLabel() { return "Save Supplier Technical Data"; }
    @Override protected String note() {
        return "Raw material record: " + rawLabel(raw, part, Lookups.parts())
            + "\nHeading / value rows (e.g. RM May'26, Tool Cost, Heat Treatment Condition). Active rows populate Purchase Orders automatically.";
    }

    @Override
    protected List<JSONObject> load() throws Exception {
        Lookups.rows(api, SUPPLIERS);
        Lookups.rows(api, GRADES);
        Lookups.rows(api, Lookups.parts());
        List<JSONObject> rows = list(api.rows("part_raw_material_technical_data?select=*&raw_material_detail_id=eq." + Api.enc(rawId) + "&order=sequence_no.asc&limit=500"));
        for (JSONObject r : rows) {
            if (r.isNull("include_on_po")) r.put("include_on_po", true);
            if (Lookups.j(r, "sequence_no").isEmpty()) r.put("sequence_no", 10);
            if (Lookups.j(r, "status").isEmpty()) r.put("status", "ACTIVE");
        }
        return rows;
    }

    @Override
    protected List<Field> fields() {
        List<Field> f = new ArrayList<>();
        f.add(Field.text("heading", "Heading").req().hint("Example: RM May'26, Tool Cost, Profit, Rej + ICC, Packaging"));
        f.add(Field.text("value_text", "Value").req());
        f.add(Field.bool("include_on_po", "Include on PO").def(true));
        f.add(Field.integer("sequence_no", "Sequence").range(1, 1e9));
        f.add(Field.select("status", "Status", "ACTIVE", "INACTIVE").req().def("ACTIVE"));
        return f;
    }

    @Override
    protected List<String[]> columns() {
        return cols("heading", "Heading", "value_text", "Value", "include_on_po", "Include on PO", "sequence_no", "Sequence", "status", "Status");
    }

    @Override
    protected String store(List<JSONObject> rows) throws Exception {
        String supplierId = Lookups.j(raw, "supplier_id");
        List<JSONObject> payloads = new ArrayList<>();
        for (int index = 0; index < rows.size(); index++) {
            JSONObject row = rows.get(index);
            String heading = Lookups.j(row, "heading").trim(), value = Lookups.j(row, "value_text").trim();
            if (heading.isEmpty() && value.isEmpty()) continue;
            if (heading.isEmpty() || value.isEmpty()) throw new Api.ApiException(422, "Both Technical Data Heading and Value are required.");
            Long seq = MstSave.lng(row.opt("sequence_no"));
            JSONObject p = new JSONObject();       // website grid carries no row id: match key decides
            p.put("raw_material_detail_id", rawId);
            p.put("supplier_id", supplierId);
            p.put("heading", heading);
            p.put("value_text", value);
            p.put("include_on_po", row.isNull("include_on_po") || row.optBoolean("include_on_po", true));
            p.put("sequence_no", seq == null || seq == 0 ? (index + 1) * 10 : seq);
            p.put("status", Lookups.j(row, "status").isEmpty() ? "ACTIVE" : Lookups.j(row, "status"));
            payloads.add(p);
        }
        MstSave.saveRows(api, "part_raw_material_technical_data", partId, payloads, "raw_material_detail_id", "heading");
        return "Supplier technical data saved. Active rows will populate Purchase Orders automatically.";
    }
}
