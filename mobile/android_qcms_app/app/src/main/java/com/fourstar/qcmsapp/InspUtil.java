package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.widget.LinearLayout;
import android.widget.ScrollView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Shared rules of the Inspection / OSP area, ported from core/inspection_service.py,
 * core/inspection_layout_metadata.py and core/password_edit.py.
 */
final class InspUtil {
    private InspUtil() { }

    static final String[] FINAL_DISPOSITIONS = {"ON_HOLD", "ACCEPTED", "ACCEPTED_UNDER_RESERVE", "REJECTED"};
    static final String[] DRAFT_DISPOSITIONS = {"PENDING", "ON_HOLD", "ACCEPTED", "ACCEPTED_UNDER_RESERVE", "REJECTED"};
    static final String[] DISPOSITION_LABELS = {"Pending", "On Hold", "Accepted", "Accepted Under Reserve", "Rejected"};
    static final String[] FINAL_LABELS = {"On Hold", "Accepted", "Accepted Under Reserve", "Rejected"};
    static final String[] STANDALONE_SCOPES = {"RAW_MATERIAL_STAGE", "OSP_STAGE", "FINAL_DISPATCH_STAGE"};
    static final String[] STANDALONE_LABELS = {"Raw Material Stage", "OSP Stage", "Final Dispatch Stage"};
    static final String GENERAL_METLAB = "GENERAL_METLAB", BEND_TEST = "BEND_TEST";
    static final Pattern CASE_DEPTH = Pattern.compile("\\bcase\\s+depth\\b", Pattern.CASE_INSENSITIVE);

    // ------------------------------------------------------------------ small JSON helpers
    static String j(JSONObject r, String k) { return r == null ? "" : Lookups.j(r, k); }

    static Object nz(String v) { return v == null || v.trim().isEmpty() ? JSONObject.NULL : v.trim(); }

    static Object nzObj(Object v) {
        if (v == null || v == JSONObject.NULL) return JSONObject.NULL;
        if (v instanceof String && (((String) v).trim().isEmpty() || "null".equals(v))) return JSONObject.NULL;
        return v;
    }

    static Object numOrNull(Object v) {
        Double d = Rules.number(v);
        return d == null ? JSONObject.NULL : (Object) d;
    }

    static double dbl(JSONObject r, String k) {
        Double d = Rules.number(r == null ? null : r.opt(k));
        return d == null ? 0 : d;
    }

    /** Number shown without a trailing .0 (10.0 -> 10). */
    static String fmt(Object v) {
        if (v == null || v == JSONObject.NULL) return "";
        String s = String.valueOf(v).trim();
        if ("null".equals(s)) return "";
        Double d = Rules.number(s);
        if (d != null && !s.matches(".*[a-zA-Z].*")) {
            if (Math.abs(d - Math.rint(d)) < 1e-9 && Math.abs(d) < 1e15) return String.valueOf(Math.round(d));
            String t = String.valueOf(d);
            return t.contains("E") ? s : t;
        }
        return s;
    }

    static String now() { return OffsetDateTime.now(ZoneOffset.UTC).toString(); }

    static String uuid() { return java.util.UUID.randomUUID().toString(); }

    static JSONObject copy(JSONObject o) {
        try { return o == null ? new JSONObject() : new JSONObject(o.toString()); } catch (Exception e) { return new JSONObject(); }
    }

    static List<JSONObject> list(JSONArray arr) {
        List<JSONObject> out = new ArrayList<>();
        if (arr == null) return out;
        for (int i = 0; i < arr.length(); i++) { JSONObject r = arr.optJSONObject(i); if (r != null) out.add(r); }
        return out;
    }

    static JSONObject get(Api api, String table, String id) throws Exception {
        if (id == null || id.isEmpty() || "null".equals(id)) return null;
        JSONArray r = api.rows(table + "?select=*&id=eq." + Api.enc(id));
        return r.length() == 0 ? null : r.getJSONObject(0);
    }

    static String scopeLabel(String scope) {
        for (int i = 0; i < STANDALONE_SCOPES.length; i++) if (STANDALONE_SCOPES[i].equals(scope)) return STANDALONE_LABELS[i];
        return Ui.pretty(scope);
    }

    static boolean isStandaloneScope(String scope) {
        return Arrays.asList(STANDALONE_SCOPES).contains(scope);
    }

    static String dispositionLabel(String d) {
        for (int i = 0; i < DRAFT_DISPOSITIONS.length; i++) if (DRAFT_DISPOSITIONS[i].equals(d)) return DISPOSITION_LABELS[i];
        return Ui.pretty(d);
    }

    /** core/selection_labels.employee_label (used for inspection_reports.inspector). */
    static String employeeLabel(JSONObject r) {
        if (r == null) return "";
        String name = (j(r, "first_name") + " " + j(r, "last_name")).trim().replaceAll("\\s+", " ");
        String label = Lookups.join(j(r, "employee_code"), name, j(r, "designation"), j(r, "department"), j(r, "plant"));
        String st = j(r, "status");
        if (!st.isEmpty()) {
            String tag = "[" + st.replace('_', ' ').toUpperCase(Locale.ROOT) + "]";
            if (!label.contains(tag)) label = label.isEmpty() ? tag : label + " " + tag;
        }
        return label;
    }

    /** osp_inspections._employee_map label. */
    static String ospEmployeeLabel(JSONObject r) {
        if (r == null) return "";
        return j(r, "employee_code") + " · " + j(r, "first_name") + " " + j(r, "last_name");
    }

    // ------------------------------------------------------------------ pickers / dialogs
    static void pick(MainActivity a, String title, List<String> ids, List<String> names, FormView.Picked picked) {
        new FormView(a, new ArrayList<>()).choose(title, ids, names, picked);
    }

    interface FormOk { void ok(FormView form, JSONObject values) throws Exception; }

    /** Form inside a dialog; the dialog closes only when the values pass validation and the callback does not throw. */
    static void formDialog(MainActivity a, String title, List<Field> fields, JSONObject values, String okLabel, FormOk ok) {
        FormView form = new FormView(a, fields);
        if (values != null) form.setAll(values);
        ScrollView sv = new ScrollView(a);
        LinearLayout pad = Ui.vbox(a);
        pad.setPadding(Ui.dp(a, 18), Ui.dp(a, 4), Ui.dp(a, 18), Ui.dp(a, 8));
        pad.addView(form);
        sv.addView(pad);
        AlertDialog dialog = new AlertDialog.Builder(a).setTitle(title).setView(sv)
            .setPositiveButton(okLabel, null).setNegativeButton("Back", null).create();
        dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            String problem = form.validate();
            if (problem != null) { a.toast(problem); return; }
            try {
                ok.ok(form, form.json());
                dialog.dismiss();
            } catch (Exception e) {
                a.toast(Api.message(e));
            }
        }));
        dialog.show();
    }

    // ------------------------------------------------------------------ layouts (inspection plans)
    static JSONObject metadata(JSONObject row) {
        if (row == null) return new JSONObject();
        Object v = row.opt("layout_metadata");
        if (v instanceof JSONObject) return copy((JSONObject) v);
        if (v instanceof String) { try { return new JSONObject((String) v); } catch (Exception ignored) { } }
        return new JSONObject();
    }

    /** inspection_layout_metadata.inspection_method_from_rows. */
    static String methodFromRows(List<JSONObject> rows, String fallbackText) {
        for (JSONObject r : rows) {
            String m = j(metadata(r), "inspection_method").trim().toUpperCase(Locale.ROOT);
            if (GENERAL_METLAB.equals(m) || BEND_TEST.equals(m)) return m;
        }
        return (fallbackText == null ? "" : fallbackText).toUpperCase(Locale.ROOT).contains("BEND TEST") ? BEND_TEST : GENERAL_METLAB;
    }

    static String planText(JSONObject plan) {
        return j(plan, "layout_name") + " " + j(plan, "report_title") + " " + j(plan, "source_template_name");
    }

    static List<JSONObject> planChars(Api api, String planId) throws Exception {
        if (planId == null || planId.isEmpty()) return new ArrayList<>();
        return list(api.rows("inspection_plan_characteristics?select=*&inspection_plan_id=eq." + Api.enc(planId)
            + "&status=eq.ACTIVE&order=sequence_no.asc&limit=1000"));
    }

    /** InspectionService.plan_inspection_method. */
    static String planMethod(Api api, JSONObject plan) throws Exception {
        if (plan == null) return GENERAL_METLAB;
        return methodFromRows(planChars(api, j(plan, "id")), planText(plan));
    }

    /** plan_inspection_method for many plans with one query. */
    static Map<String, String> planMethods(Api api, List<JSONObject> plans) throws Exception {
        Map<String, String> out = new HashMap<>();
        if (plans.isEmpty()) return out;
        Map<String, List<JSONObject>> rows = new HashMap<>();
        List<String> ids = new ArrayList<>();
        for (JSONObject p : plans) { ids.add(j(p, "id")); rows.put(j(p, "id"), new ArrayList<>()); }
        for (int s = 0; s < ids.size(); s += 60) {
            List<String> part = ids.subList(s, Math.min(ids.size(), s + 60));
            for (JSONObject c : list(api.rows("inspection_plan_characteristics?select=inspection_plan_id,layout_metadata,sequence_no&status=eq.ACTIVE&inspection_plan_id=in.("
                + String.join(",", part) + ")&order=sequence_no.asc&limit=5000"))) {
                List<JSONObject> l = rows.get(j(c, "inspection_plan_id"));
                if (l != null) l.add(c);
            }
        }
        for (JSONObject p : plans) out.put(j(p, "id"), methodFromRows(rows.get(j(p, "id")), planText(p)));
        return out;
    }

    /** InspectionService.plans. */
    static List<JSONObject> plans(Api api, String layoutType, String partId, boolean approvedOnly, String processId, String stageId, String inwardType) throws Exception {
        StringBuilder q = new StringBuilder("inspection_plans?select=*");
        if (layoutType != null && !layoutType.isEmpty()) q.append("&layout_type=eq.").append(Api.enc(layoutType));
        if (partId != null && !partId.isEmpty()) q.append("&part_id=eq.").append(Api.enc(partId));
        if (approvedOnly) q.append("&status=eq.APPROVED");
        if (processId != null && !processId.isEmpty()) q.append("&process_id=eq.").append(Api.enc(processId));
        if (stageId != null && !stageId.isEmpty()) q.append("&inspection_stage_id=eq.").append(Api.enc(stageId));
        if (inwardType != null && !inwardType.isEmpty()) q.append("&inward_type=eq.").append(Api.enc(inwardType));
        q.append("&order=plan_number.asc&limit=3000");
        return list(api.rows(q.toString()));
    }

    /** InspectionService.ranked_plans (exact process + stage match first, then effective date, then revision). */
    static List<JSONObject> rankedPlans(Api api, String layoutType, String partId, String processId, String stageId, String inwardType) throws Exception {
        List<JSONObject> list = plans(api, layoutType, partId, true, null, null, inwardType);
        list.sort((x, y) -> {
            int sx = score(x, processId, stageId), sy = score(y, processId, stageId);
            if (sx != sy) return Integer.compare(sy, sx);
            int c = j(y, "effective_date").compareTo(j(x, "effective_date"));
            if (c != 0) return c;
            return j(y, "revision").compareTo(j(x, "revision"));
        });
        return list;
    }

    private static int score(JSONObject r, String processId, String stageId) {
        boolean p = processId == null || processId.isEmpty() || j(r, "process_id").equals(processId);
        boolean s = stageId == null || stageId.isEmpty() || j(r, "inspection_stage_id").equals(stageId);
        return (p ? 1 : 0) + (s ? 1 : 0);
    }

    static boolean isRawPlan(JSONObject plan) {
        String lt = j(plan, "layout_type").isEmpty() ? "METLAB" : j(plan, "layout_type").toUpperCase(Locale.ROOT);
        String it = j(plan, "inward_type").isEmpty() ? "MATERIAL_INWARD" : j(plan, "inward_type").toUpperCase(Locale.ROOT);
        String rs = j(plan, "requirement_scope").isEmpty() ? "GENERAL" : j(plan, "requirement_scope").toUpperCase(Locale.ROOT);
        return lt.equals("METLAB") && it.equals("MATERIAL_INWARD") && rs.equals("GENERAL");
    }

    static boolean isRawRecord(JSONObject rec) {
        String scope = j(rec, "inspection_scope").toUpperCase(Locale.ROOT);
        return scope.equals("RAW_MATERIAL_STAGE") || scope.equals("MATERIAL_INWARD") || !j(rec, "inward_lot_id").isEmpty();
    }

    static List<JSONObject> rawMetlabPlans(Api api, String partId) throws Exception {
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject p : plans(api, "METLAB", partId, true, null, null, null)) {
            String rs = j(p, "requirement_scope").isEmpty() ? "GENERAL" : j(p, "requirement_scope").toUpperCase(Locale.ROOT);
            if (isRawPlan(p) && !rs.equals("FINAL_METALLURGICAL")) out.add(p);
        }
        return out;
    }

    /** InspectionService.bend_plans: every approved Bend Test layout of the part. */
    static List<JSONObject> bendPlans(Api api, String partId) throws Exception {
        List<JSONObject> all = plans(api, "METLAB", partId, true, null, null, null);
        Map<String, String> methods = planMethods(api, all);
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject p : all) if (j(p, "inspection_method").equalsIgnoreCase(BEND_TEST) || BEND_TEST.equals(methods.get(j(p, "id")))) out.add(p);
        return out;
    }

    /** metlab_report._filter_plans_by_method. */
    static List<JSONObject> filterByMethod(Api api, List<JSONObject> plans, String requiredMethod, String partId) throws Exception {
        if (requiredMethod == null || requiredMethod.isEmpty()) return plans;
        if (BEND_TEST.equals(requiredMethod) && partId != null && !partId.isEmpty()) return bendPlans(api, partId);
        Map<String, String> methods = planMethods(api, plans);
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject p : plans) if (requiredMethod.equals(methods.get(j(p, "id")))) out.add(p);
        return out;
    }

    /** InspectionService.standalone_plans. */
    static List<JSONObject> standalonePlans(Api api, String layoutType, String partId, String scope, String processId) throws Exception {
        String lt = layoutType.toUpperCase(Locale.ROOT);
        List<JSONObject> candidates = plans(api, lt, partId, true, null, null, null);
        List<JSONObject> out = new ArrayList<>();
        if ("OSP_STAGE".equals(scope)) {
            for (JSONObject r : candidates) if (j(r, "process_id").equals(processId == null ? "" : processId) && j(r, "inward_type").equals("OSP_PROCESS")) out.add(r);
        } else if ("FINAL_DISPATCH_STAGE".equals(scope) && lt.equals("METLAB")) {
            for (JSONObject r : candidates) if (j(r, "requirement_scope").equals("FINAL_METALLURGICAL")) out.add(r);
        } else if (lt.equals("METLAB")) {
            out = rawMetlabPlans(api, partId);
        } else {
            for (JSONObject r : candidates) {
                String it = j(r, "inward_type").isEmpty() ? "MATERIAL_INWARD" : j(r, "inward_type");
                String rs = j(r, "requirement_scope").isEmpty() ? "GENERAL" : j(r, "requirement_scope");
                if (it.equals("MATERIAL_INWARD") && !rs.equals("FINAL_METALLURGICAL")) out.add(r);
            }
        }
        out.sort((x, y) -> {
            int c = j(y, "effective_date").compareTo(j(x, "effective_date"));
            if (c != 0) return c;
            c = j(y, "revision").compareTo(j(x, "revision"));
            if (c != 0) return c;
            return j(y, "updated_at").compareTo(j(x, "updated_at"));
        });
        return out;
    }

    /** InspectionService.standalone_osp_process_groups. */
    static List<JSONObject> ospProcessGroups(Api api, String partId, String layoutType) throws Exception {
        String flag = layoutType.equalsIgnoreCase("METLAB") ? "metlab_required" : "dimensional_required";
        List<JSONObject> groups = list(api.rows("part_process_specifications?select=*&part_id=eq." + Api.enc(partId)
            + "&inward_type=eq.OSP_PROCESS&status=eq.ACTIVE&order=sequence_no.asc&limit=1000"));
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject g : groups) {
            if (g.optBoolean(flag, false)) { out.add(g); continue; }
            JSONArray params = api.rows("part_process_parameter_specifications?select=id&process_specification_id=eq." + Api.enc(j(g, "id"))
                + "&inspection_type=eq." + layoutType.toUpperCase(Locale.ROOT) + "&status=eq.ACTIVE&limit=5");
            if (params.length() > 0) out.add(g);
        }
        return out;
    }

    /** InspectionService.standalone_part_context supplier ids (approved part supplier links + raw material sources). */
    static List<String> partSupplierIds(Api api, String partId) throws Exception {
        Set<String> ids = new java.util.LinkedHashSet<>();
        for (JSONObject r : list(api.rows("part_supplier_links?select=supplier_id&part_id=eq." + Api.enc(partId) + "&approved=is.true&limit=1000"))) if (!j(r, "supplier_id").isEmpty()) ids.add(j(r, "supplier_id"));
        for (JSONObject r : list(api.rows("part_raw_material_details?select=supplier_id&part_id=eq." + Api.enc(partId) + "&status=eq.ACTIVE&order=sequence_no.asc&limit=1000"))) if (!j(r, "supplier_id").isEmpty()) ids.add(j(r, "supplier_id"));
        return new ArrayList<>(ids);
    }

    /** Material Inward lots eligible for inspection (InspectionService.inward_lots). */
    static List<JSONObject> eligibleInwards(Api api) throws Exception {
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject r : list(api.rows("inward_lots?select=*&receipt_disposition=in.(ACCEPTED,ACCEPTED_UNDER_RESERVE)&order=created_at.desc&limit=4000"))) {
            if (!"REJECTED".equals(j(r, "status"))) out.add(r);
        }
        return out;
    }

    /** Labels of parts / parties for pick lists (id -> row). */
    static Map<String, JSONObject> byId(Api api, String table, String select, Set<String> ids) throws Exception {
        Map<String, JSONObject> out = new HashMap<>();
        List<String> l = new ArrayList<>();
        for (String id : ids) if (id != null && !id.isEmpty()) l.add(id);
        for (int s = 0; s < l.size(); s += 80) {
            for (JSONObject r : list(api.rows(table + "?select=" + select + "&id=in.(" + String.join(",", l.subList(s, Math.min(l.size(), s + 80))) + ")"))) out.put(j(r, "id"), r);
        }
        return out;
    }

    static String inwardLabel(JSONObject row, Map<String, JSONObject> parts, Map<String, JSONObject> parties) {
        JSONObject part = parts.get(j(row, "part_id"));
        JSONObject sup = parties.get(j(row, "supplier_id"));
        double steel = dbl(row, "steel_quantity_kg") != 0 ? dbl(row, "steel_quantity_kg") : dbl(row, "quantity_received");
        return j(row, "inward_number") + " · " + j(part, "part_number") + " · " + j(sup, "party_name") + " · Heat " + j(row, "heat_number")
            + " · Steel " + Ui.num(steel, 3) + " kg · Production " + Ui.num(dbl(row, "production_quantity_pcs"), 0) + " pcs";
    }

    static String planLabel(JSONObject p) {
        return j(p, "layout_name") + " · " + j(p, "plan_number") + " Rev " + j(p, "revision");
    }

    // ------------------------------------------------------------------ raw-material MetLAB cleaning
    static boolean charHasCaseDepth(JSONObject c) {
        return metadata(c).optBoolean("case_depth_traverse", false) || CASE_DEPTH.matcher(j(c, "characteristic")).find();
    }

    /** InspectionService.raw_material_results. */
    static JSONObject rawMaterialResults(Api api, JSONObject record, JSONObject results) throws Exception {
        JSONObject plan = get(api, "inspection_plans", j(record, "layout_plan_id"));
        if (plan == null || !isRawPlan(plan) || !j(plan, "part_id").equals(j(record, "part_id"))) {
            throw new Api.ApiException(422, "Raw Material MetLAB requires a matching Layout Master inward layout. Section H is Final Dispatch only. Select an approved inward layout and save the draft.");
        }
        List<JSONObject> chars = planChars(api, j(plan, "id"));
        Set<String> allowed = new HashSet<>();
        boolean caseDepth = false;
        for (JSONObject c : chars) { allowed.add(j(c, "id")); if (charHasCaseDepth(c)) caseDepth = true; }
        JSONObject clean = copy(results);
        JSONArray rows = new JSONArray();
        JSONArray src = results.optJSONArray("rows");
        for (int i = 0; src != null && i < src.length(); i++) {
            JSONObject r = src.optJSONObject(i);
            if (r != null && allowed.contains(j(r, "inspection_plan_characteristic_id"))) rows.put(r);
        }
        clean.put("rows", rows);
        if (!caseDepth) {
            clean.put("case_depth_applicable", false);
            clean.put("case_depth_locations", new JSONArray());
            clean.put("case_depth_traverse", new JSONArray());
            clean.put("case_depth_na_reason", "Not applicable for this approved layout.");
        }
        clean.put("chemistry_rows", new JSONArray());
        clean.put("jominy_rows", new JSONArray());
        clean.put("requirement_rows", new JSONArray());
        return clean;
    }

    // ------------------------------------------------------------------ finalize / amendment
    /** InspectionService._standalone_final_payload. */
    static JSONObject standaloneFinal(String disposition, String reason, String validator, String approver) throws Exception {
        String decision = disposition == null ? "" : disposition.trim().toUpperCase(Locale.ROOT).replace(' ', '_');
        if (!Arrays.asList(FINAL_DISPOSITIONS).contains(decision)) throw new Api.ApiException(422, "Select On Hold, Accepted, Accepted Under Reserve or Rejected.");
        boolean needsReason = decision.equals("ON_HOLD") || decision.equals("ACCEPTED_UNDER_RESERVE") || decision.equals("REJECTED");
        if (needsReason && (reason == null || reason.trim().isEmpty())) throw new Api.ApiException(422, "A hold, reserve or rejection reason is mandatory.");
        String now = now();
        JSONObject p = new JSONObject();
        p.put("disposition", decision);
        p.put("disposition_reason", nz(reason));
        p.put("validated_by_employee_id", validator);
        p.put("approved_by_employee_id", approver);
        p.put("validated_at", now);
        p.put("decision_at", decision.equals("ON_HOLD") ? JSONObject.NULL : now);
        p.put("status", decision.equals("ON_HOLD") ? "ON_HOLD" : "FINAL");
        p.put("overall_result", decision.equals("REJECTED") ? "FAIL" : (decision.equals("ON_HOLD") || decision.equals("ACCEPTED_UNDER_RESERVE") ? "HOLD" : "PASS"));
        return p;
    }

    /** InspectionService.finalize_dimensional / finalize_metlab (call on a background thread). */
    static void finalizeNow(Api api, String table, String id, String disposition, String reason, String validator, String approver) throws Exception {
        JSONObject record = get(api, table, id);
        if (record == null) throw new Api.ApiException(404, "Report not found.");
        boolean dim = table.equals("inspection_reports");
        boolean standalone = j(record, "inward_lot_id").isEmpty() && j(record, "osp_job_id").isEmpty();
        if (!dim && isRawRecord(record)) {
            JSONObject stored = record.optJSONObject("results") == null ? new JSONObject() : record.optJSONObject("results");
            JSONObject cleaned = rawMaterialResults(api, record, stored);
            boolean legacy = false;
            for (String k : new String[]{"chemistry_rows", "jominy_rows", "requirement_rows"}) {
                JSONArray arr = stored.optJSONArray(k);
                if (arr != null && arr.length() > 0) legacy = true;
            }
            JSONArray sr = stored.optJSONArray("rows");
            if ((sr == null ? 0 : sr.length()) != cleaned.getJSONArray("rows").length()) legacy = true;
            if (legacy) throw new Api.ApiException(422, "This inward report contains legacy non-layout requirements. Review the Layout Master parameters and save the draft before finalizing.");
        }
        if (standalone) {
            JSONObject payload = standaloneFinal(disposition, reason, validator, approver);
            int bad = 0;
            if (dim) {
                for (JSONObject r : list(api.rows("inspection_results?select=result&inspection_report_id=eq." + Api.enc(id) + "&limit=2000"))) {
                    String res = j(r, "result").toUpperCase(Locale.ROOT);
                    if (!res.equals("PASS") && !res.equals("NOT_APPLICABLE")) bad++;
                }
                if (payload.getString("disposition").equals("ACCEPTED") && bad > 0) throw new Api.ApiException(422, "Accepted is allowed only when every applicable characteristic passes.");
            } else {
                JSONObject res = record.optJSONObject("results") == null ? new JSONObject() : record.optJSONObject("results");
                for (String k : new String[]{"rows", "chemistry_rows", "jominy_rows", "requirement_rows"}) {
                    for (JSONObject r : list(res.optJSONArray(k))) {
                        String rr = j(r, "result").toUpperCase(Locale.ROOT);
                        if (!rr.equals("PASS") && !rr.equals("NOT_APPLICABLE")) bad++;
                    }
                }
                if (payload.getString("disposition").equals("ACCEPTED") && bad > 0 && (reason == null || reason.trim().isEmpty())) {
                    throw new Api.ApiException(422, "Manual acceptance reason is mandatory when applicable MetLAB results do not all pass.");
                }
            }
            api.update(table, id, payload);
            return;
        }
        JSONObject args = new JSONObject();
        args.put("p_report_id", id);
        args.put("p_disposition", disposition);
        args.put("p_reason", nz(reason));
        args.put("p_validated_by_employee_id", validator);
        args.put("p_approved_by_employee_id", approver);
        api.rpc(dim ? "qsms_finalize_dimensional_report" : "qsms_finalize_metlab_report", args);
    }

    /** "Finalize decision" action (disposition, reason, validator, approver). */
    static void finalizeAction(MainActivity a, String table, JSONObject row, Runnable refresh) {
        Api api = Api.get(a);
        if ("FINAL".equalsIgnoreCase(j(row, "status"))) {
            a.toast("This report is already FINAL. Use Controlled amendment only if a correction is needed.");
            return;
        }
        boolean osp = !j(row, "osp_job_id").isEmpty();
        List<Field> fields = new ArrayList<>();
        fields.add(Field.select("disposition", osp ? "Validation Decision" : "Final Decision", FINAL_DISPOSITIONS).labels(FINAL_LABELS).req());
        fields.add(Field.area("disposition_reason", osp ? "Hold / Reserve / Rejection Reason" : "Decision Reason")
            .hint("Required for On Hold, Accepted Under Reserve and Rejected"));
        fields.add(Field.lookup("validated_by_employee_id", "Validated By", Lookups.employees()).req());
        fields.add(Field.lookup("approved_by_employee_id", "Approved By", Lookups.employees()).req()
            .hint(osp ? "OSP approval is recorded against the signed-in employee" : ""));
        JSONObject values = new JSONObject();
        try {
            String d = j(row, "disposition");
            if (Arrays.asList(FINAL_DISPOSITIONS).contains(d)) values.put("disposition", d);
            values.put("disposition_reason", j(row, "disposition_reason"));
            if (!j(row, "validated_by_employee_id").isEmpty()) values.put("validated_by_employee_id", j(row, "validated_by_employee_id"));
            String ap = osp ? api.employeeId : (j(row, "approved_by_employee_id").isEmpty() ? api.employeeId : j(row, "approved_by_employee_id"));
            if (ap != null && !ap.isEmpty()) values.put("approved_by_employee_id", ap);
        } catch (Exception ignored) { }
        formDialog(a, osp ? "Finalize OSP Decision" : "Finalize Decision", fields, values, "Finalize", (form, v) -> {
            String disposition = form.str("disposition"), reason = form.str("disposition_reason");
            String validator = form.str("validated_by_employee_id"), approver = form.str("approved_by_employee_id");
            if (osp) {
                if (api.employeeId == null || api.employeeId.isEmpty()) throw new Api.ApiException(422, "Your login is not linked to an Employee record. Ask the System Administrator to link your user to your employee code.");
                if (!approver.equals(api.employeeId)) throw new Api.ApiException(422, "Approved By must be your own login employee — the database only accepts approval from the person signed in.");
            }
            a.toast("Finalizing…");
            Api.async(() -> { finalizeNow(api, table, j(row, "id"), disposition, reason, validator, approver); return true; }, (ok, err) -> {
                if (err != null) { a.toast(Api.message(err)); return; }
                a.toast(osp ? "OSP inspection decision finalized and the OSP quality gate was refreshed." : "Decision finalized successfully.");
                refresh.run();
            });
        });
    }

    /** core/password_edit.password_reopen_for_edit: back to DRAFT with an audit row and password check. */
    static void amendAction(MainActivity a, String table, String entityType, JSONObject row, Runnable refresh) {
        String status = j(row, "status").toUpperCase(Locale.ROOT);
        if (status.isEmpty() || status.equals("DRAFT") || status.equals("NEW")) { a.toast("This record is already a Draft and can be edited."); return; }
        Api api = Api.get(a);
        a.askText("Controlled amendment", "Edit / Amendment Reason", "Continue", true, reason ->
            a.confirmPassword("Unlock for Controlled Edit · current QCMS password", () -> Api.async(() -> {
                JSONObject audit = new JSONObject();
                audit.put("entity_type", entityType);
                audit.put("entity_id", j(row, "id"));
                audit.put("reason", reason.trim());
                audit.put("status_before", nzObj(row.opt("status")));
                audit.put("disposition_before", nzObj(row.opt("disposition")));
                api.insert("qcms_password_edit_audit", audit);
                JSONObject payload = new JSONObject().put("status", "DRAFT");
                if (table.equals("lab_tests") || table.equals("inspection_reports") || table.equals("rmtc_approvals")) {
                    payload.put("disposition", "PENDING");
                    payload.put("disposition_reason", "Controlled amendment: " + reason.trim());
                    payload.put("validated_by_employee_id", JSONObject.NULL);
                    payload.put("approved_by_employee_id", JSONObject.NULL);
                    payload.put("validated_at", JSONObject.NULL);
                    payload.put("decision_at", JSONObject.NULL);
                }
                api.update(table, j(row, "id"), payload);
                return true;
            }, (ok, err) -> {
                if (err != null) { a.toast(Api.message(err)); return; }
                a.toast("Record unlocked for controlled editing. Re-validation / approval is required after saving.");
                refresh.run();
            })));
    }

    // ------------------------------------------------------------------ report copies / photos
    static final String[] BEND_CAPTIONS = {"Load Vs CHT", "Bend Test Part / Bend Angle", "Plating Surface Condition", "Additional Bend Test Evidence"};
    static final String[] BEND_PHOTO_LABELS = {
        "Load Vs CHT graph (compression test report image)",
        "Part Bend Photograph · Bend Test Part photograph (bent part showing the angle)",
        "Plating surface close-up after bend (peeling / flaking check)",
        "Additional bend test evidence (optional)"};

    /** Upload a report copy / photo with the InspectionService.upload_attachment path. */
    static void uploadNow(MainActivity a, String entity, String id, String docType, String table, String field, Attachments.FileData file, Runnable done) {
        a.toast("Uploading " + file.name + "…");
        Api api = Api.get(a);
        Api.async(() -> Attachments.uploadReport(api, entity, id, docType, file, table, field), (path, err) -> {
            if (err != null) { a.toast("Upload failed: " + Api.message(err)); return; }
            a.toast("Uploaded.");
            if (done != null) done.run();
        });
    }

    static void dimensionalUploadAction(MainActivity a, JSONObject row, Runnable refresh) {
        a.pickFile("Attach Report", false, file -> uploadNow(a, "DIMENSIONAL_REPORT", j(row, "id"), "REPORT_COPY", "inspection_reports", "attachment_path", file, refresh));
    }

    static void metlabUploadAction(MainActivity a, JSONObject row, Runnable refresh) {
        boolean bend = BEND_TEST.equals(j(row.optJSONObject("results"), "inspection_method"));
        String[] labels = new String[5];
        labels[0] = "Attach MetLAB Report (report copy)";
        for (int i = 1; i <= 4; i++) labels[i] = bend ? "Photo " + i + " · " + BEND_PHOTO_LABELS[i - 1] : "Microstructure Photo " + i;
        new AlertDialog.Builder(a).setTitle("Photo / document").setItems(labels, (d, which) -> {
            if (which == 0) {
                a.pickFile(labels[0], false, file -> uploadNow(a, "METLAB_REPORT", j(row, "id"), "REPORT_COPY", "lab_tests", "attachment_path", file, refresh));
            } else {
                int slot = which;
                a.pickFile(labels[which], true, file -> uploadNow(a, "METLAB_REPORT", j(row, "id"), "MICROSTRUCTURE_" + slot, "lab_tests", "microstructure_image_" + slot + "_path", file, refresh));
            }
        }).setNegativeButton("Back", null).show();
    }

    /** Learned dropdown values (LearnedValueCatalog.remember) - failures never block the save. */
    static void remember(Api api, String key, String value) {
        if (value == null || value.trim().isEmpty()) return;
        try { api.rpc("qsms_remember_master_value", new JSONObject().put("p_field_key", key).put("p_value_text", value.trim())); } catch (Exception ignored) { }
    }

    static List<String> suggestions(Api api, String key) {
        List<String> out = new ArrayList<>();
        try {
            for (JSONObject r : list(api.rows("master_value_catalog?select=value_text&field_key=eq." + Api.enc(key) + "&status=eq.ACTIVE&order=usage_count.desc&limit=500"))) {
                String v = j(r, "value_text").trim();
                if (!v.isEmpty() && !out.contains(v)) out.add(v);
            }
        } catch (Exception ignored) { }
        return out;
    }

    /** Ordered map helper for pick lists. */
    static LinkedHashMap<String, String> map() { return new LinkedHashMap<>(); }
}
