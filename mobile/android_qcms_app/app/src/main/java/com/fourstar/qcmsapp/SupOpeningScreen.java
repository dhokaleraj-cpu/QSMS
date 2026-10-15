package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Supply Chain Opening Stock add / edit (render_opening_stock + save_opening_stock). */
final class SupOpeningScreen extends SupBase {
    static final String[] LOCATIONS = {"FSI", "SUPPLIER", "VENDOR"};
    static final String[] LOCATION_LABELS = {"At FSI (own plant)", "At Supplier", "At Vendor (forger / caster / OSP)"};

    private final String id;
    private FormView form;
    private TextView supplierInfo;
    private final Map<String, JSONObject> raws = new HashMap<>();
    private String primaryGrade = "";
    private JSONObject record;

    SupOpeningScreen(MainActivity a, String id) { super(a); this.id = id; }

    @Override public String title() { return id == null ? "New · Opening Stock" : "Edit · Opening Stock"; }
    @Override public String subtitle() { return "Existing stock by Part and current process stage"; }

    private static Field.Lookup holders() {
        return new Field.Lookup("parties", "id,party_code,party_name,city,state,party_types", "&status=eq.ACTIVE&or=(party_types.is.null,party_types.not.eq.%7BCUSTOMER%7D)", "party_name.asc", Lookups.PARTY);
    }

    @Override
    public View build() {
        newPage();
        List<Field> f = new ArrayList<>();
        if (id == null) {
            f.add(Field.lookup("part_id", "Part Number", Lookups.parts()).req());
            f.add(Field.select("stage", "Supply Chain Stage", SupSvc.OPENING_STAGES).labels(SupSvc.OPENING_STAGE_LABELS).req().def("FINISHED_GOODS"));
            f.add(Field.select("material_grade_id", "Material Grade").hint("Not Applicable / Unknown when empty"));
            f.add(Field.select("raw_material_detail_id", "Raw Material / Supplier Section").hint("Not Linked when empty"));
            f.add(Field.select("stock_location", "Stock Location", LOCATIONS).labels(LOCATION_LABELS).req().def("FSI"));
            f.add(Field.lookup("location_party_id", "Supplier / Vendor holding the stock", holders()).hint("Mandatory when the stock is at a Supplier or Vendor"));
        } else {
            f.add(Field.select("stage", "Stage", SupSvc.OPENING_STAGES).labels(SupSvc.OPENING_STAGE_LABELS).req());
        }
        f.add(Field.text("lot_reference", "Opening Lot / Reference"));
        f.add(Field.text("heat_number", "Heat Number"));
        f.add(Field.text("heat_code", "Heat Code"));
        f.add(Field.number("quantity_pcs", "Opening Qty (pcs)").range(0, Double.NaN).def(0.0));
        f.add(Field.number("available_quantity_pcs", "Available Qty (pcs)").range(0, Double.NaN).hint("Quantity currently available at the stage (blank = opening qty)"));
        f.add(Field.number("quantity_kg", "Opening Qty (kg)").range(0, Double.NaN).def(0.0));
        if (id != null) f.add(Field.select("status", "Status", "ACTIVE", "CONSUMED", "INACTIVE").req());
        f.add(Field.text("remarks", "Remarks"));
        form = new FormView(a, f);
        add(form, 0);
        supplierInfo = Ui.text(a, "", 12, Ui.MUTED, false);
        add(supplierInfo, 4);
        Button save = Ui.primary(a, id == null ? "Add Opening Stock" : "Save Opening Stock Changes");
        add(save, 16);
        save.setOnClickListener(v -> save(save));
        if (id == null) {
            form.onChange((k, v) -> {
                if (k.equals("part_id")) loadPart();
                if (k.equals("raw_material_detail_id")) showSupplier();
                if (k.equals("stock_location")) form.setVisible("location_party_id", !"FSI".equals(form.str("stock_location")));
            });
            form.setVisible("location_party_id", false);
        } else {
            form.setVisibility(View.INVISIBLE);
            Api.async(() -> svc.get("supply_opening_stock", id), (row, err) -> {
                if (err != null || SupSvc.empty(row)) { page.addView(error(err != null ? err : new Exception("Opening Stock record not found."), this::reload), 0); return; }
                record = row;
                form.setAll(row);
                if (SupSvc.s(row, "status").isEmpty()) form.set("status", "ACTIVE");
                form.setVisibility(View.VISIBLE);
            });
        }
        return scroll;
    }

    private void loadPart() {
        String partId = form.str("part_id");
        Field grade = form.field("material_grade_id"), raw = form.field("raw_material_detail_id");
        grade.options = new String[0]; raw.options = new String[0];
        form.set("material_grade_id", null); form.set("raw_material_detail_id", null);
        raws.clear(); primaryGrade = "";
        supplierInfo.setText("");
        if (partId.isEmpty()) return;
        Api.async(() -> {
            JSONObject part = svc.get("parts", partId);
            List<String> gradeIds = new ArrayList<>();
            for (JSONObject l : svc.live("part_material_grade_links?select=material_grade_id&part_id=eq." + partId + "&status=eq.ACTIVE&order=created_at.asc&limit=5000"))
                if (!SupSvc.s(l, "material_grade_id").isEmpty() && !gradeIds.contains(SupSvc.s(l, "material_grade_id"))) gradeIds.add(SupSvc.s(l, "material_grade_id"));
            String primary = SupSvc.s(part, "material_grade_id");
            if (!primary.isEmpty() && !gradeIds.contains(primary)) gradeIds.add(0, primary);
            List<JSONObject> rows = svc.rawMaterialOptions(partId);
            Set<String> gset = new HashSet<>(gradeIds), pset = new HashSet<>();
            for (JSONObject r : rows) { gset.add(SupSvc.s(r, "material_grade_id")); pset.add(SupSvc.s(r, "supplier_id")); pset.add(SupSvc.s(r, "source_part_id")); }
            Map<String, JSONObject> grades = svc.byIds("material_grades", "id,grade_code", gset);
            Map<String, JSONObject> parties = svc.byIds("parties", "id,party_code,party_name,city,state,country", pset);
            Map<String, JSONObject> srcParts = svc.byIds("parts", "id,part_number,fsi_part_number", pset);
            List<String> gIds = new ArrayList<>(), gLabels = new ArrayList<>();
            for (String g : gradeIds) if (grades.containsKey(g)) { gIds.add(g); gLabels.add(SupSvc.first(SupSvc.s(grades.get(g), "grade_code"), g)); }
            List<String> rIds = new ArrayList<>(), rLabels = new ArrayList<>();
            for (JSONObject r : rows) {
                rIds.add(SupSvc.s(r, "id"));
                JSONObject src = srcParts.get(SupSvc.s(r, "source_part_id"));
                rLabels.add(SupSvc.first(SupSvc.s(r, "material_section_name"), "Raw Material") + " · Grade " + SupSvc.first(SupSvc.s(grades.get(SupSvc.s(r, "material_grade_id")), "grade_code"), "-")
                    + " · " + SupSvc.first(SupSvc.s(parties.get(SupSvc.s(r, "supplier_id")), "party_name"), "Supplier") + " · " + SupSvc.first(SupSvc.s(r, "section_size"), "-")
                    + (src != null ? " · Source " + SupSvc.first(SupSvc.s(src, "part_number"), SupSvc.s(src, "fsi_part_number")) : ""));
                r.put("_supplier_label", SupSvc.partyLabel(parties.get(SupSvc.s(r, "supplier_id"))));
            }
            return new Object[]{gIds, gLabels, rIds, rLabels, rows, primary};
        }, (res, err) -> {
            if (!partId.equals(form.str("part_id"))) return;
            if (err != null) { supplierInfo.setText(Api.message(err)); return; }
            @SuppressWarnings("unchecked") List<String> gIds = (List<String>) res[0];
            @SuppressWarnings("unchecked") List<String> gLabels = (List<String>) res[1];
            @SuppressWarnings("unchecked") List<String> rIds = (List<String>) res[2];
            @SuppressWarnings("unchecked") List<String> rLabels = (List<String>) res[3];
            @SuppressWarnings("unchecked") List<JSONObject> rows = (List<JSONObject>) res[4];
            grade.options = gIds.toArray(new String[0]); grade.optionLabels = gLabels.toArray(new String[0]);
            raw.options = rIds.toArray(new String[0]); raw.optionLabels = rLabels.toArray(new String[0]);
            for (JSONObject r : rows) raws.put(SupSvc.s(r, "id"), r);
            primaryGrade = (String) res[5];
        });
    }

    private void showSupplier() {
        JSONObject r = raws.get(form.str("raw_material_detail_id"));
        supplierInfo.setText(r == null ? "" : "Supplier: " + SupSvc.s(r, "_supplier_label"));
    }

    private void save(Button save) {
        String problem = form.validate();
        if (problem != null) { a.toast(problem); return; }
        busy(save, "Saving…", () -> {
            JSONObject v = form.json();
            JSONObject p;
            if (id == null) {
                JSONObject raw = raws.get(form.str("raw_material_detail_id"));
                String grade = SupSvc.first(form.str("material_grade_id"), SupSvc.s(raw, "material_grade_id"), primaryGrade);
                p = new JSONObject().put("part_id", form.str("part_id")).put("stage", form.str("stage")).put("material_grade_id", SupSvc.n(grade))
                    .put("raw_material_detail_id", SupSvc.n(form.str("raw_material_detail_id"))).put("supplier_id", SupSvc.n(SupSvc.s(raw, "supplier_id")))
                    .put("stock_location", form.str("stock_location")).put("location_party_id", SupSvc.n(form.str("location_party_id"))).put("status", "ACTIVE");
            } else {
                p = new JSONObject();
                for (String k : new String[]{"part_id", "material_grade_id", "raw_material_detail_id", "supplier_id", "location_party_id"}) p.put(k, SupSvc.raw(record, k));
                p.put("stock_location", SupSvc.first(SupSvc.s(record, "stock_location"), "FSI")).put("stage", form.str("stage")).put("status", form.str("status"));
            }
            p.put("lot_reference", SupSvc.raw(v, "lot_reference")).put("heat_number", SupSvc.raw(v, "heat_number")).put("heat_code", SupSvc.raw(v, "heat_code"))
                .put("quantity_pcs", SupSvc.num(v, "quantity_pcs")).put("quantity_kg", SupSvc.num(v, "quantity_kg")).put("remarks", SupSvc.raw(v, "remarks"))
                .put("available_quantity_pcs", v.isNull("available_quantity_pcs") ? JSONObject.NULL : (Object) SupSvc.num(v, "available_quantity_pcs"));
            return svc.saveOpeningStock(p, id);
        }, (saved, err) -> {
            a.toast(id == null ? "Opening Stock added successfully." : "Opening Stock updated successfully.");
            a.back();
        });
    }
}
