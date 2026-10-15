package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Iterator;

/** Generic create / edit form of a module (Field list), with the website's numbering and save rules. */
public final class EditScreen extends Screen {
    private final Module m;
    private final String id;
    private final JSONObject prefill;
    private JSONObject existing;
    private FormView form;

    private EditScreen(MainActivity a, Module m, String id, JSONObject prefill) {
        super(a);
        this.m = m; this.id = id; this.prefill = prefill;
    }

    /** Custom editor when the module has one, else the generic form. */
    public static Screen open(MainActivity a, Module m, String id, JSONObject prefill) {
        if (m.editor != null) return m.editor.open(a, id, prefill);
        return new EditScreen(a, m, id, prefill);
    }

    @Override public String title() { return (id == null ? "New · " : "Edit · ") + m.title; }
    @Override public String subtitle() { return "Fields marked * are required"; }
    @Override public int tab() { return m.tab; }

    @Override
    public View build() {
        newPage();
        form = new FormView(a, m.form);
        add(form, 0);
        Button save = Ui.primary(a, id == null ? "Save" : "Save changes");
        add(save, 18);
        save.setOnClickListener(v -> save(save));
        if (id != null) {
            form.setVisibility(View.INVISIBLE);
            Api.async(() -> {
                JSONArray r = api.rows(m.table + "?select=*&" + m.idField + "=eq." + Api.enc(id));
                if (r.length() == 0) throw new Api.ApiException(404, "Record not found.");
                return r.getJSONObject(0);
            }, (row, err) -> {
                if (err != null) { page.addView(error(err, this::reload), 0); return; }
                existing = row;
                form.setAll(row);
                form.setVisibility(View.VISIBLE);
            });
        } else if (prefill != null) {
            form.setAll(prefill);
        }
        return scroll;
    }

    private void save(Button button) {
        String problem = form.validate();
        if (problem != null) { a.toast(problem); return; }
        button.setEnabled(false);
        button.setText("Saving…");
        Api.async(() -> {
            JSONObject values = form.json();
            if (id == null && m.fixed != null) {
                Iterator<String> it = m.fixed.keys();
                while (it.hasNext()) { String k = it.next(); if (!values.has(k) || values.isNull(k)) values.put(k, m.fixed.opt(k)); }
            }
            if (id == null && m.numberField != null && (values.isNull(m.numberField) || values.optString(m.numberField).trim().isEmpty())) {
                values.put(m.numberField, api.nextNumber(m.numberRpc, m.numberArgs == null ? new JSONObject() : new JSONObject(m.numberArgs)));
            }
            if (m.beforeSave != null) m.beforeSave.apply(a, api, values, existing);
            JSONObject saved = api.save(m.table, id, values);
            if (m.afterSave != null) m.afterSave.apply(a, api, saved, existing);
            Lookups.invalidate();
            return saved;
        }, (saved, err) -> {
            button.setEnabled(true);
            button.setText(id == null ? "Save" : "Save changes");
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast("Saved.");
            if (id == null && !m.idField.isEmpty()) a.replaceTop(new RecordScreen(a, m, saved.optString(m.idField)));
            else a.back();
        });
    }

    @Override public boolean onBack() {
        a.confirm("Leave without saving?", "Changes on this form are not saved.", "Leave", () -> a.back());
        return true;
    }
}
