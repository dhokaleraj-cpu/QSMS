package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/**
 * R39 · PPAP Document Manager data layer - a port of core/ppap_service.py (R38) using the same tables
 * (ppap_packages, ppap_package_elements, ppap_element_documents, ppap_status_notes, ppap_customer_submissions,
 * ppap_element_master, ppap_customer_template_elements), the same storage keys
 * (quality-documents/&lt;tenant&gt;/ppap/&lt;package&gt;/&lt;NN_Element_name&gt;/&lt;token&gt;_&lt;file&gt;) and the same ZIP layout
 * ("NN Element name/file"). Permissions: public.qcms_ppap_can (module PPAP, falls back to NPD &amp; APQP rights).
 * Assignment e-mail: rpc qcms_ppap_assignment_mail -&gt; edge function qcms-send-email {"outbox_ids": [...]}.
 */
final class PpapData {
    private PpapData() { }

    static final String MODULE_KEY = "PPAP";
    static final String BUCKET = Api.BUCKET;
    static final int DUE_SOON_DAYS = 3;
    static final String[] ELEMENT_STATUSES = {"NOT_STARTED", "IN_PROGRESS", "COMPLETED", "NA", "REJECTED", "SUBMITTED"};   // UI order (Pending first)
    static final String[] PACKAGE_STATUSES = {"IN_PROGRESS", "SUBMITTED", "APPROVED", "ON_HOLD", "REJECTED", "CANCELLED", "CLOSED"};
    static final Set<String> INACTIVE_PACKAGE = new HashSet<>(java.util.Arrays.asList("APPROVED", "CANCELLED", "CLOSED"));
    static final String[] PSW_STATUSES = {"NOT_SUBMITTED", "INTERIM_SUBMITTED", "INTERIM_APPROVED", "FULL_SUBMITTED", "APPROVED", "REJECTED"};
    static final String[] LEVELS = {"1", "2", "3", "4", "5"};
    static final String[] DEPARTMENTS = {"Quality", "Engineering", "NPD", "Production", "Purchase", "Maintenance", "Logistics", "Sales"};
    static final Set<String> DUE_STATUSES = new HashSet<>(java.util.Arrays.asList("NOT_STARTED", "IN_PROGRESS", "REJECTED"));
    static final Object[][] DEFAULT_ELEMENTS = {
        {1, "Supplier Timing", true}, {2, "Fixtures/Tooling/Gaging", true}, {3, "Supply Chain Map", true}, {4, "Tiered Risk Assessment", true},
        {5, "DFMEA", false}, {6, "DVP", false}, {7, "Design Record", true}, {8, "Process Flow", true}, {9, "Floor Plan Layout", true},
        {10, "PFMEA", true}, {11, "Process Control Plan", true}, {12, "PM Plan", true}, {13, "Error proofing", true}, {14, "Vision Systems", false},
        {15, "Operator Instructions", true}, {16, "Visual Aids", true}, {17, "MSA", true}, {18, "Sub Supplier PPAP Approvals", true},
        {19, "Dimensional Results", true}, {20, "Material Certifications", true}, {21, "Shipping / Packaging", true}, {22, "Capability Studies", true},
        {23, "SP12 (Containment)", true}, {24, "DVP&R", true}, {25, "Run at Rate", true}, {26, "Launch Readiness Review", true},
        {27, "Interim approval action register", true}, {28, "Interim Submit", true}, {29, "Interim approved", true}, {30, "Full Submit", true},
        {31, "Approval", true}, {32, "IMDS", true},
    };
    private static final String[] DEFAULT_DEPT = {"", "NPD", "Engineering", "Purchase", "Quality", "Engineering", "Engineering", "Engineering", "Engineering",
        "Production", "Quality", "Quality", "Maintenance", "Engineering", "Engineering", "Production", "Quality", "Quality", "Purchase", "Quality", "Quality",
        "Logistics", "Quality", "Quality", "Engineering", "Production", "NPD", "Quality", "Quality", "Quality", "Quality", "Quality", "Quality"};

    // ------------------------------------------------------------------ small helpers
    static String s(JSONObject r, String k) { return r == null ? "" : Lookups.j(r, k); }

    static int num(JSONObject r, String k) {
        if (r == null) return 0;
        try { return (int) Math.round(Double.parseDouble(s(r, k))); } catch (Exception e) { return 0; }
    }

    static String statusLabel(String code) {
        String c = code == null ? "" : code.toUpperCase(Locale.ROOT);
        switch (c) {
            case "NOT_STARTED": case "": return "Pending";
            case "IN_PROGRESS": return "In progress";
            case "SUBMITTED": return "Submitted";
            case "COMPLETED": return "Completed";
            case "NA": return "NA";
            case "REJECTED": return "Rejected";
            default: return Ui.pretty(c);
        }
    }

    static String[] statusLabels(String[] codes) {
        String[] out = new String[codes.length];
        for (int i = 0; i < codes.length; i++) out[i] = statusLabel(codes[i]);
        return out;
    }

    static String defaultDepartment(int elementNo) {
        return elementNo > 0 && elementNo < DEFAULT_DEPT.length ? DEFAULT_DEPT[elementNo] : "Quality";
    }

    static LocalDate date(String iso) {
        if (iso == null || iso.length() < 10) return null;
        try { return LocalDate.parse(iso.substring(0, 10)); } catch (Exception e) { return null; }
    }

    /** element_state: completed / na / overdue / due_soon / submitted / rejected / open / not_planned. */
    static String state(JSONObject e, LocalDate today) {
        String st = s(e, "status").toUpperCase(Locale.ROOT);
        if (st.isEmpty()) st = "NOT_STARTED";
        if (st.equals("COMPLETED")) return "completed";
        if (st.equals("NA")) return "na";
        LocalDate due = date(s(e, "due_date"));
        if (due != null && due.isBefore(today)) return "overdue";
        if (st.equals("REJECTED")) return "rejected";
        if (due != null && !due.isAfter(today.plusDays(DUE_SOON_DAYS))) return "due_soon";
        if (st.equals("SUBMITTED")) return "submitted";
        if (due == null && st.equals("NOT_STARTED")) return "not_planned";
        return "open";
    }

    static String stateLabel(String state) {
        switch (state) {
            case "completed": return "Completed";
            case "na": return "NA";
            case "overdue": return "Overdue";
            case "due_soon": return "Due ≤ 3 days";
            case "submitted": return "Submitted";
            case "rejected": return "Rejected";
            case "not_planned": return "No due date";
            default: return "Pending / In progress";
        }
    }

    /** STATUS_COLORS (text, background). */
    static int[] stateColors(String state) {
        switch (state) {
            case "completed": return new int[]{0xFF166534, 0xFFDCFCE7};
            case "na": return new int[]{0xFF475569, 0xFFE2E8F0};
            case "overdue": return new int[]{0xFF991B1B, 0xFFFEE2E2};
            case "due_soon": return new int[]{0xFF9A3412, 0xFFFFEDD5};
            case "submitted": return new int[]{0xFF1D4ED8, 0xFFDBEAFE};
            case "rejected": return new int[]{0xFF9F1239, 0xFFFFE4E6};
            case "open": return new int[]{0xFF92400E, 0xFFFEF3C7};
            default: return new int[]{0xFF334155, 0xFFF1F5F9};
        }
    }

    /** package_progress: completed / applicable (NA excluded). Returns {total, na, applicable, completed, percent*10}. */
    static double[] progress(List<JSONObject> elements) {
        int total = elements.size(), na = 0, done = 0;
        for (JSONObject e : elements) {
            String st = s(e, "status").toUpperCase(Locale.ROOT);
            if (st.equals("NA")) na++;
            if (st.equals("COMPLETED")) done++;
        }
        int applicable = total - na;
        double pct = total == 0 ? 0 : (applicable == 0 ? 100 : Math.round(done * 1000.0 / applicable) / 10.0);
        return new double[]{total, na, applicable, done, pct};
    }

    static boolean active(JSONObject p) {
        String st = s(p, "status").toUpperCase(Locale.ROOT);
        return !INACTIVE_PACKAGE.contains(st.isEmpty() ? "IN_PROGRESS" : st);
    }

    /** portfolio_kpis: {packages, active, overdue, due_week, pending, percent}. */
    static Map<String, Double> kpis(List<JSONObject> packages, List<JSONObject> elements, LocalDate today) {
        Set<String> ids = new HashSet<>();
        for (JSONObject p : packages) if (active(p)) ids.add(s(p, "id"));
        int overdue = 0, dueWeek = 0, pending = 0;
        LocalDate weekEnd = today.plusDays(7);
        for (JSONObject e : elements) {
            if (!ids.contains(s(e, "package_id"))) continue;
            String st = s(e, "status").toUpperCase(Locale.ROOT);
            if (st.isEmpty()) st = "NOT_STARTED";
            if ("overdue".equals(state(e, today))) overdue++;
            LocalDate due = date(s(e, "due_date"));
            if (!st.equals("COMPLETED") && !st.equals("NA") && due != null && !due.isBefore(today) && !due.isAfter(weekEnd)) dueWeek++;
            if (DUE_STATUSES.contains(st)) pending++;
        }
        Map<String, Double> out = new LinkedHashMap<>();
        out.put("packages", (double) packages.size());
        out.put("active", (double) ids.size());
        out.put("overdue", (double) overdue);
        out.put("due_week", (double) dueWeek);
        out.put("pending", (double) pending);
        out.put("percent", progress(elements)[4]);
        return out;
    }

    /** next_revision: A -> B, Z -> AA, 01 -> 02, '' -> A. */
    static String nextRevision(String current) {
        String t = current == null ? "" : current.trim().toUpperCase(Locale.ROOT);
        if (t.isEmpty()) return "A";
        Matcher m = Pattern.compile("^(.*?)(\\d+)$").matcher(t);
        if (m.matches()) {
            String digits = m.group(2);
            String next = String.valueOf(Long.parseLong(digits) + 1);
            while (next.length() < digits.length()) next = "0" + next;
            return m.group(1) + next;
        }
        if (t.matches("[A-Z]+")) {
            char[] c = t.toCharArray();
            for (int i = c.length - 1; i >= 0; i--) {
                if (c[i] != 'Z') { c[i]++; return new String(c); }
                c[i] = 'A';
            }
            return "A" + new String(c);
        }
        return t + "-1";
    }

    /** safe_name (keep_spaces true / false). */
    static String safeName(String text, boolean keepSpaces) {
        String raw = text == null ? "" : text.trim();
        String out;
        if (keepSpaces) {
            out = raw.replaceAll("[^A-Za-z0-9 ._&()+-]+", " ").replaceAll("\\s+", " ").replaceAll("^[ ._]+|[ ._]+$", "");
        } else {
            out = raw.replaceAll("[^A-Za-z0-9._-]+", "_").replaceAll("_+", "_").replaceAll("^[_.]+|[_.]+$", "");
        }
        if (out.length() > 90) out = out.substring(0, 90);
        return out.isEmpty() ? "file" : out;
    }

    /** element_folder: '01 Supplier Timing', '21 Shipping - Packaging'. */
    static String elementFolder(int no, String name) {
        String n = (name == null || name.isEmpty() ? "Element" : name).replace("/", " - ");
        return String.format(Locale.ROOT, "%02d %s", no, safeName(n, true));
    }

    static String storagePath(String tenantId, String packageId, JSONObject element, String fileName) {
        String folder = safeName(elementFolder(num(element, "element_no"), s(element, "element_name")), false);
        return tenantId + "/ppap/" + packageId + "/" + folder + "/" + fileName;
    }

    /** package_number: PPAP-<ppap no>-<PART SLUG> (+ -2, -3 when taken). */
    static String packageNumber(String ppapNo, String partText, List<String> existing) {
        String slug = (partText == null ? "" : partText).toUpperCase(Locale.ROOT).replaceAll("[^A-Z0-9]+", "-").replaceAll("^-+|-+$", "");
        if (slug.length() > 40) slug = slug.substring(0, 40);
        if (slug.isEmpty()) slug = "PART";
        String no = ppapNo == null ? "" : ppapNo.trim();
        String base = no.isEmpty() ? "PPAP-" + slug : "PPAP-" + no + "-" + slug;
        Set<String> taken = new HashSet<>();
        for (String e : existing) taken.add(e == null ? "" : e.toUpperCase(Locale.ROOT));
        String candidate = base;
        int n = 2;
        while (taken.contains(candidate.toUpperCase(Locale.ROOT))) candidate = base + "-" + (n++);
        return candidate;
    }

    /** build_zip: one folder per element ("NN Element name/file"); duplicate names get " (2)"; extra files at the root. */
    static byte[] buildZip(List<Object[]> entries, List<Object[]> extra) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        Set<String> used = new HashSet<>();
        try (ZipOutputStream zip = new ZipOutputStream(out)) {
            for (Object[] x : extra) {
                String path = safeName((String) x[0], true);
                used.add(path.toLowerCase(Locale.ROOT));
                zip.putNextEntry(new ZipEntry(path));
                zip.write((byte[]) x[1]);
                zip.closeEntry();
            }
            for (Object[] e : entries) {   // {element_no, element_name, file_name, bytes}
                String folder = elementFolder((Integer) e[0], (String) e[1]);
                String file = safeName((String) e[2], true);
                String path = folder + "/" + file;
                int dot = file.lastIndexOf('.');
                int counter = 2;
                while (used.contains(path.toLowerCase(Locale.ROOT))) {
                    String alt = dot > 0 ? file.substring(0, dot) + " (" + counter + ")" + file.substring(dot) : file + " (" + counter + ")";
                    path = folder + "/" + alt;
                    counter++;
                }
                used.add(path.toLowerCase(Locale.ROOT));
                zip.putNextEntry(new ZipEntry(path));
                zip.write((byte[]) e[3]);
                zip.closeEntry();
            }
        }
        return out.toByteArray();
    }

    static String sha256(byte[] data) throws Exception {
        StringBuilder b = new StringBuilder();
        for (byte x : MessageDigest.getInstance("SHA-256").digest(data)) b.append(String.format(Locale.ROOT, "%02x", x));
        return b.toString();
    }

    static List<JSONObject> list(JSONArray a) {
        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; a != null && i < a.length(); i++) if (a.optJSONObject(i) != null) out.add(a.optJSONObject(i));
        return out;
    }

    /** template_sort_key: sort_order first, element number second. */
    static void sortElements(List<JSONObject> rows) {
        Collections.sort(rows, (x, y) -> {
            int ox = s(x, "sort_order").isEmpty() ? num(x, "element_no") : num(x, "sort_order");
            int oy = s(y, "sort_order").isEmpty() ? num(y, "element_no") : num(y, "sort_order");
            return ox != oy ? Integer.compare(ox, oy) : Integer.compare(num(x, "element_no"), num(y, "element_no"));
        });
    }

    static String employeeName(JSONObject e) {
        if (e == null) return "";
        String n = (s(e, "first_name") + " " + s(e, "last_name")).trim();
        return n.isEmpty() ? (s(e, "employee_code").isEmpty() ? s(e, "email") : s(e, "employee_code")) : n;
    }

    // ------------------------------------------------------------------ permissions (public.qcms_ppap_can)
    /** {view, create, edit, archive} through the database rule (module PPAP; NPD &amp; APQP while PPAP has no explicit row). */
    static boolean[] permissions(Api api) {
        boolean[] out = new boolean[4];
        String[] keys = {"view", "create", "edit", "archive"};
        for (int i = 0; i < keys.length; i++) {
            if (api.isAdmin()) { out[i] = true; continue; }
            try {
                Object v = api.rpcValue("qcms_ppap_can", new JSONObject().put("p_permission", keys[i]));
                out[i] = v != null && "true".equalsIgnoreCase(String.valueOf(v).trim());
            } catch (Exception e) {
                out[i] = i == 0;   // older database without the function: view only, writes are still checked by RLS
            }
        }
        return out;
    }

    // ------------------------------------------------------------------ reads
    static List<JSONObject> packages(Api api) throws Exception {
        return list(api.rows("ppap_packages?select=*&order=package_no.asc&limit=3000"));
    }

    static JSONObject pkg(Api api, String id) throws Exception {
        JSONArray r = api.rows("ppap_packages?select=*&id=eq." + Api.enc(id) + "&limit=1");
        if (r.length() == 0) throw new Api.ApiException(404, "PPAP package not found or not visible for your role.");
        return r.getJSONObject(0);
    }

    static List<JSONObject> elements(Api api, String packageId) throws Exception {
        List<JSONObject> rows = list(api.rows("ppap_package_elements?select=*&package_id=eq." + Api.enc(packageId) + "&order=element_no.asc&limit=500"));
        sortElements(rows);
        return rows;
    }

    static List<JSONObject> allElements(Api api) throws Exception {
        return list(api.rows("ppap_package_elements?select=id,package_id,element_no,element_name,status,due_date,responsible_employee_id,sort_order&limit=20000"));
    }

    static List<JSONObject> documents(Api api, String packageId) throws Exception {
        return list(api.rows("ppap_element_documents?select=*&package_id=eq." + Api.enc(packageId) + "&status=eq.ACTIVE&order=uploaded_at.desc&limit=2000"));
    }

    static List<JSONObject> packagesForApqp(Api api, String projectId) throws Exception {
        return list(api.rows("ppap_packages?select=*&apqp_project_id=eq." + Api.enc(projectId) + "&order=package_no.asc&limit=200"));
    }

    // ------------------------------------------------------------------ writes (PpapService)
    static double refreshProgress(Api api, String packageId) {
        try {
            double pct = progress(elements(api, packageId))[4];
            api.update("ppap_packages", packageId, new JSONObject().put("completion_percent", pct));
            return pct;
        } catch (Exception e) {
            return 0;
        }
    }

    /** template_for: the customer's own template when it exists, else the default element master (seeded with 32 elements). */
    static Object[] template(Api api, String customerId) throws Exception {
        List<JSONObject> rows = new ArrayList<>();
        boolean fromMaster = true;
        if (customerId != null && !customerId.isEmpty()) {
            try {
                rows = list(api.rows("ppap_customer_template_elements?select=*&customer_id=eq." + Api.enc(customerId) + "&limit=500"));
            } catch (Exception ignored) { rows = new ArrayList<>(); }
            if (!rows.isEmpty()) fromMaster = false;
        }
        if (rows.isEmpty()) {
            rows = list(api.rows("ppap_element_master?select=*&order=element_no.asc&limit=500"));
            if (rows.isEmpty()) {
                for (Object[] d : DEFAULT_ELEMENTS) {
                    int no = (Integer) d[0];
                    api.insert("ppap_element_master", new JSONObject().put("element_no", no).put("element_name", d[1]).put("default_required", d[2])
                        .put("default_lead_days", 0).put("default_department", defaultDepartment(no)).put("sort_order", no).put("status", "ACTIVE"));
                }
                rows = list(api.rows("ppap_element_master?select=*&order=element_no.asc&limit=500"));
            }
        }
        sortElements(rows);
        List<JSONObject> activeRows = new ArrayList<>();
        for (JSONObject r : rows) if (s(r, "status").isEmpty() || "ACTIVE".equalsIgnoreCase(s(r, "status"))) activeRows.add(r);
        return new Object[]{activeRows, fromMaster};
    }

    /** create_package: insert the package + one element per ACTIVE template element (non-required start as NA). */
    @SuppressWarnings("unchecked")
    static JSONObject createPackage(Api api, JSONObject header, String defaultDue, String responsibleId) throws Exception {
        JSONObject payload = new JSONObject(header.toString());
        if (s(payload, "package_no").trim().isEmpty()) {
            List<String> taken = new ArrayList<>();
            for (JSONObject p : list(api.rows("ppap_packages?select=package_no&limit=5000"))) taken.add(s(p, "package_no"));
            String part = s(payload, "customer_part_no");
            payload.put("package_no", packageNumber(s(payload, "customer_ppap_no"), part.isEmpty() ? "PART" : part, taken));
        }
        if (s(payload, "status").isEmpty()) payload.put("status", "IN_PROGRESS");
        if (s(payload, "psw_status").isEmpty()) payload.put("psw_status", "NOT_SUBMITTED");
        if (s(payload, "submission_level").isEmpty()) payload.put("submission_level", 3);
        JSONObject saved = api.insert("ppap_packages", payload);
        String packageId = s(saved, "id");
        Object[] t = template(api, s(payload, "customer_id"));
        List<JSONObject> tpl = (List<JSONObject>) t[0];
        boolean fromMaster = (Boolean) t[1];
        int order = 0;
        for (JSONObject m : tpl) {
            order++;
            int lead = num(m, "default_lead_days");
            String due = lead > 0 ? LocalDate.now().plusDays(lead).toString() : (defaultDue == null || defaultDue.isEmpty() ? null : defaultDue);
            boolean required = !m.has("default_required") || m.isNull("default_required") || m.optBoolean("default_required", true);
            int no = num(m, "element_no");
            JSONObject e = new JSONObject();
            e.put("package_id", packageId);
            e.put("element_master_id", fromMaster ? s(m, "id") : JSONObject.NULL);
            e.put("element_no", no);
            e.put("element_name", s(m, "element_name"));
            e.put("status", required ? "NOT_STARTED" : "NA");
            e.put("due_date", required && due != null ? due : JSONObject.NULL);
            e.put("responsible_employee_id", required && responsibleId != null && !responsibleId.isEmpty() ? responsibleId : JSONObject.NULL);
            String dept = s(m, "default_department");
            e.put("responsible_department", dept.isEmpty() ? defaultDepartment(no) : dept);
            e.put("sort_order", s(m, "sort_order").isEmpty() ? order : num(m, "sort_order"));
            api.insert("ppap_package_elements", e);
        }
        refreshProgress(api, packageId);
        return saved;
    }

    /** header_from_apqp: APQP project -> new package defaults. */
    static JSONObject headerFromApqp(JSONObject project, JSONObject part) throws Exception {
        String digits = s(project, "submission_level").replaceAll("\\D", "");
        int level = digits.isEmpty() ? 3 : Math.max(1, Math.min(5, digits.charAt(0) - '0'));
        JSONObject h = new JSONObject();
        h.put("apqp_project_id", s(project, "id"));
        h.put("part_id", s(project, "part_id"));
        h.put("customer_id", s(project, "customer_id"));
        h.put("customer_part_no", part == null ? "" : s(part, "part_number"));
        h.put("submission_level", String.valueOf(level));
        String due = s(project, "target_submission_date");
        h.put("customer_due_date", due.length() >= 10 ? due.substring(0, 10) : "");
        h.put("owner_employee_id", s(project, "coordinator_employee_id"));
        h.put("remarks", ("Created from APQP project " + s(project, "project_code")).trim());
        return h;
    }

    /** save one element (save_elements for a single row): returns true when a new responsible employee was assigned. */
    static boolean saveElement(Api api, JSONObject before, JSONObject values) throws Exception {
        String status = s(values, "status").isEmpty() ? "NOT_STARTED" : s(values, "status");
        String completed = s(values, "completed_date");
        if (status.equals("COMPLETED") && completed.isEmpty()) completed = LocalDate.now().toString();
        if (!status.equals("COMPLETED")) completed = "";
        JSONObject payload = new JSONObject();
        payload.put("status", status);
        payload.put("due_date", nz(s(values, "due_date")));
        payload.put("responsible_employee_id", nz(s(values, "responsible_employee_id")));
        payload.put("completed_date", nz(completed));
        payload.put("remarks", nz(s(values, "remarks").trim()));
        if (values.has("responsible_department")) payload.put("responsible_department", nz(s(values, "responsible_department").trim()));
        if (!s(values, "element_name").trim().isEmpty()) payload.put("element_name", s(values, "element_name").trim());
        JSONObject changes = new JSONObject();
        for (java.util.Iterator<String> it = payload.keys(); it.hasNext(); ) {
            String k = it.next();
            String now = payload.isNull(k) ? "" : String.valueOf(payload.opt(k));
            String was = s(before, k);
            if (k.endsWith("_date") && was.length() > 10) was = was.substring(0, 10);
            if (!now.equals(was)) changes.put(k, payload.opt(k));
        }
        if (changes.length() == 0) return false;
        api.update("ppap_package_elements", s(before, "id"), changes);
        refreshProgress(api, s(before, "package_id"));
        return changes.has("responsible_employee_id") && !changes.isNull("responsible_employee_id");
    }

    static Object nz(String v) { return v == null || v.isEmpty() ? JSONObject.NULL : v; }

    /** needs_assignment_mail (core/ppap_service.py): an open element whose responsible person was newly set / changed,
     *  or whose due date changed while a responsible person is assigned, gets the assignment e-mail. */
    static boolean needsAssignmentMail(JSONObject before, JSONObject after) {
        String resp = after == null || after.isNull("responsible_employee_id") ? "" : s(after, "responsible_employee_id");
        String status = s(after, "status").toUpperCase(Locale.ROOT);
        if (resp.isEmpty() || status.equals("COMPLETED") || status.equals("NA")) return false;
        if (!resp.equals(s(before, "responsible_employee_id"))) return true;
        return !day10(after == null || after.isNull("due_date") ? "" : s(after, "due_date")).equals(day10(s(before, "due_date")));
    }

    private static String day10(String v) { return v == null ? "" : (v.length() > 10 ? v.substring(0, 10) : v); }

    /** notify_assignments: in-app notification (bell / push) to the newly assigned employee. Never throws. */
    static void notifyAssignment(Api api, JSONObject pkg, JSONObject element, String employeeId) {
        try {
            JSONObject args = new JSONObject();
            args.put("p_recipient_profile_id", JSONObject.NULL);
            args.put("p_recipient_employee_id", employeeId);
            args.put("p_title", String.format(Locale.ROOT, "PPAP task: %02d %s", num(element, "element_no"), s(element, "element_name")));
            args.put("p_body", "Package " + s(pkg, "package_no") + " · due " + (s(element, "due_date").isEmpty() ? "not set" : Ui.date(s(element, "due_date")))
                + " · upload the document in PPAP → Package.");
            args.put("p_category", "TASK");
            args.put("p_module_key", MODULE_KEY);
            args.put("p_related_table", "ppap_package_elements");
            args.put("p_related_id", s(element, "id"));
            args.put("p_web_route", "ppap-package");
            api.rpc("qcms_notify", args);
        } catch (Exception ignored) { }
    }

    /**
     * R39 assignment e-mail (contract of agent P, migration 20261029100000_qcms_r39_ppap_mail.sql):
     * rpc qcms_ppap_assignment_mail(p_package_id, p_element_ids, p_resend, p_app_url) -> uuid[] outbox ids, then
     * edge function qcms-send-email {"outbox_ids": [...]}. Returns a short user message; NEVER throws (a save is never blocked).
     */
    static String assignmentMail(Api api, String packageId, List<String> elementIds, boolean resend) {
        try {
            JSONObject args = new JSONObject();
            args.put("p_package_id", packageId);
            if (elementIds == null || elementIds.isEmpty()) args.put("p_element_ids", JSONObject.NULL);
            else { JSONArray ids = new JSONArray(); for (String id : elementIds) ids.put(id); args.put("p_element_ids", ids); }
            args.put("p_resend", resend);
            args.put("p_app_url", BuildConfig.QCMS_WEB_URL == null || BuildConfig.QCMS_WEB_URL.isEmpty() ? JSONObject.NULL : BuildConfig.QCMS_WEB_URL);
            Object v = api.rpcValue("qcms_ppap_assignment_mail", args);
            List<String> outbox = new ArrayList<>();
            if (v instanceof JSONArray) for (int i = 0; i < ((JSONArray) v).length(); i++) {
                String id = ((JSONArray) v).optString(i, "");
                if (!id.isEmpty() && !"null".equals(id)) outbox.add(id);
            } else if (v != null) {
                for (String id : String.valueOf(v).replaceAll("[{}\\[\\]\"]", "").split(",")) if (!id.trim().isEmpty()) outbox.add(id.trim());
            }
            if (outbox.isEmpty()) return "No assignment e-mail queued (no responsible employee with an e-mail address).";
            JSONObject res = SndMail.dispatch(api, outbox);
            String err = res.optString("error", "");
            if (!err.isEmpty() && !"null".equals(err)) return outbox.size() + " assignment e-mail(s) queued; delivery returned: " + err;
            return outbox.size() + " assignment e-mail(s) sent to the responsible person(s).";
        } catch (Exception e) {
            return "Assignment e-mail not sent: " + Api.message(e);
        }
    }

    // ------------------------------------------------------------------ documents
    /** upload_document: storage key without spaces, revision auto (next of the current), previous -> not latest, Pending/Rejected -> In progress. */
    static JSONObject upload(Api api, JSONObject pkg, JSONObject element, Attachments.FileData f, String revision, String remarks) throws Exception {
        if (f.data == null || f.data.length == 0) throw new Api.ApiException(422, "The selected file is empty.");
        List<JSONObject> previous = list(api.rows("ppap_element_documents?select=*&package_element_id=eq." + Api.enc(s(element, "id")) + "&status=eq.ACTIVE&limit=500"));
        JSONObject latest = null;
        for (JSONObject d : previous) if (d.optBoolean("is_latest", false)) latest = d;
        String rev = revision == null || revision.trim().isEmpty() ? (latest == null ? "A" : nextRevision(s(latest, "revision"))) : revision.trim();
        String token = UUID.randomUUID().toString().replace("-", "").substring(0, 12);
        String path = storagePath(api.tenantId, s(pkg, "id"), element, token + "_" + safeName(f.name, false));
        String mime = f.mime == null || f.mime.isEmpty() ? "application/octet-stream" : f.mime;
        api.upload(path, f.data, mime, false);
        JSONObject saved;
        try {
            JSONObject row = new JSONObject();
            row.put("package_id", s(pkg, "id"));
            row.put("package_element_id", s(element, "id"));
            row.put("revision", rev);
            row.put("file_name", f.name);
            row.put("object_path", path);
            row.put("mime_type", mime);
            row.put("size_bytes", f.data.length);
            row.put("checksum", sha256(f.data));
            row.put("is_latest", true);
            row.put("status", "ACTIVE");
            row.put("uploaded_by_name", nz(api.fullName == null || api.fullName.isEmpty() ? api.email : api.fullName));
            row.put("uploaded_by_employee_id", nz(api.employeeId));
            row.put("remarks", nz(remarks == null ? "" : remarks.trim()));
            saved = api.insert("ppap_element_documents", row);
        } catch (Exception e) {
            api.removeObject(path);
            throw e;
        }
        for (JSONObject d : previous) if (d.optBoolean("is_latest", false)) api.update("ppap_element_documents", s(d, "id"), new JSONObject().put("is_latest", false));
        String st = s(element, "status").toUpperCase(Locale.ROOT);
        if (st.isEmpty() || st.equals("NOT_STARTED") || st.equals("REJECTED")) {
            api.update("ppap_package_elements", s(element, "id"), new JSONObject().put("status", "IN_PROGRESS"));
            refreshProgress(api, s(pkg, "id"));
        }
        return saved;
    }

    static void setLatest(Api api, JSONObject doc) throws Exception {
        for (JSONObject d : list(api.rows("ppap_element_documents?select=id,is_latest&package_element_id=eq." + Api.enc(s(doc, "package_element_id")) + "&limit=500"))) {
            boolean want = s(d, "id").equals(s(doc, "id"));
            if (d.optBoolean("is_latest", false) != want) api.update("ppap_element_documents", s(d, "id"), new JSONObject().put("is_latest", want));
        }
    }

    static void archive(Api api, JSONObject doc) throws Exception {
        api.update("ppap_element_documents", s(doc, "id"), new JSONObject().put("status", "ARCHIVED").put("is_latest", false));
        List<JSONObject> remaining = list(api.rows("ppap_element_documents?select=id,is_latest,uploaded_at,created_at&package_element_id=eq."
            + Api.enc(s(doc, "package_element_id")) + "&status=eq.ACTIVE&order=uploaded_at.asc&limit=500"));
        boolean any = false;
        for (JSONObject d : remaining) if (d.optBoolean("is_latest", false)) any = true;
        if (!remaining.isEmpty() && !any) api.update("ppap_element_documents", s(remaining.get(remaining.size() - 1), "id"), new JSONObject().put("is_latest", true));
    }

    /** ZIP of the given documents in "NN Element name/" folders (package_zip without the web-only cover sheets). */
    static byte[] zip(Api api, List<JSONObject> docs, List<JSONObject> elements) throws Exception {
        Map<String, JSONObject> byId = new LinkedHashMap<>();
        for (JSONObject e : elements) byId.put(s(e, "id"), e);
        List<Object[]> entries = new ArrayList<>();
        for (JSONObject d : docs) {
            JSONObject e = byId.get(s(d, "package_element_id"));
            if (e == null) continue;   // own_documents: never another package's files
            if (!s(d, "package_id").isEmpty() && !s(d, "package_id").equals(s(e, "package_id"))) continue;
            byte[] bytes = api.download(s(d, "object_path"));
            entries.add(new Object[]{num(e, "element_no"), s(e, "element_name"), s(d, "file_name"), bytes});
        }
        if (entries.isEmpty()) throw new Api.ApiException(404, "No documents to download.");
        return buildZip(entries, new ArrayList<>());
    }

    /** Log a device download in ppap_customer_submissions (method DOWNLOAD, status DOWNLOADED) like the web. Never throws. */
    static void logDownload(Api api, JSONObject pkg, List<JSONObject> docs, List<JSONObject> elements) {
        try {
            Map<String, JSONObject> byId = new LinkedHashMap<>();
            for (JSONObject e : elements) byId.put(s(e, "id"), e);
            JSONArray list = new JSONArray();
            long total = 0;
            for (JSONObject d : docs) {
                JSONObject e = byId.get(s(d, "package_element_id"));
                list.put(new JSONObject().put("element_no", e == null ? JSONObject.NULL : (Object) num(e, "element_no"))
                    .put("element_name", e == null ? JSONObject.NULL : s(e, "element_name")).put("file_name", s(d, "file_name"))
                    .put("revision", s(d, "revision")).put("document_id", s(d, "id")).put("size_bytes", d.optLong("size_bytes", 0)));
                total += d.optLong("size_bytes", 0);
            }
            JSONObject row = new JSONObject();
            row.put("package_id", s(pkg, "id"));
            row.put("sent_to", "Downloaded on the QCMS Android app");
            row.put("method", "DOWNLOAD");
            row.put("documents", list);
            row.put("document_count", docs.size());
            row.put("total_bytes", total);
            row.put("status", "DOWNLOADED");
            row.put("sent_by_name", nz(api.fullName == null || api.fullName.isEmpty() ? api.email : api.fullName));
            api.insert("ppap_customer_submissions", row);
        } catch (Exception ignored) { }
    }

    static String webPackageUrl(String packageId) {
        return "ppap-package?ppap=" + packageId;
    }
}
