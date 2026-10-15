package com.fourstar.qcmsapp;

import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Global Search (website app_pages/global_search.py, Keyword Search tab): every permitted register,
 * results grouped by module with counts, tap a result to open the record natively.
 */
final class GenSearchScreen extends Screen {
    private static String lastQuery = "";
    private static List<GenSearch.Result> lastResults = null;

    private String query;
    private String module = "";          // "" = all modules
    private LinearLayout results;
    private EditText input;
    private Button go;

    GenSearchScreen(MainActivity a) { this(a, null); }

    /** Opens Global Search and runs the query at once (e.g. from the Home search box). */
    GenSearchScreen(MainActivity a, String initialQuery) {
        super(a);
        this.query = initialQuery == null ? lastQuery : initialQuery.trim();
        if (initialQuery != null && !initialQuery.trim().equals(lastQuery)) lastResults = null;
    }

    @Override public String title() { return "Global Search"; }
    @Override public String subtitle() { return "Part, Heat, RMTC, Batch, Supplier, Customer, PO, Report…"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        LinearLayout bar = Ui.hbox(a);
        input = Ui.input(a, "Part No, FSI Part No, Heat, RMTC, FSI Batch, vendor batch, supplier, customer, PO, report…", false);
        input.setText(query);
        input.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        input.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEARCH) { run(); return true; }
            return false;
        });
        bar.addView(input, Ui.weight(1));
        go = Ui.primary(a, "Search");
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(96), dp(48));
        lp.leftMargin = dp(8);
        bar.addView(go, lp);
        go.setOnClickListener(v -> run());
        add(bar, 0);
        results = Ui.vbox(a);
        add(results, 6);
        if (lastResults != null && query.equals(lastQuery)) render(lastResults);
        else if (query.length() >= 2) run();
        else intro();
        return scroll;
    }

    private void intro() {
        results.removeAllViews();
        results.addView(Ui.text(a, "Enter a search value. Global Search respects your module View permissions and the Supabase tenant / RLS controls.", 12.5f, Ui.MUTED, false), Ui.matchWrap(a, 8));
    }

    private void run() {
        String q = input.getText().toString().trim();
        if (q.length() < 2) {
            a.toast("Enter at least 2 characters to search QCMS.");
            return;
        }
        query = q;
        module = "";
        results.removeAllViews();
        results.addView(loading());
        TextView wait = Ui.text(a, "Searching permitted QCMS masters and transactions…", 12, Ui.MUTED, false);
        results.addView(wait);
        go.setEnabled(false);
        Api.async(() -> GenSearch.everywhere(api, q, 40), (found, err) -> {
            go.setEnabled(true);
            results.removeAllViews();
            if (err != null) { results.addView(error(err, this::run)); return; }
            lastQuery = q;
            lastResults = found;
            render(found);
        });
    }

    private void render(List<GenSearch.Result> found) {
        results.removeAllViews();
        Map<String, List<GenSearch.Result>> byModule = new LinkedHashMap<>();
        for (GenSearch.Result r : found) byModule.computeIfAbsent(r.module, k -> new ArrayList<>()).add(r);

        List<View> tiles = new ArrayList<>();
        tiles.add(GenUtil.tile(a, "", "Search", query, "Current query", "neutral"));
        tiles.add(GenUtil.tile(a, "", "Matches", String.valueOf(found.size()), "Across permitted registers", "neutral"));
        tiles.add(GenUtil.tile(a, "", "Modules", String.valueOf(byModule.size()), "With matching records", "neutral"));
        tiles.add(GenUtil.tile(a, "", "Security", "Permission aware", "View rights + tenant RLS", "neutral"));
        GenUtil.grid2(a, results, tiles, 4);

        if (found.isEmpty()) {
            TextView none = Ui.text(a, "No permitted QCMS records matched \"" + query + "\". Try a Part Number, Heat Number, RMTC, Batch, PO, Supplier / Customer name or Report Number.", 13, Ui.AMBER_FG, false);
            none.setBackground(Ui.round(Ui.AMBER_BG, 0, 0, 10, a));
            none.setPadding(dp(12), dp(10), dp(12), dp(10));
            results.addView(none, Ui.matchWrap(a, 12));
            return;
        }

        // module filter chips with counts (website: "Filter Results by Module")
        List<String> keys = new ArrayList<>(byModule.keySet());
        java.util.Collections.sort(keys);
        List<String> labels = new ArrayList<>();
        labels.add("All · " + found.size());
        for (String k : keys) labels.add(k + " · " + byModule.get(k).size());
        int sel = module.isEmpty() ? 0 : keys.indexOf(module) + 1;
        results.addView(GenUtil.chips(a, labels, sel, i -> { module = i == 0 ? "" : keys.get(i - 1); render(found); }), Ui.matchWrap(a, 12));

        int visible = 0;
        for (String k : keys) if (module.isEmpty() || module.equals(k)) visible += byModule.get(k).size();
        results.addView(Ui.text(a, visible + " matching record(s) · tap a row to open the record", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 8));

        for (String k : keys) {
            if (!module.isEmpty() && !module.equals(k)) continue;
            List<GenSearch.Result> rows = byModule.get(k);
            results.addView(Ui.label(a, k + " · " + rows.size()), Ui.matchWrap(a, 8));
            List<String> cols = GenUtil.listOf("Reference", "Record Type", "Details", "Status / Result");
            List<List<String>> data = new ArrayList<>();
            for (GenSearch.Result r : rows) data.add(GenUtil.listOf(r.reference, r.recordType, r.detail, r.status));
            results.addView(new DataGrid(a, "Global Search · " + k, cols, data, 360, index -> {
                if (index >= 0 && index < rows.size()) GenUtil.openRecord(a, rows.get(index).table, rows.get(index).record);
            }), Ui.matchWrap(a, 2));
        }
        Button csv = Ui.outline(a, "Export results (CSV)", Ui.TEAL);
        csv.setOnClickListener(v -> {
            List<String[]> rows = new ArrayList<>();
            for (GenSearch.Result r : found) if (module.isEmpty() || module.equals(r.module)) rows.add(new String[]{r.module, r.recordType, r.reference, r.detail, r.status});
            GenUtil.exportCsv(a, "Global Search", "QCMS_Global_Search_" + GenUtil.safeName(query),
                GenUtil.csv(GenUtil.listOf("Module", "Record Type", "Reference", "Details", "Status / Result"), rows));
        });
        results.addView(csv, Ui.matchWrap(a, 14));
    }

    @Override public void reload() { lastResults = null; a.rebuild(); }
}
