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
 * R35: also lists matching app modules / screens and the server-wide qcms_global_search rows
 * (every table and field), merged with the local field search.
 */
final class GenSearchScreen extends Screen implements ExportDoc.Source {
    private static String lastQuery = "";
    private static List<GenSearch.Result> lastResults = null;

    private String query;
    private String module = "";          // "" = all modules
    private LinearLayout results;
    private EditText input;
    private Button go;
    private boolean focusInput = false;
    private List<GenSearch.Result> current = null;

    /** R37 "+" -> New query: empty Global Search with the keyboard up. */
    static GenSearchScreen newQuery(MainActivity a) {
        GenSearchScreen s = new GenSearchScreen(a, "");
        s.focusInput = true;
        return s;
    }

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
        if (focusInput) {
            focusInput = false;
            input.requestFocus();
            input.postDelayed(() -> {
                android.view.inputmethod.InputMethodManager imm =
                    (android.view.inputmethod.InputMethodManager) a.getSystemService(android.content.Context.INPUT_METHOD_SERVICE);
                if (imm != null) imm.showSoftInput(input, android.view.inputmethod.InputMethodManager.SHOW_IMPLICIT);
            }, 250);
        }
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
        final int run = ++runs;
        // 1) app modules / screens + qcms_global_search (every table and field on the server) - fast
        Api.async(() -> {
            Partial p = new Partial();
            p.modules = GenSearch.modules(q);
            try { p.server = GenSearch.server(api, q, 200); }
            catch (Exception e) {
                if (e instanceof Api.ApiException && ((Api.ApiException) e).status == 401) throw e;
                p.serverError = e;   // older database / offline: the local search below still runs
            }
            return p;
        }, (p, err) -> {
            if (run != runs) return;
            if (err != null) { go.setEnabled(true); results.removeAllViews(); results.addView(error(err, this::run)); return; }
            List<GenSearch.Result> first = GenSearch.merge(p.modules, p.server, null);
            query = q;
            searchingMore = true;
            if (!first.isEmpty()) render(first);
            // 2) the existing field search of the 27 registers (part / party relations) - merged in
            Api.async(() -> GenSearch.everywhere(api, q, 40), (local, err2) -> {
                if (run != runs) return;
                go.setEnabled(true);
                searchingMore = false;
                if (err2 != null && p.server == null) {
                    results.removeAllViews();
                    if (!p.modules.isEmpty()) { lastResults = null; render(p.modules); }
                    results.addView(error(err2, this::run));
                    return;
                }
                List<GenSearch.Result> all = GenSearch.merge(p.modules, p.server, err2 == null ? local : null);
                lastQuery = q;
                lastResults = all;
                render(all);
            });
        });
    }

    private static final class Partial {
        List<GenSearch.Result> modules, server;
        Exception serverError;
    }

    private int runs = 0;
    private boolean searchingMore = false;

    /** Opens a hit: module -> the module; server row -> the record natively or its website page; local -> the record. */
    private void open(GenSearch.Result r) {
        if (GenSearch.Result.MODULE.equals(r.kind)) { a.openModule(r.appModule); return; }
        if (GenSearch.Result.SERVER.equals(r.kind)) { Notif.open(a, r.table, r.recordId, r.route, r.reference); return; }
        GenUtil.openRecord(a, r.table, r.record);
    }

    /** R37: long-press a hit -> Open / Print PDF (print layout, Universal Record PDF fallback). */
    private void longPress(GenSearch.Result r) {
        if (GenSearch.Result.MODULE.equals(r.kind)) { a.openModule(r.appModule); return; }
        String id = GenSearch.Result.SERVER.equals(r.kind) ? r.recordId : (r.record == null ? "" : r.record.optString("id", ""));
        String title = r.reference == null || r.reference.isEmpty() ? r.recordType : r.reference;
        new android.app.AlertDialog.Builder(a).setTitle(title)
            .setItems(new String[]{"Open record", "Print PDF · Preview / Save / Share"}, (d, w) -> {
                if (w == 0) open(r);
                else KpiDetails.printRecord(a, r.table, id, r.route);
            })
            .setNegativeButton("Close", null).show();
    }

    private void render(List<GenSearch.Result> found) {
        results.removeAllViews();
        current = found;
        Map<String, List<GenSearch.Result>> byModule = new LinkedHashMap<>();
        for (GenSearch.Result r : found) byModule.computeIfAbsent(r.module, k -> new ArrayList<>()).add(r);

        List<View> tiles = new ArrayList<>();
        tiles.add(GenUtil.tile(a, "", "Search", query, "Current query", "neutral"));
        tiles.add(GenUtil.tile(a, "", "Matches", String.valueOf(found.size()), searchingMore ? "Searching more…" : "Records + modules", "neutral"));
        tiles.add(GenUtil.tile(a, "", "Modules", String.valueOf(byModule.size()), "With matching records", "neutral"));
        tiles.add(GenUtil.tile(a, "", "Security", "Permission aware", "View rights + tenant RLS", "neutral"));
        GenUtil.grid2(a, results, tiles, 4);

        if (found.isEmpty() && searchingMore) {
            results.addView(loading());
            return;
        }
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
        if (keys.remove(GenSearch.MODULES_GROUP)) keys.add(0, GenSearch.MODULES_GROUP);   // modules to open first
        List<String> labels = new ArrayList<>();
        labels.add("All · " + found.size());
        for (String k : keys) labels.add(k + " · " + byModule.get(k).size());
        int sel = module.isEmpty() ? 0 : keys.indexOf(module) + 1;
        results.addView(GenUtil.chips(a, labels, sel, i -> { module = i == 0 ? "" : keys.get(i - 1); render(found); }), Ui.matchWrap(a, 12));

        int visible = 0;
        for (String k : keys) if (module.isEmpty() || module.equals(k)) visible += byModule.get(k).size();
        results.addView(Ui.text(a, visible + " match(es) · tap a row to open it · hold for Print PDF" + (searchingMore ? " · searching more registers…" : ""), 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 8));

        for (String k : keys) {
            if (!module.isEmpty() && !module.equals(k)) continue;
            List<GenSearch.Result> rows = byModule.get(k);
            results.addView(Ui.label(a, k + " · " + rows.size()), Ui.matchWrap(a, 8));
            List<String> cols = GenUtil.listOf("Reference", "Record Type", "Details", "Status / Result");
            List<List<String>> data = new ArrayList<>();
            for (GenSearch.Result r : rows) data.add(GenUtil.listOf(r.reference, r.recordType, r.detail, r.status));
            results.addView(new DataGrid(a, "Global Search · " + k, cols, data, 360, index -> {
                if (index >= 0 && index < rows.size()) open(rows.get(index));
            }).onLongRow(index -> {
                if (index >= 0 && index < rows.size()) longPress(rows.get(index));
            }), Ui.matchWrap(a, 2));
        }
        // R37: search results as a print-layout PDF (View / Download / Print / Email / Share) - also from the top-bar ⇩
        Button pdf = Ui.primary(a, "🖨 Results PDF · Preview · Download · Share");
        pdf.setOnClickListener(v -> ExportKit.showData(a, this, null));
        results.addView(pdf, Ui.matchWrap(a, 14));
        Button csv = Ui.outline(a, "Export results (CSV)", Ui.TEAL);
        csv.setOnClickListener(v -> {
            List<String[]> rows = new ArrayList<>();
            for (GenSearch.Result r : found) if (module.isEmpty() || module.equals(r.module)) rows.add(new String[]{r.module, r.recordType, r.reference, r.detail, r.status});
            GenUtil.exportCsv(a, "Global Search", "QCMS_Global_Search_" + GenUtil.safeName(query),
                GenUtil.csv(GenUtil.listOf("Module", "Record Type", "Reference", "Details", "Status / Result"), rows));
        });
        results.addView(csv, Ui.matchWrap(a, 14));
    }

    /** R37: the visible search results (module filter applied) as a printable document. */
    @Override public ExportDoc export() {
        ExportDoc doc = new ExportDoc("Global Search · " + query).subtitle("Search results").file("QCMS_Global_Search_" + GenUtil.safeName(query));
        doc.kind = "Global Search";
        doc.section("Search").pair("Query", query).pair("Module filter", module.isEmpty() ? "All modules" : module)
            .pair("Matches", String.valueOf(current == null ? 0 : current.size()));
        List<List<String>> rows = new ArrayList<>();
        if (current != null) for (GenSearch.Result r : current) {
            if (!module.isEmpty() && !module.equals(r.module)) continue;
            rows.add(GenUtil.listOf(r.module, r.recordType, r.reference, r.detail, r.status));
        }
        doc.table("Results", GenUtil.listOf("Module", "Record Type", "Reference", "Details", "Status / Result"), rows);
        return doc;
    }

    @Override public void reload() { lastResults = null; a.rebuild(); }
}
