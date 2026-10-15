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

        list.add(new Module("report_builder", "Report Builder", Catalog.MORE, REPORTS, "")
            .desc("Build any report: dataset, columns, filters, totals, chart, CSV, saved reports")
            .custom(GenReportScreen::new).readOnly().noEdit());
        list.add(new Module("master_lists", "Master Lists", Catalog.MORE, REPORTS, "")
            .desc("Clean lists of every master (parts, customers, suppliers, grades, assets…) with CSV export")
            .custom(GenMasterListsScreen::new).readOnly().noEdit());
        list.add(new Module("traceability", "Traceability", Catalog.MORE, REPORTS, "")
            .desc("Customer order genealogy and heat / batch traceability from RMTC to dispatch")
            .custom(GenTraceScreen::new).readOnly().noEdit());

        list.add(new Module("my_account", "My Account", Catalog.MORE, ACCOUNT, "")
            .desc("Your login information and password change")
            .custom(GenAccountScreen::new).readOnly().noEdit());
    }
}
