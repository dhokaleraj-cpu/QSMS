package com.fourstar.qcmsapp;

import android.graphics.Color;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Inspection & quality entry. Inspection layouts, tolerances and report rules live in QCMS,
 * so entries open the controlled QCMS page inside the app (camera photo upload included).
 */
public final class InspectScreen extends Screen {
    private static final String[][] ITEMS = {
        {"OSP dimensional inspection", "Stage-wise dimensional report · photos from camera", "osp-dimensional"},
        {"OSP MetLAB", "Metallurgical results for OSP lots", "osp-metlab"},
        {"Dimensional report entry", "Layout-driven dimensional inspection", "dimensional-entry"},
        {"MetLAB report entry", "Chemistry, hardness, microstructure photos", "metlab-entry"},
        {"Bend test entry", "Bend angle and part photograph", "bend-test-entry"},
        {"Material inward", "Inward lots and quantities", "inward-entry"},
        {"RMTC entry", "Raw material test certificate", "rmtc-entry"},
        {"Standard room inspection", "Standard room records", "standard-room-inspection"},
        {"Customer complaint", "Log a customer complaint with photos", "customer-complaint"},
        {"Supplier complaint", "Log a supplier complaint with photos", "supplier-complaint"},
        {"Inspection records", "Search saved reports", "dimensional-records"},
    };

    public InspectScreen(MainActivity a) { super(a); }

    @Override public String title() { return "Inspect"; }
    @Override public String subtitle() { return "Inspection & quality entry · camera upload"; }
    @Override public int tab() { return 2; }

    @Override
    public View build() {
        newPage();
        TextView note = Ui.text(a, "Entries open the controlled QCMS form inside the app. Use the camera button of any photo field; photos are compressed and uploaded with progress. Sign in once inside QCMS web if asked.", 12, Ui.MUTED, false);
        note.setBackground(Ui.round(Ui.TEAL_SOFT, 0, 0, 12, a));
        note.setPadding(dp(12), dp(10), dp(12), dp(10));
        add(note, 0);
        for (String[] item : ITEMS) {
            LinearLayout card = Ui.card(a);
            LinearLayout row = Ui.hbox(a);
            LinearLayout text = Ui.vbox(a);
            text.addView(Ui.text(a, item[0], 14, Ui.TEXT, true));
            text.addView(Ui.text(a, item[1], 11.5f, Ui.MUTED, false));
            row.addView(text, Ui.weight(1));
            row.addView(Ui.text(a, "›", 24, Ui.TEAL, true));
            card.addView(row);
            Ui.clickable(card, Color.WHITE, Ui.LINE, 14);
            card.setOnClickListener(v -> a.openWeb(item[0], item[2]));
            add(card, 8);
        }
        return scroll;
    }
}
