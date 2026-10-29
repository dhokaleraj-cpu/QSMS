package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Port of core/supply_chain_service.py (SupplyChainService) and core/raw_source.py for the app.
 * Every method runs on a background thread (network). Business rules, payloads, statuses and
 * messages follow the website exactly.
 */
final class SupSvc {
    /** Same role as Python ValueError: a business rule stopped the action (message for the user). */
    static final class Rule extends Exception { Rule(String m) { super(m); } }

    static final String FSI_RM = "FSI_RM", DIRECT_FORGING = "DIRECT_FORGING", FSI_RM_DIRECT_PRODUCTION = "FSI_RM_DIRECT_PRODUCTION";
    static final String[] FLOWS = {FSI_RM, FSI_RM_DIRECT_PRODUCTION, DIRECT_FORGING};
    static final String[] FLOW_LABELS = {"Flow 1 · FSI RM → Forging → Production", "Flow 3 · FSI RM → Direct Production", "Flow 2 · Direct Forging → Production"};
    static final String[] INHERITED_FIELDS = {"supplier_id", "material_grade_id", "supplier_rm_item_code", "supplier_forging_part_number", "hsn_sac_code",
        "lead_time_days", "forging_weight_kg", "gross_weight_kg", "input_weight_kg", "section_size", "forging_route"};
    static final String DEFAULT_SPECIAL_INSTRUCTIONS = "1. PO number should be mentioned on your Invoice.\n"
        + "2. Material must be packed properly to avoid water damage and free from dent, damages & rust.\n"
        + "3. All QC related reports & TCs to be attached with the Invoices.\n"
        + "4. All reports to be sent to quality@fourstarindustries.com\n"
        + "5. Refer STANDARD PURCHASE ORDER TERMS AND CONDITIONS no FSI/703/F04.";
    static final String[] OPENING_STAGES = {"RAW_MATERIAL", "FORGING", "CASTING", "MACHINING", "OSP_READY", "AT_OSP", "FINAL_INSPECTION", "FINISHED_GOODS"};
    static final String[] OPENING_STAGE_LABELS = {"Raw Material", "Forging", "Casting", "Machining / WIP", "OSP Ready", "At OSP", "Final Inspection", "Finished Goods"};
    static final String[] MONTHS = {"January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"};
    private static final Pattern FLOW_RE = Pattern.compile("\\s*\\[\\[QCMS_SUPPLY_FLOW=(FSI_RM|DIRECT_FORGING|FSI_RM_DIRECT_PRODUCTION)\\]\\]\\s*", Pattern.CASE_INSENSITIVE);

    // totals indexes (supply_chain_service._totals_bulk)
    static final int RM_ORDERED = 0, RM_RECEIVED = 1, RM_DISPATCHED = 2, FORGING_ORDERED = 3, FORGING_RECEIVED = 4, RM_CONSUMED = 5, MACHINED = 6, FINISHED = 7, DISPATCHED = 8;

    final Api api;

    SupSvc(Api api) { this.api = api; }

    // ================================================================== small helpers
    static String s(JSONObject r, String k) { return r == null ? "" : Lookups.j(r, k); }
    static String t(JSONObject r, String k) { return s(r, k).trim(); }
    static String up(JSONObject r, String k) { return t(r, k).toUpperCase(Locale.ROOT); }

    static double num(Object v) {
        if (v == null || v == JSONObject.NULL) return 0;
        if (v instanceof Number) return ((Number) v).doubleValue();
        if (v instanceof Boolean) return (Boolean) v ? 1 : 0;
        String x = String.valueOf(v).trim();
        if (x.isEmpty() || "null".equals(x)) return 0;
        try { return Double.parseDouble(x); } catch (NumberFormatException e) { return 0; }
    }

    static double num(JSONObject r, String k) { return r == null ? 0 : num(r.opt(k)); }

    /** Python `a or b` for numeric master values (0 / null falls through). */
    static double firstNum(JSONObject r1, String k1, JSONObject r2, String k2) {
        double a = num(r1, k1);
        return a != 0 ? a : num(r2, k2);
    }

    static String first(String... values) {
        for (String v : values) if (v != null && !v.isEmpty() && !"null".equals(v)) return v;
        return "";
    }

    static Object n(Object v) {
        if (v == null) return JSONObject.NULL;
        if (v instanceof String && (((String) v).isEmpty())) return JSONObject.NULL;
        return v;
    }

    static Object raw(JSONObject r, String k) {
        if (r == null) return JSONObject.NULL;
        Object v = r.opt(k);
        return v == null ? JSONObject.NULL : v;
    }

    static boolean truthy(JSONObject r, String k, boolean dflt) {
        if (r == null || !r.has(k)) return dflt;
        Object v = r.opt(k);
        if (v == null || v == JSONObject.NULL) return false;
        if (v instanceof Boolean) return (Boolean) v;
        String x = String.valueOf(v);
        return !(x.isEmpty() || "false".equalsIgnoreCase(x) || "0".equals(x));
    }

    static double r3(double v) { return new BigDecimal(Double.toString(v)).setScale(3, RoundingMode.HALF_EVEN).doubleValue(); }
    static double r2(double v) { return new BigDecimal(Double.toString(v)).setScale(2, RoundingMode.HALF_EVEN).doubleValue(); }
    static double r6(double v) { return new BigDecimal(Double.toString(v)).setScale(6, RoundingMode.HALF_EVEN).doubleValue(); }

    /** normalize_match: letters and digits only, case-folded. */
    static String norm(Object v) {
        String x = v == null || v == JSONObject.NULL ? "" : String.valueOf(v);
        if ("null".equals(x)) x = "";
        return x.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]+", "");
    }

    static String d10(String v) { return v == null ? "" : (v.length() > 10 ? v.substring(0, 10) : v); }

    /** parse_business_date (ISO, dd.MM.yyyy, dd-MM-yyyy, dd/MM/yyyy, MM/dd/yyyy). */
    static String parseDate(String v) {
        if (v == null) return null;
        String text = v.trim();
        if (text.isEmpty() || "null".equals(text)) return null;
        String head = d10(text);
        String[] fmts = {"yyyy-MM-dd", "dd.MM.yyyy", "dd-MM-yyyy", "dd/MM/yyyy", "MM/dd/yyyy"};
        for (String f : fmts) {
            try { return LocalDate.parse(head, DateTimeFormatter.ofPattern(f, Locale.ROOT)).toString(); } catch (Exception ignored) { }
        }
        return null;
    }

    static LocalDate monthStart(String v) {
        LocalDate d;
        try { d = LocalDate.parse(d10(v == null || v.isEmpty() ? LocalDate.now().toString() : v)); } catch (Exception e) { d = LocalDate.now(); }
        return LocalDate.of(d.getYear(), d.getMonthValue(), 1);
    }

    static String nowUtc() { return OffsetDateTime.now(ZoneOffset.UTC).toString(); }

    /** Python "{:g}" (6 significant digits, no trailing zeros). */
    static String g(double v) {
        if (v == 0) return "0";
        double a = Math.abs(v);
        if (a >= 1e6 || a < 1e-4) return String.valueOf(v);
        String out = new BigDecimal(v).round(new MathContext(6, RoundingMode.HALF_EVEN)).stripTrailingZeros().toPlainString();
        return out;
    }

    static String fmt(double v, int decimals) { return String.format(Locale.US, "%,." + decimals + "f", v); }

    static JSONObject copy(JSONObject o) throws Exception { return o == null ? new JSONObject() : new JSONObject(o.toString()); }

    static List<JSONObject> list(JSONArray a) {
        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; a != null && i < a.length(); i++) { JSONObject o = a.optJSONObject(i); if (o != null) out.add(o); }
        return out;
    }

    static String flowLabel(String code) {
        for (int i = 0; i < FLOWS.length; i++) if (FLOWS[i].equals(code)) return FLOW_LABELS[i];
        return code;
    }

    static boolean requiresRm(String flow) { return FSI_RM.equals(flow) || FSI_RM_DIRECT_PRODUCTION.equals(flow); }
    static boolean validFlow(String flow) { return FSI_RM.equals(flow) || DIRECT_FORGING.equals(flow) || FSI_RM_DIRECT_PRODUCTION.equals(flow); }

    static String cleanFlowRemarks(String value) {
        String v = value == null || "null".equals(value) ? "" : value;
        return FLOW_RE.matcher(v).replaceAll(" ").trim();
    }

    static String flowRemarks(String value, String flow) {
        String clean = cleanFlowRemarks(value);
        String code = validFlow(flow) ? flow : FSI_RM;
        return (clean + " [[QCMS_SUPPLY_FLOW=" + code + "]]").trim();
    }

    static String flowFor(JSONObject order) {
        String explicit = up(order, "supply_flow");
        if (validFlow(explicit)) return explicit;
        Matcher m = FLOW_RE.matcher(s(order, "remarks"));
        if (m.find()) {
            String code = m.group(1).toUpperCase(Locale.ROOT);
            return validFlow(code) ? code : FSI_RM;
        }
        return FSI_RM;
    }

    static String monthlyReference(String partNumber, int month, int year) throws Rule {
        String part = partNumber == null ? "" : partNumber.trim();
        if (part.isEmpty()) throw new Rule("Part Number is required before generating a monthly schedule reference.");
        return String.format(Locale.ROOT, "%s_%02d_%04d", part, month, year);
    }

    static String partyLabel(JSONObject r) {
        if (r == null) return "";
        String loc = Lookups.join(s(r, "city"), s(r, "state"), s(r, "country")).replace(" · ", ", ");
        return Lookups.join(s(r, "party_code"), s(r, "party_name"), loc);
    }

    static String partLabel(JSONObject r) {
        if (r == null) return "";
        return Lookups.join(s(r, "part_number"), s(r, "fsi_part_number").isEmpty() ? "" : "FSI " + s(r, "fsi_part_number"), s(r, "part_name"));
    }

    /** customer_order_label (R22): Customer PO · Pos · Part · FSI · Ref · Customer · extra [STATUS]. */
    static String orderLabel(JSONObject order, JSONObject part, JSONObject customer, String extra) {
        String poNo = first(t(order, "customer_order_no"), t(order, "master_reference_no"), "-");
        String fsi = t(part, "fsi_part_number");
        String ref = t(order, "master_reference_no");
        String qty = Ui.num(num(order, "order_qty_pcs"), 0) + " pcs";
        String label = Lookups.join("Customer PO " + poNo, "Pos " + first(t(order, "order_position"), "-"), "Part " + first(t(part, "part_number"), "-"),
            fsi.isEmpty() ? "" : "FSI " + fsi, !ref.isEmpty() && !ref.equals(poNo) ? "Ref " + ref : "", t(customer, "party_name"), qty, extra);
        String st = up(order, "status");
        return st.isEmpty() ? label : label + " [" + st + "]";
    }

    // ================================================================== data access
    /** Live read (never from the offline copy) - validations must see the current database. */
    List<JSONObject> live(String path) throws Exception {
        return list(new JSONArray(api.get(path, false).body));
    }

    JSONObject get(String table, String id) throws Exception {
        if (id == null || id.trim().isEmpty() || "null".equals(id)) return new JSONObject();
        List<JSONObject> r = live(table + "?select=*&id=eq." + Api.enc(id.trim()) + "&limit=1");
        return r.isEmpty() ? new JSONObject() : r.get(0);
    }

    static boolean empty(JSONObject o) { return o == null || o.length() == 0; }

    static String inList(Iterable<String> ids) {
        StringBuilder b = new StringBuilder();
        for (String id : ids) { if (id == null || id.isEmpty() || "null".equals(id)) continue; if (b.length() > 0) b.append(','); b.append(id); }
        return b.toString();
    }

    Map<String, JSONObject> byIds(String table, String select, Set<String> ids) throws Exception {
        Map<String, JSONObject> out = new HashMap<>();
        List<String> all = new ArrayList<>();
        for (String id : ids) if (id != null && !id.isEmpty() && !"null".equals(id)) all.add(id);
        for (int i = 0; i < all.size(); i += 80) {
            String in = inList(all.subList(i, Math.min(all.size(), i + 80)));
            for (JSONObject r : live(table + "?select=" + select + "&id=in.(" + in + ")&limit=1000")) out.put(s(r, "id"), r);
        }
        return out;
    }

    // ================================================================== raw source (core/raw_source.py)
    List<JSONObject> currentApprovals(String partId, String supplierId) throws Exception {
        String today = LocalDate.now().toString();
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject r : live("part_supplier_links?select=*&part_id=eq." + Api.enc(partId) + "&approved=eq.true&limit=5000")) {
            if (!(r.opt("approved") instanceof Boolean) || !r.optBoolean("approved")) continue;
            if (supplierId != null && !supplierId.isEmpty() && !supplierId.equals(s(r, "supplier_id"))) continue;
            String from = d10(s(r, "valid_from")), to = d10(s(r, "valid_to"));
            if (!from.isEmpty() && from.compareTo(today) > 0) continue;
            if (!to.isEmpty() && to.compareTo(today) < 0) continue;
            out.add(r);
        }
        return out;
    }

    /** resolve_raw_source: returns {source part, selected raw row}. */
    JSONObject[] resolveRawSource(JSONObject part, JSONObject raw, String supplierId) throws Exception {
        String sourceId = t(raw, "source_part_id");
        if (sourceId.isEmpty()) return new JSONObject[]{copy(part), copy(raw)};
        List<JSONObject> sourceRows = live("parts?select=*&id=eq." + Api.enc(sourceId) + "&limit=1");
        JSONObject source = sourceRows.isEmpty() ? new JSONObject() : sourceRows.get(0);
        String label = first(s(source, "part_number"), sourceId);
        if (empty(source) || !"ACTIVE".equals(s(source, "status"))) throw new Rule("Linked raw part " + label + " must be ACTIVE.");
        if (sourceId.equals(s(part, "id"))) throw new Rule("A raw source cannot link to itself.");
        String kind = t(raw, "material_section_name").toLowerCase(Locale.ROOT);
        if (!kind.equals("forging") && !kind.equals("casting")) throw new Rule("Linked raw sources require Forging or Casting material type.");
        String sid = supplierId != null && !supplierId.isEmpty() ? supplierId : s(raw, "supplier_id");
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject r : live("part_raw_material_details?select=*&part_id=eq." + Api.enc(sourceId) + "&status=eq.ACTIVE&limit=5000")) {
            if (!"ACTIVE".equals(s(r, "status"))) continue;
            if (!sid.isEmpty() && !sid.equals(s(r, "supplier_id"))) continue;
            rows.add(r);
        }
        if (rows.isEmpty()) throw new Rule("Linked raw part " + label + ": add an ACTIVE Section E row for the selected supplier.");
        rows.sort((x, y) -> {
            int c = first(s(y, "updated_at"), s(y, "created_at")).compareTo(first(s(x, "updated_at"), s(x, "created_at")));
            if (c != 0) return c;
            c = s(y, "created_at").compareTo(s(x, "created_at"));
            return c != 0 ? c : s(y, "id").compareTo(s(x, "id"));
        });
        JSONObject selected = copy(rows.get(0));
        if (!s(selected, "source_part_id").isEmpty()) throw new Rule("Linked raw part " + label + " must own its Section E details; nested raw-part links are not supported.");
        List<JSONObject> approvals = currentApprovals(sourceId, s(selected, "supplier_id"));
        if (approvals.isEmpty()) throw new Rule("Linked raw part " + label + ": supplier approval is missing, expired or not yet valid in Section E.");
        selected.put("_supplier_approvals", new JSONArray(approvals));
        return new JSONObject[]{copy(source), selected};
    }

    /** effective_link: inherit values but keep the finished-part link id. */
    JSONObject effectiveLink(JSONObject part, JSONObject raw) throws Exception {
        JSONObject[] res = resolveRawSource(part, raw, null);
        if (t(raw, "source_part_id").isEmpty()) return copy(raw);
        JSONObject out = copy(raw);
        for (String k : INHERITED_FIELDS) out.put(k, raw(res[1], k));
        out.put("_source_raw_id", s(res[1], "id"));
        out.put("_source_part_number", raw(res[0], "part_number"));
        out.put("_supplier_approvals", res[1].optJSONArray("_supplier_approvals") == null ? new JSONArray() : res[1].optJSONArray("_supplier_approvals"));
        return out;
    }

    /** raw_material_options: ACTIVE Section E rows of a Part, linked sources resolved. */
    List<JSONObject> rawMaterialOptions(String partId) throws Exception {
        List<JSONObject> result = new ArrayList<>();
        if (partId == null || partId.isEmpty()) return result;
        JSONObject stub = new JSONObject().put("id", partId);
        for (JSONObject row : live("part_raw_material_details?select=*&part_id=eq." + Api.enc(partId) + "&status=eq.ACTIVE&order=sequence_no.asc&limit=1000")) {
            if (t(row, "source_part_id").isEmpty()) { result.add(row); continue; }
            try {
                result.add(effectiveLink(stub, row));
            } catch (Rule e) {
                JSONObject c = copy(row);
                for (String k : INHERITED_FIELDS) if (!k.equals("supplier_id")) c.put(k, JSONObject.NULL);
                c.put("_source_error", e.getMessage());
                result.add(c);
            }
        }
        return result;
    }

    JSONObject rawMaterialForSupplier(String partId, String supplierId, String preferredId) throws Exception {
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject r : rawMaterialOptions(partId)) {
            if (!supplierId.equals(s(r, "supplier_id"))) continue;
            if (!"ACTIVE".equals(first(s(r, "status"), "ACTIVE"))) continue;
            rows.add(r);
        }
        if (preferredId != null && !preferredId.isEmpty()) for (JSONObject r : rows) if (preferredId.equals(s(r, "id"))) return r;
        return rows.isEmpty() ? null : rows.get(0);
    }

    // ================================================================== prices
    private List<JSONObject> priceRows(String partId, String supplierId) throws Exception {
        List<JSONObject> out = new ArrayList<>();
        if (partId.isEmpty() || supplierId.isEmpty()) return out;
        for (JSONObject r : live("part_supplier_price_history?select=*&part_id=eq." + Api.enc(partId) + "&supplier_id=eq." + Api.enc(supplierId) + "&order=start_date.desc&limit=5000")) {
            String st = first(s(r, "status"), "ACTIVE").toUpperCase(Locale.ROOT);
            if (st.equals("DELETED") || st.equals("CANCELLED")) continue;
            out.add(r);
        }
        return out;
    }

    /** current_price: exact raw detail first, then UOM, latest covering revision. */
    double currentPrice(String partId, String supplierId, String onDate, String uom, String rawId) throws Exception {
        String target = parseDate(onDate);
        if (target == null) target = LocalDate.now().toString();
        List<JSONObject> covering = new ArrayList<>();
        for (JSONObject r : priceRows(partId, supplierId)) {
            String start = d10(s(r, "start_date")), end = d10(s(r, "end_date"));
            if (!start.isEmpty() && start.compareTo(target) <= 0 && (end.isEmpty() || target.compareTo(end) <= 0)) covering.add(r);
        }
        if (covering.isEmpty()) return 0;
        String rid = rawId == null ? "" : rawId.trim();
        if (!rid.isEmpty()) {
            List<JSONObject> exact = new ArrayList<>();
            for (JSONObject r : covering) if (rid.equals(s(r, "raw_material_detail_id"))) exact.add(r);
            if (!exact.isEmpty()) covering = exact;
        }
        String wanted = uom == null ? "" : uom.toUpperCase(Locale.ROOT);
        if (!wanted.isEmpty()) {
            List<JSONObject> exact = new ArrayList<>();
            for (JSONObject r : covering) if (wanted.equals(up(r, "uom"))) exact.add(r);
            if (!exact.isEmpty()) covering = exact;
        }
        covering.sort((x, y) -> { int c = s(y, "start_date").compareTo(s(x, "start_date")); return c != 0 ? c : s(y, "id").compareTo(s(x, "id")); });
        return num(covering.get(0), "price");
    }

    /** same_price_uom (R37b): NOS and PCS are the same count unit for price history. */
    static boolean samePriceUom(String rowUom, String wanted) {
        String a = rowUom == null ? "" : rowUom.trim().toUpperCase(Locale.ROOT), b = wanted == null ? "" : wanted.trim().toUpperCase(Locale.ROOT);
        if (a.equals(b)) return true;
        Set<String> count = new HashSet<>(Arrays.asList("NOS", "PCS", "NO", "PC", "EA"));
        return count.contains(a) && count.contains(b);
    }

    /** price_history (newest start first). */
    List<JSONObject> priceHistory(String partId, String supplierId, String uom, String rawId) throws Exception {
        List<JSONObject> rows = priceRows(partId, supplierId);
        String rid = rawId == null ? "" : rawId.trim();
        if (!rid.isEmpty()) {
            List<JSONObject> exact = new ArrayList<>();
            for (JSONObject r : rows) if (rid.equals(s(r, "raw_material_detail_id"))) exact.add(r);
            if (!exact.isEmpty()) rows = exact;
        }
        if (uom != null && !uom.isEmpty()) {
            List<JSONObject> same = new ArrayList<>();
            for (JSONObject r : rows) if (samePriceUom(s(r, "uom"), uom)) same.add(r);
            if (!same.isEmpty()) rows = same;
        }
        return rows;
    }

    /** price_history_for_po: complete revision history, oldest first. */
    JSONArray priceHistoryForPo(String partId, String supplierId, String uom, String rawId) throws Exception {
        List<JSONObject> all = priceHistory(partId, supplierId, null, rawId);
        List<JSONObject> same = new ArrayList<>();
        for (JSONObject r : all) if (uom == null || uom.isEmpty() || samePriceUom(s(r, "uom"), uom)) same.add(r);
        List<JSONObject> rows = same.isEmpty() ? all : same;
        rows.sort((x, y) -> {
            int c = s(x, "start_date").compareTo(s(y, "start_date"));
            if (c != 0) return c;
            c = first(s(x, "end_date"), "9999-12-31").compareTo(first(s(y, "end_date"), "9999-12-31"));
            return c != 0 ? c : s(x, "id").compareTo(s(y, "id"));
        });
        JSONArray out = new JSONArray();
        for (JSONObject r : rows) {
            JSONObject o = new JSONObject();
            for (String k : new String[]{"start_date", "end_date", "price", "freight", "tool_cost", "packing_forwarding", "profit", "icc_rejection"}) o.put(k, raw(r, k));
            o.put("currency", first(s(r, "currency"), "INR"));
            o.put("uom", first(s(r, "uom"), uom == null ? "" : uom));
            o.put("remarks", s(r, "remarks"));
            o.put("status", first(s(r, "status"), "ACTIVE"));
            o.put("raw_material_detail_id", raw(r, "raw_material_detail_id"));
            out.put(o);
        }
        return out;
    }

    private List<JSONObject> linkedPriceRows(JSONObject part, JSONObject raw, String supplierId, String uom) throws Exception {
        List<JSONObject> rows = live("part_supplier_price_history?select=*&part_id=eq." + Api.enc(s(part, "id")) + "&supplier_id=eq." + Api.enc(supplierId)
            + "&raw_material_detail_id=eq." + Api.enc(s(raw, "id")) + "&limit=5000");
        String u = uom == null ? "" : uom.toUpperCase(Locale.ROOT);
        Set<String> units = u.equals("NOS") || u.equals("PCS") ? new HashSet<>(Arrays.asList("NOS", "PCS")) : new HashSet<>(Collections.singletonList(u));
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject r : rows) if ("ACTIVE".equals(first(s(r, "status"), "ACTIVE").toUpperCase(Locale.ROOT)) && units.contains(up(r, "uom"))) out.add(r);
        out.sort((x, y) -> {
            int c = s(x, "start_date").compareTo(s(y, "start_date"));
            if (c != 0) return c;
            c = first(s(x, "updated_at"), s(x, "created_at")).compareTo(first(s(y, "updated_at"), s(y, "created_at")));
            return c != 0 ? c : s(x, "id").compareTo(s(y, "id"));
        });
        return out;
    }

    double effectiveCurrentPrice(JSONObject part, JSONObject raw, String supplierId, String onDate, String uom) throws Exception {
        JSONObject[] ctx = resolveRawSource(part, raw, supplierId);
        if (!t(raw, "source_part_id").isEmpty()) {
            String target = parseDate(onDate);
            if (target == null) target = LocalDate.now().toString();
            JSONObject last = null;
            for (JSONObject r : linkedPriceRows(ctx[0], ctx[1], supplierId, uom)) {
                String start = d10(s(r, "start_date")), end = d10(s(r, "end_date"));
                if (!start.isEmpty() && start.compareTo(target) <= 0 && (end.isEmpty() || end.compareTo(target) >= 0)) last = r;
            }
            return last == null ? 0 : num(last, "price");
        }
        return currentPrice(s(ctx[0], "id"), supplierId, onDate, uom, s(ctx[1], "id"));
    }

    JSONArray effectivePriceHistory(JSONObject part, JSONObject raw, String supplierId, String poDate, String uom) throws Exception {
        JSONObject[] ctx = resolveRawSource(part, raw, supplierId);
        if (!t(raw, "source_part_id").isEmpty()) {
            JSONArray out = new JSONArray();
            for (JSONObject r : linkedPriceRows(ctx[0], ctx[1], supplierId, uom)) {
                JSONObject o = new JSONObject();
                for (String k : new String[]{"start_date", "end_date", "price", "freight", "tool_cost", "packing_forwarding", "profit", "icc_rejection", "currency", "uom", "remarks", "status", "raw_material_detail_id"}) o.put(k, raw(r, k));
                out.put(o);
            }
            return out;
        }
        return priceHistoryForPo(s(ctx[0], "id"), supplierId, uom, s(ctx[1], "id"));
    }

    static JSONArray head(JSONArray a, int max) {
        if (a.length() <= max) return a;
        JSONArray out = new JSONArray();
        for (int i = 0; i < max; i++) out.put(a.opt(i));
        return out;
    }

    /** _record_purchase_price: keep the controlled price history in step with the PO price. */
    void recordPurchasePrice(String partId, String supplierId, String rawId, String poDate, double price, String uom, String currency, String sourceItemId) throws Exception {
        recordPurchasePrice(partId, supplierId, rawId, poDate, price, uom, currency, sourceItemId, null);
    }

    /**
     * _record_purchase_price (R37b): price revision effective from poDate; also used by PO amendments (poDate = amendment
     * Effective Date, remarks = "PO <no> Amd <n>: <reason>") so later POs pick up the amended price. Returns the written row.
     */
    JSONObject recordPurchasePrice(String partId, String supplierId, String rawId, String poDate, double price, String uom, String currency, String sourceItemId, String remarks) throws Exception {
        price = Math.max(price, 0);
        if (price <= 0) return null;
        String note = remarks == null ? "" : remarks.trim();
        if (note.length() > 500) note = note.substring(0, 500);
        String target = parseDate(poDate);
        if (target == null) target = LocalDate.now().toString();
        List<JSONObject> history = priceHistory(partId, supplierId, uom, rawId);
        for (JSONObject r : history) {
            if (d10(s(r, "start_date")).equals(target)) {
                JSONObject upd = new JSONObject().put("price", price).put("currency", n(currency)).put("raw_material_detail_id", n(rawId)).put("source_purchase_order_item_id", sourceItemId);
                if (!note.isEmpty()) upd.put("remarks", note);
                return api.update("part_supplier_price_history", s(r, "id"), upd);
            }
        }
        JSONObject covering = null;
        for (JSONObject r : history) {
            String start = d10(s(r, "start_date")), end = d10(s(r, "end_date"));
            if (start.compareTo(target) <= 0 && (end.isEmpty() || target.compareTo(end) <= 0)) { covering = r; break; }
        }
        if (covering != null && Math.abs(num(covering, "price") - price) < 0.000001) {
            if (s(covering, "source_purchase_order_item_id").isEmpty()) return api.update("part_supplier_price_history", s(covering, "id"), new JSONObject().put("source_purchase_order_item_id", sourceItemId));
            return covering;
        }
        LocalDate nextStart = null;
        for (JSONObject r : history) {
            String st = d10(s(r, "start_date"));
            if (st.compareTo(target) > 0) {
                LocalDate d = LocalDate.parse(st);
                if (nextStart == null || d.isBefore(nextStart)) nextStart = d;
            }
        }
        Object newEnd = nextStart == null ? JSONObject.NULL : nextStart.minusDays(1).toString();
        if (covering != null) {
            String oldEnd = d10(s(covering, "end_date"));
            api.update("part_supplier_price_history", s(covering, "id"), new JSONObject().put("end_date", LocalDate.parse(target).minusDays(1).toString()));
            newEnd = oldEnd.isEmpty() ? JSONObject.NULL : oldEnd;
        }
        String unit = first(covering == null ? "" : s(covering, "uom"), history.isEmpty() ? "" : s(history.get(0), "uom"), uom, "KGS").toUpperCase(Locale.ROOT);
        JSONObject row = new JSONObject().put("part_id", partId).put("supplier_id", supplierId).put("raw_material_detail_id", n(rawId))
            .put("start_date", target).put("end_date", newEnd).put("price", price).put("currency", first(currency, "INR")).put("uom", unit)
            .put("source_purchase_order_item_id", sourceItemId).put("status", "ACTIVE");
        if (!note.isEmpty()) row.put("remarks", note);
        return api.insert("part_supplier_price_history", row);
    }

    // ================================================================== grouping keys
    String rmGroupKey(JSONObject part, JSONObject raw) {
        String grade = norm(first(s(raw, "material_grade_id"), s(part, "material_grade_id")));
        String type = norm(s(raw, "material_section_name"));
        String size = first(s(raw, "section_size"), s(part, "section_size")).toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9.]", "").replace("mm", "").replace("dia", "").replace("ø", "");
        String common = norm(s(raw, "supplier_rm_item_code"));
        if (!common.isEmpty()) return String.join("|", "COMMON_RM", common, grade, type, norm(s(raw, "section_size")));
        if (!grade.isEmpty() && !size.isEmpty()) return String.join("|", "RM_SECTION", grade, type, size);
        return "PART_RM|" + first(s(part, "id"), "None") + "|" + first(s(raw, "id"), "None");
    }

    String forgingGroupKey(JSONObject part, JSONObject raw) {
        String sourcePart = t(raw, "source_part_id");
        String grade = norm(first(s(raw, "material_grade_id"), s(part, "material_grade_id")));
        if (!sourcePart.isEmpty()) return String.join("|", "SOURCE_PART_FORGING", sourcePart, norm(s(raw, "material_section_name")), grade);
        String common = norm(s(raw, "supplier_forging_part_number"));
        if (!common.isEmpty()) return String.join("|", "COMMON_FORGING", common, grade, norm(first(s(raw, "forging_route"), s(part, "manufacturing_route"))),
            String.format(Locale.ROOT, "%.6f", firstNum(raw, "forging_weight_kg", part, "forging_weight_kg")));
        return "PART_FORGING|" + first(s(part, "id"), "None") + "|" + first(s(raw, "id"), "None");
    }

    /** rm_section_label: grade · RM section · size used to club Customer Orders on one RM PO. */
    String rmSectionLabel(JSONObject part, Map<String, JSONObject> grades) throws Exception {
        List<JSONObject> raws = new ArrayList<>();
        for (JSONObject r : rawMaterialOptions(s(part, "id"))) if ("ACTIVE".equals(first(s(r, "status"), "ACTIVE").toUpperCase(Locale.ROOT))) raws.add(r);
        JSONObject raw = raws.isEmpty() ? new JSONObject() : raws.get(0);
        String gid = first(s(raw, "material_grade_id"), s(part, "material_grade_id"));
        JSONObject grade = gid.isEmpty() ? new JSONObject() : (grades != null && grades.containsKey(gid) ? grades.get(gid) : get("material_grades", gid));
        String label = Lookups.join(first(t(grade, "grade_code"), t(grade, "grade_name")), t(raw, "material_section_name"), first(t(raw, "section_size"), t(part, "section_size")));
        return label.isEmpty() ? "RM section not set" : label;
    }

    // ================================================================== technical data snapshot
    JSONArray technicalDataSnapshot(JSONObject raw, JSONObject part) throws Exception {
        JSONObject[] ctx = resolveRawSource(part, raw, s(raw, "supplier_id"));
        boolean linked = !t(raw, "source_part_id").isEmpty();
        JSONObject sp = ctx[0], sr = ctx[1];
        List<JSONObject> custom = s(sr, "id").isEmpty() ? new ArrayList<>()
            : live("part_raw_material_technical_data?select=*&raw_material_detail_id=eq." + Api.enc(s(sr, "id")) + "&status=eq.ACTIVE&order=sequence_no.asc&limit=500");
        Map<String, JSONObject> customMap = new LinkedHashMap<>();
        for (JSONObject r : custom) {
            if (!truthy(r, "include_on_po", true)) continue;
            String heading = t(r, "heading"), value = t(r, "value_text");
            if (heading.isEmpty() || value.isEmpty()) continue;
            String key = norm(heading);
            if (key.equals(norm("Raw Material Section"))) { key = norm("Raw Material Type"); heading = "Raw Material Type"; }
            customMap.put(key, new JSONObject().put("heading", heading).put("value", value).put("source", "CUSTOM"));
        }
        JSONObject grade = get("material_grades", first(s(sr, "material_grade_id"), s(sp, "material_grade_id")));
        List<String[]> standard = new ArrayList<>();
        standard.add(new String[]{"Raw Material Type", s(sr, "material_section_name")});
        standard.add(new String[]{"Supplier RM Item Code", s(sr, "supplier_rm_item_code")});
        standard.add(new String[]{"Supplier Forging Part No.", s(sr, "supplier_forging_part_number")});
        standard.add(new String[]{"Source Raw Forging / Casting Part", linked ? s(sp, "part_number") : ""});
        standard.add(new String[]{"Material Grade", s(grade, "grade_code")});
        int lead = (int) num(sr, "lead_time_days");
        standard.add(new String[]{"Supplier Lead Time", lead > 0 ? lead + " Days" : ""});
        standard.add(new String[]{"Forge wt", (!sr.isNull("forging_weight_kg") || !sp.isNull("forging_weight_kg")) ? g(firstNum(sr, "forging_weight_kg", sp, "forging_weight_kg")) + " Kgs" : ""});
        standard.add(new String[]{"Gross wt", (!sr.isNull("gross_weight_kg") || !sp.isNull("gross_weight_kg")) ? g(firstNum(sr, "gross_weight_kg", sp, "gross_weight_kg")) + " Kgs" : ""});
        standard.add(new String[]{"Input wt", !sr.isNull("input_weight_kg") ? g(num(sr, "input_weight_kg")) + " kg/part" : ""});
        standard.add(new String[]{"Section Size", first(s(sr, "section_size"), s(sp, "section_size"))});
        standard.add(new String[]{"Forging Route", first(s(sr, "forging_route"), s(sp, "manufacturing_route"))});
        if (linked) {
            standard.add(new String[]{"Source Raw Material Detail ID", s(sr, "id")});
            JSONArray approvals = sr.optJSONArray("_supplier_approvals");
            for (int i = 0; approvals != null && i < approvals.length(); i++) {
                JSONObject ap = approvals.optJSONObject(i);
                standard.add(new String[]{"Supplier Approval", Lookups.join(first(s(ap, "approval_reference"), s(ap, "id")), s(ap, "valid_from"), first(s(ap, "valid_to"), "No expiry"))});
            }
        }
        JSONArray result = new JSONArray();
        Set<String> used = new HashSet<>();
        for (String[] st : standard) {
            String key = norm(st[0]);
            if (customMap.containsKey(key)) { result.put(customMap.get(key)); used.add(key); }
            else if (!st[1].trim().isEmpty()) result.put(new JSONObject().put("heading", st[0]).put("value", st[1].trim()).put("source", "STANDARD"));
        }
        for (JSONObject r : custom) {
            String key = norm(s(r, "heading"));
            if (used.contains(key) || !truthy(r, "include_on_po", true)) continue;
            String heading = t(r, "heading"), value = t(r, "value_text");
            if (!heading.isEmpty() && !value.isEmpty()) { result.put(new JSONObject().put("heading", heading).put("value", value).put("source", "CUSTOM")); used.add(key); }
        }
        return result;
    }

    // ================================================================== snapshots
    static JSONObject branchSnapshot(JSONObject r) throws Exception {
        List<String> parts = new ArrayList<>();
        for (String k : new String[]{"address_line1", "address_line2", "address_line3"}) if (!t(r, k).isEmpty()) parts.add(t(r, k));
        List<String> loc = new ArrayList<>();
        for (String k : new String[]{"city", "state", "postal_code", "country"}) if (!t(r, k).isEmpty()) loc.add(t(r, k));
        String locality = String.join(", ", loc);
        if (!locality.isEmpty()) parts.add(locality);
        String address = String.join(", ", parts);
        JSONObject o = new JSONObject();
        o.put("branch_id", raw(r, "id")); o.put("branch_code", raw(r, "branch_code"));
        o.put("plant_code", n(first(s(r, "plant_code"), s(r, "branch_code"))));
        o.put("name", n(first(s(r, "branch_name"), s(r, "branch_code")))); o.put("branch_name", n(first(s(r, "branch_name"), s(r, "branch_code"))));
        o.put("address1", raw(r, "address_line1")); o.put("address2", raw(r, "address_line2")); o.put("address3", raw(r, "address_line3")); o.put("address", address);
        o.put("city", raw(r, "city")); o.put("state", raw(r, "state")); o.put("postal_code", raw(r, "postal_code")); o.put("country", raw(r, "country"));
        o.put("tax_identifier", raw(r, "gstin")); o.put("gstin", raw(r, "gstin")); o.put("phone", raw(r, "phone")); o.put("email", raw(r, "email")); o.put("contact_person", raw(r, "contact_person"));
        return o;
    }

    static JSONObject partySnapshot(JSONObject r) throws Exception {
        JSONObject o = new JSONObject();
        for (String k : new String[]{"party_code", "party_name", "address", "city", "state", "country", "tax_identifier", "phone", "email", "contact_person"}) o.put(k, raw(r, k));
        return o;
    }

    static Set<String> partyTypes(JSONObject r) {
        Set<String> out = new HashSet<>();
        JSONArray a = r == null ? null : r.optJSONArray("party_types");
        for (int i = 0; a != null && i < a.length(); i++) out.add(a.optString(i).toUpperCase(Locale.ROOT));
        return out;
    }

    static boolean shipToMatches(JSONObject party, String source) {
        Set<String> types = partyTypes(party);
        switch (source) {
            case "CUSTOMER": return types.contains("CUSTOMER");
            case "SUPPLIER": return types.contains("SUPPLIER") || types.contains("STEEL_MILL");
            default: return types.contains("OSP_VENDOR") || types.contains("FORGING_SUPPLIER");
        }
    }

    static String employeeName(JSONObject e) { return (t(e, "first_name") + " " + t(e, "last_name")).trim(); }

    // ================================================================== bulk registers
    /** All Supply Chain stage rows loaded once (website service memo of one page run). */
    static final class Data {
        final List<JSONObject> orders, rmPos, rmReceipts, rmDispatches, forgingOrders, forgingReceipts, downstream, confirmations;
        final Map<String, JSONObject> orderById = new HashMap<>();
        final Map<String, double[]> totals = new HashMap<>();
        final Map<String, String> confirmationByPo = new HashMap<>();

        Data(List<JSONObject> orders, List<JSONObject> rmPos, List<JSONObject> rmReceipts, List<JSONObject> rmDispatches, List<JSONObject> forgingOrders,
             List<JSONObject> forgingReceipts, List<JSONObject> downstream, List<JSONObject> confirmations) {
            this.orders = orders; this.rmPos = rmPos; this.rmReceipts = rmReceipts; this.rmDispatches = rmDispatches; this.forgingOrders = forgingOrders;
            this.forgingReceipts = forgingReceipts; this.downstream = downstream; this.confirmations = confirmations;
            for (JSONObject o : orders) orderById.put(s(o, "id"), o);
            accumulate(totals, rmPos, rmReceipts, rmDispatches, forgingOrders, forgingReceipts, downstream);
            // purchase_order_confirmation: latest by created_at per PO
            List<JSONObject> sorted = new ArrayList<>(confirmations);
            sorted.sort((x, y) -> s(x, "created_at").compareTo(s(y, "created_at")));
            for (JSONObject c : sorted) confirmationByPo.put(s(c, "purchase_order_id"), up(c, "confirmation_status"));
        }

        double[] totals(String orderId) { double[] t = totals.get(orderId); return t == null ? new double[9] : t; }
        boolean confirmed(String poId) { return poId != null && !poId.isEmpty() && "CONFIRMED".equals(confirmationByPo.get(poId)); }
        JSONObject order(String id) { JSONObject o = orderById.get(id); return o == null ? new JSONObject() : o; }
    }

    static double[] bucket(Map<String, double[]> m, String key) {
        double[] b = m.get(key);
        if (b == null) { b = new double[9]; m.put(key, b); }
        return b;
    }

    static void accumulate(Map<String, double[]> out, List<JSONObject> rmPos, List<JSONObject> rmReceipts, List<JSONObject> rmDispatches,
                           List<JSONObject> forgingOrders, List<JSONObject> forgingReceipts, List<JSONObject> downstream) {
        for (JSONObject r : rmPos) if (!"CANCELLED".equals(s(r, "status"))) bucket(out, s(r, "customer_order_id"))[RM_ORDERED] += num(r, "ordered_qty_kg");
        for (JSONObject r : rmReceipts) bucket(out, s(r, "customer_order_id"))[RM_RECEIVED] += num(r, "received_qty_kg");
        for (JSONObject r : rmDispatches) bucket(out, s(r, "customer_order_id"))[RM_DISPATCHED] += num(r, "qty_kg");
        for (JSONObject r : forgingOrders) if (!"CANCELLED".equals(s(r, "status"))) bucket(out, s(r, "customer_order_id"))[FORGING_ORDERED] += num(r, "order_qty_pcs");
        for (JSONObject r : forgingReceipts) {
            double[] b = bucket(out, s(r, "customer_order_id"));
            b[FORGING_RECEIVED] += num(r, "received_qty_pcs");
            b[RM_CONSUMED] += !r.isNull("actual_rm_consumed_kg") ? num(r, "actual_rm_consumed_kg") : num(r, "received_qty_pcs") * num(r, "gross_weight_kg_snapshot");
        }
        for (JSONObject r : downstream) {
            double[] b = bucket(out, s(r, "customer_order_id"));
            String ev = s(r, "event_type");
            if (ev.equals("MACHINING")) b[MACHINED] += num(r, "qty_pcs");
            else if (ev.equals("FINISHED_GOODS")) b[FINISHED] += num(r, "qty_pcs");
            else if (ev.equals("CUSTOMER_DISPATCH")) b[DISPATCHED] += num(r, "qty_pcs");
        }
    }

    Data load() throws Exception {
        String lim = "&order=created_at.desc&limit=10000";
        List<JSONObject> orders = live("supply_customer_orders?select=*" + lim);
        for (JSONObject o : orders) {   // customer_orders(): explicit flow + cleaned remarks
            o.put("supply_flow", flowFor(o));
            o.put("remarks", n(cleanFlowRemarks(s(o, "remarks"))));
        }
        return new Data(orders,
            live("supply_rm_purchase_orders?select=*" + lim), live("supply_rm_receipts?select=*" + lim), live("supply_rm_dispatches?select=*" + lim),
            live("supply_forging_orders?select=*" + lim), live("supply_forging_receipts?select=*" + lim), live("supply_downstream_events?select=*&order=created_at.desc&limit=20000"),
            live("supply_po_confirmations?select=id,purchase_order_id,confirmation_status,created_at&limit=5000"));
    }

    /** totals(order_id) read live for one Customer Order (CANCELLED stage orders excluded like the website). */
    double[] totals(String orderId) throws Exception {
        Map<String, double[]> m = new HashMap<>();
        String f = "&customer_order_id=eq." + Api.enc(orderId) + "&limit=10000";
        accumulate(m, live("supply_rm_purchase_orders?select=customer_order_id,status,ordered_qty_kg" + f),
            live("supply_rm_receipts?select=customer_order_id,received_qty_kg" + f),
            live("supply_rm_dispatches?select=customer_order_id,qty_kg" + f),
            live("supply_forging_orders?select=customer_order_id,status,order_qty_pcs" + f),
            live("supply_forging_receipts?select=customer_order_id,received_qty_pcs,actual_rm_consumed_kg,gross_weight_kg_snapshot" + f),
            live("supply_downstream_events?select=customer_order_id,event_type,qty_pcs" + f));
        double[] tt = m.get(orderId);
        return tt == null ? new double[9] : tt;
    }

    static boolean anyPositive(double[] t) { for (double v : t) if (v > 0) return true; return false; }

    // ================================================================== status sync
    /** sync_order_status: COMPLETED when dispatched ≥ qty, IN_PROGRESS when anything posted, else OPEN. */
    String syncOrderStatus(String orderId) throws Exception {
        if (orderId == null || orderId.isEmpty()) return "";
        JSONObject order = get("supply_customer_orders", orderId);
        if (empty(order) || "CANCELLED".equals(s(order, "status"))) return s(order, "status");
        double[] tt = totals(orderId);
        double qty = num(order, "order_qty_pcs");
        String status = qty > 0 && tt[DISPATCHED] >= qty ? "COMPLETED" : anyPositive(tt) ? "IN_PROGRESS" : "OPEN";
        if (!status.equals(s(order, "status"))) api.update("supply_customer_orders", orderId, new JSONObject().put("status", status));
        return status;
    }

    double purchaseOrderReceivedQty(JSONObject po) throws Exception {
        String id = s(po, "id");
        Set<String> ids = new HashSet<>();
        double total = 0;
        if ("RAW_MATERIAL".equals(s(po, "po_type"))) {
            for (JSONObject r : live("supply_rm_purchase_orders?select=id&purchase_order_id=eq." + id + "&limit=1000")) ids.add(s(r, "id"));
            if (ids.isEmpty()) return 0;
            for (JSONObject r : live("supply_rm_receipts?select=rm_purchase_order_id,received_qty_kg&rm_purchase_order_id=in.(" + inList(ids) + ")&limit=10000")) total += num(r, "received_qty_kg");
        } else {
            for (JSONObject r : live("supply_forging_orders?select=id&purchase_order_id=eq." + id + "&limit=1000")) ids.add(s(r, "id"));
            if (ids.isEmpty()) return 0;
            for (JSONObject r : live("supply_forging_receipts?select=forging_order_id,received_qty_pcs&forging_order_id=in.(" + inList(ids) + ")&limit=10000")) total += num(r, "received_qty_pcs");
        }
        return r3(total);
    }

    double purchaseOrderItemReceivedQty(JSONObject item, JSONObject header) throws Exception {
        if ("RAW_MATERIAL".equals(s(header, "po_type"))) {
            List<JSONObject> stages = live("supply_rm_purchase_orders?select=id,customer_order_id&purchase_order_item_id=eq." + s(item, "id") + "&limit=1000");
            if (stages.isEmpty() && !s(item, "customer_order_id").isEmpty()) {
                for (JSONObject r : live("supply_rm_purchase_orders?select=id,customer_order_id&purchase_order_id=eq." + s(item, "purchase_order_id") + "&limit=1000"))
                    if (s(r, "customer_order_id").equals(s(item, "customer_order_id"))) stages.add(r);
            }
            Set<String> ids = new HashSet<>();
            for (JSONObject r : stages) ids.add(s(r, "id"));
            if (ids.isEmpty()) return 0;
            double total = 0;
            for (JSONObject r : live("supply_rm_receipts?select=received_qty_kg&rm_purchase_order_id=in.(" + inList(ids) + ")&limit=10000")) total += num(r, "received_qty_kg");
            return r3(total);
        }
        return purchaseOrderReceivedQty(header);
    }

    /** sync_purchase_order_status: CLOSED / PARTIAL / OPEN (pending-approval POs untouched). */
    String syncPurchaseOrderStatus(String poId) throws Exception {
        if (poId == null || poId.isEmpty()) return "";
        JSONObject po = get("supply_purchase_orders", poId);
        if (empty(po) || "CANCELLED".equals(s(po, "status"))) return s(po, "status");
        if ("PENDING_APPROVAL".equals(first(s(po, "approval_status"), "APPROVED").toUpperCase(Locale.ROOT))) return "PENDING_APPROVAL";
        double ordered = 0;
        for (JSONObject r : live("supply_purchase_order_items?select=quantity&purchase_order_id=eq." + poId + "&limit=1000")) ordered += num(r, "quantity");
        double received = purchaseOrderReceivedQty(po);
        String status = ordered > 0 && received + 0.0001 >= ordered ? "CLOSED" : received > 0 ? "PARTIAL" : "OPEN";
        if (!status.equals(s(po, "status"))) api.update("supply_purchase_orders", poId, new JSONObject().put("status", status));
        return status;
    }

    boolean poConfirmed(String poId) throws Exception {
        if (poId == null || poId.isEmpty()) return false;
        List<JSONObject> rows = live("supply_po_confirmations?select=confirmation_status,created_at&purchase_order_id=eq." + poId + "&order=created_at.desc&limit=1");
        return !rows.isEmpty() && "CONFIRMED".equals(up(rows.get(0), "confirmation_status"));
    }

    // ================================================================== procurement decision
    double systemAvailableQty(String partId) throws Exception {
        double production = 0;
        for (JSONObject r : live("production_batches?select=quantity_available,status&part_id=eq." + Api.enc(partId) + "&limit=20000")) {
            String st = up(r, "status");
            if (st.equals("REJECTED") || st.equals("CANCELLED") || st.equals("SCRAPPED")) continue;
            production += Math.max(num(r, "quantity_available"), 0);
        }
        double opening = 0;
        for (JSONObject r : live("supply_opening_stock?select=available_quantity_pcs&part_id=eq." + Api.enc(partId) + "&stage=eq.FINISHED_GOODS&status=eq.ACTIVE&limit=10000"))
            opening += Math.max(num(r, "available_quantity_pcs"), 0);
        return r3(production + opening);
    }

    double threeMonthDemand(String partId, String customerId, String anchor, String excludeId) throws Exception {
        LocalDate start = monthStart(anchor), end = start.plusMonths(3);
        double total = 0;
        for (JSONObject r : live("supply_customer_orders?select=id,status,customer_id,order_type,schedule_month,order_qty_pcs&part_id=eq." + Api.enc(partId) + "&order_type=eq.MONTHLY_SCHEDULE&limit=10000")) {
            if (s(r, "id").equals(excludeId == null ? "" : excludeId) || "CANCELLED".equals(s(r, "status"))) continue;
            if (customerId != null && !customerId.isEmpty() && !customerId.equals(s(r, "customer_id"))) continue;
            String sched = parseDate(s(r, "schedule_month"));
            if (sched == null) continue;
            LocalDate d = monthStart(sched);
            if (!d.isBefore(start) && d.isBefore(end)) total += num(r, "order_qty_pcs");
        }
        return r3(total);
    }

    /** procurement_check: stock vs rolling three-month schedule demand. */
    JSONObject procurementCheck(String partId, String customerId, String anchor, double proposed, String excludeId) throws Exception {
        double stock = systemAvailableQty(partId);
        double existing = threeMonthDemand(partId, customerId, anchor, excludeId);
        double demand = r3(existing + Math.max(proposed, 0));
        double shortage = r3(Math.max(demand - stock, 0));
        return new JSONObject().put("available_stock_pcs", stock).put("existing_three_month_schedule_pcs", existing)
            .put("three_month_schedule_pcs", demand).put("shortage_pcs", shortage).put("rm_procurement_allowed", shortage > 0.0001);
    }

    // ================================================================== duplicates
    void assertPurchaseOrderDuplicate(JSONObject p, String recordId) throws Exception {
        if (!"PURCHASE_ORDER".equals(s(p, "order_type"))) return;
        String customerId = s(p, "customer_id");
        String orderNo = norm(s(p, "customer_order_no"));
        String position = norm(s(p, "order_position"));
        if (customerId.isEmpty() || orderNo.isEmpty()) return;
        for (JSONObject r : live("supply_customer_orders?select=id,status,customer_id,customer_order_no,master_reference_no,order_position&customer_id=eq." + Api.enc(customerId) + "&limit=10000")) {
            if (s(r, "id").equals(recordId == null ? "" : recordId) || "CANCELLED".equals(s(r, "status"))) continue;
            if (norm(first(s(r, "customer_order_no"), s(r, "master_reference_no"))).equals(orderNo) && norm(s(r, "order_position")).equals(position))
                throw new Rule("Duplicate Customer Order is not allowed. Customer + Order No. + PosNr already exists.");
        }
    }

    static final Map<String, String[]> DUP_KEYS = new HashMap<>();
    static {
        DUP_KEYS.put("supply_rm_purchase_orders", new String[]{"rm_supplier_id", "supplier_order_no", "customer_order_id"});
        DUP_KEYS.put("supply_rm_receipts", new String[]{"rm_purchase_order_id", "receipt_number"});
        DUP_KEYS.put("supply_rm_dispatches", new String[]{"dispatch_number"});
        DUP_KEYS.put("supply_forging_orders", new String[]{"forging_supplier_id", "supplier_order_no"});
        DUP_KEYS.put("supply_forging_receipts", new String[]{"forging_order_id", "receipt_number"});
        DUP_KEYS.put("supply_downstream_events", new String[]{"customer_order_id", "event_type", "reference_no"});
    }

    void assertTransactionDuplicate(String table, JSONObject p, String recordId) throws Exception {
        String[] fields = DUP_KEYS.get(table);
        if (fields == null) return;
        String[] expected = new String[fields.length];
        boolean any = false;
        for (int i = 0; i < fields.length; i++) { expected[i] = norm(s(p, fields[i])); any |= !expected[i].isEmpty(); }
        if (!any) return;
        // narrow the read with the first uuid key when it is filled (same comparison result)
        StringBuilder q = new StringBuilder(table + "?select=id," + String.join(",", fields) + "&limit=10000");
        if (fields[0].endsWith("_id") && !s(p, fields[0]).isEmpty()) q.append("&").append(fields[0]).append("=eq.").append(Api.enc(s(p, fields[0])));
        for (JSONObject r : live(q.toString())) {
            if (s(r, "id").equals(recordId == null ? "" : recordId)) continue;
            boolean same = true;
            for (int i = 0; i < fields.length && same; i++) same = norm(s(r, fields[i])).equals(expected[i]);
            if (same) throw new Rule("Duplicate entry is not allowed. A record with the same controlled reference already exists.");
        }
    }

    /** save_transaction (stage tables): duplicate gate then insert / update. */
    JSONObject saveTransaction(String table, JSONObject p, String recordId) throws Exception {
        assertTransactionDuplicate(table, p, recordId);
        return recordId == null || recordId.isEmpty() ? api.insert(table, p) : api.update(table, recordId, p);
    }

    // ================================================================== customer orders
    void refreshOrderRawSource(JSONObject p) throws Exception {
        String rawId = s(p, "raw_material_detail_id");
        if (rawId.isEmpty()) return;
        JSONObject raw = get("part_raw_material_details", rawId);
        if (t(raw, "source_part_id").isEmpty()) return;
        if (!s(raw, "part_id").equals(s(p, "part_id")) || !"ACTIVE".equals(s(raw, "status")))
            throw new Rule("Select an ACTIVE raw-material link belonging to the customer-order part.");
        JSONObject resolved = effectiveLink(new JSONObject().put("id", s(p, "part_id")), raw);
        p.put("forging_supplier_id", raw(resolved, "supplier_id"));
        double gross = num(resolved, "gross_weight_kg");
        if (gross == 0) gross = num(resolved, "input_weight_kg");
        if (gross == 0) gross = num(resolved, "forging_weight_kg");
        p.put("gross_weight_kg_snapshot", gross);
    }

    /** create_customer_order (checkOverride = the procurement check shown on screen, like the website). */
    JSONObject createCustomerOrder(JSONObject payload, JSONObject checkOverride) throws Exception {
        JSONObject p = copy(payload);
        refreshOrderRawSource(p);
        Object fl = p.remove("supply_flow");
        String flow = first(fl == null ? "" : String.valueOf(fl), FSI_RM).toUpperCase(Locale.ROOT);
        if (!validFlow(flow)) throw new Rule("Select a valid Supply Chain Flow.");
        double qty = num(p, "order_qty_pcs"), gross = num(p, "gross_weight_kg_snapshot");
        if (qty <= 0 || gross <= 0) throw new Rule("Order Quantity and Forging Supplier Gross Weight must be greater than zero.");
        p.put("required_rm_kg", requiresRm(flow) ? r3(qty * gross) : 0.0);
        JSONObject check;
        if (checkOverride != null) check = checkOverride;
        else {
            Object prop = p.remove("proposed_three_month_qty");
            double proposed = prop != null ? num(prop) : ("PURCHASE_ORDER".equals(s(p, "order_type")) ? qty : 0);
            check = procurementCheck(s(p, "part_id"), s(p, "customer_id"), first(s(p, "schedule_month"), s(p, "customer_delivery_date"), s(p, "order_date")), proposed, null);
        }
        boolean allowed = check.optBoolean("rm_procurement_allowed");
        boolean requested = truthy(p, "rm_procurement_required", allowed);
        String decision;
        if (DIRECT_FORGING.equals(flow)) { requested = false; decision = "DIRECT_FORGING"; }
        else if (!allowed) { requested = false; decision = "AVAILABLE_STOCK"; }
        else decision = requested ? "REQUIRED" : "MANUAL_NOT_REQUIRED";
        p.put("rm_procurement_required", requested);
        p.put("available_stock_pcs_snapshot", check.optDouble("available_stock_pcs", 0));
        p.put("three_month_schedule_pcs_snapshot", check.optDouble("three_month_schedule_pcs", 0));
        p.put("procurement_shortage_pcs_snapshot", check.optDouble("shortage_pcs", 0));
        p.put("procurement_decision", decision);
        p.put("supply_flow", flow);
        p.put("remarks", flowRemarks(s(p, "remarks"), flow));
        if ("MONTHLY_SCHEDULE".equals(s(p, "order_type"))) {
            String schedule = d10(s(p, "schedule_month"));
            if (schedule.isEmpty()) throw new Rule("Month and Year are required for a Monthly Schedule.");
            int y = Integer.parseInt(schedule.substring(0, 4)), m = Integer.parseInt(schedule.substring(5, 7));
            JSONObject part = get("parts", s(p, "part_id"));
            p.put("master_reference_no", monthlyReference(s(part, "part_number"), m, y));
            p.put("customer_order_no", JSONObject.NULL);
            p.put("order_position", first(s(p, "order_position"), String.format(Locale.ROOT, "%02d-%d", m, y)));
        } else {
            String ref = t(p, "customer_order_no");
            if (ref.isEmpty()) throw new Rule("Customer Order Number is required for a Purchase Order.");
            p.put("master_reference_no", ref);
            assertPurchaseOrderDuplicate(p, null);
        }
        return api.insert("supply_customer_orders", p);
    }

    /** update_customer_order (edit panel) incl. the flow-change rule and recomputed snapshots. */
    JSONObject updateCustomerOrder(String recordId, JSONObject payload) throws Exception {
        JSONObject existing = get("supply_customer_orders", recordId);
        if (empty(existing)) throw new Rule("Customer Order was not found.");
        existing.put("remarks", n(cleanFlowRemarks(s(existing, "remarks"))));
        JSONObject p = copy(payload);
        String existingFlow = flowFor(existing);
        Object fl = p.remove("supply_flow");
        String flow = first(fl == null ? "" : String.valueOf(fl), existingFlow).toUpperCase(Locale.ROOT);
        if (!validFlow(flow)) throw new Rule("Select a valid Supply Chain Flow.");
        if (!flow.equals(existingFlow) && anyPositive(totals(recordId)))
            throw new Rule("Supply Chain Flow cannot be changed after linked procurement / forging / production / dispatch transactions have started.");
        JSONObject merged = copy(existing);
        Iterator<String> it = p.keys();
        while (it.hasNext()) { String k = it.next(); merged.put(k, p.opt(k)); }
        refreshOrderRawSource(merged);
        p.put("forging_supplier_id", raw(merged, "forging_supplier_id"));
        p.put("gross_weight_kg_snapshot", raw(merged, "gross_weight_kg_snapshot"));
        double qty = num(merged, "order_qty_pcs"), gross = num(merged, "gross_weight_kg_snapshot");
        if (qty <= 0 || gross <= 0) throw new Rule("Order Quantity and Gross Weight must be greater than zero.");
        p.put("required_rm_kg", requiresRm(flow) ? r3(qty * gross) : 0.0);
        Object prop = p.remove("proposed_three_month_qty");
        JSONObject check = procurementCheck(s(merged, "part_id"), s(merged, "customer_id"), first(s(merged, "schedule_month"), s(merged, "customer_delivery_date"), s(merged, "order_date")),
            num(prop), recordId);
        boolean allowed = check.optBoolean("rm_procurement_allowed");
        boolean requested = requiresRm(flow) && truthy(merged, "rm_procurement_required", allowed);
        String decision;
        if (DIRECT_FORGING.equals(flow)) decision = "DIRECT_FORGING";
        else if (!allowed) { requested = false; decision = "AVAILABLE_STOCK"; }
        else decision = requested ? "REQUIRED" : "MANUAL_NOT_REQUIRED";
        p.put("rm_procurement_required", requested);
        p.put("available_stock_pcs_snapshot", check.optDouble("available_stock_pcs", 0));
        p.put("three_month_schedule_pcs_snapshot", check.optDouble("three_month_schedule_pcs", 0));
        p.put("procurement_shortage_pcs_snapshot", check.optDouble("shortage_pcs", 0));
        p.put("procurement_decision", decision);
        p.put("supply_flow", flow);
        p.put("remarks", flowRemarks(s(merged, "remarks"), flow));
        if ("PURCHASE_ORDER".equals(s(merged, "order_type"))) {
            p.put("master_reference_no", t(merged, "customer_order_no"));
            assertPurchaseOrderDuplicate(merged, recordId);
        }
        return api.update("supply_customer_orders", recordId, p);
    }

    // ================================================================== PO eligibility
    List<JSONObject> pendingCustomerOrdersForRm(Data d) throws Exception {
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject o : d.orders) {
            String st = s(o, "status");
            if (st.equals("COMPLETED") || st.equals("CANCELLED")) continue;
            if (!requiresRm(flowFor(o))) continue;
            if (!truthy(o, "rm_procurement_required", true)) continue;
            double total = d.totals(s(o, "id"))[RM_ORDERED], required = num(o, "required_rm_kg");
            if (total + 0.0001 < required) {
                JSONObject row = copy(o);
                row.put("rm_ordered_kg", total); row.put("rm_balance_kg", Math.max(required - total, 0));
                rows.add(row);
            }
        }
        rows.sort(DUE_ORDER);
        return rows;
    }

    static final Comparator<JSONObject> DUE_ORDER = (x, y) -> {
        int c = first(s(x, "customer_delivery_date"), "9999-12-31").compareTo(first(s(y, "customer_delivery_date"), "9999-12-31"));
        return c != 0 ? c : s(x, "master_reference_no").compareTo(s(y, "master_reference_no"));
    };

    List<JSONObject> pendingDirectForgingOrders(Data d) throws Exception {
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject o : d.orders) {
            String st = s(o, "status");
            if (!DIRECT_FORGING.equals(flowFor(o)) || st.equals("COMPLETED") || st.equals("CANCELLED")) continue;
            double ordered = d.totals(s(o, "id"))[FORGING_ORDERED], target = num(o, "order_qty_pcs");
            if (ordered + 0.0001 < target) {
                JSONObject row = copy(o);
                row.put("forging_ordered_pcs", ordered); row.put("forging_balance_pcs", Math.max(target - ordered, 0));
                rows.add(row);
            }
        }
        rows.sort(DUE_ORDER);
        return rows;
    }

    static Set<String> linkedDispatches(Data d) {
        Set<String> linked = new HashSet<>();
        for (JSONObject r : d.forgingOrders) if (!s(r, "rm_dispatch_id").isEmpty() && !"CANCELLED".equals(s(r, "status"))) linked.add(s(r, "rm_dispatch_id"));
        return linked;
    }

    /** pending_forging_po_sources: direct-forging orders + unlinked RM-to-forger dispatches (Flow 1). */
    List<JSONObject> pendingForgingPoSources(Data d) throws Exception {
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject o : pendingDirectForgingOrders(d)) {
            JSONObject row = copy(o);
            row.put("_source_type", "CUSTOMER_ORDER"); row.put("_source_id", s(o, "id")); row.put("_customer_order_id", s(o, "id"));
            row.put("_balance_pcs", num(o, "forging_balance_pcs"));
            rows.add(row);
        }
        Set<String> linked = linkedDispatches(d);
        for (JSONObject disp : d.rmDispatches) {
            if (linked.contains(s(disp, "id"))) continue;
            JSONObject order = d.order(s(disp, "customer_order_id"));
            if (empty(order) || !FSI_RM.equals(flowFor(order))) continue;
            JSONObject row = copy(order);
            Iterator<String> it = disp.keys();
            while (it.hasNext()) { String k = it.next(); row.put("dispatch_" + k, disp.opt(k)); }
            row.put("_source_type", "RM_DISPATCH"); row.put("_source_id", s(disp, "id")); row.put("_customer_order_id", s(order, "id"));
            row.put("_balance_pcs", Math.max(num(order, "order_qty_pcs") - d.totals(s(order, "id"))[FORGING_ORDERED], 0));
            row.put("_rm_dispatch", disp);
            rows.add(row);
        }
        rows.sort(DUE_ORDER);
        return rows;
    }

    /** purchase_order_source_status: every open order with eligibility + reason (eligible first). */
    List<JSONObject> sourceStatus(Data d, String poType) throws Exception {
        Set<String> rmPending = new HashSet<>();
        for (JSONObject r : pendingCustomerOrdersForRm(d)) rmPending.add(s(r, "id"));
        Map<String, JSONObject> forgingByOrder = new HashMap<>();
        if ("FORGING".equals(poType)) for (JSONObject r : pendingForgingPoSources(d)) forgingByOrder.put(s(r, "_customer_order_id"), r);
        Map<String, JSONObject> pendingRm = new HashMap<>();
        for (JSONObject r : pendingCustomerOrdersForRm(d)) pendingRm.put(s(r, "id"), r);
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject o : d.orders) {
            String st = s(o, "status");
            if (st.equals("COMPLETED") || st.equals("CANCELLED")) continue;
            String oid = s(o, "id"), flow = flowFor(o);
            boolean eligible = false; String reason;
            if ("RAW_MATERIAL".equals(poType)) {
                if (!requiresRm(flow)) reason = "Direct Forging flow · RM PO not required";
                else if (!truthy(o, "rm_procurement_required", true)) reason = Ui.pretty(first(s(o, "procurement_decision"), "RM not required"));
                else if (rmPending.contains(oid)) { eligible = true; reason = "Eligible for RM Purchase Order"; }
                else reason = "RM requirement already fully ordered";
            } else {
                if (forgingByOrder.containsKey(oid)) {
                    eligible = true;
                    reason = "CUSTOMER_ORDER".equals(s(forgingByOrder.get(oid), "_source_type")) ? "Eligible · Direct Customer Order" : "Eligible · RM dispatched to Forger";
                } else if (FSI_RM.equals(flow)) reason = "Waiting for RM Receipt / RM to Forger";
                else if (FSI_RM_DIRECT_PRODUCTION.equals(flow)) reason = "Direct Production flow · Forging PO not required";
                else reason = "Forging requirement already ordered";
            }
            JSONObject row = copy(o);
            row.put("_po_eligible", eligible); row.put("_po_reason", reason);
            if ("FORGING".equals(poType) && forgingByOrder.containsKey(oid)) row.put("_po_source", forgingByOrder.get(oid));
            if ("RAW_MATERIAL".equals(poType)) {
                JSONObject pend = pendingRm.get(oid);
                double ordered = pend == null ? 0 : num(pend, "rm_ordered_kg");
                row.put("rm_ordered_kg", ordered);
                row.put("rm_balance_kg", pend != null && num(pend, "rm_balance_kg") != 0 ? num(pend, "rm_balance_kg") : Math.max(num(o, "required_rm_kg") - ordered, 0));
            }
            rows.add(row);
        }
        rows.sort((x, y) -> {
            boolean ex = x.optBoolean("_po_eligible"), ey = y.optBoolean("_po_eligible");
            if (ex != ey) return ex ? -1 : 1;
            return DUE_ORDER.compare(x, y);
        });
        return rows;
    }

    // ================================================================== stage worklists
    List<JSONObject> pendingRmPurchaseOrders(Data d) throws Exception {
        Map<String, Double> receivedByPo = new HashMap<>();
        for (JSONObject r : d.rmReceipts) receivedByPo.merge(s(r, "rm_purchase_order_id"), num(r, "received_qty_kg"), Double::sum);
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject po : d.rmPos) {
            String st = s(po, "status");
            if (st.equals("CANCELLED") || st.equals("PENDING_APPROVAL")) continue;
            if (!d.confirmed(s(po, "purchase_order_id"))) continue;
            double received = receivedByPo.getOrDefault(s(po, "id"), 0.0), ordered = num(po, "ordered_qty_kg");
            if (received + 0.0001 < ordered) {
                JSONObject row = copy(po);
                row.put("received_qty_kg", received); row.put("balance_qty_kg", Math.max(ordered - received, 0));
                rows.add(row);
            }
        }
        rows.sort((x, y) -> { int c = first(s(x, "expected_date"), "9999-12-31").compareTo(first(s(y, "expected_date"), "9999-12-31")); return c != 0 ? c : s(x, "supplier_order_no").compareTo(s(y, "supplier_order_no")); });
        return rows;
    }

    List<JSONObject> pendingRmReceiptsForDispatch(Data d) throws Exception {
        Map<String, Double> sent = new HashMap<>();
        for (JSONObject r : d.rmDispatches) if (!s(r, "rm_receipt_id").isEmpty()) sent.merge(s(r, "rm_receipt_id"), num(r, "qty_kg"), Double::sum);
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject rec : d.rmReceipts) {
            if (!FSI_RM.equals(flowFor(d.order(s(rec, "customer_order_id"))))) continue;
            double out = sent.getOrDefault(s(rec, "id"), 0.0), received = num(rec, "received_qty_kg");
            if (out + 0.0001 < received) {
                JSONObject row = copy(rec);
                row.put("dispatched_qty_kg", out); row.put("balance_qty_kg", Math.max(received - out, 0));
                rows.add(row);
            }
        }
        rows.sort((x, y) -> { int c = first(s(x, "receipt_date"), "9999-12-31").compareTo(first(s(y, "receipt_date"), "9999-12-31")); return c != 0 ? c : s(x, "receipt_number").compareTo(s(y, "receipt_number")); });
        return rows;
    }

    List<JSONObject> pendingRmDispatchesForForgingOrder(Data d) {
        Set<String> linked = linkedDispatches(d);
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject r : d.rmDispatches) if (!linked.contains(s(r, "id"))) rows.add(r);
        return rows;
    }

    List<JSONObject> pendingForgingOrders(Data d) throws Exception {
        Map<String, Double> received = new HashMap<>();
        for (JSONObject r : d.forgingReceipts) received.merge(s(r, "forging_order_id"), num(r, "received_qty_pcs"), Double::sum);
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject fo : d.forgingOrders) {
            String st = s(fo, "status");
            if (st.equals("CANCELLED") || st.equals("PENDING_APPROVAL")) continue;
            if (!d.confirmed(s(fo, "purchase_order_id"))) continue;
            double rec = received.getOrDefault(s(fo, "id"), 0.0), ordered = num(fo, "order_qty_pcs");
            if (rec + .0001 < ordered) {
                JSONObject row = copy(fo);
                row.put("received_qty_pcs", rec); row.put("balance_qty_pcs", Math.max(ordered - rec, 0));
                rows.add(row);
            }
        }
        rows.sort((x, y) -> { int c = first(s(x, "expected_date"), "9999-12-31").compareTo(first(s(y, "expected_date"), "9999-12-31")); return c != 0 ? c : s(x, "supplier_order_no").compareTo(s(y, "supplier_order_no")); });
        return rows;
    }

    /** pending_sources_for_downstream: MACHINING ← forging receipt / Flow-3 RM receipt; FG ← machining; dispatch ← FG. */
    List<JSONObject> pendingSourcesForDownstream(Data d, String eventType) throws Exception {
        if ("MACHINING".equals(eventType)) {
            Set<String> usedForging = new HashSet<>(), usedRm = new HashSet<>();
            for (JSONObject e : d.downstream) {
                if (!"MACHINING".equals(s(e, "event_type"))) continue;
                if (!s(e, "source_forging_receipt_id").isEmpty()) usedForging.add(s(e, "source_forging_receipt_id"));
                if (!s(e, "source_rm_receipt_id").isEmpty()) usedRm.add(s(e, "source_rm_receipt_id"));
            }
            List<JSONObject> rows = new ArrayList<>();
            for (JSONObject rc : d.forgingReceipts) {
                if (usedForging.contains(s(rc, "id")) || num(rc, "received_qty_pcs") <= 0) continue;
                JSONObject row = copy(rc);
                row.put("_source_type", "FORGING_RECEIPT"); row.put("_source_id", s(rc, "id"));
                rows.add(row);
            }
            List<JSONObject> flow3 = new ArrayList<>();
            Set<String> inwardIds = new HashSet<>();
            for (JSONObject rc : d.rmReceipts) {
                String rid = s(rc, "id");
                if (rid.isEmpty() || usedRm.contains(rid)) continue;
                if (!FSI_RM_DIRECT_PRODUCTION.equals(flowFor(d.order(s(rc, "customer_order_id"))))) continue;
                flow3.add(rc);
                inwardIds.add(s(rc, "inward_lot_id"));
            }
            Map<String, JSONObject> inwards = byIds("inward_lots", "id,inward_number,heat_number,heat_code,accepted_production_quantity_pcs,production_quantity_pcs", inwardIds);
            for (JSONObject rc : flow3) {
                JSONObject inward = inwards.get(s(rc, "inward_lot_id"));
                if (inward == null) inward = new JSONObject();
                double production = firstNum(inward, "accepted_production_quantity_pcs", inward, "production_quantity_pcs");
                if (production <= 0) continue;
                JSONObject row = copy(rc);
                row.put("_source_type", "RM_RECEIPT"); row.put("_source_id", s(rc, "id"));
                row.put("received_qty_pcs", production);
                row.put("receipt_number", n(first(s(rc, "receipt_number"), s(inward, "inward_number"))));
                row.put("inward_lot_id", n(first(s(rc, "inward_lot_id"), s(inward, "id"))));
                row.put("heat_number", n(first(s(rc, "heat_number"), s(inward, "heat_number"))));
                row.put("heat_code", n(first(s(rc, "heat_code"), s(inward, "heat_code"))));
                rows.add(row);
            }
            rows.sort((x, y) -> { int c = first(s(x, "receipt_date"), "9999-12-31").compareTo(first(s(y, "receipt_date"), "9999-12-31")); return c != 0 ? c : s(x, "receipt_number").compareTo(s(y, "receipt_number")); });
            return rows;
        }
        String previous = "FINISHED_GOODS".equals(eventType) ? "MACHINING" : "FINISHED_GOODS";
        Set<String> used = new HashSet<>();
        for (JSONObject e : d.downstream) if (eventType.equals(s(e, "event_type")) && !s(e, "source_event_id").isEmpty()) used.add(s(e, "source_event_id"));
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject e : d.downstream) if (previous.equals(s(e, "event_type")) && !used.contains(s(e, "id")) && num(e, "qty_pcs") > 0) rows.add(e);
        return rows;
    }

    // ================================================================== Material Inward bridge
    List<JSONObject> eligibleInwardsForPo(String poId) throws Exception {
        JSONObject po = get("supply_rm_purchase_orders", poId);
        JSONObject order = get("supply_customer_orders", s(po, "customer_order_id"));
        if (empty(po) || empty(order)) return new ArrayList<>();
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject r : live("v_qsms_inward_register?select=*&part_id=eq." + Api.enc(s(order, "part_id")) + "&order=created_at.desc&limit=10000")) {
            String linked = s(r, "supply_rm_purchase_order_id");
            if (!linked.isEmpty() && !linked.equals(poId)) continue;
            rows.add(r);
        }
        return rows;
    }

    /** link_inward_to_rm_po: Material Inward → supply_rm_receipts, then order + PO status sync. */
    JSONObject linkInwardToRmPo(String poId, String inwardId) throws Exception {
        JSONObject po = get("supply_rm_purchase_orders", poId);
        JSONObject order = get("supply_customer_orders", s(po, "customer_order_id"));
        JSONObject inward = get("inward_lots", inwardId);
        if (empty(po) || empty(order) || empty(inward)) throw new Rule("RM Purchase Order or Material Inward record was not found.");
        if (!poConfirmed(s(po, "purchase_order_id")))
            throw new Rule("Supplier PO Confirmation is still pending. Upload and record the supplier acknowledgement before RM receipt / Material Inward linking.");
        if (!s(inward, "part_id").equals(s(order, "part_id"))) throw new Rule("Material Inward Part Number must match the Customer Order Part Number.");
        String other = s(inward, "supply_rm_purchase_order_id");
        if (!other.isEmpty() && !other.equals(poId)) throw new Rule("This Material Inward is already linked to another RM Procurement record.");
        try {
            api.update("inward_lots", inwardId, new JSONObject().put("supply_customer_order_id", s(order, "id")).put("supply_rm_purchase_order_id", poId));
        } catch (Exception e) {
            throw new Rule("Supply Chain v4.12.2 database migration must be applied before linking Material Inward. (" + Api.message(e) + ")");
        }
        JSONObject rmtc = get("rmtc_approvals", s(inward, "rmtc_approval_id"));
        double qty = num(inward, "steel_quantity_kg");
        if (qty == 0) qty = num(inward, "quantity_received");
        JSONObject payload = new JSONObject()
            .put("customer_order_id", s(order, "id")).put("rm_purchase_order_id", poId).put("inward_lot_id", inwardId)
            .put("receipt_number", raw(inward, "inward_number")).put("receipt_date", raw(inward, "inward_date"))
            .put("heat_number", raw(inward, "heat_number")).put("heat_code", raw(inward, "heat_code"))
            .put("received_qty_kg", qty).put("supplier_challan", raw(inward, "grn_number"))
            .put("rmtc_number", raw(rmtc, "rmtc_number")).put("rmtc_date", raw(rmtc, "certificate_date")).put("rmtc_qty_kg", num(rmtc, "certificate_quantity"))
            .put("remarks", "Linked automatically from Material Inward");
        List<JSONObject> existing = live("supply_rm_receipts?select=id&inward_lot_id=eq." + inwardId + "&limit=1");
        JSONObject saved = existing.isEmpty() ? api.insert("supply_rm_receipts", payload) : api.update("supply_rm_receipts", s(existing.get(0), "id"), payload);
        syncOrderStatus(s(order, "id"));
        syncPurchaseOrderStatus(s(po, "purchase_order_id"));
        return saved;
    }

    // ================================================================== controlled Purchase Orders
    static String friendlyPoError(Exception e) {
        String text = Api.message(e);
        if (text.contains("uq_supply_rm_supplier_order_no"))
            return "This PO clubs several Customer Orders for the same supplier, but the database still allows only one order per PO number. Ask the administrator to run QCMS_R20_RUN_IN_SUPABASE.sql once, then create the PO again. The incomplete PO was cancelled automatically, so the Customer Orders are free again.";
        if (text.contains("uq_supply_rm_po_order_supplier"))
            return "A selected Customer Order already has an active RM Purchase Order with this supplier. Cancel that PO first (cancelled POs release their Customer Orders) or remove the order from this PO.";
        return text;
    }

    void abortPurchaseOrder(JSONObject header, Exception error) {
        String poId = s(header, "id");
        if (poId.isEmpty()) return;
        String msg = Api.message(error);
        try {
            api.rpc("qcms_cancel_purchase_order", new JSONObject().put("p_purchase_order_id", poId).put("p_reason", "Auto-cancelled: PO creation failed - " + (msg.length() > 180 ? msg.substring(0, 180) : msg)));
        } catch (Exception e) {
            try {
                api.update("supply_purchase_orders", poId, new JSONObject().put("status", "CANCELLED").put("approval_status", "CANCELLED").put("cancellation_reason", "Auto-cancelled: PO creation failed"));
                for (JSONObject r : live("supply_rm_purchase_orders?select=id&purchase_order_id=eq." + poId + "&limit=200"))
                    api.update("supply_rm_purchase_orders", s(r, "id"), new JSONObject().put("status", "CANCELLED"));
            } catch (Exception ignored) { }
        }
    }

    /** Validated issuing plant / ship-to / requisitioner of a new PO (create_purchase_order header part). */
    static final class Header {
        JSONObject supplier, plantSnapshot, shipToSnapshot;
        String companyBranchId, shipToPartyId = "", shipToBranchId = "", shipToSource, requisitionerId, requisitionerName;
    }

    Header validateHeader(JSONObject p) throws Exception {
        Header h = new Header();
        h.supplier = get("parties", s(p, "supplier_id"));
        if (empty(h.supplier)) throw new Rule("Select a valid Supplier.");
        h.companyBranchId = t(p, "company_branch_id");
        JSONObject branch = get("company_branches", h.companyBranchId);
        if (empty(branch) || !"ACTIVE".equals(first(s(branch, "status"), "ACTIVE").toUpperCase(Locale.ROOT)))
            throw new Rule("Select a valid ACTIVE Company Branch / Plant for the Purchase Order.");
        h.plantSnapshot = branchSnapshot(branch);
        h.shipToSource = up(p, "ship_to_source_type");
        if (!Arrays.asList("CUSTOMER", "SUPPLIER", "VENDOR", "BRANCH").contains(h.shipToSource))
            throw new Rule("Select Ship-To Source from Company Branch, Customer, Supplier or Vendor / OSP Master.");
        if ("BRANCH".equals(h.shipToSource)) {
            h.shipToBranchId = t(p, "ship_to_branch_id");
            JSONObject sb = get("company_branches", h.shipToBranchId);
            if (empty(sb) || !"ACTIVE".equals(first(s(sb, "status"), "ACTIVE").toUpperCase(Locale.ROOT))) throw new Rule("Select a valid ACTIVE Company Branch for Ship-To.");
            h.shipToSnapshot = branchSnapshot(sb);
            h.shipToSnapshot.put("source_type", "BRANCH").put("source_branch_id", h.shipToBranchId).put("party_code", raw(sb, "branch_code")).put("party_name", raw(sb, "branch_name"));
        } else {
            h.shipToPartyId = t(p, "ship_to_party_id");
            JSONObject sp = get("parties", h.shipToPartyId);
            if (empty(sp) || !"ACTIVE".equals(first(s(sp, "status"), "ACTIVE").toUpperCase(Locale.ROOT))) throw new Rule("Select a valid ACTIVE Ship-To party/address from the selected master.");
            if (!shipToMatches(sp, h.shipToSource)) throw new Rule("The selected Ship-To party does not belong to the selected Customer / Supplier / Vendor master.");
            h.shipToSnapshot = partySnapshot(sp);
            h.shipToSnapshot.put("source_type", h.shipToSource).put("source_party_id", h.shipToPartyId);
        }
        h.requisitionerId = first(t(p, "requisitioner_employee_id"), api.employeeId);
        JSONObject emp = get("employees", h.requisitionerId);
        if (empty(emp) || !"ACTIVE".equals(first(s(emp, "status"), "ACTIVE").toUpperCase(Locale.ROOT)))
            throw new Rule("The logged-in user must be linked to an ACTIVE Employee Master record before creating a Purchase Order.");
        h.requisitionerName = employeeName(emp);
        if (h.requisitionerName.isEmpty()) throw new Rule("The logged-in Employee Master record does not have a valid employee name.");
        return h;
    }

    private JSONObject headerPayload(JSONObject p, Header h, String poNumber, String poType, String orderDate, String currency,
                                     double subtotal, double cgst, double sgst, double igst, double other, double grand) throws Exception {
        JSONObject o = new JSONObject();
        o.put("po_number", poNumber).put("po_type", poType).put("supplier_id", s(p, "supplier_id")).put("order_date", orderDate)
            .put("delivery_date", raw(p, "delivery_date")).put("requisitioner", h.requisitionerName).put("requisitioner_employee_id", h.requisitionerId)
            .put("ship_via", first(s(p, "ship_via"), "Road")).put("incoterm", first(s(p, "incoterm"), "DAP, CHAKAN")).put("payment_term", first(s(p, "payment_term"), "NET 30 DAYS AFTER GRN"))
            .put("quotation_reference", n(s(p, "quotation_reference"))).put("quotation_date", n(s(p, "quotation_date"))).put("old_po_reference", n(s(p, "old_po_reference")))
            .put("currency", currency).put("company_branch_id", h.companyBranchId).put("plant_snapshot", h.plantSnapshot).put("vendor_snapshot", partySnapshot(h.supplier))
            .put("ship_to_party_id", n(h.shipToPartyId)).put("ship_to_branch_id", n(h.shipToBranchId)).put("ship_to_source_type", h.shipToSource).put("ship_to_snapshot", h.shipToSnapshot)
            .put("remarks", first(s(p, "remarks"), "PART WILL BE SUPPLIED AS PER DRAWING.")).put("special_instructions", first(s(p, "special_instructions"), DEFAULT_SPECIAL_INSTRUCTIONS))
            .put("subtotal", subtotal).put("cgst_amount", cgst).put("sgst_amount", sgst).put("igst_amount", igst).put("other_amount", other).put("grand_total", grand)
            .put("status", "PENDING_APPROVAL").put("approval_status", "PENDING_APPROVAL").put("submitted_by_employee_id", h.requisitionerId)
            .put("submitted_at", nowUtc()).put("replaces_purchase_order_id", n(s(p, "replaces_purchase_order_id")));
        return o;
    }

    private String nextPoNumber() throws Exception {
        Object v = api.rpcValue("qcms_next_supply_po_number", new JSONObject());
        String number = v == null ? "" : String.valueOf(v).trim();
        if (number.isEmpty() || "null".equals(number)) throw new Rule("QCMS could not allocate the next Purchase Order number.");
        return number;
    }

    /** GST split: CGST + SGST when the supplier is in Maharashtra (or state blank), else IGST. */
    static double[] gst(JSONObject supplier, double subtotal, double gstPercent) {
        double amount = r2(subtotal * gstPercent / 100.0);
        String state = t(supplier, "state").toLowerCase(Locale.ROOT);
        boolean intra = state.isEmpty() || state.equals("maharashtra") || state.equals("mh");
        return intra ? new double[]{r2(amount / 2.0), r2(amount / 2.0), 0} : new double[]{0, 0, amount};
    }

    /**
     * create_purchase_order. Payload keys as on the website: po_type, supplier_id, company_branch_id, order_date, delivery_date,
     * ship_to_source_type, ship_to_branch_id / ship_to_party_id, requisitioner_employee_id, ship_via, incoterm, payment_term,
     * quotation_reference, quotation_date, old_po_reference, gst_percent, other_amount, currency, remarks, special_instructions,
     * RAW_MATERIAL: customer_order_ids[], allocations{}, line_prices{}, line_hsn_sac{}, line_fsi_part_numbers{};
     * FORGING: forging_sources[{customer_order_id, quantity, rm_dispatch}].
     */
    JSONObject createPurchaseOrder(JSONObject p) throws Exception {
        String poType = up(p, "po_type");
        if (!poType.equals("RAW_MATERIAL") && !poType.equals("FORGING")) throw new Rule("Select Raw Material or Forging Purchase Order type.");
        String supplierId = s(p, "supplier_id");
        Header h = validateHeader(p);
        double gstPercent = Math.max(num(p, "gst_percent"), 0);
        String orderDate = first(s(p, "order_date"), LocalDate.now().toString());
        String currency = first(s(p, "currency"), "INR").toUpperCase(Locale.ROOT);
        double other = Math.max(num(p, "other_amount"), 0);
        return "RAW_MATERIAL".equals(poType) ? createRawMaterialPo(p, h, supplierId, gstPercent, orderDate, currency, other)
            : createForgingPo(p, h, supplierId, gstPercent, orderDate, currency, other);
    }

    private static final class Member { JSONObject order, part, raw, dispatch; double qty; }
    private static final class Group { JSONObject part, raw; double qty; final List<Member> members = new ArrayList<>(); }

    private JSONObject createRawMaterialPo(JSONObject p, Header h, String supplierId, double gstPercent, String orderDate, String currency, double other) throws Exception {
        LinkedHashSet<String> orderIds = new LinkedHashSet<>();
        JSONArray ids = p.optJSONArray("customer_order_ids");
        for (int i = 0; ids != null && i < ids.length(); i++) { String v = ids.optString(i, "").trim(); if (!v.isEmpty() && !"null".equals(v)) orderIds.add(v); }
        if (orderIds.isEmpty()) throw new Rule("Select at least one Customer Order / Schedule for the Raw Material Purchase Order.");
        JSONObject allocations = p.optJSONObject("allocations") == null ? new JSONObject() : p.optJSONObject("allocations");
        JSONObject linePrices = p.optJSONObject("line_prices") == null ? new JSONObject() : p.optJSONObject("line_prices");
        JSONObject lineHsn = p.optJSONObject("line_hsn_sac") == null ? new JSONObject() : p.optJSONObject("line_hsn_sac");
        JSONObject lineFsi = p.optJSONObject("line_fsi_part_numbers") == null ? new JSONObject() : p.optJSONObject("line_fsi_part_numbers");
        Map<String, Group> groups = new LinkedHashMap<>();
        for (String orderId : orderIds) {
            JSONObject order = get("supply_customer_orders", orderId);
            if (empty(order)) throw new Rule("One selected Customer Order / Schedule no longer exists.");
            String ref = s(order, "master_reference_no");
            if (!requiresRm(flowFor(order))) throw new Rule(ref + ": Raw Material Purchase Order is not applicable to the Direct Forging flow.");
            if (!truthy(order, "rm_procurement_required", true)) throw new Rule(ref + ": RM Procurement is not enabled because available stock covers the saved three-month decision.");
            String decision = up(order, "procurement_decision");
            if (!decision.isEmpty() && !decision.equals("REQUIRED") && !decision.equals("RM_REQUIRED"))
                throw new Rule(ref + ": saved RM procurement decision is " + Ui.pretty(decision) + ".");
            double balance = Math.max(num(order, "required_rm_kg") - totals(orderId)[RM_ORDERED], 0);
            double allocation = allocations.has(orderId) ? num(allocations.opt(orderId)) : balance;
            if (allocation <= 0 || allocation > balance + 0.0001)
                throw new Rule(ref + ": PO allocation must be greater than zero and cannot exceed the pending RM balance of " + fmt(balance, 3) + " kg.");
            JSONObject part = get("parts", s(order, "part_id"));
            JSONObject raw = rawMaterialForSupplier(s(part, "id"), supplierId, s(order, "raw_material_detail_id"));
            if (raw == null) throw new Rule(first(t(part, "fsi_part_number"), t(part, "part_number"), ref, "Part") + ": add an ACTIVE Raw Material Detail for the selected Supplier in Part Master first.");
            String key = rmGroupKey(part, raw);
            Group g = groups.get(key);
            if (g == null) { g = new Group(); g.part = part; g.raw = raw; groups.put(key, g); }
            Member m = new Member(); m.order = order; m.part = part; m.raw = raw; m.qty = allocation;
            g.qty += allocation; g.members.add(m);
        }
        List<JSONObject> lines = new ArrayList<>();
        double subtotal = 0;
        for (Map.Entry<String, Group> e : groups.entrySet()) {
            String key = e.getKey(); Group g = e.getValue();
            JSONObject part = g.part, raw = g.raw;
            String commonCode = t(raw, "supplier_rm_item_code");
            Set<String> memberHsn = new HashSet<>();
            for (Member m : g.members) { String hv = first(t(m.raw, "hsn_sac_code"), t(m.part, "hsn_sac_code")); if (!hv.isEmpty()) memberHsn.add(hv); }
            String rmLabel = first(commonCode, Lookups.join(t(raw, "material_section_name"), t(raw, "section_size")), "Raw material");
            if (g.members.size() > 1 && memberHsn.size() > 1)
                throw new Rule("Clubbed RM " + rmLabel + ": HSN/SAC differs between the selected Parts. Align Part Master Raw Material Details or split the PO.");
            TreeSet<Double> positive = new TreeSet<>();
            for (Member m : g.members) { double pr = currentPrice(s(m.part, "id"), supplierId, orderDate, "KGS", s(m.raw, "id")); if (pr > 0) positive.add(r6(pr)); }
            if (g.members.size() > 1 && positive.size() > 1) {
                List<String> vals = new ArrayList<>();
                for (Double v : positive) vals.add(g(v));
                throw new Rule("Clubbed RM " + rmLabel + ": current supplier price per kg differs between the selected Parts (" + String.join(", ", vals) + "). Align Part Master Price History or split the PO.");
            }
            double price = linePrices.has(key) ? num(linePrices.opt(key)) : 0;
            if (price <= 0) price = currentPrice(s(part, "id"), supplierId, orderDate, "KGS", s(raw, "id"));
            price = Math.max(price, 0);
            if (price <= 0) throw new Rule(first(s(part, "fsi_part_number"), s(part, "part_number"), "Part") + ": current supplier price is missing in Part Master Price History.");
            double qty = r3(g.qty);
            double lineTotal = r2(qty * price);
            subtotal += lineTotal;
            String fsi = first(commonCode, lineFsi.has(key) ? lineFsi.optString(key, "").trim() : "", t(part, "fsi_part_number"));
            if (fsi.isEmpty()) throw new Rule("Enter an FSI Part Number for " + first(s(part, "part_number"), "the selected Part") + " in the PO item grid before creating the supplier PO.");
            JSONArray history = priceHistoryForPo(s(part, "id"), supplierId, "KGS", s(raw, "id"));
            String masterHsn = first(t(raw, "hsn_sac_code"), t(part, "hsn_sac_code"));
            String hsn = first(lineHsn.has(key) ? lineHsn.optString(key, "").trim() : "", masterHsn);
            if (hsn.isEmpty()) throw new Rule(first(s(part, "fsi_part_number"), s(part, "part_number"), "Part") + ": HSN / SAC is missing in Part Master Raw Material Details.");
            TreeSet<String> linked = new TreeSet<>();
            for (Member m : g.members) linked.add(first(s(m.part, "fsi_part_number"), s(m.part, "part_number")));
            JSONObject line = new JSONObject();
            line.put("key", key).put("fsi", fsi).put("common", commonCode).put("linked", new JSONArray(linked)).put("qty", qty).put("price", price)
                .put("hsn", hsn).put("total", lineTotal).put("gst", r2(lineTotal * gstPercent / 100.0)).put("technical", technicalDataSnapshot(raw, part)).put("history", head(history, 250));
            lines.add(line);
        }
        subtotal = r2(subtotal);
        double[] tax = gst(h.supplier, subtotal, gstPercent);
        double grand = r2(subtotal + tax[0] + tax[1] + tax[2] + other);
        String poNumber = nextPoNumber();
        JSONObject header = api.insert("supply_purchase_orders", headerPayload(p, h, poNumber, "RAW_MATERIAL", orderDate, first(s(p, "currency"), "INR").toUpperCase(Locale.ROOT), subtotal, tax[0], tax[1], tax[2], other, grand));
        linkReplaced(p, header);
        try {
            JSONArray items = new JSONArray(), stages = new JSONArray();
            int index = 0;
            for (Map.Entry<String, Group> e : groups.entrySet()) {
                Group g = e.getValue(); JSONObject line = lines.get(index++);
                JSONObject part = g.part, raw = g.raw;
                JSONObject firstOrder = g.members.get(0).order;
                JSONObject grade = get("material_grades", first(s(raw, "material_grade_id"), s(part, "material_grade_id")));
                String rmIdentity = Lookups.join(t(raw, "material_section_name"), first(t(grade, "grade_code"), t(grade, "grade_name")), first(t(raw, "section_size"), t(part, "section_size")));
                JSONObject item = new JSONObject()
                    .put("purchase_order_id", s(header, "id")).put("customer_order_id", s(firstOrder, "id")).put("part_id", s(part, "id"))
                    .put("material_grade_id", n(first(s(raw, "material_grade_id"), s(part, "material_grade_id")))).put("raw_material_detail_id", n(s(raw, "id")))
                    .put("item_no", line.getString("fsi")).put("fsi_part_number_snapshot", line.getString("fsi")).put("supplier_item_code_snapshot", n(line.optString("common", "")))
                    .put("linked_finished_parts_snapshot", line.getJSONArray("linked").length() > 0 ? line.getJSONArray("linked") : new JSONArray().put(first(s(part, "fsi_part_number"), s(part, "part_number"))))
                    .put("original_part_number_snapshot", raw(part, "part_number")).put("hsn_sac_code", n(line.getString("hsn")))
                    .put("item_description", first(rmIdentity, s(part, "part_name"), "Raw Material")).put("rm_section", n(first(s(raw, "section_size"), s(part, "section_size"))))
                    .put("quantity", line.getDouble("qty")).put("uom", "KGS").put("unit_price", line.getDouble("price")).put("gst_percent", gstPercent)
                    .put("gst_amount", line.getDouble("gst")).put("line_total", line.getDouble("total"))
                    .put("forging_weight_kg", firstOrNull(raw, "forging_weight_kg", part)).put("gross_weight_kg", firstOrNull(raw, "gross_weight_kg", part))
                    .put("technical_data_snapshot", line.getJSONArray("technical")).put("price_history_snapshot", line.getJSONArray("history")).put("remarks", n(s(p, "item_remarks")));
                item = api.insert("supply_purchase_order_items", item);
                recordPurchasePrice(s(part, "id"), supplierId, s(raw, "id"), orderDate, line.getDouble("price"), "KGS", first(s(p, "currency"), "INR").toUpperCase(Locale.ROOT), s(item, "id"));
                JSONArray refreshed = priceHistoryForPo(s(part, "id"), supplierId, "KGS", s(raw, "id"));
                if (refreshed.length() > 0) item = api.update("supply_purchase_order_items", s(item, "id"), new JSONObject().put("price_history_snapshot", head(refreshed, 250)));
                items.put(item);
                for (Member m : g.members) {
                    double alloc = r3(m.qty);
                    api.insert("supply_purchase_order_sources", new JSONObject().put("purchase_order_id", s(header, "id")).put("purchase_order_item_id", s(item, "id"))
                        .put("customer_order_id", s(m.order, "id")).put("allocated_qty", alloc).put("allocation_uom", "KGS"));
                    JSONObject stage = saveTransaction("supply_rm_purchase_orders", new JSONObject().put("customer_order_id", s(m.order, "id")).put("rm_supplier_id", supplierId)
                        .put("supplier_order_no", poNumber).put("order_date", raw(header, "order_date")).put("ordered_qty_kg", alloc).put("expected_date", raw(header, "delivery_date"))
                        .put("status", "PENDING_APPROVAL").put("remarks", "Controlled Purchase Order " + poNumber).put("purchase_order_id", s(header, "id")).put("purchase_order_item_id", s(item, "id")), null);
                    stages.put(stage);
                    syncOrderStatus(s(m.order, "id"));
                }
            }
            return new JSONObject().put("header", header).put("items", items).put("stages", stages);
        } catch (Exception e) {
            abortPurchaseOrder(header, e);
            throw new Rule(friendlyPoError(e));
        }
    }

    /** Python `a.get(k) or b.get(k)`. */
    static Object firstOrNull(JSONObject a, String key, JSONObject b) {
        return num(a, key) != 0 ? a.opt(key) : raw(b, key);
    }

    private void linkReplaced(JSONObject p, JSONObject header) {
        String replaces = s(p, "replaces_purchase_order_id");
        if (replaces.isEmpty()) return;
        try { api.update("supply_purchase_orders", replaces, new JSONObject().put("replacement_purchase_order_id", s(header, "id"))); } catch (Exception ignored) { }
    }

    /** _assert_forging_sources: R10 server-side gate for Forging PO sources (before any write). */
    void assertForgingSources(JSONArray sources, String supplierId) throws Exception {
        Set<String> linked = new HashSet<>();
        for (JSONObject r : live("supply_forging_orders?select=rm_dispatch_id,status&rm_dispatch_id=not.is.null&limit=10000"))
            if (!"CANCELLED".equals(s(r, "status"))) linked.add(s(r, "rm_dispatch_id"));
        Set<String> seen = new HashSet<>();
        Map<String, Double> qtyByOrder = new LinkedHashMap<>();
        for (int i = 0; i < sources.length(); i++) {
            JSONObject src = sources.getJSONObject(i);
            String orderId = s(src, "customer_order_id");
            JSONObject order = get("supply_customer_orders", orderId);
            if (empty(order)) throw new Rule("One selected Forging PO source no longer exists.");
            String ref = first(s(order, "master_reference_no"), s(order, "customer_order_no"), "Customer Order");
            String st = s(order, "status");
            if (st.equals("COMPLETED") || st.equals("CANCELLED")) throw new Rule(ref + ": Customer Order is " + Ui.pretty(st) + "; a Forging PO cannot be created.");
            String flow = flowFor(order);
            if (FSI_RM_DIRECT_PRODUCTION.equals(flow)) throw new Rule(ref + ": FSI RM → Direct Production flow does not use a Forging Purchase Order.");
            if (FSI_RM.equals(flow)) {
                JSONObject dref = src.optJSONObject("rm_dispatch");
                String dispatchId = t(dref, "id");
                if (dispatchId.isEmpty()) throw new Rule(ref + ": FSI RM → Forging flow needs an RM-to-Forger dispatch before the Forging PO. Post RM Receipt and RM to Forger first.");
                JSONObject dispatch = get("supply_rm_dispatches", dispatchId);
                if (empty(dispatch)) throw new Rule(ref + ": the selected RM-to-Forger dispatch no longer exists.");
                if (!s(dispatch, "customer_order_id").equals(orderId)) throw new Rule(ref + ": the selected RM-to-Forger dispatch belongs to a different Customer Order.");
                String dn = first(s(dispatch, "dispatch_number"), dispatchId);
                if (linked.contains(dispatchId) || seen.contains(dispatchId)) throw new Rule(ref + ": RM dispatch " + dn + " is already linked to a Forging Purchase Order.");
                String forger = t(dispatch, "forging_supplier_id");
                if (!forger.isEmpty() && !forger.equals(supplierId)) throw new Rule(ref + ": RM dispatch " + dn + " was sent to a different forger. Select that forging supplier on the PO.");
                seen.add(dispatchId);
            }
            qtyByOrder.merge(orderId, num(src, "quantity"), Double::sum);
        }
        for (Map.Entry<String, Double> e : qtyByOrder.entrySet()) {
            JSONObject order = get("supply_customer_orders", e.getKey());
            String ref = first(s(order, "master_reference_no"), s(order, "customer_order_no"), "Customer Order");
            double balance = Math.max(num(order, "order_qty_pcs") - totals(e.getKey())[FORGING_ORDERED], 0);
            if (e.getValue() > balance + 0.0001)
                throw new Rule(ref + ": Forging PO quantity " + fmt(e.getValue(), 0) + " pcs exceeds the pending forging balance of " + fmt(balance, 0) + " pcs.");
        }
    }

    private JSONObject createForgingPo(JSONObject p, Header h, String supplierId, double gstPercent, String orderDate, String currency, double other) throws Exception {
        JSONArray sources = p.optJSONArray("forging_sources");
        if (sources == null || sources.length() == 0) throw new Rule("Select at least one Forging PO source.");
        assertForgingSources(sources, supplierId);
        Map<String, Group> groups = new LinkedHashMap<>();
        for (int i = 0; i < sources.length(); i++) {
            JSONObject src = sources.getJSONObject(i);
            JSONObject order = get("supply_customer_orders", s(src, "customer_order_id"));
            if (empty(order)) throw new Rule("One selected Forging PO source no longer exists.");
            JSONObject part = get("parts", s(order, "part_id"));
            JSONObject raw = rawMaterialForSupplier(s(part, "id"), supplierId, s(order, "raw_material_detail_id"));
            if (raw == null) throw new Rule(first(s(part, "fsi_part_number"), s(part, "part_number")) + ": add an ACTIVE supplier Raw Material / Forging Detail first.");
            if (!s(raw, "_source_error").isEmpty()) throw new Rule(s(raw, "_source_error"));
            resolveRawSource(part, raw, supplierId);
            double qty = num(src, "quantity");
            if (qty <= 0) throw new Rule("Forging Purchase Order quantity must be greater than zero for every selected source.");
            String key = forgingGroupKey(part, raw);
            Group g = groups.get(key);
            if (g == null) { g = new Group(); g.part = part; g.raw = raw; groups.put(key, g); }
            Member m = new Member(); m.order = order; m.part = part; m.raw = raw; m.qty = qty;
            m.dispatch = src.optJSONObject("rm_dispatch") == null ? new JSONObject() : src.optJSONObject("rm_dispatch");
            g.qty += qty; g.members.add(m);
        }
        List<JSONObject> lines = new ArrayList<>();
        List<JSONObject[]> sourceCtx = new ArrayList<>();
        double subtotal = 0;
        for (Map.Entry<String, Group> e : groups.entrySet()) {
            Group g = e.getValue();
            JSONObject part = g.part, raw = g.raw;
            JSONObject[] ctx = resolveRawSource(part, raw, supplierId);
            JSONObject sp = ctx[0], sr = ctx[1];
            String sharedSource = t(raw, "source_part_id");
            String commonCode = !sharedSource.isEmpty() ? first(t(sp, "part_number"), t(sr, "supplier_forging_part_number"), t(sp, "fsi_part_number")) : t(raw, "supplier_forging_part_number");
            if (g.members.size() > 1 && commonCode.isEmpty())
                throw new Rule("Multiple finished Parts can share one Forging PO item only when they reference the same Source Raw Forging / Casting Part or the same Supplier Forging Part No. in Part Master.");
            Set<String> sourceIds = new HashSet<>();
            for (Member m : g.members) sourceIds.add(t(m.raw, "source_part_id"));
            if (!sharedSource.isEmpty() && !(sourceIds.size() == 1 && sourceIds.contains(sharedSource)))
                throw new Rule("Selected sources do not reference the same Source Raw Forging / Casting Part; split them into separate PO items.");
            if (sharedSource.isEmpty()) {
                Set<String> codes = new HashSet<>();
                for (Member m : g.members) codes.add(t(m.raw, "supplier_forging_part_number").toLowerCase(Locale.ROOT));
                if (codes.size() > 1) throw new Rule("Selected sources do not use the same Supplier Forging Part No.; split them into separate PO items.");
            }
            Set<String> hsns = new HashSet<>();
            boolean blank = false;
            for (Member m : g.members) {
                JSONObject[] c = resolveRawSource(m.part, m.raw, supplierId);
                String hv = first(t(c[1], "hsn_sac_code"), t(c[0], "hsn_sac_code"));
                if (hv.isEmpty()) blank = true;
                hsns.add(hv);
            }
            if (blank) throw new Rule("HSN / SAC is missing in Part Master Raw Material Details for one or more selected Forging sources.");
            if (hsns.size() > 1) throw new Rule("Shared Forging item " + first(commonCode, "-") + " has different HSN/SAC values; split the PO or align master data.");
            TreeSet<Double> positive = new TreeSet<>();
            for (Member m : g.members) { double pr = effectiveCurrentPrice(m.part, m.raw, supplierId, orderDate, "NOS"); if (pr > 0) positive.add(r6(pr)); }
            if (positive.isEmpty()) throw new Rule(first(commonCode, s(part, "fsi_part_number"), s(part, "part_number")) + ": current supplier price is missing in Part Master Price History.");
            if (positive.size() > 1) throw new Rule("Shared Forging item " + first(commonCode, "-") + " has different current prices across linked Parts. Align Price History or split the PO.");
            double unitPrice = positive.first();
            double qty = r3(g.qty);
            double lineTotal = r2(qty * unitPrice);
            subtotal += lineTotal;
            String itemNo = first(commonCode, t(part, "fsi_part_number"), t(p, "fsi_part_number"));
            if (itemNo.isEmpty()) throw new Rule("Enter an FSI Part Number or Supplier Forging Part No. for the supplier PO item.");
            lines.add(new JSONObject().put("technical", technicalDataSnapshot(raw, part)).put("history", head(effectivePriceHistory(part, raw, supplierId, orderDate, "NOS"), 250))
                .put("item_no", itemNo).put("common", commonCode).put("hsn", hsns.iterator().next()).put("qty", qty).put("price", unitPrice)
                .put("total", lineTotal).put("gst", r2(lineTotal * gstPercent / 100.0)));
            sourceCtx.add(ctx);
        }
        subtotal = r2(subtotal);
        double[] tax = gst(h.supplier, subtotal, gstPercent);
        double grand = r2(subtotal + tax[0] + tax[1] + tax[2] + other);
        String poNumber = nextPoNumber();
        JSONObject header = api.insert("supply_purchase_orders", headerPayload(p, h, poNumber, "FORGING", orderDate, currency, subtotal, tax[0], tax[1], tax[2], other, grand));
        linkReplaced(p, header);
        try {
            JSONArray items = new JSONArray(), stages = new JSONArray();
            int index = 0;
            for (Group g : groups.values()) {
                JSONObject line = lines.get(index);
                JSONObject sp = sourceCtx.get(index)[0], sr = sourceCtx.get(index)[1];
                index++;
                JSONObject part = g.part, raw = g.raw;
                TreeSet<String> linked = new TreeSet<>();
                for (Member m : g.members) linked.add(first(s(m.part, "fsi_part_number"), s(m.part, "part_number")));
                JSONObject item = new JSONObject()
                    .put("purchase_order_id", s(header, "id")).put("customer_order_id", s(g.members.get(0).order, "id")).put("part_id", s(part, "id"))
                    .put("material_grade_id", n(first(s(sr, "material_grade_id"), s(sp, "material_grade_id")))).put("raw_material_detail_id", n(s(raw, "id")))
                    .put("item_no", line.getString("item_no")).put("fsi_part_number_snapshot", line.getString("item_no")).put("supplier_item_code_snapshot", n(line.optString("common", "")))
                    .put("linked_finished_parts_snapshot", new JSONArray(linked)).put("original_part_number_snapshot", raw(part, "part_number")).put("hsn_sac_code", line.getString("hsn"))
                    .put("item_description", first(s(sr, "supplier_forging_part_number"), s(raw, "supplier_forging_part_number"), s(sp, "part_name"), s(part, "part_name"), "Forging"))
                    .put("rm_section", n(first(s(sr, "section_size"), s(sp, "section_size")))).put("quantity", line.getDouble("qty")).put("uom", "NOS")
                    .put("unit_price", line.getDouble("price")).put("gst_percent", gstPercent).put("gst_amount", line.getDouble("gst")).put("line_total", line.getDouble("total"))
                    .put("forging_weight_kg", firstOrNull(sr, "forging_weight_kg", sp)).put("gross_weight_kg", firstOrNull(sr, "gross_weight_kg", sp))
                    .put("technical_data_snapshot", line.getJSONArray("technical")).put("price_history_snapshot", line.getJSONArray("history")).put("remarks", n(s(p, "item_remarks")));
                item = api.insert("supply_purchase_order_items", item);
                items.put(item);
                double weight = num(sr, "gross_weight_kg");
                if (weight == 0) weight = num(sr, "input_weight_kg");
                if (weight == 0) weight = num(sr, "forging_weight_kg");
                for (Member m : g.members) {
                    api.insert("supply_purchase_order_sources", new JSONObject().put("purchase_order_id", s(header, "id")).put("purchase_order_item_id", s(item, "id"))
                        .put("customer_order_id", s(m.order, "id")).put("allocated_qty", r3(m.qty)).put("allocation_uom", "PCS"));
                    JSONObject stage = new JSONObject().put("customer_order_id", s(m.order, "id")).put("forging_supplier_id", supplierId).put("supplier_order_no", poNumber)
                        .put("order_date", raw(header, "order_date")).put("order_qty_pcs", m.qty).put("required_rm_kg", r3(m.qty * weight)).put("expected_date", raw(header, "delivery_date"))
                        .put("status", "PENDING_APPROVAL").put("remarks", "Controlled Purchase Order " + poNumber).put("purchase_order_id", s(header, "id")).put("purchase_order_item_id", s(item, "id"));
                    if (m.dispatch != null && m.dispatch.length() > 0)
                        stage.put("rm_dispatch_id", raw(m.dispatch, "id")).put("inward_lot_id", raw(m.dispatch, "inward_lot_id")).put("heat_number", raw(m.dispatch, "heat_number")).put("heat_code", raw(m.dispatch, "heat_code"));
                    stages.put(saveTransaction("supply_forging_orders", stage, null));
                    syncOrderStatus(s(m.order, "id"));
                }
            }
            return new JSONObject().put("header", header).put("items", items).put("stages", stages);
        } catch (Exception e) {
            abortPurchaseOrder(header, e);
            throw new Rule(friendlyPoError(e));
        }
    }

    // ================================================================== PO revision (update_purchase_order)
    /**
     * update_purchase_order: header fields, source allocations (+ stage rows), item fields; with refresh=true the live
     * master price / HSN / item identity / technical data overrides the snapshot. Returns the PO to PENDING_APPROVAL.
     * payload: header keys, refresh_master_data, items[{id, item_no, hsn_sac_code, quantity, unit_price, gst_percent, remarks}], allocations[{id, allocated_qty}].
     */
    JSONObject updatePurchaseOrder(String poId, JSONObject p) throws Exception {
        JSONObject header = get("supply_purchase_orders", poId);
        if (empty(header)) throw new Rule("Purchase Order was not found.");
        if ("CANCELLED".equals(up(header, "status"))) throw new Rule("Cancelled Purchase Orders are not edited. Use Cancel & Reissue to create the replacement PO.");
        boolean wasApproved = "APPROVED".equals(up(header, "approval_status"));
        String supplierId = s(header, "supplier_id");
        JSONObject supplier = get("parties", supplierId);
        if (empty(supplier)) throw new Rule("The PO Supplier no longer exists in Supplier Master.");
        String employeeId = api.employeeId;
        if (employeeId == null || employeeId.isEmpty()) throw new Rule("Your login is not linked to an ACTIVE Employee Master record.");
        String poType = s(header, "po_type");
        String today = LocalDate.now().toString();

        String orderDate = parseDate(first(s(p, "order_date"), s(header, "order_date")));
        if (orderDate == null) orderDate = today;
        String deliveryDate = parseDate(first(s(p, "delivery_date"), s(header, "delivery_date")));
        String branchId = first(s(p, "company_branch_id"), s(header, "company_branch_id"));
        JSONObject branch = get("company_branches", branchId);
        if (empty(branch)) throw new Rule("Select a valid Company Branch / Plant.");
        String sourceType = first(s(p, "ship_to_source_type"), s(header, "ship_to_source_type"), "BRANCH").toUpperCase(Locale.ROOT);
        String shipPartyId = first(s(p, "ship_to_party_id"), s(header, "ship_to_party_id"));
        String shipBranchId = first(s(p, "ship_to_branch_id"), s(header, "ship_to_branch_id"));
        JSONObject shipSnapshot;
        if ("BRANCH".equals(sourceType)) {
            JSONObject ship = get("company_branches", shipBranchId);
            if (empty(ship)) throw new Rule("Select a valid Ship-To Company Branch.");
            shipSnapshot = branchSnapshot(ship);
            shipSnapshot.put("source_type", "BRANCH").put("source_branch_id", shipBranchId).put("party_code", raw(ship, "branch_code")).put("party_name", raw(ship, "branch_name"));
            shipPartyId = "";
        } else {
            JSONObject ship = get("parties", shipPartyId);
            if (empty(ship)) throw new Rule("Select a valid Ship-To Customer / Supplier / Vendor.");
            shipSnapshot = partySnapshot(ship);
            shipSnapshot.put("source_type", sourceType).put("source_party_id", shipPartyId);
            shipBranchId = "";
        }
        Map<String, JSONObject> itemUpdates = new HashMap<>(), allocUpdates = new HashMap<>();
        JSONArray iu = p.optJSONArray("items"), au = p.optJSONArray("allocations");
        for (int i = 0; iu != null && i < iu.length(); i++) { JSONObject r = iu.optJSONObject(i); if (r != null && !s(r, "id").isEmpty()) itemUpdates.put(s(r, "id"), r); }
        for (int i = 0; au != null && i < au.length(); i++) { JSONObject r = au.optJSONObject(i); if (r != null && !s(r, "id").isEmpty()) allocUpdates.put(s(r, "id"), r); }
        boolean refresh = truthy(p, "refresh_master_data", true);
        List<JSONObject> items = live("supply_purchase_order_items?select=*&purchase_order_id=eq." + poId + "&order=created_at.asc&limit=1000");
        List<JSONObject> sources = live("supply_purchase_order_sources?select=*&purchase_order_id=eq." + poId + "&order=created_at.asc&limit=10000");
        Map<String, List<JSONObject>> sourcesByItem = new HashMap<>();
        for (JSONObject src : sources) sourcesByItem.computeIfAbsent(s(src, "purchase_order_item_id"), k -> new ArrayList<>()).add(src);
        // R35 / R37b: a changed line quantity (allocations untouched) goes to the Customer Order allocation(s):
        // one source takes the new quantity, several sources take the difference on the last allocation.
        for (JSONObject item : items) {
            String iid = s(item, "id");
            JSONObject upd = itemUpdates.get(iid);
            List<JSONObject> itemSources = sourcesByItem.get(iid);
            if (upd == null || itemSources == null || itemSources.isEmpty() || !upd.has("quantity") || s(upd, "quantity").isEmpty()) continue;
            double requested = r3(num(upd.opt("quantity"))), currentSum = 0;
            boolean touched = false;
            for (JSONObject x : itemSources) {
                currentSum += num(x, "allocated_qty");
                JSONObject au2 = allocUpdates.get(s(x, "id"));
                if (au2 != null && Math.abs(num(au2.opt("allocated_qty")) - num(x, "allocated_qty")) > 0.000001) touched = true;
            }
            currentSum = r3(currentSum);
            if (touched || Math.abs(requested - currentSum) <= 0.000001) continue;
            if (requested <= 0) throw new Rule("Purchase Order line quantity must be greater than zero. To remove an order from the PO use 'Remove' in PO Source Allocations.");
            if (itemSources.size() == 1) allocUpdates.put(s(itemSources.get(0), "id"), new JSONObject().put("id", s(itemSources.get(0), "id")).put("allocated_qty", requested));
            else {
                JSONObject last = itemSources.get(itemSources.size() - 1);
                double newLast = r3(num(last, "allocated_qty") + requested - currentSum);
                if (newLast <= 0) throw new Rule("Line " + first(s(item, "item_no"), iid) + ": the reduction is larger than the last Customer Order allocation. Edit the individual allocations in PO Source Allocations instead.");
                allocUpdates.put(s(last, "id"), new JSONObject().put("id", s(last, "id")).put("allocated_qty", newLast));
            }
        }
        boolean rmPo = "RAW_MATERIAL".equals(poType);
        List<JSONObject> stageRows = live((rmPo ? "supply_rm_purchase_orders" : "supply_forging_orders") + "?select=*&purchase_order_id=eq." + poId + "&limit=10000");
        Set<String> stageIds = new HashSet<>();
        for (JSONObject st : stageRows) stageIds.add(s(st, "id"));
        Map<String, Double> receivedByStage = new HashMap<>();
        if (!stageIds.isEmpty()) {
            if (rmPo) for (JSONObject r : live("supply_rm_receipts?select=rm_purchase_order_id,received_qty_kg&rm_purchase_order_id=in.(" + inList(stageIds) + ")&limit=10000"))
                receivedByStage.merge(s(r, "rm_purchase_order_id"), num(r, "received_qty_kg"), Double::sum);
            else for (JSONObject r : live("supply_forging_receipts?select=forging_order_id,received_qty_pcs&forging_order_id=in.(" + inList(stageIds) + ")&limit=10000"))
                receivedByStage.merge(s(r, "forging_order_id"), num(r, "received_qty_pcs"), Double::sum);
        }

        Map<String, Object[]> linkedRevisions = new HashMap<>();
        if (refresh) {
            for (JSONObject item : items) {
                JSONObject part = get("parts", s(item, "part_id"));
                JSONObject rawRow = get("part_raw_material_details", s(item, "raw_material_detail_id"));
                JSONArray tech = item.optJSONArray("technical_data_snapshot");
                if (t(rawRow, "source_part_id").isEmpty()) {
                    for (int i = 0; tech != null && i < tech.length(); i++)
                        if ("Source Raw Material Detail ID".equals(s(tech.optJSONObject(i), "heading"))) throw new Rule("The PO raw-part link was removed. Cancel & Reissue to change the purchased part.");
                    continue;
                }
                if (!"ACTIVE".equals(s(rawRow, "status"))) throw new Rule("The PO raw-material link is no longer ACTIVE.");
                JSONObject[] ctx = resolveRawSource(part, rawRow, supplierId);
                String saved = null;
                for (int i = 0; tech != null && i < tech.length(); i++) if ("Source Raw Forging / Casting Part".equals(s(tech.optJSONObject(i), "heading"))) { saved = s(tech.optJSONObject(i), "value"); break; }
                if (saved != null && !saved.isEmpty() && !saved.equals(s(ctx[0], "part_number")) && !saved.equals(s(ctx[0], "fsi_part_number")))
                    throw new Rule("The linked raw part has changed. Cancel & Reissue to change the purchased part.");
                String uom = first(s(item, "uom"), "NOS");
                double price = effectiveCurrentPrice(part, rawRow, supplierId, today, uom);
                if (price <= 0 || first(s(ctx[1], "hsn_sac_code"), s(ctx[0], "hsn_sac_code")).isEmpty())
                    throw new Rule("Linked raw part requires current supplier price and HSN/SAC before PO revision.");
                linkedRevisions.put(s(item, "id"), new Object[]{ctx[0], ctx[1], price, technicalDataSnapshot(rawRow, part), effectivePriceHistory(part, rawRow, supplierId, today, uom)});
            }
        }
        double subtotal = 0;
        List<JSONObject> revised = new ArrayList<>();
        for (JSONObject item : items) {
            String iid = s(item, "id");
            JSONObject upd = itemUpdates.containsKey(iid) ? itemUpdates.get(iid) : new JSONObject();
            List<JSONObject> itemSources = sourcesByItem.containsKey(iid) ? sourcesByItem.get(iid) : new ArrayList<>();
            Object[] lr = linkedRevisions.get(iid);
            double newSourceQty = 0;
            for (JSONObject src : itemSources) {
                String sid = s(src, "id");
                JSONObject su = allocUpdates.containsKey(sid) ? allocUpdates.get(sid) : new JSONObject();
                double qty = Math.max(su.has("allocated_qty") ? num(su.opt("allocated_qty")) : num(src, "allocated_qty"), 0);
                if (qty <= 0) throw new Rule("Every Purchase Order source allocation must be greater than zero.");
                List<JSONObject> stages = new ArrayList<>();
                for (JSONObject st : stageRows) if (s(st, "purchase_order_item_id").equals(iid) && s(st, "customer_order_id").equals(s(src, "customer_order_id"))) stages.add(st);
                double received = 0;
                for (JSONObject st : stages) received += receivedByStage.getOrDefault(s(st, "id"), 0.0);
                if (qty + 0.0001 < received) throw new Rule("Source allocation cannot be reduced below received quantity " + fmt(received, 3) + ".");
                if (Math.abs(qty - num(src, "allocated_qty")) > 0.000001) api.update("supply_purchase_order_sources", sid, new JSONObject().put("allocated_qty", r3(qty)));
                newSourceQty += qty;
                for (JSONObject st : stages) {
                    if (rmPo) {
                        api.update("supply_rm_purchase_orders", s(st, "id"), new JSONObject().put("ordered_qty_kg", r3(qty)).put("order_date", orderDate).put("expected_date", n(deliveryDate))
                            .put("rm_supplier_id", supplierId).put("supplier_order_no", raw(header, "po_number")));
                    } else {
                        double weight;
                        if (lr != null) {
                            JSONObject sr = (JSONObject) lr[1];
                            weight = num(sr, "gross_weight_kg"); if (weight == 0) weight = num(sr, "input_weight_kg"); if (weight == 0) weight = num(sr, "forging_weight_kg");
                        } else {
                            weight = num(item, "gross_weight_kg");
                            if (weight == 0) weight = num(get("supply_customer_orders", s(st, "customer_order_id")), "gross_weight_kg_snapshot");
                        }
                        api.update("supply_forging_orders", s(st, "id"), new JSONObject().put("order_qty_pcs", r3(qty)).put("required_rm_kg", r3(qty * weight)).put("order_date", orderDate)
                            .put("expected_date", n(deliveryDate)).put("forging_supplier_id", supplierId).put("supplier_order_no", raw(header, "po_number")));
                    }
                }
            }
            double qty = r3(!itemSources.isEmpty() ? newSourceQty : Math.max(upd.has("quantity") ? num(upd.opt("quantity")) : num(item, "quantity"), 0));
            double receivedItem = purchaseOrderItemReceivedQty(item, header);
            if (qty <= 0) throw new Rule("Purchase Order item quantity must be greater than zero.");
            if (qty + 0.0001 < receivedItem) throw new Rule("PO item " + first(s(item, "item_no"), iid) + " cannot be reduced below received quantity " + fmt(receivedItem, 3) + ".");
            JSONObject part = get("parts", s(item, "part_id"));
            JSONObject rawRow = get("part_raw_material_details", s(item, "raw_material_detail_id"));
            if (lr != null) { part = (JSONObject) lr[0]; rawRow = (JSONObject) lr[1]; }
            JSONObject grade = get("material_grades", first(s(rawRow, "material_grade_id"), s(item, "material_grade_id"), s(part, "material_grade_id")));
            String uom = first(s(item, "uom"), rmPo ? "KGS" : "NOS");
            double masterPrice = refresh ? currentPrice(s(part, "id"), supplierId, today, uom, s(rawRow, "id")) : 0;
            if (lr != null) masterPrice = (Double) lr[2];
            double unitPrice = Math.max(masterPrice > 0 ? masterPrice : (upd.has("unit_price") ? num(upd.opt("unit_price")) : num(item, "unit_price")), 0);
            String hsn = refresh ? first(t(rawRow, "hsn_sac_code"), t(part, "hsn_sac_code")) : (upd.has("hsn_sac_code") ? t(upd, "hsn_sac_code") : t(item, "hsn_sac_code"));
            String itemNo = upd.has("item_no") ? t(upd, "item_no") : t(item, "item_no");
            if (refresh) itemNo = first(t(rawRow, rmPo ? "supplier_rm_item_code" : "supplier_forging_part_number"), first(t(part, "fsi_part_number"), itemNo));
            if (lr != null) itemNo = first(s(part, "part_number"), itemNo);
            if (itemNo.isEmpty() || hsn.isEmpty() || unitPrice <= 0) throw new Rule("Latest Part Master item identity, HSN/SAC and current price are required before saving the revised PO.");
            double gst = Math.max(upd.has("gst_percent") ? num(upd.opt("gst_percent")) : num(item, "gst_percent"), 0);
            double lineTotal = r2(qty * unitPrice), gstAmount = r2(lineTotal * gst / 100.0);
            subtotal += lineTotal;
            String description;
            Object technical, history;
            if (refresh) {
                String rmIdentity = Lookups.join(t(rawRow, "material_section_name"), first(t(grade, "grade_code"), t(grade, "grade_name")), first(t(rawRow, "section_size"), t(part, "section_size")));
                description = rmPo ? first(rmIdentity, s(part, "part_name"), "Raw Material") : first(s(rawRow, "supplier_forging_part_number"), s(part, "part_name"), "Forging");
                technical = technicalDataSnapshot(rawRow, part);
                history = head(priceHistoryForPo(s(part, "id"), supplierId, uom, s(rawRow, "id")), 250);
            } else {
                description = upd.has("item_description") ? s(upd, "item_description") : s(item, "item_description");
                technical = item.optJSONArray("technical_data_snapshot") == null ? new JSONArray() : item.optJSONArray("technical_data_snapshot");
                history = item.optJSONArray("price_history_snapshot") == null ? new JSONArray() : item.optJSONArray("price_history_snapshot");
            }
            if (lr != null) { technical = lr[3]; history = head((JSONArray) lr[4], 250); }
            String remarks = upd.has("remarks") ? t(upd, "remarks") : t(item, "remarks");
            JSONObject payload = new JSONObject().put("item_no", itemNo).put("fsi_part_number_snapshot", itemNo).put("hsn_sac_code", hsn).put("item_description", description)
                .put("rm_section", refresh ? raw(rawRow, "section_size") : raw(item, "rm_section")).put("quantity", qty).put("unit_price", unitPrice).put("gst_percent", gst)
                .put("gst_amount", gstAmount).put("line_total", lineTotal).put("technical_data_snapshot", technical).put("price_history_snapshot", history).put("remarks", n(remarks));
            if (lr != null) payload.put("material_grade_id", raw(rawRow, "material_grade_id")).put("forging_weight_kg", raw(rawRow, "forging_weight_kg"))
                .put("gross_weight_kg", raw(rawRow, "gross_weight_kg")).put("rm_section", raw(rawRow, "section_size")).put("supplier_item_code_snapshot", raw(part, "part_number"));
            revised.add(api.update("supply_purchase_order_items", iid, payload));
        }
        subtotal = r2(subtotal);
        double gstAmount = 0;
        for (JSONObject r : revised) gstAmount += num(r, "gst_amount");
        gstAmount = r2(gstAmount);
        String state = t(supplier, "state").toLowerCase(Locale.ROOT);
        boolean intra = state.isEmpty() || state.equals("maharashtra") || state.equals("mh");
        double cgst = intra ? r2(gstAmount / 2) : 0, sgst = intra ? r2(gstAmount / 2) : 0, igst = intra ? 0 : gstAmount;
        double other = Math.max(p.has("other_amount") ? num(p.opt("other_amount")) : num(header, "other_amount"), 0);
        JSONObject hp = new JSONObject().put("order_date", orderDate).put("delivery_date", n(deliveryDate)).put("company_branch_id", branchId).put("plant_snapshot", branchSnapshot(branch))
            .put("vendor_snapshot", partySnapshot(supplier)).put("ship_to_source_type", sourceType).put("ship_to_party_id", n(shipPartyId)).put("ship_to_branch_id", n(shipBranchId))
            .put("ship_to_snapshot", shipSnapshot);
        for (String k : new String[]{"ship_via", "incoterm", "payment_term", "quotation_reference", "old_po_reference", "remarks", "special_instructions"})
            hp.put(k, n(p.has(k) ? t(p, k) : t(header, k)));
        hp.put("quotation_date", n(parseDate(p.has("quotation_date") ? s(p, "quotation_date") : s(header, "quotation_date"))));
        hp.put("subtotal", subtotal).put("cgst_amount", cgst).put("sgst_amount", sgst).put("igst_amount", igst).put("other_amount", other).put("grand_total", r2(subtotal + cgst + sgst + igst + other))
            .put("currency", first(s(p, "currency"), s(header, "currency"), "INR").toUpperCase(Locale.ROOT))
            .put("approval_status", "PENDING_APPROVAL").put("status", "PENDING_APPROVAL").put("approver_employee_id", JSONObject.NULL).put("approved_at", JSONObject.NULL)
            .put("approval_remarks", JSONObject.NULL).put("submitted_by_employee_id", employeeId).put("submitted_at", nowUtc());
        JSONObject revisedHeader = api.update("supply_purchase_orders", poId, hp);
        if (wasApproved) {
            List<JSONObject> conf = live("supply_po_confirmations?select=id,created_at&purchase_order_id=eq." + poId + "&order=created_at.desc&limit=1");
            if (!conf.isEmpty()) api.update("supply_po_confirmations", s(conf.get(0), "id"), new JSONObject().put("confirmation_status", "PENDING").put("requested_at", nowUtc())
                .put("confirmation_reference", JSONObject.NULL).put("confirmation_date", JSONObject.NULL).put("confirmed_delivery_date", JSONObject.NULL)
                .put("remarks", "PO revised after approval; supplier acknowledgement will be requested again after re-approval."));
        }
        return new JSONObject().put("header", revisedHeader).put("reapproval_required", wasApproved);
    }

    // ================================================================== R39 · PO amendment (web R37b, supply_chain_service)
    static final String[] AMENDABLE_HEADER_FIELDS = {"delivery_date", "payment_term", "incoterm", "ship_via", "other_amount", "quotation_reference", "quotation_date", "remarks", "special_instructions"};

    /** po_display_number: "PD9131000096 · Amd 2" for an amended PO, the plain PO number otherwise. */
    static String poDisplayNumber(JSONObject header) {
        String number = s(header, "po_number");
        int amd = (int) Math.round(num(header, "amendment_no"));
        return amd > 0 && !number.isEmpty() ? number + " \u00b7 Amd " + amd : number;
    }

    /** purchase_order_amendments: amendment register (oldest first) with line before / after; PENDING turns APPROVED once the PO is approved later. */
    List<JSONObject> purchaseOrderAmendments(String poId, JSONObject header) {
        List<JSONObject> out = new ArrayList<>();
        List<JSONObject> rows;
        try { rows = live("supply_po_amendments?select=*&purchase_order_id=eq." + Api.enc(poId) + "&order=amendment_no.asc&limit=500"); } catch (Exception e) { return out; }
        String approvedAt = s(header, "approved_at");
        boolean approved = "APPROVED".equals(up(header, "approval_status"));
        for (JSONObject row : rows) {
            try {
                JSONObject item = new JSONObject(row.toString());
                List<JSONObject> lines;
                try { lines = live("supply_po_amendment_lines?select=*&amendment_id=eq." + Api.enc(s(row, "id")) + "&order=line_no.asc&limit=500"); } catch (Exception e) { lines = new ArrayList<>(); }
                JSONArray arr = new JSONArray();
                for (JSONObject l : lines) arr.put(l);
                item.put("lines", arr);
                String status = first(s(item, "status"), "PENDING_APPROVAL").toUpperCase(Locale.ROOT);
                if ("PENDING_APPROVAL".equals(status) && approved && !approvedAt.isEmpty() && approvedAt.compareTo(s(item, "created_at")) >= 0) status = "APPROVED";
                item.put("status", status);
                out.add(item);
            } catch (Exception ignored) { }
        }
        return out;
    }

    /** amendment_price_suggestion: price-history revision effective on the Effective Date (else the latest) of the line's Supplier + Part + RM record. */
    JSONObject amendmentPriceSuggestion(JSONObject header, JSONObject item, String effectiveDate) throws Exception {
        String supplierId = s(header, "supplier_id");
        JSONObject part = get("parts", s(item, "part_id"));
        JSONObject raw = get("part_raw_material_details", s(item, "raw_material_detail_id"));
        if (supplierId.isEmpty() || empty(part)) return new JSONObject();
        if (!t(raw, "source_part_id").isEmpty()) { JSONObject[] ctx = resolveRawSource(part, raw, supplierId); part = ctx[0]; raw = ctx[1]; }
        String uom = s(item, "uom");
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject r : priceHistory(s(part, "id"), supplierId, uom.isEmpty() ? null : uom, s(raw, "id"))) if (!s(r, "start_date").isEmpty()) rows.add(r);
        if (rows.isEmpty()) return new JSONObject();
        String target = parseDate(effectiveDate);
        if (target == null) target = LocalDate.now().toString();
        List<JSONObject> covering = new ArrayList<>();
        for (JSONObject r : rows) {
            String st = d10(s(r, "start_date")), en = d10(s(r, "end_date"));
            if (st.compareTo(target) <= 0 && (en.isEmpty() || target.compareTo(en) <= 0)) covering.add(r);
        }
        List<JSONObject> pool = covering.isEmpty() ? rows : covering;
        pool.sort((x, y) -> { int c = s(y, "start_date").compareTo(s(x, "start_date")); return c != 0 ? c : s(y, "updated_at").compareTo(s(x, "updated_at")); });
        JSONObject best = pool.get(0);
        return new JSONObject().put("price", num(best, "price")).put("start_date", d10(s(best, "start_date"))).put("end_date", n(d10(s(best, "end_date"))))
            .put("remarks", s(best, "remarks")).put("covering", !covering.isEmpty()).put("currency", first(s(best, "currency"), "INR")).put("uom", first(s(best, "uom"), uom));
    }

    private static Object amendValue(String key, Object v) {
        if (v == null || v == JSONObject.NULL) return key.equals("other_amount") ? (Object) 0.0 : null;
        if (key.equals("delivery_date") || key.equals("quotation_date")) return parseDate(String.valueOf(v));
        if (key.equals("other_amount")) { try { return r2(Double.parseDouble(String.valueOf(v).trim().isEmpty() ? "0" : String.valueOf(v).trim())); } catch (Exception e) { return 0.0; } }
        String t = String.valueOf(v).trim();
        return t.isEmpty() || "null".equals(t) ? null : t;
    }

    /**
     * amend_purchase_order (R37b): payload {reason, effective_date, lines:[{id, unit_price, quantity}], optional AMENDABLE_HEADER_FIELDS}.
     * PO number stays; amendment no = previous + 1. Lines revised through updatePurchaseOrder (refresh_master_data=false, R35 rules:
     * quantity to the Customer Order allocation, never below received; PO back to approval, approved PO needs supplier re-confirmation).
     * A changed price goes to part_supplier_price_history from the Effective Date; amendment + line before / after are stored.
     */
    JSONObject amendPurchaseOrder(String poId, JSONObject p) throws Exception {
        String reason = t(p, "reason");
        if (reason.isEmpty()) throw new Rule("Amendment Reason is required.");
        String effective = parseDate(s(p, "effective_date"));
        if (effective == null) throw new Rule("Amendment Effective Date is required (dd-mm-yyyy).");
        JSONObject header = get("supply_purchase_orders", poId);
        if (empty(header)) throw new Rule("Purchase Order was not found.");
        if ("CANCELLED".equals(up(header, "status"))) throw new Rule("A cancelled Purchase Order cannot be amended. Use Cancel & Reissue.");
        List<JSONObject> existing;
        try { existing = new ArrayList<>(list(api.rows("supply_po_amendments?select=amendment_no&purchase_order_id=eq." + Api.enc(poId) + "&limit=500"))); }
        catch (Exception e) { throw new Rule("PO Amendment tables are not installed yet. Run the R37b Supabase update (20261027100000_qcms_r37b_po_amendment.sql) and try again."); }
        int amendmentNo = (int) Math.round(num(header, "amendment_no"));
        for (JSONObject r : existing) amendmentNo = Math.max(amendmentNo, (int) Math.round(num(r, "amendment_no")));
        amendmentNo += 1;

        Map<String, JSONObject> items = new LinkedHashMap<>();
        for (JSONObject r : live("supply_purchase_order_items?select=*&purchase_order_id=eq." + poId + "&order=created_at.asc&limit=1000")) items.put(s(r, "id"), r);
        List<Object[]> changes = new ArrayList<>();   // item, oldPrice, newPrice, oldQty, newQty, received, priceChanged, lineNo
        JSONArray itemPayload = new JSONArray();
        JSONArray lines = p.optJSONArray("lines");
        for (int i = 0; lines != null && i < lines.length(); i++) {
            JSONObject line = lines.getJSONObject(i);
            JSONObject item = items.get(s(line, "id"));
            int index = i + 1;
            if (item == null) throw new Rule("Amendment line " + index + ": the PO line no longer exists. Refresh the page.");
            String label = first(s(item, "item_no"), s(item, "fsi_part_number_snapshot"), "line " + index);
            double oldPrice = Math.round(num(item, "unit_price") * 1e6) / 1e6, oldQty = r3(num(item, "quantity"));
            double newPrice = s(line, "unit_price").isEmpty() ? oldPrice : Math.round(num(line, "unit_price") * 1e6) / 1e6;
            double newQty = s(line, "quantity").isEmpty() ? oldQty : r3(num(line, "quantity"));
            if (newPrice <= 0) throw new Rule(label + ": amended Unit Price must be greater than zero.");
            if (newQty <= 0) throw new Rule(label + ": amended Quantity must be greater than zero.");
            double received = purchaseOrderItemReceivedQty(item, header);
            if (newQty + 0.0001 < received) throw new Rule(label + ": amended Quantity " + fmt(newQty, 3) + " cannot be below the quantity already received (" + fmt(received, 3) + ").");
            boolean priceChanged = Math.abs(newPrice - oldPrice) > 0.000001, qtyChanged = Math.abs(newQty - oldQty) > 0.0001;
            if (!priceChanged && !qtyChanged) continue;
            itemPayload.put(new JSONObject().put("id", s(item, "id")).put("unit_price", newPrice).put("quantity", newQty));
            changes.add(new Object[]{item, oldPrice, newPrice, oldQty, newQty, received, priceChanged, index});
        }
        JSONObject headerChanges = new JSONObject();
        JSONObject update = new JSONObject().put("refresh_master_data", false).put("items", itemPayload);
        for (String key : AMENDABLE_HEADER_FIELDS) {
            if (!p.has(key)) continue;
            Object nv = amendValue(key, p.opt(key)), ov = amendValue(key, header.opt(key));
            boolean same = nv == null ? ov == null : ov != null && String.valueOf(nv).equals(String.valueOf(ov));
            if (same) continue;
            headerChanges.put(key, new JSONObject().put("old", ov == null ? JSONObject.NULL : ov).put("new", nv == null ? JSONObject.NULL : nv));
            update.put(key, nv == null ? JSONObject.NULL : nv);
        }
        if (changes.isEmpty() && headerChanges.length() == 0) throw new Rule("Nothing was changed. Change a line price / quantity or a commercial field before saving the amendment.");

        JSONObject revision = updatePurchaseOrder(poId, update);
        String poNumber = s(header, "po_number"), supplierId = s(header, "supplier_id");
        String currency = first(s(header, "currency"), "INR").toUpperCase(Locale.ROOT);
        String note = "PO " + poNumber + " Amd " + amendmentNo + ": " + reason;
        List<String> warnings = new ArrayList<>();
        Map<String, String> priceRows = new HashMap<>();
        for (Object[] ch : changes) {
            if (!(Boolean) ch[6]) continue;
            JSONObject item = (JSONObject) ch[0];
            JSONObject part = get("parts", s(item, "part_id"));
            JSONObject raw = get("part_raw_material_details", s(item, "raw_material_detail_id"));
            if (!t(raw, "source_part_id").isEmpty()) { JSONObject[] ctx = resolveRawSource(part, raw, supplierId); part = ctx[0]; raw = ctx[1]; }
            if (s(part, "id").isEmpty()) { warnings.add(s(item, "item_no") + ": no Part Master link - price history not updated."); continue; }
            try {
                String uom = first(s(item, "uom"), "RAW_MATERIAL".equals(s(header, "po_type")) ? "KGS" : "NOS");
                JSONObject row = recordPurchasePrice(s(part, "id"), supplierId, s(raw, "id").isEmpty() ? null : s(raw, "id"), effective, (Double) ch[2], uom, currency, s(item, "id"), note);
                if (row != null) priceRows.put(s(item, "id"), s(row, "id"));
                JSONArray history = priceHistoryForPo(s(part, "id"), supplierId, s(item, "uom"), s(raw, "id"));
                api.update("supply_purchase_order_items", s(item, "id"), new JSONObject().put("price_history_snapshot", head(history, 250)));
            } catch (Exception e) {
                warnings.add(s(item, "item_no") + ": price history not updated - " + friendlyPoError(e));
            }
        }
        String today = LocalDate.now().toString();
        JSONObject amendment = api.insert("supply_po_amendments", new JSONObject().put("purchase_order_id", poId).put("amendment_no", amendmentNo).put("amendment_date", today)
            .put("effective_date", effective).put("reason", reason).put("header_changes", headerChanges).put("status", "PENDING_APPROVAL")
            .put("created_by_employee_id", n(api.employeeId)));
        JSONArray linesOut = new JSONArray();
        for (Object[] ch : changes) {
            JSONObject item = (JSONObject) ch[0];
            linesOut.put(api.insert("supply_po_amendment_lines", new JSONObject().put("amendment_id", s(amendment, "id")).put("purchase_order_item_id", s(item, "id"))
                .put("line_no", ch[7]).put("item_no", n(first(s(item, "item_no"), s(item, "fsi_part_number_snapshot")))).put("item_description", n(s(item, "item_description")))
                .put("uom", n(s(item, "uom"))).put("currency", currency).put("old_unit_price", ch[1]).put("new_unit_price", ch[2]).put("old_quantity", ch[3])
                .put("new_quantity", ch[4]).put("received_qty", ch[5]).put("price_history_id", n(priceRows.get(s(item, "id"))))));
        }
        JSONObject headerAfter = api.update("supply_purchase_orders", poId, new JSONObject().put("amendment_no", amendmentNo).put("amendment_date", today)
            .put("amendment_effective_date", effective).put("amendment_reason", reason));
        JSONArray warn = new JSONArray();
        for (String w : warnings) warn.put(w);
        return new JSONObject().put("header", headerAfter).put("amendment", amendment).put("lines", linesOut).put("amendment_no", amendmentNo)
            .put("display_number", poDisplayNumber(empty(headerAfter) ? new JSONObject().put("po_number", poNumber).put("amendment_no", amendmentNo) : headerAfter))
            .put("warnings", warn).put("reapproval_required", true).put("revision", revision);
    }

    // ================================================================== opening stock
    JSONObject saveOpeningStock(JSONObject payload, String recordId) throws Exception {
        JSONObject p = copy(payload);
        String partId = s(p, "part_id");
        if (partId.isEmpty() || empty(get("parts", partId))) throw new Rule("Select a valid Part Number for Opening Stock.");
        String stage = up(p, "stage");
        if (!Arrays.asList(OPENING_STAGES).contains(stage)) throw new Rule("Select a valid Supply Chain stage for Opening Stock.");
        String location = first(t(p, "stock_location"), "FSI").toUpperCase(Locale.ROOT);
        if (!Arrays.asList("FSI", "SUPPLIER", "VENDOR").contains(location)) throw new Rule("Stock Location must be FSI, SUPPLIER or VENDOR.");
        p.put("stock_location", location);
        if ("FSI".equals(location)) p.put("location_party_id", JSONObject.NULL);
        else if (t(p, "location_party_id").isEmpty()) throw new Rule("Select the " + ("SUPPLIER".equals(location) ? "Supplier" : "Vendor") + " where this opening stock is lying.");
        double pcs = Math.max(num(p, "quantity_pcs"), 0);
        double available = Math.max(p.isNull("available_quantity_pcs") ? pcs : num(p, "available_quantity_pcs"), 0);
        double kg = Math.max(num(p, "quantity_kg"), 0);
        if (pcs <= 0 && kg <= 0) throw new Rule("Opening Stock must contain a positive quantity in pieces or kilograms.");
        if (available > pcs && pcs > 0) throw new Rule("Opening Stock available quantity cannot exceed the recorded opening quantity.");
        p.put("stage", stage).put("quantity_pcs", pcs).put("available_quantity_pcs", available).put("quantity_kg", kg).put("status", first(s(p, "status"), "ACTIVE").toUpperCase(Locale.ROOT));
        return recordId == null || recordId.isEmpty() ? api.insert("supply_opening_stock", p) : api.update("supply_opening_stock", recordId, p);
    }
}
