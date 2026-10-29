package com.fourstar.qcmsapp;

import java.util.List;

/**
 * R39 · PPAP Document Manager (More tab, NPD / APQP, module key PPAP) and the ECN / PCN register (Masters tab, Parts)
 * - the website's R38 routes ppap-home / ppap-package and ecn-register, on the same tables and RPCs.
 */
public final class CatPpap {
    private CatPpap() { }

    static final String NPD = "NPD / APQP";

    public static void register(List<Module> list) {
        list.add(new Module("ppap", "PPAP Document Manager", Catalog.MORE, NPD, "ppap_packages")
            .desc("PPAP packages linked to APQP: elements, responsible, due dates, documents, ZIP, assignment e-mail")
            .order("package_no.asc").titleField("package_no")
            .col("package_no", "Package No.").col("customer_ppap_no", "PPAP No.").col("customer_part_no", "Part No.").col("customer_id", "Customer")
            .col("submission_level", "Level").col("customer_due_date", "Customer Due").col("completion_percent", "Progress %").col("status", "Status")
            .search("package_no", "customer_ppap_no", "customer_part_no")
            .readOnly().noEdit()
            .action("Open PPAP package", "", (a, row, refresh) -> a.push(new PpapPackageScreen(a, row.optString("id"))))
            .custom(PpapHomeScreen::new));

        list.add(new Module("ecn_register", "ECN / PCN Register", Catalog.MASTERS, "Parts", "part_ecns")
            .desc("Engineering / Process Change Notes (FSI/806/F05): approvals, implementation actions, print")
            .order("ecn_date.desc").titleField("ecn_number")
            .col("ecn_number", "ECN No.").col("change_type", "Type").col("ecn_date", "Date").col("part_number", "Part No.")
            .col("drawing_number", "Drawing No.").col("new_revision", "Rev To").col("status", "Status")
            .search("ecn_number", "part_number", "drawing_number")
            .readOnly().noEdit()
            .action("Open ECN / PCN", "", (a, row, refresh) -> a.push(new EcnScreen(a, row.optString("id"))))
            .custom(a -> new EcnRegisterScreen(a, null)));
    }
}
