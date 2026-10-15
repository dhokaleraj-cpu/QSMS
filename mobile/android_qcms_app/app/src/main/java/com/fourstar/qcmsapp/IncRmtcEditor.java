package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Native RMTC Entry · Header (rmtc_pages.render_entry): heat search with the global heat balance, covered parts,
 * approved raw-material source, certificate data, heat code, prepared by and microstructure titles, saved
 * atomically with rpc qsms_save_rmtc_header exactly like the website.
 */
final class IncRmtcEditor extends Screen {
    private final String id;
    private final JSONObject prefill;

    private JSONObject existing;
    private Map<String, JSONObject> parts;
    private final List<String> selectedParts = new ArrayList<>();
    private List<JSONObject> sources = new ArrayList<>();
    private List<JSONObject> mills = new ArrayList<>();
    private List<JSONObject> suppliers = new ArrayList<>();
    private JSONObject heatSummary = new JSONObject();
    private String canonicalHeatCode = "";
    private String sourcesForPart = null;
    private String searchedHeat = null;

    private FormView form, heatForm;
    private LinearLayout partsBox, heatBox;
    private CheckBox sameHeatNew;
    private TextView sourceNote, qtyNote;
    private Button save;
    private boolean saving = false;

    private static final String SOURCE = "source_option", DETAIL = "raw_detail_id", MILL = "steel_mill_id";

    IncRmtcEditor(MainActivity a, String id, JSONObject prefill) {
        super(a);
        this.id = id == null || id.isEmpty() ? null : id;
        this.prefill = prefill;
    }

    @Override public String title() { return id == null ? "New RMTC · Header" : "Edit RMTC · Header"; }
    @Override public String subtitle() { return "RMTC Entry · Step 1 · fields marked * are required"; }
    @Override public int tab() { return Catalog.QUALITY; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONObject rec = id == null ? null : IncRmtcData.rmtc(api, id);
            List<String> covered = new ArrayList<>();
            if (rec != null) for (JSONObject r : IncRmtcData.coveredParts(api, id)) covered.add(Lookups.j(r, "part_id"));
            Map<String, JSONObject> p = IncRmtcData.parts(api);
            IncRmtcData.addMissingParts(api, p, covered);
            List<JSONObject> m = IncCalc.list(Lookups.rows(api, Lookups.steelMills()));
            List<JSONObject> s = IncCalc.list(Lookups.rows(api, Lookups.suppliers()));
            Lookups.rows(api, IncCalc.employeeLookup("RMTC_PREPARE"));
            return new Object[]{rec, covered, p, m, s};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            existing = (JSONObject) res[0];
            @SuppressWarnings("unchecked") List<String> covered = (List<String>) res[1];
            @SuppressWarnings("unchecked") Map<String, JSONObject> p = (Map<String, JSONObject>) res[2];
            @SuppressWarnings("unchecked") List<JSONObject> m = (List<JSONObject>) res[3];
            @SuppressWarnings("unchecked") List<JSONObject> s = (List<JSONObject>) res[4];
            parts = p; mills = m; suppliers = s;
            selectedParts.clear();
            selectedParts.addAll(covered);
            if (existing != null && !"DRAFT".equalsIgnoreCase(IncCalc.firstText(Lookups.j(existing, "status"), "DRAFT"))) renderLocked();
            else render();
        });
        return scroll;
    }

    // ------------------------------------------------------------------ locked (final) record
    private void renderLocked() {
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "Edit Approved / Final RMTC with Password", 15, Ui.TEXT, true));
        card.addView(Ui.text(a, "RMTC " + Lookups.j(existing, "rmtc_number") + " is " + Ui.pretty(Lookups.j(existing, "status"))
            + ". Header fields can be edited only in Draft. Administrator access is not required: your current QCMS password and RMTC Edit permission "
            + "are required. The record returns to Draft and must be validated / approved again after the amendment.", 12.5f, Ui.MUTED, false));
        EditText reason = Ui.input(a, "Edit / Amendment Reason", false);
        card.addView(reason, Ui.matchWrap(a, 10));
        Button unlock = Ui.primary(a, "Unlock for Controlled Edit");
        card.addView(unlock, Ui.matchWrap(a, 10));
        unlock.setOnClickListener(v -> {
            String why = reason.getText().toString().trim();
            if (why.isEmpty()) { a.toast("Enter the amendment reason before unlocking the record."); return; }
            a.confirmPassword("Confirm with your QCMS password", () -> Api.async(() -> {
                api.insert("qcms_password_edit_audit", new JSONObject().put("entity_type", "RMTC").put("entity_id", id).put("reason", why)
                    .put("status_before", IncCalc.jo(existing, "status")).put("disposition_before", IncCalc.jo(existing, "disposition")));
                api.update("rmtc_approvals", id, new JSONObject().put("status", "DRAFT").put("disposition", "PENDING")
                    .put("disposition_reason", "Controlled amendment: " + why)
                    .put("validated_by_employee_id", JSONObject.NULL).put("approved_by_employee_id", JSONObject.NULL)
                    .put("validated_at", JSONObject.NULL).put("decision_at", JSONObject.NULL));
                return true;
            }, (ok, e) -> {
                if (e != null) { a.toast(Api.message(e)); return; }
                a.toast("Record unlocked for controlled editing. Re-validation / approval is required after saving.");
                a.rebuild();
            }));
        });
        add(card, 0);
    }

    // ------------------------------------------------------------------ form
    private static String nowNumber() {
        return "RMTC-D9-" + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMddHHmmss", Locale.ROOT));
    }

    private String partyLabel(List<JSONObject> rows, String id) {
        for (JSONObject r : rows) if (id.equals(Lookups.j(r, "id"))) return Lookups.PARTY.of(r);
        return "";
    }

    private void render() {
        boolean isNew = existing == null;
        add(Ui.label(a, "A · HEAT NUMBER SEARCH"), 0);
        add(Ui.text(a, "Search the Heat Number first. The same Heat may be reused only with a different Supplier RMTC Number.", 12, Ui.MUTED, false), 2);

        List<Field> fields = new ArrayList<>();
        fields.add(Field.text("heat_number", "Search / Enter Heat Number").req().hint("Enter supplier Heat Number"));
        heatForm = new FormView(a, fields);
        add(heatForm, 4);
        Button search = Ui.outline(a, "Search Heat", Ui.TEAL);
        add(search, 6);
        heatBox = Ui.vbox(a);
        add(heatBox, 6);
        sameHeatNew = new CheckBox(a);
        sameHeatNew.setText("New RMTC / TC for this existing Heat (enter only the quantity certified on this new certificate)");
        sameHeatNew.setTextColor(Ui.TEXT);
        sameHeatNew.setChecked(true);
        sameHeatNew.setVisibility(View.GONE);
        add(sameHeatNew, 4);
        search.setOnClickListener(v -> searchHeat(true));

        add(Ui.label(a, "B · CERTIFICATE & COVERED PARTS"), 16);
        add(Ui.text(a, "Part Numbers Covered by this Heat * (1 to 30; the first part is the primary part)", 12, Ui.MUTED, false), 2);
        partsBox = Ui.vbox(a);
        add(partsBox, 4);
        Button addPart = Ui.outline(a, "+ Add Part Number", Ui.TEAL);
        add(addPart, 6);
        addPart.setOnClickListener(v -> pickPart());

        List<Field> cert = new ArrayList<>();
        cert.add(Field.text("rmtc_number", "QCMS RMTC Number").req());
        cert.add(Field.date("entry_date", "Entry Date").req().def(Ui.today()));
        cert.add(Field.text("certificate_reference", "Supplier RMTC Number").req());
        cert.add(Field.date("certificate_date", "RMTC Date").req().def(Ui.today()));
        cert.add(Field.select(SOURCE, "Approved Raw Material Source").req().hint("One row per approved Supplier from Part Master"));
        cert.add(Field.select(DETAIL, "Raw Material Detail").req().hint("Controlled Part Master raw material section / route"));
        cert.add(Field.select(MILL, "Steel Mill").req());
        cert.add(Field.text("heat_code", "Internal Heat Code").hint("Auto on save: Steel Mill initial-0001"));
        cert.add(Field.number("certificate_quantity", "Global Heat Steel Quantity (kg)").req().range(0, Double.MAX_VALUE));
        cert.add(Field.info("rm_section", "RM Section"));
        cert.add(Field.info("forging_route", "Forging Route / Root"));
        cert.add(Field.lookup("prepared_by_employee_id", "Prepared By", IncCalc.employeeLookup("RMTC_PREPARE")).req());
        cert.add(Field.area("remarks", "RMTC Remarks"));
        cert.add(Field.text("microstructure_caption_1", "Photo 1 Title").def("Microstructure Photo 1"));
        cert.add(Field.text("microstructure_caption_2", "Photo 2 Title").def("Microstructure Photo 2"));
        cert.add(Field.text("microstructure_caption_3", "Photo 3 Title").def("Microstructure Photo 3"));
        form = new FormView(a, cert);
        add(form, 10);
        sourceNote = Ui.text(a, "", 12, Ui.AMBER_FG, false);
        qtyNote = Ui.text(a, "", 12, Ui.MUTED, false);
        add(sourceNote, 4);
        add(qtyNote, 2);
        add(Ui.text(a, "Microstructure photographs and the RMTC certificate copy are uploaded on the saved RMTC record (Upload actions).", 11.5f, Ui.MUTED, false), 4);

        save = Ui.primary(a, "Save RMTC Header & Continue");
        add(save, 18);
        save.setOnClickListener(v -> save());

        // initial values
        if (isNew) {
            form.set("rmtc_number", nowNumber());
            if (!api.employeeId.isEmpty()) form.set("prepared_by_employee_id", api.employeeId);
            if (prefill != null) {
                if (!Lookups.j(prefill, "heat_number").isEmpty()) heatForm.set("heat_number", Lookups.j(prefill, "heat_number"));
                if (!Lookups.j(prefill, "part_id").isEmpty()) selectedParts.add(Lookups.j(prefill, "part_id"));
            }
        } else {
            heatForm.set("heat_number", existing.opt("heat_number"));
            for (String k : new String[]{"rmtc_number", "entry_date", "certificate_reference", "certificate_date", "heat_code",
                "certificate_quantity", "rm_section", "forging_route", "prepared_by_employee_id", "remarks"}) {
                if (existing.has(k) && !existing.isNull(k)) form.set(k, existing.opt(k));
            }
            for (int s = 1; s <= 3; s++) {
                String cap = Lookups.j(existing, "microstructure_caption_" + s);
                form.set("microstructure_caption_" + s, cap.isEmpty() ? "Microstructure Photo " + s : cap);
            }
            if (Lookups.j(existing, "entry_date").isEmpty()) form.set("entry_date", Ui.today());
            if (Lookups.j(existing, "certificate_date").isEmpty()) form.set("certificate_date", Ui.today());
        }
        form.onChange((key, value) -> {
            if (SOURCE.equals(key)) onSource(false);
            else if (DETAIL.equals(key)) onDetail();
        });
        sameHeatNew.setOnCheckedChangeListener((b, on) -> applyQtyMode());
        renderParts();
        loadSources(true);
        if (!heatForm.str("heat_number").isEmpty()) searchHeat(false);
    }

    // ------------------------------------------------------------------ heat search
    private void searchHeat(boolean fromButton) {
        String heat = heatForm.str("heat_number");
        heatBox.removeAllViews();
        if (heat.isEmpty()) { if (fromButton) a.toast("Enter the Heat Number first."); return; }
        heatBox.addView(loading());
        Api.async(() -> new Object[]{IncRmtcData.heatSummary(api, heat), IncRmtcData.heatUsage(api, heat), IncRmtcData.canonicalHeatCode(api, heat)}, (res, err) -> {
            heatBox.removeAllViews();
            if (err != null) { heatBox.addView(Ui.text(a, Api.message(err), 12, Ui.RED_FG, false)); return; }
            heatSummary = (JSONObject) res[0];
            searchedHeat = heat;
            @SuppressWarnings("unchecked") List<JSONObject> usage = (List<JSONObject>) res[1];
            canonicalHeatCode = heatSummary.length() > 0 ? (String) res[2] : "";
            renderHeat(heat, usage);
            applyQtyMode();
        });
    }

    private void renderHeat(String heat, List<JSONObject> usage) {
        if (heatSummary.length() == 0) {
            heatBox.addView(Ui.chip(a, "New Heat Number. The steel quantity entered below becomes the global Heat steel quantity.", "teal"));
            return;
        }
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "GLOBAL HEAT QUANTITY BALANCE & RECORD LIST", 13, Ui.TEXT, true));
        card.addView(Ui.pair(a, "Global Heat Steel", IncCalc.kg(IncCalc.f(heatSummary.opt("global_steel_quantity_kg")))));
        card.addView(Ui.pair(a, "Inward Steel Used", IncCalc.kg(IncCalc.f(heatSummary.opt("inward_steel_quantity_kg")))));
        card.addView(Ui.pair(a, "Remaining Planned Steel", IncCalc.kg(IncCalc.f(heatSummary.opt("remaining_planned_steel_quantity_kg")))));
        card.addView(Ui.pair(a, "Unallocated Heat Balance", IncCalc.kg(IncCalc.first(heatSummary, "available_unallocated_steel_quantity_kg", "available_steel_quantity_kg"))));
        card.addView(Ui.text(a, "Committed Heat steel: " + IncCalc.kg(IncCalc.f(heatSummary.opt("committed_steel_quantity_kg"))) + " = Inward "
            + IncCalc.kg(IncCalc.f(heatSummary.opt("inward_steel_quantity_kg"))) + " + Remaining planned " + IncCalc.kg(IncCalc.f(heatSummary.opt("remaining_planned_steel_quantity_kg"))) + ".", 11.5f, Ui.MUTED, false));
        boolean rejectedOnly = (int) IncCalc.f(heatSummary.opt("active_rmtc_count")) == 0 && (int) IncCalc.f(heatSummary.opt("rejected_rmtc_count")) > 0;
        TextView note = Ui.text(a, rejectedOnly
            ? "The previous RMTC record(s) for this Heat Number are rejected. Create another RMTC using a different Supplier RMTC Number."
            : "This Heat Number already exists. Supplier and Part may be reused, but every RMTC must have a different Supplier RMTC Number.", 12, rejectedOnly ? Ui.GREEN_FG : Ui.AMBER_FG, false);
        note.setPadding(0, dp(6), 0, 0);
        card.addView(note);
        if (!canonicalHeatCode.isEmpty()) {
            TextView hc = Ui.text(a, "Existing Heat detected · Internal Heat Code " + canonicalHeatCode + ". The new RMTC will share this Heat Code and the same global Heat steel balance.", 12, Ui.TEAL_DARK, false);
            hc.setPadding(0, dp(6), 0, 0);
            card.addView(hc);
        }
        heatBox.addView(card);
        if (!usage.isEmpty()) {
            String[][] cols = {{"rmtc_number", "RMTC Number"}, {"supplier_rmtc_number", "Supplier RMTC Number"}, {"rmtc_status", "RMTC Status"},
                {"rmtc_disposition", "RMTC Disposition"}, {"supplier_name", "Supplier"}, {"part_number", "Part Number"}, {"part_name", "Part Description"},
                {"planned_production_quantity_pcs", "Planned Qty (pcs)"}, {"input_weight_kg", "Input Wt (kg)"}, {"planned_steel_quantity_kg", "Planned Steel (kg)"},
                {"inward_production_quantity_pcs", "Inward Qty (pcs)"}, {"inward_steel_quantity_kg", "Inward Steel (kg)"},
                {"remaining_planned_steel_quantity_kg", "Remaining Plan (kg)"}, {"automated_validation", "Automated Validation"}, {"part_disposition", "Part Decision"}};
            List<String> headers = new ArrayList<>();
            for (String[] c : cols) headers.add(c[1]);
            List<List<String>> data = new ArrayList<>();
            for (JSONObject r : usage) {
                List<String> line = new ArrayList<>();
                for (String[] c : cols) line.add(Labels.cell(c[0], r.opt(c[0]), null));
                data.add(line);
            }
            heatBox.addView(new DataGrid(a, "Heat ledger", headers, data, 260, null), Ui.matchWrap(a, 6));
        }
        if (existing == null) {
            heatBox.addView(Ui.text(a, "Tick the option below to enter a separate Supplier TC / RMTC for this Heat. Only the Heat identity and Internal Heat Code are reused.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 4));
        }
    }

    private boolean isSameHeatNew() {
        return existing == null && heatSummary.length() > 0 && sameHeatNew.isChecked();
    }

    private double heatGlobalQty() { return heatSummary.length() > 0 ? IncCalc.f(heatSummary.opt("global_steel_quantity_kg")) : 0.0; }

    private void applyQtyMode() {
        boolean exists = heatSummary.length() > 0;
        sameHeatNew.setVisibility(existing == null && exists ? View.VISIBLE : View.GONE);
        if (existing == null && exists && !canonicalHeatCode.isEmpty()) form.set("heat_code", canonicalHeatCode);
        if (existing != null) { qtyNote.setText(""); return; }
        if (exists && !isSameHeatNew()) {
            form.set("certificate_quantity", heatGlobalQty());
            qtyNote.setText("Global Heat Steel Quantity is taken from the existing Heat (" + IncCalc.kg(heatGlobalQty()) + ") and cannot be changed here.");
        } else if (isSameHeatNew()) {
            if (IncCalc.f(form.num("certificate_quantity")) == heatGlobalQty()) form.set("certificate_quantity", "");
            qtyNote.setText("New RMTC / TC Certified Quantity (kg): enter only the quantity certified on this NEW Supplier RMTC/TC. "
                + "Existing Heat balance before this TC: " + IncCalc.kg(heatGlobalQty()) + " certified.");
        } else {
            qtyNote.setText("");
        }
    }

    // ------------------------------------------------------------------ covered parts
    private void renderParts() {
        partsBox.removeAllViews();
        if (selectedParts.isEmpty()) partsBox.addView(Ui.text(a, "No Part Number selected yet.", 12.5f, Ui.MUTED, false));
        for (int i = 0; i < selectedParts.size(); i++) {
            final int index = i;
            LinearLayout row = Ui.hbox(a);
            row.setPadding(dp(10), dp(8), dp(6), dp(8));
            row.setBackground(Ui.round(i == 0 ? Ui.TEAL_SOFT : android.graphics.Color.WHITE, Ui.LINE, 1, 10, a));
            row.addView(Ui.text(a, (i + 1) + ". " + IncRmtcData.partLabel(parts, selectedParts.get(i)) + (i == 0 ? "  (primary)" : ""), 13, Ui.TEXT, i == 0), Ui.weight(1));
            TextView rm = Ui.text(a, "Remove", 12.5f, Ui.ORANGE, true);
            rm.setPadding(dp(10), dp(6), dp(6), dp(6));
            rm.setOnClickListener(v -> { selectedParts.remove(index); renderParts(); loadSources(false); });
            row.addView(rm);
            partsBox.addView(row, Ui.matchWrap(a, 4));
        }
    }

    private void pickPart() {
        if (selectedParts.size() >= 30) { a.toast("A maximum of 30 Part Numbers can be covered by one RMTC."); return; }
        List<String> ids = new ArrayList<>(), names = new ArrayList<>();
        for (Map.Entry<String, JSONObject> e : parts.entrySet()) {
            if (selectedParts.contains(e.getKey()) || !"ACTIVE".equalsIgnoreCase(IncCalc.firstText(Lookups.j(e.getValue(), "status"), "ACTIVE"))) continue;
            ids.add(e.getKey());
            names.add(Lookups.PART.of(e.getValue()));
        }
        if (ids.isEmpty()) { a.toast("Create an active Part Master first."); return; }
        form.choose("Part Number", ids, names, pid -> { selectedParts.add(pid); renderParts(); loadSources(false); });
    }

    // ------------------------------------------------------------------ approved sources
    private String primaryId() {
        if (!selectedParts.isEmpty()) return selectedParts.get(0);
        return existing != null ? Lookups.j(existing, "part_id") : "";
    }

    private void loadSources(boolean initial) {
        String primary = primaryId();
        if (primary.equals(sourcesForPart)) return;
        sourcesForPart = primary;
        Field f = form.field(SOURCE);
        if (primary.isEmpty()) { sources = new ArrayList<>(); setOptions(f, new ArrayList<>(), new ArrayList<>()); form.set(SOURCE, null); onSource(false); return; }
        sourceNote.setText("Loading approved sources…");
        Api.async(() -> IncRmtcData.approvedSourceOptions(api, primary), (list, err) -> {
            if (!primary.equals(sourcesForPart)) return;
            sourceNote.setText("");
            if (err != null) { sourceNote.setText(Api.message(err)); return; }
            sources = list;
            List<String> ids = new ArrayList<>(), names = new ArrayList<>();
            for (JSONObject s : sources) { ids.add(Lookups.j(s, "option_key")); names.add(sourceLabel(s)); }
            setOptions(f, ids, names);
            String current = "";
            if (initial && existing != null) {
                String sup = Lookups.j(existing, "supplier_id"), det = Lookups.j(existing, "selected_source_detail_id");
                for (JSONObject s : sources) {
                    boolean match = !sup.isEmpty() && sup.equals(Lookups.j(s, "supplier_id"));
                    JSONArray d = s.optJSONArray("raw_material_details");
                    for (int i = 0; !match && d != null && i < d.length(); i++) if (!det.isEmpty() && det.equals(Lookups.j(d.optJSONObject(i), "id"))) match = true;
                    if (match) { current = Lookups.j(s, "option_key"); break; }
                }
            } else if (ids.contains(form.str(SOURCE))) {
                current = form.str(SOURCE);
            }
            form.set(SOURCE, current.isEmpty() ? null : current);
            onSource(initial);
            if (sources.isEmpty()) sourceNote.setText("No approved Raw Material Source exists in Part Master for the primary Part Number.");
        });
    }

    private String sourceLabel(JSONObject s) {
        String supplier = partyLabel(suppliers, Lookups.j(s, "supplier_id"));
        if (supplier.isEmpty()) supplier = "Supplier";
        String mill = Lookups.j(s, "steel_mill_id").isEmpty() ? "" : partyLabel(mills, Lookups.j(s, "steel_mill_id"));
        String ref = Lookups.j(s, "approval_reference");
        return supplier + (mill.isEmpty() ? "" : " · " + mill) + (ref.isEmpty() ? "" : " · Ref " + ref) + " · APPROVED"
            + (s.optBoolean("source_ready", true) ? "" : " · ⚠ Complete Raw Material Details");
    }

    private static void setOptions(Field f, List<String> ids, List<String> names) {
        f.options = ids.toArray(new String[0]);
        f.optionLabels = names.toArray(new String[0]);
    }

    private JSONObject currentSource() {
        String key = form.str(SOURCE);
        for (JSONObject s : sources) if (key.equals(Lookups.j(s, "option_key"))) return s;
        return new JSONObject();
    }

    private static String detailLabel(JSONObject raw) {
        String section = IncCalc.firstText(Lookups.j(raw, "material_section_name").trim(), "Raw Material");
        String size = IncCalc.firstText(Lookups.j(raw, "section_size").trim(), "-");
        String route = IncCalc.firstText(Lookups.j(raw, "forging_route").trim(), "-");
        String item = Lookups.j(raw, "supplier_rm_item_code").trim();
        return section + " · " + size + " · " + route + (item.isEmpty() ? "" : " · Item " + item);
    }

    private void onSource(boolean initial) {
        JSONObject src = currentSource();
        JSONArray details = src.optJSONArray("raw_material_details");
        List<String> ids = new ArrayList<>(), names = new ArrayList<>();
        for (int i = 0; details != null && i < details.length(); i++) {
            JSONObject d = details.optJSONObject(i);
            if (d == null || Lookups.j(d, "id").isEmpty()) continue;
            ids.add(Lookups.j(d, "id"));
            names.add(detailLabel(d));
        }
        setOptions(form.field(DETAIL), ids, names);
        String cur = form.str(DETAIL);
        String existingDetail = existing == null ? "" : Lookups.j(existing, "selected_source_detail_id");
        String desired = ids.contains(cur) ? cur : ids.contains(existingDetail) ? existingDetail : (ids.size() == 1 ? ids.get(0) : "");
        form.set(DETAIL, desired.isEmpty() ? null : desired);

        // steel mill: the approved mill of this supplier is locked, else any active steel mill
        String approvedMill = Lookups.j(src, "steel_mill_id");
        List<String> mIds = new ArrayList<>(), mNames = new ArrayList<>();
        boolean locked = false;
        if (!approvedMill.isEmpty() && !partyLabel(mills, approvedMill).isEmpty()) {
            mIds.add(approvedMill); mNames.add(partyLabel(mills, approvedMill)); locked = true;
        } else {
            for (JSONObject m : mills) { mIds.add(Lookups.j(m, "id")); mNames.add(Lookups.PARTY.of(m)); }
        }
        setOptions(form.field(MILL), mIds, mNames);
        String curMill = form.str(MILL);
        if (initial && existing != null) curMill = Lookups.j(existing, "steel_mill_id");
        if (locked) form.set(MILL, approvedMill);
        else form.set(MILL, mIds.contains(curMill) ? curMill : null);

        String note = "";
        if (!form.str(SOURCE).isEmpty() && ids.isEmpty()) note = "This Supplier is approved in Part Master, but it has no ACTIVE Raw Material Detail row. Complete the Raw Material Details section in Part Master before saving this RMTC.";
        else if (!form.str(SOURCE).isEmpty() && ids.size() > 1 && form.str(DETAIL).isEmpty()) note = "This approved Supplier has " + ids.size() + " active Raw Material Detail rows. Select the exact Raw Material Detail.";
        if (locked) note = (note.isEmpty() ? "" : note + "\n") + "Part Master Approved Sources specifies the Steel Mill for this Supplier; it is locked for this RMTC.";
        sourceNote.setText(note);
        onDetail();
    }

    private JSONObject selectedRaw() {
        JSONArray details = currentSource().optJSONArray("raw_material_details");
        String id = form.str(DETAIL);
        for (int i = 0; details != null && i < details.length(); i++) {
            JSONObject d = details.optJSONObject(i);
            if (d != null && id.equals(Lookups.j(d, "id"))) return d;
        }
        return null;
    }

    private void onDetail() {
        JSONObject raw = selectedRaw();
        JSONObject src = currentSource();
        String section = raw != null ? Lookups.j(raw, "section_size") : Lookups.j(src, "section_size");
        String route = raw != null ? Lookups.j(raw, "forging_route") : Lookups.j(src, "forging_route");
        form.set("rm_section", IncCalc.firstText(section, existing == null ? "" : Lookups.j(existing, "rm_section")));
        form.set("forging_route", IncCalc.firstText(route, existing == null ? "" : Lookups.j(existing, "forging_route")));
    }

    // ------------------------------------------------------------------ save
    private void save() {
        if (saving) return;
        String heat = heatForm.str("heat_number");
        if (heat.isEmpty()) { a.toast("Search or enter the Heat Number first."); return; }
        if (!heat.equals(searchedHeat)) { searchHeat(false); a.toast("Heat Number checked. Review the Heat balance above, then save again."); return; }
        if (selectedParts.isEmpty()) { a.toast("Select at least one Part Number."); return; }
        String rmtcNo = form.str("rmtc_number"), certRef = form.str("certificate_reference"), sourceKey = form.str(SOURCE),
            steelId = form.str(MILL), prepared = form.str("prepared_by_employee_id");
        String sizeProblem = form.validate();
        JSONObject src = currentSource();
        JSONObject raw = selectedRaw();
        final boolean sameHeat = isSameHeatNew();
        final boolean editing = existing != null;
        final double typedQty = IncCalc.f(form.num("certificate_quantity"));
        final String typedHeatCode = form.str("heat_code");
        final String primary = selectedParts.get(0);
        final List<String> partIds = new ArrayList<>(selectedParts);
        final String[] captions = {form.str("microstructure_caption_1"), form.str("microstructure_caption_2"), form.str("microstructure_caption_3")};
        final String remarks = form.str("remarks");
        final String entryDate = form.str("entry_date"), certDate = form.str("certificate_date");
        saving = true;
        save.setEnabled(false);
        save.setText("Saving RMTC and preparing Part Worksheets…");
        Api.async(() -> {
            // fresh server state for the heat (same as the website's rerun)
            JSONObject summary = IncRmtcData.heatSummary(api, heat);
            String canonical = summary.length() > 0 ? IncRmtcData.canonicalHeatCode(api, heat) : "";
            double qty = (!editing && summary.length() > 0 && !sameHeat) ? IncCalc.f(summary.opt("global_steel_quantity_kg")) : typedQty;
            JSONObject dup = certRef.isEmpty() ? null : IncRmtcData.duplicate(api, heat, certRef, editing ? id : null);
            if (dup != null) throw new IllegalArgumentException("Heat " + heat + " already uses Supplier RMTC Number " + certRef + " in " + Lookups.j(dup, "rmtc_number") + ". Enter a different Supplier RMTC Number.");
            if (rmtcNo.isEmpty() || certRef.isEmpty() || sourceKey.isEmpty() || steelId.isEmpty() || prepared.isEmpty() || qty <= 0)
                throw new IllegalArgumentException("Complete all mandatory certificate, source, heat, quantity and employee fields.");
            if (!src.optBoolean("source_ready", true) || raw == null)
                throw new IllegalArgumentException("The selected Approved Raw Material Source is missing its ACTIVE Raw Material Detail. Complete the Raw Material Details row in Part Master first.");
            if (sizeProblem != null) throw new IllegalArgumentException(sizeProblem);
            String heatCode = !canonical.isEmpty() ? canonical : !typedHeatCode.isEmpty() ? typedHeatCode
                : api.nextNumber("qsms_next_heat_code", new JSONObject().put("p_steel_mill_id", steelId));
            JSONObject part = parts.get(primary);
            JSONObject payload = new JSONObject();
            payload.put("rmtc_number", rmtcNo);
            payload.put("entry_date", entryDate.isEmpty() ? Ui.today() : entryDate);
            payload.put("certificate_reference", certRef);
            payload.put("certificate_date", certDate.isEmpty() ? Ui.today() : certDate);
            payload.put("part_id", primary);
            payload.put("supplier_id", Lookups.j(src, "supplier_id"));
            payload.put("steel_mill_id", steelId);
            payload.put("material_grade_id", IncCalc.jo(part, "material_grade_id"));
            payload.put("heat_number", heat);
            payload.put("heat_code", heatCode);
            payload.put("certificate_quantity", qty);
            payload.put("chemistry_results", new JSONObject());
            payload.put("chemistry_compliance", "NOT_EVALUATED");
            payload.put("chemistry_failures", new JSONArray());
            payload.put("mechanical_results", new JSONObject());
            payload.put("status", editing ? IncCalc.firstText(Lookups.j(existing, "status"), "DRAFT") : "DRAFT");
            payload.put("selected_source_detail_id", Lookups.j(raw, "id"));
            payload.put("rm_section", IncCalc.jo(raw, "section_size"));
            payload.put("forging_route", IncCalc.jo(raw, "forging_route"));
            payload.put("prepared_by_employee_id", prepared);
            String preparedAt = editing ? Lookups.j(existing, "prepared_at") : "";
            payload.put("prepared_at", preparedAt.isEmpty() ? LocalDateTime.now().toString() : preparedAt);
            payload.put("remarks", IncCalc.jt(remarks));
            for (int s = 0; s < 3; s++) payload.put("microstructure_caption_" + (s + 1), IncCalc.jt(captions[s]));
            JSONArray ids = new JSONArray();
            for (String p : partIds) ids.put(p);
            Object result = api.rpcValue("qsms_save_rmtc_header", new JSONObject()
                .put("p_rmtc_id", editing ? id : JSONObject.NULL).put("p_payload", payload).put("p_part_ids", ids));
            String savedId = "";
            String savedNo = rmtcNo;
            if (result instanceof JSONObject) { savedId = ((JSONObject) result).optString("id"); savedNo = IncCalc.firstText(Lookups.j((JSONObject) result, "rmtc_number"), rmtcNo); }
            else if (result instanceof JSONArray && ((JSONArray) result).length() > 0) {
                Object first = ((JSONArray) result).get(0);
                if (first instanceof JSONObject) { savedId = ((JSONObject) first).optString("id"); savedNo = IncCalc.firstText(Lookups.j((JSONObject) first, "rmtc_number"), rmtcNo); }
                else savedId = String.valueOf(first);
            } else if (result != null) savedId = String.valueOf(result);
            if (savedId.isEmpty() && editing) savedId = id;
            if (savedId.isEmpty()) {
                JSONObject found = IncCalc.one(api, "rmtc_approvals?select=id&rmtc_number=eq." + Api.enc(rmtcNo) + "&limit=1");
                if (found == null) throw new Api.ApiException(500, "The RMTC was saved but its id was not returned. Open RMTC Records to continue.");
                savedId = found.optString("id");
            }
            // The legacy atomic RMTC header RPC predates photo titles, so persist the title columns explicitly.
            JSONObject caps = new JSONObject();
            for (int s = 0; s < 3; s++) caps.put("microstructure_caption_" + (s + 1), IncCalc.jt(captions[s]));
            try { api.update("rmtc_approvals", savedId, caps); } catch (Exception e) {
                throw new Api.ApiException(0, "RMTC " + savedNo + " was saved, but the photo titles could not be saved: " + Api.message(e));
            }
            Lookups.invalidate();
            return new String[]{savedId, savedNo, heatCode};
        }, (res, err) -> {
            saving = false;
            save.setEnabled(true);
            save.setText("Save RMTC Header & Continue");
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast("RMTC " + res[1] + " saved successfully. Internal Heat Code: " + res[2] + ".");
            Module m = Catalog.get("rmtc");
            a.replaceTop(new RecordScreen(a, m != null ? m : Catalog.adhoc("rmtc_approvals"), res[0]));
            a.push(new IncRmtcWorksheet(a, res[0], partIds.get(0)));
        });
    }

    @Override public boolean onBack() {
        if (form == null) return false;
        a.confirm("Leave without saving?", "Changes on this RMTC header are not saved.", "Leave", () -> a.back());
        return true;
    }

    static final List<String> FINAL = Arrays.asList("APPROVED", "PARTIALLY_APPROVED", "REJECTED");
}
