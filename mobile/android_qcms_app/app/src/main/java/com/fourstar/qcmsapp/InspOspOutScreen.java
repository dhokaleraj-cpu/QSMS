package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * OSP Material Out (osp_transactions._render_material_out_entry): one document, several RMTC / heat source lines,
 * saved atomically with rpc qcms_create_osp_material_out (p_request_id idempotency key kept until success).
 * With an id: edit of a multi-heat document via qcms_update_osp_material_out_group.
 */
final class InspOspOutScreen extends Screen {
    private final String id;
    private boolean loaded = false;
    private String requestId = InspUtil.uuid();
    // create
    private List<JSONObject> candidates = new ArrayList<>();
    private String partId = "";
    private final Set<String> selected = new HashSet<>();
    private List<JSONObject> specs = new ArrayList<>();
    // R38/R39: the Returnable Delivery Challan is captured with the Material Out (entered once, saved together)
    private List<JSONObject> branches = new ArrayList<>();
    private JSONObject prices;
    private String pricesKey = "";
    private String suggestedFor = null;
    // edit
    private JSONObject doc;
    private List<JSONObject> lines = new ArrayList<>();
    private FormView form;
    private RowsEditor grid;

    InspOspOutScreen(MainActivity a, String id) { super(a); this.id = id; }

    @Override public String title() { return id == null ? "OSP Material Out" : "Edit · " + InspUtil.j(doc, "material_out_number"); }
    @Override public String subtitle() { return "Dispatch released material by Part and Heat Number to an approved OSP vendor"; }
    @Override public int tab() { return Catalog.QUALITY; }

    @Override
    public View build() {
        newPage();
        if (loaded) { render(); return scroll; }
        page.addView(loading());
        Api.async(() -> {
            Lookups.rows(api, Lookups.processes());
            if (id != null) loadDocument(); else loadCandidates();
            return true;
        }, (ok, err) -> {
            loaded = true;
            if (err != null) { page.removeAllViews(); page.addView(error(err, () -> { loaded = false; a.rebuild(); })); return; }
            a.rebuildTitle(this);
            render();
        });
        return scroll;
    }

    // ------------------------------------------------------------------ data
    /** OSPService.dispatch_candidates (released inward balances + eligible opening stock) with RMTC numbers. */
    private void loadCandidates() throws Exception {
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject r : InspUtil.list(api.rows("v_qsms_osp_dispatch_candidates?select=*&order=inward_date.desc&limit=5000"))) {
            if (InspUtil.dbl(r, "osp_available_quantity_pcs") <= 0) continue;
            JSONObject item = InspUtil.copy(r);
            item.put("source_type", "INWARD");
            item.put("candidate_key", "INWARD:" + InspUtil.j(r, "inward_lot_id"));
            out.add(item);
        }
        Set<String> eligible = new HashSet<>(Arrays.asList("MACHINING", "OSP_READY", "FINAL_INSPECTION", "FINISHED_GOODS"));
        for (JSONObject s : InspUtil.list(api.rows("supply_opening_stock?select=*&status=eq.ACTIVE&order=created_at.desc&limit=5000"))) {
            if (!eligible.contains(InspUtil.j(s, "stage").toUpperCase())) continue;
            double avail = InspUtil.dbl(s, "available_quantity_pcs");
            if (avail <= 0) continue;
            JSONObject item = new JSONObject();
            item.put("source_type", "OPENING_STOCK");
            item.put("candidate_key", "OPEN:" + InspUtil.j(s, "id"));
            item.put("opening_stock_id", InspUtil.j(s, "id"));
            item.put("inward_number", InspUtil.j(s, "lot_reference").isEmpty() ? "Opening Stock" : InspUtil.j(s, "lot_reference"));
            item.put("part_id", InspUtil.j(s, "part_id"));
            item.put("heat_number", InspUtil.j(s, "heat_number").isEmpty() ? "OPENING" : InspUtil.j(s, "heat_number"));
            item.put("osp_available_quantity_pcs", avail);
            out.add(item);
        }
        Set<String> partIds = new HashSet<>(), inwardIds = new HashSet<>();
        for (JSONObject r : out) { partIds.add(InspUtil.j(r, "part_id")); if (!InspUtil.j(r, "inward_lot_id").isEmpty()) inwardIds.add(InspUtil.j(r, "inward_lot_id")); }
        Map<String, JSONObject> parts = InspUtil.byId(api, "parts", "id,part_number,fsi_part_number,part_name", partIds);
        Map<String, JSONObject> inwards = InspUtil.byId(api, "inward_lots", "id,rmtc_approval_id", inwardIds);
        Set<String> certIds = new HashSet<>();
        for (JSONObject i : inwards.values()) if (!InspUtil.j(i, "rmtc_approval_id").isEmpty()) certIds.add(InspUtil.j(i, "rmtc_approval_id"));
        Map<String, JSONObject> certs = InspUtil.byId(api, "rmtc_approvals", "id,rmtc_number,certificate_reference", certIds);
        for (JSONObject r : out) {
            JSONObject p = parts.get(InspUtil.j(r, "part_id"));
            r.put("part_number", InspUtil.j(p, "part_number"));
            r.put("fsi_part_number", InspUtil.j(p, "fsi_part_number"));
            r.put("part_name", InspUtil.j(p, "part_name"));
            JSONObject in = inwards.get(InspUtil.j(r, "inward_lot_id"));
            JSONObject c = in == null ? null : certs.get(InspUtil.j(in, "rmtc_approval_id"));
            r.put("rmtc_number", InspUtil.j(c, "rmtc_number"));
            r.put("supplier_rmtc_number", InspUtil.j(c, "certificate_reference"));
        }
        candidates = out;
        branches = OspChallan.branches(api);
    }

    private void loadDocument() throws Exception {
        doc = InspUtil.get(api, "osp_material_outs", id);
        if (doc == null) throw new Api.ApiException(404, "Material Out document not found.");
        List<JSONObject> jobs = InspUtil.list(api.rows("osp_jobs?select=id,material_out_line_no,osp_job_number,quantity_dispatched,quantity_received,dispatch_date,expected_return_date,dispatch_challan,dispatch_remarks&material_out_id=eq."
            + Api.enc(id) + "&order=material_out_line_no.asc&limit=200"));
        Set<String> ids = new HashSet<>();
        for (JSONObject j : jobs) ids.add(InspUtil.j(j, "id"));
        Map<String, JSONObject> reg = new HashMap<>();
        List<String> l = new ArrayList<>(ids);
        for (int s = 0; s < l.size(); s += 80) for (JSONObject r : InspUtil.list(api.rows("v_qsms_osp_register?select=id,heat_number,osp_batch_code,part_number&id=in.(" + String.join(",", l.subList(s, Math.min(l.size(), s + 80))) + ")"))) reg.put(InspUtil.j(r, "id"), r);
        for (JSONObject j : jobs) {
            JSONObject r = reg.get(InspUtil.j(j, "id"));
            j.put("heat_number", InspUtil.j(r, "heat_number"));
            j.put("osp_batch_code", InspUtil.j(r, "osp_batch_code"));
        }
        lines = jobs;
    }

    // ------------------------------------------------------------------ UI
    private String sourceLabel(JSONObject r) {
        String batch = "OPENING_STOCK".equals(InspUtil.j(r, "source_type")) ? InspUtil.j(r, "inward_number") : "SRC-" + InspUtil.j(r, "inward_number");
        return "Source Batch / Lot " + batch + " · RMTC " + (InspUtil.j(r, "rmtc_number").isEmpty() ? "Opening / legacy" : InspUtil.j(r, "rmtc_number"))
            + " · Supplier RMTC " + (InspUtil.j(r, "supplier_rmtc_number").isEmpty() ? "-" : InspUtil.j(r, "supplier_rmtc_number"))
            + " · Heat " + InspUtil.j(r, "heat_number") + " · Inward " + InspUtil.j(r, "inward_number") + " · Available " + Ui.num(InspUtil.dbl(r, "osp_available_quantity_pcs"), 0) + " pcs";
    }

    private View selector(String label, String value, Runnable onClick) {
        LinearLayout box = Ui.vbox(a);
        box.addView(Ui.label(a, label));
        TextView t = Ui.text(a, value == null || value.isEmpty() ? "Select…" : value, 14, value == null || value.isEmpty() ? Ui.MUTED : Ui.TEXT, false);
        t.setPadding(dp(12), dp(12), dp(12), dp(12));
        t.setBackground(Ui.round(android.graphics.Color.WHITE, Ui.LINE_STRONG, 1, 10, a));
        t.setOnClickListener(v -> onClick.run());
        box.addView(t, Ui.matchWrap(a, 0));
        return box;
    }

    private void render() {
        page.removeAllViews();
        if (id != null) { renderEdit(); return; }
        if (candidates.isEmpty()) { add(Ui.empty(a, "No released Material Inward or eligible Opening Stock balance is available for OSP dispatch."), 4); return; }
        LinearLayout card = Ui.card(a);
        JSONObject anyPart = null;
        for (JSONObject r : candidates) if (InspUtil.j(r, "part_id").equals(partId)) anyPart = r;
        card.addView(selector("Part for Material Out", anyPart == null ? "" : InspUtil.j(anyPart, "part_number") + " · FSI " + (InspUtil.j(anyPart, "fsi_part_number").isEmpty() ? "-" : InspUtil.j(anyPart, "fsi_part_number")) + " · " + InspUtil.j(anyPart, "part_name"), this::pickPart));
        if (!partId.isEmpty()) card.addView(selector("Select RMTCs / Heat Numbers / Source Lots", selected.isEmpty() ? "" : selected.size() + " source lot(s) selected", this::pickSources), Ui.matchWrap(a, 8));
        add(card, 4);
        if (partId.isEmpty() || selected.isEmpty()) {
            add(Ui.text(a, "Select one or more source lots. One Material Out can include several RMTCs and heat numbers for this part.", 12.5f, Ui.MUTED, false), 8);
            return;
        }
        if (specs.isEmpty()) { add(Ui.text(a, "Maintain an ACTIVE OSP Process Specification for this Part (Part Master) and an approved OSP Vendor before dispatch.", 13, Ui.AMBER_FG, false), 8); return; }
        List<Field> f = new ArrayList<>();
        f.add(Field.lookup("process_specification_id", "OSP Process / Specification", new Field.Lookup("part_process_specifications", "id,process_id,process_specification,sample_quantity,sequence_no",
            "&part_id=eq." + partId + "&inward_type=eq.OSP_PROCESS&status=eq.ACTIVE", "sequence_no.asc", r -> {
                JSONObject p = Lookups.rowOf(Lookups.processes(), InspUtil.j(r, "process_id"));
                return Lookups.join(p == null ? "" : InspUtil.j(p, "process_code") + " · " + InspUtil.j(p, "process_name"), InspUtil.j(r, "process_specification").isEmpty() ? "-" : InspUtil.j(r, "process_specification"));
            })).req());
        f.add(Field.lookup("vendor_id", "OSP Vendor", Lookups.ospVendors().where("&or=(approval_status.eq.APPROVED,approval_status.is.null)")).req());
        List<String> bIds = new ArrayList<>(), bNames = new ArrayList<>();
        String defaultBranch = "";
        for (JSONObject b : branches) {
            bIds.add(InspUtil.j(b, "id"));
            bNames.add(InspUtil.j(b, "branch_name") + " · " + SupPdfKit.first(InspUtil.j(b, "plant_code"), InspUtil.j(b, "branch_code")));
        }
        JSONObject def = OspChallan.defaultBranch(branches);
        if (def != null) defaultBranch = InspUtil.j(def, "id");
        if (!bIds.isEmpty()) f.add(Field.select("branch_id", "Plant / Company Branch (challan series)", bIds.toArray(new String[0])).labels(bNames.toArray(new String[0])));
        f.add(Field.date("dispatch_date", "Material Out / Challan Date").req());
        f.add(Field.date("expected_return_date", "Expected Return / Delivery Date").req());
        f.add(Field.text("dispatch_challan", "Material Out Challan Number").req().hint("Suggested from the branch challan series (JWC + plant + number). You can overwrite it."));
        f.add(Field.lookup("ship_to_party_id", "Ship To (empty = Same as OSP Vendor)", new Field.Lookup("parties", "id,party_code,party_name,party_types,city,status",
            "&status=eq.ACTIVE", "party_name.asc", Lookups.PARTY)));
        f.add(Field.text("user_name", "User"));
        f.add(Field.select("ship_via", "Ship Via", OspChallan.SHIP_VIA_OPTIONS).labels(OspChallan.SHIP_VIA_OPTIONS));
        f.add(Field.select("incoterm", "Incoterm", OspChallan.INCOTERM_OPTIONS).labels(OspChallan.INCOTERM_OPTIONS));
        f.add(Field.select("payment_term", "Payment Term", OspChallan.PAYMENT_TERM_OPTIONS).labels(OspChallan.PAYMENT_TERM_OPTIONS));
        f.add(Field.text("vehicle_number", "Vehicle No"));
        f.add(Field.text("transporter_name", "Transporter"));
        f.add(Field.text("eway_bill_number", "E-way Bill No"));
        f.add(Field.text("reference_details", "Reference Details"));
        f.add(Field.text("old_po_details", "Old PO Details"));
        f.add(Field.text("process_text", "Process To Be Done"));
        f.add(Field.number("shipping_amount", "Shipping (INR)").range(0, Double.MAX_VALUE));
        f.add(Field.number("other_amount", "Other (INR)").range(0, Double.MAX_VALUE));
        f.add(Field.area("remarks", "Dispatch Remarks (printed as the challan remarks)"));
        String spec = form == null ? InspUtil.j(specs.get(0), "id") : form.str("process_specification_id");
        Map<String, String> keep = new LinkedHashMap<>();
        if (form != null) for (String k : CHALLAN_KEEP) keep.put(k, form.str(k));
        form = new FormView(a, f);
        form.set("process_specification_id", spec);
        form.set("dispatch_date", Ui.today());
        form.set("expected_return_date", LocalDate.now().plusDays(7).toString());
        if (!defaultBranch.isEmpty()) form.set("branch_id", defaultBranch);
        form.set("user_name", api.fullName);
        form.set("ship_via", OspChallan.SHIP_VIA_OPTIONS[0]);
        form.set("incoterm", OspChallan.INCOTERM_OPTIONS[0]);
        form.set("payment_term", OspChallan.PAYMENT_TERM_OPTIONS[0]);
        form.set("process_text", processName(spec).toUpperCase(java.util.Locale.ROOT));
        for (Map.Entry<String, String> e : keep.entrySet()) if (!e.getValue().isEmpty()) form.set(e.getKey(), e.getValue());
        if (form.str("dispatch_challan").isEmpty()) suggestNumber(form.str("branch_id"));
        loadPrices(spec);
        LinearLayout fc = Ui.card(a);
        fc.addView(form);
        add(fc, 8);
        Map<String, JSONObject> previous = new HashMap<>();
        if (grid != null) for (JSONObject r : grid.rows()) previous.put(InspUtil.j(r, "candidate_key"), r);
        grid = new RowsEditor(a, "Heat lines", Arrays.asList(
            Field.info("_label", "Source"),
            Field.number("quantity_dispatched", "Out Qty pcs").range(1, Double.MAX_VALUE).req(),
            Field.number("sample_quantity", "Sample Qty pcs").range(1, 20).req(),
            Field.number("unit_price", "Unit Price (challan)").range(0, Double.MAX_VALUE),
            Field.number("gst_percent", "GST %").range(0, 100),
            Field.text("uom", "UOM"),
            Field.text("batch_code", "Batch Code (blank = FSI batch)")),
            Arrays.asList(new String[]{"rmtc_number", "RMTC"}, new String[]{"supplier_rmtc_number", "Supplier RMTC"}, new String[]{"heat_number", "Heat Number"}, new String[]{"inward_number", "Inward / Lot"},
                new String[]{"osp_available_quantity_pcs", "Available pcs"}, new String[]{"quantity_dispatched", "Out Qty pcs"}, new String[]{"sample_quantity", "Sample Qty pcs"},
                new String[]{"unit_price", "Unit Price"}, new String[]{"gst_percent", "GST %"}, new String[]{"uom", "UOM"}, new String[]{"batch_code", "Batch Code"}));
        grid.fixedRows();
        double specSample = Math.max(1, InspUtil.dbl(byId(specs, spec), "sample_quantity"));
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject c : candidates) {
            if (!selected.contains(InspUtil.j(c, "candidate_key"))) continue;
            if (previous.containsKey(InspUtil.j(c, "candidate_key"))) { rows.add(previous.get(InspUtil.j(c, "candidate_key"))); continue; }
            JSONObject r = InspUtil.copy(c);
            try {
                double avail = InspUtil.dbl(c, "osp_available_quantity_pcs");
                r.put("_label", sourceLabel(c));
                if (r.optString("rmtc_number", "").isEmpty()) r.put("rmtc_number", "Opening / legacy");
                r.put("quantity_dispatched", avail);
                r.put("sample_quantity", Math.min(specSample, avail));
                r.put("unit_price", OspChallan.f(prices, "unit_price"));
                r.put("gst_percent", prices != null && prices.has("gst_percent") ? OspChallan.f(prices, "gst_percent") : OspChallan.DEFAULT_GST);
                r.put("uom", SupPdfKit.first(OspChallan.s(prices, "uom"), OspChallan.DEFAULT_UOM));
                r.put("batch_code", "");
            } catch (Exception ignored) { }
            rows.add(r);
        }
        grid.setRows(rows);
        add(Ui.label(a, "Heat lines · tap a line to change quantities"), 12);
        add(grid, 4);
        add(Ui.text(a, "One Material Out document; a separate FSI batch is generated for each heat line. Samples and inward quantities remain independent for each batch. "
            + "Unit Price / GST % / Batch Code print on the Returnable Delivery Challan (blank Batch Code prints the FSI batch). No customer details print on the challan.", 11.5f, Ui.MUTED, false), 4);
        form.onChange((k, v) -> {
            if ("branch_id".equals(k)) suggestNumber(form.str("branch_id"));
            if ("process_specification_id".equals(k)) {
                form.set("process_text", processName(form.str("process_specification_id")).toUpperCase(java.util.Locale.ROOT));
                loadPrices(form.str("process_specification_id"));
            }
            if ("process_specification_id".equals(k) && grid != null) {
                double ss = Math.max(1, InspUtil.dbl(byId(specs, form.str("process_specification_id")), "sample_quantity"));
                for (JSONObject r : grid.rows()) try { r.put("sample_quantity", Math.min(ss, InspUtil.dbl(r, "osp_available_quantity_pcs"))); } catch (Exception ignored) { }
                grid.refresh();
            }
        });
        Button save = Ui.primary(a, "Create OSP Material Out + Returnable Delivery Challan");
        save.setOnClickListener(v -> create(save));
        add(save, 16);
        add(Ui.text(a, "Saves the Material Out and its Returnable Delivery Challan in one step; the record then opens with Details · Print · Vendor returns.", 11.5f, Ui.MUTED, false), 4);
    }

    private static final String[] CHALLAN_KEEP = {"vendor_id", "dispatch_date", "expected_return_date", "dispatch_challan", "remarks", "branch_id", "ship_to_party_id", "user_name",
        "ship_via", "incoterm", "payment_term", "vehicle_number", "transporter_name", "eway_bill_number", "reference_details", "old_po_details", "process_text",
        "shipping_amount", "other_amount"};

    private String processName(String specId) {
        JSONObject spec = byId(specs, specId);
        JSONObject p = spec == null ? null : Lookups.rowOf(Lookups.processes(), InspUtil.j(spec, "process_id"));
        return InspUtil.j(p, "process_name");
    }

    /** challans.next_number(branch): JWC + plant + number (rpc qcms_next_osp_challan_number, Python fallback). */
    private void suggestNumber(String branchId) {
        String key = branchId == null ? "" : branchId;
        if (key.equals(suggestedFor)) return;
        suggestedFor = key;
        FormView target = form;
        Api.async(() -> OspChallan.nextNumber(api, key), (no, err) -> {
            if (err != null || no == null || target != form) return;
            form.set("dispatch_challan", no);
        });
    }

    /** challans.default_prices(part, None, process): last challan price for the part / process, else the price master. */
    private void loadPrices(String specId) {
        JSONObject spec = byId(specs, specId);
        String processId = InspUtil.j(spec, "process_id");
        String key = partId + "|" + processId;
        if (key.equals(pricesKey)) return;
        pricesKey = key;
        Api.async(() -> OspChallan.defaultPrices(api, partId, null, processId), (p, err) -> {
            if (err != null || p == null || !key.equals(pricesKey)) return;
            prices = p;
            if (grid == null) return;
            for (JSONObject r : grid.rows()) try {
                if (OspChallan.f(r, "unit_price") == 0) r.put("unit_price", OspChallan.f(p, "unit_price"));
                r.put("gst_percent", OspChallan.f(p, "gst_percent"));
                if (OspChallan.s(r, "uom").isEmpty() || OspChallan.DEFAULT_UOM.equals(OspChallan.s(r, "uom"))) r.put("uom", SupPdfKit.first(OspChallan.s(p, "uom"), OspChallan.DEFAULT_UOM));
            } catch (Exception ignored) { }
            grid.refresh();
        });
    }

    /** Challan header of the one-form entry (header of save_material_out_challan). */
    private JSONObject challanHeader() throws Exception {
        JSONObject h = new JSONObject();
        h.put("challan_number", form.str("dispatch_challan"));
        h.put("challan_date", form.str("dispatch_date"));
        h.put("delivery_date", form.str("expected_return_date"));
        h.put("vendor_id", form.str("vendor_id"));
        for (String k : new String[]{"branch_id", "ship_to_party_id", "user_name", "ship_via", "incoterm", "payment_term", "vehicle_number", "transporter_name",
            "eway_bill_number", "reference_details", "old_po_details", "process_text", "remarks"}) h.put(k, form.str(k));
        h.put("shipping_amount", OspChallan.f(form.str("shipping_amount")));
        h.put("other_amount", OspChallan.f(form.str("other_amount")));
        return h;
    }

    private static JSONObject byId(List<JSONObject> l, String id) {
        for (JSONObject r : l) if (InspUtil.j(r, "id").equals(id)) return r;
        return null;
    }

    private void pickPart() {
        Map<String, String> parts = new LinkedHashMap<>();
        for (JSONObject r : candidates) parts.put(InspUtil.j(r, "part_id"), InspUtil.j(r, "part_number") + " · FSI " + (InspUtil.j(r, "fsi_part_number").isEmpty() ? "-" : InspUtil.j(r, "fsi_part_number")) + " · " + InspUtil.j(r, "part_name"));
        InspUtil.pick(a, "Part for Material Out", new ArrayList<>(parts.keySet()), new ArrayList<>(parts.values()), picked -> {
            partId = picked;
            selected.clear();
            form = null;
            grid = null;
            Api.async(() -> InspUtil.list(api.rows("part_process_specifications?select=id,process_id,process_specification,sample_quantity&part_id=eq." + Api.enc(picked)
                + "&inward_type=eq.OSP_PROCESS&status=eq.ACTIVE&order=sequence_no.asc&limit=2000")), (rows, err) -> {
                if (err != null) { a.toast(Api.message(err)); return; }
                specs = rows;
                render();
                pickSources();
            });
        });
    }

    private void pickSources() {
        List<JSONObject> mine = new ArrayList<>();
        for (JSONObject r : candidates) if (InspUtil.j(r, "part_id").equals(partId)) mine.add(r);
        String[] names = new String[mine.size()];
        boolean[] checked = new boolean[mine.size()];
        for (int i = 0; i < mine.size(); i++) { names[i] = sourceLabel(mine.get(i)); checked[i] = selected.contains(InspUtil.j(mine.get(i), "candidate_key")); }
        new AlertDialog.Builder(a).setTitle("Select RMTCs / Heat Numbers / Source Lots")
            .setMultiChoiceItems(names, checked, (d, i, on) -> checked[i] = on)
            .setPositiveButton("OK", (d, w) -> {
                selected.clear();
                for (int i = 0; i < checked.length; i++) if (checked[i]) selected.add(InspUtil.j(mine.get(i), "candidate_key"));
                if (selected.size() > 100) { a.toast("Select between 1 and 100 RMTC / heat lines."); }
                render();
            })
            .setNegativeButton("Back", null).show();
    }

    /** OSPService.validate_dispatch_lines + displayed balance check, then qcms_create_osp_material_out. */
    private void create(Button button) {
        String problem = form.validate();
        if (problem != null) { a.toast(problem); return; }
        JSONObject spec = byId(specs, form.str("process_specification_id"));
        if (spec == null) { a.toast("Select the OSP Process / Specification."); return; }
        JSONArray clean = new JSONArray();
        try {
            List<JSONObject> rows = grid.rows();
            if (rows.isEmpty() || rows.size() > 100) throw new Exception("Select between 1 and 100 RMTC / heat lines.");
            Set<String> seen = new HashSet<>();
            for (JSONObject r : rows) {
                String inward = InspUtil.j(r, "inward_lot_id"), opening = InspUtil.j(r, "opening_stock_id");
                if (inward.isEmpty() == opening.isEmpty()) throw new Exception("Each heat line requires exactly one released inward or opening-stock source.");
                String key = (inward.isEmpty() ? "OPEN:" + opening : "INWARD:" + inward);
                if (!seen.add(key)) throw new Exception("The same source cannot be selected twice.");
                Double qty = Rules.number(r.opt("quantity_dispatched")), sample = Rules.number(r.opt("sample_quantity"));
                if (qty == null || sample == null) throw new Exception("Enter valid dispatch and sample quantities for every heat line.");
                if (qty > InspUtil.dbl(r, "osp_available_quantity_pcs")) throw new Exception("Heat " + InspUtil.j(r, "heat_number") + ": quantity exceeds displayed balance. Refresh the source list.");
                if (qty.isInfinite() || qty.isNaN() || qty <= 0) throw new Exception("Every heat line needs a finite positive dispatch quantity.");
                if (sample.isInfinite() || sample.isNaN() || sample <= 0 || sample > Math.min(qty, 20)) throw new Exception("Sample quantity must be positive, at most 20, and no more than its heat quantity.");
                clean.put(new JSONObject().put("inward_lot_id", InspUtil.nz(inward)).put("opening_stock_id", InspUtil.nz(opening))
                    .put("quantity_dispatched", qty).put("sample_quantity", sample));
            }
        } catch (Exception e) { a.toast(e.getMessage()); return; }
        // R38: validate the challan part BEFORE the stock-allocating Material Out RPC, so a challan problem never leaves a half entry.
        final JSONObject challanHeader;
        final List<JSONObject> challanLines = new ArrayList<>();
        try {
            challanHeader = challanHeader();
            int index = 0;
            List<JSONObject> probe = new ArrayList<>();
            for (JSONObject r : grid.rows()) {
                index++;
                JSONObject l = new JSONObject();
                l.put("line_no", index);
                l.put("item_code", JSONObject.NULL);
                l.put("unit_price", OspChallan.f(r.opt("unit_price")));
                l.put("gst_percent", OspChallan.s(r, "gst_percent").isEmpty() ? OspChallan.DEFAULT_GST : OspChallan.f(r.opt("gst_percent")));
                l.put("uom", SupPdfKit.first(OspChallan.s(r, "uom"), OspChallan.DEFAULT_UOM));
                l.put("batch_code", OspChallan.s(r, "batch_code"));
                challanLines.add(l);
                probe.add(new JSONObject(l.toString()).put("osp_job_id", "pending"));
            }
            OspChallan.cleanHeader(challanHeader);
            OspChallan.cleanLines(probe);
        } catch (Exception e) { a.toast(Api.message(e)); return; }
        button.setEnabled(false);
        button.setText("Saving…");
        String req = requestId;
        Api.async(() -> {
            if (OspChallan.duplicateNumber(api, form.str("dispatch_challan"), null))
                throw new Api.ApiException(409, "Challan Number " + form.str("dispatch_challan").trim().toUpperCase(java.util.Locale.ROOT)
                    + " is already used by another Material Out. Use the suggested series number.");
            JSONObject header = new JSONObject();
            header.put("vendor_id", form.str("vendor_id"));
            header.put("process_id", InspUtil.j(spec, "process_id"));
            header.put("process_specification_id", InspUtil.j(spec, "id"));
            header.put("dispatch_date", form.str("dispatch_date"));
            header.put("dispatch_challan", form.str("dispatch_challan"));
            header.put("expected_return_date", form.str("expected_return_date"));
            header.put("remarks", form.str("remarks"));
            Object res = api.rpcValue("qcms_create_osp_material_out", new JSONObject().put("p_request_id", req).put("p_header", header).put("p_lines", clean));
            JSONObject saved = res instanceof JSONObject ? (JSONObject) res : null;
            JSONArray savedLines = saved == null ? null : saved.optJSONArray("lines");
            if (saved == null || InspUtil.j(saved, "id").isEmpty() || savedLines == null || savedLines.length() != clean.length()) {
                throw new Api.ApiException(500, "Material Out save could not be confirmed. Retry the same entry to recover its saved document.");
            }
            // R38 save_material_out_challan: the challan right after the Material Out (one retry, re-using a header a failed attempt inserted)
            for (int i = 0; i < challanLines.size() && i < savedLines.length(); i++) challanLines.get(i).put("osp_job_id", InspUtil.j(savedLines.optJSONObject(i), "id"));
            Exception challanError = OspChallan.saveWithRetry(api, InspUtil.j(saved, "id"), challanHeader, challanLines);
            if (challanError != null) {
                JSONObject pendingLines = new JSONObject().put("lines", OspRecordView.toArray(challanLines));
                OspChallan.PENDING.put(InspUtil.j(saved, "id"), new JSONObject[]{challanHeader, pendingLines});
                saved.put("_challan_error", Api.message(challanError));
            }
            return saved;
        }, (saved, err) -> {
            button.setEnabled(true);
            button.setText("Create OSP Material Out + Returnable Delivery Challan");
            if (err != null) { a.toast(Api.message(err)); return; }   // same request id is re-used on retry
            requestId = InspUtil.uuid();
            String number = form.str("dispatch_challan").trim().toUpperCase(java.util.Locale.ROOT);
            if (InspUtil.j(saved, "_challan_error").isEmpty())
                a.toast("Material Out " + InspUtil.j(saved, "material_out_number") + " saved with Returnable Delivery Challan " + number + " · "
                    + saved.optJSONArray("lines").length() + " separately traceable heat batches.");
            else
                a.confirm("Challan still to be saved", "Material Out " + InspUtil.j(saved, "material_out_number") + " is saved (stock allocated), but its challan could not be saved: "
                    + InspUtil.j(saved, "_challan_error") + ".\n\nDo NOT create the Material Out again - open Details → Complete challan details (your entries are filled in) and save to retry.", "OK", () -> { });
            Module m = Catalog.get("osp_material_out");
            a.replaceTop(new RecordScreen(a, m == null ? Catalog.adhoc("osp_material_outs") : m, InspUtil.j(saved, "id")));
        });
    }

    // ------------------------------------------------------------------ edit document
    private void renderEdit() {
        if (lines.isEmpty()) { add(Ui.empty(a, "This Material Out document has no heat lines."), 4); return; }
        JSONObject first = lines.get(0);
        List<Field> f = new ArrayList<>();
        f.add(Field.date("dispatch_date", "Dispatch Date").req());
        f.add(Field.date("expected_return_date", "Expected Return").req());
        f.add(Field.text("dispatch_challan", "Common Challan"));
        f.add(Field.area("remarks", "Common Dispatch Remarks"));
        if (form == null) {
            form = new FormView(a, f);
            form.set("dispatch_date", InspUtil.j(first, "dispatch_date").length() >= 10 ? InspUtil.j(first, "dispatch_date").substring(0, 10) : Ui.today());
            form.set("expected_return_date", InspUtil.j(first, "expected_return_date").length() >= 10 ? InspUtil.j(first, "expected_return_date").substring(0, 10) : Ui.today());
            form.set("dispatch_challan", InspUtil.j(first, "dispatch_challan"));
            form.set("remarks", InspUtil.j(first, "dispatch_remarks"));
        } else if (form.getParent() != null) {
            ((android.view.ViewGroup) form.getParent()).removeView(form);
        }
        LinearLayout card = Ui.card(a);
        card.addView(form);
        add(card, 4);
        if (grid == null) {
            grid = new RowsEditor(a, "Heat lines", Arrays.asList(Field.number("quantity_dispatched", "Out Qty pcs").range(1, Double.MAX_VALUE).req()),
                Arrays.asList(new String[]{"material_out_line_no", "Line"}, new String[]{"osp_job_number", "OSP Job"}, new String[]{"heat_number", "Heat"},
                    new String[]{"osp_batch_code", "FSI Batch"}, new String[]{"quantity_dispatched", "Out Qty pcs"}, new String[]{"quantity_received", "Received pcs"}));
            grid.fixedRows();
            grid.setRows(lines);
        } else if (grid.getParent() != null) {
            ((android.view.ViewGroup) grid.getParent()).removeView(grid);
        }
        add(Ui.label(a, "Heat lines · tap a line to change the quantity"), 12);
        add(grid, 4);
        Button save = Ui.primary(a, "Update Material Out Document");
        save.setOnClickListener(v -> {
            String problem = form.validate();
            if (problem != null) { a.toast(problem); return; }
            save.setEnabled(false);
            Api.async(() -> {
                JSONObject header = new JSONObject();
                header.put("dispatch_date", form.str("dispatch_date"));
                header.put("expected_return_date", form.str("expected_return_date"));
                header.put("dispatch_challan", form.str("dispatch_challan"));
                header.put("remarks", form.str("remarks"));
                JSONArray ls = new JSONArray();
                for (JSONObject r : grid.rows()) ls.put(new JSONObject().put("id", InspUtil.j(r, "id")).put("quantity_dispatched", Rules.number(r.opt("quantity_dispatched"))));
                return api.rpc("qcms_update_osp_material_out_group", new JSONObject().put("p_material_out_id", id).put("p_header", header).put("p_lines", ls));
            }, (ok, err) -> {
                save.setEnabled(true);
                if (err != null) { a.toast(Api.message(err)); return; }
                a.toast("Material Out document updated.");
                a.back();
            });
        });
        add(save, 16);
    }
}
