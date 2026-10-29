package com.fourstar.qcmsapp;

import android.view.View;

/**
 * R39 · Material Out / Returnable Delivery Challan record opened from the OSP Register (one heat line opens its whole
 * Material Out document; an older single-heat job opens on its own) - same view as the OSP Material Out record
 * (web OSP Records section B: Details · Print · Vendor returns, no delete there).
 */
final class OspRecordScreen extends Screen {
    private final String moId, jobId;

    OspRecordScreen(MainActivity a, String moId, String jobId) {
        super(a);
        this.moId = moId == null ? "" : moId;
        this.jobId = jobId == null ? "" : jobId;
    }

    @Override public String title() { return "Material Out · Challan"; }
    @Override public String subtitle() { return "Details · Print · Vendor returns"; }
    @Override public int tab() { return Catalog.QUALITY; }

    @Override
    public View build() {
        newPage();
        add(OspRecordView.build(a, moId.isEmpty() ? null : moId, jobId.isEmpty() ? null : jobId, false, this::reload), 4);
        return scroll;
    }

    /** OSP Register action: open the Material Out / challan record of a register row (v_qsms_osp_register). */
    static void open(MainActivity a, org.json.JSONObject row, Runnable refresh) {
        a.push(new OspRecordScreen(a, null, Lookups.j(row, "id")));
    }
}
