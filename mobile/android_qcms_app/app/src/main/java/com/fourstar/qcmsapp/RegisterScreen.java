package com.fourstar.qcmsapp;

import android.content.Intent;
import android.graphics.Color;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Register of one module: search, status filter and a spreadsheet grid (slide ↔ ↕, pinch, frozen panes). */
public final class RegisterScreen extends Screen implements ExportDoc.Source {
    private final Module m;
    private JSONArray rows = new JSONArray();
    private Map<String, Map<String, String>> fk = new HashMap<>();
    private String status = "";
    private String query = "";
    private SheetView sheet;
    private TextView info;
    private final List<JSONObject> shown = new ArrayList<>();
    private boolean wildcard = false;
    private final List<TextView> chipViews = new ArrayList<>();

    private void paintChips() {
        for (TextView chip : chipViews) {
            boolean on = status.equals(chip.getTag());
            chip.setTextColor(on ? Color.WHITE : Ui.TEXT);
            chip.setBackground(on ? Ui.round(Ui.TEAL, 0, 0, 16, a) : Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 16, a));
        }
    }

    public RegisterScreen(MainActivity a, Module m) { super(a); this.m = m; }

    @Override public String title() { return m.title; }
    @Override public String subtitle() { return m.description.isEmpty() ? m.section : m.description; }
    @Override public int tab() { return m.tab; }

    @Override
    public View build() {
        LinearLayout root = Ui.vbox(a);
        root.setPadding(dp(10), dp(8), dp(10), dp(6));
        chipViews.clear();

        LinearLayout tools = Ui.hbox(a);
        EditText search = Ui.input(a, "Search " + m.title.toLowerCase(Locale.ROOT) + "…", false);
        search.setText(query);
        tools.addView(search, Ui.weight(1));
        if (m.canCreate() && m.editable) {
            Button add = Ui.primary(a, "+ New");
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(92), dp(48));
            lp.leftMargin = dp(8);
            tools.addView(add, lp);
            add.setOnClickListener(v -> a.push(EditScreen.open(a, m, null, null)));
        }
        root.addView(tools, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        if (m.statusFilters.length > 0) {
            HorizontalScrollView hs = new HorizontalScrollView(a);
            hs.setHorizontalScrollBarEnabled(false);
            LinearLayout chips = Ui.hbox(a);
            List<String> options = new ArrayList<>();
            options.add("");
            for (String s : m.statusFilters) options.add(s);
            for (String s : options) {
                boolean on = s.equals(status);
                TextView chip = Ui.text(a, s.isEmpty() ? "All" : Ui.pretty(s), 12, on ? Color.WHITE : Ui.TEXT, on);
                chip.setPadding(dp(12), dp(7), dp(12), dp(7));
                chip.setBackground(on ? Ui.round(Ui.TEAL, 0, 0, 16, a) : Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 16, a));
                chip.setTag(s);
                chipViews.add(chip);
                chip.setOnClickListener(v -> { status = s; paintChips(); fill(); });
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
                lp.rightMargin = dp(6);
                chips.addView(chip, lp);
            }
            hs.addView(chips);
            root.addView(hs, Ui.matchWrap(a, 8));
        }

        LinearLayout bar = Ui.hbox(a);
        info = Ui.text(a, "Loading…", 11.5f, Ui.MUTED, false);
        bar.addView(info, Ui.weight(1));
        TextView share = Ui.text(a, "⇩ PDF · Excel · Print · Email", 12, Ui.TEAL_DARK, true);
        share.setPadding(dp(8), dp(6), dp(4), dp(6));
        share.setOnClickListener(v -> ExportKit.show(a, this, null));
        bar.addView(share);
        root.addView(bar, Ui.matchWrap(a, 6));

        LinearLayout frame = Ui.vbox(a);
        frame.setBackground(Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 10, a));
        frame.setPadding(1, 1, 1, 1);
        frame.setClipToOutline(true);
        sheet = new SheetView(a);
        sheet.setOnRowClick(this::openRow);
        frame.addView(sheet, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        LinearLayout.LayoutParams flp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1);
        flp.topMargin = dp(4);
        root.addView(frame, flp);

        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
            @Override public void afterTextChanged(Editable e) { query = e.toString().trim(); fill(); }
        });
        load();
        return root;
    }

    private String path(boolean all) {
        String select = all ? "*" : m.selectList();
        String order = m.order == null || m.order.isEmpty() ? "" : "&order=" + m.order;
        return m.table + "?select=" + select + m.filter + order + "&limit=3000";
    }

    private void load() {
        Api.async(() -> {
            JSONArray data;
            try {
                data = api.rows(path(wildcard));
            } catch (Api.ApiException e) {
                if (e.status != 400 || wildcard) throw e;
                wildcard = true;   // a column of this register is not in this database version - show everything
                data = api.rows(path(true));
            }
            List<String> cols = new ArrayList<>();
            for (String[] c : m.cols) cols.add(c[0]);
            fk = Labels.resolve(api, m.table, data, cols);
            return data;
        }, (data, err) -> {
            if (err != null) {
                info.setText(Api.message(err));
                info.setTextColor(Ui.RED_FG);
                if (err instanceof Api.ApiException && ((Api.ApiException) err).status == 401) a.sessionExpired();
                return;
            }
            rows = data;
            fill();
        });
    }

    private String cell(JSONObject r, String[] col) {
        String field = col[0];
        Object v = r.opt(field);
        if ("money".equals(col[2])) return Ui.money(r.optDouble(field, 0), r.optString("currency", "INR"));
        return Labels.cell(field, v, fk.get(field));
    }

    private void fill() {
        if (sheet == null) return;
        String q = query.toLowerCase(Locale.ROOT);
        List<String> headers = new ArrayList<>();
        for (String[] c : m.cols) headers.add(c[1]);
        List<String[]> data = new ArrayList<>();
        shown.clear();
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.optJSONObject(i);
            if (r == null) continue;
            if (!status.isEmpty() && !status.equalsIgnoreCase(Lookups.j(r, m.statusField))) continue;
            String[] line = new String[m.cols.size()];
            StringBuilder hay = new StringBuilder();
            for (int c = 0; c < m.cols.size(); c++) {
                line[c] = cell(r, m.cols.get(c));
                hay.append(line[c]).append(' ');
            }
            if (!q.isEmpty() && !hay.toString().toLowerCase(Locale.ROOT).contains(q)) continue;
            data.add(line);
            shown.add(r);
        }
        sheet.setData(headers, data);
        info.setText(data.size() + (data.size() == rows.length() ? "" : " of " + rows.length()) + " record(s) · slide ↔ ↕ · pinch to zoom · tap a row to open"
            + (api.lastCallOffline ? " · OFFLINE (saved copy)" : ""));
    }

    private void openRow(int index) {
        if (index < 0 || index >= shown.size() || m.idField.isEmpty()) return;
        String id = Lookups.j(shown.get(index), m.idField);
        if (id.isEmpty()) return;
        a.push(new RecordScreen(a, m, id));
    }

    private void shareCsv() {
        StringBuilder csv = new StringBuilder();
        for (int c = 0; c < m.cols.size(); c++) { if (c > 0) csv.append(','); csv.append(q(m.cols.get(c)[1])); }
        csv.append('\n');
        for (JSONObject r : shown) {
            for (int c = 0; c < m.cols.size(); c++) { if (c > 0) csv.append(','); csv.append(q(cell(r, m.cols.get(c)))); }
            csv.append('\n');
        }
        Intent send = new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_SUBJECT, "QCMS " + m.title);
        send.putExtra(Intent.EXTRA_TEXT, csv.toString());
        try { a.startActivity(Intent.createChooser(send, "Share " + m.title)); } catch (Exception e) { a.toast("No app to share with."); }
    }

    /** Register as shown (status chip + search applied): all columns, all filtered rows. */
    @Override
    public ExportDoc export() {
        List<String> headers = new ArrayList<>();
        for (String[] c : m.cols) headers.add(c[1]);
        List<List<String>> data = new ArrayList<>();
        for (JSONObject r : new ArrayList<>(shown)) {
            List<String> line = new ArrayList<>();
            for (String[] c : m.cols) line.add(cell(r, c));
            data.add(line);
        }
        String filters = (status.isEmpty() ? "" : "Status " + Ui.pretty(status)) + (query.isEmpty() ? "" : (status.isEmpty() ? "" : " · ") + "Search \"" + query + "\"");
        ExportDoc doc = new ExportDoc(m.title + " Register").subtitle(filters.isEmpty() ? m.section : m.section + " · " + filters).file("QCMS_" + m.title + "_Register");
        doc.table(m.title, headers, data);
        return doc;
    }

    private static String q(String s) {
        String v = s == null ? "" : s;
        return v.contains(",") || v.contains("\"") || v.contains("\n") ? "\"" + v.replace("\"", "\"\"") + "\"" : v;
    }

    @Override public void reload() { load(); }
}
