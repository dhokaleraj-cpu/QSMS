package com.fourstar.qcmsapp;

import android.annotation.SuppressLint;
import android.graphics.Color;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/** Orders tab: Purchase Orders (approval list) and Customer Orders (tracker). */
public final class OrdersScreen extends Screen {
    static int segment = 0;
    static int filter = 0;
    private static final String[] FILTERS = {"Pending", "Approved", "Cancelled", "All"};
    private static final String[] FILTER_QUERY = {
        "&approval_status=eq.PENDING_APPROVAL&status=neq.CANCELLED",
        "&approval_status=eq.APPROVED&status=neq.CANCELLED",
        "&status=eq.CANCELLED",
        ""};

    private LinearLayout list;
    private EditText search;
    private JSONArray rows = new JSONArray();
    private final Map<String, double[]> qtyByPo = new HashMap<>();
    private final Map<String, String> uomByPo = new HashMap<>();
    private final Map<String, Integer> linesByPo = new HashMap<>();
    private final Map<String, JSONObject> parts = new HashMap<>();
    private int[] counts = new int[3];

    public OrdersScreen(MainActivity a) { super(a); }

    @Override public String title() { return segment == 0 ? "Purchase Orders" : "Customer Orders"; }
    @Override public String subtitle() { return segment == 0 ? "Approval · swipe a pending card right to approve" : "Open orders · tap to track every stage"; }
    @Override public int tab() { return 1; }

    @Override
    public View build() {
        newPage();
        LinearLayout seg = Ui.hbox(a);
        seg.setBackground(Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 12, a));
        seg.setPadding(dp(3), dp(3), dp(3), dp(3));
        String[] names = {"Purchase Orders", "Customer Orders"};
        for (int i = 0; i < 2; i++) {
            final int index = i;
            TextView t = Ui.text(a, names[i], 13, i == segment ? Color.WHITE : Ui.TEAL_DARK, true);
            t.setGravity(Gravity.CENTER);
            t.setPadding(0, dp(9), 0, dp(9));
            if (i == segment) t.setBackground(Ui.round(Ui.TEAL, 0, 0, 10, a));
            t.setOnClickListener(v -> { segment = index; a.rebuild(); });
            seg.addView(t, Ui.weight(1));
        }
        add(seg, 0);

        if (segment == 0) {
            LinearLayout chips = Ui.hbox(a);
            for (int i = 0; i < FILTERS.length; i++) {
                final int index = i;
                String label = FILTERS[i] + (i < 3 && counts[i] > 0 ? " " + counts[i] : "");
                TextView chip = Ui.text(a, label, 12, i == filter ? Color.WHITE : Ui.TEXT, i == filter);
                chip.setGravity(Gravity.CENTER);
                chip.setPadding(dp(4), dp(8), dp(4), dp(8));
                chip.setBackground(i == filter ? Ui.round(Ui.TEAL, 0, 0, 10, a) : Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 10, a));
                chip.setOnClickListener(v -> { filter = index; a.rebuild(); });
                LinearLayout.LayoutParams lp = Ui.weight(1);
                lp.rightMargin = i < FILTERS.length - 1 ? dp(6) : 0;
                chips.addView(chip, lp);
            }
            add(chips, 10);
        }

        search = Ui.input(a, segment == 0 ? "Search PO number / supplier" : "Search order / position / part", false);
        add(search, 10);
        list = Ui.vbox(a);
        add(list, 4);
        list.addView(loading());
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
            @Override public void afterTextChanged(Editable e) { fill(); }
        });
        if (segment == 0) loadPurchaseOrders(); else loadCustomerOrders();
        return scroll;
    }

    // ------------------------------------------------------------------ POs
    private void loadPurchaseOrders() {
        Api.async(() -> {
            int[] c = new int[3];
            for (int i = 0; i < 3; i++) c[i] = api.count("supply_purchase_orders?select=id" + FILTER_QUERY[i]);
            JSONArray data = api.rows("supply_purchase_orders?select=id,po_number,po_type,order_date,delivery_date,grand_total,currency,status,approval_status,vendor_snapshot,submitted_at,approved_at&order=created_at.desc&limit=200" + FILTER_QUERY[filter]);
            StringBuilder ids = new StringBuilder();
            for (int i = 0; i < data.length(); i++) {
                if (ids.length() > 0) ids.append(',');
                ids.append(data.getJSONObject(i).getString("id"));
            }
            JSONArray items = ids.length() == 0 ? new JSONArray() : api.rows("supply_purchase_order_items?select=purchase_order_id,quantity,uom&limit=5000&purchase_order_id=in.(" + ids + ")");
            qtyByPo.clear(); uomByPo.clear(); linesByPo.clear();
            for (int i = 0; i < items.length(); i++) {
                JSONObject it = items.getJSONObject(i);
                String po = it.optString("purchase_order_id");
                double[] q = qtyByPo.get(po);
                if (q == null) { q = new double[1]; qtyByPo.put(po, q); }
                q[0] += it.optDouble("quantity", 0);
                uomByPo.put(po, it.optString("uom", ""));
                Integer n = linesByPo.get(po);
                linesByPo.put(po, n == null ? 1 : n + 1);
            }
            counts = c;
            return data;
        }, (data, err) -> {
            list.removeAllViews();
            if (err != null) { list.addView(error(err, this::reload)); return; }
            rows = data;
            fill();
        });
    }

    private void fill() {
        if (list == null) return;
        list.removeAllViews();
        String q = search == null ? "" : search.getText().toString().trim().toLowerCase(Locale.ROOT);
        int shown = 0;
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.optJSONObject(i);
            if (r == null) continue;
            View card = segment == 0 ? poCard(r, q) : orderCard(r, q);
            if (card == null) continue;
            list.addView(card, Ui.matchWrap(a, 8));
            shown++;
        }
        if (shown == 0) list.addView(Ui.empty(a, rows.length() == 0 ? "Nothing here." : "No match for \"" + q + "\"."));
        if (api.lastCallOffline) list.addView(Ui.chip(a, "Offline · last saved data", "amber"), 0);
    }

    private static String supplier(JSONObject po) {
        JSONObject v = po.optJSONObject("vendor_snapshot");
        return v == null ? "" : v.optString("party_name", "");
    }

    @SuppressLint("ClickableViewAccessibility")
    private View poCard(JSONObject po, String q) {
        String number = po.optString("po_number");
        String sup = supplier(po);
        if (!q.isEmpty() && !(number.toLowerCase(Locale.ROOT).contains(q) || sup.toLowerCase(Locale.ROOT).contains(q))) return null;
        final String id = po.optString("id");
        String approval = po.optString("approval_status");
        String status = po.optString("status");
        boolean cancelled = "CANCELLED".equalsIgnoreCase(status);
        boolean pending = !cancelled && "PENDING_APPROVAL".equalsIgnoreCase(approval);

        LinearLayout card = Ui.card(a);
        LinearLayout top = Ui.hbox(a);
        top.addView(Ui.text(a, number, 15, Ui.TEXT, true), Ui.weight(1));
        String chip = cancelled ? "Cancelled" : Ui.pretty(approval);
        top.addView(Ui.chip(a, chip, Ui.tone(chip)));
        card.addView(top);
        card.addView(Ui.text(a, Ui.pretty(po.optString("po_type")) + " · " + sup + " · " + Ui.date(po.optString("order_date")), 12, Ui.MUTED, false));
        double[] qty = qtyByPo.get(id);
        Integer lines = linesByPo.get(id);
        String uom = uomByPo.containsKey(id) ? " " + uomByPo.get(id).toLowerCase(Locale.ROOT).replace("kgs", "kg") : "";
        TextView sum = Ui.text(a, (lines == null ? 0 : lines) + " line(s) · " + (qty == null ? "-" : Ui.num(qty[0], 3) + uom) + " · " + Ui.money(po.optDouble("grand_total", 0), po.optString("currency")), 12.5f, Ui.TEXT, true);
        sum.setPadding(0, dp(4), 0, 0);
        card.addView(sum);
        Ui.clickable(card, Color.WHITE, Ui.LINE, 14);
        card.setOnClickListener(v -> a.push(new PoDetailScreen(a, id)));
        if (pending) enableSwipeApprove(card, id, number);
        return card;
    }

    /** Swipe a pending card to the right to approve it (with confirmation). */
    @SuppressLint("ClickableViewAccessibility")
    private void enableSwipeApprove(View card, String id, String number) {
        final float[] start = new float[2];
        final boolean[] swiping = new boolean[1];
        card.setOnTouchListener((v, e) -> {
            switch (e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    start[0] = e.getRawX(); start[1] = e.getRawY(); swiping[0] = false;
                    return false;
                case MotionEvent.ACTION_MOVE: {
                    float dx = e.getRawX() - start[0], dy = e.getRawY() - start[1];
                    if (!swiping[0] && dx > dp(16) && Math.abs(dx) > Math.abs(dy) * 1.5f) {
                        swiping[0] = true;
                        v.getParent().requestDisallowInterceptTouchEvent(true);
                        v.setPressed(false);
                    }
                    if (swiping[0]) {
                        v.setTranslationX(Math.max(0, dx));
                        v.setAlpha(1f - Math.min(0.5f, dx / (v.getWidth() * 2f)));
                        return true;
                    }
                    return false;
                }
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL:
                    if (swiping[0]) {
                        float dx = e.getRawX() - start[0];
                        v.animate().translationX(0).alpha(1f).setDuration(180).start();
                        if (e.getActionMasked() == MotionEvent.ACTION_UP && dx > v.getWidth() * 0.35f) {
                            a.confirm("Approve " + number + "?", "The PO is approved without emailing the supplier. Open the PO to choose print sections or to send it to the supplier.",
                                "Approve", () -> PoDetailScreen.approve(a, id, null, false, () -> a.rebuild()));
                        }
                        swiping[0] = false;
                        return true;
                    }
                    return false;
                default:
                    return false;
            }
        });
    }

    // ------------------------------------------------------------------ customer orders
    private void loadCustomerOrders() {
        Api.async(() -> {
            JSONArray data = api.rows("supply_customer_orders?select=id,master_reference_no,customer_order_no,order_position,part_id,order_qty_pcs,required_rm_kg,customer_delivery_date,status,supply_flow&status=in.(OPEN,IN_PROGRESS)&order=customer_delivery_date.asc&limit=500");
            StringBuilder ids = new StringBuilder();
            for (int i = 0; i < data.length(); i++) {
                String pid = data.getJSONObject(i).optString("part_id", "");
                if (pid.isEmpty() || "null".equals(pid) || ids.indexOf(pid) >= 0) continue;
                if (ids.length() > 0) ids.append(',');
                ids.append(pid);
            }
            if (ids.length() > 0) {
                JSONArray p = api.rows("parts?select=id,part_number,fsi_part_number,part_name&limit=1000&id=in.(" + ids + ")");
                for (int i = 0; i < p.length(); i++) parts.put(p.getJSONObject(i).getString("id"), p.getJSONObject(i));
            }
            return data;
        }, (data, err) -> {
            list.removeAllViews();
            if (err != null) { list.addView(error(err, this::reload)); return; }
            rows = data;
            fill();
        });
    }

    private View orderCard(JSONObject o, String q) {
        JSONObject part = parts.get(o.optString("part_id"));
        String ref = o.optString("master_reference_no", o.optString("customer_order_no"));
        String partNo = part == null ? "" : part.optString("part_number");
        String fsi = part == null ? "" : part.optString("fsi_part_number");
        String hay = (ref + " " + o.optString("order_position") + " " + partNo + " " + fsi).toLowerCase(Locale.ROOT);
        if (!q.isEmpty() && !hay.contains(q)) return null;
        LinearLayout card = Ui.card(a);
        LinearLayout top = Ui.hbox(a);
        top.addView(Ui.text(a, ref + " · Pos " + o.optString("order_position", "-"), 14, Ui.TEXT, true), Ui.weight(1));
        String status = o.optString("status");
        top.addView(Ui.chip(a, Ui.pretty(status), Ui.tone(status)));
        card.addView(top);
        card.addView(Ui.text(a, "Part " + partNo + (fsi.isEmpty() ? "" : " · FSI " + fsi) + (part == null ? "" : " · " + part.optString("part_name")), 12, Ui.MUTED, false));
        TextView qty = Ui.text(a, Ui.num(o.optDouble("order_qty_pcs", 0), 0) + " pcs · RM " + Ui.num(o.optDouble("required_rm_kg", 0), 3) + " kg · Due " + Ui.date(o.optString("customer_delivery_date")), 12.5f, Ui.TEXT, true);
        qty.setPadding(0, dp(4), 0, 0);
        card.addView(qty);
        Ui.clickable(card, Color.WHITE, Ui.LINE, 14);
        final String id = o.optString("id");
        final String label = ref + " · Pos " + o.optString("order_position", "-");
        card.setOnClickListener(v -> a.push(new OrderTrackerScreen(a, id, label)));
        return card;
    }
}
