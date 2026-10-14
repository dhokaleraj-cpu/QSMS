package com.fourstar.qcmsapp;

import android.graphics.Color;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.Locale;

/** Quality Assets & calibration status. Same name may repeat; the Asset Number tells them apart. */
public final class AssetsScreen extends Screen {
    private static final String[] FILTERS = {"All", "Overdue", "Due 30 d", "Gauges", "Instruments"};
    static int filter = 0;
    private JSONArray rows = new JSONArray();
    private LinearLayout list;
    private EditText search;

    public AssetsScreen(MainActivity a) { super(a); }

    @Override public String title() { return "Quality Assets"; }
    @Override public String subtitle() { return "Gauges · instruments · equipment · calibration status"; }
    @Override public int tab() { return 3; }

    @Override
    public View build() {
        newPage();
        search = Ui.input(a, "Search name / asset number / location", false);
        add(search, 0);
        LinearLayout chips = Ui.hbox(a);
        for (int i = 0; i < FILTERS.length; i++) {
            final int index = i;
            TextView chip = Ui.text(a, FILTERS[i], 11.5f, i == filter ? Color.WHITE : Ui.TEXT, i == filter);
            chip.setGravity(Gravity.CENTER);
            chip.setPadding(dp(2), dp(8), dp(2), dp(8));
            chip.setBackground(i == filter ? Ui.round(Ui.TEAL, 0, 0, 10, a) : Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 10, a));
            chip.setOnClickListener(v -> { filter = index; a.rebuild(); });
            LinearLayout.LayoutParams lp = Ui.weight(1);
            lp.rightMargin = i < FILTERS.length - 1 ? dp(5) : 0;
            chips.addView(chip, lp);
        }
        add(chips, 10);
        list = Ui.vbox(a);
        add(list, 4);
        list.addView(loading());
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
            @Override public void afterTextChanged(Editable e) { fill(); }
        });
        Api.async(() -> api.rows("quality_assets?select=id,asset_code,asset_number,asset_name,asset_type,range_text,location,next_due_date,status&status=neq.INACTIVE&order=asset_name.asc,asset_number.asc&limit=2000"),
            (data, err) -> {
                list.removeAllViews();
                if (err != null) { list.addView(error(err, this::reload)); return; }
                rows = data;
                fill();
            });
        return scroll;
    }

    static String dueState(String nextDue) {
        if (nextDue == null || nextDue.isEmpty() || "null".equals(nextDue)) return "none";
        try {
            LocalDate d = LocalDate.parse(nextDue.substring(0, 10));
            LocalDate today = LocalDate.now();
            if (d.isBefore(today)) return "overdue";
            if (!d.isAfter(today.plusDays(30))) return "due";
            return "valid";
        } catch (Exception e) {
            return "none";
        }
    }

    static View dueChip(MainActivity a, String nextDue) {
        String s = dueState(nextDue);
        switch (s) {
            case "overdue": return Ui.chip(a, "Overdue " + Ui.date(nextDue), "red");
            case "due": return Ui.chip(a, "Due " + Ui.date(nextDue), "amber");
            case "valid": return Ui.chip(a, "Valid " + Ui.date(nextDue), "green");
            default: return Ui.chip(a, "No due date", "grey");
        }
    }

    private void fill() {
        if (list == null) return;
        list.removeAllViews();
        String q = search.getText().toString().trim().toLowerCase(Locale.ROOT);
        int shown = 0;
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.optJSONObject(i);
            if (r == null) continue;
            String type = r.optString("asset_type").toUpperCase(Locale.ROOT);
            String state = dueState(r.optString("next_due_date"));
            if (filter == 1 && !state.equals("overdue")) continue;
            if (filter == 2 && !state.equals("due")) continue;
            if (filter == 3 && !(type.contains("GAUGE") || type.contains("FIXTURE") || type.contains("JIG"))) continue;
            if (filter == 4 && !(type.contains("INSTRUMENT") || type.contains("EQUIPMENT"))) continue;
            String hay = (r.optString("asset_name") + " " + r.optString("asset_number") + " " + r.optString("asset_code") + " " + r.optString("location") + " " + r.optString("range_text")).toLowerCase(Locale.ROOT);
            if (!q.isEmpty() && !hay.contains(q)) continue;
            list.addView(card(r), Ui.matchWrap(a, 8));
            if (++shown >= 400) break;
        }
        if (shown == 0) list.addView(Ui.empty(a, "No asset matches."));
        if (api.lastCallOffline) list.addView(Ui.chip(a, "Offline · last saved data", "amber"), 0);
    }

    private View card(JSONObject r) {
        LinearLayout card = Ui.card(a);
        LinearLayout top = Ui.hbox(a);
        top.addView(Ui.text(a, r.optString("asset_name"), 14, Ui.TEXT, true), Ui.weight(1));
        top.addView(dueChip(a, r.optString("next_due_date")));
        card.addView(top);
        String number = r.optString("asset_number", "");
        if (number.isEmpty() || "null".equals(number)) number = r.optString("asset_code");
        String type = r.optString("asset_type");
        boolean direct = type.toUpperCase(Locale.ROOT).contains("INSTRUMENT") || type.toUpperCase(Locale.ROOT).contains("EQUIPMENT");
        card.addView(Ui.text(a, number + " · " + Ui.pretty(type) + (direct ? " · no Part link" : "") + " · " + nz(r.optString("range_text")), 12, Ui.MUTED, false));
        String loc = nz(r.optString("location"));
        if (!loc.isEmpty()) card.addView(Ui.text(a, "Location " + loc, 11.5f, Ui.MUTED, false));
        Ui.clickable(card, Color.WHITE, Ui.LINE, 14);
        final String id = r.optString("id");
        card.setOnClickListener(v -> a.push(new AssetDetailScreen(a, id)));
        return card;
    }

    static String nz(String v) { return v == null || "null".equals(v) ? "" : v; }
}
