package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/** One Quality Asset with its calibration / validation history. */
public final class AssetDetailScreen extends Screen {
    private final String id;
    private String name = "";

    public AssetDetailScreen(MainActivity a, String id) { super(a); this.id = id; }

    @Override public String title() { return name.isEmpty() ? "Quality Asset" : name; }
    @Override public String subtitle() { return "Calibration status & history"; }
    @Override public int tab() { return Catalog.QUALITY; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONArray r = api.rows("quality_assets?select=*&id=eq." + id);
            if (r.length() == 0) throw new Api.ApiException(404, "Asset not found.");
            JSONArray hist = api.rows("quality_asset_calibration_records?select=record_type,service_date,result,certificate_number,report_number,calibration_agency,next_due_date,status&asset_id=eq." + id + "&order=service_date.desc&limit=200");
            return new JSONObject().put("asset", r.getJSONObject(0)).put("hist", hist);
        }, (d, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            render(d.optJSONObject("asset"), d.optJSONArray("hist"));
        });
        return scroll;
    }

    private void render(JSONObject r, JSONArray hist) {
        name = r.optString("asset_name");
        a.rebuildTitle(this);
        offlineNote();
        LinearLayout card = Ui.card(a);
        LinearLayout top = Ui.hbox(a);
        top.addView(Ui.text(a, name, 17, Ui.TEXT, true), Ui.weight(1));
        top.addView(AssetsScreen.dueChip(a, r.optString("next_due_date")));
        card.addView(top);
        String type = r.optString("asset_type");
        boolean direct = type.toUpperCase(Locale.ROOT).contains("INSTRUMENT") || type.toUpperCase(Locale.ROOT).contains("EQUIPMENT");
        card.addView(Ui.pair(a, "Asset number", AssetsScreen.nz(r.optString("asset_number"))));
        card.addView(Ui.pair(a, "Master code", r.optString("asset_code")));
        card.addView(Ui.pair(a, "Type", Ui.pretty(type) + (direct ? " (calibrated directly, no Part link)" : "")));
        card.addView(Ui.pair(a, "Manufacturer · Model", AssetsScreen.nz(r.optString("manufacturer")) + " · " + AssetsScreen.nz(r.optString("model"))));
        card.addView(Ui.pair(a, "Serial number", AssetsScreen.nz(r.optString("serial_number"))));
        card.addView(Ui.pair(a, "Range · Least count", AssetsScreen.nz(r.optString("range_text")) + " · " + AssetsScreen.nz(r.optString("least_count"))));
        card.addView(Ui.pair(a, "Location", AssetsScreen.nz(r.optString("location"))));
        card.addView(Ui.pair(a, "Last calibration", Ui.date(r.optString("last_calibration_date"))));
        card.addView(Ui.pair(a, "Next calibration due", Ui.date(r.optString("next_due_date"))));
        card.addView(Ui.pair(a, "Frequency", r.optInt("calibration_frequency_days", 0) + " days"));
        if (!r.isNull("next_validation_due_date")) card.addView(Ui.pair(a, "Next validation due", Ui.date(r.optString("next_validation_due_date"))));
        card.addView(Ui.pair(a, "Record status", Ui.pretty(r.optString("status"))));
        add(card, 2);

        add(Ui.label(a, "Calibration / validation history (" + (hist == null ? 0 : hist.length()) + ")"), 10);
        List<String> cols = Arrays.asList("Date", "Type", "Result", "Certificate", "Report", "Agency", "Next due", "Status");
        List<List<String>> rows = new ArrayList<>();
        for (int i = 0; hist != null && i < hist.length(); i++) {
            JSONObject h = hist.optJSONObject(i);
            rows.add(Arrays.asList(Ui.date(h.optString("service_date")), Ui.pretty(h.optString("record_type")), Ui.pretty(h.optString("result")),
                AssetsScreen.nz(h.optString("certificate_number")), AssetsScreen.nz(h.optString("report_number")), AssetsScreen.nz(h.optString("calibration_agency")),
                Ui.date(h.optString("next_due_date")), Ui.pretty(h.optString("status"))));
        }
        add(new DataGrid(a, cols, rows, 300, null), 2);

        Button record = Ui.primary(a, "Record calibration / validation");
        record.setOnClickListener(v -> {
            JSONObject pre = new JSONObject();
            try { pre.put("asset_id", id); } catch (Exception ignored) { }
            a.push(new CalRecordEditor(a, null, pre));
        });
        add(record, 14);
        Button edit = Ui.outline(a, "Edit asset (Quality Asset Master)", Ui.TEAL);
        edit.setOnClickListener(v -> {
            Module m = Catalog.get("quality_assets");
            if (m != null) a.push(EditScreen.open(a, m, id, null));
        });
        add(edit, 10);
    }
}
