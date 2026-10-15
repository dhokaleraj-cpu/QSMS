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

/**
 * Base of the Part Master child grids (raw material, technical data, price history, Jominy, metallurgical):
 * loads the rows of THIS part only, edits them in a RowsEditor and saves them in one background task.
 * Saved rows removed from the grid are deleted permanently after password confirmation (website password
 * delete panel → qsms_delete_master_row) before the remaining rows are written.
 */
public abstract class MstPartGrid extends Screen {
    protected final JSONObject part;
    protected final String partId;
    protected RowsEditor editor;
    protected LinearLayout extra;
    private TextView problem;
    private Button saveButton;

    protected MstPartGrid(MainActivity a, JSONObject part) {
        super(a);
        this.part = part;
        this.partId = Lookups.j(part, "id");
    }

    /** Screen title, e.g. "Raw material details". */
    protected abstract String heading();
    /** Child table (for deletes). */
    protected abstract String table();
    /** Background: load lookups + rows of this part. */
    protected abstract List<JSONObject> load() throws Exception;
    protected abstract List<Field> fields();
    protected abstract List<String[]> columns();
    /** Background: validate all rows, then write them; returns the success message. */
    protected abstract String store(List<JSONObject> rows) throws Exception;
    protected String note() { return ""; }
    protected String check(JSONObject row) { return null; }
    protected JSONObject template() { return null; }
    protected String saveLabel() { return "Save " + heading(); }
    /** Extra controls under the save button (e.g. generate layout). */
    protected void addExtra(LinearLayout box) { }

    @Override public String title() { return heading(); }
    @Override public String subtitle() { return partLabel(part); }
    @Override public int tab() { return Catalog.MASTERS; }

    static String partLabel(JSONObject p) {
        return Lookups.join(Lookups.j(p, "part_number"), Lookups.j(p, "fsi_part_number").isEmpty() ? "" : "FSI " + Lookups.j(p, "fsi_part_number"), Lookups.j(p, "part_name"));
    }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(this::load, (rows, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            render(rows);
        });
        return scroll;
    }

    private void render(List<JSONObject> rows) {
        offlineNote();
        LinearLayout head = Ui.card(a);
        head.addView(Ui.text(a, partLabel(part), 15, Ui.TEXT, true));
        if (!note().isEmpty()) head.addView(Ui.text(a, note(), 12, Ui.MUTED, false));
        add(head, 2);
        editor = new RowsEditor(a, heading(), fields(), columns());
        editor.check(this::check);
        JSONObject t = template();
        if (t != null) editor.template(t);
        editor.setRows(rows);
        add(editor, 10);
        problem = Ui.text(a, "", 13, Ui.RED_FG, false);
        problem.setVisibility(View.GONE);
        add(problem, 8);
        saveButton = Ui.primary(a, saveLabel());
        add(saveButton, 10);
        saveButton.setOnClickListener(v -> save());
        extra = Ui.vbox(a);
        add(extra, 6);
        addExtra(extra);
    }

    protected void showProblem(String t) {
        problem.setText(t == null ? "" : t);
        problem.setVisibility(t == null || t.isEmpty() ? View.GONE : View.VISIBLE);
    }

    private void save() {
        showProblem("");
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject r : editor.rows()) rows.add(MstSave.copy(r));
        List<JSONObject> removed = new ArrayList<>(editor.removedRows());
        if (removed.isEmpty()) { run(rows, removed); return; }
        a.confirm("Delete " + removed.size() + " saved row(s)?",
            "Rows removed from the grid are deleted permanently from " + heading() + ". You will be asked for your password.",
            "Continue", () -> a.confirmPassword("Confirm delete with your password", () -> run(rows, removed)));
    }

    private void run(List<JSONObject> rows, List<JSONObject> removed) {
        saveButton.setEnabled(false);
        saveButton.setText("Saving…");
        Api.async(() -> {
            int deleted = 0;
            if (!removed.isEmpty()) {
                try { deleted = MstSave.deleteRows(api, table(), removed); }
                catch (Exception e) { throw new Api.ApiException(409, "Deletion blocked: " + Api.message(e) + " Nothing else was saved."); }
            }
            String msg = store(rows);
            return deleted > 0 ? msg + " " + deleted + " row(s) deleted." : msg;
        }, (msg, err) -> {
            saveButton.setEnabled(true);
            saveButton.setText(saveLabel());
            if (err != null) { showProblem(Api.message(err)); a.toast(Api.message(err)); return; }
            a.toast(msg);
            a.rebuild();
        });
    }

    @Override public boolean onBack() {
        a.confirm("Leave this grid?", "Unsaved grid changes are lost.", "Leave", () -> a.back());
        return true;
    }

    // ------------------------------------------------------------------ shared helpers
    static List<JSONObject> list(JSONArray rows) {
        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; rows != null && i < rows.length(); i++) { JSONObject r = rows.optJSONObject(i); if (r != null) out.add(r); }
        return out;
    }

    static List<String[]> cols(String... pairs) {
        List<String[]> out = new ArrayList<>();
        for (int i = 0; i + 1 < pairs.length; i += 2) out.add(new String[]{pairs[i], pairs[i + 1]});
        return out;
    }

    static final Field.Lookup SUPPLIERS = Lookups.suppliers();
    static final Field.Lookup GRADES = Lookups.grades();

    /** Website raw_labels: Supplier · HSN · Grade · Raw Material Type · Section · Source · LT. */
    static String rawLabel(JSONObject r, JSONObject part, Field.Lookup parts) {
        String hsn = Lookups.j(r, "hsn_sac_code").isEmpty() ? Lookups.j(part, "hsn_sac_code") : Lookups.j(r, "hsn_sac_code");
        String src = Lookups.j(r, "source_part_id").isEmpty() ? "Own Part" : Lookups.labelOf(parts, Lookups.j(r, "source_part_id"));
        String type = Lookups.j(r, "material_section_name");
        return Lookups.labelOf(SUPPLIERS, Lookups.j(r, "supplier_id")) + " · HSN " + (hsn.isEmpty() ? "-" : hsn) + " · "
            + (Lookups.j(r, "material_grade_id").isEmpty() ? "Grade -" : Lookups.labelOf(GRADES, Lookups.j(r, "material_grade_id"))) + " · "
            + (type.isEmpty() ? "Raw Material Type -" : type) + " · " + (Lookups.j(r, "section_size").isEmpty() ? "-" : Lookups.j(r, "section_size"))
            + " · Source " + src + " · LT " + (Lookups.j(r, "lead_time_days").isEmpty() ? "0" : Lookups.j(r, "lead_time_days")) + "d";
    }

    interface RawPicked { void picked(JSONObject raw); }

    /** "Raw Material / Supplier Record" picker used by Supplier technical data and Price history. */
    static void chooseRaw(MainActivity a, JSONObject part, RawPicked picked) {
        Api api = Api.get(a);
        String partId = Lookups.j(part, "id");
        Field.Lookup parts = Lookups.parts();
        a.toast("Loading raw material records…");
        Api.async(() -> {
            Lookups.rows(api, SUPPLIERS);
            Lookups.rows(api, GRADES);
            Lookups.rows(api, parts);
            return api.rows("part_raw_material_details?select=*&part_id=eq." + Api.enc(partId) + "&order=sequence_no.asc&limit=500");
        }, (rows, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            if (rows.length() == 0) { a.toast("Save at least one Raw Material Detail row before adding supplier technical data or price history."); return; }
            String[] labels = new String[rows.length()];
            for (int i = 0; i < rows.length(); i++) labels[i] = rawLabel(rows.optJSONObject(i), part, parts);
            new AlertDialog.Builder(a).setTitle("Raw Material / Supplier Record")
                .setItems(labels, (d, which) -> picked.picked(rows.optJSONObject(which)))
                .setNegativeButton("Back", null).show();
        });
    }
}
