package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Base of the native editors of this area: loads the record (and any extra data) in the background,
 * builds a sectioned form, validates, saves in one background task and returns to the record.
 */
abstract class CalEditScreen extends Screen {
    protected final String id;
    protected final JSONObject prefill;
    protected JSONObject existing;
    protected CalSections form;
    protected LinearLayout buttons;
    /** Set by persist() when the main write worked but a follow-up step did not. */
    protected volatile String warning;
    /** True while the screen sets values itself (onChange handlers should ignore those). */
    protected boolean quiet;

    CalEditScreen(MainActivity a, String id, JSONObject prefill) {
        super(a);
        this.id = id == null || id.isEmpty() ? null : id;
        this.prefill = prefill;
    }

    /** Table of the edited row (null for screens that update another record). */
    protected abstract String table();
    /** Module whose record screen opens after a new record is saved (null = go back). */
    protected Module module() { return null; }
    /** Background: extra rows needed by the form (lookups, links …). */
    protected void load() throws Exception { }
    /** UI: add the form sections. */
    protected abstract void buildForm(CalSections f);
    /** UI: after the values are filled (wire onChange, visibility …). */
    protected void afterFill() { }
    /** UI: extra validation; return the problem or null. */
    protected String check() { return null; }
    /** UI: the values to save (default: the form values). */
    protected JSONObject collect() throws Exception { return form.json(); }
    /** Background: write exactly what the website writes; returns the saved row. */
    protected abstract JSONObject persist(JSONObject values) throws Exception;
    /** UI: extra buttons below the save button. */
    protected void addButtons(LinearLayout b) { }
    protected String saveLabel() { return id == null ? "Save" : "Save changes"; }
    protected String savedMessage() { return "Saved."; }

    @Override public int tab() { return Catalog.QUALITY; }
    @Override public String subtitle() { return "Fields marked * are required"; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            if (id != null && table() != null) {
                JSONArray r = api.rows(table() + "?select=*&id=eq." + Api.enc(id));
                if (r.length() == 0) throw new Api.ApiException(404, "Record not found or not visible for your role.");
                existing = r.getJSONObject(0);
            }
            load();
            return true;
        }, (ok, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            if (existing != null) a.rebuildTitle(this);
            offlineNote();
            form = new CalSections(a);
            quiet = true;
            buildForm(form);
            add(form, 0);
            if (existing != null) form.setAll(existing);
            else if (prefill != null) form.setAll(prefill);
            quiet = false;
            afterFill();
            buttons = Ui.vbox(a);
            Button save = Ui.primary(a, saveLabel());
            save.setOnClickListener(v -> save(save));
            buttons.addView(save, Ui.matchWrap(a, 0));
            addButtons(buttons);
            add(buttons, 18);
        });
        return scroll;
    }

    protected void save(Button button) {
        String problem = form.validate();
        if (problem == null) problem = check();
        if (problem != null) { a.toast(problem); return; }
        JSONObject values;
        try { values = collect(); } catch (Exception e) { a.toast(Api.message(e)); return; }
        String label = button.getText().toString();
        button.setEnabled(false);
        button.setText("Saving…");
        warning = null;
        Api.async(() -> {
            JSONObject saved = persist(values);
            Lookups.invalidate();
            return saved;
        }, (saved, err) -> {
            button.setEnabled(true);
            button.setText(label);
            if (err != null) { a.toast(Api.message(err)); return; }
            done(saved);
        });
    }

    protected void done(JSONObject saved) {
        if (warning != null) a.confirm("Saved with a warning", warning, "OK", () -> { });
        else a.toast(savedMessage());
        Module m = module();
        if (id == null && m != null && saved != null && !Lookups.j(saved, "id").isEmpty()) a.replaceTop(new RecordScreen(a, m, Lookups.j(saved, "id")));
        else a.back();
    }

    @Override public boolean onBack() {
        a.confirm("Leave without saving?", "Changes on this form are not saved.", "Leave", () -> a.back());
        return true;
    }
}
