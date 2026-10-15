package com.fourstar.qcmsapp;

import org.json.JSONObject;

import java.util.List;

/**
 * Quality tab: Calibration & gauges (quality assets, calibration / validation records, part / process links,
 * standard room inspections) and Complaints (customer / supplier) - native screens of the website pages
 * calibration_validation.py, reference_master.py (quality_assets) and complaints.py.
 */
public final class CatCalib {
    private CatCalib() { }

    private static final String CAL = "Calibration & gauges";
    private static final String CMP = "Complaints";

    public static void register(List<Module> list) {
        // ---------------------------------------------------------------- calibration status (existing screen)
        list.add(new Module("asset_status", "Calibration Status", Catalog.QUALITY, CAL, "quality_assets")
            .desc("Gauges · instruments · equipment · overdue / due in 30 days")
            .custom(AssetsScreen::new)
            .readOnly().noEdit());

        // ---------------------------------------------------------------- quality asset master
        list.add(new Module("quality_assets", "Quality Assets", Catalog.QUALITY, CAL, "quality_assets")
            .desc("Instruments, equipment, gauges, fixtures, jigs, masters and reference standards")
            .order("asset_code.asc")
            .titleField("asset_number")
            .col("asset_code", "Master code")
            .col("asset_number", "Asset number")
            .col("asset_name", "Asset name")
            .col("asset_type", "Asset type")
            .col("service_type", "Control type")
            .col("location", "Location")
            .col("next_due_date", "Next calibration due")
            .col("next_validation_due_date", "Next validation due")
            .col("status", "Record status")
            .statuses("ACTIVE", "INACTIVE", "BLOCKED")
            .editor(CalAssetEditor::new)
            .action("Record calibration / validation", "status=ACTIVE", (a, row, refresh) ->
                a.push(new CalRecordEditor(a, null, prefill("asset_id", Lookups.j(row, "id")))))
            .action("Add Part / Process link", "status=ACTIVE;asset_type=GAUGE|FIXTURE|JIG", (a, row, refresh) ->
                a.push(new CalLinkEditor(a, null, prefill("asset_id", Lookups.j(row, "id")))))
            .action("Deactivate asset", "status=ACTIVE|BLOCKED", (a, row, refresh) ->
                a.confirm("Deactivate " + Lookups.j(row, "asset_name") + "?", "The asset is set to INACTIVE and no longer offered for new records.", "Deactivate", () ->
                    Api.async(() -> Api.get(a).update("quality_assets", Lookups.j(row, "id"), new JSONObject().put("status", "INACTIVE")), (r, err) -> {
                        if (err != null) { a.toast(Api.message(err)); return; }
                        Lookups.invalidate();
                        a.toast("Record deactivated successfully.");
                        refresh.run();
                    })))
            .child("Calibration / validation history", "quality_asset_calibration_records", "asset_id", "service_date.desc", new String[][]{
                {"service_date", "Service date"}, {"record_type", "Type"}, {"result", "Result"}, {"link_id", "Part / Process link"},
                {"certificate_number", "Certificate"}, {"report_number", "Report"}, {"calibration_agency", "Agency"},
                {"next_due_date", "Next due"}, {"status", "Status"}})
            .child("Part / Process links", "quality_asset_part_process_links", "asset_id", "next_due_date.asc", new String[][]{
                {"part_id", "Part"}, {"process_id", "Process"}, {"service_type", "Control"}, {"frequency_days", "Frequency days"},
                {"last_service_date", "Last service"}, {"next_due_date", "Next due"}, {"status", "Status"}})
            .attach("QUALITY_ASSET", "quality_assets")
            .slots("GAUGE_FIXTURE_DRAWING", "ASSET_PHOTOGRAPH", "ASSET_REFERENCE_DOCUMENT"));

        // ---------------------------------------------------------------- calibration / validation records
        list.add(new Module("calibration_records", "Calibration / Validation", Catalog.QUALITY, CAL, "quality_asset_calibration_records")
            .desc("Service records · next due date from the controlled frequency")
            .order("service_date.desc")
            .titleField("report_number")
            .col("service_date", "Service date")
            .col("asset_id", "Asset")
            .col("link_id", "Part / Process link")
            .col("record_type", "Record type")
            .col("result", "Result")
            .col("report_number", "Report number")
            .col("certificate_number", "Certificate number")
            .col("calibration_agency", "Agency")
            .col("performed_by_employee_id", "Performed by")
            .col("next_due_date", "Next due")
            .col("status", "Status")
            .statuses("VALID", "PENDING", "REJECTED")
            .editor(CalRecordEditor::new)
            .attach("CALIBRATION_RECORD", "calibration_records")
            .slots("CALIBRATION_VALIDATION_REPORT", "CALIBRATION_CERTIFICATE"));

        // ---------------------------------------------------------------- part / process links
        list.add(new Module("asset_part_links", "Part / Process Links", Catalog.QUALITY, CAL, "quality_asset_part_process_links")
            .desc("Gauge / fixture / jig applicability per Part and Process with frequency and due date")
            .order("next_due_date.asc")
            .col("asset_id", "Gauge / Fixture")
            .col("part_id", "Part")
            .col("process_id", "Process")
            .col("service_type", "Control")
            .col("frequency_days", "Frequency days")
            .col("last_service_date", "Last service")
            .col("next_due_date", "Next due")
            .col("responsible_employee_id", "Responsible")
            .col("characteristic_use", "Use / characteristic")
            .col("status", "Status")
            .statuses("ACTIVE", "INACTIVE")
            .editor(CalLinkEditor::new)
            .action("Record calibration / validation", "status=ACTIVE", (a, row, refresh) -> {
                JSONObject p = prefill("asset_id", Lookups.j(row, "asset_id"));
                try { p.put("link_id", Lookups.j(row, "id")); } catch (Exception ignored) { }
                a.push(new CalRecordEditor(a, null, p));
            })
            .child("Calibration / validation records", "quality_asset_calibration_records", "link_id", "service_date.desc", new String[][]{
                {"service_date", "Service date"}, {"record_type", "Type"}, {"result", "Result"}, {"certificate_number", "Certificate"},
                {"report_number", "Report"}, {"next_due_date", "Next due"}, {"status", "Status"}}));

        // ---------------------------------------------------------------- standard room
        list.add(new Module("standard_room", "Standard Room Inspection", Catalog.QUALITY, CAL, "standard_room_inspection_records")
            .desc("CMM, Counter, VMM, Roughness and other standard-room instrument inspections by Part / Heat / Batch")
            .order("inspection_date.desc")
            .titleField("report_number")
            .status("inspection_status")
            .col("inspection_date", "Date")
            .col("report_number", "Report")
            .col("instrument_asset_id", "Instrument")
            .col("instrument_type", "Type")
            .col("part_id", "Part")
            .col("process_id", "Process")
            .col("heat_number", "Heat")
            .col("batch_code", "Batch")
            .col("quantity_inspected", "Qty")
            .col("operator_employee_id", "Inspector / Operator")
            .col("inspection_status", "Inspection status")
            .statuses("PASS", "FAIL", "HOLD", "PENDING")
            .form(
                Field.date("inspection_date", "Inspection Date").req().def(Ui.today()),
                Field.text("report_number", "Report Number"),
                Field.lookup("instrument_asset_id", "Standard Room Instrument", Lookups.assets()).hint("Blank = Manual / Other Instrument"),
                Field.select("instrument_type", "Instrument Type", "CMM", "COUNTER", "VMM", "ROUGHNESS TESTER", "HEIGHT GAUGE", "PROFILE PROJECTOR",
                    "ROUNDNESS TESTER", "CONTOUR TRACER", "HARDNESS TESTER", "OTHER").req().def("CMM"),
                Field.lookup("part_id", "Part Number", Lookups.parts()).req(),
                Field.lookup("process_id", "Process", Lookups.processes()).hint("Blank = General / Final Inspection"),
                Field.select("inspection_status", "Inspection Status", "PASS", "FAIL", "HOLD", "PENDING").req().def("PENDING"),
                Field.text("heat_number", "Heat Number"),
                Field.text("batch_code", "Batch Code"),
                Field.number("quantity_inspected", "Quantity Inspected").req().range(0, Double.MAX_VALUE).def(1),
                Field.text("program_reference", "CMM / VMM Program / Method Reference"),
                Field.lookup("operator_employee_id", "Inspector / Operator", Lookups.employees()).hint("Blank = Not Assigned"),
                Field.area("remarks", "Inspection Remarks"))
            // Website writes status ACTIVE on every save (no tenant_id is sent for this table - the database fills it).
            .before((a, api, values, existing) -> values.put("status", "ACTIVE"))
            .attach("STANDARD_ROOM_INSPECTION", "standard_room_inspections")
            .slots("STANDARD_ROOM_REPORT", "STANDARD_ROOM_PHOTOGRAPH"));

        // ---------------------------------------------------------------- complaints
        list.add(complaints("CUSTOMER"));
        list.add(complaints("SUPPLIER"));
    }

    private static Module complaints(String type) {
        String word = CalComplaints.partyWord(type);
        Module m = new Module("CUSTOMER".equals(type) ? "customer_complaints" : "supplier_complaints", word + " Complaints", Catalog.QUALITY, CMP, "quality_complaints")
            .desc("Controlled " + word.toLowerCase() + " complaint entry, evidence, action and follow-up")
            .filter("&complaint_type=eq." + type)
            .order("complaint_date.desc")
            .titleField("complaint_number")
            .col("complaint_number", "Complaint No.")
            .col("complaint_date", "Date")
            .col("party_id", word)
            .col("part_id", "Part")
            .col("subject", "Subject")
            .col("severity", "Severity")
            .col("heat_number", "Heat")
            .col("lot_batch_number", "Batch")
            .col("fourstar_responsible_employee_id", "Responsible")
            .col("target_closure_date", "Target closure")
            .col("root_cause_confirmed", "RCA confirmed")
            .col("debit_note_status", "Debit note")
            .col("status", "Status")
            .statuses(CalComplaints.STATUSES)
            .editor((a, id, prefill) -> new CalComplaintEditor(a, type, id, prefill))
            .action("Detailed analysis (problem · containment · 5-Why · verification)", "", (a, row, refresh) ->
                a.push(new CalComplaintAnalysis(a, Lookups.j(row, "id"))))
            .action("Add corrective action", "status!=CLOSED", (a, row, refresh) ->
                a.push(new CalComplaintAction(a, row, null)))
            .action("Update corrective action", "", (a, row, refresh) ->
                CalComplaints.pickAction(a, Api.get(a), row, refresh))
            .action("Add follow-up", "", (a, row, refresh) ->
                a.push(new CalComplaintFollowup(a, row)))
            .action("Close complaint", "status!=CLOSED", (a, row, refresh) ->
                a.push(new CalComplaintClose(a, Lookups.j(row, "id"))))
            .action("Closure details", "status=CLOSED", (a, row, refresh) ->
                a.push(new CalComplaintClose(a, Lookups.j(row, "id"))))
            .action("Controlled documents (claim · analysis evidence · 8D / closure report)", "", (a, row, refresh) ->
                CalUtil.uploadFixedSlot(a, Api.get(a), CalComplaints.ENTITY, Lookups.j(row, "id"), CalComplaints.FOLDER,
                    CalComplaints.FIXED_SLOTS, CalComplaints.FIXED_LABELS, refresh))
            .child("Corrective / preventive action plan", "quality_complaint_actions", "complaint_id", "action_no.asc", new String[][]{
                {"action_no", "No."}, {"action_type", "Type"}, {"action_description", "Action"}, {"owner_employee_id", "Four Star owner"},
                {"external_owner_name", "External owner"}, {"target_date", "Target"}, {"completion_date", "Completion"}, {"status", "Status"},
                {"evidence", "Evidence"}, {"effectiveness_result", "Effectiveness"}})
            .child("Follow-ups", "quality_complaint_followups", "complaint_id", "followup_date.desc", new String[][]{
                {"followup_date", "Date"}, {"followup_type", "Type"}, {"remarks", "Remarks / update"}, {"next_followup_date", "Next follow-up"},
                {"responsible_employee_id", "Responsible"}, {"status_after_followup", "Status after"}})
            .attach(CalComplaints.ENTITY, CalComplaints.FOLDER)
            .slots("COMPLAINT_PHOTO", "COMPLAINT_ATTACHMENT")
            .multiAttach();
        return m;
    }

    private static JSONObject prefill(String key, String value) {
        JSONObject o = new JSONObject();
        try { o.put(key, value); } catch (Exception ignored) { }
        return o;
    }
}
