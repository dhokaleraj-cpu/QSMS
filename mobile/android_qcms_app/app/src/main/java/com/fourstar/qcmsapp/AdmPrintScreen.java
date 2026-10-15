package com.fourstar.qcmsapp;

import android.graphics.Color;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;

/**
 * Native port of app_pages/print_designer.py: design selector, colours (preset swatches + hex), heading style,
 * PO section defaults, title / company / footer texts, heading renames, save + version restore.
 * The website's sample-PDF preview is replaced by a small style preview drawn with views.
 */
public final class AdmPrintScreen extends Screen {
    /** Unsaved edits per document (like the website's session state). */
    private static final Map<String, JSONObject> SESSION = new HashMap<>();
    private static String doc = "PURCHASE_ORDER";

    static final String[] PALETTE = {"#0B6E70", "#0F8B8D", "#334155", "#1E3A8A", "#000000", "#9A3412", "#166534", "#991B1B",
        "#C9D6D6", "#CBD5E1", "#9AA5A5", "#EAF4F4", "#F3F8F8", "#F1F5F9", "#FFF7ED", "#FFFFFF"};

    private JSONObject layout;
    private List<JSONObject> history = new ArrayList<>();
    private LinearLayout preview;
    private boolean admin;

    public AdmPrintScreen(MainActivity a) { super(a); }

    @Override public String title() { return "Print Layout Designer"; }
    @Override public String subtitle() { return "Design, colours, headings, sections and texts of every QCMS print"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        admin = api.isAdmin();
        page.addView(loading());
        final String d = doc;
        Api.async(() -> {
            JSONObject l = SESSION.containsKey(d) ? SESSION.get(d) : AdmPrint.read(api, d);
            return new Object[]{l, AdmPrint.history(api, d)};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { add(error(err, this::reload)); return; }
            layout = (JSONObject) res[0];
            SESSION.put(d, layout);
            @SuppressWarnings("unchecked") List<JSONObject> h = (List<JSONObject>) res[1];
            history = h;
            render();
        });
        return scroll;
    }

    private void put(String key, Object value) {
        try { layout.put(key, value); } catch (Exception ignored) { }
        refreshPreview();
    }

    private void render() {
        boolean po = "PURCHASE_ORDER".equals(doc);
        if (!admin) add(AdmUi.note(a, "View only — only the QCMS System Administrator can save print layouts.", "teal"), 2);
        List<String> docs = new ArrayList<>(), docLabels = new ArrayList<>();
        for (String[] x : AdmPrint.DOCUMENTS) { docs.add(x[0]); docLabels.add(x[1]); }
        AdmUi.choice(a, page, "Document", docs, docLabels, doc, v -> { doc = v; a.rebuild(); });

        LinearLayout sa = AdmUi.section(a, page, "A", "DESIGN SELECTOR", "");
        String cur = layout.optString("preset", "B5");
        AdmUi.radio(a, sa, "Design", AdmPrint.PRESET_NAMES, AdmPrint.isPreset(cur) ? cur : "B1", true, v -> {
            if (!v.equals(layout.optString("preset"))) {
                layout = AdmPrint.withPreset(doc, layout, v);
                SESSION.put(doc, layout);
                a.rebuild();
            }
        });

        LinearLayout sb = AdmUi.section(a, page, "B", "COLOURS & STYLE", "Tap a swatch or type a hex colour (#RRGGBB).");
        colour(sb, "Heading colour", "accent", layout.optString("accent"));
        colour(sb, "Table lines", "rule", layout.optString("rule"));
        colour(sb, "Remarks text", "remark", layout.optString("remark"));
        String concl = layout.optString("conclusion", "");
        colour(sb, "Conclusion text", "conclusion", concl.isEmpty() ? "#166534" : concl);
        AdmUi.radio(a, sb, "Heading style", AdmPrint.BAR_STYLES, layout.optString("bar", "fill"), true, v -> put("bar", v));
        if (po) {
            String[][] fills = {{"head_fill", "Table header fill"}, {"label_fill", "Label cell fill"}, {"remark_fill", "Remarks box fill"}};
            for (String[] f : fills) fill(sb, f[1], f[0]);
        } else {
            decimal(sb, "Body text size (pt) · 7.0 – 12.0", "body_pt", layout.optDouble("body_pt", 8.6), 7.0, 12.0);
            decimal(sb, "Heading size (pt) · 8.0 – 14.0", "heading_pt", layout.optDouble("heading_pt", 10.5), 8.0, 14.0);
        }

        LinearLayout sc = AdmUi.section(a, page, "C", "TITLE, COMPANY & FOOTER", "");
        if (po) {
            String t = layout.optString("title", "");
            text(sc, "Document title", "title", t.isEmpty() ? "PURCHASE ORDER" : t, "PURCHASE ORDER");
        }
        text(sc, "Company name on print" + (po ? " (signatory)" : " (header)"), "company_name", layout.optString("company_name", ""), "Leave blank for the default");
        text(sc, "Footer text", "footer_text", layout.optString("footer_text", ""), "Leave blank for the default");

        if (po) {
            LinearLayout sd = AdmUi.section(a, page, "D", "SECTIONS SHOWN ON PRINT", "These are the defaults. Each PO can still tick / untick sections in PO Entry, Order List, Edit PO, PO PDF and every PO email.");
            for (String[] o : AdmPrint.SECTION_OPTIONS) {
                CheckBox c = AdmUi.check(a, o[1], layout.optBoolean(o[0], true));
                c.setOnCheckedChangeListener((b, on) -> put(o[0], on));
                sd.addView(c, Ui.matchWrap(a, 2));
            }
        }

        renderHeadings(po);

        LinearLayout pv = AdmUi.section(a, page, "", "STYLE PREVIEW (sample data)", "Colours and heading style as they appear on the print. The full sample PDF preview is available on the website.");
        preview = Ui.vbox(a);
        pv.addView(preview, Ui.matchWrap(a, 6));
        refreshPreview();

        LinearLayout save = AdmUi.section(a, page, "", "SAVE", "");
        Button sv = AdmUi.primary(a, save, "Save layout", v -> {
            Button b = (Button) v;
            AdmUi.enable(b, false);
            final String d = doc;
            JSONObject current = layout;
            Api.async(() -> AdmPrint.save(api, d, current), (clean, err) -> {
                AdmUi.enable(b, true);
                if (err != null) { a.toast("Could not save: " + Api.message(err)); return; }
                SESSION.put(d, clean);
                a.toast(AdmPrint.docLabel(d) + " layout saved. All new prints use it now.");
                a.rebuild();
            });
        });
        AdmUi.enable(sv, admin);
        Button reset = AdmUi.outline(a, save, "Reset to approved default", v -> {
            SESSION.put(doc, AdmPrint.defaultLayout(doc));
            a.rebuild();
        });
        AdmUi.enable(reset, admin);
        AdmUi.outline(a, save, "Export layout (JSON)", v -> {
            String json;
            try { json = layout.toString(2); } catch (Exception e) { json = layout.toString(); }
            AdmUi.share(a, "QCMS_" + doc + "_layout.json", json);
        });

        LinearLayout hs = AdmUi.section(a, page, "", "LAYOUT VERSIONS", "Restore an earlier layout (loaded into the editor; tap Save layout to make it active).");
        if (history.isEmpty()) hs.addView(Ui.text(a, "No saved versions yet.", 12, Ui.MUTED, false));
        for (JSONObject row : history) {
            LinearLayout line = Ui.hbox(a);
            line.setGravity(Gravity.CENTER_VERTICAL);
            String when = AdmPy.j(row, "updated_at").isEmpty() ? AdmPy.j(row, "created_at") : AdmPy.j(row, "updated_at");
            when = when.length() > 16 ? when.substring(0, 16) : when;
            line.addView(Ui.text(a, when.replace('T', ' ') + " · " + AdmPy.j(row, "status"), 12.5f, Ui.TEXT, true), Ui.weight(1));
            Button load = Ui.outline(a, "Load", Ui.TEAL);
            AdmUi.enable(load, admin);
            load.setOnClickListener(v -> {
                SESSION.put(doc, AdmPrint.normalize(doc, AdmPrint.parse(AdmPy.j(row, "value_text"))));
                a.toast("Version loaded into the editor. Tap Save layout to make it active.");
                a.rebuild();
            });
            line.addView(load);
            hs.addView(line, Ui.matchWrap(a, 6));
        }
    }

    // ------------------------------------------------------------------ headings
    private void renderHeadings(boolean po) {
        LinearLayout se = AdmUi.section(a, page, "E", "RENAME HEADINGS", "Leave New heading blank to keep the original.");
        List<String> headings = new ArrayList<>();
        if (po) {
            for (String[] s : AdmPrint.PO_SECTIONS) headings.add(s[0]);
            for (String h : AdmPrint.PO_EXTRA_HEADINGS) headings.add(h);
        } else {
            String[] r = AdmPrint.REPORT_HEADINGS.get(doc);
            if (r != null) for (String h : r) headings.add(h);
        }
        JSONObject labels = layout.optJSONObject("labels");
        if (labels == null) labels = new JSONObject();
        LinkedHashSet<String> all = new LinkedHashSet<>(headings);
        for (Iterator<String> it = labels.keys(); it.hasNext(); ) all.add(it.next());
        List<EditText[]> rows = new ArrayList<>();
        LinearLayout list = Ui.vbox(a);
        se.addView(list);
        for (String h : all) addHeadingRow(list, rows, h, labels.optString(h, ""), false);
        AdmUi.outline(a, se, "+ Add heading", v -> addHeadingRow(list, rows, "", "", true));
    }

    /** Renamed headings from the editor rows (website: rows with both texts, "None" ignored). */
    private void applyLabels(List<EditText[]> rows) {
        JSONObject out = new JSONObject();
        for (EditText[] r : rows) {
            String o = AdmUi.text(r[0]).trim(), n = AdmUi.text(r[1]).trim();
            if (!o.isEmpty() && !n.isEmpty() && !"None".equals(n)) { try { out.put(o, n); } catch (Exception ignored) { } }
        }
        put("labels", out);
    }

    private void addHeadingRow(LinearLayout list, List<EditText[]> rows, String original, String renamed, boolean editableOriginal) {
        LinearLayout card = Ui.vbox(a);
        card.setBackground(Ui.round(Color.WHITE, Ui.LINE, 1, 10, a));
        card.setPadding(dp(10), dp(6), dp(10), dp(8));
        EditText o = Ui.input(a, "Original heading", false);
        o.setText(original);
        if (!editableOriginal) {
            card.addView(Ui.text(a, original, 12.5f, Ui.TEXT, true));
        } else {
            card.addView(o, Ui.matchWrap(a, 0));
        }
        EditText n = Ui.input(a, "New heading (blank = keep original)", false);
        n.setText(renamed);
        card.addView(n, Ui.matchWrap(a, 4));
        rows.add(new EditText[]{o, n});
        list.addView(card, Ui.matchWrap(a, 6));
        o.addTextChangedListener(watcher(t -> applyLabels(rows)));
        n.addTextChangedListener(watcher(t -> applyLabels(rows)));
    }

    // ------------------------------------------------------------------ inputs
    private void colour(LinearLayout box, String label, String key, String value) {
        box.addView(Ui.label(a, label));
        LinearLayout row = Ui.hbox(a);
        row.setGravity(Gravity.CENTER_VERTICAL);
        TextView sw = new TextView(a);
        sw.setBackground(Ui.round(parse(value, Color.WHITE), Ui.LINE_STRONG, 1, 8, a));
        row.addView(sw, new LinearLayout.LayoutParams(dp(40), dp(40)));
        EditText hex = Ui.input(a, "#RRGGBB", false);
        hex.setText(value);
        LinearLayout.LayoutParams lp = Ui.weight(1);
        lp.leftMargin = dp(8);
        row.addView(hex, lp);
        box.addView(row, Ui.matchWrap(a, 0));
        box.addView(palette(v -> hex.setText(v)), Ui.matchWrap(a, 4));
        hex.addTextChangedListener(watcher(t -> {
            String v = t.trim();
            if (AdmPrint.hex(v)) {
                sw.setBackground(Ui.round(parse(v, Color.WHITE), Ui.LINE_STRONG, 1, 8, a));
                hex.setError(null);
                put(key, v.toUpperCase(java.util.Locale.ROOT));
            } else {
                hex.setError("Use #RRGGBB");
            }
        }));
    }

    private void fill(LinearLayout box, String label, String key) {
        String cur = layout.optString(key, "");
        CheckBox use = AdmUi.check(a, label, !cur.isEmpty());
        box.addView(use, Ui.matchWrap(a, 8));
        LinearLayout holder = Ui.vbox(a);
        box.addView(holder);
        final String[] last = {cur.isEmpty() ? "#F3F8F8" : cur};
        Runnable draw = () -> {
            holder.removeAllViews();
            if (!use.isChecked()) return;
            LinearLayout inner = Ui.vbox(a);
            holder.addView(inner);
            colourInto(inner, label + " colour", key, last);
        };
        use.setOnCheckedChangeListener((b, on) -> { put(key, on ? last[0] : ""); draw.run(); });
        draw.run();
    }

    private void colourInto(LinearLayout box, String label, String key, String[] last) {
        box.addView(Ui.text(a, label, 11.5f, Ui.MUTED, false));
        LinearLayout row = Ui.hbox(a);
        row.setGravity(Gravity.CENTER_VERTICAL);
        TextView sw = new TextView(a);
        sw.setBackground(Ui.round(parse(last[0], Color.WHITE), Ui.LINE_STRONG, 1, 8, a));
        row.addView(sw, new LinearLayout.LayoutParams(dp(40), dp(40)));
        EditText hex = Ui.input(a, "#RRGGBB", false);
        hex.setText(last[0]);
        LinearLayout.LayoutParams lp = Ui.weight(1);
        lp.leftMargin = dp(8);
        row.addView(hex, lp);
        box.addView(row, Ui.matchWrap(a, 0));
        box.addView(palette(v -> hex.setText(v)), Ui.matchWrap(a, 4));
        hex.addTextChangedListener(watcher(t -> {
            String v = t.trim();
            if (AdmPrint.hex(v)) {
                last[0] = v.toUpperCase(java.util.Locale.ROOT);
                sw.setBackground(Ui.round(parse(v, Color.WHITE), Ui.LINE_STRONG, 1, 8, a));
                hex.setError(null);
                put(key, last[0]);
            } else {
                hex.setError("Use #RRGGBB");
            }
        }));
    }

    private View palette(AdmUi.Picked pick) {
        HorizontalScrollView hs = new HorizontalScrollView(a);
        hs.setHorizontalScrollBarEnabled(false);
        LinearLayout row = Ui.hbox(a);
        for (String c : PALETTE) {
            TextView t = new TextView(a);
            t.setBackground(Ui.round(parse(c, Color.WHITE), Ui.LINE_STRONG, 1, 14, a));
            t.setOnClickListener(v -> pick.value(c));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(28), dp(28));
            lp.rightMargin = dp(6);
            row.addView(t, lp);
        }
        hs.addView(row);
        return hs;
    }

    private void decimal(LinearLayout box, String label, String key, double value, double lo, double hi) {
        EditText e = AdmUi.field(a, box, label, AdmPy.pyStr(value), label);
        e.setInputType(android.text.InputType.TYPE_CLASS_NUMBER | android.text.InputType.TYPE_NUMBER_FLAG_DECIMAL);
        e.addTextChangedListener(watcher(t -> {
            try {
                double d = Double.parseDouble(t.trim());
                if (d < lo || d > hi) { e.setError("Between " + lo + " and " + hi); return; }
                e.setError(null);
                put(key, d);
            } catch (NumberFormatException ex) {
                e.setError("Number");
            }
        }));
    }

    private void text(LinearLayout box, String label, String key, String value, String hint) {
        EditText e = AdmUi.field(a, box, label, value, hint);
        e.addTextChangedListener(watcher(t -> put(key, t)));
    }

    private interface OnText { void text(String t); }

    private static TextWatcher watcher(OnText on) {
        return new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
            @Override public void afterTextChanged(Editable e) { on.text(e.toString()); }
        };
    }

    private static int parse(String hex, int def) {
        try { return AdmPrint.hex(hex) ? Color.parseColor(hex) : def; } catch (Exception e) { return def; }
    }

    // ------------------------------------------------------------------ preview
    private void refreshPreview() {
        if (preview == null || layout == null) return;
        preview.removeAllViews();
        JSONObject l = AdmPrint.normalize(doc, layout);
        int accent = parse(l.optString("accent"), Ui.TEAL_DARK);
        int rule = parse(l.optString("rule"), Ui.LINE);
        String bar = l.optString("bar", "fill");
        boolean po = "PURCHASE_ORDER".equals(doc);
        String company = l.optString("company_name", "");
        String title = po ? (l.optString("title", "").isEmpty() ? "PURCHASE ORDER" : l.optString("title")) : AdmPrint.docLabel(doc).toUpperCase(java.util.Locale.ROOT);
        TextView head = Ui.text(a, (company.isEmpty() ? "" : company + "\n") + title, 14, accent, true);
        preview.addView(head);
        String heading = po ? AdmPrint.PO_SECTIONS[1][0] : first(AdmPrint.REPORT_HEADINGS.get(doc), "RECORD DETAILS");
        JSONObject labels = l.optJSONObject("labels");
        heading = relabel(labels, heading);
        TextView h = Ui.text(a, heading, 12, "fill".equals(bar) ? Color.WHITE : accent, true);
        h.setPadding(dp(8), dp(4), dp(8), dp(4));
        if ("fill".equals(bar)) h.setBackground(Ui.round(accent, 0, 0, 2, a));
        else if ("outline".equals(bar)) h.setBackground(Ui.round(Color.WHITE, accent, 1, 2, a));
        preview.addView(h, Ui.matchWrap(a, 8));
        if ("underline".equals(bar)) {
            View line = new View(a);
            line.setBackgroundColor(accent);
            preview.addView(line, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(2)));
        }
        int headFill = parse(l.optString("head_fill", ""), Color.WHITE);
        int labelFill = parse(l.optString("label_fill", ""), Color.WHITE);
        String[][] cells = {{"Part Number", "TEST-PART"}, {"Heat Number", "TEST-HEAT"}, {"Quantity", "1,000 Nos"}};
        LinearLayout table = Ui.vbox(a);
        table.setBackground(Ui.round(Color.WHITE, rule, 1, 0, a));
        table.setPadding(1, 1, 1, 1);
        LinearLayout th = Ui.hbox(a);
        th.setBackgroundColor(headFill);
        th.addView(cell("Field", accent, true), Ui.weight(1));
        th.addView(cell("Value", accent, true), Ui.weight(1));
        table.addView(th);
        for (String[] c : cells) {
            View sep = new View(a);
            sep.setBackgroundColor(rule);
            table.addView(sep, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 1));
            LinearLayout tr = Ui.hbox(a);
            TextView k = cell(c[0], Ui.TEXT, true);
            k.setBackgroundColor(labelFill);
            tr.addView(k, Ui.weight(1));
            tr.addView(cell(c[1], Ui.TEXT, false), Ui.weight(1));
            table.addView(tr);
        }
        preview.addView(table, Ui.matchWrap(a, 6));
        TextView remark = Ui.text(a, "Remarks: sample remark text", 11.5f, parse(l.optString("remark"), Ui.ORANGE), false);
        remark.setPadding(dp(8), dp(4), dp(8), dp(4));
        String rf = l.optString("remark_fill", "");
        if (!rf.isEmpty()) remark.setBackgroundColor(parse(rf, Color.WHITE));
        preview.addView(remark, Ui.matchWrap(a, 6));
        preview.addView(Ui.text(a, "Conclusion: ACCEPTED", 12, parse(l.optString("conclusion"), Ui.GREEN_FG), true), Ui.matchWrap(a, 4));
        String footer = l.optString("footer_text", "");
        if (!footer.isEmpty()) preview.addView(Ui.text(a, footer, 10, Ui.MUTED, false), Ui.matchWrap(a, 6));
    }

    private TextView cell(String t, int color, boolean bold) {
        TextView v = Ui.text(a, t, 11, color, bold);
        v.setPadding(dp(6), dp(4), dp(6), dp(4));
        return v;
    }

    private static String first(String[] v, String def) { return v == null || v.length == 0 ? def : v[0]; }

    /** core/print_designer.relabel. */
    static String relabel(JSONObject labels, String title) {
        if (labels == null) return title;
        if (labels.has(title)) return labels.optString(title);
        for (Iterator<String> it = labels.keys(); it.hasNext(); ) {
            String o = it.next();
            if (title.startsWith(o)) return labels.optString(o) + title.substring(o.length());
        }
        return title;
    }
}
