package com.fourstar.qcmsapp;

import android.graphics.Color;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.TreeSet;

/**
 * R39 · Indirect Purchase Order and Indirect GRN prints - port of core/indirect_po_pdf.py in the Direct PO style
 * (SupPdfKit = purchase_order_reporting Design B family, saved PURCHASE_ORDER layout, approver stamp, status watermark,
 * standard FSI PO terms appended). Indirect POs carry no customer data: nothing customer-related is printed.
 */
final class IndPdf {
    private IndPdf() { }

    static final String TITLE = "INDIRECT PURCHASE ORDER";
    static final String GRN_TITLE = "INDIRECT GOODS RECEIPT NOTE";
    private static final String[] COL_TITLES = {"#", "ITEM CODE / DESCRIPTION", "HSN/SAC", "QTY", "UOM", "RATE", "DISC %", "TAXABLE", "GST %", "GST AMT", "AMOUNT"};
    private static final float[] COL_W = {18, 160, 44, 40, 30, 48, 30, 54, 28, 47, 40};
    private static final List<Integer> NUMERIC = Arrays.asList(3, 5, 6, 7, 8, 9, 10);
    private static final float SUMMARY_TOP = 300;

    static String watermark(JSONObject h) {
        String approval = IndSvc.up(h, "approval_status"), status = IndSvc.up(h, "status");
        if ("CANCELLED".equals(status) || "CANCELLED".equals(approval)) return "CANCELLED";
        if ("APPROVED".equals(approval)) return "APPROVED";
        if ("REJECTED".equals(approval)) return "REJECTED";
        if ("DRAFT".equals(approval) || "PREVIEW".equals(approval) || "DRAFT".equals(status) || "PREVIEW".equals(status)) return "DRAFT";
        return "PENDING APPROVAL";
    }

    static String fileName(JSONObject h) {
        String n = IndSvc.c(h, "po_number");
        return (n.isEmpty() ? "Indirect_PO" : n).replaceAll("[\\\\/:*?\"<>|]+", "-") + ".pdf";
    }

    private static String s(JSONObject o, String k) { return IndSvc.c(o, k); }
    private static String date(Object v) { return SupPdfKit.date(IndSvc.clean(v)); }
    private static String money(JSONObject o, String k) { return SupPdfKit.money(IndSvc.num(o, k)); }
    private static String qty(JSONObject o, String k) { return SupPdfKit.qty(IndSvc.num(o, k)); }

    private static float[] widths(float total) {
        float sum = 0;
        for (float w : COL_W) sum += w;
        float[] out = new float[COL_W.length];
        for (int i = 0; i < COL_W.length; i++) out[i] = COL_W[i] * total / sum;
        return out;
    }

    /** build_indirect_po_pdf(header, items): saved Print Layout Designer theme + the PO's print_options. */
    static byte[] build(Api api, JSONObject header, List<JSONObject> items, boolean includeTerms) throws Exception {
        if (items.isEmpty()) throw new SupSvc.Rule("At least one Indirect Purchase Order line is required.");
        JSONObject layout = SndData.printLayout(SupPdfKit.layout(api), header.optJSONObject("print_options"));
        List<JSONObject> rows = new ArrayList<>();
        for (int i = 0; i < items.size(); i++) {
            JSONObject r = new JSONObject(items.get(i).toString());
            if (IndSvc.num(r, "line_no") == 0) r.put("line_no", i + 1);
            rows.add(r);
        }
        SupPdfKit k = new SupPdfKit(layout, watermark(header));
        float w = SupPdfKit.W, left = 28, right = 28;
        float[] widths = widths(w - left - right);
        k.newPage();
        float y = firstPageHeader(k, header);
        y = tableHead(k, left, y, widths);
        for (int i = 0; i < rows.size(); i++) {
            JSONObject item = rows.get(i);
            float need = rowHeight(k, item, widths);
            boolean last = i == rows.size() - 1;
            float floor = last ? SUMMARY_TOP + 4 : 60;
            if (y - need < floor) {
                k.centre(w / 2, 27, "QCMS controlled Indirect Purchase Order · continued on next page", 5.8f, false, SupPdfKit.GREY);
                k.showPage();
                k.newPage();
                continuationHeader(k, header, TITLE + " · ITEMS CONTINUED", "IPO #");
                y = tableHead(k, left, SupPdfKit.H - 92, widths);
            }
            y = drawRow(k, item, left, y, widths);
        }
        if (y < SUMMARY_TOP + 4) {
            k.showPage();
            k.newPage();
            continuationHeader(k, header, TITLE + " · TOTALS", "IPO #");
        }
        summary(k, header, rows);
        k.showPage();
        if (includeTerms) {
            JSONObject plant = plant(header);
            k.termsPages(s(header, "po_number"), s(header, "po_date"), SupPdfKit.first(s(plant, "name"), s(plant, "branch_name")), "");
        }
        return k.finish();
    }

    private static JSONObject plant(JSONObject header) {
        JSONObject p = header.optJSONObject("plant_snapshot");
        return p == null || p.length() == 0 ? SndPoPdf.defaultPlant() : p;
    }

    private static void logoAndTitle(SupPdfKit k, String title, float size) {
        k.logo();
        k.right(SupPdfKit.W - 28, SupPdfKit.H - 34, title, size, true, k.accent());
        k.rules();
    }

    private static void continuationHeader(SupPdfKit k, JSONObject header, String title, String numberLabel) {
        float w = SupPdfKit.W, h = SupPdfKit.H;
        k.logo();
        k.right(w - 28, h - 33, title, 15.5f, true, k.accent());
        k.rules();
        k.text(w - 176, h - 51, numberLabel + " " + SupPdfKit.first(s(header, "po_number"), s(header, "grn_number")), 7.2f, true, SupPdfKit.TEXT);
        k.text(w - 176, h - 64, "DATE " + date(SupPdfKit.first(s(header, "po_date"), s(header, "grn_date"))), 7.2f, false, SupPdfKit.TEXT);
    }

    private static float firstPageHeader(SupPdfKit k, JSONObject header) {
        float w = SupPdfKit.W, h = SupPdfKit.H, left = 28, right = 28;
        String title = SupPdfKit.first(s(k.layout, "indirect_title"), TITLE);
        logoAndTitle(k, title, 20);
        k.text(w - 150, h - 51, "DATE", 7.4f, false, SupPdfKit.TEXT);
        k.rect(w - 104, h - 58, 76, 12, true, false);
        k.text(w - 100, h - 55, date(header.opt("po_date")), 7.2f, false, SupPdfKit.TEXT);
        k.text(w - 150, h - 65, "IPO #", 7.4f, false, SupPdfKit.TEXT);
        k.rect(w - 104, h - 72, 76, 12, true, false);
        k.text(w - 100, h - 69, s(header, "po_number"), 6.8f, false, SupPdfKit.TEXT, 72);

        float colW = 230, rightX = w - right - 184, y0 = h - 62;
        JSONObject plant = plant(header);
        if (k.show("show_plant"))
            k.block(left, y0, colW, "PLANT / COMPANY BRANCH", Arrays.asList(SupPdfKit.first(s(plant, "name"), s(plant, "branch_name")),
                SupPdfKit.first(s(plant, "address1"), s(plant, "address")), s(plant, "address2"), s(plant, "address3"),
                SupPdfKit.first(s(plant, "tax_identifier"), s(plant, "gstin")), s(plant, "phone"), s(plant, "email")), 7);
        if (k.show("show_vendor")) {
            JSONObject v = header.optJSONObject("vendor_snapshot");
            k.block(left, h - 154, colW, "VENDOR", SupPdfKit.partyLines(v == null ? new JSONObject() : v), 7);
        }
        if (k.show("show_reference"))
            k.block(rightX, h - 86, 184, "REFERENCE DETAILS", Arrays.asList("QUOTATION DATE: " + date(header.opt("quotation_date")), s(header, "quotation_reference"),
                "CURRENCY: " + SupPdfKit.first(s(header, "currency"), "INR")), 3);
        String dept = SupPdfKit.join(" · ", s(header, "department"), s(header, "cost_centre"));
        k.block(rightX, h - 136, 184, "DEPARTMENT / COST CENTRE", Arrays.asList(dept.isEmpty() ? "-" : dept), 2);
        if (k.show("show_ship_to")) {
            JSONObject ship = header.optJSONObject("ship_to_snapshot");
            k.block(rightX, h - 174, 184, "SHIP TO", SupPdfKit.partyLines(ship == null || ship.length() == 0 ? plant : ship), 7);
        }
        float yStrip = h - 284;
        float[] sw = {78, 106, 82, 93, w - left - right - 359};
        String[] titles = {"REQUISITIONER", "SHIP VIA", "INCOTERM", "DELIVERY DATE", "PAYMENT TERM"};
        String[] values = {s(header, "requisitioner"), s(header, "ship_via"), s(header, "incoterm"), date(header.opt("delivery_date")), s(header, "payment_term")};
        float x = left;
        for (int i = 0; i < sw.length; i++) {
            k.bar(x, yStrip, sw[i], titles[i], 14);
            k.rect(x, yStrip - 34, sw[i], 20, true, false);
            k.text(x + 4, yStrip - 27, values[i], 6.6f, false, SupPdfKit.TEXT, sw[i] - 8);
            x += sw[i];
        }
        return yStrip - 45;
    }

    private static float tableHead(SupPdfKit k, float x, float yTop, float[] widths) {
        for (int i = 0; i < widths.length; i++) { k.bar(x, yTop, widths[i], COL_TITLES[i], 14); x += widths[i]; }
        return yTop - 14;
    }

    private static List<String[]> rowLines(SupPdfKit k, JSONObject item, float width) {
        List<String[]> out = new ArrayList<>();   // {text, "b"|"n"}
        String head = SupPdfKit.join(" · ", s(item, "item_code"), s(item, "item_name"));
        for (String l : k.wrapLines(head, width - 6, 6.4f, true, 2)) out.add(new String[]{l, "b"});
        String desc = s(item, "description");
        if (!desc.isEmpty() && !desc.equalsIgnoreCase(s(item, "item_name")))
            for (String l : k.wrapLines(desc, width - 6, 5.8f, false, 3)) out.add(new String[]{l, "n"});
        if (!s(item, "required_date").isEmpty()) out.add(new String[]{"Required by " + date(item.opt("required_date")), "n"});
        if (out.isEmpty()) out.add(new String[]{"-", "b"});
        return out;
    }

    private static float rowHeight(SupPdfKit k, JSONObject item, float[] widths) {
        return Math.max(16f, 6f + 7.6f * rowLines(k, item, widths[1]).size());
    }

    private static float drawRow(SupPdfKit k, JSONObject item, float x, float yTop, float[] widths) {
        float height = rowHeight(k, item, widths);
        float bottom = yTop - height;
        float total = 0;
        for (float w : widths) total += w;
        k.rules();
        k.fill = Color.WHITE;
        k.rect(x, bottom, total, height, true, true);
        String[] values = {String.valueOf((int) IndSvc.num(item, "line_no")), null, s(item, "hsn_sac"), qty(item, "quantity"), s(item, "uom"), money(item, "rate"),
            SupPdfKit.g(IndSvc.num(item, "discount_percent")), money(item, "taxable_amount"), SupPdfKit.g(IndSvc.num(item, "gst_percent")),
            money(item, "gst_amount"), money(item, "line_total")};
        float cx = x;
        for (int i = 0; i < widths.length; i++) {
            float width = widths[i];
            if (i == 1) {
                float ly = yTop - 9;
                List<String[]> lines = rowLines(k, item, width);
                for (int n = 0; n < lines.size(); n++) {
                    boolean b = "b".equals(lines.get(n)[1]);
                    k.text(cx + 3, ly, lines.get(n)[0], n == 0 ? 6.4f : 5.8f, b && n == 0, n == 0 ? SupPdfKit.TEXT : Color.parseColor("#374151"), width - 6);
                    ly -= 7.6f;
                }
            } else if (NUMERIC.contains(i)) {
                k.rightFit(cx + width - 2, yTop - 10, values[i], 6.3f, false, SupPdfKit.TEXT, width - 4);
            } else {
                k.text(cx + 3, yTop - 10, values[i], 6.3f, false, SupPdfKit.TEXT, width - 5);
            }
            cx += width;
        }
        return bottom;
    }

    private static void footer(SupPdfKit k, String document) {
        float w = SupPdfKit.W;
        k.centre(w / 2, 47, "If you have any questions about this " + document + ", please contact", 6.0f, false, SupPdfKit.GREY);
        k.centre(w / 2, 36, k.footerText(), 6.0f, false, SupPdfKit.GREY);
    }

    private static void summary(SupPdfKit k, JSONObject header, List<JSONObject> items) {
        float w = SupPdfKit.W, left = 28;
        int accent = k.accent();
        int remark = k.color("remark", Color.parseColor("#9A3412"));
        k.text(left + 2, 286, "Amount in words:", 7.2f, true, accent);
        k.rules(); k.fill = k.fillOrWhite("remark_fill"); k.rect(left, 262, 386, 20, true, true);
        k.text(left + 4, 269, SupPdfKit.first(s(header, "amount_in_words"), "-"), 6.8f, true, SupPdfKit.TEXT, 378);
        k.text(left + 2, 250, "Remarks:", 7.4f, true, accent);
        k.rules(); k.fill = k.fillOrWhite("remark_fill"); k.rect(left, 226, 386, 20, true, true);
        k.text(left + 4, 233, SupPdfKit.first(s(header, "remarks"), "-"), 7.0f, true, remark, 378);
        if (k.show("show_special_instructions")) {
            k.bar(left, 220, 386, "TERMS & SPECIAL INSTRUCTIONS", 14);
            String terms = header.isNull("terms") ? "" : header.optString("terms", "").trim();
            String instr = header.isNull("special_instructions") ? "" : header.optString("special_instructions", "").trim();
            if (instr.isEmpty()) instr = IndSvc.DEFAULT_INSTRUCTIONS;
            k.specialLines(left + 2, 196, terms.isEmpty() ? instr : terms + "\n" + instr, 374, 96);
        }
        float tx = 417, y = 286;
        String mode = SupPdfKit.first(IndSvc.up(header, "gst_mode"), "INTRA");
        TreeSet<Double> rates = new TreeSet<>();
        for (JSONObject i : items) if (IndSvc.num(i, "gst_percent") > 0) rates.add(IndSvc.num(i, "gst_percent"));
        String rateTxt = rates.size() == 1 ? " " + SupPdfKit.g("INTRA".equals(mode) ? rates.first() / 2 : rates.first()) + "%" : "";
        List<String[]> rows = new ArrayList<>();
        rows.add(new String[]{"PO LINES", String.valueOf(items.size())});
        rows.add(new String[]{"GROSS", money(header, "gross_amount")});
        rows.add(new String[]{"DISCOUNT", money(header, "discount_amount")});
        rows.add(new String[]{"TAXABLE", money(header, "subtotal")});
        if ("INTER".equals(mode)) rows.add(new String[]{"IGST" + rateTxt, money(header, "igst_amount")});
        else { rows.add(new String[]{"CGST" + rateTxt, money(header, "cgst_amount")}); rows.add(new String[]{"SGST" + rateTxt, money(header, "sgst_amount")}); }
        rows.add(new String[]{"FREIGHT", money(header, "freight_amount")});
        rows.add(new String[]{"OTHER", money(header, "other_amount")});
        rows.add(new String[]{"ROUND OFF", money(header, "round_off")});
        for (String[] r : rows) {
            k.text(tx, y, r[0], 6.8f, "PO LINES".equals(r[0]), SupPdfKit.TEXT);
            k.rect(tx + 58, y - 5, 92, 13, true, false);
            k.right(tx + 147, y - 1, r[1], 6.8f, false, SupPdfKit.TEXT);
            y -= 15;
        }
        k.string(tx, y - 2, "TOTAL", 8.2f, true, accent);
        k.right(tx + 147, y - 2, SupPdfKit.first(s(header, "currency"), "INR") + " " + money(header, "grand_total"), 8.2f, true, accent);
        JSONObject plant = plant(header);
        String signatory = SupPdfKit.first(s(k.layout, "company_name"), s(plant, "name"), s(plant, "branch_name"), s(SndPoPdf.defaultPlant(), "name"));
        if ("APPROVED".equals(IndSvc.up(header, "approval_status")) && k.show("show_approval_stamp")) k.approverStamp(header, w);
        else {
            k.text(w - 143, 81, "Authorised Signatory", 7.0f, true, SupPdfKit.TEXT);
            k.text(w - 174, 67, signatory, 6.2f, false, SupPdfKit.TEXT);
        }
        footer(k, "purchase order");
    }

    // ================================================================== GRN
    private static final String[] GRN_TITLES = {"#", "ITEM CODE / DESCRIPTION", "UOM", "ORDERED", "RECEIVED", "ACCEPTED", "REJECTED", "REJECT REASON", "LOCATION"};
    private static final float[] GRN_W = {18, 170, 32, 46, 46, 46, 46, 76, 59};

    static String grnWatermark(JSONObject grn) {
        switch (IndSvc.up(grn, "status")) {
            case "POSTED": return "POSTED";
            case "PENDING_APPROVAL": return "PENDING APPROVAL";
            case "REJECTED": return "REJECTED";
            case "CANCELLED": return "CANCELLED";
            default: return "DRAFT";
        }
    }

    /** build_indirect_grn_pdf(grn, items, po). */
    static byte[] grn(Api api, JSONObject grn, List<JSONObject> items, JSONObject po) throws Exception {
        SupPdfKit k = new SupPdfKit(SndData.printLayout(SupPdfKit.layout(api), null), grnWatermark(grn));
        float w = SupPdfKit.W, h = SupPdfKit.H, left = 28, right = 28;
        k.newPage();
        logoAndTitle(k, GRN_TITLE, 17);
        k.text(w - 150, h - 51, "DATE", 7.4f, false, SupPdfKit.TEXT);
        k.rect(w - 104, h - 58, 76, 12, true, false);
        k.text(w - 100, h - 55, date(grn.opt("grn_date")), 7.2f, false, SupPdfKit.TEXT);
        k.text(w - 150, h - 65, "GRN #", 7.4f, false, SupPdfKit.TEXT);
        k.rect(w - 104, h - 72, 76, 12, true, false);
        k.text(w - 100, h - 69, s(grn, "grn_number"), 6.8f, false, SupPdfKit.TEXT, 72);
        JSONObject plant = po != null && po.optJSONObject("plant_snapshot") != null ? po.optJSONObject("plant_snapshot") : SndPoPdf.defaultPlant();
        k.block(left, h - 62, 260, "PLANT / COMPANY BRANCH", Arrays.asList(SupPdfKit.first(s(plant, "name"), s(plant, "branch_name")),
            SupPdfKit.first(s(plant, "address1"), s(plant, "address")), SupPdfKit.first(s(plant, "tax_identifier"), s(plant, "gstin"))), 4);
        JSONObject vendor = po == null ? null : po.optJSONObject("vendor_snapshot");
        k.block(left, h - 136, 260, "SUPPLIER", vendor != null && vendor.length() > 0 ? SupPdfKit.partyLines(vendor) : Arrays.asList(SupPdfKit.first(s(grn, "supplier_name"), "-")), 5);
        String poNo = po == null ? "" : s(po, "po_number");
        k.block(w - right - 260, h - 86, 260, "RECEIPT DETAILS", Arrays.asList(
            "GRN TYPE: " + s(grn, "grn_type").replace('_', ' ') + " · PAYMENT: " + s(grn, "payment_mode").replace('_', ' '),
            "INDIRECT PO: " + (poNo.isEmpty() ? "-" : poNo) + "  " + (po == null ? "" : date(po.opt("po_date"))),
            "INVOICE: " + SupPdfKit.first(s(grn, "supplier_invoice_no"), "-") + "  " + date(grn.opt("supplier_invoice_date")),
            "CHALLAN: " + SupPdfKit.first(s(grn, "challan_no"), "-") + "  " + date(grn.opt("challan_date")),
            "GATE ENTRY: " + SupPdfKit.first(s(grn, "gate_entry_no"), "-") + "  " + date(grn.opt("gate_entry_date")) + " · VEHICLE: " + SupPdfKit.first(s(grn, "vehicle_no"), "-"),
            "DEPARTMENT: " + SupPdfKit.first(s(grn, "department"), "-") + " · COST CENTRE: " + SupPdfKit.first(s(grn, "cost_centre"), "-")), 6);
        float y = h - 232;
        float sum = 0;
        for (float v : GRN_W) sum += v;
        float[] widths = new float[GRN_W.length];
        for (int i = 0; i < GRN_W.length; i++) widths[i] = GRN_W[i] * (w - left - right) / sum;
        float x = left;
        for (int i = 0; i < widths.length; i++) { k.bar(x, y, widths[i], GRN_TITLES[i], 14); x += widths[i]; }
        y -= 14;
        int lineNo = 0;
        for (JSONObject item : items) {
            lineNo++;
            List<String> lines = k.wrapLines(SupPdfKit.join(" · ", s(item, "item_code"), SupPdfKit.first(s(item, "item_name"), s(item, "description"))), widths[1] - 6, 6.3f, false, 2);
            List<String> reason = k.wrapLines(s(item, "rejection_reason"), widths[7] - 6, 5.8f, false, 2);
            float height = Math.max(16f, 6 + 7.6f * Math.max(Math.max(lines.size(), reason.size()), 1));
            if (y - height < 150) {
                k.showPage();
                k.newPage();
                continuationHeader(k, grn, GRN_TITLE + " · CONTINUED", "GRN #");
                y = h - 92;
            }
            k.rules(); k.fill = Color.WHITE;
            k.rect(left, y - height, w - left - right, height, true, true);
            String ordered = s(item, "ordered_qty").isEmpty() ? "-" : qty(item, "ordered_qty");
            String[] values = {String.valueOf(IndSvc.num(item, "line_no") == 0 ? lineNo : (int) IndSvc.num(item, "line_no")), null, s(item, "uom"), ordered,
                qty(item, "received_qty"), qty(item, "accepted_qty"), qty(item, "rejected_qty"), null, SupPdfKit.first(s(item, "storage_location"), s(grn, "storage_location"))};
            float cx = left;
            for (int i = 0; i < widths.length; i++) {
                if (i == 1) for (int n = 0; n < lines.size(); n++) k.text(cx + 3, y - 9 - n * 7.6f, lines.get(n), 6.3f, n == 0, SupPdfKit.TEXT, widths[i] - 6);
                else if (i == 7) for (int n = 0; n < reason.size(); n++) k.text(cx + 3, y - 9 - n * 7.6f, reason.get(n), 5.8f, false, SupPdfKit.TEXT, widths[i] - 6);
                else if (i >= 3 && i <= 6) k.right(cx + widths[i] - 3, y - 10, values[i], 6.4f, false, SupPdfKit.TEXT);
                else k.text(cx + 3, y - 10, values[i], 6.3f, false, SupPdfKit.TEXT, widths[i] - 5);
                cx += widths[i];
            }
            y -= height;
        }
        k.text(left + 2, 132, "Remarks:", 7.2f, true, k.accent());
        k.text(left + 50, 132, SupPdfKit.first(s(grn, "remarks"), "-"), 7.0f, false, SupPdfKit.TEXT, w - left - right - 60);
        float sig = (w - left - right) / 4;
        String[] labels = {"RECEIVED BY", "STORES", "QUALITY / USER DEPT.", "APPROVED BY"};
        for (int i = 0; i < 4; i++) {
            float sx = left + i * sig;
            k.bar(sx, 118, sig - 4, labels[i], 13);
            k.rect(sx, 78, sig - 4, 27, true, false);
            String value = i == 0 ? s(grn, "received_by_name") : i == 3 ? s(grn, "approver_name") : "";
            k.text(sx + 4, 88, value, 6.6f, false, SupPdfKit.TEXT, sig - 12);
        }
        footer(k, "goods receipt note");
        k.showPage();
        return k.finish();
    }

    /** indirect_grn_pdf_bytes(grn_id): background thread. */
    static byte[] grnById(Api api, IndSvc svc, String grnId) throws Exception {
        JSONObject grn = new JSONObject(svc.grn(grnId).toString());
        if (grn.length() == 0) throw new SupSvc.Rule("Indirect GRN not found.");
        JSONObject po = IndSvc.c(grn, "purchase_order_id").isEmpty() ? null : svc.purchaseOrder(IndSvc.c(grn, "purchase_order_id"));
        if (!IndSvc.c(grn, "approver_employee_id").isEmpty()) grn.put("approver_name", IndSvc.employeeName(svc.employee(IndSvc.c(grn, "approver_employee_id"))));
        return grn(api, grn, svc.grnItems(grnId), po);
    }

    /** indirect_po_pdf_bytes(po_id): background thread. */
    static byte[] poById(Api api, IndSvc svc, String poId, boolean includeTerms) throws Exception {
        JSONObject header = svc.purchaseOrder(poId);
        if (header.length() == 0) throw new SupSvc.Rule("Indirect Purchase Order not found.");
        return build(api, header, svc.poItems(poId), includeTerms);
    }

    static List<JSONObject> list(JSONArray a) { return SupSvc.list(a); }

    static String grnFileName(JSONObject grn) {
        String n = IndSvc.c(grn, "grn_number");
        return (n.isEmpty() ? "Indirect_GRN" : n).replaceAll("[\\\\/:*?\"<>|]+", "-") + ".pdf";
    }

    static String upper(String v) { return v == null ? "" : v.toUpperCase(Locale.ROOT); }
}
