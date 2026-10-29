package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeSet;

/**
 * R36 trial / test data purge (app_pages/dev_purge.py + core/dev_purge_service.py) - STAWN developer login only.
 * The server functions qcms_dev_purge_preview / qcms_dev_purge_execute check is_stawn_developer again, work in the
 * current company only, never delete master data and archive every row before removing it. Same confirmations as the
 * website: preview first, Excel backup, type DELETE TRIAL DATA, reason (>= 5 characters), current password re-entry
 * and the "I downloaded the backup" tick.
 */
final class DevPurgeScreen extends Screen {
    static final String CONFIRM_PHRASE = "DELETE TRIAL DATA";

    /** dev_purge_service.MODULES: label -> {table, date column, party column ("" = none), reference columns...}. */
    static final String[][] MODULES = {
        {"Customer Orders / Schedules", "supply_customer_orders", "order_date", "customer_id", "master_reference_no", "customer_order_no"},
        {"Purchase Orders", "supply_purchase_orders", "order_date", "supplier_id", "po_number", "quotation_reference", "old_po_reference"},
        {"PO Confirmations", "supply_po_confirmations", "confirmation_date", "supplier_id", "confirmation_reference"},
        {"RM Procurement Stage", "supply_rm_purchase_orders", "order_date", "rm_supplier_id", "supplier_order_no"},
        {"RM Receipts", "supply_rm_receipts", "receipt_date", "", "receipt_number", "heat_number", "rmtc_number"},
        {"RM to Forging (RM Dispatch)", "supply_rm_dispatches", "dispatch_date", "forging_supplier_id", "dispatch_number", "challan_number", "heat_number"},
        {"Forging Orders", "supply_forging_orders", "order_date", "forging_supplier_id", "supplier_order_no", "heat_number"},
        {"Forging Receipts", "supply_forging_receipts", "receipt_date", "forging_supplier_id", "receipt_number", "heat_number"},
        {"Production / Dispatch Events", "supply_downstream_events", "event_date", "", "reference_no", "invoice_no", "asn_no", "event_type"},
        {"Opening Stock", "supply_opening_stock", "created_at", "supplier_id", "lot_reference", "heat_number"},
        {"Material Inward", "inward_lots", "inward_date", "supplier_id", "inward_number", "grn_number", "invoice_number", "heat_number"},
        {"RMTC", "rmtc_approvals", "certificate_date", "supplier_id", "rmtc_number", "certificate_reference", "heat_number"},
        {"MetLAB / Bend Reports", "lab_tests", "test_date", "supplier_id", "report_number", "test_type", "heat_number"},
        {"Dimensional Reports", "inspection_reports", "inspection_date", "supplier_id", "report_number", "report_type", "heat_number"},
        {"Production Batches", "production_batches", "created_at", "", "vendor_batch_number", "heat_number"},
        {"OSP Jobs", "osp_jobs", "dispatch_date", "vendor_id", "osp_job_number", "receipt_number", "vendor_batch_number"},
        {"OSP Receipts", "osp_receipts", "receipt_date", "", "receipt_number", "vendor_invoice_number", "tc_number"},
        {"OSP Material Outs", "osp_material_outs", "created_at", "", "material_out_number"},
        {"Customer Dispatches", "dispatches", "dispatch_date", "customer_id", "dispatch_number", "invoice_number"},
        {"Quality Complaints", "quality_complaints", "complaint_date", "party_id", "complaint_number", "external_reference"},
        {"NPD Orders", "npd_orders", "order_date", "customer_id", "order_number"},
        {"QC Calculations", "qc_calculation_records", "calculation_date", "", "calculation_number", "calculation_type", "heat_number"},
        {"Calibration Records", "quality_asset_calibration_records", "service_date", "", "report_number", "certificate_number"},
        {"Standard Room Inspections", "standard_room_inspection_records", "inspection_date", "", "report_number", "program_reference"},
    };
    static final String[] STATUS_FIELDS = {"approval_status", "status", "confirmation_status", "receipt_status", "inspection_status"};

    private static int moduleIdx = 0;
    private static boolean useDates = false;
    private static String dateFrom = LocalDate.now().minusDays(30).toString(), dateTo = LocalDate.now().toString();
    private static JSONObject lastResult;

    private List<JSONObject> allRows = new ArrayList<>();
    private String creator = "All", needle = "";
    private final LinkedHashSet<String> picked = new LinkedHashSet<>();
    /** Preview of the current selection: key, table, ids, result. */
    private String previewKey = "";
    private JSONObject preview;
    private List<String> previewIds = new ArrayList<>();
    private LinearLayout listBox, previewBox;

    DevPurgeScreen(MainActivity a) { super(a); }

    @Override public String title() { return "Trial-data purge"; }
    @Override public String subtitle() { return "STAWN developer only · current company"; }
    @Override public int tab() { return Catalog.MORE; }

    static boolean isRootTable(String table) {
        for (String[] m : MODULES) if (m[1].equals(table)) return true;
        return false;
    }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> Licence.load(api), (st, err) -> {
            page.removeAllViews();
            if (err != null && Licence.status == null) { add(error(err, this::reload)); return; }
            JSONObject s = st == null ? Licence.status : st;
            if (s == null || !s.optBoolean("is_stawn_developer", false)) {
                add(AdmUi.adminOnly(a, "Trial-data purge is only available to the STAWN developer login."), 0);
                return;
            }
            render();
        });
        return scroll;
    }

    private void render() {
        LinearLayout intro = AdmUi.section(a, page, "", "TRIAL / TEST DATA PURGE",
            "Deletes the selected trial transactions together with EVERY record linked to them (lines, receipts, inwards, reports, attachments, "
                + "notifications …) in this company only. Master data (parts, parties, grades, processes, employees, layouts) is never deleted. "
                + "Every row is archived before it is removed.");
        if (lastResult != null) {
            intro.addView(AdmUi.note(a, "Last purge removed " + lastResult.optInt("total_deleted", 0) + " row(s) and "
                + lastResult.optInt("storage_removed", 0) + " file(s).", "green"), Ui.matchWrap(a, 6));
            JSONObject counts = lastResult.optJSONObject("deleted_counts");
            if (counts != null && counts.length() > 0) {
                List<List<String>> data = new ArrayList<>();
                for (String k : new TreeSet<>(keys(counts))) data.add(AdmUi.listOf(k, counts.optString(k)));
                intro.addView(new DataGrid(a, "Rows deleted", AdmUi.listOf("Table", "Rows deleted"), data, 220, null), Ui.matchWrap(a, 6));
            }
            JSONArray problems = lastResult.optJSONArray("storage_problems");
            for (int i = 0; problems != null && i < problems.length(); i++) intro.addView(AdmUi.note(a, "File removal: " + problems.optString(i), "amber"), Ui.matchWrap(a, 4));
        }

        LinearLayout h = AdmUi.section(a, page, "H", "PURGE TRIAL / TEST DATA (STAWN DEVELOPER ONLY)",
            "1 choose records · 2 preview everything linked · 3 download the Excel backup · 4 confirm");
        List<String> idx = new ArrayList<>(), names = new ArrayList<>();
        for (int i = 0; i < MODULES.length; i++) { idx.add(String.valueOf(i)); names.add(MODULES[i][0]); }
        AdmUi.choice(a, h, "Transaction module", idx, names, String.valueOf(moduleIdx), v -> { moduleIdx = Integer.parseInt(v); resetSelection(); loadRecords(); });
        CheckBox dates = AdmUi.check(a, "Filter by date", useDates);
        h.addView(dates, Ui.matchWrap(a, 6));
        EditText from = AdmUi.field(a, h, "From (YYYY-MM-DD)", dateFrom, "YYYY-MM-DD");
        EditText to = AdmUi.field(a, h, "To (YYYY-MM-DD)", dateTo, "YYYY-MM-DD");
        AdmUi.enableView(from, useDates);
        AdmUi.enableView(to, useDates);
        dates.setOnCheckedChangeListener((b, on) -> { useDates = on; AdmUi.enableView(from, on); AdmUi.enableView(to, on); });
        AdmUi.outline(a, h, "Apply filter / reload records", v -> {
            try {
                if (useDates) { dateFrom = LocalDate.parse(AdmUi.text(from).trim()).toString(); dateTo = LocalDate.parse(AdmUi.text(to).trim()).toString(); }
            } catch (Exception e) { a.toast("Use dates as YYYY-MM-DD."); return; }
            resetSelection();
            loadRecords();
        });
        listBox = Ui.vbox(a);
        h.addView(listBox, Ui.matchWrap(a, 8));
        previewBox = Ui.vbox(a);
        h.addView(previewBox, Ui.matchWrap(a, 8));
        loadRecords();

        LinearLayout runBox = AdmUi.section(a, page, "I", "PREVIOUS TRIAL-DATA PURGES", "");
        LinearLayout runs = Ui.vbox(a);
        runBox.addView(runs, Ui.matchWrap(a, 4));
        runs.addView(Ui.text(a, "Loading…", 12, Ui.MUTED, false));
        Api.async(this::recentRuns, (rows, err) -> {
            runs.removeAllViews();
            if (err != null || rows == null || rows.isEmpty()) { runs.addView(AdmUi.note(a, "No purge has been run yet.", "teal"), Ui.matchWrap(a, 4)); return; }
            runs.addView(new DataGrid(a, "Trial-data purges", AdmUi.listOf("When", "Module", "Records selected", "Rows deleted", "Files", "Reason", "By"), rows, 300, null), Ui.matchWrap(a, 4));
        });
    }

    private void resetSelection() {
        picked.clear();
        preview = null;
        previewKey = "";
        creator = "All";
        needle = "";
        if (previewBox != null) previewBox.removeAllViews();
    }

    private static List<String> keys(JSONObject o) {
        List<String> out = new ArrayList<>();
        Iterator<String> it = o.keys();
        while (it.hasNext()) out.add(it.next());
        return out;
    }

    private static String s(JSONObject o, String k) { return o == null || o.isNull(k) ? "" : o.optString(k, "").trim(); }

    // ------------------------------------------------------------------ list_records
    private void loadRecords() {
        listBox.removeAllViews();
        listBox.addView(Ui.text(a, "Loading records…", 12, Ui.MUTED, false));
        String[] spec = MODULES[moduleIdx];
        Api.async(() -> listRecords(spec), (rows, err) -> {
            listBox.removeAllViews();
            if (err != null) { listBox.addView(AdmUi.note(a, Api.message(err), "red")); return; }
            allRows = rows;
            renderList();
        });
    }

    private Map<String, String> labels(String table, List<String> ids, String... fields) {
        Map<String, String> out = new LinkedHashMap<>();
        LinkedHashSet<String> want = new LinkedHashSet<>();
        for (String i : ids) if (i != null && !i.isEmpty()) want.add(i);
        if (want.isEmpty()) return out;
        List<String> list = new ArrayList<>(want);
        for (int start = 0; start < list.size(); start += 150) {
            List<String> chunk = list.subList(start, Math.min(list.size(), start + 150));
            try {
                JSONArray rows = new JSONArray(api.get(table + "?select=id," + String.join(",", fields) + "&id=in.(" + String.join(",", chunk) + ")", false).body);
                for (int i = 0; i < rows.length(); i++) {
                    JSONObject r = rows.getJSONObject(i);
                    String label = "";
                    for (String f : fields) if (!s(r, f).isEmpty()) { label = s(r, f); break; }
                    String id = s(r, "id");
                    out.put(id, label.isEmpty() ? id.substring(0, Math.min(8, id.length())) : label);
                }
            } catch (Exception ignored) { }
        }
        return out;
    }

    private static LocalDate dateOf(JSONObject row, String column) {
        String raw = s(row, column);
        if (raw.isEmpty()) raw = s(row, "created_at");
        if (raw.length() < 10) return null;
        try { return LocalDate.parse(raw.substring(0, 10)); } catch (Exception e) { return null; }
    }

    private List<JSONObject> listRecords(String[] spec) throws Exception {
        String table = spec[1], dateCol = spec[2], partyCol = spec[3];
        JSONArray rows;
        try {
            rows = new JSONArray(api.get(table + "?select=*&tenant_id=eq." + Api.enc(api.tenantId) + "&order=created_at.desc&limit=2000", false).body);
        } catch (Exception e) {
            rows = new JSONArray(api.get(table + "?select=*&limit=2000", false).body);
        }
        List<String> partIds = new ArrayList<>(), partyIds = new ArrayList<>(), people = new ArrayList<>();
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.getJSONObject(i);
            partIds.add(s(r, "part_id"));
            if (!partyCol.isEmpty()) partyIds.add(s(r, partyCol));
            people.add(s(r, "created_by"));
        }
        Map<String, String> parts = labels("parts", partIds, "fsi_part_number", "part_number", "customer_part_number");
        Map<String, String> parties = partyCol.isEmpty() ? new LinkedHashMap<>() : labels("parties", partyIds, "party_name", "party_code");
        Map<String, String> creators = labels("profiles", people, "full_name", "email");
        LocalDate from = useDates ? LocalDate.parse(dateFrom) : null, to = useDates ? LocalDate.parse(dateTo) : null;
        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.getJSONObject(i);
            LocalDate when = dateOf(r, dateCol);
            if (from != null && (when == null || when.isBefore(from))) continue;
            if (to != null && (when == null || when.isAfter(to))) continue;
            String ref = "";
            for (int c = 4; c < spec.length && ref.isEmpty(); c++) ref = s(r, spec[c]);
            String id = s(r, "id");
            if (ref.isEmpty()) ref = id.substring(0, Math.min(8, id.length()));
            String status = "";
            for (String f : STATUS_FIELDS) if (status.isEmpty()) status = s(r, f).replace("_", " ");
            String cb = s(r, "created_by");
            String by = cb.isEmpty() ? "System / Legacy" : (creators.containsKey(cb) ? creators.get(cb) : cb.substring(0, Math.min(8, cb.length())));
            StringBuilder hay = new StringBuilder();
            for (int c = 4; c < spec.length; c++) hay.append(' ').append(s(r, spec[c]));
            out.add(new JSONObject().put("id", id).put("Reference", ref)
                .put("Date", when == null ? "" : Ui.date(when.toString()))
                .put("Part", parts.containsKey(s(r, "part_id")) ? parts.get(s(r, "part_id")) : "")
                .put("Party", partyCol.isEmpty() || !parties.containsKey(s(r, partyCol)) ? "" : parties.get(s(r, partyCol)))
                .put("Status", status).put("Created By", by).put("_hay", hay.toString()));
        }
        return out;
    }

    static String recordLabel(JSONObject r) {
        List<String> bits = new ArrayList<>();
        for (String k : new String[]{"Reference", "Date", "Part", "Party", "Status", "Created By"}) if (!s(r, k).isEmpty()) bits.add(s(r, k));
        String id = s(r, "id");
        return String.join(" · ", bits) + "  [" + id.substring(0, Math.min(8, id.length())) + "]";
    }

    private List<JSONObject> filtered() {
        List<JSONObject> out = new ArrayList<>();
        String n = needle.trim().toLowerCase(Locale.ROOT);
        for (JSONObject r : allRows) {
            if (!"All".equals(creator) && !creator.equals(s(r, "Created By"))) continue;
            if (!n.isEmpty()) {
                String hay = (s(r, "Reference") + " " + s(r, "Date") + " " + s(r, "Part") + " " + s(r, "Party") + " " + s(r, "Status") + " "
                    + s(r, "Created By") + " " + s(r, "_hay")).toLowerCase(Locale.ROOT);
                if (!hay.contains(n)) continue;
            }
            out.add(r);
        }
        return out;
    }

    private void renderList() {
        listBox.removeAllViews();
        TreeSet<String> creators = new TreeSet<>();
        for (JSONObject r : allRows) if (!s(r, "Created By").isEmpty()) creators.add(s(r, "Created By"));
        List<String> opts = new ArrayList<>();
        opts.add("All");
        opts.addAll(creators);
        if (!opts.contains(creator)) creator = "All";
        AdmUi.choice(a, listBox, "Created by", opts, creator, v -> { creator = v; renderList(); });
        EditText search = AdmUi.field(a, listBox, "Search (reference, part, party, status)", needle, null);
        AdmUi.outline(a, listBox, "Search", v -> { needle = AdmUi.text(search); renderList(); });
        List<JSONObject> rows = filtered();
        if (rows.isEmpty()) { listBox.addView(AdmUi.note(a, "No records match the filters.", "teal"), Ui.matchWrap(a, 6)); renderPreview(); return; }
        List<List<String>> data = new ArrayList<>();
        for (int i = 0; i < Math.min(300, rows.size()); i++) {
            JSONObject r = rows.get(i);
            data.add(AdmUi.listOf(s(r, "Reference"), s(r, "Date"), s(r, "Part"), s(r, "Party"), s(r, "Status"), s(r, "Created By")));
        }
        listBox.addView(new DataGrid(a, "Records", AdmUi.listOf("Reference", "Date", "Part", "Party", "Status", "Created By"), data, 320, i -> {
            String id = s(rows.get(i), "id");
            if (!picked.remove(id)) picked.add(id);
            renderList();
        }), Ui.matchWrap(a, 6));
        listBox.addView(Ui.text(a, rows.size() + " record(s) shown. Tap a row or tick below to select records to purge.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 4));
        listBox.addView(Ui.label(a, "Records to purge (" + picked.size() + " selected)"), Ui.matchWrap(a, 8));
        for (int i = 0; i < Math.min(300, rows.size()); i++) {
            JSONObject r = rows.get(i);
            String id = s(r, "id");
            CheckBox c = AdmUi.check(a, recordLabel(r), picked.contains(id));
            c.setOnCheckedChangeListener((b, on) -> { if (on) picked.add(id); else picked.remove(id); renderPreview(); });
            listBox.addView(c, Ui.matchWrap(a, 2));
        }
        renderPreview();
    }

    private String selectionKey() {
        List<String> ids = new ArrayList<>(new TreeSet<>(picked));
        return MODULES[moduleIdx][1] + ":" + String.join(",", ids);
    }

    // ------------------------------------------------------------------ preview + confirm
    private void renderPreview() {
        previewBox.removeAllViews();
        String table = MODULES[moduleIdx][1];
        Button run = AdmUi.outline(a, previewBox, "Preview everything that will be deleted", v -> {
            Button b = (Button) v;
            AdmUi.enable(b, false);
            List<String> ids = new ArrayList<>(picked);
            String key = selectionKey();
            Api.async(() -> preview(table, ids, true), (res, err) -> {
                AdmUi.enable(b, true);
                if (err != null) { preview = null; previewKey = ""; a.toast(Api.message(err)); renderPreview(); return; }
                preview = res; previewKey = key; previewIds = ids;
                renderPreview();
            });
        });
        AdmUi.enable(run, !picked.isEmpty());
        if (preview == null || !previewKey.equals(selectionKey())) {
            if (!picked.isEmpty()) previewBox.addView(Ui.text(a, "Run the preview for the current selection before deleting.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 4));
            return;
        }
        JSONObject result = preview;
        JSONArray tables = result.optJSONArray("tables");
        List<List<String>> summary = new ArrayList<>();
        List<String> tableNames = new ArrayList<>();
        for (int i = 0; tables != null && i < tables.length(); i++) {
            JSONObject t = tables.optJSONObject(i);
            String min = s(t, "min_depth"), max = s(t, "max_depth");
            summary.add(AdmUi.listOf(s(t, "table"), Ui.pretty(s(t, "table")), String.valueOf(t.optInt("count", 0)),
                t.optBoolean("is_root_table", false) ? "Yes" : "", min.equals(max) ? max : min + "–" + max));
            tableNames.add(s(t, "table"));
        }
        previewBox.addView(Ui.text(a, result.optInt("total_rows", 0) + " row(s) in " + summary.size() + " table(s) will be deleted.", 13.5f, Ui.TEXT, true), Ui.matchWrap(a, 8));
        previewBox.addView(new DataGrid(a, "Purge preview", AdmUi.listOf("Table", "Transaction", "Rows", "Selected root", "Level"), summary, 300, i -> showSamples(tableNames.get(i))), Ui.matchWrap(a, 4));
        previewBox.addView(Ui.text(a, "Tap a table to see up to 50 of its records; the Excel backup contains every row.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 4));
        JSONArray nullify = result.optJSONArray("nullify");
        for (int i = 0; nullify != null && i < nullify.length(); i++) {
            JSONObject n = nullify.optJSONObject(i);
            previewBox.addView(AdmUi.note(a, s(n, "count") + " " + s(n, "table") + " row(s) stay; their link " + s(n, "column") + " → " + s(n, "references") + " is cleared.", "teal"), Ui.matchWrap(a, 4));
        }
        JSONArray blockers = result.optJSONArray("blockers");
        boolean blocked = blockers != null && blockers.length() > 0;
        for (int i = 0; blocked && i < blockers.length(); i++) {
            JSONObject bl = blockers.optJSONObject(i);
            previewBox.addView(AdmUi.note(a, "Blocked: " + s(bl, "count") + " master row(s) in " + s(bl, "table") + "." + s(bl, "column") + " require these records.", "red"), Ui.matchWrap(a, 4));
        }
        boolean deep = result.optBoolean("depth_limit_reached", false);
        if (deep) previewBox.addView(AdmUi.note(a, "The linked chain is too deep (or loops). Purge a lower-level transaction first.", "red"), Ui.matchWrap(a, 4));
        JSONArray paths = result.optJSONArray("storage_paths");
        if (paths != null && paths.length() > 0) previewBox.addView(Ui.text(a, paths.length() + " stored file(s) will also be removed from the document store.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 4));

        AdmUi.primary(a, previewBox, "Download Excel backup (all rows)", v -> {
            String name = "STAWN_QCMS_trial_purge_backup_" + table + "_" + LocalDate.now().toString().replace("-", "") + ".xlsx";
            Api.async(() -> SndFiles.saveToDownloads(a, name, ExportKit.xlsx(a, backupDoc(result)), ExportKit.XLSX), (saved, err) -> {
                if (err != null || saved == null) { a.toast("Could not save the backup: " + Api.message(err)); return; }
                a.toast("Backup saved: " + saved.where);
                if (saved.uri != null) SndFiles.share(a, saved.uri, ExportKit.XLSX, name);
            });
        });

        previewBox.addView(Ui.label(a, "Confirm permanent deletion"), Ui.matchWrap(a, 12));
        EditText confirm = AdmUi.field(a, previewBox, "Type " + CONFIRM_PHRASE, "", CONFIRM_PHRASE);
        EditText reason = AdmUi.field(a, previewBox, "Reason (mandatory)", "", "At least 5 characters");
        EditText password = AdmUi.password(a, previewBox, "Your current QCMS password", "Password");
        CheckBox agree = AdmUi.check(a, "I downloaded the backup. These records are trial / test data and must be deleted with everything linked.", false);
        previewBox.addView(agree, Ui.matchWrap(a, 6));
        Button go = AdmUi.primary(a, previewBox, "Delete trial data permanently", v -> {
            String c = AdmUi.text(confirm).trim(), r = AdmUi.text(reason).trim(), pw = AdmUi.text(password);
            if (!CONFIRM_PHRASE.equals(c)) { confirm.setError("Type " + CONFIRM_PHRASE + " exactly to confirm."); return; }
            if (r.length() < 5) { reason.setError("Enter the reason for this purge (at least 5 characters)."); return; }
            if (pw.isEmpty()) { password.setError("Enter your current QCMS password."); return; }
            if (!agree.isChecked()) { a.toast("Tick the backup confirmation first."); return; }
            if (blocked || deep) { a.toast("This selection cannot be purged (see the red notes)."); return; }
            Button b = (Button) v;
            AdmUi.enable(b, false);
            List<String> ids = new ArrayList<>(previewIds);
            Api.async(() -> execute(table, ids, c, r, pw), (out, err) -> {
                AdmUi.enable(b, true);
                if (err != null) { a.toast(Api.message(err)); return; }
                lastResult = out;
                a.toast("Trial data purged: " + out.optInt("total_deleted", 0) + " row(s) deleted.");
                reload();
            });
        });
        AdmUi.enable(go, !blocked && !deep);
    }

    private void showSamples(String table) {
        JSONArray tables = preview == null ? null : preview.optJSONArray("tables");
        StringBuilder b = new StringBuilder();
        for (int i = 0; tables != null && i < tables.length(); i++) {
            JSONObject t = tables.optJSONObject(i);
            if (!table.equals(s(t, "table"))) continue;
            JSONArray samples = t.optJSONArray("samples");
            for (int j = 0; samples != null && j < samples.length(); j++) {
                JSONObject x = samples.optJSONObject(j);
                String created = s(x, "created_at");
                b.append("• ").append(s(x, "label")).append(s(x, "status").isEmpty() ? "" : " · " + s(x, "status"))
                    .append(created.isEmpty() ? "" : " · " + created.substring(0, Math.min(16, created.length())).replace("T", " "))
                    .append(" · level ").append(s(x, "depth")).append('\n');
            }
        }
        new android.app.AlertDialog.Builder(a).setTitle("Records of " + table).setMessage(b.length() == 0 ? "No sample records." : b.toString())
            .setPositiveButton("OK", null).show();
    }

    // ------------------------------------------------------------------ service (dev_purge_service.py)
    private JSONObject preview(String table, List<String> ids, boolean includeRows) throws Exception {
        if (!isRootTable(table)) throw new Api.ApiException(422, table + " is not a transaction module that can be purged.");
        if (ids.isEmpty()) throw new Api.ApiException(422, "Select at least one record.");
        JSONArray arr = new JSONArray();
        for (String i : new LinkedHashSet<>(ids)) arr.put(i);
        return api.rpcObject("qcms_dev_purge_preview", new JSONObject().put("p_table", table).put("p_ids", arr).put("p_include_rows", includeRows));
    }

    /** Re-check the password, purge on the server (one transaction), then remove the stored files. */
    private JSONObject execute(String table, List<String> ids, String confirm, String reason, String password) throws Exception {
        if (!CONFIRM_PHRASE.equals(confirm == null ? "" : confirm.trim())) throw new Api.ApiException(422, "Type " + CONFIRM_PHRASE + " exactly to confirm.");
        if (reason == null || reason.trim().length() < 5) throw new Api.ApiException(422, "Enter the reason for this purge (at least 5 characters).");
        if (!isRootTable(table)) throw new Api.ApiException(422, table + " is not a transaction module that can be purged.");
        if (ids.isEmpty()) throw new Api.ApiException(422, "Select at least one record.");
        try { api.verifyPassword(password); } catch (Exception e) { throw new Api.ApiException(403, "The password is incorrect. Nothing was deleted."); }
        JSONArray arr = new JSONArray();
        for (String i : new LinkedHashSet<>(ids)) arr.put(i);
        JSONObject result = api.rpcObject("qcms_dev_purge_execute", new JSONObject().put("p_table", table).put("p_ids", arr)
            .put("p_confirm", CONFIRM_PHRASE).put("p_reason", reason.trim()));
        int removed = 0;
        JSONArray problems = new JSONArray();
        JSONArray paths = result.optJSONArray("storage_paths");
        LinkedHashSet<String> clean = new LinkedHashSet<>();
        for (int i = 0; paths != null && i < paths.length(); i++) if (!paths.optString(i, "").trim().isEmpty()) clean.add(paths.optString(i).trim());
        int failed = 0;
        for (String p : clean) { if (api.removeFrom(Api.BUCKET, p)) removed++; else failed++; }
        if (failed > 0) problems.put(failed + " file(s) were not found or could not be removed.");
        result.put("storage_removed", removed).put("storage_problems", problems);
        return result;
    }

    /** backup_workbook: Summary sheet + one sheet per table with every previewed row. */
    private static ExportDoc backupDoc(JSONObject result) {
        ExportDoc doc = new ExportDoc("Trial-data purge backup").file("STAWN_QCMS_trial_purge_backup");
        StringBuilder files = new StringBuilder();
        JSONArray paths = result.optJSONArray("storage_paths");
        for (int i = 0; paths != null && i < paths.length(); i++) files.append(i == 0 ? "" : "\n").append(paths.optString(i));
        doc.section("Summary").pair("Root table", s(result, "root_table")).pair("Root records", s(result, "root_count"))
            .pair("Total rows", s(result, "total_rows")).pair("Company (tenant)", s(result, "tenant_id"))
            .pair("Backup taken", java.time.LocalDateTime.now().withNano(0).toString().replace("T", " ")).pair("Storage files", files.toString());
        JSONArray tables = result.optJSONArray("tables");
        List<List<String>> summary = new ArrayList<>();
        for (int i = 0; tables != null && i < tables.length(); i++) {
            JSONObject t = tables.optJSONObject(i);
            summary.add(AdmUi.listOf(s(t, "table"), String.valueOf(t.optInt("count", 0)), t.optBoolean("is_root_table", false) ? "Yes" : ""));
        }
        doc.table("Summary", AdmUi.listOf("Table", "Rows", "Selected root"), summary);
        for (int i = 0; tables != null && i < tables.length(); i++) {
            JSONObject t = tables.optJSONObject(i);
            JSONArray rows = t.has("rows") && !t.isNull("rows") ? t.optJSONArray("rows") : t.optJSONArray("samples");
            LinkedHashSet<String> cols = new LinkedHashSet<>();
            for (int j = 0; rows != null && j < rows.length(); j++) { JSONObject r = rows.optJSONObject(j); if (r != null) cols.addAll(keys(r)); }
            if (cols.isEmpty()) cols.add("id");
            List<List<String>> data = new ArrayList<>();
            for (int j = 0; rows != null && j < rows.length(); j++) {
                JSONObject r = rows.optJSONObject(j);
                List<String> line = new ArrayList<>();
                for (String c : cols) line.add(r == null || r.isNull(c) ? "" : String.valueOf(r.opt(c)));
                data.add(line);
            }
            doc.table(s(t, "table"), new ArrayList<>(cols), data);
        }
        return doc;
    }

    private List<List<String>> recentRuns() throws Exception {
        JSONArray rows = new JSONArray(api.get("qcms_purge_runs?select=*&order=executed_at.desc&limit=50", false).body);
        List<String> by = new ArrayList<>();
        for (int i = 0; i < rows.length(); i++) by.add(s(rows.getJSONObject(i), "executed_by"));
        Map<String, String> people = labels("profiles", by, "full_name", "email");
        List<List<String>> out = new ArrayList<>();
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.getJSONObject(i);
            Object rawCounts = r.opt("deleted_counts");
            JSONObject counts = rawCounts instanceof JSONObject ? (JSONObject) rawCounts : null;
            if (counts == null && rawCounts instanceof String) { try { counts = new JSONObject((String) rawCounts); } catch (Exception ignored) { } }
            int total = 0;
            if (counts != null) for (String k : keys(counts)) total += counts.optInt(k, 0);
            String module = s(r, "root_table");
            for (String[] m : MODULES) if (m[1].equals(s(r, "root_table"))) module = m[0];
            JSONArray ids = r.optJSONArray("root_ids"), files = r.optJSONArray("storage_paths");
            String when = s(r, "executed_at");
            String who = s(r, "executed_by");
            out.add(AdmUi.listOf(when.substring(0, Math.min(16, when.length())).replace("T", " "), module, String.valueOf(ids == null ? 0 : ids.length()),
                String.valueOf(total), String.valueOf(files == null ? 0 : files.length()), s(r, "reason"),
                people.containsKey(who) ? people.get(who) : who.substring(0, Math.min(8, who.length()))));
        }
        return out;
    }
}
