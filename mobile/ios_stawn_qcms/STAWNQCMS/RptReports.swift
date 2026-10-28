import UIKit
import CoreImage

/// Builds the website's controlled reports (core/reporting.py) from the same Supabase rows the website reads.
/// Swift port of the Android RptReports: MetLAB, Bend Test, Dimensional, Material Inward, RMTC, Complaint,
/// Calibration, Standard Room, QC Calculation; every other record prints as the Universal Record PDF.
enum RptReports {
    static var api: Api { Api.shared }

    static func dedicated(_ table: String) -> Bool {
        ["lab_tests", "inspection_reports", "rmtc_approvals", "inward_lots", "quality_complaints", "quality_asset_calibration_records",
         "standard_room_inspection_records", "qc_calculation_records"].contains(table)
    }

    static func forRecord(_ m: QModule, _ id: String) async throws -> RptDoc {
        switch m.table {
        case "lab_tests": return try await metlab(id)
        case "inspection_reports": return try await dimensional(id)
        case "rmtc_approvals": return try await rmtc(id)
        case "inward_lots": return try await inward(id)
        case "quality_complaints": return try await complaint(id)
        case "quality_asset_calibration_records": return try await calibration(id)
        case "standard_room_inspection_records": return try await standardRoom(id)
        case "qc_calculation_records": return try await qcCalculation(id)
        default: return try await universal(m, id)
        }
    }

    // ------------------------------------------------------------------ helpers
    static func s(_ v: Any?) -> String { J.str(v) }
    static func truthy(_ v: Any?) -> Bool { J.truthy(v) }
    static func or(_ values: Any?...) -> Any? {
        for v in values where J.truthy(v) { return v }
        return values.last ?? nil
    }
    static func v(_ o: Any?) -> String { RptDoc.v(o) }
    static func raw(_ o: Any?) -> String { RptDoc.raw(o) }
    static func dash(_ o: Any?) -> String { let r = raw(o); return r.isEmpty ? "-" : r }
    static func present(_ o: Any?) -> Bool { !J.isNull(o) }

    /// Table row: Strings as written, other values like str(value).
    static func row(_ cells: Any?...) -> [String] { cells.map { ($0 as? String) ?? raw($0) } }
    /// Label / value row: values through _display_value.
    static func vrow(_ cells: Any?...) -> [String] { cells.map { v($0) } }

    static func employees(_ ids: Any?...) async -> [String: Row] {
        var want: [String] = []
        for i in ids { let x = s(i); if !x.isEmpty && !want.contains(x) { want.append(x) } }
        if want.isEmpty { return [:] }
        var out: [String: Row] = [:]
        for e in await api.list("employees?select=*&id=in.(\(want.joined(separator: ",")))&limit=20") { out[s(e["id"])] = e }
        return out
    }

    /// _employee_name: "code - first last".
    static func emp(_ emps: [String: Row], _ id: Any?) -> String {
        guard let e = emps[s(id)] else { return "-" }
        let name = "\(s(e["first_name"])) \(s(e["last_name"]))".trimmingCharacters(in: .whitespaces)
        let code = s(e["employee_code"])
        if !code.isEmpty && !name.isEmpty { return "\(code) - \(name)" }
        return !name.isEmpty ? name : (!code.isEmpty ? code : "-")
    }

    private static var plant: String?

    static let presets: [String: [String: Any]] = [
        "B1": ["accent": "#0B6E70", "bar": "fill", "rule": "#C9D6D6", "remark": "#9A3412", "conclusion": "#166534"],
        "B2": ["accent": "#0B6E70", "bar": "underline", "rule": "#C9D6D6", "remark": "#9A3412", "conclusion": "#166534"],
        "B3": ["accent": "#0B6E70", "bar": "outline", "rule": "#C9D6D6", "remark": "#9A3412", "conclusion": "#166534"],
        "B4": ["accent": "#334155", "bar": "fill", "rule": "#CBD5E1", "remark": "#0B6E70", "conclusion": "#166534"],
        "B5": ["accent": "#0B6E70", "bar": "fill", "rule": "#C9D6D6", "remark": "#9A3412", "conclusion": "#166534"],
    ]

    /// core/print_designer.read_layout + normalize_layout, then the theme is applied.
    static func theme(_ d: RptDoc, _ doc: String) async {
        var base: [String: Any] = ["preset": "B1", "accent": "#0B6E70", "bar": "fill", "rule": "#9AA5A5", "remark": "#9A3412", "conclusion": "#166534",
                                   "body_pt": 8.6, "heading_pt": 10.5, "labels": [String: String](), "company_name": "", "footer_text": ""]
        let rows = await api.list("master_value_catalog?select=value_text&field_key=eq.\(Api.enc("qcms.print.layout." + doc))&status=eq.ACTIVE&order=last_used_at.desc&limit=1")
        if let text = rows.first.map({ s($0["value_text"]) }), let data = text.data(using: .utf8),
           let saved = (try? JSONSerialization.jsonObject(with: data)) as? Row {
            let p = s(saved["preset"]).uppercased()
            if let preset = presets[p], p != "B1" { for (k, v) in preset { base[k] = v }; base["preset"] = p }
            for (k, value) in saved {
                switch k {
                case "accent", "rule", "remark", "conclusion":
                    if let h = value as? String, UIColor(hexString: h) != nil { base[k] = h.uppercased() }
                case "bar":
                    if let b = value as? String, ["fill", "underline", "outline"].contains(b) { base[k] = b }
                case "body_pt", "heading_pt":
                    if let n = J.num(value) { base[k] = max(6, min(14, n)) }
                case "labels":
                    var out: [String: String] = [:]
                    for (lk, lv) in J.obj(value) { let kk = lk.trimmingCharacters(in: .whitespaces), vv = s(lv); if !kk.isEmpty && !vv.isEmpty { out[kk] = vv } }
                    base["labels"] = out
                case "company_name", "footer_text":
                    base[k] = String(s(value).prefix(120))
                default: break
                }
            }
        }
        d.applyLayout(base)
        if plant == nil {
            plant = "D9"
            if let t = await api.list("tenants?select=plant_code&limit=1").first, !s(t["plant_code"]).isEmpty { plant = s(t["plant_code"]) }
        }
        d.plantCode = plant ?? "D9"
    }

    /// Microstructure / evidence photographs (one per slot, newest file of each type).
    static func slotPhotos(entity: String, id: String, prefix: String, record: Row, slots: Int) async -> [RptPhoto] {
        var byType: [String: Row] = [:]
        for a in await api.list("document_attachments?select=*&entity_type=eq.\(entity)&entity_id=eq.\(Api.enc(id))&status=eq.ACTIVE&order=created_at.asc&limit=250") {
            byType[s(a["document_type"])] = a
        }
        var out: [RptPhoto] = []
        for slot in 1...slots {
            var data: Data? = nil
            if let a = byType["\(prefix)\(slot)"] { data = try? await api.download(s(a["object_path"])) }
            let cap = s(record["microstructure_caption_\(slot)"])
            out.append(RptPhoto(caption: cap.isEmpty ? "Microstructure Photo \(slot)" : cap, data: data))
        }
        return out
    }

    static func ospJob(_ record: Row) async -> Row {
        guard truthy(record["osp_job_id"]) else { return [:] }
        return await api.list("v_qsms_osp_register?select=*&id=eq.\(Api.enc(s(record["osp_job_id"])))&limit=1").first ?? [:]
    }

    static func titleWords(_ x: String) -> String { Fmt.title(x.replacingOccurrences(of: "_", with: " ")) }

    // ================================================================== MetLAB (metlab_record_pdf_bytes)
    static func metlab(_ id: String) async throws -> RptDoc {
        let record = await api.one("lab_tests", id)
        if record.isEmpty { throw ApiError(status: 404, message: "MetLAB report not found.") }
        var results = J.obj(record["results"])
        if rawMaterial(record) { results = await rawMaterialResults(record, results) }
        let part = await api.one("parts", record["part_id"])
        let inward = await api.one("inward_lots", record["inward_lot_id"])
        let supplier = await api.one("parties", or(record["supplier_id"], inward["supplier_id"]))
        let grade = await api.one("material_grades", or(record["material_grade_id"], part["material_grade_id"]))
        let customer = await api.one("parties", or(record["customer_id"], part["customer_id"]))
        let process = await api.one("processes", record["process_id"])
        let stage = await api.one("inspection_stages", record["inspection_stage_id"])
        let osp = await ospJob(record)
        let ospVendor = await api.one("parties", or(record["osp_vendor_id"], osp["vendor_id"]))
        let emps = await employees(record["prepared_by_employee_id"], record["validated_by_employee_id"], record["approved_by_employee_id"])
        let photos = await slotPhotos(entity: "METLAB_REPORT", id: id, prefix: "MICROSTRUCTURE_", record: record, slots: 4)
        let method = s(or(results["inspection_method"], "GENERAL_METLAB")).uppercased()
        if method == "BEND_TEST" { return await bend(record, part, customer, grade, inward, osp, emps, results, photos) }

        let scope = s(or(record["inspection_scope"], "MATERIAL_INWARD"))
        let isOsp = scope.hasPrefix("OSP_") || truthy(record["osp_job_id"])
        let title = isOsp ? "OSP METALLURGICAL TEST REPORT" : (scope == "FINAL_DISPATCH_STAGE" ? "FINAL METALLURGICAL TEST REPORT" : "RAW MATERIAL METALLURGICAL TEST REPORT")
        let d = RptDoc(title).file("QCMS_MetLAB_\(s(record["report_number"]))")
        await theme(d, "METLAB")
        d.bar(title)
        let ospVendorName = or(ospVendor["party_name"], osp["vendor_name"], "-")
        let supplyCondition = or(osp["process_name"], process["process_name"], record["layout_name_snapshot"])
        let qty: Any? = scope == "OSP_SAMPLE" ? osp["sample_quantity"] : (isOsp ? osp["quantity_received"] : record["production_quantity_pcs"])
        let processName = or(process["process_name"], record["process_specification_snapshot"])
        let meta: [[String]] = [
            vrow("Report No.", record["report_number"], "Date", record["test_date"]),
            vrow("Part Name", part["part_name"], "Part No.", part["part_number"]),
            vrow("Customer", customer["party_name"], "Supplier", supplier["party_name"]),
            vrow("OSP Vendor", ospVendorName, "Material Used", or(grade["grade_code"], grade["grade_name"])),
            vrow("Supply / Process Condition", or(record["supply_condition"], supplyCondition), "Process", processName),
            vrow("Supplier Invoice / Reference", record["supplier_reference_number"], "Quantity (pcs)", or(record["production_quantity_pcs"], qty)),
            vrow("Heat Number", or(record["heat_number"], inward["heat_number"], osp["heat_number"]), "Heat Code", or(record["heat_code"], inward["heat_code"])),
            vrow("Supplier / HT / OSP Batch", or(record["vendor_batch_number_snapshot"], osp["vendor_batch_number"]), "Internal / FSI Batch", record["batch_number"]),
            vrow("Inspection Stage", or(stage["stage_name"], titleWords(scope)), "Process", processName),
            vrow("Drawing / Revision", "\(dash(part["drawing_number"])) / \(dash(part["drawing_revision"]))", "Specification Reference", record["specification_reference"]),
            vrow("Sample / Reference", or(record["reference_text"], record["sample_reference"], inward["inward_number"], osp["sample_reference"]), "Report Layout", record["layout_name_snapshot"]),
        ]
        d.labeled(meta, [32, 65, 32, 65], 0, 2)

        var test: [[String]] = [row("Sr.", "Parameter", "Specification", "Observations", "Unit", "Result")]
        var seq = 1
        for r in J.rows(results["rows"]) {
            var spec: Any? = r["specification"]
            if !truthy(spec) {
                let lo = r["lower_spec"], hi = r["upper_spec"]
                if present(lo) || present(hi) {
                    spec = "\(present(lo) ? raw(lo) : "") - \(present(hi) ? raw(hi) : "")".trimmingCharacters(in: CharacterSet(charactersIn: " -"))
                }
            }
            test.append(row(or(r["sequence_no"], seq), r["parameter"], spec, r["actual_value"], r["unit"], r["result"]))
            seq += 1
        }
        for r in J.rows(results["requirement_rows"]) {
            test.append(row(seq, r["requirement_name"], r["requirement_value"], r["actual_value"], r["unit"], r["result"]))
            seq += 1
        }
        if test.count == 1 { test.append(row(1, "Metallurgical requirements", "As approved inspection layout", "No result rows recorded", "", "NOT_EVALUATED")) }
        d.space(1.4)
        d.bar("METALLURGICAL TEST RESULTS")
        d.grid(test, [12, 54, 50, 46, 14, 18], 5)

        caseDepth(d, results)
        let chem = J.rows(results["chemistry_rows"])
        if !chem.isEmpty { d.sub("CHEMICAL ANALYSIS · ASTM E 415 / IS 8811"); chemistryTable(d, chem) }
        let jom = J.rows(results["jominy_rows"])
        if !jom.isEmpty {
            d.sub("HARDNESS / JOMINY TRAVERSE")
            let jr = jominyHorizontal(jom, [("Min HRC", "minimum_hrc"), ("Max HRC", "maximum_hrc"), ("RMTC HRC", "rmtc_actual_hrc"), ("MetLAB HRC", "actual_value"), ("Result", "result"), ("Remark", "remarks")])
            for band in ChemGrid.bands(jr) { d.grid(band, spread(d, band[0].count, 26)) }
        }
        d.keep(70)
        d.bar("MICROSTRUCTURE PHOTOGRAPHS")
        d.photos(photos, cols: 2, maxHmm: 46)
        references(d, results, "REFERENCE DOCUMENTS / STATEMENTS")
        let overall = or(record["disposition"], record["overall_result"], "NOT_EVALUATED")
        let conclusion = or(record["remarks"], "Overall result: " + raw(or(record["overall_result"], overall)))
        d.space(1.5)
        d.conclusion(raw(conclusion), raw(results["conclusion_remark"]), raw(overall), raw(or(record["disposition_reason"], "-")))
        d.labeledCenter([
            vrow("Prepared By", emp(emps, record["prepared_by_employee_id"]), "Validated By", emp(emps, record["validated_by_employee_id"]), "Verified & Approved By", emp(emps, record["approved_by_employee_id"])),
            vrow("Prepared / Test Date", record["test_date"], "Validated At", record["validated_at"], "Decision At", record["decision_at"]),
        ], [25, 37, 25, 37, 34, 36], 0, 2, 4)
        return d
    }

    static func rawMaterial(_ record: Row) -> Bool {
        let scope = s(record["inspection_scope"]).uppercased()
        return scope == "RAW_MATERIAL_STAGE" || scope == "MATERIAL_INWARD" || truthy(record["inward_lot_id"])
    }

    /// InspectionService.raw_material_results: only the selected Layout Master characteristics; RMTC values are reference data.
    static func rawMaterialResults(_ record: Row, _ results: Row) async -> Row {
        var clean = results
        let plan = await api.one("inspection_plans", record["layout_plan_id"])
        if !plan.isEmpty {
            let chars = await api.list("inspection_plan_characteristics?select=*&inspection_plan_id=eq.\(Api.enc(s(plan["id"])))&order=sequence_no.asc&limit=2000")
            var allowed = Set<String>()
            var caseDepth = false
            for c in chars {
                allowed.insert(s(c["id"]))
                let meta = J.obj(c["layout_metadata"])
                if truthy(meta["case_depth_traverse"]) || truthy(c["case_depth_traverse_enabled"])
                    || s(c["characteristic"]).lowercased().range(of: "\\bcase\\s+depth\\b", options: .regularExpression) != nil { caseDepth = true }
            }
            clean["rows"] = J.rows(results["rows"]).filter { allowed.contains(s($0["inspection_plan_characteristic_id"])) }
            if !caseDepth {
                clean["case_depth_applicable"] = false
                clean["case_depth_locations"] = [Any]()
                clean["case_depth_traverse"] = [Any]()
                clean["case_depth_na_reason"] = "Not applicable for this approved layout."
            }
        }
        clean["chemistry_rows"] = [Any]()
        clean["jominy_rows"] = [Any]()
        clean["requirement_rows"] = [Any]()
        return clean
    }

    static func caseDepth(_ d: RptDoc, _ results: Row) {
        let locs = J.rows(results["case_depth_locations"]), trav = J.rows(results["case_depth_traverse"])
        if truthy(results["case_depth_applicable"]) && !locs.isEmpty && !trav.isEmpty {
            let names = locs.map { s(or($0["location"], $0["name"])) }.filter { !$0.isEmpty }
            d.space(1.4)
            d.bar("CASE DEPTH / MICROHARDNESS TRAVERSE")
            var specs: [[String]] = [row("Location", "Controlled Parameter", "Specification", "Unit")]
            for l in locs { specs.append(row(or(l["location"], l["name"]), or(l["parameter"], "Case Depth"), or(l["specification"], "-"), or(l["unit"], ""))) }
            d.grid(specs, [34, 66, 72, 22])
            d.space(1.0)
            var t: [[String]] = [["Distance (mm)"] + names]
            var pts: [[(Double, Double)]] = Array(repeating: [], count: names.count)
            for r in trav {
                let readings = J.obj(r["readings"])
                var line = [raw(r["distance_mm"])]
                for (i, n) in names.enumerated() {
                    line.append(raw(readings[n]))
                    if let dist = Double(raw(r["distance_mm"])), let hv = Double(raw(readings[n])) { pts[i].append((dist, hv)) }
                }
                t.append(line)
            }
            let rest = (d.contentMm - 28) / CGFloat(max(1, names.count))
            d.grid(t, [28] + Array(repeating: rest, count: names.count))
            let chart = RptChart()
            for (i, n) in names.enumerated() where !pts[i].isEmpty { chart.names.append(n); chart.series.append(pts[i]) }
            if !chart.series.isEmpty {
                d.space(1.2)
                d.sub("CASE DEPTH TRAVERSE · Distance (mm) vs Hardness (HV)")
                d.blocks.append(chart)
            }
        } else if truthy(results["case_depth_na_reason"]) {
            d.sub("CASE DEPTH / MICROHARDNESS TRAVERSE")
            d.text("Not Applicable: " + raw(results["case_depth_na_reason"]), .normal)
        }
    }

    private static let chemOrder = ["C", "Mn", "Si", "S", "P", "Cr", "Ni", "Mo", "V", "Al", "Cu", "Nb", "Ti"]
    private static let ratioKey = "aln2ratio"

    static func chemKey(_ value: Any?) -> String {
        let t = String(s(value).unicodeScalars.filter { CharacterSet.alphanumerics.contains($0) }).lowercased()
        let alias: [String: String] = ["carbon": "c", "manganese": "mn", "silicon": "si", "sulphur": "s", "sulfur": "s", "phosphorus": "p", "chromium": "cr",
                                       "nickel": "ni", "molybdenum": "mo", "vanadium": "v", "aluminium": "al", "aluminum": "al", "copper": "cu", "niobium": "nb",
                                       "titanium": "ti", "alnratio": ratioKey, "aln2ratio": ratioKey, "alnitrogenratio": ratioKey]
        return alias[t] ?? t
    }

    // R38: horizontal chemistry / Jominy grids (elements / distances are columns; Jominy shows inch + mm).
    static func orderedChem(_ chem: [Row]) -> [Row] {
        var rank: [String: Int] = [:]
        for (i, e) in chemOrder.enumerated() { rank[chemKey(e)] = i }
        var normal: [Row] = [], extras: [Row] = [], ratio: [Row] = []
        for r in chem {
            let k = chemKey(r["element"])
            if k == ratioKey { ratio.append(r) } else if rank[k] != nil { normal.append(r) } else { extras.append(r) }
        }
        normal.sort { (rank[chemKey($0["element"])] ?? 0, s($0["element"])) < (rank[chemKey($1["element"])] ?? 0, s($1["element"])) }
        extras.sort { s($0["element"]) < s($1["element"]) }
        return normal + extras + ratio
    }

    static func chemHorizontal(_ chem: [Row], _ lines: [(String, String)]) -> [[String]] {
        let ordered = orderedChem(chem)
        var t: [[String]] = [["Element"] + ordered.map { r -> String in
            let e = s(r["element"]); return chemKey(e) == ratioKey ? "Al/N2 Ratio" : (e.contains("%") ? e : e + "%") }]
        for (label, field) in lines {
            t.append([label] + ordered.map { r -> String in let v = r[field]; return !present(v) || raw(v).isEmpty ? "-" : raw(v) })
        }
        return t
    }

    static func sixteenth(_ r: Row) -> Int {
        return ChemGrid.sixteenthOf(r)  // R38: J5/16", 5/16", J 5, J3, 5 or distance_mm
    }

    /// 1/16 inch = 1.5875 mm, two decimals half-up (J2/16" = 3.18 mm).
    static func jominyMm(_ n: Int) -> String {
        guard n > 0 else { return "-" }
        var value = Decimal(n) * Decimal(string: "1.5875")!, out = Decimal()
        NSDecimalRound(&out, &value, 2, .plain)
        return String(format: "%.2f", NSDecimalNumber(decimal: out).doubleValue)
    }

    static func jominyHorizontal(_ rows: [Row], _ lines: [(String, String)]) -> [[String]] {
        let ordered = rows.sorted { (sixteenth($0) == 0 ? 999 : sixteenth($0)) < (sixteenth($1) == 0 ? 999 : sixteenth($1)) }
        var t: [[String]] = [["Distance (inch)"] + ordered.map { r -> String in let n = sixteenth(r); return n > 0 ? "J\(n)/16\"" : raw(r["distance_label"]) }]
        t.append(["Distance (mm)"] + ordered.map { r -> String in let n = sixteenth(r); return n > 0 ? jominyMm(n) : raw(r["distance_mm"]) })
        for (label, field) in lines {
            t.append([label] + ordered.map { r -> String in
                var v: Any? = field == "__na" ? (s(r["applicability"]) == "NOT_APPLICABLE" ? "No" : "Yes") : r[field]
                if field == "actual_value" && (!present(v) || s(v).isEmpty) { v = r["actual_hrc"] }
                return !present(v) || raw(v).isEmpty ? "-" : raw(v)
            })
        }
        return t
    }

    static func spread(_ d: RptDoc, _ columns: Int, _ first: CGFloat) -> [CGFloat] {
        let n = max(2, columns)
        return [first] + Array(repeating: (d.contentMm - first) / CGFloat(n - 1), count: n - 1)
    }

    /// R38: QR image (CoreImage) of the public certificate URL of an approved RMTC.
    static func qrPNG(_ text: String) -> Data? {
        guard let filter = CIFilter(name: "CIQRCodeGenerator") else { return nil }
        filter.setValue(Data(text.utf8), forKey: "inputMessage")
        filter.setValue("M", forKey: "inputCorrectionLevel")
        guard let image = filter.outputImage?.transformed(by: CGAffineTransform(scaleX: 10, y: 10)),
              let cg = CIContext().createCGImage(image, from: image.extent) else { return nil }
        return UIImage(cgImage: cg).pngData()
    }

    static func rmtcQrUrl(_ id: String, _ record: Row) async -> String {
        let st = s(record["status"]), disp = s(record["disposition"])
        guard ["APPROVED", "PARTIALLY_APPROVED"].contains(st), ["ACCEPTED", "ACCEPTED_UNDER_RESERVE"].contains(disp) else { return "" }
        // R38: login-protected website link (no secret in the QR)
        let number = s(record["rmtc_number"])
        guard !number.isEmpty, number != "-" else { return "" }
        return "https://vf6fa9hrhxquqxmfgyy4wf.streamlit.app/rmtc-records?rmtc=" + Api.enc(number)
    }

    static func chemistryTable(_ d: RptDoc, _ chem: [Row]) {
        var rank: [String: Int] = [:]
        for (i, e) in chemOrder.enumerated() { rank[chemKey(e)] = i }
        var normal: [Row] = [], extras: [Row] = [], ratio: [Row] = []
        for r in chem {
            let k = chemKey(r["element"])
            if k == ratioKey { ratio.append(r) } else if rank[k] != nil { normal.append(r) } else { extras.append(r) }
        }
        normal.sort { (rank[chemKey($0["element"])] ?? 0, s($0["element"])) < (rank[chemKey($1["element"])] ?? 0, s($1["element"])) }
        extras.sort { s($0["element"]) < s($1["element"]) }
        let ordered = normal + extras + ratio
        let head = ["Element"] + ordered.map { r -> String in
            let e = s(r["element"])
            return chemKey(e) == ratioKey ? "Al/N2 Ratio" : (e.contains("%") ? e : e + "%")
        }
        var t: [[String]] = [head]
        for (label, field) in [("Spec. Min", "minimum_value"), ("Spec. Max", "maximum_value"), ("RMTC Achieved", "rmtc_actual_value"), ("MetLAB Achieved", "actual_value")] {
            var line = [label]
            for r in ordered {
                var val = r[field]
                if label == "RMTC Achieved" && (!present(val) || s(val).isEmpty) { val = r["source_actual_value"] }
                line.append(!present(val) || raw(val).isEmpty ? "-" : raw(val))
            }
            t.append(line)
        }
        for band in ChemGrid.bands(t) { d.grid(band, spread(d, band[0].count, 26)) }  // R38 A2: A4 bands
    }

    static func references(_ d: RptDoc, _ results: Row, _ title: String) {
        let refs = J.list(results["reference_documents"]).map { s($0) }.filter { !$0.isEmpty }
        if refs.isEmpty { return }
        d.space(1.2)
        d.sub(title)
        var r: [[String]] = [row("Sr.", "Reference")]
        for (i, x) in refs.enumerated() { r.append(row(i + 1, x)) }
        d.grid(r, [14, d.contentMm - 14])
    }

    // ================================================================== Bend test (bend_test_report_pdf_bytes)
    static func bendFind(_ rows: [Row], units: [String], words: [String], textOnly: Bool = false) -> Row {
        for r in rows {
            let unit = s(r["unit"]).lowercased()
            let name = "\(s(r["parameter"])) \(s(r["characteristic"])) \(s(r["specification"]))".lowercased()
            let ctype = s(r["characteristic_type"]).uppercased()
            if textOnly && !(ctype == "TEXT" || ctype == "ATTRIBUTE") { continue }
            if units.contains(unit) { return r }
            if words.contains(where: { name.contains($0) }) { return r }
        }
        return [:]
    }

    static func bendActual(_ r: Row) -> String {
        var val: Any? = r["actual_value"]
        if !present(val) || s(val).isEmpty {
            val = J.list(r["observations"]).map { s($0) }.filter { !$0.isEmpty && $0 != "null" }.joined(separator: ", ")
        }
        let x = raw(val)
        return x == "None" ? "" : x
    }

    static func pv(_ o: Any?) -> String { let r = raw(o); return r.isEmpty ? "-" : r }

    static func same(_ a: Row, _ b: Row) -> Bool { !a.isEmpty && !b.isEmpty && NSDictionary(dictionary: a).isEqual(to: b) }

    static func bend(_ record: Row, _ part: Row, _ customer: Row, _ grade: Row, _ inward: Row, _ osp: Row, _ emps: [String: Row], _ results: Row, _ photos: [RptPhoto]) async -> RptDoc {
        let det = J.obj(results["bend_report"])
        let rows = J.rows(results["rows"])
        let d = RptDoc("METALLURGICAL LABORATORY - BEND TEST REPORT").file("QCMS_Bend_Test_\(s(record["report_number"]))")
        await theme(d, "BEND_TEST")
        d.edgeMm = 9
        d.topMm = 28
        d.band("BEND TEST REPORT")
        let batch = or(det["fsi_batch_no"], record["batch_number"])
        let info: [[String]] = [
            ["Report No.", pv(record["report_number"]), "Date", pv(record["test_date"])],
            ["Part #", pv(part["part_number"]), "Part Name", pv(part["part_name"])],
            ["Customer Name", pv(or(det["customer_name"], customer["party_name"])), "Material Used", pv(or(det["material_used"], grade["grade_code"], grade["grade_name"]))],
            ["Baking Batch No.", pv(or(det["baking_batch_no"], record["vendor_batch_number_snapshot"])), "Batch Quantity (Pcs)", pv(or(det["batch_quantity_pcs"], record["production_quantity_pcs"]))],
            ["Steel Heat Code", pv(or(det["steel_heat_code"], record["heat_code"], inward["heat_code"], record["heat_number"])), "Part Diameter", pv(det["part_diameter"])],
            ["FSI Batch No.", pv(batch), "HT Batch No.", pv(or(det["ht_batch_no"], osp["vendor_batch_number"]))],
        ]
        let infoGrid = RptLabeled(info, [0.19, 0.31, 0.19, 0.31], labelCols: [0, 2], center: false, size: 8.6)
        infoGrid.valueColor = RptDoc.ink
        d.blocks.append(infoGrid)

        let temp = bendFind(rows, units: ["°c", "c", "deg c", "degc"], words: ["°c", "baking temp"])
        let btime = bendFind(rows, units: ["minutes", "minute", "min", "mins"], words: ["minutes", "baking time"])
        let hard = bendFind(rows, units: ["hrc", "hv", "hrc/hv"], words: ["hrc", "hardness"])
        d.band("Baking / Aging")
        let tA = bendActual(temp), timeA = bendActual(btime), hA = bendActual(hard)
        let tempActual: String = tA + (!tA.isEmpty && !tA.contains("°") ? "°C" : "")
        let timeActual: String = timeA.isEmpty ? "" : timeA + " Minutes"
        let hardActual: String = "\(hA) \(s(hard["unit"]))".trimmingCharacters(in: .whitespaces)
        let bk: [[String]] = [
            ["", "Baking Temp.", "Baking Time (Minutes)", s(or(det["hardness_title"], "Base Metal Hardness below plating in HV0.5kgs at 0.1mm & (HRC) Avg reading of Three observations"))],
            ["Specification", pv(or(det["baking_temp_spec"], s(temp["specification"]))), pv(or(det["baking_time_spec"], s(btime["specification"]))), pv(or(det["hardness_spec"], s(hard["specification"])))],
            ["Actual", pv(or(det["baking_temp_actual"], tempActual)), pv(or(det["baking_time_actual"], timeActual)), pv(or(det["hardness_actual"], hardActual))],
        ]
        let bkg = RptGrid(bk, [0.19, 0.22, 0.24, 0.35], status: [], headerRows: 1, headSize: 8.6, cellSize: 8.6)
        bkg.allCenter = true; bkg.firstColBold = true; bkg.noTopLine = true
        d.blocks.append(bkg)

        let load = bendFind(rows, units: ["kn"], words: ["load"])
        let cht = bendFind(rows, units: ["mm"], words: ["cross head", "cht"])
        var angleValue: Any? = results["bend_angle_degrees"]
        if !present(angleValue) || s(angleValue).isEmpty { angleValue = bendActual(bendFind(rows, units: ["degree", "degrees", "deg", "°"], words: ["angle"])) }
        var angle: String
        if let a = Double(raw(angleValue)) { angle = (a == a.rounded() ? String(Int(a)) : String(a)) + "°" } else { angle = raw(angleValue).isEmpty ? "-" : raw(angleValue) }
        let disp = s(or(record["disposition"], record["overall_result"])).uppercased()
        let statusFallback: String = ["ACCEPTED", "PASS"].contains(disp) ? "Passed" : (["REJECTED", "FAIL"].contains(disp) ? "Failed" : (disp.isEmpty ? "Pending" : titleWords(disp)))
        let status = s(or(det["bend_status"], statusFallback))
        d.band("Bend Test Results")
        let rs: [[String]] = [
            ["Load Vs CHT", "CHT (mm)", "Bend Angle (Degree)", "Bend Test Status"],
            [pv(or(det["load_kn"], bendActual(load))), pv(or(det["cht_mm"], bendActual(cht))), angle == "-" ? "-" : "Including angle   " + angle, pv(status)],
        ]
        let rsg = RptGrid(rs, [0.25, 0.25, 0.25, 0.25], status: status.lowercased().hasPrefix("pass") ? [3] : [], headerRows: 1, headSize: 8.6, cellSize: 8.6)
        rsg.allCenter = true; rsg.noTopLine = true
        d.blocks.append(rsg)

        func slot(_ i: Int) -> RptPhoto? { i - 1 < photos.count ? photos[i - 1] : nil }
        let surfRow = bendFind(rows, units: [], words: ["peeling", "flaking", "plating"], textOnly: true)
        let surface = s(or(det["surface_remark"], bendActual(surfRow), s(surfRow["specification"])))
        d.blocks.append(RptBendPanel(left: slot(1), angle: angle, r1: slot(2), r2: slot(3), r3: slot(4), surface: surface))
        d.text("Part Bend Angle: " + angle, .small)
        let caps = (1...4).compactMap { i -> String? in if let p = slot(i), p.has { return p.caption }; return nil }
        d.text("BEND TEST PART PHOTOGRAPHS: " + caps.joined(separator: " · "), .small)

        let conclusion = s(or(results["conclusion_remark"], record["remarks"]))
        d.space(3)
        let cl = RptLabeled([["Conclusion:-", conclusion.isEmpty ? "-" : conclusion]], [0.2, 0.8], labelCols: [0], center: false, size: 9.6)
        cl.ruled = true; cl.valueColor = d.conclusionColor; cl.valueBold = true; cl.labelSize = 10
        d.blocks.append(cl)
        let prepared = emp(emps, record["prepared_by_employee_id"])
        var approved = emp(emps, record["approved_by_employee_id"])
        if approved == "-" { approved = emp(emps, record["validated_by_employee_id"]) }
        d.space(4)
        d.blocks.append(RptSignatures(values: [prepared, approved], labels: ["Prepared By", "Verified & Approved By"], w: [0.6, 0.4]))
        let refs = J.list(results["reference_documents"]).map { s($0) }.filter { !$0.isEmpty }
        if !refs.isEmpty {
            d.space(3)
            d.text("Referance Documents:", .heading)
            for r in refs { d.text("- " + r, .small) }
        }
        var unmapped: [[String]] = [row("Parameter / Specification", "Actual", "Unit", "Result")]
        for r in rows {
            if [temp, btime, hard, load, cht].contains(where: { same($0, r) }) { continue }
            if ["degree", "degrees", "deg", "°"].contains(s(r["unit"]).lowercased()) { continue }
            let ctype = s(or(r["characteristic_type"], "NUMBER")).uppercased()
            if ctype == "TEXT" || ctype == "ATTRIBUTE" { continue }
            unmapped.append(row(or(r["specification"], r["parameter"], r["characteristic"]), bendActual(r), or(r["unit"], ""), or(r["result"], "")))
        }
        if unmapped.count > 1 {
            d.space(3)
            d.band("Layout Parameters")
            let ug = RptGrid(unmapped, [0.55, 0.2, 0.1, 0.15], status: [], headerRows: 1, headSize: 7.4, cellSize: 7.4)
            ug.noAlign = true; ug.plainHeader = true
            d.blocks.append(ug)
        }
        return d
    }

    // ================================================================== Dimensional (dimensional_record_pdf_bytes)
    static func dimensional(_ id: String) async throws -> RptDoc {
        let record = await api.one("inspection_reports", id)
        if record.isEmpty { throw ApiError(status: 404, message: "Dimensional report not found.") }
        let part = await api.one("parts", record["part_id"])
        let inward = await api.one("inward_lots", record["inward_lot_id"])
        let supplier = await api.one("parties", or(record["supplier_id"], inward["supplier_id"]))
        let customer = await api.one("parties", or(record["customer_id"], part["customer_id"]))
        let grade = await api.one("material_grades", or(record["material_grade_id"], part["material_grade_id"]))
        let process = await api.one("processes", record["process_id"])
        let stage = await api.one("inspection_stages", record["inspection_stage_id"])
        let osp = await ospJob(record)
        let emps = await employees(record["prepared_by_employee_id"], record["validated_by_employee_id"], record["approved_by_employee_id"])
        let results = await api.list("inspection_results?select=*&inspection_report_id=eq.\(Api.enc(id))&order=sequence_no.asc&limit=2000")
        let scope = s(or(record["inspection_scope"], "MATERIAL_INWARD"))
        let isOsp = scope.hasPrefix("OSP_") || truthy(record["osp_job_id"])
        let title = isOsp ? "OSP DIMENSIONAL INSPECTION REPORT" : (scope == "RAW_MATERIAL_STAGE" ? "RAW MATERIAL DIMENSIONAL INSPECTION REPORT" : "FINAL INSPECTION / DIMENSIONAL REPORT")
        let d = RptDoc(title).file("QCMS_Dimensional_\(s(record["report_number"]))")
        await theme(d, "DIMENSIONAL")
        d.bar(title)
        d.labeled([
            vrow("Report No.", record["report_number"], "Date", record["inspection_date"]),
            vrow("Part Name", part["part_name"], "Part No.", part["part_number"]),
            vrow("Customer", customer["party_name"], "Supplier / OSP Vendor", or(osp["vendor_name"], supplier["party_name"])),
            vrow("Material Grade", or(grade["grade_code"], grade["grade_name"]), "Supply / Process Condition", or(record["supply_condition"], osp["process_name"], process["process_name"])),
            vrow("Heat Number", or(record["heat_number"], inward["heat_number"], osp["heat_number"]), "Heat Code", or(record["heat_code"], inward["heat_code"])),
            vrow("Supplier / HT / OSP Batch", or(record["vendor_batch_number_snapshot"], osp["vendor_batch_number"]), "Internal / FSI Batch", record["batch_number"]),
            vrow("Supplier Invoice / Reference", record["supplier_reference_number"], "Inspection Stage", or(stage["stage_name"], record["layout_type_name"])),
            vrow("Drawing", or(record["drawing_number"], part["drawing_number"]), "Revision", or(record["drawing_revision"], part["drawing_revision"])),
            vrow("Process", or(osp["process_name"], process["process_name"], record["process_specification_snapshot"]), "Layout", record["layout_name_snapshot"]),
            vrow("Lot / Production Qty", or(record["production_quantity_pcs"], record["lot_quantity"]), "Sample Size", record["sample_size"]),
            vrow("Sample / Lot Reference", record["reference_text"], "Report Scope", titleWords(scope)),
        ], [32, 65, 32, 65], 0, 2)
        d.space(1.5)
        d.bar("INSPECTION RESULTS")
        var t: [[String]] = [row("Sr.", "Parameter / Characteristic", "Specification", "Observations", "Method / Aid", "Result")]
        for (i, r) in results.enumerated() {
            let obs = r["observations"]
            let observations = obs is [Any] ? raw(obs) : raw(obs)
            var spec: Any? = r["specification"]
            if !truthy(spec) && (present(r["lower_spec"]) || present(r["upper_spec"])) {
                spec = "\(raw(r["lower_spec"])) - \(raw(r["upper_spec"])) \(raw(r["unit"]))".trimmingCharacters(in: .whitespaces)
            }
            t.append(row(or(r["sequence_no"], r["characteristic_no"], i + 1), r["characteristic"], spec, observations.isEmpty ? r["attribute_result"] : observations, r["checking_aid"], r["result"]))
        }
        if t.count == 1 { t.append(row(1, "Inspection characteristic", "As approved layout", "No results recorded", "", "NOT_EVALUATED")) }
        d.grid(t, [12, 54, 48, 42, 22, 16], 5)
        let overall = or(record["disposition"], record["overall_result"], "NOT_EVALUATED")
        let conclusion = or(record["remarks"], "Overall result: " + raw(or(record["overall_result"], overall)))
        d.space(1.5)
        d.conclusion(raw(conclusion), "", raw(overall), raw(or(record["disposition_reason"], "-")))
        d.labeledCenter([vrow("Prepared By", emp(emps, record["prepared_by_employee_id"]), "Validated By", emp(emps, record["validated_by_employee_id"]),
                              "Approved By", emp(emps, record["approved_by_employee_id"]))], [25, 39, 25, 39, 25, 41], 0, 2, 4)
        return d
    }

    // ================================================================== Material inward
    static func inward(_ id: String) async throws -> RptDoc {
        let record = await api.one("inward_lots", id)
        if record.isEmpty { throw ApiError(status: 404, message: "Material Inward record not found.") }
        let register = await api.list("v_qsms_inward_register?select=*&id=eq.\(Api.enc(id))&limit=1").first ?? [:]
        let part = await api.one("parts", record["part_id"])
        let supplier = await api.one("parties", record["supplier_id"])
        let rmtc = await api.one("rmtc_approvals", record["rmtc_approval_id"])
        let emps = await employees(record["prepared_by_employee_id"], record["validated_by_employee_id"])
        let metlab = await api.list("lab_tests?select=*&inward_lot_id=eq.\(Api.enc(id))&test_type=eq.METLAB&order=updated_at.desc&limit=1").first ?? [:]
        let dim = await api.list("inspection_reports?select=*&inward_lot_id=eq.\(Api.enc(id))&report_type=eq.DIMENSIONAL&order=updated_at.desc&limit=1").first ?? [:]
        let title = "MATERIAL INWARD INSPECTION RECORD"
        let d = RptDoc(title).file("QCMS_Material_Inward_\(s(record["inward_number"]))")
        await theme(d, "MATERIAL_INWARD")
        d.bar(title)
        d.labeled([
            vrow("Inward No.", record["inward_number"], "Date", record["inward_date"]),
            vrow("GRN Number", record["grn_number"], "Supplier Invoice", record["invoice_number"]),
            vrow("Part Name", or(part["part_name"], register["part_name"]), "Part No.", or(part["part_number"], register["part_number"])),
            vrow("Supplier", or(supplier["party_name"], register["supplier_name"]), "Heat Number", record["heat_number"]),
            vrow("Heat Code", record["heat_code"], "RMTC Number", or(rmtc["rmtc_number"], register["rmtc_number"])),
            vrow("Supplier RMTC", or(rmtc["certificate_reference"], register["supplier_rmtc_number"]), "Input Weight kg/part", record["input_weight_kg"]),
        ], [32, 65, 32, 65], 0, 2)
        d.space(1.5)
        d.bar("QUANTITY & STEEL ALLOCATION")
        d.grid([
            row("Quantity", "Production pcs", "Steel kg", "Disposition / Status"),
            row("Total", record["production_quantity_pcs"], or(record["required_steel_quantity_kg"], record["steel_quantity_kg"]), record["receipt_disposition"]),
            row("Accepted", record["accepted_production_quantity_pcs"], record["accepted_steel_quantity_kg"], "ACCEPTED"),
            row("Rejected", record["rejected_production_quantity_pcs"], record["rejected_steel_quantity_kg"], "REJECTED"),
            row("On Hold", record["hold_production_quantity_pcs"], record["hold_steel_quantity_kg"], "ON_HOLD"),
        ], [44, 45, 45, 60], 3)
        d.bar("QUALITY GATE & LINKED INSPECTIONS")
        d.grid([
            row("Quality Gate", "Status", "Linked Report", "Report / Decision"),
            row("RMTC Validation", or(rmtc["disposition"], register["rmtc_disposition"]), rmtc["rmtc_number"], rmtc["validation_result"]),
            row("MetLAB", record["metallurgical_status"], or(metlab["report_number"], "-"), or(metlab["disposition"], metlab["overall_result"])),
            row("Dimensional / Final Inspection", record["dimensional_status"], or(dim["report_number"], "-"), or(dim["disposition"], dim["overall_result"])),
            row("Final Quality Decision", record["quality_disposition"], "Material Inward", record["status"]),
        ], [50, 42, 47, 55], 1, 3)
        if truthy(record["reserve_reason"]) || truthy(record["remarks"]) {
            d.labeled([vrow("Hold / Reserve / Rejection Reason", or(record["reserve_reason"], "-")), vrow("Remarks", or(record["remarks"], "-"))], [48, 146], 0)
        }
        d.space(1.5)
        d.labeledCenter([vrow("Prepared By", emp(emps, record["prepared_by_employee_id"]), "Validated By", emp(emps, record["validated_by_employee_id"]))], [32, 65, 32, 65], 0, 2)
        return d
    }

    // ================================================================== RMTC
    static func rmtcGrid(_ d: RptDoc, _ rows: [[String]], _ w: [CGFloat], _ cell: CGFloat, _ status: [Int]) {
        d.blocks.append(RptGrid(rows, w, status: status, headerRows: 1, headSize: 7.6, cellSize: cell))
    }

    static func rmtc(_ id: String) async throws -> RptDoc {
        let record = await api.one("rmtc_approvals", id)
        if record.isEmpty { throw ApiError(status: 404, message: "RMTC record not found.") }
        let eid = Api.enc(id)
        let approvals = await api.list("rmtc_part_approvals?select=*&rmtc_approval_id=eq.\(eid)&order=created_at.asc&limit=100")
        let chemistry = await api.list("rmtc_chemistry_results?select=*&rmtc_approval_id=eq.\(eid)&order=element.asc&limit=300")
        let jominy = await api.list("rmtc_jominy_results?select=*&rmtc_approval_id=eq.\(eid)&order=distance_mm.asc&limit=300")
        let requirements = await api.list("rmtc_requirement_results?select=*&rmtc_approval_id=eq.\(eid)&order=sequence_no.asc&limit=300")
        var parts: [String: Row] = [:], grades: [String: Row] = [:]
        let partIds = approvals.map { s($0["part_id"]) }.filter { !$0.isEmpty }
        if !partIds.isEmpty { for p in await api.list("parts?select=*&id=in.(\(partIds.joined(separator: ",")))&limit=200") { parts[s(p["id"])] = p } }
        let gradeIds = parts.values.map { s($0["material_grade_id"]) }.filter { !$0.isEmpty }
        if !gradeIds.isEmpty { for g in await api.list("material_grades?select=*&id=in.(\(gradeIds.joined(separator: ",")))&limit=200") { grades[s(g["id"])] = g } }
        let supplier = await api.one("parties", record["supplier_id"])
        let mill = await api.one("parties", record["steel_mill_id"])
        let emps = await employees(record["prepared_by_employee_id"], record["validated_by_employee_id"], record["approved_by_employee_id"], record["decision_by_employee_id"])
        let norm = String(s(record["heat_number"]).unicodeScalars.filter { CharacterSet.alphanumerics.contains($0) }).uppercased()
        var heat: Row = [:]
        var usage: [Row] = []
        if !norm.isEmpty {
            heat = await api.list("v_qsms_heat_summary?select=*&normalized_heat_number=eq.\(Api.enc(norm))&limit=1").first ?? [:]
            usage = await api.list("v_qsms_heat_steel_ledger?select=*&normalized_heat_number=eq.\(Api.enc(norm))&order=created_at.desc&limit=500")
        }
        let photos = await slotPhotos(entity: "RMTC", id: id, prefix: "RMTC_MICROSTRUCTURE_", record: record, slots: 3)

        let d = RptDoc("RMTC RECORD - " + s(or(record["rmtc_number"], "QUALITY RECORD"))).file("QCMS_RMTC_\(s(record["rmtc_number"]))")
        await theme(d, "RMTC")
        d.heatNumber = s(record["heat_number"])
        d.recordNumber = s(record["rmtc_number"])
        d.reportLabel = "RMTC RECORD"
        let body: CGFloat = 8.0
        d.bar("RMTC HEADER & TRACEABILITY")
        d.blocks.append(RptLabeled([
            vrow("QCMS RMTC Number", record["rmtc_number"], "Entry Date", record["entry_date"]),
            vrow("Supplier RMTC Number", record["certificate_reference"], "RMTC Date", record["certificate_date"]),
            vrow("Supplier", supplier["party_name"], "Steel Mill", mill["party_name"]),
            vrow("Heat Number", record["heat_number"], "Internal Heat Code", record["heat_code"]),
            vrow("Global Heat Steel Qty kg", record["certificate_quantity"], "RM Section", record["rm_section"]),
            vrow("Forging Route / Root", record["forging_route"], "Prepared By", emp(emps, record["prepared_by_employee_id"])),
            vrow("Workflow Status", record["status"], "Validation Result", record["validation_result"]),
            vrow("Final Disposition", record["disposition"], "Decision Date", record["decision_at"]),
        ], [29, 68, 29, 68], labelCols: [0, 2], center: false, size: body))
        if truthy(record["remarks"]) { d.blocks.append(RptLabeled([vrow("RMTC Remarks", record["remarks"])], [29, d.contentMm - 29], labelCols: [0], center: false, size: body)) }
        d.space(1.6)
        d.bar("GLOBAL HEAT QUANTITY BALANCE & RECORD LIST")
        d.blocks.append(RptLabeled([
            vrow("Global Heat Qty kg", or(heat["global_steel_quantity_kg"], record["certificate_quantity"]), "Committed kg", heat["committed_steel_quantity_kg"],
                 "Unallocated Balance kg", or(heat["available_unallocated_steel_quantity_kg"], heat["available_steel_quantity_kg"])),
            vrow("Inward Steel Used kg", heat["inward_steel_quantity_kg"], "Remaining Planned kg", heat["remaining_planned_steel_quantity_kg"], "Active RMTC Records", heat["active_rmtc_count"]),
        ], [31, 33, 31, 33, 34, 32], labelCols: [0, 2, 4], center: false, size: body))
        var hr: [[String]] = [row("RMTC No.", "Supplier RMTC", "Supplier", "Part", "Planned kg", "Inward kg", "Balance Plan kg", "Decision")]
        for r in usage {
            hr.append(row(r["rmtc_number"], r["supplier_rmtc_number"], r["supplier_name"], r["part_number"], r["planned_steel_quantity_kg"], r["inward_steel_quantity_kg"],
                          r["remaining_planned_steel_quantity_kg"], or(r["part_disposition"], r["rmtc_disposition"], r["rmtc_status"])))
        }
        if hr.count == 1 { hr.append(row(record["rmtc_number"], record["certificate_reference"], supplier["party_name"], "-", "-", "-", "-", or(record["disposition"], record["status"]))) }
        rmtcGrid(d, hr, [24, 27, 34, 21, 21, 21, 25, 21], 7.6, [7])
        d.space(1.6)
        d.bar("COVERED PART WORKSHEET REGISTER")
        var ps: [[String]] = [row("Part No.", "FSI Part No.", "Description", "Grade", "Planned Qty", "Input kg", "Steel kg", "Worksheet", "Auto Validation", "Final Decision")]
        for a in approvals {
            let p = parts[s(a["part_id"])] ?? [:], g = grades[s(p["material_grade_id"])] ?? [:]
            ps.append(row(p["part_number"], p["fsi_part_number"], p["part_name"], or(g["grade_code"], g["grade_name"]), a["planned_production_quantity_pcs"], a["input_weight_kg"],
                          a["planned_steel_quantity_kg"], truthy(a["worksheet_completed_at"]) ? "Completed" : "Pending", or(a["approval_status"], "NOT_EVALUATED"), or(a["disposition"], "PENDING")))
        }
        if ps.count == 1 { ps.append(row("-", "-", "No covered part worksheets found", "", "", "", "", "Pending", "NOT_EVALUATED", "PENDING")) }
        rmtcGrid(d, ps, [17, 20, 27, 17, 16, 17, 18, 20, 21, 21], 7.6, [7, 8, 9])
        d.space(1.6)
        d.bar("SUPPLIER RMTC MECHANICAL PROPERTIES")
        var mech: [[String]] = [row("Property", "Actual / Result", "Source")]
        let mr = J.obj(record["mechanical_results"])
        if !mr.isEmpty { for k in mr.keys.sorted() { mech.append(row(titleWords(k), mr[k], "Supplier RMTC")) } }
        else { mech.append(row("Mechanical Properties", "No dedicated mechanical property values recorded", "Supplier RMTC")) }
        rmtcGrid(d, mech, [55, 94, 45], body, [])

        for (wi, a) in approvals.enumerated() {
            d.keep(42)
            let pid = s(a["part_id"])
            let p = parts[pid] ?? [:], g = grades[s(p["material_grade_id"])] ?? [:]
            d.bar("PART WORKSHEET \(wi + 1) - \(dash(p["part_number"])) - \(raw(p["part_name"]))")
            d.blocks.append(RptLabeled([
                vrow("Part Number", p["part_number"], "FSI Part Number", p["fsi_part_number"], "Part Description", p["part_name"]),
                vrow("Material Grade", or(g["grade_code"], g["grade_name"]), "Heat Number", record["heat_number"], "Heat Code", record["heat_code"]),
                vrow("Worksheet Status", truthy(a["worksheet_completed_at"]) ? "Completed" : "Pending", "", "", "", ""),
                vrow("Planned Production Qty pcs", a["planned_production_quantity_pcs"], "Input Weight kg", a["input_weight_kg"], "Planned Steel kg", a["planned_steel_quantity_kg"]),
            ], [25, 37, 27, 43, 27, 35], labelCols: [0, 2, 4], center: false, size: body))
            d.sub("Chemical Composition")
            let pchem = chemistry.filter { s($0["part_id"]) == pid }
            var cr = chemHorizontal(pchem, [("Minimum", "minimum_value"), ("Maximum", "maximum_value"), ("Actual", "actual_value"), ("Status", "result")])
            if pchem.isEmpty { cr = [row("Element", "-"), row("Actual", "No chemistry values recorded")] }
            for band in ChemGrid.bands(cr) { rmtcGrid(d, band, spread(d, band[0].count, 22), 7.6, []) }
            d.sub("Jominy Results")
            let pjom = jominy.filter { s($0["part_id"]) == pid }
            var jr = jominyHorizontal(pjom, [("Min HRC", "minimum_hrc"), ("Max HRC", "maximum_hrc"), ("Actual HRC", "actual_hrc"), ("Actual Status", "result"),
                                             ("Calculated HRC", "calculated_hrc"), ("Calc. Status", "calculated_result"), ("Applicable", "__na")])
            if pjom.isEmpty { jr = [row("Distance (inch)", "-"), row("Actual HRC", "No Jominy values recorded")] }
            for band in ChemGrid.bands(jr) { rmtcGrid(d, band, spread(d, band[0].count, 22), 7.6, []) }
            d.sub("DI / Hardenability")
            rmtcGrid(d, [row("Grain Size ASTM E-112", "Actual DI", "Actual DI Status", "Calculated DI", "Calculated DI Status"),
                         row(a["grain_size"], a["actual_di"], a["actual_di_status"], a["calculated_di"], a["calculated_di_status"])], [42, 32, 42, 32, 46], body, [2, 4])
            let preq = requirements.filter { s($0["part_id"]) == pid }
            let tokens = ["tensile", "yield", "elongation", "reduction", "impact", "proof", "mechanical", "uts"]
            let isMech = { (r: Row) -> Bool in let n = s(or(r["requirement_name"], r["requirement_code"])).lowercased(); return tokens.contains(where: { n.contains($0) }) }
            d.sub("Mechanical Properties")
            var mp: [[String]] = [row("Property", "Specification", "Actual / Observation", "Unit", "Status", "Remarks")]
            for r in preq where isMech(r) { mp.append(row(or(r["requirement_name"], r["requirement_code"]), r["requirement_value"], r["actual_value"], r["unit"], r["result"], r["remarks"])) }
            if mp.count == 1 { mp.append(row("Mechanical Properties", "As supplier RMTC / Part requirement", "No separate part-level mechanical property row", "", "NOT_EVALUATED", "")) }
            rmtcGrid(d, mp, [38, 42, 40, 18, 24, 32], 7.6, [4])
            d.sub("Heat Treatment & Other Requirements")
            var orq: [[String]] = [row("Requirement", "Specification / Part Master", "RMTC Actual / Observation", "Unit", "Status", "Remarks")]
            for r in preq where !isMech(r) { orq.append(row(or(r["requirement_name"], r["requirement_code"]), r["requirement_value"], r["actual_value"], r["unit"], r["result"], r["remarks"])) }
            if orq.count == 1 { orq.append(row("-", "No additional requirements recorded", "", "", "NOT_EVALUATED", "")) }
            rmtcGrid(d, orq, [38, 45, 39, 18, 24, 30], 7.6, [4])
        }
        d.keep(55)
        d.bar("RMTC MICROSTRUCTURE PHOTOGRAPHS")
        d.blocks.append(RptPhotos(photos, cols: 3, maxHmm: 40, slots: true))
        d.keep(44)
        d.bar("RMTC VALIDATION STATUS & FINAL DECISION")
        let qrUrl = await rmtcQrUrl(id, record)
        if !qrUrl.isEmpty {
            d.blocks.append(RptPhotos([RptPhoto(caption: "Material location QR · scan to download the approved certificate", data: qrPNG(qrUrl))], cols: 3, maxHmm: 30))
            d.blocks.append(RptLabeled([vrow("Material Location QR", qrUrl)], [42, d.contentMm - 42], labelCols: [0], center: false, size: body))
        }
        if approvals.isEmpty {
            rmtcGrid(d, [row("Validation Check", "Status", "Validation Check", "Status"), row("Record", "NOT_EVALUATED", "Final Decision", "PENDING")], [42, 55, 42, 55], body, [1, 3])
        } else {
            for (ai, a) in approvals.enumerated() {
                let p = parts[s(a["part_id"])] ?? [:], g = grades[s(p["material_grade_id"])] ?? [:]
                if ai > 0 { d.space(1.2) }
                d.sub("\(dash(p["part_number"])) - \(raw(p["part_name"])) - \(raw(or(g["grade_code"], g["grade_name"], "")))")
                rmtcGrid(d, [
                    row("Validation Check", "Status", "Validation Check", "Status"),
                    row("Source", a["source_status"], "Material Grade", a["material_grade_status"]),
                    row("Raw Material", a["raw_material_status"], "Chemistry", a["chemistry_status"]),
                    row("Jominy", a["jominy_status"], "Requirements", a["requirement_status"]),
                    row("Actual DI", a["actual_di_status"], "Calculated DI", a["calculated_di_status"]),
                    row("Automated Recommendation", a["approval_status"], "Final Decision", a["disposition"]),
                ], [42, 55, 42, 55], body, [1, 3])
                let reason = or(a["decision_reason"], record["decision_reason"], "")
                d.blocks.append(RptLabeled([vrow("Decision / Reserve Reason", or(reason, "-"))], [42, 152], labelCols: [0], center: false, size: body))
            }
        }
        d.space(1.6)
        d.blocks.append(RptLabeled([
            ["Prepared By", emp(emps, record["prepared_by_employee_id"]), "Validated By", emp(emps, record["validated_by_employee_id"]),
             "Approved / Decided By", emp(emps, or(record["approved_by_employee_id"], record["decision_by_employee_id"]))],
            ["Prepared At", v(record["prepared_at"]), "Validated At", v(record["validated_at"]), "Decision At", v(or(record["decision_at"], record["approved_at"]))],
        ], [24, 41, 24, 41, 30, 34], labelCols: [0, 2, 4], center: true, size: body))
        return d
    }

    // ================================================================== controlled records (controlled_record_pdf_bytes)
    static let maxColumns = 9, cellLimit = 160

    /// A section of a controlled record: ordered pairs (Field / Value) or a table.
    enum Section {
        case pairs([(String, Any?)])
        case table([String], [[String]])
        case maps([[(String, Any?)]])
    }

    static func cut(_ x: String) -> String { x.count > cellLimit ? String(x.prefix(cellLimit - 1)) + "…" : x }

    static func controlled(_ title: String, header: [(String, Any?)], sections: [(String, Section)], recordNumber: String, subtitle: String,
                           images: [RptPhoto] = [], imagesTitle: String = "PHOTOGRAPHS") -> RptDoc {
        let d = RptDoc(title)
        d.topMm = 32
        d.bottomMm = 14
        d.recordNumber = recordNumber
        d.reportLabel = subtitle
        if !subtitle.isEmpty { d.text(subtitle, .subtitle) }
        if !header.isEmpty {
            d.bar("RECORD DETAILS")
            var rows: [[String]] = []
            var i = 0
            while i < header.count {
                let l = header[i]
                let r: (String, Any?)? = i + 1 < header.count ? header[i + 1] : nil
                rows.append([l.0, v(l.1), r?.0 ?? "", r.map { v($0.1) } ?? ""])
                i += 2
            }
            d.labeled(rows, [33, 61, 33, d.contentMm - 127], 0, 2)
        }
        for (name, sec) in sections { section(d, name, sec) }
        let imgs = images.filter { $0.has }
        if !imgs.isEmpty {
            d.space(2.4)
            d.bar(imagesTitle)
            d.photos(imgs, cols: 2, maxHmm: 52)
        }
        return d
    }

    static func section(_ d: RptDoc, _ name: String, _ sec: Section) {
        d.space(2.4)
        d.bar(name)
        var cols: [String] = []
        var data: [[String]] = []
        switch sec {
        case .pairs(let pairs):
            cols = ["Field", "Value"]
            data = pairs.map { [$0.0, cut(raw($0.1))] }
        case .table(let c, let rows):
            cols = c
            data = rows.map { $0.map { cut($0) } }
        case .maps(let list):
            for m in list { for (k, _) in m where !cols.contains(k) { cols.append(k) } }
            for m in list {
                var line: [String] = []
                for c in cols {
                    let found = m.first(where: { $0.0 == c })
                    let value: Any? = found?.1 ?? nil
                    line.append(cut(raw(value)))
                }
                data.append(line)
            }
        }
        if data.isEmpty { cols = ["Information"]; data = [["No records available."]] }
        var groups: [[Int]] = []
        if cols.count <= maxColumns { groups = [Array(0..<cols.count)] }
        else {
            var i = 1
            while i < cols.count { groups.append([0] + Array(i..<min(cols.count, i + maxColumns - 1))); i += maxColumns - 1 }
        }
        for (gi, gr) in groups.enumerated() {
            if groups.count > 1 { d.space(1.6); d.sub("\(name) · columns \(gi + 1) of \(groups.count)") }
            let head = gr.map { cols[$0] }
            let status = head.enumerated().filter { $0.element.lowercased().contains("status") || $0.element.lowercased().contains("result") }.map { $0.offset }
            var t: [[String]] = [head]
            for r in data { t.append(gr.map { $0 < r.count ? r[$0] : "" }) }
            let w = Array(repeating: d.contentMm / CGFloat(max(1, gr.count)), count: gr.count)
            d.blocks.append(RptGrid(t, w, status: status, headerRows: 1, headSize: 8.2, cellSize: d.bodyPt))
        }
    }

    static func pretty(_ o: Any?) -> String { titleWords(s(o)) }
    static func yn(_ o: Any?) -> String { truthy(o) ? "Yes" : "No" }
    static func empLabel(_ e: Row) -> String {
        let name = "\(s(e["first_name"])) \(s(e["last_name"]))".trimmingCharacters(in: .whitespaces)
        return [s(e["employee_code"]), name].filter { !$0.isEmpty }.joined(separator: " · ")
    }

    // ---------------------------------------------------------------- calibration
    static func calibration(_ id: String) async throws -> RptDoc {
        let r = await api.one("quality_asset_calibration_records", id)
        if r.isEmpty { throw ApiError(status: 404, message: "Calibration record not found.") }
        let asset = await api.one("quality_assets", r["asset_id"])
        let link = await api.one("quality_asset_part_process_links", r["link_id"])
        let part = await api.one("parts", link["part_id"])
        let process = await api.one("processes", link["process_id"])
        let e = await api.one("employees", r["performed_by_employee_id"])
        let d = controlled("GAUGE / FIXTURE CALIBRATION & VALIDATION RECORD", header: [
            ("Asset Code", asset["asset_code"]), ("Asset Number", asset["asset_number"]), ("Asset", asset["asset_name"]), ("Asset Type", asset["asset_type"]),
            ("Part Number", part["part_number"]), ("Process", process["process_name"]), ("Record Type", r["record_type"]), ("Service Date", r["service_date"]),
            ("Next Due Date", r["next_due_date"]), ("Result", r["result"]), ("Status", r["status"])], sections: [
            ("CALIBRATION / VALIDATION DETAILS", .pairs([("Report Number", r["report_number"]), ("Certificate Number", r["certificate_number"]),
                                                       ("Calibration / Validation Agency", r["calibration_agency"]), ("Performed By", empLabel(e)), ("Remarks", r["remarks"])])),
            ("ASSET MASTER CONTEXT", .pairs([("Manufacturer", asset["manufacturer"]), ("Model", asset["model"]), ("Serial Number", asset["serial_number"]),
                                             ("Range", asset["range_text"]), ("Least Count", asset["least_count"]), ("Location", asset["location"])]))],
            recordNumber: s(or(r["report_number"], r["certificate_number"], r["id"])), subtitle: "Part-wise · Process-wise controlled calibration / validation genealogy")
        d.file("QCMS_Calibration_\(s(or(r["report_number"], r["certificate_number"], "Record")))")
        await theme(d, "QUALITY_RECORD")
        return d
    }

    // ---------------------------------------------------------------- standard room
    static func standardRoom(_ id: String) async throws -> RptDoc {
        let r = await api.one("standard_room_inspection_records", id)
        if r.isEmpty { throw ApiError(status: 404, message: "Standard room record not found.") }
        let asset = await api.one("quality_assets", r["instrument_asset_id"])
        let part = await api.one("parts", r["part_id"])
        let process = await api.one("processes", r["process_id"])
        let e = await api.one("employees", r["operator_employee_id"])
        let d = controlled("STANDARD ROOM PART INSPECTION RECORD", header: [
            ("Inspection Date", r["inspection_date"]), ("Report Number", r["report_number"]), ("Instrument", or(asset["asset_name"], r["instrument_type"])),
            ("Instrument Code", asset["asset_code"]), ("Asset Number", asset["asset_number"]), ("Part Number", part["part_number"]), ("Part Name", part["part_name"]),
            ("Process", process["process_name"]), ("Heat Number", r["heat_number"]), ("Batch Code", r["batch_code"]), ("Status", r["inspection_status"])], sections: [
            ("STANDARD ROOM INSPECTION", .pairs([("Instrument Type", r["instrument_type"]), ("Program / Method Reference", r["program_reference"]),
                                                 ("Quantity Inspected", r["quantity_inspected"]), ("Operator", empLabel(e)), ("Remarks", r["remarks"]), ("Record Status", r["status"])]))],
            recordNumber: s(or(r["report_number"], r["id"])), subtitle: "CMM · VMM · Roughness · Counter · Standard Room Instrument Inspection")
        d.file("QCMS_Standard_Room_\(s(or(r["report_number"], "Record")))")
        await theme(d, "QUALITY_RECORD")
        return d
    }

    // ---------------------------------------------------------------- complaint
    static func complaint(_ id: String) async throws -> RptDoc {
        let c = await api.one("quality_complaints", id)
        if c.isEmpty { throw ApiError(status: 404, message: "Complaint not found.") }
        let party = await api.one("parties", c["party_id"])
        let part = await api.one("parts", c["part_id"])
        let process = await api.one("processes", c["process_id"])
        let eid = Api.enc(id)
        let followups = await api.list("quality_complaint_followups?select=*&complaint_id=eq.\(eid)&order=followup_date.asc&limit=5000")
        let actions = await api.list("quality_complaint_actions?select=*&complaint_id=eq.\(eid)&order=action_no.asc&limit=5000")
        var ids: [String] = []
        for k in ["fourstar_responsible_employee_id", "containment_responsible_employee_id", "root_cause_responsible_employee_id", "effectiveness_verified_by_employee_id",
                  "closure_approved_by_employee_id"] where truthy(c[k]) { ids.append(s(c[k])) }
        for a in actions where truthy(a["owner_employee_id"]) { ids.append(s(a["owner_employee_id"])) }
        for f in followups where truthy(f["responsible_employee_id"]) { ids.append(s(f["responsible_employee_id"])) }
        var emps: [String: Row] = [:]
        let unique = Array(Set(ids))
        if !unique.isEmpty { for e in await api.list("employees?select=*&id=in.(\(unique.joined(separator: ",")))&limit=200") { emps[s(e["id"])] = e } }
        func el(_ id: Any?) -> String {
            guard let e = emps[s(id)] else { return "-" }
            let x = LookupLabel.of("employee", e)
            return x.isEmpty ? "-" : x
        }
        let media = await api.list("document_attachments?select=*&entity_type=eq.QUALITY_COMPLAINT&entity_id=eq.\(eid)&status=eq.ACTIVE&order=created_at.desc&limit=250")
            .filter { ["COMPLAINT_PHOTO", "COMPLAINT_ATTACHMENT"].contains(s($0["document_type"])) }
        let header: [(String, Any?)] = [
            ("Complaint No.", c["complaint_number"]), ("Complaint Type", Fmt.title(s(c["complaint_type"]))), ("Complaint Date", c["complaint_date"]),
            ("Status", pretty(c["status"])), ("Party", LookupLabel.of("party", party)), ("Part", part.isEmpty ? "Not linked" : LookupLabel.of("part", part)),
            ("Process", process.isEmpty ? "Not linked" : LookupLabel.of("process", process)), ("External Reference", or(c["external_reference"], "-")),
            ("Severity", c["severity"]), ("Target Closure", or(c["target_closure_date"], "-")), ("Actual Closure", or(c["closure_date"], "-"))]
        var secs: [(String, Section)] = []
        secs.append(("PROBLEM DEFINITION / COMPLAINT ANALYSIS", .pairs([("Subject", c["subject"]), ("Complaint Description", c["description"]),
            ("Defect / Failure Mode", or(c["defect_mode"], "-")), ("What happened?", or(c["problem_what"], "-")), ("Where detected / occurred?", or(c["problem_where"], "-")),
            ("When / under what condition?", or(c["problem_when"], "-")), ("Detection Point", or(c["detection_point"], "-")),
            ("Occurrence Pattern / Frequency", or(c["occurrence_pattern"], "-")), ("Lot / Batch", or(c["lot_batch_number"], "-")), ("Heat Number", or(c["heat_number"], "-")),
            ("Affected Quantity", c["affected_quantity"]), ("Impact / Risk Summary", or(c["impact_summary"], "-"))])))
        secs.append(("RESPONSIBILITY MATRIX", .pairs([("Complaint Coordinator", el(c["fourstar_responsible_employee_id"])),
            ("Containment Owner", el(c["containment_responsible_employee_id"])), ("Root Cause Analysis Owner", el(c["root_cause_responsible_employee_id"])),
            ("Effectiveness Verified By", el(c["effectiveness_verified_by_employee_id"])), ("Closure Approved By", el(c["closure_approved_by_employee_id"])),
            ("Customer / Supplier Responsible", or(c["external_responsible_name"], "-")), ("External Email", or(c["external_responsible_email"], "-")),
            ("External Phone", or(c["external_responsible_phone"], "-"))])))
        secs.append(("IMMEDIATE CORRECTION & CONTAINMENT", .pairs([("Immediate Correction", or(c["immediate_correction"], "-")), ("Containment Action", or(c["containment_action"], "-")),
            ("Containment Due Date", or(c["containment_due_date"], "-")), ("Containment Completed Date", or(c["containment_completed_date"], "-")),
            ("Containment Effectiveness", or(c["containment_effectiveness"], "-"))])))
        secs.append(("ROOT CAUSE ANALYSIS", .pairs([("Analysis Method", titleWords(s(or(c["analysis_method"], "-")))), ("Why 1", or(c["why_1"], "-")),
            ("Why 2", or(c["why_2"], "-")), ("Why 3", or(c["why_3"], "-")), ("Why 4", or(c["why_4"], "-")), ("Why 5", or(c["why_5"], "-")),
            ("Occurrence Root Cause", or(c["occurrence_root_cause"], c["root_cause"], "-")), ("Escape / Detection Root Cause", or(c["escape_root_cause"], "-")),
            ("Systemic Root Cause", or(c["systemic_root_cause"], "-")), ("Evidence / Validation", or(c["root_cause_evidence"], "-")),
            ("Root Cause Confirmed", yn(c["root_cause_confirmed"])), ("Confirmed Date", or(c["root_cause_confirmed_date"], "-"))])))
        let today = Fmt.today()
        secs.append(("CORRECTIVE / PREVENTIVE ACTION PLAN", .maps(actions.map { a -> [(String, Any?)] in
            let target = s(a["target_date"])
            let overdue = !target.isEmpty && target < today && !["COMPLETED", "CLOSED", "VERIFIED", "CANCELLED"].contains(s(a["status"]).uppercased())
            return [("Action No.", a["action_no"]), ("Action Type", pretty(a["action_type"])), ("Action", a["action_description"]), ("Four Star Owner", el(a["owner_employee_id"])),
                    ("External Owner", or(a["external_owner_name"], "-")), ("Target Date", or(a["target_date"], "-")), ("Completion Date", or(a["completion_date"], "-")),
                    ("Status", overdue ? "Overdue" : pretty(a["status"])), ("Evidence", or(a["evidence"], "-")), ("Effectiveness", or(a["effectiveness_result"], "-"))]
        })))
        secs.append(("EFFECTIVENESS VERIFICATION & CLOSURE", .pairs([("Verification Plan", or(c["verification_plan"], "-")), ("Effectiveness Criteria", or(c["effectiveness_criteria"], "-")),
            ("Verification Result", or(c["verification_result"], "-")), ("Effectiveness Verified", yn(c["effectiveness_verified"])),
            ("Verified Date", or(c["effectiveness_verified_date"], "-")), ("Recurrence Check", or(c["recurrence_check_result"], "-")),
            ("Closure Remarks", or(c["closure_remarks"], "-")), ("Closure Approval Date", or(c["closure_approved_date"], "-"))])))
        let cur = s(or(c["currency"], "INR"))
        let money = { (x: Any?) -> String in
            let f = NumberFormatter(); f.locale = Locale(identifier: "en_US"); f.numberStyle = .decimal; f.minimumFractionDigits = 2; f.maximumFractionDigits = 2
            return "\(cur) \(f.string(from: NSNumber(value: J.double(x))) ?? "0.00")"
        }
        secs.append(("DEBIT NOTE / COMMERCIAL STATUS", .pairs([("Debit Note Required", yn(c["debit_note_required"])), ("Debit Note Status", pretty(c["debit_note_status"])),
            ("Debit Note Number", or(c["debit_note_number"], "-")), ("Debit Note Date", or(c["debit_note_date"], "-")), ("Debit Note Amount", money(c["debit_note_amount"])),
            ("Settled Amount", money(c["debit_note_settled_amount"])), ("Settled Date", or(c["debit_note_settled_date"], "-")), ("Commercial Remarks", or(c["commercial_remarks"], "-"))])))
        var photos: [RptPhoto] = []
        var reg: [[(String, Any?)]] = []
        for m in media {
            let t = s(or(m["document_title"], m["file_name"], "Attachment"))
            let photo = s(m["document_type"]) == "COMPLAINT_PHOTO"
            let at = s(m["created_at"])
            reg.append([("Type", photo ? "Photograph" : "Attachment"), ("Title", t), ("File Name", or(m["file_name"], "-")), ("Uploaded At", at.isEmpty ? "-" : String(at.prefix(16)))])
            if photo, let data = try? await api.download(s(m["object_path"])) { photos.append(RptPhoto(caption: t, data: data)) }
        }
        secs.append(("PHOTOGRAPHS & ATTACHMENTS REGISTER", .maps(reg)))
        secs.append(("FOLLOW-UP HISTORY", .maps(followups.map { f -> [(String, Any?)] in
            [("Date", f["followup_date"]), ("Type", pretty(f["followup_type"])), ("Follow-up / Remarks", f["remarks"]), ("Next Follow-up", or(f["next_followup_date"], "-")),
             ("Status", s(f["status_after_followup"]).isEmpty ? "-" : pretty(f["status_after_followup"])), ("Responsible", el(f["responsible_employee_id"]))]
        })))
        let d = controlled("DETAILED COMPLAINT ANALYSIS RECORD", header: header, sections: secs, recordNumber: s(c["complaint_number"]),
                           subtitle: "Problem Definition · Root Cause · Corrective Action · Responsibility · Verification · Commercial Closure", images: photos, imagesTitle: "COMPLAINT PHOTOGRAPHS")
        d.file("QCMS_Complaint_\(s(c["complaint_number"]))")
        await theme(d, "QUALITY_RECORD")
        return d
    }

    // ---------------------------------------------------------------- QC calculation
    static func qcCalculation(_ id: String) async throws -> RptDoc {
        let r = await api.one("qc_calculation_records", id)
        if r.isEmpty { throw ApiError(status: 404, message: "Calculation not found.") }
        let e = await api.one("employees", r["performed_by_employee_id"])
        let part = await api.one("parts", r["part_id"])
        let grade = await api.one("material_grades", r["material_grade_id"])
        let input = J.obj(r["input_payload"]), res = J.obj(r["result_payload"])
        let header: [(String, Any?)] = [("Calculation No.", r["calculation_number"]), ("Calculation Type", pretty(r["calculation_type"])),
            ("Calculation Date", r["calculation_date"]), ("Performed By", emp([s(e["id"]): e], e["id"])), ("Part Number", part["part_number"]),
            ("FSI Part Number", part["fsi_part_number"]), ("Material Grade", grade["grade_code"]), ("Heat Number", r["heat_number"]),
            ("Standard / Basis", r["standard_reference"]), ("Status", r["status"]), ("Remarks", r["remarks"])]
        var secs: [(String, Section)] = [("Calculation Inputs", .pairs(input.keys.sorted().map { ($0, input[$0]) }))]
        switch s(r["calculation_type"]) {
        case "JOMINY":
            let curve = J.obj(res["curve"])
            let keys = curve.keys.compactMap { Int($0) }.sorted()
            secs.append(("Calculated Jominy Curve", .maps(keys.map { k -> [(String, Any?)] in [("Distance (1/16 in.)", k), ("Calculated HRC", curve[String(k)])] })))
        case "DI_VALUE":
            let fac = J.obj(res["factors"])
            secs.append(("DI Factor Details", .maps(fac.keys.sorted().map { k -> [(String, Any?)] in [("Factor", k), ("Value", fac[k])] })))
            secs.append(("Calculated Result", .pairs([("Calculated DI", res["value"]), ("Error", or(res["error"], ""))])))
        case "HARDNESS_CONVERSION":
            secs.append(("Hardness Conversion Result", .pairs([("Primary Value", "\(raw(r["primary_value"])) \(raw(r["primary_unit"]))".trimmingCharacters(in: .whitespaces)),
                ("Converted Value", "\(raw(r["result_value"])) \(raw(r["conversion_unit"]))".trimmingCharacters(in: .whitespaces)), ("Method", res["method"]),
                ("Warning", res["warning"]), ("Interpolation Bracket", res["bracket"])])))
        default: break
        }
        let d = controlled("QC CALCULATION RECORD", header: header, sections: secs, recordNumber: s(r["calculation_number"]), subtitle: "Stored quality calculation result")
        d.file("QCMS_QC_Calculation_\(s(r["calculation_number"]))")
        await theme(d, "QUALITY_RECORD")
        return d
    }

    // ---------------------------------------------------------------- Universal record PDF
    static func universal(_ m: QModule, _ id: String) async throws -> RptDoc {
        let idField = m.idField.isEmpty ? "id" : m.idField
        guard let rec = try await api.rows("\(m.table)?select=*&\(idField)=eq.\(Api.enc(id))&limit=1").first else {
            throw ApiError(status: 404, message: "Record not found or not visible for your role.")
        }
        let keys = rec.keys.sorted()
        let fk = await Labels.resolve(m.table, rows: [rec], columns: keys)
        var header: [(String, Any?)] = []
        for k in keys {
            if k == "tenant_id" || k == "id" || k.hasSuffix("_path") { continue }
            let val = rec[k]
            if !truthy(val) && !(val is NSNumber) { continue }
            let text = (val is [Any] || val is [String: Any]) ? raw(val) : Labels.cell(k, val, fk[k])
            if text.isEmpty { continue }
            header.append((Labels.header(k), text.count > 400 ? String(text.prefix(399)) + "…" : text))
        }
        var secs: [(String, Section)] = []
        for child in m.children {
            let order = child.order.isEmpty ? "" : "&order=\(child.order)"
            guard let rows = try? await api.rows("\(child.table)?select=*&\(child.fk)=eq.\(Api.enc(id))\(order)&limit=2000") else { continue }
            let cfk = await Labels.resolve(child.table, rows: rows, columns: child.cols.map { $0[0] })
            if ChemGrid.handles(child.table) {  // R38: chemistry / Jominy children print horizontally (inch + mm)
                for (label, t) in ChemGrid.horizontal(child.table, rows, cfk["part_id"]) where t.count > 1 && t[0].count > 1 {
                    secs.append((child.title.uppercased() + (label.isEmpty ? "" : " · " + label), .table(t[0], Array(t.dropFirst()))))
                }
                continue
            }
            secs.append((child.title.uppercased(), .table(child.cols.map { $0[1] }, rows.map { r in child.cols.map { Labels.cell($0[0], r[$0[0]], cfk[$0[0]]) } })))
        }
        let number = m.recordTitle(rec)
        let d = controlled(m.title.uppercased() + " RECORD", header: header, sections: secs, recordNumber: number, subtitle: "")
        d.file("QCMS_\(m.title)_\(number)")
        await theme(d, "QUALITY_RECORD")
        return d
    }

    /// Full register PDF ("<TYPE> REGISTER", Record Count, one table).
    static func register(_ title: String, columns: [String], rows: [[String]]) async -> RptDoc {
        let d = controlled(title.uppercased() + " REGISTER", header: [("Record Count", rows.count)], sections: [(title, .table(columns, rows))], recordNumber: "", subtitle: "")
        d.file("QCMS_\(title)_Register")
        await theme(d, "QUALITY_RECORD")
        return d
    }
}
