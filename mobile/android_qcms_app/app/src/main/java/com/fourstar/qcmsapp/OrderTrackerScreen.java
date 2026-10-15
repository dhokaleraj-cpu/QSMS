package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Set;

/** Customer Order tracker: every Supply Chain stage with status and linked document numbers. */
public final class OrderTrackerScreen extends Screen {
    private final String id;
    private final String label;

    public OrderTrackerScreen(MainActivity a, String id, String label) { super(a); this.id = id; this.label = label; }

    @Override public String title() { return label; }
    @Override public String subtitle() { return "Customer Order tracker"; }
    @Override public int tab() { return 1; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONObject d = new JSONObject();
            JSONArray o = api.rows("supply_customer_orders?select=*&id=eq." + id);
            if (o.length() == 0) throw new Api.ApiException(404, "Customer Order not found.");
            JSONObject order = o.getJSONObject(0);
            d.put("order", order);
            String pid = order.optString("part_id");
            d.put("part", api.rows("parts?select=part_number,fsi_part_number,part_name&id=eq." + pid));
            d.put("rmpo", api.rows("supply_rm_purchase_orders?select=supplier_order_no,ordered_qty_kg,status,purchase_order_id,order_date&customer_order_id=eq." + id));
            d.put("rmr", api.rows("supply_rm_receipts?select=receipt_number,receipt_date,received_qty_kg,heat_number&customer_order_id=eq." + id));
            d.put("disp", api.rows("supply_rm_dispatches?select=dispatch_number,dispatch_date,qty_kg&customer_order_id=eq." + id));
            d.put("fo", api.rows("supply_forging_orders?select=supplier_order_no,order_qty_pcs,status,purchase_order_id&customer_order_id=eq." + id));
            d.put("fr", api.rows("supply_forging_receipts?select=receipt_number,receipt_date,received_qty_pcs&customer_order_id=eq." + id));
            d.put("ev", api.rows("supply_downstream_events?select=event_type,reference_no,event_date,qty_pcs&customer_order_id=eq." + id));
            Set<String> poIds = new LinkedHashSet<>();
            for (String key : new String[]{"rmpo", "fo"}) {
                JSONArray rows = d.getJSONArray(key);
                for (int i = 0; i < rows.length(); i++) {
                    JSONObject r = rows.getJSONObject(i);
                    if (!"CANCELLED".equalsIgnoreCase(r.optString("status")) && !r.isNull("purchase_order_id")) poIds.add(r.optString("purchase_order_id"));
                }
            }
            d.put("conf", poIds.isEmpty() ? new JSONArray() : api.rows("supply_po_confirmations?select=confirmation_status,confirmation_reference,purchase_order_id&purchase_order_id=in.(" + String.join(",", poIds) + ")"));
            d.put("po", poIds.isEmpty() ? new JSONArray() : api.rows("supply_purchase_orders?select=id,po_number,approval_status,status&id=in.(" + String.join(",", poIds) + ")"));
            return d;
        }, (d, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            render(d);
        });
        return scroll;
    }

    private static double sum(JSONArray rows, String field, boolean skipCancelled) {
        double total = 0;
        for (int i = 0; rows != null && i < rows.length(); i++) {
            JSONObject r = rows.optJSONObject(i);
            if (r == null || (skipCancelled && "CANCELLED".equalsIgnoreCase(r.optString("status")))) continue;
            total += r.optDouble(field, 0);
        }
        return total;
    }

    private static String refs(JSONArray rows, String field, boolean skipCancelled) {
        Set<String> out = new LinkedHashSet<>();
        for (int i = 0; rows != null && i < rows.length(); i++) {
            JSONObject r = rows.optJSONObject(i);
            if (r == null || (skipCancelled && "CANCELLED".equalsIgnoreCase(r.optString("status")))) continue;
            String v = r.optString(field, "");
            if (!v.isEmpty() && !"null".equals(v)) out.add(v);
        }
        return String.join(", ", out);
    }

    private void render(JSONObject d) {
        offlineNote();
        JSONObject o = d.optJSONObject("order");
        JSONArray partRows = d.optJSONArray("part");
        JSONObject part = partRows != null && partRows.length() > 0 ? partRows.optJSONObject(0) : new JSONObject();
        String flow = o.optString("supply_flow", "FSI_RM");
        if (flow.isEmpty() || "null".equals(flow)) flow = "FSI_RM";
        double qty = o.optDouble("order_qty_pcs", 0);
        double rmReq = o.optDouble("required_rm_kg", 0);

        LinearLayout head = Ui.card(a);
        head.addView(Ui.text(a, label, 16, Ui.TEXT, true));
        head.addView(Ui.pair(a, "Part", part.optString("part_number") + " · FSI " + part.optString("fsi_part_number")));
        head.addView(Ui.pair(a, "Description", part.optString("part_name")));
        head.addView(Ui.pair(a, "Order qty", Ui.num(qty, 0) + " pcs"));
        head.addView(Ui.pair(a, "Delivery due", Ui.date(o.optString("customer_delivery_date"))));
        head.addView(Ui.pair(a, "Flow", flow.equals("DIRECT_FORGING") ? "Direct Forging → Production" : (flow.equals("FSI_RM_DIRECT_PRODUCTION") ? "FSI RM → Direct Production" : "FSI RM → Forging → Production")));
        head.addView(Ui.pair(a, "Status", Ui.pretty(o.optString("status"))));
        add(head, 2);

        LinearLayout steps = Ui.card(a);
        steps.addView(step("done", "Customer Order", "Saved " + Ui.date(o.optString("order_date")) + (rmReq > 0 ? " · RM required " + Ui.num(rmReq, 3) + " kg" : "")));
        boolean usesRm = !flow.equals("DIRECT_FORGING");
        if (usesRm) {
            double ordered = sum(d.optJSONArray("rmpo"), "ordered_qty_kg", true);
            steps.addView(step(state(ordered, rmReq), "RM Purchase Order", ordered <= 0 ? "Not ordered yet · balance " + Ui.num(rmReq, 3) + " kg"
                : Ui.num(ordered, 3) + " / " + Ui.num(rmReq, 3) + " kg · " + refs(d.optJSONArray("rmpo"), "supplier_order_no", true)));
        }
        JSONArray pos = d.optJSONArray("po");
        JSONArray conf = d.optJSONArray("conf");
        if (pos != null && pos.length() > 0) {
            int approved = 0, confirmed = 0;
            for (int i = 0; i < pos.length(); i++) if ("APPROVED".equalsIgnoreCase(pos.optJSONObject(i).optString("approval_status"))) approved++;
            for (int i = 0; conf != null && i < conf.length(); i++) if ("CONFIRMED".equalsIgnoreCase(conf.optJSONObject(i).optString("confirmation_status"))) confirmed++;
            steps.addView(step(approved == pos.length() ? "done" : "current", "PO approval", approved + " of " + pos.length() + " PO(s) approved"));
            steps.addView(step(confirmed >= pos.length() ? "done" : (approved > 0 ? "current" : "pending"), "Supplier confirmation",
                confirmed >= pos.length() ? refs(conf, "confirmation_reference", false) : "Pending · daily reminder to supplier"));
        } else {
            steps.addView(step("pending", "PO approval & supplier confirmation", "After the PO is created"));
        }
        if (usesRm) {
            double received = sum(d.optJSONArray("rmr"), "received_qty_kg", false);
            steps.addView(step(state(received, rmReq), "RM Receipt / RMTC", received <= 0 ? "Waiting for material" : Ui.num(received, 3) + " kg · " + refs(d.optJSONArray("rmr"), "receipt_number", false)));
        }
        if (flow.equals("FSI_RM")) {
            double sent = sum(d.optJSONArray("disp"), "qty_kg", false);
            steps.addView(step(sent > 0 ? "done" : "pending", "RM to Forger", sent <= 0 ? "Not dispatched yet" : Ui.num(sent, 3) + " kg · " + refs(d.optJSONArray("disp"), "dispatch_number", false)));
        }
        if (!flow.equals("FSI_RM_DIRECT_PRODUCTION")) {
            double fo = sum(d.optJSONArray("fo"), "order_qty_pcs", true);
            steps.addView(step(state(fo, qty), "Forging PO", fo <= 0 ? "Not ordered yet" : Ui.num(fo, 0) + " / " + Ui.num(qty, 0) + " pcs · " + refs(d.optJSONArray("fo"), "supplier_order_no", true)));
            double fr = sum(d.optJSONArray("fr"), "received_qty_pcs", false);
            steps.addView(step(state(fr, qty), "Forging receipt", Ui.num(fr, 0) + " / " + Ui.num(qty, 0) + " pcs"));
        }
        double mach = 0, fg = 0, disp = 0;
        JSONArray ev = d.optJSONArray("ev");
        for (int i = 0; ev != null && i < ev.length(); i++) {
            JSONObject e = ev.optJSONObject(i);
            String t = e.optString("event_type").toUpperCase(Locale.ROOT);
            if (t.equals("MACHINING")) mach += e.optDouble("qty_pcs", 0);
            else if (t.equals("FINISHED_GOODS")) fg += e.optDouble("qty_pcs", 0);
            else if (t.equals("CUSTOMER_DISPATCH")) disp += e.optDouble("qty_pcs", 0);
        }
        steps.addView(step(state(mach, qty), "Machining", Ui.num(mach, 0) + " / " + Ui.num(qty, 0) + " pcs"));
        steps.addView(step(state(fg, qty), "Finished goods", Ui.num(fg, 0) + " / " + Ui.num(qty, 0) + " pcs"));
        steps.addView(step(state(disp, qty), "Customer dispatch", Ui.num(disp, 0) + " / " + Ui.num(qty, 0) + " pcs"));
        add(steps, 10);

        if (pos != null) {
            for (int i = 0; i < pos.length(); i++) {
                JSONObject po = pos.optJSONObject(i);
                final String poId = po.optString("id");
                Button b = Ui.outline(a, "Open PO " + po.optString("po_number") + " · " + Ui.pretty(po.optString("approval_status")), Ui.TEAL);
                b.setOnClickListener(v -> a.push(new PoDetailScreen(a, poId)));
                add(b, 8);
            }
        }
        Button web = Ui.outline(a, "Open traceability", Ui.TEAL);
        web.setOnClickListener(v -> a.push(GenTraceScreen.forOrder(a, id)));
        add(web, 8);
    }

    private static String state(double value, double target) {
        if (target > 0 && value >= target - 0.0001) return "done";
        return value > 0 ? "current" : "pending";
    }

    private View step(String state, String title, String detail) {
        LinearLayout row = Ui.hbox(a);
        row.setPadding(0, dp(7), 0, dp(7));
        TextView dot = Ui.text(a, "done".equals(state) ? "✓" : ("current".equals(state) ? "•" : ""), 11, android.graphics.Color.WHITE, true);
        dot.setGravity(android.view.Gravity.CENTER);
        int color = "done".equals(state) ? Ui.TEAL : ("current".equals(state) ? android.graphics.Color.parseColor("#F59E0B") : Ui.LINE);
        dot.setBackground(Ui.round(color, 0, 0, 10, a));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(20), dp(20));
        lp.rightMargin = dp(10);
        row.addView(dot, lp);
        LinearLayout text = Ui.vbox(a);
        text.addView(Ui.text(a, title, 13, Ui.TEXT, true));
        TextView s = Ui.text(a, detail, 11.5f, Ui.MUTED, false);
        text.addView(s);
        row.addView(text, Ui.weight(1));
        return row;
    }
}
