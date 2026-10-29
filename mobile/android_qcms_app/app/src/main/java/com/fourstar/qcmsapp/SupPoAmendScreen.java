package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * R39 · Amend Purchase Order (web supply_chain._render_po_amendment, R37b): Effective Date (separate from the PO date),
 * new unit price / quantity per line (the price-history revision effective on that date is suggested), commercial terms
 * and a mandatory reason. The PO number stays; Amendment No. + Amendment Date + Effective Date print in the PO header and
 * the AMENDMENT HISTORY page lists every change. A changed price is added to Part Master price history from the Effective
 * Date. Quantity never goes below the received quantity. The amended PO returns to approval (password required).
 */
final class SupPoAmendScreen extends Screen {
    private final String poId;
    private JSONObject header;
    private List<JSONObject> amendments = new ArrayList<>();
    private List<JSONObject> rows;
    private FormView form;
    private RowsEditor grid;
    private boolean saving;
    private String suggestedFor = "";

    SupPoAmendScreen(MainActivity a, String poId) { super(a); this.poId = poId; }

    @Override public String title() { return header == null ? "Amend PO" : "Amend " + SupSvc.s(header, "po_number"); }
    @Override public String subtitle() { return header == null ? "" : "Next = Amendment " + (next()) + (current() > 0 ? " · current " + SupSvc.poDisplayNumber(header) : ""); }
    @Override public int tab() { return Catalog.SUPPLY; }

    private int current() { return (int) Math.round(SupSvc.num(header, "amendment_no")); }
    private int next() { return current() + 1; }

    @Override
    public View build() {
        newPage();
        if (rows != null) { render(); return scroll; }
        page.addView(loading());
        Api.async(() -> {
            SupSvc svc = new SupSvc(api);
            JSONObject h = svc.get("supply_purchase_orders", poId);
            if (SupSvc.empty(h)) throw new Api.ApiException(404, "Purchase Order not found or not visible for your role.");
            if ("CANCELLED".equals(SupSvc.up(h, "status"))) throw new Api.ApiException(422, "A cancelled Purchase Order cannot be amended. Use Cancel & Reissue.");
            if (!AdmPerm.current(api, "SUPPLY_CHAIN", "can_edit")) throw new Api.ApiException(403, "Purchase Order Edit permission is required to amend a PO.");
            List<JSONObject> items = svc.live("supply_purchase_order_items?select=*&purchase_order_id=eq." + poId + "&order=created_at.asc&limit=1000");
            List<JSONObject> out = new ArrayList<>();
            String today = Ui.today();
            int index = 0;
            for (JSONObject it : items) {
                index++;
                JSONObject r = new JSONObject();
                r.put("id", SupSvc.s(it, "id"));
                r.put("line", index);
                r.put("item", Lookups.join(SupSvc.s(it, "item_no"), SupSvc.s(it, "item_description")));
                r.put("uom", SupSvc.s(it, "uom"));
                r.put("received_qty", svc.purchaseOrderItemReceivedQty(it, h));
                r.put("current_qty", SupSvc.num(it, "quantity"));
                r.put("new_qty", SupSvc.num(it, "quantity"));
                r.put("current_price", SupSvc.num(it, "unit_price"));
                r.put("_item", it);
                suggest(svc, h, r, today);
                out.add(r);
            }
            return new Object[]{h, svc.purchaseOrderAmendments(poId, h), out};
        }, (r, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            header = (JSONObject) r[0];
            @SuppressWarnings("unchecked") List<JSONObject> am = (List<JSONObject>) r[1];
            @SuppressWarnings("unchecked") List<JSONObject> rs = (List<JSONObject>) r[2];
            amendments = am;
            rows = rs;
            suggestedFor = Ui.today();
            a.rebuildTitle(this);
            render();
        });
        return scroll;
    }

    @Override public void reload() { rows = null; form = null; grid = null; a.rebuild(); }

    /** amendment_price_suggestion → "Price History (Effective)" text and the default New Unit Price. */
    private static void suggest(SupSvc svc, JSONObject header, JSONObject r, String effective) throws Exception {
        JSONObject s = svc.amendmentPriceSuggestion(header, r.getJSONObject("_item"), effective);
        double current = SupSvc.num(r, "current_price");
        if (s.length() > 0 && SupSvc.num(s, "price") > 0) {
            r.put("history", Ui.num(SupSvc.num(s, "price"), 2) + " from " + Ui.date(SupSvc.s(s, "start_date")) + (s.optBoolean("covering") ? "" : " (latest)"));
            r.put("new_price", SupSvc.num(s, "price"));
        } else {
            r.put("history", "No price history");
            r.put("new_price", current);
        }
    }

    private static void detach(View v) { if (v != null && v.getParent() != null) ((android.view.ViewGroup) v.getParent()).removeView(v); }

    private void render() {
        page.removeAllViews();
        add(Ui.text(a, "The PO number stays the same; the amendment number, amendment date and Effective Date print in the PO header and in the AMENDMENT HISTORY page. "
            + "A changed price is added to Part Master price history from the Effective Date so later POs use it. Quantity can never go below the quantity already received. "
            + "The amended PO returns to approval; on approval the supplier-safe copy downloads and it is e-mailed to the supplier through the normal PO e-mail.", 11.5f, Ui.MUTED, false), 0);
        if (!amendments.isEmpty()) {
            List<List<String>> data = new ArrayList<>();
            for (JSONObject am : amendments) {
                JSONArray l = am.optJSONArray("lines");
                data.add(Arrays.asList(String.valueOf((int) SupSvc.num(am, "amendment_no")), Ui.date(SupSvc.s(am, "amendment_date")), Ui.date(SupSvc.s(am, "effective_date")),
                    SupSvc.s(am, "reason"), String.valueOf(l == null ? 0 : l.length()), Ui.pretty(SupSvc.s(am, "status"))));
            }
            add(new DataGrid(a, "Amendment history", Arrays.asList("Amd No.", "Amendment Date", "Effective Date", "Reason", "Lines Changed", "Status"), data, 220, null), 8);
        }
        if (form == null) {
            List<Field> f = new ArrayList<>();
            f.add(Field.date("effective_date", "Effective Date (prices / quantities apply from)").req()
                .hint("Can differ from the PO date. The default new unit price is the Part Master price-history revision effective on this date."));
            f.add(Field.date("delivery_date", "Delivery Date"));
            f.add(Field.text("payment_term", "Payment Term"));
            f.add(Field.text("incoterm", "Incoterm"));
            f.add(Field.text("ship_via", "Ship Via"));
            f.add(Field.number("other_amount", "Other Charges").range(0, Double.MAX_VALUE));
            f.add(Field.text("remarks", "PO Remarks"));
            f.add(Field.area("reason", "Amendment Reason (mandatory, printed on the PO)").req());
            form = new FormView(a, f);
            form.set("effective_date", Ui.today());
            String delivery = SupSvc.d10(SupSvc.s(header, "delivery_date"));
            if (!delivery.isEmpty()) form.set("delivery_date", delivery);
            for (String k : new String[]{"payment_term", "incoterm", "ship_via", "remarks"}) form.set(k, SupSvc.s(header, k));
            form.set("other_amount", Ui.num(SupSvc.num(header, "other_amount"), 2).replace(",", ""));
            form.onChange((k, v) -> { if ("effective_date".equals(k)) resuggest(); });
            grid = new RowsEditor(a, "PO lines", Arrays.asList(
                Field.info("item", "Item"), Field.info("uom", "UOM"), Field.info("received_qty", "Received Qty"), Field.info("current_qty", "Current Qty"),
                Field.info("current_price", "Current Unit Price"), Field.info("history", "Price History (Effective)"),
                Field.number("new_qty", "New Qty").range(0.001, Double.MAX_VALUE).req(), Field.number("new_price", "New Unit Price").range(0.0001, Double.MAX_VALUE).req()),
                Arrays.asList(new String[]{"line", "Line"}, new String[]{"item", "Item"}, new String[]{"uom", "UOM"}, new String[]{"received_qty", "Received Qty"},
                    new String[]{"current_qty", "Current Qty"}, new String[]{"new_qty", "New Qty"}, new String[]{"current_price", "Current Unit Price"},
                    new String[]{"history", "Price History (Effective)"}, new String[]{"new_price", "New Unit Price"})).fixedRows();
            grid.setRows(rows);
        } else { detach(form); detach(grid); }
        LinearLayout card = Ui.card(a);
        card.addView(form);
        add(card, 8);
        add(Ui.label(a, "Lines · tap a line to change New Qty / New Unit Price"), 12);
        add(grid, 4);
        Button save = Ui.primary(a, "Save Amendment " + next() + " & Submit for Approval");
        save.setOnClickListener(v -> {
            String problem = form.validate();
            if (problem != null) { a.toast(problem); return; }
            if (form.str("reason").trim().isEmpty()) { a.toast("Amendment Reason is required."); return; }
            a.confirmPassword("Confirm the PO amendment with your password", () -> save(save));
        });
        add(save, 16);
        if (api.employeeId == null || api.employeeId.isEmpty())
            add(Ui.text(a, "Your login is not linked to an ACTIVE Employee Master record - the amendment cannot be submitted.", 12, Ui.RED_FG, false), 6);
    }

    private void resuggest() {
        String eff = form.str("effective_date");
        if (eff.isEmpty() || eff.equals(suggestedFor)) return;
        suggestedFor = eff;
        JSONObject h = header;
        Api.async(() -> {
            SupSvc svc = new SupSvc(api);
            for (JSONObject r : grid.rows()) suggest(svc, h, r, eff);
            return true;
        }, (ok, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            grid.refresh();
        });
    }

    private void save(Button button) {
        if (saving) return;
        saving = true;
        button.setEnabled(false);
        button.setText("Saving amendment…");
        Api.async(() -> {
            JSONObject p = new JSONObject();
            p.put("reason", form.str("reason").trim());
            p.put("effective_date", form.str("effective_date"));
            JSONArray lines = new JSONArray();
            for (JSONObject r : grid.rows()) lines.put(new JSONObject().put("id", SupSvc.s(r, "id")).put("unit_price", r.opt("new_price")).put("quantity", r.opt("new_qty")));
            p.put("lines", lines);
            p.put("delivery_date", form.str("delivery_date"));
            for (String k : new String[]{"payment_term", "incoterm", "ship_via", "remarks"}) p.put(k, form.str(k));
            p.put("other_amount", form.str("other_amount").isEmpty() ? 0 : SupSvc.num(form.str("other_amount")));
            return new SupSvc(api).amendPurchaseOrder(poId, p);
        }, (res, err) -> {
            saving = false;
            button.setEnabled(true);
            button.setText("Save Amendment " + next() + " & Submit for Approval");
            if (err != null) { a.toast(Api.message(err)); return; }
            JSONArray warn = res.optJSONArray("warnings");
            StringBuilder w = new StringBuilder();
            for (int i = 0; warn != null && i < warn.length(); i++) w.append(' ').append(warn.optString(i));
            a.confirm("Amendment saved", SupSvc.s(res, "display_number") + " saved (Effective " + Ui.date(form.str("effective_date")) + ") and sent for approval. "
                + "Price history updated for changed prices." + (w.length() > 0 ? "\n\nNote:" + w : ""), "OK", () -> { });
            a.back();
        });
    }
}
