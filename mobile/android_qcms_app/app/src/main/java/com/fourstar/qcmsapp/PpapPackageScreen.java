package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * R39 · One PPAP package (website route ppap-package): header, KPIs (progress, overdue, due ≤ 3 days, documents, PSW,
 * APQP link), element list with required / NA, responsible, due date, status and remarks (overdue highlighted), bulk
 * assignment, per-element files (PpapElementScreen), ZIP of all / selected current documents built on the phone in the
 * website's "NN Element name/" folders, status notes, customer submissions and the assignment e-mail again.
 * Sending the package to the customer: PpapSend (same rules as the website - own customer only, 10 MB / 18 files, 7-day ZIP link).
 */
public final class PpapPackageScreen extends Screen {
    private final String id;
    private JSONObject pkg;
    private List<JSONObject> elements = new ArrayList<>();
    private List<JSONObject> docs = new ArrayList<>();
    private List<JSONObject> notes = new ArrayList<>();
    private List<JSONObject> submissions = new ArrayList<>();
    private final Map<String, String> employees = new HashMap<>();
    private JSONObject apqp;
    private String customer = "", part = "";
    private boolean[] perms = {true, false, false, false};

    public PpapPackageScreen(MainActivity a, String id) { super(a); this.id = id; }

    @Override public String title() { return pkg == null ? "PPAP package" : PpapData.s(pkg, "package_no"); }
    @Override public String subtitle() { return "PPAP Document Manager · package"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            boolean[] p = PpapData.permissions(api);
            JSONObject row = PpapData.pkg(api, id);
            List<JSONObject> els = PpapData.elements(api, id);
            List<JSONObject> ds = PpapData.documents(api, id);
            List<JSONObject> ns = PpapData.list(api.rows("ppap_status_notes?select=*&package_id=eq." + Api.enc(id) + "&order=created_at.desc&limit=500"));
            List<JSONObject> subs = PpapData.list(api.rows("ppap_customer_submissions?select=*&package_id=eq." + Api.enc(id) + "&order=submitted_at.desc&limit=200"));
            Map<String, String> emp = new HashMap<>();
            for (JSONObject e : PpapData.list(Lookups.rows(api, Lookups.employees()))) emp.put(PpapData.s(e, "id"), Lookups.EMPLOYEE.of(e));
            JSONObject project = null;
            if (!PpapData.s(row, "apqp_project_id").isEmpty()) {
                List<JSONObject> r = PpapData.list(api.rows("ppap_projects?select=*&id=eq." + Api.enc(PpapData.s(row, "apqp_project_id")) + "&limit=1"));
                project = r.isEmpty() ? null : r.get(0);
            }
            String cust = "", prt = "";
            if (!PpapData.s(row, "customer_id").isEmpty()) {
                List<JSONObject> r = PpapData.list(api.rows("parties?select=id,party_code,party_name,city&id=eq." + Api.enc(PpapData.s(row, "customer_id")) + "&limit=1"));
                if (!r.isEmpty()) cust = Lookups.PARTY.of(r.get(0));
            }
            if (!PpapData.s(row, "part_id").isEmpty()) {
                List<JSONObject> r = PpapData.list(api.rows("parts?select=id,part_number,fsi_part_number,part_name&id=eq." + Api.enc(PpapData.s(row, "part_id")) + "&limit=1"));
                if (!r.isEmpty()) prt = Lookups.PART.of(r.get(0));
            }
            return new Object[]{p, row, els, ds, ns, subs, emp, project, cust, prt};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            perms = (boolean[]) res[0];
            pkg = (JSONObject) res[1];
            elements = cast(res[2]);
            docs = cast(res[3]);
            notes = cast(res[4]);
            submissions = cast(res[5]);
            employees.clear();
            @SuppressWarnings("unchecked") Map<String, String> emp = (Map<String, String>) res[6];
            employees.putAll(emp);
            apqp = (JSONObject) res[7];
            customer = (String) res[8];
            part = (String) res[9];
            a.rebuildTitle(this);
            render();
        });
        return scroll;
    }

    @SuppressWarnings("unchecked")
    static List<JSONObject> cast(Object o) { return (List<JSONObject>) o; }

    private boolean canWrite() { return perms[1] || perms[2]; }

    private List<JSONObject> docsOf(String elementId) {
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject d : docs) if (elementId.equals(PpapData.s(d, "package_element_id"))) out.add(d);
        return out;
    }

    private List<JSONObject> latest() {
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject d : docs) if (d.optBoolean("is_latest", false)) out.add(d);
        return out;
    }

    private void render() {
        offlineNote();
        LocalDate today = LocalDate.now();
        // ---- header
        LinearLayout head = Ui.card(a);
        LinearLayout top = Ui.hbox(a);
        top.addView(Ui.text(a, PpapData.s(pkg, "package_no"), 17, Ui.TEXT, true), Ui.weight(1));
        String st = PpapData.s(pkg, "status");
        top.addView(Ui.chip(a, Ui.pretty(st.isEmpty() ? "IN_PROGRESS" : st), Ui.tone(st)));
        head.addView(top);
        head.addView(Ui.pair(a, "Customer PPAP No.", PpapData.s(pkg, "customer_ppap_no")));
        head.addView(Ui.pair(a, "Customer Part No.", PpapData.s(pkg, "customer_part_no")));
        head.addView(Ui.pair(a, "Part (Part Master)", part));
        head.addView(Ui.pair(a, "Customer", customer));
        head.addView(Ui.pair(a, "Submission Level", "Level " + (PpapData.s(pkg, "submission_level").isEmpty() ? "3" : PpapData.s(pkg, "submission_level"))));
        head.addView(Ui.pair(a, "PSW Status", Ui.pretty(PpapData.s(pkg, "psw_status"))));
        head.addView(Ui.pair(a, "Customer Due Date", Ui.date(PpapData.s(pkg, "customer_due_date"))));
        head.addView(Ui.pair(a, "Interim Submit / Approved", Ui.date(PpapData.s(pkg, "interim_submit_date")) + " / " + Ui.date(PpapData.s(pkg, "interim_approved_date"))));
        head.addView(Ui.pair(a, "Full Submit / Approval", Ui.date(PpapData.s(pkg, "full_submit_date")) + " / " + Ui.date(PpapData.s(pkg, "approval_date"))));
        head.addView(Ui.pair(a, "PPAP Owner", employees.containsKey(PpapData.s(pkg, "owner_employee_id")) ? employees.get(PpapData.s(pkg, "owner_employee_id")) : ""));
        head.addView(Ui.pair(a, "Customer Contact", PpapData.s(pkg, "customer_contact_email")));
        if (!PpapData.s(pkg, "remarks").isEmpty()) head.addView(Ui.pair(a, "Remarks", PpapData.s(pkg, "remarks")));
        add(head, 2);

        // ---- KPIs
        double[] pr = PpapData.progress(elements);
        int overdue = 0, dueSoon = 0;
        for (JSONObject e : elements) {
            String s = PpapData.state(e, today);
            if (s.equals("overdue")) overdue++;
            if (s.equals("due_soon")) dueSoon++;
        }
        List<LinearLayout> t = new ArrayList<>();
        t.add(PpapHomeScreen.tile(a, "Progress", Ui.num(pr[4], 0) + "%", (int) pr[3] + "/" + (int) pr[2] + " applicable · " + (int) pr[1] + " NA", 0xFF15803D, 0xFFF0FDF4));
        t.add(PpapHomeScreen.tile(a, "Overdue", String.valueOf(overdue), "Elements past due date", 0xFFB91C1C, 0xFFFEF2F2));
        t.add(PpapHomeScreen.tile(a, "Due ≤ 3 days", String.valueOf(dueSoon), "Daily e-mail goes to the responsible", 0xFFD97706, 0xFFFFF7ED));
        t.add(PpapHomeScreen.tile(a, "Documents", String.valueOf(latest().size()), docs.size() + " file version(s)", 0xFF1469A8, 0xFFEFF6FF));
        t.add(PpapHomeScreen.tile(a, "PSW Status", Ui.pretty(PpapData.s(pkg, "psw_status")), "Level " + PpapData.s(pkg, "submission_level"), 0xFF0F766E, 0xFFF0FDFA));
        t.add(PpapHomeScreen.tile(a, "APQP Project", apqp == null ? "Not linked" : PpapData.s(apqp, "project_code"), "Customer due " + Ui.date(PpapData.s(pkg, "customer_due_date")), 0xFF6D28D9, 0xFFF5F3FF));
        LinearLayout box = Ui.vbox(a);
        PpapHomeScreen.tiles(a, box, t);
        add(box, 10);

        // ---- actions
        LinearLayout actions = Ui.vbox(a);
        if (perms[2]) actions.addView(button("Edit package header", true, v -> a.push(new PpapPackageEditScreen(a, id, null))), Ui.matchWrap(a, 0));
        if (apqp != null) actions.addView(button("Open linked APQP project " + PpapData.s(apqp, "project_code"), false, v -> {
            Module m = Catalog.get("apqp_projects");
            if (m != null) a.push(new RecordScreen(a, m, PpapData.s(apqp, "id")));
        }), Ui.matchWrap(a, 8));
        actions.addView(button("⇩ Download all current documents (ZIP)", false, v -> download(latest())), Ui.matchWrap(a, 8));
        actions.addView(button("⇩ Download selected documents (ZIP)", false, v -> chooseDownload()), Ui.matchWrap(a, 8));
        if (perms[2]) actions.addView(button("Assign several elements at once", false, v -> bulkAssign()), Ui.matchWrap(a, 8));
        if (canWrite()) actions.addView(button("✉ Send assignment e-mail again", false, v -> resendMail(null)), Ui.matchWrap(a, 8));
        if (canWrite()) actions.addView(button("✉ Send PPAP package to the customer", false, v -> PpapSend.dialog(a, api, pkg, latest(), elements, this::reload)), Ui.matchWrap(a, 8));
        add(actions, 10);

        // ---- elements
        add(Ui.label(a, "PPAP elements · status, due date & responsible"), 14);
        add(legend(), 2);
        if (elements.isEmpty()) add(Ui.empty(a, "No elements in this package."), 2);
        for (JSONObject e : elements) add(elementCard(e, today), 6);

        // ---- notes
        add(Ui.label(a, "Status notes"), 14);
        LinearLayout nb = Ui.card(a);
        if (notes.isEmpty()) nb.addView(Ui.text(a, "No status notes yet.", 12, Ui.MUTED, false));
        for (JSONObject n : notes) {
            nb.addView(Ui.text(a, Ui.date(PpapData.s(n, "note_date")) + " · " + (PpapData.s(n, "author_name").isEmpty() ? "-" : PpapData.s(n, "author_name"))
                + " · " + Ui.pretty(PpapData.s(n, "source")), 11, Ui.MUTED, true));
            TextView body = Ui.text(a, PpapData.s(n, "note"), 13, Ui.TEXT, false);
            body.setPadding(0, 0, 0, dp(6));
            nb.addView(body);
        }
        if (canWrite()) {
            Button add = Ui.outline(a, "+ Add status note", Ui.TEAL);
            add.setOnClickListener(v -> a.askText("Status note", "e.g. PFMEA sent to customer for review", "Save", true, text ->
                Api.async(() -> api.insert("ppap_status_notes", new JSONObject().put("package_id", id).put("note", text.trim())
                        .put("author_name", PpapData.nz(api.fullName == null || api.fullName.isEmpty() ? api.email : api.fullName))
                        .put("note_date", LocalDate.now().toString()).put("source", "MANUAL")),
                    (r, err) -> { if (err != null) a.toast(Api.message(err)); else { a.toast("Status note saved."); reload(); } })));
            nb.addView(add, Ui.matchWrap(a, 8));
        }
        add(nb, 2);

        // ---- submissions
        add(Ui.label(a, "Customer submissions / downloads"), 14);
        if (submissions.isEmpty()) add(Ui.empty(a, "Nothing sent to the customer yet."), 2);
        else {
            List<List<String>> rows = new ArrayList<>();
            for (JSONObject s : submissions) rows.add(java.util.Arrays.asList(Ui.date(PpapData.s(s, "submitted_at")), PpapData.s(s, "sent_to"),
                Ui.pretty(PpapData.s(s, "method")), PpapData.s(s, "document_count"), Ui.pretty(PpapData.s(s, "status")), PpapData.s(s, "sent_by_name")));
            add(new DataGrid(a, "Customer submissions", java.util.Arrays.asList("Date", "Sent to", "Method", "Documents", "Status", "By"), rows, 260, null), 2);
        }
    }

    private Button button(String label, boolean primary, View.OnClickListener l) {
        Button b = primary ? Ui.primary(a, label) : Ui.outline(a, label, Ui.TEAL);
        b.setOnClickListener(l);
        return b;
    }

    private View legend() {
        android.widget.HorizontalScrollView hs = new android.widget.HorizontalScrollView(a);
        hs.setHorizontalScrollBarEnabled(false);
        LinearLayout row = Ui.hbox(a);
        for (String s : new String[]{"completed", "na", "overdue", "due_soon", "submitted", "rejected", "open", "not_planned"}) {
            int[] c = PpapData.stateColors(s);
            TextView chip = Ui.text(a, PpapData.stateLabel(s), 10, c[0], true);
            chip.setBackground(Ui.round(c[1], 0, 0, 6, a));
            chip.setPadding(dp(6), dp(2), dp(6), dp(2));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
            lp.rightMargin = dp(4);
            row.addView(chip, lp);
        }
        hs.addView(row);
        return hs;
    }

    private View elementCard(JSONObject e, LocalDate today) {
        String state = PpapData.state(e, today);
        int[] c = PpapData.stateColors(state);
        LinearLayout card = Ui.vbox(a);
        Ui.clickable(card, state.equals("overdue") ? 0xFFFFF5F5 : Ui.PANEL, state.equals("overdue") ? 0xFFFCA5A5 : Ui.LINE, 12);
        card.setPadding(dp(12), dp(9), dp(12), dp(9));
        LinearLayout top = Ui.hbox(a);
        top.addView(Ui.text(a, String.format(Locale.ROOT, "%02d · %s", PpapData.num(e, "element_no"), PpapData.s(e, "element_name")), 13.5f, Ui.TEXT, true), Ui.weight(1));
        TextView chip = Ui.text(a, PpapData.statusLabel(PpapData.s(e, "status")) + (state.equals("overdue") ? " · Overdue" : state.equals("due_soon") ? " · Due soon" : ""), 10.5f, c[0], true);
        chip.setBackground(Ui.round(c[1], 0, 0, 12, a));
        chip.setPadding(dp(8), dp(3), dp(8), dp(3));
        top.addView(chip);
        card.addView(top);
        String resp = employees.containsKey(PpapData.s(e, "responsible_employee_id")) ? employees.get(PpapData.s(e, "responsible_employee_id")) : "Not assigned";
        int files = docsOf(PpapData.s(e, "id")).size();
        card.addView(Ui.text(a, Lookups.join("Due " + Ui.date(PpapData.s(e, "due_date")), resp, PpapData.s(e, "responsible_department"),
            files + " file(s)", "NA".equalsIgnoreCase(PpapData.s(e, "status")) ? "Not applicable" : "Required"), 11.5f, state.equals("overdue") ? Ui.RED_FG : Ui.MUTED, false));
        if (!PpapData.s(e, "remarks").isEmpty()) card.addView(Ui.text(a, PpapData.s(e, "remarks"), 11.5f, Ui.TEXT, false));
        card.setOnClickListener(v -> a.push(new PpapElementScreen(a, pkg, e)));
        return card;
    }

    // ------------------------------------------------------------------ ZIP
    private void chooseDownload() {
        List<JSONObject> cur = latest();
        if (cur.isEmpty()) { a.toast("No documents uploaded yet."); return; }
        Map<String, JSONObject> byId = new HashMap<>();
        for (JSONObject e : elements) byId.put(PpapData.s(e, "id"), e);
        String[] labels = new String[cur.size()];
        boolean[] checked = new boolean[cur.size()];
        for (int i = 0; i < cur.size(); i++) {
            JSONObject d = cur.get(i);
            JSONObject e = byId.get(PpapData.s(d, "package_element_id"));
            labels[i] = String.format(Locale.ROOT, "%02d %s · %s (Rev %s)", e == null ? 0 : PpapData.num(e, "element_no"), e == null ? "" : PpapData.s(e, "element_name"),
                PpapData.s(d, "file_name"), PpapData.s(d, "revision"));
        }
        new AlertDialog.Builder(a).setTitle("Documents for the ZIP").setMultiChoiceItems(labels, checked, (dlg, w, on) -> checked[w] = on)
            .setPositiveButton("Download ZIP", (dlg, w) -> {
                List<JSONObject> chosen = new ArrayList<>();
                for (int i = 0; i < cur.size(); i++) if (checked[i]) chosen.add(cur.get(i));
                if (chosen.isEmpty()) a.toast("Select at least one document.");
                else download(chosen);
            }).setNegativeButton("Back", null).show();
    }

    private void download(List<JSONObject> chosen) {
        if (chosen.isEmpty()) { a.toast("No documents uploaded yet."); return; }
        a.toast("Building the PPAP ZIP on the phone (" + chosen.size() + " document(s))…");
        String stamp = new SimpleDateFormat("yyyyMMdd_HHmm", Locale.ENGLISH).format(new Date());
        String name = SndFiles.safeName("PPAP_" + PpapData.safeName(PpapData.s(pkg, "package_no"), false) + "_" + stamp + ".zip");
        Api.async(() -> {
            byte[] zip = PpapData.zip(api, chosen, elements);
            PpapData.logDownload(api, pkg, chosen, elements);
            return SndFiles.saveToDownloads(a, name, zip, "application/zip");
        }, (saved, err) -> {
            if (err != null || saved == null) { a.toast("Could not build the ZIP: " + Api.message(err)); return; }
            if (saved.uri == null) { a.toast("Saved: " + saved.where); return; }
            new AlertDialog.Builder(a).setTitle("PPAP ZIP saved").setMessage(saved.where + "\n\nFolders: NN Element name / file (same as the website).")
                .setPositiveButton("Share", (x, y) -> SndFiles.share(a, saved.uri, "application/zip", "PPAP " + PpapData.s(pkg, "package_no")))
                .setNeutralButton("Open", (x, y) -> SndFiles.open(a, saved.uri, "application/zip"))
                .setNegativeButton("Done", null).show();
        });
    }

    // ------------------------------------------------------------------ assignments
    private void resendMail(List<String> elementIds) {
        a.toast("Sending the assignment e-mail…");
        Api.async(() -> PpapData.assignmentMail(api, id, elementIds, true), (msg, err) -> a.toast(err != null ? Api.message(err) : msg));
    }

    private void bulkAssign() {
        if (elements.isEmpty()) return;
        String[] labels = new String[elements.size()];
        boolean[] checked = new boolean[elements.size()];
        for (int i = 0; i < elements.size(); i++) {
            JSONObject e = elements.get(i);
            labels[i] = String.format(Locale.ROOT, "%02d · %s · %s", PpapData.num(e, "element_no"), PpapData.s(e, "element_name"), PpapData.statusLabel(PpapData.s(e, "status")));
        }
        new AlertDialog.Builder(a).setTitle("Elements").setMultiChoiceItems(labels, checked, (d, w, on) -> checked[w] = on)
            .setPositiveButton("Next", (d, w) -> {
                List<JSONObject> chosen = new ArrayList<>();
                for (int i = 0; i < elements.size(); i++) if (checked[i]) chosen.add(elements.get(i));
                if (chosen.isEmpty()) { a.toast("Select at least one element."); return; }
                bulkForm(chosen);
            }).setNegativeButton("Back", null).show();
    }

    private void bulkForm(List<JSONObject> chosen) {
        List<Field> f = new ArrayList<>();
        f.add(Field.lookup("responsible_employee_id", "Responsible (blank = keep)", Lookups.employees()));
        f.add(Field.date("due_date", "Due date (blank = keep)"));
        String[] codes = new String[PpapData.ELEMENT_STATUSES.length + 1];
        String[] names = new String[codes.length];
        codes[0] = "";
        names[0] = "— Keep —";
        for (int i = 0; i < PpapData.ELEMENT_STATUSES.length; i++) { codes[i + 1] = PpapData.ELEMENT_STATUSES[i]; names[i + 1] = PpapData.statusLabel(PpapData.ELEMENT_STATUSES[i]); }
        f.add(Field.select("status", "Status", codes).labels(names));
        FormView form = new FormView(a, f);
        ScrollView sv = new ScrollView(a);
        LinearLayout pad = Ui.vbox(a);
        pad.setPadding(dp(18), dp(4), dp(18), dp(8));
        pad.addView(form);
        sv.addView(pad);
        new AlertDialog.Builder(a).setTitle(chosen.size() + " element(s)").setView(sv)
            .setPositiveButton("Apply", (d, w) -> {
                String resp = form.str("responsible_employee_id"), due = form.str("due_date"), status = form.str("status");
                a.toast("Saving…");
                Api.async(() -> {
                    List<String> assigned = new ArrayList<>();
                    for (JSONObject e : chosen) {
                        JSONObject values = new JSONObject(e.toString());
                        if (!resp.isEmpty()) values.put("responsible_employee_id", resp);
                        if (!due.isEmpty()) values.put("due_date", PpapPackageEditScreen.iso(due));
                        if (!status.isEmpty()) values.put("status", status);
                        boolean mail = PpapData.needsAssignmentMail(e, values);   // R39: same rule as the website
                        if (PpapData.saveElement(api, e, values)) PpapData.notifyAssignment(api, pkg, values, PpapData.s(values, "responsible_employee_id"));
                        if (mail) assigned.add(PpapData.s(e, "id"));
                    }
                    String mail = assigned.isEmpty() ? "" : " " + PpapData.assignmentMail(api, id, assigned, false);
                    return chosen.size() + " element(s) updated." + mail;
                }, (msg, err) -> { a.toast(err != null ? Api.message(err) : msg); reload(); });
            }).setNegativeButton("Back", null).show();
    }
}
