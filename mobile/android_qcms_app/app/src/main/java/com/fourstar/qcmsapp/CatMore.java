package com.fourstar.qcmsapp;

import org.json.JSONObject;

import java.util.LinkedHashMap;
import java.util.List;

/** More tab: NPD / APQP, QC tools, reports and records. */
public final class CatMore {
    private CatMore() { }

    private static final String NPD = "NPD / APQP", QC = "QC tools", REP = "Reports", REC = "Records";

    public static void register(List<Module> list) {
        // ------------------------------------------------------------------ NPD / APQP
        list.add(new Module("npd_flows", "Process Flow (NPD)", Catalog.MORE, NPD, "npd_process_flows")
            .desc("Operational sequence and checkpoints per part")
            .order("updated_at.desc").titleField("revision")
            .col("part_id", "Part").col("revision", "Revision").col("effective_date", "Effective Date").col("status", "Status").col("remarks", "Remarks")
            .statuses("ACTIVE", "DRAFT", "INACTIVE")
            .child("Operational sequence", "npd_process_flow_steps", "flow_id", "operation_no.asc", new String[][]{
                {"operation_no", "OP"}, {"process_name_snapshot", "Process"}, {"target_lead_days", "Lead days"}, {"responsible", "Responsible"}, {"remarks", "Remarks"}})
            .editor((a, id, prefill) -> new NpdFlowScreen(a, id)));

        list.add(new Module("npd_orders", "NPD Orders", Catalog.MORE, NPD, "npd_orders")
            .desc("NPD order status with process cards and checkpoints")
            .order("delivery_date.asc").titleField("order_number")
            .col("order_number", "Order").col("part_id", "Part").col("customer_id", "Customer").col("order_qty", "Order Qty")
            .col("start_date", "Start Date").col("delivery_date", "Delivery Date").col("status", "Status")
            .statuses("OPEN", "IN_PROGRESS", "ON_HOLD", "COMPLETED", "CANCELLED")
            .action("Process status & checkpoints", "", (a, row, refresh) -> a.push(new NpdOrderProgressScreen(a, row.optString("id"))))
            .child("Process status", "npd_order_steps", "npd_order_id", "operation_no.asc", new String[][]{
                {"operation_no", "OP"}, {"process_name", "Process"}, {"target_date", "Target Date"}, {"status", "Status"},
                {"completed_date", "Completed"}, {"responsible", "Responsible"}, {"remarks", "Remarks"}})
            .editor((a, id, prefill) -> new NpdOrderEditScreen(a, id, prefill)));

        list.add(new Module("apqp_projects", "APQP Projects", Catalog.MORE, NPD, "ppap_projects")
            .desc("APQP / PPAP project header and phase gates")
            .order("target_submission_date.asc").titleField("project_code")
            .col("project_code", "Project / NPD No.").col("part_id", "Part").col("customer_id", "Customer").col("submission_level", "PPAP Level")
            .col("target_submission_date", "Target Submission").col("coordinator", "Coordinator").col("completion_percent", "Completion %").col("status", "Status")
            .statuses("IN_PROGRESS", "ON_HOLD", "COMPLETED", "CANCELLED")
            .action("PPAP packages (open / create)", "", (a, row, refresh) -> PpapHomeScreen.fromApqp(a, row))   // R39 PPAP link
            .child("APQP gates / deliverables", "ppap_documents", "ppap_project_id", "sequence_no.asc", new String[][]{
                {"sequence_no", "Seq"}, {"apqp_phase", "APQP Phase"}, {"document_type", "Activity / Deliverable"}, {"document_number", "Evidence / Doc No."},
                {"owner", "Owner"}, {"due_date", "Due Date"}, {"status", "Status"}, {"approved_date", "Approved"}})
            .editor((a, id, prefill) -> new NpdApqpScreen(a, id)));

        // PFD / PFMEA / Control Plan: the website has no entry form for these tables (only Records views) -> read-only
        list.add(new Module("pfd", "Process Flow Diagrams", Catalog.MORE, NPD, "pfd_headers")
            .desc("PFD headers and steps (view only)").order("created_at.desc").titleField("document_number")
            .col("document_number", "Document No.").col("revision", "Rev").col("part_id", "Part").col("ppap_project_id", "APQP Project")
            .col("effective_date", "Effective Date").col("status", "Status").noEdit()
            .child("PFD steps", "pfd_steps", "pfd_header_id", "step_no.asc", new String[][]{
                {"step_no", "Step"}, {"step_type", "Type"}, {"location_type", "Location"}, {"process_operation", "Process / Operation"},
                {"product_characteristic", "Product Char."}, {"process_characteristic", "Process Char."}, {"control_verification", "Control / Verification"}, {"responsible", "Responsible"}}));

        list.add(new Module("pfmea", "PFMEA", Catalog.MORE, NPD, "pfmea_headers")
            .desc("Process FMEA headers and items (view only)").order("created_at.desc").titleField("document_number")
            .col("document_number", "Document No.").col("revision", "Rev").col("part_id", "Part").col("ppap_project_id", "APQP Project")
            .col("methodology", "Methodology").col("effective_date", "Effective Date").col("status", "Status").noEdit()
            .child("PFMEA items", "pfmea_items", "pfmea_header_id", "line_no.asc", new String[][]{
                {"line_no", "Line"}, {"process_step_function", "Process Step / Function"}, {"failure_mode", "Failure Mode"}, {"failure_effect", "Effect"},
                {"severity", "S"}, {"failure_cause", "Cause"}, {"occurrence", "O"}, {"detection", "D"}, {"rpn", "RPN"}, {"action_priority", "AP"},
                {"recommended_action", "Recommended Action"}, {"responsible_due", "Resp. / Due"}, {"action_taken", "Action Taken"}, {"revised_rpn", "Revised RPN"}}));

        list.add(new Module("control_plans", "Control Plans", Catalog.MORE, NPD, "control_plan_headers")
            .desc("Control plan headers and items (view only)").order("created_at.desc").titleField("document_number")
            .col("document_number", "Document No.").col("revision", "Rev").col("plan_type", "Plan Type").col("part_id", "Part")
            .col("ppap_project_id", "APQP Project").col("effective_date", "Effective Date").col("status", "Status").noEdit()
            .child("Control plan items", "control_plan_items", "control_plan_header_id", "line_no.asc", new String[][]{
                {"line_no", "Line"}, {"process_no", "Process No."}, {"process_operation", "Process / Operation"}, {"machine_equipment", "Machine"},
                {"characteristic_no", "Char. No."}, {"product_characteristic", "Product"}, {"process_characteristic", "Process"}, {"special_class", "Special"},
                {"specification_tolerance", "Spec / Tolerance"}, {"measurement_technique", "Measurement"}, {"sample_size", "Size"}, {"frequency", "Frequency"},
                {"control_method_responsibility", "Control Method"}, {"reaction_plan", "Reaction Plan"}}));

        // ------------------------------------------------------------------ QC tools
        list.add(new Module("qc_calculations", "QC Calculation Tools", Catalog.MORE, QC, "qc_calculation_records")
            .desc("Jominy, DI value and ASTM E140 hardness conversion with stored records")
            .order("created_at.desc").titleField("calculation_number")
            .col("calculation_number", "Calculation No.").col("calculation_date", "Date").col("calculation_type", "Type").col("heat_number", "Heat Number")
            .col("primary_value", "Primary").col("primary_unit", "Unit").col("result_value", "Result").col("conversion_unit", "Result Unit")
            .col("standard_reference", "Standard").col("performed_by_employee_id", "Performed By").col("status", "Status")
            .action("Show calculation details", "", (a, row, refresh) -> NpdCalcScreen.showDetails(a, row))
            .custom(a -> new NpdCalcScreen(a)).noEdit());

        // ------------------------------------------------------------------ Reports (database views)
        list.add(new Module("rep_heat_transactions", "Heat Transaction Report", Catalog.MORE, REP, "v_qsms_heat_transaction_report")
            .desc("Every steel / production movement per heat").id("").status("").order("transaction_at.desc").readOnly().noEdit()
            .col("transaction_at", "Date").col("heat_number", "Heat").col("part_number", "Part").col("part_name", "Part Name")
            .col("transaction_type", "Transaction").col("transaction_number", "Number").col("reference_number", "Reference").col("party_name", "Party")
            .col("process_name", "Process").col("steel_quantity_kg", "Steel kg").col("production_quantity_pcs", "Pcs")
            .col("movement_direction", "Direction").col("transaction_status", "Status"));

        list.add(new Module("rep_steel_ledger", "Heat Steel Ledger", Catalog.MORE, REP, "v_qsms_heat_steel_ledger")
            .desc("Steel balance per heat, RMTC and part").id("").status("").order("heat_number.asc").readOnly().noEdit()
            .col("heat_number", "Heat").col("rmtc_number", "RMTC").col("supplier_rmtc_number", "Supplier RMTC").col("supplier_name", "Supplier")
            .col("part_number", "Part").col("global_steel_quantity_kg", "Global Steel kg").col("heat_inward_steel_quantity_kg", "Heat Inward kg")
            .col("committed_steel_quantity_kg", "Committed kg").col("heat_balance_quantity_kg", "Heat Balance kg").col("heat_balance_status", "Balance Status")
            .col("planned_steel_quantity_kg", "Planned kg").col("inward_steel_quantity_kg", "Part Inward kg").col("remaining_planned_steel_quantity_kg", "Remaining Planned kg")
            .col("rmtc_status", "RMTC Status").col("part_disposition", "Part Disposition"));

        list.add(new Module("rep_heat_production", "Heat Production Summary", Catalog.MORE, REP, "v_qsms_heat_production_summary")
            .desc("Steel and accepted / rejected / hold pieces per RMTC heat").id("").status("").order("heat_number.asc").readOnly().noEdit()
            .col("rmtc_number", "RMTC").col("heat_number", "Heat").col("heat_code", "Heat Code").col("rmtc_steel_quantity_kg", "RMTC Steel kg")
            .col("planned_steel_quantity_kg", "Planned kg").col("inward_steel_quantity_kg", "Inward kg").col("committed_steel_quantity_kg", "Committed kg")
            .col("available_unallocated_steel_quantity_kg", "Unallocated kg").col("available_steel_quantity_kg", "Available kg")
            .col("accepted_production_quantity_pcs", "Accepted pcs").col("rejected_production_quantity_pcs", "Rejected pcs").col("hold_production_quantity_pcs", "Hold pcs"));

        list.add(new Module("rep_global_balance", "Heat Global Balance", Catalog.MORE, REP, "v_qsms_heat_global_balance_report")
            .desc("Global steel and OSP balance per heat").id("").status("").order("last_activity_at.desc.nullslast").readOnly().noEdit()
            .col("heat_number", "Heat").col("global_steel_quantity_kg", "Global Steel kg").col("rmtc_count", "RMTCs").col("active_rmtc_count", "Active RMTCs")
            .col("rejected_rmtc_count", "Rejected RMTCs").col("active_planned_steel_quantity_kg", "Planned kg").col("inward_steel_quantity_kg", "Inward kg")
            .col("remaining_planned_steel_quantity_kg", "Remaining Planned kg").col("committed_steel_quantity_kg", "Committed kg")
            .col("available_unallocated_steel_quantity_kg", "Unallocated kg").col("available_steel_quantity_kg", "Available kg")
            .col("osp_out_quantity_pcs", "OSP Out pcs").col("osp_inward_quantity_pcs", "OSP In pcs").col("osp_quantity_at_vendor_pcs", "At Vendor pcs")
            .col("last_activity_at", "Last Activity"));

        list.add(new Module("rep_osp_balance", "Heat OSP Balance", Catalog.MORE, REP, "v_qsms_heat_osp_balance_report")
            .desc("Released, sent to OSP, received back and at vendor per inward lot").id("").status("").order("inward_date.desc").readOnly().noEdit()
            .col("inward_number", "Inward No.").col("inward_date", "Inward Date").col("heat_number", "Heat").col("part_number", "Part")
            .col("released_quantity_pcs", "Released pcs").col("osp_out_quantity_pcs", "OSP Out pcs").col("osp_inward_quantity_pcs", "OSP In pcs")
            .col("balance_to_send_osp_pcs", "Balance to Send").col("quantity_at_osp_vendor_pcs", "At Vendor pcs").col("osp_job_count", "Jobs")
            .col("osp_processes", "Processes").col("osp_vendors", "Vendors").col("last_osp_activity_at", "Last OSP Activity"));

        list.add(new Module("rep_inward_register", "Inward Register", Catalog.MORE, REP, "v_qsms_inward_register")
            .desc("Material inward with RMTC, supplier and quality status").order("inward_date.desc").titleField("inward_number").readOnly().noEdit()
            .col("inward_number", "Inward No.").col("inward_date", "Date").col("part_number", "Part").col("supplier_name", "Supplier")
            .col("heat_number", "Heat").col("heat_code", "Heat Code").col("rmtc_number", "RMTC").col("material_grade", "Grade")
            .col("quantity_received", "Received").col("quantity_accepted", "Accepted").col("quantity_rejected", "Rejected")
            .col("steel_quantity_kg", "Steel kg").col("quality_disposition", "Quality Disposition").col("status", "Status"));

        list.add(new Module("rep_rmtc_usage", "Heat RMTC Usage", Catalog.MORE, REP, "v_qsms_heat_rmtc_usage")
            .desc("Planned vs inward steel per RMTC part approval").id("").status("").order("created_at.desc").readOnly().noEdit()
            .col("heat_number", "Heat").col("rmtc_number", "RMTC").col("rmtc_status", "RMTC Status").col("supplier_name", "Supplier")
            .col("part_number", "Part").col("automated_validation", "Validation").col("part_disposition", "Part Disposition")
            .col("rmtc_steel_quantity_kg", "RMTC Steel kg").col("planned_production_quantity_pcs", "Planned pcs").col("input_weight_kg", "Input Wt kg")
            .col("planned_steel_quantity_kg", "Planned kg").col("inward_production_quantity_pcs", "Inward pcs").col("inward_steel_quantity_kg", "Inward kg")
            .col("remaining_planned_steel_quantity_kg", "Remaining kg"));

        // ------------------------------------------------------------------ Records
        list.add(new Module("deletion_requests", "Deletion Requests", Catalog.MORE, REC, "qcms_delete_requests")
            .desc("Approved records are deleted only after Admin approval").order("requested_at.desc").titleField("record_label").readOnly().noEdit()
            .col("requested_at", "Requested").col("table_name", "Record Type").col("record_label", "Reference").col("reason", "Reason")
            .col("status", "Status").col("decided_at", "Decided").col("decision_note", "Admin Note").col("error_text", "Last Error")
            .statuses("PENDING", "FAILED", "EXECUTED", "REJECTED")
            .action("Approve & delete", "status=PENDING|FAILED", (a, row, refresh) -> decide(a, row, true, refresh))
            .action("Reject", "status=PENDING|FAILED", (a, row, refresh) -> decide(a, row, false, refresh))
            .action("View record data", "", (a, row, refresh) -> {
                LinkedHashMap<String, String> head = new LinkedHashMap<>();
                head.put("Record Type", NpdDeletedScreen.tableLabel(Lookups.j(row, "table_name")));
                head.put("Reference", Lookups.j(row, "record_label"));
                head.put("Reason", Lookups.j(row, "reason"));
                head.put("Status", Ui.pretty(Lookups.j(row, "status")));
                a.push(new NpdDeletedScreen.NpdDataScreen(a, "Deletion request", Lookups.j(row, "record_label"), head, row.optJSONObject("record_snapshot"), "Record data"));
            }));

        list.add(new Module("deleted_records", "Deleted Records", Catalog.MORE, REC, "")
            .desc("Archive of deleted records with their data, who deleted / approved and why")
            .custom(NpdDeletedScreen::new).readOnly().noEdit());

        list.add(new Module("activity_log", "User Activity Log", Catalog.MORE, REC, "qcms_user_activity_log")
            .desc("Who created, changed or deleted what and when").order("occurred_at.desc").status("action").readOnly().noEdit()
            .col("occurred_at", "When").col("user_email_snapshot", "User").col("role_snapshot", "Role").col("department_snapshot", "Department")
            .col("action", "Action").col("module_key", "Module").col("table_name", "Table").col("row_id", "Row"));

        list.add(new Module("email_outbox", "Email Outbox", Catalog.MORE, REC, "qcms_notification_outbox")
            .desc("Notification e-mails and their delivery status").order("created_at.desc").titleField("subject").readOnly().noEdit()
            .col("created_at", "Created").col("event_key", "Event").col("recipient_email", "To").col("subject", "Subject")
            .col("status", "Status").col("attempts", "Attempts").col("sent_at", "Sent").col("last_error", "Last Error")
            .statuses("PENDING", "SENDING", "SENT", "FAILED", "CANCELLED"));
    }

    /** Admin decision on a deletion request (core/delete_approval.decide) after password confirmation. */
    private static void decide(MainActivity a, JSONObject row, boolean approve, Runnable refresh) {
        Api api = Api.get(a);
        if (!api.isAdmin()) { a.toast("Only the QCMS Administrator can approve or reject deletion requests."); return; }
        String label = NpdDeletedScreen.tableLabel(Lookups.j(row, "table_name")) + " " + Lookups.j(row, "record_label");
        a.askText(approve ? "Approve & delete " + label : "Reject deletion of " + label, "Admin note (optional)", approve ? "Approve & delete" : "Reject", false, note ->
            a.confirmPassword("Confirm with your password", () -> Api.async(() -> {
                JSONObject args = new JSONObject();
                args.put("p_request_id", row.optString("id"));
                args.put("p_approve", approve);
                args.put("p_note", note.isEmpty() ? JSONObject.NULL : note);
                String body = api.rpc("qcms_decide_delete_request", args).trim();
                return body.startsWith("{") ? new JSONObject(body) : new JSONObject();
            }, (res, err) -> {
                if (err != null) { a.toast(Api.message(err)); return; }
                String status = res.optString("status");
                if (!approve) a.toast("Request rejected; the record stays.");
                else if ("EXECUTED".equals(status)) a.toast("Deleted. The record is kept in Deleted Records.");
                else a.toast("Deletion failed: " + res.optString("error", status) + ". Handle the linked transactions, then approve again.");
                refresh.run();
            })));
    }
}
