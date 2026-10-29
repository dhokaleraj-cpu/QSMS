package com.fourstar.qcmsapp;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Part Master · Supplier / FSI Part price history of one Raw Material record (part_supplier_price_history).
 * Rows are written oldest start date first so the database no-overlap rule passes; end date ≥ start date;
 * match key {part_id, supplier_id, raw_material_detail_id, uom, start_date}.
 */
public final class MstPartPriceScreen extends MstPartGrid {
    private final JSONObject raw;
    private final String rawId, supplierId;

    public MstPartPriceScreen(MainActivity a, JSONObject part, JSONObject raw) {
        super(a, part);
        this.raw = raw;
        this.rawId = Lookups.j(raw, "id");
        this.supplierId = Lookups.j(raw, "supplier_id");
    }

    @Override protected String heading() { return "Price history"; }
    @Override protected String table() { return "part_supplier_price_history"; }
    @Override protected String saveLabel() { return "Save Supplier / FSI Part Price History"; }
    @Override protected String note() {
        return "Raw material record: " + rawLabel(raw, part, Lookups.parts())
            + "\nPrices are controlled per Supplier + Raw Material record + UOM. Add a new row with a new Start Date and leave End Date blank: "
            + "QCMS closes the previous open price automatically (End Date = new Start Date - 1).";
    }

    @Override
    protected List<JSONObject> load() throws Exception {
        Lookups.rows(api, SUPPLIERS);
        Lookups.rows(api, GRADES);
        Lookups.rows(api, Lookups.parts());
        List<JSONObject> rows = list(api.rows("part_supplier_price_history?select=*&part_id=eq." + Api.enc(partId) + "&supplier_id=eq." + Api.enc(supplierId)
            + "&raw_material_detail_id=eq." + Api.enc(rawId) + "&order=start_date.asc&limit=500"));
        for (JSONObject r : rows) {
            if (Lookups.j(r, "currency").isEmpty()) r.put("currency", "INR");
            if (Lookups.j(r, "uom").isEmpty()) r.put("uom", "KGS");
            if (Lookups.j(r, "status").isEmpty()) r.put("status", "ACTIVE");
        }
        return rows;
    }

    @Override protected JSONObject template() {
        try { return new JSONObject().put("currency", "INR").put("uom", "KGS").put("status", "ACTIVE").put("start_date", Ui.today()); } catch (Exception e) { return null; }
    }

    @Override
    protected List<Field> fields() {
        List<Field> f = new ArrayList<>();
        f.add(Field.date("start_date", "Start Date").req());
        f.add(Field.date("end_date", "End Date").hint("Leave blank for the current / open-ended price."));
        f.add(Field.number("price", "Basic Rate").req().range(0, 1e12).hint("Controlled supplier basic rate used as the default PO unit price."));
        f.add(Field.number("freight", "Freight").range(0, 1e12));
        f.add(Field.number("tool_cost", "Tool Cost").range(0, 1e12));
        f.add(Field.number("packing_forwarding", "P&F").range(0, 1e12).hint("Packing & Forwarding component."));
        f.add(Field.number("profit", "Profit").range(0, 1e12));
        f.add(Field.number("icc_rejection", "ICC/Rej.").range(0, 1e12).hint("ICC / rejection component."));
        f.add(Field.select("currency", "Currency", "INR", "USD", "EUR", "GBP").req().def("INR"));
        f.add(Field.select("uom", "UOM", "KGS", "NOS", "PCS").req().def("KGS"));
        f.add(Field.text("remarks", "Remark").hint("Reason / commercial note; printed in the PO Price Revision History table."));
        f.add(Field.select("status", "Status", "ACTIVE", "INACTIVE").req().def("ACTIVE"));
        return f;
    }

    @Override
    protected List<String[]> columns() {
        return cols("start_date", "Start Date", "end_date", "End Date", "price", "Basic Rate", "freight", "Freight", "tool_cost", "Tool Cost",
            "packing_forwarding", "P&F", "profit", "Profit", "icc_rejection", "ICC/Rej.", "currency", "Currency", "uom", "UOM", "remarks", "Remark", "status", "Status");
    }

    @Override
    protected String check(JSONObject row) {
        String start = Lookups.j(row, "start_date"), end = Lookups.j(row, "end_date");
        if (!start.isEmpty() && !end.isEmpty() && end.compareTo(start) < 0) return "Price History End Date cannot be earlier than Start Date.";
        return null;
    }

    private static String day(Object v) {
        String t = MstSave.s(v).trim();
        return t.length() >= 10 ? t.substring(0, 10) : t;
    }

    private static Object money(JSONObject row, String key) {
        Double d = MstSave.dbl(row.opt(key));
        return d == null ? JSONObject.NULL : d;
    }

    /**
     * R39 (web R37b core/price_history_service.py): rows are saved BY ROW ID through PriceHistoryPlan - the whole grid is
     * validated first (no partial save), the previous open period is closed automatically and writes are ordered so the
     * database non-overlap guard always passes (editing a Start Date / UOM no longer inserts an overlapping period).
     */
    @Override
    protected String store(List<JSONObject> rows) throws Exception {
        List<JSONObject> edited = new ArrayList<>();
        for (JSONObject row : rows) {
            JSONObject p = new JSONObject();
            p.put("id", Lookups.j(row, "id"));
            p.put("start_date", day(row.opt("start_date")));
            p.put("end_date", day(row.opt("end_date")));
            p.put("price", money(row, "price"));
            for (String k : new String[]{"freight", "tool_cost", "packing_forwarding", "profit", "icc_rejection"}) p.put(k, money(row, k));
            p.put("currency", Lookups.j(row, "currency").isEmpty() ? "INR" : Lookups.j(row, "currency"));
            p.put("uom", Lookups.j(row, "uom").isEmpty() ? "KGS" : Lookups.j(row, "uom"));
            p.put("remarks", Lookups.j(row, "remarks"));
            p.put("status", Lookups.j(row, "status").isEmpty() ? "ACTIVE" : Lookups.j(row, "status"));
            edited.add(p);
        }
        PriceHistoryPlan plan = PriceHistoryPlan.save(api, partId, supplierId, rawId, edited);
        String closed = plan.autoClosed.isEmpty() ? "" : " Previous period closed automatically: " + String.join("; ", plan.autoClosed) + ".";
        return plan.changed() == 0 ? "No price-history change to save." : "Supplier / FSI Part price history saved successfully (" + plan.changed() + " row(s))." + closed;
    }
}
