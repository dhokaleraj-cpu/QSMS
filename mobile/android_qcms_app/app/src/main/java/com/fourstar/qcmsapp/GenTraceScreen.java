package com.fourstar.qcmsapp;

import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Traceability (website supply_chain.render_traceability): global search over every Supply Chain
 * field of every Customer Order, then the complete history, genealogy and forging supplier RM
 * balance of one order. Second tab: heat / batch genealogy from v_qsms_trace_events.
 */
final class GenTraceScreen extends Screen {
    /** Entry point for OrderTrackerScreen's "Open traceability" button. */
    static Screen forOrder(MainActivity a, String customerOrderId) { return new OrderScreen(a, customerOrderId); }

    private static int mode = 0;          // 0 = customer order, 1 = heat / batch
    private static String orderQuery = "", heatQuery = "";
    private GenTrace.SearchData data;
    private LinearLayout results;
    private List<JSONObject> heatRows;

    GenTraceScreen(MainActivity a) { super(a); }

    @Override public String title() { return "Traceability"; }
    @Override public String subtitle() { return "Customer, Part, Material, RMTC, Heat, supplier and every linked stage"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        add(GenUtil.chips(a, GenUtil.listOf("Customer order traceability", "Heat / batch genealogy"), mode, i -> { mode = i; a.rebuild(); }), 0);
        if (mode == 0) buildOrders(); else buildHeat();
        return scroll;
    }

    // ------------------------------------------------------------------ customer orders
    private void buildOrders() {
        add(Ui.label(a, "Global search · all Supply Chain fields"), 10);
        EditText search = Ui.input(a, "Order, PosNr, customer, part, grade, supplier, RMTC, Heat, GRN, dispatch, invoice, ASN…", false);
        search.setText(orderQuery);
        add(search, 2);
        results = Ui.vbox(a);
        add(results, 8);
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
            @Override public void afterTextChanged(Editable e) { orderQuery = e.toString(); if (data != null) showOrders(); }
        });
        if (data != null) { showOrders(); return; }
        results.addView(loading());
        Api.async(() -> GenTrace.searchData(api), (d, err) -> {
            results.removeAllViews();
            if (err != null) { results.addView(error(err, this::reload)); return; }
            data = d;
            showOrders();
        });
    }

    private void showOrders() {
        results.removeAllViews();
        List<JSONObject> matches = GenTrace.match(data, orderQuery);
        results.addView(Ui.label(a, "A · Global order search results · " + matches.size()), Ui.matchWrap(a, 0));
        if (matches.isEmpty()) {
            results.addView(Ui.text(a, "No matching Supply Chain record found.", 13, Ui.TEAL_DARK, false), Ui.matchWrap(a, 4));
            return;
        }
        List<String> headers = new ArrayList<>(data.displayHeaders);
        List<String[]> rows = new ArrayList<>();
        for (JSONObject o : matches) rows.add(data.display.get(GenUtil.str(o.opt("id"))));
        List<List<String>> grid = new ArrayList<>();
        for (String[] r : rows) grid.add(Arrays.asList(r));
        results.addView(Ui.text(a, "Tap an order to see its complete supply chain history and genealogy.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 2));
        results.addView(new DataGrid(a, "Supply Chain Global Search Results", headers, grid, 460, index -> {
            if (index >= 0 && index < matches.size()) a.push(new OrderScreen(a, GenUtil.str(matches.get(index).opt("id"))));
        }), Ui.matchWrap(a, 4));
        Button csv = Ui.outline(a, "Export results (CSV)", Ui.TEAL);
        csv.setOnClickListener(v -> GenUtil.exportCsv(a, "Supply Chain Global Search Results", "QCMS_Supply_Chain_Search_" + LocalDate.now(), GenUtil.csv(headers, rows)));
        results.addView(csv, Ui.matchWrap(a, 10));
    }

    // ------------------------------------------------------------------ heat / batch genealogy
    private void buildHeat() {
        add(Ui.label(a, "Heat / batch genealogy"), 10);
        add(Ui.text(a, "Search a Heat No., heat code, FSI batch, vendor batch, inward / RMTC / OSP / dispatch number or part: every linked event from RMTC to customer dispatch is shown.", 12, Ui.MUTED, false), 0);
        LinearLayout bar = Ui.hbox(a);
        EditText search = Ui.input(a, "Heat, batch, part, inward, RMTC, OSP, dispatch…", false);
        search.setText(heatQuery);
        search.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        bar.addView(search, Ui.weight(1));
        Button go = Ui.primary(a, "Search");
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(96), dp(48));
        lp.leftMargin = dp(8);
        bar.addView(go, lp);
        add(bar, 6);
        results = Ui.vbox(a);
        add(results, 8);
        Runnable run = () -> {
            String q = search.getText().toString().trim();
            if (q.length() < 2) { a.toast("Enter at least 2 characters."); return; }
            heatQuery = q;
            results.removeAllViews();
            results.addView(loading());
            go.setEnabled(false);
            Api.async(() -> GenTrace.heatSearch(api, q), (rows, err) -> {
                go.setEnabled(true);
                results.removeAllViews();
                if (err != null) { results.addView(error(err, null)); return; }
                heatRows = rows;
                showHeat();
            });
        };
        go.setOnClickListener(v -> run.run());
        search.setOnEditorActionListener((v, id, e) -> { if (id == EditorInfo.IME_ACTION_SEARCH) { run.run(); return true; } return false; });
        if (heatRows != null) showHeat();
    }

    private void showHeat() {
        results.removeAllViews();
        results.addView(Ui.label(a, "Linked events · " + heatRows.size()), Ui.matchWrap(a, 0));
        if (heatRows.isEmpty()) {
            results.addView(Ui.text(a, "No traceability event matched \"" + heatQuery + "\".", 13, Ui.TEAL_DARK, false), Ui.matchWrap(a, 4));
            return;
        }
        Map<String, Integer> heats = new LinkedHashMap<>();
        for (JSONObject r : heatRows) {
            String h = GenUtil.str(r.opt("heat_number"));
            if (!h.isEmpty()) heats.merge(h, 1, Integer::sum);
        }
        if (!heats.isEmpty()) results.addView(Ui.text(a, "Heats: " + String.join(", ", heats.keySet()), 12, Ui.TEXT, true), Ui.matchWrap(a, 4));
        List<String> headers = GenUtil.listOf("Reference", "Stage", "Part", "Heat Number", "Heat Code", "Date", "Status", "Quantity", "Source", "Process", "Result", "Secondary Reference");
        List<String[]> rows = new ArrayList<>();
        for (JSONObject r : heatRows) {
            rows.add(new String[]{GenUtil.str(r.opt("reference")), Ui.pretty(GenUtil.str(r.opt("event_type"))),
                GenTrace.join(r.opt("part_number"), r.opt("part_name")), GenUtil.str(r.opt("heat_number")), GenUtil.str(r.opt("heat_code")),
                GenUtil.str(r.opt("event_date")), GenUtil.str(r.opt("status")), GenTrace.text(r.opt("quantity")), GenUtil.str(r.opt("source_name")),
                GenUtil.str(r.opt("process_name")), GenUtil.str(r.opt("result")), GenUtil.str(r.opt("secondary_reference"))});
        }
        List<List<String>> grid = new ArrayList<>();
        for (String[] r : rows) grid.add(Arrays.asList(r));
        results.addView(Ui.text(a, "Tap an event to open its record.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 4));
        results.addView(new DataGrid(a, "Heat / batch genealogy", headers, grid, 520, index -> {
            if (index < 0 || index >= heatRows.size()) return;
            JSONObject ev = heatRows.get(index);
            String table = GenTrace.eventTable(GenUtil.str(ev.opt("event_type")));
            String id = GenUtil.str(ev.opt("event_id"));
            if (table == null || id.isEmpty()) { a.toast("This event has no record to open."); return; }
            Api.async(() -> {
                List<JSONObject> r = GenUtil.big(api, table + "?select=*&id=eq." + Api.enc(id) + "&limit=1");
                if (r.isEmpty()) throw new Api.ApiException(404, "Record not found or not visible for your role.");
                return r.get(0);
            }, (row, err) -> {
                if (err != null) { a.toast(Api.message(err)); return; }
                GenUtil.openRecord(a, table, row);
            });
        }), Ui.matchWrap(a, 2));
        Button csv = Ui.outline(a, "Export genealogy (CSV)", Ui.TEAL);
        csv.setOnClickListener(v -> GenUtil.exportCsv(a, "Heat genealogy", "QCMS_Heat_Genealogy_" + GenUtil.safeName(heatQuery), GenUtil.csv(headers, rows)));
        results.addView(csv, Ui.matchWrap(a, 10));
    }

    @Override public void reload() { data = null; heatRows = null; a.rebuild(); }

    // ================================================================== one Customer Order
    static final class OrderScreen extends Screen {
        private final String id;
        private GenTrace.OrderData d;

        OrderScreen(MainActivity a, String id) { super(a); this.id = id; }

        @Override public String title() { return d == null || GenUtil.str(d.order.opt("master_reference_no")).isEmpty() ? "Order traceability" : GenUtil.str(d.order.opt("master_reference_no")); }
        @Override public String subtitle() { return "Complete supply chain history"; }
        @Override public int tab() { return Catalog.MORE; }

        @Override
        public View build() {
            newPage();
            if (d != null) { render(); return scroll; }
            page.addView(loading());
            Api.async(() -> GenTrace.order(api, id), (res, err) -> {
                page.removeAllViews();
                if (err != null) { page.addView(error(err, this::reload)); return; }
                d = res;
                a.rebuildTitle(this);
                render();
            });
            return scroll;
        }

        private void render() {
            page.removeAllViews();
            LinearLayout head = Ui.card(a);
            LinearLayout top = Ui.hbox(a);
            top.addView(Ui.text(a, d.label, 14.5f, Ui.TEXT, true), Ui.weight(1));
            String st = GenTrace.dueStatus(d.order.opt("status"), d.order.opt("customer_delivery_date"));
            top.addView(Ui.chip(a, Ui.pretty(st), Ui.tone(st)));
            head.addView(top);
            for (Map.Entry<String, Object> e : d.ctx.entrySet()) {
                String v = GenTrace.text(e.getValue());
                if (e.getKey().equals("Delivery Date")) v = Ui.date(v);
                head.addView(Ui.pair(a, e.getKey(), v));
            }
            add(head, 0);
            Button tracker = Ui.outline(a, "Stage progress (order tracker)", Ui.TEAL);
            tracker.setOnClickListener(v -> a.push(new OrderTrackerScreen(a, id, d.label)));
            add(tracker, 8);

            add(Ui.label(a, "B · Complete supply chain history"), 14);
            add(Ui.text(a, "Heat and references remain visible from RM receipt through final customer dispatch.", 11.5f, Ui.MUTED, false), 0);
            List<String> th = GenUtil.listOf("Date", "Stage", "Reference", "Quantity", "Heat Number", "Status", "Remarks");
            grid("Complete Supply Chain History", th, d.timeline, 420);

            add(Ui.label(a, "C · Complete genealogy data"), 14);
            List<String> gh = new ArrayList<>();
            List<String[]> gr = new ArrayList<>();
            for (LinkedHashMap<String, Object> g : d.genealogy) {
                if (gh.isEmpty()) gh.addAll(g.keySet());
                String[] line = new String[g.size()];
                int i = 0;
                for (Object v : g.values()) line[i++] = GenTrace.text(v);
                gr.add(line);
            }
            if (gh.isEmpty()) { gh.addAll(d.ctx.keySet()); gh.addAll(GenUtil.listOf("Stage", "Stage Date", "Stage Reference", "Stage Qty", "Heat Number", "Heat Code", "RMTC Number", "Remarks")); }
            // the stage columns first on a phone (the order context repeats on every row)
            List<String> phoneHead = new ArrayList<>(GenUtil.listOf("Stage", "Stage Date", "Stage Reference", "Stage Qty", "Heat Number", "Heat Code", "RMTC Number", "Status", "Remarks"));
            for (String h : gh) if (!phoneHead.contains(h)) phoneHead.add(h);
            List<String[]> phoneRows = new ArrayList<>();
            for (String[] r : gr) {
                String[] line = new String[phoneHead.size()];
                for (int i = 0; i < phoneHead.size(); i++) { int j = gh.indexOf(phoneHead.get(i)); line[i] = j >= 0 && j < r.length ? r[j] : ""; }
                phoneRows.add(line);
            }
            grid("Complete Supply Chain Genealogy", phoneHead, phoneRows, 460);

            add(Ui.label(a, "D · Forging supplier raw material balance"), 14);
            grid("Forging Supplier RM Balance", GenUtil.listOf("Supplier", "RM Dispatched kg", "RM Consumed kg", "RM Balance kg", "Order Reference"), d.balances, 260);
        }

        private void grid(String title, List<String> headers, List<String[]> rows, int height) {
            if (rows.isEmpty()) { add(Ui.text(a, "No rows.", 12.5f, Ui.MUTED, false), 4); return; }
            List<List<String>> g = new ArrayList<>();
            for (String[] r : rows) g.add(Arrays.asList(r));
            add(new DataGrid(a, title, headers, g, height, null), 4);
            TextView csv = Ui.text(a, "Export " + title + " (CSV)", 12.5f, Ui.TEAL_DARK, true);
            csv.setPadding(0, dp(8), 0, dp(4));
            String ref = GenUtil.str(d.order.opt("master_reference_no"));
            csv.setOnClickListener(v -> GenUtil.exportCsv(a, title, GenUtil.safeName(title + "_" + ref), GenUtil.csv(headers, rows)));
            add(csv, 2);
        }

        @Override public void reload() { d = null; a.rebuild(); }
    }
}
