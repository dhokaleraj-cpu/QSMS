package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * R39 · OSP Material Out returnable delivery challan - port of core/osp_challan.py (OSPChallanService + pure helpers):
 * osp_challans / osp_challan_lines / osp_challan_returns over the live OSP genealogy (RLS module OSP_TRANSACTIONS).
 *
 * Customer confidentiality (core/customer_privacy.py): the challan goes to the OSP vendor, so the payload carries the
 * FSI part number / description only - never customer name / code / PO / order / customer part number / delivery date.
 */
final class OspChallan {
    private OspChallan() { }

    static final String CHALLAN_TITLE = "RETURNABLE DELIVERY CHALLAN";
    static final double DEFAULT_GST = 18.0;
    static final String DEFAULT_UOM = "NOS";
    static final String[] SHIP_VIA_OPTIONS = {"Road", "Hand Delivery", "Courier", "Vendor Vehicle", "FSI Vehicle", "Rail", "Air"};
    static final String[] INCOTERM_OPTIONS = {"EXWORKS", "FOR", "DAP", "FCA", "CIF", "FOB"};
    static final String[] PAYMENT_TERM_OPTIONS = {"NET 30 DAYS AFTER GRN", "NET 45 DAYS AFTER GRN", "NET 60 DAYS AFTER GRN", "ADVANCE", "NOT APPLICABLE (JOB WORK)"};
    /** core.osp_challan._INTERNAL_KEYS - never on a vendor-facing challan line. */
    static final String[] INTERNAL_KEYS = {"part_number", "customer_id", "customer_name", "customer_part_number", "customer_po_number"};
    /** core.customer_privacy.CUSTOMER_KEYS. */
    static final Set<String> CUSTOMER_KEYS = new HashSet<>(Arrays.asList(
        "customer", "customer_name", "customer_code", "customer_email", "customer_phone", "customer_address",
        "customer_po", "customer_po_no", "customer_po_number", "customer_order_no", "customer_order_number",
        "customer_order_position", "order_position", "po_position", "customer_part_number", "customer_part_no",
        "customer_delivery_date", "customer_source_rows", "customer_reference", "customer_references",
        "master_reference_no", "end_customer", "customer_party", "customers"));
    static final String[] HEADER_KEYS = {"challan_date", "branch_id", "vendor_id", "ship_to_party_id", "ship_to_text", "user_name", "ship_via", "incoterm",
        "delivery_date", "payment_term", "reference_details", "old_po_details", "process_text", "vehicle_number",
        "transporter_name", "eway_bill_number", "remarks", "status"};

    // ================================================================== pure helpers
    static String s(Object v) {
        if (v == null || v == JSONObject.NULL) return "";
        String t = String.valueOf(v).trim();
        return "null".equals(t) ? "" : t.replaceAll("\\s+", " ");
    }

    static String s(JSONObject o, String k) { return o == null ? "" : s(o.opt(k)); }

    static double f(Object v) {
        if (v == null || v == JSONObject.NULL) return 0;
        try {
            double d = v instanceof Number ? ((Number) v).doubleValue() : Double.parseDouble(String.valueOf(v).trim());
            return Double.isNaN(d) || Double.isInfinite(d) ? 0 : d;
        } catch (Exception e) { return 0; }
    }

    static double f(JSONObject o, String k) { return o == null ? 0 : f(o.opt(k)); }

    static double round(double v, int places) {
        double p = Math.pow(10, places);
        return Math.round(v * p) / p;
    }

    static String dateText(Object v) {
        String t = s(v);
        if (t.length() < 10) return t;
        String[] p = t.substring(0, 10).split("-");
        return p.length == 3 ? p[2] + "-" + p[1] + "-" + p[0] : t.substring(0, 10);
    }

    static String qty(Object v) { return SupPdfKit.qty(f(v)); }

    /** Python mirror of qcms_next_osp_challan_number: JWC + plant code + 5 digits. */
    static String nextNumberFrom(Iterable<String> existing, String plantCode) {
        String code = (plantCode == null || plantCode.trim().isEmpty() ? "D9" : plantCode).replaceAll("[^A-Za-z0-9]", "").toUpperCase(Locale.ROOT);
        String prefix = "JWC" + code;
        Pattern pattern = Pattern.compile("^" + Pattern.quote(prefix) + "([0-9]{1,12})$");
        long best = 0;
        for (String v : existing) {
            Matcher m = pattern.matcher(s(v).toUpperCase(Locale.ROOT));
            if (m.matches()) best = Math.max(best, Long.parseLong(m.group(1)));
        }
        return prefix + String.format(Locale.US, "%05d", best + 1);
    }

    /** line_amounts: quantity, taxable = qty x price, gst = taxable x GST% (2 decimals). */
    static double[] lineAmounts(JSONObject line) {
        double q = line.has("quantity") && line.opt("quantity") != JSONObject.NULL ? f(line, "quantity") : f(line, "quantity_dispatched");
        double taxable = round(q * f(line, "unit_price"), 2);
        double gst = round(taxable * f(line, "gst_percent") / 100.0, 2);
        return new double[]{q, taxable, gst};
    }

    static JSONObject totals(List<JSONObject> lines, Object shipping, Object other) {
        double sub = 0, tax = 0;
        for (JSONObject l : lines) { double[] a = lineAmounts(l); sub += a[1]; tax += a[2]; }
        sub = round(sub, 2); tax = round(tax, 2);
        JSONObject t = new JSONObject();
        try {
            t.put("subtotal", sub); t.put("tax", tax); t.put("shipping", round(f(shipping), 2)); t.put("other", round(f(other), 2));
            t.put("total", round(sub + tax + f(shipping) + f(other), 2));
        } catch (Exception ignored) { }
        return t;
    }

    /** merge_returns: every OSP Inward receipt is a return; linked entries only add details; standalone entries add returns. */
    static List<JSONObject> mergeReturns(List<JSONObject> receipts, List<JSONObject> entries) {
        Map<String, JSONObject> linked = new HashMap<>();
        for (JSONObject e : entries) if (!s(e, "osp_receipt_id").isEmpty()) linked.put(s(e, "osp_receipt_id"), e);
        Set<String> receiptIds = new HashSet<>();
        for (JSONObject r : receipts) receiptIds.add(s(r, "id"));
        List<JSONObject> rows = new ArrayList<>();
        try {
            for (JSONObject receipt : receipts) {
                JSONObject e = linked.get(s(receipt, "id"));
                if (e == null) e = new JSONObject();
                JSONObject row = new JSONObject();
                row.put("source", "OSP Inward");
                row.put("receipt_id", s(receipt, "id"));
                row.put("entry_id", s(e, "id"));
                row.put("osp_job_id", s(receipt, "osp_job_id"));
                row.put("receipt_number", s(receipt, "receipt_number"));
                row.put("challan_no", SupPdfKit.first(s(e, "vendor_challan_number"), s(receipt, "receipt_challan")));
                row.put("challan_date", SupPdfKit.first(s(e, "vendor_challan_date"), s(receipt, "receipt_date")));
                row.put("invoice_no", SupPdfKit.first(s(e, "vendor_invoice_number"), s(receipt, "vendor_invoice_number")));
                row.put("invoice_date", SupPdfKit.first(s(e, "vendor_invoice_date"), s(receipt, "vendor_invoice_date")));
                row.put("qty_returned", f(receipt, "quantity_received"));
                row.put("qty_rejected", f(e, "quantity_rejected"));
                row.put("vehicle_no", s(e, "vehicle_number"));
                row.put("remarks", SupPdfKit.first(s(e, "remarks"), s(receipt, "remarks")));
                rows.add(row);
            }
            for (JSONObject e : entries) {
                if (!s(e, "osp_receipt_id").isEmpty()) continue;   // linked (counted with its receipt) or receipt deleted (FK cascade)
                JSONObject row = new JSONObject();
                row.put("source", "Vendor return");
                row.put("receipt_id", "");
                row.put("entry_id", s(e, "id"));
                row.put("osp_job_id", s(e, "osp_job_id"));
                row.put("receipt_number", "");
                row.put("challan_no", s(e, "vendor_challan_number"));
                row.put("challan_date", s(e, "vendor_challan_date"));
                row.put("invoice_no", s(e, "vendor_invoice_number"));
                row.put("invoice_date", s(e, "vendor_invoice_date"));
                row.put("qty_returned", f(e, "quantity_returned"));
                row.put("qty_rejected", f(e, "quantity_rejected"));
                row.put("vehicle_no", s(e, "vehicle_number"));
                row.put("remarks", s(e, "remarks"));
                rows.add(row);
            }
        } catch (Exception ignored) { }
        rows.sort((x, y) -> {
            int c = s(x, "challan_date").compareTo(s(y, "challan_date"));
            return c != 0 ? c : s(x, "challan_no").compareTo(s(y, "challan_no"));
        });
        return rows;
    }

    /** balance_summary: dispatched / returned / rejected / balance (never negative). */
    static JSONObject balanceSummary(double dispatched, List<JSONObject> returns) {
        double returned = 0, rejected = 0;
        for (JSONObject r : returns) { returned += f(r, "qty_returned"); rejected += f(r, "qty_rejected"); }
        JSONObject o = new JSONObject();
        try {
            o.put("dispatched", dispatched);
            o.put("returned", round(returned, 3));
            o.put("rejected", round(rejected, 3));
            o.put("balance", round(Math.max(dispatched - returned - rejected, 0.0), 3));
        } catch (Exception ignored) { }
        return o;
    }

    /** strip_customer (deep, 4 levels) + _INTERNAL_KEYS removed from every challan line. */
    static JSONObject vendorSafe(JSONObject payload) {
        JSONObject clean = (JSONObject) strip(payload, 0);
        JSONArray lines = clean.optJSONArray("lines");
        if (lines != null) for (int i = 0; i < lines.length(); i++) {
            JSONObject l = lines.optJSONObject(i);
            if (l != null) for (String k : INTERNAL_KEYS) l.remove(k);
        }
        return clean;
    }

    /** core.customer_privacy.strip_customer for one supplier / vendor facing row (deep copy, customer keys removed). */
    static JSONObject stripCustomer(JSONObject row) {
        Object o = strip(row == null ? new JSONObject() : row, 0);
        return o instanceof JSONObject ? (JSONObject) o : new JSONObject();
    }

    private static Object strip(Object v, int depth) {
        try {
            if (v instanceof JSONObject) {
                JSONObject in = (JSONObject) v, out = new JSONObject();
                Iterator<String> it = in.keys();
                while (it.hasNext()) {
                    String k = it.next();
                    String low = k.toLowerCase(Locale.ROOT);
                    if (CUSTOMER_KEYS.contains(low) || low.startsWith("customer_")) continue;
                    out.put(k, depth > 4 ? in.opt(k) : strip(in.opt(k), depth + 1));
                }
                return out;
            }
            if (v instanceof JSONArray) {
                JSONArray in = (JSONArray) v, out = new JSONArray();
                for (int i = 0; i < in.length(); i++) out.put(depth > 4 ? in.opt(i) : strip(in.opt(i), depth + 1));
                return out;
            }
        } catch (Exception ignored) { }
        return v;
    }

    /** clean_header: challan number required (upper case), amounts >= 0, status ISSUED by default. */
    static JSONObject cleanHeader(JSONObject header) throws Exception {
        String number = s(header, "challan_number").toUpperCase(Locale.ROOT);
        if (number.isEmpty()) throw new Api.ApiException(422, "Enter the Challan Number (use the suggested series number or your own).");
        JSONObject out = new JSONObject();
        out.put("challan_number", number);
        for (String k : HEADER_KEYS) {
            if (!header.has(k)) continue;
            String v = s(header, k);
            out.put(k, v.isEmpty() ? JSONObject.NULL : v);
        }
        for (String k : new String[]{"shipping_amount", "other_amount"}) {
            if (!header.has(k)) continue;
            double amount = f(header, k);
            if (amount < 0) throw new Api.ApiException(422, "Shipping and Other amounts cannot be negative.");
            out.put(k, round(amount, 2));
        }
        if (!out.has("status") || out.isNull("status")) out.put("status", "ISSUED");
        return out;
    }

    /** clean_lines: OSP heat line required, price >= 0, GST 0-100. */
    static List<JSONObject> cleanLines(List<JSONObject> lines) throws Exception {
        List<JSONObject> result = new ArrayList<>();
        int position = 0;
        for (JSONObject line : lines) {
            position++;
            if (s(line, "osp_job_id").isEmpty()) throw new Api.ApiException(422, "Every challan line must belong to an OSP heat line.");
            double price = f(line, "unit_price"), gst = f(line, "gst_percent");
            if (price < 0) throw new Api.ApiException(422, "Unit price cannot be negative.");
            if (gst < 0 || gst > 100) throw new Api.ApiException(422, "GST % must be between 0 and 100.");
            JSONObject r = new JSONObject();
            r.put("osp_job_id", s(line, "osp_job_id"));
            int ln = (int) f(line, "line_no");
            r.put("line_no", ln > 0 ? ln : position);
            for (String k : new String[]{"item_code", "item_description", "hsn_code", "batch_code", "remarks"}) r.put(k, s(line, k).isEmpty() ? JSONObject.NULL : s(line, k));
            r.put("uom", s(line, "uom").isEmpty() ? DEFAULT_UOM : s(line, "uom").toUpperCase(Locale.ROOT));
            r.put("unit_price", round(price, 4));
            r.put("gst_percent", round(gst, 2));
            result.add(r);
        }
        return result;
    }

    /** clean_return: quantities >= 0; a return without OSP Inward needs a quantity and a vendor challan / invoice number. */
    static JSONObject cleanReturn(JSONObject p) throws Exception {
        double returned = f(p, "quantity_returned"), rejected = f(p, "quantity_rejected");
        if (returned < 0 || rejected < 0) throw new Api.ApiException(422, "Returned and rejected quantities cannot be negative.");
        boolean linked = !s(p, "osp_receipt_id").isEmpty();
        if (!linked && returned <= 0 && rejected <= 0) throw new Api.ApiException(422, "Enter the returned or rejected quantity.");
        if (!linked && s(p, "vendor_challan_number").isEmpty() && s(p, "vendor_invoice_number").isEmpty())
            throw new Api.ApiException(422, "Enter the vendor challan number or the vendor invoice number.");
        JSONObject out = new JSONObject();
        out.put("quantity_returned", linked ? 0.0 : round(returned, 3));
        out.put("quantity_rejected", round(rejected, 3));
        for (String k : new String[]{"osp_job_id", "osp_receipt_id", "vendor_challan_number", "vendor_challan_date", "vendor_invoice_number",
            "vendor_invoice_date", "vehicle_number", "remarks"}) out.put(k, s(p, k).isEmpty() ? JSONObject.NULL : s(p, k));
        return out;
    }

    static List<String> vendorEmails(JSONObject vendor) {
        String raw = s(vendor, "notification_emails") + " " + s(vendor, "email");
        List<String> seen = new ArrayList<>();
        for (String v : raw.split("[\\s,;]+")) {
            v = v.trim();
            if (!v.contains("@")) continue;
            boolean dup = false;
            for (String x : seen) if (x.equalsIgnoreCase(v)) dup = true;
            if (!dup) seen.add(v);
        }
        return seen;
    }

    /** email_body: vendor-facing subject + body (FSI part number only). */
    static String[] emailBody(JSONObject payload) {
        JSONObject data = vendorSafe(payload);
        StringBuilder b = new StringBuilder();
        b.append("Please find attached Returnable Delivery Challan ").append(s(data, "challan_number")).append(" dated ").append(dateText(data.opt("challan_date"))).append(".\n\n");
        JSONArray items = data.optJSONArray("lines");
        if (items != null) for (int i = 0; i < items.length(); i++) {
            JSONObject it = items.optJSONObject(i);
            if (it == null) continue;
            b.append("- FSI Part ").append(s(it, "item_code")).append(" · ").append(s(it, "item_description")).append(" · Heat ")
                .append(s(it, "heat_number").isEmpty() ? "-" : s(it, "heat_number")).append(" · Batch ").append(s(it, "batch_code").isEmpty() ? "-" : s(it, "batch_code"))
                .append(" · Qty ").append(qty(it.opt("quantity"))).append(" ").append(s(it, "uom")).append("\n");
        }
        b.append("\nProcess to be done: ").append(s(data, "process_text").isEmpty() ? "-" : s(data, "process_text"));
        b.append("\nExpected delivery: ").append(dateText(data.opt("delivery_date")).isEmpty() ? "-" : dateText(data.opt("delivery_date")));
        b.append("\n\nPlease mention this challan number on your return delivery challan / invoice.\n\nRegards,\nFour Star Industries · QCMS");
        return new String[]{"Returnable Delivery Challan " + s(data, "challan_number") + " · OSP job work", b.toString()};
    }

    /** challan_status_label: DRAFT / CANCELLED / CLOSED (all back) / ISSUED. */
    static String statusLabel(JSONObject payload) {
        String status = s(payload, "status").toUpperCase(Locale.ROOT);
        if (!payload.optBoolean("saved", true) || "DRAFT".equals(status)) return "DRAFT";
        if ("CANCELLED".equals(status) || "CLOSED".equals(status)) return status;
        JSONObject summary = payload.optJSONObject("summary");
        JSONArray returns = payload.optJSONArray("returns");
        if (returns != null && returns.length() > 0 && f(summary, "dispatched") > 0 && f(summary, "balance") <= 0) return "CLOSED";
        return "ISSUED";
    }

    // ================================================================== service (reads never throw, like OSPChallanService._select)
    static List<JSONObject> select(Api api, String path) {
        try { return InspUtil.list(api.rows(path)); } catch (Exception e) { return new ArrayList<>(); }
    }

    static JSONObject one(Api api, String table, String id) {
        if (id == null || id.isEmpty()) return null;
        List<JSONObject> r = select(api, table + "?select=*&id=eq." + Api.enc(id) + "&limit=1");
        return r.isEmpty() ? null : r.get(0);
    }

    static List<JSONObject> branches(Api api) { return select(api, "company_branches?select=*&status=eq.ACTIVE&order=branch_name.asc&limit=200"); }

    static JSONObject defaultBranch(List<JSONObject> branches) {
        for (JSONObject b : branches) if (b.optBoolean("is_default", false)) return b;
        return branches.isEmpty() ? null : branches.get(0);
    }

    static List<JSONObject> shipToParties(Api api) { return select(api, "parties?select=id,party_code,party_name,party_types,city,status&status=eq.ACTIVE&order=party_name.asc&limit=3000"); }

    /** challan_for(document): group challan by material_out_id, legacy single job by osp_job_id. */
    static JSONObject challanFor(Api api, String materialOutId, String jobId) {
        List<JSONObject> r = materialOutId != null && !materialOutId.isEmpty()
            ? select(api, "osp_challans?select=*&material_out_id=eq." + Api.enc(materialOutId) + "&limit=1")
            : select(api, "osp_challans?select=*&osp_job_id=eq." + Api.enc(jobId) + "&limit=1");
        return r.isEmpty() ? null : r.get(0);
    }

    static List<JSONObject> lines(Api api, String challanId) {
        return select(api, "osp_challan_lines?select=*&challan_id=eq." + Api.enc(challanId) + "&order=line_no.asc&limit=500");
    }

    static List<JSONObject> returnEntries(Api api, String challanId) {
        return select(api, "osp_challan_returns?select=*&challan_id=eq." + Api.enc(challanId) + "&order=created_at.asc&limit=500");
    }

    static List<JSONObject> receipts(Api api, List<String> jobIds) {
        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; i < jobIds.size(); i += 80) {
            out.addAll(select(api, "osp_receipts?select=*&osp_job_id=in.(" + String.join(",", jobIds.subList(i, Math.min(jobIds.size(), i + 80))) + ")&order=receipt_date.asc&limit=2000"));
        }
        return out;
    }

    static List<JSONObject> returnsFor(Api api, JSONObject challan, List<String> jobIds) {
        List<JSONObject> entries = challan == null || s(challan, "id").isEmpty() ? new ArrayList<>() : returnEntries(api, s(challan, "id"));
        return mergeReturns(receipts(api, jobIds), entries);
    }

    /** next_number: RPC qcms_next_osp_challan_number, else the Python fallback over saved challans / dispatch challans. */
    static String nextNumber(Api api, String branchId) {
        try {
            Object v = api.rpcValue("qcms_next_osp_challan_number", new JSONObject().put("p_branch_id", branchId == null || branchId.isEmpty() ? JSONObject.NULL : branchId));
            if (v instanceof String && !((String) v).trim().isEmpty()) return ((String) v).trim();
        } catch (Exception ignored) { }
        String code = "D9";
        for (JSONObject b : branches(api)) {
            if (branchId == null || branchId.isEmpty() || branchId.equals(s(b, "id"))) {
                code = SupPdfKit.first(s(b, "plant_code"), s(b, "branch_code"), code);
                break;
            }
        }
        List<String> existing = new ArrayList<>();
        for (JSONObject r : select(api, "osp_challans?select=challan_number&order=challan_date.desc&limit=5000")) existing.add(s(r, "challan_number"));
        for (JSONObject r : select(api, "osp_jobs?select=dispatch_challan&order=created_at.desc&limit=5000")) existing.add(s(r, "dispatch_challan"));
        return nextNumberFrom(existing, code);
    }

    /** default_prices: last challan price for the same Part + OSP Vendor (+ Process), else the Part/Supplier price master. */
    static JSONObject defaultPrices(Api api, String partId, String vendorId, String processId) {
        JSONObject result = new JSONObject();
        try {
            result.put("unit_price", 0.0); result.put("gst_percent", DEFAULT_GST); result.put("uom", DEFAULT_UOM);
            if (partId == null || partId.isEmpty()) return result;
            List<JSONObject> jobs = select(api, "osp_jobs?select=id,process_id&part_id=eq." + Api.enc(partId)
                + (vendorId == null || vendorId.isEmpty() ? "" : "&vendor_id=eq." + Api.enc(vendorId)) + "&order=created_at.desc&limit=200");
            if (processId != null && !processId.isEmpty()) {
                List<JSONObject> same = new ArrayList<>();
                for (JSONObject j : jobs) if (processId.equals(s(j, "process_id"))) same.add(j);
                if (!same.isEmpty()) jobs = same;
            }
            List<String> ids = new ArrayList<>();
            for (JSONObject j : jobs) if (!s(j, "id").isEmpty() && ids.size() < 150) ids.add(s(j, "id"));
            if (!ids.isEmpty()) {
                List<JSONObject> lines = select(api, "osp_challan_lines?select=unit_price,gst_percent,uom&osp_job_id=in.(" + String.join(",", ids) + ")&order=updated_at.desc&limit=1");
                if (!lines.isEmpty()) {
                    JSONObject l = lines.get(0);
                    result.put("unit_price", f(l, "unit_price"));
                    result.put("gst_percent", l.isNull("gst_percent") ? DEFAULT_GST : f(l, "gst_percent"));
                    result.put("uom", s(l, "uom").isEmpty() ? DEFAULT_UOM : s(l, "uom"));
                    return result;
                }
            }
            if (vendorId != null && !vendorId.isEmpty()) {
                List<JSONObject> prices = select(api, "part_supplier_price_history?select=price,uom,status&part_id=eq." + Api.enc(partId)
                    + "&supplier_id=eq." + Api.enc(vendorId) + "&order=start_date.desc&limit=5");
                List<JSONObject> active = new ArrayList<>();
                for (JSONObject p : prices) if ("ACTIVE".equalsIgnoreCase(s(p, "status").isEmpty() ? "ACTIVE" : s(p, "status"))) active.add(p);
                if (active.isEmpty()) active = prices;
                if (!active.isEmpty()) {
                    result.put("unit_price", f(active.get(0), "price"));
                    result.put("uom", s(active.get(0), "uom").isEmpty() ? DEFAULT_UOM : s(active.get(0), "uom").toUpperCase(Locale.ROOT));
                }
            }
        } catch (Exception ignored) { }
        return result;
    }

    static boolean duplicateNumber(Api api, String number, String challanId) {
        String wanted = s(number).toUpperCase(Locale.ROOT);
        for (JSONObject r : select(api, "osp_challans?select=id&challan_number=eq." + Api.enc(wanted) + "&limit=5")) {
            if (!s(r, "id").equals(challanId == null ? "" : challanId)) return true;
        }
        return false;
    }

    /** save(document, header, lines, challan_id): header insert / update, then each line insert / update by OSP job. */
    static JSONObject save(Api api, String materialOutId, String jobId, JSONObject header, List<JSONObject> lines, String challanId) throws Exception {
        JSONObject payload = cleanHeader(header);
        List<JSONObject> clean = cleanLines(lines);
        JSONObject saved;
        if (challanId != null && !challanId.isEmpty()) saved = api.update("osp_challans", challanId, payload);
        else {
            if (materialOutId != null && !materialOutId.isEmpty()) payload.put("material_out_id", materialOutId);
            else payload.put("osp_job_id", jobId);
            saved = api.insert("osp_challans", payload);
        }
        String cid = SupPdfKit.first(s(saved, "id"), challanId);
        if (cid.isEmpty()) throw new Api.ApiException(500, "QCMS did not receive the saved challan ID from the database.");
        Map<String, JSONObject> existing = new HashMap<>();
        for (JSONObject r : lines(api, cid)) existing.put(s(r, "osp_job_id"), r);
        for (JSONObject line : clean) {
            JSONObject row = new JSONObject(line.toString());
            row.put("challan_id", cid);
            JSONObject ex = existing.get(s(line, "osp_job_id"));
            if (ex != null) api.update("osp_challan_lines", s(ex, "id"), row);
            else api.insert("osp_challan_lines", row);
        }
        JSONObject out = saved == null ? new JSONObject() : new JSONObject(saved.toString());
        out.put("id", cid);
        return out;
    }

    /** save_material_out_challan (R38): one retry; a retry re-uses a header a failed attempt already inserted. */
    static Exception saveWithRetry(Api api, String materialOutId, JSONObject header, List<JSONObject> lines) {
        Exception error = null;
        for (int attempt = 0; attempt < 2; attempt++) {
            try {
                JSONObject existing = attempt > 0 ? challanFor(api, materialOutId, null) : null;
                save(api, materialOutId, null, header, lines, existing == null ? null : s(existing, "id"));
                return null;
            } catch (Exception e) { error = e; }
        }
        return error;
    }

    static JSONObject saveReturn(Api api, String challanId, JSONObject payload, String entryId) throws Exception {
        JSONObject row = cleanReturn(payload);
        if (entryId != null && !entryId.isEmpty()) return api.update("osp_challan_returns", entryId, row);
        row.put("challan_id", challanId);
        return api.insert("osp_challan_returns", row);
    }

    /**
     * R38 one-click recovery: challan values entered with a Material Out whose challan could not be saved after the
     * stock-allocating RPC (key = Material Out id, value = {header, lines}). The record's "Complete challan details"
     * form is pre-filled from it; never create the Material Out twice.
     */
    static final Map<String, JSONObject[]> PENDING = new java.util.concurrent.ConcurrentHashMap<>();

    /** link_receipt (R37): OSP Inward -> vendor return details on the challan; null when nothing to store / no challan yet. */
    static JSONObject linkReceipt(Api api, String jobId, String materialOutId, String receiptId, String vehicle, double rejected, String remarks) throws Exception {
        if (receiptId == null || receiptId.isEmpty() || (s(vehicle).isEmpty() && rejected == 0 && s(remarks).isEmpty())) return null;
        JSONObject challan = challanFor(api, materialOutId, materialOutId == null || materialOutId.isEmpty() ? jobId : null);
        if (challan == null) return null;
        List<JSONObject> existing = select(api, "osp_challan_returns?select=id&osp_receipt_id=eq." + Api.enc(receiptId) + "&limit=1");
        JSONObject p = new JSONObject().put("osp_job_id", jobId).put("osp_receipt_id", receiptId).put("vehicle_number", s(vehicle))
            .put("quantity_rejected", rejected).put("remarks", s(remarks));
        return saveReturn(api, s(challan, "id"), p, existing.isEmpty() ? null : s(existing.get(0), "id"));
    }

    static void deleteReturn(Api api, String entryId) throws Exception { api.delete("osp_challan_returns", entryId); }

    /**
     * challan_notifier().notify("OSP_MATERIAL_OUT_CHALLAN", include_generated_pdf=True, include_supplier=False): the
     * vendor-safe challan PDF is stored under notification_exports, one outbox row is queued for the vendor and
     * dispatched through qcms-send-email; the challan is marked e-mailed. Returns the dispatch result text.
     */
    static String emailVendor(Api api, JSONObject challan, JSONObject doc, byte[] pdf, String to, List<String> cc, String subject, String body, String vendorName) throws Exception {
        String recipient = s(to);
        if (!recipient.contains("@")) throw new Api.ApiException(422, "Enter the vendor e-mail address.");
        String file = SndFiles.safeName(s(challan, "challan_number") + ".pdf");
        JSONObject manifest = SndMail.uploadExport(api, SndMail.exportFolder(api), file, pdf, "application/pdf", true);
        JSONArray ccArr = new JSONArray();
        for (String c : cc) if (s(c).contains("@") && !s(c).equalsIgnoreCase(recipient)) ccArr.put(s(c));
        JSONObject ctx = new JSONObject().put("supplier_id", s(doc, "vendor_id")).put("supplier_name", vendorName).put("document_no", s(challan, "challan_number"))
            .put("document_type", "OSP Returnable Delivery Challan").put("next_task", "OSP vendor processing and return").put("event_key", "OSP_MATERIAL_OUT_CHALLAN");
        JSONObject row = new JSONObject();
        row.put("event_key", "OSP_MATERIAL_OUT_CHALLAN");
        row.put("recipient_email", recipient);
        row.put("recipient_name", vendorName == null || vendorName.isEmpty() ? JSONObject.NULL : vendorName);
        row.put("cc_emails", ccArr);
        row.put("subject", s(subject));
        row.put("body_text", body == null ? "" : body);
        row.put("body_html", SndMail.notificationHtml(body == null ? "" : body));
        row.put("related_table", "osp_challans");
        row.put("related_id", s(challan, "id"));
        row.put("context", ctx);
        row.put("template_key", "OSP_MATERIAL_OUT_CHALLAN");
        row.put("attachment_manifest", new JSONArray().put(manifest));
        row.put("is_automatic", false);
        row.put("status", "PENDING");
        JSONObject saved = api.insert("qcms_notification_outbox", row);
        List<String> ids = new ArrayList<>();
        if (!s(saved, "id").isEmpty()) ids.add(s(saved, "id"));
        JSONObject res = SndMail.dispatch(api, ids);
        StringBuilder all = new StringBuilder(recipient);
        for (int i = 0; i < ccArr.length(); i++) all.append(", ").append(ccArr.optString(i));
        markEmailed(api, s(challan, "id"), all.toString());
        return res.has("error") ? "queued (dispatch: " + res.optString("error") + ")" : "sent";
    }

    static void markEmailed(Api api, String challanId, String recipients) {
        try {
            String r = recipients == null ? "" : recipients;
            api.update("osp_challans", challanId, new JSONObject().put("emailed_at", OffsetDateTime.now(ZoneOffset.UTC).toString())
                .put("emailed_to", r.length() > 500 ? r.substring(0, 500) : r));
        } catch (Exception ignored) { }
    }

    // ================================================================== print payload
    /** document_rows: register rows of the challan's heat lines with FSI part number / HSN / description. */
    static List<JSONObject> documentRows(Api api, String materialOutId, String jobId) throws Exception {
        List<String> ids = new ArrayList<>();
        if (materialOutId != null && !materialOutId.isEmpty()) {
            for (JSONObject r : select(api, "osp_jobs?select=id&material_out_id=eq." + Api.enc(materialOutId) + "&limit=200")) ids.add(s(r, "id"));
        } else if (jobId != null && !jobId.isEmpty()) ids.add(jobId);
        List<JSONObject> out = new ArrayList<>();
        if (ids.isEmpty()) return out;
        Map<String, JSONObject> raw = new HashMap<>();
        List<JSONObject> rows = new ArrayList<>();
        for (int i = 0; i < ids.size(); i += 80) {
            String in = String.join(",", ids.subList(i, Math.min(ids.size(), i + 80)));
            rows.addAll(select(api, "v_qsms_osp_register?select=*&id=in.(" + in + ")"));
            for (JSONObject j : select(api, "osp_jobs?select=id,material_out_line_no,expected_return_date,dispatch_remarks&id=in.(" + in + ")")) raw.put(s(j, "id"), j);
        }
        Set<String> partIds = new HashSet<>();
        for (JSONObject r : rows) if (!s(r, "part_id").isEmpty()) partIds.add(s(r, "part_id"));
        Map<String, JSONObject> parts = partIds.isEmpty() ? new HashMap<>() : InspUtil.byId(api, "parts", "id,fsi_part_number,hsn_sac_code,part_name", partIds);
        for (JSONObject r : rows) {
            JSONObject row = new JSONObject(r.toString());
            JSONObject part = parts.get(s(r, "part_id"));
            JSONObject j = raw.get(s(r, "id"));
            int ln = j == null ? 0 : (int) f(j, "material_out_line_no");
            row.put("material_out_line_no", ln > 0 ? ln : 1);
            row.put("fsi_part_number", s(part, "fsi_part_number"));
            row.put("hsn_sac_code", s(part, "hsn_sac_code"));
            row.put("part_name", SupPdfKit.first(s(part, "part_name"), s(r, "part_name")));
            out.add(row);
        }
        out.sort((x, y) -> {
            int c = Integer.compare((int) f(x, "material_out_line_no"), (int) f(y, "material_out_line_no"));
            return c != 0 ? c : s(x, "id").compareTo(s(y, "id"));
        });
        return out;
    }

    /** build_print_payload: vendor-facing payload (FSI part number as ITEM #, no customer data). */
    static JSONObject buildPayload(JSONObject challan, List<JSONObject> rows, List<JSONObject> lines, List<JSONObject> returns,
                                   JSONObject branch, JSONObject vendor, JSONObject shipTo) throws Exception {
        Map<String, JSONObject> byJob = new HashMap<>();
        for (JSONObject l : lines) byJob.put(s(l, "osp_job_id"), l);
        List<JSONObject> items = new ArrayList<>();
        int position = 0;
        LinkedHashMap<String, Boolean> processes = new LinkedHashMap<>();
        double dispatched = 0;
        for (JSONObject row : rows) {
            position++;
            JSONObject line = byJob.get(s(row, "id"));
            boolean has = line != null;
            if (line == null) line = new JSONObject();
            JSONObject it = new JSONObject();
            int ln = (int) f(line, "line_no");
            if (ln <= 0) ln = (int) f(row, "material_out_line_no");
            it.put("line_no", ln > 0 ? ln : position);
            it.put("item_code", SupPdfKit.first(s(line, "item_code"), s(row, "fsi_part_number"), "-"));
            it.put("item_description", SupPdfKit.first(s(line, "item_description"), s(row, "part_name")));
            it.put("hsn_code", SupPdfKit.first(s(line, "hsn_code"), s(row, "hsn_sac_code")));
            it.put("quantity", f(row, "quantity_dispatched"));
            it.put("uom", SupPdfKit.first(s(line, "uom"), DEFAULT_UOM));
            it.put("unit_price", f(line, "unit_price"));
            it.put("gst_percent", has ? f(line, "gst_percent") : DEFAULT_GST);
            it.put("heat_number", s(row, "heat_number"));
            it.put("batch_code", SupPdfKit.first(s(line, "batch_code"), s(row, "osp_batch_code")));
            it.put("process_name", s(row, "process_name"));
            if (!s(row, "process_name").isEmpty()) processes.put(s(row, "process_name").toUpperCase(Locale.ROOT), true);
            dispatched += f(row, "quantity_dispatched");
            items.add(it);
        }
        String process = s(challan, "process_text").isEmpty() ? String.join(", ", processes.keySet()) : s(challan, "process_text");
        JSONObject plant = new JSONObject();
        if (branch != null && branch.length() > 0) {
            plant.put("name", s(branch, "branch_name"));
            plant.put("address1", s(branch, "address_line1"));
            plant.put("address2", SupPdfKit.join(", ", s(branch, "address_line2"), s(branch, "address_line3")));
            plant.put("address3", SupPdfKit.join(" ", s(branch, "city"), s(branch, "postal_code")));
            plant.put("gstin", s(branch, "gstin"));
            plant.put("phone", s(branch, "phone"));
            plant.put("email", s(branch, "email"));
        }
        JSONObject v = vendor == null ? new JSONObject() : vendor;
        JSONObject ship = shipTo != null && shipTo.length() > 0 ? shipTo
            : !s(challan, "ship_to_text").isEmpty() ? new JSONObject().put("party_name", s(challan, "ship_to_text")) : v;
        String[] partyKeys = {"party_name", "address", "city", "state", "country", "tax_identifier", "phone", "email"};
        JSONObject vend = new JSONObject(), shp = new JSONObject();
        for (String k : partyKeys) { vend.put(k, s(v, k)); shp.put(k, s(ship, k)); }
        JSONObject p = new JSONObject();
        p.put("title", CHALLAN_TITLE);
        p.put("challan_number", s(challan, "challan_number"));
        p.put("challan_date", s(challan, "challan_date"));
        p.put("status", s(challan, "status").isEmpty() ? "DRAFT" : s(challan, "status").toUpperCase(Locale.ROOT));
        p.put("saved", !s(challan, "id").isEmpty());
        p.put("plant", plant);
        p.put("vendor", vend);
        p.put("ship_to", shp);
        for (String k : new String[]{"user_name", "ship_via", "incoterm", "delivery_date", "payment_term", "reference_details", "old_po_details",
            "vehicle_number", "transporter_name", "eway_bill_number", "remarks"}) p.put(k, s(challan, k));
        p.put("process_text", process);
        JSONArray arr = new JSONArray();
        for (JSONObject it : items) arr.put(it);
        p.put("lines", arr);
        p.put("totals", totals(items, challan.opt("shipping_amount"), challan.opt("other_amount")));
        JSONArray ret = new JSONArray();
        for (JSONObject r : returns) ret.put(r);
        p.put("returns", ret);
        p.put("summary", balanceSummary(dispatched, returns));
        return vendorSafe(p);
    }

    /** print_payload_for(challan_id). */
    static JSONObject payloadForChallan(Api api, JSONObject challan) throws Exception {
        String moId = s(challan, "material_out_id");
        List<JSONObject> rows = documentRows(api, moId, moId.isEmpty() ? s(challan, "osp_job_id") : null);
        JSONObject branch = one(api, "company_branches", s(challan, "branch_id"));
        String vendorId = SupPdfKit.first(s(challan, "vendor_id"), rows.isEmpty() ? "" : s(rows.get(0), "vendor_id"));
        JSONObject vendor = one(api, "parties", vendorId);
        JSONObject ship = one(api, "parties", s(challan, "ship_to_party_id"));
        List<String> jobIds = new ArrayList<>();
        for (JSONObject r : rows) jobIds.add(s(r, "id"));
        return buildPayload(challan, rows, lines(api, s(challan, "id")), returnsFor(api, challan, jobIds), branch, vendor, ship);
    }

    /**
     * osp_challan_payload: a saved challan prints as saved; a Material Out without saved challan details prints a DRAFT
     * challan from the Material Out itself (challan no = dispatch challan, delivery = expected return).
     */
    static JSONObject payloadForDocument(Api api, String materialOutId, String jobId) throws Exception {
        JSONObject challan = challanFor(api, materialOutId, jobId);
        if (challan != null) return payloadForChallan(api, challan);
        JSONObject source = null;
        if (materialOutId != null && !materialOutId.isEmpty()) {
            List<JSONObject> first = select(api, "osp_jobs?select=*&material_out_id=eq." + Api.enc(materialOutId) + "&order=material_out_line_no.asc&limit=1");
            if (!first.isEmpty()) source = first.get(0);
        } else source = one(api, "osp_jobs", jobId);
        if (source == null) throw new Api.ApiException(404, "OSP job / Material Out not found.");
        JSONObject group = materialOutId == null || materialOutId.isEmpty() ? null : one(api, "osp_material_outs", materialOutId);
        JSONObject draft = new JSONObject();
        draft.put("challan_number", SupPdfKit.first(s(source, "dispatch_challan"), s(group, "material_out_number")));
        draft.put("challan_date", s(source, "dispatch_date"));
        draft.put("delivery_date", s(source, "expected_return_date"));
        draft.put("vendor_id", s(source, "vendor_id"));
        draft.put("status", "DRAFT");
        List<JSONObject> rows = documentRows(api, materialOutId, materialOutId == null || materialOutId.isEmpty() ? s(source, "id") : null);
        JSONObject branch = defaultBranch(branches(api));
        JSONObject vendor = one(api, "parties", s(source, "vendor_id"));
        List<String> jobIds = new ArrayList<>();
        for (JSONObject r : rows) jobIds.add(s(r, "id"));
        return buildPayload(draft, rows, new ArrayList<>(), returnsFor(api, null, jobIds), branch, vendor, null);
    }
}
