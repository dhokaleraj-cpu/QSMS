package com.fourstar.qcmsapp;

import java.util.List;

/** More tab → Administration: native ports of the website's admin pages (user access, settings, email, print, import). */
public final class CatAdmin {
    private CatAdmin() { }

    static final String SECTION = "Administration";

    public static void register(List<Module> list) {
        list.add(new Module("user_access", "Users & Access", Catalog.MORE, SECTION, "")
            .desc("Users, roles, employee link, module / section permissions, defaults, approval routes and audit (Admin)")
            .custom(AdmUsersScreen::new).readOnly().noEdit());
        list.add(new Module("system_settings", "System Settings", Catalog.MORE, SECTION, "")
            .desc("AI Assistant on / off and the email From mode (Admin)")
            .custom(AdmSystemScreen::new).readOnly().noEdit());
        list.add(new Module("email_server", "Email Settings", Catalog.MORE, SECTION, "")
            .desc("Email server, notification routes, templates, automatic report schedules and outbox (Admin)")
            .custom(AdmEmailScreen::new).readOnly().noEdit());
        list.add(new Module("print_designer", "Print Layout Designer", Catalog.MORE, SECTION, "")
            .desc("Design, colours, headings, PO sections and footer of every QCMS print; restore earlier layouts")
            .custom(AdmPrintScreen::new).readOnly().noEdit());
        list.add(new Module("master_import", "Master Import", Catalog.MORE, SECTION, "")
            .desc("Import masters from a CSV file with the website's duplicate-safe rules")
            .custom(AdmImportScreen::new).readOnly().noEdit());
    }
}
