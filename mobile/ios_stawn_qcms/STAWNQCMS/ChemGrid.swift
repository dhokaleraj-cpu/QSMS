import Foundation

/// R38 · Horizontal chemistry / Jominy grids for record views and prints (website core/chem_grid.py).
/// Elements and Jominy distances are COLUMNS; Jominy shows the inch label (J5/16") and a Distance (mm) row
/// (n / 16 x 25.4 mm, two decimals half-up: J5/16" = 7.94 mm). Stored rows are never changed.
enum ChemGrid {
    static let pdfBandColumns = 14

    private static func group(_ pattern: String, _ text: String) -> String? {
        guard let re = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]) else { return nil }
        let ns = text as NSString
        guard let m = re.firstMatch(in: text, options: [], range: NSRange(location: 0, length: ns.length)), m.numberOfRanges > 1 else { return nil }
        let r = m.range(at: 1)
        return r.location == NSNotFound ? nil : ns.substring(with: r)
    }

    /// Sixteenths of an inch from J-notation: J5/16", 5/16", J 5, J3, 5 -> n; blank / mm label -> 0.
    static func sixteenths(_ v: Any?) -> Double {
        if let n = v as? NSNumber { return n.doubleValue > 0 ? n.doubleValue : 0 }
        let t = J.str(v).trimmingCharacters(in: .whitespacesAndNewlines).replacingOccurrences(of: "\u{2033}", with: "\"")
        if t.isEmpty { return 0 }
        if group(#"^\s*J?\s*(\d+(?:\.\d+)?)\s*mm\s*$"#, t) != nil { return 0 }
        let patterns = [#"(\d+(?:\.\d+)?)\s*/\s*16"#, #"^\s*J\s*(\d+(?:\.\d+)?)\s*(?:"|in|inch)?\s*$"#, #"^\s*(\d+(?:\.\d+)?)\s*$"#]
        for p in patterns {
            if let g = group(p, t), let n = Double(g), n > 0 { return n }
        }
        return 0
    }

    /// J-notation -> millimetres text with two decimals ("7.94"), "" when unknown.
    static func inchToMm(_ v: Any?) -> String {
        let n = sixteenths(v)
        guard n > 0, let base = Decimal(string: String(n)), let factor = Decimal(string: "1.5875") else { return "" }
        var value = base * factor, out = Decimal()
        NSDecimalRound(&out, &value, 2, .plain)
        return String(format: "%.2f", NSDecimalNumber(decimal: out).doubleValue)
    }

    /// Millimetres -> decimal inches text (7.9375 -> "0.3125").
    static func mmToInch(_ mm: Double) -> String {
        guard mm > 0 else { return "" }
        let inches = (mm / 25.4 * 10000).rounded() / 10000
        return String(format: "%g", inches)
    }

    /// Sixteenths of a stored Jominy row: distance_16th, then the label, then distance_mm.
    static func sixteenthOf(_ r: Row) -> Int {
        var n = sixteenths(r["distance_16th"])
        if n <= 0 { n = sixteenths(r["distance_label"]) }
        if n <= 0, let mm = Double(J.str(r["distance_mm"])), mm > 0 { n = mm / 1.5875 }
        return Int(n.rounded())
    }

    static func handles(_ table: String) -> Bool {
        return ["material_grade_elements", "part_jominy_requirements", "rmtc_chemistry_results", "rmtc_jominy_results"].contains(table)
    }

    /// One horizontal table per part ("" title when the child has no part split).
    static func horizontal(_ table: String, _ rows: [Row], _ partLabels: [String: String]?) -> [(String, [[String]])] {
        let byPart = table == "rmtc_chemistry_results" || table == "rmtc_jominy_results"
        var keys: [String] = []
        var groups: [String: [Row]] = [:]
        for r in rows {
            let status = J.str(r["status"])
            if table == "part_jominy_requirements" && !status.isEmpty && status != "ACTIVE" { continue }
            let key = byPart ? J.str(r["part_id"]) : ""
            if groups[key] == nil { groups[key] = []; keys.append(key) }
            groups[key]?.append(r)
        }
        var out: [(String, [[String]])] = []
        for key in keys {
            let label = keys.count == 1 ? "" : (partLabels?[key] ?? key)
            out.append((label, grid(table, groups[key] ?? [])))
        }
        return out
    }

    static func grid(_ table: String, _ rows: [Row]) -> [[String]] {
        switch table {
        case "material_grade_elements":
            return RptReports.chemHorizontal(rows, [("Minimum", "minimum"), ("Maximum", "maximum"), ("Unit", "unit"), ("Test Method", "test_method")])
        case "rmtc_chemistry_results":
            return RptReports.chemHorizontal(rows, [("Minimum", "minimum_value"), ("Maximum", "maximum_value"), ("Actual", "actual_value"), ("Status", "result")])
        case "part_jominy_requirements":
            return RptReports.jominyHorizontal(rows, [("Min HRC", "minimum_hrc"), ("Max HRC", "maximum_hrc")])
        default:
            return RptReports.jominyHorizontal(rows, [("Actual HRC", "actual_hrc"), ("Actual Status", "result"), ("Calculated HRC", "calculated_hrc"),
                                                      ("Calc. Status", "calculated_result"), ("Applicable", "__na")])
        }
    }

    /// One on-screen grid: part tables stacked, row titles prefixed with the part; a part with other columns
    /// repeats its own header as a row. Every row is padded to the widest table.
    static func combined(_ table: String, _ rows: [Row], _ partLabels: [String: String]?) -> [[String]] {
        let parts = horizontal(table, rows, partLabels)
        guard let first = parts.first, !first.1.isEmpty else { return [] }
        var out: [[String]] = [first.1[0]]
        for (label, t) in parts {
            guard !t.isEmpty else { continue }
            let prefix = label.isEmpty ? "" : label + " · "
            if t[0] != first.1[0] { out.append([prefix + t[0][0]] + Array(t[0].dropFirst())) }
            for line in t.dropFirst() { out.append([prefix + (line.first ?? "")] + Array(line.dropFirst())) }
        }
        let width = out.map { $0.count }.max() ?? 0
        return out.map { $0.count < width ? $0 + Array(repeating: "", count: width - $0.count) : $0 }
    }

    /// Wide grids are cut into bands of `per` value columns (row titles repeated) so a print fits A4.
    static func bands(_ t: [[String]], _ per: Int = ChemGrid.pdfBandColumns) -> [[[String]]] {
        guard !t.isEmpty else { return [] }
        let values = (t.map { $0.count }.max() ?? 1) - 1
        if values <= per { return [t] }
        var out: [[[String]]] = []
        var start = 1
        while start <= values {
            out.append(t.map { r -> [String] in
                let end = min(r.count, start + per)
                let body: [String] = start < end ? Array(r[start..<end]) : []
                return [r.first ?? ""] + body
            })
            start += per
        }
        return out
    }
}
