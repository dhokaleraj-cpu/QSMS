package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * R39 · One ECN / PCN (app_pages/ecn.py render_ecn_register_panel, selected note): KPIs, previous / new revision files,
 * status transitions (Submit, Approve / Disapprove = Part Master approve right, Return to Draft, Cancel, Mark Completed -
 * refused while an implementation action is open), edit, implementation actions (part_ecn_actions), supporting documents
 * (document_attachments entity PART_ECN, folder part_ecns/&lt;id&gt; like the website) and the FSI/806/F05 print.
 */
public final class EcnScreen extends Screen {
    static final String[][] SLOTS = {{"REDLINE_DRAWING", "Redline Drawing"}, {"DATASHEET", "Datasheet"}, {"SUPPORTING_DOCUMENT", "Other Supporting Document"}};

    private final String id;
    private JSONObject ecn;
    private List<JSONObject> actions = new ArrayList<>();
    private JSONArray files = new JSONArray();
    private JSONObject prevFile, newFile;
    private Map<String, String> employees;
    private boolean[] perms = {false, false, false};

    public EcnScreen(MainActivity a, String id) { super(a); this.id = id; }

    @Override public String title() { return ecn == null ? "ECN / PCN" : EcnData.s(ecn, "ecn_number"); }
    @Override public String subtitle() { return ecn == null ? "Engineering / Process Change Note" : EcnData.changeTitle(EcnData.s(ecn, "change_type")).toLowerCase(Locale.ROOT); }
    @Override public int tab() { return Catalog.MASTERS; }

    private boolean writable() { return perms[0] || perms[1]; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            boolean[] p = EcnData.permissions(api);
            JSONArray r = api.rows(EcnData.TABLE + "?select=*&id=eq." + Api.enc(id) + "&limit=1");
            if (r.length() == 0) throw new Api.ApiException(404, "ECN / PCN not found or not visible for your role.");
            JSONObject row = r.getJSONObject(0);
            List<JSONObject> acts = EcnData.actions(api, id);
            JSONArray att = Attachments.list(api, EcnData.ATTACHMENT_ENTITY, id);
            JSONObject prev = attachment(EcnData.s(row, "previous_attachment_id"));
            JSONObject next = attachment(EcnData.s(row, "document_attachment_id"));
            Map<String, String> emp = EcnData.employees(api);
            return new Object[]{p, row, acts, att, prev, next, emp};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            perms = (boolean[]) res[0];
            ecn = (JSONObject) res[1];
            actions = EcnData.cast(res[2]);
            files = (JSONArray) res[3];
            prevFile = (JSONObject) res[4];
            newFile = (JSONObject) res[5];
            @SuppressWarnings("unchecked") Map<String, String> emp = (Map<String, String>) res[6];
            employees = emp;
            a.rebuildTitle(this);
            render();
        });
        return scroll;
    }

    private JSONObject attachment(String attId) throws Exception {
        if (attId == null || attId.isEmpty()) return null;
        JSONArray r = api.rows("document_attachments?select=id,document_type,drawing_number,revision,revision_date,file_name,object_path,mime_type,status&id=eq." + Api.enc(attId) + "&limit=1");
        return r.length() == 0 ? null : r.getJSONObject(0);
    }

    private String emp(String empId) { return employees != null && employees.containsKey(empId) ? employees.get(empId) : ""; }

    private void render() {
        offlineNote();
        String st = EcnData.status(ecn);
        // ---- KPI tiles (register panel kpi_grid)
        List<LinearLayout> t = new ArrayList<>();
        t.add(PpapHomeScreen.tile(a, "ECN / PCN No.", EcnData.s(ecn, "ecn_number"), EcnData.changeTitle(EcnData.s(ecn, "change_type")).toLowerCase(Locale.ROOT) + " · " + Ui.date(EcnData.s(ecn, "ecn_date")), 0xFF0B6E70, 0xFFE3F2F2));
        t.add(PpapHomeScreen.tile(a, "Status", EcnData.statusLabel(st), "Customer approval: " + Ui.pretty(EcnData.s(ecn, "customer_approval")), 0xFF2563EB, 0xFFEFF6FF));
        t.add(PpapHomeScreen.tile(a, "Drawing / Revision", EcnData.s(ecn, "drawing_number").isEmpty() ? "-" : EcnData.s(ecn, "drawing_number"),
            "Rev " + dash(EcnData.s(ecn, "previous_revision")) + " → " + dash(EcnData.s(ecn, "new_revision")), 0xFF7C3AED, 0xFFF5F3FF));
        t.add(PpapHomeScreen.tile(a, "Linked Revision", EcnData.s(ecn, "document_attachment_id").isEmpty() ? "No" : "Yes", EcnData.scopeLabel(EcnData.s(ecn, "document_scope")), 0xFFB45309, 0xFFFFFBEB));
        LinearLayout tiles = Ui.vbox(a);
        PpapHomeScreen.tiles(a, tiles, t);
        add(tiles, 2);

        // ---- details
        LinearLayout head = Ui.card(a);
        head.addView(Ui.pair(a, "Part", Lookups.join(EcnData.s(ecn, "part_number"), EcnData.s(ecn, "part_name"))));
        head.addView(Ui.pair(a, "Plant", EcnData.s(ecn, "plant_code")));
        head.addView(Ui.pair(a, "Priority", EcnData.s(ecn, "requested_priority")));
        head.addView(Ui.pair(a, "Response By", Ui.date(EcnData.s(ecn, "response_by")) + (EcnData.s(ecn, "response_by_party").isEmpty() ? "" : " · " + EcnData.s(ecn, "response_by_party"))));
        head.addView(Ui.pair(a, "Previous Description", EcnData.s(ecn, "previous_description")));
        head.addView(Ui.pair(a, "Revision Requested", EcnData.s(ecn, "revision_requested")));
        if (!EcnData.s(ecn, "fsi_approval_date").isEmpty()) head.addView(Ui.pair(a, "FSI Approval", emp(EcnData.s(ecn, "fsi_approver_employee_id")) + " · " + Ui.date(EcnData.s(ecn, "fsi_approval_date"))));
        if (!EcnData.s(ecn, "completed_date").isEmpty()) head.addView(Ui.pair(a, "Completed", emp(EcnData.s(ecn, "completed_by_employee_id")) + " · " + Ui.date(EcnData.s(ecn, "completed_date"))));
        if (!EcnData.s(ecn, "comments").isEmpty()) head.addView(Ui.pair(a, "Comments", EcnData.s(ecn, "comments")));
        add(head, 10);

        // ---- revision files
        if (prevFile != null || newFile != null) {
            LinearLayout box = Ui.vbox(a);
            if (prevFile != null) box.addView(fileButton("Previous Revision (Rev " + dash(EcnData.s(prevFile, "revision")) + ")", prevFile), Ui.matchWrap(a, 0));
            if (newFile != null) box.addView(fileButton("New Revision (Rev " + dash(EcnData.s(newFile, "revision")) + ")", newFile), Ui.matchWrap(a, 6));
            add(box, 8);
        }

        // ---- transitions
        List<String[]> targets = EcnData.allowedTargets(st, writable(), perms[2]);
        if (!targets.isEmpty()) {
            add(Ui.label(a, "Status change"), 14);
            LinearLayout box = Ui.vbox(a);
            boolean first = true;
            for (String[] x : targets) {
                String target = x[0];
                boolean primary = target.equals("APPROVED") || target.equals("PENDING_APPROVAL") || target.equals("COMPLETED");
                Button b = primary ? Ui.primary(a, EcnData.transitionLabel(target)) : Ui.outline(a, EcnData.transitionLabel(target), Ui.TEAL);
                b.setOnClickListener(v -> transition(target));
                box.addView(b, Ui.matchWrap(a, first ? 0 : 6));
                first = false;
            }
            add(box, 2);
        } else if ("PENDING_APPROVAL".equals(st) && !perms[2]) {
            add(Ui.text(a, "Approve / disapprove requires Part Master approve permission.", 12, Ui.MUTED, false), 8);
        }

        // ---- edit / print
        LinearLayout acts = Ui.vbox(a);
        if (writable() && !st.equals("CANCELLED") && !st.equals("COMPLETED")) {
            Button edit = Ui.outline(a, "Edit ECN details", Ui.TEAL);
            edit.setOnClickListener(v -> a.push(new EcnFormScreen(a, null, ecn, null, null)));
            acts.addView(edit, Ui.matchWrap(a, 0));
        }
        Button print = Ui.outline(a, "Print / PDF (" + EcnData.FORMAT_NO + ") · view, download, e-mail, share", Ui.TEAL);
        print.setOnClickListener(v -> ExportKit.layoutMenu(a, () -> EcnData.pdf(api, id)));
        acts.addView(print, Ui.matchWrap(a, 6));
        if (!st.equals("CANCELLED")) {
            Button mail = Ui.outline(a, "✉ E-mail this ECN print to employees", Ui.TEAL);
            mail.setOnClickListener(v -> emailDialog());
            acts.addView(mail, Ui.matchWrap(a, 6));
        }
        add(acts, 12);

        // ---- implementation actions
        add(Ui.label(a, "Implementation actions (affected documents)"), 14);
        boolean locked = st.equals("COMPLETED") || st.equals("CANCELLED") || !writable();
        LinearLayout ab = Ui.card(a);
        if (actions.isEmpty()) ab.addView(Ui.text(a, "No implementation actions yet.", 12, Ui.MUTED, false));
        int i = 0;
        for (JSONObject r : actions) {
            if (i++ > 0) ab.addView(Ui.divider(a));
            LinearLayout line = Ui.vbox(a);
            line.setPadding(0, dp(6), 0, dp(6));
            LinearLayout top = Ui.hbox(a);
            top.addView(Ui.text(a, EcnData.s(r, "affected_document").isEmpty() ? "Action" : EcnData.s(r, "affected_document"), 13, Ui.TEXT, true), Ui.weight(1));
            top.addView(Ui.chip(a, Ui.pretty(EcnData.s(r, "status")), Ui.tone(EcnData.s(r, "status"))));
            line.addView(top);
            line.addView(Ui.text(a, EcnData.s(r, "action_text"), 12, Ui.TEXT, false));
            String resp = emp(EcnData.s(r, "responsible_employee_id"));
            line.addView(Ui.text(a, Lookups.join(resp.isEmpty() ? EcnData.s(r, "responsible_text") : resp, "Target " + Ui.date(EcnData.s(r, "target_date")),
                EcnData.s(r, "completed_date").isEmpty() ? "" : "Done " + Ui.date(EcnData.s(r, "completed_date"))), 11, Ui.MUTED, false));
            if (!locked) line.setOnClickListener(v -> a.push(new EcnActionScreen(a, ecn, r)));
            ab.addView(line);
        }
        if (!locked) {
            Button add = Ui.outline(a, "+ Add implementation action", Ui.TEAL);
            add.setOnClickListener(v -> a.push(new EcnActionScreen(a, ecn, null)));
            ab.addView(add, Ui.matchWrap(a, 8));
            List<JSONObject> suggested = EcnData.defaultActions(ecn);
            if (actions.isEmpty() && !suggested.isEmpty()) {
                Button sug = Ui.outline(a, "Add " + suggested.size() + " suggested action(s) from the supporting documents", Ui.TEAL);
                sug.setOnClickListener(v -> Api.async(() -> {
                    for (JSONObject x : suggested) api.insert(EcnData.ACTIONS, x.put("ecn_id", id));
                    return suggested.size();
                }, (n, err) -> { if (err != null) a.toast(Api.message(err)); else { a.toast(n + " action(s) added."); reload(); } }));
                ab.addView(sug, Ui.matchWrap(a, 6));
            }
        }
        add(ab, 2);

        // ---- supporting documents
        add(Ui.label(a, "Supporting documents attached"), 14);
        LinearLayout fb = Ui.card(a);
        if (files.length() == 0) fb.addView(Ui.text(a, "No supporting documents yet.", 12, Ui.MUTED, false));
        for (int k = 0; k < files.length(); k++) {
            JSONObject f = files.optJSONObject(k);
            if (k > 0) fb.addView(Ui.divider(a));
            LinearLayout line = Ui.hbox(a);
            line.setPadding(0, dp(8), 0, dp(8));
            LinearLayout text = Ui.vbox(a);
            text.addView(Ui.text(a, slotLabel(Lookups.j(f, "document_type")), 13, Ui.TEXT, true));
            text.addView(Ui.text(a, Lookups.j(f, "file_name") + " · " + Ui.date(Lookups.j(f, "created_at")), 11, Ui.MUTED, false));
            line.addView(text, Ui.weight(1));
            TextView open = Ui.text(a, "Open", 13, Ui.TEAL_DARK, true);
            open.setPadding(dp(10), dp(6), dp(4), dp(6));
            final String path = Lookups.j(f, "object_path");
            open.setOnClickListener(v -> Api.async(() -> Attachments.signedUrl(api, path), (url, e2) -> { if (e2 != null) a.toast(Api.message(e2)); else a.openInBrowser(url); }));
            line.addView(open);
            fb.addView(line);
        }
        if (writable() && !st.equals("CANCELLED")) {
            Button up = Ui.outline(a, "Add / replace supporting document", Ui.TEAL);
            up.setOnClickListener(v -> pickSlot());
            fb.addView(up, Ui.matchWrap(a, 10));
        }
        add(fb, 2);
    }

    private static String dash(String s) { return s == null || s.isEmpty() ? "-" : s; }

    static String slotLabel(String type) {
        for (String[] s : SLOTS) if (s[0].equalsIgnoreCase(type)) return s[1];
        return Ui.pretty(type);
    }

    private Button fileButton(String label, JSONObject f) {
        Button b = Ui.outline(a, "⇩ " + label + " · " + Lookups.j(f, "file_name"), Ui.TEAL);
        b.setOnClickListener(v -> Api.async(() -> Attachments.signedUrl(api, Lookups.j(f, "object_path")), (url, e) -> { if (e != null) a.toast(Api.message(e)); else a.openInBrowser(url); }));
        return b;
    }

    private void pickSlot() {
        String[] labels = new String[SLOTS.length];
        for (int i = 0; i < SLOTS.length; i++) labels[i] = SLOTS[i][1];
        new AlertDialog.Builder(a).setTitle("Document type").setItems(labels, (d, which) -> {
            String slot = SLOTS[which][0];
            a.pickFile(SLOTS[which][1], false, file -> {
                a.toast("Uploading " + file.name + "…");
                Api.async(() -> Attachments.uploadSlot(api, EcnData.ATTACHMENT_ENTITY, id, "part_ecns/" + id, slot, file, null, null), (path, err) -> {
                    if (err != null) { a.toast("Upload failed: " + Api.message(err)); return; }
                    a.toast("Uploaded.");
                    reload();
                });
            });
        }).setNegativeButton("Back", null).show();
    }

    /** app_pages/ecn.py "E-mail this ECN print to (employees)": recipients, subject, message, send. */
    private void emailDialog() {
        if (employees == null || employees.isEmpty()) { a.toast("No active employees in Employee Master."); return; }
        final String[] ids = employees.keySet().toArray(new String[0]);
        final String[] names = employees.values().toArray(new String[0]);
        final boolean[] on = new boolean[ids.length];
        JSONArray pre = ecn.optJSONArray("email_employee_ids");
        for (int i = 0; i < ids.length; i++) for (int k = 0; pre != null && k < pre.length(); k++) if (ids[i].equals(pre.optString(k))) on[i] = true;
        new AlertDialog.Builder(a).setTitle("E-mail " + EcnData.s(ecn, "ecn_number") + " to")
            .setMultiChoiceItems(names, on, (d, w, c) -> on[w] = c)
            .setNegativeButton("Back", null)
            .setPositiveButton("Next", (d, w) -> {
                List<String> chosen = new ArrayList<>();
                for (int i = 0; i < ids.length; i++) if (on[i]) chosen.add(ids[i]);
                if (chosen.isEmpty()) { a.toast("Select at least one employee."); return; }
                String[] t = EcnData.emailText(ecn);
                LinearLayout box = Ui.vbox(a);
                box.setPadding(dp(18), dp(6), dp(18), 0);
                android.widget.EditText sub = new android.widget.EditText(a);
                sub.setText(t[0]);
                android.widget.EditText body = new android.widget.EditText(a);
                body.setText(t[1]);
                body.setMinLines(5);
                box.addView(Ui.text(a, "Subject", 12, Ui.MUTED, true));
                box.addView(sub);
                box.addView(Ui.text(a, "Message", 12, Ui.MUTED, true));
                box.addView(body);
                new AlertDialog.Builder(a).setTitle("Send ECN e-mail").setView(box).setNegativeButton("Back", null)
                    .setPositiveButton("Send", (d2, w2) -> {
                        a.toast("Sending…");
                        String subject = sub.getText().toString(), message = body.getText().toString();
                        Api.async(() -> EcnData.email(api, ecn, chosen, subject, message), (msg, err) -> {
                            if (err != null) a.toast(Api.message(err)); else a.toast(msg);
                        });
                    }).show();
            }).show();
    }

    private void transition(String target) {
        String label = EcnData.transitionLabel(target);
        a.askText(label + " · " + EcnData.s(ecn, "ecn_number"), "Remarks for the status change (optional)", label, false, remarks ->
            Api.async(() -> EcnData.transition(api, ecn, target, remarks, writable(), perms[2]), (row, err) -> {
                if (err != null) { a.toast(Api.message(err)); return; }
                a.toast(EcnData.s(ecn, "ecn_number") + " is now " + EcnData.statusLabel(target) + ".");
                reload();
            }));
    }
}
