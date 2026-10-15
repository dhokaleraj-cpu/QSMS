package com.fourstar.qcmsapp;

import org.json.JSONObject;

import java.util.List;

/** Quality tab · Incoming material: RMTC approvals, Material Inward and the heat steel reports. */
public final class CatIncoming {
    private CatIncoming() { }

    static final String SECTION = "Incoming material";

    public static void register(List<Module> list) {
        // ---------------------------------------------------------------- RMTC
        list.add(new Module("rmtc", "RMTC Approvals", Catalog.QUALITY, SECTION, "rmtc_approvals")
            .desc("Raw material test certificates · header, part worksheets, validation & decision")
            .titleField("rmtc_number")
            .col("rmtc_number", "QCMS RMTC").col("certificate_reference", "Supplier RMTC").col("certificate_date", "RMTC Date")
            .col("entry_date", "Entry Date").col("heat_number", "Heat Number").col("heat_code", "Internal Heat Code")
            .col("part_id", "Primary Part").col("supplier_id", "Supplier").col("steel_mill_id", "Steel Mill")
            .col("certificate_quantity", "Steel Quantity kg").col("validation_result", "Validation").col("status", "Workflow")
            .col("disposition", "Disposition").col("decision_at", "Decision Date")
            .statuses("DRAFT", "APPROVAL_PENDING", "APPROVED", "PARTIALLY_APPROVED", "REJECTED")
            .editor((a, id, prefill) -> new IncRmtcEditor(a, id, prefill))
            .action("Part Worksheets", "", (a, row, refresh) -> IncRmtcFlow.worksheets(a, row))
            .action("1 · Submit Draft → Approval Pending", "status=DRAFT|EMPTY", IncRmtcFlow::submit)
            .action("2 · Validate Against Masters", "status=APPROVAL_PENDING", IncRmtcFlow::validate)
            .action("3 · Final Decision per Part", "status=APPROVAL_PENDING", (a, row, refresh) -> IncRmtcFlow.decide(a, row))
            .action("Add Part / Added Part Decision", "status=APPROVED|PARTIALLY_APPROVED", (a, row, refresh) -> a.push(new IncRmtcAdded(a, Lookups.j(row, "id"))))
            .action("Admin · Reopen Decision for Change", "status=APPROVED|PARTIALLY_APPROVED|REJECTED", IncRmtcFlow::adminReopen)
            .action("Upload RMTC certificate / document", "", IncRmtcFlow::uploadDocument)
            .action("Upload microstructure photo", "", IncRmtcFlow::uploadMicrostructure)
            .action("Heat Steel Ledger (this Heat)", "", (a, row, refresh) -> IncRmtcFlow.heatLedger(a, Lookups.j(row, "heat_number")))
            .child("Covered Parts", "rmtc_part_approvals", "rmtc_approval_id", "created_at.asc", new String[][]{
                {"part_id", "Part"}, {"worksheet_completed_at", "Worksheet Done"}, {"approval_status", "Automated Recommendation"},
                {"source_status", "Source"}, {"material_grade_status", "Material Grade"}, {"raw_material_status", "Raw Material"},
                {"chemistry_status", "Chemistry"}, {"jominy_status", "Jominy"}, {"requirement_status", "Requirements"},
                {"actual_di", "Actual DI"}, {"calculated_di", "Calculated DI"}, {"planned_production_quantity_pcs", "Planned pcs"},
                {"input_weight_kg", "Input Wt kg"}, {"planned_steel_quantity_kg", "Planned Steel kg"},
                {"disposition", "Final Decision"}, {"decision_reason", "Decision Reason"}})
            .child("Chemistry", "rmtc_chemistry_results", "rmtc_approval_id", "element.asc", new String[][]{
                {"part_id", "Part"}, {"element", "Element"}, {"minimum_value", "Min %"}, {"maximum_value", "Max %"}, {"actual_value", "Actual %"}, {"result", "Status"}})
            .child("Jominy", "rmtc_jominy_results", "rmtc_approval_id", "distance_mm.asc", new String[][]{
                {"part_id", "Part"}, {"distance_label", "Distance"}, {"distance_mm", "MM"}, {"actual_hrc", "Actual HRC"}, {"result", "Actual Status"},
                {"calculated_hrc", "Calculated HRC"}, {"calculated_result", "Calculated Status"}, {"applicability", "Applicability"}})
            .child("Heat Treatment & Other Requirements", "rmtc_requirement_results", "rmtc_approval_id", "sequence_no.asc", new String[][]{
                {"part_id", "Part"}, {"requirement_name", "Property / Requirement"}, {"requirement_value", "Part Master Value"},
                {"actual_value", "RMTC Actual / Observation"}, {"result", "Status"}})
            .child("Decision Reopen History", "rmtc_decision_revisions", "rmtc_approval_id", "reopened_at.desc", new String[][]{
                {"reopened_at", "Reopened At"}, {"reason", "Reason"}, {"previous_status", "Previous Status"}, {"previous_disposition", "Previous Disposition"}})
            .attach("RMTC", "rmtc"));

        // ---------------------------------------------------------------- Material inward
        list.add(new Module("inward", "Material Inward", Catalog.QUALITY, SECTION, "inward_lots")
            .desc("Steel receipts against accepted RMTCs · production conversion")
            .titleField("inward_number")
            .col("inward_number", "Inward Number").col("inward_date", "Date").col("grn_number", "GRN").col("invoice_number", "Supplier Invoice")
            .col("supplier_id", "Supplier").col("part_id", "Part Number").col("heat_number", "Heat Number").col("heat_code", "Heat Code")
            .col("steel_quantity_kg", "Steel Qty kg").col("production_quantity_pcs", "Production Qty pcs")
            .col("accepted_production_quantity_pcs", "Accepted pcs").col("rejected_production_quantity_pcs", "Rejected pcs")
            .col("hold_production_quantity_pcs", "On Hold pcs").col("input_weight_kg", "Input Weight kg")
            .col("rmtc_disposition", "RMTC Decision").col("receipt_disposition", "Receipt Decision")
            .col("metallurgical_status", "MetLAB").col("dimensional_status", "Dimensional").col("quality_disposition", "Quality Decision")
            .col("status", "Status")
            .statuses("HOLD_PENDING_INSPECTION", "RELEASED", "REJECTED")
            .editor((a, id, prefill) -> new IncInwardEditor(a, id, prefill))
            .action("Upload GRN / invoice / document", "", CatIncoming::uploadInward)
            .action("Link to RM Purchase Order", "supply_rm_purchase_order_id=EMPTY", (a, row, refresh) -> {
                Module m = Catalog.get("rm_receipts");
                if (m == null) { a.toast("RM Receipts (Supply Chain) is not available in this app version."); return; }
                JSONObject pre = new JSONObject();
                try { pre.put("inward_lot_id", Lookups.j(row, "id")); } catch (Exception ignored) { }
                a.push(EditScreen.open(a, m, null, pre));
            })
            .action("Heat Steel Ledger (this Heat)", "", (a, row, refresh) -> IncRmtcFlow.heatLedger(a, Lookups.j(row, "heat_number")))
            .attach("MATERIAL_INWARD", "inward"));

        // ---------------------------------------------------------------- reports
        list.add(new Module("heat_ledger", "Heat Steel Ledger", Catalog.QUALITY, SECTION, "v_qsms_heat_steel_ledger")
            .desc("Global heat steel · every RMTC / part allocation").order("updated_at.desc").status("heat_balance_status").id("")
            .col("heat_number", "Heat Number").col("global_steel_quantity_kg", "Global Heat Steel kg").col("heat_inward_steel_quantity_kg", "Heat Inward kg")
            .col("heat_remaining_planned_steel_quantity_kg", "Heat Remaining Plan kg").col("committed_steel_quantity_kg", "Committed kg")
            .col("heat_balance_quantity_kg", "Heat Balance kg").col("heat_balance_status", "Balance Status")
            .col("rmtc_number", "RMTC Number").col("supplier_rmtc_number", "Supplier RMTC").col("rmtc_status", "RMTC Status")
            .col("rmtc_disposition", "RMTC Disposition").col("rmtc_steel_quantity_kg", "RMTC Steel kg").col("supplier_name", "Supplier")
            .col("part_number", "Part Number").col("part_name", "Part Description").col("automated_validation", "Automated Validation")
            .col("part_disposition", "Part Decision").col("planned_production_quantity_pcs", "Planned Qty pcs").col("input_weight_kg", "Input Wt kg")
            .col("planned_steel_quantity_kg", "Planned Steel kg").col("inward_production_quantity_pcs", "Inward Qty pcs")
            .col("inward_steel_quantity_kg", "Inward Steel kg").col("remaining_planned_steel_quantity_kg", "Remaining Plan kg")
            .readOnly().noEdit());
        list.add(new Module("heat_summary", "Heat Summary", Catalog.QUALITY, SECTION, "v_qsms_heat_summary")
            .desc("One line per heat · global, committed and available steel").order("last_activity_at.desc").status("").id("")
            .col("heat_number", "Heat Number").col("global_steel_quantity_kg", "Global Heat Steel kg").col("rmtc_count", "RMTCs")
            .col("active_rmtc_count", "Active RMTCs").col("rejected_rmtc_count", "Rejected RMTCs")
            .col("active_planned_steel_quantity_kg", "Active Planned kg").col("inward_steel_quantity_kg", "Inward Steel kg")
            .col("remaining_planned_steel_quantity_kg", "Remaining Plan kg").col("committed_steel_quantity_kg", "Committed kg")
            .col("available_unallocated_steel_quantity_kg", "Unallocated kg").col("available_steel_quantity_kg", "Available kg")
            .col("last_activity_at", "Last Activity")
            .readOnly().noEdit());
        list.add(new Module("accepted_rmtc_parts", "Accepted RMTC Parts", Catalog.QUALITY, SECTION, "v_qsms_accepted_rmtc_parts")
            .desc("Steel sources available for Material Inward").order("certificate_date.desc").status("disposition").id("")
            .col("rmtc_number", "RMTC").col("certificate_reference", "Supplier RMTC").col("certificate_date", "RMTC Date")
            .col("part_number", "Part Number").col("part_name", "Part Description").col("supplier_name", "Supplier")
            .col("steel_mill_name", "Steel Mill").col("material_grade", "Material Grade").col("heat_number", "Heat Number")
            .col("heat_code", "Heat Code").col("disposition", "RMTC Decision").col("rmtc_steel_quantity_kg", "RMTC Steel kg")
            .col("source_input_weight_kg", "Input Wt kg").col("planned_production_quantity_pcs", "Planned pcs")
            .col("inward_production_quantity_pcs", "Inward pcs").col("available_production_quantity_pcs", "Available pcs")
            .col("heat_committed_steel_quantity_kg", "Heat Committed kg").col("available_steel_quantity_kg", "Available Steel kg")
            .statuses("ACCEPTED", "ACCEPTED_UNDER_RESERVE")
            .readOnly().noEdit());
    }

    static final String[] INWARD_SLOTS = {"INWARD_COPY", "INWARD_ATTACHMENT_2", "INWARD_ATTACHMENT_3"};
    static final String[] INWARD_LABELS = {"Attachment 1 · GRN / Inward Document", "Attachment 2 · Supplier Invoice", "Attachment 3 · Supporting Document"};

    static void uploadInward(MainActivity a, JSONObject row, Runnable refresh) {
        String id = Lookups.j(row, "id");
        Api api = Api.get(a);
        new android.app.AlertDialog.Builder(a).setTitle("Material Inward attachment").setItems(INWARD_LABELS, (d, which) -> {
            String slot = INWARD_SLOTS[which];
            boolean copy = "INWARD_COPY".equals(slot);
            a.pickFile(INWARD_LABELS[which], false, file -> IncRmtcFlow.run(a, "Uploading " + file.name + "…", () -> {
                Attachments.uploadSlot(api, "MATERIAL_INWARD", id, "inward", slot, file, copy ? "inward_lots" : null, copy ? "inward_copy_path" : null);
                return "Uploaded " + Ui.pretty(slot) + ".";
            }, refresh));
        }).setNegativeButton("Back", null).show();
    }
}
