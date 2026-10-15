package com.fourstar.qcmsapp;

import android.graphics.Color;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** Shared helpers of the Supply Chain editors (pickers, info cards, busy buttons). */
abstract class SupBase extends Screen {
    protected final SupSvc svc;

    protected SupBase(MainActivity a) {
        super(a);
        svc = new SupSvc(api);
    }

    @Override public int tab() { return Catalog.SUPPLY; }

    interface Picked { void picked(String id); }

    /** Searchable single choice (same dialog as the form dropdowns). */
    protected void choose(String title, List<String> ids, List<String> labels, Picked p) {
        if (ids.isEmpty()) { a.toast("Nothing available to select."); return; }
        new FormView(a, new ArrayList<>()).choose(title, ids, labels, p::picked);
    }

    /** Tappable "Select …" box. */
    protected TextView pickBox(String text) {
        TextView t = Ui.text(a, text, 14.5f, Ui.TEXT, false);
        t.setPadding(dp(12), dp(12), dp(12), dp(12));
        Ui.clickable(t, Color.WHITE, Ui.LINE_STRONG, 10);
        return t;
    }

    protected LinearLayout infoCard(String title, String... lines) {
        LinearLayout c = Ui.card(a);
        if (title != null && !title.isEmpty()) c.addView(Ui.text(a, title, 14, Ui.TEXT, true));
        for (String l : lines) {
            if (l == null || l.isEmpty()) continue;
            TextView t = Ui.text(a, l, 12.5f, Ui.MUTED, false);
            t.setPadding(0, dp(3), 0, 0);
            c.addView(t);
        }
        return c;
    }

    protected TextView note(String text, String tone) {
        TextView t = Ui.chip(a, text, tone);
        t.setSingleLine(false);
        return t;
    }

    /** Runs a write task with the button disabled; done gets the result on success. */
    protected <T> void busy(Button b, String busyText, Api.Task<T> task, Api.Callback<T> done) {
        CharSequence label = b.getText();
        b.setEnabled(false);
        b.setText(busyText);
        Api.async(task, (res, err) -> {
            b.setEnabled(true);
            b.setText(label);
            if (err != null) { showError(err); return; }
            done.done(res, null);
        });
    }

    /** Readable context of a Customer Order (website _show_order_context, short form). Background thread. */
    protected String[] orderContext(String orderId) throws Exception {
        JSONObject o = svc.get("supply_customer_orders", orderId);
        JSONObject part = svc.get("parts", SupSvc.s(o, "part_id"));
        JSONObject cust = svc.get("parties", SupSvc.s(o, "customer_id"));
        JSONObject forger = svc.get("parties", SupSvc.s(o, "forging_supplier_id"));
        return new String[]{
            SupSvc.orderLabel(o, part, cust, ""),
            "Supply Flow: " + SupSvc.flowLabel(SupSvc.flowFor(o)),
            "Part: " + SupSvc.partLabel(part),
            "Forging Supplier: " + SupSvc.partyLabel(forger),
            "Order Qty " + Ui.num(SupSvc.num(o, "order_qty_pcs"), 0) + " pcs · Gross " + Ui.num(SupSvc.num(o, "gross_weight_kg_snapshot"), 3)
                + " kg/pc · RM Required " + Ui.num(SupSvc.num(o, "required_rm_kg"), 3) + " kg · Due " + Ui.date(SupSvc.s(o, "customer_delivery_date"))};
    }

    /** Long business messages need a dialog (a toast is cut off). */
    protected void showError(Exception e) {
        new android.app.AlertDialog.Builder(a).setTitle("Not saved").setMessage(Api.message(e)).setPositiveButton("OK", null).show();
    }

    protected static String f3(double v) { return Ui.num(v, 3); }
    protected static String f0(double v) { return Ui.num(v, 0); }

    @Override public boolean onBack() {
        a.confirm("Leave without saving?", "Changes on this screen are not saved.", "Leave", () -> a.back());
        return true;
    }

    protected View spacer() { View v = new View(a); v.setMinimumHeight(dp(4)); return v; }
}
