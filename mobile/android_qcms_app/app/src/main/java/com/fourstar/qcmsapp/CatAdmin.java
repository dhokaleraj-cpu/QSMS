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
        // R39: Licence & Company (company admin edits; others view) and the STAWN Developer Console (STAWN developers only -
        // hidden from the catalogue for everybody else by Catalog.sections, and checked again by the screen and every qcms_dev_* RPC)
        list.add(new Module("licence_company", "Licence & Company", Catalog.MORE, SECTION, "")
            .desc("STAWN QCMS licence, company profile and logo, WhatsApp auto messages (company admin)")
            .custom(LicCompanyScreen::new).readOnly().noEdit());
        list.add(new Module(Catalog.DEVELOPER_CONSOLE, "STAWN Developer Console", Catalog.MORE, SECTION, "")
            .desc("All companies and licence keys, company admins, any company profile, login cover photo, trial-data purge (STAWN only)")
            .custom(DevConsoleScreen::new).readOnly().noEdit());
    }
}
