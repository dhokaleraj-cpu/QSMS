package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;

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

/** Edit Purchase Order (_render_purchase_order_edit + update_purchase_order): returns the PO to PENDING_APPROVAL. */
final class SupPoEditScreen extends SupBase {
    private final String id;
    private JSONObject header;
    private FormView form;
    private RowsEditor allocEditor, itemEditor;
    private List<JSONObject> branches = new ArrayList<>();
    private final Map<String, JSONObject> parties = new HashMap<>();

    SupPoEditScreen(MainActivity a, String id) { super(a); this.id = id; }

    @Override public String title() { return header == null ? "Edit Purchase Order" : "Edit · " + SupSvc.s(header, "po_number"); }
    @Override public String subtitle() { return "Revision returns the PO to approval"; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONObject h = svc.get("supply_purchase_orders", id);
            if (SupSvc.empty(h)) throw new Api.ApiException(404, "Purchase Order was not found.");
            List<JSONObject> items = svc.live("supply_purchase_order_items?select=*&purchase_order_id=eq." + id + "&order=created_at.asc&limit=1000");
            List<JSONObject> sources = svc.live("supply_purchase_order_sources?select=*&purchase_order_id=eq." + id + "&order=created_at.asc&limit=10000");
            Set<String> orderIds = new HashSet<>(), partIds = new HashSet<>();
            for (JSONObject s : sources) orderIds.add(SupSvc.s(s, "customer_order_id"));
            Map<String, JSONObject> orders = svc.byIds("supply_customer_orders", "id,master_reference_no,customer_order_no,part_id", orderIds);
            for (JSONObject o : orders.values()) partIds.add(SupSvc.s(o, "part_id"));
            for (JSONObject i : items) partIds.add(SupSvc.s(i, "part_id"));
            Map<String, JSONObject> parts = svc.byIds("parts", "id,part_number,fsi_part_number", partIds);
            List<JSONObject> br = svc.live("company_branches?select=*&status=eq.ACTIVE&order=branch_code.asc&limit=500");
            List<JSONObject> py = svc.live("parties?select=*&status=eq.ACTIVE&order=party_name.asc&limit=5000");
            JSONObject supplier = svc.get("parties", SupSvc.s(h, "supplier_id"));
            List<JSONObject> srcRows = new ArrayList<>();
            for (JSONObject s : sources) {
                JSONObject item = null;
                for (JSONObject i : items) if (SupSvc.s(i, "id").equals(SupSvc.s(s, "purchase_order_item_id"))) item = i;
                JSONObject o = orders.get(SupSvc.s(s, "customer_order_id"));
                JSONObject part = parts.get(SupSvc.first(SupSvc.s(o, "part_id"), SupSvc.s(item, "part_id")));
                srcRows.add(new JSONObject().put("id", SupSvc.s(s, "id")).put("order", SupSvc.first(SupSvc.s(o, "master_reference_no"), SupSvc.s(o, "customer_order_no")))
                    .put("part", SupSvc.s(part, "part_number")).put("fsi", SupSvc.s(part, "fsi_part_number")).put("allocated_qty", SupSvc.num(s, "allocated_qty"))
                    .put("uom", SupSvc.first(SupSvc.s(s, "allocation_uom"), SupSvc.s(item, "uom"))));
            }
            List<JSONObject> itemRows = new ArrayList<>();
            for (JSONObject i : items) {
                itemRows.add(new JSONObject().put("id", SupSvc.s(i, "id")).put("part", SupSvc.s(parts.get(SupSvc.s(i, "part_id")), "part_number"))
                    .put("item_no", SupSvc.first(SupSvc.s(i, "item_no"), SupSvc.s(i, "fsi_part_number_snapshot"))).put("hsn_sac_code", SupSvc.s(i, "hsn_sac_code"))
                    .put("quantity", SupSvc.num(i, "quantity")).put("uom", SupSvc.s(i, "uom")).put("received", svc.purchaseOrderItemReceivedQty(i, h))
                    .put("unit_price", SupSvc.num(i, "unit_price")).put("gst_percent", SupSvc.num(i, "gst_percent")).put("remarks", SupSvc.s(i, "remarks")));
            }
            return new Object[]{h, srcRows, itemRows, br, py, supplier};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            header = (JSONObject) res[0];
            a.rebuildTitle(this);
            @SuppressWarnings("unchecked") List<JSONObject> srcRows = (List<JSONObject>) res[1];
            @SuppressWarnings("unchecked") List<JSONObject> itemRows = (List<JSONObject>) res[2];
            @SuppressWarnings("unchecked") List<JSONObject> br = (List<JSONObject>) res[3]; branches = br;
            @SuppressWarnings("unchecked") List<JSONObject> py = (List<JSONObject>) res[4];
            for (JSONObject p : py) parties.put(SupSvc.s(p, "id"), p);
            render(srcRows, itemRows, (JSONObject) res[5]);
        });
        return scroll;
    }

    private void render(List<JSONObject> srcRows, List<JSONObject> itemRows, JSONObject supplier) {
        if ("CANCELLED".equalsIgnoreCase(SupSvc.s(header, "status"))) {
            add(Ui.empty(a, "Cancelled POs are not edited. Use Cancel & Reissue to create a replacement PO."), 0);
            return;
        }
        add(infoCard(SupSvc.s(header, "po_number") + " · " + Ui.pretty(SupSvc.s(header, "po_type")), "Supplier: " + SupSvc.partyLabel(supplier),
            "A Supplier change uses Cancel & Reissue (website Order List) so the RM / forging details of the new supplier are applied. Supplier Confirmation never blocks editing."), 0);
        String[] brIds = new String[branches.size()], brLabels = new String[branches.size()];
        for (int i = 0; i < branches.size(); i++) { brIds[i] = SupSvc.s(branches.get(i), "id"); brLabels[i] = Lookups.BRANCH.of(branches.get(i)); }
        String source = SupSvc.first(SupSvc.s(header, "ship_to_source_type"), "BRANCH");
        if (!Arrays.asList(SupPoScreen.SHIP_SOURCES).contains(source)) source = "BRANCH";
        String[] currencies = {"INR", "USD", "EUR", "GBP", "JPY"};
        String cur = SupSvc.first(SupSvc.s(header, "currency"), "INR").toUpperCase(Locale.ROOT);
        if (!Arrays.asList(currencies).contains(cur)) currencies = new String[]{cur, "INR", "USD", "EUR", "GBP", "JPY"};
        List<Field> f = new ArrayList<>();
        f.add(Field.date("order_date", "PO Date").req());
        f.add(Field.date("delivery_date", "Delivery Date"));
        f.add(Field.select("company_branch_id", "Company Branch / Plant", brIds).labels(brLabels).req());
        f.add(Field.select("ship_to_source_type", "Ship-To Source", SupPoScreen.SHIP_SOURCES).labels(SupPoScreen.SHIP_LABELS).req());
        f.add(Field.select("ship_to_id", "Ship-To Master Record").req());
        f.add(Field.bool("refresh_master_data", "Refresh Latest Master Data").hint("Refresh snapshots, HSN, technical data and the current supplier price on save").def(true));
        f.add(Field.text("ship_via", "Ship Via"));
        f.add(Field.text("incoterm", "Incoterm"));
        f.add(Field.text("payment_term", "Payment Term"));
        f.add(Field.date("quotation_date", "Quotation Date"));
        f.add(Field.text("quotation_reference", "Quotation Reference"));
        f.add(Field.text("old_po_reference", "Old PO Details"));
        f.add(Field.select("currency", "Currency", currencies).req());
        f.add(Field.number("other_amount", "Other Charges").range(0, Double.NaN));
        form = new FormView(a, f);
        add(form, 6);
        form.setAll(header);
        form.set("ship_to_source_type", source);
        form.set("currency", cur);
        if (SupSvc.s(header, "special_instructions").isEmpty()) { /* default applied below */ }
        refreshShip(true);
        form.onChange((k, v) -> { if (k.equals("ship_to_source_type")) refreshShip(false); });

        add(Ui.label(a, "PO source allocations · reduction below received quantity is blocked"), 12);
        if (!srcRows.isEmpty()) {
            List<Field> af = new ArrayList<>();
            af.add(Field.info("order", "Customer Order / Schedule")); af.add(Field.info("part", "Part Number")); af.add(Field.info("fsi", "FSI Part Number")); af.add(Field.info("uom", "UOM"));
            af.add(Field.number("allocated_qty", "Allocated Qty").req().range(0.001, Double.NaN));
            allocEditor = new RowsEditor(a, "Allocations", af, Arrays.asList(new String[]{"order", "Order / Schedule"}, new String[]{"part", "Part"}, new String[]{"fsi", "FSI"},
                new String[]{"allocated_qty", "Allocated Qty"}, new String[]{"uom", "UOM"})).fixedRows();
            allocEditor.setRows(srcRows);
            add(allocEditor, 2);
        } else add(Ui.text(a, "This historical PO has no source-allocation rows. Item quantity is edited directly below.", 12, Ui.MUTED, false), 2);

        add(Ui.label(a, "PO items · with master refresh ON, current master item / HSN / price override these on save"), 12);
        List<Field> itf = new ArrayList<>();
        itf.add(Field.info("part", "Finished Part"));
        itf.add(Field.text("item_no", "Supplier Item / FSI"));
        itf.add(Field.text("hsn_sac_code", "HSN / SAC"));
        Field qty = Field.number("quantity", "Ordered Qty").range(0.001, Double.NaN);
        if (!srcRows.isEmpty()) qty = Field.info("quantity", "Ordered Qty (sum of allocations)");
        itf.add(qty);
        itf.add(Field.info("uom", "UOM"));
        itf.add(Field.info("received", "Received Qty"));
        itf.add(Field.number("unit_price", "Unit Price").range(0, Double.NaN));
        itf.add(Field.number("gst_percent", "GST %").range(0, Double.NaN));
        itf.add(Field.text("remarks", "Remarks"));
        itemEditor = new RowsEditor(a, "Items", itf, Arrays.asList(new String[]{"part", "Finished Part"}, new String[]{"item_no", "Item / FSI"}, new String[]{"hsn_sac_code", "HSN"},
            new String[]{"quantity", "Qty"}, new String[]{"uom", "UOM"}, new String[]{"received", "Received"}, new String[]{"unit_price", "Unit Price"}, new String[]{"gst_percent", "GST %"})).fixedRows();
        itemEditor.setRows(itemRows);
        add(itemEditor, 2);

        List<Field> tf = new ArrayList<>();
        tf.add(Field.area("remarks", "Remarks"));
        tf.add(Field.area("special_instructions", "Comments / Special Instructions"));
        FormView tail = new FormView(a, tf);
        tail.setAll(header);
        if (SupSvc.s(header, "special_instructions").isEmpty()) tail.set("special_instructions", SupSvc.DEFAULT_SPECIAL_INSTRUCTIONS);
        add(tail, 8);
        boolean approved = "APPROVED".equalsIgnoreCase(SupSvc.first(SupSvc.s(header, "approval_status"), SupSvc.s(header, "status")));
        Button save = Ui.primary(a, approved ? "Save Revised Purchase Order · Submit for Re-Approval" : "Save / Update Purchase Order · Keep Pending Approval");
        add(save, 16);
        save.setOnClickListener(v -> save(save, tail, approved));
    }

    private void refreshShip(boolean initial) {
        String source = form.str("ship_to_source_type");
        List<String> ids = new ArrayList<>(), labels = new ArrayList<>();
        String current;
        if ("BRANCH".equals(source)) {
            for (JSONObject b : branches) { ids.add(SupSvc.s(b, "id")); labels.add(Lookups.join(SupSvc.first(SupSvc.s(b, "branch_code"), "-"), SupSvc.first(SupSvc.s(b, "branch_name"), "-"), SupSvc.first(SupSvc.s(b, "city"), "-"))); }
            current = SupSvc.first(SupSvc.s(header, "ship_to_branch_id"), SupSvc.s(header, "company_branch_id"));
        } else {
            List<JSONObject> c = new ArrayList<>();
            for (JSONObject p : parties.values()) if (SupSvc.shipToMatches(p, source)) c.add(p);
            c.sort((x, y) -> SupSvc.s(x, "party_name").toLowerCase(Locale.ROOT).compareTo(SupSvc.s(y, "party_name").toLowerCase(Locale.ROOT)));
            for (JSONObject p : c) { ids.add(SupSvc.s(p, "id")); labels.add(Lookups.join(SupSvc.first(SupSvc.s(p, "party_code"), "-"), SupSvc.first(SupSvc.s(p, "party_name"), "-"), SupSvc.first(SupSvc.s(p, "city"), "-"))); }
            current = SupSvc.s(header, "ship_to_party_id");
        }
        Field f = form.field("ship_to_id");
        f.options = ids.toArray(new String[0]);
        f.optionLabels = labels.toArray(new String[0]);
        form.set("ship_to_id", ids.contains(current) ? current : (ids.isEmpty() ? null : ids.get(0)));
    }

    private void save(Button save, FormView tail, boolean approved) {
        String problem = form.validate();
        if (problem != null) { a.toast(problem); return; }
        if (api.employeeId == null || api.employeeId.isEmpty()) { a.toast("Your login is not linked to an ACTIVE Employee Master record."); return; }
        JSONObject p;
        try {
            String src = form.str("ship_to_source_type");
            p = new JSONObject().put("order_date", form.str("order_date")).put("delivery_date", SupSvc.n(form.str("delivery_date"))).put("company_branch_id", form.str("company_branch_id"))
                .put("ship_to_source_type", src).put("ship_to_branch_id", "BRANCH".equals(src) ? form.str("ship_to_id") : JSONObject.NULL)
                .put("ship_to_party_id", "BRANCH".equals(src) ? JSONObject.NULL : form.str("ship_to_id"))
                .put("ship_via", form.str("ship_via")).put("incoterm", form.str("incoterm")).put("payment_term", form.str("payment_term"))
                .put("quotation_reference", form.str("quotation_reference")).put("quotation_date", SupSvc.n(form.str("quotation_date"))).put("old_po_reference", form.str("old_po_reference"))
                .put("remarks", tail.str("remarks")).put("special_instructions", tail.str("special_instructions")).put("refresh_master_data", form.bool("refresh_master_data"))
                .put("currency", form.str("currency")).put("other_amount", form.num("other_amount") == null ? 0 : form.num("other_amount"));
            JSONArray items = new JSONArray();
            for (JSONObject r : itemEditor.rows())
                items.put(new JSONObject().put("id", SupSvc.s(r, "id")).put("item_no", SupSvc.s(r, "item_no")).put("hsn_sac_code", SupSvc.s(r, "hsn_sac_code"))
                    .put("quantity", r.optDouble("quantity", 0)).put("unit_price", r.optDouble("unit_price", 0)).put("gst_percent", r.optDouble("gst_percent", 0)).put("remarks", SupSvc.s(r, "remarks")));
            JSONArray alloc = new JSONArray();
            if (allocEditor != null) for (JSONObject r : allocEditor.rows()) alloc.put(new JSONObject().put("id", SupSvc.s(r, "id")).put("allocated_qty", r.optDouble("allocated_qty", 0)));
            p.put("items", items).put("allocations", alloc);
        } catch (Exception e) { showError(e); return; }
        busy(save, "Saving…", () -> svc.updatePurchaseOrder(id, p), (res, err) -> {
            a.toast(approved ? "Purchase Order revised and returned for re-approval." : "Purchase Order updated successfully and remains Pending Approval.");
            a.replaceTop(new PoDetailScreen(a, id));
        });
    }
}
