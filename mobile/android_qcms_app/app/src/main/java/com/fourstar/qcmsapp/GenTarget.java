package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.HashMap;
import java.util.Map;

/**
 * R39 (website app_pages/global_search.py _resolve_target + core/universal_pdf.py WEB_ROUTES): opens the exact record a
 * search hit / KPI row / notification points to. Detail rows open their parent record (inspection result -> its
 * dimensional report, complaint action -> its complaint, attachment -> its owner record, deletion request -> the record),
 * and a record whose table has no app module opens as a read-only record view (fields, attachments, Print PDF)
 * instead of the website.
 */
final class GenTarget {
    private GenTarget() { }

    /** child table -> {parent table, link column} (global_search._CHILD_PARENT). */
    static final Map<String, String[]> CHILD_PARENT = new HashMap<>();
    /** document_attachments.entity_type -> owner table (global_search._ATTACHMENT_OWNER). */
    static final Map<String, String> ATTACHMENT_OWNER = new HashMap<>();
    /** tables shown by an app module over a view with the same id (osp_jobs -> OSP Register v_qsms_osp_register). */
    static final Map<String, String> VIEW_MODULE = new HashMap<>();
    /** website "home" routes that are a bottom-navigation tab in the app. */
    static final Map<String, Integer> TAB_ROUTES = new HashMap<>();

    static {
        String[][] cp = {
            {"part_supplier_links", "parts", "part_id"}, {"part_process_specifications", "parts", "part_id"},
            {"part_process_parameter_specifications", "parts", "part_id"}, {"part_metallurgical_requirements", "parts", "part_id"},
            {"part_heat_treatment_details", "parts", "part_id"}, {"part_rmtc_requirements", "parts", "part_id"},
            {"part_material_grade_links", "parts", "part_id"}, {"part_jominy_requirements", "parts", "part_id"},
            {"part_standard_links", "parts", "part_id"}, {"part_process_routes", "parts", "part_id"},
            {"part_raw_material_technical_data", "parts", "part_id"}, {"part_supplier_price_history", "parts", "part_id"},
            {"material_grade_elements", "material_grades", "material_grade_id"},
            {"inspection_plan_characteristics", "inspection_plans", "inspection_plan_id"},
            {"inspection_results", "inspection_reports", "inspection_report_id"},
            {"quality_complaint_actions", "quality_complaints", "complaint_id"}, {"quality_complaint_followups", "quality_complaints", "complaint_id"},
            {"npd_order_steps", "npd_orders", "npd_order_id"}, {"npd_process_flow_steps", "npd_process_flows", "flow_id"},
            {"ppap_documents", "ppap_projects", "ppap_project_id"}, {"msa_plans", "ppap_projects", "ppap_project_id"},
            {"spc_plans", "ppap_projects", "ppap_project_id"}, {"capacity_studies", "ppap_projects", "ppap_project_id"},
            {"balloon_characteristics", "ppap_projects", "ppap_project_id"},
            {"rmtc_chemistry_results", "rmtc_approvals", "rmtc_approval_id"}, {"rmtc_requirement_results", "rmtc_approvals", "rmtc_approval_id"},
            {"rmtc_jominy_results", "rmtc_approvals", "rmtc_approval_id"}, {"rmtc_decision_revisions", "rmtc_approvals", "rmtc_approval_id"},
            {"rmtc_part_approvals", "rmtc_approvals", "rmtc_approval_id"},
            {"osp_material_outs", "osp_jobs", "osp_job_id"}, {"supply_purchase_order_sources", "supply_purchase_orders", "purchase_order_id"},
            {"supply_purchase_order_items", "supply_purchase_orders", "purchase_order_id"},
            {"calibration_events", "quality_assets", "asset_id"}, {"quality_asset_part_process_links", "quality_assets", "asset_id"},
            {"part_ecn_actions", "part_ecns", "ecn_id"}};
        for (String[] r : cp) CHILD_PARENT.put(r[0], new String[]{r[1], r[2]});
        String[][] ao = {
            {"METLAB_REPORT", "lab_tests"}, {"QUALITY_COMPLAINT", "quality_complaints"}, {"PO_CONFIRMATION", "supply_po_confirmations"},
            {"PART_MASTER", "parts"}, {"RMTC", "rmtc_approvals"}, {"CUSTOMER_STANDARD", "customer_standards"}, {"MATERIAL_INWARD", "inward_lots"},
            {"PART_PROCESS_SPEC", "part_process_specifications"}, {"SUPPLY_CUSTOMER_ORDER", "supply_customer_orders"},
            {"DIMENSIONAL_REPORT", "inspection_reports"}, {"OSP_JOB", "osp_jobs"}, {"NPD_ORDER", "npd_orders"}};
        for (String[] r : ao) ATTACHMENT_OWNER.put(r[0], r[1]);
        VIEW_MODULE.put("osp_jobs", "osp_register");
        TAB_ROUTES.put("dashboard", Catalog.HOME);
        TAB_ROUTES.put("supply-chain-home", Catalog.SUPPLY);
        TAB_ROUTES.put("inspection-home", Catalog.QUALITY);
        TAB_ROUTES.put("masters", Catalog.MASTERS);
    }

    static String s(JSONObject o, String k) { return o == null || o.isNull(k) ? "" : o.optString(k, ""); }

    /** True when the table is a detail / pointer table that resolves to another record. */
    static boolean resolvable(String table) {
        return table != null && (CHILD_PARENT.containsKey(table) || "document_attachments".equals(table) || "qcms_delete_requests".equals(table));
    }

    private static JSONObject fetch(Api api, String table, String id) throws Exception {
        if (table == null || table.isEmpty() || id == null || id.isEmpty() || "null".equals(id)) return null;
        JSONArray rows = api.rows(table + "?select=*&id=eq." + Api.enc(id) + "&limit=1");
        return rows.length() > 0 ? rows.optJSONObject(0) : null;
    }

    /** {table, id} of the record with its own screen (detail row -> parent, attachment -> owner). Background thread. */
    static String[] resolve(Api api, String table, String id) {
        String t = table, i = id;
        try {
            for (int depth = 0; depth < 4; depth++) {
                if (Notif.moduleForTable(t, "") != null || VIEW_MODULE.containsKey(t)) break;   // the app opens this record itself
                JSONObject row = fetch(api, t, i);
                if (row == null) break;
                String nt = "", ni = "";
                if (CHILD_PARENT.containsKey(t)) {
                    String[] p = CHILD_PARENT.get(t);
                    nt = p[0]; ni = s(row, p[1]);
                } else if ("document_attachments".equals(t)) {
                    nt = ATTACHMENT_OWNER.getOrDefault(s(row, "entity_type").toUpperCase(java.util.Locale.ROOT), "");
                    ni = s(row, "entity_id");
                } else if ("qcms_delete_requests".equals(t)) {
                    nt = s(row, "table_name"); ni = s(row, "record_id");
                }
                if (nt.isEmpty() || ni.isEmpty() || fetch(api, nt, ni) == null) break;
                t = nt; i = ni;
            }
        } catch (Exception ignored) {
            // keep the hit itself (offline / no permission on the parent)
        }
        return new String[]{t, i};
    }

    /**
     * Opens the exact record: resolves detail rows to their parent, then the app module's record screen,
     * else a read-only record view (with Print PDF); without an id the route / module opens (Notif.open).
     */
    static void open(MainActivity a, String table, String id, String route, String title) {
        boolean hasId = id != null && !id.isEmpty() && !"null".equals(id);
        if (!hasId || table == null || table.isEmpty()) { Notif.open(a, table, id, route, title); return; }
        if (VIEW_MODULE.containsKey(table)) { openResolved(a, table, id, route, title); return; }
        if (Notif.moduleForTable(table, route) != null) { Notif.open(a, table, id, route, title); return; }
        Api api = Api.get(a);
        Api.async(() -> resolve(api, table, id), (target, err) -> {
            String t = target == null ? table : target[0], i = target == null ? id : target[1];
            openResolved(a, t, i, t.equals(table) ? route : "", title);
        });
    }

    private static void openResolved(MainActivity a, String table, String id, String route, String title) {
        Module view = VIEW_MODULE.containsKey(table) ? Catalog.get(VIEW_MODULE.get(table)) : null;
        if (view != null) { a.push(new RecordScreen(a, view, id)); return; }
        if (Notif.moduleForTable(table, route) != null || "supply_purchase_orders".equals(table)) { Notif.open(a, table, id, route, title); return; }
        // no app module for this table: read-only record view (fields, attachments, Print PDF) like the website viewer
        a.push(new RecordScreen(a, Catalog.adhoc(table), id));
    }
}
