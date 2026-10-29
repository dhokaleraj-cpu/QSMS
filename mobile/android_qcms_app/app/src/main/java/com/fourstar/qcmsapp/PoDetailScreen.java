package com.fourstar.qcmsapp;

import android.graphics.Color;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Purchase Order preview with print-section choice, send / do-not-send choice, approve and cancel. */
public final class PoDetailScreen extends Screen implements ExportKit.RecordPrint {
    /** Same flags as the QCMS website (core/po_print_ui.SECTION_OPTIONS). */
    static final String[][] SECTIONS = {
        {"show_plant", "Plant / Company Branch"}, {"show_vendor", "Vendor"}, {"show_reference", "Reference Details"},
        {"show_old_po", "Old PO Details"}, {"show_ship_to", "Ship To"}, {"show_source_reference", "PO Source Ref (internal only)"},
        {"show_technical", "RM Details & Technical Data"}, {"show_price_history", "Price Revision History"},
        {"show_special_instructions", "Comments / Special Instructions"}, {"show_approval_stamp", "Approval Stamp"}};

    private final String id;
    private String number = "";
    private boolean sendToSupplier = true;
    private final Map<String, CheckBox> sectionBoxes = new LinkedHashMap<>();

    public PoDetailScreen(MainActivity a, String id) { super(a); this.id = id; }

    // R37: the PO PDF viewer (Preview · Save to Downloads · Share) from the top-bar ⇩ too
    @Override public boolean layoutReady() { return id != null && !id.isEmpty(); }
    @Override public void printLayout() { SndPdfView.forPo(a, id); }

    @Override public String title() { return number.isEmpty() ? "Purchase Order" : number; }
    @Override public String subtitle() { return "Preview · print sections · approval"; }
    @Override public int tab() { return 1; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONArray h = api.rows("supply_purchase_orders?select=*&id=eq." + id);
            if (h.length() == 0) throw new Api.ApiException(404, "Purchase Order not found or not visible for your role.");
            JSONObject header = h.getJSONObject(0);
            JSONArray items = api.rows("supply_purchase_order_items?select=item_no,item_description,rm_section,quantity,uom,unit_price,line_total,hsn_sac_code,gst_percent&purchase_order_id=eq." + id + "&order=created_at.asc");
            JSONArray sources = api.rows("supply_purchase_order_sources?select=customer_order_id,allocated_qty,allocation_uom&purchase_order_id=eq." + id);
            StringBuilder ids = new StringBuilder();
            for (int i = 0; i < sources.length(); i++) {
                if (ids.length() > 0) ids.append(',');
                ids.append(sources.getJSONObject(i).optString("customer_order_id"));
            }
            JSONArray orders = ids.length() == 0 ? new JSONArray() : api.rows("supply_customer_orders?select=id,master_reference_no,customer_order_no,order_position&id=in.(" + ids + ")");
            return new JSONObject().put("header", header).put("items", items).put("sources", sources).put("orders", orders);
        }, (data, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            render(data);
        });
        return scroll;
    }

    private void render(JSONObject data) {
        JSONObject h = data.optJSONObject("header");
        JSONArray items = data.optJSONArray("items");
        if (h == null || items == null) return;
        number = h.optString("po_number");
        a.rebuildTitle(this);
        offlineNote();
        String status = h.optString("status");
        String approval = h.optString("approval_status");
        boolean cancelled = "CANCELLED".equalsIgnoreCase(status);
        boolean pending = !cancelled && "PENDING_APPROVAL".equalsIgnoreCase(approval);
        String currency = h.optString("currency");

        // ---- header
        LinearLayout card = Ui.card(a);
        LinearLayout top = Ui.hbox(a);
        top.addView(Ui.text(a, "PURCHASE ORDER", 12, Ui.TEAL_DARK, true), Ui.weight(1));
        String chip = cancelled ? "Cancelled" : Ui.pretty(approval);
        top.addView(Ui.chip(a, chip, Ui.tone(chip)));
        card.addView(top);
        card.addView(Ui.text(a, number, 20, Ui.TEXT, true));
        JSONObject vendor = h.optJSONObject("vendor_snapshot");
        card.addView(Ui.pair(a, "Type", Ui.pretty(h.optString("po_type"))));
        card.addView(Ui.pair(a, "Supplier", vendor == null ? "-" : vendor.optString("party_name")));
        card.addView(Ui.pair(a, "PO date", Ui.date(h.optString("order_date"))));
        card.addView(Ui.pair(a, "Delivery date", Ui.date(h.optString("delivery_date"))));
        card.addView(Ui.pair(a, "Requisitioner", h.optString("requisitioner")));
        card.addView(Ui.pair(a, "Payment term", h.optString("payment_term")));
        card.addView(Ui.pair(a, "Incoterm · Ship via", h.optString("incoterm") + " · " + h.optString("ship_via")));
        if (!h.isNull("quotation_reference")) card.addView(Ui.pair(a, "Quotation", h.optString("quotation_reference") + " · " + Ui.date(h.optString("quotation_date"))));
        if (!h.isNull("approved_at")) card.addView(Ui.pair(a, "Approved", Ui.date(h.optString("approved_at"))));
        if (h.optDouble("amendment_no", 0) > 0) {   // R39 (web R37b): Amendment No. · Amendment Date · Effective Date
            card.addView(Ui.pair(a, "Amendment", SupSvc.poDisplayNumber(h) + " · " + Ui.date(h.optString("amendment_date")) + " · effective " + Ui.date(h.optString("amendment_effective_date"))));
            if (!h.isNull("amendment_reason")) card.addView(Ui.pair(a, "Amendment reason", h.optString("amendment_reason")));
        }
        if (cancelled) card.addView(Ui.pair(a, "Cancel reason", h.optString("cancellation_reason")));
        add(card, 2);

        // ---- customer orders on this PO
        JSONArray sources = data.optJSONArray("sources");
        JSONArray orders = data.optJSONArray("orders");
        if (sources != null && sources.length() > 0) {
            Map<String, JSONObject> byId = new LinkedHashMap<>();
            for (int i = 0; orders != null && i < orders.length(); i++) byId.put(orders.optJSONObject(i).optString("id"), orders.optJSONObject(i));
            LinearLayout oc = Ui.card(a);
            oc.addView(Ui.text(a, "Customer Orders on this PO (" + sources.length() + ")", 13.5f, Ui.TEXT, true));
            for (int i = 0; i < sources.length(); i++) {
                JSONObject s = sources.optJSONObject(i);
                JSONObject o = byId.get(s.optString("customer_order_id"));
                String ref = o == null ? "-" : o.optString("master_reference_no", o.optString("customer_order_no")) + " · Pos " + o.optString("order_position", "-");
                oc.addView(Ui.pair(a, ref, Ui.num(s.optDouble("allocated_qty", 0), 3) + " " + s.optString("allocation_uom", "").toLowerCase(Locale.ROOT)));
            }
            add(oc, 10);
        }

        // ---- lines (scrollable grid)
        add(Ui.label(a, "PO lines (" + items.length() + ") · scroll ← → ↑ ↓"), 6);
        List<String> cols = Arrays.asList("#", "Item No.", "Description", "RM Section", "Qty", "UOM", "Rate", "Amount", "HSN/SAC", "GST %");
        List<List<String>> rows = new ArrayList<>();
        Map<String, Double> qtyByUom = new LinkedHashMap<>();
        for (int i = 0; i < items.length(); i++) {
            JSONObject it = items.optJSONObject(i);
            double qty = it.optDouble("quantity", 0);
            String uom = it.optString("uom", "");
            Double prev = qtyByUom.get(uom);
            qtyByUom.put(uom, (prev == null ? 0 : prev) + qty);
            rows.add(Arrays.asList(String.valueOf(i + 1), it.optString("item_no"), it.optString("item_description"), nz(it.optString("rm_section")),
                Ui.num(qty, 3), uom, Ui.num(it.optDouble("unit_price", 0), 4), Ui.num(it.optDouble("line_total", 0), 2), it.optString("hsn_sac_code"), Ui.num(it.optDouble("gst_percent", 0), 2)));
        }
        add(new DataGrid(a, cols, rows, 320, null), 2);

        // ---- totals
        LinearLayout tot = Ui.card(a);
        StringBuilder q = new StringBuilder();
        for (Map.Entry<String, Double> e : qtyByUom.entrySet()) {
            if (q.length() > 0) q.append(" + ");
            q.append(Ui.num(e.getValue(), 3)).append(' ').append(e.getKey());
        }
        tot.addView(Ui.pair(a, "Total quantity", q.toString()));
        tot.addView(Ui.pair(a, "Subtotal", Ui.money(h.optDouble("subtotal", 0), currency)));
        if (h.optDouble("cgst_amount", 0) > 0) tot.addView(Ui.pair(a, "CGST", Ui.money(h.optDouble("cgst_amount", 0), currency)));
        if (h.optDouble("sgst_amount", 0) > 0) tot.addView(Ui.pair(a, "SGST", Ui.money(h.optDouble("sgst_amount", 0), currency)));
        if (h.optDouble("igst_amount", 0) > 0) tot.addView(Ui.pair(a, "IGST", Ui.money(h.optDouble("igst_amount", 0), currency)));
        if (h.optDouble("other_amount", 0) > 0) tot.addView(Ui.pair(a, "Other charges", Ui.money(h.optDouble("other_amount", 0), currency)));
        tot.addView(Ui.divider(a));
        LinearLayout grand = Ui.pair(a, "GRAND TOTAL", Ui.money(h.optDouble("grand_total", 0), currency));
        ((TextView) grand.getChildAt(1)).setTextSize(16);
        ((TextView) grand.getChildAt(1)).setTextColor(Ui.TEAL_DARK);
        tot.addView(grand);
        add(tot, 10);

        if (pending) renderApproval(h);
        else if (!cancelled) {
            Button send = Ui.primary(a, "Send approved PO to supplier (PDF + email preview)");
            send.setOnClickListener(v -> SndPoSend.open(a, id));
            add(send, 14);
        }
        Button web = Ui.outline(a, "🖨 Open PO PDF (print sections as saved) · Preview · Save · Share", Ui.TEAL);
        web.setOnClickListener(v -> SndPdfView.forPo(a, id));
        add(web, 10);
        if (!cancelled) {
            // R39 (web R37b): controlled amendment - PO number stays, Amendment No. + Effective Date, price history, back to approval
            int amd = (int) Math.round(h.optDouble("amendment_no", 0));
            Button amend = Ui.outline(a, "Amend PO · next = Amendment " + (amd + 1) + " (price / qty from an Effective Date)", Ui.TEAL_DARK);
            amend.setOnClickListener(v -> a.push(new SupPoAmendScreen(a, id)));
            add(amend, 10);
            Button cancel = Ui.outline(a, "Cancel PO (reason required)", Ui.ORANGE);
            cancel.setOnClickListener(v -> a.askText("Cancel " + number, "Reason for cancellation", "Cancel PO", true, reason -> cancel(reason)));
            add(cancel, 10);
        }
    }

    private static String nz(String v) { return v == null || "null".equals(v) ? "" : v; }

    private void renderApproval(JSONObject h) {
        JSONObject saved = h.optJSONObject("print_options");
        add(Ui.label(a, "Print sections (ticked = printed on the PO)"), 10);
        LinearLayout box = Ui.card(a);
        LinearLayout row = null;
        for (int i = 0; i < SECTIONS.length; i++) {
            if (i % 2 == 0) { row = Ui.hbox(a); box.addView(row); }
            CheckBox cb = new CheckBox(a);
            cb.setText(SECTIONS[i][1]);
            cb.setTextSize(12);
            cb.setTextColor(Ui.TEXT);
            cb.setChecked(saved == null || saved.optBoolean(SECTIONS[i][0], true));
            sectionBoxes.put(SECTIONS[i][0], cb);
            row.addView(cb, Ui.weight(1));
        }
        add(box, 2);

        add(Ui.label(a, "After approval"), 10);
        LinearLayout seg = Ui.hbox(a);
        TextView yes = Ui.text(a, "Approve & send to supplier", 12.5f, Ui.TEXT, true);
        TextView no = Ui.text(a, "Approve, do not send", 12.5f, Ui.TEXT, true);
        for (TextView t : new TextView[]{yes, no}) { t.setGravity(Gravity.CENTER); t.setPadding(dp(6), dp(11), dp(6), dp(11)); }
        Runnable paint = () -> {
            yes.setBackground(sendToSupplier ? Ui.round(Ui.TEAL, 0, 0, 10, a) : Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 10, a));
            yes.setTextColor(sendToSupplier ? Color.WHITE : Ui.TEXT);
            no.setBackground(!sendToSupplier ? Ui.round(Ui.TEAL, 0, 0, 10, a) : Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 10, a));
            no.setTextColor(!sendToSupplier ? Color.WHITE : Ui.TEXT);
        };
        paint.run();
        yes.setOnClickListener(v -> { sendToSupplier = true; paint.run(); });
        no.setOnClickListener(v -> { sendToSupplier = false; paint.run(); });
        LinearLayout.LayoutParams l = Ui.weight(1); l.rightMargin = dp(6);
        seg.addView(yes, l);
        seg.addView(no, Ui.weight(1));
        add(seg, 2);
        TextView hint = Ui.text(a, "Sending opens the QCMS email preview: To = supplier, CC, message and the PO PDF with the ticked sections.", 11.5f, Ui.MUTED, false);
        add(hint, 4);

        EditText remarks = Ui.input(a, "Approval remarks (optional)", false);
        add(remarks, 10);
        Button approve = Ui.primary(a, "Approve Purchase Order");
        add(approve, 10);
        approve.setOnClickListener(v -> a.confirm("Approve " + number + "?",
            sendToSupplier ? "After approval the email preview opens so you can send the PO to the supplier." : "The PO is approved. Nothing is emailed to the supplier now.",
            "Approve", () -> {
                approve.setEnabled(false);
                approve.setText("Approving…");
                JSONObject options = new JSONObject();
                try { for (Map.Entry<String, CheckBox> e : sectionBoxes.entrySet()) options.put(e.getKey(), e.getValue().isChecked()); } catch (Exception ignored) { }
                approve(a, id, options, sendToSupplier, () -> {
                    if (sendToSupplier) SndPoSend.open(a, id);
                    else a.rebuild();
                }, remarks.getText().toString().trim());
            }));
    }

    static void approve(MainActivity a, String id, JSONObject options, boolean send, Runnable done) {
        approve(a, id, options, send, done, "");
    }

    /** Same server steps as the website: approve RPC, save print sections, open supplier confirmation. */
    static void approve(MainActivity a, String id, JSONObject options, boolean send, Runnable done, String remarks) {
        Api api = Api.get(a);
        Api.async(() -> {
            JSONObject args = new JSONObject();
            args.put("p_purchase_order_id", id);
            args.put("p_remarks", remarks == null || remarks.isEmpty() ? JSONObject.NULL : remarks);
            api.rpc("qcms_approve_purchase_order", args);
            if (options != null) {
                try { api.patch("supply_purchase_orders", id, new JSONObject().put("print_options", options)); } catch (Exception ignored) { }
            }
            try { api.rpc("qcms_ensure_po_confirmation", new JSONObject().put("p_purchase_order_id", id)); } catch (Exception ignored) { }
            return true;
        }, (ok, err) -> {
            if (err != null) {
                a.toast(Api.message(err));
                a.rebuild();
                return;
            }
            a.toast(send ? "Approved. Check the email preview and send." : "Purchase Order approved.");
            done.run();
            autoDownloadApproved(a, id);   // R38: approved PO copy downloads + opens right after approval
        });
    }

    /**
     * R39 (web R38 _po_approved_auto_download): right after approval the supplier-safe copy of the approved PO
     * (no customer source reference) is saved to Downloads as "<PO>[_AmdN].pdf" and opened in the PDF viewer.
     */
    static void autoDownloadApproved(MainActivity a, String id) {
        Api api = Api.get(a);
        Api.async(() -> {
            SndData.Po po = SndData.load(api, id);
            if (!po.approved()) return null;
            byte[] pdf = SndPoPdf.build(SndData.supplierSafe(po), null);
            String name = SndData.downloadFileName(po.header);
            return new Object[]{name, SndFiles.saveToDownloads(a, name, pdf, ExportKit.PDF), pdf};
        }, (r, err) -> {
            if (err != null) { a.toast("The approved PO copy could not be generated for download: " + Api.message(err)); return; }
            if (r == null) return;
            String name = (String) r[0];
            SndFiles.Saved saved = (SndFiles.Saved) r[1];
            if (saved != null && saved.uri != null) {
                a.toast("Purchase Order approved - " + name + " saved to Downloads.");
                SndFiles.open(a, saved.uri, ExportKit.PDF);
            } else {
                a.toast("Purchase Order approved - " + name + (saved == null ? "" : " saved: " + saved.where));
                SndPdfView.show(a, "Approved PO", name, (byte[]) r[2]);
            }
        });
    }

    private void cancel(String reason) {
        Api.async(() -> {
            JSONObject args = new JSONObject();
            args.put("p_purchase_order_id", id);
            args.put("p_reason", reason);
            return api.rpc("qcms_cancel_purchase_order", args);
        }, (ok, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast("PO cancelled. Its Customer Orders are free for a new PO.");
            a.rebuild();
        });
    }
}
