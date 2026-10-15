package com.fourstar.qcmsapp;

import android.graphics.Color;
import android.view.View;
import android.widget.LinearLayout;

/**
 * Replaces the "Website-only administration" block of MoreScreen.addSettings with native Administration links.
 * Call: AdmSettings.addAdminLinks(a, page) in place of the openWeb("system-settings") link.
 */
public final class AdmSettings {
    private AdmSettings() { }

    static void addAdminLinks(MainActivity a, LinearLayout page) {
        boolean admin = Api.get(a).isAdmin();
        page.addView(Ui.label(a, "Administration"), Ui.matchWrap(a, 16));
        String only = admin ? "" : " · Admin only";
        page.addView(link(a, "Users & Access", "Users, roles, permissions, approval routes, audit" + only, v -> a.openModule("user_access")), Ui.matchWrap(a, 4));
        page.addView(link(a, "System Settings", "AI Assistant, email From mode" + only, v -> a.openModule("system_settings")), Ui.matchWrap(a, 6));
        page.addView(link(a, "Email Settings", "Server, routes, templates, schedules, outbox" + only, v -> a.openModule("email_server")), Ui.matchWrap(a, 6));
        page.addView(link(a, "Print Layout Designer", "Design, colours and headings of QCMS prints" + (admin ? "" : " · view only"), v -> a.openModule("print_designer")), Ui.matchWrap(a, 6));
        page.addView(link(a, "Master Import", "Import masters from a CSV file", v -> a.openModule("master_import")), Ui.matchWrap(a, 6));
    }

    private static View link(MainActivity a, String title, String detail, View.OnClickListener click) {
        LinearLayout card = Ui.card(a);
        LinearLayout row = Ui.hbox(a);
        LinearLayout text = Ui.vbox(a);
        text.addView(Ui.text(a, title, 14, Ui.TEXT, true));
        text.addView(Ui.text(a, detail, 11.5f, Ui.MUTED, false));
        row.addView(text, Ui.weight(1));
        row.addView(Ui.text(a, "›", 24, Ui.TEAL, true));
        card.addView(row);
        Ui.clickable(card, Color.WHITE, Ui.LINE, 14);
        card.setOnClickListener(click);
        return card;
    }
}
