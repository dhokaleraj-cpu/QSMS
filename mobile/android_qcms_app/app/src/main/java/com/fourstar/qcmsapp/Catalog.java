package com.fourstar.qcmsapp;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Every QCMS module available in the app. Each area registers its modules in its own class
 * (CatSupply, CatIncoming, CatInspection, CatCalib, CatMasters, CatMore) so the catalogue stays readable.
 */
public final class Catalog {
    public static final int HOME = 0, SUPPLY = 1, QUALITY = 2, MASTERS = 3, MORE = 4;
    public static final String[] TAB_NAMES = {"Home", "Supply", "Quality", "Masters", "More"};

    private static List<Module> modules;

    private Catalog() { }

    public static synchronized List<Module> all() {
        if (modules == null) {
            List<Module> list = new ArrayList<>();
            CatSupply.register(list);      // Supply tab
            CatIncoming.register(list);    // Quality tab: RMTC, material inward
            CatInspection.register(list);  // Quality tab: dimensional, MetLAB, bend test, layouts, OSP
            CatCalib.register(list);       // Quality tab: assets, calibration, standard room, complaints
            CatMasters.register(list);     // Masters tab
            CatMore.register(list);        // More tab: NPD / APQP, QC tools, reports, records
            CatGeneral.register(list);     // More tab: search, KPI dashboards, reports, traceability, account
            CatEmail.register(list);       // More tab: email send / sent / groups
            CatAdmin.register(list);       // More tab: administration
            modules = list;
        }
        return modules;
    }

    public static Module get(String key) {
        for (Module m : all()) if (m.key.equals(key)) return m;
        return null;
    }

    /** First module that shows this table (used to open child rows as records). */
    public static Module forTable(String table) {
        for (Module m : all()) if (m.table.equals(table)) return m;
        return null;
    }

    /** Modules of one bottom-navigation tab grouped by section, in catalogue order. */
    public static Map<String, List<Module>> sections(int tab) {
        Map<String, List<Module>> out = new LinkedHashMap<>();
        for (Module m : all()) {
            if (m.tab != tab) continue;
            List<Module> list = out.get(m.section);
            if (list == null) { list = new ArrayList<>(); out.put(m.section, list); }
            list.add(m);
        }
        return out;
    }

    /** Ad-hoc read-only module for a table that has no catalogue entry (child rows). */
    public static Module adhoc(String table) {
        Module m = new Module("adhoc_" + table, Ui.pretty(table), MORE, "Records", table);
        m.readOnly();
        return m;
    }
}
