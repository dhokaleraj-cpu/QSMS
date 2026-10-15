package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.app.DatePickerDialog;
import android.graphics.Color;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Generic native form: text, number, date, yes/no, dropdown, searchable lookup, multi-select. */
public final class FormView extends LinearLayout {
    public interface Change { void changed(String key, Object value); }

    private final MainActivity a;
    private final Map<String, Field> fields = new LinkedHashMap<>();
    private final Map<String, View> inputs = new LinkedHashMap<>();
    private final Map<String, Object> values = new LinkedHashMap<>();
    private final Map<String, TextView> labels = new LinkedHashMap<>();
    private Change change;

    public FormView(MainActivity a, List<Field> list) {
        super(a);
        this.a = a;
        setOrientation(VERTICAL);
        for (Field f : list) add(f);
    }

    public void onChange(Change c) { change = c; }

    public void add(Field f) {
        fields.put(f.key, f);
        TextView label = Ui.label(a, f.label + (f.required ? " *" : ""));
        labels.put(f.key, label);
        addView(label);
        View input = build(f);
        inputs.put(f.key, input);
        addView(input, Ui.matchWrap(a, 0));
        if (f.hint != null && !f.hint.isEmpty() && !Field.INFO.equals(f.type)) {
            TextView h = Ui.text(a, f.hint, 11, Ui.MUTED, false);
            h.setPadding(Ui.dp(a, 2), Ui.dp(a, 2), 0, 0);
            addView(h);
        }
        if (f.def != null) set(f.key, f.def);
    }

    public Field field(String key) { return fields.get(key); }

    public void setVisible(String key, boolean visible) {
        int v = visible ? View.VISIBLE : View.GONE;
        if (inputs.containsKey(key)) inputs.get(key).setVisibility(v);
        if (labels.containsKey(key)) labels.get(key).setVisibility(v);
    }

    private View build(Field f) {
        switch (f.type) {
            case Field.BOOL: {
                CheckBox cb = new CheckBox(a);
                cb.setText(f.hint == null || f.hint.isEmpty() ? "Yes" : f.hint);
                cb.setTextColor(Ui.TEXT);
                cb.setEnabled(!f.readOnly);
                cb.setOnCheckedChangeListener((b, on) -> { values.put(f.key, on); fire(f.key, on); });
                values.put(f.key, false);
                return cb;
            }
            case Field.INFO: {
                TextView t = Ui.text(a, "-", 14, Ui.TEXT, true);
                t.setPadding(Ui.dp(a, 12), Ui.dp(a, 10), Ui.dp(a, 12), Ui.dp(a, 10));
                t.setBackground(Ui.round(Color.parseColor("#F3F7F7"), Ui.LINE, 1, 10, a));
                return t;
            }
            case Field.DATE:
            case Field.SELECT:
            case Field.LOOKUP:
            case Field.MULTI: {
                TextView t = Ui.text(a, "Select…", 14.5f, Ui.MUTED, false);
                t.setPadding(Ui.dp(a, 12), Ui.dp(a, 12), Ui.dp(a, 12), Ui.dp(a, 12));
                t.setBackground(Ui.round(f.readOnly ? Color.parseColor("#F3F7F7") : Color.WHITE, Ui.LINE_STRONG, 1, 10, a));
                if (!f.readOnly) t.setOnClickListener(v -> open(f));
                return t;
            }
            default: {
                EditText e = Ui.input(a, f.hint == null || f.hint.isEmpty() ? f.label : f.hint, false);
                if (Field.AREA.equals(f.type)) {
                    e.setSingleLine(false);
                    e.setMinLines(3);
                    e.setGravity(Gravity.TOP | Gravity.START);
                    e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
                } else if (Field.INT.equals(f.type)) {
                    e.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_SIGNED);
                } else if (Field.NUM.equals(f.type)) {
                    e.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL | InputType.TYPE_NUMBER_FLAG_SIGNED);
                }
                e.setEnabled(!f.readOnly);
                e.addTextChangedListener(new TextWatcher() {
                    @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
                    @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
                    @Override public void afterTextChanged(Editable ed) {
                        values.put(f.key, ed.toString());
                        fire(f.key, ed.toString());
                    }
                });
                return e;
            }
        }
    }

    private void fire(String key, Object value) {
        if (change != null) change.changed(key, value);
    }

    // ------------------------------------------------------------------ pickers
    private void open(Field f) {
        if (Field.DATE.equals(f.type)) {
            LocalDate d;
            try { d = LocalDate.parse(String.valueOf(values.get(f.key)).substring(0, 10)); } catch (Exception e) { d = LocalDate.now(); }
            DatePickerDialog dialog = new DatePickerDialog(a, (view, y, m, day) -> set(f.key, LocalDate.of(y, m + 1, day).toString()), d.getYear(), d.getMonthValue() - 1, d.getDayOfMonth());
            dialog.setButton(DatePickerDialog.BUTTON_NEUTRAL, "Clear", (dlg, w) -> set(f.key, null));
            dialog.show();
            return;
        }
        if (Field.SELECT.equals(f.type)) {
            List<String> ids = new ArrayList<>();
            List<String> names = new ArrayList<>();
            if (!f.required) { ids.add(""); names.add("— none —"); }
            for (String o : f.options) { ids.add(o); names.add(f.optionLabel(o)); }
            choose(f.label, ids, names, id -> set(f.key, id.isEmpty() ? null : id));
            return;
        }
        if (Field.MULTI.equals(f.type)) {
            boolean[] checked = new boolean[f.options.length];
            Object cur = values.get(f.key);
            String curText = cur == null ? "" : cur.toString();
            String[] names = new String[f.options.length];
            for (int i = 0; i < f.options.length; i++) {
                names[i] = f.optionLabel(f.options[i]);
                checked[i] = curText.contains("\"" + f.options[i] + "\"");
            }
            new AlertDialog.Builder(a).setTitle(f.label)
                .setMultiChoiceItems(names, checked, (d, i, on) -> checked[i] = on)
                .setPositiveButton("OK", (d, w) -> {
                    JSONArray arr = new JSONArray();
                    for (int i = 0; i < checked.length; i++) if (checked[i]) arr.put(f.options[i]);
                    set(f.key, arr);
                })
                .setNegativeButton("Back", null).show();
            return;
        }
        // LOOKUP
        TextView t = (TextView) inputs.get(f.key);
        t.setText("Loading…");
        Api api = Api.get(a);
        Api.async(() -> Lookups.rows(api, f.lookup), (rows, err) -> {
            setLabel(f, values.get(f.key));
            if (err != null) { a.toast(Api.message(err)); return; }
            List<String> ids = new ArrayList<>();
            List<String> names = new ArrayList<>();
            if (!f.required) { ids.add(""); names.add("— none —"); }
            for (int i = 0; i < rows.length(); i++) {
                JSONObject r = rows.optJSONObject(i);
                if (r == null) continue;
                ids.add(r.optString("id"));
                names.add(f.lookup.label.of(r));
            }
            choose(f.label, ids, names, id -> set(f.key, id.isEmpty() ? null : id));
        });
    }

    interface Picked { void id(String id); }

    /** Searchable list dialog. */
    void choose(String title, List<String> ids, List<String> names, Picked picked) {
        LinearLayout box = Ui.vbox(a);
        int p = Ui.dp(a, 14);
        box.setPadding(p, Ui.dp(a, 6), p, 0);
        EditText search = Ui.input(a, "Search…", false);
        box.addView(search, Ui.matchWrap(a, 0));
        ListView list = new ListView(a);
        List<String> shown = new ArrayList<>(names);
        List<String> shownIds = new ArrayList<>(ids);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(a, android.R.layout.simple_list_item_1, shown);
        list.setAdapter(adapter);
        box.addView(list, new LayoutParams(LayoutParams.MATCH_PARENT, Ui.dp(a, 380)));
        AlertDialog dialog = new AlertDialog.Builder(a).setTitle(title).setView(box).setNegativeButton("Back", null).create();
        list.setOnItemClickListener((parent, view, pos, id) -> {
            dialog.dismiss();
            picked.id(shownIds.get(pos));
        });
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
            @Override public void afterTextChanged(Editable e) {
                String q = e.toString().trim().toLowerCase(Locale.ROOT);
                shown.clear(); shownIds.clear();
                for (int i = 0; i < names.size(); i++) {
                    if (q.isEmpty() || names.get(i).toLowerCase(Locale.ROOT).contains(q)) { shown.add(names.get(i)); shownIds.add(ids.get(i)); }
                }
                adapter.notifyDataSetChanged();
            }
        });
        dialog.show();
    }

    private void setLabel(Field f, Object v) {
        View input = inputs.get(f.key);
        if (!(input instanceof TextView) || input instanceof EditText) return;
        TextView t = (TextView) input;
        String text;
        if (v == null || v == JSONObject.NULL || String.valueOf(v).isEmpty()) {
            text = Field.INFO.equals(f.type) ? "-" : "Select…";
            t.setTextColor(Field.INFO.equals(f.type) ? Ui.TEXT : Ui.MUTED);
        } else {
            switch (f.type) {
                case Field.DATE: text = Ui.date(String.valueOf(v)); break;
                case Field.SELECT: text = f.optionLabel(String.valueOf(v)); break;
                case Field.LOOKUP: text = Lookups.labelOf(f.lookup, String.valueOf(v)); break;
                case Field.MULTI: {
                    StringBuilder b = new StringBuilder();
                    JSONArray arr = v instanceof JSONArray ? (JSONArray) v : parseArray(String.valueOf(v));
                    for (int i = 0; i < arr.length(); i++) { if (b.length() > 0) b.append(", "); b.append(f.optionLabel(arr.optString(i))); }
                    text = b.length() == 0 ? "Select…" : b.toString();
                    break;
                }
                default: text = String.valueOf(v);
            }
            t.setTextColor(Ui.TEXT);
        }
        t.setText(text);
    }

    private static JSONArray parseArray(String s) {
        try { return new JSONArray(s); } catch (Exception e) { return new JSONArray(); }
    }

    // ------------------------------------------------------------------ values
    public void set(String key, Object v) {
        Field f = fields.get(key);
        if (f == null) return;
        if (v == JSONObject.NULL) v = null;
        View input = inputs.get(key);
        if (input instanceof CheckBox) {
            boolean on = v instanceof Boolean ? (Boolean) v : "true".equalsIgnoreCase(String.valueOf(v));
            ((CheckBox) input).setChecked(on);
            values.put(key, on);
            return;
        }
        if (input instanceof EditText) {
            String s = v == null ? "" : String.valueOf(v);
            if (v instanceof Double && Math.abs((Double) v - Math.rint((Double) v)) < 1e-9 && !Field.NUM.equals(f.type)) s = String.valueOf(Math.round((Double) v));
            ((EditText) input).setText(s);
            values.put(key, s);
            return;
        }
        values.put(key, v);
        if (Field.LOOKUP.equals(f.type) && v != null) {
            // make sure the label is known (cache may be cold)
            Api api = Api.get(a);
            Api.async(() -> Lookups.rows(api, f.lookup), (rows, err) -> setLabel(f, values.get(key)));
        }
        setLabel(f, v);
        fire(key, v);
    }

    public void setAll(JSONObject row) {
        if (row == null) return;
        for (String k : fields.keySet()) if (row.has(k)) set(k, row.opt(k));
    }

    public String str(String key) {
        Object v = values.get(key);
        return v == null || v == JSONObject.NULL ? "" : String.valueOf(v).trim();
    }

    public Double num(String key) {
        String s = str(key);
        if (s.isEmpty()) return null;
        try { return Double.parseDouble(s.replace(",", "")); } catch (NumberFormatException e) { return null; }
    }

    public boolean bool(String key) {
        Object v = values.get(key);
        return v instanceof Boolean ? (Boolean) v : "true".equalsIgnoreCase(String.valueOf(v));
    }

    /** Values as JSON (empty → null, numbers parsed), ready for Api.insert/update. */
    public JSONObject json() throws Exception {
        JSONObject o = new JSONObject();
        for (Field f : fields.values()) {
            if (Field.INFO.equals(f.type)) continue;
            Object v = values.get(f.key);
            String s = v == null ? "" : String.valueOf(v).trim();
            switch (f.type) {
                case Field.BOOL: o.put(f.key, bool(f.key)); break;
                case Field.INT: o.put(f.key, s.isEmpty() ? JSONObject.NULL : (Object) Long.parseLong(s.replace(",", "").replaceAll("\\.0+$", ""))); break;
                case Field.NUM: o.put(f.key, s.isEmpty() ? JSONObject.NULL : (Object) Double.parseDouble(s.replace(",", ""))); break;
                case Field.MULTI: o.put(f.key, v instanceof JSONArray ? v : (s.isEmpty() ? new JSONArray() : parseArray(s))); break;
                default: o.put(f.key, s.isEmpty() ? JSONObject.NULL : s);
            }
        }
        return o;
    }

    /** First problem, or null when the form is complete. */
    public String validate() {
        for (Field f : fields.values()) {
            View input = inputs.get(f.key);
            if (input != null && input.getVisibility() != View.VISIBLE) continue;
            String s = str(f.key);
            if (f.required && !Field.BOOL.equals(f.type) && (s.isEmpty() || "[]".equals(s))) return f.label + " is required.";
            if ((Field.INT.equals(f.type) || Field.NUM.equals(f.type)) && !s.isEmpty()) {
                Double n = num(f.key);
                if (n == null) return f.label + ": enter a number.";
                if (!Double.isNaN(f.min) && n < f.min) return f.label + " must be at least " + Ui.num(f.min, 3) + ".";
                if (!Double.isNaN(f.max) && n > f.max) return f.label + " must be at most " + Ui.num(f.max, 3) + ".";
            }
        }
        return null;
    }
}
