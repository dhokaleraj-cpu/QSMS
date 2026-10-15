package com.fourstar.qcmsapp;

import org.json.JSONObject;

/**
 * Part / Process → gauge / fixture control link (calibration_validation.py section A). Only gauges, fixtures
 * and jigs are part- or process-specific (R28); the frequency drives the reminder and next due date.
 */
final class CalLinkEditor extends CalEditScreen {
    static final String[] FREQ = {"30", "90", "180", "365", "730", "CUSTOM"};
    static final String[] FREQ_LABELS = {"1 Month", "3 Months", "6 Months", "1 Year", "2 Years", "Custom"};

    static final Field.Lookup LINK_ASSETS = new Field.Lookup("quality_assets",
        "id,asset_code,asset_number,asset_name,asset_type,range_text,status",
        "&status=eq.ACTIVE&asset_type=in.(GAUGE,FIXTURE,JIG)", "asset_code.asc",
        r -> Lookups.join(Lookups.j(r, "asset_code"), Lookups.j(r, "asset_number"), Lookups.j(r, "asset_name"), Ui.pretty(Lookups.j(r, "asset_type"))));

    CalLinkEditor(MainActivity a, String id, JSONObject prefill) { super(a, id, prefill); }

    @Override public String title() { return (id == null ? "New · " : "Edit · ") + "Part / Process Link"; }
    @Override protected String table() { return "quality_asset_part_process_links"; }
    @Override protected Module module() { return Catalog.get("asset_part_links"); }
    @Override protected String saveLabel() { return id == null ? "Create Part / Process Gauge-Fixture Link" : "Update Part / Process Gauge-Fixture Link"; }
    @Override protected String savedMessage() { return "Gauge / Fixture applicability saved."; }

    @Override
    protected void buildForm(CalSections f) {
        f.note(CalUtil.infoCard(a, "Part / Process → Gauge / Fixture control",
            "Instruments, equipment, masters and reference standards do not need a Part / Process link - record their calibration directly."));
        f.section("Applicability",
            Field.lookup("asset_id", "Gauge / Fixture / Jig", LINK_ASSETS).req(),
            Field.lookup("part_id", "Part Number", Lookups.parts()).req(),
            Field.lookup("process_id", "Process", Lookups.processes()).hint("Blank = General / All Processes"));
        f.section("Control",
            Field.select("service_type", "Control Type", "CALIBRATION", "VALIDATION", "BOTH").req().def("CALIBRATION"),
            Field.select("_frequency", "Frequency", FREQ).labels(FREQ_LABELS).req().def("365"),
            Field.integer("frequency_days", "Frequency Days").req().range(1, 3650).def(365),
            Field.lookup("responsible_employee_id", "Responsible Employee", Lookups.employees()).hint("Blank = Quality Department Default"),
            Field.text("characteristic_use", "Gauge / Fixture Use / Characteristic"),
            Field.date("next_due_date", "Next Calibration / Validation Due").req(),
            Field.area("remarks", "Remarks"));
    }

    @Override
    protected void afterFill() {
        int days = existing != null ? CalUtil.intOr(existing, "frequency_days", 365) : 365;
        quiet = true;
        String preset = "CUSTOM";
        for (String o : FREQ) if (o.equals(String.valueOf(days))) preset = o;
        form.set("_frequency", preset);
        form.set("frequency_days", days);
        if (form.str("next_due_date").isEmpty()) form.set("next_due_date", CalUtil.plusDays(Ui.today(), days));
        quiet = false;
        form.onChange((k, v) -> {
            if (quiet) return;
            if ("_frequency".equals(k)) {
                String p = form.str("_frequency");
                if (!p.isEmpty() && !"CUSTOM".equals(p)) {
                    quiet = true;
                    form.set("frequency_days", p);
                    if (existing == null) form.set("next_due_date", CalUtil.plusDays(Ui.today(), Integer.parseInt(p)));
                    quiet = false;
                }
            } else if ("frequency_days".equals(k)) {
                Double d = form.num("frequency_days");
                quiet = true;
                String match = "CUSTOM";
                if (d != null) for (String o : FREQ) if (o.equals(String.valueOf(Math.round(d)))) match = o;
                form.set("_frequency", match);
                if (existing == null && d != null && d >= 1) form.set("next_due_date", CalUtil.plusDays(Ui.today(), Math.round(d)));
                quiet = false;
            }
        });
    }

    @Override
    protected JSONObject collect() throws Exception {
        JSONObject p = new JSONObject();
        p.put("asset_id", form.str("asset_id"));
        p.put("part_id", form.str("part_id"));
        p.put("process_id", CalUtil.id(form.str("process_id")));
        p.put("service_type", form.str("service_type"));
        p.put("frequency_days", Math.round(CalUtil.dbl(form.num("frequency_days"))));
        p.put("characteristic_use", CalUtil.v(form.str("characteristic_use")));
        p.put("next_due_date", form.str("next_due_date"));
        p.put("responsible_employee_id", CalUtil.id(form.str("responsible_employee_id")));
        String st = existing == null ? "" : Lookups.j(existing, "status");
        p.put("status", st.isEmpty() ? "ACTIVE" : st);
        p.put("remarks", CalUtil.v(form.str("remarks")));
        return p;
    }

    @Override
    protected JSONObject persist(JSONObject p) throws Exception {
        return api.save("quality_asset_part_process_links", id, p);
    }
}
