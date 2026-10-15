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

    @Override
    protected String store(List<JSONObject> rows) throws Exception {
        List<JSONObject> sorted = new ArrayList<>(rows);
        sorted.sort((x, y) -> {        // sort_values("Start Date", na_position="last")
            String a1 = day(x.opt("start_date")), b1 = day(y.opt("start_date"));
            if (a1.isEmpty() && b1.isEmpty()) return 0;
            if (a1.isEmpty()) return 1;
            if (b1.isEmpty()) return -1;
            return a1.compareTo(b1);
        });
        List<JSONObject> payloads = new ArrayList<>();
        for (JSONObject row : sorted) {
            String start = day(row.opt("start_date")), end = day(row.opt("end_date"));
            Double price = MstSave.dbl(row.opt("price"));
            if (start.isEmpty() && price == null) continue;
            if (start.isEmpty()) throw new Api.ApiException(422, "Start Date is required for every price-history row.");
            if (!end.isEmpty() && end.compareTo(start) < 0) throw new Api.ApiException(422, "Price History End Date cannot be earlier than Start Date.");
            JSONObject p = new JSONObject();
            p.put("supplier_id", supplierId);
            p.put("raw_material_detail_id", rawId);
            p.put("start_date", start);
            p.put("end_date", end.isEmpty() ? JSONObject.NULL : end);
            p.put("price", price == null ? 0.0 : price);
            p.put("freight", money(row, "freight"));
            p.put("tool_cost", money(row, "tool_cost"));
            p.put("packing_forwarding", money(row, "packing_forwarding"));
            p.put("profit", money(row, "profit"));
            p.put("icc_rejection", money(row, "icc_rejection"));
            p.put("currency", Lookups.j(row, "currency").isEmpty() ? "INR" : Lookups.j(row, "currency"));
            p.put("uom", Lookups.j(row, "uom").isEmpty() ? "KGS" : Lookups.j(row, "uom"));
            p.put("remarks", MstSave.orNull(Lookups.j(row, "remarks")));
            p.put("status", Lookups.j(row, "status").isEmpty() ? "ACTIVE" : Lookups.j(row, "status"));
            payloads.add(p);
        }
        MstSave.saveRows(api, "part_supplier_price_history", partId, payloads, "part_id", "supplier_id", "raw_material_detail_id", "uom", "start_date");
        return "Supplier / FSI Part price history saved successfully.";
    }
}
