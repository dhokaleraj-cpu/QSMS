package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/** core/access.py + app_pages/user_access.py constants and the effective-permission rules (with source). */
final class AdmPerm {
    private AdmPerm() { }

    static final String[] ROLES = {
        "ADMIN", "MANAGEMENT", "SUPPLY_CHAIN", "PROCUREMENT", "BUSINESS_DEVELOPMENT",
        "QUALITY_MANAGER", "METLAB_APPROVER", "QUALITY_ENGINEER", "PRODUCTION", "SQA",
        "MASTER_DATA", "AUDITOR", "VIEWER"};
    static final String[] ACCESS_STATUSES = {"ACTIVE", "INACTIVE", "LOCKED"};

    /** MODULES (key, label). */
    static final String[][] MODULES = {
        {"PART_MASTER", "Part Master"}, {"MATERIAL_GRADE", "Material Grade"}, {"REFERENCE_MASTERS", "Reference Masters"},
        {"EMPLOYEE_MASTER", "Employee Master"}, {"RMTC_ENTRY", "RMTC Entry"}, {"MATERIAL_INWARD", "Material Inward"},
        {"OSP_TRANSACTIONS", "OSP Transactions"}, {"INSPECTION_LAYOUTS", "Inspection Layouts"}, {"DIMENSIONAL_REPORT", "Dimensional Report"},
        {"METLAB_REPORT", "MetLAB Report"}, {"NPD_APQP", "NPD & APQP"}, {"QC_CALCULATION_TOOLS", "QC Calculation Tools"},
        {"COMPLAINT_MANAGEMENT", "Complaint Management"}, {"CALIBRATION_VALIDATION", "Calibration & Validation"},
        {"SUPPLY_CHAIN", "Supply Chain"}, {"USER_ACCESS", "Users & Access"}};

    /** Permission columns in grid order with the website column headers. */
    static final String[][] PERMS = {
        {"can_view", "View"}, {"can_create", "Entry/Create"}, {"can_edit", "Edit"},
        {"can_validate", "Validate/Review"}, {"can_approve", "Approve"}, {"can_archive", "Delete/Archive"}};

    /** SECTION_CATALOG (module, section, label). */
    static final String[][] SECTIONS = {
        {"PART_MASTER", "BASIC_IDENTITY", "Part Master · Basic Identity / Drawing"},
        {"PART_MASTER", "RAW_MATERIAL_DETAILS", "Part Master · Raw Material Details / Approved Sources"},
        {"PART_MASTER", "SUPPLIER_TECHNICAL", "Part Master · Supplier Technical Data"},
        {"PART_MASTER", "PRICE_HISTORY", "Part Master · Supplier Price History"},
        {"PART_MASTER", "HEAT_TREATMENT", "Part Master · Heat Treatment / Metallurgical"},
        {"PART_MASTER", "PROCESS_SPECIFICATIONS", "Part Master · Process Specifications"},
        {"MATERIAL_GRADE", "GRADE_IDENTITY", "Material Grade · Grade Identity / Standard"},
        {"MATERIAL_GRADE", "CHEMICAL_COMPOSITION", "Material Grade · Chemical Composition"},
        {"MATERIAL_GRADE", "HARDENABILITY", "Material Grade · Jominy / Hardenability"},
        {"REFERENCE_MASTERS", "PARTIES", "Reference Masters · Suppliers / Customers / Steel Mills"},
        {"REFERENCE_MASTERS", "PROCESSES", "Reference Masters · Processes / Inspection Stages"},
        {"REFERENCE_MASTERS", "QUALITY_ASSETS", "Reference Masters · Quality Assets / Standards"},
        {"REFERENCE_MASTERS", "REUSABLE_VALUES", "Reference Masters · Reusable Controlled Values"},
        {"EMPLOYEE_MASTER", "IDENTITY", "Employee Master · Identity / Contact"},
        {"EMPLOYEE_MASTER", "ORGANIZATION", "Employee Master · Department / Reports-To"},
        {"EMPLOYEE_MASTER", "APPROVAL_AUTHORITY", "Employee Master · Approval Authority"},
        {"RMTC_ENTRY", "HEADER", "RMTC · Header Entry / Approved RM Source"},
        {"RMTC_ENTRY", "PART_WORKSHEET", "RMTC · Part Worksheet"},
        {"RMTC_ENTRY", "VALIDATION", "RMTC · Validation / Decision"},
        {"RMTC_ENTRY", "REPORTS", "RMTC · Records / Print Layout"},
        {"MATERIAL_INWARD", "RECEIPT_ENTRY", "Material Inward · Receipt Entry"},
        {"MATERIAL_INWARD", "SOURCE_TRACEABILITY", "Material Inward · RMTC / Heat / Source Traceability"},
        {"MATERIAL_INWARD", "QUALITY_GATE", "Material Inward · Quality Gate / Disposition"},
        {"MATERIAL_INWARD", "RECORDS", "Material Inward · Records / Reports"},
        {"OSP_TRANSACTIONS", "MATERIAL_OUT", "OSP · Material Out"},
        {"OSP_TRANSACTIONS", "SAMPLE", "OSP · Sample Receipt / Gate"},
        {"OSP_TRANSACTIONS", "DIMENSIONAL_GATE", "OSP · Dimensional Inspection Gate"},
        {"OSP_TRANSACTIONS", "METLAB_GATE", "OSP · MetLAB Inspection Gate"},
        {"OSP_TRANSACTIONS", "INWARD", "OSP · Inward / Production Release"},
        {"OSP_TRANSACTIONS", "RECORDS", "OSP · Records / Traceability"},
        {"INSPECTION_LAYOUTS", "HEADER", "Inspection Layouts · Header / Scope"},
        {"INSPECTION_LAYOUTS", "CHARACTERISTICS", "Inspection Layouts · Characteristics"},
        {"INSPECTION_LAYOUTS", "CASE_DEPTH_CONFIGURATION", "Inspection Layouts · Case Depth Traverse Setup"},
        {"INSPECTION_LAYOUTS", "APPROVAL", "Inspection Layouts · Approval / Revision"},
        {"DIMENSIONAL_REPORT", "ENTRY", "Dimensional · Entry / Report Header"},
        {"DIMENSIONAL_REPORT", "RESULTS", "Dimensional · Inspection Results"},
        {"DIMENSIONAL_REPORT", "FINAL_DECISION", "Dimensional · Conclusion / Final Decision"},
        {"DIMENSIONAL_REPORT", "RECORDS", "Dimensional · Records / Print / Excel"},
        {"METLAB_REPORT", "ENTRY", "MetLAB · Entry / Report Header"},
        {"METLAB_REPORT", "CHEMICAL_ANALYSIS", "MetLAB · Chemical Analysis"},
        {"METLAB_REPORT", "CASE_DEPTH", "MetLAB · Case Depth Traverse"},
        {"METLAB_REPORT", "MICROSTRUCTURE", "MetLAB · Photographs / Evidence"},
        {"METLAB_REPORT", "REFERENCES", "MetLAB · Reference Documents / Statements"},
        {"METLAB_REPORT", "FINAL_DECISION", "MetLAB · Conclusion / Final Decision"},
        {"METLAB_REPORT", "RECORDS", "MetLAB · Records / Print / Excel"},
        {"NPD_APQP", "PROCESS_FLOW", "NPD / APQP · Process Flow Designer"},
        {"NPD_APQP", "ORDER_STATUS", "NPD / APQP · NPD Status / Target Dates"},
        {"NPD_APQP", "APQP", "NPD / APQP · APQP"},
        {"NPD_APQP", "RECORDS", "NPD / APQP · Records / Reports"},
        {"QC_CALCULATION_TOOLS", "CALCULATORS", "QC Calculation Tools · Calculators"},
        {"QC_CALCULATION_TOOLS", "SAVED_RESULTS", "QC Calculation Tools · Saved Results / Reports"},
        {"COMPLAINT_MANAGEMENT", "COMPLAINT_ENTRY", "Complaints · Customer / Supplier Complaint Entry"},
        {"COMPLAINT_MANAGEMENT", "TRACEABILITY", "Complaints · Heat / Batch / Photo Traceability"},
        {"COMPLAINT_MANAGEMENT", "COMMERCIAL", "Complaints · Commercial / Debit Note"},
        {"COMPLAINT_MANAGEMENT", "RECORDS", "Complaints · Records / PDF / Excel"},
        {"CALIBRATION_VALIDATION", "GAUGE_FIXTURE_LINKS", "Calibration · Gauge / Fixture Part-Process Links"},
        {"CALIBRATION_VALIDATION", "CALIBRATION_RECORDS", "Calibration · Calibration / Validation Records"},
        {"CALIBRATION_VALIDATION", "STANDARD_ROOM", "Calibration · Standard Room Inspection"},
        {"CALIBRATION_VALIDATION", "REMINDERS", "Calibration · Due Dates / Reminders"},
        {"SUPPLY_CHAIN", "CUSTOMER_ORDERS", "Supply Chain · Customer Orders / Schedules"},
        {"SUPPLY_CHAIN", "RM_PROCUREMENT", "Supply Chain · RM Procurement"},
        {"SUPPLY_CHAIN", "PURCHASE_ORDERS", "Supply Chain · Purchase Orders"},
        {"SUPPLY_CHAIN", "PO_COMMERCIAL", "Supply Chain · PO Commercial / Price Fields"},
        {"SUPPLY_CHAIN", "PO_REPORTS", "Supply Chain · Purchase Order Reports"},
        {"SUPPLY_CHAIN", "RM_RECEIPT", "Supply Chain · RM Receipt / Material Inward"},
        {"SUPPLY_CHAIN", "RM_TO_FORGING", "Supply Chain · RM to Forging"},
        {"SUPPLY_CHAIN", "FORGING", "Supply Chain · Forging Order / Receipt"},
        {"SUPPLY_CHAIN", "MACHINING_DISPATCH", "Supply Chain · Machining / FG / Dispatch"},
        {"SUPPLY_CHAIN", "OPENING_STOCK", "Supply Chain · Opening Stock"},
        {"SUPPLY_CHAIN", "TRACEABILITY", "Supply Chain · Traceability / MIS"},
        {"USER_ACCESS", "USER_IDENTITY", "Users & Access · User / Employee Link"},
        {"USER_ACCESS", "MODULE_PERMISSIONS", "Users & Access · Module Permissions"},
        {"USER_ACCESS", "SECTION_PERMISSIONS", "Users & Access · Section Permissions"},
        {"USER_ACCESS", "DEFAULTS_APPROVAL_ROUTES", "Users & Access · Role / Department Defaults & Approval Routes"},
        {"USER_ACCESS", "AUDIT", "Users & Access · Activity Audit"},
    };

    static final String[] FIXED_DEPARTMENTS = {"Production", "Supply Chain", "Procurement", "Quality", "METLAB", "Management", "Business Development", "R & D", "HR", "Accounts"};

    static String moduleLabel(String key) {
        for (String[] m : MODULES) if (m[0].equals(key)) return m[1];
        return key;
    }

    static String normRole(String role) {
        String r = role == null || role.trim().isEmpty() ? "VIEWER" : role.trim();
        return r.toUpperCase(java.util.Locale.ROOT).replace(" ", "_");
    }

    /** Effective rights + their source (module_permissions_with_source). */
    static final class Effective {
        final JSONObject values; final String source;
        Effective(JSONObject values, String source) { this.values = values; this.source = source; }
        boolean has(String perm) { return AdmPy.truthy(values, perm); }
    }

    static JSONObject permissionRow(JSONObject row) {
        JSONObject o = new JSONObject();
        try {
            for (String[] p : PERMS) o.put(p[0], AdmPy.truthy(row, p[0]));
        } catch (Exception ignored) { }
        return o;
    }

    /** _legacy_role_permissions. */
    static JSONObject legacy(String roleText, String module) {
        String role = normRole(roleText);
        JSONObject o = new JSONObject();
        try {
            if (role.equals("VIEWER") || role.equals("AUDITOR")) {
                for (String[] p : PERMS) o.put(p[0], p[0].equals("can_view"));
                return o;
            }
            Set<String> supply = set("SUPPLY_CHAIN", "PROCUREMENT", "PRODUCTION", "MANAGEMENT");
            Set<String> quality = set("QUALITY_MANAGER", "QUALITY_ENGINEER", "METLAB_APPROVER", "SQA");
            boolean write;
            if (module.equals("SUPPLY_CHAIN")) write = supply.contains(role) || role.equals("QUALITY_MANAGER") || role.equals("MASTER_DATA");
            else if (set("RMTC_ENTRY", "MATERIAL_INWARD", "DIMENSIONAL_REPORT", "METLAB_REPORT", "OSP_TRANSACTIONS").contains(module))
                write = quality.contains(role) || role.equals("PRODUCTION") || role.equals("MANAGEMENT");
            else if (module.equals("NPD_APQP")) write = quality.contains(role) || set("PRODUCTION", "BUSINESS_DEVELOPMENT", "MANAGEMENT", "MASTER_DATA").contains(role);
            else if (module.equals("CALIBRATION_VALIDATION")) write = quality.contains(role) || role.equals("MANAGEMENT") || role.equals("MASTER_DATA");
            else write = quality.contains(role) || role.equals("MASTER_DATA") || role.equals("MANAGEMENT");
            boolean validate = set("QUALITY_MANAGER", "QUALITY_ENGINEER", "METLAB_APPROVER", "SQA", "SUPPLY_CHAIN", "PROCUREMENT", "MANAGEMENT").contains(role);
            boolean approve;
            if (module.equals("DIMENSIONAL_REPORT")) approve = set("QUALITY_MANAGER", "QUALITY_ENGINEER", "SQA", "MANAGEMENT").contains(role);
            else if (module.equals("METLAB_REPORT")) approve = set("QUALITY_MANAGER", "METLAB_APPROVER", "MANAGEMENT").contains(role);
            else approve = role.equals("MANAGEMENT");
            o.put("can_view", true); o.put("can_create", write); o.put("can_edit", write);
            o.put("can_archive", false); o.put("can_validate", validate); o.put("can_approve", approve);
        } catch (Exception ignored) { }
        return o;
    }

    private static Set<String> set(String... v) { return new HashSet<>(Arrays.asList(v)); }

    private static Map<String, JSONObject> byModule(JSONArray rows) {
        Map<String, JSONObject> out = new HashMap<>();
        for (int i = 0; rows != null && i < rows.length(); i++) {
            JSONObject r = rows.optJSONObject(i);
            if (r == null) continue;
            String k = AdmPy.j(r, "module_key").toUpperCase(java.util.Locale.ROOT);
            if (!out.containsKey(k)) out.put(k, r);
        }
        return out;
    }

    private static JSONArray safeRows(Api api, String path) {
        try { return new JSONArray(api.get(path, false).body); } catch (Exception e) { return new JSONArray(); }
    }

    /** _profile_department: linked Employee Master department (profile_id first, then email). */
    static String profileDepartment(Api api, JSONObject profile) {
        String value = AdmPy.j(profile, "department").trim();
        if (!value.isEmpty()) return value;
        String pid = AdmPy.j(profile, "id").trim();
        String email = AdmPy.fold(AdmPy.j(profile, "email").trim());
        JSONArray rows = safeRows(api, "employees?select=id,profile_id,email,department&status=eq.ACTIVE&limit=5000");
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.optJSONObject(i);
            if (r != null && !pid.isEmpty() && pid.equals(AdmPy.j(r, "profile_id"))) return AdmPy.j(r, "department").trim();
        }
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.optJSONObject(i);
            if (r != null && !email.isEmpty() && email.equals(AdmPy.fold(AdmPy.j(r, "email").trim()))) return AdmPy.j(r, "department").trim();
        }
        return "";
    }

    /** module_permissions_with_source for every module (call on a background thread). */
    static Map<String, Effective> effectiveAll(Api api, JSONObject profile) {
        Map<String, Effective> out = new LinkedHashMap<>();
        String role = normRole(AdmPy.j(profile, "role"));
        if (role.equals("ADMIN")) {
            JSONObject all = new JSONObject();
            try { for (String[] p : PERMS) all.put(p[0], true); } catch (Exception ignored) { }
            for (String[] m : MODULES) out.put(m[0], new Effective(all, "ADMIN"));
            for (String[] s : SECTIONS) if (!out.containsKey(s[0])) out.put(s[0], new Effective(all, "ADMIN"));
            return out;
        }
        String pid = AdmPy.j(profile, "id");
        Map<String, JSONObject> user = byModule(safeRows(api, "user_module_permissions?select=*&profile_id=eq." + Api.enc(pid) + "&limit=200"));
        Map<String, JSONObject> roles = byModule(safeRows(api, "role_module_defaults?select=*&role=eq." + Api.enc(role) + "&status=eq.ACTIVE&limit=200"));
        String dept = profileDepartment(api, profile);
        Map<String, JSONObject> depts = dept.isEmpty() ? new HashMap<>()
            : byModule(safeRows(api, "department_module_defaults?select=*&department=eq." + Api.enc(dept) + "&status=eq.ACTIVE&limit=200"));
        String roleText = role.replace('_', ' ');
        for (String[] m : MODULES) {
            String k = m[0];
            if (user.containsKey(k)) out.put(k, new Effective(permissionRow(user.get(k)), "USER OVERRIDE"));
            else if (roles.containsKey(k)) out.put(k, new Effective(permissionRow(roles.get(k)), "ROLE · " + roleText));
            else if (depts.containsKey(k)) out.put(k, new Effective(permissionRow(depts.get(k)), "DEPARTMENT · " + dept));
            else out.put(k, new Effective(legacy(role, k), "LEGACY ROLE · " + roleText));
        }
        return out;
    }

    /** Current user's effective right through the same database function the RLS uses. */
    static boolean current(Api api, String module, String permission) {
        if (api.isAdmin()) return true;
        try {
            Object v = api.rpcValue("qcms_effective_module_permission", new JSONObject().put("p_module_key", module).put("p_permission", permission));
            return v != null && "true".equalsIgnoreCase(String.valueOf(v).trim());
        } catch (Exception e) {
            return false;
        }
    }
}
