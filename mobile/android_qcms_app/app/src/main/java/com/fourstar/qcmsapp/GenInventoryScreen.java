package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

/**
 * R39 (website R36b app_pages/inventory_reports.py): Inventory & Stock Reports - five reports, each with filters
 * (core.report_filters: search all columns, column values, date / number ranges), KPI cards, a totals row,
 * spreadsheet grids and Excel / PDF / print / e-mail export of the filtered rows:
 * a) Stock by stage per part (v_qcms_stock_by_stage, RPC qcms_stock_by_stage fallback)
 * b) Raw material stock by heat / grade / section (v_qcms_rm_stock_by_heat)
 * c) Forging stock by supplier (v_qcms_forging_stock_by_supplier) + material at OSP vendors (v_qsms_osp_register)
 * d) FG stock & customer dispatch summary (stock by stage + movement ledger)
 * e) Date-wise stock movement ledger with running net (v_qcms_stock_movement_ledger)
 * All views are security invoker - the signed-in user's RLS (company) applies.
 */
final class GenInventoryScreen extends Screen implements ExportDoc.Source {
    static final String[] TABS = {"Stock by Stage", "RM Stock by Heat", "Forging / OSP Stock", "FG Stock & Dispatch", "Stock Movement Ledger"};
    static final int ROW_LIMIT = 20000;

    static final String[][] STAGE = {
        {"Part Number", "part_number"}, {"FSI Part Number", "fsi_part_number"}, {"Part Description", "part_name"}, {"Customer", "customer_name"},
        {"Material Grade", "material_grade"}, {"Open Orders", "open_orders"}, {"Open Order Qty pcs", "open_order_qty_pcs"},
        {"Pending Order pcs", "pending_order_pcs"}, {"RM Required kg", "rm_required_kg"}, {"RM Ordered kg", "rm_ordered_kg"},
        {"RM Received kg", "rm_received_kg"}, {"RM Pending Receipt kg", "rm_pending_receipt_kg"}, {"RM at FSI kg", "rm_at_fsi_kg"},
        {"RM Sent to Forger kg", "rm_sent_to_forger_kg"}, {"RM at Forger kg", "rm_at_forger_kg"}, {"Forgings Ordered pcs", "forging_ordered_pcs"},
        {"Forgings Pending at Forger pcs", "forging_pending_at_forger_pcs"}, {"Forgings Received pcs", "forging_received_pcs"},
        {"Forgings Rejected pcs", "forging_rejected_pcs"}, {"Machining WIP pcs", "machining_wip_pcs"}, {"Machined pcs", "machined_pcs"},
        {"Machined Pending FG pcs", "machined_pending_fg_pcs"}, {"FG Produced pcs", "fg_produced_pcs"}, {"FG Stock pcs", "fg_stock_pcs"},
        {"Dispatched pcs", "dispatched_pcs"}, {"Opening RM kg", "opening_rm_kg"}, {"Opening Forging pcs", "opening_forging_pcs"},
        {"Opening Machining pcs", "opening_machining_pcs"}, {"Opening FG pcs", "opening_fg_pcs"}, {"Last Activity", "last_activity_date"}};
    static final String[][] STAGE_SEQUENCE = {
        {"Open customer orders", "Pending Order pcs", "pcs"}, {"RM ordered", "RM Ordered kg", "kg"}, {"RM pending receipt", "RM Pending Receipt kg", "kg"},
        {"RM at FSI", "RM at FSI kg", "kg"}, {"RM at forger", "RM at Forger kg", "kg"}, {"Forging pending at forger", "Forgings Pending at Forger pcs", "pcs"},
        {"Forgings received", "Forgings Received pcs", "pcs"}, {"Machining WIP", "Machining WIP pcs", "pcs"}, {"Machined, pending FG", "Machined Pending FG pcs", "pcs"},
        {"Finished goods stock", "FG Stock pcs", "pcs"}, {"Dispatched to customer", "Dispatched pcs", "pcs"}};
    static final String[][] RM = {
        {"Heat Number", "heat_number"}, {"Heat Code", "heat_code"}, {"Material Grade", "material_grade"}, {"RM Section", "rm_section"},
        {"Supplier", "supplier_name"}, {"RMTC", "rmtc_number"}, {"Part Number(s)", "part_numbers"}, {"FSI Part Number(s)", "fsi_part_numbers"},
        {"Opening kg", "opening_kg"}, {"Received kg", "received_kg"}, {"Dispatched to Forger kg", "dispatched_kg"}, {"Balance kg", "balance_kg"},
        {"Last Movement", "last_movement_date"}};
    static final String[][] FORGING = {
        {"Forging Supplier", "supplier_name"}, {"Supplier Code", "supplier_code"}, {"Part Number", "part_number"}, {"FSI Part Number", "fsi_part_number"},
        {"Part Description", "part_name"}, {"Customer", "customer_name"}, {"Material Grade", "material_grade"},
        {"RM Sent kg", "rm_sent_kg"}, {"RM Consumed kg", "rm_consumed_kg"}, {"RM at Forger kg", "rm_at_forger_kg"},
        {"Forgings Ordered pcs", "forging_ordered_pcs"}, {"Forgings Received pcs", "forging_received_pcs"},
        {"Forgings Rejected pcs", "forging_rejected_pcs"}, {"Forgings Pending pcs", "forging_pending_pcs"}, {"Last Movement", "last_movement_date"}};
    static final String[][] OSP = {
        {"OSP Vendor", "vendor_name"}, {"OSP Job", "osp_job_number"}, {"Part Number", "part_number"}, {"Heat Number", "heat_number"},
        {"OSP Process", "process_name"}, {"Material Out Date", "dispatch_date"}, {"Out Challan", "dispatch_challan"},
        {"Out Qty pcs", "quantity_dispatched"}, {"Received pcs", "quantity_received"}, {"Pending Return pcs", "quantity_outstanding"},
        {"Expected Return", "expected_return_date"}, {"Status", "status"}};
    static final String[][] LEDGER = {
        {"Date", "movement_date"}, {"Movement", "movement_type"}, {"Stage", "stage"}, {"Direction", "direction"},
        {"Part Number", "part_number"}, {"FSI Part Number", "fsi_part_number"}, {"Part Description", "part_name"}, {"Customer", "customer_name"},
        {"Material Grade", "material_grade"}, {"Heat Number", "heat_number"}, {"Supplier / Party", "party_name"}, {"Reference", "reference_no"},
        {"Customer Order", "customer_order_no"}, {"Qty kg", "qty_kg"}, {"Qty pcs", "qty_pcs"},
        {"kg In", "kg_in"}, {"kg Out", "kg_out"}, {"pcs In", "pcs_in"}, {"pcs Out", "pcs_out"}};

    // ================================================================== frame (pandas-like table: label columns, Double numbers)
    static final class Frame {
        final List<String> cols;
        final List<Object[]> rows = new ArrayList<>();
        Frame(List<String> cols) { this.cols = new ArrayList<>(cols); }
        int idx(String c) { return cols.indexOf(c); }
        double total(String c) {
            int i = idx(c);
            double t = 0;
            if (i < 0) return 0;
            for (Object[] r : rows) if (r[i] instanceof Double) t += (Double) r[i];
            return t;
        }
        int unique(String c) {
            int i = idx(c);
            Set<String> s = new LinkedHashSet<>();
            if (i >= 0) for (Object[] r : rows) s.add(str(r[i]));
            return s.size();
        }
        Frame copyEmpty() { return new Frame(cols); }
        Frame select(String... wanted) {
            List<String> keep = new ArrayList<>();
            for (String w : wanted) if (cols.contains(w)) keep.add(w);
            Frame out = new Frame(keep);
            for (Object[] r : rows) {
                Object[] n = new Object[keep.size()];
                for (int k = 0; k < keep.size(); k++) n[k] = r[idx(keep.get(k))];
                out.rows.add(n);
            }
            return out;
        }
        Frame addColumn(String name, java.util.function.Function<Object[], Object> f) {
            Frame out = new Frame(cols);
            out.cols.add(name);
            for (Object[] r : rows) {
                Object[] n = Arrays.copyOf(r, r.length + 1);
                n[r.length] = f.apply(r);
                out.rows.add(n);
            }
            return out;
        }
    }

    static boolean numeric(String label) { return label.endsWith(" kg") || label.endsWith(" pcs") || label.equals("Open Orders"); }
    static boolean dateCol(String label) { return label.equals("Date") || label.contains("Date") || label.startsWith("Last ") || label.startsWith("Expected") || label.equals("Month"); }
    static String str(Object v) { return v == null || v == JSONObject.NULL ? "" : String.valueOf(v); }
    static double num(Object v) { return v instanceof Double ? (Double) v : GenUtil.n(v); }

    static Frame frame(List<JSONObject> rows, String[][] spec) {
        List<String> cols = new ArrayList<>();
        for (String[] c : spec) cols.add(c[0]);
        Frame f = new Frame(cols);
        if (rows == null) return f;
        for (JSONObject r : rows) {
            Object[] o = new Object[spec.length];
            for (int i = 0; i < spec.length; i++) {
                Object v = r.opt(spec[i][1]);
                if (numeric(spec[i][0])) o[i] = GenUtil.n(v);
                else {
                    String sv = v == null || v == JSONObject.NULL ? "" : String.valueOf(v);
                    if (v instanceof JSONArray) {
                        JSONArray arr = (JSONArray) v;
                        StringBuilder b = new StringBuilder();
                        for (int k = 0; k < arr.length(); k++) { if (k > 0) b.append(", "); b.append(arr.optString(k, "")); }
                        sv = b.toString();
                    }
                    if (dateCol(spec[i][0]) && sv.length() > 10 && sv.charAt(4) == '-') sv = sv.substring(0, 10);
                    o[i] = sv;
                }
            }
            f.rows.add(o);
        }
        return f;
    }

    /** groupby(keys)[sumCols].sum() in first-seen order. */
    static Frame groupSum(Frame f, String[] keys, String[] sums) {
        List<String> cols = new ArrayList<>(Arrays.asList(keys));
        cols.addAll(Arrays.asList(sums));
        Frame out = new Frame(cols);
        LinkedHashMap<String, Object[]> acc = new LinkedHashMap<>();
        for (Object[] r : f.rows) {
            StringBuilder k = new StringBuilder();
            for (String key : keys) k.append(str(r[f.idx(key)])).append('\u0000');
            Object[] row = acc.get(k.toString());
            if (row == null) {
                row = new Object[cols.size()];
                for (int i = 0; i < keys.length; i++) row[i] = str(r[f.idx(keys[i])]);
                for (int i = 0; i < sums.length; i++) row[keys.length + i] = 0.0;
                acc.put(k.toString(), row);
            }
            for (int i = 0; i < sums.length; i++) { int c = f.idx(sums[i]); if (c >= 0) row[keys.length + i] = (Double) row[keys.length + i] + num(r[c]); }
        }
        out.rows.addAll(acc.values());
        return out;
    }

    // ================================================================== filters (core.report_filters)
    static final class Filter {
        String search = "";
        final LinkedHashMap<String, Set<String>> values = new LinkedHashMap<>();
        final LinkedHashMap<String, String[]> ranges = new LinkedHashMap<>();   // from / to (date) or min / max (number)
        boolean active() { return !search.trim().isEmpty() || !values.isEmpty() || !ranges.isEmpty(); }
    }

    private static final Map<String, Filter> FILTERS = new HashMap<>();
    private static final Map<String, Boolean> TOGGLES = new HashMap<>();
    private static int tabIndex = 0;

    static Filter filter(String key) { return FILTERS.computeIfAbsent(key, k -> new Filter()); }
    static boolean toggle(String key, boolean dflt) { Boolean b = TOGGLES.get(key); return b == null ? dflt : b; }

    static Frame apply(Frame f, Filter flt) {
        if (flt == null || !flt.active()) return f;
        Frame out = f.copyEmpty();
        String q = flt.search.trim().toLowerCase(Locale.ROOT);
        for (Object[] r : f.rows) {
            boolean ok = true;
            if (!q.isEmpty()) {
                StringBuilder hay = new StringBuilder();
                for (Object v : r) hay.append(cell(v, "")).append(' ').append(str(v)).append(' ');
                ok = hay.toString().toLowerCase(Locale.ROOT).contains(q);
            }
            for (Map.Entry<String, Set<String>> e : flt.values.entrySet()) {
                int i = f.idx(e.getKey());
                if (!ok || i < 0) continue;
                ok = e.getValue().contains(str(r[i]).isEmpty() ? "(blank)" : str(r[i]));
            }
            for (Map.Entry<String, String[]> e : flt.ranges.entrySet()) {
                int i = f.idx(e.getKey());
                if (!ok || i < 0) continue;
                String lo = e.getValue()[0], hi = e.getValue()[1];
                if (numeric(e.getKey())) {
                    double v = num(r[i]);
                    if (!lo.isEmpty()) ok = v >= GenUtil.n(lo);
                    if (ok && !hi.isEmpty()) ok = v <= GenUtil.n(hi);
                } else {
                    String d = str(r[i]);
                    if (d.isEmpty()) { ok = false; continue; }
                    d = d.length() >= 10 ? d.substring(0, 10) : d;
                    if (!lo.isEmpty()) ok = d.compareTo(lo) >= 0;
                    if (ok && !hi.isEmpty()) ok = d.compareTo(hi) <= 0;
                }
            }
            if (ok) out.rows.add(r);
        }
        return out;
    }

    static String cell(Object v, String col) {
        if (v instanceof Double) {
            double d = (Double) v;
            int dec = col.endsWith(" pcs") || col.equals("Open Orders") || col.equals("Parts with stock") ? 0 : 3;
            return Ui.num(d, dec);
        }
        return str(v);
    }

    /** Frame + TOTAL row (core.report_filters.totals_row): sums of the number columns, label in labelCol. */
    static Frame totals(Frame f, String labelCol, String... skip) {
        if (f.rows.isEmpty()) return f;
        Frame out = f.copyEmpty();
        out.rows.addAll(f.rows);
        Object[] t = new Object[f.cols.size()];
        List<String> sk = Arrays.asList(skip);
        for (int i = 0; i < f.cols.size(); i++) {
            String c = f.cols.get(i);
            boolean isNum = false;
            for (Object[] r : f.rows) if (r[i] instanceof Double) { isNum = true; break; }
            t[i] = isNum && !sk.contains(c) ? (Object) GenUtil.round(f.total(c), 3) : "";
        }
        int li = f.idx(labelCol);
        t[li < 0 ? 0 : li] = "TOTAL";
        out.rows.add(t);
        return out;
    }

    // ================================================================== screen state
    private List<JSONObject> stageRows, ledgerRows, rmRows, forgingRows, ospRows;
    private final Map<String, String> warnings = new LinkedHashMap<>();
    /** Tables of the tab shown (export). */
    private final LinkedHashMap<String, Frame> shown = new LinkedHashMap<>();
    private LinearLayout results;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private Runnable pending;

    GenInventoryScreen(MainActivity a) { super(a); }

    @Override public String title() { return "Inventory & Stock Reports"; }
    @Override public String subtitle() { return TABS[tabIndex] + " · filters · totals · Excel / PDF"; }
    @Override public int tab() { return Catalog.MORE; }

    /** Every row of a view / table (pages of 1000; the API caps one response). Background thread. */
    private List<JSONObject> all(String path) throws Exception {
        List<JSONObject> out = new ArrayList<>();
        for (int offset = 0; offset < ROW_LIMIT; offset += 1000) {
            List<JSONObject> page = GenUtil.big(api, path + (path.contains("?") ? "&" : "?") + "limit=1000&offset=" + offset);
            out.addAll(page);
            if (page.size() < 1000) break;
        }
        return out;
    }

    private List<JSONObject> safe(String label, String path) {
        try { return all(path); }
        catch (Exception e) {
            warnings.put(label, label + " could not be read: " + Api.message(e) + " Apply the R36b inventory migration if this is a new installation.");
            return new ArrayList<>();
        }
    }

    @Override
    public View build() {
        newPage();
        List<String> tabs = Arrays.asList(TABS);
        add(GenUtil.chips(a, tabs, tabIndex, i -> { tabIndex = i; a.setSubtitle(subtitle()); renderTab(); }), 0);
        results = Ui.vbox(a);
        add(results, 8);
        if (stageRows != null) { renderTab(); return scroll; }
        results.addView(loading());
        Api.async(() -> {
            warnings.clear();
            List<JSONObject> stage;
            try { stage = all("v_qcms_stock_by_stage?select=*"); }
            catch (Exception viewErr) {
                try { stage = GenUtil.list(api.rpcRows("qcms_stock_by_stage", new JSONObject().put("p_part_id", JSONObject.NULL))); }
                catch (Exception rpcErr) { warnings.put("stage", "Stock by stage is unavailable: " + Api.message(rpcErr)); stage = new ArrayList<>(); }
            }
            ledgerRows = safe("v_qcms_stock_movement_ledger", "v_qcms_stock_movement_ledger?select=*&order=movement_date.asc");
            rmRows = safe("v_qcms_rm_stock_by_heat", "v_qcms_rm_stock_by_heat?select=*&order=last_movement_date.desc.nullslast");
            forgingRows = safe("v_qcms_forging_stock_by_supplier", "v_qcms_forging_stock_by_supplier?select=*");
            ospRows = safe("v_qsms_osp_register", "v_qsms_osp_register?select=*&order=created_at.desc");
            return stage;
        }, (stage, err) -> {
            if (err != null) { results.removeAllViews(); results.addView(error(err, this::reload)); return; }
            stageRows = stage;
            renderTab();
        });
        return scroll;
    }

    @Override public void reload() { stageRows = null; a.rebuild(); }

    // ------------------------------------------------------------------ tab layout: filter panels on top, results below
    private LinearLayout body;

    private void renderTab() {
        if (results == null || stageRows == null) return;
        results.removeAllViews();
        for (String w : warnings.values()) {
            TextView t = Ui.text(a, w, 12, Ui.AMBER_FG, false);
            t.setBackground(Ui.round(Ui.AMBER_BG, 0, 0, 10, a));
            t.setPadding(dp(10), dp(8), dp(10), dp(8));
            results.addView(t, Ui.matchWrap(a, 6));
        }
        LinearLayout panels = Ui.vbox(a);
        results.addView(panels, Ui.matchWrap(a, 4));
        body = Ui.vbox(a);
        results.addView(body, Ui.matchWrap(a, 8));
        switch (tabIndex) {
            case 0:
                toggleRow(panels, "inv_stage_hide_zero", "Only parts with stock, orders or movements", true);
                panel(panels, "inv_stock_by_stage", "Stock by stage", stageFrame(), "Customer", "Part Number", "FSI Part Number", "Material Grade", "Last Activity");
                break;
            case 1:
                toggleRow(panels, "inv_rm_balance_only", "Only heats with balance", false);
                panel(panels, "inv_rm_by_heat", "RM stock by heat", frame(rmRows, RM), "Heat Number", "Material Grade", "RM Section", "Supplier", "Last Movement");
                break;
            case 2:
                panel(panels, "inv_forging_stock", "Forging stock", frame(forgingRows, FORGING), "Forging Supplier", "Customer", "Part Number", "Material Grade");
                toggleRow(panels, "inv_osp_pending_only", "OSP: only jobs pending return", true);
                panel(panels, "inv_osp_stock", "OSP vendors", frame(ospRows, OSP), "OSP Vendor", "OSP Process", "Part Number", "Status", "Material Out Date");
                break;
            case 3:
                panel(panels, "inv_fg_stock", "FG stock", fgBase(), "Customer", "Part Number", "FSI Part Number", "Last Activity");
                panel(panels, "inv_fg_dispatch", "Customer dispatches", dispatchBase(), "Customer", "Part Number", "Date");
                break;
            default:
                panel(panels, "inv_movement_ledger", "Movement ledger", frame(ledgerRows, LEDGER), "Part Number", "Heat Number", "Movement", "Stage", "Date");
        }
        refresh();
    }

    private void refresh() {
        if (body == null) return;
        body.removeAllViews();
        shown.clear();
        switch (tabIndex) {
            case 0: tabStage(); break;
            case 1: tabRm(); break;
            case 2: tabForgingOsp(); break;
            case 3: tabFg(); break;
            default: tabLedger();
        }
        Button export = Ui.outline(a, "Export · Excel / PDF / Print / Email", Ui.TEAL_DARK);
        export.setOnClickListener(v -> ExportKit.menu(a, doc()));
        body.addView(export, Ui.matchWrap(a, 14));
    }

    private void later() {
        if (pending != null) handler.removeCallbacks(pending);
        pending = this::refresh;
        handler.postDelayed(pending, 450);
    }

    private void toggleRow(LinearLayout parent, String key, String label, boolean dflt) {
        Switch sw = new Switch(a);
        sw.setText(label);
        sw.setTextColor(Ui.TEXT);
        sw.setChecked(toggle(key, dflt));
        sw.setOnCheckedChangeListener((b, on) -> { TOGGLES.put(key, on); refresh(); });
        parent.addView(sw, Ui.matchWrap(a, 6));
    }

    /** Filter panel: search all columns + column filters (values / date range / number range) as removable chips. */
    private void panel(LinearLayout parent, String key, String title, Frame base, String... defaults) {
        Filter flt = filter(key);
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "Filters · " + title, 12.5f, Ui.TEAL_DARK, true));
        EditText search = Ui.input(a, "Search all columns: part, heat, supplier, number, status…", false);
        search.setText(flt.search);
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
            @Override public void afterTextChanged(Editable e) { flt.search = e.toString(); later(); }
        });
        card.addView(search, Ui.matchWrap(a, 6));
        LinearLayout chips = Ui.vbox(a);
        card.addView(chips, Ui.matchWrap(a, 4));
        Runnable[] drawChips = new Runnable[1];
        drawChips[0] = () -> {
            chips.removeAllViews();
            List<String[]> active = new ArrayList<>();
            for (Map.Entry<String, Set<String>> e : flt.values.entrySet()) active.add(new String[]{"v", e.getKey(), e.getKey() + ": " + String.join(", ", e.getValue())});
            for (Map.Entry<String, String[]> e : flt.ranges.entrySet()) {
                String lo = e.getValue()[0], hi = e.getValue()[1];
                active.add(new String[]{"r", e.getKey(), e.getKey() + ": " + (lo.isEmpty() ? "…" : lo) + " → " + (hi.isEmpty() ? "…" : hi)});
            }
            for (String[] f : active) {
                TextView chip = Ui.text(a, f[2] + "  ✕", 12, Ui.TEXT, false);
                chip.setPadding(dp(10), dp(6), dp(10), dp(6));
                chip.setBackground(Ui.round(Ui.TEAL_SOFT, Ui.LINE, 1, 14, a));
                chip.setOnClickListener(v -> {
                    if ("v".equals(f[0])) flt.values.remove(f[1]); else flt.ranges.remove(f[1]);
                    drawChips[0].run();
                    refresh();
                });
                chips.addView(chip, Ui.matchWrap(a, 4));
            }
            LinearLayout row = Ui.hbox(a);
            row.setGravity(Gravity.CENTER_VERTICAL);
            TextView add = Ui.text(a, "＋ Filter by column", 12.5f, Ui.TEAL_DARK, true);
            add.setPadding(0, dp(8), dp(12), dp(4));
            add.setOnClickListener(v -> pickColumn(base, flt, defaults, () -> { drawChips[0].run(); refresh(); }));
            row.addView(add);
            if (flt.active()) {
                TextView clear = Ui.text(a, "Clear all", 12.5f, Ui.RED_FG, true);
                clear.setPadding(dp(12), dp(8), 0, dp(4));
                clear.setOnClickListener(v -> {
                    flt.values.clear(); flt.ranges.clear(); flt.search = "";
                    search.setText("");
                    drawChips[0].run();
                    refresh();
                });
                row.addView(clear);
            }
            chips.addView(row);
        };
        drawChips[0].run();
        parent.addView(card, Ui.matchWrap(a, 6));
    }

    private void pickColumn(Frame base, Filter flt, String[] defaults, Runnable changed) {
        List<String> cols = new ArrayList<>();
        for (String d : defaults) if (base.cols.contains(d)) cols.add(d);
        for (String c : base.cols) if (!cols.contains(c)) cols.add(c);
        GenUtil.pick(a, "Filter by column", cols, i -> {
            String col = cols.get(i);
            if (numeric(col) || dateCol(col)) rangeDialog(col, flt, changed);
            else valuesDialog(base, col, flt, changed);
        });
    }

    private void rangeDialog(String col, Filter flt, Runnable changed) {
        boolean isDate = !numeric(col);
        LinearLayout box = Ui.vbox(a);
        box.setPadding(dp(16), dp(8), dp(16), 0);
        String[] cur = flt.ranges.get(col);
        EditText lo = Ui.input(a, isDate ? "From (yyyy-mm-dd)" : "Minimum", false);
        EditText hi = Ui.input(a, isDate ? "To (yyyy-mm-dd)" : "Maximum", false);
        if (cur != null) { lo.setText(cur[0]); hi.setText(cur[1]); }
        else if (isDate) { lo.setText(LocalDate.now().withDayOfMonth(1).toString()); hi.setText(LocalDate.now().toString()); }
        box.addView(lo);
        box.addView(hi, Ui.matchWrap(a, 8));
        new AlertDialog.Builder(a).setTitle(col).setView(box)
            .setPositiveButton("Apply", (d, w) -> {
                String l = lo.getText().toString().trim(), h = hi.getText().toString().trim();
                if (isDate && (!l.isEmpty() && !l.matches("\\d{4}-\\d{2}-\\d{2}") || !h.isEmpty() && !h.matches("\\d{4}-\\d{2}-\\d{2}"))) { a.toast("Dates as yyyy-mm-dd, e.g. " + LocalDate.now()); return; }
                if (l.isEmpty() && h.isEmpty()) flt.ranges.remove(col); else flt.ranges.put(col, new String[]{l, h});
                changed.run();
            })
            .setNegativeButton("Cancel", null).show();
    }

    private void valuesDialog(Frame base, String col, Filter flt, Runnable changed) {
        int i = base.idx(col);
        TreeSet<String> distinct = new TreeSet<>();
        for (Object[] r : base.rows) { String v = str(r[i]); distinct.add(v.isEmpty() ? "(blank)" : v); if (distinct.size() > 400) break; }
        List<String> names = new ArrayList<>(distinct);
        if (names.isEmpty()) { a.toast("No values in " + col + "."); return; }
        Set<String> cur = flt.values.getOrDefault(col, new LinkedHashSet<>());
        boolean[] checked = new boolean[names.size()];
        for (int k = 0; k < names.size(); k++) checked[k] = cur.contains(names.get(k));
        GenUtil.pickMany(a, col, names, checked, state -> {
            Set<String> chosen = new LinkedHashSet<>();
            for (int k = 0; k < state.length; k++) if (state[k]) chosen.add(names.get(k));
            if (chosen.isEmpty()) flt.values.remove(col); else flt.values.put(col, chosen);
            changed.run();
        });
    }

    // ------------------------------------------------------------------ shared output helpers
    private void section(String title, String sub) {
        body.addView(Ui.label(a, title), Ui.matchWrap(a, 14));
        if (sub != null && !sub.isEmpty()) body.addView(Ui.text(a, sub, 11.5f, Ui.MUTED, false));
    }

    private void tiles(String[][] items) {
        List<View> views = new ArrayList<>();
        for (String[] t : items) views.add(GenUtil.tile(a, "", t[0], t[1], t[2], t.length > 3 ? t[3] : "neutral"));
        GenUtil.grid2(a, body, views, 8);
    }

    private void grid(String title, Frame f, String labelCol, int heightDp, String... skip) {
        Frame t = totals(f, labelCol, skip);
        shown.put(title, t);
        if (f.rows.isEmpty()) { body.addView(Ui.empty(a, "No rows match."), Ui.matchWrap(a, 6)); return; }
        List<List<String>> rows = new ArrayList<>();
        for (Object[] r : t.rows) {
            List<String> line = new ArrayList<>();
            for (int i = 0; i < r.length; i++) line.add(cell(r[i], t.cols.get(i)));
            rows.add(line);
        }
        body.addView(new DataGrid(a, title, t.cols, rows, heightDp, null), Ui.matchWrap(a, 8));
    }

    static String kg(double v) { return Ui.num(v, 3) + " kg"; }
    static String pcs(double v) { return Ui.num(v, 0) + " pcs"; }

    // ------------------------------------------------------------------ a) stock by stage
    private Frame stageFrame() { return frame(stageRows, STAGE); }

    private Frame stageFiltered() {
        Frame f = stageFrame();
        if (toggle("inv_stage_hide_zero", true)) {
            Frame out = f.copyEmpty();
            for (Object[] r : f.rows) {
                double act = 0;
                for (int i = 0; i < f.cols.size(); i++) if (numeric(f.cols.get(i))) act += Math.abs(num(r[i]));
                if (act > 0) out.rows.add(r);
            }
            f = out;
        }
        return apply(f, filter("inv_stock_by_stage"));
    }

    private void tabStage() {
        section("STOCK BY STAGE · PER PART", "RM kg at FSI and at forger, forgings, machining WIP, FG stock, dispatched and open order quantity");
        Frame f = stageFiltered();
        tiles(new String[][]{
            {"Parts", Ui.num(f.rows.size(), 0), "matching the filters"},
            {"RM at FSI", kg(f.total("RM at FSI kg")), "received − sent + opening", "good"},
            {"RM at Forger", kg(f.total("RM at Forger kg")), "sent − consumed", "warning"},
            {"Forgings at Forger", pcs(f.total("Forgings Pending at Forger pcs")), "ordered − received − rejected", "warning"},
            {"Machining WIP", pcs(f.total("Machining WIP pcs")), "forgings in machining"},
            {"FG Stock", pcs(f.total("FG Stock pcs")), "available to dispatch", "good"},
            {"Pending Orders", pcs(f.total("Pending Order pcs")), "open order − dispatched", "critical"}});
        grid("Stock by Stage", f, "Part Number", 460);
        section("STAGE TOTALS", "Quantities of the filtered parts at every stage");
        Frame st = new Frame(GenUtil.listOf("Stage", "Quantity", "Unit", "Parts with stock"));
        for (String[] s : STAGE_SEQUENCE) {
            int i = f.idx(s[1]);
            double parts = 0;
            if (i >= 0) for (Object[] r : f.rows) if (num(r[i]) > 0) parts++;
            st.rows.add(new Object[]{s[0], GenUtil.round(f.total(s[1]), 3), s[2], parts});
        }
        shown.put("Stage Totals", st);
        List<List<String>> rows = new ArrayList<>();
        for (Object[] r : st.rows) rows.add(GenUtil.listOf(str(r[0]), Ui.num((Double) r[1], "kg".equals(r[2]) ? 3 : 0), str(r[2]), Ui.num((Double) r[3], 0)));
        body.addView(new DataGrid(a, "Stage Totals", st.cols, rows, 380, null), Ui.matchWrap(a, 8));
    }

    // ------------------------------------------------------------------ b) RM by heat
    private void tabRm() {
        section("RAW MATERIAL STOCK BY HEAT / GRADE / SECTION", "Opening + received − dispatched to forger, in kg, with supplier, RMTC and parts");
        Frame f = frame(rmRows, RM);
        if (toggle("inv_rm_balance_only", false)) {
            Frame out = f.copyEmpty();
            int b = f.idx("Balance kg");
            for (Object[] r : f.rows) if (Math.abs(num(r[b])) > 0.0005) out.rows.add(r);
            f = out;
        }
        f = apply(f, filter("inv_rm_by_heat"));
        tiles(new String[][]{
            {"Heats", Ui.num(f.rows.isEmpty() ? 0 : f.unique("Heat Number"), 0), "heat / grade / section rows"},
            {"Opening", kg(f.total("Opening kg")), "opening RM stock"},
            {"Received", kg(f.total("Received kg")), "RM receipts", "good"},
            {"Sent to Forger", kg(f.total("Dispatched to Forger kg")), "RM issued", "warning"},
            {"Balance", kg(f.total("Balance kg")), "RM stock at FSI", "good"}});
        grid("RM Stock by Heat", f, "Heat Number", 460);
        if (!f.rows.isEmpty()) {
            section("GRADE / SECTION SUMMARY", "");
            grid("Grade Section Summary", groupSum(f, new String[]{"Material Grade", "RM Section"},
                new String[]{"Opening kg", "Received kg", "Dispatched to Forger kg", "Balance kg"}), "Material Grade", 320);
        }
    }

    // ------------------------------------------------------------------ c) forging / OSP
    private void tabForgingOsp() {
        section("FORGING STOCK AT FORGING SUPPLIERS", "RM sent / consumed / at forger and forgings ordered, received and pending, by supplier and part");
        Frame forging = apply(frame(forgingRows, FORGING), filter("inv_forging_stock"));
        Frame osp = frame(ospRows, OSP);
        if (toggle("inv_osp_pending_only", true)) {
            Frame out = osp.copyEmpty();
            int p = osp.idx("Pending Return pcs");
            for (Object[] r : osp.rows) if (num(r[p]) > 0) out.rows.add(r);
            osp = out;
        }
        osp = apply(osp, filter("inv_osp_stock"));
        tiles(new String[][]{
            {"Forging Suppliers", Ui.num(forging.rows.isEmpty() ? 0 : forging.unique("Forging Supplier"), 0), "with movements"},
            {"RM at Forgers", kg(forging.total("RM at Forger kg")), "sent − consumed", "warning"},
            {"Forgings Pending", pcs(forging.total("Forgings Pending pcs")), "at forging suppliers", "warning"},
            {"At OSP Vendors", pcs(osp.total("Pending Return pcs")), "pending return"}});
        grid("Forging Stock", forging, "Forging Supplier", 420);
        section("MATERIAL AT OSP VENDORS · PENDING RETURN", "OSP jobs: material out, received back and balance at vendor");
        grid("OSP Pending", osp, "OSP Vendor", 420);
        if (!forging.rows.isEmpty() || !osp.rows.isEmpty()) {
            section("SUPPLIER SUMMARY", "");
            Frame sup = new Frame(GenUtil.listOf("Supplier", "Type", "RM at Forger kg", "Forgings Pending pcs", "OSP Pending Return pcs"));
            for (Object[] r : groupSum(forging, new String[]{"Forging Supplier"}, new String[]{"RM at Forger kg", "Forgings Pending pcs"}).rows)
                sup.rows.add(new Object[]{r[0], "Forging", r[1], r[2], 0.0});
            for (Object[] r : groupSum(osp, new String[]{"OSP Vendor"}, new String[]{"Pending Return pcs"}).rows)
                sup.rows.add(new Object[]{r[0], "OSP", 0.0, 0.0, r[1]});
            grid("Supplier Summary", sup, "Supplier", 320);
        }
    }

    // ------------------------------------------------------------------ d) FG stock & dispatch
    private Frame fgBase() {
        Frame st = stageFrame().select("Part Number", "FSI Part Number", "Part Description", "Customer", "Material Grade", "Open Orders", "Open Order Qty pcs",
            "Machined Pending FG pcs", "FG Produced pcs", "Opening FG pcs", "FG Stock pcs", "Dispatched pcs", "Pending Order pcs", "Last Activity");
        Frame out = st.copyEmpty();
        for (Object[] r : st.rows) {
            double s = 0;
            for (String c : new String[]{"FG Produced pcs", "Opening FG pcs", "FG Stock pcs", "Dispatched pcs", "Pending Order pcs"}) s += num(r[st.idx(c)]);
            if (s > 0) out.rows.add(r);
        }
        return out;
    }

    private Frame dispatchBase() {
        Frame l = frame(ledgerRows, LEDGER);
        Frame d = l.copyEmpty();
        int m = l.idx("Movement");
        for (Object[] r : l.rows) if ("CUSTOMER DISPATCH".equals(str(r[m]))) d.rows.add(r);
        return d.select("Date", "Customer", "Part Number", "FSI Part Number", "Part Description", "Heat Number", "Reference", "Customer Order", "Qty pcs");
    }

    private void tabFg() {
        section("FINISHED GOODS STOCK", "FG produced, FG stock, dispatched and pending customer orders per part");
        Frame fg = apply(fgBase(), filter("inv_fg_stock"));
        int pend = fg.idx("Pending Order pcs"), stock = fg.idx("FG Stock pcs");
        fg = fg.addColumn("Short vs Pending pcs", r -> Math.max(0.0, num(r[pend]) - num(r[stock])));
        tiles(new String[][]{
            {"FG Stock", pcs(fg.total("FG Stock pcs")), "available", "good"},
            {"Dispatched", pcs(fg.total("Dispatched pcs")), "to customers"},
            {"Pending Orders", pcs(fg.total("Pending Order pcs")), "open order − dispatched", "critical"},
            {"FG Shortfall", pcs(fg.total("Short vs Pending pcs")), "pending − FG stock", "warning"}});
        grid("FG Stock", fg, "Part Number", 420);
        section("CUSTOMER DISPATCH REGISTER", "Every customer dispatch with invoice / reference");
        Frame dispatch = apply(dispatchBase(), filter("inv_fg_dispatch"));
        grid("Customer Dispatches", dispatch, "Date", 380);
        if (!dispatch.rows.isEmpty()) {
            section("DISPATCH SUMMARY BY CUSTOMER / MONTH", "");
            int di = dispatch.idx("Date");
            Frame withMonth = dispatch.addColumn("Month", r -> str(r[di]).length() >= 7 ? str(r[di]).substring(0, 7) : "");
            Frame summary = groupSum(withMonth, new String[]{"Month", "Customer", "Part Number"}, new String[]{"Qty pcs"});
            summary.rows.sort((x, y) -> str(x[0]).compareTo(str(y[0])));
            grid("Dispatch Summary", summary, "Month", 320);
        }
    }

    // ------------------------------------------------------------------ e) movement ledger
    private void tabLedger() {
        section("STOCK MOVEMENT LEDGER", "Date-wise receipts and issues: opening, RM receipt / issue, forging receipt, machining, FG, dispatch, OSP out / in");
        Frame f = apply(frame(ledgerRows, LEDGER), filter("inv_movement_ledger"));
        int di = f.idx("Date"), mi = f.idx("Movement");
        f.rows.sort((x, y) -> str(x[di]).equals(str(y[di])) ? str(x[mi]).compareTo(str(y[mi])) : str(x[di]).compareTo(str(y[di])));
        int ki = f.idx("kg In"), ko = f.idx("kg Out"), pi = f.idx("pcs In"), po = f.idx("pcs Out");
        double[] run = {0, 0};
        Frame withKg = f.addColumn("Running Net kg", r -> { run[0] += num(r[ki]) - num(r[ko]); return GenUtil.round(run[0], 3); });
        Frame out = withKg.addColumn("Running Net pcs", r -> { run[1] += num(r[pi]) - num(r[po]); return (double) Math.round(run[1]); });
        tiles(new String[][]{
            {"Movements", Ui.num(out.rows.size(), 0), "matching the filters"},
            {"kg In / Out", Ui.num(out.total("kg In"), 3) + " / " + Ui.num(out.total("kg Out"), 3), "RM receipts / issues"},
            {"pcs In / Out", Ui.num(out.total("pcs In"), 0) + " / " + Ui.num(out.total("pcs Out"), 0), "receipts / issues"}});
        body.addView(Ui.text(a, "Running Net columns add up the filtered rows in date order – filter one part or heat for a true stock card.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 6));
        grid("Stock Movement Ledger", out, "Date", 520, "Running Net kg", "Running Net pcs");
    }

    // ------------------------------------------------------------------ export
    private ExportDoc doc() {
        ExportDoc d = new ExportDoc(TABS[tabIndex] + " Report").subtitle("Inventory & Stock Reports").file("QCMS_Inventory_" + GenUtil.safeName(TABS[tabIndex]));
        d.kind = "Inventory Report";
        ExportDoc.Section s = d.section("Filters");
        boolean any = false;
        for (Map.Entry<String, Filter> e : FILTERS.entrySet()) {
            if (!e.getKey().startsWith("inv_") || !e.getValue().active()) continue;
            Filter f = e.getValue();
            StringBuilder b = new StringBuilder();
            if (!f.search.trim().isEmpty()) b.append("Search \"").append(f.search.trim()).append("\"");
            for (Map.Entry<String, Set<String>> v : f.values.entrySet()) b.append(b.length() > 0 ? "; " : "").append(v.getKey()).append(": ").append(String.join(", ", v.getValue()));
            for (Map.Entry<String, String[]> r : f.ranges.entrySet()) b.append(b.length() > 0 ? "; " : "").append(r.getKey()).append(": ").append(r.getValue()[0]).append(" → ").append(r.getValue()[1]);
            s.pair(Ui.pretty(e.getKey().replace("inv_", "").toUpperCase(Locale.ROOT)), b.toString());
            any = true;
        }
        if (!any) s.pair("Filters", "None");
        for (Map.Entry<String, Frame> e : shown.entrySet()) {
            Frame f = e.getValue();
            List<List<String>> rows = new ArrayList<>();
            for (Object[] r : f.rows) {
                List<String> line = new ArrayList<>();
                for (int i = 0; i < r.length; i++) line.add(r[i] instanceof Double ? GenUtil.cell((Double) r[i]) : str(r[i]));
                rows.add(line);
            }
            d.table(e.getKey(), new ArrayList<>(f.cols), rows);
        }
        return d;
    }

    @Override public ExportDoc export() { return doc(); }
}
