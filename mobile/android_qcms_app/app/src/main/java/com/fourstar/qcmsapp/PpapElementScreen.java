package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * R39 · One PPAP element (website ppap-package sections B + C for a single element): required / NA, status, due date,
 * responsible employee + department, completed date, remarks; document upload (camera / gallery / file like
 * Attachments) as a new revision, view, download, share, make current, archive and the full revision history.
 * A new responsible employee gets the in-app task + the assignment e-mail (never blocks the save).
 */
public final class PpapElementScreen extends Screen {
    private final JSONObject pkg;
    private JSONObject element;
    private List<JSONObject> versions = new ArrayList<>();
    private boolean[] perms = {true, false, false, false};
    private FormView form;
    private Button save;

    public PpapElementScreen(MainActivity a, JSONObject pkg, JSONObject element) { super(a); this.pkg = pkg; this.element = element; }

    @Override public String title() { return String.format(Locale.ROOT, "%02d %s", PpapData.num(element, "element_no"), PpapData.s(element, "element_name")); }
    @Override public String subtitle() { return "PPAP " + PpapData.s(pkg, "package_no"); }
    @Override public int tab() { return Catalog.MORE; }

    private String eid() { return PpapData.s(element, "id"); }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            boolean[] p = PpapData.permissions(api);
            List<JSONObject> r = PpapData.list(api.rows("ppap_package_elements?select=*&id=eq." + Api.enc(eid()) + "&limit=1"));
            List<JSONObject> v = PpapData.list(api.rows("ppap_element_documents?select=*&package_element_id=eq." + Api.enc(eid()) + "&status=eq.ACTIVE&order=uploaded_at.desc&limit=500"));
            Lookups.rows(api, Lookups.employees());
            return new Object[]{p, r.isEmpty() ? element : r.get(0), v};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            perms = (boolean[]) res[0];
            element = (JSONObject) res[1];
            versions = PpapPackageScreen.cast(res[2]);
            render();
        });
        return scroll;
    }

    private boolean canWrite() { return perms[1] || perms[2]; }

    private void render() {
        offlineNote();
        String state = PpapData.state(element, LocalDate.now());
        int[] c = PpapData.stateColors(state);
        LinearLayout head = Ui.card(a);
        head.addView(Ui.text(a, title(), 16, Ui.TEXT, true));
        TextView chip = Ui.text(a, PpapData.stateLabel(state), 11, c[0], true);
        chip.setBackground(Ui.round(c[1], 0, 0, 12, a));
        chip.setPadding(dp(8), dp(3), dp(8), dp(3));
        LinearLayout row = Ui.hbox(a);
        row.addView(chip);
        row.setPadding(0, dp(6), 0, 0);
        head.addView(row);
        head.addView(Ui.text(a, "Package " + PpapData.s(pkg, "package_no") + " · Part " + PpapData.s(pkg, "customer_part_no"), 12, Ui.MUTED, false));
        add(head, 2);

        // ---- element fields
        add(Ui.label(a, "Status, due date & responsible"), 12);
        List<Field> f = new ArrayList<>();
        f.add(Field.text("element_name", "Element").req());
        f.add(Field.bool("applicable", "Applicable (untick = NA, not applicable for this part)"));
        f.add(Field.select("status", "Status", PpapData.ELEMENT_STATUSES).labels(PpapData.statusLabels(PpapData.ELEMENT_STATUSES)).req());
        f.add(Field.date("due_date", "Due Date"));
        f.add(Field.lookup("responsible_employee_id", "Responsible", Lookups.employees()));
        Set<String> depts = new LinkedHashSet<>();
        Collections.addAll(depts, PpapData.DEPARTMENTS);
        if (!PpapData.s(element, "responsible_department").isEmpty()) depts.add(PpapData.s(element, "responsible_department"));
        f.add(Field.select("responsible_department", "Department", depts.toArray(new String[0])));
        f.add(Field.date("completed_date", "Completed Date").hint("Set automatically to today when the status is Completed"));
        f.add(Field.area("remarks", "Remarks"));
        form = new FormView(a, f);
        form.setAll(element);
        String st = PpapData.s(element, "status").isEmpty() ? "NOT_STARTED" : PpapData.s(element, "status");
        form.set("status", st);
        form.set("applicable", !"NA".equalsIgnoreCase(st));
        if (PpapData.s(element, "responsible_department").isEmpty()) form.set("responsible_department", PpapData.defaultDepartment(PpapData.num(element, "element_no")));
        form.onChange((k, v) -> {
            if ("applicable".equals(k)) {
                boolean on = form.bool("applicable");
                if (!on) form.set("status", "NA");
                else if ("NA".equals(form.str("status"))) form.set("status", "NOT_STARTED");
            }
            if ("status".equals(k)) form.set("applicable", !"NA".equals(form.str("status")));
        });
        add(form, 0);
        if (perms[2]) {
            save = Ui.primary(a, "Save element");
            save.setOnClickListener(v -> saveElement());
            add(save, 10);
        } else {
            add(Ui.text(a, "PPAP edit permission is required to change the element.", 12, Ui.MUTED, false), 8);
        }
        if (canWrite() && !PpapData.s(element, "responsible_employee_id").isEmpty()) {
            Button again = Ui.outline(a, "✉ Send assignment e-mail again", Ui.TEAL);
            again.setOnClickListener(v -> {
                a.toast("Sending the assignment e-mail…");
                List<String> ids = new ArrayList<>();
                ids.add(eid());
                Api.async(() -> PpapData.assignmentMail(api, PpapData.s(pkg, "id"), ids, true), (msg, err) -> a.toast(err != null ? Api.message(err) : msg));
            });
            add(again, 8);
        }

        // ---- documents
        add(Ui.label(a, "Documents · revision history"), 16);
        add(Ui.text(a, "Each upload is kept as a revision; the newest is the current document used in the package. Tap a file to view, download, share or make it current.",
            11.5f, Ui.MUTED, false), 2);
        if (versions.isEmpty()) add(Ui.empty(a, "No document uploaded for this element yet."), 2);
        for (JSONObject d : versions) add(docRow(d), 6);
        if (canWrite()) {
            JSONObject cur = null;
            for (JSONObject d : versions) if (d.optBoolean("is_latest", false)) cur = d;
            String nextRev = cur == null ? "A" : PpapData.nextRevision(PpapData.s(cur, "revision"));
            LinearLayout up = Ui.card(a);
            up.addView(Ui.text(a, "Upload / replace document", 14, Ui.TEXT, true));
            EditText rev = Ui.input(a, "Revision", false);
            rev.setText(nextRev);
            up.addView(Ui.label(a, "Revision"));
            up.addView(rev);
            EditText remarks = Ui.input(a, "Document remarks (optional)", false);
            up.addView(Ui.label(a, "Document remarks"));
            up.addView(remarks);
            Button pick = Ui.primary(a, "Upload document (camera or file)");
            pick.setOnClickListener(v -> a.pickFile("PPAP · " + PpapData.s(element, "element_name"), false, file -> {
                a.toast("Uploading " + file.name + " (" + (file.data.length / 1024) + " KB)…");
                String r = rev.getText().toString(), rm = remarks.getText().toString();
                Api.async(() -> PpapData.upload(api, pkg, element, file, r, rm), (saved, err) -> {
                    if (err != null) { a.toast("Upload failed: " + Api.message(err)); return; }
                    a.toast("Document uploaded to " + title() + " (Rev " + PpapData.s(saved, "revision") + ").");
                    reload();
                });
            }));
            up.addView(pick, Ui.matchWrap(a, 10));
            add(up, 10);
        }
    }

    private View docRow(JSONObject d) {
        LinearLayout card = Ui.vbox(a);
        boolean cur = d.optBoolean("is_latest", false);
        Ui.clickable(card, cur ? Ui.TEAL_SOFT : Ui.PANEL, Ui.LINE, 12);
        card.setPadding(dp(12), dp(9), dp(12), dp(9));
        LinearLayout top = Ui.hbox(a);
        top.addView(Ui.text(a, PpapData.s(d, "file_name"), 13, Ui.TEXT, true), Ui.weight(1));
        top.addView(Ui.chip(a, (cur ? "✓ Current · " : "") + "Rev " + PpapData.s(d, "revision"), cur ? "green" : "grey"));
        card.addView(top);
        card.addView(Ui.text(a, Lookups.join(Ui.num(d.optLong("size_bytes", 0) / 1024.0, 1) + " KB", PpapData.s(d, "uploaded_by_name"),
            Ui.date(PpapData.s(d, "uploaded_at")), PpapData.s(d, "remarks")), 11, Ui.MUTED, false));
        card.setOnClickListener(v -> docMenu(d));
        return card;
    }

    private void docMenu(JSONObject d) {
        List<String> items = new ArrayList<>();
        items.add("View");
        items.add("Download to the phone");
        items.add("Share (WhatsApp, Gmail…)");
        if (canWrite() && !d.optBoolean("is_latest", false)) items.add("Make this the current revision");
        if (perms[3]) items.add("Archive this file");
        new AlertDialog.Builder(a).setTitle(PpapData.s(d, "file_name")).setItems(items.toArray(new String[0]), (dlg, w) -> {
            String item = items.get(w);
            String path = PpapData.s(d, "object_path");
            String mime = PpapData.s(d, "mime_type").isEmpty() ? "application/octet-stream" : PpapData.s(d, "mime_type");
            String name = SndFiles.safeName(PpapData.s(d, "file_name"));
            if (item.startsWith("View")) {
                Api.async(() -> Attachments.signedUrl(api, path), (url, e) -> { if (e != null) a.toast(Api.message(e)); else a.openInBrowser(url); });
            } else if (item.startsWith("Download") || item.startsWith("Share")) {
                boolean share = item.startsWith("Share");
                Api.async(() -> SndFiles.saveToDownloads(a, name, api.download(path), mime), (saved, e) -> {
                    if (e != null || saved == null) { a.toast("Could not download: " + Api.message(e)); return; }
                    if (saved.uri == null) { a.toast("Saved: " + saved.where); return; }
                    if (share) SndFiles.share(a, saved.uri, mime, PpapData.s(d, "file_name"));
                    else new AlertDialog.Builder(a).setTitle("Saved").setMessage(saved.where)
                        .setPositiveButton("Open", (x, y) -> SndFiles.open(a, saved.uri, mime))
                        .setNeutralButton("Share", (x, y) -> SndFiles.share(a, saved.uri, mime, PpapData.s(d, "file_name")))
                        .setNegativeButton("Done", null).show();
                });
            } else if (item.startsWith("Make")) {
                Api.async(() -> { PpapData.setLatest(api, d); return true; }, (ok, e) -> { a.toast(e != null ? Api.message(e) : "Rev " + PpapData.s(d, "revision") + " is now the current document."); reload(); });
            } else {
                a.confirm("Archive " + PpapData.s(d, "file_name") + "?", "The file is kept in storage but no longer used in the package.", "Archive", () ->
                    Api.async(() -> { PpapData.archive(api, d); return true; }, (ok, e) -> { a.toast(e != null ? Api.message(e) : "File archived."); reload(); }));
            }
        }).setNegativeButton("Close", null).show();
    }

    private void saveElement() {
        String p = form.validate();
        if (p != null) { a.toast(p); return; }
        JSONObject values;
        try { values = form.json(); } catch (Exception e) { a.toast(Api.message(e)); return; }
        try {
            String status = PpapData.s(values, "status");
            if (!form.bool("applicable")) status = "NA";
            else if (status.equals("NA")) status = "NOT_STARTED";
            values.put("status", status);
            values.put("due_date", PpapData.nz(PpapPackageEditScreen.iso(PpapData.s(values, "due_date"))));
            values.put("completed_date", PpapData.nz(PpapPackageEditScreen.iso(PpapData.s(values, "completed_date"))));
            values.remove("applicable");
        } catch (Exception ignored) { }
        save.setEnabled(false);
        save.setText("Saving…");
        final JSONObject v = values;
        Api.async(() -> {
            JSONObject merged = new JSONObject(element.toString());
            for (java.util.Iterator<String> it = v.keys(); it.hasNext(); ) { String k = it.next(); merged.put(k, v.opt(k)); }
            boolean mail = PpapData.needsAssignmentMail(element, merged);   // R39: new / changed responsible or new due date
            boolean assigned = PpapData.saveElement(api, element, v);
            if (assigned) PpapData.notifyAssignment(api, pkg, merged, PpapData.s(v, "responsible_employee_id"));
            if (!mail) return "PPAP element saved.";
            List<String> ids = new ArrayList<>();
            ids.add(eid());
            return "PPAP element saved. " + PpapData.assignmentMail(api, PpapData.s(pkg, "id"), ids, false);
        }, (msg, err) -> {
            save.setEnabled(true);
            save.setText("Save element");
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast(msg);
            a.back();
        });
    }
}
