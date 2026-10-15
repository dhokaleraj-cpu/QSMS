package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.graphics.Color;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Phone-friendly readings grid of an inspection report: the whole table in a SheetView (slide / pinch),
 * tap a characteristic to enter its sample readings, NA and remark in a dialog with a live OK / NG result
 * (Rules.evaluate = InspectionService.evaluate_characteristic). "Save & next" walks through the layout.
 *
 * Row keys: sequence_no, characteristic_no, characteristic, specification, lower_spec, upper_spec, unit,
 * checking_aid, characteristic_type, observations (JSONArray of text), applicability, result, remarks.
 */
final class InspReadings extends LinearLayout {
    interface Changed { void changed(); }

    private final MainActivity a;
    private final String title;
    private final String aidHeader;
    private final List<JSONObject> rows = new ArrayList<>();
    private final SheetView sheet;
    private final TextView info;
    private int samples = 1;
    private boolean editable = true;
    private Changed changed;

    InspReadings(MainActivity a, String title, String aidHeader) {
        super(a);
        this.a = a; this.title = title; this.aidHeader = aidHeader;
        setOrientation(VERTICAL);
        info = Ui.text(a, "", 11.5f, Ui.MUTED, false);
        addView(info, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        LinearLayout frame = Ui.vbox(a);
        frame.setBackground(Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 10, a));
        frame.setPadding(1, 1, 1, 1);
        frame.setClipToOutline(true);
        sheet = new SheetView(a);
        sheet.setMaxHeightDp(380);
        sheet.setOnRowClick(this::edit);
        frame.addView(sheet, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        addView(frame, Ui.matchWrap(a, 4));
        Button start = Ui.outline(a, "Enter readings (one characteristic after the other)", Ui.TEAL);
        start.setOnClickListener(v -> {
            if (rows.isEmpty()) { a.toast("No characteristics in this layout."); return; }
            int first = 0;
            for (int i = 0; i < rows.size(); i++) if (Rules.NOT_EVALUATED.equals(InspUtil.j(rows.get(i), "result"))) { first = i; break; }
            edit(first);
        });
        addView(start, Ui.matchWrap(a, 8));
        refresh();
    }

    void onChanged(Changed c) { changed = c; }
    void setEditable(boolean e) { editable = e; }
    List<JSONObject> rows() { return rows; }
    int samples() { return samples; }

    void setRows(List<JSONObject> list, int sampleCount) {
        rows.clear();
        rows.addAll(list);
        setSamples(sampleCount);
    }

    /** Pad / cut the observations to the report sample size (website _editor_frame) and re-evaluate. */
    void setSamples(int n) {
        samples = Math.max(1, n);
        for (JSONObject r : rows) {
            JSONArray obs = r.optJSONArray("observations");
            JSONArray out = new JSONArray();
            for (int i = 0; i < samples; i++) out.put(obs != null && i < obs.length() ? text(obs.opt(i)) : "");
            try { r.put("observations", out); } catch (Exception ignored) { }
            evaluate(r);
        }
        refresh();
    }

    static String text(Object v) {
        if (v == null || v == JSONObject.NULL) return "";
        String s = String.valueOf(v);
        return "null".equals(s) ? "" : s;
    }

    static List<String> readings(JSONObject r) {
        List<String> out = new ArrayList<>();
        JSONArray obs = r.optJSONArray("observations");
        for (int i = 0; obs != null && i < obs.length(); i++) out.add(text(obs.opt(i)));
        return out;
    }

    static boolean na(JSONObject r) { return "NOT_APPLICABLE".equals(InspUtil.j(r, "applicability")); }

    static void evaluate(JSONObject r) {
        String res = Rules.evaluate(InspUtil.j(r, "characteristic_type").isEmpty() ? "VARIABLE" : InspUtil.j(r, "characteristic_type"),
            InspUtil.j(r, "specification"), Rules.number(r.opt("lower_spec")), Rules.number(r.opt("upper_spec")), readings(r), na(r));
        try { r.put("result", res); } catch (Exception ignored) { }
    }

    void refresh() {
        List<String> headers = new ArrayList<>();
        headers.add("Sr No");
        headers.add("Parameter");
        headers.add("Specification");
        headers.add("Min");
        headers.add("Max");
        headers.add("Unit");
        headers.add(aidHeader);
        for (int i = 0; i < samples; i++) headers.add(samples == 1 ? "Actual Value" : "Actual " + (i + 1));
        headers.add("NA");
        headers.add("Result");
        headers.add("Remark");
        List<String[]> data = new ArrayList<>();
        int ok = 0, ng = 0, open = 0, naCount = 0;
        for (JSONObject r : rows) {
            List<String> line = new ArrayList<>();
            String sr = InspUtil.j(r, "characteristic_no");
            line.add(sr.isEmpty() ? InspUtil.j(r, "sequence_no") : sr);
            line.add(InspUtil.j(r, "characteristic"));
            line.add(InspUtil.j(r, "specification"));
            line.add(InspUtil.fmt(r.opt("lower_spec")));
            line.add(InspUtil.fmt(r.opt("upper_spec")));
            line.add(InspUtil.j(r, "unit"));
            line.add(InspUtil.j(r, "checking_aid"));
            List<String> obs = readings(r);
            for (int i = 0; i < samples; i++) line.add(i < obs.size() ? obs.get(i) : "");
            line.add(na(r) ? "NA" : "");
            String res = InspUtil.j(r, "result");
            line.add(Rules.shortLabel(res) + " · " + Ui.pretty(res));
            line.add(InspUtil.j(r, "remarks"));
            data.add(line.toArray(new String[0]));
            if (Rules.PASS.equals(res)) ok++; else if (Rules.FAIL.equals(res)) ng++; else if (Rules.NOT_APPLICABLE.equals(res)) naCount++; else open++;
        }
        sheet.setData(headers, data);
        info.setText(title + " · " + rows.size() + " characteristic(s) · OK " + ok + " · NG " + ng + " · NA " + naCount + " · not entered " + open
            + (editable ? " · tap a row to enter readings" : " · read only"));
    }

    private void edit(int index) {
        if (index < 0 || index >= rows.size()) return;
        JSONObject r = rows.get(index);
        String type = InspUtil.j(r, "characteristic_type").toUpperCase(Locale.ROOT);
        boolean textType = type.equals("TEXT") || type.equals("ATTRIBUTE");
        LinearLayout box = Ui.vbox(a);
        box.setPadding(Ui.dp(a, 18), Ui.dp(a, 4), Ui.dp(a, 18), Ui.dp(a, 8));
        String spec = InspUtil.j(r, "specification");
        String lo = InspUtil.fmt(r.opt("lower_spec")), hi = InspUtil.fmt(r.opt("upper_spec"));
        if (!spec.isEmpty()) box.addView(Ui.pair(a, "Specification", spec));
        if (!lo.isEmpty() || !hi.isEmpty()) box.addView(Ui.pair(a, "Min / Max", (lo.isEmpty() ? "-" : lo) + "  …  " + (hi.isEmpty() ? "-" : hi) + " " + InspUtil.j(r, "unit")));
        if (!InspUtil.j(r, "checking_aid").isEmpty()) box.addView(Ui.pair(a, aidHeader, InspUtil.j(r, "checking_aid")));
        box.addView(Ui.pair(a, "Type", textType ? "Text / attribute" : "Numeric"));
        TextView result = Ui.chip(a, "", "grey");
        List<EditText> inputs = new ArrayList<>();
        List<String> current = readings(r);
        CheckBox naBox = new CheckBox(a);
        Runnable live = () -> {
            List<String> vals = new ArrayList<>();
            for (EditText e : inputs) vals.add(e.getText().toString());
            String res = Rules.evaluate(type.isEmpty() ? "VARIABLE" : type, spec, Rules.number(r.opt("lower_spec")), Rules.number(r.opt("upper_spec")), vals, naBox.isChecked());
            result.setText(Rules.shortLabel(res) + " · " + Ui.pretty(res));
            String tone = Rules.tone(res);
            result.setTextColor("green".equals(tone) ? Ui.GREEN_FG : "red".equals(tone) ? Ui.RED_FG : "amber".equals(tone) ? Ui.AMBER_FG : Ui.GREY_FG);
            result.setBackground(Ui.round("green".equals(tone) ? Ui.GREEN_BG : "red".equals(tone) ? Ui.RED_BG : "amber".equals(tone) ? Ui.AMBER_BG : Ui.GREY_BG, 0, 0, 12, a));
        };
        TextWatcher watcher = new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
            @Override public void afterTextChanged(Editable e) { live.run(); }
        };
        for (int i = 0; i < samples; i++) {
            box.addView(Ui.label(a, samples == 1 ? "Actual Value" : "Actual " + (i + 1)));
            EditText e = Ui.input(a, textType ? "Observation" : "Reading", false);
            if (!textType) e.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL | InputType.TYPE_NUMBER_FLAG_SIGNED);
            e.setText(i < current.size() ? current.get(i) : "");
            e.setEnabled(editable);
            e.addTextChangedListener(watcher);
            inputs.add(e);
            box.addView(e, Ui.matchWrap(a, 0));
        }
        naBox.setText("Not applicable (NA)");
        naBox.setTextColor(Ui.TEXT);
        naBox.setChecked(na(r));
        naBox.setEnabled(editable);
        naBox.setOnCheckedChangeListener((b, on) -> live.run());
        box.addView(naBox, Ui.matchWrap(a, 8));
        box.addView(Ui.label(a, "Remark"));
        EditText remark = Ui.input(a, "Remark", false);
        remark.setText(InspUtil.j(r, "remarks"));
        remark.setEnabled(editable);
        box.addView(remark, Ui.matchWrap(a, 0));
        LinearLayout resRow = Ui.hbox(a);
        resRow.addView(Ui.text(a, "Result  ", 13, Ui.MUTED, false));
        resRow.addView(result);
        box.addView(resRow, Ui.matchWrap(a, 10));
        live.run();
        ScrollView sv = new ScrollView(a);
        sv.addView(box);
        String sr = InspUtil.j(r, "characteristic_no").isEmpty() ? InspUtil.j(r, "sequence_no") : InspUtil.j(r, "characteristic_no");
        AlertDialog.Builder b = new AlertDialog.Builder(a)
            .setTitle((index + 1) + "/" + rows.size() + " · " + sr + " · " + InspUtil.j(r, "characteristic"))
            .setView(sv)
            .setNegativeButton("Back", null);
        if (editable) {
            b.setPositiveButton("Save", (d, w) -> store(r, inputs, naBox, remark));
            if (index + 1 < rows.size()) b.setNeutralButton("Save & next ›", (d, w) -> { store(r, inputs, naBox, remark); edit(index + 1); });
        } else if (index + 1 < rows.size()) {
            b.setNeutralButton("Next ›", (d, w) -> edit(index + 1));
        }
        b.show();
    }

    private void store(JSONObject r, List<EditText> inputs, CheckBox naBox, EditText remark) {
        try {
            JSONArray obs = new JSONArray();
            for (EditText e : inputs) obs.put(e.getText().toString().trim());
            r.put("observations", obs);
            r.put("applicability", naBox.isChecked() ? "NOT_APPLICABLE" : "APPLICABLE");
            r.put("remarks", remark.getText().toString().trim());
            evaluate(r);
        } catch (Exception e) {
            a.toast(Api.message(e));
        }
        refresh();
        if (changed != null) changed.changed();
    }
}
