package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Deleted Records archive (records_center.py render_deleted_records + core/delete_approval.py): rpc
 * qcms_deleted_records(p_table_name, p_from, p_to, p_limit) (audit_log fallback), register grid and the data of
 * one deleted record at the time of deletion.
 */
public final class NpdDeletedScreen extends Screen {
    /** MASTER_DELETE_TABLES + TRANSACTION_DELETE_TABLES of records_center.py (label, table). */
    static final String[][] CATALOGUE = {
        {"Customer Order / Schedule", "supply_customer_orders"}, {"Purchase Order", "supply_purchase_orders"},
        {"Supplier PO Confirmation", "supply_po_confirmations"}, {"OSP Transaction / Job", "osp_jobs"}, {"OSP Inward Receipt", "osp_receipts"},
        {"RM Purchase Order", "supply_rm_purchase_orders"}, {"RM Receipt", "supply_rm_receipts"}, {"RM Dispatch to Forging", "supply_rm_dispatches"},
        {"Forging Order", "supply_forging_orders"}, {"Forging Receipt", "supply_forging_receipts"}, {"Supply Chain Event", "supply_downstream_events"},
        {"RMTC", "rmtc_approvals"}, {"Material Inward", "inward_lots"}, {"Dimensional Report", "inspection_reports"}, {"MetLAB Report", "lab_tests"},
        {"NPD Order", "npd_orders"}, {"NPD Process Flow", "npd_process_flows"}, {"PPAP Project", "ppap_projects"},
        {"Process Flow Diagram", "pfd_headers"}, {"PFMEA", "pfmea_headers"}, {"Control Plan", "control_plan_headers"},
        {"SPC Study", "spc_studies"}, {"MSA Study", "msa_studies"}, {"Capacity Study", "capacity_studies"},
        {"QC Calculation", "qc_calculation_records"}, {"Quality Complaint", "quality_complaints"},
        {"Part Master", "parts"}, {"Material Grade", "material_grades"}, {"Reference Party", "parties"}, {"Process", "processes"},
        {"Inspection Stage", "inspection_stages"}, {"Company Branch", "company_branches"}, {"Employee", "employees"},
        {"Inspection Layout", "inspection_plans"},
    };
    /** core/record_history.py TABLE_LABELS. */
    static final Map<String, String> TABLE_LABELS = new HashMap<>();
    static {
        String[][] l = {
            {"supply_purchase_orders", "Purchase Order"}, {"supply_purchase_order_items", "PO Line"},
            {"supply_purchase_order_sources", "PO Customer Order Source"}, {"supply_rm_purchase_orders", "RM Procurement Stage"},
            {"supply_forging_orders", "Forging Order Stage"}, {"supply_po_confirmations", "PO Confirmation"},
            {"supply_rm_receipts", "RM Receipt"}, {"supply_rm_dispatches", "RM Dispatch"}, {"supply_forging_receipts", "Forging Receipt"},
            {"supply_customer_orders", "Customer Order"}, {"supply_downstream_events", "Downstream Event"}, {"inward_lots", "Material Inward"},
            {"rmtc_approvals", "RMTC"}, {"inspection_reports", "Inspection Report"}, {"lab_tests", "MetLAB Test"}, {"osp_jobs", "OSP Job"},
            {"osp_receipts", "OSP Receipt"}, {"part_supplier_price_history", "Price History"}, {"parts", "Part Master"},
            {"parties", "Party Master"}, {"quality_complaints", "Quality Complaint"}};
        for (String[] p : l) TABLE_LABELS.put(p[0], p[1]);
    }
    /** REFERENCE_FIELDS of core/record_history.py. */
    static final String[] REFERENCE_FIELDS = {"po_number", "inward_number", "rmtc_number", "master_reference_no", "supplier_order_no", "receipt_number",
        "receipt_no", "dispatch_number", "dispatch_no", "osp_job_number", "report_number", "inspection_number",
        "test_number", "complaint_number", "document_number", "confirmation_number", "fsi_part_number_snapshot",
        "item_no", "fsi_part_number", "part_number", "heat_number", "code", "party_name", "name", "title"};

    static String tableLabel(String table) {
        String l = TABLE_LABELS.get(table);
        if (l != null) return l;
        String t = table.replace("supply_", "").replace("_", " ");
        StringBuilder b = new StringBuilder();
        for (String w : t.split(" ")) { if (w.isEmpty()) continue; if (b.length() > 0) b.append(' '); b.append(Character.toUpperCase(w.charAt(0))).append(w.substring(1).toLowerCase(Locale.ROOT)); }
        return b.toString();
    }

    static String reference(JSONObject data, String recordId) {
        if (data != null) {
            for (String k : REFERENCE_FIELDS) { String v = NpdUtil.clean(data.opt(k)); if (!v.isEmpty()) return v; }
            String id = NpdUtil.s(data, "id");
            return id.length() > 8 ? id.substring(0, 8) : id;
        }
        return recordId.length() > 8 ? recordId.substring(0, 8) : recordId;
    }

    static String time(String iso) {
        if (iso == null || iso.isEmpty()) return "";
        try { return OffsetDateTime.parse(iso.replace(" ", "T")).atZoneSameInstant(java.time.ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("dd-MM-yyyy HH:mm")); }
        catch (Exception e) { return iso.length() > 16 ? iso.substring(0, 16).replace('T', ' ') : iso; }
    }

    /** deleted_summary(). */
    static LinkedHashMap<String, String> summary(JSONObject row) {
        JSONObject data = row.optJSONObject("old_data");
        LinkedHashMap<String, String> m = new LinkedHashMap<>();
        m.put("Deleted At", time(NpdUtil.s(row, "deleted_at")));
        m.put("Record Type", tableLabel(NpdUtil.s(row, "table_name")));
        m.put("Reference", reference(data, NpdUtil.s(row, "record_id")));
        String st = data == null ? "" : (!NpdUtil.s(data, "approval_status").isEmpty() ? NpdUtil.s(data, "approval_status") : NpdUtil.s(data, "status"));
        m.put("Status When Deleted", st.isEmpty() ? "-" : st.replace('_', ' '));
        m.put("Deleted By", dash(NpdUtil.s(row, "deleted_by_name")));
        m.put("Delete Reason", dash(NpdUtil.s(row, "delete_reason")));
        m.put("Requested By", dash(NpdUtil.s(row, "requested_by_name")));
        m.put("Approved By", dash(NpdUtil.s(row, "approved_by_name")));
        return m;
    }

    private static String dash(String s) { return s.isEmpty() ? "-" : s; }

    private int kind = -1;   // -1 = all record types
    private String from = LocalDate.now().minusDays(90).toString(), to = LocalDate.now().toString();
    private boolean mainOnly = true;
    private FormView filters;
    private LinearLayout results;

    public NpdDeletedScreen(MainActivity a) { super(a); }

    @Override public String title() { return "Deleted Records"; }
    @Override public String subtitle() { return "Data of every deleted record is kept for audit"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        String[] opts = new String[CATALOGUE.length];
        for (int i = 0; i < opts.length; i++) opts[i] = CATALOGUE[i][1];
        String[] labels = new String[CATALOGUE.length];
        for (int i = 0; i < labels.length; i++) labels[i] = CATALOGUE[i][0];
        filters = new FormView(a, Arrays.asList(
            Field.select("table", "Record type", opts).labels(labels).hint("Blank = all record types"),
            Field.date("from", "From").req().def(from),
            Field.date("to", "To").req().def(to)));
        if (kind >= 0) filters.set("table", CATALOGUE[kind][1]);
        LinearLayout card = Ui.card(a);
        card.addView(filters);
        Switch main = new Switch(a);
        main.setText("Main records only (hide child rows deleted together with a main record)");
        main.setTextColor(Ui.TEXT);
        main.setChecked(mainOnly);
        card.addView(main, Ui.matchWrap(a, 8));
        Button show = Ui.primary(a, "Show deleted records");
        card.addView(show, Ui.matchWrap(a, 10));
        add(card, 2);
        results = Ui.vbox(a);
        add(results, 10);
        show.setOnClickListener(v -> {
            mainOnly = main.isChecked();
            load();
        });
        load();
        return scroll;
    }

    private void load() {
        String problem = filters.validate();
        if (problem != null) { a.toast(problem); return; }
        String table = filters.str("table");
        kind = -1;
        for (int i = 0; i < CATALOGUE.length; i++) if (CATALOGUE[i][1].equals(table)) kind = i;
        from = filters.str("from").substring(0, 10);
        to = filters.str("to").substring(0, 10);
        results.removeAllViews();
        results.addView(loading());
        Api.async(() -> {
            JSONObject args = new JSONObject();
            args.put("p_table_name", table.isEmpty() ? JSONObject.NULL : table);
            args.put("p_from", from);
            args.put("p_to", to);
            args.put("p_limit", 1000);
            try {
                Object v = api.rpcValue("qcms_deleted_records", args);
                if (v instanceof JSONArray) return (JSONArray) v;
            } catch (Exception ignored) { }
            // fallback before the R25 SQL (Admin / Quality Manager can read audit_log)
            JSONArray raw = api.rows("audit_log?select=id,table_name,row_id,changed_at,changed_by,old_data&operation=eq.DELETE"
                + (table.isEmpty() ? "" : "&table_name=eq." + Api.enc(table)) + "&changed_at=gte." + from + "&changed_at=lt." + LocalDate.parse(to).plusDays(1)
                + "&order=changed_at.desc&limit=1000");
            JSONArray out = new JSONArray();
            for (JSONObject r : NpdUtil.list(raw)) {
                out.put(new JSONObject().put("audit_id", r.opt("id")).put("table_name", r.opt("table_name")).put("record_id", r.opt("row_id"))
                    .put("deleted_at", r.opt("changed_at")).put("deleted_by", r.opt("changed_by")).put("deleted_by_name", "").put("old_data", r.opt("old_data")));
            }
            return out;
        }, (rows, err) -> {
            results.removeAllViews();
            if (err != null) { results.addView(error(err, this::load)); return; }
            List<JSONObject> list = NpdUtil.list(rows);
            if (mainOnly && table.isEmpty()) {
                Set<String> main = new HashSet<>();
                for (String[] c : CATALOGUE) main.add(c[1]);
                List<JSONObject> keep = new ArrayList<>();
                for (JSONObject r : list) if (main.contains(NpdUtil.s(r, "table_name"))) keep.add(r);
                list = keep;
            }
            if (list.isEmpty()) { results.addView(Ui.empty(a, "No deleted records in this selection.")); return; }
            List<String> headers = new ArrayList<>(summary(list.get(0)).keySet());
            List<List<String>> data = new ArrayList<>();
            int approved = 0;
            Set<String> types = new HashSet<>(), users = new HashSet<>();
            for (JSONObject r : list) {
                LinkedHashMap<String, String> s = summary(r);
                data.add(new ArrayList<>(s.values()));
                if (!"-".equals(s.get("Approved By"))) approved++;
                types.add(s.get("Record Type"));
                users.add(s.get("Deleted By"));
            }
            TextView kpi = Ui.text(a, "Deleted records " + list.size() + " · With Admin approval " + approved + " · Record types " + types.size() + " · Users " + users.size()
                + "\nTap a row to view the record data at the time of deletion.", 12, Ui.MUTED, false);
            results.addView(kpi);
            final List<JSONObject> shown = list;
            results.addView(new DataGrid(a, "Deleted records", headers, data, 520, i -> {
                JSONObject r = shown.get(i);
                a.push(new NpdDataScreen(a, "Deleted · " + summary(r).get("Reference"), summary(r).get("Record Type"), summary(r), r.optJSONObject("old_data"), "Record data at the time of deletion"));
            }), Ui.matchWrap(a, 6));
        });
    }

    /** Read-only view of a JSON record (deleted record data, deletion-request snapshot). */
    public static final class NpdDataScreen extends Screen {
        private final String title, sub, dataTitle;
        private final LinkedHashMap<String, String> head;
        private final JSONObject data;

        public NpdDataScreen(MainActivity a, String title, String sub, LinkedHashMap<String, String> head, JSONObject data, String dataTitle) {
            super(a);
            this.title = title; this.sub = sub; this.head = head; this.data = data; this.dataTitle = dataTitle;
        }

        @Override public String title() { return title; }
        @Override public String subtitle() { return sub; }
        @Override public int tab() { return Catalog.MORE; }

        @Override
        public View build() {
            newPage();
            if (head != null && !head.isEmpty()) {
                LinearLayout card = Ui.card(a);
                for (Map.Entry<String, String> e : head.entrySet()) card.addView(Ui.pair(a, e.getKey(), e.getValue()));
                add(card, 2);
            }
            add(Ui.label(a, dataTitle), 12);
            List<List<String>> rows = new ArrayList<>();
            if (data != null) {
                for (Iterator<String> it = data.keys(); it.hasNext(); ) {
                    String k = it.next();
                    if ("tenant_id".equals(k) || "search_vector".equals(k)) continue;
                    Object v = data.opt(k);
                    String text = v == null || v == JSONObject.NULL ? "-" : String.valueOf(v);
                    if (text.length() > 400) text = text.substring(0, 400) + "…";
                    rows.add(Arrays.asList(fieldLabel(k), text));
                }
            }
            if (rows.isEmpty()) add(Ui.empty(a, "No record data was kept."), 2);
            else add(new DataGrid(a, dataTitle, Arrays.asList("Field", "Value"), rows, 640, null), 2);
            return scroll;
        }

        /** field_label(): name.replace("_id","").replace("_"," ").title(). */
        static String fieldLabel(String name) {
            String s = name.replace("_id", "").replace("_", " ").trim();
            StringBuilder b = new StringBuilder();
            boolean up = true;
            for (char ch : s.toCharArray()) {
                b.append(up ? Character.toUpperCase(ch) : Character.toLowerCase(ch));
                up = !Character.isLetter(ch);
            }
            return b.toString();
        }
    }
}
