package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.graphics.Color;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Home: numbers first (KPI tiles) and the list of items that need the user. */
public final class HomeScreen extends Screen {
    private static final class Data {
        int pendingPo, confirmations, openOrders, overdue, dueSoon, deleteRequests;
        JSONArray pos = new JSONArray(), assets = new JSONArray(), deletes = new JSONArray();
    }

    public HomeScreen(MainActivity a) { super(a); }

    @Override public String title() { return a.greeting(); }
    @Override public String subtitle() {
        return LocalDate.now().format(DateTimeFormatter.ofPattern("EEE dd MMM yyyy", Locale.ENGLISH)) + " · " + (api.fullName.isEmpty() ? api.email : api.role.replace('_', ' '));
    }
    @Override public int tab() { return 0; }

    @Override
    public View build() {
        FrameLayout frame = new FrameLayout(a);
        frame.addView(newPage());
        page.addView(loading());
        load();

        TextView fab = Ui.text(a, "+", 28, Color.WHITE, true);
        fab.setGravity(Gravity.CENTER);
        Ui.clickable(fab, Ui.TEAL, 0, 18);
        fab.setElevation(dp(6));
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(dp(56), dp(56), Gravity.BOTTOM | Gravity.END);
        lp.setMargins(0, 0, dp(18), dp(18));
        frame.addView(fab, lp);
        fab.setOnClickListener(v -> quickActions());
        return frame;
    }

    private void quickActions() {
        String[] items = {"OSP dimensional inspection (camera)", "Material inward entry", "Record calibration", "Bend test entry", "Customer complaint", "Open full QCMS website"};
        String[] paths = {"osp-dimensional", "inward-entry", "calibration-validation", "bend-test-entry", "customer-complaint", ""};
        new AlertDialog.Builder(a)
            .setTitle("Quick entry")
            .setItems(items, (d, which) -> a.openWeb(items[which], paths[which]))
            .show();
    }

    private void load() {
        Api.async(() -> {
            Data d = new Data();
            String today = Ui.today();
            String soon = LocalDate.now().plusDays(30).toString();
            d.pendingPo = api.count("supply_purchase_orders?select=id&approval_status=eq.PENDING_APPROVAL&status=neq.CANCELLED");
            d.confirmations = api.count("supply_po_confirmations?select=id&confirmation_status=eq.PENDING");
            d.openOrders = api.count("supply_customer_orders?select=id&status=in.(OPEN,IN_PROGRESS)");
            d.overdue = api.count("quality_assets?select=id&status=eq.ACTIVE&next_due_date=lt." + today);
            d.dueSoon = api.count("quality_assets?select=id&status=eq.ACTIVE&next_due_date=gte." + today + "&next_due_date=lte." + soon);
            d.pos = api.rows("supply_purchase_orders?select=id,po_number,po_type,order_date,grand_total,currency,vendor_snapshot&approval_status=eq.PENDING_APPROVAL&status=neq.CANCELLED&order=created_at.desc&limit=5");
            d.assets = api.rows("quality_assets?select=id,asset_name,asset_number,asset_code,next_due_date&status=eq.ACTIVE&next_due_date=lt." + today + "&order=next_due_date.asc&limit=5");
            if (api.isAdmin()) {
                d.deleteRequests = api.count("qcms_delete_requests?select=id&status=eq.PENDING");
                d.deletes = api.rows("qcms_delete_requests?select=id,table_name,record_label,reason,requested_at&status=eq.PENDING&order=requested_at.desc&limit=10");
            }
            return d;
        }, (d, err) -> {
            page.removeAllViews();
            if (err != null) {
                page.addView(error(err, this::reload));
                return;
            }
            render(d);
        });
    }

    private void render(Data d) {
        offlineNote();
        int need = d.pendingPo + d.overdue + d.deleteRequests;
        a.setSubtitle(subtitle() + (need > 0 ? " · " + need + " item(s) need you" : ""));

        List<View> tiles = new ArrayList<>();
        tiles.add(tile(d.pendingPo, "POs awaiting approval", "amber", v -> openOrders(0)));
        tiles.add(tile(d.confirmations, "Supplier confirmations pending", "teal", v -> a.openWeb("PO confirmation", "supply-po-approval")));
        tiles.add(tile(d.openOrders, "Open customer orders", "teal", v -> openOrders(1)));
        tiles.add(tile(d.overdue, "Calibrations overdue", d.overdue > 0 ? "red" : "green", v -> a.openTab(3)));
        tiles.add(tile(d.dueSoon, "Calibrations due in 30 days", "amber", v -> a.openTab(3)));
        if (api.isAdmin()) tiles.add(tile(d.deleteRequests, "Deletion requests (Admin)", d.deleteRequests > 0 ? "red" : "green", null));
        for (int i = 0; i < tiles.size(); i += 2) {
            LinearLayout row = Ui.hbox(a);
            LinearLayout.LayoutParams l = Ui.weight(1); l.rightMargin = dp(5);
            row.addView(tiles.get(i), l);
            LinearLayout.LayoutParams r = Ui.weight(1); r.leftMargin = dp(5);
            if (i + 1 < tiles.size()) row.addView(tiles.get(i + 1), r);
            else row.addView(new View(a), r);
            add(row, i == 0 ? 4 : 10);
        }

        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "Needs your action", 14, Ui.TEXT, true));
        int count = 0;
        for (int i = 0; i < d.pos.length(); i++) {
            JSONObject po = d.pos.optJSONObject(i);
            if (po == null) continue;
            String supplier = po.optJSONObject("vendor_snapshot") == null ? "" : po.optJSONObject("vendor_snapshot").optString("party_name", "");
            final String id = po.optString("id");
            card.addView(actionRow("PO " + po.optString("po_number") + " · " + Ui.pretty(po.optString("po_type")),
                supplier + " · " + Ui.money(po.optDouble("grand_total", 0), po.optString("currency")), "Approve", "amber",
                v -> a.push(new PoDetailScreen(a, id))));
            count++;
        }
        for (int i = 0; i < d.deletes.length(); i++) {
            JSONObject r = d.deletes.optJSONObject(i);
            if (r == null) continue;
            card.addView(actionRow("Deletion request · " + Ui.pretty(r.optString("table_name")) + " " + r.optString("record_label"),
                "Reason: " + r.optString("reason"), "Admin", "red", v -> decideDelete(r)));
            count++;
        }
        for (int i = 0; i < d.assets.length(); i++) {
            JSONObject r = d.assets.optJSONObject(i);
            if (r == null) continue;
            final String id = r.optString("id");
            card.addView(actionRow(r.optString("asset_name") + " · " + r.optString("asset_number", r.optString("asset_code")),
                "Calibration was due " + Ui.date(r.optString("next_due_date")), "Overdue", "red", v -> a.push(new AssetDetailScreen(a, id))));
            count++;
        }
        if (count == 0) {
            TextView ok = Ui.text(a, "Nothing is waiting for you. ✓", 13, Ui.GREEN_FG, false);
            ok.setPadding(0, dp(10), 0, dp(4));
            card.addView(ok);
        }
        add(card, 14);
    }

    private void openOrders(int segment) {
        OrdersScreen.segment = segment;
        a.openTab(1);
    }

    private View tile(int value, String label, String tone, View.OnClickListener click) {
        LinearLayout t = Ui.vbox(a);
        t.setPadding(dp(12), dp(12), dp(12), dp(12));
        Ui.clickable(t, Color.WHITE, Ui.LINE, 14);
        int color = "red".equals(tone) ? Ui.RED_FG : ("amber".equals(tone) ? Ui.AMBER_FG : ("green".equals(tone) ? Ui.GREEN_FG : Ui.TEAL_DARK));
        TextView n = Ui.text(a, Ui.num(value, 0), 26, color, true);
        t.addView(n);
        TextView l = Ui.text(a, label, 11.5f, Ui.MUTED, false);
        l.setMinLines(2);
        t.addView(l);
        if (click != null) t.setOnClickListener(click);
        t.setLayoutParams(new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return t;
    }

    private View actionRow(String title, String detail, String chip, String tone, View.OnClickListener click) {
        LinearLayout row = Ui.hbox(a);
        row.setPadding(0, dp(10), 0, dp(10));
        LinearLayout text = Ui.vbox(a);
        TextView t = Ui.text(a, title, 13, Ui.TEXT, true);
        TextView s = Ui.text(a, detail, 11.5f, Ui.MUTED, false);
        s.setMaxLines(2);
        text.addView(t);
        text.addView(s);
        row.addView(text, Ui.weight(1));
        row.addView(Ui.chip(a, chip, tone));
        row.setOnClickListener(click);
        LinearLayout wrap = Ui.vbox(a);
        wrap.addView(Ui.divider(a));
        wrap.addView(row);
        return wrap;
    }

    private void decideDelete(JSONObject request) {
        String id = request.optString("id");
        new AlertDialog.Builder(a)
            .setTitle("Deletion request")
            .setMessage(Ui.pretty(request.optString("table_name")) + " " + request.optString("record_label")
                + "\n\nReason: " + request.optString("reason")
                + "\nRequested: " + Ui.date(request.optString("requested_at"))
                + "\n\nApproving deletes the record now. It stays viewable in Records → Deleted Records.")
            .setPositiveButton("Approve & delete", (dlg, w) -> a.confirmPassword("Confirm with your password", () -> decide(id, true, "Approved from QCMS app")))
            .setNegativeButton("Reject", (dlg, w) -> a.askText("Reject deletion", "Reason for rejecting", "Reject", true, note -> decide(id, false, note)))
            .setNeutralButton("Back", null)
            .show();
    }

    private void decide(String id, boolean approve, String note) {
        Api.async(() -> {
            JSONObject args = new JSONObject();
            args.put("p_request_id", id);
            args.put("p_approve", approve);
            args.put("p_note", note);
            return new JSONObject(api.rpc("qcms_decide_delete_request", args));
        }, (res, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            String status = res.optString("status");
            if ("FAILED".equals(status)) a.toast("Deletion failed: " + res.optString("error"));
            else a.toast(approve ? "Approved and deleted." : "Request rejected.");
            reload();
        });
    }
}
