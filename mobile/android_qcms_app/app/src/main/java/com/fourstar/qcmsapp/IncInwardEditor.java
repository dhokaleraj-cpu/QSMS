package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

/**
 * Native Material Inward · Entry (app_pages/material_inward.render_entry): accepted RMTC steel source, accepted /
 * rejected / on-hold pieces converted to steel with the input weight, available heat steel check, disposition rules,
 * INWARD numbering and a plain insert / update of inward_lots exactly like InwardService.save.
 */
final class IncInwardEditor extends Screen {
    private final String id;
    private final JSONObject prefill;
    private JSONObject existing;
    private List<JSONObject> acceptedAll = new ArrayList<>();
    private JSONObject source = new JSONObject();
    private String sourceId = "";
    private Map<String, JSONObject> parts;

    private FormView form;
    private LinearLayout sourceBox;
    private TextView sourcePick, calcNote;
    private Button save;
    private boolean saving = false;

    // figures of the current source
    private double inputWeight, availableForEntry;

    IncInwardEditor(MainActivity a, String id, JSONObject prefill) {
        super(a);
        this.id = id == null || id.isEmpty() ? null : id;
        this.prefill = prefill;
    }

    @Override public String title() { return id == null ? "New Material Inward" : "Edit Material Inward"; }
    @Override public String subtitle() { return "Steel quantity and production conversion · * required"; }
    @Override public int tab() { return Catalog.QUALITY; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONObject rec = id == null ? null : IncCalc.one(api, "inward_lots?select=*&id=eq." + Api.enc(id));
            if (id != null && rec == null) throw new Api.ApiException(404, "Material Inward record not found.");
            List<JSONObject> acc = IncCalc.list(api.rows("v_qsms_accepted_rmtc_parts?select=*&order=certificate_date.desc&limit=3000"));
            Map<String, JSONObject> p = IncRmtcData.parts(api);
            Lookups.rows(api, Lookups.employees());
            Lookups.rows(api, IncCalc.employeeLookup("RAW_MATERIAL_INSPECTION"));
            return new Object[]{rec, acc, p};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            existing = (JSONObject) res[0];
            @SuppressWarnings("unchecked") List<JSONObject> acc = (List<JSONObject>) res[1];
            @SuppressWarnings("unchecked") Map<String, JSONObject> p = (Map<String, JSONObject>) res[2];
            acceptedAll = acc; parts = p;
            render();
        });
        return scroll;
    }

    private static double available(JSONObject r) {
        return IncCalc.first(r, "available_steel_quantity_kg", "available_quantity");
    }

    private String sourceLabel(JSONObject r) {
        JSONObject part = parts.get(Lookups.j(r, "part_id"));
        String fsi = IncCalc.firstText(part == null ? "" : Lookups.j(part, "fsi_part_number"), Lookups.j(r, "fsi_part_number"));
        return Lookups.j(r, "rmtc_number") + " · Supplier RMTC " + IncCalc.firstText(Lookups.j(r, "certificate_reference"), "-") + " · " + Lookups.j(r, "part_number")
            + " · FSI " + IncCalc.firstText(fsi, "-") + " · " + Lookups.j(r, "supplier_name") + " · Heat " + Lookups.j(r, "heat_number")
            + " · Heat Code " + IncCalc.firstText(Lookups.j(r, "heat_code"), "-") + " · RMTC balance " + IncCalc.kg(available(r));
    }

    private List<JSONObject> selectable() {
        if (existing != null) return acceptedAll;
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject r : acceptedAll) if (available(r) > 0) out.add(r);
        return out;
    }

    private void render() {
        boolean isNew = existing == null;
        if (existing != null && !Lookups.j(existing, "supply_rm_purchase_order_id").isEmpty()) {
            add(Ui.chip(a, "Supply Chain link · RM Procurement linked (kept unchanged; the RM Receipt mirror is refreshed on save)", "teal"), 0);
        } else if (isNew) {
            add(Ui.text(a, "Standalone Material Inward · use 'Link to RM Purchase Order' on the saved record to link it to Supply Chain.", 11.5f, Ui.MUTED, false), 0);
        }

        add(Ui.label(a, "B · ACCEPTED RMTC STEEL SOURCE"), 10);
        add(Ui.text(a, "Approved RMTCs remain reusable for the same or another approved covered Part Number until the global RMTC steel balance reaches zero.", 11.5f, Ui.MUTED, false), 2);
        sourcePick = Ui.text(a, "— Select accepted RMTC steel source — *", 14, Ui.MUTED, false);
        sourcePick.setPadding(dp(12), dp(12), dp(12), dp(12));
        sourcePick.setBackground(Ui.round(isNew ? android.graphics.Color.WHITE : android.graphics.Color.parseColor("#F3F7F7"), Ui.LINE_STRONG, 1, 10, a));
        add(sourcePick, 4);
        if (isNew) sourcePick.setOnClickListener(v -> pickSource());
        sourceBox = Ui.vbox(a);
        add(sourceBox, 4);

        add(Ui.label(a, "C · INWARD AND PRODUCTION QUANTITY"), 14);
        List<Field> f = new ArrayList<>(Arrays.asList(
            Field.text("inward_number", "Inward Number").hint("Auto on save"),
            Field.date("inward_date", "Inward Date").req().def(Ui.today()),
            Field.text("grn_number", "GRN Number").req(),
            Field.text("invoice_number", "Supplier Invoice Number"),
            Field.number("accepted_production_quantity_pcs", "Accepted Production Quantity (pcs)").range(0, Double.MAX_VALUE),
            Field.number("rejected_production_quantity_pcs", "Rejected Production Quantity (pcs)").range(0, Double.MAX_VALUE),
            Field.number("hold_production_quantity_pcs", "On Hold Production Quantity (pcs)").range(0, Double.MAX_VALUE),
            Field.info("total_pcs", "Total Production Quantity (pcs)"),
            Field.info("accepted_steel", "Accepted Steel Quantity (kg)"),
            Field.info("rejected_steel", "Rejected Steel Quantity (kg)"),
            Field.info("hold_steel", "On Hold Steel Quantity (kg)"),
            Field.info("total_steel", "Total Steel Quantity (kg)"),
            Field.info("input_weight", "Input Weight (kg/part)"),
            Field.info("available_pcs", "Available Production from RMTC Balance (pcs)"),
            Field.info("available_steel", "Heat Steel Available Before Entry (kg)"),
            Field.info("balance_steel", "Heat Steel Balance After Entry (kg)"),
            Field.select("receipt_disposition", "Receipt Disposition", IncCalc.DISPOSITIONS).req().def("PENDING"),
            Field.info("quality_gate", "Quality Gate"),
            Field.info("metlab_status", "MetLAB Status"),
            Field.info("dim_status", "Dimensional Status"),
            Field.lookup("prepared_by_employee_id", "Prepared By", Lookups.employees()).req(),
            Field.lookup("validated_by_employee_id", "Validated By", IncCalc.employeeLookup("RAW_MATERIAL_INSPECTION")),
            Field.text("reserve_reason", "Hold / Reserve / Rejection Reason"),
            Field.area("remarks", "Remarks")));
        form = new FormView(a, f);
        add(form, 4);
        calcNote = Ui.text(a, "", 12.5f, Ui.MUTED, false);
        add(calcNote, 6);
        add(Ui.text(a, "GRN / invoice / supporting documents are uploaded on the saved record (Upload actions).", 11.5f, Ui.MUTED, false), 4);
        save = Ui.primary(a, "Save Material Inward");
        add(save, 16);
        save.setOnClickListener(v -> save());

        if (existing != null) {
            for (String k : new String[]{"inward_number", "inward_date", "grn_number", "invoice_number", "accepted_production_quantity_pcs",
                "rejected_production_quantity_pcs", "hold_production_quantity_pcs", "receipt_disposition", "prepared_by_employee_id",
                "validated_by_employee_id", "reserve_reason", "remarks"}) if (existing.has(k) && !existing.isNull(k)) form.set(k, existing.opt(k));
            if (Lookups.j(existing, "receipt_disposition").isEmpty()) form.set("receipt_disposition", "PENDING");
            sourceId = Lookups.j(existing, "rmtc_part_approval_id");
            for (JSONObject r : acceptedAll) if (sourceId.equals(Lookups.j(r, "rmtc_part_approval_id"))) source = r;
        } else {
            if (!api.employeeId.isEmpty()) form.set("prepared_by_employee_id", api.employeeId);
            String pre = prefill == null ? "" : Lookups.j(prefill, "rmtc_part_approval_id");
            for (JSONObject r : selectable()) if (!pre.isEmpty() && pre.equals(Lookups.j(r, "rmtc_part_approval_id"))) { source = r; sourceId = pre; }
        }
        String gate = existing == null ? "" : Lookups.j(existing, "quality_disposition");
        form.set("quality_gate", Ui.pretty(IncCalc.firstText(gate, "PENDING")));
        form.set("metlab_status", Ui.pretty(IncCalc.firstText(existing == null ? "" : Lookups.j(existing, "metallurgical_status"), "PENDING")));
        form.set("dim_status", Ui.pretty(IncCalc.firstText(existing == null ? "" : Lookups.j(existing, "dimensional_status"), "PENDING")));
        form.onChange((k, v) -> { if (k.endsWith("_production_quantity_pcs")) recalc(); });
        showSource();
    }

    private void pickSource() {
        List<JSONObject> rows = selectable();
        if (rows.isEmpty()) { a.toast("No accepted RMTC steel source with available steel exists."); return; }
        List<String> ids = new ArrayList<>(), names = new ArrayList<>();
        for (JSONObject r : rows) { ids.add(Lookups.j(r, "rmtc_part_approval_id")); names.add(sourceLabel(r)); }
        form.choose("RMTC / Part / Supplier / Available Steel", ids, names, pick -> {
            sourceId = pick;
            for (JSONObject r : rows) if (pick.equals(Lookups.j(r, "rmtc_part_approval_id"))) source = r;
            showSource();
        });
    }

    private void showSource() {
        sourceBox.removeAllViews();
        double ew = existing == null ? 0 : IncCalc.f(existing.opt("input_weight_kg"));
        inputWeight = ew != 0 ? ew : IncCalc.first(source, "source_input_weight_kg", "input_weight_kg", "gross_weight_kg", "forging_weight_kg");
        double availableSteel = IncCalc.first(source, "available_steel_for_selected_entry_kg", "available_steel_quantity_kg", "available_quantity");
        double existingSteel = existing == null ? 0 : IncCalc.first(existing, "required_steel_quantity_kg", "steel_quantity_kg", "quantity_received");
        availableForEntry = availableSteel + existingSteel;
        if (sourceId.isEmpty()) { sourcePick.setText("— Select accepted RMTC steel source — *"); sourcePick.setTextColor(Ui.MUTED); recalc(); return; }
        if (source.length() == 0) {
            sourcePick.setText("Existing linked RMTC Part · " + sourceId);
            sourcePick.setTextColor(Ui.TEXT);
            sourceBox.addView(Ui.text(a, "The linked RMTC part is no longer in the accepted steel source list; the current heat balance cannot be shown.", 12, Ui.AMBER_FG, false));
            recalc();
            return;
        }
        sourcePick.setText(sourceLabel(source));
        sourcePick.setTextColor(Ui.TEXT);
        LinearLayout card = Ui.card(a);
        JSONObject part = parts.get(Lookups.j(source, "part_id"));
        card.addView(Ui.pair(a, "Supplier", Lookups.j(source, "supplier_name") + (Lookups.j(source, "forging_route").isEmpty() ? "" : " · " + Lookups.j(source, "forging_route"))));
        card.addView(Ui.pair(a, "Global Heat Steel", IncCalc.kg(IncCalc.f(source.opt("rmtc_steel_quantity_kg"))) + " · Committed " + IncCalc.kg(IncCalc.f(source.opt("heat_committed_steel_quantity_kg")))));
        card.addView(Ui.pair(a, "Reusable Production", Ui.num(inputWeight > 0 ? availableForEntry / inputWeight : 0, 0) + " pcs"));
        card.addView(Ui.pair(a, "RMTC Balance", IncCalc.kg(availableForEntry)));
        card.addView(Ui.pair(a, "Part Number", Lookups.j(source, "part_number")));
        card.addView(Ui.pair(a, "FSI Part Number", part == null ? "" : Lookups.j(part, "fsi_part_number")));
        card.addView(Ui.pair(a, "Part Description", Lookups.j(source, "part_name")));
        card.addView(Ui.pair(a, "Steel Mill", Lookups.j(source, "steel_mill_name")));
        card.addView(Ui.pair(a, "Material Grade", Lookups.j(source, "material_grade")));
        card.addView(Ui.pair(a, "Heat Number", Lookups.j(source, "heat_number")));
        card.addView(Ui.pair(a, "Internal Heat Code", Lookups.j(source, "heat_code")));
        card.addView(Ui.pair(a, "Section", Lookups.j(source, "section_size")));
        card.addView(Ui.pair(a, "RMTC Decision", Ui.pretty(Lookups.j(source, "disposition"))));
        sourceBox.addView(card);
        recalc();
    }

    private double pcs(String k) { return IncCalc.f(form.num(k)); }

    private boolean invalidQuantity() {
        double total = pcs("accepted_production_quantity_pcs") + pcs("rejected_production_quantity_pcs") + pcs("hold_production_quantity_pcs");
        return IncCalc.round(total * inputWeight, 3) > availableForEntry + 0.001;
    }

    private void recalc() {
        double acc = pcs("accepted_production_quantity_pcs"), rej = pcs("rejected_production_quantity_pcs"), hold = pcs("hold_production_quantity_pcs");
        double total = acc + rej + hold;
        double required = IncCalc.round(total * inputWeight, 3);
        form.set("total_pcs", Ui.num(total, 3));
        form.set("accepted_steel", Ui.num(IncCalc.round(acc * inputWeight, 3), 3));
        form.set("rejected_steel", Ui.num(IncCalc.round(rej * inputWeight, 3), 3));
        form.set("hold_steel", Ui.num(IncCalc.round(hold * inputWeight, 3), 3));
        form.set("total_steel", Ui.num(required, 3));
        form.set("input_weight", Ui.num(inputWeight, 3));
        form.set("available_pcs", Ui.num(inputWeight > 0 ? availableForEntry / inputWeight : 0, 3));
        form.set("available_steel", Ui.num(availableForEntry, 3));
        double remaining = Math.max(availableForEntry - required, 0);
        form.set("balance_steel", Ui.num(remaining, 3));
        if (!sourceId.isEmpty() && required > availableForEntry + 0.001) {
            calcNote.setText("Total production steel " + IncCalc.kg(required) + " exceeds the Heat steel available before this entry " + IncCalc.kg(availableForEntry) + ". The after-entry balance cannot be negative.");
            calcNote.setTextColor(Ui.RED_FG);
        } else if (!sourceId.isEmpty() && total > 0 && inputWeight > 0) {
            calcNote.setText("Automatic conversion: " + Ui.num(total, 0) + " pcs × " + Ui.num(inputWeight, 3) + " kg = " + IncCalc.kg(required) + ". Heat balance after entry: " + IncCalc.kg(remaining) + ".");
            calcNote.setTextColor(Ui.GREEN_FG);
        } else {
            calcNote.setText("");
        }
    }

    private void save() {
        if (saving) return;
        String problem = form.validate();
        if (problem != null && !problem.startsWith("GRN") && !problem.startsWith("Prepared")) { a.toast(problem); return; }
        if (invalidQuantity()) { a.toast("Total production steel exceeds the Heat steel available before this entry."); return; }
        double acc = pcs("accepted_production_quantity_pcs"), rej = pcs("rejected_production_quantity_pcs"), hold = pcs("hold_production_quantity_pcs");
        double total = acc + rej + hold;
        String grn = form.str("grn_number"), prepared = form.str("prepared_by_employee_id"), disp = IncCalc.firstText(form.str("receipt_disposition"), "PENDING");
        String reason = form.str("reserve_reason");
        double accSteel = IncCalc.round(acc * inputWeight, 3), rejSteel = IncCalc.round(rej * inputWeight, 3), holdSteel = IncCalc.round(hold * inputWeight, 3);
        double required = IncCalc.round(total * inputWeight, 3);
        String msg = null;
        if (sourceId.isEmpty()) msg = "Select an Accepted or Accepted Under Reserve RMTC Part Number.";
        else if (grn.isEmpty() || total <= 0 || inputWeight <= 0 || prepared.isEmpty()) msg = "GRN, Production Quantity, Input Weight and Prepared By are mandatory.";
        else if (required > availableForEntry) msg = "Calculated steel quantity cannot exceed the available RMTC heat balance.";
        else if (disp.equals("REJECTED") && (acc > 0 || hold > 0 || rej <= 0)) msg = "Rejected disposition requires only Rejected Production Quantity.";
        else if (disp.equals("ON_HOLD") && hold <= 0) msg = "On Hold disposition requires On Hold Production Quantity.";
        else if ((disp.equals("ACCEPTED") || disp.equals("ACCEPTED_UNDER_RESERVE")) && acc <= 0) msg = "Accepted disposition requires Accepted Production Quantity.";
        else if ((disp.equals("ON_HOLD") || disp.equals("ACCEPTED_UNDER_RESERVE") || disp.equals("REJECTED")) && reason.isEmpty())
            msg = "Reason is mandatory for On Hold, Accepted Under Reserve or Rejected disposition.";
        if (msg != null) { a.toast(msg); return; }
        // source fields (fall back to the stored values when the source left the accepted list)
        JSONObject src = source.length() > 0 ? source : existing == null ? new JSONObject() : existing;
        final JSONObject payload = new JSONObject();
        try {
            payload.put("inward_number", form.str("inward_number"));
            payload.put("inward_date", IncCalc.firstText(form.str("inward_date"), Ui.today()));
            payload.put("grn_number", grn);
            payload.put("invoice_number", IncCalc.jt(form.str("invoice_number")));
            payload.put("rmtc_approval_id", IncCalc.jo(src, "rmtc_approval_id"));
            payload.put("rmtc_part_approval_id", sourceId);
            payload.put("part_id", IncCalc.jo(src, "part_id"));
            payload.put("supplier_id", IncCalc.jo(src, "supplier_id"));
            payload.put("supplier_source_detail_id", IncCalc.jo(src, "supplier_source_detail_id"));
            payload.put("heat_number", IncCalc.jo(src, "heat_number"));
            payload.put("heat_code", IncCalc.jo(src, "heat_code"));
            payload.put("steel_quantity_kg", required);
            payload.put("quantity_received", required);
            payload.put("production_quantity_pcs", total);
            payload.put("accepted_production_quantity_pcs", acc);
            payload.put("rejected_production_quantity_pcs", rej);
            payload.put("hold_production_quantity_pcs", hold);
            payload.put("input_weight_kg", inputWeight);
            payload.put("required_steel_quantity_kg", required);
            payload.put("accepted_steel_quantity_kg", accSteel);
            payload.put("rejected_steel_quantity_kg", rejSteel);
            payload.put("hold_steel_quantity_kg", holdSteel);
            payload.put("quantity_accepted", accSteel);
            payload.put("quantity_rejected", rejSteel);
            payload.put("metallurgical_status", existing == null ? "PENDING" : IncCalc.firstText(Lookups.j(existing, "metallurgical_status"), "PENDING"));
            payload.put("dimensional_status", existing == null ? "PENDING" : IncCalc.firstText(Lookups.j(existing, "dimensional_status"), "PENDING"));
            payload.put("receipt_disposition", disp);
            payload.put("reserve_reason", IncCalc.jt(reason));
            payload.put("prepared_by_employee_id", prepared);
            payload.put("validated_by_employee_id", IncCalc.jt(form.str("validated_by_employee_id")));
            payload.put("status", existing == null ? "HOLD_PENDING_INSPECTION" : IncCalc.firstText(Lookups.j(existing, "status"), "HOLD_PENDING_INSPECTION"));
            payload.put("remarks", IncCalc.jt(form.str("remarks")));
            // Supply Chain link fields are preserved (linking / unlinking is done from RM Receipts)
            payload.put("supply_customer_order_id", existing == null ? IncCalc.jo(prefill, "supply_customer_order_id") : IncCalc.jo(existing, "supply_customer_order_id"));
            payload.put("supply_rm_purchase_order_id", existing == null ? IncCalc.jo(prefill, "supply_rm_purchase_order_id") : IncCalc.jo(existing, "supply_rm_purchase_order_id"));
        } catch (Exception e) { a.toast(Api.message(e)); return; }
        saving = true;
        save.setEnabled(false);
        save.setText("Saving steel and production allocation…");
        Api.async(() -> {
            if (payload.optString("inward_number").trim().isEmpty())
                payload.put("inward_number", api.nextNumber("qsms_next_document_number", new JSONObject().put("p_sequence_code", "INWARD")));
            JSONObject saved = api.save("inward_lots", id, payload);
            String note = "";
            String po = Lookups.j(saved, "supply_rm_purchase_order_id");
            if (!po.isEmpty()) {
                // SupplyChainService.link_inward_to_rm_po keeps the RM Receipt mirror in step with the inward
                try {
                    JSONObject mirror = IncCalc.one(api, "supply_rm_receipts?select=id&inward_lot_id=eq." + saved.optString("id") + "&limit=1");
                    if (mirror != null) {
                        JSONObject rmtc = IncCalc.one(api, "rmtc_approvals?select=rmtc_number,certificate_date,certificate_quantity&id=eq." + Lookups.j(saved, "rmtc_approval_id"));
                        api.update("supply_rm_receipts", mirror.getString("id"), new JSONObject()
                            .put("receipt_number", IncCalc.jo(saved, "inward_number")).put("receipt_date", IncCalc.jo(saved, "inward_date"))
                            .put("heat_number", IncCalc.jo(saved, "heat_number")).put("heat_code", IncCalc.jo(saved, "heat_code"))
                            .put("received_qty_kg", IncCalc.first(saved, "steel_quantity_kg", "quantity_received"))
                            .put("supplier_challan", IncCalc.jo(saved, "grn_number"))
                            .put("rmtc_number", IncCalc.jo(rmtc, "rmtc_number")).put("rmtc_date", IncCalc.jo(rmtc, "certificate_date"))
                            .put("rmtc_qty_kg", IncCalc.f(rmtc == null ? null : rmtc.opt("certificate_quantity"))));
                    }
                } catch (Exception e) {
                    note = " The linked RM Receipt could not be refreshed: " + Api.message(e);
                }
            }
            Lookups.invalidate();
            return new Object[]{saved, note};
        }, (res, err) -> {
            saving = false;
            save.setEnabled(true);
            save.setText("Save Material Inward");
            if (err != null) { a.toast(Api.message(err)); return; }
            JSONObject saved = (JSONObject) res[0];
            a.toast("Material Inward " + Lookups.j(saved, "inward_number") + " saved successfully." + res[1]);
            Module m = Catalog.get("inward");
            if (id == null) a.replaceTop(new RecordScreen(a, m != null ? m : Catalog.adhoc("inward_lots"), saved.optString("id")));
            else a.back();
        });
    }

    @Override public boolean onBack() {
        if (form == null) return false;
        a.confirm("Leave without saving?", "Changes on this Material Inward are not saved.", "Leave", () -> a.back());
        return true;
    }
}
