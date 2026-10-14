package com.fourstar.qcmsapp;

import android.graphics.Color;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Part Master viewer: search a Part, then its Raw Material details in a frozen-pane grid. */
public final class PartRmScreen extends Screen {
    private static String lastQuery = "";
    private LinearLayout results;
    private EditText search;

    public PartRmScreen(MainActivity a) { super(a); }

    @Override public String title() { return "Part Master · RM details"; }
    @Override public String subtitle() { return "Search part number / FSI number / description"; }
    @Override public int tab() { return 4; }

    @Override
    public View build() {
        newPage();
        LinearLayout row = Ui.hbox(a);
        search = Ui.input(a, "e.g. K11696 or 10.11696", false);
        search.setText(lastQuery);
        search.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        row.addView(search, Ui.weight(1));
        Button go = Ui.primary(a, "Search");
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(96), dp(48));
        lp.leftMargin = dp(8);
        row.addView(go, lp);
        add(row, 0);
        results = Ui.vbox(a);
        add(results, 6);
        go.setOnClickListener(v -> find());
        search.setOnEditorActionListener((v, actionId, e) -> { find(); return true; });
        if (!lastQuery.isEmpty()) find();
        return scroll;
    }

    private void find() {
        String q = search.getText().toString().trim().replace(",", " ").replace("(", " ").replace(")", " ");
        lastQuery = q;
        if (q.length() < 2) { a.toast("Type at least 2 characters."); return; }
        results.removeAllViews();
        results.addView(loading());
        String like = Api.enc("*" + q + "*");
        Api.async(() -> api.rows("parts?select=id,part_number,fsi_part_number,part_name,status&or=(part_number.ilike." + like + ",fsi_part_number.ilike." + like + ",part_name.ilike." + like + ")&order=part_number.asc&limit=40"),
            (rows, err) -> {
                results.removeAllViews();
                if (err != null) { results.addView(error(err, this::find)); return; }
                if (rows.length() == 0) { results.addView(Ui.empty(a, "No Part found.")); return; }
                for (int i = 0; i < rows.length(); i++) {
                    JSONObject p = rows.optJSONObject(i);
                    LinearLayout card = Ui.card(a);
                    LinearLayout top = Ui.hbox(a);
                    top.addView(Ui.text(a, p.optString("part_number") + " · FSI " + AssetsScreen.nz(p.optString("fsi_part_number")), 14, Ui.TEXT, true), Ui.weight(1));
                    top.addView(Ui.chip(a, Ui.pretty(p.optString("status")), Ui.tone(p.optString("status"))));
                    card.addView(top);
                    card.addView(Ui.text(a, AssetsScreen.nz(p.optString("part_name")), 12, Ui.MUTED, false));
                    Ui.clickable(card, Color.WHITE, Ui.LINE, 14);
                    card.setOnClickListener(v -> showPart(p));
                    results.addView(card, Ui.matchWrap(a, 8));
                }
            });
    }

    private void showPart(JSONObject part) {
        results.removeAllViews();
        results.addView(loading());
        String pid = part.optString("id");
        Api.async(() -> {
            JSONArray rm = api.rows("part_raw_material_details?select=*&part_id=eq." + pid + "&order=sequence_no.asc");
            Set<String> sup = new LinkedHashSet<>();
            Set<String> grades = new LinkedHashSet<>();
            for (int i = 0; i < rm.length(); i++) {
                JSONObject r = rm.getJSONObject(i);
                if (!r.isNull("supplier_id")) sup.add(r.optString("supplier_id"));
                if (!r.isNull("material_grade_id")) grades.add(r.optString("material_grade_id"));
            }
            Map<String, String> names = new HashMap<>();
            if (!sup.isEmpty()) {
                JSONArray p = api.rows("parties?select=id,party_name&id=in.(" + String.join(",", sup) + ")");
                for (int i = 0; i < p.length(); i++) names.put(p.getJSONObject(i).optString("id"), p.getJSONObject(i).optString("party_name"));
            }
            if (!grades.isEmpty()) {
                JSONArray g = api.rows("material_grades?select=id,grade_code&id=in.(" + String.join(",", grades) + ")");
                for (int i = 0; i < g.length(); i++) names.put(g.getJSONObject(i).optString("id"), g.getJSONObject(i).optString("grade_code"));
            }
            JSONObject out = new JSONObject();
            out.put("rm", rm);
            out.put("names", new JSONObject(names));
            return out;
        }, (d, err) -> {
            results.removeAllViews();
            if (err != null) { results.addView(error(err, () -> showPart(part))); return; }
            JSONArray rm = d.optJSONArray("rm");
            JSONObject names = d.optJSONObject("names");
            LinearLayout head = Ui.card(a);
            head.addView(Ui.text(a, part.optString("part_number") + " · FSI " + AssetsScreen.nz(part.optString("fsi_part_number")), 15, Ui.TEXT, true));
            head.addView(Ui.text(a, AssetsScreen.nz(part.optString("part_name")), 12, Ui.MUTED, false));
            results.addView(head, Ui.matchWrap(a, 0));
            results.addView(Ui.label(a, "Raw Material details (" + rm.length() + ") · scroll ← → ↑ ↓"));
            List<String> cols = Arrays.asList("Supplier", "Section", "Size", "Grade", "Forging kg", "Gross kg", "Input kg", "Lead days", "HSN/SAC", "Supplier RM code", "Forging part no.", "Status", "Remarks");
            List<List<String>> rows = new ArrayList<>();
            for (int i = 0; i < rm.length(); i++) {
                JSONObject r = rm.optJSONObject(i);
                rows.add(Arrays.asList(names.optString(r.optString("supplier_id"), "-"), AssetsScreen.nz(r.optString("material_section_name")), AssetsScreen.nz(r.optString("section_size")),
                    names.optString(r.optString("material_grade_id"), "-"), num(r, "forging_weight_kg"), num(r, "gross_weight_kg"), num(r, "input_weight_kg"),
                    AssetsScreen.nz(r.optString("lead_time_days")), AssetsScreen.nz(r.optString("hsn_sac_code")), AssetsScreen.nz(r.optString("supplier_rm_item_code")),
                    AssetsScreen.nz(r.optString("supplier_forging_part_number")), Ui.pretty(r.optString("status")), AssetsScreen.nz(r.optString("remarks"))));
            }
            results.addView(new DataGrid(a, cols, rows, 360, null), Ui.matchWrap(a, 2));
            Button edit = Ui.outline(a, "Edit Part in QCMS (Part Master)", Ui.TEAL);
            edit.setOnClickListener(v -> a.openWeb("Part Master", "part-entry"));
            results.addView(edit, Ui.matchWrap(a, 12));
            Button again = Ui.outline(a, "Search another Part", Ui.TEAL);
            again.setOnClickListener(v -> find());
            results.addView(again, Ui.matchWrap(a, 8));
        });
    }

    private static String num(JSONObject r, String key) {
        if (r.isNull(key)) return "";
        return Ui.num(r.optDouble(key, 0), 3);
    }
}
