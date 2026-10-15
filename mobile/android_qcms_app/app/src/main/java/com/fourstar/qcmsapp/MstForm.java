package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Native create / edit form for a master record. By default it saves through MstSave.save (the port of
 * MasterService.save); masters with their own website save path (employees, company branches) pass a Saver.
 * A controlled code is reserved when a new form opens (like the website) and stays editable before saving.
 */
public final class MstForm extends Screen {
    public interface Fields { List<Field> of(JSONObject existing); }
    public interface Saver { JSONObject save(Api api, JSONObject values, JSONObject existing) throws Exception; }
    public interface Reserve { String code(Api api) throws Exception; }

    /** Everything the form needs for one master. */
    public static final class Spec {
        Fields fields;
        MstSave.Def def;
        Saver saver;
        Reserve reserve;
        String reserveField;
        String note = "";

        public static Spec of(MstSave.Def def) {
            Spec s = new Spec();
            s.def = def;
            s.fields = existing -> def.fields;
            if (!def.autoField.isEmpty()) { s.reserveField = def.autoField; s.reserve = api -> MstSave.nextMasterCode(api, def.key); }
            return s;
        }
        public static Spec custom(Fields fields, Saver saver) { Spec s = new Spec(); s.fields = fields; s.saver = saver; return s; }
        public Spec reserve(String field, Reserve r) { reserveField = field; reserve = r; return this; }
        public Spec note(String n) { note = n; return this; }
    }

    /** Codes reserved for a still-unsaved new record (like the website's session_state), per module. */
    private static final Map<String, String> RESERVED = new HashMap<>();

    private final Module m;
    private final String id;
    private final JSONObject prefill;
    private final Spec spec;
    private JSONObject existing;
    private FormView form;
    private TextView problem;

    public MstForm(MainActivity a, Module m, String id, JSONObject prefill, Spec spec) {
        super(a);
        this.m = m; this.id = id; this.prefill = prefill; this.spec = spec;
    }

    @Override public String title() { return (id == null ? "New · " : "Edit · ") + m.title; }
    @Override public String subtitle() { return spec.note.isEmpty() ? "Fields marked * are required" : spec.note; }
    @Override public int tab() { return m.tab; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONObject row = null;
            if (id != null) {
                row = MstSave.get(api, m.table, id);
                if (row == null) throw new Api.ApiException(404, "Record not found or not visible for your role.");
            }
            String code = null;
            if (id == null && spec.reserve != null) {
                synchronized (RESERVED) { code = RESERVED.get(m.key); }
                if (code == null || code.isEmpty()) {
                    try { code = spec.reserve.code(api); } catch (Exception e) { code = ""; }
                    synchronized (RESERVED) { RESERVED.put(m.key, code); }
                }
            }
            return new Object[]{row, code};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            existing = (JSONObject) res[0];
            render((String) res[1]);
        });
        return scroll;
    }

    private void render(String code) {
        form = new FormView(a, spec.fields.of(existing));
        add(form, 0);
        if (existing != null) form.setAll(existing);
        else if (prefill != null) form.setAll(prefill);
        if (existing == null && spec.reserveField != null) {
            if (code != null && !code.isEmpty() && form.str(spec.reserveField).isEmpty()) form.set(spec.reserveField, code);
            if (code == null || code.isEmpty()) a.toast("Automatic code could not be reserved - it is generated on save.");
        }
        problem = Ui.text(a, "", 13, Ui.RED_FG, false);
        problem.setVisibility(View.GONE);
        add(problem, 10);
        Button save = Ui.primary(a, id == null ? "Save" : "Save changes");
        add(save, 14);
        save.setOnClickListener(v -> save(save));
    }

    private void showProblem(String text) {
        problem.setText(text);
        problem.setVisibility(text == null || text.isEmpty() ? View.GONE : View.VISIBLE);
        if (text != null && !text.isEmpty()) a.toast(text);
    }

    private void save(Button button) {
        String p = form.validate();
        if (p != null) { showProblem(p); return; }
        showProblem("");
        final JSONObject values;
        try { values = form.json(); } catch (Exception e) { showProblem(Api.message(e)); return; }
        button.setEnabled(false);
        button.setText("Saving…");
        Api.async(() -> {
            JSONObject saved = spec.saver != null ? spec.saver.save(api, values, existing) : MstSave.save(api, spec.def, values, id);
            Lookups.invalidate();
            return saved;
        }, (saved, err) -> {
            button.setEnabled(true);
            button.setText(id == null ? "Save" : "Save changes");
            if (err != null) { showProblem(Api.message(err)); return; }
            if (id == null) synchronized (RESERVED) { RESERVED.remove(m.key); }
            a.toast(m.title + (id == null ? " created." : " updated."));
            if (id == null && saved != null && !Lookups.j(saved, "id").isEmpty()) a.replaceTop(new RecordScreen(a, m, Lookups.j(saved, "id")));
            else a.back();
        });
    }

    @Override public boolean onBack() {
        a.confirm("Leave without saving?", "Changes on this form are not saved.", "Leave", () -> a.back());
        return true;
    }

    /** Small helper for screens: a card with a caption. */
    static LinearLayout noteCard(MainActivity a, String text) {
        LinearLayout c = Ui.card(a);
        c.addView(Ui.text(a, text, 12, Ui.MUTED, false));
        return c;
    }
}
