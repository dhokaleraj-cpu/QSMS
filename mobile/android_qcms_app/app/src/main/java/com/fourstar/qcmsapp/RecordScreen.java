package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/** One record: details, actions (edit / workflow / delete), child tables, photos & documents, history. */
public final class RecordScreen extends Screen implements ExportKit.RecordPrint {
    static final Set<String> HIDDEN = new HashSet<>(Arrays.asList("id", "tenant_id", "created_by", "updated_by", "search_vector", "search_text"));
    /** Same lists as core/delete_service.py. */
    static final Set<String> TRANSACTION_TABLES = new HashSet<>(Arrays.asList(
        "supply_customer_orders", "supply_purchase_orders", "supply_po_confirmations", "supply_rm_purchase_orders", "supply_rm_receipts",
        "supply_rm_dispatches", "supply_forging_orders", "supply_forging_receipts", "supply_downstream_events", "supply_opening_stock",
        "osp_jobs", "osp_receipts", "rmtc_approvals", "inward_lots", "inspection_reports", "lab_tests", "npd_orders", "npd_process_flows",
        "ppap_projects", "pfd_headers", "pfmea_headers", "control_plan_headers", "spc_studies", "msa_studies", "capacity_studies",
        "qc_calculation_records", "quality_complaints", "quality_asset_part_process_links", "quality_asset_calibration_records",
        "standard_room_inspection_records"));

    static final Set<String> FULL_REPORT = new HashSet<>(Arrays.asList(
        "lab_tests", "inspection_reports", "rmtc_approvals", "inward_lots", "qc_calculation_records", "quality_complaints"));

    private final Module m;
    private final String id;

    @Override public boolean layoutReady() { return row != null && !m.idField.isEmpty(); }

    /** Website print layout of this record (dedicated report or Universal Record PDF). */
    @Override public void printLayout() { ExportKit.layoutMenu(a, () -> RptReports.forRecord(api, m, id)); }

    private void addFullReport() {
        add(Ui.label(a, "Full report (as printed)"), 10);
        LinearLayout holder = Ui.card(a);
        holder.addView(Ui.text(a, "Loading every entry of this report…", 12, Ui.MUTED, false));
        add(holder, 2);
        Api.async(() -> RptReports.forRecord(api, m, id), (doc, err) -> {
            holder.removeAllViews();
            if (err != null || doc == null) { holder.addView(Ui.text(a, "Could not load the report: " + Api.message(err), 12, Ui.RED_FG, false)); return; }
            holder.addView(RptView.build(a, doc));
        });
    }
    private JSONObject row;
    private String title = "";

    public RecordScreen(MainActivity a, Module m, String id) { super(a); this.m = m; this.id = id; }

    @Override public String title() { return title.isEmpty() ? m.title : title; }
    @Override public String subtitle() { return m.title; }
    @Override public int tab() { return m.tab; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONArray r = api.rows(m.table + "?select=*&" + m.idField + "=eq." + Api.enc(id));
            if (r.length() == 0) throw new Api.ApiException(404, "Record not found or not visible for your role.");
            JSONObject rec = r.getJSONObject(0);
            List<String> keys = new ArrayList<>();
            Iterator<String> it = rec.keys();
            while (it.hasNext()) keys.add(it.next());
            JSONArray one = new JSONArray();
            one.put(rec);
            Map<String, Map<String, String>> fk = Labels.resolve(api, m.table, one, keys);
            return new Object[]{rec, keys, fk};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            @SuppressWarnings("unchecked") List<String> keys = (List<String>) res[1];
            @SuppressWarnings("unchecked") Map<String, Map<String, String>> fk = (Map<String, Map<String, String>>) res[2];
            render((JSONObject) res[0], keys, fk);
        });
        return scroll;
    }

    /** "status=DRAFT|ON_HOLD;approval_status!=APPROVED" - every part must hold. */
    static boolean when(JSONObject row, String condition) {
        if (condition == null || condition.trim().isEmpty() || row == null) return true;
        for (String part : condition.split(";")) {
            String p = part.trim();
            if (p.isEmpty()) continue;
            boolean not = p.contains("!=");
            String[] kv = p.split(not ? "!=" : "=", 2);
            if (kv.length < 2) continue;
            String v = Lookups.j(row, kv[0].trim()).toUpperCase(Locale.ROOT);
            boolean match = false;
            for (String opt : kv[1].split("\\|")) if (opt.trim().equalsIgnoreCase(v) || ("EMPTY".equals(opt.trim()) && v.isEmpty())) match = true;
            if (not == match) return false;
        }
        return true;
    }

    private void render(JSONObject rec, List<String> keys, Map<String, Map<String, String>> fk) {
        row = rec;
        title = m.recordTitle(rec);
        a.rebuildTitle(this);
        offlineNote();

        LinearLayout head = Ui.card(a);
        LinearLayout top = Ui.hbox(a);
        top.addView(Ui.text(a, title, 17, Ui.TEXT, true), Ui.weight(1));
        String st = m.statusField.isEmpty() ? "" : Lookups.j(rec, m.statusField);
        if (!st.isEmpty()) top.addView(Ui.chip(a, Ui.pretty(st), Ui.tone(st)));
        head.addView(top);
        if (!m.description.isEmpty()) head.addView(Ui.text(a, m.title, 12, Ui.MUTED, false));
        add(head, 2);

        // ---- R39: OSP Material Out = Returnable Delivery Challan record (Details · Print · Vendor returns)
        if ("osp_material_outs".equals(m.table)) add(OspRecordView.build(a, id, null, true, this::reload), 8);
        // ---- R39: approved RMTC - material-location QR (PNG / JPEG / PDF / 100 x 60 mm label) and sections applicable
        if ("rmtc_approvals".equals(m.table)) add(IncQrLabel.panel(a, rec, this::reload), 8);

        // ---- actions
        LinearLayout actions = Ui.vbox(a);
        if (m.canCreate() && m.editable && !m.idField.isEmpty()) {
            Button edit = Ui.primary(a, "Edit");
            edit.setOnClickListener(v -> a.push(EditScreen.open(a, m, id, null)));
            actions.addView(edit, Ui.matchWrap(a, 0));
        }
        for (Module.Act act : m.actions) {
            if (!when(rec, act.when)) continue;
            if ("parts".equals(m.table) && !MstPartSections.showAction(rec, act.label)) continue;   // R39 Part sections applicable
            Button b = Ui.outline(a, act.label, Ui.TEAL);
            b.setOnClickListener(v -> act.action.run(a, row, this::reload));
            actions.addView(b, Ui.matchWrap(a, 8));
        }
        Button layout = Ui.primary(a, "🖨 Print layout PDF · Preview · Download · Share · Email");
        layout.setOnClickListener(v -> printLayout());
        actions.addView(layout, Ui.matchWrap(a, actions.getChildCount() > 0 ? 8 : 0));
        Button export = Ui.outline(a, "⇩ Data export: PDF / Excel", Ui.TEAL_DARK);
        export.setOnClickListener(v -> ExportKit.showData(a, this, scroll));
        actions.addView(export, Ui.matchWrap(a, actions.getChildCount() > 0 ? 8 : 0));
        if (actions.getChildCount() > 0) add(actions, 10);

        // ---- R33: the full report exactly as printed (all entries of MetLAB / Bend Test / Dimensional / RMTC / Inward)
        if (FULL_REPORT.contains(m.table)) addFullReport();

        // ---- details
        add(Ui.label(a, "Details"), 10);
        LinearLayout details = Ui.card(a);
        for (String k : keys) {
            if (HIDDEN.contains(k) || k.endsWith("_path") || k.endsWith("_snapshot") && rec.opt(k) instanceof JSONObject) continue;
            Object v = rec.opt(k);
            if (v instanceof JSONObject && ((JSONObject) v).length() > 6) continue;
            String text = Labels.cell(k, v, fk.get(k));
            if (text.isEmpty()) continue;
            details.addView(Ui.pair(a, Labels.header(k), text));
        }
        add(details, 2);

        // ---- child tables
        for (Module.Child child : m.children) if (!"parts".equals(m.table) || MstPartSections.showChild(rec, child.table)) addChild(child);   // R39 N/A sections hidden

        // ---- photos & documents
        if (m.attachEntity != null) addAttachments();

        // ---- history & delete
        Button history = Ui.outline(a, "Record history (who changed what)", Ui.TEAL);
        history.setOnClickListener(v -> a.push(new HistoryScreen(a, m, id, title)));
        add(history, 14);
        if (m.deletable && !m.idField.isEmpty() && !m.table.startsWith("v_")) {
            Button del = Ui.outline(a, "Delete", Ui.ORANGE);
            del.setOnClickListener(v -> delete());
            add(del, 8);
        }
    }

    private void addChild(Module.Child child) {
        add(Ui.label(a, child.title), 12);
        LinearLayout holder = Ui.vbox(a);
        holder.addView(loading());
        add(holder, 2);
        Api.async(() -> {
            String order = child.order == null || child.order.isEmpty() ? "" : "&order=" + child.order;
            JSONArray rows = api.rows(child.table + "?select=*&" + child.fk + "=eq." + Api.enc(id) + order + "&limit=2000");
            List<String> cols = new ArrayList<>();
            for (String[] c : child.cols) cols.add(c[0]);
            Map<String, Map<String, String>> fk = Labels.resolve(api, child.table, rows, cols);
            return new Object[]{rows, fk};
        }, (res, err) -> {
            holder.removeAllViews();
            if (err != null) { holder.addView(Ui.text(a, Api.message(err), 12, Ui.RED_FG, false)); return; }
            JSONArray rows = (JSONArray) res[0];
            @SuppressWarnings("unchecked") Map<String, Map<String, String>> fk = (Map<String, Map<String, String>>) res[1];
            if (ChemGrid.handles(child.table) && rows.length() > 0) {
                // R38: chemistry / Jominy shown horizontally - elements / distances are columns, Jominy inch + mm rows.
                for (Map.Entry<String, List<String[]>> e : ChemGrid.horizontal(child.table, rows, fk.get("part_id")).entrySet()) {
                    if (e.getValue().size() < 2) continue;
                    String t = e.getKey().isEmpty() ? child.title : child.title + " · " + e.getKey();
                    if (!e.getKey().isEmpty()) holder.addView(Ui.text(a, e.getKey(), 12, Ui.MUTED, true));
                    holder.addView(new DataGrid(a, t, ChemGrid.headers(e.getValue()), ChemGrid.data(e.getValue()), 300, null));
                }
                return;
            }
            List<String> headers = new ArrayList<>();
            for (String[] c : child.cols) headers.add(c[1]);
            List<List<String>> data = new ArrayList<>();
            for (int i = 0; i < rows.length(); i++) {
                JSONObject r = rows.optJSONObject(i);
                List<String> line = new ArrayList<>();
                for (String[] c : child.cols) line.add(Labels.cell(c[0], r.opt(c[0]), fk.get(c[0])));
                data.add(line);
            }
            Module target = Catalog.forTable(child.table);
            Module open = target != null ? target : Catalog.adhoc(child.table);
            holder.addView(new DataGrid(a, child.title, headers, data, 300, index -> {
                JSONObject r = rows.optJSONObject(index);
                if (r != null && r.has("id")) a.push(new RecordScreen(a, open, r.optString("id")));
            }));
        });
    }

    private void addAttachments() {
        add(Ui.label(a, "Photos & documents"), 12);
        LinearLayout box = Ui.card(a);
        box.addView(loading());
        add(box, 2);
        Api.async(() -> Attachments.list(api, m.attachEntity, id), (rows, err) -> {
            box.removeAllViews();
            if (err != null) { box.addView(Ui.text(a, Api.message(err), 12, Ui.RED_FG, false)); }
            else if (rows.length() == 0) box.addView(Ui.text(a, "No photos or documents yet.", 12.5f, Ui.MUTED, false));
            for (int i = 0; rows != null && i < rows.length(); i++) {
                JSONObject r = rows.optJSONObject(i);
                LinearLayout line = Ui.hbox(a);
                line.setPadding(0, dp(8), 0, dp(8));
                LinearLayout text = Ui.vbox(a);
                String t = Lookups.j(r, "document_title");
                text.addView(Ui.text(a, t.isEmpty() ? Ui.pretty(Lookups.j(r, "document_type")) : t, 13, Ui.TEXT, true));
                text.addView(Ui.text(a, Lookups.j(r, "file_name") + " · " + Ui.date(Lookups.j(r, "created_at")), 11, Ui.MUTED, false));
                line.addView(text, Ui.weight(1));
                TextView open = Ui.text(a, "Open", 13, Ui.TEAL_DARK, true);
                open.setPadding(dp(10), dp(6), dp(4), dp(6));
                final String path = Lookups.j(r, "object_path");
                open.setOnClickListener(v -> Api.async(() -> Attachments.signedUrl(api, path), (url, e2) -> {
                    if (e2 != null) a.toast(Api.message(e2)); else a.openInBrowser(url);
                }));
                line.addView(open);
                box.addView(Ui.divider(a));
                box.addView(line);
            }
            if (m.attachSlots.length > 0 || m.attachMulti) {
                Button add = Ui.outline(a, "Add photo / document (camera or file)", Ui.TEAL);
                add.setOnClickListener(v -> pickSlot());
                box.addView(add, Ui.matchWrap(a, 10));
            }
        });
    }

    private void pickSlot() {
        String[] slots = m.attachSlots.length > 0 ? m.attachSlots : new String[]{"PHOTO"};
        String[] labels = new String[slots.length];
        for (int i = 0; i < slots.length; i++) labels[i] = Ui.pretty(slots[i]);
        new android.app.AlertDialog.Builder(a).setTitle("Document type").setItems(labels, (d, which) -> {
            String slot = slots[which];
            boolean imagesOnly = slot.contains("PHOTO") || slot.contains("MICROSTRUCTURE");
            a.pickFile(Ui.pretty(slot), imagesOnly, file -> {
                if (m.attachMulti) {
                    a.askText("Title of this " + (imagesOnly ? "photo" : "document"), "e.g. Damaged thread close-up", "Upload", true,
                        titleText -> upload(slot, file, titleText));
                } else {
                    upload(slot, file, null);
                }
            });
        }).setNegativeButton("Back", null).show();
    }

    private void upload(String slot, Attachments.FileData file, String titleText) {
        a.toast("Uploading " + file.name + " (" + (file.data.length / 1024) + " KB)…");
        Api.async(() -> titleText == null
                ? Attachments.uploadSlot(api, m.attachEntity, id, m.attachFolder, slot, file, null, null)
                : Attachments.uploadAdditional(api, m.attachEntity, id, m.attachFolder, slot, file, titleText),
            (path, err) -> {
                if (err != null) { a.toast("Upload failed: " + Api.message(err)); return; }
                a.toast("Uploaded.");
                reload();
            });
    }

    private void delete() {
        if (row == null) return;
        boolean approved = "APPROVED".equalsIgnoreCase(Lookups.j(row, "approval_status"))
            || Arrays.asList("APPROVED", "RELEASED", "FINAL", "CLOSED", "COMPLETED").contains(Lookups.j(row, "status").toUpperCase(Locale.ROOT))
            || "CONFIRMED".equalsIgnoreCase(Lookups.j(row, "confirmation_status"));
        if (approved && !api.isAdmin()) {
            a.askText("Approved record · deletion request", "Reason for deletion (sent to the Admin)", "Send request", true, reason ->
                Api.async(() -> api.rpc("qcms_request_delete", new JSONObject().put("p_table_name", m.table).put("p_record_id", id).put("p_reason", reason).put("p_label", title)),
                    (ok, err) -> a.toast(err != null ? Api.message(err) : "Deletion request sent to the Admin.")));
            return;
        }
        a.confirm("Delete " + title + "?", "Deletion is permanent. You will be asked for your password." + (approved ? "\n\nThis record is approved: as Admin it is deleted through an approved deletion request." : ""), "Continue", () ->
            a.confirmPassword("Confirm delete with your password", () -> Api.async(() -> {
                if (approved) {
                    JSONObject req = new JSONObject(api.rpc("qcms_request_delete", new JSONObject().put("p_table_name", m.table).put("p_record_id", id).put("p_reason", "Deleted by Admin from the QCMS app").put("p_label", title)));
                    JSONObject res = new JSONObject(api.rpc("qcms_decide_delete_request", new JSONObject().put("p_request_id", req.optString("id")).put("p_approve", true).put("p_note", "Approved from the QCMS app")));
                    if ("FAILED".equals(res.optString("status"))) throw new Api.ApiException(409, res.optString("error"));
                } else if ("supply_purchase_orders".equals(m.table)) {
                    api.rpc("qcms_delete_purchase_order", new JSONObject().put("p_purchase_order_id", id));
                } else if ("supply_customer_orders".equals(m.table)) {
                    api.rpc("qcms_delete_customer_order", new JSONObject().put("p_customer_order_id", id));
                } else if (TRANSACTION_TABLES.contains(m.table)) {
                    api.rpc("qcms_delete_transaction_row", new JSONObject().put("p_table_name", m.table).put("p_record_id", id));
                } else {
                    api.rpc("qsms_delete_master_row", new JSONObject().put("p_table_name", m.table).put("p_record_id", id));
                }
                return true;
            }, (ok, err) -> {
                if (err != null) { a.toast("Deletion blocked: " + Api.message(err)); return; }
                a.toast("Deleted. It stays viewable in Records → Deleted Records.");
                a.back();
            })));
    }

    @Override public void reload() { a.rebuild(); }

    /** Audit trail of one record (qcms_record_history). */
    static final class HistoryScreen extends Screen {
        private final Module m; private final String id; private final String label;
        HistoryScreen(MainActivity a, Module m, String id, String label) { super(a); this.m = m; this.id = id; this.label = label; }
        @Override public String title() { return "History · " + label; }
        @Override public String subtitle() { return "Every change with date, user and old → new value"; }
        @Override public int tab() { return m.tab; }
        @Override public View build() {
            newPage();
            page.addView(loading());
            Api.async(() -> {
                Object v = api.rpcValue("qcms_record_history", new JSONObject().put("p_table_name", m.table).put("p_row_id", id));
                if (v instanceof JSONArray) return (JSONArray) v;
                return api.rows("audit_log?select=changed_at,operation,changed_by,old_data,new_data&table_name=eq." + m.table + "&row_id=eq." + id + "&order=changed_at.desc&limit=200");
            }, (rows, err) -> {
                page.removeAllViews();
                if (err != null) { page.addView(error(err, this::reload)); return; }
                List<String> cols = Arrays.asList("When", "Action", "By", "Changes");
                List<List<String>> data = new ArrayList<>();
                for (int i = 0; i < rows.length(); i++) {
                    JSONObject r = rows.optJSONObject(i);
                    JSONObject oldD = r.optJSONObject("old_data"), newD = r.optJSONObject("new_data");
                    StringBuilder ch = new StringBuilder();
                    if (oldD != null && newD != null) {
                        Iterator<String> it = newD.keys();
                        while (it.hasNext()) {
                            String k = it.next();
                            if (k.equals("updated_at") || k.equals("search_vector")) continue;
                            String o = String.valueOf(oldD.opt(k)), n = String.valueOf(newD.opt(k));
                            if (!o.equals(n)) { if (ch.length() > 0) ch.append("; "); ch.append(Labels.header(k)).append(": ").append(o.equals("null") ? "-" : o).append(" → ").append(n.equals("null") ? "-" : n); }
                        }
                    }
                    String by = Lookups.j(r, "changed_by_name");
                    if (by.isEmpty()) by = Lookups.j(r, "changed_by");
                    data.add(Arrays.asList(Ui.date(Lookups.j(r, "changed_at")) + " " + (Lookups.j(r, "changed_at").length() > 16 ? Lookups.j(r, "changed_at").substring(11, 16) : ""),
                        Ui.pretty(Lookups.j(r, "operation")), by, ch.length() == 0 ? "-" : ch.toString()));
                }
                add(new DataGrid(a, "History", cols, data, 600, null), 0);
            });
            return scroll;
        }
    }
}
