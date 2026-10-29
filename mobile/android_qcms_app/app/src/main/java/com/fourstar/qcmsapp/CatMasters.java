package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.List;

/** Masters tab: Part Master (+ native child editors), materials, processes & stages, parties, company & people. */
public final class CatMasters {
    private CatMasters() { }

    private static final String T = "Masters";

    // ------------------------------------------------------------------ master definitions (core/master_definitions.py)
    static Field[] partyFields() {
        return new Field[]{
            Field.text("party_code", "Master code").req().hint("Auto-generated; editable"),
            Field.text("party_name", "Name").req().hint("Company name"),
            Field.text("country", "Country").hint("India"),
            Field.text("state", "State / Region"),
            Field.text("city", "City"),
            Field.area("address", "Address"),
            Field.text("contact_person", "Contact person"),
            Field.text("email", "Primary Email"),
            Field.text("notification_emails", "Notification Email(s)").hint("Additional email addresses separated by comma or semicolon"),
            Field.text("phone", "Phone"),
            Field.text("tax_identifier", "GSTIN / Tax identifier"),
            Field.select("approval_status", "Approval status", "APPROVED", "PENDING", "REJECTED").req().def("APPROVED"),
            Field.select("status", "Record status", "ACTIVE", "INACTIVE").req().def("ACTIVE"),
            Field.area("remarks", "Remarks"),
        };
    }

    static MstSave.Def party(String key, String label, String... types) {
        JSONArray arr = new JSONArray();
        for (String t : types) arr.put(t);
        JSONObject fixed = new JSONObject();
        try { fixed.put("party_types", arr); } catch (Exception ignored) { }
        return new MstSave.Def(key, label, "parties").fields(partyFields()).natural("party_code").identity("party_name")
            .fixed(fixed).list("&party_types=cs.%7B" + types[0] + "%7D").auto("party_code");
    }

    static final MstSave.Def PROCESSES = new MstSave.Def("processes", "Processes", "processes").fields(
        Field.text("process_code", "Process Code").req().hint("Generated automatically; editable before saving"),
        Field.text("process_name", "Process Name").req().hint("e.g. Case Carburizing"),
        Field.select("process_type", "Process Type", "IN_HOUSE", "OUTSOURCED").req().def("IN_HOUSE"),
        Field.bool("special_process", "Special Process").def(false),
        Field.text("cqi_standard", "CQI Standard").hint("CQI-9"),
        Field.select("status", "Status", "ACTIVE", "INACTIVE").req().def("ACTIVE"),
        Field.area("remarks", "Remarks")
    ).natural("process_code").identity("process_name").auto("process_code");

    static final MstSave.Def STAGES = new MstSave.Def("inspection_stages", "Inspection Stages", "inspection_stages").fields(
        Field.text("stage_code", "Master code").req().hint("Auto-generated; editable"),
        Field.text("stage_name", "Stage name").req().hint("e.g. Final Inspection"),
        Field.integer("sequence_no", "Sequence").req().def(10),
        Field.select("status", "Record status", "ACTIVE", "INACTIVE").req().def("ACTIVE")
    ).natural("stage_code").identity("stage_name").auto("stage_code");

    static final MstSave.Def STANDARDS = new MstSave.Def("customer_standards", "Customer Standards & Specifications", "customer_standards").fields(
        Field.text("standard_code", "Standard Code").req().hint("Auto-generated; editable"),
        Field.text("standard_name", "Standard / Specification Name").req().hint("e.g. Heat Treatment Specification"),
        Field.lookup("customer_id", "Customer", Lookups.customers()).hint("Optional: leave blank for a general / industry specification"),
        Field.lookup("process_id", "Related Process", Lookups.processes()).req(),
        Field.text("author_name", "Author / Issuing Authority"),
        Field.text("revision_number", "Revision Number").req().def("00"),
        Field.date("revision_date", "Revision Date"),
        Field.select("status", "Record Status", "ACTIVE", "INACTIVE", "SUPERSEDED").req().def("ACTIVE"),
        Field.area("remarks", "Remarks")
    ).natural("customer_id", "process_id", "standard_code", "revision_number").identity("standard_code", "standard_name").auto("standard_code");

    private static Module master(List<Module> list, Module m, MstSave.Def def) {
        MstForm.Spec spec = MstForm.Spec.of(def);
        m.form(def.fields.toArray(new Field[0]));   // canCreate() + field list for reference
        m.editor((a, id, prefill) -> new MstForm(a, m, id, prefill, spec));
        list.add(m);
        return m;
    }

    private static Module.Action push(Opener o) { return (a, row, refresh) -> a.push(o.open(a, row)); }
    private interface Opener { Screen open(MainActivity a, JSONObject row); }

    public static void register(List<Module> list) {
        // ================================================================ Parts
        Module parts = new Module("parts", "Part Master", Catalog.MASTERS, "Parts", "parts")
            .desc("Part identity, controlled drawings and all RMTC validation grids")
            .order("part_number.asc").titleField("part_number")
            .col("part_number", "Part Number").col("fsi_part_number", "FSI Part Number").col("part_name", "Part Description")
            .col("customer_id", "Customer").col("material_grade_id", "Material Grade").col("hsn_sac_code", "HSN / SAC")
            .col("finished_weight_kg", "Finish Weight kg").col("drawing_number", "Drawing").col("drawing_revision", "Revision").col("status", "Status")
            .statuses("ACTIVE", "INACTIVE")
            .action("Raw material details", "", push((a, row) -> new MstPartRmScreen(a, row)))
            .action("Supplier technical data", "", (a, row, refresh) -> MstPartGrid.chooseRaw(a, row, raw -> a.push(new MstPartTechScreen(a, row, raw))))
            .action("Price history", "", (a, row, refresh) -> MstPartGrid.chooseRaw(a, row, raw -> a.push(new MstPartPriceScreen(a, row, raw))))
            .action("Approved sources", "", push((a, row) -> new MstPartSourcesScreen(a, row)))
            .action("Jominy requirements", "", push((a, row) -> new MstPartJominyScreen(a, row)))
            .action("Metallurgical requirements", "", push((a, row) -> new MstPartMetScreen(a, row)))
            .action("Standards", "", push((a, row) -> new MstPartStandardsScreen(a, row)))
            .action("Controlled drawings", "", push((a, row) -> new MstPartDrawingsScreen(a, row)))
            // R39 (web R38): Part processes & drawings, ECN / PCN of the Part, Sections applicable (MstPartSections hides N/A sections)
            .action("Part processes & drawings", "", push((a, row) -> new MstPartProcessScreen(a, row)))
            .action("ECN / PCN of this Part", "", (a, row, refresh) -> a.push(new EcnRegisterScreen(a, row.optString("id"))))
            .action("Sections applicable", "", push((a, row) -> new MstPartSections(a, row)))
            .child("Part processes", "part_process_routes", "part_id", "operation_no.asc",
                new String[][]{{"operation_no", "Op No."}, {"process_id", "Process"}, {"is_mandatory", "Mandatory"}, {"source_type", "Source"},
                    {"remarks", "Remarks"}, {"status", "Status"}})
            .child("Approved / alternate grades", "part_material_grade_links", "part_id", "is_primary.desc",
                new String[][]{{"material_grade_id", "Material Grade"}, {"is_primary", "Primary"}, {"status", "Status"}})
            .child("Raw material details", "part_raw_material_details", "part_id", "sequence_no.asc",
                new String[][]{{"supplier_id", "Supplier"}, {"material_section_name", "Raw Material Type"}, {"source_part_id", "Source Part"},
                    {"material_grade_id", "Grade"}, {"section_size", "Section Size"}, {"forging_route", "Forging Route"}, {"forging_weight_kg", "Forging kg"},
                    {"gross_weight_kg", "Gross kg"}, {"input_weight_kg", "Input kg"}, {"lead_time_days", "Lead days"}, {"hsn_sac_code", "HSN/SAC"}, {"status", "Status"}})
            .child("Approved sources", "part_supplier_links", "part_id", "created_at.asc",
                new String[][]{{"source_code", "Code"}, {"supplier_id", "Supplier"}, {"steel_mill_id", "Steel Mill"}, {"supplier_part_number", "Supplier Part No."},
                    {"approval_reference", "Approval Reference"}, {"valid_from", "Valid From"}, {"valid_to", "Valid To"}, {"approved", "Approved"}})
            .child("Supplier technical data", "part_raw_material_technical_data", "part_id", "sequence_no.asc",
                new String[][]{{"supplier_id", "Supplier"}, {"heading", "Heading"}, {"value_text", "Value"}, {"include_on_po", "Include on PO"}, {"status", "Status"}})
            .child("Price history", "part_supplier_price_history", "part_id", "start_date.asc",
                new String[][]{{"supplier_id", "Supplier"}, {"start_date", "Start Date"}, {"end_date", "End Date"}, {"price", "Basic Rate"}, {"freight", "Freight"},
                    {"tool_cost", "Tool Cost"}, {"packing_forwarding", "P&F"}, {"profit", "Profit"}, {"icc_rejection", "ICC/Rej."}, {"currency", "Currency"},
                    {"uom", "UOM"}, {"status", "Status"}})
            .child("Jominy requirements", "part_jominy_requirements", "part_id", "sequence_no.asc",
                new String[][]{{"distance_label", "Distance (inch)"}, {"minimum_hrc", "Minimum HRC"}, {"maximum_hrc", "Maximum HRC"}, {"status", "Status"}})
            .child("Metallurgical requirements (final dispatch)", "part_metallurgical_requirements", "part_id", "sequence_no.asc",
                new String[][]{{"parameter_name", "Parameter"}, {"characteristic_type", "Type"}, {"specification_text", "Text Specification"},
                    {"minimum_spec", "Minimum"}, {"maximum_spec", "Maximum"}, {"status", "Status"}})
            .child("Linked standards", "part_standard_links", "part_id", "sequence_no.asc",
                new String[][]{{"standard_id", "Standard"}, {"sequence_no", "Sequence"}, {"status", "Status"}})
            .child("Controlled drawings", "document_attachments", "entity_id", "created_at.desc",
                new String[][]{{"document_type", "Drawing Type"}, {"drawing_number", "Drawing Number"}, {"revision", "Revision"}, {"revision_date", "Revision Date"},
                    {"status", "Status"}, {"file_name", "File"}});
        parts.editor((a, id, prefill) -> new MstPartScreen(a, parts, id));
        list.add(parts);

        list.add(new Module("part_rm_viewer", "Part RM details", Catalog.MASTERS, "Parts", "part_raw_material_details")
            .desc("Search a Part and view its Raw Material details").readOnly().noEdit()
            .custom(a -> new PartRmScreen(a)));

        // ================================================================ Materials
        Module grades = new Module("material_grades", "Material Grades", Catalog.MASTERS, "Materials", "material_grades")
            .desc("Material header and chemical composition").order("grade_code.asc").titleField("grade_code")
            .col("grade_code", "Material Grade").col("material_number", "Material Number").col("standard", "Standard").col("revision", "Revision")
            .col("effective_date", "Effective Date").col("status", "Status").statuses("ACTIVE", "INACTIVE")
            .child("Chemical composition", "material_grade_elements", "material_grade_id", "element.asc",
                new String[][]{{"element", "Element"}, {"minimum", "Minimum %"}, {"maximum", "Maximum %"}, {"unit", "Unit"}, {"test_method", "Test Method"}});
        grades.editor((a, id, prefill) -> new MstGradeScreen(a, grades, id));
        list.add(grades);

        list.add(new Module("jominy_distances", "Jominy Distances", Catalog.MASTERS, "Materials", "jominy_distances")
            .desc("Controlled Jominy distances (1/16 inch → mm)").order("distance_16th.asc").titleField("distance_label")
            .col("distance_label", "Distance (inch)").col("distance_16th", "1/16 inch").col("distance_mm", "MM").col("status", "Status")
            .readOnly().noEdit());

        // ================================================================ Processes & stages
        Module processes = new Module("processes", "Process Master", Catalog.MASTERS, "Processes & stages", "processes")
            .desc("In-house and outsourced processes, special process and CQI controls").order("process_code.asc").titleField("process_name")
            .col("process_code", "Process Code").col("process_name", "Process Name").col("process_type", "Process Type")
            .col("special_process", "Special Process").col("cqi_standard", "CQI Standard").col("status", "Status").statuses("ACTIVE", "INACTIVE")
            .child("Related customer standards", "customer_standards", "process_id", "standard_code.asc",
                new String[][]{{"standard_code", "Code"}, {"standard_name", "Standard / Specification"}, {"customer_id", "Customer"},
                    {"revision_number", "Revision"}, {"revision_date", "Revision Date"}, {"status", "Status"}});
        master(list, processes, PROCESSES);

        master(list, new Module("inspection_stages", "Inspection Stages", Catalog.MASTERS, "Processes & stages", "inspection_stages")
            .desc("Incoming, setup, stage, OSP receipt and final inspection sequence").order("sequence_no.asc").titleField("stage_name")
            .col("sequence_no", "Sequence").col("stage_code", "Stage Code").col("stage_name", "Stage Name").col("status", "Status")
            .statuses("ACTIVE", "INACTIVE"), STAGES);

        // ================================================================ Parties
        partyModule(list, "customers", "Customers", "Customer identity, location and approval status", party("customers", "Customers", "CUSTOMER"), true);
        partyModule(list, "suppliers", "Suppliers", "Raw material, forging and bought-out suppliers", party("suppliers", "Suppliers", "SUPPLIER"), false);
        partyModule(list, "steel_mills", "Steel Mills", "Approved steel-producing mills", party("steel_mills", "Steel Mills", "STEEL_MILL"), false);
        partyModule(list, "osp_vendors", "OSP Vendors", "Outside-process vendors (heat treatment, gear shaping …)", party("osp_vendors", "OSP Vendors", "OSP_VENDOR", "SUPPLIER"), false);

        // ================================================================ Company & people
        Module branches = new Module("company_branches", "Company Branches", Catalog.MASTERS, "Company & people", "company_branches")
            .desc("Company / plant / address identity used for POs and Ship-To").order("branch_code.asc").titleField("branch_name")
            .col("branch_code", "Branch Code").col("plant_code", "Plant Code").col("branch_name", "Branch Name").col("city", "City").col("state", "State")
            .col("gstin", "GSTIN").col("phone", "Phone").col("email", "Email").col("is_default", "Default").col("status", "Status")
            .statuses("ACTIVE", "INACTIVE");
        MstForm.Spec branchSpec = MstForm.Spec.custom(MstPeople::branchFields, MstPeople::saveBranch);
        branches.form(MstPeople.branchFields(null).toArray(new Field[0]));
        branches.editor((a, id, prefill) -> new MstForm(a, branches, id, prefill, branchSpec));
        list.add(branches);

        Module employees = new Module("employees", "Employee Master", Catalog.MASTERS, "Company & people", "employees")
            .desc("Employee code, reporting line, experience and approval authority").order("employee_code.asc").titleField("employee_code")
            .col("employee_code", "Employee Code").col("first_name", "First Name").col("last_name", "Last Name").col("email", "Email")
            .col("department", "Department").col("designation", "Designation").col("plant", "Plant").col("mobile_number", "Mobile")
            .col("reports_to_employee_id", "Reports To").col("status", "Status").statuses("ACTIVE", "INACTIVE", "LEFT")
            .action("Photo, reporting line, escalation & approval routes", "", (a, row, refresh) -> a.push(new EmpDetailsScreen(a, Lookups.j(row, "id"))))
            .action("Upload / replace employee photo", "", MstPeople::uploadPhoto)
            .action("View employee photo", "photo_storage_path!=EMPTY", (a, row, refresh) -> MstPeople.viewPhoto(a, row));
        MstForm.Spec empSpec = MstForm.Spec.custom(MstPeople::employeeFields, MstPeople::saveEmployee)
            .note("Employee code is generated automatically when blank and remains editable");
        employees.form(MstPeople.employeeFields(null).toArray(new Field[0]));
        employees.editor((a, id, prefill) -> new MstForm(a, employees, id, prefill, empSpec));
        list.add(employees);

        master(list, new Module("customer_standards", "Customer Standards", Catalog.MASTERS, "Company & people", "customer_standards")
            .desc("Standards bank: customer / process standards and specifications with controlled file").order("standard_code.asc").titleField("standard_name")
            .col("standard_code", "Standard Code").col("standard_name", "Standard / Specification").col("customer_id", "Customer").col("process_id", "Related Process")
            .col("author_name", "Author").col("revision_number", "Revision").col("revision_date", "Revision Date").col("status", "Status")
            .statuses("ACTIVE", "INACTIVE", "SUPERSEDED")
            .attach("CUSTOMER_STANDARD", "customer_standards").slots("STANDARD_DOCUMENT"), STANDARDS);
    }

    private static void partyModule(List<Module> list, String key, String title, String desc, MstSave.Def def, boolean customer) {
        Module m = new Module(key, title, Catalog.MASTERS, "Parties", "parties")
            .desc(desc).filter(def.listFilter).order("party_code.asc").titleField("party_name")
            .col("party_code", "Master Code").col("party_name", "Name").col("country", "Country").col("city", "City")
            .col("contact_person", "Contact Person").col("approval_status", "Approval Status").col("status", "Status")
            .statuses("ACTIVE", "INACTIVE");
        if (customer) m.child("Parts of this customer", "parts", "customer_id", "part_number.asc",
            new String[][]{{"part_number", "Part Number"}, {"fsi_part_number", "FSI Part Number"}, {"part_name", "Part Description"}, {"status", "Status"}});
        master(list, m, def);
    }
}
