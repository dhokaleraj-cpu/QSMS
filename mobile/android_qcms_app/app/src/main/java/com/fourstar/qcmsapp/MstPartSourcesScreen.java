package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

/**
 * Part Master section E · Approved sources (part_supplier_links): one row per Supplier × Steel Mill pair
 * (no mill → steel_mill_id null). New pairs get source_code from qsms_next_master_code('approved_sources');
 * pairs no longer selected are set approved = false.
 */
public final class MstPartSourcesScreen extends Screen {
    private final JSONObject part;
    private final String partId;
    private JSONArray links = new JSONArray();
    private FormView form;
    private TextView problem;
    private Button save;

    public MstPartSourcesScreen(MainActivity a, JSONObject part) { super(a); this.part = part; this.partId = Lookups.j(part, "id"); }

    @Override public String title() { return "Approved sources"; }
    @Override public String subtitle() { return MstPartGrid.partLabel(part); }
    @Override public int tab() { return Catalog.MASTERS; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONArray sup = Lookups.rows(api, Lookups.suppliers());
            JSONArray mills = Lookups.rows(api, Lookups.steelMills());
            JSONArray l = api.rows("part_supplier_links?select=*&part_id=eq." + Api.enc(partId) + "&limit=2000");
            return new JSONArray[]{sup, mills, l};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            links = res[2];
            render(res[0], res[1]);
        });
        return scroll;
    }

    private static Field multi(String key, String label, JSONArray rows) {
        String[] ids = new String[rows.length()], names = new String[rows.length()];
        for (int i = 0; i < rows.length(); i++) { ids[i] = Lookups.j(rows.optJSONObject(i), "id"); names[i] = Lookups.PARTY.of(rows.optJSONObject(i)); }
        return Field.multi(key, label, ids).labels(names);
    }

    private static boolean approved(JSONObject r) { return r.isNull("approved") || r.optBoolean("approved", true); }

    /** Value shared by every approved link (else ""), to prefill the common fields. */
    private String common(String key) {
        String v = null;
        for (int i = 0; i < links.length(); i++) {
            JSONObject r = links.optJSONObject(i);
            if (!approved(r)) continue;
            String x = Lookups.j(r, key);
            if (v == null) v = x; else if (!v.equals(x)) return "";
        }
        return v == null ? "" : v;
    }

    private void render(JSONArray suppliers, JSONArray mills) {
        offlineNote();
        List<Field> fields = new ArrayList<>();
        fields.add(multi("suppliers", "Approved Suppliers", suppliers).req());
        fields.add(multi("mills", "Approved Steel Mills", mills));
        fields.add(Field.text("supplier_part_number", "Supplier Part Number"));
        fields.add(Field.text("approval_reference", "Approval Reference"));
        fields.add(Field.date("valid_from", "Valid From"));
        fields.add(Field.date("valid_to", "Valid To"));
        form = new FormView(a, fields);
        TreeSet<String> sup = new TreeSet<>(), mil = new TreeSet<>();
        for (int i = 0; i < links.length(); i++) {
            JSONObject r = links.optJSONObject(i);
            if (!approved(r)) continue;
            if (!Lookups.j(r, "supplier_id").isEmpty()) sup.add(Lookups.j(r, "supplier_id"));
            if (!Lookups.j(r, "steel_mill_id").isEmpty()) mil.add(Lookups.j(r, "steel_mill_id"));
        }
        form.set("suppliers", new JSONArray(sup));
        form.set("mills", new JSONArray(mil));
        form.set("supplier_part_number", common("supplier_part_number"));
        form.set("approval_reference", common("approval_reference"));
        String from = common("valid_from");
        form.set("valid_from", from.isEmpty() ? Ui.today() : from);
        String to = common("valid_to");
        if (!to.isEmpty()) form.set("valid_to", to);
        add(MstForm.noteCard(a, "Select multiple approved Suppliers and Steel Mills for this Part. Supplier Part Number, Approval Reference and validity "
            + "are written to every selected Supplier × Steel Mill pair."), 0);
        add(form, 8);
        problem = Ui.text(a, "", 13, Ui.RED_FG, false);
        problem.setVisibility(View.GONE);
        add(problem, 8);
        save = Ui.primary(a, "Save Approved Sources");
        add(save, 10);
        save.setOnClickListener(v -> save());

        add(Ui.label(a, "Current source links"), 14);
        List<List<String>> data = new ArrayList<>();
        for (int i = 0; i < links.length(); i++) {
            JSONObject r = links.optJSONObject(i);
            data.add(Arrays.asList(Lookups.j(r, "source_code"), Lookups.labelOf(Lookups.suppliers(), Lookups.j(r, "supplier_id")),
                Lookups.j(r, "steel_mill_id").isEmpty() ? "-" : Lookups.labelOf(Lookups.steelMills(), Lookups.j(r, "steel_mill_id")),
                Lookups.j(r, "supplier_part_number"), Lookups.j(r, "approval_reference"), Ui.date(Lookups.j(r, "valid_from")), Ui.date(Lookups.j(r, "valid_to")),
                approved(r) ? "Yes" : "No"));
        }
        if (data.isEmpty()) add(Ui.empty(a, "No approved sources yet."), 2);
        else add(new DataGrid(a, "Approved sources", Arrays.asList("Code", "Supplier", "Steel Mill", "Supplier Part No.", "Approval Reference", "Valid From", "Valid To", "Approved"), data, 300, null), 2);
    }

    private void save() {
        String p = form.validate();
        if (p != null) { problem.setText(p); problem.setVisibility(View.VISIBLE); return; }
        problem.setVisibility(View.GONE);
        final JSONObject vals;
        try { vals = form.json(); } catch (Exception e) { a.toast(Api.message(e)); return; }
        String from = MstSave.s(vals.opt("valid_from")), to = MstSave.s(vals.opt("valid_to"));
        save.setEnabled(false);
        save.setText("Saving…");
        Api.async(() -> {
            JSONArray sup = vals.optJSONArray("suppliers"), mil = vals.optJSONArray("mills");
            if (sup == null || sup.length() == 0) throw new Api.ApiException(422, "Select at least one Approved Supplier.");
            LinkedHashSet<String> wanted = new LinkedHashSet<>();
            for (int i = 0; i < sup.length(); i++) {
                if (mil == null || mil.length() == 0) wanted.add(sup.optString(i) + "|");
                else for (int j = 0; j < mil.length(); j++) wanted.add(sup.optString(i) + "|" + mil.optString(j));
            }
            JSONArray current = new JSONArray(api.get("part_supplier_links?select=*&part_id=eq." + Api.enc(partId) + "&limit=2000", false).body);
            Map<String, JSONObject> byPair = new HashMap<>();
            for (int i = 0; i < current.length(); i++) {
                JSONObject r = current.getJSONObject(i);
                byPair.put(Lookups.j(r, "supplier_id") + "|" + Lookups.j(r, "steel_mill_id"), r);
            }
            for (Map.Entry<String, JSONObject> e : byPair.entrySet()) {
                if (!wanted.contains(e.getKey()) && approved(e.getValue()))
                    api.update("part_supplier_links", Lookups.j(e.getValue(), "id"), new JSONObject().put("approved", false));
            }
            int n = 0;
            for (String pair : wanted) {
                String sid = pair.substring(0, pair.indexOf('|')), mid = pair.substring(pair.indexOf('|') + 1);
                JSONObject payload = new JSONObject();
                payload.put("part_id", partId);
                payload.put("supplier_id", sid);
                payload.put("steel_mill_id", mid.isEmpty() ? JSONObject.NULL : mid);
                payload.put("supplier_part_number", MstSave.orNull(MstSave.s(vals.opt("supplier_part_number"))));
                payload.put("approval_reference", MstSave.orNull(MstSave.s(vals.opt("approval_reference"))));
                payload.put("approved", true);
                payload.put("valid_from", from.isEmpty() ? JSONObject.NULL : from);
                payload.put("valid_to", to.isEmpty() ? JSONObject.NULL : to);
                JSONObject link = byPair.get(pair);
                if (link == null) payload.put("source_code", MstSave.nextMasterCode(api, "approved_sources"));
                if (link != null) api.update("part_supplier_links", Lookups.j(link, "id"), payload);
                else api.insert("part_supplier_links", payload);
                n++;
            }
            return n;
        }, (n, err) -> {
            save.setEnabled(true);
            save.setText("Save Approved Sources");
            if (err != null) { problem.setText(Api.message(err)); problem.setVisibility(View.VISIBLE); a.toast(Api.message(err)); return; }
            a.toast("Approved Part sources saved successfully (" + n + " pair(s)).");
            a.rebuild();
        });
    }
}
