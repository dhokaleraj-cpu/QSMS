import UIKit

/// One controlled QCMS report in the website's print layout (core/reporting.py, Design B) - Swift port of the
/// Android RptDoc. The same document is drawn as the PDF (RptPdf) and shown on the record screen (RptView).
protocol RptBlock: AnyObject {}

final class RptBar: RptBlock {
    let text: String; let light: Bool
    var keepCase = false, fixedFill = false
    init(_ t: String, light: Bool) { text = t; self.light = light }
}

final class RptLabeled: RptBlock {
    let rows: [[String]]; let w: [CGFloat]; let labelCols: Set<Int>; let center: Bool; let size: CGFloat
    var ruled = false
    var valueColor: UIColor? = nil
    var valueBold = false
    var labelSize: CGFloat = 0
    init(_ rows: [[String]], _ w: [CGFloat], labelCols: [Int], center: Bool, size: CGFloat) {
        self.rows = rows; self.w = w; self.labelCols = Set(labelCols); self.center = center; self.size = size
    }
}

final class RptGrid: RptBlock {
    let rows: [[String]]; let w: [CGFloat]; let statusCols: Set<Int>; let headerRows: Int; let headSize: CGFloat; let cellSize: CGFloat
    var noAlign = false, allCenter = false, firstColBold = false, noTopLine = false, plainHeader = false
    init(_ rows: [[String]], _ w: [CGFloat], status: [Int], headerRows: Int = 1, headSize: CGFloat = 8.2, cellSize: CGFloat = 8.2) {
        self.rows = rows; self.w = w; self.statusCols = Set(status); self.headerRows = headerRows; self.headSize = headSize; self.cellSize = cellSize
    }
}

final class RptConclusion: RptBlock {
    let conclusion: String, remark: String, decision: String, reason: String
    init(_ c: String, _ r: String, _ d: String, _ why: String) { conclusion = c; remark = r; decision = d; reason = why }
}

struct RptPhoto {
    let caption: String
    let data: Data?
    var has: Bool { (data?.count ?? 0) > 0 }
}

final class RptPhotos: RptBlock {
    let items: [RptPhoto]; let cols: Int; let maxHmm: CGFloat; let slots: Bool
    init(_ items: [RptPhoto], cols: Int, maxHmm: CGFloat, slots: Bool = false) { self.items = items; self.cols = cols; self.maxHmm = maxHmm; self.slots = slots }
}

final class RptChart: RptBlock {
    var names: [String] = []
    var series: [[(Double, Double)]] = []
}

enum RptTextStyle { case normal, small, center, big, remark, heading, concl, subtitle }

final class RptText: RptBlock {
    let text: String; let style: RptTextStyle
    init(_ t: String, _ s: RptTextStyle) { text = t; style = s }
}

final class RptSpace: RptBlock { let mm: CGFloat; init(_ mm: CGFloat) { self.mm = mm } }
final class RptKeep: RptBlock { let mm: CGFloat; init(_ mm: CGFloat) { self.mm = mm } }

final class RptBendPanel: RptBlock {
    let left: RptPhoto?, r1: RptPhoto?, r2: RptPhoto?, r3: RptPhoto?; let angle: String, surface: String
    init(left: RptPhoto?, angle: String, r1: RptPhoto?, r2: RptPhoto?, r3: RptPhoto?, surface: String) {
        self.left = left; self.angle = angle; self.r1 = r1; self.r2 = r2; self.r3 = r3; self.surface = surface
    }
}

final class RptSignatures: RptBlock {
    let values: [String], labels: [String]; let w: [CGFloat]
    init(values: [String], labels: [String], w: [CGFloat]) { self.values = values; self.labels = labels; self.w = w }
}

final class RptDoc {
    let title: String
    var heatNumber = "", recordNumber = "", reportLabel = "", subtitle = ""
    var fileBase: String
    var landscape = false
    var edgeMm: CGFloat = 8, topMm: CGFloat = 30, bottomMm: CGFloat = 12
    var blocks: [RptBlock] = []

    // Design B theme (overridden by the saved Print Layout Designer layout)
    var accent = UIColor(rgb: 0x0B6E70), rule = UIColor(rgb: 0x9AA5A5), conclusionColor = UIColor(rgb: 0x166534), remarkColor = UIColor(rgb: 0x9A3412)
    var bodyPt: CGFloat = 8.6, headingPt: CGFloat = 10.5
    var company = "FOUR STAR INDUSTRIES", footer = "", barStyle = "fill", plantCode = "D9"
    var labels: [String: String] = [:]

    init(_ title: String) { self.title = title; self.fileBase = "QCMS_" + title }

    @discardableResult func file(_ base: String) -> RptDoc { fileBase = base; return self }
    var contentMm: CGFloat { (landscape ? 297 : 210) - 2 * edgeMm }

    /// applied_print_layout: theme of the saved Print Layout Designer layout.
    func applyLayout(_ l: Row) {
        if let c = UIColor(hexString: J.str(l["accent"])) { accent = c }
        if let c = UIColor(hexString: J.str(l["rule"])) { rule = c }
        if let c = UIColor(hexString: J.str(l["conclusion"])) { conclusionColor = c }
        if let c = UIColor(hexString: J.str(l["remark"])) { remarkColor = c }
        if let b = J.num(l["body_pt"]), b > 0 { bodyPt = CGFloat(b) }
        if let h = J.num(l["heading_pt"]), h > 0 { headingPt = CGFloat(h) }
        let c = J.str(l["company_name"]); if !c.isEmpty { company = c }
        footer = J.str(l["footer_text"])
        let bar = J.str(l["bar"]); if !bar.isEmpty { barStyle = bar }
        for (k, v) in J.obj(l["labels"]) { labels[k] = J.str(v) }
    }

    /// core/print_designer.relabel (exact, then prefix match).
    func relabel(_ t: String) -> String {
        if let v = labels[t] { return v }
        for (k, v) in labels where !k.isEmpty && t.hasPrefix(k) { return v + t.dropFirst(k.count) }
        return t
    }

    // builder helpers
    func bar(_ t: String) { blocks.append(RptBar(t, light: false)) }
    func sub(_ t: String) { blocks.append(RptBar(t, light: true)) }
    func band(_ t: String) { let b = RptBar(t, light: false); b.keepCase = true; b.fixedFill = true; blocks.append(b) }
    func space(_ mm: CGFloat) { blocks.append(RptSpace(mm)) }
    func keep(_ mm: CGFloat) { blocks.append(RptKeep(mm)) }
    func text(_ t: String, _ s: RptTextStyle) { blocks.append(RptText(t, s)) }
    func labeled(_ rows: [[String]], _ w: [CGFloat], _ labelCols: Int...) { blocks.append(RptLabeled(rows, w, labelCols: labelCols, center: false, size: bodyPt)) }
    func labeledCenter(_ rows: [[String]], _ w: [CGFloat], _ labelCols: Int...) { blocks.append(RptLabeled(rows, w, labelCols: labelCols, center: true, size: bodyPt)) }
    @discardableResult func grid(_ rows: [[String]], _ w: [CGFloat], _ status: Int...) -> RptGrid { let g = RptGrid(rows, w, status: status); blocks.append(g); return g }
    func conclusion(_ c: String, _ r: String, _ d: String, _ why: String) { blocks.append(RptConclusion(c, r, d, why)) }
    func photos(_ items: [RptPhoto], cols: Int, maxHmm: CGFloat) { blocks.append(RptPhotos(items, cols: cols, maxHmm: maxHmm)) }

    // ------------------------------------------------------------------ value formatting (reporting.py)
    private static let statusWords: Set<String> = ["DRAFT", "APPROVAL_PENDING", "APPROVED", "PARTIALLY_APPROVED", "REJECTED", "PENDING", "ON_HOLD", "ACCEPTED",
                                                    "ACCEPTED_UNDER_RESERVE", "PASS", "FAIL", "NOT_EVALUATED", "NOT_APPLICABLE"]

    /// _display_value: dates dd-mm-yyyy, floats with thousands separators, workflow words in title case.
    static func v(_ value: Any?) -> String {
        guard let value = value, !(value is NSNull) else { return "" }
        if let n = value as? NSNumber, !J.isBool(value), isFloat(n) {
            let f = NumberFormatter()
            f.locale = Locale(identifier: "en_US")
            f.numberStyle = .decimal
            f.minimumFractionDigits = 0
            f.maximumFractionDigits = 3
            return f.string(from: n) ?? n.stringValue
        }
        if value is [Any] || value is [String: Any] { return raw(value) }
        let text = J.str(value)
        if text.isEmpty { return "" }
        let chars = Array(text)
        if chars.count >= 16, chars[4] == "-", chars[7] == "-", chars[10] == "T" {
            return "\(String(chars[8...9]))-\(String(chars[5...6]))-\(String(chars[0...3])) \(String(chars[11...15]))"
        }
        if chars.count == 10, chars[4] == "-", chars[7] == "-" { return "\(String(chars[8...9]))-\(String(chars[5...6]))-\(String(chars[0...3]))" }
        if statusWords.contains(text.uppercased()) { return Fmt.title(text.replacingOccurrences(of: "_", with: " ")) }
        return text
    }

    static func isFloat(_ n: NSNumber) -> Bool {
        let t = String(cString: n.objCType)
        return t == "d" || t == "f" || n is NSDecimalNumber && n.stringValue.contains(".")
    }

    /// str(value) as the website's tables print it.
    static func raw(_ value: Any?) -> String {
        guard let value = value, !(value is NSNull) else { return "" }
        if J.isBool(value) { return (value as? Bool ?? false) ? "True" : "False" }
        if let n = value as? NSNumber {
            if isFloat(n) {
                let d = n.doubleValue
                if d == d.rounded() && abs(d) < 1e15 { return "\(Int64(d)).0" }
                return "\(d)"
            }
            return n.stringValue
        }
        if let a = value as? [Any] { return a.filter { !J.isNull($0) && !J.str($0).isEmpty }.map { raw($0) }.joined(separator: ", ") }
        if let d = value as? [String: Any] { return d.keys.sorted().map { "\($0): \(raw(d[$0]))" }.joined(separator: "; ") }
        return "\(value)"
    }

    // ------------------------------------------------------------------ colours (_status_text_color)
    static let ink = UIColor(rgb: 0x111111)

    static func statusColor(_ value: String) -> UIColor {
        switch value.trimmingCharacters(in: .whitespaces).uppercased().replacingOccurrences(of: " ", with: "_") {
        case "PASS", "APPROVED", "ACCEPTED", "RELEASED", "COMPLETED", "OK", "PASSED": return UIColor(rgb: 0x166534)
        case "FAIL", "REJECTED", "LOCKED", "FAILED", "NOT_OK": return UIColor(rgb: 0xB91C1C)
        case "ON_HOLD", "HOLD", "APPROVAL_PENDING", "ACCEPTED_UNDER_RESERVE", "PARTIALLY_APPROVED": return UIColor(rgb: 0xB45309)
        case "PENDING", "DRAFT", "NOT_EVALUATED": return UIColor(rgb: 0x1D4ED8)
        case "NOT_APPLICABLE", "INACTIVE": return UIColor(rgb: 0x555555)
        default: return ink
        }
    }

    static func isRemark(_ t: String) -> Bool { t.uppercased().contains("REMARK") }
    static func isConclusion(_ t: String) -> Bool { let u = t.uppercased(); return u.contains("CONCLUSION") && !u.contains("REMARK") }

    enum Align { case left, center, right }
    private static let rightWords = ["KG", "QTY", "QUANTITY", "WEIGHT", "AMOUNT", "VALUE", "RATE", "PRICE", "BALANCE", "PCS", "TOTAL"]
    private static let centerWords = ["SR", "NO.", "SR.", "UNIT", "MIN", "MAX", "RESULT", "STATUS", "DECISION", "DATE", "SPEC", "ACTUAL", "OBSERV",
                                      "READING", "HARDNESS", "HRC", "HV", "DEPTH", "DISTANCE", "GRADE", "HEAT", "%", "SAMPLE", "TOLERANCE", "LOCATION", "J",
                                      "DISPOSITION", "VALIDATION", "WORKSHEET"]
    private static let leftWords = ["PARAMETER", "CHARACTERISTIC", "DESCRIPTION", "REMARK", "NAME", "SUPPLIER", "METHOD", "AID", "PROPERTY", "SOURCE",
                                    "DOCUMENT", "TEST", "ELEMENT", "PART", "REQUIREMENT", "PROCESS"]

    /// _column_alignment: text columns left, measured / status columns centred, quantities right.
    static func alignment(_ header: String) -> Align {
        let t = header.uppercased().trimmingCharacters(in: .whitespaces)
        if t.isEmpty { return .center }
        if leftWords.contains(where: { t.contains($0) }) && !["RESULT", "STATUS", "DATE", "QTY", "KG"].contains(where: { t.contains($0) }) { return .left }
        if rightWords.contains(where: { t.contains($0) }) { return .right }
        let tokens = Set(t.components(separatedBy: CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789%.").inverted))
        if !tokens.isDisjoint(with: ["SR", "SR.", "NO", "NO.", "#", "S.NO"]) { return .center }
        if centerWords.contains(where: { t.contains($0) }) { return .center }
        return .left
    }

    static func plainNumber(_ v: String) -> Bool {
        v.trimmingCharacters(in: .whitespaces).range(of: "^[-+]?\\d+(?:[.,]\\d+)?(?:\\s*%)?$", options: .regularExpression) != nil
    }
}

extension UIColor {
    convenience init(rgb: UInt32) {
        self.init(red: CGFloat((rgb >> 16) & 0xFF) / 255, green: CGFloat((rgb >> 8) & 0xFF) / 255, blue: CGFloat(rgb & 0xFF) / 255, alpha: 1)
    }

    convenience init?(hexString: String) {
        guard hexString.count == 7, hexString.hasPrefix("#"), let v = UInt32(hexString.dropFirst(), radix: 16) else { return nil }
        self.init(rgb: v)
    }
}
