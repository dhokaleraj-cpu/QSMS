import Foundation

/// Foreign-key ids -> readable labels (Part number, supplier, employee …) in batches; cell / header formatting (Labels.java).
actor LabelCache {
    static let shared = LabelCache()
    private var cache: [String: [String: String]] = [:]

    func load(_ refTable: String, ids: Set<String>) async -> [String: String] {
        var known = cache[refTable] ?? [:]
        let missing = ids.filter { !$0.isEmpty && $0 != "null" && known[$0] == nil }.sorted()
        if !missing.isEmpty {
            let cols = Catalog.shared.labels[refTable] ?? []
            var select = "id"
            for c in cols where c != "id" { select += ",\(c)" }
            var start = 0
            while start < missing.count {
                let part = Array(missing[start..<min(missing.count, start + 80)])
                let rows = await Api.shared.list("\(refTable)?select=\(select)&id=in.(\(part.joined(separator: ",")))")
                for r in rows { known[J.str(r["id"])] = Labels.label(refTable, r) }
                start += 80
            }
            cache[refTable] = known
        }
        return known
    }

    func clear() { cache = [:] }
}

enum Labels {
    static func refTable(_ table: String, _ column: String) -> String? {
        if let ref = Catalog.shared.fk[table]?[column] { return ref }
        switch column {
        case "part_id", "source_part_id": return "parts"
        case "supplier_id", "customer_id", "steel_mill_id", "vendor_id", "party_id", "osp_vendor_id", "forging_supplier_id", "rm_supplier_id",
             "location_party_id", "ship_to_party_id": return "parties"
        case "process_id": return "processes"
        case "material_grade_id": return "material_grades"
        case "inspection_stage_id": return "inspection_stages"
        case "customer_order_id": return "supply_customer_orders"
        case "purchase_order_id": return "supply_purchase_orders"
        case "inward_lot_id": return "inward_lots"
        case "asset_id", "instrument_asset_id": return "quality_assets"
        case "company_branch_id": return "company_branches"
        default: return column.hasSuffix("employee_id") ? "employees" : nil
        }
    }

    static func label(_ refTable: String, _ row: Row) -> String {
        let cols = Catalog.shared.labels[refTable] ?? ["name"]
        let parts = cols.filter { $0 != "id" }.map { J.str(row[$0]) }.filter { !$0.isEmpty }
        return parts.isEmpty ? J.str(row["id"]) : parts.joined(separator: " · ")
    }

    /// column -> (id -> label) for every FK column of these rows.
    static func resolve(_ table: String, rows: [Row], columns: [String]) async -> [String: [String: String]] {
        var out: [String: [String: String]] = [:]
        for col in columns {
            guard let ref = refTable(table, col) else { continue }
            let ids = Set(rows.map { J.str($0[col]) })
            out[col] = await LabelCache.shared.load(ref, ids: ids)
        }
        return out
    }

    /// Display text for one cell.
    static func cell(_ column: String, _ value: Any?, _ fk: [String: String]?) -> String {
        guard let value = value, !(value is NSNull) else { return "" }
        let s = J.str(value)
        if s == "null" { return "" }
        if let fk = fk { return fk[s] ?? s }
        let c = column.lowercased()
        if J.isBool(value) { return (value as? Bool ?? false) ? "Yes" : "No" }
        if let a = value as? [Any] {
            let items = a.filter { !($0 is [String: Any]) }.map { Fmt.pretty(J.str($0)) }
            return items.isEmpty ? "\(a.count) item(s)" : items.joined(separator: ", ")
        }
        if let d = value as? [String: Any] { return "\(d.count) field(s)" }
        if (c.hasSuffix("_date") || c.hasSuffix("_at") || c == "date") && s.count >= 10 && Array(s)[4] == "-" { return Fmt.date(s) }
        if value is NSNumber, let n = J.num(value) { return Fmt.num(n, 3) }
        if c.contains("status") || c.contains("disposition") || c == "result" || c.hasSuffix("_type") || c.hasSuffix("_result") { return Fmt.pretty(s) }
        return s
    }

    /// part_id -> Part, inward_date -> Inward Date.
    static func header(_ column: String) -> String {
        var c = column
        if c.hasSuffix("_employee_id") { c = String(c.dropLast("_employee_id".count)) } else if c.hasSuffix("_id") { c = String(c.dropLast(3)) }
        var p = Fmt.pretty(c)
        for (a, b) in [("Kg", "kg"), ("Pcs", "pcs"), ("Fsi", "FSI"), ("Rm ", "RM "), ("Po ", "PO "), ("Hsn", "HSN"), ("Osp", "OSP"), ("Rmtc", "RMTC"), ("Grn", "GRN")] {
            p = p.replacingOccurrences(of: a, with: b)
        }
        return p
    }
}

/// Labels of lookup rows (Lookups.java).
enum LookupLabel {
    static func join(_ parts: String...) -> String { parts.filter { !$0.isEmpty }.joined(separator: " · ") }

    static func of(_ kind: String, _ r: Row) -> String {
        let j = { (k: String) -> String in J.str(r[k]) }
        switch kind {
        case "part": return join(j("part_number"), j("fsi_part_number").isEmpty ? "" : "FSI " + j("fsi_part_number"), j("part_name"))
        case "party": return join(j("party_code"), j("party_name"), j("city"))
        case "employee": return join(j("employee_code"), "\(j("first_name")) \(j("last_name"))".trimmingCharacters(in: .whitespaces), j("designation"))
        case "process": return join(j("process_code"), j("process_name"), Fmt.pretty(j("process_type")))
        case "grade": return join(j("material_number"), j("grade_code"), j("standard"))
        case "stage": return join(j("stage_code"), j("stage_name"))
        case "branch": return join(j("branch_code"), j("branch_name"), j("city"))
        case "asset": return join(j("asset_number").isEmpty ? j("asset_code") : j("asset_number"), j("asset_name"), Fmt.pretty(j("asset_type")), j("range_text"))
        case "jominy": return j("distance_label")
        case "standard": return join(j("standard_code"), j("standard_name"), "Rev " + j("revision_number"))
        default:
            for k in ["name", "code", "title"] where !j(k).isEmpty { return j(k) }
            return j("id")
        }
    }
}
