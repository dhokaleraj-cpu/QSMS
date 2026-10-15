package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Supply Chain stage postings exactly like the website pages: RM Receipt (Material Inward link), RM to Forging,
 * Forging Order, Forging Receipt and Machining / Finished Goods / Customer Dispatch. Every posting runs the
 * duplicate gate, writes the stage row and then the same status sync as the website. Edit mode = the
 * website's "EDIT / DELETE" panel fields (save_transaction + sync_order_status).
 */
final class SupStageScreen extends SupBase {
    static final String LINK = "LINK", DISPATCH = "DISPATCH", FORGING_ORDER = "FORGING_ORDER", FORGING_RECEIPT = "FORGING_RECEIPT", DOWNSTREAM = "DOWNSTREAM";

    private final String mode, id;
    private SupSvc.Data data;
    private LinearLayout sourceBox, formBox;
    private FormView form;
    private JSONObject source;
    private String flowChoice = SupSvc.FSI_RM, eventType = "MACHINING";

    SupStageScreen(MainActivity a, String mode, String id) { super(a); this.mode = mode; this.id = id; }

    static String table(String mode) {
        switch (mode) {
            case LINK: return "supply_rm_receipts";
            case DISPATCH: return "supply_rm_dispatches";
            case FORGING_ORDER: return "supply_forging_orders";
            case FORGING_RECEIPT: return "supply_forging_receipts";
            default: return "supply_downstream_events";
        }
    }

    @Override public String title() {
        String t;
        switch (mode) {
            case LINK: t = "RM Receipt · Material Inward Link"; break;
            case DISPATCH: t = "RM Dispatch to Forging"; break;
            case FORGING_ORDER: t = "Forging Supplier Order"; break;
            case FORGING_RECEIPT: t = "Forging Receipt"; break;
            default: t = "Production / Customer Dispatch"; break;
        }
        return (id == null ? "" : "Edit · ") + t;
    }

    @Override public String subtitle() { return id == null ? "Select the pending source · context and Heat are inherited" : "Controlled fields of the saved entry"; }

    @Override
    public View build() {
        newPage();
        if (id != null) return LINK.equals(mode) ? buildRelink() : buildEdit();
        if (FORGING_ORDER.equals(mode)) {
            FormView flow = new FormView(a, java.util.Collections.singletonList(
                Field.select("flow", "Supply Chain Flow", SupSvc.FSI_RM, SupSvc.DIRECT_FORGING).labels(SupSvc.flowLabel(SupSvc.FSI_RM), SupSvc.flowLabel(SupSvc.DIRECT_FORGING)).req().def(flowChoice)));
            flow.onChange((k, v) -> { flowChoice = flow.str("flow"); source = null; renderSource(); });
            add(flow, 0);
            add(Ui.text(a, "Controlled Forging Purchase Orders are created in Purchase Orders → New (Forging PO). This screen records a direct forging supplier order like the website's Forging Order section.", 11.5f, Ui.MUTED, false), 4);
        }
        if (DOWNSTREAM.equals(mode)) {
            FormView ev = new FormView(a, java.util.Collections.singletonList(
                Field.select("event", "Stage", "MACHINING", "FINISHED_GOODS", "CUSTOMER_DISPATCH").labels("Machining", "Finished Goods", "Customer Dispatch / Invoice / ASN").req().def(eventType)));
            ev.onChange((k, v) -> { eventType = ev.str("event"); source = null; renderSource(); });
            add(ev, 0);
        }
        sourceBox = Ui.vbox(a);
        add(sourceBox, 6);
        formBox = Ui.vbox(a);
        add(formBox, 6);
        sourceBox.addView(loading());
        Api.async(svc::load, (d, err) -> {
            sourceBox.removeAllViews();
            if (err != null) { sourceBox.addView(error(err, this::reload)); return; }
            data = d;
            renderSource();
        });
        return scroll;
    }

    // ------------------------------------------------------------------ pending sources
    private List<JSONObject> pending() throws Exception {
        switch (mode) {
            case LINK: return svc.pendingRmPurchaseOrders(data);
            case DISPATCH: return svc.pendingRmReceiptsForDispatch(data);
            case FORGING_ORDER: {
                if (SupSvc.DIRECT_FORGING.equals(flowChoice)) return svc.pendingDirectForgingOrders(data);
                List<JSONObject> out = new ArrayList<>();
                for (JSONObject r : svc.pendingRmDispatchesForForgingOrder(data))
                    if (SupSvc.FSI_RM.equals(SupSvc.flowFor(data.order(SupSvc.s(r, "customer_order_id"))))) out.add(r);
                return out;
            }
            case FORGING_RECEIPT: return svc.pendingForgingOrders(data);
            default: return svc.pendingSourcesForDownstream(data, eventType);
        }
    }

    private String sourceLabel(JSONObject r) {
        switch (mode) {
            case LINK: return SupSvc.s(r, "supplier_order_no") + " · Expected " + Ui.date(SupSvc.s(r, "expected_date")) + " · Balance " + f3(SupSvc.num(r, "balance_qty_kg")) + " kg";
            case DISPATCH: return SupSvc.s(r, "receipt_number") + " · Heat " + SupSvc.s(r, "heat_number") + " · Balance " + f3(SupSvc.num(r, "balance_qty_kg")) + " kg";
            case FORGING_ORDER:
                if (SupSvc.DIRECT_FORGING.equals(flowChoice)) return SupSvc.orderLabel(r, null, null, "Forging Balance " + f0(SupSvc.num(r, "forging_balance_pcs")) + " pcs · Due " + Ui.date(SupSvc.s(r, "customer_delivery_date")));
                return SupSvc.s(r, "dispatch_number") + " · Heat " + SupSvc.first(SupSvc.s(r, "heat_number"), "-") + " · " + f3(SupSvc.num(r, "qty_kg")) + " kg";
            case FORGING_RECEIPT: return SupSvc.s(r, "supplier_order_no") + " · Heat " + SupSvc.first(SupSvc.s(r, "heat_number"), "-") + " · Balance " + f0(SupSvc.num(r, "balance_qty_pcs")) + " pcs";
            default:
                if ("MACHINING".equals(eventType))
                    return SupSvc.s(r, "receipt_number") + " · " + ("RM_RECEIPT".equals(SupSvc.s(r, "_source_type")) ? "Direct RM → Production" : "Forging → Production")
                        + " · Heat " + SupSvc.first(SupSvc.s(r, "heat_number"), "-") + " · " + f0(SupSvc.num(r, "received_qty_pcs")) + " pcs";
                return SupSvc.s(r, "reference_no") + " · Heat " + SupSvc.first(SupSvc.s(r, "heat_number"), "-") + " · " + f0(SupSvc.num(r, "qty_pcs")) + " pcs";
        }
    }

    private List<JSONObject> pendingRows;

    /** Reload the worklist (background: the Flow-3 MACHINING source reads inward lots) and show it. */
    private void renderSource() {
        if (sourceBox == null || data == null) return;
        sourceBox.removeAllViews();
        formBox.removeAllViews();
        sourceBox.addView(loading());
        final String key = flowChoice + "|" + eventType;
        Api.async(this::pending, (rows, err) -> {
            if (!key.equals(flowChoice + "|" + eventType)) return;
            if (err != null) { sourceBox.removeAllViews(); sourceBox.addView(error(err, this::reload)); return; }
            pendingRows = rows;
            showSource();
        });
    }

    private void showSource() {
        sourceBox.removeAllViews();
        formBox.removeAllViews();
        List<JSONObject> rows = pendingRows;
        sourceBox.addView(Ui.label(a, "Pending source (" + rows.size() + ")"));
        if (rows.isEmpty()) { sourceBox.addView(Ui.empty(a, emptyText())); return; }
        List<String> ids = new ArrayList<>(), labels = new ArrayList<>();
        for (int i = 0; i < rows.size(); i++) { ids.add(String.valueOf(i)); labels.add(sourceLabel(rows.get(i))); }
        TextView box = pickBox(source == null ? "Select…" : sourceLabel(source));
        box.setOnClickListener(v -> choose("Pending source", ids, labels, pick -> { source = rows.get(Integer.parseInt(pick)); showSource(); }));
        sourceBox.addView(box, Ui.matchWrap(a, 0));
        if (source != null) renderForm();
    }

    private String emptyText() {
        switch (mode) {
            case LINK: return "No pending RM Procurement is waiting for Material Inward (the supplier PO confirmation must be CONFIRMED).";
            case DISPATCH: return "No RM Receipt balance is pending dispatch.";
            case FORGING_ORDER: return SupSvc.DIRECT_FORGING.equals(flowChoice) ? "No Flow 2 Customer Order is waiting for a Forging Order." : "No Flow 1 RM dispatch is waiting for a Forging Order.";
            case FORGING_RECEIPT: return "No forging order is pending receipt (the supplier PO confirmation must be CONFIRMED).";
            default: return "No record is pending for this stage.";
        }
    }

    private void renderForm() {
        formBox.removeAllViews();
        String orderId = FORGING_ORDER.equals(mode) && SupSvc.DIRECT_FORGING.equals(flowChoice) ? SupSvc.s(source, "id") : SupSvc.s(source, "customer_order_id");
        JSONObject order = data.order(orderId);
        LinearLayout ctx = infoCard("Customer Order context");
        formBox.addView(ctx);
        Api.async(() -> orderContext(orderId), (lines, err) -> {
            if (err != null) return;
            for (String l : lines) { TextView t = Ui.text(a, l, 12.5f, Ui.MUTED, false); t.setPadding(0, dp(3), 0, 0); ctx.addView(t); }
        });
        if (LINK.equals(mode)) { renderLink(); return; }
        List<Field> f = new ArrayList<>();
        String today = Ui.today();
        switch (mode) {
            case DISPATCH: {
                double bal = SupSvc.num(source, "balance_qty_kg");
                formBox.addView(note("Heat " + SupSvc.first(SupSvc.s(source, "heat_number"), "-") + " · Available " + f3(bal) + " kg", "teal"), Ui.matchWrap(a, 6));
                f.add(Field.text("dispatch_number", "RM Dispatch No.").req());
                f.add(Field.date("dispatch_date", "Dispatch Date").def(today));
                f.add(Field.number("qty_kg", "Dispatch Qty kg").req().range(0.001, Math.max(bal, 0.001)).def(Math.max(bal, 0.001)));
                f.add(Field.text("challan_number", "Challan No."));
                f.add(Field.text("vehicle_number", "Vehicle No."));
                f.add(Field.text("remarks", "Dispatch Remarks"));
                break;
            }
            case FORGING_ORDER: {
                boolean direct = SupSvc.DIRECT_FORGING.equals(flowChoice);
                double balance = direct ? Math.max(SupSvc.num(order, "order_qty_pcs") - data.totals(orderId)[SupSvc.FORGING_ORDERED], 0) : SupSvc.num(order, "order_qty_pcs");
                double max = Math.max(balance, 1);
                f.add(Field.text("supplier_order_no", "Forging Supplier Order No.").req());
                f.add(Field.date("order_date", "Order Date").def(today));
                f.add(Field.date("expected_date", "Expected Forging Receipt").def(today));
                Field q = Field.number("order_qty_pcs", "Forging Order Qty pcs").req().range(1, max).def(max);
                if (direct) q.ro().hint("Flow 2 uses the full pending Customer Order quantity.");
                f.add(q);
                if (direct) {
                    f.add(Field.text("heat_number", "Supplier Heat Number (if known)"));
                    f.add(Field.text("heat_code", "Supplier Heat Code (if known)"));
                } else {
                    f.add(Field.text("heat_number", "Heat Number").ro().def(SupSvc.s(source, "heat_number")));
                    f.add(Field.text("heat_code", "Heat Code").ro().def(SupSvc.s(source, "heat_code")));
                }
                f.add(Field.text("remarks", "Forging Order Remarks"));
                break;
            }
            case FORGING_RECEIPT: {
                boolean direct = SupSvc.DIRECT_FORGING.equals(SupSvc.flowFor(order));
                double max = Math.max(SupSvc.num(source, "balance_qty_pcs"), 1);
                f.add(Field.text("receipt_number", "Forging Receipt No.").req());
                f.add(Field.date("receipt_date", "Receipt Date").def(today));
                f.add(Field.number("received_qty_pcs", "Received Forging Qty pcs").req().range(1, max).hint("1 to " + f0(max) + " pcs"));
                f.add(Field.number("rejected_qty_pcs", "Rejected Qty pcs").range(0, Double.NaN).def(0.0));
                Field h = Field.text("heat_number", "Heat Number").def(SupSvc.s(source, "heat_number"));
                Field c = Field.text("heat_code", "Heat Code").def(SupSvc.s(source, "heat_code"));
                if (!direct && !SupSvc.s(source, "heat_number").isEmpty()) h.ro();
                if (!direct && !SupSvc.s(source, "heat_code").isEmpty()) c.ro();
                f.add(h); f.add(c);
                f.add(Field.number("actual_rm_consumed_kg", "Actual RM Consumed kg (0 = auto)").range(0, Double.NaN).def(0.0));
                f.add(Field.text("remarks", "Forging Receipt Remarks"));
                break;
            }
            default: {
                double max = Math.max("MACHINING".equals(eventType) ? SupSvc.num(source, "received_qty_pcs") : SupSvc.num(source, "qty_pcs"), 1);
                f.add(Field.text("reference_no", "Reference No.").req());
                f.add(Field.date("event_date", "Date").def(today));
                f.add(Field.number("qty_pcs", "Quantity pcs").req().range(1, max).def(max));
                f.add(Field.number("rejected_qty_pcs", "Rejected Qty pcs").range(0, Double.NaN).def(0.0));
                if ("CUSTOMER_DISPATCH".equals(eventType)) {
                    f.add(Field.text("invoice_no", "Invoice No."));
                    f.add(Field.date("invoice_date", "Invoice Date").def(today));
                    f.add(Field.text("asn_no", "ASN No."));
                }
                f.add(Field.text("remarks", "Remarks"));
                break;
            }
        }
        form = new FormView(a, f);
        formBox.addView(form, Ui.matchWrap(a, 6));
        Button save = Ui.primary(a, saveLabel());
        formBox.addView(save, Ui.matchWrap(a, 14));
        save.setOnClickListener(v -> post(save, orderId, order));
    }

    private String saveLabel() {
        switch (mode) {
            case DISPATCH: return "Post RM Dispatch to Forging";
            case FORGING_ORDER: return "Create Forging Supplier Order";
            case FORGING_RECEIPT: return "Post Forging Receipt";
            default: return "Post " + Ui.pretty(eventType);
        }
    }

    private void post(Button save, String orderId, JSONObject order) {
        String problem = form.validate();
        if (problem != null) { a.toast(problem); return; }
        final JSONObject src = source;
        final String flow = flowChoice, ev = eventType;
        busy(save, "Posting…", () -> {
            JSONObject v = form.json();
            switch (mode) {
                case DISPATCH: {
                    JSONObject p = new JSONObject().put("customer_order_id", orderId).put("rm_receipt_id", SupSvc.s(src, "id")).put("inward_lot_id", SupSvc.raw(src, "inward_lot_id"))
                        .put("forging_supplier_id", SupSvc.raw(order, "forging_supplier_id")).put("dispatch_number", SupSvc.t(v, "dispatch_number")).put("dispatch_date", SupSvc.raw(v, "dispatch_date"))
                        .put("heat_number", SupSvc.raw(src, "heat_number")).put("heat_code", SupSvc.raw(src, "heat_code")).put("qty_kg", SupSvc.num(v, "qty_kg"))
                        .put("challan_number", SupSvc.raw(v, "challan_number")).put("vehicle_number", SupSvc.raw(v, "vehicle_number")).put("remarks", SupSvc.raw(v, "remarks"));
                    svc.saveTransaction("supply_rm_dispatches", p, null);
                    svc.syncOrderStatus(orderId);
                    return "RM dispatched with inherited Heat traceability.";
                }
                case FORGING_ORDER: {
                    boolean direct = SupSvc.DIRECT_FORGING.equals(flow);
                    double qty = SupSvc.num(v, "order_qty_pcs");
                    JSONObject p = new JSONObject().put("customer_order_id", orderId).put("rm_dispatch_id", direct ? JSONObject.NULL : SupSvc.s(src, "id"))
                        .put("inward_lot_id", direct ? JSONObject.NULL : SupSvc.raw(src, "inward_lot_id")).put("forging_supplier_id", SupSvc.raw(order, "forging_supplier_id"))
                        .put("supplier_order_no", SupSvc.t(v, "supplier_order_no")).put("order_date", SupSvc.raw(v, "order_date")).put("order_qty_pcs", qty)
                        .put("required_rm_kg", qty * SupSvc.num(order, "gross_weight_kg_snapshot")).put("expected_date", SupSvc.raw(v, "expected_date"))
                        .put("heat_number", SupSvc.n(SupSvc.t(v, "heat_number"))).put("heat_code", SupSvc.n(SupSvc.t(v, "heat_code"))).put("status", "OPEN").put("remarks", SupSvc.raw(v, "remarks"));
                    svc.saveTransaction("supply_forging_orders", p, null);
                    svc.syncOrderStatus(orderId);
                    return "Forging Order created and linked to the selected Supply Chain flow.";
                }
                case FORGING_RECEIPT: {
                    JSONObject fo = src;
                    String foId = SupSvc.s(src, "id");
                    boolean direct = SupSvc.DIRECT_FORGING.equals(SupSvc.flowFor(svc.get("supply_customer_orders", SupSvc.s(fo, "customer_order_id"))));
                    String heat = SupSvc.t(v, "heat_number"), code = SupSvc.t(v, "heat_code");
                    if (direct && (!heat.equals(SupSvc.t(fo, "heat_number")) || !code.equals(SupSvc.t(fo, "heat_code")))) {
                        svc.saveTransaction("supply_forging_orders", new JSONObject().put("heat_number", SupSvc.n(heat)).put("heat_code", SupSvc.n(code)), foId);
                        JSONObject fresh = svc.get("supply_forging_orders", foId);
                        if (!SupSvc.empty(fresh)) fo = fresh;
                    }
                    double actual = SupSvc.num(v, "actual_rm_consumed_kg");
                    JSONObject p = new JSONObject().put("customer_order_id", SupSvc.raw(fo, "customer_order_id")).put("forging_order_id", foId).put("rm_dispatch_id", SupSvc.raw(fo, "rm_dispatch_id"))
                        .put("inward_lot_id", SupSvc.raw(fo, "inward_lot_id")).put("forging_supplier_id", SupSvc.raw(fo, "forging_supplier_id")).put("receipt_number", SupSvc.t(v, "receipt_number"))
                        .put("receipt_date", SupSvc.raw(v, "receipt_date")).put("received_qty_pcs", SupSvc.num(v, "received_qty_pcs")).put("rejected_qty_pcs", SupSvc.num(v, "rejected_qty_pcs"))
                        .put("actual_rm_consumed_kg", actual > 0 ? (Object) actual : JSONObject.NULL).put("gross_weight_kg_snapshot", SupSvc.num(order, "gross_weight_kg_snapshot"))
                        .put("heat_number", SupSvc.raw(fo, "heat_number")).put("heat_code", SupSvc.raw(fo, "heat_code")).put("remarks", SupSvc.raw(v, "remarks"));
                    svc.saveTransaction("supply_forging_receipts", p, null);
                    svc.syncOrderStatus(SupSvc.s(fo, "customer_order_id"));
                    svc.syncPurchaseOrderStatus(SupSvc.s(fo, "purchase_order_id"));
                    return "Forging Receipt posted with linked genealogy.";
                }
                default: {
                    boolean dispatch = "CUSTOMER_DISPATCH".equals(ev);
                    JSONObject p = new JSONObject().put("customer_order_id", orderId).put("event_type", ev).put("reference_no", SupSvc.t(v, "reference_no"))
                        .put("event_date", SupSvc.raw(v, "event_date")).put("qty_pcs", SupSvc.num(v, "qty_pcs")).put("rejected_qty_pcs", SupSvc.num(v, "rejected_qty_pcs"))
                        .put("inward_lot_id", SupSvc.raw(src, "inward_lot_id")).put("heat_number", SupSvc.raw(src, "heat_number")).put("heat_code", SupSvc.raw(src, "heat_code"))
                        .put("invoice_no", dispatch ? SupSvc.raw(v, "invoice_no") : JSONObject.NULL).put("invoice_date", dispatch ? SupSvc.raw(v, "invoice_date") : JSONObject.NULL)
                        .put("asn_no", dispatch ? SupSvc.raw(v, "asn_no") : JSONObject.NULL).put("remarks", SupSvc.raw(v, "remarks"));
                    String sourceId = SupSvc.first(SupSvc.s(src, "_source_id"), SupSvc.s(src, "id"));
                    if ("MACHINING".equals(ev)) p.put("RM_RECEIPT".equals(SupSvc.s(src, "_source_type")) ? "source_rm_receipt_id" : "source_forging_receipt_id", sourceId);
                    else p.put("source_event_id", sourceId);
                    svc.saveTransaction("supply_downstream_events", p, null);
                    svc.syncOrderStatus(orderId);
                    return Ui.pretty(ev) + " linked to previous stage with Heat traceability.";
                }
            }
        }, (msg, err) -> { a.toast(msg); a.back(); });
    }

    // ------------------------------------------------------------------ RM receipt (Material Inward link)
    private void renderLink() {
        String poId = SupSvc.s(source, "id");
        LinearLayout box = Ui.vbox(a);
        formBox.addView(box, Ui.matchWrap(a, 8));
        box.addView(loading());
        Api.async(() -> svc.eligibleInwardsForPo(poId), (rows, err) -> {
            box.removeAllViews();
            if (err != null) { box.addView(error(err, this::renderForm)); return; }
            box.addView(Ui.label(a, "Eligible Material Inward records (" + rows.size() + ")"));
            if (rows.isEmpty()) { box.addView(Ui.empty(a, "No Material Inward of this Part is available. Create the Material Inward first (Quality → Material Inward).")); return; }
            List<String> ids = new ArrayList<>(), labels = new ArrayList<>();
            for (JSONObject r : rows) {
                ids.add(SupSvc.s(r, "id"));
                double q = SupSvc.num(r, "steel_quantity_kg"); if (q == 0) q = SupSvc.num(r, "quantity_received");
                labels.add(SupSvc.s(r, "inward_number") + " · " + SupSvc.s(r, "part_number") + " · Heat " + SupSvc.s(r, "heat_number") + " · " + f3(q) + " kg · RMTC " + SupSvc.first(SupSvc.s(r, "rmtc_number"), "-")
                    + " [" + SupSvc.first(SupSvc.s(r, "status"), "-") + "]");
            }
            final String[] chosen = {null};
            TextView pick = pickBox("Select existing Material Inward…");
            Button link = Ui.primary(a, "Link Selected Material Inward to RM Procurement");
            link.setEnabled(false);
            pick.setOnClickListener(v -> choose("Existing Material Inward", ids, labels, inward -> {
                chosen[0] = inward;
                pick.setText(labels.get(ids.indexOf(inward)));
                link.setEnabled(true);
            }));
            box.addView(pick, Ui.matchWrap(a, 0));
            box.addView(Ui.text(a, "Heat, Heat Code, RMTC Number, RMTC Date and RMTC Quantity are inherited from the Material Inward record.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 4));
            box.addView(link, Ui.matchWrap(a, 12));
            link.setOnClickListener(v -> {
                if (chosen[0] == null) { a.toast("Select the Material Inward."); return; }
                busy(link, "Linking…", () -> svc.linkInwardToRmPo(poId, chosen[0]), (saved, e2) -> {
                    a.toast("Material Inward linked to RM Procurement; RM Receipt genealogy updated.");
                    a.back();
                });
            });
        });
    }

    /** Edit of a linked RM receipt = refresh the link from its Material Inward (link_inward_to_rm_po upserts by inward). */
    private View buildRelink() {
        page.addView(loading());
        Api.async(() -> svc.get("supply_rm_receipts", id), (row, err) -> {
            page.removeAllViews();
            if (err != null || SupSvc.empty(row)) { page.addView(error(err != null ? err : new Exception("RM Receipt not found."), this::reload)); return; }
            add(infoCard("RM Receipt " + SupSvc.s(row, "receipt_number"), "Heat " + SupSvc.first(SupSvc.s(row, "heat_number"), "-") + " · " + f3(SupSvc.num(row, "received_qty_kg")) + " kg",
                "Material Inward is the source of truth: correct the inward record in Quality → Material Inward, then refresh this link to copy Heat, RMTC and quantity again."), 0);
            Button b = Ui.primary(a, "Refresh link from Material Inward");
            add(b, 14);
            b.setOnClickListener(v -> {
                if (SupSvc.s(row, "inward_lot_id").isEmpty()) { a.toast("This receipt has no Material Inward link."); return; }
                busy(b, "Refreshing…", () -> svc.linkInwardToRmPo(SupSvc.s(row, "rm_purchase_order_id"), SupSvc.s(row, "inward_lot_id")),
                    (saved, e2) -> { a.toast("RM Receipt refreshed from Material Inward."); a.back(); });
            });
        });
        return scroll;
    }

    // ------------------------------------------------------------------ edit panel
    private List<Field> editFields() {
        List<Field> f = new ArrayList<>();
        switch (mode) {
            case DISPATCH:
                f.add(Field.text("dispatch_number", "Dispatch No.").req()); f.add(Field.date("dispatch_date", "Dispatch Date"));
                f.add(Field.number("qty_kg", "Qty kg").req().range(0, Double.NaN)); f.add(Field.text("challan_number", "Challan No."));
                f.add(Field.text("vehicle_number", "Vehicle No.")); f.add(Field.text("remarks", "Remarks"));
                break;
            case FORGING_ORDER:
                f.add(Field.text("supplier_order_no", "Supplier Order No.").req()); f.add(Field.date("order_date", "Order Date")); f.add(Field.date("expected_date", "Expected Receipt"));
                f.add(Field.number("order_qty_pcs", "Order Qty pcs").req().range(0, Double.NaN)); f.add(Field.text("heat_number", "Heat Number")); f.add(Field.text("heat_code", "Heat Code"));
                f.add(Field.select("status", "Status", "OPEN", "PART_RECEIVED", "CLOSED", "CANCELLED").req()); f.add(Field.text("remarks", "Remarks"));
                break;
            case FORGING_RECEIPT:
                f.add(Field.text("receipt_number", "Receipt No.").req()); f.add(Field.date("receipt_date", "Receipt Date"));
                f.add(Field.number("received_qty_pcs", "Received pcs").req().range(0, Double.NaN)); f.add(Field.number("rejected_qty_pcs", "Rejected pcs").range(0, Double.NaN));
                f.add(Field.text("remarks", "Remarks"));
                break;
            default:
                f.add(Field.text("reference_no", "Reference No.").req()); f.add(Field.date("event_date", "Date"));
                f.add(Field.number("qty_pcs", "Qty pcs").req().range(0, Double.NaN)); f.add(Field.number("rejected_qty_pcs", "Rejected pcs").range(0, Double.NaN));
                f.add(Field.text("invoice_no", "Invoice No.")); f.add(Field.text("asn_no", "ASN No.")); f.add(Field.text("remarks", "Remarks"));
                break;
        }
        return f;
    }

    private View buildEdit() {
        String table = table(mode);
        form = new FormView(a, editFields());
        form.setVisibility(View.INVISIBLE);
        add(form, 0);
        Button save = Ui.primary(a, "Save Edited Entry");
        add(save, 16);
        Api.async(() -> svc.get(table, id), (row, err) -> {
            if (err != null || SupSvc.empty(row)) { page.addView(error(err != null ? err : new Exception("Entry not found."), this::reload), 0); return; }
            form.setAll(row);
            if (FORGING_ORDER.equals(mode) && SupSvc.s(row, "status").isEmpty()) form.set("status", "OPEN");
            form.setVisibility(View.VISIBLE);
        });
        save.setOnClickListener(v -> {
            String problem = form.validate();
            if (problem != null) { a.toast(problem); return; }
            busy(save, "Saving…", () -> {
                JSONObject values = form.json();
                for (Field fl : editFields()) if (Field.NUM.equals(fl.type) && values.isNull(fl.key)) values.put(fl.key, 0);
                svc.saveTransaction(table, values, id);
                String orderId = SupSvc.s(svc.get(table, id), "customer_order_id");
                if (!orderId.isEmpty()) svc.syncOrderStatus(orderId);
                return true;
            }, (ok, e2) -> { a.toast("Supply Chain entry updated successfully."); a.back(); });
        });
        return scroll;
    }

    static Map<String, String> none() { return null; }
}
