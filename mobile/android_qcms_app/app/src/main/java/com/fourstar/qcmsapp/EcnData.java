package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.HashSet;

/**
 * R39 · ECN / PCN register (format FSI/806/F05 rev 00) - a port of core/ecn_service.py: part_ecns + part_ecn_actions,
 * number series qcms_next_ecn_number (ECN-&lt;PLANT&gt;-YYYY-####), status flow DRAFT -&gt; PENDING_APPROVAL -&gt;
 * APPROVED | DISAPPROVED -&gt; COMPLETED (CANCELLED from DRAFT / DISAPPROVED), approve / disapprove = Part Master approve
 * right (also enforced by trigger qcms_guard_part_ecn), COMPLETED refused while an action is open. The print is drawn
 * in the app's controlled print layout (RptDoc / RptPdf) with the sections of core/ecn_pdf.py.
 */
final class EcnData {
    private EcnData() { }

    static final String TABLE = "part_ecns", ACTIONS = "part_ecn_actions", ATTACHMENT_ENTITY = "PART_ECN";
    static final String FORMAT_NO = "FSI/806/F05", FORMAT_REV_NO = "00", FORMAT_REV_DATE = "25.09.2024";
    static final String[] STATUSES = {"DRAFT", "PENDING_APPROVAL", "APPROVED", "DISAPPROVED", "COMPLETED", "CANCELLED"};
    static final String[] PRIORITIES = {"Normal", "High", "Urgent", "Low"};
    static final String[][] SUPPORTING = {{"redline_drawing", "Redline Drawing"}, {"datasheet", "Datasheet"}, {"purchase_order", "Purchase Orders"},
        {"ppap", "PPAP"}, {"pfd", "PFD"}, {"control_plan", "CP"}, {"pfmea", "PFMEA"}, {"maintain_inventory", "Maintain Inventory"}};
    static final String[] MODES = {"AS_SUGGESTED", "NOT_AS_SUGGESTED", "OTHER"};
    static final String[] MODE_LABELS = {"As suggested", "Not as suggested", "Other (See Comments)"};
    static final String[] CUSTOMER_APPROVALS = {"PENDING", "APPROVED", "DISAPPROVED", "NOT_REQUIRED"};
    static final String[][] CONTACTS = {{"name", "Contact Name"}, {"address", "Address"}, {"phone", "Phone"}, {"fax", "Fax"}};
    static final String[] ACTION_STATUSES = {"OPEN", "IN_PROGRESS", "DONE", "NOT_REQUIRED"};
    static final String[][] DEFAULT_ACTIONS = {
        {"redline_drawing", "Drawing", "Release the revised drawing and withdraw the superseded copies from the shop floor"},
        {"pfd", "PFD", "Update the Process Flow Diagram"},
        {"control_plan", "Control Plan", "Update the Control Plan"},
        {"pfmea", "PFMEA", "Review / update the PFMEA"},
        {"ppap", "PPAP", "Prepare PPAP resubmission / customer approval"},
        {"purchase_order", "Purchase Orders", "Amend affected Purchase Orders"},
        {"maintain_inventory", "Inventory", "Disposition of existing stock (raw material / WIP / FG / at supplier)"},
    };
    static final String[][] SCOPES = {{"FINISH_DRAWING", "Finish Drawing"}, {"FORGING_DRAWING", "Forging Drawing"},
        {"HEAT_TREATMENT_DRAWING", "Heat Treatment Drawing"}, {"PROCESS_DRAWING", "Process Drawing"}, {"PROCESS_SPEC", "Process Specification"},
        {"PROCESS_FLOW", "Process Flow / Process List"}, {"GENERAL", "General change"}};
    /** status -> {target, permission} (TRANSITIONS). */
    static final Map<String, String[][]> TRANSITIONS = new HashMap<>();
    static {
        TRANSITIONS.put("DRAFT", new String[][]{{"PENDING_APPROVAL", "edit"}, {"CANCELLED", "edit"}});
        TRANSITIONS.put("PENDING_APPROVAL", new String[][]{{"APPROVED", "approve"}, {"DISAPPROVED", "approve"}, {"DRAFT", "edit"}});
        TRANSITIONS.put("DISAPPROVED", new String[][]{{"DRAFT", "edit"}, {"CANCELLED", "edit"}});
        TRANSITIONS.put("APPROVED", new String[][]{{"COMPLETED", "edit"}});
    }
    static final Set<String> EDITABLE = new HashSet<>(Arrays.asList("DRAFT", "DISAPPROVED"));
    static final Set<String> AFTER_SUBMIT = new HashSet<>(Arrays.asList("fsi_decision", "drawing_change_mode", "customer_approval", "customer_name_text",
        "fsi_approver_employee_id", "fsi_approval_date", "customer_approver_name", "customer_approval_date", "completed_by_employee_id",
        "completed_date", "comments", "benefit_of_change", "email_employee_ids"));

    static String s(JSONObject r, String k) { return r == null ? "" : Lookups.j(r, k); }

    static String status(JSONObject ecn) {
        String st = s(ecn, "status").toUpperCase(Locale.ROOT).replace(' ', '_');
        if (st.isEmpty()) return "DRAFT";
        switch (st) {
            case "SUBMITTED": return "PENDING_APPROVAL";
            case "REJECTED": return "DISAPPROVED";
            case "IMPLEMENTED": return "COMPLETED";
            default: return st;
        }
    }

    static String statusLabel(String st) { return "PENDING_APPROVAL".equals(st) ? "Pending Approval" : Ui.pretty(st); }

    static String transitionLabel(String target) {
        switch (target) {
            case "PENDING_APPROVAL": return "Submit for Approval";
            case "APPROVED": return "Approve";
            case "DISAPPROVED": return "Disapprove";
            case "COMPLETED": return "Mark Completed";
            case "DRAFT": return "Return to Draft";
            case "CANCELLED": return "Cancel";
            default: return Ui.pretty(target);
        }
    }

    static String changeTitle(String type) { return "PCN".equalsIgnoreCase(type) ? "PROCESS CHANGE NOTE" : "ENGINEERING CHANGE NOTE"; }

    static String scopeLabel(String scope) {
        for (String[] x : SCOPES) if (x[0].equalsIgnoreCase(scope)) return x[1];
        return scope == null || scope.isEmpty() ? "General change" : Ui.pretty(scope);
    }

    static String plantToken(String plant) {
        String t = (plant == null ? "" : plant).replaceAll("[^A-Za-z0-9]+", "").toUpperCase(Locale.ROOT);
        return t.isEmpty() ? "FSI" : t;
    }

    /** {can_edit/create, can_approve} of module PART_MASTER (qcms_effective_module_permission). */
    static boolean[] permissions(Api api) {
        if (api.isAdmin()) return new boolean[]{true, true, true};
        boolean[] out = new boolean[3];
        String[] keys = {"create", "edit", "approve"};
        for (int i = 0; i < 3; i++) {
            try {
                Object v = api.rpcValue("qcms_effective_module_permission", new JSONObject().put("p_module_key", "PART_MASTER").put("p_permission", keys[i]));
                out[i] = v != null && "true".equalsIgnoreCase(String.valueOf(v).trim());
            } catch (Exception e) { out[i] = false; }
        }
        return out;   // create, edit, approve
    }

    static List<String[]> allowedTargets(String status, boolean writable, boolean approve) {
        List<String[]> out = new ArrayList<>();
        String[][] t = TRANSITIONS.get(status);
        if (t == null) return out;
        for (String[] x : t) if ("approve".equals(x[1]) ? approve : writable) out.add(x);
        return out;
    }

    /** Plant code of the current branch / tenant (resolve_current_branch -> plant_token). */
    static String plant(Api api) {
        try {
            JSONArray r = api.rows("tenants?select=plant_code&limit=1");
            if (r.length() > 0 && !s(r.getJSONObject(0), "plant_code").isEmpty()) return plantToken(s(r.getJSONObject(0), "plant_code"));
        } catch (Exception ignored) { }
        return "FSI";
    }

    static String nextNumber(Api api, String type, String plant, String date) throws Exception {
        try {
            Object v = api.rpcValue("qcms_next_ecn_number", new JSONObject().put("p_change_type", type).put("p_plant_code", plant).put("p_date", date));
            String t = v == null ? "" : String.valueOf(v).trim();
            if (!t.isEmpty() && !"null".equals(t)) return t;
        } catch (Exception ignored) { }
        String prefix = type + "-" + plant + "-" + date.substring(0, 4) + "-";
        int last = 0;
        JSONArray rows = api.rows("part_ecns?select=ecn_number&ecn_number=like." + Api.enc(prefix + "*") + "&limit=5000");
        for (int i = 0; i < rows.length(); i++) {
            String d = s(rows.getJSONObject(i), "ecn_number").substring(Math.min(prefix.length(), s(rows.getJSONObject(i), "ecn_number").length())).replaceAll("\\D", "");
            if (!d.isEmpty()) last = Math.max(last, Integer.parseInt(d));
        }
        return prefix + String.format(Locale.ROOT, "%04d", last + 1);
    }

    /** validate_ecn (submitting = complete identification + change description). */
    static List<String> validate(JSONObject p, boolean submitting) {
        List<String> e = new ArrayList<>();
        if (s(p, "part_number").isEmpty() && s(p, "part_id").isEmpty()) e.add("Part No. is required.");
        if (s(p, "revision_requested").isEmpty()) e.add("Revision Requested (new description) is required.");
        if (submitting) {
            JSONArray reps = p.optJSONArray("fsi_representative_ids");
            if ((reps == null || reps.length() == 0) && s(p, "fsi_representatives_text").isEmpty()) e.add("Select at least one FSI Representative.");
            if (s(p, "drawing_number").isEmpty()) e.add("Drawing No. is required.");
            if (s(p, "part_name").isEmpty()) e.add("Part Name is required.");
            if (s(p, "previous_description").isEmpty()) e.add("Previous Description is required.");
        }
        return e;
    }

    /** ECNService.create: number from the server series, status DRAFT or PENDING_APPROVAL. */
    static JSONObject create(Api api, JSONObject payload, String status) throws Exception {
        List<String> errors = validate(payload, "PENDING_APPROVAL".equals(status));
        if (!errors.isEmpty()) throw new Api.ApiException(422, String.join(" ", errors));
        JSONObject p = new JSONObject(payload.toString());
        String plant = plantToken(s(p, "plant_code").isEmpty() ? plant(api) : s(p, "plant_code"));
        String date = s(p, "ecn_date").isEmpty() ? LocalDate.now().toString() : s(p, "ecn_date").substring(0, 10);
        String type = "PCN".equalsIgnoreCase(s(p, "change_type")) ? "PCN" : "ECN";
        p.put("change_type", type);
        p.put("ecn_date", date);
        p.put("plant_code", plant);
        p.put("ecn_number", nextNumber(api, type, plant, date));
        p.put("status", status);
        return api.insert(TABLE, p);
    }

    /** ECNService.save: after submission only the FSI-use / completion block, comments and e-mail list change. */
    static JSONObject save(Api api, JSONObject current, JSONObject payload) throws Exception {
        String st = status(current);
        JSONObject p = new JSONObject(payload.toString());
        if (!EDITABLE.contains(st)) {
            JSONObject only = new JSONObject();
            for (String k : AFTER_SUBMIT) if (p.has(k)) only.put(k, p.opt(k));
            p = only;
        } else {
            JSONObject merged = new JSONObject(current.toString());
            for (java.util.Iterator<String> it = p.keys(); it.hasNext(); ) { String k = it.next(); merged.put(k, p.opt(k)); }
            List<String> errors = validate(merged, false);
            if (!errors.isEmpty()) throw new Api.ApiException(422, String.join(" ", errors));
            if (!s(current, "ecn_number").isEmpty()) p.remove("change_type");
        }
        p.remove("ecn_number");
        p.remove("status");
        return api.update(TABLE, s(current, "id"), p);
    }

    static List<JSONObject> actions(Api api, String ecnId) throws Exception {
        return list(api.rows(ACTIONS + "?select=*&ecn_id=eq." + Api.enc(ecnId) + "&order=sequence_no.asc&limit=500"));
    }

    /** ECNService.transition. */
    static JSONObject transition(Api api, JSONObject current, String target, String remarks, boolean writable, boolean approve) throws Exception {
        String st = status(current);
        boolean ok = false;
        for (String[] x : allowedTargets(st, writable, approve)) if (x[0].equals(target)) ok = true;
        if (!ok) throw new Api.ApiException(403, "ECN " + s(current, "ecn_number") + ": " + st + " -> " + target + " is not allowed for your permission.");
        if ("PENDING_APPROVAL".equals(target)) {
            List<String> errors = validate(current, true);
            if (!errors.isEmpty()) throw new Api.ApiException(422, String.join(" ", errors));
        }
        JSONObject ch = new JSONObject();
        ch.put("status", target);
        String today = LocalDate.now().toString();
        if ("APPROVED".equals(target) || "DISAPPROVED".equals(target)) {
            ch.put("fsi_decision", target);
            if (s(current, "fsi_approval_date").isEmpty()) ch.put("fsi_approval_date", today);
            if (!api.employeeId.isEmpty() && s(current, "fsi_approver_employee_id").isEmpty()) ch.put("fsi_approver_employee_id", api.employeeId);
        }
        if ("COMPLETED".equals(target)) {
            int open = 0;
            for (JSONObject r : actions(api, s(current, "id"))) {
                String as = s(r, "status").toUpperCase(Locale.ROOT);
                if (as.equals("OPEN") || as.equals("IN_PROGRESS")) open++;
            }
            if (open > 0) throw new Api.ApiException(422, "ECN " + s(current, "ecn_number") + ": close every implementation action (DONE / NOT REQUIRED) before completing - "
                + open + " action(s) still open.");
            if (s(current, "completed_date").isEmpty()) ch.put("completed_date", today);
            if (!api.employeeId.isEmpty() && s(current, "completed_by_employee_id").isEmpty()) ch.put("completed_by_employee_id", api.employeeId);
        }
        if (remarks != null && !remarks.trim().isEmpty()) {
            String prefix = s(current, "comments");
            ch.put("comments", (prefix.isEmpty() ? "" : prefix + "\n") + "[" + target + " " + today + "] " + remarks.trim());
        }
        return api.update(TABLE, s(current, "id"), ch);
    }

    static JSONObject cancel(Api api, String ecnId, String reason) {
        try {
            JSONArray r = api.rows(TABLE + "?select=id,comments&id=eq." + Api.enc(ecnId) + "&limit=1");
            String note = r.length() > 0 ? s(r.getJSONObject(0), "comments") : "";
            String text = "[CANCELLED " + LocalDate.now() + "] " + (reason == null || reason.isEmpty() ? "Revision release failed." : reason);
            return api.update(TABLE, ecnId, new JSONObject().put("status", "CANCELLED").put("comments", (note.isEmpty() ? "" : note + "\n") + text));
        } catch (Exception e) {
            return null;
        }
    }

    /** default_actions: suggested implementation actions from the ticked supporting documents. */
    static List<JSONObject> defaultActions(JSONObject ecn) {
        List<JSONObject> out = new ArrayList<>();
        JSONObject flags = ecn.optJSONObject("supporting_documents");
        if (flags == null) return out;
        int seq = 0;
        for (String[] d : DEFAULT_ACTIONS) {
            if (!flags.optBoolean(d[0], false)) continue;
            seq += 10;
            try {
                out.add(new JSONObject().put("sequence_no", seq).put("affected_document", d[1]).put("action_text", d[2]).put("status", "OPEN")
                    .put("target_date", s(ecn, "response_by").isEmpty() ? JSONObject.NULL : s(ecn, "response_by")));
            } catch (Exception ignored) { }
        }
        return out;
    }

    /** revision_defaults: ECN form defaults for a drawing / document replacement (always an ECN, like the web). */
    static JSONObject revisionDefaults(JSONObject part, String scope, String drawingNumber, JSONObject current, String newRevision,
                                       String newRevisionDate, String processText, String newTitle) throws Exception {
        String label = scopeLabel(scope);
        String where = processText == null || processText.isEmpty() ? "" : " · " + processText;
        String prevNo = s(current, "drawing_number").isEmpty() ? drawingNumber : s(current, "drawing_number");
        String previous = label + where + " " + prevNo + " Rev " + (s(current, "revision").isEmpty() ? "-" : s(current, "revision"))
            + " dated " + (s(current, "revision_date").isEmpty() ? "-" : s(current, "revision_date"))
            + (s(current, "document_title").isEmpty() ? "" : " (" + s(current, "document_title") + ")");
        String requested = "Release " + label + where + " " + drawingNumber + " Rev " + newRevision
            + (newRevisionDate == null || newRevisionDate.isEmpty() ? "" : " dated " + newRevisionDate.substring(0, Math.min(10, newRevisionDate.length())))
            + (newTitle == null || newTitle.isEmpty() ? "" : " (" + newTitle + ")") + ". Describe the change: ";
        JSONObject d = new JSONObject();
        d.put("change_type", "ECN");
        d.put("document_scope", scope);
        d.put("part_id", s(part, "id"));
        d.put("part_number", s(part, "part_number"));
        d.put("part_name", s(part, "part_name"));
        d.put("drawing_number", drawingNumber);
        d.put("previous_revision", s(current, "revision"));
        d.put("new_revision", newRevision);
        d.put("previous_attachment_id", s(current, "id"));
        d.put("previous_description", previous);
        d.put("revision_requested", requested);
        d.put("supporting_documents", new JSONObject().put("redline_drawing", true));
        d.put("drawing_change_mode", "AS_SUGGESTED");
        d.put("customer_approval", "PENDING");
        return d;
    }

    /** process_change_defaults: PCN for a Part process list change. */
    static JSONObject processChangeDefaults(JSONObject part, String before, String after) throws Exception {
        JSONObject d = new JSONObject();
        d.put("change_type", "PCN");
        d.put("document_scope", "PROCESS_FLOW");
        d.put("part_id", s(part, "id"));
        d.put("part_number", s(part, "part_number"));
        d.put("part_name", s(part, "part_name"));
        d.put("drawing_number", s(part, "drawing_number"));
        d.put("previous_revision", s(part, "drawing_revision"));
        d.put("previous_description", "Previous process flow:\n" + (before == null || before.isEmpty() ? "-" : before));
        d.put("revision_requested", "Revision requested - new process flow:\n" + (after == null || after.isEmpty() ? "-" : after));
        d.put("supporting_documents", new JSONObject().put("purchase_order", true).put("ppap", true).put("pfd", true).put("control_plan", true).put("pfmea", true));
        d.put("customer_approval", "PENDING");
        d.put("drawing_change_mode", "AS_SUGGESTED");
        return d;
    }

    // ------------------------------------------------------------------ print (core/ecn_pdf.py sections in the app print layout)
    private static String dmy(String iso) {
        if (iso == null || iso.length() < 10 || iso.charAt(4) != '-') return iso == null ? "" : iso;
        return iso.substring(8, 10) + "." + iso.substring(5, 7) + "." + iso.substring(0, 4);
    }

    private static String box(boolean on) { return on ? "[X]" : "[  ]"; }

    private static String contact(JSONObject c, String key) { return c == null ? "" : s(c, key); }

    static RptDoc pdf(Api api, String ecnId) throws Exception {
        JSONArray r = api.rows(TABLE + "?select=*&id=eq." + Api.enc(ecnId) + "&limit=1");
        if (r.length() == 0) throw new Api.ApiException(404, "ECN not found or not visible for your role.");
        JSONObject e = r.getJSONObject(0);
        Map<String, String> emp = new HashMap<>();
        for (JSONObject x : list(api.rows("employees?select=id,employee_code,first_name,last_name&limit=5000"))) emp.put(s(x, "id"), employeeName(x));
        List<JSONObject> acts = actions(api, ecnId);
        String type = s(e, "change_type");
        boolean pcn = "PCN".equalsIgnoreCase(type);
        RptDoc d = new RptDoc(changeTitle(type));
        d.topMm = 32;
        d.bottomMm = 14;
        d.recordNumber = s(e, "ecn_number");
        d.reportLabel = "FMT NO. " + FORMAT_NO + " · REV. DATE " + FORMAT_REV_DATE + " · REV. NO. " + FORMAT_REV_NO;
        d.file(SndFiles.safeName(s(e, "ecn_number").isEmpty() ? "ECN" : s(e, "ecn_number")));
        RptReports.theme(api, d, "QUALITY_RECORD");
        float w = d.contentMm();
        String st = status(e);
        d.text(statusLabel(st).toUpperCase(Locale.ROOT) + " · " + FORMAT_NO + " Rev " + FORMAT_REV_NO, RptDoc.SUBTITLE);
        d.bar("RECORD DETAILS");
        d.labeled(new String[][]{
            {"ECN / PCN No.", s(e, "ecn_number"), "Date", dmy(s(e, "ecn_date"))},
            {"Plant", s(e, "plant_code"), "Status", statusLabel(st)},
            {"Requested Priority", s(e, "requested_priority"), "Response By", dmy(s(e, "response_by")) + (s(e, "response_by_party").isEmpty() ? "" : " · " + s(e, "response_by_party"))},
            {"Document", scopeLabel(s(e, "document_scope")), "Customer Approval", Ui.pretty(s(e, "customer_approval"))},
        }, RptReports.f(33, 61, 33, w - 127), 0, 2);
        List<String> reps = new ArrayList<>();
        JSONArray ids = e.optJSONArray("fsi_representative_ids");
        for (int i = 0; ids != null && i < ids.length(); i++) if (emp.containsKey(ids.optString(i))) reps.add(emp.get(ids.optString(i)));
        if (!s(e, "fsi_representatives_text").isEmpty()) reps.add(s(e, "fsi_representatives_text"));
        d.space(2.4f);
        d.bar("FSI REPRESENTATIVE(S)");
        d.text(reps.isEmpty() ? "-" : String.join(", ", reps), RptDoc.NORMAL);
        d.space(2.4f);
        d.bar("IDENTIFICATION");
        List<String[]> ident = new ArrayList<>();
        ident.add(new String[]{"", "TO", "CC", "FROM"});
        for (String[] c : CONTACTS) ident.add(new String[]{c[1], contact(e.optJSONObject("to_contact"), c[0]), contact(e.optJSONObject("cc_contact"), c[0]), contact(e.optJSONObject("from_contact"), c[0])});
        d.grid(ident.toArray(new String[0][]), RptReports.f(30, (w - 30) / 3, (w - 30) / 3, (w - 30) / 3));
        d.space(2.4f);
        d.bar("DRAWING CRITERIA · Fill in the information completely to expedite the process.");
        d.labeled(new String[][]{
            {"Drawing No.", s(e, "drawing_number"), "Part No.", s(e, "part_number")},
            {"Part Name", s(e, "part_name"), "Revision", (s(e, "previous_revision").isEmpty() ? "-" : s(e, "previous_revision")) + " -> " + (s(e, "new_revision").isEmpty() ? "-" : s(e, "new_revision"))},
        }, RptReports.f(33, 61, 33, w - 127), 0, 2);
        d.space(2.4f);
        d.bar("PREVIOUS DESCRIPTION");
        d.text(s(e, "previous_description").isEmpty() ? "-" : s(e, "previous_description"), RptDoc.NORMAL);
        d.space(2.4f);
        d.bar("REVISION REQUESTED");
        d.text(s(e, "revision_requested").isEmpty() ? "-" : s(e, "revision_requested"), RptDoc.NORMAL);
        d.space(2.4f);
        d.bar(pcn ? "SUPPORTING DOCUMENTS REQUIRED (Purchase Orders, PPAP, PFD, CP, PFMEA, inventory)" : "SUPPORTING DOCUMENTS ATTACHED (redline drawings, datasheets, etc.)");
        JSONObject sup = e.optJSONObject("supporting_documents");
        StringBuilder b = new StringBuilder();
        for (String[] x : SUPPORTING) b.append(box(sup != null && sup.optBoolean(x[0], false))).append(' ').append(x[1]).append("    ");
        d.text(b.toString().trim(), RptDoc.NORMAL);
        d.labeled(new String[][]{
            {"Purchase Orders Affected", box(e.optBoolean("po_affected", false)), "Current Inventory Affected",
                box(e.optBoolean("inventory_affected", false)) + (s(e, "inventory_qty").isEmpty() ? "" : "  Qty " + s(e, "inventory_qty"))},
            {"Current Demands Affected", box(e.optBoolean("demands_affected", false)) + (s(e, "demands_qty").isEmpty() ? "" : "  Qty " + s(e, "demands_qty")), "", ""},
        }, RptReports.f(45, 49, 45, w - 139), 0, 2);
        d.space(2.4f);
        d.bar("FSI USE ONLY (Check the appropriate box(s))");
        String decision = s(e, "fsi_decision").toUpperCase(Locale.ROOT);
        String mode = s(e, "drawing_change_mode").toUpperCase(Locale.ROOT);
        StringBuilder m = new StringBuilder();
        for (int i = 0; i < MODES.length; i++) m.append(box(MODES[i].equals(mode))).append(' ').append(MODE_LABELS[i]).append("   ");
        d.labeled(new String[][]{
            {"Decision", box("APPROVED".equals(decision)) + " Approved   " + box("DISAPPROVED".equals(decision)) + " Disapproved", "Drawing change to occur", m.toString().trim()},
            {"Customer", s(e, "customer_name_text"), "Customer Approval", Ui.pretty(s(e, "customer_approval"))},
            {"FSI Approval Signatory", emp.containsKey(s(e, "fsi_approver_employee_id")) ? emp.get(s(e, "fsi_approver_employee_id")) : "", "FSI Approval Date", dmy(s(e, "fsi_approval_date"))},
            {"Customer Approval Signatory", s(e, "customer_approver_name"), "Customer Approval Date", dmy(s(e, "customer_approval_date"))},
            {"Completed By", emp.containsKey(s(e, "completed_by_employee_id")) ? emp.get(s(e, "completed_by_employee_id")) : "", "Completed Date", dmy(s(e, "completed_date"))},
        }, RptReports.f(33, 61, 33, w - 127), 0, 2);
        d.space(2.4f);
        d.bar("COMMENTS / BENEFIT OF CHANGE");
        d.text("Comments: " + (s(e, "comments").isEmpty() ? "-" : s(e, "comments")), RptDoc.NORMAL);
        d.text("Benefit to this Change: " + (s(e, "benefit_of_change").isEmpty() ? "-" : s(e, "benefit_of_change")), RptDoc.NORMAL);
        if (!acts.isEmpty()) {
            d.keep(1000);   // page 2 (core/ecn_pdf.py _draw_actions continuation page)
            d.bar("IMPLEMENTATION ACTIONS (AFFECTED DOCUMENTS · RESPONSIBLE · TARGET DATE)");
            List<String[]> rows = new ArrayList<>();
            rows.add(new String[]{"#", "Affected Document", "Action", "Responsible", "Target Date", "Status", "Done On"});
            int i = 0;
            for (JSONObject x : acts) {
                i++;
                String resp = emp.containsKey(s(x, "responsible_employee_id")) ? emp.get(s(x, "responsible_employee_id")) : s(x, "responsible_text");
                rows.add(new String[]{String.valueOf(i), s(x, "affected_document"), s(x, "action_text"), resp, dmy(s(x, "target_date")), Ui.pretty(s(x, "status")), dmy(s(x, "completed_date"))});
            }
            d.grid(rows.toArray(new String[0][]), RptReports.f(8, 28, w - 8 - 28 - 32 - 20 - 20 - 20, 32, 20, 20, 20), 5);
        }
        return d;
    }

    // ------------------------------------------------------------------ local helpers (no dependency on other areas)
    static List<JSONObject> list(JSONArray a) {
        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; a != null && i < a.length(); i++) { JSONObject o = a.optJSONObject(i); if (o != null) out.add(o); }
        return out;
    }

    @SuppressWarnings("unchecked")
    static List<JSONObject> cast(Object o) { return (List<JSONObject>) o; }

    static String employeeName(JSONObject r) {
        String n = (s(r, "first_name") + " " + s(r, "last_name")).trim();
        return n.isEmpty() ? s(r, "employee_code") : n;
    }

    static String iso(String v) { return v == null || v.length() < 10 ? (v == null ? "" : v) : v.substring(0, 10); }

    static String[] pretty(String[] codes) {
        String[] out = new String[codes.length];
        for (int i = 0; i < codes.length; i++) out[i] = Ui.pretty(codes[i]);
        return out;
    }

    // ------------------------------------------------------------------ e-mail (core/ecn_service.ecn_email_text / notify_ecn_created, app_pages/ecn.email_ecn)
    static final String DEPARTMENT = "Engineering";
    static final String[] NOTIFY_DEPARTMENTS = {"Quality", "NPD"};

    /** ecn_email_text: {subject, body}; the subject starts with the department. */
    static String[] emailText(JSONObject e) {
        String title = Ui.pretty(changeTitle(s(e, "change_type")).replace(' ', '_'));
        String kind = "PCN".equalsIgnoreCase(s(e, "change_type")) ? "PCN" : "ECN";
        String st = statusLabel(status(e));
        String subject = DEPARTMENT + " · " + kind + " " + s(e, "ecn_number") + " · Part " + s(e, "part_number") + " · " + title + " · " + st;
        String body = "Dear Sir / Madam,\n\nPlease find attached " + title + " " + s(e, "ecn_number") + " dated " + s(e, "ecn_date") + ".\n"
            + "Part No.: " + s(e, "part_number") + "  ·  Part Name: " + s(e, "part_name") + "\n"
            + "Drawing No.: " + s(e, "drawing_number") + "  ·  Revision " + dash(s(e, "previous_revision")) + " -> " + dash(s(e, "new_revision")) + "\n"
            + "Requested priority: " + dash(s(e, "requested_priority")) + "  ·  Response by: " + dash(s(e, "response_by")) + "\n"
            + "Status: " + st + "\n\nRevision requested:\n" + dash(s(e, "revision_requested")) + "\n\nRegards,\nSTAWN QCMS";
        return new String[]{subject, body};
    }

    private static String dash(String v) { return v == null || v.isEmpty() ? "-" : v; }

    private static void addMail(List<String> out, String mail) {
        String m = mail == null ? "" : mail.trim();
        if (!m.contains("@")) return;
        for (String x : out) if (x.equalsIgnoreCase(m)) return;
        out.add(m);
    }

    /** Queue one outbox row with the ECN print attached and dispatch it through qcms-send-email. Returns "" or a note. */
    private static String queue(Api api, JSONObject ecn, String event, List<String> emails, String subject, String body, String dedupe, boolean automatic) throws Exception {
        byte[] pdf = RptPdf.render(pdf(api, s(ecn, "id")));
        JSONObject manifest = SndMail.uploadExport(api, SndMail.exportFolder(api), SndFiles.safeName((s(ecn, "ecn_number").isEmpty() ? "ECN" : s(ecn, "ecn_number")) + ".pdf"),
            pdf, "application/pdf", true);
        JSONArray cc = new JSONArray();
        for (int i = 1; i < emails.size(); i++) cc.put(emails.get(i));
        JSONObject row = new JSONObject();
        row.put("event_key", event);
        row.put("recipient_email", emails.get(0));
        row.put("recipient_name", JSONObject.NULL);
        row.put("cc_emails", cc);
        row.put("subject", SndMail.departmentSubject(subject, DEPARTMENT, event));
        row.put("body_text", body);
        row.put("body_html", SndMail.notificationHtml(body));
        row.put("related_table", TABLE);
        row.put("related_id", s(ecn, "id"));
        row.put("context", new JSONObject().put("department", DEPARTMENT).put("document_no", s(ecn, "ecn_number")).put("event_key", event)
            .put("document_type", changeTitle(s(ecn, "change_type"))));
        row.put("template_key", event);
        row.put("attachment_manifest", new JSONArray().put(manifest));
        row.put("dedupe_key", dedupe == null ? JSONObject.NULL : dedupe);
        row.put("is_automatic", automatic);
        row.put("status", "PENDING");
        JSONObject saved = api.insert("qcms_notification_outbox", row);
        List<String> ids = new ArrayList<>();
        if (!s(saved, "id").isEmpty()) ids.add(s(saved, "id"));
        JSONObject res = SndMail.dispatch(api, ids);
        return res.has("error") ? "Queued; delivery returned: " + res.optString("error") + "." : "";
    }

    /** notify_ecn_created: event ECN_CREATED -> Quality + NPD employees (print attached). Never throws; returns a note. */
    static String notifyCreated(Api api, JSONObject ecn) {
        try {
            JSONObject route = SndMail.route(api, "ECN_CREATED");
            List<JSONObject> employees = SndMail.employees(api);
            List<String> emails = new ArrayList<>();
            for (String dept : NOTIFY_DEPARTMENTS) for (String m : SndMail.departmentEmails(employees, dept, new ArrayList<>())) addMail(emails, m);
            if (route != null && route.optBoolean("department_cc", false))
                for (String m : SndMail.departmentEmails(employees, s(route, "department"), new ArrayList<>())) addMail(emails, m);
            if (emails.isEmpty()) return " No active Quality / NPD employee with an e-mail address in Employee Master.";
            String[] t = emailText(ecn);
            String subject = t[0].replaceFirst(java.util.regex.Pattern.quote(DEPARTMENT + " · "), DEPARTMENT + " · New ");
            String note = queue(api, ecn, "ECN_CREATED", emails, subject, t[1], "ECN_CREATED:" + s(ecn, "id"), true);
            return note.isEmpty() ? " Quality / NPD notified (" + emails.size() + ")." : " " + note;
        } catch (Exception e) {
            return " Quality / NPD notification failed: " + Api.message(e);
        }
    }

    /** email_ecn: the ECN print to selected employees (internal recipients only); marks emailed_at. */
    static String email(Api api, JSONObject ecn, List<String> employeeIds, String subject, String body) throws Exception {
        List<String> emails = new ArrayList<>();
        for (JSONObject e : SndMail.employees(api)) if (employeeIds.contains(s(e, "id"))) addMail(emails, s(e, "email"));
        if (emails.isEmpty()) throw new Api.ApiException(422, "The selected employees have no e-mail address in Employee Master.");
        String[] t = emailText(ecn);
        String event = "ECN_" + ("PCN".equalsIgnoreCase(s(ecn, "change_type")) ? "PCN" : "ECN");
        String note = queue(api, ecn, event, emails, subject == null || subject.isEmpty() ? t[0] : subject, body == null || body.isEmpty() ? t[1] : body, null, false);
        try { api.update(TABLE, s(ecn, "id"), new JSONObject().put("emailed_at", java.time.OffsetDateTime.now().toString())); } catch (Exception ignored) { }
        return note.isEmpty() ? "E-mailed to " + emails.size() + " employee(s) with the ECN print." : note;
    }

    static Map<String, String> employees(Api api) throws Exception {
        Map<String, String> out = new LinkedHashMap<>();
        for (JSONObject x : list(Lookups.rows(api, Lookups.employees()))) out.put(s(x, "id"), Lookups.EMPLOYEE.of(x));
        return out;
    }
}
