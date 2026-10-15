package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.graphics.Color;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Editable child rows inside a form (like the website's data_editor grids): spreadsheet view of the
 * rows, "Add row", tap a row to edit it in a form dialog, remove rows. Values stay in memory until the
 * owning screen saves them.
 */
public final class RowsEditor extends LinearLayout {
    public interface RowCheck { String problem(JSONObject row); }
    public interface Changed { void changed(); }

    private final MainActivity a;
    private final String title;
    private final List<Field> fields;
    private final List<String[]> columns;   // field, header
    private final List<JSONObject> rows = new ArrayList<>();
    private final List<JSONObject> removed = new ArrayList<>();
    private final SheetView sheet;
    private final TextView info;
    private RowCheck check;
    private Changed changed;
    private boolean allowAdd = true, allowRemove = true;
    private JSONObject template;

    public RowsEditor(MainActivity a, String title, List<Field> fields, List<String[]> columns) {
        super(a);
        this.a = a; this.title = title; this.fields = fields; this.columns = columns;
        setOrientation(VERTICAL);
        LinearLayout bar = Ui.hbox(a);
        info = Ui.text(a, "", 11.5f, Ui.MUTED, false);
        bar.addView(info, Ui.weight(1));
        Button add = Ui.outline(a, "+ Add row", Ui.TEAL);
        add.setTextSize(12.5f);
        add.setOnClickListener(v -> { if (allowAdd) edit(-1); });
        bar.addView(add, new LayoutParams(Ui.dp(a, 116), Ui.dp(a, 42)));
        addView(bar, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        LinearLayout frame = Ui.vbox(a);
        frame.setBackground(Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 10, a));
        frame.setPadding(1, 1, 1, 1);
        frame.setClipToOutline(true);
        sheet = new SheetView(a);
        sheet.setMaxHeightDp(320);
        sheet.setOnRowClick(this::edit);
        frame.addView(sheet, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        LayoutParams lp = new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = Ui.dp(a, 4);
        addView(frame, lp);
        refresh();
    }

    public RowsEditor check(RowCheck c) { check = c; return this; }
    public RowsEditor onChanged(Changed c) { changed = c; return this; }
    public RowsEditor fixedRows() { allowAdd = false; allowRemove = false; return this; }
    /** Values copied into every new row (e.g. defaults). */
    public RowsEditor template(JSONObject t) { template = t; return this; }

    public void setRows(List<JSONObject> list) {
        rows.clear();
        removed.clear();
        rows.addAll(list);
        refresh();
    }

    public List<JSONObject> rows() { return rows; }
    /** Rows the user removed that already existed in the database (have an id). */
    public List<JSONObject> removedRows() { return removed; }

    private String display(JSONObject row, String field) {
        Field f = null;
        for (Field x : fields) if (x.key.equals(field)) f = x;
        Object v = row.opt(field);
        if (f != null && Field.LOOKUP.equals(f.type) && v != null && v != JSONObject.NULL) return Lookups.labelOf(f.lookup, String.valueOf(v));
        if (f != null && Field.SELECT.equals(f.type) && v != null && v != JSONObject.NULL) return f.optionLabel(String.valueOf(v));
        return Labels.cell(field, v, null);
    }

    public void refresh() {
        List<String> headers = new ArrayList<>();
        headers.add("#");
        for (String[] c : columns) headers.add(c[1]);
        List<String[]> data = new ArrayList<>();
        for (int i = 0; i < rows.size(); i++) {
            String[] line = new String[columns.size() + 1];
            line[0] = String.valueOf(i + 1);
            for (int c = 0; c < columns.size(); c++) line[c + 1] = display(rows.get(i), columns.get(c)[0]);
            data.add(line);
        }
        sheet.setData(headers, data);
        info.setText(title + " · " + rows.size() + " row(s) · tap a row to edit");
    }

    private void edit(int index) {
        JSONObject current = index >= 0 ? rows.get(index) : null;
        FormView form = new FormView(a, fields);
        if (current != null) form.setAll(current);
        else if (template != null) form.setAll(template);
        ScrollView sv = new ScrollView(a);
        LinearLayout pad = Ui.vbox(a);
        pad.setPadding(Ui.dp(a, 18), Ui.dp(a, 4), Ui.dp(a, 18), Ui.dp(a, 8));
        pad.addView(form);
        sv.addView(pad);
        AlertDialog.Builder b = new AlertDialog.Builder(a)
            .setTitle((index >= 0 ? "Row " + (index + 1) : "New row") + " · " + title)
            .setView(sv)
            .setPositiveButton("OK", null)
            .setNegativeButton("Back", null);
        if (index >= 0 && allowRemove) b.setNeutralButton("Remove row", (d, w) -> {
            JSONObject r = rows.remove(index);
            if (r.has("id") && !r.isNull("id")) removed.add(r);
            refresh();
            if (changed != null) changed.changed();
        });
        AlertDialog dialog = b.create();
        dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            String problem = form.validate();
            JSONObject values;
            try {
                values = form.json();
            } catch (Exception e) {
                problem = Api.message(e);
                values = null;
            }
            if (problem == null && values != null && check != null) problem = check.problem(values);
            if (problem != null) { a.toast(problem); return; }
            try {
                JSONObject target = current != null ? current : new JSONObject(template == null ? "{}" : template.toString());
                java.util.Iterator<String> it = values.keys();
                while (it.hasNext()) { String k = it.next(); target.put(k, values.opt(k)); }
                if (current == null) rows.add(target);
            } catch (Exception e) {
                a.toast(Api.message(e));
                return;
            }
            dialog.dismiss();
            refresh();
            if (changed != null) changed.changed();
        }));
        dialog.show();
    }
}
