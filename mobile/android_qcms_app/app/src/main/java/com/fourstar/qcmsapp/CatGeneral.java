package com.fourstar.qcmsapp;

import java.util.List;

/** More tab: Global Search, KPI dashboards, Report Builder, Master Lists, Traceability, My Account. */
public final class CatGeneral {
    private CatGeneral() { }

    private static final String SEARCH = "Search & dashboards", REPORTS = "Reports", ACCOUNT = "Account";

    public static void register(List<Module> list) {
        list.add(new Module("global_search", "Global Search", Catalog.MORE, SEARCH, "")
            .desc("Search Part, Heat, RMTC, Batch, Supplier, Customer, PO, Report and other records")
            .custom(GenSearchScreen::new).readOnly().noEdit());
        list.add(new Module("kpi_dashboards", "KPI Dashboards", Catalog.MORE, SEARCH, "")
            .desc("Top-10 management dashboards: live numbers, charts and tables")
            .custom(GenKpiScreen::new).readOnly().noEdit());

        // R39: website KPI Dashboards views "Modules" (qcms_module_kpis) and "My Dashboards" (qcms_user_dashboards)
        list.add(new Module("module_kpis", "Module KPIs", Catalog.MORE, SEARCH, "")
            .desc("Every module's KPI cards with 6-month trend · tap a card for the records behind it")
            .custom(KpiModules.ModulesScreen::new).readOnly().noEdit());
        list.add(new Module("my_dashboards", "My Dashboards", Catalog.MORE, SEARCH, "")
            .desc("Your own KPI dashboards: KPI cards, charts and tables · share with your company")
            .custom(GenDashScreen::new).readOnly().noEdit());

        list.add(new Module("reports_centre", "Reports Centre", Catalog.MORE, REPORTS, "")
            .desc("All reports like the website: supply chain, heat, quality, complaints, NPD, APQP")
            .custom(GenCentres.ReportsScreen::new).readOnly().noEdit());
        list.add(new Module("records_centre", "Records Centre", Catalog.MORE, REPORTS, "")
            .desc("Every register and record as PDF (website print layout), deletion requests, history")
            .custom(GenCentres.RecordsScreen::new).readOnly().noEdit());
        list.add(new Module("report_builder", "Report Builder", Catalog.MORE, REPORTS, "")
            .desc("Build any report: dataset, columns, filters, totals, chart, CSV, saved reports")
            .custom(GenReportScreen::new).readOnly().noEdit());
        list.add(new Module("master_lists", "Master Lists", Catalog.MORE, REPORTS, "")
            .desc("Clean lists of every master (parts, customers, suppliers, grades, assets…) with CSV export")
            .custom(GenMasterListsScreen::new).readOnly().noEdit());
        list.add(new Module("inventory_reports", "Inventory & Stock Reports", Catalog.MORE, REPORTS, "")
            .desc("Stock by stage, RM by heat, forging / OSP stock, FG & dispatch, movement ledger · filters · Excel / PDF")
            .custom(GenInventoryScreen::new).readOnly().noEdit());
        list.add(new Module("traceability", "Traceability", Catalog.MORE, REPORTS, "")
            .desc("Customer order genealogy and heat / batch traceability from RMTC to dispatch")
            .custom(GenTraceScreen::new).readOnly().noEdit());

        list.add(new Module("my_account", "My Account", Catalog.MORE, ACCOUNT, "")
            .desc("Your login information and password change")
            .custom(GenAccountScreen::new).readOnly().noEdit());
        list.add(new Module("about", "About STAWN QCMS", Catalog.MORE, ACCOUNT, "")
            .desc("Version, developer STAWN PRECISION PRIVATE LIMITED, copyright and licence")
            .custom(GenCentres.AboutScreen::new).readOnly().noEdit());
    }
}
