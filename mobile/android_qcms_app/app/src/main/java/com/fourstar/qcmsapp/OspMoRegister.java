package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;

import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * R39 · OSP Material Out / Challan register (web osp_transactions._render_challan_module section B, R38):
 * one row per Material Out with its challan number, vendor, FSI part, process, heats, out / returned / rejected /
 * balance pcs, challan saved / e-mailed and status (material_out_register). A row opens the ONE record
 * (Details · Print · Vendor returns). "New" opens the one-form Material Out + Returnable Delivery Challan entry.
 */
final class OspMoRegister extends Screen {
    static final String[] BALANCE_FILTERS = {"All", "Open at vendor", "Fully returned", "Challan not created"};
    private static int balanceFilter = 0;
    private static int days = 180;
    private List<JSONObject> rows;
    private LinearLayout list;
    private EditText search;

    OspMoRegister(MainActivity a) { super(a); }

    @Override public String title() { return "OSP Material Out"; }
    @Override public String subtitle() { return "Material Out = Returnable Delivery Challan · one row per Material Out"; }
    @Override public int tab() { return Catalog.QUALITY; }

    @Override
    public View build() {
        newPage();
        Button create = Ui.primary(a, "+ New Material Out · Returnable Delivery Challan");
        create.setOnClickListener(v -> {
            Api.async(() -> AdmPerm.current(api, OspRecordView.MODULE, "can_create"), (ok, err) -> {
                if (ok == null || !ok) { a.toast("Your role has no OSP Transactions Entry/Create right."); return; }
                a.push(new InspOspOutScreen(a, null));
            });
        });
        add(create, 0);
        search = Ui.input(a, "Search challan, Material Out, vendor, FSI part, heat or process", false);
        add(search, 10);
        LinearLayout chips = Ui.hbox(a);
        for (int i = 0; i < BALANCE_FILTERS.length; i++) {
            final int index = i;
            Button b = i == balanceFilter ? Ui.primary(a, BALANCE_FILTERS[i]) : Ui.outline(a, BALANCE_FILTERS[i], Ui.TEAL_DARK);
            b.setTextSize(10.5f);
            b.setOnClickListener(v -> { balanceFilter = index; fill(); a.rebuild(); });
            LinearLayout.LayoutParams lp = Ui.weight(1);
            lp.rightMargin = i < BALANCE_FILTERS.length - 1 ? dp(4) : 0;
            chips.addView(b, lp);
        }
        add(chips, 8);
        Button period = Ui.outline(a, "Period: last " + days + " days (tap to change)", Ui.TEAL);
        period.setOnClickListener(v -> InspUtil.pick(a, "Challan date period", Arrays.asList("30", "90", "180", "365", "3650"),
            Arrays.asList("Last 30 days", "Last 90 days", "Last 180 days", "Last 365 days", "All"), picked -> { days = Integer.parseInt(picked); a.rebuild(); }));
        add(period, 6);
        list = Ui.vbox(a);
        add(list, 6);
        search.addTextChangedListener(new android.text.TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
            @Override public void afterTextChanged(android.text.Editable e) { fill(); }
        });
        if (rows != null) { fill(); return scroll; }
        list.addView(loading());
        Api.async(() -> load(api), (r, err) -> {
            list.removeAllViews();
            if (err != null) { list.addView(error(err, this::reload)); return; }
            rows = r;
            fill();
        });
        return scroll;
    }

    @Override public void reload() { rows = null; a.rebuild(); }

    /** OSPService.material_out_documents + material_out_register over the live register / challans / returns. */
    static List<JSONObject> load(Api api) throws Exception {
        List<JSONObject> reg = InspUtil.list(api.rows("v_qsms_osp_register?select=id,osp_job_number,part_id,part_number,vendor_name,process_name,heat_number,dispatch_date,dispatch_challan,"
            + "quantity_dispatched,quantity_received,status&order=created_at.desc&limit=5000"));
        Map<String, JSONObject> jobs = new HashMap<>();
        for (JSONObject j : OspChallan.select(api, "osp_jobs?select=id,material_out_id,material_out_line_no&limit=10000")) jobs.put(OspChallan.s(j, "id"), j);
        Map<String, String> moNumbers = new HashMap<>();
        for (JSONObject m : OspChallan.select(api, "osp_material_outs?select=id,material_out_number&limit=5000")) moNumbers.put(OspChallan.s(m, "id"), OspChallan.s(m, "material_out_number"));
        Map<String, String> fsi = new HashMap<>();
        for (JSONObject p : OspChallan.select(api, "parts?select=id,fsi_part_number&limit=10000")) fsi.put(OspChallan.s(p, "id"), OspChallan.s(p, "fsi_part_number"));
        Map<String, List<JSONObject>> groups = new LinkedHashMap<>();
        for (JSONObject r : reg) {
            JSONObject j = jobs.get(OspChallan.s(r, "id"));
            String mo = OspChallan.s(j, "material_out_id");
            r.put("material_out_id", mo);
            r.put("material_out_line_no", OspChallan.f(j, "material_out_line_no"));
            groups.computeIfAbsent(mo.isEmpty() ? OspChallan.s(r, "id") : mo, k -> new ArrayList<>()).add(r);
        }
        List<JSONObject> challans = OspChallan.select(api, "osp_challans?select=id,material_out_id,osp_job_id,challan_number,challan_date,emailed_at&limit=5000");
        Map<String, JSONObject> byKey = new HashMap<>();
        for (JSONObject c : challans) byKey.put(SupPdfKit.first(OspChallan.s(c, "material_out_id"), OspChallan.s(c, "osp_job_id")), c);
        Map<String, Double> standalone = new HashMap<>(), rejected = new HashMap<>();
        for (JSONObject e : OspChallan.select(api, "osp_challan_returns?select=challan_id,osp_receipt_id,quantity_returned,quantity_rejected&limit=5000")) {
            String cid = OspChallan.s(e, "challan_id");
            rejected.merge(cid, OspChallan.f(e, "quantity_rejected"), Double::sum);
            if (OspChallan.s(e, "osp_receipt_id").isEmpty()) standalone.merge(cid, OspChallan.f(e, "quantity_returned"), Double::sum);
        }
        List<JSONObject> out = new ArrayList<>();
        for (Map.Entry<String, List<JSONObject>> g : groups.entrySet()) {
            List<JSONObject> lines = g.getValue();
            lines.sort((x, y) -> Double.compare(OspChallan.f(x, "material_out_line_no"), OspChallan.f(y, "material_out_line_no")));
            JSONObject first = lines.get(0);
            boolean group = !OspChallan.s(first, "material_out_id").isEmpty();
            double dispatched = 0, received = 0;
            LinkedHashMap<String, Boolean> heats = new LinkedHashMap<>(), states = new LinkedHashMap<>();
            for (JSONObject l : lines) {
                dispatched += OspChallan.f(l, "quantity_dispatched");
                received += OspChallan.f(l, "quantity_received");
                heats.put(SupPdfKit.first(OspChallan.s(l, "heat_number"), "-"), true);
                states.put(OspChallan.s(l, "status"), true);
            }
            JSONObject ch = byKey.get(g.getKey());
            String cid = OspChallan.s(ch, "id");
            double returned = received + standalone.getOrDefault(cid, 0.0), rej = rejected.getOrDefault(cid, 0.0);
            JSONObject row = new JSONObject();
            row.put("_key", g.getKey());
            row.put("_group", group);
            row.put("_job_id", OspChallan.s(first, "id"));
            row.put("material_out", group ? SupPdfKit.first(moNumbers.get(g.getKey()), OspChallan.s(first, "osp_job_number")) : OspChallan.s(first, "osp_job_number"));
            row.put("challan_no", SupPdfKit.first(OspChallan.s(ch, "challan_number"), OspChallan.s(first, "dispatch_challan")));
            row.put("challan_date", OspChallan.s(ch, "challan_date").isEmpty() ? OspChallan.s(first, "dispatch_date") : OspChallan.s(ch, "challan_date"));
            row.put("vendor", OspChallan.s(first, "vendor_name"));
            row.put("fsi_part", fsi.getOrDefault(OspChallan.s(first, "part_id"), ""));
            row.put("process", OspChallan.s(first, "process_name"));
            row.put("heats", String.join(", ", heats.keySet()));
            row.put("out", dispatched);
            row.put("returned", returned);
            row.put("rejected", rej);
            row.put("balance", Math.max(dispatched - returned - rej, 0.0));
            row.put("challan", ch == null ? "Not created" : "Saved");
            String mailed = OspChallan.s(ch, "emailed_at");
            row.put("emailed", mailed.length() >= 10 ? mailed.substring(0, 10) : "-");
            row.put("status", states.size() == 1 ? states.keySet().iterator().next() : "PARTIAL / MIXED");
            out.add(row);
        }
        out.sort((x, y) -> OspChallan.s(y, "challan_date").compareTo(OspChallan.s(x, "challan_date")));
        return out;
    }

    /** material_out_register filter (period, balance, search). */
    static boolean keep(JSONObject r, int balance, String query, String fromDay) {
        String day = OspChallan.s(r, "challan_date");
        if (day.length() >= 10 && fromDay != null && day.substring(0, 10).compareTo(fromDay) < 0) return false;
        double bal = OspChallan.f(r, "balance");
        if (balance == 1 && bal <= 0) return false;
        if (balance == 2 && bal > 0) return false;
        if (balance == 3 && !"Not created".equals(OspChallan.s(r, "challan"))) return false;
        if (query == null || query.trim().isEmpty()) return true;
        String hay = String.join(" ", OspChallan.s(r, "challan_no"), OspChallan.s(r, "material_out"), OspChallan.s(r, "vendor"), OspChallan.s(r, "fsi_part"),
            OspChallan.s(r, "heats"), OspChallan.s(r, "process"), OspChallan.s(r, "status")).toLowerCase(Locale.ROOT);
        return hay.contains(query.trim().toLowerCase(Locale.ROOT));
    }

    private void fill() {
        if (list == null || rows == null) return;
        list.removeAllViews();
        String from = days >= 3650 ? null : LocalDate.now().minusDays(days).toString();
        List<JSONObject> shown = new ArrayList<>();
        for (JSONObject r : rows) if (keep(r, balanceFilter, search == null ? "" : search.getText().toString(), from)) shown.add(r);
        if (shown.isEmpty()) { list.addView(Ui.empty(a, "No Material Out matches these filters.")); return; }
        List<String> head = Arrays.asList("Challan No", "Material Out", "Challan Date", "OSP Vendor", "FSI Part", "Process", "Heat Numbers", "Out Qty pcs",
            "Returned pcs", "Rejected pcs", "Balance pcs", "Challan", "E-mailed", "Status");
        List<List<String>> data = new ArrayList<>();
        for (JSONObject r : shown) data.add(Arrays.asList(SupPdfKit.first(OspChallan.s(r, "challan_no"), "-"), OspChallan.s(r, "material_out"), Ui.date(OspChallan.s(r, "challan_date")),
            OspChallan.s(r, "vendor"), SupPdfKit.first(OspChallan.s(r, "fsi_part"), "-"), OspChallan.s(r, "process"), OspChallan.s(r, "heats"),
            Ui.num(OspChallan.f(r, "out"), 0), Ui.num(OspChallan.f(r, "returned"), 0), Ui.num(OspChallan.f(r, "rejected"), 0), Ui.num(OspChallan.f(r, "balance"), 0),
            OspChallan.s(r, "challan"), OspChallan.s(r, "emailed"), Ui.pretty(OspChallan.s(r, "status"))));
        list.addView(new DataGrid(a, "Material Out / Challan register", head, data, 460, index -> open(shown.get(index))));
        list.addView(Ui.text(a, "Tap a row to open the record: Details · Print · Vendor returns. Customer details never print on the vendor challan.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 4));
    }

    private void open(JSONObject r) {
        if (r.optBoolean("_group", false)) {
            Module m = Catalog.get("osp_material_out");
            a.push(new RecordScreen(a, m == null ? Catalog.adhoc("osp_material_outs") : m, OspChallan.s(r, "_key")));
        } else {
            a.push(new OspRecordScreen(a, null, OspChallan.s(r, "_job_id")));   // older single-heat job: same record view
        }
    }
}
