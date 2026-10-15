package com.fourstar.qcmsapp;

import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;

import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Report Builder (website app_pages/report_builder.py): saved reports, dataset, columns, filters,
 * group / totals / sort / limit, chart, result grid, CSV export and saved definitions.
 */
final class GenReportScreen extends Screen {
    private List<GenSearch.Source> sources;
    private List<GenReport.Saved> saved = new ArrayList<>();
    private GenReport.Saved base;
    private GenReport.Spec spec;
    private GenReport.Frame frame;
    private int loadedRows = 0;
    private String frameDataset = "";
    private GenReport.Result result;
    private String error;
    private final Map<String, List<org.json.JSONObject>> labelCache = new HashMap<>();

    // live inputs (read back by sync())
    private final List<EditText[]> filterInputs = new ArrayList<>();
    private EditText limitInput, titleInput, nameInput;
    private Switch descSwitch;
    private String saveName = "";

    GenReportScreen(MainActivity a) { super(a); }

    @Override public String title() { return "Report Builder"; }
    @Override public String subtitle() { return "Any report from the QCMS data you are allowed to see"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        if (sources == null) {
            page.addView(loading());
            Api.async(() -> {
                List<GenSearch.Source> ok = new ArrayList<>();
                for (GenSearch.Source s : GenSearch.SOURCES) if (GenUtil.canView(api, s.moduleKey)) ok.add(s);
                List<GenReport.Saved> sv = new ArrayList<>();
                for (GenReport.Saved r : GenReport.saved(api)) for (GenSearch.Source s : ok) if (s.table.equals(r.spec.dataset)) { sv.add(r); break; }
                return new Object[]{ok, sv};
            }, (res, err) -> {
                if (err != null) { page.removeAllViews(); page.addView(error(err, this::reload)); return; }
                @SuppressWarnings("unchecked") List<GenSearch.Source> ok = (List<GenSearch.Source>) res[0];
                @SuppressWarnings("unchecked") List<GenReport.Saved> sv = (List<GenReport.Saved>) res[1];
                sources = ok; saved = sv;
                if (sources.isEmpty()) { page.removeAllViews(); add(Ui.empty(a, "You do not have View permission on any QCMS dataset."), 0); return; }
                startFrom(null);
            });
            return scroll;
        }
        if (frame == null || !frameDataset.equals(spec.dataset)) { loadDataset(); return scroll; }
        renderForm();
        return scroll;
    }

    private GenSearch.Source src(String table) {
        for (GenSearch.Source s : sources) if (s.table.equals(table)) return s;
        return sources.get(0);
    }

    /** New report (null) or a saved one: spec0 like the website. */
    private void startFrom(GenReport.Saved s) {
        base = s;
        if (s != null) spec = GenReport.Spec.from(safeJson(s.spec));
        else { spec = new GenReport.Spec(); spec.dataset = sources.get(0).table; }
        if (src(spec.dataset) != null && !containsTable(spec.dataset)) spec.dataset = sources.get(0).table;
        saveName = s != null ? s.name : "";
        result = null; error = null;
        loadDataset();
    }

    private static JSONObject safeJson(GenReport.Spec s) { try { return s.json(); } catch (Exception e) { return new JSONObject(); } }

    private boolean containsTable(String t) { for (GenSearch.Source s : sources) if (s.table.equals(t)) return true; return false; }

    private void loadDataset() {
        page.removeAllViews();
        page.addView(loading());
        TextView wait = Ui.text(a, "Loading data…", 12, Ui.MUTED, false);
        wait.setGravity(android.view.Gravity.CENTER);
        page.addView(wait);
        final String ds = spec.dataset;
        Api.async(() -> {
            List<org.json.JSONObject> rows = GenUtil.big(api, ds + "?select=*&limit=" + GenReport.ROW_LIMIT);
            GenReport.Frame f = GenReport.readable(rows, this::loadTable);
            return new Object[]{f, rows.size()};
        }, (res, err) -> {
            if (err != null) {
                page.removeAllViews();
                add(Ui.text(a, "Could not read " + src(ds).recordType + ": " + Api.message(err), 13, Ui.RED_FG, false), 0);
                Button retry = Ui.outline(a, "Try again", Ui.TEAL);
                retry.setOnClickListener(v -> loadDataset());
                add(retry, 8);
                return;
            }
            frame = (GenReport.Frame) res[0];
            loadedRows = (Integer) res[1];
            frameDataset = ds;
            // columns default like the website (saved columns, else the search columns, else the first 8)
            List<String> keep = new ArrayList<>();
            for (String c : spec.columns) if (frame.col(c) >= 0) keep.add(c);
            if (keep.isEmpty()) for (String c : src(ds).columns) if (frame.col(c) >= 0 && keep.size() < 8) keep.add(c);
            if (keep.isEmpty()) for (int i = 0; i < Math.min(8, frame.columns.size()); i++) keep.add(frame.columns.get(i));
            spec.columns = keep;
            spec.filters.removeIf(f -> frame.col(f.column) < 0);
            spec.groupBy.removeIf(g -> frame.col(g) < 0);
            spec.measures.removeIf(m -> frame.col(m.column) < 0);
            if (!spec.sortBy.isEmpty() && frame.col(spec.sortBy) < 0) spec.sortBy = "";
            if (spec.title.isEmpty()) spec.title = base != null ? base.name : src(ds).recordType + " report";
            run(false);
        });
    }

    private List<org.json.JSONObject> loadTable(String table) throws Exception {
        List<org.json.JSONObject> hit = labelCache.get(table);
        if (hit != null) return hit;
        List<org.json.JSONObject> rows = GenUtil.big(api, table + "?select=*&limit=" + GenReport.ROW_LIMIT);
        labelCache.put(table, rows);
        return rows;
    }

    // ------------------------------------------------------------------ form
    private void sync() {
        for (int i = 0; i < filterInputs.size() && i < spec.filters.size(); i++) {
            spec.filters.get(i).value = filterInputs.get(i)[0].getText().toString();
            spec.filters.get(i).value2 = filterInputs.get(i)[1].getText().toString();
        }
        if (limitInput != null) {
            String t = limitInput.getText().toString().trim();
            int v = 0;
            try { v = t.isEmpty() ? 0 : Integer.parseInt(t); } catch (Exception ignored) { }
            spec.limit = Math.max(0, Math.min(GenReport.ROW_LIMIT, v));
        }
        if (descSwitch != null) spec.descending = descSwitch.isChecked();
        if (titleInput != null) spec.title = titleInput.getText().toString();
        if (nameInput != null) saveName = nameInput.getText().toString();
    }

    private void refreshForm() { sync(); renderForm(); }

    private String pretty(String c) { return c == null || c.isEmpty() ? "— None —" : GenReport.pretty(c); }

    private String joinPretty(List<String> cols) {
        List<String> p = new ArrayList<>();
        for (String c : cols) p.add(GenReport.pretty(c));
        return p.isEmpty() ? "—" : String.join(", ", p);
    }

    private void renderForm() {
        page.removeAllViews();
        filterInputs.clear();
        GenSearch.Source source = src(spec.dataset);

        // A · saved reports
        add(Ui.label(a, "A · Saved reports"), 0);
        String current = base == null ? "＋ New report" : base.name + " · " + src(base.spec.dataset).recordType + " · by " + (base.owner.isEmpty() ? "-" : base.owner);
        TextView pick = GenUtil.selector(a, current);
        pick.setOnClickListener(v -> {
            List<String> names = new ArrayList<>();
            names.add("＋ New report");
            for (GenReport.Saved s : saved) names.add(s.name + " · " + src(s.spec.dataset).recordType + " · by " + (s.owner.isEmpty() ? "-" : s.owner));
            GenUtil.pick(a, "Report", names, i -> startFrom(i == 0 ? null : saved.get(i - 1)));
        });
        add(pick, 2);

        // B · data & columns
        add(Ui.label(a, "B · Data & columns"), 12);
        TextView ds = GenUtil.selector(a, "Dataset: " + source.recordType + " · " + source.module);
        ds.setOnClickListener(v -> {
            List<String> names = new ArrayList<>();
            for (GenSearch.Source s : sources) names.add(s.recordType + " · " + s.module);
            GenUtil.pick(a, "Dataset", names, i -> {
                sync();
                if (sources.get(i).table.equals(spec.dataset)) return;
                spec.dataset = sources.get(i).table;
                spec.columns = new ArrayList<>(); spec.filters = new ArrayList<>(); spec.groupBy = new ArrayList<>(); spec.measures = new ArrayList<>(); spec.sortBy = "";
                spec.title = sources.get(i).recordType + " report";
                result = null; error = null;
                loadDataset();
            });
        });
        add(ds, 2);
        add(Ui.text(a, String.format(Locale.US, "%,d", frame.rows.size()) + " record(s) loaded" + (loadedRows >= GenReport.ROW_LIMIT ? " (first 10,000)" : "")
            + ". Linked IDs are shown as part numbers, party names, employees, etc.", 11.5f, Ui.MUTED, false), 4);
        if (frame.isEmpty()) {
            add(Ui.text(a, "No records in this dataset yet.", 13, Ui.TEAL_DARK, false), 10);
            return;
        }
        TextView cols = GenUtil.selector(a, "Columns (" + spec.columns.size() + "): " + joinPretty(spec.columns));
        cols.setMaxLines(3);
        cols.setOnClickListener(v -> pickOrdered("Columns (in this order)", spec.columns, picked -> { spec.columns = picked; refreshForm(); }));
        add(cols, 8);

        // C · filters
        add(Ui.label(a, "C · Filters (all must match)"), 12);
        for (int i = 0; i < spec.filters.size(); i++) addFilter(i);
        if (spec.filters.size() < 8) {
            Button addF = Ui.outline(a, "+ Add filter", Ui.TEAL);
            addF.setOnClickListener(v -> {
                sync();
                GenReport.Filter f = new GenReport.Filter();
                f.column = frame.columns.get(0);
                spec.filters.add(f);
                renderForm();
            });
            add(addF, 6);
        }

        // D · group, total & sort
        add(Ui.label(a, "D · Group, total & sort"), 12);
        TextView gb = GenUtil.selector(a, "Group by: " + joinPretty(spec.groupBy));
        gb.setMaxLines(3);
        gb.setOnClickListener(v -> pickOrdered("Group by", spec.groupBy, picked -> {
            spec.groupBy = picked;
            if (picked.isEmpty()) spec.measures = new ArrayList<>();
            refreshForm();
        }));
        add(gb, 2);
        if (!spec.groupBy.isEmpty()) {
            List<String> mcols = new ArrayList<>();
            for (GenReport.Measure m : spec.measures) mcols.add(m.column);
            TextView mc = GenUtil.selector(a, "Totals for columns: " + joinPretty(mcols));
            mc.setMaxLines(3);
            mc.setOnClickListener(v -> pickOrdered("Totals for columns", mcols, picked -> {
                List<GenReport.Measure> next = new ArrayList<>();
                for (String c : picked) {
                    String agg = "sum";
                    for (GenReport.Measure m : spec.measures) if (m.column.equals(c)) agg = m.agg;
                    next.add(new GenReport.Measure(c, agg));
                }
                spec.measures = next;
                refreshForm();
            }));
            add(mc, 8);
            for (GenReport.Measure m : spec.measures) {
                TextView ag = GenUtil.selector(a, GenReport.pretty(m.column) + ": " + GenReport.aggLabel(m.agg));
                ag.setOnClickListener(v -> GenUtil.pick(a, GenReport.pretty(m.column), Arrays.asList(GenReport.AGG_LABELS), i -> { m.agg = GenReport.AGGS[i]; refreshForm(); }));
                add(ag, 6);
            }
        }
        TextView sort = GenUtil.selector(a, "Sort by: " + pretty(spec.sortBy));
        sort.setOnClickListener(v -> {
            List<String> names = new ArrayList<>();
            names.add("— None —");
            for (String c : frame.columns) names.add(GenReport.pretty(c));
            GenUtil.pick(a, "Sort by", names, i -> { spec.sortBy = i == 0 ? "" : frame.columns.get(i - 1); refreshForm(); });
        });
        add(sort, 8);
        descSwitch = new Switch(a);
        descSwitch.setText("Highest first");
        descSwitch.setChecked(spec.descending);
        add(descSwitch, 6);
        add(Ui.text(a, "Max rows (0 = all)", 12, Ui.MUTED, false), 6);
        limitInput = Ui.input(a, "0", false);
        limitInput.setInputType(InputType.TYPE_CLASS_NUMBER);
        limitInput.setText(String.valueOf(spec.limit));
        add(limitInput, 2);
        int ci = Math.max(0, Arrays.asList(GenReport.CHARTS).indexOf(spec.chart));
        TextView chart = GenUtil.selector(a, "Chart: " + GenReport.CHART_LABELS[ci]);
        chart.setOnClickListener(v -> GenUtil.pick(a, "Chart", Arrays.asList(GenReport.CHART_LABELS), i -> { spec.chart = GenReport.CHARTS[i]; refreshForm(); }));
        add(chart, 8);

        add(Ui.label(a, "Report title"), 12);
        titleInput = Ui.input(a, "Report title", false);
        titleInput.setText(spec.title);
        add(titleInput, 2);

        Button runB = Ui.primary(a, "Show result");
        runB.setOnClickListener(v -> run(true));
        add(runB, 12);

        renderResult();
    }

    private void addFilter(int index) {
        GenReport.Filter f = spec.filters.get(index);
        LinearLayout card = Ui.card(a);
        LinearLayout head = Ui.hbox(a);
        head.addView(Ui.text(a, "Filter " + (index + 1), 12.5f, Ui.TEAL_DARK, true), Ui.weight(1));
        TextView remove = Ui.text(a, "Remove", 12.5f, Ui.RED_FG, true);
        remove.setPadding(dp(10), dp(4), dp(4), dp(4));
        remove.setOnClickListener(v -> { sync(); spec.filters.remove(index); renderForm(); });
        head.addView(remove);
        card.addView(head);
        TextView col = GenUtil.selector(a, "Column: " + GenReport.pretty(f.column));
        col.setOnClickListener(v -> {
            List<String> names = new ArrayList<>();
            for (String c : frame.columns) names.add(GenReport.pretty(c));
            GenUtil.pick(a, "Column " + (index + 1), names, i -> { sync(); f.column = frame.columns.get(i); renderForm(); });
        });
        card.addView(col, Ui.matchWrap(a, 6));
        TextView op = GenUtil.selector(a, "Condition: " + GenReport.opLabel(f.op));
        op.setOnClickListener(v -> GenUtil.pick(a, "Condition", Arrays.asList(GenReport.OP_LABELS), i -> { sync(); f.op = GenReport.OPS[i]; renderForm(); }));
        card.addView(op, Ui.matchWrap(a, 6));
        EditText v1 = Ui.input(a, "Value (dates as YYYY-MM-DD)", false);
        v1.setText(f.value);
        EditText v2 = Ui.input(a, "To (for between)", false);
        v2.setText(f.value2);
        boolean noValue = f.op.equals("is_empty") || f.op.equals("not_empty");
        v1.setVisibility(noValue ? View.GONE : View.VISIBLE);
        v2.setVisibility(f.op.equals("between") ? View.VISIBLE : View.GONE);
        card.addView(v1, Ui.matchWrap(a, 6));
        card.addView(v2, Ui.matchWrap(a, 6));
        filterInputs.add(new EditText[]{v1, v2});
        add(card, 6);
    }

    interface OrderedPicked { void picked(List<String> columns); }

    /** Multi-select that keeps the order in which columns were chosen (website multiselect order). */
    private void pickOrdered(String title, List<String> current, OrderedPicked done) {
        sync();
        List<String> names = new ArrayList<>();
        boolean[] checked = new boolean[frame.columns.size()];
        for (int i = 0; i < frame.columns.size(); i++) { names.add(GenReport.pretty(frame.columns.get(i))); checked[i] = current.contains(frame.columns.get(i)); }
        GenUtil.pickMany(a, title, names, checked, state -> {
            List<String> out = new ArrayList<>();
            for (String c : current) { int i = frame.columns.indexOf(c); if (i >= 0 && state[i]) out.add(c); }
            for (int i = 0; i < state.length; i++) if (state[i] && !out.contains(frame.columns.get(i))) out.add(frame.columns.get(i));
            done.picked(out);
        });
    }

    // ------------------------------------------------------------------ result
    private void run(boolean fromButton) {
        if (fromButton) sync();
        final GenReport.Spec s = spec;
        final GenReport.Frame f = frame;
        Api.async(() -> GenReport.build(f, s), (res, err) -> {
            result = err == null ? res : null;
            error = err == null ? null : Api.message(err);
            renderForm();
            if (fromButton) scrollToResult();
        });
    }

    private View resultAnchor;

    private void scrollToResult() {
        if (scroll == null || resultAnchor == null) return;
        scroll.post(() -> {
            int y = dp(10);
            for (int i = 0; i < page.getChildCount(); i++) {
                View v = page.getChildAt(i);
                if (v == resultAnchor) { scroll.scrollTo(0, Math.max(0, y - dp(8))); return; }
                y += v.getHeight() + dp(8);
            }
        });
    }

    private void renderResult() {
        resultAnchor = Ui.label(a, "Result" + (result != null ? " · " + String.format(Locale.US, "%,d", result.rows.size()) + " row(s)" : ""));
        add(resultAnchor, 16);
        if (error != null) {
            add(Ui.text(a, error, 13, Ui.RED_FG, false), 4);
            return;
        }
        if (result == null) return;
        String title = spec.title.trim().isEmpty() ? "QCMS Report" : spec.title.trim();
        if (result.rows.isEmpty()) {
            add(Ui.text(a, "No records match these filters.", 13, Ui.TEAL_DARK, false), 4);
        } else {
            List<List<String>> rows = new ArrayList<>();
            for (String[] r : GenReport.cells(result.rows)) rows.add(Arrays.asList(r));
            final GenReport.Result shown = result;
            final String table = spec.dataset;
            add(new DataGrid(a, title, result.headers, rows, 460, index -> {
                if (index < 0 || index >= shown.raw.size() || shown.raw.get(index) == null) return;
                sync();
                GenUtil.openRecord(a, table, shown.raw.get(index));
            }), 4);
            if (!result.grouped) add(Ui.text(a, "Tap a row to open the record.", 11, Ui.MUTED, false), 2);
            if (!spec.chart.isEmpty() && result.headers.size() >= 2) {
                GenKpi.Chart ch = GenReport.chart(result, spec.chart, title);
                if (ch != null) {
                    LinearLayout card = Ui.card(a);
                    card.addView(Ui.text(a, title, 13.5f, Ui.TEXT, true));
                    card.addView(new GenChart(a, ch), Ui.matchWrap(a, 8));
                    add(card, 10);
                } else {
                    add(Ui.text(a, "Add a Group by and a Total to draw a chart.", 12, Ui.MUTED, false), 6);
                }
            }
        }
        Button csv = Ui.outline(a, "Download CSV", Ui.TEAL);
        csv.setEnabled(!result.rows.isEmpty());
        final GenReport.Result r = result;
        csv.setOnClickListener(v -> {
            sync();
            String safe = GenUtil.safeName(title);
            GenUtil.exportCsv(a, title, safe + "_" + LocalDate.now(), GenUtil.csv(r.headers, GenReport.cells(r.rows)));
        });
        add(csv, 12);

        add(Ui.label(a, "Save report"), 12);
        nameInput = Ui.input(a, "Report name", false);
        nameInput.setText(saveName.isEmpty() ? title : saveName);
        add(nameInput, 2);
        Button save = Ui.primary(a, base != null ? "Update saved report" : "Save report");
        save.setOnClickListener(v -> {
            sync();
            final String name = saveName;
            final String owner = !api.fullName.isEmpty() ? api.fullName : (!api.email.isEmpty() ? api.email : "QCMS user");
            final String existing = base == null ? null : base.id;
            save.setEnabled(false);
            Api.async(() -> {
                GenReport.save(api, name, spec, owner, existing);
                return GenReport.saved(api);
            }, (list, err) -> {
                save.setEnabled(true);
                if (err != null) { new android.app.AlertDialog.Builder(a).setTitle("Not saved").setMessage(Api.message(err)).setPositiveButton("OK", null).show(); return; }
                List<GenReport.Saved> keep = new ArrayList<>();
                for (GenReport.Saved s : list) if (containsTable(s.spec.dataset)) keep.add(s);
                saved = keep;
                for (GenReport.Saved s : saved) if (s.name.equals(name.trim()) && (existing == null || s.id.equals(existing))) base = s;
                new android.app.AlertDialog.Builder(a).setTitle("Report saved")
                    .setMessage(name.trim() + " is saved. Anyone who can view " + src(spec.dataset).recordType + " can open it from Saved Reports.")
                    .setPositiveButton("OK", null).show();
                renderForm();
            });
        });
        add(save, 6);
        if (base != null) {
            Button del = Ui.outline(a, "Delete this saved report", Ui.ORANGE);
            del.setOnClickListener(v -> a.confirm("Delete saved report?", "\"" + base.name + "\" will no longer be listed in Saved Reports.", "Delete", () -> {
                final String id = base.id;
                Api.async(() -> { GenReport.delete(api, id); return GenReport.saved(api); }, (list, err) -> {
                    if (err != null) { a.toast(Api.message(err)); return; }
                    List<GenReport.Saved> keep = new ArrayList<>();
                    for (GenReport.Saved s : list) if (containsTable(s.spec.dataset)) keep.add(s);
                    saved = keep;
                    a.toast("Saved report deleted.");
                    startFrom(null);
                });
            }));
            add(del, 8);
        }
    }

    @Override public void reload() {
        sources = null; frame = null; frameDataset = ""; labelCache.clear(); result = null; error = null;
        a.rebuild();
    }
}
