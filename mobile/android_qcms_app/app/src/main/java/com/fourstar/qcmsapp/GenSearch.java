package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Port of app_pages/global_search.py keyword search (search_everywhere): same 27 record sources,
 * same columns, same part / party relationship expansion, same permission check (module View),
 * same reference / detail / status texts and the same result order. Background thread only.
 */
final class GenSearch {
    private GenSearch() { }

    static final class Source {
        final String table, recordType, module, moduleKey;
        final String[] columns, partFields, partyFields;
        Source(String table, String recordType, String module, String moduleKey, String[] columns, String[] partFields, String[] partyFields) {
            this.table = table; this.recordType = recordType; this.module = module; this.moduleKey = moduleKey;
            this.columns = columns; this.partFields = partFields; this.partyFields = partyFields;
        }
    }

    private static String[] a(String... v) { return v; }
    private static final String[] NONE = new String[0];

    /** global_search.SEARCH_SOURCES (also the datasets of the Report Builder). */
    static final List<Source> SOURCES = Arrays.asList(
        new Source("parts", "Part Master", "Masters", "PART_MASTER", a("part_number", "fsi_part_number", "part_name", "drawing_number", "drawing_revision", "section_size", "manufacturing_route", "remarks"), NONE, NONE),
        new Source("parties", "Customer / Supplier / OSP Vendor", "Masters", "REFERENCE_MASTERS", a("party_code", "party_name", "country", "state", "city", "address", "contact_person", "email", "phone", "tax_identifier", "approval_status", "status", "remarks"), NONE, NONE),
        new Source("material_grades", "Material Grade", "Masters", "MATERIAL_GRADE", a("grade_code", "standard", "revision", "status", "remarks"), NONE, NONE),
        new Source("processes", "Process Master", "Masters", "REFERENCE_MASTERS", a("process_code", "process_name", "process_type", "cqi_standard", "status", "remarks"), NONE, NONE),
        new Source("employees", "Employee", "Masters", "EMPLOYEE_MASTER", a("employee_code", "first_name", "last_name", "email", "department", "designation", "plant", "mobile_number", "status"), NONE, NONE),
        new Source("inspection_plans", "Inspection Layout", "Inspections", "INSPECTION_LAYOUTS", a("plan_number", "revision", "layout_type", "layout_name", "report_title", "status"), NONE, NONE),
        new Source("rmtc_approvals", "RMTC", "RMTC", "RMTC_ENTRY", a("rmtc_number", "certificate_reference", "heat_number", "heat_code", "rm_section", "forging_route", "status", "remarks"), a("part_id"), a("supplier_id", "steel_mill_id")),
        new Source("inward_lots", "Material Inward", "Inward", "MATERIAL_INWARD", a("inward_number", "grn_number", "invoice_number", "heat_number", "heat_code", "metallurgical_status", "dimensional_status", "status", "remarks"), a("part_id"), a("supplier_id")),
        new Source("production_batches", "Production / FSI Batch", "OSP", "OSP_TRANSACTIONS", a("batch_code", "heat_number", "heat_code", "vendor_batch_number", "work_order", "status", "remarks"), a("part_id"), NONE),
        new Source("osp_jobs", "OSP Job / Material Out", "OSP", "OSP_TRANSACTIONS", a("osp_job_number", "dispatch_challan", "process_specification", "receipt_challan", "vendor_batch_number", "receipt_status", "inspection_status", "status", "receipt_remarks"), a("part_id"), a("vendor_id")),
        new Source("osp_receipts", "OSP Inward Receipt", "OSP", "OSP_TRANSACTIONS", a("receipt_number", "receipt_challan", "vendor_invoice_number", "tc_number", "vendor_batch_number", "remarks"), NONE, NONE),
        new Source("inspection_reports", "Dimensional Report", "Inspections", "DIMENSIONAL_REPORT", a("report_number", "report_type", "inspector", "overall_result", "status", "remarks"), a("part_id"), NONE),
        new Source("lab_tests", "MetLAB / Bend Test Report", "Inspections", "METLAB_REPORT", a("report_number", "test_type", "sample_reference", "specification_reference", "overall_result", "status", "remarks"), a("part_id"), NONE),
        new Source("quality_complaints", "Quality Complaint", "Complaints", "COMPLAINT_MANAGEMENT", a("complaint_number", "complaint_type", "external_reference", "subject", "description", "severity", "status", "containment_action", "root_cause", "corrective_action", "verification_result", "closure_remarks", "debit_note_number", "commercial_remarks"), a("part_id"), a("party_id")),
        new Source("supply_customer_orders", "Customer Order / Schedule", "Supply Chain", "SUPPLY_CHAIN", a("master_reference_no", "order_type", "customer_order_no", "order_position", "status", "remarks"), a("part_id"), a("customer_id", "forging_supplier_id")),
        new Source("supply_purchase_orders", "Purchase Order", "Supply Chain", "SUPPLY_CHAIN", a("po_number", "po_type", "requisitioner", "ship_via", "incoterm", "payment_term", "quotation_reference", "old_po_reference", "currency", "remarks", "special_instructions", "status"), NONE, a("supplier_id")),
        new Source("supply_rm_purchase_orders", "RM Procurement Order", "Supply Chain", "SUPPLY_CHAIN", a("supplier_order_no", "status", "remarks"), NONE, a("rm_supplier_id")),
        new Source("supply_rm_receipts", "RM Receipt", "Supply Chain", "SUPPLY_CHAIN", a("receipt_number", "heat_number", "supplier_challan", "remarks"), NONE, NONE),
        new Source("supply_rm_dispatches", "RM to Forging", "Supply Chain", "SUPPLY_CHAIN", a("dispatch_number", "heat_number", "challan_number", "vehicle_number", "remarks"), NONE, a("forging_supplier_id")),
        new Source("supply_forging_orders", "Forging Order", "Supply Chain", "SUPPLY_CHAIN", a("supplier_order_no", "status", "remarks"), NONE, a("forging_supplier_id")),
        new Source("supply_forging_receipts", "Forging Receipt", "Supply Chain", "SUPPLY_CHAIN", a("receipt_number", "remarks"), NONE, a("forging_supplier_id")),
        new Source("supply_downstream_events", "Machining / FG / Dispatch", "Supply Chain", "SUPPLY_CHAIN", a("event_type", "reference_no", "invoice_no", "asn_no", "remarks"), NONE, NONE),
        new Source("npd_orders", "NPD Order / Status", "NPD & APQP", "NPD_APQP", a("order_number", "status", "remarks"), a("part_id"), a("customer_id")),
        new Source("ppap_projects", "PPAP / APQP Project", "NPD & APQP", "NPD_APQP", a("project_code", "submission_level", "reason", "coordinator", "status", "remarks"), a("part_id"), a("customer_id")),
        new Source("quality_assets", "Gauge / Fixture / Quality Asset", "Calibration & Validation", "CALIBRATION_VALIDATION", a("asset_code", "asset_number", "asset_name", "asset_type", "manufacturer", "model", "serial_number", "range_text", "least_count", "location", "status", "remarks"), NONE, NONE),
        new Source("quality_asset_calibration_records", "Calibration / Validation Record", "Calibration & Validation", "CALIBRATION_VALIDATION", a("record_type", "result", "report_number", "certificate_number", "calibration_agency", "status", "remarks"), NONE, NONE),
        new Source("standard_room_inspection_records", "Standard Room Inspection", "Calibration & Validation", "CALIBRATION_VALIDATION", a("instrument_type", "heat_number", "batch_code", "report_number", "inspection_status", "program_reference", "status", "remarks"), a("part_id"), NONE));

    static Source source(String table) {
        for (Source s : SOURCES) if (s.table.equals(table)) return s;
        return null;
    }

    static final class Result {
        static final String LOCAL = "local", SERVER = "server", MODULE = "module";
        final String key, module, recordType, reference, detail, status, table;
        final JSONObject record;
        /** R35: where the hit came from (local field search, qcms_global_search, app module / screen). */
        String kind = LOCAL;
        String recordId = "", route = "", appModule = "";
        Result(String key, String module, String recordType, String reference, String detail, String status, String table, JSONObject record) {
            this.key = key; this.module = module; this.recordType = recordType; this.reference = reference; this.detail = detail;
            this.status = status; this.table = table; this.record = record;
        }
    }

    // ------------------------------------------------------------------ R35: modules / screens + server-wide search
    static final String MODULES_GROUP = "Modules & screens";

    /** App modules whose name / section / description contain every word of the query ("bend test" -> Bend Test modules). */
    static List<Result> modules(String query) {
        List<Result> out = new ArrayList<>();
        String q = casefold(query == null ? "" : query.trim());
        if (q.length() < 2) return out;
        String[] words = q.split("\\s+");
        for (Module m : Catalog.all()) {
            String hay = casefold(m.title + " " + m.key.replace('_', ' ') + " " + m.section + " " + (m.description == null ? "" : m.description));
            boolean all = true;
            for (String w : words) if (!w.isEmpty() && !hay.contains(w)) { all = false; break; }
            if (!all) continue;
            Result r = new Result("module:" + m.key, MODULES_GROUP, "Open module", m.title, joinNonEmpty(Catalog.TAB_NAMES[Math.max(0, Math.min(Catalog.TAB_NAMES.length - 1, m.tab))], m.section, m.description), "", m.table, new JSONObject());
            r.kind = Result.MODULE;
            r.appModule = m.key;
            out.add(r);
        }
        // the module whose title starts with the query first
        out.sort((x, y) -> {
            boolean xs = casefold(x.reference).startsWith(q), ys = casefold(y.reference).startsWith(q);
            if (xs != ys) return xs ? -1 : 1;
            return casefold(x.reference).compareTo(casefold(y.reference));
        });
        return out;
    }

    private static String s(JSONObject o, String k) { return o == null || o.isNull(k) ? "" : o.optString(k, ""); }

    /** Group (module) label for a server row: the local source's module, else the module key in words. */
    static String groupFor(String table, String moduleKey) {
        Source src = source(table);
        if (src != null) return src.module;
        if (moduleKey != null && !moduleKey.isEmpty()) return GenUtil.title(moduleKey.replace('_', ' ').toLowerCase(Locale.ROOT));
        return table == null || table.isEmpty() ? "Other records" : Ui.pretty(table);
    }

    /** qcms_global_search(p_query, p_limit): every business table and field, RLS scoped. Background thread. */
    static List<Result> server(Api api, String query, int limit) throws Exception {
        JSONArray rows = api.rpcRows("qcms_global_search", new JSONObject().put("p_query", query.trim()).put("p_limit", limit));
        List<Result> out = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.optJSONObject(i);
            if (r == null) continue;
            String table = s(r, "source_table"), id = s(r, "record_id");
            String key = table + ":" + id;
            if (seen.contains(key)) continue;
            seen.add(key);
            String matched = s(r, "matched_field"), snippet = s(r, "snippet");
            String match = matched.isEmpty() ? snippet : (snippet.isEmpty() ? Ui.pretty(matched) : Ui.pretty(matched) + ": " + snippet);
            String title = s(r, "title");
            String type = s(r, "record_type");
            JSONObject record = new JSONObject();
            try { record.put("id", id); } catch (Exception ignored) { }
            Result res = new Result(key, groupFor(table, s(r, "module_key")), type.isEmpty() ? Ui.pretty(table) : type,
                title.isEmpty() ? (id.isEmpty() ? "Record" : id) : title, joinNonEmpty(s(r, "subtitle"), match), "", table, record);
            res.kind = Result.SERVER;
            res.recordId = id;
            res.route = s(r, "web_route");
            res.appModule = s(r, "module_key");
            out.add(res);
        }
        return out;
    }

    /** Module hits first, then server rows, then local rows not already found by the server (same table:id). */
    static List<Result> merge(List<Result> modules, List<Result> server, List<Result> local) {
        List<Result> out = new ArrayList<>(modules == null ? new ArrayList<>() : modules);
        Set<String> keys = new HashSet<>();
        if (server != null) for (Result r : server) if (keys.add(r.key)) out.add(r);
        if (local != null) for (Result r : local) if (keys.add(r.key)) out.add(r);
        return out;
    }

    private static final String[] REFERENCE_KEYS = {"part_number", "fsi_part_number", "party_code", "grade_code", "process_code", "employee_code",
        "plan_number", "rmtc_number", "inward_number", "batch_code", "osp_job_number", "receipt_number",
        "report_number", "complaint_number", "master_reference_no", "customer_order_no", "po_number",
        "supplier_order_no", "dispatch_number", "reference_no", "order_number", "project_code", "asset_code",
        "certificate_number", "tc_number", "heat_number"};
    private static final String[] STATUS_KEYS = {"status", "disposition", "overall_result", "inspection_status", "receipt_status", "result", "approval_status"};
    private static final String[] LINK_KEYS = {"part_id", "customer_id", "supplier_id", "party_id", "vendor_id", "forging_supplier_id", "rm_supplier_id", "steel_mill_id"};
    private static final String[] DETAIL_KEYS = {"part_name", "party_name", "subject", "heat_number", "heat_code", "vendor_batch_number", "batch_code",
        "sample_reference", "certificate_reference", "grn_number", "invoice_number", "invoice_no", "asn_no",
        "drawing_number", "layout_name", "report_title", "remarks"};

    static String reference(JSONObject row) {
        for (String k : REFERENCE_KEYS) { String v = GenUtil.str(row.opt(k)).trim(); if (!v.isEmpty()) return v; }
        String id = GenUtil.str(row.opt("id"));
        return id.isEmpty() ? "Record" : id;
    }

    static String status(JSONObject row) {
        for (String k : STATUS_KEYS) { String v = GenUtil.str(row.opt(k)).trim(); if (!v.isEmpty()) return GenUtil.title(v.replace("_", " ")); }
        return "";
    }

    static String detail(JSONObject row, Map<String, String> partMap, Map<String, String> partyMap) {
        List<String> values = new ArrayList<>();
        for (String k : LINK_KEYS) {
            String raw = GenUtil.str(row.opt(k));
            String label = k.equals("part_id") ? partMap.get(raw) : partyMap.get(raw);
            if (label != null && !label.isEmpty() && !values.contains(label)) values.add(label);
        }
        for (String k : DETAIL_KEYS) {
            String v = GenUtil.str(row.opt(k)).trim();
            if (!v.isEmpty() && !values.contains(v)) values.add(v);
            if (values.size() >= 4) break;
        }
        return String.join(" · ", values.subList(0, Math.min(4, values.size())));
    }

    /** PostgREST or=(col.ilike.*term*,...) exactly like Repository.select(search_columns, search_term). */
    static String ilike(String[] columns, String term) {
        String clean = term.replace(",", " ").replace("(", " ").replace(")", " ").trim();
        StringBuilder b = new StringBuilder();
        for (String c : columns) { if (b.length() > 0) b.append(','); b.append(c).append(".ilike.*").append(clean).append('*'); }
        return "&or=" + Api.enc("(" + b + ")");
    }

    private static List<JSONObject> select(Api api, String table, String filter, int limit) throws Exception {
        return GenUtil.big(api, table + "?select=*" + filter + "&limit=" + limit);
    }

    private static String inList(List<String> ids) {
        List<String> head = ids.subList(0, Math.min(50, ids.size()));
        return Api.enc("(" + String.join(",", head) + ")");
    }

    private static String joinNonEmpty(String... v) {
        List<String> out = new ArrayList<>();
        for (String s : v) if (s != null && !s.trim().isEmpty()) out.add(s.trim());
        return String.join(" · ", out);
    }

    private static String casefold(String s) { return s == null ? "" : s.toLowerCase(Locale.ROOT); }

    /** search_everywhere(repo, profile, query, per_source_limit=40). Background thread. */
    static List<Result> everywhere(Api api, String query, int perSourceLimit) throws Exception {
        String q = query == null ? "" : query.trim();
        if (q.length() < 2) return new ArrayList<>();
        boolean partsOk = GenUtil.canView(api, "PART_MASTER"), partiesOk = GenUtil.canView(api, "REFERENCE_MASTERS");
        List<JSONObject> partRows = partsOk ? select(api, "parts", ilike(new String[]{"part_number", "fsi_part_number", "part_name", "drawing_number", "drawing_revision", "remarks"}, q), 50) : new ArrayList<>();
        List<JSONObject> partyRows = partiesOk ? select(api, "parties", ilike(new String[]{"party_code", "party_name", "country", "state", "city", "contact_person", "email", "remarks"}, q), 50) : new ArrayList<>();
        List<String> partIds = new ArrayList<>(), partyIds = new ArrayList<>();
        for (JSONObject r : partRows) { String id = GenUtil.str(r.opt("id")); if (!id.isEmpty()) partIds.add(id); }
        for (JSONObject r : partyRows) { String id = GenUtil.str(r.opt("id")); if (!id.isEmpty()) partyIds.add(id); }

        Map<String, String> partMap = new HashMap<>(), partyMap = new HashMap<>();
        if (partsOk) for (JSONObject r : select(api, "parts", "", 5000)) {
            String id = GenUtil.str(r.opt("id"));
            if (!id.isEmpty()) partMap.put(id, joinNonEmpty(GenUtil.str(r.opt("part_number")), GenUtil.str(r.opt("fsi_part_number")), GenUtil.str(r.opt("part_name"))));
        }
        if (partiesOk) for (JSONObject r : select(api, "parties", "", 5000)) {
            String id = GenUtil.str(r.opt("id"));
            if (!id.isEmpty()) partyMap.put(id, joinNonEmpty(GenUtil.str(r.opt("party_code")), GenUtil.str(r.opt("party_name"))));
        }

        String fold = casefold(q);
        List<Result> found = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for (Source src : SOURCES) {
            if (!GenUtil.canView(api, src.moduleKey)) continue;
            LinkedHashMap<String, JSONObject> byId = new LinkedHashMap<>();
            try {
                merge(byId, select(api, src.table, ilike(src.columns, q), perSourceLimit));
                LinkedHashMap<String, JSONObject> related = new LinkedHashMap<>();
                for (String f : src.partFields) if (!partIds.isEmpty()) merge(related, select(api, src.table, "&" + f + "=in." + inList(partIds), perSourceLimit));
                for (String f : src.partyFields) if (!partyIds.isEmpty()) merge(related, select(api, src.table, "&" + f + "=in." + inList(partyIds), perSourceLimit));
                merge(byId, new ArrayList<>(related.values()));
            } catch (Exception e) {
                // One optional register must never break Global Search (website: continue) - but a lost
                // connection must be reported instead of an empty answer.
                if (e instanceof java.io.IOException || (e instanceof Api.ApiException && (((Api.ApiException) e).status == 0 || ((Api.ApiException) e).status == 401))) throw e;
                continue;
            }
            for (JSONObject row : byId.values()) {
                String rowId = GenUtil.str(row.opt("id"));
                String token = src.table + ":" + rowId;
                if (rowId.isEmpty() || seen.contains(token)) continue;
                seen.add(token);
                List<String> rel = new ArrayList<>();
                for (String f : src.partFields) { String v = partMap.get(GenUtil.str(row.opt(f))); rel.add(v == null ? "" : v); }
                for (String f : src.partyFields) { String v = partyMap.get(GenUtil.str(row.opt(f))); rel.add(v == null ? "" : v); }
                String relation = String.join(" ", rel);
                if (!casefold(GenUtil.text(row)).contains(fold) && !casefold(relation).contains(fold)) continue;
                found.add(new Result(token, src.module, src.recordType, reference(row), detail(row, partMap, partyMap), status(row), src.table, row));
            }
        }
        found.sort((x, y) -> {
            int c = x.module.compareTo(y.module);
            if (c != 0) return c;
            c = x.recordType.compareTo(y.recordType);
            if (c != 0) return c;
            return casefold(x.reference).compareTo(casefold(y.reference));
        });
        return found;
    }

    private static void merge(LinkedHashMap<String, JSONObject> target, List<JSONObject> rows) {
        for (JSONObject r : rows) {
            String id = GenUtil.str(r.opt("id"));
            if (!id.isEmpty()) target.put(id, r);
        }
    }
}
