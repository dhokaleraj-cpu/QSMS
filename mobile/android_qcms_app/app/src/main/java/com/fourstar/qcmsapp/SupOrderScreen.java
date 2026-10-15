package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Customer Order / Monthly Schedule entry (render_customer_orders section A + create_customer_order) and the
 * controlled edit panel (update_customer_order + sync_order_status).
 */
final class SupOrderScreen extends SupBase {
    private final String id;
    private FormView form, months;
    private LinearLayout monthsBox;
    private TextView checkText, rawNote;
    private final Map<String, JSONObject> rawRows = new HashMap<>();
    private JSONObject check;
    private int seq = 0;
    private String partNumber = "";

    SupOrderScreen(MainActivity a, String id, JSONObject prefill) { super(a); this.id = id; }

    @Override public String title() { return id == null ? "New · Customer Order / Schedule" : "Edit · Customer Order"; }
    @Override public String subtitle() { return id == null ? "Customer, Part, weights and sources come from Masters" : "Controlled fields · flow change rule applies"; }

    @Override
    public View build() {
        newPage();
        if (id != null) return buildEdit();
        List<Field> f = new ArrayList<>();
        f.add(Field.select("order_type", "Order Source", "PURCHASE_ORDER", "MONTHLY_SCHEDULE").labels("Customer Purchase Order", "Monthly Schedule · 6 Months").req().def("PURCHASE_ORDER"));
        f.add(Field.select("supply_flow", "Supply Chain Flow", SupSvc.FLOWS).labels(SupSvc.FLOW_LABELS).req().def(SupSvc.FSI_RM));
        f.add(Field.lookup("customer_id", "Customer", Lookups.customers()).req());
        f.add(Field.lookup("part_id", "Part Number", Lookups.parts()).req());
        f.add(Field.select("raw_material_detail_id", "Part Master Raw Material / Forging Source").req().hint("Select the Part first"));
        f.add(Field.lookup("responsible_employee_id", "Responsible Employee", Lookups.employees()));
        // Customer PO
        f.add(Field.text("customer_order_no", "Customer Order No."));
        f.add(Field.text("order_position", "PosNr / Position"));
        f.add(Field.number("order_qty_pcs", "Order Qty pcs").range(1, Double.NaN));
        f.add(Field.date("order_date", "Order Date").def(Ui.today()));
        f.add(Field.date("customer_delivery_date", "Delivery / Arrival Date").def(Ui.today()));
        // Monthly schedule
        LocalDate now = LocalDate.now();
        String[] monthIds = new String[12];
        for (int i = 0; i < 12; i++) monthIds[i] = String.valueOf(i + 1);
        f.add(Field.select("start_month", "Start Month", monthIds).labels(SupSvc.MONTHS).def(String.valueOf(now.getMonthValue())));
        String[] years = new String[8];
        for (int i = 0; i < 8; i++) years[i] = String.valueOf(now.getYear() - 1 + i);
        f.add(Field.select("start_year", "Start Year", years).def(String.valueOf(now.getYear())));
        f.add(Field.date("receipt_date", "Schedule Receipt Date").def(Ui.today()));
        f.add(Field.text("remarks", "Remarks"));
        f.add(Field.bool("rm_procurement_required", "RM Procurement").hint("RM Procurement Required").def(true));
        form = new FormView(a, f);
        add(form, 0);
        rawNote = Ui.text(a, "", 12, Ui.ORANGE, false);
        add(rawNote, 2);
        monthsBox = Ui.vbox(a);
        add(monthsBox, 6);
        checkText = Ui.text(a, "Select Customer and Part to see the stock / three-month demand check.", 12.5f, Ui.TEXT, false);
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "RM procurement check", 14, Ui.TEXT, true));
        card.addView(checkText);
        add(card, 10);
        Button save = Ui.primary(a, "Create Customer Order");
        add(save, 16);
        save.setOnClickListener(v -> create(save));
        form.onChange((key, value) -> {
            switch (key) {
                case "order_type": layoutType(); recheck(); break;
                case "customer_id": {
                    Field part = form.field("part_id");
                    String cid = form.str("customer_id");
                    part.lookup = cid.isEmpty() ? Lookups.parts() : Lookups.parts().where("&or=(customer_id.is.null,customer_id.eq." + cid + ")");
                    form.set("part_id", null);
                    recheck();
                    break;
                }
                case "part_id": loadRaw(); recheck(); break;
                case "start_month": case "start_year": buildMonths(); recheck(); break;
                case "supply_flow": case "order_qty_pcs": case "customer_delivery_date": case "raw_material_detail_id": recheck(); break;
                default: break;
            }
        });
        layoutType();
        return scroll;
    }

    private boolean schedule() { return "MONTHLY_SCHEDULE".equals(form.str("order_type")); }

    private void layoutType() {
        boolean sch = schedule();
        for (String k : new String[]{"customer_order_no", "order_position", "order_qty_pcs", "order_date", "customer_delivery_date"}) form.setVisible(k, !sch);
        for (String k : new String[]{"start_month", "start_year", "receipt_date"}) form.setVisible(k, sch);
        monthsBox.setVisibility(sch ? View.VISIBLE : View.GONE);
        if (sch) buildMonths();
    }

    private LocalDate startMonth() {
        int m = 1, y = LocalDate.now().getYear();
        try { m = Integer.parseInt(form.str("start_month")); y = Integer.parseInt(form.str("start_year")); } catch (Exception ignored) { }
        return LocalDate.of(y, m, 1);
    }

    private void buildMonths() {
        if (monthsBox == null) return;
        monthsBox.removeAllViews();
        monthsBox.addView(Ui.label(a, "Six-month schedule · quantity per month"));
        List<Field> f = new ArrayList<>();
        LocalDate start = startMonth();
        for (int i = 0; i < 6; i++) {
            LocalDate d = start.plusMonths(i);
            String name = SupSvc.MONTHS[d.getMonthValue() - 1].substring(0, 3) + " " + d.getYear();
            String ref = partNumber.isEmpty() ? "Select Part" : String.format(java.util.Locale.ROOT, "%s_%02d_%04d", partNumber, d.getMonthValue(), d.getYear());
            f.add(Field.number("q" + i, name + " · Qty pcs").range(0, Double.NaN).hint(ref));
            f.add(Field.date("d" + i, name + " · Delivery").def(d.toString()));
        }
        months = new FormView(a, f);
        months.onChange((k, v) -> { if (k.startsWith("q")) recheck(); });
        monthsBox.addView(months);
    }

    private void loadRaw() {
        String partId = form.str("part_id");
        Field raw = form.field("raw_material_detail_id");
        raw.options = new String[0];
        raw.optionLabels = new String[0];
        form.set("raw_material_detail_id", null);
        rawRows.clear();
        rawNote.setText("");
        partNumber = "";
        if (partId.isEmpty()) return;
        rawNote.setText("Loading raw material sources…");
        Api.async(() -> {
            List<JSONObject> rows = svc.rawMaterialOptions(partId);
            Set<String> partyIds = new HashSet<>(), gradeIds = new HashSet<>(), partIds = new HashSet<>();
            for (JSONObject r : rows) { partyIds.add(SupSvc.s(r, "supplier_id")); gradeIds.add(SupSvc.s(r, "material_grade_id")); partIds.add(SupSvc.s(r, "source_part_id")); }
            partIds.add(partId);
            Map<String, JSONObject> parties = svc.byIds("parties", "id,party_code,party_name,city,state,country", partyIds);
            Map<String, JSONObject> grades = svc.byIds("material_grades", "id,grade_code", gradeIds);
            Map<String, JSONObject> parts = svc.byIds("parts", "id,part_number,fsi_part_number", partIds);
            List<String[]> out = new ArrayList<>();
            StringBuilder errors = new StringBuilder();
            for (JSONObject r : rows) {
                if (!SupSvc.s(r, "_source_error").isEmpty()) errors.append(SupSvc.s(r, "_source_error")).append('\n');
                double gross = SupSvc.num(r, "gross_weight_kg");
                if (gross == 0) gross = SupSvc.num(r, "input_weight_kg");
                if (gross == 0) gross = SupSvc.num(r, "forging_weight_kg");
                JSONObject g = grades.get(SupSvc.s(r, "material_grade_id"));
                JSONObject src = parts.get(SupSvc.s(r, "source_part_id"));
                String label = SupSvc.first(SupSvc.s(r, "material_section_name"), "Raw Material") + " · Grade " + SupSvc.first(SupSvc.s(g, "grade_code"), "-")
                    + " · " + SupSvc.partyLabel(parties.get(SupSvc.s(r, "supplier_id"))) + " · Gross " + String.format(java.util.Locale.US, "%.3f", gross) + " kg/pc · "
                    + SupSvc.first(SupSvc.s(r, "section_size"), "-") + (src != null ? " · Source " + SupSvc.first(SupSvc.s(src, "part_number"), SupSvc.s(src, "fsi_part_number")) : "")
                    + " · Lead " + (int) SupSvc.num(r, "lead_time_days") + "d";
                out.add(new String[]{SupSvc.s(r, "id"), label});
            }
            JSONObject me = parts.get(partId);
            return new Object[]{rows, out, errors.toString(), me == null ? "" : SupSvc.s(me, "part_number")};
        }, (res, err) -> {
            if (!partId.equals(form.str("part_id"))) return;
            if (err != null) { rawNote.setText(Api.message(err)); return; }
            @SuppressWarnings("unchecked") List<JSONObject> rows = (List<JSONObject>) res[0];
            @SuppressWarnings("unchecked") List<String[]> out = (List<String[]>) res[1];
            for (JSONObject r : rows) rawRows.put(SupSvc.s(r, "id"), r);
            String[] ids = new String[out.size()], labels = new String[out.size()];
            for (int i = 0; i < out.size(); i++) { ids[i] = out.get(i)[0]; labels[i] = out.get(i)[1]; }
            raw.options = ids;
            raw.optionLabels = labels;
            partNumber = (String) res[3];
            String errors = (String) res[2];
            rawNote.setText(out.isEmpty() ? "Part Master E - Raw Material Details requires an active raw material / forging source and gross/input weight." : errors.trim());
            if (ids.length == 1) form.set("raw_material_detail_id", ids[0]);
            if (schedule()) buildMonths();
        });
    }

    private double gross() {
        JSONObject r = rawRows.get(form.str("raw_material_detail_id"));
        double g = SupSvc.num(r, "gross_weight_kg");
        if (g == 0) g = SupSvc.num(r, "input_weight_kg");
        if (g == 0) g = SupSvc.num(r, "forging_weight_kg");
        return g;
    }

    private double threeMonthQty() {
        double sum = 0;
        for (int i = 0; i < 3 && months != null; i++) { Double q = months.num("q" + i); sum += q == null ? 0 : q; }
        return sum;
    }

    private void recheck() {
        if (checkText == null) return;
        final int mySeq = ++seq;
        String partId = form.str("part_id"), customerId = form.str("customer_id");
        boolean sch = schedule();
        Double q = form.num("order_qty_pcs");
        double qty = sch ? threeMonthQty() : (q == null ? 0 : q);
        String anchor = sch ? startMonth().toString() : form.str("customer_delivery_date");
        String flow = form.str("supply_flow");
        if (partId.isEmpty()) { check = null; checkText.setText("Select Customer and Part to see the stock / three-month demand check."); return; }
        checkText.setText("Checking stock and three-month demand…");
        Api.async(() -> svc.procurementCheck(partId, customerId, anchor, qty, null), (c, err) -> {
            if (mySeq != seq) return;
            if (err != null) { checkText.setText(Api.message(err)); check = null; return; }
            check = c;
            double gross = gross();
            if (!SupSvc.requiresRm(flow)) {
                checkText.setText("Direct Forging flow · FSI RM Procurement / Receipt stages are bypassed.\nEstimated RM at Forging Supplier: " + f3((sch ? threeMonthQty() : qty) * gross) + " kg (reference only)");
                return;
            }
            boolean allowed = c.optBoolean("rm_procurement_allowed");
            StringBuilder b = new StringBuilder();
            b.append("System Available Qty: ").append(f0(c.optDouble("available_stock_pcs", 0))).append(" pcs\n");
            b.append(sch ? "3-Month Schedule: " : "3-Month Schedule / Demand: ").append(f0(c.optDouble("three_month_schedule_pcs", 0))).append(" pcs\n");
            b.append(sch ? "3-Month Shortage: " : "Shortage: ").append(f0(c.optDouble("shortage_pcs", 0))).append(" pcs");
            if (!sch) b.append("\nRM Reference: ").append(f3(qty * gross)).append(" kg");
            if (!allowed) {
                b.append("\n\nAvailable system quantity covers the rolling three-month demand. RM Procurement is not required (it cannot be raised until a shortage exists).");
                form.set("rm_procurement_required", false);
            }
            checkText.setText(b.toString());
        });
    }

    private void create(Button save) {
        String problem = form.validate();
        if (problem == null && form.str("raw_material_detail_id").isEmpty()) problem = "Part Master Raw Material / Forging Source is required.";
        if (problem == null && gross() <= 0) problem = "The selected raw material source has no gross / input / forging weight in Part Master.";
        boolean sch = schedule();
        if (problem == null && !sch) {
            if (form.str("customer_order_no").isEmpty()) problem = "Customer Order No. is required.";
            else if (form.str("order_position").isEmpty()) problem = "PosNr / Position is required.";
            else if (form.num("order_qty_pcs") == null || form.num("order_qty_pcs") < 1) problem = "Order Qty pcs must be at least 1.";
        }
        if (problem == null && sch) {
            String mp = months == null ? null : months.validate();
            if (mp != null) problem = mp;
            else if (months == null || totalMonths() <= 0) problem = "Enter quantity for at least one of the six months.";
        }
        if (problem != null) { a.toast(problem); return; }
        JSONObject raw = rawRows.get(form.str("raw_material_detail_id"));
        double gross = gross();
        String flow = form.str("supply_flow");
        boolean requested = SupSvc.requiresRm(flow) && form.bool("rm_procurement_required");
        String partId = form.str("part_id"), customerId = form.str("customer_id");
        String remarks = form.str("remarks");
        List<JSONObject> payloads = new ArrayList<>();
        try {
            JSONObject base = new JSONObject().put("customer_id", customerId).put("part_id", partId)
                .put("forging_supplier_id", SupSvc.raw(raw, "supplier_id")).put("raw_material_detail_id", form.str("raw_material_detail_id"))
                .put("gross_weight_kg_snapshot", gross).put("status", "OPEN").put("remarks", SupSvc.n(remarks)).put("supply_flow", flow)
                .put("rm_procurement_required", requested).put("responsible_employee_id", SupSvc.n(form.str("responsible_employee_id")));
            if (!sch) {
                JSONObject p = SupSvc.copy(base);
                p.put("order_type", "PURCHASE_ORDER").put("customer_order_no", form.str("customer_order_no")).put("order_position", form.str("order_position"))
                    .put("order_date", SupSvc.n(form.str("order_date"))).put("customer_delivery_date", SupSvc.n(form.str("customer_delivery_date"))).put("order_qty_pcs", form.num("order_qty_pcs"));
                payloads.add(p);
            } else {
                LocalDate start = startMonth();
                for (int i = 0; i < 6; i++) {
                    Double q = months.num("q" + i);
                    if (q == null || q <= 0) continue;
                    LocalDate d = start.plusMonths(i);
                    JSONObject p = SupSvc.copy(base);
                    p.put("order_type", "MONTHLY_SCHEDULE").put("order_position", String.format(java.util.Locale.ROOT, "%02d-%d", d.getMonthValue(), d.getYear()))
                        .put("schedule_month", d.toString()).put("order_date", SupSvc.n(form.str("receipt_date")))
                        .put("customer_delivery_date", SupSvc.first(months.str("d" + i), d.toString())).put("order_qty_pcs", q);
                    payloads.add(p);
                }
            }
        } catch (Exception e) { showError(e); return; }
        final double proposed = sch ? threeMonthQty() : form.num("order_qty_pcs");
        final String anchor = sch ? startMonth().toString() : form.str("customer_delivery_date");
        busy(save, "Saving…", () -> {
            // procurement check as shown on the screen (website passes it as _procurement_check)
            JSONObject c = svc.procurementCheck(partId, customerId, anchor, proposed, null);
            List<JSONObject> saved = new ArrayList<>();
            for (JSONObject p : payloads) {
                try {
                    saved.add(svc.createCustomerOrder(p, c));
                } catch (Exception e) {
                    if (saved.isEmpty()) throw e;
                    throw new SupSvc.Rule(saved.size() + " schedule record(s) were created, then: " + Api.message(e));
                }
            }
            Lookups.invalidate();
            return saved;
        }, (saved, err) -> {
            if (sch) {
                a.toast(saved.size() + " monthly schedule record(s) created.");
                a.back();
            } else {
                JSONObject o = saved.get(0);
                a.toast("Customer Order " + SupSvc.s(o, "master_reference_no") + " / Pos " + SupSvc.s(o, "order_position") + " created.");
                Module m = Catalog.get("customer_orders");
                if (m != null) a.replaceTop(new RecordScreen(a, m, SupSvc.s(o, "id"))); else a.back();
            }
        });
    }

    private double totalMonths() {
        double t = 0;
        for (int i = 0; i < 6; i++) { Double q = months.num("q" + i); t += q == null ? 0 : q; }
        return t;
    }

    // ------------------------------------------------------------------ edit panel
    private View buildEdit() {
        List<Field> f = new ArrayList<>();
        f.add(Field.select("supply_flow", "Supply Chain Flow", SupSvc.FLOWS).labels(SupSvc.FLOW_LABELS).req());
        f.add(Field.text("customer_order_no", "Customer Order No."));
        f.add(Field.text("order_position", "PosNr / Position"));
        f.add(Field.date("order_date", "Order Date"));
        f.add(Field.date("customer_delivery_date", "Delivery Date"));
        f.add(Field.number("order_qty_pcs", "Order Qty pcs").range(0, Double.NaN).req());
        f.add(Field.select("status", "Status", "OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED").req());
        f.add(Field.text("remarks", "Remarks"));
        form = new FormView(a, f);
        form.setVisibility(View.INVISIBLE);
        add(form, 0);
        TextView info = Ui.text(a, "The Supply Chain Flow cannot be changed after linked procurement / forging / production / dispatch transactions have started. Stock snapshots and the RM procurement decision are recalculated on save.", 12, Ui.MUTED, false);
        add(info, 8);
        Button save = Ui.primary(a, "Save Edited Entry");
        add(save, 16);
        Api.async(() -> svc.get("supply_customer_orders", id), (row, err) -> {
            if (err != null || SupSvc.empty(row)) { page.addView(error(err != null ? err : new Exception("Customer Order was not found."), this::reload), 0); return; }
            try {
                row.put("supply_flow", SupSvc.flowFor(row));
                row.put("remarks", SupSvc.n(SupSvc.cleanFlowRemarks(SupSvc.s(row, "remarks"))));
            } catch (Exception ignored) { }
            form.setAll(row);
            if (SupSvc.s(row, "status").isEmpty()) form.set("status", "OPEN");
            form.setVisibility(View.VISIBLE);
        });
        save.setOnClickListener(v -> {
            String problem = form.validate();
            if (problem != null) { a.toast(problem); return; }
            busy(save, "Saving…", () -> {
                JSONObject values = form.json();
                if (values.isNull("order_qty_pcs")) values.put("order_qty_pcs", 0);
                svc.updateCustomerOrder(id, values);
                svc.syncOrderStatus(id);
                return true;
            }, (ok, err) -> { a.toast("Supply Chain entry updated successfully."); a.back(); });
        });
        return scroll;
    }

    static JSONArray none() { return new JSONArray(); }
}
