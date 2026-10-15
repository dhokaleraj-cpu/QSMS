package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Quality Asset master entry (MasterService.save for "quality_assets"): reserved AST code, required fields,
 * frequency > 0, duplicate check on the master code and the Asset Number. The Asset Name may repeat
 * (many SNAP GAUGEs) - the Asset Number tells them apart.
 */
final class CalAssetEditor extends CalEditScreen {
    static final String[] TYPES = {"INSTRUMENT", "EQUIPMENT", "GAUGE", "FIXTURE", "JIG", "MASTER", "REFERENCE_STANDARD"};
    static final String[] SERVICE = {"CALIBRATION", "VALIDATION", "BOTH"};
    static final String[] STATUS = {"ACTIVE", "INACTIVE", "BLOCKED"};

    private String reservedCode = "";
    private String reserveError = "";

    CalAssetEditor(MainActivity a, String id, JSONObject prefill) { super(a, id, prefill); }

    @Override public String title() { return (id == null ? "New · " : "Edit · ") + "Quality Asset"; }
    @Override protected String table() { return "quality_assets"; }
    @Override protected Module module() { return Catalog.get("quality_assets"); }
    @Override protected String saveLabel() { return "Save controlled record"; }

    @Override
    protected void load() throws Exception {
        if (id == null) {
            // The website reserves the next AST code before the form is shown; it stays editable.
            try { reservedCode = api.nextNumber("qsms_next_master_code", new JSONObject().put("p_master_key", "quality_assets")); }
            catch (Exception e) { reserveError = Api.message(e); }
        }
    }

    @Override
    protected void buildForm(CalSections f) {
        f.section("Quality Assets · instruments, equipment, gauges, fixtures, jigs, masters and reference standards",
            Field.text("asset_code", "Master code *").hint("Auto-generated; editable"),
            Field.text("asset_number", "Asset number").hint("Company asset register number (e.g. FSI-QA-0001)"),
            Field.text("asset_name", "Asset name").req().hint("The same name may repeat (e.g. SNAP GAUGE)"),
            Field.select("asset_type", "Asset type", TYPES).req().def("GAUGE"),
            Field.text("manufacturer", "Manufacturer"),
            Field.text("model", "Model"),
            Field.text("serial_number", "Serial number"),
            Field.text("range_text", "Range"),
            Field.text("least_count", "Least count"),
            Field.text("location", "Location"));
        f.section("Calibration / validation control",
            Field.select("service_type", "Control type", SERVICE).req().def("CALIBRATION"),
            Field.integer("calibration_frequency_days", "Calibration frequency (days)").req().def(365),
            Field.date("last_calibration_date", "Last calibration date"),
            Field.date("next_due_date", "Next calibration due date"),
            Field.integer("validation_frequency_days", "Validation frequency (days)").def(365),
            Field.date("last_validation_date", "Last validation date"),
            Field.date("next_validation_due_date", "Next validation due date"));
        f.section("Record",
            Field.select("status", "Record status", STATUS).req().def("ACTIVE"),
            Field.area("remarks", "Remarks"));
        if (id == null) {
            if (!reservedCode.isEmpty()) f.set("asset_code", reservedCode);
            if (!reserveError.isEmpty()) a.toast("Automatic code could not be reserved: " + reserveError);
        }
    }

    @Override
    protected String check() {
        Double freq = form.num("calibration_frequency_days");
        if (freq != null && freq <= 0) return "Calibration frequency must be greater than zero.";
        return null;
    }

    @Override
    protected JSONObject persist(JSONObject v) throws Exception {
        // normalize_payload: every field, text trimmed / empty -> null, integers, dates
        String[] text = {"asset_code", "asset_number", "asset_name", "manufacturer", "model", "serial_number", "range_text", "least_count", "location", "remarks"};
        JSONObject p = new JSONObject();
        for (String k : text) p.put(k, CalUtil.v(v.isNull(k) ? "" : v.optString(k)));
        p.put("asset_type", v.opt("asset_type"));
        p.put("service_type", v.opt("service_type"));
        p.put("calibration_frequency_days", v.opt("calibration_frequency_days"));
        p.put("validation_frequency_days", v.opt("validation_frequency_days"));
        for (String k : new String[]{"last_calibration_date", "next_due_date", "last_validation_date", "next_validation_due_date"}) p.put(k, v.opt(k));
        p.put("status", v.opt("status"));

        if (id == null && p.isNull("asset_code")) {
            p.put("asset_code", api.nextNumber("qsms_next_master_code", new JSONObject().put("p_master_key", "quality_assets")));
        }
        if (p.isNull("asset_code") || p.optString("asset_code").isEmpty()) throw new Exception("Master code is mandatory.");
        assertNoDuplicate(p);
        try {
            return api.save("quality_assets", id, p);
        } catch (Api.ApiException e) {
            String msg = String.valueOf(e.getMessage());
            if (msg.contains("uq_quality_assets_asset_number")) throw new Exception("This Asset Number is already used by another Quality Asset.");
            if (msg.contains("asset_number")) throw new Exception("Asset Number needs the R21 database step: ask the administrator to run QCMS_R21_RUN_IN_SUPABASE.sql once in Supabase SQL Editor.");
            throw e;
        }
    }

    /** MasterService.assert_no_duplicate: exact natural key (asset_code) + exact identity field (asset_number). */
    private void assertNoDuplicate(JSONObject p) throws Exception {
        String code = CalUtil.norm(p.optString("asset_code"));
        String number = p.isNull("asset_number") ? "" : CalUtil.norm(p.optString("asset_number"));
        // Legacy duplicates stay editable while the controlled code is unchanged.
        boolean checkCode = existing == null || !code.equals(CalUtil.norm(Lookups.j(existing, "asset_code")));
        JSONArray rows = api.rows("quality_assets?select=id,asset_code,asset_number&limit=10000");
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.optJSONObject(i);
            if (r == null) continue;
            if (id != null && id.equals(Lookups.j(r, "id"))) continue;
            if (checkCode && !code.isEmpty() && code.equals(CalUtil.norm(Lookups.j(r, "asset_code"))))
                throw new Exception("Duplicate Quality Assets is not allowed. Matching words already exist: matching controlled key asset_code.");
            if (!number.isEmpty() && number.equals(CalUtil.norm(Lookups.j(r, "asset_number"))))
                throw new Exception("Duplicate Quality Assets is not allowed. Matching words already exist: matching asset number.");
        }
    }
}
