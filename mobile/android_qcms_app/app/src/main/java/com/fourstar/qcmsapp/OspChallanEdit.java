package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * R39 · "Correct / Complete challan details" (osp_transactions._render_challan_edit_form): ONE form corrects the
 * Material Out (challan number, dates, quantities, remarks - through the controlled RPCs qcms_update_osp_material_out_group
 * / qcms_update_osp_material_out, _sync_material_out) and its Returnable Delivery Challan (osp_challans + lines).
 * A challan already e-mailed to the vendor or with vendor returns needs the current password.
 */
final class OspChallanEdit extends Screen {
    private final String moId, jobId;
    private OspRecordView.Doc doc;
    private List<JSONObject> branches = new ArrayList<>();
    private JSONObject prices;
    private FormView form;
    private RowsEditor grid;
    private boolean saving;

    OspChallanEdit(MainActivity a, String moId, String jobId) {
        super(a);
        this.moId = moId == null ? "" : moId;
        this.jobId = jobId == null ? "" : jobId;
    }

    @Override public String title() { return doc == null ? "Challan details" : (doc.challan == null ? "Complete challan · " : "Correct challan · ") + doc.number; }
    @Override public String subtitle() { return "Material Out + Returnable Delivery Challan together"; }
    @Override public int tab() { return Catalog.QUALITY; }

    @Override
    public View build() {
        newPage();
        if (doc != null) { render(); return scroll; }
        page.addView(loading());
        Api.async(() -> {
            OspRecordView.Doc d = OspRecordView.load(api, moId.isEmpty() ? null : moId, jobId.isEmpty() ? null : jobId);
            List<JSONObject> b = OspChallan.branches(api);
            JSONObject p = d.challanLines.isEmpty() ? OspChallan.defaultPrices(api, OspChallan.s(d.first, "part_id"), OspChallan.s(d.first, "vendor_id"), OspChallan.s(d.first, "process_id")) : null;
            return new Object[]{d, b, p};
        }, (r, err) -> {
            if (err != null) { page.removeAllViews(); page.addView(error(err, () -> { doc = null; a.rebuild(); })); return; }
            doc = (OspRecordView.Doc) r[0];
            @SuppressWarnings("unchecked") List<JSONObject> b = (List<JSONObject>) r[1];
            branches = b;
            prices = (JSONObject) r[2];
            a.rebuildTitle(this);
            render();
        });
        return scroll;
    }

    private boolean locked() { return doc.challan != null && (!OspChallan.s(doc.challan, "emailed_at").isEmpty() || !doc.returns.isEmpty()); }

    private static String day(String v, String fallback) { return v == null || v.length() < 10 ? fallback : v.substring(0, 10); }

    private void render() {
        page.removeAllViews();
        if (form != null) {   // rebuild after rotation / back: keep the views
            detach(form); detach(grid);
            addAll();
            return;
        }
        JSONObject[] pending = OspChallan.PENDING.get(doc.key());
        JSONObject cd = doc.challan != null ? doc.challan : pending != null ? pending[0] : new JSONObject();
        Map<String, JSONObject> lineByJob = new HashMap<>();
        for (JSONObject l : doc.challanLines) lineByJob.put(OspChallan.s(l, "osp_job_id"), l);
        if (doc.challan == null && pending != null && pending[1] != null) {
            JSONArray pl = pending[1].optJSONArray("lines");
            if (pl != null) for (int i = 0; i < pl.length(); i++) { JSONObject l = pl.optJSONObject(i); if (l != null) lineByJob.put(OspChallan.s(l, "osp_job_id"), l); }
        }
        List<String> bIds = new ArrayList<>(), bNames = new ArrayList<>();
        bIds.add("");
        bNames.add("Default plant");
        String defaultBranch = "";
        for (JSONObject b : branches) {
            bIds.add(OspChallan.s(b, "id"));
            bNames.add(OspChallan.s(b, "branch_name") + " · " + SupPdfKit.first(OspChallan.s(b, "plant_code"), OspChallan.s(b, "branch_code")));
            if (b.optBoolean("is_default", false)) defaultBranch = OspChallan.s(b, "id");
        }
        List<Field> f = new ArrayList<>();
        f.add(Field.text("challan_number", "Challan Number").req());
        f.add(Field.date("challan_date", "Material Out / Challan Date").req());
        f.add(Field.date("delivery_date", "Expected Return / Delivery Date").req());
        f.add(Field.select("branch_id", "Plant / Company Branch", bIds.toArray(new String[0])).labels(bNames.toArray(new String[0])));
        f.add(shipTo());
        f.add(Field.text("user_name", "User"));
        f.add(Field.select("ship_via", "Ship Via", OspChallan.SHIP_VIA_OPTIONS).labels(OspChallan.SHIP_VIA_OPTIONS));
        f.add(Field.select("incoterm", "Incoterm", OspChallan.INCOTERM_OPTIONS).labels(OspChallan.INCOTERM_OPTIONS));
        f.add(Field.select("payment_term", "Payment Term", OspChallan.PAYMENT_TERM_OPTIONS).labels(OspChallan.PAYMENT_TERM_OPTIONS));
        f.add(Field.text("vehicle_number", "Vehicle No"));
        f.add(Field.text("transporter_name", "Transporter"));
        f.add(Field.text("eway_bill_number", "E-way Bill No"));
        f.add(Field.text("reference_details", "Reference Details"));
        f.add(Field.text("old_po_details", "Old PO Details"));
        f.add(Field.text("process_text", "Process To Be Done"));
        f.add(Field.number("shipping_amount", "Shipping (INR)").range(0, Double.MAX_VALUE));
        f.add(Field.number("other_amount", "Other (INR)").range(0, Double.MAX_VALUE));
        f.add(Field.area("remarks", "Remarks (Material Out dispatch remarks = challan remarks)"));
        form = new FormView(a, f);
        JSONObject first = doc.first;
        form.set("challan_number", SupPdfKit.first(OspChallan.s(cd, "challan_number"), OspChallan.s(first, "dispatch_challan")));
        form.set("challan_date", day(SupPdfKit.first(OspChallan.s(first, "dispatch_date"), OspChallan.s(cd, "challan_date")), Ui.today()));
        form.set("delivery_date", day(SupPdfKit.first(OspChallan.s(first, "expected_return_date"), OspChallan.s(cd, "delivery_date")), Ui.today()));
        form.set("branch_id", SupPdfKit.first(OspChallan.s(cd, "branch_id"), defaultBranch));
        form.set("ship_to_party_id", OspChallan.s(cd, "ship_to_party_id"));
        form.set("user_name", SupPdfKit.first(OspChallan.s(cd, "user_name"), api.fullName));
        form.set("ship_via", SupPdfKit.first(OspChallan.s(cd, "ship_via"), OspChallan.SHIP_VIA_OPTIONS[0]));
        form.set("incoterm", SupPdfKit.first(OspChallan.s(cd, "incoterm"), OspChallan.INCOTERM_OPTIONS[0]));
        form.set("payment_term", SupPdfKit.first(OspChallan.s(cd, "payment_term"), OspChallan.PAYMENT_TERM_OPTIONS[0]));
        for (String k : new String[]{"vehicle_number", "transporter_name", "eway_bill_number", "reference_details", "old_po_details"}) form.set(k, OspChallan.s(cd, k));
        form.set("process_text", SupPdfKit.first(OspChallan.s(cd, "process_text"), OspChallan.s(first, "process_name").toUpperCase(Locale.ROOT)));
        form.set("shipping_amount", Ui.num(OspChallan.f(cd, "shipping_amount"), 2).replace(",", ""));
        form.set("other_amount", Ui.num(OspChallan.f(cd, "other_amount"), 2).replace(",", ""));
        form.set("remarks", SupPdfKit.first(OspChallan.s(first, "dispatch_remarks"), OspChallan.s(cd, "remarks")));
        List<JSONObject> rows = new ArrayList<>();
        int i = 0;
        for (JSONObject r : doc.lines) {
            i++;
            JSONObject l = lineByJob.get(OspChallan.s(r, "id"));
            JSONObject row = new JSONObject();
            try {
                row.put("osp_job_id", OspChallan.s(r, "id"));
                int ln = (int) OspChallan.f(r, "material_out_line_no");
                row.put("line_no", ln > 0 ? ln : i);
                row.put("heat_number", OspChallan.s(r, "heat_number"));
                row.put("item_code", SupPdfKit.first(OspChallan.s(l, "item_code"), OspChallan.s(r, "fsi_part_number")));
                row.put("item_description", SupPdfKit.first(OspChallan.s(l, "item_description"), OspChallan.s(r, "part_name")));
                row.put("quantity_dispatched", OspChallan.f(r, "quantity_dispatched"));
                row.put("_original_qty", OspChallan.f(r, "quantity_dispatched"));
                row.put("uom", SupPdfKit.first(OspChallan.s(l, "uom"), OspChallan.s(prices, "uom"), OspChallan.DEFAULT_UOM));
                row.put("unit_price", l != null ? OspChallan.f(l, "unit_price") : OspChallan.f(prices, "unit_price"));
                row.put("gst_percent", l != null ? (l.isNull("gst_percent") ? OspChallan.DEFAULT_GST : OspChallan.f(l, "gst_percent"))
                    : prices != null && prices.has("gst_percent") ? OspChallan.f(prices, "gst_percent") : OspChallan.DEFAULT_GST);
                row.put("batch_code", OspChallan.s(l, "batch_code"));
            } catch (Exception ignored) { }
            rows.add(row);
        }
        grid = new RowsEditor(a, "Challan lines", Arrays.asList(
            Field.info("heat_number", "Heat Number"), Field.text("item_code", "FSI Item #"), Field.text("item_description", "Description"),
            Field.number("quantity_dispatched", "Qty pcs").range(1, Double.MAX_VALUE).req(), Field.text("uom", "UOM"),
            Field.number("unit_price", "Unit Price").range(0, Double.MAX_VALUE), Field.number("gst_percent", "GST %").range(0, 100), Field.text("batch_code", "Batch Code")),
            Arrays.asList(new String[]{"line_no", "Line"}, new String[]{"item_code", "FSI Item #"}, new String[]{"item_description", "Description"}, new String[]{"heat_number", "Heat Number"},
                new String[]{"quantity_dispatched", "Qty pcs"}, new String[]{"uom", "UOM"}, new String[]{"unit_price", "Unit Price"}, new String[]{"gst_percent", "GST %"},
                new String[]{"batch_code", "Batch Code"})).fixedRows();
        grid.setRows(rows);
        addAll();
    }

    private Field shipTo() {
        return Field.lookup("ship_to_party_id", "Ship To (empty = Same as OSP Vendor)", new Field.Lookup("parties", "id,party_code,party_name,party_types,city,status",
            "&status=eq.ACTIVE", "party_name.asc", r -> Lookups.join(Lookups.j(r, "party_code"), Lookups.j(r, "party_name"), Lookups.j(r, "city"))));
    }

    private static void detach(View v) {
        if (v != null && v.getParent() != null) ((android.view.ViewGroup) v.getParent()).removeView(v);
    }

    private void addAll() {
        if (doc.challan == null && OspChallan.PENDING.containsKey(doc.key()))
            add(Ui.chip(a, "Your challan entries from the Material Out are filled in - click Save Challan to retry.", "amber"), 2);
        if (locked()) add(Ui.chip(a, "This challan was e-mailed to the vendor or has vendor returns: saving asks for your current QCMS password.", "amber"), 2);
        LinearLayout card = Ui.card(a);
        card.addView(form);
        add(card, 4);
        add(Ui.label(a, "Challan lines · tap a line to change FSI item, quantity, price, GST or batch code"), 12);
        add(grid, 4);
        add(Ui.text(a, "Quantity / date changes go through the controlled Material Out update (blocked when downstream OSP receipt / inspection genealogy does not permit them). Blank Batch Code prints the FSI batch. No customer details print on the challan.", 11.5f, Ui.MUTED, false), 4);
        Button save = Ui.primary(a, doc.challan == null ? "Save Challan" : "Update Challan");
        save.setOnClickListener(v -> {
            if (locked()) a.confirmPassword("Confirm the challan change with your password", () -> save(save));
            else save(save);
        });
        add(save, 16);
    }

    private void save(Button button) {
        if (saving) return;
        String problem = form.validate();
        if (problem != null) { a.toast(problem); return; }
        JSONObject header = new JSONObject();
        List<JSONObject> lines = new ArrayList<>();
        Map<String, Double> qty = new HashMap<>();
        try {
            for (String k : new String[]{"challan_number", "challan_date", "branch_id", "ship_to_party_id", "user_name", "ship_via", "incoterm", "delivery_date", "payment_term",
                "vehicle_number", "transporter_name", "eway_bill_number", "reference_details", "old_po_details", "process_text", "remarks"}) header.put(k, form.str(k));
            header.put("vendor_id", OspChallan.s(doc.first, "vendor_id"));
            header.put("shipping_amount", OspChallan.f(form.str("shipping_amount")));
            header.put("other_amount", OspChallan.f(form.str("other_amount")));
            for (JSONObject r : grid.rows()) {
                Double q = Rules.number(r.opt("quantity_dispatched"));
                if (q == null || q <= 0) throw new Api.ApiException(422, "Every challan line needs a positive quantity.");
                qty.put(OspChallan.s(r, "osp_job_id"), q);
                JSONObject l = new JSONObject();
                for (String k : new String[]{"osp_job_id", "line_no", "item_code", "item_description", "uom", "batch_code"}) l.put(k, r.opt(k));
                l.put("unit_price", OspChallan.f(r.opt("unit_price")));
                l.put("gst_percent", r.isNull("gst_percent") || OspChallan.s(r, "gst_percent").isEmpty() ? OspChallan.DEFAULT_GST : OspChallan.f(r.opt("gst_percent")));
                lines.add(l);
            }
            OspChallan.cleanHeader(header);
            OspChallan.cleanLines(lines);
        } catch (Exception e) { a.toast(Api.message(e)); return; }
        saving = true;
        button.setEnabled(false);
        String challanId = doc.challan == null ? null : OspChallan.s(doc.challan, "id");
        Api.async(() -> {
            if (OspChallan.duplicateNumber(api, form.str("challan_number"), challanId))
                throw new Api.ApiException(409, "Challan Number " + form.str("challan_number").trim().toUpperCase(Locale.ROOT) + " is already used by another Material Out.");
            String warning = syncMaterialOut(header, qty);
            JSONObject saved = OspChallan.save(api, doc.moId, doc.group() ? null : doc.jobId, header, lines, challanId);
            OspChallan.PENDING.remove(doc.key());
            return "Material Out / Challan " + SupPdfKit.first(OspChallan.s(saved, "challan_number"), form.str("challan_number")) + " saved." + (warning.isEmpty() ? "" : " " + warning);
        }, (msg, err) -> {
            saving = false;
            button.setEnabled(true);
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast(msg);
            a.back();
        });
    }

    /**
     * _sync_material_out: keep osp_jobs equal to the corrected record. Quantity / date failures stop the save; a
     * challan-number / remarks-only failure is reported but the challan is still saved.
     */
    private String syncMaterialOut(JSONObject header, Map<String, Double> qty) throws Exception {
        String number = OspChallan.s(header, "challan_number").toUpperCase(Locale.ROOT);
        String dispatch = OspChallan.s(header, "challan_date"), expected = OspChallan.s(header, "delivery_date"), remarks = OspChallan.s(header, "remarks");
        Set<String> changed = new HashSet<>();
        boolean qtyChanged = false;
        for (JSONObject r : doc.lines) {
            if (!OspChallan.s(r, "dispatch_challan").toUpperCase(Locale.ROOT).equals(number)) changed.add("dispatch_challan");
            if (!day(OspChallan.s(r, "dispatch_date"), "").equals(dispatch)) changed.add("dispatch_date");
            if (!day(OspChallan.s(r, "expected_return_date"), "").equals(expected)) changed.add("expected_return_date");
            if (!OspChallan.s(r, "dispatch_remarks").equals(remarks)) changed.add("remarks");
            Double q = qty.get(OspChallan.s(r, "id"));
            if (q != null && Math.abs(q - OspChallan.f(r, "quantity_dispatched")) > 1e-9) qtyChanged = true;
        }
        if (changed.isEmpty() && !qtyChanged) return "";
        try {
            if (doc.group()) {
                JSONObject h = new JSONObject().put("dispatch_date", dispatch).put("expected_return_date", expected.isEmpty() ? JSONObject.NULL : expected)
                    .put("dispatch_challan", number).put("remarks", remarks);
                JSONArray ls = new JSONArray();
                for (JSONObject r : doc.lines) {
                    Double q = qty.get(OspChallan.s(r, "id"));
                    ls.put(new JSONObject().put("id", OspChallan.s(r, "id")).put("quantity_dispatched", q == null ? OspChallan.f(r, "quantity_dispatched") : q));
                }
                api.rpc("qcms_update_osp_material_out_group", new JSONObject().put("p_material_out_id", doc.moId).put("p_header", h).put("p_lines", ls));
            } else {
                Double q = qty.get(OspChallan.s(doc.first, "id"));
                api.rpc("qcms_update_osp_material_out", new JSONObject().put("p_osp_job_id", OspChallan.s(doc.first, "id")).put("p_dispatch_date", dispatch)
                    .put("p_dispatch_challan", number).put("p_quantity_dispatched", q == null ? OspChallan.f(doc.first, "quantity_dispatched") : q)
                    .put("p_expected_return_date", expected.isEmpty() ? JSONObject.NULL : expected).put("p_remarks", remarks));
            }
            return "Material Out updated.";
        } catch (Exception e) {
            if (qtyChanged || changed.contains("dispatch_date") || changed.contains("expected_return_date")) throw e;
            return "Material Out challan number / remarks could not be updated (" + Api.message(e) + ").";
        }
    }
}
