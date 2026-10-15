package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.graphics.Color;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

/**
 * Purchase Order Entry · Raw Material / Forging (render_purchase_orders + create_purchase_order):
 * eligibility of every open Customer Order, multi-order selection, supplier compatibility, allocations,
 * clubbed RM lines, prices / HSN from Part Master, ship-to masters, then the controlled PO write.
 */
final class SupPoScreen extends SupBase {
    static final String[] SHIP_SOURCES = {"BRANCH", "CUSTOMER", "SUPPLIER", "VENDOR"};
    static final String[] SHIP_LABELS = {"Company Branch Master", "Customer Master", "Supplier Master", "Vendor / OSP Master"};

    private static String poType = "RAW_MATERIAL";
    private SupSvc.Data data;
    private List<JSONObject> eligibility = new ArrayList<>();
    private final Map<String, JSONObject> parts = new HashMap<>(), parties = new HashMap<>(), grades = new HashMap<>();
    private final Map<String, String> sectionOf = new HashMap<>();
    private List<JSONObject> branches = new ArrayList<>();
    private String defaultBranch = "";
    private final List<JSONObject> selected = new ArrayList<>();

    private LinearLayout statusBox, entryBox, linesBox;
    private FormView head;
    private RowsEditor allocEditor, lineEditor, forgingEditor;
    private TextView warnings;
    private boolean linesValid = false;
    private int lineSeq = 0;

    private String preselect;

    /** prefill = a Customer Order row ("Create Purchase Order from this order"): its PO type and source are preselected. */
    SupPoScreen(MainActivity a, JSONObject prefill) {
        super(a);
        if (prefill != null && !SupSvc.s(prefill, "id").isEmpty() && !SupSvc.s(prefill, "order_type").isEmpty()) {
            preselect = SupSvc.s(prefill, "id");
            poType = SupSvc.DIRECT_FORGING.equals(SupSvc.flowFor(prefill)) || SupSvc.FSI_RM.equals(SupSvc.flowFor(prefill)) && !SupSvc.truthy(prefill, "rm_procurement_required", true)
                ? "FORGING" : "RAW_MATERIAL";
        }
    }

    @Override public String title() { return "New Purchase Order"; }
    @Override public String subtitle() { return "Raw Material / Forging · controlled supplier PO"; }

    @Override
    public View build() {
        newPage();
        LinearLayout seg = Ui.hbox(a);
        seg.setBackground(Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 12, a));
        seg.setPadding(dp(3), dp(3), dp(3), dp(3));
        String[] types = {"RAW_MATERIAL", "FORGING"};
        String[] names = {"Raw Material PO", "Forging PO"};
        for (int i = 0; i < 2; i++) {
            final String tp = types[i];
            boolean on = tp.equals(poType);
            TextView t = Ui.text(a, names[i], 13, on ? Color.WHITE : Ui.TEAL_DARK, true);
            t.setGravity(Gravity.CENTER);
            t.setPadding(0, dp(9), 0, dp(9));
            if (on) t.setBackground(Ui.round(Ui.TEAL, 0, 0, 10, a));
            t.setOnClickListener(v -> { if (!tp.equals(poType)) { poType = tp; a.rebuild(); } });
            seg.addView(t, Ui.weight(1));
        }
        add(seg, 0);
        statusBox = Ui.vbox(a);
        add(statusBox, 8);
        entryBox = Ui.vbox(a);
        add(entryBox, 8);
        statusBox.addView(loading());
        load();
        return scroll;
    }

    private void load() {
        final String type = poType;
        Api.async(() -> {
            SupSvc.Data d = svc.load();
            List<JSONObject> elig = svc.sourceStatus(d, type);
            Map<String, JSONObject> pm = new HashMap<>(), py = new HashMap<>(), gm = new HashMap<>();
            for (JSONObject r : svc.live("parts?select=*&limit=5000")) pm.put(SupSvc.s(r, "id"), r);
            for (JSONObject r : svc.live("parties?select=*&status=eq.ACTIVE&order=party_name.asc&limit=5000")) py.put(SupSvc.s(r, "id"), r);
            for (JSONObject r : svc.live("material_grades?select=id,grade_code,grade_name&limit=3000")) gm.put(SupSvc.s(r, "id"), r);
            List<JSONObject> br = svc.live("company_branches?select=*&status=eq.ACTIVE&order=branch_code.asc&limit=500");
            Map<String, String> sections = new HashMap<>();
            if ("RAW_MATERIAL".equals(type)) {
                Map<String, String> byPart = new HashMap<>();
                for (JSONObject r : elig) {
                    if (!r.optBoolean("_po_eligible")) continue;
                    String pid = SupSvc.s(r, "part_id");
                    if (!byPart.containsKey(pid)) byPart.put(pid, svc.rmSectionLabel(pm.containsKey(pid) ? pm.get(pid) : svc.get("parts", pid), gm));
                    sections.put(SupSvc.s(r, "id"), byPart.get(pid));
                }
            }
            // resolve_current_branch: Employee Master plant → branch code / plant code / name, else default, else first
            String def = "";
            JSONObject emp = svc.get("employees", api.employeeId);
            String plant = SupSvc.t(emp, "plant").toLowerCase(Locale.ROOT);
            if (!plant.isEmpty()) for (JSONObject b : br) {
                if (plant.equals(SupSvc.t(b, "branch_code").toLowerCase(Locale.ROOT)) || plant.equals(SupSvc.t(b, "plant_code").toLowerCase(Locale.ROOT))
                    || plant.equals(SupSvc.t(b, "branch_name").toLowerCase(Locale.ROOT))) { def = SupSvc.s(b, "id"); break; }
            }
            if (def.isEmpty()) for (JSONObject b : br) if (b.optBoolean("is_default")) { def = SupSvc.s(b, "id"); break; }
            if (def.isEmpty() && !br.isEmpty()) def = SupSvc.s(br.get(0), "id");
            return new Object[]{d, elig, pm, py, gm, br, sections, def};
        }, (res, err) -> {
            statusBox.removeAllViews();
            if (err != null) { statusBox.addView(error(err, this::reload)); return; }
            data = (SupSvc.Data) res[0];
            @SuppressWarnings("unchecked") List<JSONObject> el = (List<JSONObject>) res[1]; eligibility = el;
            @SuppressWarnings("unchecked") Map<String, JSONObject> pm = (Map<String, JSONObject>) res[2]; parts.putAll(pm);
            @SuppressWarnings("unchecked") Map<String, JSONObject> py = (Map<String, JSONObject>) res[3]; parties.putAll(py);
            @SuppressWarnings("unchecked") Map<String, JSONObject> gm = (Map<String, JSONObject>) res[4]; grades.putAll(gm);
            @SuppressWarnings("unchecked") List<JSONObject> br = (List<JSONObject>) res[5]; branches = br;
            @SuppressWarnings("unchecked") Map<String, String> sec = (Map<String, String>) res[6]; sectionOf.putAll(sec);
            defaultBranch = (String) res[7];
            if (preselect != null) {
                for (JSONObject r : eligibility) if (preselect.equals(SupSvc.s(r, "id")) && r.optBoolean("_po_eligible")
                    && ("RAW_MATERIAL".equals(poType) || r.optJSONObject("_po_source") != null)) selected.add(r);
                if (selected.isEmpty()) a.toast("The selected Customer Order is not eligible for a " + Ui.pretty(poType) + " PO now - see the reason column.");
                preselect = null;
            }
            renderStatus();
            if (!selected.isEmpty()) prepare();
        });
    }

    private String label(JSONObject o, String extra) {
        return SupSvc.orderLabel(o, parts.get(SupSvc.s(o, "part_id")), parties.get(SupSvc.s(o, "customer_id")), extra);
    }

    private void renderStatus() {
        boolean rm = "RAW_MATERIAL".equals(poType);
        List<String> headers = Arrays.asList("Customer PO / Ref", "Pos", "Part", "FSI", "Customer", "Supply Flow", "Qty pcs", rm ? "RM Balance kg" : "Forging Balance pcs", "Due", "PO Eligibility", "Reason");
        List<List<String>> rows = new ArrayList<>();
        int eligible = 0;
        for (JSONObject r : eligibility) {
            JSONObject part = parts.get(SupSvc.s(r, "part_id"));
            boolean el = r.optBoolean("_po_eligible");
            if (el) eligible++;
            JSONObject src = r.optJSONObject("_po_source");
            rows.add(Arrays.asList(SupSvc.first(SupSvc.s(r, "customer_order_no"), SupSvc.s(r, "master_reference_no")), SupSvc.s(r, "order_position"),
                SupSvc.s(part, "part_number"), SupSvc.s(part, "fsi_part_number"), SupSvc.s(parties.get(SupSvc.s(r, "customer_id")), "party_name"),
                SupSvc.flowLabel(SupSvc.flowFor(r)), f0(SupSvc.num(r, "order_qty_pcs")),
                rm ? f3(SupSvc.num(r, "rm_balance_kg")) : (src == null ? "-" : f0(SupSvc.num(src, "_balance_pcs"))),
                Ui.date(SupSvc.s(r, "customer_delivery_date")), el ? "ELIGIBLE" : "WAITING / NOT REQUIRED", SupSvc.s(r, "_po_reason")));
        }
        offlineNote();
        statusBox.addView(Ui.label(a, "A · Customer Orders / Schedules · PO source status"));
        if (rows.isEmpty()) statusBox.addView(Ui.empty(a, "No open Customer Order / Schedule is available."));
        else statusBox.addView(new DataGrid(a, "PO source status", headers, rows, 300, null));
        statusBox.addView(Ui.text(a, "Open Customer Orders / Schedules: " + eligibility.size() + " · Eligible for " + (rm ? "RM" : "Forging") + " PO: " + eligible, 12, Ui.MUTED, false), Ui.matchWrap(a, 4));
        Button pick = Ui.outline(a, selected.isEmpty() ? "Select eligible " + (rm ? "Customer Orders / Schedules" : "Forging PO source(s)") : "Change selected sources (" + selected.size() + ")", Ui.TEAL);
        pick.setOnClickListener(v -> pickSources());
        statusBox.addView(pick, Ui.matchWrap(a, 8));
        if (eligible == 0) statusBox.addView(note("No Customer Order is currently eligible for a" + (rm ? "n RM" : " Forging") + " Purchase Order. Review the reason column above.", "amber"), Ui.matchWrap(a, 6));
    }

    private void pickSources() {
        boolean rm = "RAW_MATERIAL".equals(poType);
        List<JSONObject> eligible = new ArrayList<>();
        for (JSONObject r : eligibility) if (r.optBoolean("_po_eligible") && (rm || r.optJSONObject("_po_source") != null)) eligible.add(r);
        if (eligible.isEmpty()) { a.toast("Nothing is eligible."); return; }
        if (rm) {
            TreeSet<String> sections = new TreeSet<>();
            for (JSONObject r : eligible) sections.add(SupSvc.first(sectionOf.get(SupSvc.s(r, "id")), "RM section not set"));
            if (sections.size() > 1) {
                List<String> opts = new ArrayList<>();
                opts.add("All RM sections");
                opts.addAll(sections);
                new AlertDialog.Builder(a).setTitle("Club by Raw Material Section").setItems(opts.toArray(new String[0]), (dlg, w) -> {
                    List<JSONObject> list = new ArrayList<>();
                    for (JSONObject r : eligible) if (w == 0 || opts.get(w).equals(sectionOf.get(SupSvc.s(r, "id")))) list.add(r);
                    multi(list);
                }).setNegativeButton("Back", null).show();
                return;
            }
        }
        multi(eligible);
    }

    private void multi(List<JSONObject> list) {
        boolean rm = "RAW_MATERIAL".equals(poType);
        String[] names = new String[list.size()];
        boolean[] checked = new boolean[list.size()];
        Set<String> current = new HashSet<>();
        for (JSONObject r : selected) current.add(SupSvc.s(r, "id"));
        for (int i = 0; i < list.size(); i++) {
            JSONObject r = list.get(i);
            if (rm) names[i] = "[" + SupSvc.first(sectionOf.get(SupSvc.s(r, "id")), "-") + "] " + label(r, "RM Balance " + f3(SupSvc.num(r, "rm_balance_kg")) + " kg · Due " + Ui.date(SupSvc.s(r, "customer_delivery_date")));
            else {
                JSONObject src = r.optJSONObject("_po_source");
                names[i] = label(r, SupSvc.s(src, "_source_type") + " · Balance " + f0(SupSvc.num(src, "_balance_pcs")) + " pcs");
            }
            checked[i] = current.contains(SupSvc.s(r, "id"));
        }
        new AlertDialog.Builder(a).setTitle(rm ? "Customer Orders for this RM PO" : "Forging PO sources")
            .setMultiChoiceItems(names, checked, (d, i, on) -> checked[i] = on)
            .setPositiveButton("OK", (d, w) -> {
                selected.clear();
                for (int i = 0; i < checked.length; i++) if (checked[i]) selected.add(list.get(i));
                statusBox.removeAllViews();
                renderStatus();
                prepare();
            }).setNegativeButton("Back", null).show();
    }

    // ------------------------------------------------------------------ entry form
    private void prepare() {
        entryBox.removeAllViews();
        head = null;
        if (selected.isEmpty()) { entryBox.addView(Ui.text(a, "Select the pending source(s) above.", 12.5f, Ui.MUTED, false)); return; }
        entryBox.addView(loading());
        final boolean rm = "RAW_MATERIAL".equals(poType);
        final List<JSONObject> sel = new ArrayList<>(selected);
        Api.async(() -> {
            Set<String> compatible = null;
            StringBuilder errors = new StringBuilder();
            for (JSONObject o : sel) {
                Set<String> ids = new HashSet<>();
                for (JSONObject r : svc.rawMaterialOptions(SupSvc.s(o, "part_id"))) {
                    if (rm) { if ("ACTIVE".equals(SupSvc.first(SupSvc.s(r, "status"), "ACTIVE"))) ids.add(SupSvc.s(r, "supplier_id")); }
                    else if (!SupSvc.s(r, "_source_error").isEmpty()) errors.append(SupSvc.s(r, "_source_error")).append('\n');
                    else ids.add(SupSvc.s(r, "supplier_id"));
                }
                if (compatible == null) compatible = ids; else compatible.retainAll(ids);
            }
            if (compatible == null) compatible = new HashSet<>();
            if (!rm) {
                Set<String> forgers = new HashSet<>();
                for (JSONObject o : sel) {
                    JSONObject disp = o.optJSONObject("_po_source") == null ? null : o.optJSONObject("_po_source").optJSONObject("_rm_dispatch");
                    if (disp != null && !SupSvc.t(disp, "forging_supplier_id").isEmpty()) forgers.add(SupSvc.t(disp, "forging_supplier_id"));
                }
                if (forgers.size() > 1) { errors.append("The selected RM-to-Forger dispatches were sent to different forgers. Create a separate Forging PO for each forger.\n"); compatible.clear(); }
                else if (!forgers.isEmpty()) compatible.retainAll(forgers);
            }
            return new Object[]{compatible, errors.toString()};
        }, (res, err) -> {
            entryBox.removeAllViews();
            if (err != null) { entryBox.addView(error(err, this::prepare)); return; }
            @SuppressWarnings("unchecked") Set<String> compatible = (Set<String>) res[0];
            renderEntry(compatible, (String) res[1]);
        });
    }

    private void renderEntry(Set<String> compatible, String errors) {
        boolean rm = "RAW_MATERIAL".equals(poType);
        List<String> supIds = new ArrayList<>(), supLabels = new ArrayList<>();
        for (JSONObject p : parties.values()) {
            Set<String> types = SupSvc.partyTypes(p);
            if (!(types.contains("SUPPLIER") || types.contains("STEEL_MILL") || types.contains("OSP_VENDOR"))) continue;
            if (!compatible.contains(SupSvc.s(p, "id"))) continue;
            supIds.add(SupSvc.s(p, "id"));
            supLabels.add(SupSvc.partyLabel(p));
        }
        entryBox.addView(Ui.label(a, "B · Purchase Order entry"));
        if (!errors.isEmpty()) entryBox.addView(note(errors.trim(), "red"), Ui.matchWrap(a, 4));
        if (supIds.isEmpty()) {
            entryBox.addView(note(rm ? "The selected Customer Orders / Schedules do not share one common supplier-specific Raw Material record in Part Master. Split them into separate POs or add the same approved supplier to each Part Raw Material Detail."
                : "No common valid supplier source. Maintain the linked raw part's ACTIVE Section E details and current supplier approval. The PO supplier must be the forger the RM was dispatched to.", "red"), Ui.matchWrap(a, 4));
            return;
        }
        if (api.employeeId == null || api.employeeId.isEmpty())
            entryBox.addView(note("Your login is not linked to an ACTIVE Employee Master record. Link the user to Employee Master before creating a Purchase Order so Requisitioner is controlled.", "red"), Ui.matchWrap(a, 4));
        String defSupplier = supIds.get(0);
        if (!rm) { String fs = SupSvc.s(selected.get(0), "forging_supplier_id"); if (supIds.contains(fs)) defSupplier = fs; }
        String[] brIds = new String[branches.size()], brLabels = new String[branches.size()];
        for (int i = 0; i < branches.size(); i++) { brIds[i] = SupSvc.s(branches.get(i), "id"); brLabels[i] = Lookups.BRANCH.of(branches.get(i)); }
        if (brIds.length == 0) entryBox.addView(note("No ACTIVE Company Branch is available. Add one in Masters → Company Branch before creating a PO.", "red"), Ui.matchWrap(a, 4));
        List<Field> f = new ArrayList<>();
        f.add(Field.select("supplier_id", "Supplier", supIds.toArray(new String[0])).labels(supLabels.toArray(new String[0])).req().def(defSupplier));
        f.add(Field.date("order_date", "PO Date").req().def(Ui.today()));
        f.add(Field.select("company_branch_id", "Company Branch / Plant", brIds).labels(brLabels).req().def(defaultBranch.isEmpty() ? null : defaultBranch));
        f.add(Field.select("ship_to_source_type", "Ship-To Source", SHIP_SOURCES).labels(SHIP_LABELS).req().def("BRANCH"));
        f.add(Field.select("ship_to_id", "Ship-To Branch / Party / Address").req());
        f.add(Field.date("delivery_date", "Delivery Date").hint("Defaults from the supplier lead time; editable"));
        f.add(Field.info("requisitioner", "Requisitioner (Logged-in Employee)").def(SupSvc.first(api.employeeLabel, "Employee link required")));
        f.add(Field.text("ship_via", "Ship Via").def("Road"));
        f.add(Field.text("incoterm", "Incoterm").def("DAP, CHAKAN"));
        f.add(Field.text("payment_term", "Payment Term").def("NET 30 DAYS AFTER GRN"));
        f.add(Field.date("quotation_date", "Quotation Date").def(Ui.today()));
        f.add(Field.text("quotation_reference", "Quotation Reference"));
        f.add(Field.text("old_po_reference", "Old PO Details"));
        f.add(Field.number("gst_percent", "GST %").def(18.0).range(0, Double.NaN));
        head = new FormView(a, f);
        entryBox.addView(head, Ui.matchWrap(a, 0));
        linesBox = Ui.vbox(a);
        entryBox.addView(linesBox, Ui.matchWrap(a, 10));
        List<Field> tail = new ArrayList<>();
        tail.add(Field.area("remarks", "Remarks").def("PART WILL BE SUPPLIED AS PER DRAWING."));
        tail.add(Field.area("special_instructions", "Comments / Special Instructions").def(SupSvc.DEFAULT_SPECIAL_INSTRUCTIONS));
        FormView tailForm = new FormView(a, tail);
        entryBox.addView(tailForm, Ui.matchWrap(a, 6));
        warnings = Ui.text(a, "", 12, Ui.ORANGE, false);
        entryBox.addView(warnings, Ui.matchWrap(a, 8));
        Button create = Ui.primary(a, "Create Controlled Purchase Order");
        entryBox.addView(create, Ui.matchWrap(a, 12));
        create.setOnClickListener(v -> create(create, tailForm));
        head.onChange((k, val) -> {
            if (k.equals("supplier_id") || k.equals("order_date")) computeLines();
            if (k.equals("ship_to_source_type") || k.equals("company_branch_id") || k.equals("supplier_id")) refreshShipTo();
        });
        refreshShipTo();
        computeLines();
    }

    private void refreshShipTo() {
        if (head == null) return;
        String source = head.str("ship_to_source_type");
        List<String> ids = new ArrayList<>(), labels = new ArrayList<>();
        String def = "";
        if ("BRANCH".equals(source) || source.isEmpty()) {
            for (JSONObject b : branches) { ids.add(SupSvc.s(b, "id")); labels.add(Lookups.join(SupSvc.first(SupSvc.s(b, "branch_code"), "-"), SupSvc.first(SupSvc.s(b, "branch_name"), "-"), SupSvc.first(SupSvc.s(b, "city"), "-"))); }
            def = SupSvc.first(head.str("company_branch_id"), defaultBranch);
        } else {
            List<JSONObject> cands = new ArrayList<>();
            for (JSONObject p : parties.values()) if (SupSvc.shipToMatches(p, source)) cands.add(p);
            cands.sort((x, y) -> SupSvc.s(x, "party_name").toLowerCase(Locale.ROOT).compareTo(SupSvc.s(y, "party_name").toLowerCase(Locale.ROOT)));
            for (JSONObject p : cands) { ids.add(SupSvc.s(p, "id")); labels.add(Lookups.join(SupSvc.first(SupSvc.s(p, "party_code"), "-"), SupSvc.first(SupSvc.s(p, "party_name"), "-"), SupSvc.first(SupSvc.s(p, "city"), "-"))); }
            if ("CUSTOMER".equals(source) && !selected.isEmpty() && ids.contains(SupSvc.s(selected.get(0), "customer_id"))) def = SupSvc.s(selected.get(0), "customer_id");
            if ("SUPPLIER".equals(source) && ids.contains(head.str("supplier_id"))) def = head.str("supplier_id");
        }
        Field ship = head.field("ship_to_id");
        ship.options = ids.toArray(new String[0]);
        ship.optionLabels = labels.toArray(new String[0]);
        head.set("ship_to_id", ids.contains(def) ? def : (ids.isEmpty() ? null : ids.get(0)));
    }

    // ------------------------------------------------------------------ PO lines
    private void computeLines() {
        if (head == null) return;
        final int mySeq = ++lineSeq;
        final String supplier = head.str("supplier_id"), orderDate = SupSvc.first(head.str("order_date"), Ui.today());
        final boolean rm = "RAW_MATERIAL".equals(poType);
        final List<JSONObject> sel = new ArrayList<>(selected);
        linesValid = false;
        linesBox.removeAllViews();
        if (supplier.isEmpty()) return;
        linesBox.addView(loading());
        Api.async(() -> {
            List<JSONObject> rows = new ArrayList<>();
            Map<String, JSONObject> lines = new LinkedHashMap<>();
            StringBuilder problems = new StringBuilder();
            int lead = 0;
            List<String> dues = new ArrayList<>();
            for (JSONObject o : sel) {
                String oid = SupSvc.s(o, "id");
                JSONObject order = data.order(oid);
                if (!SupSvc.s(order, "customer_delivery_date").isEmpty()) dues.add(SupSvc.d10(SupSvc.s(order, "customer_delivery_date")));
                JSONObject part = parts.containsKey(SupSvc.s(order, "part_id")) ? parts.get(SupSvc.s(order, "part_id")) : svc.get("parts", SupSvc.s(order, "part_id"));
                JSONObject raw = svc.rawMaterialForSupplier(SupSvc.s(part, "id"), supplier, SupSvc.s(order, "raw_material_detail_id"));
                lead = Math.max(lead, raw == null ? 0 : (int) SupSvc.num(raw, "lead_time_days"));
                JSONObject cust = parties.get(SupSvc.s(order, "customer_id"));
                if (rm) {
                    double balance = Math.max(SupSvc.num(order, "required_rm_kg") - data.totals(oid)[SupSvc.RM_ORDERED], 0);
                    JSONObject rr = raw == null ? new JSONObject() : raw;
                    String key = svc.rmGroupKey(part, rr);
                    JSONObject grade = grades.get(SupSvc.first(SupSvc.s(rr, "material_grade_id"), SupSvc.s(part, "material_grade_id")));
                    rows.add(new JSONObject().put("order_id", oid).put("key", key).put("ref", SupSvc.s(order, "master_reference_no")).put("customer", SupSvc.s(cust, "party_name"))
                        .put("part_number", SupSvc.s(part, "part_number")).put("position", SupSvc.s(order, "order_position"))
                        .put("fsi", SupSvc.first(SupSvc.s(part, "fsi_part_number"), "ENTER IN ITEM GRID")).put("part_desc", SupSvc.s(part, "part_name"))
                        .put("raw_type", raw == null ? "NO SUPPLIER RM DETAIL" : SupSvc.s(raw, "material_section_name")).put("grade", SupSvc.first(SupSvc.s(grade, "grade_code"), "-"))
                        .put("size", SupSvc.first(SupSvc.s(rr, "section_size"), "-")).put("pending", balance).put("alloc", balance));
                    if (raw == null) problems.append(SupSvc.first(SupSvc.s(part, "fsi_part_number"), SupSvc.s(part, "part_number"))).append(": no ACTIVE Raw Material Detail for this supplier.\n");
                    JSONObject line = lines.get(key);
                    if (line == null) {
                        double price = svc.currentPrice(SupSvc.s(part, "id"), supplier, orderDate, "KGS", SupSvc.s(rr, "id"));
                        String hsn = SupSvc.first(SupSvc.t(rr, "hsn_sac_code"), SupSvc.t(part, "hsn_sac_code"));
                        line = new JSONObject().put("key", key).put("fsi", SupSvc.first(SupSvc.s(rr, "supplier_rm_item_code"), SupSvc.s(part, "fsi_part_number")))
                            .put("linked", "").put("hsn", hsn).put("desc", SupSvc.s(part, "part_name")).put("raw_type", SupSvc.s(rr, "material_section_name"))
                            .put("grade", SupSvc.first(SupSvc.s(grade, "grade_code"), "-")).put("size", SupSvc.s(rr, "section_size")).put("qty", 0.0).put("price", price)
                            .put("_parts", new JSONArray());
                        lines.put(key, line);
                    }
                    line.getJSONArray("_parts").put(SupSvc.first(SupSvc.s(part, "fsi_part_number"), SupSvc.s(part, "part_number")));
                } else {
                    JSONObject src = o.optJSONObject("_po_source");
                    JSONObject rr = raw == null ? new JSONObject() : raw;
                    String common = SupSvc.t(rr, "supplier_forging_part_number");
                    double price = 0; String hsn = "";
                    try {
                        price = svc.effectiveCurrentPrice(part, rr, supplier, orderDate, "NOS");
                        JSONObject[] ctx = svc.resolveRawSource(part, rr, supplier);
                        hsn = SupSvc.first(SupSvc.t(ctx[1], "hsn_sac_code"), SupSvc.t(ctx[0], "hsn_sac_code"));
                        if (!SupSvc.t(rr, "source_part_id").isEmpty()) common = SupSvc.first(SupSvc.s(ctx[0], "part_number"), SupSvc.s(ctx[1], "supplier_forging_part_number"));
                    } catch (SupSvc.Rule e) {
                        problems.append(e.getMessage()).append('\n');
                        continue;
                    }
                    double balance = Math.max(SupSvc.num(src, "_balance_pcs"), 0);
                    rows.add(new JSONObject().put("order_id", oid).put("ref", SupSvc.s(order, "master_reference_no")).put("customer", SupSvc.s(cust, "party_name"))
                        .put("part_number", SupSvc.s(part, "part_number")).put("fsi", SupSvc.s(part, "fsi_part_number")).put("common", common)
                        .put("available", balance).put("qty", balance).put("price", price).put("hsn", hsn)
                        .put("_dispatch", src != null && src.optJSONObject("_rm_dispatch") != null ? src.optJSONObject("_rm_dispatch") : new JSONObject()));
                }
            }
            for (JSONObject line : lines.values()) {
                TreeSet<String> lp = new TreeSet<>();
                JSONArray ps = line.getJSONArray("_parts");
                for (int i = 0; i < ps.length(); i++) lp.add(ps.optString(i));
                line.put("linked", String.join(", ", lp));
                line.remove("_parts");
            }
            String delivery;
            java.time.LocalDate od = java.time.LocalDate.parse(SupSvc.d10(orderDate));
            if (lead > 0) delivery = od.plusDays(lead).toString();
            else if (!dues.isEmpty()) { java.util.Collections.sort(dues); delivery = dues.get(0); }
            else delivery = od.toString();
            return new Object[]{rows, new ArrayList<>(lines.values()), problems.toString(), delivery, lead};
        }, (res, err) -> {
            if (mySeq != lineSeq) return;
            linesBox.removeAllViews();
            if (err != null) { linesBox.addView(error(err, this::computeLines)); return; }
            @SuppressWarnings("unchecked") List<JSONObject> rows = (List<JSONObject>) res[0];
            @SuppressWarnings("unchecked") List<JSONObject> lines = (List<JSONObject>) res[1];
            String problems = (String) res[2];
            head.set("delivery_date", res[3]);
            if ((Integer) res[4] > 0) linesBox.addView(Ui.text(a, "Delivery default calculated from Part Master supplier lead time: " + res[4] + " day(s) from PO Date.", 11.5f, Ui.MUTED, false));
            if (!problems.isEmpty()) linesBox.addView(note(problems.trim(), "red"), Ui.matchWrap(a, 4));
            if ("RAW_MATERIAL".equals(poType)) renderRmLines(rows, lines); else renderForgingLines(rows);
            linesValid = problems.isEmpty();
            validateLines();
        });
    }

    private void renderRmLines(List<JSONObject> rows, List<JSONObject> lines) {
        List<Field> af = new ArrayList<>();
        for (String[] c : new String[][]{{"ref", "Customer Order / Schedule"}, {"customer", "Customer"}, {"part_number", "Part Number"}, {"position", "Position"}, {"fsi", "FSI Part Number"},
            {"raw_type", "Raw Material Type"}, {"grade", "Material Grade"}, {"size", "Section Size"}, {"pending", "Pending RM kg"}}) af.add(Field.info(c[0], c[1]));
        af.add(Field.number("alloc", "PO Allocation kg").req().range(0.001, Double.NaN));
        List<String[]> ac = Arrays.asList(new String[]{"ref", "Order / Schedule"}, new String[]{"part_number", "Part"}, new String[]{"position", "Pos"},
            new String[]{"raw_type", "RM Type"}, new String[]{"grade", "Grade"}, new String[]{"size", "Size"}, new String[]{"pending", "Pending kg"}, new String[]{"alloc", "PO Allocation kg"});
        allocEditor = new RowsEditor(a, "PO allocations", af, ac).fixedRows();
        allocEditor.setRows(rows);
        allocEditor.check(r -> {
            double v = r.optDouble("alloc", 0);
            return v <= 0 ? "PO Allocation kg must be greater than zero." : null;
        });
        linesBox.addView(Ui.label(a, "Customer Order allocations · tap a row to change the kg"));
        linesBox.addView(allocEditor);
        List<Field> lf = new ArrayList<>();
        lf.add(Field.text("fsi", "FSI Part Number").req().hint("Supplier-facing identity; enter it here if Part Master is blank"));
        for (String[] c : new String[][]{{"linked", "Linked Finished Parts"}, {"hsn", "HSN / SAC"}, {"desc", "Part Description"}, {"raw_type", "Raw Material Type"}, {"grade", "Material Grade"},
            {"size", "Section Size"}, {"qty", "PO Qty kg"}, {"price", "Current Price"}}) lf.add(Field.info(c[0], c[1]));
        List<String[]> lc = Arrays.asList(new String[]{"fsi", "FSI Part Number"}, new String[]{"linked", "Linked Parts"}, new String[]{"hsn", "HSN / SAC"},
            new String[]{"raw_type", "RM Type"}, new String[]{"grade", "Grade"}, new String[]{"size", "Size"}, new String[]{"qty", "PO Qty kg"}, new String[]{"price", "Price / kg"});
        lineEditor = new RowsEditor(a, "PO items (clubbed by raw material)", lf, lc).fixedRows();
        lineEditor.setRows(lines);
        lineEditor.onChanged(this::validateLines);
        allocEditor.onChanged(() -> { sumLines(); validateLines(); });
        sumLines();
        linesBox.addView(Ui.label(a, "PO items · price and HSN from Part Master"), Ui.matchWrap(a, 8));
        linesBox.addView(lineEditor);
    }

    private void sumLines() {
        Map<String, Double> qty = new HashMap<>();
        for (JSONObject r : allocEditor.rows()) qty.merge(SupSvc.s(r, "key"), r.optDouble("alloc", 0), Double::sum);
        for (JSONObject l : lineEditor.rows()) {
            try { l.put("qty", SupSvc.r3(qty.getOrDefault(SupSvc.s(l, "key"), 0.0))); } catch (Exception ignored) { }
        }
        lineEditor.refresh();
    }

    private void renderForgingLines(List<JSONObject> rows) {
        List<Field> ff = new ArrayList<>();
        for (String[] c : new String[][]{{"ref", "Customer Order"}, {"customer", "Customer"}, {"part_number", "Finished Part"}, {"fsi", "FSI Part"}, {"common", "Supplier Forging Part No."},
            {"available", "Available pcs"}, {"price", "Current Price"}, {"hsn", "HSN / SAC"}}) ff.add(Field.info(c[0], c[1]));
        ff.add(Field.number("qty", "PO Qty pcs").req().range(0.001, Double.NaN));
        List<String[]> fc = Arrays.asList(new String[]{"ref", "Customer Order"}, new String[]{"part_number", "Finished Part"}, new String[]{"fsi", "FSI Part"},
            new String[]{"common", "Supplier Forging Part No."}, new String[]{"available", "Available pcs"}, new String[]{"qty", "PO Qty pcs"}, new String[]{"price", "Price"}, new String[]{"hsn", "HSN / SAC"});
        forgingEditor = new RowsEditor(a, "Forging PO sources", ff, fc).fixedRows();
        forgingEditor.setRows(rows);
        forgingEditor.onChanged(this::validateLines);
        linesBox.addView(Ui.label(a, "Forging sources · tap a row to change the pcs"));
        linesBox.addView(forgingEditor);
    }

    /** Same "PO creation is waiting for" checks as the website form. */
    private String blockers() {
        List<String> b = new ArrayList<>();
        if (api.employeeId == null || api.employeeId.isEmpty()) b.add("signed-in user is not linked to an ACTIVE Employee Master");
        if (head == null || head.str("supplier_id").isEmpty()) b.add("Supplier is not selected");
        if (head == null || head.str("company_branch_id").isEmpty()) b.add("Company Branch / Plant is not selected");
        if (head == null || head.str("ship_to_id").isEmpty()) b.add("Ship-To address is not selected");
        boolean valid = linesValid;
        List<String> warn = new ArrayList<>();
        if ("RAW_MATERIAL".equals(poType)) {
            if (lineEditor == null) valid = false;
            else {
                for (JSONObject r : allocEditor.rows()) if (r.optDouble("alloc", 0) <= 0) valid = false;
                for (JSONObject l : lineEditor.rows()) {
                    if (SupSvc.t(l, "fsi").isEmpty() || l.optDouble("price", 0) <= 0 || SupSvc.t(l, "hsn").isEmpty()) valid = false;
                    if (l.optDouble("price", 0) <= 0) warn.add("Current Price is missing in Part Master price history for one or more items. Add the current supplier price before creating the PO.");
                    if (SupSvc.t(l, "hsn").isEmpty()) warn.add("HSN / SAC is missing in Part Master Raw Material Details for one or more items. Add it in Part Master before creating the PO.");
                }
            }
        } else {
            if (forgingEditor == null || forgingEditor.rows().isEmpty()) valid = false;
            else {
                Set<String> codes = new HashSet<>(), hsns = new HashSet<>();
                Set<Double> prices = new HashSet<>();
                for (JSONObject r : forgingEditor.rows()) {
                    double q = r.optDouble("qty", 0);
                    if (q <= 0 || q > r.optDouble("available", 0) + .0001) valid = false;
                    codes.add(SupSvc.t(r, "common").toLowerCase(Locale.ROOT));
                    prices.add(SupSvc.r6(r.optDouble("price", 0)));
                    hsns.add(SupSvc.t(r, "hsn"));
                }
                if (forgingEditor.rows().size() > 1 && (codes.contains("") || codes.size() > 1)) { valid = false; warn.add("To combine multiple finished Parts in one Forging PO, maintain the SAME Supplier Forging Part No. for each supplier Raw Material Detail in Part Master."); }
                if (prices.size() > 1) { valid = false; warn.add("The shared forging sources have different current supplier prices. Align Price History or split the PO."); }
                if (hsns.contains("") || hsns.size() > 1) { valid = false; warn.add("The shared forging sources must use the same HSN/SAC."); }
                for (Double p : prices) if (p <= 0) { valid = false; warn.add("Current Price is missing for one or more forging sources."); break; }
            }
        }
        if (!valid) b.add("one or more PO item fields / prices / HSN / FSI Part Numbers are incomplete");
        StringBuilder out = new StringBuilder();
        for (String w : new LinkedHashSet<>(warn)) out.append(w).append('\n');
        if (!b.isEmpty()) out.append("PO creation is waiting for: ").append(String.join("; ", b)).append('.');
        return out.toString().trim();
    }

    private void validateLines() {
        if (warnings == null) return;
        String b = blockers();
        warnings.setText(b.isEmpty() ? "PO entry is ready." : b);
        warnings.setTextColor(b.contains("waiting for") ? Ui.ORANGE : Ui.GREEN_FG);
    }

    private void create(Button button, FormView tail) {
        String problem = head.validate();
        String b = blockers();
        if (problem == null && b.contains("waiting for")) problem = b.substring(b.indexOf("PO creation is waiting for"));
        if (problem != null) { a.toast(problem); validateLines(); return; }
        JSONObject p;
        try {
            String ship = head.str("ship_to_source_type");
            p = new JSONObject().put("po_type", poType).put("supplier_id", head.str("supplier_id")).put("company_branch_id", head.str("company_branch_id"))
                .put("order_date", head.str("order_date")).put("delivery_date", SupSvc.n(head.str("delivery_date"))).put("requisitioner_employee_id", SupSvc.n(api.employeeId))
                .put("ship_to_source_type", ship).put("ship_to_branch_id", "BRANCH".equals(ship) ? head.str("ship_to_id") : JSONObject.NULL)
                .put("ship_to_party_id", "BRANCH".equals(ship) ? JSONObject.NULL : head.str("ship_to_id"))
                .put("ship_via", head.str("ship_via")).put("incoterm", head.str("incoterm")).put("payment_term", head.str("payment_term"))
                .put("quotation_reference", SupSvc.n(head.str("quotation_reference"))).put("quotation_date", SupSvc.n(head.str("quotation_date")))
                .put("old_po_reference", SupSvc.n(head.str("old_po_reference"))).put("gst_percent", head.num("gst_percent") == null ? 0 : head.num("gst_percent"))
                .put("remarks", SupSvc.n(tail.str("remarks"))).put("special_instructions", SupSvc.n(tail.str("special_instructions")));
            if ("RAW_MATERIAL".equals(poType)) {
                JSONArray ids = new JSONArray();
                JSONObject alloc = new JSONObject(), prices = new JSONObject(), hsn = new JSONObject(), fsi = new JSONObject();
                for (JSONObject r : allocEditor.rows()) { ids.put(SupSvc.s(r, "order_id")); alloc.put(SupSvc.s(r, "order_id"), r.optDouble("alloc", 0)); }
                for (JSONObject l : lineEditor.rows()) {
                    String key = SupSvc.s(l, "key");
                    prices.put(key, l.optDouble("price", 0)); hsn.put(key, SupSvc.t(l, "hsn")); fsi.put(key, SupSvc.t(l, "fsi"));
                }
                p.put("customer_order_ids", ids).put("allocations", alloc).put("line_prices", prices).put("line_hsn_sac", hsn).put("line_fsi_part_numbers", fsi);
            } else {
                JSONArray src = new JSONArray();
                for (JSONObject r : forgingEditor.rows())
                    src.put(new JSONObject().put("customer_order_id", SupSvc.s(r, "order_id")).put("quantity", r.optDouble("qty", 0))
                        .put("rm_dispatch", r.optJSONObject("_dispatch") == null ? new JSONObject() : r.optJSONObject("_dispatch")));
                p.put("forging_sources", src).put("uom", "NOS");
            }
        } catch (Exception e) { showError(e); return; }
        a.confirm("Create Purchase Order?", "The PO is saved and submitted for approval. You may edit it at any time before approval.", "Create", () ->
            busy(button, "Creating…", () -> svc.createPurchaseOrder(p), (res, err) -> {
                JSONObject h = res.optJSONObject("header");
                a.toast("Purchase Order " + SupSvc.s(h, "po_number") + " created and submitted for approval.");
                a.replaceTop(new PoDetailScreen(a, SupSvc.s(h, "id")));
            }));
    }
}
