package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

/**
 * Master List export (website report_builder.render_master_lists): pick masters, active-only
 * switch, every list as a spreadsheet grid and CSV export (one file with every list, or one list).
 */
final class GenMasterListsScreen extends Screen {
    /** report_builder.master_catalog() - core/master_definitions.DEFINITIONS + Employees. */
    static final class Item {
        final String key, label, group, table, filterField, orderBy, module;
        final String[] filterValues;
        final List<String> columns = new ArrayList<>();
        final Map<String, String> labels = new HashMap<>();
        Item(String key, String label, String group, String table, String filterField, String[] filterValues, String orderBy, String[][] fields) {
            this.key = key; this.label = label; this.group = group; this.table = table; this.filterField = filterField; this.filterValues = filterValues;
            this.orderBy = orderBy;
            String m = GenReport.MASTER_MODULE.get(table);
            this.module = m == null ? "REFERENCE_MASTERS" : m;
            for (String[] f : fields) { columns.add(f[0]); if (f.length > 1) labels.put(f[0], f[1]); }
        }
    }

    private static final String[][] PARTY = {{"party_code", "Master code"}, {"party_name", "Name"}, {"country", "Country"}, {"state", "State / Region"}, {"city", "City"},
        {"address", "Address"}, {"contact_person", "Contact person"}, {"email", "Primary Email"}, {"notification_emails", "Notification Email(s)"}, {"phone", "Phone"},
        {"tax_identifier", "GSTIN / Tax identifier"}, {"approval_status", "Approval status"}, {"status", "Record status"}, {"remarks", "Remarks"}};

    static final List<Item> CATALOG = Arrays.asList(
        new Item("customers", "Customers", "Parties", "parties", "party_types", new String[]{"CUSTOMER"}, "party_code", PARTY),
        new Item("suppliers", "Suppliers", "Parties", "parties", "party_types", new String[]{"SUPPLIER"}, "party_code", PARTY),
        new Item("steel_mills", "Steel Mills", "Parties", "parties", "party_types", new String[]{"STEEL_MILL"}, "party_code", PARTY),
        new Item("osp_vendors", "OSP Vendors", "Parties", "parties", "party_types", new String[]{"OSP_VENDOR"}, "party_code", PARTY),
        new Item("parts", "Parts", "Product & Material", "parts", null, null, "part_number", new String[][]{
            {"part_number", "Part number"}, {"fsi_part_number", "FSI Part Number"}, {"part_name", "Part description"}, {"customer_id", "Customer"},
            {"material_grade_id", "Material grade"}, {"drawing_number", "Drawing number"}, {"drawing_revision", "Drawing revision"},
            {"finished_weight_kg", "Finished weight (kg)"}, {"forging_weight_kg", "Forging weight (kg)"}, {"gross_weight_kg", "Gross weight (kg)"},
            {"section_size", "Raw material section"}, {"manufacturing_route", "Manufacturing route"},
            {"special_characteristics", "Special characteristics / Jominy / heat-treatment details"}, {"status", "Record status"}, {"remarks", "Remarks"}}),
        new Item("material_grades", "Material Grades", "Product & Material", "material_grades", null, null, "grade_code", new String[][]{
            {"grade_code", "Grade"}, {"standard", "Standard"}, {"revision", "Revision"}, {"effective_date", "Effective date"}, {"status", "Record status"}, {"remarks", "Remarks"}}),
        new Item("chemical_composition", "Chemical Composition", "Product & Material", "material_grade_elements", null, null, "element", new String[][]{
            {"material_grade_id", "Material grade"}, {"element", "Element"}, {"minimum", "Minimum"}, {"maximum", "Maximum"}, {"unit", "Unit"}, {"test_method", "Test method"}}),
        new Item("approved_sources", "Approved Sources", "Product & Material", "part_supplier_links", null, null, "created_at", new String[][]{
            {"source_code", "Master code"}, {"part_id", "Part"}, {"supplier_id", "Supplier"}, {"steel_mill_id", "Steel mill"}, {"supplier_part_number", "Supplier part number"},
            {"approval_reference", "Approval reference"}, {"approved", "Approved"}, {"valid_from", "Valid from"}, {"valid_to", "Valid to"}}),
        new Item("customer_standards", "Customer Standards & Specifications", "Standards & Specifications", "customer_standards", null, null, "standard_code", new String[][]{
            {"standard_code", "Standard Code"}, {"standard_name", "Standard / Specification Name"}, {"customer_id", "Customer"}, {"process_id", "Related Process"},
            {"author_name", "Author / Issuing Authority"}, {"revision_number", "Revision Number"}, {"revision_date", "Revision Date"}, {"status", "Record Status"}, {"remarks", "Remarks"}}),
        new Item("processes", "Processes", "Process & Quality", "processes", null, null, "process_code", new String[][]{
            {"process_code", "Master code"}, {"process_name", "Process name"}, {"process_type", "Process type"}, {"special_process", "Special process"},
            {"cqi_standard", "CQI standard"}, {"status", "Record status"}, {"remarks", "Remarks"}}),
        new Item("inspection_stages", "Inspection Stages", "Process & Quality", "inspection_stages", null, null, "sequence_no", new String[][]{
            {"stage_code", "Master code"}, {"stage_name", "Stage name"}, {"sequence_no", "Sequence"}, {"status", "Record status"}}),
        new Item("quality_assets", "Quality Assets", "Process & Quality", "quality_assets", null, null, "asset_code", new String[][]{
            {"asset_code", "Master code"}, {"asset_number", "Asset number"}, {"asset_name", "Asset name"}, {"asset_type", "Asset type"}, {"manufacturer", "Manufacturer"},
            {"model", "Model"}, {"serial_number", "Serial number"}, {"range_text", "Range"}, {"least_count", "Least count"}, {"location", "Location"},
            {"service_type", "Control type"}, {"calibration_frequency_days", "Calibration frequency (days)"}, {"last_calibration_date", "Last calibration date"},
            {"next_due_date", "Next calibration due date"}, {"validation_frequency_days", "Validation frequency (days)"}, {"last_validation_date", "Last validation date"},
            {"next_validation_due_date", "Next validation due date"}, {"status", "Record status"}, {"remarks", "Remarks"}}),
        new Item("inspection_plans", "Inspection Plans", "Process & Quality", "inspection_plans", null, null, "plan_number", new String[][]{
            {"part_id", "Part"}, {"process_id", "Process"}, {"inspection_stage_id", "Inspection stage"}, {"plan_number", "Plan number"}, {"revision", "Revision"},
            {"effective_date", "Effective date"}, {"sample_plan", "Sample plan"}, {"status", "Plan status"}}),
        new Item("inspection_characteristics", "Inspection Characteristics", "Process & Quality", "inspection_plan_characteristics", null, null, "sequence_no", new String[][]{
            {"inspection_plan_id", "Inspection plan"}, {"sequence_no", "Sequence"}, {"characteristic_no", "Characteristic number"}, {"characteristic", "Characteristic"},
            {"specification", "Specification"}, {"lower_spec", "Lower specification"}, {"upper_spec", "Upper specification"}, {"unit", "Unit"},
            {"characteristic_type", "Type"}, {"special_class", "Special class"}, {"checking_aid_id", "Checking aid"}, {"checking_method", "Checking method"},
            {"sample_size", "Sample size"}, {"frequency", "Frequency"}, {"reaction_plan", "Reaction plan"}}),
        new Item("test_plans", "Test Plans", "Process & Quality", "test_plans", null, null, "plan_number", new String[][]{
            {"part_id", "Part"}, {"process_id", "Process"}, {"inspection_stage_id", "Inspection stage"}, {"plan_number", "Plan number"}, {"revision", "Revision"},
            {"test_type", "Test type"}, {"specification_reference", "Specification reference"}, {"frequency", "Frequency"}, {"sample_size", "Sample size"},
            {"acceptance_criteria", "Acceptance criteria"}, {"status", "Plan status"}}),
        new Item("employees", "Employees", "People", "employees", null, null, "employee_code", new String[][]{
            {"employee_code"}, {"first_name"}, {"last_name"}, {"email"}, {"department"}, {"designation"}, {"phone"}, {"status"}}));

    /** One finished sheet. */
    static final class Sheet {
        final String name; final List<String> headers; final List<String[]> rows;
        final List<JSONObject> raw; final String table;
        Sheet(String name, List<String> headers, List<String[]> rows, List<JSONObject> raw, String table) { this.name = name; this.headers = headers; this.rows = rows; this.raw = raw; this.table = table; }
    }

    private static final Set<String> CHOSEN = new LinkedHashSet<>(Arrays.asList("parts", "customers", "suppliers"));
    private static boolean activeOnly = false;
    private List<Item> items;
    private List<Sheet> sheets;
    private int tabIndex = 0;

    GenMasterListsScreen(MainActivity a) { super(a); }

    @Override public String title() { return "Master Lists"; }
    @Override public String subtitle() { return "Clean lists of every master · CSV export"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        if (items == null) {
            page.addView(loading());
            Api.async(() -> {
                List<Item> ok = new ArrayList<>();
                for (Item i : CATALOG) if (GenUtil.canView(api, i.module)) ok.add(i);
                return ok;
            }, (ok, err) -> {
                if (err != null) { page.removeAllViews(); page.addView(error(err, this::reload)); return; }
                items = ok;
                render();
            });
            return scroll;
        }
        render();
        return scroll;
    }

    private void render() {
        page.removeAllViews();
        if (items.isEmpty()) { add(Ui.empty(a, "You do not have View permission on any master."), 0); return; }
        add(Ui.label(a, "A · Choose masters"), 0);
        add(Ui.text(a, "Pick one or many. Each master becomes its own list (and its own section in the CSV file).", 12, Ui.MUTED, false), 0);
        Set<String> groups = new TreeSet<>();
        for (Item i : items) groups.add(i.group);
        LinearLayout card = Ui.card(a);
        for (String g : groups) {
            card.addView(Ui.text(a, g, 13, Ui.TEAL_DARK, true), Ui.matchWrap(a, card.getChildCount() == 0 ? 0 : 10));
            for (Item i : items) {
                if (!i.group.equals(g)) continue;
                CheckBox cb = new CheckBox(a);
                cb.setText(i.label);
                cb.setChecked(CHOSEN.contains(i.key));
                cb.setOnCheckedChangeListener((b, on) -> { if (on) CHOSEN.add(i.key); else CHOSEN.remove(i.key); });
                card.addView(cb, Ui.matchWrap(a, 0));
            }
        }
        add(card, 4);
        Switch active = new Switch(a);
        active.setText("Active records only");
        active.setChecked(activeOnly);
        active.setOnCheckedChangeListener((b, on) -> activeOnly = on);
        add(active, 8);
        Button show = Ui.primary(a, "Prepare master lists");
        show.setOnClickListener(v -> prepare());
        add(show, 10);
        if (sheets != null) renderSheets();
    }

    private void prepare() {
        List<Item> chosen = new ArrayList<>();
        for (Item i : items) if (CHOSEN.contains(i.key)) chosen.add(i);
        if (chosen.isEmpty()) { a.toast("Select at least one master."); return; }
        final boolean active = activeOnly;
        page.removeAllViews();
        page.addView(loading());
        TextView wait = Ui.text(a, "Preparing master lists…", 12, Ui.MUTED, false);
        wait.setGravity(android.view.Gravity.CENTER);
        page.addView(wait);
        Api.async(() -> {
            Map<String, List<JSONObject>> cache = new HashMap<>();
            List<String> warnings = new ArrayList<>();
            GenReport.Loader load = t -> {
                List<JSONObject> hit = cache.get(t);
                if (hit == null) { hit = GenUtil.big(api, t + "?select=*&limit=" + GenReport.ROW_LIMIT); cache.put(t, hit); }
                return hit;
            };
            List<Sheet> out = new ArrayList<>();
            for (Item item : chosen) {
                List<JSONObject> rows;
                try { rows = load.load(item.table); }
                catch (Exception e) {
                    if (e instanceof Api.ApiException && ((Api.ApiException) e).status == 0) throw e;   // offline: say so once
                    warnings.add(item.label + ": " + Api.message(e)); rows = new ArrayList<>();
                }
                if (active) {
                    List<JSONObject> keep = new ArrayList<>();
                    for (JSONObject r : rows) { String st = GenUtil.str(r.opt("status")); if ((st.isEmpty() ? "ACTIVE" : st).toUpperCase(Locale.ROOT).equals("ACTIVE")) keep.add(r); }
                    rows = keep;
                }
                out.add(frame(item, rows, load));
            }
            return new Object[]{out, warnings};
        }, (res, err) -> {
            if (err != null) { page.removeAllViews(); page.addView(error(err, this::prepare)); return; }
            @SuppressWarnings("unchecked") List<Sheet> s = (List<Sheet>) res[0];
            @SuppressWarnings("unchecked") List<String> w = (List<String>) res[1];
            sheets = s;
            tabIndex = 0;
            for (String msg : w) a.toast(msg);
            render();
        });
    }

    /** report_builder.master_frame */
    static Sheet frame(Item item, List<JSONObject> rows, GenReport.Loader load) {
        if (item.filterField != null) {
            Set<String> wanted = new HashSet<>();
            for (String v : item.filterValues) wanted.add(v.toUpperCase(Locale.ROOT));
            List<JSONObject> keep = new ArrayList<>();
            for (JSONObject r : rows) {
                JSONArray arr = r.optJSONArray(item.filterField);
                boolean hit = false;
                for (int i = 0; arr != null && i < arr.length(); i++) if (wanted.contains(GenUtil.py(arr.opt(i)).toUpperCase(Locale.ROOT))) hit = true;
                if (hit) keep.add(r);
            }
            rows = keep;
        }
        GenReport.Frame f = GenReport.readable(rows, load);
        if (f.isEmpty()) {
            List<String> headers = new ArrayList<>();
            for (String c : item.columns) headers.add(item.labels.containsKey(c) ? item.labels.get(c) : GenReport.pretty(c));
            return new Sheet(item.label, headers, new ArrayList<>(), new ArrayList<>(), item.table);
        }
        List<String> order = new ArrayList<>();
        for (String c : item.columns) if (f.col(c) >= 0) order.add(c);
        for (String c : f.columns) if (!order.contains(c) && !c.equals("created_at") && !c.equals("updated_at")) order.add(c);
        for (String c : new String[]{"created_at", "updated_at"}) if (f.col(c) >= 0) order.add(c);
        Integer[] idx = new Integer[f.rows.size()];
        for (int i = 0; i < idx.length; i++) idx[i] = i;
        int oc = f.col(item.orderBy);
        if (oc >= 0) Arrays.sort(idx, (x, y) -> GenUtil.py(f.rows.get(x)[oc]).toLowerCase(Locale.ROOT).compareTo(GenUtil.py(f.rows.get(y)[oc]).toLowerCase(Locale.ROOT)));
        List<String> headers = new ArrayList<>();
        for (String c : order) headers.add(item.labels.containsKey(c) ? item.labels.get(c) : GenReport.pretty(c));
        List<String[]> out = new ArrayList<>();
        List<JSONObject> raw = new ArrayList<>();
        for (int i : idx) {
            String[] line = new String[order.size()];
            for (int c = 0; c < order.size(); c++) line[c] = GenReport.cell(f.rows.get(i)[f.col(order.get(c))]);
            out.add(line);
            raw.add(f.raw.get(i));
        }
        return new Sheet(item.label, headers, out, raw, item.table);
    }

    private void renderSheets() {
        List<String> parts = new ArrayList<>();
        for (Sheet s : sheets) parts.add(s.name + ": " + String.format(Locale.US, "%,d", s.rows.size()));
        add(Ui.label(a, "Preview"), 16);
        add(Ui.text(a, String.join(" · ", parts), 12, Ui.MUTED, false), 0);
        List<String> names = new ArrayList<>();
        for (Sheet s : sheets) names.add(s.name);
        if (tabIndex >= sheets.size()) tabIndex = 0;
        add(GenUtil.chips(a, names, tabIndex, i -> { tabIndex = i; render(); }), 8);
        Sheet s = sheets.get(tabIndex);
        List<List<String>> rows = new ArrayList<>();
        for (String[] r : s.rows) rows.add(Arrays.asList(r));
        add(new DataGrid(a, s.name, s.headers, rows, 460, index -> {
            if (index >= 0 && index < s.raw.size()) GenUtil.openRecord(a, s.table, s.raw.get(index));
        }), 6);
        Button one = Ui.outline(a, "Download " + s.name + " (CSV)", Ui.TEAL);
        one.setOnClickListener(v -> GenUtil.exportCsv(a, s.name, "QCMS_" + GenUtil.safeName(s.name) + "_" + LocalDate.now(), GenUtil.csv(s.headers, s.rows)));
        add(one, 10);
        Button all = Ui.primary(a, "Download " + sheets.size() + " master list(s) as one CSV");
        all.setOnClickListener(v -> {
            StringBuilder b = new StringBuilder();
            b.append(GenUtil.q("FOUR STAR INDUSTRIES PVT. LTD. · Master List")).append(',').append(GenUtil.q(activeOnly ? "Active only" : "All statuses")).append('\n');
            for (Sheet x : sheets) {
                b.append('\n').append(GenUtil.q(x.name + " · " + x.rows.size() + " record(s)")).append('\n');
                GenUtil.appendCsv(b, x.headers, x.rows);
            }
            GenUtil.exportCsv(a, "Master Lists", "QCMS_Master_Lists_" + LocalDate.now(), b.toString());
        });
        add(all, 8);
    }

    @Override public void reload() { items = null; sheets = null; a.rebuild(); }
}
