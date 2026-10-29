package com.fourstar.qcmsapp;

import android.graphics.Color;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/**
 * R39 · OSP Material Out "RETURNABLE DELIVERY CHALLAN" print - port of core/osp_challan_pdf.py (_render_plain +
 * _draw_supplier_box + challan_status_label watermark) on the shared PO-look kit SupPdfKit (A4 portrait, ReportLab
 * coordinates, saved PURCHASE_ORDER print layout colours, company logo).
 *
 * Vendor-facing: the payload is passed through OspChallan.vendorSafe first - FSI part number / description only, never
 * customer name / code / PO / order / customer part number / customer delivery date (core/customer_privacy.py).
 */
final class OspChallanPdf {
    private OspChallanPdf() { }

    /** Item rows per page: {rows when this is the last page, rows otherwise} (FIRST_PAGE_ROWS / NEXT_PAGE_ROWS). */
    static final int[] FIRST_PAGE_ROWS = {6, 13};
    static final int[] NEXT_PAGE_ROWS = {12, 19};
    /** po.PLANT fallback when the challan has no company branch. */
    static final String[] PLANT_FALLBACK = {"Four Star Industries Private Limited D9", "Plot No.D9, Chakan MIDC PH II", "Bhamboli, Khed", "Pune 410501",
        "27AAGCF3769A1ZP", "022 40104412", "orders@fourstarindustries.com"};

    /** challan_pages: the last page always keeps room for the process bar, totals and the supplier box. */
    static List<List<JSONObject>> pages(List<JSONObject> lines) {
        List<List<JSONObject>> pages = new ArrayList<>();
        List<JSONObject> remaining = new ArrayList<>(lines);
        int[] caps = FIRST_PAGE_ROWS;
        while (true) {
            if (remaining.size() <= caps[0]) { pages.add(remaining); return pages; }
            int take = Math.min(caps[1], remaining.size() - 1);
            pages.add(new ArrayList<>(remaining.subList(0, take)));
            remaining = new ArrayList<>(remaining.subList(take, remaining.size()));
            caps = NEXT_PAGE_ROWS;
        }
    }

    static String fileBase(JSONObject payload) {
        String no = OspChallan.s(payload, "challan_number");
        String label = OspChallan.statusLabel(payload);
        return SndFiles.safeName((no.isEmpty() ? "OSP_Challan" : no) + ("DRAFT".equals(label) ? "_DRAFT" : ""));
    }

    private static String price(double v) {
        String t = String.format(Locale.US, "%,.2f", v);
        if (t.contains(".")) t = t.replaceAll("0+$", "").replaceAll("\\.$", "");
        return t;
    }

    private static String pct(double v) {
        return (v == Math.rint(v) ? String.valueOf((long) v) : SndPoPdf.strip(String.format(Locale.US, "%.4f", v))) + "%";
    }

    private static String amount(double v) { return String.format(Locale.US, "%,.2f", v); }

    /** RETURNABLE DELIVERY CHALLAN PDF from a print payload (OspChallan.payloadForChallan / payloadForDocument). */
    static byte[] render(JSONObject layout, JSONObject payload) throws Exception {
        JSONObject data = OspChallan.vendorSafe(payload);
        SupPdfKit k = new SupPdfKit(layout, OspChallan.statusLabel(data));
        float w = SupPdfKit.W, h = SupPdfKit.H, left = 28, right = 28;
        List<JSONObject> lines = new ArrayList<>();
        JSONArray arr = data.optJSONArray("lines");
        if (arr != null) for (int i = 0; i < arr.length(); i++) if (arr.optJSONObject(i) != null) lines.add(arr.optJSONObject(i));
        float rowH = 34;
        List<List<JSONObject>> pages = pages(lines);
        for (int pi = 0; pi < pages.size(); pi++) {
            List<JSONObject> pageLines = pages.get(pi);
            boolean last = pi == pages.size() - 1;
            k.newPage();
            k.logo();
            k.right(w - right, h - 36, OspChallan.CHALLAN_TITLE, 19, true, SupPdfKit.DARK);
            k.rules();
            k.text(w - 160, h - 53, "DATE", 7.4f, false, SupPdfKit.TEXT);
            k.rect(w - 112, h - 58, 84, 12, true, false);
            k.text(w - 107, h - 55, OspChallan.dateText(data.opt("challan_date")), 7.2f, false, SupPdfKit.TEXT);
            k.text(w - 160, h - 67, "CHALLAN #", 7.4f, false, SupPdfKit.TEXT);
            k.rect(w - 112, h - 72, 84, 12, true, false);
            k.text(w - 107, h - 69, OspChallan.s(data, "challan_number"), 7.2f, true, SupPdfKit.TEXT, 78);
            float y;
            if (pi == 0) {
                float colW = 260, rx = w - right - 220;
                JSONObject plant = data.optJSONObject("plant");
                List<String> plantLines;
                if (plant == null || plant.length() == 0) plantLines = Arrays.asList(PLANT_FALLBACK[0], PLANT_FALLBACK[1], PLANT_FALLBACK[2], PLANT_FALLBACK[3], PLANT_FALLBACK[4], PLANT_FALLBACK[5], PLANT_FALLBACK[6]);
                else plantLines = Arrays.asList(OspChallan.s(plant, "name"), OspChallan.s(plant, "address1"), OspChallan.s(plant, "address2"), OspChallan.s(plant, "address3"),
                    OspChallan.s(plant, "gstin"), OspChallan.s(plant, "phone"), OspChallan.s(plant, "email"));
                k.block(left, h - 64, colW, "PLANT ADDRESS", plantLines, 7);
                k.block(left, h - 160, colW, "VENDOR", SupPdfKit.partyLines(data.optJSONObject("vendor")), 7);
                k.block(rx, h - 84, 220, "REFERENCE DETAILS", Arrays.asList(OspChallan.s(data, "reference_details")), 2);
                k.block(rx, h - 120, 220, "OLD PO DETAILS", Arrays.asList(OspChallan.s(data, "old_po_details")), 2);
                k.block(rx, h - 160, 220, "SHIP TO", SupPdfKit.partyLines(data.optJSONObject("ship_to")), 7);
                float yStrip = h - 262;
                float[] widths = {92, 104, 84, 90, w - left - right - 370};
                String[] titles = {"USER", "SHIP VIA", "INCOTERM", "DELIVERY DATE", "PAYMENT TERM"};
                String[] values = {OspChallan.s(data, "user_name"), OspChallan.s(data, "ship_via"), OspChallan.s(data, "incoterm"),
                    OspChallan.dateText(data.opt("delivery_date")), OspChallan.s(data, "payment_term")};
                float x = left;
                for (int i = 0; i < widths.length; i++) {
                    k.bar(x, yStrip, widths[i], titles[i], 14);
                    k.rect(x, yStrip - 34, widths[i], 20, true, false);
                    k.text(x + 4, yStrip - 27, values[i], 6.8f, false, SupPdfKit.TEXT, widths[i] - 8);
                    x += widths[i];
                }
                y = yStrip - 44;
            } else {
                k.text(left, h - 80, "Continued · Challan " + OspChallan.s(data, "challan_number"), 8, true, k.accent());
                y = h - 92;
            }
            // item grid
            String[] colT = {"ITEM #", "QTY", "UNIT PRICE", "UNIT", "GST%", "GST AMOUNT", "TAXABLE AMOUNT"};
            float[] colW = {165, 52, 62, 42, 42, 88, w - left - right - 451};
            float x = left;
            for (int i = 0; i < colT.length; i++) { k.bar(x, y, colW[i], colT[i], 14); x += colW[i]; }
            y -= 14;
            float gridTop = y;
            for (JSONObject item : pageLines) {
                double[] am = OspChallan.lineAmounts(item);
                String uom = OspChallan.s(item, "uom").isEmpty() ? OspChallan.DEFAULT_UOM : OspChallan.s(item, "uom");
                String[] values = {"", OspChallan.qty(item.opt("quantity")), price(OspChallan.f(item, "unit_price")), uom, pct(OspChallan.f(item, "gst_percent")),
                    amount(am[2]), amount(am[1])};
                k.text(left + 4, y - 10, OspChallan.s(item, "item_code"), 7.6f, true, SupPdfKit.TEXT, 160);
                String hsn = OspChallan.s(item, "hsn_code");
                k.text(left + 4, y - 19, OspChallan.s(item, "item_description") + (hsn.isEmpty() ? "" : " · HSN " + hsn), 6.2f, false, SupPdfKit.TEXT, 160);
                x = left + colW[0];
                for (int i = 1; i < colT.length; i++) {
                    if (i >= 5) k.right(x + colW[i] - 4, y - 12, values[i], 7.2f, false, SupPdfKit.TEXT);
                    else k.text(x + 4, y - 12, values[i], 7.2f, false, SupPdfKit.TEXT, colW[i] - 8);
                    x += colW[i];
                }
                String heat = OspChallan.s(item, "heat_number"), batch = OspChallan.s(item, "batch_code");
                String label = "Heat No." + (heat.isEmpty() ? "-" : heat) + "   Batch Code :- " + (batch.isEmpty() ? "-" : batch);
                k.fill = Color.parseColor("#FFF700");
                k.rect(left + 1, y - rowH + 2, Math.min(250, 12 + label.length() * 4.1f), 9.5f, false, true);
                k.text(left + 4, y - rowH + 4.5f, label, 6.8f, true, SupPdfKit.TEXT, 244);
                y -= rowH;
            }
            if (last) {
                k.bar(left, y - 2, 365, "PROCESS TO BE DONE", 14);
                String process = OspChallan.s(data, "process_text");
                y = k.wrap(left + 4, y - 26, process.isEmpty() ? "-" : process, 357, 8.0f, 10, false, 3);
                if (!OspChallan.s(data, "remarks").isEmpty()) y = k.wrap(left + 4, y - 2, "Remarks: " + OspChallan.s(data, "remarks"), 357, 6.8f, 8.4f, false, 2);
            }
            float gridBottom = last ? 250 : 60;
            k.rules();
            k.rect(left, gridBottom, w - left - right, gridTop - gridBottom, true, false);
            if (!last) {
                k.centre(w / 2, 40, "Continued on next page", 6, false, SupPdfKit.GREY);
                k.showPage();
                continue;
            }
            // totals
            JSONObject totals = data.optJSONObject("totals");
            if (totals == null) totals = new JSONObject();
            float tx = w - right - 170, ty = 238;
            String[][] tl = {{"SUBTOTAL", "subtotal"}, {"TAX", "tax"}, {"SHIPPING", "shipping"}, {"OTHER", "other"}};
            for (String[] t : tl) {
                k.text(tx, ty, t[0], 7.0f, false, SupPdfKit.TEXT);
                k.rect(tx + 70, ty - 4, 100, 12, true, false);
                double v = OspChallan.f(totals, t[1]);
                k.text(tx + 74, ty - 1, v != 0 ? amount(v) : "-", 7.0f, false, SupPdfKit.TEXT);
                ty -= 15;
            }
            k.stroke = SupPdfKit.DARK;
            k.lw = 1.4f;
            k.line(tx, ty + 9, tx + 170, ty + 9);
            k.rules();
            k.string(tx, ty - 2, "TOTAL", 8.2f, true, SupPdfKit.DARK);
            k.right(tx + 168, ty - 2, "INR " + amount(OspChallan.f(totals, "total")), 8.2f, true, SupPdfKit.DARK);
            supplierBox(k, data, left, 244, 300);
            JSONObject plant = data.optJSONObject("plant");
            String company = SupPdfKit.first(OspChallan.s(plant, "name"), PLANT_FALLBACK[0]);
            k.text(w - right - 105, 92, "Authorised Signatory", 7.4f, true, SupPdfKit.TEXT);
            k.text(w - right - 150, 80, "For " + company, 6.2f, false, SupPdfKit.TEXT, 150);
            k.centre(w / 2, 47, "If you have any questions about this document, please contact", 6.0f, false, SupPdfKit.GREY);
            k.centre(w / 2, 36, "FSI, " + SupPdfKit.first(OspChallan.s(plant, "email"), PLANT_FALLBACK[6]), 6.0f, false, SupPdfKit.GREY);
            k.showPage();
        }
        return k.finish();
    }

    /** _draw_supplier_box: key / value for 0-1 return, a small table (last 7) for several returns. */
    private static void supplierBox(SupPdfKit k, JSONObject data, float x, float top, float width) {
        JSONArray ret = data.optJSONArray("returns");
        List<JSONObject> returns = new ArrayList<>();
        if (ret != null) for (int i = 0; i < ret.length(); i++) if (ret.optJSONObject(i) != null) returns.add(ret.optJSONObject(i));
        JSONObject summary = data.optJSONObject("summary");
        if (summary == null) summary = new JSONObject();
        k.fill = Color.parseColor("#BFBFBF");
        k.stroke = Color.BLACK;
        k.lw = 0.5f;
        k.rect(x, top - 13, width, 13, true, true);
        k.text(x + 3, top - 9.5f, "Supplier Details for Returnable Challan / Return details", 7.2f, true, SupPdfKit.TEXT);
        float y = top - 13;
        k.rules();
        if (returns.size() <= 1) {
            JSONObject r = returns.isEmpty() ? new JSONObject() : returns.get(0);
            boolean any = !returns.isEmpty();
            String inv = SupPdfKit.join(" / ", OspChallan.s(r, "invoice_no"), OspChallan.dateText(r.opt("invoice_date")));
            String[][] pairs = {
                {"Challan No", OspChallan.s(r, "challan_no")}, {"Challan Date", OspChallan.dateText(r.opt("challan_date"))},
                {"Invoice No / Date", inv}, {"Quantity dispatch", OspChallan.qty(summary.opt("dispatched"))},
                {"Quantity returned", any ? OspChallan.qty(summary.opt("returned")) : ""},
                {"Quantity rejected", OspChallan.f(summary, "rejected") != 0 ? OspChallan.qty(summary.opt("rejected")) : ""},
                {"Balance Quantity", any ? OspChallan.qty(summary.opt("balance")) : ""},
                {"Vehicle No", SupPdfKit.first(OspChallan.s(r, "vehicle_no"), OspChallan.s(data, "vehicle_number"))},
                {"Remarks", OspChallan.s(r, "remarks")}};
            for (String[] p : pairs) {
                k.rect(x, y - 13, width, 13, true, false);
                k.text(x + 3, y - 9.5f, p[0], 6.8f, false, SupPdfKit.TEXT);
                k.text(x + 98, y - 9.5f, ":  " + p[1], 6.8f, false, SupPdfKit.TEXT, width - 102);
                y -= 13;
            }
            return;
        }
        String[] ct = {"Vendor Challan", "Date", "Invoice", "Qty Ret.", "Rej.", "Vehicle"};
        float[] cw = {70, 46, 62, 36, 28, width - 242};
        List<JSONObject> shown = returns.size() > 7 ? returns.subList(returns.size() - 7, returns.size()) : returns;
        float cx = x;
        for (int i = 0; i < ct.length; i++) {
            k.fill = Color.parseColor("#E4E5E7");
            k.rect(cx, y - 11, cw[i], 11, true, true);
            k.text(cx + 2, y - 8, ct[i], 6.0f, true, SupPdfKit.TEXT);
            cx += cw[i];
        }
        y -= 11;
        for (JSONObject r : shown) {
            String[] v = {OspChallan.s(r, "challan_no"), OspChallan.dateText(r.opt("challan_date")), OspChallan.s(r, "invoice_no"), OspChallan.qty(r.opt("qty_returned")),
                OspChallan.f(r, "qty_rejected") != 0 ? OspChallan.qty(r.opt("qty_rejected")) : "-", OspChallan.s(r, "vehicle_no")};
            cx = x;
            for (int i = 0; i < ct.length; i++) {
                k.rect(cx, y - 11, cw[i], 11, true, false);
                k.text(cx + 2, y - 8, v[i], 6.0f, false, SupPdfKit.TEXT, cw[i] - 4);
                cx += cw[i];
            }
            y -= 11;
        }
        String note = returns.size() > shown.size() ? "  (" + (returns.size() - shown.size()) + " earlier returns not shown)" : "";
        k.rect(x, y - 12, width, 12, true, false);
        k.text(x + 3, y - 8.5f, "Dispatched " + OspChallan.qty(summary.opt("dispatched")) + " · Returned " + OspChallan.qty(summary.opt("returned")) + " · Rejected "
            + OspChallan.qty(summary.opt("rejected")) + " · Balance " + OspChallan.qty(summary.opt("balance")) + note, 6.4f, true, SupPdfKit.TEXT, width - 6);
        y -= 12;
        k.rect(x, y - 12, width, 12, true, false);
        String veh = OspChallan.s(data, "vehicle_number");
        k.text(x + 3, y - 8.5f, "Dispatch Vehicle No : " + (veh.isEmpty() ? "-" : veh), 6.4f, false, SupPdfKit.TEXT, width - 6);
    }
}
