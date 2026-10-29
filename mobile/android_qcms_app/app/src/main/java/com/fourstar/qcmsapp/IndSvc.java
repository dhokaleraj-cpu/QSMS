package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;
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
import java.util.TreeSet;

/**
 * R39 · Indirect Purchase service - port of core/indirect_purchase_service.py (website R37).
 * Item master + categories, Purchase Requisition → Indirect PO (own IPO series, value-based approval via
 * qcms_module_approval_routes module key INDIRECT_PURCHASE), Indirect Inward (GRN) and the indirect stock ledger.
 * Approval, GRN posting and stock movements run in the same SECURITY DEFINER RPCs as the website
 * (qcms_approve_indirect_po, qcms_reject_indirect_po, qcms_post_indirect_grn, qcms_decide_indirect_grn,
 * qcms_issue_indirect_stock, qcms_next_indirect_number, qcms_indirect_po_approval_target).
 * Indirect POs carry no customer data (supplier documents are customer-safe by construction).
 * All methods that read / write run on a background thread.
 */
final class IndSvc {
    static final String MODULE_KEY = "INDIRECT_PURCHASE";
    static final String[][] DEFAULT_CATEGORIES = {
        {"CONSUMABLES", "Consumables"}, {"TOOLS_TOOLING", "Tools & Tooling"}, {"SPARES_MAINTENANCE", "Spares / Maintenance"},
        {"STATIONERY", "Stationery"}, {"IT", "IT / Computers"}, {"SERVICES", "Services"}, {"CAPITAL_ASSET", "Capital / Asset"},
        {"PACKING", "Packing Material"}, {"SAFETY_PPE", "Safety / PPE"}, {"OTHERS", "Others"}};
    static final String[] UOMS = {"NOS", "PCS", "SET", "PAIR", "BOX", "PKT", "KG", "GM", "LTR", "ML", "MTR", "MM", "SQM", "ROLL", "REAM", "LOT", "JOB", "HRS", "DAYS", "MONTH", "YEAR", "LS"};
    static final String[] GST_RATES = {"0", "5", "12", "18", "28"};
    static final Set<String> SUPPLIER_TYPES = new HashSet<>(Arrays.asList("SUPPLIER", "OSP_VENDOR", "VENDOR", "SERVICE_PROVIDER", "CONTRACTOR", "STEEL_MILL"));
    static final Set<String> OPEN_PO_STATUSES = new HashSet<>(Arrays.asList("APPROVED", "PARTIALLY_RECEIVED"));
    static final Set<String> EDITABLE_PO_STATUSES = new HashSet<>(Arrays.asList("DRAFT", "PENDING_APPROVAL", "REJECTED", "APPROVED"));
    static final String DEFAULT_TERMS = "Prices are firm for the order quantity. Goods / services are subject to inspection and acceptance at our premises.";
    static final String DEFAULT_INSTRUCTIONS = "1. Indirect PO number must be mentioned on your Invoice / Delivery Challan.\n"
        + "2. Material / service must conform to the specification, make and quantity stated in this order.\n"
        + "3. Warranty / guarantee certificates, manuals and test certificates (where applicable) to accompany the supply.\n"
        + "4. Delivery to the Ship-To address within the delivery date; partial supply only with prior written consent.\n"
        + "5. Payment as per the payment term after receipt and acceptance (GRN) of the material / service.";
    static final String[][] SERIES = {{"IPO", "Indirect Purchase Order"}, {"IGRN", "Indirect GRN"}, {"IPR", "Purchase Requisition"}, {"IITEM", "Indirect Item Code"}, {"ISS", "Stock Issue"}};

    static String statusLabel(String status) {
        switch (status == null ? "" : status.toUpperCase(Locale.ROOT)) {
            case "DRAFT": return "Draft";
            case "PENDING_APPROVAL": return "Pending Approval";
            case "APPROVED": return "Approved (Open)";
            case "PARTIALLY_RECEIVED": return "Partially Received";
            case "CLOSED": return "Closed";
            case "CANCELLED": return "Cancelled";
            case "REJECTED": return "Rejected";
            default: return status == null || status.isEmpty() ? "-" : Ui.pretty(status);
        }
    }

    final Api api;
    private final Map<String, Object> memo = new HashMap<>();

    IndSvc(Api api) { this.api = api; }

    void invalidate() { memo.clear(); }

    // ================================================================== pure helpers
    static String s(JSONObject r, String k) { return SupSvc.s(r, k); }
    static String clean(Object v) {
        if (v == null || v == JSONObject.NULL) return "";
        String t = String.valueOf(v).trim();
        return "null".equals(t) ? "" : t.replaceAll("\\s+", " ");
    }
    static String c(JSONObject r, String k) { return r == null ? "" : clean(r.opt(k)); }
    static double num(Object v) { return SupSvc.num(v); }
    static double num(JSONObject r, String k) { return r == null ? 0 : SupSvc.num(r.opt(k)); }
    static boolean blank(JSONObject r, String k) { return r == null || c(r, k).isEmpty(); }
    static double r2(double v) { return SupSvc.r2(v); }
    static double r4(double v) { return Math.round(v * 10000.0) / 10000.0; }
    static Object nul(String v) { return v == null || v.trim().isEmpty() ? JSONObject.NULL : v.trim(); }
    static String d10(Object v) { String t = clean(v); return t.length() >= 10 ? t.substring(0, 10) : t; }
    static String nowUtc() { return OffsetDateTime.now(ZoneOffset.UTC).toString(); }
    static String up(JSONObject r, String k) { return c(r, k).toUpperCase(Locale.ROOT); }

    private static final String[] ONES = {"", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
        "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"};
    private static final String[] TENS = {"", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"};

    private static String belowThousand(long n) {
        List<String> words = new ArrayList<>();
        if (n >= 100) { words.add(ONES[(int) (n / 100)] + " Hundred"); n %= 100; }
        if (n >= 20) words.add(TENS[(int) (n / 10)] + (n % 10 != 0 ? " " + ONES[(int) (n % 10)] : ""));
        else if (n > 0) words.add(ONES[(int) n]);
        return String.join(" ", words);
    }

    /** indian_words: Thousand, Lakh, Crore. */
    static String indianWords(long n) {
        if (n == 0) return "Zero";
        List<String> parts = new ArrayList<>();
        long crore = n / 10_000_000L; n %= 10_000_000L;
        long lakh = n / 100_000L; n %= 100_000L;
        long thousand = n / 1000L; n %= 1000L;
        if (crore > 0) parts.add(indianWords(crore) + " Crore");
        if (lakh > 0) parts.add(belowThousand(lakh) + " Lakh");
        if (thousand > 0) parts.add(belowThousand(thousand) + " Thousand");
        if (n > 0) parts.add(belowThousand(n));
        return String.join(" ", parts);
    }

    static String amountInWords(double amount, String currency) {
        double value = Math.round((Math.abs(amount) + 1e-9) * 100.0) / 100.0;
        long whole = (long) value;
        long fraction = Math.round((value - whole) * 100);
        String cur = currency == null || currency.isEmpty() ? "INR" : currency.toUpperCase(Locale.ROOT);
        String unit, sub;
        switch (cur) {
            case "INR": unit = "Rupees"; sub = "Paise"; break;
            case "USD": unit = "US Dollars"; sub = "Cents"; break;
            case "EUR": unit = "Euros"; sub = "Cents"; break;
            default: unit = cur; sub = "Cents";
        }
        String text = unit + " " + indianWords(whole);
        if (fraction > 0) text += " and " + indianWords(fraction) + " " + sub;
        return text + " Only";
    }

    private static String stateCode(String gstin) {
        String t = clean(gstin).toUpperCase(Locale.ROOT);
        return t.length() >= 2 && Character.isDigit(t.charAt(0)) && Character.isDigit(t.charAt(1)) ? t.substring(0, 2) : "";
    }

    /** INTRA (CGST + SGST) when the supplier is in the plant state, else INTER (IGST). */
    static String gstMode(JSONObject supplier, JSONObject plant) {
        String sc = stateCode(SupSvc.first(c(supplier, "tax_identifier"), c(supplier, "gstin")));
        String pc = stateCode(SupSvc.first(c(plant, "gstin"), c(plant, "tax_identifier")));
        if (!sc.isEmpty() && !pc.isEmpty()) return sc.equals(pc) ? "INTRA" : "INTER";
        Map<String, String> aliases = new HashMap<>();
        aliases.put("mh", "maharashtra"); aliases.put("ka", "karnataka"); aliases.put("gj", "gujarat"); aliases.put("tn", "tamil nadu"); aliases.put("dl", "delhi");
        String ss = c(supplier, "state").toLowerCase(Locale.ROOT);
        String ps = c(plant, "state").toLowerCase(Locale.ROOT);
        if (ps.isEmpty()) ps = "maharashtra";
        if (aliases.containsKey(ss)) ss = aliases.get(ss);
        if (aliases.containsKey(ps)) ps = aliases.get(ps);
        String country = c(supplier, "country").toLowerCase(Locale.ROOT);
        if (!country.isEmpty() && !country.equals("india") && !country.equals("in") && !country.equals("bharat")) return "INTER";
        if (ss.isEmpty()) return "INTRA";
        return ss.equals(ps) ? "INTRA" : "INTER";
    }

    static JSONObject computeLine(JSONObject line, String mode) throws Exception {
        double qty = r4(num(line, "quantity"));
        double rate = r4(num(line, "rate"));
        double disc = Math.min(Math.max(num(line, "discount_percent"), 0), 100);
        double gross = r2(qty * rate);
        double discount = r2(gross * disc / 100.0);
        double taxable = r2(gross - discount);
        double gstPct = Math.max(num(line, "gst_percent"), 0);
        double gst = r2(taxable * gstPct / 100.0);
        double cgst, sgst, igst;
        if ("INTER".equalsIgnoreCase(mode)) { cgst = 0; sgst = 0; igst = gst; }
        else { cgst = r2(gst / 2.0); sgst = r2(gst - cgst); igst = 0; }
        JSONObject out = new JSONObject(line.toString());
        out.put("quantity", qty).put("rate", rate).put("discount_percent", disc).put("gross_amount", gross).put("discount_amount", discount)
            .put("taxable_amount", taxable).put("gst_percent", gstPct).put("gst_amount", gst).put("cgst_amount", cgst).put("sgst_amount", sgst)
            .put("igst_amount", igst).put("line_total", r2(taxable + gst));
        return out;
    }

    static JSONObject computeTotals(List<JSONObject> lines, String mode, double freight, double other, boolean roundToRupee, String currency) throws Exception {
        JSONArray computed = new JSONArray();
        double gross = 0, discount = 0, taxable = 0, cgst = 0, sgst = 0, igst = 0;
        for (JSONObject l : lines) {
            JSONObject c = computeLine(l, mode);
            computed.put(c);
            gross += num(c, "gross_amount"); discount += num(c, "discount_amount"); taxable += num(c, "taxable_amount");
            cgst += num(c, "cgst_amount"); sgst += num(c, "sgst_amount"); igst += num(c, "igst_amount");
        }
        gross = r2(gross); discount = r2(discount); taxable = r2(taxable); cgst = r2(cgst); sgst = r2(sgst); igst = r2(igst);
        double freightV = r2(Math.max(freight, 0)), otherV = r2(other);
        double before = r2(taxable + cgst + sgst + igst + freightV + otherV);
        double grand = roundToRupee ? Math.rint(before) : before;   // Python round(): banker's rounding on .5
        return new JSONObject().put("lines", computed).put("gst_mode", mode.toUpperCase(Locale.ROOT)).put("gross_amount", gross).put("discount_amount", discount)
            .put("subtotal", taxable).put("cgst_amount", cgst).put("sgst_amount", sgst).put("igst_amount", igst).put("freight_amount", freightV)
            .put("other_amount", otherV).put("round_off", r2(grand - before)).put("grand_total", r2(grand)).put("amount_in_words", amountInWords(grand, currency));
    }

    static String financialYear(LocalDate on) {
        LocalDate d = on == null ? LocalDate.now() : on;
        int start = d.getMonthValue() >= 4 ? d.getYear() : d.getYear() - 1;
        return String.format(Locale.US, "%02d", start % 100);
    }

    static String previewNumber(String series, String branchCode) {
        if ("IITEM".equalsIgnoreCase(series)) return "IND-NEW";
        String b = clean(branchCode).toUpperCase(Locale.ROOT);
        return series.toUpperCase(Locale.ROOT) + "-" + (b.isEmpty() ? "HO" : b) + "-" + financialYear(null) + "-NEW";
    }

    /** ordered × (1 + tolerance %) − accepted (never negative). */
    static double receivableQty(double ordered, double accepted, double tolerancePercent) {
        double tol = Math.min(Math.max(tolerancePercent, 0), 50);
        return r4(Math.max(ordered * (1.0 + tol / 100.0) - accepted, 0));
    }

    static String employeeName(JSONObject row) {
        String n = (c(row, "first_name") + " " + c(row, "last_name")).trim();
        return n.isEmpty() ? c(row, "employee_code") : n;
    }

    static JSONObject partySnapshot(JSONObject row) throws Exception {
        JSONObject out = new JSONObject();
        for (String k : new String[]{"party_code", "party_name", "address", "city", "state", "country", "tax_identifier", "phone", "email", "contact_person"})
            out.put(k, row == null || row.isNull(k) ? JSONObject.NULL : row.opt(k));
        return out;
    }

    // ================================================================== data access
    @SuppressWarnings("unchecked")
    private List<JSONObject> memoRows(String key, String path) throws Exception {
        Object v = memo.get(key);
        if (v != null) return (List<JSONObject>) v;
        List<JSONObject> rows = SupSvc.list(new JSONArray(api.get(path, false).body));
        memo.put(key, rows);
        return rows;
    }

    private List<JSONObject> select(String path) {
        try { return SupSvc.list(new JSONArray(api.get(path, false).body)); } catch (Exception e) { return new ArrayList<>(); }
    }

    private JSONObject one(String table, String id) {
        if (id == null || id.isEmpty()) return new JSONObject();
        List<JSONObject> r = select(table + "?select=*&id=eq." + Api.enc(id) + "&limit=1");
        return r.isEmpty() ? new JSONObject() : r.get(0);
    }

    /** Effective INDIRECT_PURCHASE permission (view / create / edit / validate / approve / archive) - same function as RLS. */
    boolean can(String perm) {
        if (api.isAdmin()) return true;
        try {
            Object v = api.rpcValue("qcms_indirect_purchase_can", new JSONObject().put("p_permission", perm));
            return v != null && "true".equalsIgnoreCase(String.valueOf(v).trim());
        } catch (Exception e) {
            return AdmPerm.current(api, MODULE_KEY, "can_" + perm);
        }
    }

    /** Map of view/create/edit/validate/approve/archive → granted (one background call each). */
    Map<String, Boolean> perms() {
        Map<String, Boolean> out = new HashMap<>();
        for (String p : new String[]{"view", "create", "edit", "validate", "approve", "archive"}) out.put(p, can(p));
        return out;
    }

    List<JSONObject> parties() throws Exception { return memoRows("parties", "parties?select=*&status=eq.ACTIVE&order=party_name.asc&limit=5000"); }

    List<JSONObject> suppliers() throws Exception {
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject r : parties()) {
            for (String t : SupSvc.partyTypes(r)) if (SUPPLIER_TYPES.contains(t)) { out.add(r); break; }
        }
        return out;
    }

    JSONObject party(String id) throws Exception {
        if (id == null || id.isEmpty()) return new JSONObject();
        for (JSONObject r : parties()) if (id.equals(s(r, "id"))) return r;
        return one("parties", id);
    }

    List<JSONObject> branches() throws Exception { return memoRows("branches", "company_branches?select=*&status=eq.ACTIVE&order=branch_code.asc&limit=500"); }

    JSONObject branch(String id) throws Exception {
        if (id == null || id.isEmpty()) return new JSONObject();
        for (JSONObject r : branches()) if (id.equals(s(r, "id"))) return r;
        return new JSONObject();
    }

    static String branchLabel(JSONObject b) { return Lookups.join(c(b, "branch_code"), c(b, "branch_name"), c(b, "city")); }

    List<JSONObject> employees() throws Exception { return memoRows("employees", "employees?select=*&status=eq.ACTIVE&order=first_name.asc&limit=5000"); }

    JSONObject employee(String id) throws Exception {
        if (id == null || id.isEmpty()) return new JSONObject();
        for (JSONObject r : employees()) if (id.equals(s(r, "id"))) return r;
        return one("employees", id);
    }

    List<String> departments() throws Exception {
        TreeSet<String> set = new TreeSet<>(String.CASE_INSENSITIVE_ORDER);
        for (JSONObject e : employees()) if (!c(e, "department").isEmpty()) set.add(c(e, "department"));
        return new ArrayList<>(set);
    }

    List<JSONObject> categories() throws Exception {
        Map<String, JSONObject> byCode = new LinkedHashMap<>();
        for (String[] d : DEFAULT_CATEGORIES) byCode.put(d[0], new JSONObject().put("category_code", d[0]).put("category_name", d[1]).put("status", "ACTIVE").put("_default", true));
        for (JSONObject r : memoRows("categories", "indirect_item_categories?select=*&order=category_name.asc&limit=500"))
            byCode.put(up(r, "category_code"), r);
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject r : byCode.values()) if ("ACTIVE".equals(c(r, "status").isEmpty() ? "ACTIVE" : up(r, "status"))) out.add(r);
        return out;
    }

    Map<String, String> categoryLabels() throws Exception {
        Map<String, String> out = new LinkedHashMap<>();
        for (JSONObject r : categories()) out.put(c(r, "category_code"), SupSvc.first(c(r, "category_name"), c(r, "category_code")));
        return out;
    }

    JSONObject saveCategory(String code, String name, String description, String status) throws Exception {
        String key = clean(code).toUpperCase(Locale.ROOT).replaceAll("[^A-Z0-9]", "_").replaceAll("^_+|_+$", "");
        if (key.isEmpty() || clean(name).isEmpty()) throw new SupSvc.Rule("Category code and name are required.");
        JSONObject p = new JSONObject().put("category_code", key).put("category_name", clean(name)).put("description", nul(description)).put("status", status == null ? "ACTIVE" : status);
        JSONObject row = api.upsertBy("indirect_item_categories", p, "category_code");
        invalidate();
        return row;
    }

    List<JSONObject> items(boolean activeOnly) throws Exception {
        List<JSONObject> rows = memoRows("items", "indirect_items?select=*&order=item_code.asc&limit=10000");
        if (!activeOnly) return rows;
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject r : rows) if (c(r, "status").isEmpty() || "ACTIVE".equals(up(r, "status"))) out.add(r);
        return out;
    }

    JSONObject item(String id) throws Exception {
        if (id == null || id.isEmpty()) return new JSONObject();
        for (JSONObject r : items(false)) if (id.equals(s(r, "id"))) return r;
        return one("indirect_items", id);
    }

    static String itemLabel(JSONObject r) { return c(r, "item_code") + " · " + c(r, "item_name") + " · " + c(r, "uom"); }

    String nextNumber(String series, String branchId) throws Exception {
        Object v = api.rpcValue("qcms_next_indirect_number", new JSONObject().put("p_series_key", series.toUpperCase(Locale.ROOT)).put("p_company_branch_id", nul(branchId)));
        String value = v == null ? "" : clean(v).replace("\"", "");
        if (value.isEmpty() || "null".equals(value)) throw new SupSvc.Rule("The Indirect Purchase number series did not return a number. Run the R37 database step.");
        return value;
    }

    static Object optNum(JSONObject p, String k) { return p == null || c(p, k).isEmpty() ? JSONObject.NULL : (Object) num(p, k); }

    JSONObject itemPayload(JSONObject p) throws Exception {
        String name = c(p, "item_name");
        if (name.isEmpty()) throw new SupSvc.Rule("Item name is required.");
        double gst = num(p, "gst_percent");
        if (gst < 0 || gst > 100) throw new SupSvc.Rule("GST % must be between 0 and 100.");
        for (String k : new String[]{"reorder_level", "min_stock", "max_stock"})
            if (!c(p, k).isEmpty() && num(p, k) < 0) throw new SupSvc.Rule(Ui.pretty(k) + " cannot be negative.");
        if (!c(p, "min_stock").isEmpty() && !c(p, "max_stock").isEmpty() && num(p, "max_stock") != 0 && num(p, "min_stock") > num(p, "max_stock"))
            throw new SupSvc.Rule("Minimum stock cannot be more than maximum stock.");
        String spec = p.isNull("specification") ? "" : p.optString("specification", "").trim();
        boolean stock = !p.has("is_stock_item") || p.isNull("is_stock_item") || SndData.truthy(p.opt("is_stock_item"));
        return new JSONObject().put("item_code", nul(c(p, "item_code").toUpperCase(Locale.ROOT))).put("item_name", name)
            .put("category", c(p, "category").isEmpty() ? "OTHERS" : c(p, "category").toUpperCase(Locale.ROOT)).put("description", nul(c(p, "description")))
            .put("specification", nul(spec)).put("uom", c(p, "uom").isEmpty() ? "NOS" : c(p, "uom").toUpperCase(Locale.ROOT)).put("hsn_sac", nul(c(p, "hsn_sac")))
            .put("gst_percent", gst).put("default_supplier_id", nul(c(p, "default_supplier_id"))).put("last_price", optNum(p, "last_price"))
            .put("is_stock_item", stock).put("reorder_level", optNum(p, "reorder_level")).put("min_stock", optNum(p, "min_stock")).put("max_stock", optNum(p, "max_stock"))
            .put("storage_location", nul(c(p, "storage_location"))).put("status", c(p, "status").isEmpty() ? "ACTIVE" : up(p, "status")).put("remarks", nul(c(p, "remarks")));
    }

    JSONObject saveItem(JSONObject payload, String recordId) throws Exception {
        JSONObject data = itemPayload(payload);
        String code = data.isNull("item_code") ? "" : data.getString("item_code");
        for (JSONObject row : items(false)) {
            if (recordId != null && recordId.equals(s(row, "id"))) continue;
            if (!code.isEmpty() && up(row, "item_code").equals(code)) throw new SupSvc.Rule("Item code " + code + " already exists.");
            if (c(row, "item_name").equalsIgnoreCase(data.getString("item_name")) && up(row, "uom").equals(data.getString("uom"))
                && (c(row, "status").isEmpty() || "ACTIVE".equals(c(row, "status"))))
                throw new SupSvc.Rule("An active item '" + data.getString("item_name") + "' (" + data.getString("uom") + ") already exists as " + c(row, "item_code") + ".");
        }
        JSONObject row;
        if (recordId != null && !recordId.isEmpty()) {
            if (code.isEmpty()) data.remove("item_code");
            row = api.update("indirect_items", recordId, data);
        } else {
            if (code.isEmpty()) data.put("item_code", nextNumber("IITEM", null));
            row = api.insert("indirect_items", data);
        }
        invalidate();
        return row;
    }

    Map<String, JSONObject> seriesSettings() throws Exception {
        Map<String, JSONObject> rows = new HashMap<>();
        for (JSONObject r : select("indirect_number_series?select=*&limit=50")) rows.put(up(r, "series_key"), r);
        Map<String, JSONObject> out = new LinkedHashMap<>();
        for (String[] s : SERIES) {
            String key = s[0];
            JSONObject d = new JSONObject().put("series_key", key).put("prefix", "IITEM".equals(key) ? "IND" : key).put("include_branch", !"IITEM".equals(key))
                .put("include_year", !"IITEM".equals(key)).put("year_mode", "FY").put("digits", "IITEM".equals(key) ? 5 : 4).put("separator", "-");
            JSONObject saved = rows.get(key);
            if (saved != null) { Iterator<String> it = saved.keys(); while (it.hasNext()) { String k = it.next(); if (!saved.isNull(k)) d.put(k, saved.opt(k)); } }
            d.put("label", s[1]);
            out.put(key, d);
        }
        return out;
    }

    JSONObject saveSeries(String key, JSONObject p) throws Exception {
        String sep = p.optString("separator", "-");
        if (sep.isEmpty()) sep = "-";
        if (sep.length() > 2) sep = sep.substring(0, 2);
        int digits = (int) Math.min(Math.max(num(p, "digits") == 0 ? 4 : num(p, "digits"), 3), 8);
        JSONObject data = new JSONObject().put("series_key", key.toUpperCase(Locale.ROOT))
            .put("prefix", c(p, "prefix").isEmpty() ? key.toUpperCase(Locale.ROOT) : c(p, "prefix").toUpperCase(Locale.ROOT))
            .put("include_branch", SndData.truthy(p.opt("include_branch"))).put("include_year", SndData.truthy(p.opt("include_year")))
            .put("year_mode", "CALENDAR".equalsIgnoreCase(c(p, "year_mode")) ? "CALENDAR" : "FY").put("digits", digits).put("separator", sep);
        return api.upsertBy("indirect_number_series", data, "series_key");
    }

    // ================================================================== requisitions
    List<JSONObject> requisitions() throws Exception { return memoRows("reqs", "indirect_purchase_requisitions?select=*&order=created_at.desc&limit=3000"); }

    JSONObject requisition(String id) throws Exception {
        for (JSONObject r : requisitions()) if (s(r, "id").equals(id)) return r;
        return one("indirect_purchase_requisitions", id);
    }

    List<JSONObject> requisitionItems(String prId) {
        if (prId == null || prId.isEmpty()) return new ArrayList<>();
        return select("indirect_purchase_requisition_items?select=*&requisition_id=eq." + Api.enc(prId) + "&order=line_no.asc&limit=500");
    }

    JSONObject createRequisition(JSONObject h, List<JSONObject> lines) throws Exception {
        List<JSONObject> valid = new ArrayList<>();
        for (JSONObject l : lines)
            if (num(l, "quantity") > 0 && (!c(l, "item_id").isEmpty() || !c(l, "description").isEmpty() || !c(l, "item_name").isEmpty())) valid.add(l);
        if (valid.isEmpty()) throw new SupSvc.Rule("Add at least one requisition line with a quantity.");
        if (c(h, "department").isEmpty()) throw new SupSvc.Rule("Department is required.");
        String number = nextNumber("IPR", c(h, "company_branch_id"));
        JSONObject pr = api.insert("indirect_purchase_requisitions", new JSONObject().put("pr_number", number)
            .put("pr_date", c(h, "pr_date").isEmpty() ? LocalDate.now().toString() : d10(h.opt("pr_date"))).put("company_branch_id", nul(c(h, "company_branch_id")))
            .put("department", c(h, "department")).put("cost_centre", nul(c(h, "cost_centre"))).put("requested_by_employee_id", nul(c(h, "requested_by_employee_id")))
            .put("requested_by_name", nul(c(h, "requested_by_name"))).put("required_date", nul(d10(h.opt("required_date")))).put("purpose", nul(c(h, "purpose")))
            .put("priority", c(h, "priority").isEmpty() ? "NORMAL" : up(h, "priority")).put("status", "SUBMITTED").put("remarks", nul(c(h, "remarks"))));
        int index = 1;
        for (JSONObject line : valid) {
            JSONObject it = c(line, "item_id").isEmpty() ? new JSONObject() : item(c(line, "item_id"));
            double rate = num(line, "estimated_rate");
            api.insert("indirect_purchase_requisition_items", new JSONObject().put("requisition_id", s(pr, "id")).put("line_no", index++)
                .put("item_id", nul(c(line, "item_id"))).put("item_code", nul(SupSvc.first(c(it, "item_code"), c(line, "item_code"))))
                .put("item_name", SupSvc.first(c(it, "item_name"), c(line, "item_name"), c(line, "description")))
                .put("description", nul(SupSvc.first(c(line, "description"), c(it, "description")))).put("uom", SupSvc.first(c(line, "uom").toUpperCase(Locale.ROOT), c(it, "uom"), "NOS"))
                .put("quantity", num(line, "quantity")).put("estimated_rate", rate != 0 ? (Object) rate : (it.isNull("last_price") || !it.has("last_price") ? JSONObject.NULL : it.opt("last_price")))
                .put("required_date", nul(SupSvc.first(d10(line.opt("required_date")), d10(h.opt("required_date"))))).put("remarks", nul(c(line, "remarks"))));
        }
        invalidate();
        return pr;
    }

    JSONObject decideRequisition(String prId, boolean approve, String remarks, String employeeId) throws Exception {
        JSONObject pr = requisition(prId);
        if (!"SUBMITTED".equals(up(pr, "status"))) throw new SupSvc.Rule("Only a submitted requisition can be approved or rejected.");
        if (!approve && clean(remarks).length() < 3) throw new SupSvc.Rule("Enter the rejection remarks.");
        if (employeeId != null && !employeeId.isEmpty() && employeeId.equals(s(pr, "requested_by_employee_id"))) throw new SupSvc.Rule("Self-approval is not permitted for a requisition.");
        JSONObject row = api.update("indirect_purchase_requisitions", prId, new JSONObject().put("status", approve ? "APPROVED" : "REJECTED")
            .put("approver_employee_id", nul(employeeId)).put("approved_at", nowUtc()).put("approval_remarks", nul(remarks)));
        invalidate();
        return row;
    }

    /** Pre-fill of an Indirect PO from an approved requisition (pending quantities only). */
    JSONObject requisitionPrefill(String prId) throws Exception {
        JSONObject pr = requisition(prId);
        JSONArray lines = new JSONArray();
        for (JSONObject l : requisitionItems(prId)) {
            double pending = num(l, "quantity") - num(l, "ordered_qty");
            if (pending <= 0) continue;
            lines.put(new JSONObject().put("item_id", nul(c(l, "item_id"))).put("item_name", c(l, "item_name")).put("description", nul(c(l, "description")))
                .put("uom", c(l, "uom")).put("quantity", pending).put("rate", num(l, "estimated_rate")).put("requisition_item_id", s(l, "id")));
        }
        return new JSONObject().put("requisition_id", prId).put("department", c(pr, "department")).put("cost_centre", c(pr, "cost_centre"))
            .put("company_branch_id", c(pr, "company_branch_id")).put("delivery_date", d10(pr.opt("required_date"))).put("requisitioner", c(pr, "requested_by_name"))
            .put("requisitioner_employee_id", c(pr, "requested_by_employee_id")).put("lines", lines);
    }

    // ================================================================== purchase orders
    List<JSONObject> purchaseOrders() throws Exception { return memoRows("pos", "indirect_purchase_orders?select=*&order=created_at.desc&limit=5000"); }
    List<JSONObject> allPoItems() throws Exception { return memoRows("po_items", "indirect_purchase_order_items?select=*&order=line_no.asc&limit=50000"); }

    List<JSONObject> poItems(String poId) throws Exception {
        if (poId == null || poId.isEmpty()) return new ArrayList<>();
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject r : allPoItems()) if (poId.equals(s(r, "purchase_order_id"))) rows.add(r);
        if (rows.isEmpty()) rows = select("indirect_purchase_order_items?select=*&purchase_order_id=eq." + Api.enc(poId) + "&order=line_no.asc&limit=500");
        rows.sort((x, y) -> Double.compare(num(x, "line_no"), num(y, "line_no")));
        return rows;
    }

    JSONObject purchaseOrder(String poId) throws Exception {
        if (poId == null || poId.isEmpty()) return new JSONObject();
        JSONObject row = null;
        for (JSONObject r : purchaseOrders()) if (poId.equals(s(r, "id"))) { row = r; break; }
        if (row == null) row = one("indirect_purchase_orders", poId);
        return enrichApprover(row);
    }

    JSONObject enrichApprover(JSONObject row) throws Exception {
        JSONObject item = new JSONObject(row == null ? "{}" : row.toString());
        if (!c(item, "approver_employee_id").isEmpty()) {
            JSONObject emp = employee(c(item, "approver_employee_id"));
            if (emp.length() > 0) {
                item.put("approver_employee_name", employeeName(emp));
                item.put("approver_employee_code", c(emp, "employee_code"));
            }
        }
        return item;
    }

    /** build_po: validate + compute header and lines without writing. Returns {header, items}. */
    JSONObject buildPo(JSONObject p, List<JSONObject> lines) throws Exception {
        JSONObject supplier = party(c(p, "supplier_id"));
        if (supplier.length() == 0) throw new SupSvc.Rule("Select the supplier.");
        JSONObject branch = branch(c(p, "company_branch_id"));
        if (branch.length() == 0 && !branches().isEmpty()) throw new SupSvc.Rule("Select the Company Branch / Plant.");
        JSONObject plant = branch.length() > 0 ? SupSvc.branchSnapshot(branch) : new JSONObject();
        List<JSONObject> valid = new ArrayList<>();
        for (JSONObject line : lines) {
            if (num(line, "quantity") <= 0 && c(line, "item_id").isEmpty() && c(line, "description").isEmpty()) continue;
            JSONObject it = c(line, "item_id").isEmpty() ? new JSONObject() : item(c(line, "item_id"));
            String name = SupSvc.first(c(line, "item_name"), c(it, "item_name"), c(line, "description"));
            int n = valid.size() + 1;
            if (name.isEmpty()) throw new SupSvc.Rule("Line " + n + ": select an item or enter a description.");
            if (num(line, "quantity") <= 0) throw new SupSvc.Rule("Line " + n + " (" + name + "): quantity must be more than zero.");
            if (num(line, "rate") < 0) throw new SupSvc.Rule("Line " + n + " (" + name + "): rate cannot be negative.");
            if (num(line, "discount_percent") < 0 || num(line, "discount_percent") > 100) throw new SupSvc.Rule("Line " + n + " (" + name + "): discount % must be 0–100.");
            valid.add(new JSONObject().put("item_id", nul(c(line, "item_id"))).put("item_code", nul(SupSvc.first(c(line, "item_code"), c(it, "item_code"))))
                .put("item_name", name).put("description", nul(SupSvc.first(c(line, "description"), c(it, "description"))))
                .put("category", nul(SupSvc.first(c(line, "category"), c(it, "category")))).put("hsn_sac", nul(SupSvc.first(c(line, "hsn_sac"), c(it, "hsn_sac"))))
                .put("uom", SupSvc.first(c(line, "uom").toUpperCase(Locale.ROOT), c(it, "uom").toUpperCase(Locale.ROOT), "NOS"))
                .put("quantity", num(line, "quantity")).put("rate", num(line, "rate")).put("discount_percent", num(line, "discount_percent"))
                .put("gst_percent", c(line, "gst_percent").isEmpty() ? num(it, "gst_percent") : num(line, "gst_percent"))
                .put("required_date", nul(d10(line.opt("required_date")))).put("requisition_item_id", nul(c(line, "requisition_item_id"))).put("remarks", nul(c(line, "remarks"))));
        }
        if (valid.isEmpty()) throw new SupSvc.Rule("Add at least one PO line.");
        String mode = c(p, "gst_mode").isEmpty() ? gstMode(supplier, plant) : up(p, "gst_mode");
        String currency = c(p, "currency").isEmpty() ? "INR" : up(p, "currency");
        boolean roundRupee = !p.has("round_to_rupee") || SndData.truthy(p.opt("round_to_rupee"));
        JSONObject totals = computeTotals(valid, mode, num(p, "freight_amount"), num(p, "other_amount"), roundRupee, currency);
        String shipSource = c(p, "ship_to_source_type").isEmpty() ? "BRANCH" : up(p, "ship_to_source_type");
        JSONObject shipSnap;
        if ("BRANCH".equals(shipSource)) {
            JSONObject sb = branch(SupSvc.first(c(p, "ship_to_branch_id"), c(p, "company_branch_id")));
            shipSnap = sb.length() > 0 ? SupSvc.branchSnapshot(sb) : plant;
        } else shipSnap = partySnapshot(party(c(p, "ship_to_party_id")));
        String poDate = c(p, "po_date").isEmpty() ? LocalDate.now().toString() : d10(p.opt("po_date"));
        String delivery = d10(p.opt("delivery_date"));
        if (!delivery.isEmpty() && delivery.compareTo(poDate) < 0) throw new SupSvc.Rule("Delivery date cannot be before the PO date.");
        JSONObject printOptions = new JSONObject();
        JSONObject po = p.optJSONObject("print_options");
        if (po != null) { Iterator<String> it = po.keys(); while (it.hasNext()) { String k = it.next(); if (k.startsWith("show_")) printOptions.put(k, SndData.truthy(po.opt(k))); } }
        JSONObject header = new JSONObject().put("po_date", poDate).put("company_branch_id", nul(c(p, "company_branch_id"))).put("plant_snapshot", plant)
            .put("supplier_id", s(supplier, "id")).put("vendor_snapshot", partySnapshot(supplier)).put("ship_to_source_type", shipSource)
            .put("ship_to_branch_id", "BRANCH".equals(shipSource) ? nul(SupSvc.first(c(p, "ship_to_branch_id"), c(p, "company_branch_id"))) : JSONObject.NULL)
            .put("ship_to_party_id", "BRANCH".equals(shipSource) ? JSONObject.NULL : nul(c(p, "ship_to_party_id"))).put("ship_to_snapshot", shipSnap)
            .put("department", nul(c(p, "department"))).put("cost_centre", nul(c(p, "cost_centre"))).put("requisitioner", nul(c(p, "requisitioner")))
            .put("requisitioner_employee_id", nul(c(p, "requisitioner_employee_id"))).put("requisition_id", nul(c(p, "requisition_id")))
            .put("delivery_date", nul(delivery)).put("payment_term", nul(c(p, "payment_term"))).put("incoterm", nul(c(p, "incoterm"))).put("ship_via", nul(c(p, "ship_via")))
            .put("quotation_reference", nul(c(p, "quotation_reference"))).put("quotation_date", nul(d10(p.opt("quotation_date")))).put("currency", currency)
            .put("gst_mode", totals.getString("gst_mode"));
        for (String k : new String[]{"gross_amount", "discount_amount", "subtotal", "cgst_amount", "sgst_amount", "igst_amount", "freight_amount", "other_amount", "round_off", "grand_total", "amount_in_words"})
            header.put(k, totals.get(k));
        String terms = p.isNull("terms") ? "" : p.optString("terms", "").trim();
        String instr = p.isNull("special_instructions") ? "" : p.optString("special_instructions", "").trim();
        header.put("terms", nul(terms)).put("special_instructions", nul(instr)).put("remarks", nul(c(p, "remarks"))).put("print_options", printOptions)
            .put("over_receipt_tolerance_percent", Math.min(Math.max(num(p, "over_receipt_tolerance_percent"), 0), 50));
        JSONArray items = new JSONArray();
        JSONArray computed = totals.getJSONArray("lines");
        String[] keys = {"item_id", "item_code", "item_name", "description", "category", "hsn_sac", "uom", "quantity", "rate", "discount_percent", "discount_amount",
            "taxable_amount", "gst_percent", "gst_amount", "cgst_amount", "sgst_amount", "igst_amount", "line_total", "required_date", "requisition_item_id", "remarks"};
        for (int i = 0; i < computed.length(); i++) {
            JSONObject l = computed.getJSONObject(i);
            JSONObject o = new JSONObject();
            for (String k : keys) o.put(k, l.has(k) ? l.opt(k) : JSONObject.NULL);
            o.put("line_no", i + 1);
            items.put(o);
        }
        return new JSONObject().put("header", header).put("items", items);
    }

    JSONObject previewPo(JSONObject p, List<JSONObject> lines) throws Exception {
        JSONObject built = buildPo(p, lines);
        JSONObject h = built.getJSONObject("header");
        JSONObject b = branch(c(h, "company_branch_id"));
        h.put("po_number", previewNumber("IPO", SupSvc.first(c(b, "plant_code"), c(b, "branch_code")))).put("status", "DRAFT").put("approval_status", "DRAFT");
        return built;
    }

    private void insertLines(String poId, JSONArray items) throws Exception {
        for (int i = 0; i < items.length(); i++) {
            JSONObject o = new JSONObject(items.getJSONObject(i).toString());
            o.put("purchase_order_id", poId);
            api.insert("indirect_purchase_order_items", o);
        }
    }

    JSONObject createPo(JSONObject p, List<JSONObject> lines, boolean submit, String submittedBy) throws Exception {
        JSONObject built = buildPo(p, lines);
        JSONObject h = built.getJSONObject("header");
        JSONArray items = built.getJSONArray("items");
        if (submit && (submittedBy == null || submittedBy.isEmpty()))
            throw new SupSvc.Rule("Your login must be linked to an ACTIVE Employee Master record to submit an Indirect PO for approval.");
        h.put("po_number", nextNumber("IPO", c(h, "company_branch_id")));
        String status = submit ? "PENDING_APPROVAL" : "DRAFT";
        h.put("status", status).put("approval_status", status).put("approval_level", JSONObject.NULL).put("submitted_by_employee_id", nul(submittedBy))
            .put("submitted_at", submit ? nowUtc() : JSONObject.NULL);
        JSONObject po = api.insert("indirect_purchase_orders", h);
        try {
            insertLines(s(po, "id"), items);
        } catch (Exception e) {
            try {
                api.update("indirect_purchase_orders", s(po, "id"), new JSONObject().put("status", "CANCELLED").put("approval_status", "CANCELLED")
                    .put("cancellation_reason", "Auto-cancelled: PO lines could not be saved"));
            } catch (Exception ignored) { }
            throw e;
        }
        markRequisition(c(h, "requisition_id"), s(po, "id"), items);
        invalidate();
        return po;
    }

    private void markRequisition(String prId, String poId, JSONArray items) {
        if (prId == null || prId.isEmpty()) return;
        try {
            Map<String, Double> ordered = new HashMap<>();
            for (int i = 0; i < items.length(); i++) {
                JSONObject it = items.getJSONObject(i);
                if (!c(it, "requisition_item_id").isEmpty()) ordered.merge(c(it, "requisition_item_id"), num(it, "quantity"), Double::sum);
            }
            List<JSONObject> prLines = requisitionItems(prId);
            boolean fully = true;
            for (JSONObject l : prLines) {
                double add = ordered.getOrDefault(s(l, "id"), 0.0);
                if (ordered.containsKey(s(l, "id"))) api.update("indirect_purchase_requisition_items", s(l, "id"), new JSONObject().put("ordered_qty", num(l, "ordered_qty") + add));
                if (num(l, "ordered_qty") + add + 0.0005 < num(l, "quantity")) fully = false;
            }
            api.update("indirect_purchase_requisitions", prId, new JSONObject().put("status", fully ? "CONVERTED" : "PARTIALLY_ORDERED").put("converted_po_id", poId));
        } catch (Exception ignored) { }
    }

    boolean hasReceipts(String poId) throws Exception {
        for (JSONObject i : poItems(poId)) if (num(i, "received_qty") > 0) return true;
        for (JSONObject g : grns()) if (poId.equals(s(g, "purchase_order_id")) && ("POSTED".equals(up(g, "status")) || "DRAFT".equals(up(g, "status")))) return true;
        return false;
    }

    JSONObject updatePo(String poId, JSONObject p, List<JSONObject> lines, boolean submit, String submittedBy) throws Exception {
        JSONObject current = purchaseOrder(poId);
        String status = up(current, "status");
        if (!EDITABLE_PO_STATUSES.contains(status)) throw new SupSvc.Rule("An Indirect PO in status " + statusLabel(status) + " cannot be edited.");
        if (hasReceipts(poId)) throw new SupSvc.Rule("Material has already been received against this PO; it cannot be revised. Cancel the balance and raise a new PO.");
        if (submit && (submittedBy == null || submittedBy.isEmpty()))
            throw new SupSvc.Rule("Your login must be linked to an ACTIVE Employee Master record to submit an Indirect PO for approval.");
        JSONObject built = buildPo(p, lines);
        JSONObject h = built.getJSONObject("header");
        String newStatus = submit ? "PENDING_APPROVAL" : "DRAFT";
        h.put("status", newStatus).put("approval_status", newStatus).put("approval_level", JSONObject.NULL)
            .put("submitted_by_employee_id", nul(SupSvc.first(submittedBy, c(current, "submitted_by_employee_id"))))
            .put("submitted_at", submit ? nowUtc() : (current.isNull("submitted_at") ? JSONObject.NULL : current.opt("submitted_at")))
            .put("revision_no", (int) num(current, "revision_no") + ("APPROVED".equals(status) ? 1 : 0));
        h.remove("requisition_id");
        JSONObject row = api.update("indirect_purchase_orders", poId, h);
        for (JSONObject old : poItems(poId)) api.delete("indirect_purchase_order_items", s(old, "id"));
        insertLines(poId, built.getJSONArray("items"));
        invalidate();
        return row;
    }

    JSONObject submitPo(String poId, String employeeId) throws Exception {
        JSONObject current = purchaseOrder(poId);
        String st = up(current, "status");
        if (!"DRAFT".equals(st) && !"REJECTED".equals(st)) throw new SupSvc.Rule("Only a Draft or Rejected Indirect PO can be submitted.");
        if (employeeId == null || employeeId.isEmpty()) throw new SupSvc.Rule("Your login must be linked to an ACTIVE Employee Master record.");
        JSONObject row = api.update("indirect_purchase_orders", poId, new JSONObject().put("status", "PENDING_APPROVAL").put("approval_status", "PENDING_APPROVAL")
            .put("approval_level", JSONObject.NULL).put("submitted_by_employee_id", employeeId).put("submitted_at", nowUtc()));
        invalidate();
        return row;
    }

    JSONObject cancelPo(String poId, String reason, String employeeId) throws Exception {
        JSONObject current = purchaseOrder(poId);
        String st = up(current, "status");
        if ("CLOSED".equals(st) || "CANCELLED".equals(st)) throw new SupSvc.Rule("This Indirect PO is already closed / cancelled.");
        if (clean(reason).length() < 3) throw new SupSvc.Rule("Enter the cancellation reason.");
        for (JSONObject i : poItems(poId)) if (num(i, "received_qty") > 0)
            throw new SupSvc.Rule("Material has been received against this PO; it cannot be cancelled. Short-close is recorded by a final GRN.");
        JSONObject row = api.update("indirect_purchase_orders", poId, new JSONObject().put("status", "CANCELLED").put("approval_status", "CANCELLED")
            .put("cancellation_reason", clean(reason)).put("cancelled_by_employee_id", nul(employeeId)).put("cancelled_at", nowUtc()));
        invalidate();
        return row;
    }

    // ================================================================== approval
    JSONObject approvalTarget(String poId) throws Exception {
        try {
            JSONObject r = api.rpcObject("qcms_indirect_po_approval_target", new JSONObject().put("p_po_id", poId));
            if (r.length() > 0) return r;
        } catch (Exception ignored) { }
        JSONObject po = purchaseOrder(poId);
        JSONObject submitter = employee(c(po, "submitted_by_employee_id"));
        String dept = SupSvc.first(c(po, "department"), c(submitter, "department")).toLowerCase(Locale.ROOT);
        List<JSONObject> routes = new ArrayList<>();
        for (JSONObject r : approvalRoutes()) {
            boolean required = !r.has("required") || r.isNull("required") || SndData.truthy(r.opt("required"));
            if (required && !c(r, "employee_id").isEmpty() && num(r, "min_amount") <= num(po, "grand_total")
                && (c(r, "department").isEmpty() || c(r, "department").equalsIgnoreCase(dept))) routes.add(r);
        }
        TreeSet<Integer> levels = new TreeSet<>();
        for (JSONObject r : routes) levels.add(num(r, "level_no") == 0 ? 1 : (int) num(r, "level_no"));
        if (!levels.isEmpty()) {
            Integer level = levels.ceiling((int) num(po, "approval_level"));
            if (level == null) level = levels.last();
            JSONObject route = null;
            for (JSONObject r : routes) {
                int l = num(r, "level_no") == 0 ? 1 : (int) num(r, "level_no");
                if (l != level) continue;
                if (route == null || (c(route, "department").isEmpty() && !c(r, "department").isEmpty())) route = r;
            }
            JSONObject emp = employee(c(route, "employee_id"));
            return new JSONObject().put("source", "CONFIGURED_ROUTE").put("employee_id", c(emp, "id")).put("employee_name", employeeName(emp)).put("email", c(emp, "email"))
                .put("level_no", level).put("level_name", SupSvc.first(c(route, "level_name"), "Level " + level + " Approval")).put("levels", new JSONArray(levels));
        }
        JSONObject manager = employee(c(submitter, "reports_to_employee_id"));
        if (manager.length() > 0)
            return new JSONObject().put("source", "REPORTS_TO").put("employee_id", c(manager, "id")).put("employee_name", employeeName(manager)).put("email", c(manager, "email"))
                .put("level_no", 1).put("level_name", "Reports-To Manager Approval").put("levels", new JSONArray().put(1));
        return new JSONObject().put("source", "PERMISSION_FALLBACK").put("employee_id", JSONObject.NULL).put("employee_name", JSONObject.NULL).put("email", JSONObject.NULL)
            .put("level_no", 1).put("level_name", "Any different employee with Indirect Purchase Approve permission").put("levels", new JSONArray().put(1));
    }

    JSONObject approvePo(String poId, String remarks) throws Exception {
        JSONObject r = api.rpcObject("qcms_approve_indirect_po", new JSONObject().put("p_po_id", poId).put("p_remarks", nul(remarks)));
        invalidate();
        return enrichApprover(r);
    }

    JSONObject rejectPo(String poId, String remarks) throws Exception {
        if (clean(remarks).length() < 3) throw new SupSvc.Rule("Enter the rejection remarks.");
        JSONObject r = api.rpcObject("qcms_reject_indirect_po", new JSONObject().put("p_po_id", poId).put("p_remarks", clean(remarks)));
        invalidate();
        return r;
    }

    List<JSONObject> approvalLog(String poId) {
        return select("indirect_po_approval_log?select=*&purchase_order_id=eq." + Api.enc(poId) + "&order=created_at.asc&limit=200");
    }

    List<JSONObject> approvalRoutes() throws Exception {
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject r : memoRows("routes", "qcms_module_approval_routes?select=*&module_key=eq." + MODULE_KEY + "&order=level_no.asc&limit=200"))
            if (c(r, "status").isEmpty() || "ACTIVE".equals(up(r, "status"))) out.add(r);
        return out;
    }

    JSONObject saveRoute(int levelNo, String employeeId, String levelName, String department, double minAmount, int overdueHours) throws Exception {
        if (levelNo < 1 || levelNo > 3) throw new SupSvc.Rule("Approval level must be 1, 2 or 3.");
        if (employeeId == null || employeeId.isEmpty()) throw new SupSvc.Rule("Select the approver employee.");
        Object dept = nul(department);
        JSONObject p = new JSONObject().put("module_key", MODULE_KEY).put("department", dept).put("level_no", levelNo)
            .put("level_name", clean(levelName).isEmpty() ? "Level " + levelNo + " Approval" : clean(levelName)).put("employee_id", employeeId).put("required", true)
            .put("status", "ACTIVE").put("min_amount", Math.max(minAmount, 0)).put("overdue_after_hours", Math.min(Math.max(overdueHours == 0 ? 24 : overdueHours, 1), 720));
        JSONObject row = api.upsertBy("qcms_module_approval_routes", p, "module_key", "department", "level_no");
        invalidate();
        return row;
    }

    JSONObject deactivateRoute(String id) throws Exception {
        JSONObject r = api.update("qcms_module_approval_routes", id, new JSONObject().put("status", "INACTIVE"));
        invalidate();
        return r;
    }

    // ================================================================== registers
    static String supplierName(JSONObject po) {
        JSONObject v = po.optJSONObject("vendor_snapshot");
        return v == null ? "" : c(v, "party_name");
    }

    List<JSONObject> poRegisterRows() throws Exception {
        Map<String, List<JSONObject>> byPo = new HashMap<>();
        for (JSONObject it : allPoItems()) byPo.computeIfAbsent(s(it, "purchase_order_id"), k -> new ArrayList<>()).add(it);
        Map<String, String> names = new HashMap<>();
        for (JSONObject p : parties()) names.put(s(p, "id"), c(p, "party_name"));
        Map<String, String> codes = new HashMap<>();
        for (JSONObject b : branches()) codes.put(s(b, "id"), SupSvc.first(c(b, "plant_code"), c(b, "branch_code")));
        String today = LocalDate.now().toString();
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject po : purchaseOrders()) {
            List<JSONObject> items = byPo.getOrDefault(s(po, "id"), new ArrayList<>());
            double ordered = 0, accepted = 0;
            List<String> names3 = new ArrayList<>();
            for (int i = 0; i < items.size(); i++) {
                ordered += num(items.get(i), "quantity"); accepted += num(items.get(i), "accepted_qty");
                if (i < 3) names3.add(c(items.get(i), "item_name"));
            }
            String status = up(po, "status");
            String delivery = d10(po.opt("delivery_date"));
            boolean overdue = OPEN_PO_STATUSES.contains(status) && (delivery.isEmpty() ? "9999" : delivery).compareTo(today) < 0;
            rows.add(new JSONObject().put("IPO Number", c(po, "po_number")).put("PO Date", d10(po.opt("po_date")))
                .put("Branch", codes.getOrDefault(s(po, "company_branch_id"), "-")).put("Supplier", SupSvc.first(supplierName(po), names.get(s(po, "supplier_id")), "-"))
                .put("Department", SupSvc.first(c(po, "department"), "-")).put("Cost Centre", SupSvc.first(c(po, "cost_centre"), "-"))
                .put("Items", String.join(", ", names3) + (items.size() > 3 ? " +" + (items.size() - 3) : "")).put("Lines", items.size())
                .put("Grand Total", num(po, "grand_total")).put("Currency", SupSvc.first(c(po, "currency"), "INR")).put("Delivery Date", delivery)
                .put("Received %", ordered > 0 ? Math.round(1000.0 * accepted / ordered) / 10.0 : 0.0).put("Status", status)
                .put("Approval Status", up(po, "approval_status")).put("Delivery", overdue ? "OVERDUE" : "").put("Requisitioner", SupSvc.first(c(po, "requisitioner"), "-"))
                .put("_id", s(po, "id")));
        }
        return rows;
    }

    List<JSONObject> pendingApprovalRows() throws Exception {
        List<JSONObject> rows = new ArrayList<>();
        OffsetDateTime now = OffsetDateTime.now(ZoneOffset.UTC);
        for (JSONObject po : purchaseOrders()) {
            if (!"PENDING_APPROVAL".equals(up(po, "approval_status"))) continue;
            JSONObject target = approvalTarget(s(po, "id"));
            long days = 0;
            try {
                OffsetDateTime submitted = OffsetDateTime.parse(SupSvc.first(c(po, "submitted_at"), c(po, "created_at")).replace(" ", "T"));
                days = Math.max(0, ChronoUnit.DAYS.between(submitted, now));
            } catch (Exception ignored) { }
            rows.add(new JSONObject().put("IPO Number", c(po, "po_number")).put("PO Date", d10(po.opt("po_date"))).put("Supplier", SupSvc.first(supplierName(po), "-"))
                .put("Department", SupSvc.first(c(po, "department"), "-")).put("Grand Total", num(po, "grand_total")).put("Requisitioner", SupSvc.first(c(po, "requisitioner"), "-"))
                .put("Approver", SupSvc.first(c(target, "employee_name"), "ANY APPROVER")).put("Approver Email", SupSvc.first(c(target, "email"), "-"))
                .put("Approval Level", SupSvc.first(c(target, "level_name"), "-")).put("Pending Days", days).put("Status", "PENDING_APPROVAL")
                .put("_id", s(po, "id")).put("_approver_id", c(target, "employee_id")));
        }
        return rows;
    }

    List<JSONObject> openPosForGrn() throws Exception {
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject po : purchaseOrders()) if ("APPROVED".equals(up(po, "approval_status")) && OPEN_PO_STATUSES.contains(up(po, "status"))) out.add(po);
        return out;
    }

    List<JSONObject> poPendingLines(String poId) throws Exception {
        double tol = num(purchaseOrder(poId), "over_receipt_tolerance_percent");
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject it : poItems(poId)) {
            JSONObject line = new JSONObject(it.toString());
            line.remove("received_qty"); line.remove("accepted_qty"); line.remove("rejected_qty");
            double pending = r4(num(it, "quantity") - num(it, "accepted_qty"));
            line.put("po_received_qty", num(it, "received_qty")).put("po_accepted_qty", num(it, "accepted_qty")).put("po_rejected_qty", num(it, "rejected_qty"))
                .put("pending_qty", Math.max(pending, 0)).put("tolerance_percent", tol)
                .put("max_receivable_qty", receivableQty(num(it, "quantity"), num(it, "accepted_qty"), tol));
            rows.add(line);
        }
        return rows;
    }

    // ================================================================== GRN
    List<JSONObject> grns() throws Exception { return memoRows("grns", "indirect_grns?select=*&order=created_at.desc&limit=5000"); }

    JSONObject grn(String id) throws Exception {
        for (JSONObject g : grns()) if (s(g, "id").equals(id)) return g;
        return one("indirect_grns", id);
    }

    List<JSONObject> grnItems(String grnId) {
        if (grnId == null || grnId.isEmpty()) return new ArrayList<>();
        return select("indirect_grn_items?select=*&grn_id=eq." + Api.enc(grnId) + "&order=line_no.asc&limit=500");
    }

    static String g(double v) { return SupSvc.g(v); }

    static List<JSONObject> validateGrnLines(List<JSONObject> lines, boolean againstPo) throws Exception {
        List<JSONObject> valid = new ArrayList<>();
        for (JSONObject raw : lines) {
            JSONObject line = new JSONObject(raw.toString());
            double received = num(line, "received_qty");
            if (received <= 0) continue;
            double accepted = c(line, "accepted_qty").isEmpty() ? received : num(line, "accepted_qty");
            double rejected = c(line, "rejected_qty").isEmpty() ? Math.max(received - accepted, 0) : num(line, "rejected_qty");
            String label = SupSvc.first(c(line, "item_code"), c(line, "item_name"), "line " + (valid.size() + 1));
            if (accepted < 0 || rejected < 0) throw new SupSvc.Rule(label + ": accepted / rejected cannot be negative.");
            if (Math.abs(accepted + rejected - received) > 0.0005)
                throw new SupSvc.Rule(label + ": accepted (" + g(accepted) + ") + rejected (" + g(rejected) + ") must equal received (" + g(received) + ").");
            if (rejected > 0 && c(line, "rejection_reason").isEmpty()) throw new SupSvc.Rule(label + ": enter the rejection reason.");
            if (againstPo) {
                double pending = num(line, "pending_qty");
                if (!c(line, "max_receivable_qty").isEmpty()) {
                    double limit = num(line, "max_receivable_qty");
                    if (received > limit + 0.0005)
                        throw new SupSvc.Rule(label + ": received " + g(received) + " exceeds the receivable balance " + g(limit) + " (pending " + g(pending)
                            + " + over-receipt tolerance " + g(num(line, "tolerance_percent")) + "%).");
                } else if (!c(line, "pending_qty").isEmpty() && received > pending + 0.0005)
                    throw new SupSvc.Rule(label + ": received " + g(received) + " exceeds the pending PO quantity " + g(pending) + ".");
            } else if (c(line, "item_id").isEmpty() && c(line, "item_name").isEmpty())
                throw new SupSvc.Rule("Select an item (or enter a description) for every received line.");
            line.put("received_qty", received).put("accepted_qty", accepted).put("rejected_qty", rejected);
            valid.add(line);
        }
        if (valid.isEmpty()) throw new SupSvc.Rule("Enter a received quantity on at least one line.");
        return valid;
    }

    JSONObject createGrn(JSONObject h, List<JSONObject> lines) throws Exception {
        boolean againstPo = !"WITHOUT_PO".equals(c(h, "grn_type").isEmpty() ? "AGAINST_PO" : up(h, "grn_type"));
        JSONObject po = againstPo ? purchaseOrder(c(h, "purchase_order_id")) : new JSONObject();
        if (againstPo && po.length() == 0) throw new SupSvc.Rule("Select the approved Indirect PO.");
        if (againstPo && (!"APPROVED".equals(up(po, "approval_status")) || !OPEN_PO_STATUSES.contains(up(po, "status"))))
            throw new SupSvc.Rule("Indirect PO " + c(po, "po_number") + " is not approved / open for receipt.");
        if (!againstPo && c(h, "supplier_id").isEmpty() && c(h, "supplier_name").isEmpty()) throw new SupSvc.Rule("Enter the supplier / shop name for a GRN without PO.");
        List<JSONObject> valid = validateGrnLines(lines, againstPo);
        String branchId = SupSvc.first(c(h, "company_branch_id"), c(po, "company_branch_id"));
        JSONObject supplier = party(SupSvc.first(c(h, "supplier_id"), c(po, "supplier_id")));
        double subtotal = 0, gst = 0;
        for (JSONObject l : valid) {
            subtotal += num(l, "accepted_qty") * num(l, "rate");
            gst += num(l, "accepted_qty") * num(l, "rate") * num(l, "gst_percent") / 100.0;
        }
        subtotal = r2(subtotal); gst = r2(gst);
        String gate = c(h, "gate_entry_no");
        JSONObject grn = api.insert("indirect_grns", new JSONObject().put("grn_number", nextNumber("IGRN", branchId))
            .put("grn_date", c(h, "grn_date").isEmpty() ? LocalDate.now().toString() : d10(h.opt("grn_date"))).put("grn_type", againstPo ? "AGAINST_PO" : "WITHOUT_PO")
            .put("purchase_order_id", againstPo ? s(po, "id") : JSONObject.NULL).put("company_branch_id", nul(branchId)).put("supplier_id", nul(s(supplier, "id")))
            .put("supplier_name", nul(SupSvc.first(c(supplier, "party_name"), c(h, "supplier_name")))).put("supplier_invoice_no", nul(c(h, "supplier_invoice_no")))
            .put("supplier_invoice_date", nul(d10(h.opt("supplier_invoice_date")))).put("challan_no", nul(c(h, "challan_no"))).put("challan_date", nul(d10(h.opt("challan_date"))))
            .put("vehicle_no", nul(c(h, "vehicle_no").toUpperCase(Locale.ROOT))).put("gate_entry_no", nul(gate)).put("gate_entry_date", gate.isEmpty() ? JSONObject.NULL : nul(d10(h.opt("gate_entry_date"))))
            .put("payment_mode", c(h, "payment_mode").isEmpty() ? (againstPo ? "CREDIT" : "PETTY_CASH") : up(h, "payment_mode"))
            .put("department", nul(SupSvc.first(c(h, "department"), c(po, "department")))).put("cost_centre", nul(SupSvc.first(c(h, "cost_centre"), c(po, "cost_centre"))))
            .put("storage_location", nul(c(h, "storage_location"))).put("received_by_employee_id", nul(c(h, "received_by_employee_id")))
            .put("received_by_name", nul(c(h, "received_by_name"))).put("subtotal", subtotal).put("gst_amount", gst).put("grand_total", r2(subtotal + gst))
            .put("status", "DRAFT").put("approval_status", againstPo ? "NOT_REQUIRED" : "PENDING").put("remarks", nul(c(h, "remarks"))));
        JSONObject result;
        try {
            int index = 1;
            for (JSONObject line : valid) {
                JSONObject it = c(line, "item_id").isEmpty() ? new JSONObject() : item(c(line, "item_id"));
                api.insert("indirect_grn_items", new JSONObject().put("grn_id", s(grn, "id")).put("line_no", index++)
                    .put("po_item_id", againstPo ? nul(SupSvc.first(c(line, "po_item_id"), c(line, "id"))) : JSONObject.NULL)
                    .put("item_id", nul(c(line, "item_id"))).put("item_code", nul(SupSvc.first(c(line, "item_code"), c(it, "item_code"))))
                    .put("item_name", nul(SupSvc.first(c(line, "item_name"), c(it, "item_name")))).put("description", nul(c(line, "description")))
                    .put("uom", nul(SupSvc.first(c(line, "uom"), c(it, "uom")))).put("ordered_qty", againstPo ? (Object) num(line, "quantity") : JSONObject.NULL)
                    .put("received_qty", num(line, "received_qty")).put("accepted_qty", num(line, "accepted_qty")).put("rejected_qty", num(line, "rejected_qty"))
                    .put("rejection_reason", nul(c(line, "rejection_reason"))).put("rate", num(line, "rate")).put("gst_percent", num(line, "gst_percent"))
                    .put("amount", r2(num(line, "accepted_qty") * num(line, "rate")))
                    .put("storage_location", nul(SupSvc.first(c(line, "storage_location"), c(h, "storage_location"), c(it, "storage_location"))))
                    .put("remarks", nul(c(line, "remarks"))));
            }
            result = api.rpcObject("qcms_post_indirect_grn", new JSONObject().put("p_grn_id", s(grn, "id")));
        } catch (Exception e) {
            try { api.update("indirect_grns", s(grn, "id"), new JSONObject().put("status", "CANCELLED").put("remarks", "Auto-cancelled: GRN could not be posted")); } catch (Exception ignored) { }
            invalidate();
            throw e;
        }
        invalidate();
        JSONObject out = new JSONObject(grn.toString());
        Iterator<String> it = result.keys();
        while (it.hasNext()) { String k = it.next(); out.put(k, result.opt(k)); }
        return out;
    }

    JSONObject decideGrn(String grnId, boolean approve, String remarks) throws Exception {
        if (!approve && clean(remarks).length() < 3) throw new SupSvc.Rule("Enter the rejection remarks.");
        JSONObject r = api.rpcObject("qcms_decide_indirect_grn", new JSONObject().put("p_grn_id", grnId).put("p_approve", approve).put("p_remarks", nul(remarks)));
        invalidate();
        return r;
    }

    List<JSONObject> grnRegisterRows() throws Exception {
        Map<String, String> poNumbers = new HashMap<>();
        for (JSONObject p : purchaseOrders()) poNumbers.put(s(p, "id"), c(p, "po_number"));
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject gr : grns()) {
            List<String> inv = new ArrayList<>();
            if (!c(gr, "supplier_invoice_no").isEmpty()) inv.add(c(gr, "supplier_invoice_no"));
            if (!c(gr, "challan_no").isEmpty()) inv.add(c(gr, "challan_no"));
            rows.add(new JSONObject().put("GRN Number", c(gr, "grn_number")).put("GRN Date", d10(gr.opt("grn_date")))
                .put("Type", Ui.pretty(c(gr, "grn_type"))).put("Indirect PO", poNumbers.getOrDefault(s(gr, "purchase_order_id"), "-"))
                .put("Supplier", SupSvc.first(c(gr, "supplier_name"), "-")).put("Invoice / Challan", inv.isEmpty() ? "-" : String.join(" / ", inv))
                .put("Gate Entry", SupSvc.first(c(gr, "gate_entry_no"), "-")).put("Department", SupSvc.first(c(gr, "department"), "-"))
                .put("Value", num(gr, "grand_total")).put("Received By", SupSvc.first(c(gr, "received_by_name"), "-")).put("Status", up(gr, "status")).put("_id", s(gr, "id")));
        }
        return rows;
    }

    // ================================================================== stock
    List<JSONObject> ledger(String itemId, String branchId) {
        StringBuilder q = new StringBuilder("indirect_stock_ledger?select=*&order=created_at.asc&limit=20000");
        if (itemId != null && !itemId.isEmpty()) q.append("&item_id=eq.").append(Api.enc(itemId));
        if (branchId != null && !branchId.isEmpty()) q.append("&company_branch_id=eq.").append(Api.enc(branchId));
        return select(q.toString());
    }

    List<JSONObject> stockRows(String branchId) throws Exception {
        Map<String, Double> balances = new HashMap<>();
        Map<String, String> lastMove = new HashMap<>();
        for (JSONObject r : ledger(null, branchId)) {
            String key = s(r, "item_id");
            balances.merge(key, num(r, "qty_in") - num(r, "qty_out"), Double::sum);
            lastMove.put(key, d10(r.opt("txn_date")));
        }
        Map<String, String> labels = categoryLabels();
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject it : items(false)) {
            if (it.has("is_stock_item") && !it.isNull("is_stock_item") && !SndData.truthy(it.opt("is_stock_item"))) continue;
            String key = s(it, "id");
            double balance = r4(balances.getOrDefault(key, 0.0));
            String alert = "";
            if (!c(it, "reorder_level").isEmpty() && balance <= num(it, "reorder_level")) alert = "REORDER";
            else if (!c(it, "min_stock").isEmpty() && balance < num(it, "min_stock")) alert = "BELOW MIN";
            if (!c(it, "max_stock").isEmpty() && num(it, "max_stock") != 0 && balance > num(it, "max_stock")) alert = "ABOVE MAX";
            rows.add(new JSONObject().put("Item Code", c(it, "item_code")).put("Item Name", c(it, "item_name"))
                .put("Category", labels.getOrDefault(c(it, "category"), c(it, "category"))).put("UOM", c(it, "uom")).put("Balance", balance)
                .put("Last Price", num(it, "last_price")).put("Stock Value", r2(balance * num(it, "last_price"))).put("Reorder Level", c(it, "reorder_level"))
                .put("Min", c(it, "min_stock")).put("Max", c(it, "max_stock")).put("Location", SupSvc.first(c(it, "storage_location"), "-"))
                .put("Last Movement", lastMove.getOrDefault(key, "-")).put("Stock Alert", alert).put("Status", c(it, "status").isEmpty() ? "ACTIVE" : c(it, "status"))
                .put("_id", key));
        }
        return rows;
    }

    JSONObject issueStock(String itemId, double qty, String branchId, String department, String costCentre, String employeeId, String issueDate, String remarks, String txnType) throws Exception {
        String type = txnType == null ? "ISSUE" : txnType.toUpperCase(Locale.ROOT);
        if (itemId == null || itemId.isEmpty()) throw new SupSvc.Rule("Select the item.");
        if ("ISSUE".equals(type) && clean(department).isEmpty()) throw new SupSvc.Rule("Select the department the stock is issued to.");
        if (qty == 0 || (!"ADJUSTMENT".equals(type) && qty < 0)) throw new SupSvc.Rule("Enter a quantity greater than zero.");
        JSONObject r = api.rpcObject("qcms_issue_indirect_stock", new JSONObject().put("p_item_id", itemId).put("p_qty", qty).put("p_company_branch_id", nul(branchId))
            .put("p_department", nul(department)).put("p_cost_centre", nul(costCentre)).put("p_issued_to_employee_id", nul(employeeId))
            .put("p_issue_date", nul(d10(issueDate))).put("p_remarks", nul(remarks)).put("p_txn_type", type));
        invalidate();
        return r;
    }

    // ================================================================== dashboard
    JSONObject dashboard() throws Exception {
        LocalDate today = LocalDate.now();
        String month = today.toString().substring(0, 7);
        List<JSONObject> pos = purchaseOrders();
        Map<String, List<JSONObject>> byPo = new HashMap<>();
        for (JSONObject it : allPoItems()) byPo.computeIfAbsent(s(it, "purchase_order_id"), k -> new ArrayList<>()).add(it);
        Map<String, String> labels = categoryLabels();
        int pending = 0, open = 0, overdue = 0, grnMonth = 0, reqOpen = 0, grnPending = 0;
        double pendingValue = 0, openValue = 0, grnValue = 0;
        JSONArray overdueRows = new JSONArray();
        Map<String, Double> spend = new HashMap<>(), spendSupplier = new HashMap<>();
        for (JSONObject p : pos) {
            if ("PENDING_APPROVAL".equals(up(p, "approval_status"))) { pending++; pendingValue += num(p, "grand_total"); }
            if (OPEN_PO_STATUSES.contains(up(p, "status"))) {
                open++; openValue += num(p, "grand_total");
                String d = d10(p.opt("delivery_date"));
                if (!d.isEmpty() && d.compareTo(today.toString()) < 0) { overdue++; overdueRows.put(p); }
            }
            if ("APPROVED".equals(up(p, "approval_status")) && d10(p.opt("po_date")).startsWith(month)) {
                String sup = SupSvc.first(supplierName(p), "-");
                spendSupplier.merge(sup, num(p, "subtotal"), Double::sum);
                for (JSONObject it : byPo.getOrDefault(s(p, "id"), new ArrayList<>())) {
                    String cat = c(it, "category").isEmpty() ? "OTHERS" : c(it, "category");
                    spend.merge(labels.getOrDefault(cat, cat), num(it, "taxable_amount"), Double::sum);
                }
            }
        }
        for (JSONObject gr : grns()) {
            if ("POSTED".equals(up(gr, "status")) && d10(gr.opt("grn_date")).startsWith(month)) { grnMonth++; grnValue += num(gr, "grand_total"); }
            if ("PENDING_APPROVAL".equals(up(gr, "status"))) grnPending++;
        }
        for (JSONObject r : requisitions()) { String st = up(r, "status"); if (st.equals("SUBMITTED") || st.equals("APPROVED") || st.equals("PARTIALLY_ORDERED")) reqOpen++; }
        double spendMonth = 0;
        for (double v : spend.values()) spendMonth += v;
        return new JSONObject().put("pending_approval", pending).put("pending_value", r2(pendingValue)).put("open", open).put("open_value", r2(openValue))
            .put("overdue", overdue).put("received_month", grnMonth).put("received_month_value", r2(grnValue)).put("spend_month", r2(spendMonth))
            .put("spend_by_category", sortedDesc(spend, 100)).put("spend_by_supplier", sortedDesc(spendSupplier, 10))
            .put("requisitions_open", reqOpen).put("grn_pending_approval", grnPending).put("overdue_rows", overdueRows);
    }

    private static JSONArray sortedDesc(Map<String, Double> m, int max) throws Exception {
        List<Map.Entry<String, Double>> list = new ArrayList<>(m.entrySet());
        list.sort((x, y) -> Double.compare(y.getValue(), x.getValue()));
        JSONArray out = new JSONArray();
        for (int i = 0; i < list.size() && i < max; i++) out.put(new JSONArray().put(list.get(i).getKey()).put(r2(list.get(i).getValue())));
        return out;
    }

    // ================================================================== e-mail text
    /** po_email_text: SUPPLIER (approved PO to the supplier) or APPROVAL (draft to the approver). No customer data. */
    static String[] poEmailText(JSONObject header, String purpose) {
        String number = c(header, "po_number");
        String supplier = SupSvc.first(supplierName(header), "Supplier");
        JSONObject plant = header.optJSONObject("plant_snapshot");
        String company = SupSvc.first(c(plant, "name"), c(plant, "branch_name"), "Four Star Industries");
        String total = SupSvc.first(c(header, "currency"), "INR") + " " + String.format(Locale.US, "%,.2f", num(header, "grand_total"));
        if ("APPROVAL".equals(purpose)) {
            return new String[]{"Approval required · Indirect Purchase Order " + number + " · " + supplier + " · " + total,
                "Dear Approver,\n\nIndirect Purchase Order " + number + " for " + supplier + " (" + total + ") is waiting for your approval.\n"
                    + "Department: " + SupSvc.first(c(header, "department"), "-") + " · Cost centre: " + SupSvc.first(c(header, "cost_centre"), "-") + "\n"
                    + "Requisitioner: " + SupSvc.first(c(header, "requisitioner"), "-") + "\n\nThe draft PO (PENDING APPROVAL watermark) is attached. "
                    + "Approve or reject it in STAWN QCMS → Indirect Purchase → PO Approval.\n\nRegards,\nSTAWN QCMS"};
        }
        return new String[]{"Indirect Purchase Order " + number + " · " + company,
            "Dear " + supplier + ",\n\nPlease find attached our Indirect Purchase Order " + number + " dated " + c(header, "po_date") + " for " + total + ".\n"
                + "Delivery date: " + SupSvc.first(c(header, "delivery_date"), "as agreed") + " · Payment term: " + SupSvc.first(c(header, "payment_term"), "as agreed") + ".\n\n"
                + "Kindly acknowledge the order and quote the PO number on your invoice and delivery challan.\n\n"
                + "Regards,\n" + SupSvc.first(c(header, "requisitioner"), "Purchase Department") + "\n" + company};
    }
}
