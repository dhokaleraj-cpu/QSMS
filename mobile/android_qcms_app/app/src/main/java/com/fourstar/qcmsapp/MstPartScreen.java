package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Part Master · Part details (app_pages/part_master.py section A): header payload, find_part_conflicts
 * (exact = blocked, 4+ matching digits = review + "Not a duplicate"), then part_material_grade_links sync
 * (clear primary first, upsert wanted grades, deactivate the rest).
 */
public final class MstPartScreen extends Screen {
    private final Module m;
    private final String id;
    private JSONObject existing;
    private FormView form;
    private TextView problem;
    private Button saveButton;

    public MstPartScreen(MainActivity a, Module m, String id) { super(a); this.m = m; this.id = id; }

    @Override public String title() { return id == null ? "New Part" : "Edit Part"; }
    @Override public String subtitle() { return "Part Master · Part details"; }
    @Override public int tab() { return Catalog.MASTERS; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONObject row = id == null ? null : MstSave.get(api, "parts", id);
            if (id != null && row == null) throw new Api.ApiException(404, "Part not found or not visible for your role.");
            JSONArray grades = Lookups.rows(api, Lookups.grades());
            Lookups.rows(api, Lookups.customers());
            JSONArray links = id == null ? new JSONArray() : api.rows("part_material_grade_links?select=*&part_id=eq." + Api.enc(id) + "&limit=500");
            return new Object[]{row, grades, links};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            existing = (JSONObject) res[0];
            render((JSONArray) res[1], (JSONArray) res[2]);
        });
        return scroll;
    }

    private void render(JSONArray grades, JSONArray links) {
        String[] gradeIds = new String[grades.length()];
        String[] gradeNames = new String[grades.length()];
        for (int i = 0; i < grades.length(); i++) {
            JSONObject g = grades.optJSONObject(i);
            gradeIds[i] = Lookups.j(g, "id");
            gradeNames[i] = Lookups.GRADE.of(g);
        }
        List<Field> fields = new ArrayList<>();
        fields.add(Field.text("part_number", "Part Number").req().hint("Original / customer Part Number. Internal QCMS identity."));
        fields.add(Field.text("fsi_part_number", "FSI Part Number").hint("Secondary FSI identity used on supplier-facing documents."));
        fields.add(Field.text("part_name", "Part Description").req());
        fields.add(Field.number("finished_weight_kg", "Part Finish Weight (kg)").range(0, 1e9).def(0));
        fields.add(Field.text("hsn_sac_code", "HSN / SAC Code").hint("Default supplier PO HSN/SAC; can be overridden on the PO line."));
        fields.add(Field.select("status", "Status", "ACTIVE", "INACTIVE").req().def("ACTIVE"));
        fields.add(Field.lookup("customer_id", "Customer", Lookups.customers()).req());
        fields.add(Field.lookup("material_grade_id", "Primary Material Grade", Lookups.grades()).req()
            .hint("Primary/default grade. Alternate approved grades are selected below."));
        fields.add(Field.info("drawing_number", "Current Finish Drawing No."));
        fields.add(Field.info("drawing_revision", "Current Finish Revision"));
        Field alt = Field.multi("alternate_grades", "Approved / Alternate Material Grades", gradeIds).labels(gradeNames);
        alt.hint = "A Part may use several approved grades. Each supplier Raw Material row selects the applicable grade.";
        fields.add(alt);
        fields.add(Field.area("remarks", "Remarks"));
        fields.add(Field.bool("not_duplicate", "Not a duplicate").hint("I have reviewed the similar Part Numbers (4+ matching digits)"));
        form = new FormView(a, fields);
        add(form, 0);
        if (existing != null) {
            form.setAll(existing);
            JSONArray alts = new JSONArray();
            Set<String> known = new LinkedHashSet<>();
            for (String g : gradeIds) known.add(g);
            for (int i = 0; i < links.length(); i++) {
                JSONObject l = links.optJSONObject(i);
                String status = Lookups.j(l, "status");
                if ((status.isEmpty() || "ACTIVE".equals(status)) && !l.optBoolean("is_primary", false) && known.contains(Lookups.j(l, "material_grade_id"))) alts.put(Lookups.j(l, "material_grade_id"));
            }
            form.set("alternate_grades", alts);
        }
        add(MstForm.noteCard(a, "Exact duplicates of a Part Number / FSI Part Number (case, spaces and dashes ignored) are always blocked. "
            + "When 4 or more consecutive digits match an existing Part, QCMS lists the similar Parts and asks you to confirm."), 10);
        problem = Ui.text(a, "", 13, Ui.RED_FG, false);
        problem.setVisibility(View.GONE);
        add(problem, 10);
        saveButton = Ui.primary(a, "Save Part Master");
        add(saveButton, 12);
        saveButton.setOnClickListener(v -> save(form.bool("not_duplicate")));
    }

    private void showProblem(String t) {
        problem.setText(t == null ? "" : t);
        problem.setVisibility(t == null || t.isEmpty() ? View.GONE : View.VISIBLE);
    }

    private void save(boolean confirmed) {
        String p = form.validate();
        if (p != null) { showProblem(p); a.toast(p); return; }
        showProblem("");
        saveButton.setEnabled(false);
        saveButton.setText("Saving…");
        final String partNumber = form.str("part_number");
        final String fsi = form.str("fsi_part_number");
        final JSONObject vals;
        try { vals = form.json(); } catch (Exception e) { saveButton.setEnabled(true); saveButton.setText("Save Part Master"); showProblem(Api.message(e)); return; }
        Api.async(() -> {
            JSONObject conflicts = MstSave.partConflicts(api, partNumber, fsi, existing == null ? null : Lookups.j(existing, "id"));
            JSONArray exact = conflicts.getJSONArray("exact");
            if (exact.length() > 0) return new JSONObject().put("exact", exact);
            JSONArray similar = conflicts.getJSONArray("similar");
            if (similar.length() > 0 && !confirmed) return new JSONObject().put("similar", similar);

            Double weight = MstSave.dbl(vals.opt("finished_weight_kg"));
            JSONObject payload = new JSONObject();
            payload.put("part_number", partNumber);
            payload.put("fsi_part_number", MstSave.orNull(fsi));
            payload.put("part_name", MstSave.s(vals.opt("part_name")));
            payload.put("customer_id", MstSave.s(vals.opt("customer_id")));
            payload.put("material_grade_id", MstSave.s(vals.opt("material_grade_id")));
            payload.put("finished_weight_kg", weight == null ? 0.0 : weight);
            payload.put("hsn_sac_code", MstSave.orNull(MstSave.s(vals.opt("hsn_sac_code"))));
            payload.put("status", MstSave.s(vals.opt("status")).isEmpty() ? "ACTIVE" : MstSave.s(vals.opt("status")));
            payload.put("remarks", MstSave.orNull(MstSave.s(vals.opt("remarks"))));
            if (existing != null) {
                payload.put("drawing_number", existing.opt("drawing_number") == null ? JSONObject.NULL : existing.opt("drawing_number"));
                payload.put("drawing_revision", existing.opt("drawing_revision") == null ? JSONObject.NULL : existing.opt("drawing_revision"));
            }
            JSONObject saved = existing != null ? api.update("parts", Lookups.j(existing, "id"), payload) : api.insert("parts", payload);
            String partId = Lookups.j(saved, "id");
            try {
                syncGrades(partId, MstSave.s(vals.opt("material_grade_id")), vals.optJSONArray("alternate_grades"));
            } catch (Exception e) {
                throw new Api.ApiException(500, "Part saved, but the approved grade list was not fully updated: " + Api.message(e) + " Open the Part and save again.");
            }
            Lookups.invalidate();
            return new JSONObject().put("saved", saved).put("similarCount", similar.length());
        }, (res, err) -> {
            saveButton.setEnabled(true);
            saveButton.setText("Save Part Master");
            if (err != null) { showProblem(Api.message(err)); a.toast(Api.message(err)); return; }
            if (res.has("exact")) {
                JSONArray exact = res.optJSONArray("exact");
                String reasons = "";
                for (int i = 0; i < exact.length(); i++) reasons += exact.optJSONObject(i).optString("Reason") + " ";
                String msg = reasons.startsWith("FSI Part Number") && !reasons.contains("Part Number " + partNumber)
                    ? "Duplicate FSI Part Number is not allowed. The same identity already exists in Part Master (case, spaces and dashes are ignored)."
                    : "Duplicate Part Number is not allowed. The same identity already exists in Part Master (case, spaces and dashes are ignored).";
                showProblem(msg);
                new AlertDialog.Builder(a).setTitle("Duplicate Part").setMessage(msg + "\n\n" + MstSave.conflictText(exact)).setPositiveButton("OK", null).show();
                return;
            }
            if (res.has("similar")) {
                JSONArray similar = res.optJSONArray("similar");
                String msg = similar.length() + " existing Part(s) share 4 or more consecutive digits with this Part Number / FSI Part Number.";
                showProblem("Possible duplicate Part. If this is a different Part, confirm 'Not a duplicate'.");
                new AlertDialog.Builder(a).setTitle("Possible duplicate Part").setMessage(msg + "\n\n" + MstSave.conflictText(similar))
                    .setPositiveButton("Not a duplicate - Save", (d, w) -> { form.set("not_duplicate", true); save(true); })
                    .setNegativeButton("Back", null).show();
                return;
            }
            JSONObject saved = res.optJSONObject("saved");
            a.toast("Part Master saved: " + partNumber + (res.optInt("similarCount") > 0 ? " (confirmed not a duplicate)" : ""));
            if (existing == null) a.replaceTop(new RecordScreen(a, m, Lookups.j(saved, "id")));
            else a.back();
        });
    }

    /** Primary + alternate grades → part_material_grade_links exactly like the website. */
    private void syncGrades(String partId, String primary, JSONArray alternates) throws Exception {
        Set<String> wanted = new LinkedHashSet<>();
        wanted.add(primary);
        for (int i = 0; alternates != null && i < alternates.length(); i++) {
            String g = alternates.optString(i);
            if (!g.isEmpty() && !"null".equals(g)) wanted.add(g);
        }
        JSONArray links = new JSONArray(api.get("part_material_grade_links?select=*&part_id=eq." + Api.enc(partId) + "&limit=500", false).body);
        Map<String, JSONObject> byGrade = new HashMap<>();
        for (int i = 0; i < links.length(); i++) {
            JSONObject l = links.getJSONObject(i);
            byGrade.put(Lookups.j(l, "material_grade_id"), l);
        }
        for (int i = 0; i < links.length(); i++) {
            JSONObject l = links.getJSONObject(i);
            if (l.optBoolean("is_primary", false)) api.update("part_material_grade_links", Lookups.j(l, "id"), new JSONObject().put("is_primary", false));
        }
        for (String gid : wanted) {
            JSONObject data = new JSONObject().put("part_id", partId).put("material_grade_id", gid).put("is_primary", gid.equals(primary)).put("status", "ACTIVE");
            JSONObject link = byGrade.get(gid);
            if (link != null) api.update("part_material_grade_links", Lookups.j(link, "id"), data);
            else api.insert("part_material_grade_links", data);
        }
        for (Map.Entry<String, JSONObject> e : byGrade.entrySet()) {
            if (!wanted.contains(e.getKey())) api.update("part_material_grade_links", Lookups.j(e.getValue(), "id"), new JSONObject().put("is_primary", false).put("status", "INACTIVE"));
        }
    }

    @Override public boolean onBack() {
        a.confirm("Leave without saving?", "Changes on this form are not saved.", "Leave", () -> a.back());
        return true;
    }
}
