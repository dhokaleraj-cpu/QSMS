package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/**
 * R39 · ECN / PCN register (website route ecn-register, app_pages/ecn.py render_ecn_register_panel + report_register
 * filters): every part_ecns row of the tenant (or of one Part when opened from Part Master), filters Status / Type /
 * Part / Date from-to / free text, KPI counts, open a note (EcnScreen), raise a new ECN / PCN without a drawing
 * replacement (document scope GENERAL), data export (PDF / Excel).
 */
public final class EcnRegisterScreen extends Screen {
    static final String ALL = "ALL";
    private final String partId;
    private JSONObject part;
    private List<JSONObject> rows = new ArrayList<>();
    private FormView filters;
    private LinearLayout listBox;
    private boolean[] perms = {false, false, false};

    /** partId = null for the whole register, else the ECN / PCN of one Part. */
    public EcnRegisterScreen(MainActivity a, String partId) { super(a); this.partId = partId; }

    @Override public String title() { return "ECN / PCN Register"; }
    @Override public String subtitle() {
        return part != null ? "Part " + EcnData.s(part, "part_number") + " · " + EcnData.FORMAT_NO : "Engineering / Process Change Notes · " + EcnData.FORMAT_NO;
    }
    @Override public int tab() { return Catalog.MASTERS; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            boolean[] p = EcnData.permissions(api);
            String filter = partId == null || partId.isEmpty() ? "" : "&part_id=eq." + Api.enc(partId);
            JSONArray r = api.rows(EcnData.TABLE + "?select=*" + filter + "&order=ecn_date.desc,ecn_number.desc&limit=3000");
            JSONObject pr = null;
            if (partId != null && !partId.isEmpty()) {
                JSONArray x = api.rows("parts?select=id,part_number,part_name,drawing_number,drawing_revision&id=eq." + Api.enc(partId) + "&limit=1");
                if (x.length() > 0) pr = x.getJSONObject(0);
            }
            return new Object[]{p, r, pr};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            perms = (boolean[]) res[0];
            rows = EcnData.list((JSONArray) res[1]);
            part = (JSONObject) res[2];
            a.rebuildTitle(this);
            render();
        });
        return scroll;
    }

    private boolean writable() { return perms[0] || perms[1]; }

    private void render() {
        offlineNote();
        // ---- KPI counts
        int open = 0, pending = 0, approved = 0, done = 0;
        for (JSONObject r : rows) {
            String st = EcnData.status(r);
            if (st.equals("DRAFT") || st.equals("DISAPPROVED")) open++;
            else if (st.equals("PENDING_APPROVAL")) pending++;
            else if (st.equals("APPROVED")) approved++;
            else if (st.equals("COMPLETED")) done++;
        }
        List<LinearLayout> t = new ArrayList<>();
        t.add(PpapHomeScreen.tile(a, "Draft / Disapproved", String.valueOf(open), rows.size() + " note(s) in the register", 0xFF0B6E70, 0xFFE3F2F2));
        t.add(PpapHomeScreen.tile(a, "Pending Approval", String.valueOf(pending), "Part Master approve permission", 0xFF2563EB, 0xFFEFF6FF));
        t.add(PpapHomeScreen.tile(a, "Approved", String.valueOf(approved), "Implementation in progress", 0xFF7C3AED, 0xFFF5F3FF));
        t.add(PpapHomeScreen.tile(a, "Completed", String.valueOf(done), "All actions closed", 0xFF166534, 0xFFF0FDF4));
        LinearLayout tiles = Ui.vbox(a);
        PpapHomeScreen.tiles(a, tiles, t);
        add(tiles, 2);

        // ---- new note
        if (writable()) {
            Button nw = Ui.primary(a, "+ Raise a new ECN / PCN (without a drawing replacement)");
            nw.setOnClickListener(v -> raiseNew());
            add(nw, 10);
        }

        // ---- filters
        add(Ui.label(a, "Filters"), 12);
        String[] statuses = new String[EcnData.STATUSES.length + 1];
        statuses[0] = ALL;
        System.arraycopy(EcnData.STATUSES, 0, statuses, 1, EcnData.STATUSES.length);
        String[] statusLabels = new String[statuses.length];
        statusLabels[0] = "All statuses";
        for (int i = 1; i < statuses.length; i++) statusLabels[i] = EcnData.statusLabel(statuses[i]);
        List<Field> f = new ArrayList<>();
        f.add(Field.select("status", "Status", statuses).labels(statusLabels).def(ALL));
        f.add(Field.select("change_type", "Type", ALL, "ECN", "PCN").labels("ECN + PCN", "ECN · Engineering Change Note", "PCN · Process Change Note").def(ALL));
        if (partId == null || partId.isEmpty()) f.add(Field.lookup("part_id", "Part", Lookups.parts()));
        f.add(Field.date("date_from", "Date from"));
        f.add(Field.date("date_to", "Date to"));
        f.add(Field.text("q", "Search").hint("ECN No., Part No., Drawing No., description"));
        filters = new FormView(a, f);
        filters.onChange((k, v) -> renderList());
        add(filters, 2);
        filters.set("status", ALL);
        filters.set("change_type", ALL);

        listBox = Ui.vbox(a);
        add(listBox, 10);
        renderList();

        Button export = Ui.outline(a, "⇩ Data export: PDF / Excel", Ui.TEAL_DARK);
        export.setOnClickListener(v -> ExportKit.showData(a, this, scroll));
        add(export, 14);
    }

    /** Rows matching the filters (report_register). */
    List<JSONObject> filtered() {
        String st = filters.str("status"), type = filters.str("change_type"), pid = filters.field("part_id") == null ? "" : filters.str("part_id");
        String from = EcnData.iso(filters.str("date_from")), to = EcnData.iso(filters.str("date_to"));
        String q = filters.str("q").trim().toLowerCase(Locale.ROOT);
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject r : rows) {
            if (!st.isEmpty() && !ALL.equals(st) && !EcnData.status(r).equals(st)) continue;
            if (!type.isEmpty() && !ALL.equals(type) && !type.equalsIgnoreCase(EcnData.s(r, "change_type"))) continue;
            if (!pid.isEmpty() && !pid.equals(EcnData.s(r, "part_id"))) continue;
            String d = EcnData.iso(EcnData.s(r, "ecn_date"));
            if (!from.isEmpty() && d.compareTo(from) < 0) continue;
            if (!to.isEmpty() && d.compareTo(to) > 0) continue;
            if (!q.isEmpty()) {
                String hay = (EcnData.s(r, "ecn_number") + " " + EcnData.s(r, "part_number") + " " + EcnData.s(r, "part_name") + " " + EcnData.s(r, "drawing_number")
                    + " " + EcnData.s(r, "revision_requested") + " " + EcnData.s(r, "previous_description") + " " + EcnData.s(r, "plant_code")).toLowerCase(Locale.ROOT);
                if (!hay.contains(q)) continue;
            }
            out.add(r);
        }
        return out;
    }

    private void renderList() {
        if (listBox == null) return;
        listBox.removeAllViews();
        List<JSONObject> list = filtered();
        listBox.addView(Ui.text(a, list.size() + " of " + rows.size() + " ECN / PCN", 12, Ui.MUTED, false));
        if (rows.isEmpty()) {
            listBox.addView(Ui.empty(a, "No Engineering / Process Change Notes yet. An ECN is requested automatically whenever a controlled drawing or a "
                + "process drawing / specification revision is replaced."), Ui.matchWrap(a, 6));
            return;
        }
        if (list.isEmpty()) { listBox.addView(Ui.empty(a, "No ECN matches the filters."), Ui.matchWrap(a, 6)); return; }
        List<List<String>> data = new ArrayList<>();
        for (JSONObject r : list) {
            data.add(Arrays.asList(EcnData.s(r, "ecn_number"), EcnData.s(r, "change_type"), Ui.date(EcnData.s(r, "ecn_date")), EcnData.s(r, "plant_code"),
                EcnData.s(r, "part_number"), EcnData.s(r, "part_name"), EcnData.scopeLabel(EcnData.s(r, "document_scope")), EcnData.s(r, "drawing_number"),
                EcnData.s(r, "previous_revision"), EcnData.s(r, "new_revision"), EcnData.s(r, "requested_priority"), Ui.date(EcnData.s(r, "response_by")),
                Ui.pretty(EcnData.s(r, "customer_approval")), EcnData.statusLabel(EcnData.status(r)), EcnData.s(r, "document_attachment_id").isEmpty() ? "No" : "Yes"));
        }
        listBox.addView(new DataGrid(a, "ECN / PCN Register (tap a row to open)", Arrays.asList("ECN No.", "Type", "Date", "Plant", "Part No.", "Part Name", "Document",
            "Drawing No.", "Rev From", "Rev To", "Priority", "Response By", "Customer Approval", "Status", "Revision Linked"), data, 420,
            index -> a.push(new EcnScreen(a, EcnData.s(list.get(index), "id")))), Ui.matchWrap(a, 6));
    }

    /** "Raise a new ECN / PCN (without a drawing replacement)": document scope GENERAL, Part from the screen or the Part filter. */
    private void raiseNew() {
        String pid = partId != null && !partId.isEmpty() ? partId : (filters != null && filters.field("part_id") != null ? filters.str("part_id") : "");
        if (pid.isEmpty()) { a.toast("Select the Part in the Part filter first."); return; }
        Api.async(() -> {
            JSONArray x = api.rows("parts?select=id,part_number,part_name,drawing_number,drawing_revision&id=eq." + Api.enc(pid) + "&limit=1");
            if (x.length() == 0) throw new Api.ApiException(404, "Part not found.");
            JSONObject p = x.getJSONObject(0);
            return new JSONObject().put("part_id", pid).put("part_number", EcnData.s(p, "part_number")).put("part_name", EcnData.s(p, "part_name"))
                .put("drawing_number", EcnData.s(p, "drawing_number")).put("previous_revision", EcnData.s(p, "drawing_revision"))
                .put("document_scope", "GENERAL").put("change_type", "ECN").put("customer_approval", "PENDING").put("drawing_change_mode", "AS_SUGGESTED");
        }, (d, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            a.push(new EcnFormScreen(a, d, null, null, null));
        });
    }
}
