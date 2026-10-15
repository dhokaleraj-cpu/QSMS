package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.Switch;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Small view helpers shared by the Administration screens. */
final class AdmUi {
    private AdmUi() { }

    interface Picked { void value(String value); }
    interface IntPicked { void index(int index); }

    /** Website stage_section: letter + title + caption inside a card; returns the card body. */
    static LinearLayout section(MainActivity a, LinearLayout page, String letter, String title, String caption) {
        LinearLayout card = Ui.card(a);
        LinearLayout head = Ui.hbox(a);
        if (letter != null && !letter.isEmpty()) {
            TextView badge = Ui.text(a, letter, 12, Color.WHITE, true);
            badge.setGravity(Gravity.CENTER);
            badge.setBackground(Ui.round(Ui.TEAL, 0, 0, 8, a));
            badge.setPadding(Ui.dp(a, 8), Ui.dp(a, 2), Ui.dp(a, 8), Ui.dp(a, 2));
            head.addView(badge);
            TextView sp = new TextView(a);
            sp.setWidth(Ui.dp(a, 8));
            head.addView(sp);
        }
        head.addView(Ui.text(a, title, 13.5f, Ui.TEAL_DARK, true), Ui.weight(1));
        card.addView(head);
        if (caption != null && !caption.isEmpty()) {
            TextView c = Ui.text(a, caption, 11.5f, Ui.MUTED, false);
            c.setPadding(0, Ui.dp(a, 4), 0, Ui.dp(a, 2));
            card.addView(c);
        }
        page.addView(card, Ui.matchWrap(a, 10));
        return card;
    }

    /** Multi-line coloured message block (st.info / st.warning / st.error / st.success). */
    static TextView note(MainActivity a, String text, String tone) {
        int fg = Ui.TEAL_DARK, bg = Ui.TEAL_SOFT;
        if ("amber".equals(tone)) { fg = Ui.AMBER_FG; bg = Ui.AMBER_BG; }
        else if ("red".equals(tone)) { fg = Ui.RED_FG; bg = Ui.RED_BG; }
        else if ("green".equals(tone)) { fg = Ui.GREEN_FG; bg = Ui.GREEN_BG; }
        else if ("grey".equals(tone)) { fg = Ui.GREY_FG; bg = Ui.GREY_BG; }
        TextView t = Ui.text(a, text, 12.5f, fg, false);
        t.setBackground(Ui.round(bg, 0, 0, 10, a));
        t.setPadding(Ui.dp(a, 10), Ui.dp(a, 8), Ui.dp(a, 10), Ui.dp(a, 8));
        return t;
    }

    static void add(MainActivity a, LinearLayout box, View v, int topDp) { box.addView(v, Ui.matchWrap(a, topDp)); }

    static Button primary(MainActivity a, LinearLayout box, String label, View.OnClickListener click) {
        Button b = Ui.primary(a, label);
        b.setOnClickListener(click);
        box.addView(b, Ui.matchWrap(a, 10));
        return b;
    }

    static Button outline(MainActivity a, LinearLayout box, String label, View.OnClickListener click) {
        Button b = Ui.outline(a, label, Ui.TEAL);
        b.setOnClickListener(click);
        box.addView(b, Ui.matchWrap(a, 8));
        return b;
    }

    static void enableView(View v, boolean on) {
        v.setEnabled(on);
        v.setAlpha(on ? 1f : 0.45f);
    }

    static void enable(Button b, boolean on) {
        b.setEnabled(on);
        b.setAlpha(on ? 1f : 0.45f);
    }

    static Switch toggle(MainActivity a, LinearLayout box, String label, boolean on) {
        Switch s = new Switch(a);
        s.setText(label);
        s.setTextColor(Ui.TEXT);
        s.setChecked(on);
        s.setMinHeight(Ui.dp(a, 44));
        box.addView(s, Ui.matchWrap(a, 4));
        return s;
    }

    static CheckBox check(MainActivity a, String label, boolean on) {
        CheckBox c = new CheckBox(a);
        c.setText(label);
        c.setTextColor(Ui.TEXT);
        c.setChecked(on);
        return c;
    }

    static EditText field(MainActivity a, LinearLayout box, String label, String value, String hint) {
        box.addView(Ui.label(a, label));
        EditText e = Ui.input(a, hint == null ? label : hint, false);
        e.setText(value == null ? "" : value);
        box.addView(e, Ui.matchWrap(a, 0));
        return e;
    }

    static EditText password(MainActivity a, LinearLayout box, String label, String hint) {
        box.addView(Ui.label(a, label));
        EditText e = Ui.input(a, hint, true);
        box.addView(e, Ui.matchWrap(a, 0));
        return e;
    }

    static String text(EditText e) { return e.getText() == null ? "" : e.getText().toString(); }

    /** Tap-to-choose selector (same look as FormView dropdowns). */
    static TextView selector(MainActivity a, LinearLayout box, String label, String shown) {
        if (label != null) box.addView(Ui.label(a, label));
        TextView t = Ui.text(a, shown, 14.5f, Ui.TEXT, false);
        t.setPadding(Ui.dp(a, 12), Ui.dp(a, 12), Ui.dp(a, 12), Ui.dp(a, 12));
        t.setBackground(Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 10, a));
        box.addView(t, Ui.matchWrap(a, 0));
        return t;
    }

    /** Selector bound to values/labels: shows the current label, opens the searchable picker, reports the choice. */
    static TextView choice(MainActivity a, LinearLayout box, String label, List<String> values, List<String> labels, String current, Picked onPick) {
        int i = values.indexOf(current == null ? "" : current);
        TextView t = selector(a, box, label, i >= 0 && i < labels.size() ? labels.get(i) : (labels.isEmpty() ? "" : labels.get(0)));
        t.setOnClickListener(v -> {
            pick(a, label == null ? "Select" : label, values, labels, value -> {
                int k = values.indexOf(value);
                t.setText(k >= 0 ? labels.get(k) : value);
                if (onPick != null) onPick.value(value);
            });
        });
        return t;
    }

    /** Same as choice() for a plain list where value = label. */
    static TextView choice(MainActivity a, LinearLayout box, String label, List<String> values, String current, Picked onPick) {
        return choice(a, box, label, values, values, current, onPick);
    }

    /** st.radio: one RadioButton per option (wrapping text), reports the chosen value. */
    static android.widget.RadioGroup radio(MainActivity a, LinearLayout box, String label, String[][] options, String current, boolean enabled, Picked onPick) {
        if (label != null) box.addView(Ui.label(a, label));
        android.widget.RadioGroup group = new android.widget.RadioGroup(a);
        group.setOrientation(LinearLayout.VERTICAL);
        for (String[] o : options) {
            android.widget.RadioButton rb = new android.widget.RadioButton(a);
            rb.setId(View.generateViewId());
            rb.setText(o[1]);
            rb.setTextColor(Ui.TEXT);
            rb.setTextSize(13);
            rb.setMinHeight(Ui.dp(a, 40));
            rb.setEnabled(enabled);
            group.addView(rb);
            if (o[0].equals(current)) group.check(rb.getId());
            rb.setOnCheckedChangeListener((b, on) -> { if (on && onPick != null) onPick.value(o[0]); });
        }
        box.addView(group, Ui.matchWrap(a, 2));
        return group;
    }

    /** st.multiselect: tap to tick several options; `selected` is updated in place (option order kept). */
    static TextView multi(MainActivity a, LinearLayout box, String label, List<String> options, List<String> selected, Runnable changed) {
        TextView t = selector(a, box, label, selected.isEmpty() ? "— None —" : String.join(", ", selected));
        t.setOnClickListener(v -> {
            boolean[] on = new boolean[options.size()];
            for (int i = 0; i < on.length; i++) on[i] = selected.contains(options.get(i));
            new AlertDialog.Builder(a).setTitle(label)
                .setMultiChoiceItems(options.toArray(new String[0]), on, (d, which, checked) -> on[which] = checked)
                .setPositiveButton("OK", (d, w) -> {
                    selected.clear();
                    for (int i = 0; i < on.length; i++) if (on[i]) selected.add(options.get(i));
                    t.setText(selected.isEmpty() ? "— None —" : String.join(", ", selected));
                    if (changed != null) changed.run();
                })
                .setNegativeButton("Back", null).show();
        });
        return t;
    }

    /** Integer from a text box within [lo, hi]; null when empty / invalid / out of range. */
    static Integer intIn(EditText e, int lo, int hi) {
        try {
            int v = Integer.parseInt(text(e).trim());
            return v < lo || v > hi ? null : v;
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    static EditText number(MainActivity a, LinearLayout box, String label, int value) {
        EditText e = field(a, box, label, String.valueOf(value), label);
        e.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);
        return e;
    }

    /** Small "metric" tile: caption + value. */
    static LinearLayout metric(MainActivity a, LinearLayout box, String caption, String value) {
        LinearLayout t = Ui.vbox(a);
        t.setBackground(Ui.round(Ui.BG, Ui.LINE, 1, 10, a));
        t.setPadding(Ui.dp(a, 10), Ui.dp(a, 6), Ui.dp(a, 10), Ui.dp(a, 6));
        t.addView(Ui.text(a, caption, 11, Ui.MUTED, false));
        t.addView(Ui.text(a, value == null || value.isEmpty() ? "—" : value, 14.5f, Ui.TEXT, true));
        box.addView(t, Ui.matchWrap(a, 6));
        return t;
    }

    static List<String> listOf(String... v) {
        List<String> out = new ArrayList<>();
        for (String s : v) out.add(s);
        return out;
    }

    /** Horizontal tab strip (st.tabs). */
    static View tabs(MainActivity a, String[] names, int selected, IntPicked pick) {
        HorizontalScrollView scroll = new HorizontalScrollView(a);
        scroll.setHorizontalScrollBarEnabled(false);
        LinearLayout row = Ui.hbox(a);
        for (int i = 0; i < names.length; i++) {
            final int index = i;
            boolean on = i == selected;
            TextView t = Ui.text(a, names[i], 13, on ? Color.WHITE : Ui.TEAL_DARK, true);
            t.setPadding(Ui.dp(a, 14), Ui.dp(a, 9), Ui.dp(a, 14), Ui.dp(a, 9));
            t.setBackground(Ui.round(on ? Ui.TEAL : Ui.TEAL_SOFT, 0, 0, 18, a));
            t.setOnClickListener(v -> pick.index(index));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.rightMargin = Ui.dp(a, 6);
            row.addView(t, lp);
        }
        scroll.addView(row);
        return scroll;
    }

    /** Searchable single choice (search box shown for longer lists). */
    static void pick(MainActivity a, String title, List<String> values, List<String> labels, Picked picked) {
        if (values.size() <= 10) {
            String[] items = labels.toArray(new String[0]);
            new AlertDialog.Builder(a).setTitle(title).setItems(items, (d, which) -> picked.value(values.get(which)))
                .setNegativeButton("Back", null).show();
            return;
        }
        LinearLayout box = Ui.vbox(a);
        int p = Ui.dp(a, 14);
        box.setPadding(p, Ui.dp(a, 6), p, 0);
        EditText search = Ui.input(a, "Search…", false);
        box.addView(search, Ui.matchWrap(a, 0));
        ListView list = new ListView(a);
        List<String> shown = new ArrayList<>(labels);
        List<String> shownValues = new ArrayList<>(values);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(a, android.R.layout.simple_list_item_1, shown);
        list.setAdapter(adapter);
        box.addView(list, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(a, 380)));
        AlertDialog dialog = new AlertDialog.Builder(a).setTitle(title).setView(box).setNegativeButton("Back", null).create();
        list.setOnItemClickListener((parent, view, pos, id) -> {
            dialog.dismiss();
            picked.value(shownValues.get(pos));
        });
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
            @Override public void afterTextChanged(Editable e) {
                String q = e.toString().trim().toLowerCase(Locale.ROOT);
                shown.clear(); shownValues.clear();
                for (int i = 0; i < labels.size(); i++) {
                    if (q.isEmpty() || labels.get(i).toLowerCase(Locale.ROOT).contains(q)) { shown.add(labels.get(i)); shownValues.add(values.get(i)); }
                }
                adapter.notifyDataSetChanged();
            }
        });
        dialog.show();
    }

    /** Website-style admin-only message card. */
    static View adminOnly(MainActivity a, String message) {
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "Administrator only", 15, Ui.RED_FG, true));
        TextView t = Ui.text(a, message, 13, Ui.TEXT, false);
        t.setPadding(0, Ui.dp(a, 6), 0, 0);
        card.addView(t);
        return card;
    }

    /** Share plain text (CSV / JSON) with another app. */
    static void share(MainActivity a, String subject, String text) {
        try {
            Intent send = new Intent(Intent.ACTION_SEND);
            send.setType("text/plain");
            send.putExtra(Intent.EXTRA_SUBJECT, subject);
            send.putExtra(Intent.EXTRA_TEXT, text);
            a.startActivity(Intent.createChooser(send, subject));
        } catch (Exception e) {
            a.toast("No app available to share.");
        }
    }

    static String csv(List<String> headers, List<List<String>> rows) {
        StringBuilder b = new StringBuilder();
        line(b, headers);
        for (List<String> r : rows) line(b, r);
        return b.toString();
    }

    private static void line(StringBuilder b, List<String> cells) {
        for (int i = 0; i < cells.size(); i++) {
            if (i > 0) b.append(',');
            String c = cells.get(i) == null ? "" : cells.get(i);
            if (c.contains(",") || c.contains("\"") || c.contains("\n")) c = "\"" + c.replace("\"", "\"\"") + "\"";
            b.append(c);
        }
        b.append('\n');
    }

    /** Timestamp text yyyy-MM-dd HH:mm:ss (website shows ISO values). */
    static String ts(String iso) {
        if (iso == null || iso.isEmpty() || "null".equals(iso)) return "";
        String t = iso.replace('T', ' ');
        return t.length() > 19 ? t.substring(0, 19) : t;
    }
}
