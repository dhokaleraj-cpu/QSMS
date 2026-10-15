package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeSet;

/**
 * Supply Chain Traceability data (website supply_chain.render_traceability + SupplyChainService
 * order_context / genealogy_context / timeline / supplier_balances) and the QSMS heat genealogy
 * search (qsms_trace_search over v_qsms_trace_events). Background thread only.
 */
final class GenTrace {
    private GenTrace() { }

    static final String[][] STAGE_TABLES = {
        // table, stage, date, reference, qty, unit
        {"supply_rm_purchase_orders", "RM Procurement", "order_date", "supplier_order_no", "ordered_qty_kg", "kg"},
        {"supply_rm_receipts", "Material Inward / RM Receipt", "receipt_date", "receipt_number", "received_qty_kg", "kg"},
        {"supply_rm_dispatches", "RM to Forging", "dispatch_date", "dispatch_number", "qty_kg", "kg"},
        {"supply_forging_orders", "Forging Order", "order_date", "supplier_order_no", "order_qty_pcs", "pcs"},
        {"supply_forging_receipts", "Forging Receipt", "receipt_date", "receipt_number", "received_qty_pcs", "pcs"}};

    /** Masters used by the labels (SupplyChainService.master_maps: ACTIVE parts / parties / grades). */
    static final class Masters {
        final Map<String, JSONObject> parts = new HashMap<>(), parties = new HashMap<>(), grades = new HashMap<>(), employees = new HashMap<>();
    }

    static Masters masters(Api api) throws Exception {
        Masters m = new Masters();
        for (JSONObject r : GenUtil.big(api, "parts?select=*&status=eq.ACTIVE&order=part_number.asc&limit=5000")) m.parts.put(GenUtil.str(r.opt("id")), r);
        for (JSONObject r : GenUtil.big(api, "parties?select=*&status=eq.ACTIVE&order=party_name.asc&limit=5000")) m.parties.put(GenUtil.str(r.opt("id")), r);
        for (JSONObject r : GenUtil.big(api, "material_grades?select=*&status=eq.ACTIVE&order=grade_code.asc&limit=3000")) m.grades.put(GenUtil.str(r.opt("id")), r);
        try {
            for (JSONObject r : GenUtil.big(api, "employees?select=id,employee_code,first_name,last_name&limit=5000")) m.employees.put(GenUtil.str(r.opt("id")), r);
        } catch (Exception ignored) { }
        return m;
    }

    static String clean(Object v) {
        String s = GenUtil.str(v).trim();
        return s.replaceAll("\\s+", " ");
    }

    static String join(Object... values) {
        List<String> out = new ArrayList<>();
        for (Object v : values) { String s = clean(v); if (!s.isEmpty()) out.add(s); }
        return String.join(" · ", out);
    }

    /** selection_labels.party_label (with status tag). */
    static String partyLabel(JSONObject r) {
        if (r == null || r.length() == 0) return "";
        List<String> loc = new ArrayList<>();
        for (String k : new String[]{"city", "state", "country"}) { String s = clean(r.opt(k)); if (!s.isEmpty()) loc.add(s); }
        return withStatus(join(r.opt("party_code"), r.opt("party_name"), String.join(", ", loc), r.opt("approval_status")), r);
    }

    static String withStatus(String label, JSONObject row) {
        String st = clean(GenUtil.or(row, "status", "record_status"));
        String tag = st.isEmpty() ? "" : "[" + st.replace('_', ' ').toUpperCase(Locale.ROOT) + "]";
        if (tag.isEmpty() || label.contains(tag)) return label;
        return label.isEmpty() ? tag : label + " " + tag;
    }

    static double number(Object v) { return GenUtil.n(v); }

    static String employeeLabel(Masters m, String id) {
        JSONObject r = m.employees.get(id == null ? "" : id);
        if (r == null) return "";
        String name = join(r.opt("first_name"), r.opt("last_name")).replace(" · ", " ");
        return name.isEmpty() ? GenUtil.str(r.opt("employee_code")) : name;
    }

    /** SupplyChainService.order_context */
    static LinkedHashMap<String, Object> context(JSONObject order, Masters m) {
        JSONObject part = m.parts.getOrDefault(GenUtil.str(order.opt("part_id")), new JSONObject());
        JSONObject customer = m.parties.getOrDefault(GenUtil.str(order.opt("customer_id")), new JSONObject());
        JSONObject forger = m.parties.getOrDefault(GenUtil.str(order.opt("forging_supplier_id")), new JSONObject());
        JSONObject grade = m.grades.getOrDefault(GenUtil.str(part.opt("material_grade_id")), new JSONObject());
        LinkedHashMap<String, Object> c = new LinkedHashMap<>();
        String flow = SupSvc.flowFor(order);
        c.put("Customer Ref", v(order, "master_reference_no"));
        c.put("Supply Flow", SupSvc.flowLabel(flow));
        c.put("Customer Order No", v(order, "customer_order_no"));
        c.put("Position", v(order, "order_position"));
        c.put("Customer", partyLabel(customer));
        c.put("Part Number", v(part, "part_number"));
        c.put("FSI Part Number", v(part, "fsi_part_number"));
        c.put("Part Description", v(part, "part_name"));
        c.put("Material Grade", v(grade, "grade_code"));
        List<String> dr = new ArrayList<>();
        for (String k : new String[]{"drawing_number", "drawing_revision"}) { String s = GenUtil.str(part.opt(k)).trim(); if (!s.isEmpty()) dr.add(s); }
        c.put("Drawing / Revision", String.join(" / ", dr));
        c.put("Forging Supplier", partyLabel(forger));
        c.put("Order Qty pcs", number(order.opt("order_qty_pcs")));
        c.put("Gross kg/pc", number(order.opt("gross_weight_kg_snapshot")));
        c.put("RM Required kg", number(order.opt("required_rm_kg")));
        c.put("Available Stock pcs", number(order.opt("available_stock_pcs_snapshot")));
        c.put("3 Month Schedule pcs", number(order.opt("three_month_schedule_pcs_snapshot")));
        Object rmReq = order.has("rm_procurement_required") ? order.opt("rm_procurement_required") : Boolean.TRUE;
        c.put("RM Procurement Required", GenUtil.truthy(rmReq));
        c.put("Procurement Decision", v(order, "procurement_decision"));
        c.put("Delivery Date", v(order, "customer_delivery_date"));
        c.put("Responsible Employee", employeeLabel(m, GenUtil.str(order.opt("responsible_employee_id"))));
        c.put("Status", v(order, "status"));
        return c;
    }

    private static Object v(JSONObject r, String k) { Object x = r == null ? null : r.opt(k); return x == JSONObject.NULL ? null : x; }

    /** Text of a cell (numbers without trailing zeros, booleans Yes/No). */
    static String text(Object v) {
        if (v == null || v == JSONObject.NULL) return "";
        if (v instanceof Boolean) return ((Boolean) v) ? "True" : "False";
        if (v instanceof Double || v instanceof Float) return GenUtil.cell(((Number) v).doubleValue());
        return String.valueOf(v);
    }

    /** _due_status */
    static String dueStatus(Object status, Object due) {
        String base = GenUtil.str(status);
        base = (base.isEmpty() ? "PENDING" : base).toUpperCase(Locale.ROOT);
        if (base.equals("COMPLETED") || base.equals("CLOSED") || base.equals("CANCELLED") || base.equals("REJECTED")) return base;
        String d = GenUtil.str(due);
        if (d.length() > 10) d = d.substring(0, 10);
        return !d.isEmpty() && d.compareTo(LocalDate.now().toString()) < 0 ? "OVERDUE" : base;
    }

    /** _order_display_rows (one row). */
    static LinkedHashMap<String, Object> displayRow(JSONObject r, Masters m) {
        JSONObject part = m.parts.getOrDefault(GenUtil.str(r.opt("part_id")), new JSONObject());
        JSONObject customer = m.parties.getOrDefault(GenUtil.str(r.opt("customer_id")), new JSONObject());
        JSONObject grade = m.grades.getOrDefault(GenUtil.str(part.opt("material_grade_id")), new JSONObject());
        String flow = SupSvc.flowFor(r);
        boolean rm = SupSvc.requiresRm(flow);
        LinkedHashMap<String, Object> o = new LinkedHashMap<>();
        o.put("Customer Ref", v(r, "master_reference_no"));
        o.put("Order No", v(r, "customer_order_no"));
        o.put("PosNr", v(r, "order_position"));
        o.put("Supply Flow", SupSvc.flowLabel(flow));
        o.put("Customer", partyLabel(customer));
        o.put("Part Number", v(part, "part_number"));
        o.put("FSI Part Number", v(part, "fsi_part_number"));
        o.put("Part Description", v(part, "part_name"));
        o.put("Material Grade", v(grade, "grade_code"));
        o.put("Order Qty pcs", v(r, "order_qty_pcs"));
        o.put("RM Required kg", rm ? v(r, "required_rm_kg") : null);
        o.put("RM Ordered kg", rm ? v(r, "rm_ordered_kg") : null);
        o.put("RM Balance kg", rm ? v(r, "rm_balance_kg") : null);
        o.put("Available Stock pcs", v(r, "available_stock_pcs_snapshot"));
        o.put("3 Month Schedule pcs", v(r, "three_month_schedule_pcs_snapshot"));
        o.put("RM Procurement Required", v(r, "rm_procurement_required"));
        o.put("Procurement Decision", v(r, "procurement_decision"));
        o.put("Delivery Date", v(r, "customer_delivery_date"));
        o.put("Data Entry Status", v(r, "status"));
        o.put("Display Status", dueStatus(r.opt("status"), r.opt("customer_delivery_date")));
        return o;
    }

    // ------------------------------------------------------------------ global order search
    static final class SearchData {
        Masters m;
        List<JSONObject> orders = new ArrayList<>();
        Map<String, List<JSONObject>> linked = new HashMap<>();
        /** Lower-case search text of every order (context + every linked stage value), built once. */
        Map<String, String> blobs = new HashMap<>();
        Map<String, String[]> display = new HashMap<>();
        List<String> displayHeaders = new ArrayList<>();
    }

    static SearchData searchData(Api api) throws Exception {
        SearchData d = new SearchData();
        d.m = masters(api);
        d.orders = GenUtil.big(api, "supply_customer_orders?select=*&order=created_at.desc&limit=10000");
        for (JSONObject o : d.orders) d.linked.put(GenUtil.str(o.opt("id")), new ArrayList<>());
        String[] tables = {"supply_rm_purchase_orders", "supply_rm_receipts", "supply_rm_dispatches", "supply_forging_orders", "supply_forging_receipts", "supply_downstream_events"};
        for (String t : tables) {
            int limit = t.equals("supply_downstream_events") ? 20000 : 10000;
            for (JSONObject r : GenUtil.big(api, t + "?select=*&order=created_at.desc&limit=" + limit))
                d.linked.computeIfAbsent(GenUtil.str(r.opt("customer_order_id")), k -> new ArrayList<>()).add(r);
        }
        for (JSONObject order : d.orders) {
            String id = GenUtil.str(order.opt("id"));
            d.blobs.put(id, blob(d, order));
            LinkedHashMap<String, Object> row = displayRow(order, d.m);
            if (d.displayHeaders.isEmpty()) d.displayHeaders.addAll(row.keySet());
            String[] line = new String[row.size()];
            int i = 0;
            for (Object v : row.values()) line[i++] = text(v);
            d.display.put(id, line);
        }
        return d;
    }

    /** Orders whose context or any linked stage value contains the text (website blob search). */
    static List<JSONObject> match(SearchData d, String search) {
        String q = search == null ? "" : search.toLowerCase(Locale.ROOT);
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject order : d.orders) {
            if (q.isEmpty()) { out.add(order); continue; }
            String blob = d.blobs.get(GenUtil.str(order.opt("id")));
            if (blob != null && blob.contains(q)) out.add(order);
        }
        return out;
    }

    private static String blob(SearchData d, JSONObject order) {
        StringBuilder blob = new StringBuilder();
        for (Object v : context(order, d.m).values()) blob.append(blobText(v)).append(' ');
        blob.append(' ');
        List<JSONObject> rows = d.linked.get(GenUtil.str(order.opt("id")));
        if (rows != null) for (JSONObject r : rows) for (String k : GenUtil.keys(r)) blob.append(blobText(r.opt(k))).append(' ');
        return blob.toString().toLowerCase(Locale.ROOT);
    }

    private static String blobText(Object v) {
        if (v == null || v == JSONObject.NULL) return "";
        if (v instanceof Boolean) return ((Boolean) v) ? "True" : "";
        if (v instanceof JSONObject || v instanceof JSONArray) return v.toString();
        return GenUtil.str(v);
    }

    // ------------------------------------------------------------------ one order
    static final class OrderData {
        JSONObject order;
        Masters m;
        LinkedHashMap<String, Object> ctx;
        List<LinkedHashMap<String, Object>> genealogy = new ArrayList<>();
        List<String[]> timeline = new ArrayList<>();
        List<String[]> balances = new ArrayList<>();
        String label = "";
    }

    static OrderData order(Api api, String orderId) throws Exception {
        OrderData d = new OrderData();
        List<JSONObject> o = GenUtil.big(api, "supply_customer_orders?select=*&id=eq." + Api.enc(orderId) + "&limit=1");
        if (o.isEmpty()) throw new Api.ApiException(404, "Customer Order not found or not visible for your role.");
        d.order = o.get(0);
        d.m = masters(api);
        d.ctx = context(d.order, d.m);
        String oid = Api.enc(orderId);
        Map<String, List<JSONObject>> stage = new HashMap<>();
        for (String[] s : STAGE_TABLES) {
            List<JSONObject> rows = GenUtil.big(api, s[0] + "?select=*&customer_order_id=eq." + oid + "&limit=10000");
            stage.put(s[0], rows);
            for (JSONObject r : rows) {
                LinkedHashMap<String, Object> g = new LinkedHashMap<>(d.ctx);
                g.put("Stage", s[1]);
                g.put("Stage Date", v(r, s[2]));
                g.put("Stage Reference", v(r, s[3]));
                g.put("Stage Qty", GenUtil.fmt(number(r.opt(s[4])), 3) + " " + s[5]);
                g.put("Heat Number", v(r, "heat_number"));
                g.put("Heat Code", v(r, "heat_code"));
                g.put("RMTC Number", v(r, "rmtc_number"));
                String st = GenUtil.str(r.opt("status"));
                g.put("Status", st.isEmpty() ? "POSTED" : st);
                g.put("Remarks", SupSvc.cleanFlowRemarks(GenUtil.str(r.opt("remarks"))));
                d.genealogy.add(g);
            }
        }
        for (JSONObject r : GenUtil.big(api, "supply_downstream_events?select=*&customer_order_id=eq." + oid + "&limit=10000")) {
            LinkedHashMap<String, Object> g = new LinkedHashMap<>(d.ctx);
            g.put("Stage", GenUtil.title(GenUtil.str(r.opt("event_type")).replace("_", " ")));
            g.put("Stage Date", v(r, "event_date"));
            g.put("Stage Reference", v(r, "reference_no"));
            g.put("Stage Qty", GenUtil.fmt(number(r.opt("qty_pcs")), 0) + " pcs");
            g.put("Heat Number", v(r, "heat_number"));
            g.put("Heat Code", v(r, "heat_code"));
            g.put("RMTC Number", null);
            g.put("Status", "POSTED");
            g.put("Remarks", SupSvc.cleanFlowRemarks(GenUtil.str(r.opt("remarks"))));
            d.genealogy.add(g);
        }
        // timeline
        List<String[]> events = new ArrayList<>();
        events.add(new String[]{GenUtil.str(d.order.opt("order_date")), "Customer Order", GenUtil.str(d.order.opt("master_reference_no")),
            GenUtil.fmt(number(d.order.opt("order_qty_pcs")), 0) + " pcs", "", GenUtil.str(d.order.opt("status")), SupSvc.cleanFlowRemarks(GenUtil.str(d.order.opt("remarks")))});
        for (LinkedHashMap<String, Object> g : d.genealogy)
            events.add(new String[]{GenUtil.str(g.get("Stage Date")), GenUtil.str(g.get("Stage")), GenUtil.str(g.get("Stage Reference")), GenUtil.str(g.get("Stage Qty")),
                GenUtil.str(g.get("Heat Number")), GenUtil.str(g.get("Status")), GenUtil.str(g.get("Remarks"))});
        events.sort((x, y) -> x[0].compareTo(y[0]));
        d.timeline = events;
        // supplier balances (FSI RM -> forging flow only)
        String flow = SupSvc.flowFor(d.order);
        if (!flow.equals(SupSvc.DIRECT_FORGING) && !flow.equals(SupSvc.FSI_RM_DIRECT_PRODUCTION)) {
            List<JSONObject> disp = stage.get("supply_rm_dispatches"), rec = stage.get("supply_forging_receipts");
            TreeSet<String> ids = new TreeSet<>();
            for (JSONObject r : disp) if (GenUtil.truthy(r.opt("forging_supplier_id"))) ids.add(GenUtil.str(r.opt("forging_supplier_id")));
            for (JSONObject r : rec) if (GenUtil.truthy(r.opt("forging_supplier_id"))) ids.add(GenUtil.str(r.opt("forging_supplier_id")));
            for (String sid : ids) {
                double sent = 0, consumed = 0;
                for (JSONObject r : disp) if (sid.equals(GenUtil.str(r.opt("forging_supplier_id")))) sent += number(r.opt("qty_kg"));
                for (JSONObject r : rec) if (sid.equals(GenUtil.str(r.opt("forging_supplier_id")))) {
                    Object act = r.opt("actual_rm_consumed_kg");
                    consumed += act != null && act != JSONObject.NULL ? number(act) : number(r.opt("received_qty_pcs")) * number(r.opt("gross_weight_kg_snapshot"));
                }
                d.balances.add(new String[]{partyLabel(d.m.parties.get(sid)), GenUtil.cell(GenUtil.round(sent, 3)), GenUtil.cell(GenUtil.round(consumed, 3)),
                    GenUtil.cell(GenUtil.round(sent - consumed, 3)), GenUtil.str(d.order.opt("master_reference_no"))});
            }
        }
        JSONObject part = d.m.parts.getOrDefault(GenUtil.str(d.order.opt("part_id")), new JSONObject());
        JSONObject cust = d.m.parties.getOrDefault(GenUtil.str(d.order.opt("customer_id")), new JSONObject());
        d.label = SupSvc.orderLabel(d.order, part, cust, "");
        return d;
    }

    // ------------------------------------------------------------------ heat / batch genealogy (v_qsms_trace_events)
    static final String[] EVENT_TYPES = {"PART_MASTER", "RMTC_APPROVAL", "RAW_MATERIAL_INWARD", "PRODUCTION_BATCH", "BATCH_MOVEMENT", "OSP_DISPATCH", "OSP_RECEIPT", "INSPECTION", "LAB_TEST", "CUSTOMER_DISPATCH"};
    static final String[] EVENT_TABLES = {"parts", "rmtc_approvals", "inward_lots", "production_batches", "batch_movements", "osp_jobs", "osp_jobs", "inspection_reports", "lab_tests", "dispatches"};

    static String eventTable(String type) {
        for (int i = 0; i < EVENT_TYPES.length; i++) if (EVENT_TYPES[i].equalsIgnoreCase(type)) return EVENT_TABLES[i];
        return null;
    }

    static List<JSONObject> heatSearch(Api api, String query) throws Exception {
        Object v = api.rpcValue("qsms_trace_search", new JSONObject().put("p_query", query.trim()).put("p_limit", 1000));
        return v instanceof JSONArray ? GenUtil.list((JSONArray) v) : new ArrayList<>();
    }
}
