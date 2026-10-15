package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Port of app_pages/master_import.py for CSV files: same IMPORTABLE list, header mapping (field names, labels and
 * COMMON_SYNONYMS), value cleaning, lookup resolution, MasterService normalize / validate / duplicate rules
 * (natural key, identity fuzzy match, duplicates inside the file) and the Employee Master import path.
 * Rows are only ever inserted (existing / duplicate rows are skipped). Network methods run inside Api.async.
 */
final class AdmImport {
    private AdmImport() { }

    /** IMPORTABLE (key, label, access module). */
    static final String[][] IMPORTABLE = {
        {"parts", "Part Master", "PART_MASTER"}, {"material_grades", "Material Grade", "MATERIAL_GRADE"},
        {"chemical_composition", "Chemical Composition", "MATERIAL_GRADE"}, {"customers", "Customers", "REFERENCE_MASTERS"},
        {"suppliers", "Suppliers", "REFERENCE_MASTERS"}, {"steel_mills", "Steel Mills", "REFERENCE_MASTERS"},
        {"osp_vendors", "OSP Vendors", "REFERENCE_MASTERS"}, {"processes", "Processes", "REFERENCE_MASTERS"},
        {"customer_standards", "Customer Standards & Specifications", "REFERENCE_MASTERS"}, {"inspection_stages", "Inspection Stages", "REFERENCE_MASTERS"},
        {"quality_assets", "Quality Assets", "REFERENCE_MASTERS"}, {"inspection_plans", "Inspection Plans", "INSPECTION_LAYOUTS"},
        {"inspection_characteristics", "Inspection Characteristics", "INSPECTION_LAYOUTS"}, {"test_plans", "Test Plans", "INSPECTION_LAYOUTS"},
        {"employees", "Employee Master", "EMPLOYEE_MASTER"}};

    static String[] importable(String key) {
        for (String[] i : IMPORTABLE) if (i[0].equals(key)) return i;
        return IMPORTABLE[0];
    }

    // ------------------------------------------------------------------ master definitions (core/master_definitions.py)
    static final class F {
        final String name, label, kind, lookup; final boolean required; final Object def;
        F(String name, String label, String kind, boolean required, Object def, String lookup) {
            this.name = name; this.label = label; this.kind = kind; this.required = required; this.def = def; this.lookup = lookup;
        }
    }

    static final class Def {
        final String key, label, table, order;
        final List<F> fields = new ArrayList<>();
        String[] natural = new String[0], identity = new String[0];
        String arrayType = "";
        JSONArray fixedPartyTypes;
        String auto = "";
        Def(String key, String label, String table, String order) { this.key = key; this.label = label; this.table = table; this.order = order; }
        Def f(String name, String label, String kind, boolean req, Object def) { fields.add(new F(name, label, kind, req, def, "")); return this; }
        Def lk(String name, String label, String lookup, boolean req) { fields.add(new F(name, label, "lookup", req, null, lookup)); return this; }
        Def nat(String... n) { natural = n; return this; }
        Def id(String... n) { identity = n; return this; }
        Def party(String filterType, String... types) {
            arrayType = filterType;
            fixedPartyTypes = new JSONArray();
            for (String t : types) fixedPartyTypes.put(t);
            return this;
        }
        Def auto(String f) { auto = f; return this; }
        /** list_records select path (array_filter -> contains). */
        String listPath() {
            return table + "?select=*" + (arrayType.isEmpty() ? "" : "&party_types=cs.%7B" + arrayType + "%7D") + "&order=" + order + ".asc&limit=1000";
        }
    }

    private static Def party(String key, String label, String filter, String... types) {
        return new Def(key, label, "parties", "party_code")
            .f("party_code", "Master code", "text", true, null).f("party_name", "Name", "text", true, null)
            .f("country", "Country", "text", false, null).f("state", "State / Region", "text", false, null).f("city", "City", "text", false, null)
            .f("address", "Address", "textarea", false, null).f("contact_person", "Contact person", "text", false, null)
            .f("email", "Primary Email", "text", false, null).f("notification_emails", "Notification Email(s)", "text", false, null)
            .f("phone", "Phone", "text", false, null).f("tax_identifier", "GSTIN / Tax identifier", "text", false, null)
            .f("approval_status", "Approval status", "select", true, "APPROVED").f("status", "Record status", "select", true, "ACTIVE")
            .f("remarks", "Remarks", "textarea", false, null)
            .nat("party_code").id("party_name").party(filter, types).auto("party_code");
    }

    static final Map<String, Def> DEFS = new LinkedHashMap<>();
    static {
        DEFS.put("customers", party("customers", "Customers", "CUSTOMER", "CUSTOMER"));
        DEFS.put("suppliers", party("suppliers", "Suppliers", "SUPPLIER", "SUPPLIER"));
        DEFS.put("steel_mills", party("steel_mills", "Steel Mills", "STEEL_MILL", "STEEL_MILL"));
        DEFS.put("osp_vendors", party("osp_vendors", "OSP Vendors", "OSP_VENDOR", "OSP_VENDOR", "SUPPLIER"));
        DEFS.put("parts", new Def("parts", "Parts", "parts", "part_number")
            .f("part_number", "Part number", "text", true, null).f("fsi_part_number", "FSI Part Number", "text", false, null)
            .f("part_name", "Part description", "text", true, null)
            .lk("customer_id", "Customer", "customers", true).lk("material_grade_id", "Material grade", "material_grades", true)
            .f("drawing_number", "Drawing number", "text", false, null).f("drawing_revision", "Drawing revision", "text", false, null)
            .f("finished_weight_kg", "Finished weight (kg)", "number", false, null).f("forging_weight_kg", "Forging weight (kg)", "number", false, null)
            .f("gross_weight_kg", "Gross weight (kg)", "number", false, null).f("section_size", "Raw material section", "text", false, null)
            .f("manufacturing_route", "Manufacturing route", "textarea", false, null)
            .f("special_characteristics", "Special characteristics / Jominy / heat-treatment details", "json", false, null)
            .f("status", "Record status", "select", true, "ACTIVE").f("remarks", "Remarks", "textarea", false, null)
            .nat("part_number").id("fsi_part_number"));
        DEFS.put("material_grades", new Def("material_grades", "Material Grades", "material_grades", "grade_code")
            .f("grade_code", "Grade", "text", true, null).f("standard", "Standard", "text", false, null)
            .f("revision", "Revision", "text", false, "Current").f("effective_date", "Effective date", "date", false, null)
            .f("status", "Record status", "select", true, "ACTIVE").f("remarks", "Remarks", "textarea", false, null)
            .nat("grade_code", "revision").id("grade_code"));
        DEFS.put("chemical_composition", new Def("chemical_composition", "Chemical Composition", "material_grade_elements", "element")
            .lk("material_grade_id", "Material grade", "material_grades", true).f("element", "Element", "text", true, null)
            .f("minimum", "Minimum", "number", false, null).f("maximum", "Maximum", "number", false, null)
            .f("unit", "Unit", "select", true, "%").f("test_method", "Test method", "text", false, null)
            .nat("material_grade_id", "element"));
        DEFS.put("customer_standards", new Def("customer_standards", "Customer Standards & Specifications", "customer_standards", "standard_code")
            .f("standard_code", "Standard Code", "text", true, null).f("standard_name", "Standard / Specification Name", "text", true, null)
            .lk("customer_id", "Customer", "customers", false).lk("process_id", "Related Process", "processes", true)
            .f("author_name", "Author / Issuing Authority", "text", false, null).f("revision_number", "Revision Number", "text", true, "00")
            .f("revision_date", "Revision Date", "date", false, null).f("status", "Record Status", "select", true, "ACTIVE")
            .f("remarks", "Remarks", "textarea", false, null)
            .nat("customer_id", "process_id", "standard_code", "revision_number").id("standard_code", "standard_name").auto("standard_code"));
        DEFS.put("processes", new Def("processes", "Processes", "processes", "process_code")
            .f("process_code", "Master code", "text", true, null).f("process_name", "Process name", "text", true, null)
            .f("process_type", "Process type", "select", true, "IN_HOUSE").f("special_process", "Special process", "boolean", false, false)
            .f("cqi_standard", "CQI standard", "text", false, null).f("status", "Record status", "select", true, "ACTIVE")
            .f("remarks", "Remarks", "textarea", false, null)
            .nat("process_code").id("process_name").auto("process_code"));
        DEFS.put("inspection_stages", new Def("inspection_stages", "Inspection Stages", "inspection_stages", "sequence_no")
            .f("stage_code", "Master code", "text", true, null).f("stage_name", "Stage name", "text", true, null)
            .f("sequence_no", "Sequence", "integer", true, 10).f("status", "Record status", "select", true, "ACTIVE")
            .nat("stage_code").id("stage_name").auto("stage_code"));
        DEFS.put("quality_assets", new Def("quality_assets", "Quality Assets", "quality_assets", "asset_code")
            .f("asset_code", "Master code", "text", true, null).f("asset_number", "Asset number", "text", false, null)
            .f("asset_name", "Asset name", "text", true, null).f("asset_type", "Asset type", "select", true, "GAUGE")
            .f("manufacturer", "Manufacturer", "text", false, null).f("model", "Model", "text", false, null)
            .f("serial_number", "Serial number", "text", false, null).f("range_text", "Range", "text", false, null)
            .f("least_count", "Least count", "text", false, null).f("location", "Location", "text", false, null)
            .f("service_type", "Control type", "select", true, "CALIBRATION").f("calibration_frequency_days", "Calibration frequency (days)", "integer", true, 365)
            .f("last_calibration_date", "Last calibration date", "date", false, null).f("next_due_date", "Next calibration due date", "date", false, null)
            .f("validation_frequency_days", "Validation frequency (days)", "integer", false, 365)
            .f("last_validation_date", "Last validation date", "date", false, null).f("next_validation_due_date", "Next validation due date", "date", false, null)
            .f("status", "Record status", "select", true, "ACTIVE").f("remarks", "Remarks", "textarea", false, null)
            .nat("asset_code").id("asset_number").auto("asset_code"));
        DEFS.put("inspection_plans", new Def("inspection_plans", "Inspection Plans", "inspection_plans", "plan_number")
            .lk("part_id", "Part", "parts", true).lk("process_id", "Process", "processes", false)
            .lk("inspection_stage_id", "Inspection stage", "inspection_stages", false)
            .f("plan_number", "Plan number", "text", true, null).f("revision", "Revision", "text", true, "00")
            .f("effective_date", "Effective date", "date", false, null).f("sample_plan", "Sample plan", "text", false, null)
            .f("status", "Plan status", "select", true, "DRAFT")
            .nat("plan_number", "revision"));
        DEFS.put("inspection_characteristics", new Def("inspection_characteristics", "Inspection Characteristics", "inspection_plan_characteristics", "sequence_no")
            .lk("inspection_plan_id", "Inspection plan", "inspection_plans", true).f("sequence_no", "Sequence", "integer", true, 10)
            .f("characteristic_no", "Characteristic number", "text", false, null).f("characteristic", "Characteristic", "text", true, null)
            .f("specification", "Specification", "text", false, null).f("lower_spec", "Lower specification", "number", false, null)
            .f("upper_spec", "Upper specification", "number", false, null).f("unit", "Unit", "text", false, null)
            .f("characteristic_type", "Type", "select", true, "VARIABLE").f("special_class", "Special class", "text", false, null)
            .lk("checking_aid_id", "Checking aid", "quality_assets", false).f("checking_method", "Checking method", "text", false, null)
            .f("sample_size", "Sample size", "integer", false, null).f("frequency", "Frequency", "text", false, null)
            .f("reaction_plan", "Reaction plan", "textarea", false, null)
            .nat("inspection_plan_id", "sequence_no"));
        DEFS.put("test_plans", new Def("test_plans", "Test Plans", "test_plans", "plan_number")
            .lk("part_id", "Part", "parts", true).lk("process_id", "Process", "processes", false)
            .lk("inspection_stage_id", "Inspection stage", "inspection_stages", false)
            .f("plan_number", "Plan number", "text", true, null).f("revision", "Revision", "text", true, "00")
            .f("test_type", "Test type", "select", true, null).f("specification_reference", "Specification reference", "text", false, null)
            .f("frequency", "Frequency", "text", false, null).f("sample_size", "Sample size", "integer", false, null)
            .f("acceptance_criteria", "Acceptance criteria", "json", false, null).f("status", "Plan status", "select", true, "DRAFT")
            .nat("plan_number", "revision"));
    }

    static final String[] EMPLOYEE_COLUMNS = {"Employee Code", "First Name", "Last Name", "Email", "Department", "Designation", "Plant",
        "Mobile Number", "Approval Authorities", "Reports To Employee Code", "Experience Start Date", "Status", "Remarks"};

    /** Column headings the importer recognises for a master (field labels). */
    static List<String> expectedColumns(String key) {
        if ("employees".equals(key)) return Arrays.asList(EMPLOYEE_COLUMNS);
        List<String> out = new ArrayList<>();
        Def d = DEFS.get(key);
        if (d != null) for (F f : d.fields) out.add(f.label);
        if ("material_grades".equals(key)) out.add("Material Number");
        return out;
    }

    // ------------------------------------------------------------------ header mapping
    static final String[][] SYNONYMS = {
        {"part description", "part_name"}, {"part name", "part_name"}, {"fsi part number", "fsi_part_number"}, {"fsi part no", "fsi_part_number"}, {"customer", "customer_id"},
        {"material grade", "material_grade_id"}, {"grade", "grade_code"}, {"material number", "material_number"},
        {"drawing", "drawing_number"}, {"revision", "revision"}, {"drawing revision", "drawing_revision"},
        {"finished weight kg", "finished_weight_kg"}, {"finish weight kg", "finished_weight_kg"},
        {"forging weight kg", "forging_weight_kg"}, {"gross weight kg", "gross_weight_kg"},
        {"raw material section", "section_size"}, {"section size", "section_size"},
        {"process code", "process_code"}, {"process name", "process_name"}, {"process type", "process_type"},
        {"standard code", "standard_code"}, {"standard name", "standard_name"}, {"specification name", "standard_name"},
        {"author name", "author_name"}, {"author", "author_name"}, {"issuing authority", "author_name"},
        {"revision number", "revision_number"}, {"revision date", "revision_date"}, {"related process", "process_id"},
        {"special process", "special_process"}, {"cqi standard", "cqi_standard"},
        {"stage code", "stage_code"}, {"stage name", "stage_name"}, {"sequence no", "sequence_no"}, {"sequence", "sequence_no"},
        {"employee code", "employee_code"}, {"first name", "first_name"}, {"last name", "last_name"},
        {"mobile number", "mobile_number"}, {"approval authorities", "approval_authorities"},
        {"reports to employee code", "reports_to_employee_id"}, {"experience start date", "experience_start_date"},
        {"party code", "party_code"}, {"party name", "party_name"}, {"party type", "party_types"},
        {"approval status", "approval_status"}, {"record status", "status"},
        {"standard / specification", "standard"}, {"standard", "standard"},
        {"element", "element"}, {"minimum %", "minimum"}, {"maximum %", "maximum"}, {"minimum", "minimum"}, {"maximum", "maximum"},
        {"test method", "test_method"}, {"supplier", "supplier_id"}, {"steel mill", "steel_mill_id"},
        {"supplier part number", "supplier_part_number"}, {"approval reference", "approval_reference"},
        {"valid from", "valid_from"}, {"valid to", "valid_to"}, {"approved", "approved"},
        {"asset code", "asset_code"}, {"asset number", "asset_number"}, {"asset no", "asset_number"}, {"asset no.", "asset_number"}, {"asset name", "asset_name"}, {"asset type", "asset_type"},
        {"calibration frequency days", "calibration_frequency_days"}, {"last calibration date", "last_calibration_date"}, {"next due date", "next_due_date"},
        {"inspection plan", "inspection_plan_id"}, {"plan number", "plan_number"}, {"inspection stage", "inspection_stage_id"},
        {"characteristic number", "characteristic_no"}, {"parameter", "characteristic"}, {"characteristic", "characteristic"},
        {"lower specification", "lower_spec"}, {"upper specification", "upper_spec"}, {"checking aid", "checking_aid_id"},
        {"checking method", "checking_method"}, {"sample size", "sample_size"}, {"reaction plan", "reaction_plan"},
        {"test type", "test_type"}, {"specification reference", "specification_reference"}, {"acceptance criteria", "acceptance_criteria"}};

    static Map<String, String> fieldMap(Def d) {
        Map<String, String> m = new HashMap<>();
        for (F f : d.fields) { m.put(AdmPy.norm(f.name), f.name); m.put(AdmPy.norm(f.label), f.name); }
        for (String[] s : SYNONYMS) m.put(AdmPy.norm(s[0]), s[1]);
        return m;
    }

    // ------------------------------------------------------------------ CSV (pandas.read_csv(dtype=object))
    /** pandas default NA strings: such cells become empty (NaN). */
    static final Set<String> NA = new HashSet<>(Arrays.asList("", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan",
        "1.#IND", "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "None", "n/a", "nan", "null"));

    static final class Frame {
        final List<String> columns = new ArrayList<>();
        final List<Map<String, String>> rows = new ArrayList<>();
    }

    /** Parse CSV text (comma, double quotes, CRLF, UTF-8 BOM). Fully empty rows are dropped like dropna(how="all"). */
    static Frame readCsv(byte[] data) throws Exception {
        String text = new String(data, StandardCharsets.UTF_8);
        if (text.startsWith("﻿")) text = text.substring(1);
        List<List<String>> records = new ArrayList<>();
        List<String> cur = new ArrayList<>();
        StringBuilder cell = new StringBuilder();
        boolean quoted = false, any = false;
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (quoted) {
                if (c == '"') {
                    if (i + 1 < text.length() && text.charAt(i + 1) == '"') { cell.append('"'); i++; }
                    else quoted = false;
                } else cell.append(c);
                continue;
            }
            if (c == '"') { quoted = true; any = true; }
            else if (c == ',') { cur.add(cell.toString()); cell.setLength(0); any = true; }
            else if (c == '\r' || c == '\n') {
                if (c == '\r' && i + 1 < text.length() && text.charAt(i + 1) == '\n') i++;
                if (any || cell.length() > 0) { cur.add(cell.toString()); records.add(cur); }
                cur = new ArrayList<>(); cell.setLength(0); any = false;
            } else { cell.append(c); any = true; }
        }
        if (any || cell.length() > 0) { cur.add(cell.toString()); records.add(cur); }
        if (records.isEmpty()) throw new Api.ApiException(400, "The file is empty.");
        Frame f = new Frame();
        Map<String, Integer> seen = new HashMap<>();
        List<String> head = records.get(0);
        for (int i = 0; i < head.size(); i++) {
            String h = head.get(i);
            if (h.trim().isEmpty()) h = "Unnamed: " + i;
            Integer n = seen.get(h);
            seen.put(h, n == null ? 1 : n + 1);
            f.columns.add(n == null ? h : h + "." + n);
        }
        for (int r = 1; r < records.size(); r++) {
            List<String> rec = records.get(r);
            if (rec.size() > f.columns.size()) throw new Api.ApiException(400, "Error tokenizing data. Expected " + f.columns.size() + " fields in line " + (r + 1) + ", saw " + rec.size());
            Map<String, String> row = new LinkedHashMap<>();
            boolean hasValue = false;
            for (int i = 0; i < f.columns.size(); i++) {
                String v = i < rec.size() ? rec.get(i) : "";
                if (NA.contains(v)) v = null;
                if (v != null) hasValue = true;
                row.put(f.columns.get(i), v);
            }
            if (hasValue) f.rows.add(row);
        }
        return f;
    }

    /** _clean_value for CSV text: None stays None, strings stripped, blank -> None. */
    static String clean(String v) {
        if (v == null) return null;
        String t = v.trim();
        return t.isEmpty() ? null : t;
    }

    static boolean truthy(Object v) {
        String n = AdmPy.norm(v);
        return n.equals("1") || n.equals("true") || n.equals("yes") || n.equals("y") || n.equals("approved") || n.equals("active");
    }

    /** Rows of a combined Parties sheet that belong to the selected party master. */
    static void filterParty(Frame f, String key) {
        String expected = key.equals("customers") ? "CUSTOMER" : key.equals("suppliers") ? "SUPPLIER" : key.equals("steel_mills") ? "STEEL_MILL" : key.equals("osp_vendors") ? "OSP_VENDOR" : "";
        if (expected.isEmpty()) return;
        String col = null;
        for (String c : f.columns) { String n = AdmPy.norm(c); if (n.equals("party type") || n.equals("party types") || n.equals("type")) { col = c; break; } }
        if (col == null) return;
        List<Map<String, String>> keep = new ArrayList<>();
        for (Map<String, String> r : f.rows) {
            String value = r.get(col) == null ? "" : r.get(col);
            Set<String> tokens = new HashSet<>();
            for (String t : value.toUpperCase(Locale.ROOT).split("[,;|/]+")) if (!t.trim().isEmpty()) tokens.add(t.trim().replace(" ", "_"));
            if (tokens.contains(expected) || AdmPy.norm(value).equals(AdmPy.norm(expected))) keep.add(r);
        }
        f.rows.clear();
        f.rows.addAll(keep);
    }

    // ------------------------------------------------------------------ import run
    interface Progress { void at(int done, int total); }

    static final class Result {
        int created, skipped;
        final List<String> errors = new ArrayList<>();
    }

    private static final class Run {
        final Api api;
        final Map<String, List<JSONObject>> lookupCache = new HashMap<>();
        Run(Api api) { this.api = api; }

        List<JSONObject> records(Def d) throws Exception {
            List<JSONObject> rows = lookupCache.get(d.key);
            if (rows == null) { rows = AdmDb.list(new JSONArray(api.get(d.listPath(), false).body)); lookupCache.put(d.key, rows); }
            return rows;
        }
    }

    /** _lookup_candidates keys for one row. */
    private static List<String> candidateKeys(String lookup, JSONObject row, String[] labelOut) {
        List<Object> keys = new ArrayList<>();
        String label;
        switch (lookup) {
            case "customers": case "suppliers": case "steel_mills": case "osp_vendors":
                keys.add(row.opt("party_code")); keys.add(row.opt("party_name"));
                label = AdmPy.strip(AdmPy.j(row, "party_code") + " · " + AdmPy.j(row, "party_name"), " ·"); break;
            case "material_grades":
                keys.add(row.opt("material_number")); keys.add(row.opt("grade_code"));
                label = AdmPy.strip(AdmPy.j(row, "material_number") + " · " + AdmPy.j(row, "grade_code"), " ·"); break;
            case "parts": {
                keys.add(row.opt("part_number")); keys.add(row.opt("fsi_part_number")); keys.add(row.opt("part_name"));
                String fsi = AdmPy.j(row, "fsi_part_number");
                label = AdmPy.strip(AdmPy.j(row, "part_number") + " · FSI " + (fsi.isEmpty() ? "-" : fsi) + " · " + AdmPy.j(row, "part_name"), " ·"); break;
            }
            case "processes":
                keys.add(row.opt("process_code")); keys.add(row.opt("process_name"));
                label = AdmPy.strip(AdmPy.j(row, "process_code") + " · " + AdmPy.j(row, "process_name"), " ·"); break;
            case "customer_standards":
                keys.add(row.opt("standard_code")); keys.add(row.opt("standard_name")); keys.add(row.opt("revision_number"));
                label = AdmPy.strip(AdmPy.j(row, "standard_code") + " · " + AdmPy.j(row, "standard_name") + " · Rev " + AdmPy.j(row, "revision_number"), " ·"); break;
            case "inspection_stages":
                keys.add(row.opt("stage_code")); keys.add(row.opt("stage_name"));
                label = AdmPy.strip(AdmPy.j(row, "stage_code") + " · " + AdmPy.j(row, "stage_name"), " ·"); break;
            case "quality_assets":
                keys.add(row.opt("asset_code")); keys.add(row.opt("asset_number")); keys.add(row.opt("asset_name")); keys.add(row.opt("serial_number"));
                label = AdmPy.strip(AdmPy.j(row, "asset_code") + " · " + AdmPy.j(row, "asset_name"), " ·"); break;
            case "inspection_plans": {
                String k = AdmPy.j(row, "plan_number") + " Rev " + AdmPy.j(row, "revision");
                keys.add(row.opt("plan_number")); keys.add(k);
                label = k; break;
            }
            default:
                keys.add(AdmPy.j(row, "id")); label = AdmPy.j(row, "id");
        }
        labelOut[0] = label;
        List<String> out = new ArrayList<>();
        for (Object k : keys) if (!AdmPy.isNull(k) && !"".equals(k)) out.add(AdmPy.norm(k));
        return out;
    }

    /** _resolve_lookup. */
    private static Object resolveLookup(Run run, String lookup, String value) throws Exception {
        String text = value == null ? "" : value.trim();
        if (text.isEmpty()) return JSONObject.NULL;
        String needle = AdmPy.norm(text);
        List<JSONObject> rows = run.records(DEFS.get(lookup));
        String[] label = new String[1];
        for (JSONObject r : rows) {
            String rid = AdmPy.j(r, "id");
            List<String> keys = candidateKeys(lookup, r, label);
            if (text.equals(rid) || keys.contains(needle) || needle.equals(AdmPy.norm(label[0]))) return rid;
        }
        for (String segment : text.split("[·|]")) {
            String seg = AdmPy.norm(segment);
            if (seg.isEmpty()) continue;
            for (JSONObject r : rows) if (candidateKeys(lookup, r, label).contains(seg)) return AdmPy.j(r, "id");
        }
        throw new Api.ApiException(400, "Could not resolve " + lookup.replace('_', ' ') + " value: " + text);
    }

    /** _row_payload. Keys present in the file map to fields; values are cleaned and lookups resolved. */
    private static JSONObject rowPayload(Run run, Def d, Map<String, String> source) throws Exception {
        Map<String, String> mapping = fieldMap(d);
        JSONObject raw = new JSONObject();
        for (Map.Entry<String, String> e : source.entrySet()) {
            String field = mapping.get(AdmPy.norm(e.getKey()));
            if (field == null) continue;
            String v = clean(e.getValue());
            raw.put(field, v == null ? JSONObject.NULL : v);
        }
        for (F f : d.fields) {
            if (!raw.has(f.name)) continue;
            Object value = raw.opt(f.name);
            if (f.kind.equals("lookup")) raw.put(f.name, resolveLookup(run, f.lookup, AdmPy.isNull(value) ? null : String.valueOf(value)));
            else if (f.kind.equals("boolean")) raw.put(f.name, truthy(value));
            else if (f.kind.equals("select") && !AdmPy.isNull(value)) raw.put(f.name, String.valueOf(value).trim().toUpperCase(Locale.ROOT).replace(" ", "_"));
        }
        if (!d.auto.isEmpty()) {
            String n = AdmPy.norm(raw.opt(d.auto));
            if (n.equals("auto") || n.equals("automatic") || n.equals("auto generated")) raw.put(d.auto, JSONObject.NULL);
        }
        return raw;
    }

    /** MasterService.normalize_payload (existing = None). */
    static JSONObject normalize(Def d, JSONObject raw) throws Exception {
        JSONObject p = new JSONObject();
        for (F f : d.fields) {
            Object value = raw.has(f.name) ? raw.opt(f.name) : (f.def == null ? JSONObject.NULL : f.def);
            switch (f.kind) {
                case "json": value = normalizeJson(f, value); break;
                case "number":
                    if (AdmPy.isNull(value) || "".equals(value)) value = JSONObject.NULL;
                    else if (!(value instanceof Number)) {
                        try { value = Double.parseDouble(String.valueOf(value).trim()); }
                        catch (NumberFormatException e) { throw new Api.ApiException(400, "could not convert string to float: '" + value + "'"); }
                    }
                    break;
                case "integer":
                    if (AdmPy.isNull(value) || "".equals(value)) value = JSONObject.NULL;
                    else if (!(value instanceof Number)) {
                        try { value = Long.parseLong(String.valueOf(value).trim()); }
                        catch (NumberFormatException e) { throw new Api.ApiException(400, "invalid literal for int() with base 10: '" + value + "'"); }
                    }
                    break;
                case "date":
                    if (AdmPy.isNull(value) || "".equals(value)) value = JSONObject.NULL;
                    break;
                case "boolean":
                    value = value instanceof Boolean ? value : (!AdmPy.isNull(value) && !"".equals(value) && !Boolean.FALSE.equals(value));
                    break;
                case "text": case "textarea": {
                    String t = AdmPy.isNull(value) ? "" : String.valueOf(value).trim();
                    value = t.isEmpty() ? JSONObject.NULL : t;
                    break;
                }
                default: break;
            }
            p.put(f.name, value == null ? JSONObject.NULL : value);
        }
        if (d.fixedPartyTypes != null) {
            java.util.TreeSet<String> sorted = new java.util.TreeSet<>();
            for (int i = 0; i < d.fixedPartyTypes.length(); i++) sorted.add(d.fixedPartyTypes.optString(i));
            JSONArray arr = new JSONArray();
            for (String s : sorted) arr.put(s);
            p.put("party_types", arr);
        }
        return p;
    }

    private static Object normalizeJson(F f, Object value) {
        if (value instanceof JSONObject || value instanceof JSONArray) return value;
        String text = AdmPy.isNull(value) ? "" : String.valueOf(value).trim();
        boolean sc = f.name.equals("special_characteristics");
        if (text.isEmpty()) return sc ? new JSONArray() : new JSONObject();
        try {
            return jsonLoads(text);
        } catch (Exception e) {
            try {
                return sc ? new JSONArray().put(new JSONObject().put("note", text)) : new JSONObject().put("criteria", text);
            } catch (Exception ignored) { return JSONObject.NULL; }
        }
    }

    /** json.loads of a text cell (object, array, number, string, true / false / null); throws when invalid. */
    static Object jsonLoads(String text) throws Exception {
        String t = text.trim();
        if (t.startsWith("{")) return new JSONObject(t);
        if (t.startsWith("[")) return new JSONArray(t);
        if (t.equals("true")) return Boolean.TRUE;
        if (t.equals("false")) return Boolean.FALSE;
        if (t.equals("null")) return JSONObject.NULL;
        if (t.startsWith("\"") && t.endsWith("\"") && t.length() >= 2) return new JSONArray("[" + t + "]").get(0);
        if (t.matches("-?(0|[1-9]\\d*)")) return Long.parseLong(t);
        if (t.matches("-?(0|[1-9]\\d*)(\\.\\d+)?([eE][+-]?\\d+)?")) return Double.parseDouble(t);
        throw new Exception("Expecting value");
    }

    private static boolean empty(Object v) {
        if (AdmPy.isNull(v)) return true;
        if (v instanceof JSONArray) return ((JSONArray) v).length() == 0;
        if (v instanceof JSONObject) return ((JSONObject) v).length() == 0;
        return "".equals(v);
    }

    /** MasterService.validate_payload. */
    static List<String> validate(Def d, JSONObject p) {
        List<String> errors = new ArrayList<>();
        for (F f : d.fields) if (f.required && empty(p.opt(f.name))) errors.add(f.label + " is mandatory.");
        if (d.key.equals("chemical_composition")) {
            Object mn = p.opt("minimum"), mx = p.opt("maximum");
            if (mn instanceof Number && mx instanceof Number && ((Number) mn).doubleValue() > ((Number) mx).doubleValue()) errors.add("Minimum cannot be greater than maximum.");
        }
        if (d.key.equals("quality_assets")) {
            Object fr = p.opt("calibration_frequency_days");
            if (fr instanceof Number && ((Number) fr).longValue() <= 0) errors.add("Calibration frequency must be greater than zero.");
        }
        return errors;
    }

    /** MasterService.duplicate_match against the listed records (kept current during the run). */
    static String duplicateMatch(Def d, List<JSONObject> rows, JSONObject payload, String... extra) {
        String[] expected = new String[d.natural.length];
        boolean all = d.natural.length > 0;
        for (int i = 0; i < d.natural.length; i++) { expected[i] = MstSave.normKey(payload.opt(d.natural[i])); if (expected[i].isEmpty()) all = false; }
        LinkedHashSet<String> fuzzy = new LinkedHashSet<>(Arrays.asList(d.identity));
        fuzzy.addAll(Arrays.asList(extra));
        for (JSONObject row : rows) {
            if (all) {
                boolean same = true;
                for (int i = 0; i < d.natural.length; i++) if (!expected[i].equals(MstSave.normKey(row.opt(d.natural[i])))) { same = false; break; }
                if (same) return "matching controlled key " + String.join(" + ", d.natural);
            }
            for (String field : fuzzy) {
                Object candidate = payload.opt(field), existing = row.opt(field);
                String nc = MstSave.normKey(candidate);
                if (nc.isEmpty()) continue;
                if (nc.equals(MstSave.normKey(existing))) return "matching " + field.replace('_', ' ');
                if ((field.contains("name") || field.contains("description")) && MstSave.fuzzyDuplicate(candidate, existing))
                    return "2–3 matching words in " + field.replace('_', ' ') + " (" + AdmPy.s(existing) + ")";
            }
        }
        return null;
    }

    /** _existing_id: same normalized natural key (any part non-empty). */
    private static boolean existing(Def d, List<JSONObject> rows, JSONObject payload) {
        String[] expected = new String[d.natural.length];
        boolean any = false;
        for (int i = 0; i < d.natural.length; i++) { expected[i] = MstSave.normKey(payload.opt(d.natural[i])); if (!expected[i].isEmpty()) any = true; }
        if (!any) return false;
        for (JSONObject row : rows) {
            boolean same = true;
            for (int i = 0; i < d.natural.length; i++) if (!expected[i].equals(MstSave.normKey(row.opt(d.natural[i])))) { same = false; break; }
            if (same) return true;
        }
        return false;
    }

    private static String[] extraUnique(String key) {
        switch (key) {
            case "customers": case "suppliers": case "steel_mills": case "osp_vendors": return new String[]{"party_name"};
            case "processes": return new String[]{"process_name"};
            case "inspection_stages": return new String[]{"stage_name"};
            case "quality_assets": return new String[]{"asset_number"};
            default: return new String[0];
        }
    }

    /** _import_definition (+ the material-number step for material grades). */
    static Result importMaster(Api api, String key, Frame frame, Progress progress) throws Exception {
        if ("employees".equals(key)) return importEmployees(api, frame, progress);
        Def d = DEFS.get(key);
        if (d == null) throw new Api.ApiException(400, "Unknown master: " + key);
        Run run = new Run(api);
        Set<String> preexistingGrades = new HashSet<>();
        if (key.equals("material_grades"))
            for (JSONObject r : AdmDb.list(AdmDb.select(api, "material_grades", null, null, 5000))) preexistingGrades.add(AdmPy.norm(r.opt("grade_code")));
        Result res = new Result();
        Set<String> seen = new HashSet<>();
        String[] extra = extraUnique(key);
        int total = frame.rows.size();
        for (int i = 0; i < total; i++) {
            int rowNo = i + 2;
            Map<String, String> record = frame.rows.get(i);
            if (progress != null) progress.at(i, total);
            boolean anyValue = false;
            for (String v : record.values()) if (clean(v) != null) anyValue = true;
            if (!anyValue) continue;
            try {
                List<JSONObject> rows = run.records(d);
                JSONObject raw = rowPayload(run, d, record);
                JSONObject normalized = normalize(d, raw);
                boolean exists = existing(d, rows, normalized);
                StringBuilder sig = new StringBuilder();
                for (int k = 0; k < d.natural.length; k++) {
                    if (k > 0) sig.append('|');
                    Object v = normalized.opt(d.natural[k]);
                    sig.append(AdmPy.fold((AdmPy.isNull(v) || "".equals(v) || Boolean.FALSE.equals(v) || (v instanceof Number && ((Number) v).doubleValue() == 0) ? "" : AdmPy.pyStr(v)).trim()));
                }
                String signature = sig.toString();
                boolean sigSet = !signature.isEmpty();
                String fuzzy = duplicateMatch(d, rows, normalized, extra);
                if (exists || fuzzy != null || (sigSet && seen.contains(signature))) { res.skipped++; continue; }
                // MasterService.save(definition, raw, record_id=None)
                JSONObject payload = normalize(d, raw);
                if (!d.auto.isEmpty() && empty(payload.opt(d.auto))) payload.put(d.auto, MstSave.nextMasterCode(api, d.key));
                List<String> errors = validate(d, payload);
                if (!errors.isEmpty()) throw new Api.ApiException(422, String.join("\n", errors));
                String dup = duplicateMatch(d, rows, payload);
                if (dup != null) throw new Api.ApiException(409, "Duplicate " + d.label + " is not allowed. Matching words already exist: " + dup + ".");
                JSONObject saved = api.insert(d.table, payload);
                rows.add(saved);
                res.created++;
                if (sigSet) seen.add(signature);
            } catch (Exception e) {
                res.errors.add("Row " + rowNo + ": " + Api.message(e));
            }
        }
        if (key.equals("material_grades")) materialNumbers(api, frame, preexistingGrades);
        return res;
    }

    /** Material Number of newly imported grades (controlled field outside the generic form). */
    private static void materialNumbers(Api api, Frame frame, Set<String> preexisting) throws Exception {
        Map<String, String> headers = new HashMap<>();
        for (String c : frame.columns) headers.put(AdmPy.norm(c), c);
        String matCol = headers.get("material number");
        String gradeCol = headers.containsKey("material grade") ? headers.get("material grade") : headers.containsKey("grade") ? headers.get("grade") : headers.get("grade code");
        if (gradeCol == null) return;
        for (Map<String, String> source : frame.rows) {
            String gradeCode = clean(source.get(gradeCol));
            if (gradeCode == null || preexisting.contains(AdmPy.norm(gradeCode))) continue;
            JSONObject grade = null;
            for (JSONObject r : AdmDb.list(AdmDb.select(api, "material_grades", null, "grade_code.asc", 3000)))
                if (AdmPy.norm(r.opt("grade_code")).equals(AdmPy.norm(gradeCode))) { grade = r; break; }
            if (grade == null) continue;
            String materialNo = matCol == null ? "" : (clean(source.get(matCol)) == null ? "" : clean(source.get(matCol)));
            String n = AdmPy.norm(materialNo);
            if (n.isEmpty() || n.equals("auto") || n.equals("automatic")) {
                materialNo = AdmPy.j(grade, "material_number");
                if (materialNo.isEmpty()) materialNo = MstSave.codeRpc(api, "qcms_next_material_number");
            }
            if (!materialNo.isEmpty() && !AdmPy.j(grade, "material_number").equals(materialNo))
                api.update("material_grades", AdmPy.j(grade, "id"), new JSONObject().put("material_number", materialNo));
        }
    }

    // ------------------------------------------------------------------ employees (_import_employees + EmployeeService.save)
    static final List<String> AUTHORITIES = Arrays.asList("RMTC_PREPARE", "RMTC_VALIDATE", "RMTC_APPROVE", "MATERIAL_INWARD_PREPARE",
        "RAW_MATERIAL_INSPECTION", "SETUP_APPROVAL", "STAGE_INSPECTION", "OSP_QUALITY_RELEASE", "LAB_VALIDATION", "FINAL_QUALITY_RELEASE",
        "PPAP_APPROVAL", "CALIBRATION_APPROVAL", "AUDIT_APPROVAL");

    private static String ws(Object v) { return AdmPy.fold(String.join(" ", AdmPy.s(v).trim().split("\\s+")).trim()); }

    static Result importEmployees(Api api, Frame frame, Progress progress) throws Exception {
        List<JSONObject> existing = AdmDb.list(AdmDb.select(api, "employees", null, "first_name.asc", 1000));
        Map<String, JSONObject> byCode = new HashMap<>(), byEmail = new HashMap<>();
        for (JSONObject r : existing) {
            if (!AdmPy.j(r, "employee_code").isEmpty()) byCode.put(AdmPy.norm(r.opt("employee_code")), r);
            if (!AdmPy.j(r, "email").isEmpty()) byEmail.put(AdmPy.norm(r.opt("email")), r);
        }
        Result res = new Result();
        List<String[]> pendingManager = new ArrayList<>();
        int total = frame.rows.size();
        for (int i = 0; i < total; i++) {
            int rowNo = i + 2;
            if (progress != null) progress.at(i, total);
            Map<String, String> source = frame.rows.get(i);
            Map<String, String> values = new HashMap<>();
            boolean any = false;
            for (Map.Entry<String, String> e : source.entrySet()) {
                String v = clean(e.getValue());
                if (v != null) any = true;
                values.put(AdmPy.norm(e.getKey()), v);
            }
            if (!any) continue;
            try {
                String code = nz(values.get("employee code")).trim();
                String nc = AdmPy.norm(code);
                if (nc.isEmpty() || nc.equals("auto") || nc.equals("automatic")) code = MstSave.codeRpc(api, "qsms_next_employee_code");
                String email = nz(values.get("email")).trim().toLowerCase(Locale.ROOT);
                List<String> authorities = new ArrayList<>();
                String at = values.get("approval authorities");
                if (at != null) for (String item : at.split("[,;|]")) {
                    String t = item.trim().toUpperCase(Locale.ROOT);
                    if (!t.isEmpty() && AUTHORITIES.contains(t)) authorities.add(t);
                }
                String managerCode = nz(values.get("reports to employee code")).trim();
                JSONObject existingRow = byCode.containsKey(AdmPy.norm(code)) ? byCode.get(AdmPy.norm(code)) : byEmail.get(AdmPy.norm(email));
                if (existingRow != null) { res.skipped++; continue; }
                JSONObject p = new JSONObject();
                p.put("employee_code", code);
                p.put("first_name", nz(values.get("first name")).trim());
                p.put("last_name", nz(values.get("last name")).trim());
                p.put("email", email);
                p.put("department", nz(values.get("department")).trim());
                p.put("designation", nz(values.get("designation")).trim());
                String plant = values.get("plant");
                p.put("plant", (plant == null ? "D9" : plant).trim());
                String mobile = nz(values.get("mobile number")).trim();
                p.put("mobile_number", mobile.isEmpty() ? JSONObject.NULL : mobile);
                JSONArray auth = new JSONArray();
                for (String x : authorities) auth.put(x);
                p.put("approval_authorities", auth);
                p.put("reports_to_employee_id", JSONObject.NULL);
                String start = values.get("experience start date");
                String sd = start == null ? LocalDate.now().toString() : start;
                p.put("experience_start_date", sd.length() > 10 ? sd.substring(0, 10) : sd);
                String status = values.get("status");
                p.put("status", (status == null ? "ACTIVE" : status).trim().toUpperCase(Locale.ROOT));
                String remarks = nz(values.get("remarks")).trim();
                p.put("remarks", remarks.isEmpty() ? JSONObject.NULL : remarks);
                p.put("source_system", "QCMS_IMPORT");
                for (String k : new String[]{"first_name", "last_name", "email", "department", "designation", "plant", "employee_code"})
                    if (AdmPy.s(p.opt(k)).trim().isEmpty()) throw new Api.ApiException(422, AdmPy.title(k.replace('_', ' ')) + " is mandatory.");
                for (String field : new String[]{"employee_code", "email"}) {
                    String value = ws(p.opt(field));
                    if (value.isEmpty()) continue;
                    for (JSONObject r : existing) if (ws(r.opt(field)).equals(value))
                        throw new Api.ApiException(409, "Duplicate " + AdmPy.title(field.replace('_', ' ')) + " is not allowed.");
                }
                JSONObject saved = api.insert("employees", p);
                existing.add(saved);
                res.created++;
                byCode.put(AdmPy.norm(saved.opt("employee_code")), saved);
                byEmail.put(AdmPy.norm(saved.opt("email")), saved);
                if (!managerCode.isEmpty()) pendingManager.add(new String[]{AdmPy.j(saved, "id"), managerCode});
            } catch (Exception e) {
                res.errors.add("Row " + rowNo + ": " + Api.message(e));
            }
        }
        for (String[] pm : pendingManager) {
            JSONObject manager = byCode.get(AdmPy.norm(pm[1]));
            if (manager != null && !AdmPy.j(manager, "id").equals(pm[0]))
                api.update("employees", pm[0], new JSONObject().put("reports_to_employee_id", AdmPy.j(manager, "id")));
        }
        return res;
    }

    private static String nz(String v) { return v == null ? "" : v; }
}
