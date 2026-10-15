package com.fourstar.qcmsapp;

import android.graphics.Color;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Root of a bottom-navigation tab: every module of that area as a card with its record count. */
public final class SectionScreen extends Screen {
    private final int tab;
    private final List<View[]> cards = new ArrayList<>();

    public SectionScreen(MainActivity a, int tab) { super(a); this.tab = tab; }

    @Override public String title() { return Catalog.TAB_NAMES[tab]; }
    @Override public String subtitle() {
        switch (tab) {
            case Catalog.SUPPLY: return "Customer orders · purchase orders · receipts · forging · dispatch";
            case Catalog.QUALITY: return "RMTC · inward · inspections · MetLAB · OSP · calibration · complaints";
            case Catalog.MASTERS: return "Parts · grades · processes · parties · assets · standards · employees";
            default: return "NPD / APQP · QC tools · reports · records · settings";
        }
    }
    @Override public int tab() { return tab; }

    @Override
    public View build() {
        newPage();
        cards.clear();
        EditText search = Ui.input(a, "Find a module…", false);
        add(search, 0);
        for (Map.Entry<String, List<Module>> e : Catalog.sections(tab).entrySet()) {
            TextView head = Ui.label(a, e.getKey());
            add(head, 10);
            for (Module m : e.getValue()) {
                View card = card(m);
                add(card, 6);
                cards.add(new View[]{card, head});
                card.setTag(m.title.toLowerCase(Locale.ROOT) + " " + m.description.toLowerCase(Locale.ROOT) + " " + e.getKey().toLowerCase(Locale.ROOT));
            }
        }
        if (tab == Catalog.MORE) MoreScreen.addSettings(a, this, page);
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
            @Override public void afterTextChanged(Editable ed) {
                String q = ed.toString().trim().toLowerCase(Locale.ROOT);
                for (View[] pair : cards) pair[0].setVisibility(q.isEmpty() || String.valueOf(pair[0].getTag()).contains(q) ? View.VISIBLE : View.GONE);
            }
        });
        return scroll;
    }

    private View card(Module m) {
        LinearLayout card = Ui.card(a);
        LinearLayout row = Ui.hbox(a);
        LinearLayout text = Ui.vbox(a);
        text.addView(Ui.text(a, m.title, 14.5f, Ui.TEXT, true));
        if (!m.description.isEmpty()) {
            TextView d = Ui.text(a, m.description, 11.5f, Ui.MUTED, false);
            d.setMaxLines(2);
            text.addView(d);
        }
        row.addView(text, Ui.weight(1));
        TextView count = Ui.text(a, "", 13, Ui.TEAL_DARK, true);
        count.setGravity(Gravity.END);
        count.setPadding(dp(8), 0, dp(6), 0);
        row.addView(count);
        row.addView(Ui.text(a, "›", 24, Ui.TEAL, true));
        card.addView(row);
        Ui.clickable(card, Color.WHITE, Ui.LINE, 14);
        card.setOnClickListener(v -> a.push(m.custom != null ? m.custom.open(a) : new RegisterScreen(a, m)));
        if (!m.table.isEmpty() && !m.table.startsWith("v_qsms_heat")) {
            String path = m.table + "?select=" + (m.idField.isEmpty() ? "tenant_id" : m.idField) + m.filter;
            Api.async(() -> api.count(path), (n, err) -> { if (err == null && n != null) count.setText(Ui.num(n, 0)); });
        }
        return card;
    }
}
