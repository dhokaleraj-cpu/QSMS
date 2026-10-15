package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Purchase Order print data, exactly as the website builds it:
 * SupplyChainService.purchase_order (+ approver enrichment), purchase_order_items_for_print,
 * core/print_designer (saved layout in master_value_catalog) and core/po_print_ui.effective_options.
 */
final class SndData {
    private SndData() { }

    /** core/po_print_ui.SECTION_OPTIONS (flag, label) in print order. */
    static final String[][] SECTIONS = {
        {"show_plant", "Plant / Company Branch"}, {"show_vendor", "Vendor"}, {"show_reference", "Reference Details"},
        {"show_old_po", "Old PO Details"}, {"show_ship_to", "Ship To"}, {"show_source_reference", "PO Source Reference"},
        {"show_technical", "RM Details & Technical Data"}, {"show_price_history", "Price Revision History"},
        {"show_special_instructions", "Comments / Special Instructions"}, {"show_approval_stamp", "Approval Stamp"}};

    static final String LAYOUT_KEY = "qcms.print.layout.PURCHASE_ORDER";

    /** A PO loaded for print / email. */
    static final class Po {
        JSONObject header = new JSONObject();
        List<JSONObject> items = new ArrayList<>();
        JSONObject supplier = new JSONObject();
        JSONObject layout = defaultLayout();
        JSONArray attachments = new JSONArray();

        String id() { return s(header, "id"); }
        String number() { return s(header, "po_number"); }
        boolean approved() { return "APPROVED".equalsIgnoreCase(s(header, "approval_status")); }
        boolean cancelled() { return "CANCELLED".equalsIgnoreCase(s(header, "status")); }
        /** Workflow event used to send the PO to the supplier (app_pages/supply_chain.py). */
        String releaseEvent() { return "RAW_MATERIAL".equalsIgnoreCase(s(header, "po_type")) ? "RM_PO_CREATED" : "FORGING_PO_CREATED"; }
        String releaseNextStage() { return "RM_PO_CREATED".equals(releaseEvent()) ? "Raw Material Receipt" : "Forging Receipt"; }
        String fileName() { return (number().isEmpty() ? "Purchase_Order" : number()) + ".pdf"; }
    }

    // ------------------------------------------------------------------ small value helpers (like _s / _n)
    static String s(JSONObject o, String key) {
        if (o == null || key == null) return "";
        Object v = o.opt(key);
        if (v == null || v == JSONObject.NULL) return "";
        String t = String.valueOf(v).trim();
        if ("null".equals(t)) return "";
        return t.replaceAll("\\s+", " ");
    }

    static String clean(Object v) {
        if (v == null || v == JSONObject.NULL) return "";
        String t = String.valueOf(v).trim();
        return "null".equals(t) ? "" : t.replaceAll("\\s+", " ");
    }

    static double n(JSONObject o, String key) {
        if (o == null) return 0;
        Object v = o.opt(key);
        if (v == null || v == JSONObject.NULL) return 0;
        if (v instanceof Number) return ((Number) v).doubleValue();
        try { return Double.parseDouble(String.valueOf(v).trim()); } catch (Exception e) { return 0; }
    }

    static boolean has(JSONObject o, String key) {
        return o != null && o.has(key) && !o.isNull(key) && !String.valueOf(o.opt(key)).trim().isEmpty();
    }

    static JSONObject obj(JSONObject o, String key) {
        Object v = o == null ? null : o.opt(key);
        if (v instanceof JSONObject) return (JSONObject) v;
        if (v instanceof String) {
            try { return new JSONObject((String) v); } catch (Exception ignored) { }
        }
        return null;
    }

    static JSONArray arr(JSONObject o, String key) {
        Object v = o == null ? null : o.opt(key);
        if (v instanceof JSONArray) return (JSONArray) v;
        if (v instanceof String) {
            try { return new JSONArray((String) v); } catch (Exception ignored) { }
        }
        return new JSONArray();
    }

    static String inList(Set<String> ids) {
        StringBuilder b = new StringBuilder();
        for (String id : ids) {
            if (id == null || id.isEmpty()) continue;
            if (b.length() > 0) b.append(',');
            b.append(id);
        }
        return b.toString();
    }

    // ------------------------------------------------------------------ print layout (core/print_designer.py)
    private static final Pattern HEX = Pattern.compile("^#[0-9A-Fa-f]{6}$");
    private static final String[] PO_FLAGS = {"show_plant", "show_vendor", "show_reference", "show_old_po", "show_ship_to",
        "show_source_reference", "show_technical", "show_price_history", "show_special_instructions"};
    private static final Map<String, String[]> PRESETS = new HashMap<>();
    static {
        // accent, bar, rule, head_fill, label_fill, remark, remark_fill, conclusion
        PRESETS.put("B1", new String[]{"#0B6E70", "fill", "#C9D6D6", "", "", "#9A3412", "", "#166534"});
        PRESETS.put("B2", new String[]{"#0B6E70", "underline", "#C9D6D6", "", "", "#9A3412", "", "#166534"});
        PRESETS.put("B3", new String[]{"#0B6E70", "outline", "#C9D6D6", "", "", "#9A3412", "", "#166534"});
        PRESETS.put("B4", new String[]{"#334155", "fill", "#CBD5E1", "", "#F1F5F9", "#0B6E70", "", "#166534"});
        PRESETS.put("B5", new String[]{"#0B6E70", "fill", "#C9D6D6", "#EAF4F4", "#F3F8F8", "#9A3412", "#FFF7ED", "#166534"});
    }
    private static final String[] PRESET_KEYS = {"accent", "bar", "rule", "head_fill", "label_fill", "remark", "remark_fill", "conclusion"};

    private static void applyPreset(JSONObject base, String code) {
        String[] p = PRESETS.get(code);
        if (p == null) return;
        try {
            for (int i = 0; i < PRESET_KEYS.length; i++) base.put(PRESET_KEYS[i], p[i]);
            base.put("preset", code);
        } catch (Exception ignored) { }
    }

    /** print_designer.default_layout("PURCHASE_ORDER"). */
    static JSONObject defaultLayout() {
        JSONObject l = new JSONObject();
        try {
            applyPreset(l, "B5");
            l.put("labels", new JSONObject());
            l.put("company_name", "");
            l.put("footer_text", "");
            l.put("title", "PURCHASE ORDER");
            l.put("show_approval_stamp", true);
            for (String f : PO_FLAGS) l.put(f, true);
        } catch (Exception ignored) { }
        return l;
    }

    /** print_designer.normalize_layout: merge the saved layout over the defaults, drop invalid values. */
    static JSONObject normalizeLayout(JSONObject data) {
        JSONObject base = defaultLayout();
        if (data == null) return base;
        try {
            String preset = s(data, "preset").toUpperCase(Locale.ROOT);
            if (PRESETS.containsKey(preset) && !preset.equals(base.optString("preset"))) applyPreset(base, preset);
            Iterator<String> it = data.keys();
            while (it.hasNext()) {
                String key = it.next();
                Object value = data.opt(key);
                boolean isNull = value == null || value == JSONObject.NULL;
                if (key.equals("accent") || key.equals("rule") || key.equals("remark") || key.equals("conclusion")) {
                    if (value instanceof String && HEX.matcher((String) value).matches()) base.put(key, ((String) value).toUpperCase(Locale.ROOT));
                } else if (key.equals("head_fill") || key.equals("label_fill") || key.equals("remark_fill")) {
                    if (isNull || "".equals(value)) base.put(key, "");
                    else if (value instanceof String && HEX.matcher((String) value).matches()) base.put(key, ((String) value).toUpperCase(Locale.ROOT));
                } else if (key.equals("bar")) {
                    if ("fill".equals(value) || "underline".equals(value) || "outline".equals(value)) base.put(key, value);
                } else if (key.startsWith("show_")) {
                    base.put(key, truthy(value));
                } else if (key.equals("labels") && value instanceof JSONObject) {
                    JSONObject labels = new JSONObject();
                    JSONObject src = (JSONObject) value;
                    Iterator<String> li = src.keys();
                    while (li.hasNext()) {
                        String k = li.next();
                        String v = clean(src.opt(k));
                        if (!k.trim().isEmpty() && !v.isEmpty()) labels.put(k.trim(), String.valueOf(src.opt(k)).trim());
                    }
                    base.put("labels", labels);
                } else if (key.equals("title") || key.equals("company_name") || key.equals("footer_text")) {
                    String v = isNull ? "" : String.valueOf(value).trim();
                    base.put(key, v.length() > 120 ? v.substring(0, 120) : v);
                }
            }
        } catch (Exception ignored) { }
        return base;
    }

    /** Python bool(value) for JSON values. */
    static boolean truthy(Object v) {
        if (v == null || v == JSONObject.NULL) return false;
        if (v instanceof Boolean) return (Boolean) v;
        if (v instanceof Number) return ((Number) v).doubleValue() != 0;
        if (v instanceof String) return !((String) v).isEmpty();
        if (v instanceof JSONArray) return ((JSONArray) v).length() > 0;
        if (v instanceof JSONObject) return ((JSONObject) v).length() > 0;
        return true;
    }

    /** print_designer.read_layout: saved layout from master_value_catalog (or defaults). */
    static JSONObject loadLayout(Api api) {
        try {
            JSONArray rows = api.rows("master_value_catalog?select=value_text&field_key=eq." + Api.enc(LAYOUT_KEY)
                + "&status=eq.ACTIVE&order=last_used_at.desc&limit=1");
            if (rows.length() > 0) {
                String text = Lookups.j(rows.getJSONObject(0), "value_text");
                return normalizeLayout(text.isEmpty() ? new JSONObject() : new JSONObject(text));
            }
        } catch (Exception ignored) { }
        return defaultLayout();
    }

    /** po_print_ui.effective_options: this PO's own choice over the saved layout defaults. */
    static JSONObject effectiveOptions(JSONObject layout, JSONObject header) {
        JSONObject own = obj(header, "print_options");
        JSONObject out = new JSONObject();
        try {
            for (String[] sec : SECTIONS) {
                String f = sec[0];
                boolean v;
                if (own != null && own.has(f)) v = truthy(own.opt(f));
                else if (layout != null && layout.has(f)) v = truthy(layout.opt(f));
                else v = true;
                out.put(f, v);
            }
        } catch (Exception ignored) { }
        return out;
    }

    /** supply_chain_service.clean_print_options (only the known flags). */
    static JSONObject cleanOptions(JSONObject options) {
        JSONObject out = new JSONObject();
        if (options == null) return out;
        try {
            for (String[] sec : SECTIONS) if (options.has(sec[0])) out.put(sec[0], truthy(options.opt(sec[0])));
        } catch (Exception ignored) { }
        return out;
    }

    /** purchase_order_pdf_bytes: per-PO show_* flags override the saved layout. */
    static JSONObject printLayout(JSONObject layout, JSONObject options) {
        JSONObject l = normalizeLayout(layout == null ? new JSONObject() : layout);
        if (options != null && options.length() > 0) {
            try {
                Iterator<String> it = options.keys();
                while (it.hasNext()) {
                    String k = it.next();
                    if (k.startsWith("show_")) l.put(k, truthy(options.opt(k)));
                }
            } catch (Exception ignored) { }
        }
        return l;
    }

    // ------------------------------------------------------------------ load one PO for print
    static Po load(Api api, String poId) throws Exception {
        Po po = new Po();
        JSONArray h = api.rows("supply_purchase_orders?select=*&id=eq." + Api.enc(poId));
        if (h.length() == 0) throw new Api.ApiException(404, "Purchase Order not found or not visible for your role.");
        po.header = enrichApprover(api, h.getJSONObject(0));
        po.layout = loadLayout(api);
        String supplierId = s(po.header, "supplier_id");
        if (!supplierId.isEmpty()) {
            JSONArray sp = api.rows("parties?select=*&id=eq." + Api.enc(supplierId));
            if (sp.length() > 0) po.supplier = sp.getJSONObject(0);
        }
        po.items = itemsForPrint(api, po.header);
        try {
            po.attachments = api.rows("document_attachments?select=id,document_type,document_title,file_name,object_path,mime_type,size_bytes,created_at"
                + "&entity_type=eq.SUPPLY_PURCHASE_ORDER&entity_id=eq." + Api.enc(poId) + "&status=eq.ACTIVE&order=created_at.asc&limit=25");
        } catch (Exception ignored) { po.attachments = new JSONArray(); }
        return po;
    }

    /** SupplyChainService._enrich_purchase_order_approver. */
    static JSONObject enrichApprover(Api api, JSONObject row) {
        JSONObject item;
        try { item = new JSONObject(row.toString()); } catch (Exception e) { return row; }
        try {
            String employeeId = s(item, "approver_employee_id");
            JSONObject employee = null;
            if (!employeeId.isEmpty()) {
                JSONArray e = api.rows("employees?select=id,first_name,last_name,employee_code,department,designation&id=eq." + Api.enc(employeeId));
                if (e.length() > 0) employee = e.getJSONObject(0);
            } else if ("APPROVED".equalsIgnoreCase(s(item, "approval_status"))) {
                String profileId = s(item, "updated_by");
                if (!profileId.isEmpty()) {
                    JSONArray e = api.rows("employees?select=id,first_name,last_name,employee_code,department,designation&profile_id=eq."
                        + Api.enc(profileId) + "&status=eq.ACTIVE&limit=2");
                    if (e.length() > 0) {
                        employee = e.getJSONObject(0);
                        if (!s(employee, "id").isEmpty()) item.put("approver_employee_id", s(employee, "id"));
                    }
                }
            }
            if (employee == null) return item;
            String name = (s(employee, "first_name") + " " + s(employee, "last_name")).trim();
            item.put("approver_employee_name", name);
            item.put("approver_employee_code", s(employee, "employee_code"));
            item.put("approver_department", s(employee, "department"));
            item.put("approver_designation", s(employee, "designation"));
        } catch (Exception ignored) { }
        return item;
    }

    /** SupplyChainService.purchase_order_items_for_print. */
    static List<JSONObject> itemsForPrint(Api api, JSONObject header) throws Exception {
        String poId = s(header, "id");
        String supplierId = s(header, "supplier_id");
        JSONArray rawItems = api.rows("supply_purchase_order_items?select=*&purchase_order_id=eq." + Api.enc(poId) + "&order=created_at.asc&limit=10000");
        JSONArray sources = new JSONArray();
        try {
            sources = api.rows("supply_purchase_order_sources?select=*&purchase_order_id=eq." + Api.enc(poId) + "&order=created_at.asc&limit=10000");
        } catch (Exception ignored) { }
        List<JSONObject> items = new ArrayList<>();
        for (int i = 0; i < rawItems.length(); i++) items.add(new JSONObject(rawItems.getJSONObject(i).toString()));

        Map<String, List<JSONObject>> byItem = new LinkedHashMap<>();
        Set<String> orderIds = new LinkedHashSet<>();
        for (int i = 0; i < sources.length(); i++) {
            JSONObject src = sources.getJSONObject(i);
            String key = s(src, "purchase_order_item_id");
            List<JSONObject> list = byItem.get(key);
            if (list == null) { list = new ArrayList<>(); byItem.put(key, list); }
            list.add(src);
            orderIds.add(s(src, "customer_order_id"));
        }
        Set<String> partIds = new LinkedHashSet<>();
        for (JSONObject it : items) {
            if (!s(it, "customer_order_id").isEmpty()) orderIds.add(s(it, "customer_order_id"));
            if (!s(it, "part_id").isEmpty()) partIds.add(s(it, "part_id"));
        }
        orderIds.remove("");
        Map<String, JSONObject> orders = new HashMap<>();
        if (!orderIds.isEmpty()) {
            JSONArray o = api.rows("supply_customer_orders?select=id,customer_id,part_id,customer_order_no,master_reference_no,order_position,customer_delivery_date&id=in.(" + inList(orderIds) + ")");
            for (int i = 0; i < o.length(); i++) {
                JSONObject r = o.getJSONObject(i);
                orders.put(s(r, "id"), r);
                if (!s(r, "part_id").isEmpty()) partIds.add(s(r, "part_id"));
            }
        }
        partIds.remove("");
        Map<String, JSONObject> parts = new HashMap<>();
        if (!partIds.isEmpty()) {
            JSONArray p = api.rows("parts?select=id,part_number,part_name,fsi_part_number&id=in.(" + inList(partIds) + ")");
            for (int i = 0; i < p.length(); i++) parts.put(s(p.getJSONObject(i), "id"), p.getJSONObject(i));
        }
        Map<String, JSONArray> historyCache = new HashMap<>();

        for (JSONObject item : items) {
            String partId = s(item, "part_id");
            String rawId = s(item, "raw_material_detail_id");
            boolean linkedSnapshot = false;
            JSONArray tech = arr(item, "technical_data_snapshot");
            for (int i = 0; i < tech.length(); i++) {
                JSONObject t = tech.optJSONObject(i);
                if (t != null && "Source Raw Material Detail ID".equals(t.optString("heading"))) { linkedSnapshot = true; break; }
            }
            if (!partId.isEmpty() && !supplierId.isEmpty() && !linkedSnapshot) {
                try {
                    JSONArray history = priceHistoryForPo(api, historyCache, partId, supplierId, s(item, "uom"), rawId);
                    if (history.length() > 0) item.put("price_history_snapshot", history);
                } catch (Exception ignored) { }
            }
            List<JSONObject> itemSources = byItem.get(s(item, "id"));
            if (itemSources == null || itemSources.isEmpty()) {
                itemSources = new ArrayList<>();
                if (!s(item, "customer_order_id").isEmpty()) {
                    JSONObject fb = new JSONObject();
                    fb.put("customer_order_id", s(item, "customer_order_id"));
                    fb.put("allocated_qty", item.opt("quantity"));
                    fb.put("allocation_uom", item.opt("uom"));
                    itemSources.add(fb);
                }
            }
            JSONArray customerSources = new JSONArray();
            List<String> descriptions = new ArrayList<>();
            for (JSONObject source : itemSources) {
                JSONObject order = orders.get(s(source, "customer_order_id"));
                if (order == null) order = new JSONObject();
                String pid = s(order, "part_id").isEmpty() ? partId : s(order, "part_id");
                JSONObject part = parts.get(pid);
                if (part == null) part = new JSONObject();
                JSONObject row = new JSONObject();
                row.put("customer_po_number", s(order, "customer_order_no").isEmpty() ? s(order, "master_reference_no") : s(order, "customer_order_no"));
                row.put("po_position", s(order, "order_position"));
                row.put("part_number", s(part, "part_number").isEmpty() ? s(item, "original_part_number_snapshot") : s(part, "part_number"));
                row.put("part_description", s(part, "part_name"));
                row.put("fsi_part_number", s(part, "fsi_part_number"));
                row.put("schedule_reference", s(order, "master_reference_no"));
                double alloc = n(source, "allocated_qty");
                row.put("quantity", alloc != 0 ? alloc : n(item, "quantity"));
                row.put("uom", s(source, "allocation_uom").isEmpty() ? s(item, "uom") : s(source, "allocation_uom"));
                customerSources.put(row);
                String desc = s(part, "part_name");
                if (!desc.isEmpty() && !descriptions.contains(desc)) descriptions.add(desc);
            }
            item.put("customer_source_rows", customerSources);
            JSONObject partMaster = parts.get(partId);
            String fallback = partMaster == null ? "" : s(partMaster, "part_name");
            if (!fallback.isEmpty() && !descriptions.contains(fallback)) descriptions.add(fallback);
            String joined = String.join(" / ", descriptions);
            item.put("part_description_master", linkedSnapshot ? s(item, "item_description") : (joined.isEmpty() ? s(item, "item_description") : joined));
        }
        return items;
    }

    /** SupplyChainService.price_history + price_history_for_po (oldest first). */
    private static JSONArray priceHistoryForPo(Api api, Map<String, JSONArray> cache, String partId, String supplierId, String uom, String rawId) throws Exception {
        String key = partId + "|" + supplierId;
        JSONArray all = cache.get(key);
        if (all == null) {
            all = api.rows("part_supplier_price_history?select=*&part_id=eq." + Api.enc(partId) + "&supplier_id=eq." + Api.enc(supplierId)
                + "&order=start_date.desc&limit=5000");
            cache.put(key, all);
        }
        List<JSONObject> rows = new ArrayList<>();
        for (int i = 0; i < all.length(); i++) {
            JSONObject r = all.getJSONObject(i);
            String st = s(r, "status").isEmpty() ? "ACTIVE" : s(r, "status").toUpperCase(Locale.ROOT);
            if (st.equals("DELETED") || st.equals("CANCELLED")) continue;
            rows.add(r);
        }
        if (!rawId.isEmpty()) {
            List<JSONObject> exact = new ArrayList<>();
            for (JSONObject r : rows) if (rawId.equals(s(r, "raw_material_detail_id"))) exact.add(r);
            if (!exact.isEmpty()) rows = exact;
        }
        List<JSONObject> same = new ArrayList<>();
        for (JSONObject r : rows) if (uom.isEmpty() || s(r, "uom").equalsIgnoreCase(uom)) same.add(r);
        if (!same.isEmpty()) rows = same;
        Collections.sort(rows, (x, y) -> {
            int c = s(x, "start_date").compareTo(s(y, "start_date"));
            if (c != 0) return c;
            String ex = s(x, "end_date").isEmpty() ? "9999-12-31" : s(x, "end_date");
            String ey = s(y, "end_date").isEmpty() ? "9999-12-31" : s(y, "end_date");
            c = ex.compareTo(ey);
            if (c != 0) return c;
            return s(x, "id").compareTo(s(y, "id"));
        });
        JSONArray out = new JSONArray();
        for (JSONObject r : rows) {
            JSONObject o = new JSONObject();
            o.put("start_date", r.opt("start_date"));
            o.put("end_date", r.opt("end_date"));
            o.put("price", r.opt("price"));
            o.put("currency", s(r, "currency").isEmpty() ? "INR" : s(r, "currency"));
            o.put("uom", s(r, "uom").isEmpty() ? uom : s(r, "uom"));
            o.put("remarks", s(r, "remarks"));
            o.put("status", s(r, "status").isEmpty() ? "ACTIVE" : s(r, "status"));
            out.put(o);
        }
        return out;
    }
}
