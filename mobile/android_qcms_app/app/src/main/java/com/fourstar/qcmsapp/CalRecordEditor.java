package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Calibration / validation record (calibration_validation.py section B). R28 rule: gauges, fixtures and jigs are
 * recorded against their Part / Process link; instruments, equipment, masters and reference standards are
 * calibrated directly (link_id null). Accepted / limited-use results move the due dates on the link and the asset.
 */
final class CalRecordEditor extends CalEditScreen {
    static final Set<String> PART_LINKED = new HashSet<>(Arrays.asList("GAUGE", "FIXTURE", "JIG"));
    static final String[] RESULTS = {"ACCEPTED", "LIMITED_USE", "REJECTED", "PENDING"};

    static final Field.Lookup ASSETS = new Field.Lookup("quality_assets",
        "id,asset_code,asset_number,asset_name,asset_type,range_text,serial_number,location,calibration_frequency_days,service_type,next_due_date,status",
        "&status=eq.ACTIVE", "asset_code.asc",
        r -> Lookups.join(Lookups.j(r, "asset_code"), Lookups.j(r, "asset_number"), Lookups.j(r, "asset_name"), Ui.pretty(Lookups.j(r, "asset_type"))));

    private final List<JSONObject> links = new ArrayList<>();
    private Map<String, String> partLabels;
    private Map<String, String> processLabels;
    private JSONObject extraAsset;

    CalRecordEditor(MainActivity a, String id, JSONObject prefill) { super(a, id, prefill); }

    @Override public String title() { return (id == null ? "New · " : "Edit · ") + "Calibration / Validation"; }
    @Override protected String table() { return "quality_asset_calibration_records"; }
    @Override protected Module module() { return Catalog.get("calibration_records"); }
    @Override protected String saveLabel() { return id == null ? "Save Calibration / Validation Record" : "Update Calibration / Validation Record"; }
    @Override protected String savedMessage() { return "Calibration / Validation record saved and next due date updated."; }

    @Override
    protected void load() throws Exception {
        Lookups.rows(api, ASSETS);
        Lookups.rows(api, Lookups.employees());
        JSONArray l = api.rows("quality_asset_part_process_links?select=id,asset_id,part_id,process_id,frequency_days,service_type,next_due_date,status&status=eq.ACTIVE&order=next_due_date.asc&limit=10000");
        for (int i = 0; i < l.length(); i++) if (l.optJSONObject(i) != null) links.add(l.optJSONObject(i));
        String keepLink = existing != null ? Lookups.j(existing, "link_id") : (prefill != null ? Lookups.j(prefill, "link_id") : "");
        if (!keepLink.isEmpty() && link(keepLink) == null) {
            JSONArray one = api.rows("quality_asset_part_process_links?select=id,asset_id,part_id,process_id,frequency_days,service_type,next_due_date,status&id=eq." + keepLink);
            if (one.length() > 0) links.add(one.getJSONObject(0));
        }
        String assetId = existing != null ? Lookups.j(existing, "asset_id") : (prefill != null ? Lookups.j(prefill, "asset_id") : "");
        if (!assetId.isEmpty() && Lookups.rowOf(ASSETS, assetId) == null) {
            JSONArray one = api.rows("quality_assets?select=" + ASSETS.select + "&id=eq." + assetId);
            if (one.length() > 0) extraAsset = one.getJSONObject(0);
        }
        Set<String> parts = new HashSet<>(), procs = new HashSet<>();
        for (JSONObject r : links) { parts.add(Lookups.j(r, "part_id")); procs.add(Lookups.j(r, "process_id")); }
        partLabels = Labels.load(api, "parts", parts);
        processLabels = Labels.load(api, "processes", procs);
    }

    private JSONObject link(String linkId) {
        if (linkId == null || linkId.isEmpty()) return null;
        for (JSONObject r : links) if (linkId.equals(Lookups.j(r, "id"))) return r;
        return null;
    }

    private JSONObject asset(String assetId) {
        if (assetId == null || assetId.isEmpty()) return null;
        JSONObject r = Lookups.rowOf(ASSETS, assetId);
        if (r == null && extraAsset != null && assetId.equals(Lookups.j(extraAsset, "id"))) r = extraAsset;
        return r;
    }

    private static String type(JSONObject asset) { return asset == null ? "" : Lookups.j(asset, "asset_type").toUpperCase(Locale.ROOT); }

    private boolean partLinked() { return PART_LINKED.contains(type(asset(form.str("asset_id")))); }

    @Override
    protected void buildForm(CalSections f) {
        f.section("Gauge-fixture link or instrument / equipment",
            Field.lookup("asset_id", "Gauge / Fixture / Instrument / Equipment", ASSETS).req(),
            Field.info("asset_info", "Asset details"),
            Field.select("link_id", "Part / Process gauge-fixture link *").hint("Gauges, fixtures and jigs are recorded against their Part / Process link"));
        f.section("Calibration / validation",
            Field.select("record_type", "Record Type", "CALIBRATION", "VALIDATION").req().def("CALIBRATION"),
            Field.date("service_date", "Service Date").req().def(Ui.today()),
            Field.select("result", "Result", RESULTS).req().def("ACCEPTED"),
            Field.date("next_due_date", "Next Due Date").req().hint("Default = service date + controlled frequency"),
            Field.info("status_info", "Record status (derived from the result)"),
            Field.text("report_number", "Report Number"),
            Field.text("certificate_number", "Certificate Number"),
            Field.text("calibration_agency", "Calibration / Validation Agency"),
            Field.lookup("performed_by_employee_id", "Performed / Verified By", Lookups.employees()).hint("Leave blank = External / Not Assigned"),
            Field.area("remarks", "Service Remarks"));
    }

    @Override
    protected void afterFill() {
        quiet = true;
        String aid = form.str("asset_id");
        applyAsset(aid, true);
        quiet = false;
        if (existing == null) {
            defaultRecordType();
            recalcDue();
        }
        status();
        form.onChange((k, v) -> {
            if (quiet) return;
            switch (k) {
                case "asset_id":
                    quiet = true; applyAsset(form.str("asset_id"), false); quiet = false;
                    if (existing == null) defaultRecordType();
                    recalcDue();
                    break;
                case "link_id":
                    if (existing == null) defaultRecordType();
                    recalcDue();
                    break;
                case "service_date":
                    recalcDue();
                    break;
                case "result":
                    status();
                    break;
                default:
            }
        });
    }

    private void applyAsset(String aid, boolean keepLink) {
        JSONObject asset = asset(aid);
        boolean linked = PART_LINKED.contains(type(asset));
        form.setVisible("link_id", linked);
        Field lf = form.field("link_id");
        List<String> ids = new ArrayList<>(), names = new ArrayList<>();
        for (JSONObject r : links) {
            if (!aid.equals(Lookups.j(r, "asset_id"))) continue;
            ids.add(Lookups.j(r, "id"));
            String part = partLabels.get(Lookups.j(r, "part_id"));
            String proc = Lookups.j(r, "process_id").isEmpty() ? "General / All Processes" : processLabels.get(Lookups.j(r, "process_id"));
            names.add(Lookups.join(part == null ? "-" : part, proc == null ? "-" : proc, "Due " + Ui.date(Lookups.j(r, "next_due_date"))));
        }
        lf.options = ids.toArray(new String[0]);
        lf.optionLabels = names.toArray(new String[0]);
        String cur = form.str("link_id");
        if (!linked) form.set("link_id", null);
        else if (keepLink && ids.contains(cur)) form.set("link_id", cur);
        else if (ids.size() == 1) form.set("link_id", ids.get(0));
        else form.set("link_id", null);

        if (asset == null) { form.set("asset_info", null); return; }
        String number = Lookups.j(asset, "asset_number");
        String info = "Asset Number: " + (number.isEmpty() ? "— (add it in Quality Asset Master)" : number)
            + "\nAsset Code: " + nz(Lookups.j(asset, "asset_code"))
            + " · Serial No.: " + nz(Lookups.j(asset, "serial_number"))
            + " · Location: " + nz(Lookups.j(asset, "location"))
            + "\n" + (linked
                ? (ids.isEmpty() ? "Gauge / fixture / jig without an ACTIVE Part / Process link - create the link first (Part / Process Links)." : "Gauge / fixture / jig: select its Part / Process link.")
                : "Direct calibration (no Part link) · Due " + Ui.date(Lookups.j(asset, "next_due_date")));
        form.set("asset_info", info);
    }

    private static String nz(String s) { return s == null || s.isEmpty() ? "-" : s; }

    /** Website: VALIDATION when the link's (or direct asset's) control type is VALIDATION, else CALIBRATION. */
    private void defaultRecordType() {
        JSONObject src = partLinked() ? link(form.str("link_id")) : asset(form.str("asset_id"));
        String st = src == null ? "" : Lookups.j(src, "service_type");
        quiet = true;
        form.set("record_type", "VALIDATION".equals(st) ? "VALIDATION" : "CALIBRATION");
        quiet = false;
    }

    private int frequency() {
        if (partLinked()) return CalUtil.intOr(link(form.str("link_id")), "frequency_days", 365);
        JSONObject asset = asset(form.str("asset_id"));
        return CalUtil.intOr(asset, "calibration_frequency_days", 365);
    }

    private void recalcDue() {
        String service = form.str("service_date");
        if (service.isEmpty()) return;
        quiet = true;
        form.set("next_due_date", CalUtil.plusDays(service, frequency()));
        quiet = false;
    }

    private static String derivedStatus(String result) {
        if ("ACCEPTED".equals(result) || "LIMITED_USE".equals(result)) return "VALID";
        return "REJECTED".equals(result) ? "REJECTED" : "PENDING";
    }

    private void status() {
        quiet = true;
        form.set("status_info", Ui.pretty(derivedStatus(form.str("result"))));
        quiet = false;
    }

    @Override
    protected String check() {
        JSONObject asset = asset(form.str("asset_id"));
        if (asset == null) return "Select the gauge / fixture / instrument / equipment.";
        if (partLinked()) {
            JSONObject l = link(form.str("link_id"));
            if (l == null) return "Select the Part / Process link of this " + Ui.pretty(type(asset)).toLowerCase(Locale.ROOT)
                + ". Gauges, fixtures and jigs are calibrated through their Part / Process link (create it under Part / Process Links).";
            if (!form.str("asset_id").equals(Lookups.j(l, "asset_id"))) return "The selected Part / Process link belongs to another asset.";
        }
        return null;
    }

    @Override
    protected JSONObject collect() throws Exception {
        boolean linked = partLinked();
        String result = form.str("result");
        JSONObject p = new JSONObject();
        p.put("link_id", linked ? CalUtil.id(form.str("link_id")) : JSONObject.NULL);
        p.put("asset_id", form.str("asset_id"));
        p.put("record_type", form.str("record_type"));
        p.put("service_date", form.str("service_date"));
        p.put("result", result);
        p.put("report_number", CalUtil.v(form.str("report_number")));
        p.put("certificate_number", CalUtil.v(form.str("certificate_number")));
        p.put("calibration_agency", CalUtil.v(form.str("calibration_agency")));
        p.put("performed_by_employee_id", CalUtil.id(form.str("performed_by_employee_id")));
        p.put("next_due_date", form.str("next_due_date"));
        p.put("status", derivedStatus(result));
        p.put("remarks", CalUtil.v(form.str("remarks")));
        return p;
    }

    @Override
    protected JSONObject persist(JSONObject p) throws Exception {
        // Same table write as the website (no tenant_id is sent for this table - the database fills it).
        JSONObject saved = api.save("quality_asset_calibration_records", id, p);
        String result = p.optString("result");
        if ("ACCEPTED".equals(result) || "LIMITED_USE".equals(result)) {
            String service = p.optString("service_date"), next = p.optString("next_due_date");
            StringBuilder failed = new StringBuilder();
            if (!p.isNull("link_id")) {
                try {
                    api.update("quality_asset_part_process_links", p.optString("link_id"),
                        new JSONObject().put("last_service_date", service).put("next_due_date", next));
                } catch (Exception e) { failed.append("Part / Process link: ").append(Api.message(e)).append('\n'); }
            }
            try {
                JSONObject au = new JSONObject().put("next_due_date", next);
                if ("CALIBRATION".equals(p.optString("record_type"))) au.put("last_calibration_date", service);
                else au.put("last_validation_date", service).put("next_validation_due_date", next);
                api.update("quality_assets", p.optString("asset_id"), au);
            } catch (Exception e) { failed.append("Quality asset: ").append(Api.message(e)); }
            if (failed.length() > 0) warning = "The calibration / validation record was saved, but the due-date update failed:\n" + failed
                + "\nOpen the record and save it again to retry.";
        }
        return saved;
    }
}
