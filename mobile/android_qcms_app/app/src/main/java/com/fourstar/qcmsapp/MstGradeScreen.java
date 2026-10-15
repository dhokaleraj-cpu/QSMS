package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Material Grade entry (app_pages/material_grade.py): header (material number from qcms_next_material_number,
 * grade_code unique ignoring case) + chemical composition (material_grade_elements, upsert by
 * {material_grade_id, element}, minimum ≤ maximum, grid pre-filled with C Si Mn P S Cr Mo Ni).
 */
public final class MstGradeScreen extends Screen {
    static final String[] DEFAULT_ELEMENTS = {"C", "Si", "Mn", "P", "S", "Cr", "Mo", "Ni"};
    private static String reservedNumber;

    private final Module m;
    private final String id;
    private JSONObject existing;
    private FormView form;
    private RowsEditor elements;
    private TextView problem;
    private Button save;

    public MstGradeScreen(MainActivity a, Module m, String id) { super(a); this.m = m; this.id = id; }

    @Override public String title() { return id == null ? "New Material Grade" : "Edit Material Grade"; }
    @Override public String subtitle() { return "Material header and chemical composition"; }
    @Override public int tab() { return Catalog.MASTERS; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONObject row = id == null ? null : MstSave.get(api, "material_grades", id);
            if (id != null && row == null) throw new Api.ApiException(404, "Material Grade not found.");
            JSONArray chem = id == null ? new JSONArray() : api.rows("material_grade_elements?select=*&material_grade_id=eq." + Api.enc(id) + "&order=element.asc&limit=300");
            String number = null;
            if (id == null) {
                synchronized (MstGradeScreen.class) { number = reservedNumber; }
                if (number == null || number.isEmpty()) {
                    try { number = MstSave.codeRpc(api, "qcms_next_material_number"); } catch (Exception e) { number = ""; }
                    synchronized (MstGradeScreen.class) { reservedNumber = number; }
                }
            }
            return new Object[]{row, chem, number};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            existing = (JSONObject) res[0];
            render((JSONArray) res[1], (String) res[2]);
        });
        return scroll;
    }

    private void render(JSONArray chem, String number) {
        List<Field> f = new ArrayList<>();
        f.add(Field.text("grade_code", "Material Grade").req().hint("e.g. 20MnCr5"));
        f.add(Field.text("material_number", "Material Number").req().hint("Generated automatically for new Material Grades and editable before save."));
        f.add(Field.text("standard", "Standard / Specification"));
        f.add(Field.text("revision", "Revision").def("00"));
        f.add(Field.date("effective_date", "Effective Date"));
        f.add(Field.select("status", "Status", "ACTIVE", "INACTIVE").req().def("ACTIVE"));
        f.add(Field.text("remarks", "Remarks"));
        form = new FormView(a, f);
        add(Ui.label(a, "Material grade details"), 0);
        add(form, 0);
        if (existing != null) form.setAll(existing);
        else if (number != null && !number.isEmpty()) form.set("material_number", number);

        List<Field> ef = new ArrayList<>();
        ef.add(Field.text("element", "Element").req());
        ef.add(Field.number("minimum", "Minimum %"));
        ef.add(Field.number("maximum", "Maximum %"));
        ef.add(Field.text("unit", "Unit").def("%"));
        ef.add(Field.text("test_method", "Test Method"));
        List<String[]> cols = MstPartGrid.cols("element", "Element", "minimum", "Minimum %", "maximum", "Maximum %", "unit", "Unit", "test_method", "Test Method");
        elements = new RowsEditor(a, "Chemical composition", ef, cols);
        elements.check(r -> {
            Double lo = MstSave.dbl(r.opt("minimum")), hi = MstSave.dbl(r.opt("maximum"));
            return lo != null && hi != null && lo > hi ? Lookups.j(r, "element") + ": Minimum cannot exceed Maximum." : null;
        });
        try { elements.template(new JSONObject().put("unit", "%")); } catch (Exception ignored) { }
        List<JSONObject> rows = MstPartGrid.list(chem);
        Set<String> have = new HashSet<>();
        for (JSONObject r : rows) {
            have.add(Lookups.j(r, "element").trim().toLowerCase(Locale.ROOT));
            if (Lookups.j(r, "unit").isEmpty()) try { r.put("unit", "%"); } catch (Exception ignored) { }
        }
        for (String e : DEFAULT_ELEMENTS) {
            if (have.contains(e.toLowerCase(Locale.ROOT))) continue;
            try { rows.add(new JSONObject().put("element", e).put("unit", "%")); } catch (Exception ignored) { }
        }
        elements.setRows(rows);
        add(Ui.label(a, "Chemical composition"), 14);
        add(elements, 0);

        problem = Ui.text(a, "", 13, Ui.RED_FG, false);
        problem.setVisibility(View.GONE);
        add(problem, 8);
        save = Ui.primary(a, "Save Material Grade");
        add(save, 10);
        save.setOnClickListener(v -> trySave());
    }

    private void showProblem(String t) {
        problem.setText(t == null ? "" : t);
        problem.setVisibility(t == null || t.isEmpty() ? View.GONE : View.VISIBLE);
        if (t != null && !t.isEmpty()) a.toast(t);
    }

    private void trySave() {
        String p = form.validate();
        if (p != null) { showProblem(p); return; }
        List<JSONObject> removed = new ArrayList<>(elements.removedRows());
        if (removed.isEmpty()) { run(removed); return; }
        a.confirm("Delete " + removed.size() + " saved element(s)?", "Removed chemical composition rows are deleted permanently. You will be asked for your password.",
            "Continue", () -> a.confirmPassword("Confirm delete with your password", () -> run(removed)));
    }

    private void run(List<JSONObject> removed) {
        showProblem("");
        final JSONObject vals;
        try { vals = form.json(); } catch (Exception e) { showProblem(Api.message(e)); return; }
        final List<JSONObject> chem = new ArrayList<>();
        for (JSONObject r : elements.rows()) chem.add(MstSave.copy(r));
        save.setEnabled(false);
        save.setText("Saving…");
        Api.async(() -> {
            String grade = MstSave.s(vals.opt("grade_code")).trim();
            String number = MstSave.s(vals.opt("material_number")).trim();
            if (grade.isEmpty()) throw new Api.ApiException(422, "Material Grade is mandatory.");
            if (number.isEmpty() && existing == null) number = MstSave.codeRpc(api, "qcms_next_material_number");
            if (number.isEmpty()) throw new Api.ApiException(422, "Material Number is mandatory and is normally generated automatically.");
            for (JSONObject r : chem) {
                Double lo = MstSave.dbl(r.opt("minimum")), hi = MstSave.dbl(r.opt("maximum"));
                if (!Lookups.j(r, "element").trim().isEmpty() && lo != null && hi != null && lo > hi)
                    throw new Api.ApiException(422, Lookups.j(r, "element").trim() + ": Minimum cannot exceed Maximum.");
            }
            JSONObject payload = new JSONObject();
            payload.put("grade_code", grade);
            payload.put("material_number", number);
            payload.put("standard", MstSave.orNull(MstSave.s(vals.opt("standard"))));
            String rev = MstSave.s(vals.opt("revision")).trim();
            payload.put("revision", rev.isEmpty() ? "00" : rev);
            payload.put("effective_date", MstSave.s(vals.opt("effective_date")).isEmpty() ? JSONObject.NULL : vals.opt("effective_date"));
            payload.put("status", MstSave.s(vals.opt("status")).isEmpty() ? "ACTIVE" : vals.opt("status"));
            payload.put("remarks", MstSave.orNull(MstSave.s(vals.opt("remarks"))));
            String expected = grade.toLowerCase(Locale.ROOT);
            JSONArray all = new JSONArray(api.get("material_grades?select=id,grade_code&limit=5000", false).body);
            for (int i = 0; i < all.length(); i++) {
                JSONObject r = all.getJSONObject(i);
                if (existing != null && Lookups.j(existing, "id").equals(Lookups.j(r, "id"))) continue;
                if (Lookups.j(r, "grade_code").trim().toLowerCase(Locale.ROOT).equals(expected))
                    throw new Api.ApiException(409, "Duplicate Material Grade code is not allowed. Standard, revision and other common fields may repeat and should be updated on the same grade record.");
            }
            JSONObject saved = existing != null ? api.update("material_grades", Lookups.j(existing, "id"), payload) : api.insert("material_grades", payload);
            String gid = Lookups.j(saved, "id");
            try {
                MstSave.deleteRows(api, "material_grade_elements", removed);
                for (JSONObject r : chem) {
                    String element = Lookups.j(r, "element").trim();
                    if (element.isEmpty()) continue;
                    Double lo = MstSave.dbl(r.opt("minimum")), hi = MstSave.dbl(r.opt("maximum"));
                    String unit = Lookups.j(r, "unit").trim();
                    JSONObject e = new JSONObject();
                    e.put("material_grade_id", gid);
                    e.put("element", element);
                    e.put("minimum", lo == null ? JSONObject.NULL : lo);
                    e.put("maximum", hi == null ? JSONObject.NULL : hi);
                    e.put("unit", unit.isEmpty() ? "%" : unit);
                    e.put("test_method", MstSave.orNull(Lookups.j(r, "test_method")));
                    api.upsertBy("material_grade_elements", e, "material_grade_id", "element");
                }
            } catch (Exception ex) {
                throw new Api.ApiException(500, "Material Grade " + grade + " saved, but the chemical composition was not fully saved: " + Api.message(ex));
            }
            Lookups.invalidate();
            return saved;
        }, (saved, err) -> {
            save.setEnabled(true);
            save.setText("Save Material Grade");
            if (err != null) { showProblem(Api.message(err)); return; }
            if (existing == null) synchronized (MstGradeScreen.class) { reservedNumber = null; }
            a.toast("Material Grade " + Lookups.j(saved, "grade_code") + " saved successfully.");
            if (existing == null) a.replaceTop(new RecordScreen(a, m, Lookups.j(saved, "id")));
            else a.back();
        });
    }

    @Override public boolean onBack() {
        a.confirm("Leave without saving?", "Changes on this form are not saved.", "Leave", () -> a.back());
        return true;
    }
}
