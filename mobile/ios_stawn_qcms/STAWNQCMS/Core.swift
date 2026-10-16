import SwiftUI
import Foundation

/// One database row as returned by PostgREST (JSON object).
typealias Row = [String: Any]

enum AppConfig {
    static let supabaseURL = "https://xxrxopzxzyjnzumrwuwy.supabase.co"
    /// Publishable (anon) key only - the service-role key is never in the app.
    static let supabaseKey = "sb_publishable_o1EpvnCYWnfJaSWQH5vfFA_EWzN4QGh"
    static let webURL = "https://vf6fa9hrhxquqxmfgyy4wf.streamlit.app"
    static let bucket = "quality-documents"
    static let webVersion = "4.14.49"
    static var appVersion: String { Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0.0" }
}

enum Theme {
    static let teal = Color(hex: 0x0F8B8D)
    static let tealDark = Color(hex: 0x0B6E70)
    static let tealSoft = Color(hex: 0xE3F2F2)
    static let brand = Color(hex: 0x165D91)
    static let bg = Color(hex: 0xF1F6F6)
    static let text = Color(hex: 0x173233)
    static let muted = Color(hex: 0x5C7778)
    static let line = Color(hex: 0xD5E4E4)
    static let lineStrong = Color(hex: 0xB5CFCF)
    static let red = Color(hex: 0x991B1B)
    static let redBg = Color(hex: 0xFEE2E2)
    static let green = Color(hex: 0x166534)
    static let greenBg = Color(hex: 0xDCFCE7)
    static let amber = Color(hex: 0x92400E)
    static let amberBg = Color(hex: 0xFEF3C7)
    static let grey = Color(hex: 0x334155)
    static let greyBg = Color(hex: 0xE2E8F0)

    /// Ui.tone: colour family of a QCMS status word.
    static func tone(_ status: String) -> (Color, Color) {
        let s = status.uppercased()
        if s.contains("CANCEL") || s.contains("REJECT") || s.contains("OVERDUE") || s.contains("FAIL") || s == "NG" { return (red, redBg) }
        if s.contains("PENDING") || s.contains("DUE") || s.contains("PROGRESS") || s.contains("DRAFT") || s.contains("REVISED") || s.contains("HOLD") { return (amber, amberBg) }
        if s.contains("APPROV") || s.contains("COMPLETE") || s.contains("CONFIRM") || s.contains("VALID") || s == "OK" || s.contains("ACTIVE")
            || s.contains("CLOSED") || s.contains("RELEASED") || s.contains("ACCEPT") || s.contains("PASS") { return (green, greenBg) }
        if s.contains("OPEN") { return (tealDark, tealSoft) }
        return (grey, greyBg)
    }
}

extension Color {
    init(hex: UInt32) {
        self.init(.sRGB, red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255, blue: Double(hex & 0xFF) / 255, opacity: 1)
    }
}

/// Helpers for loosely typed JSON values (the website's dict.get semantics).
enum J {
    static func isNull(_ v: Any?) -> Bool { v == nil || v is NSNull }

    static func isBool(_ v: Any?) -> Bool {
        guard let n = v as? NSNumber else { return v is Bool }
        return CFGetTypeID(n) == CFBooleanGetTypeID()
    }

    /// Text of a value ("" for null).
    static func str(_ v: Any?) -> String {
        guard let v = v, !(v is NSNull) else { return "" }
        if isBool(v) { return (v as? Bool ?? false) ? "true" : "false" }
        if let s = v as? String { return s.trimmingCharacters(in: .whitespacesAndNewlines) }
        if let n = v as? NSNumber { return n.stringValue }
        if let a = v as? [Any] { return a.map { str($0) }.joined(separator: ", ") }
        if let d = v as? [String: Any] { return d.keys.sorted().map { "\($0): \(str(d[$0]))" }.joined(separator: "; ") }
        return "\(v)"
    }

    static func num(_ v: Any?) -> Double? {
        if isNull(v) || isBool(v) { return nil }
        if let n = v as? NSNumber { return n.doubleValue }
        if let s = v as? String { return Double(s.trimmingCharacters(in: .whitespaces)) }
        return nil
    }

    static func double(_ v: Any?) -> Double { num(v) ?? 0 }

    /// Python truthiness.
    static func truthy(_ v: Any?) -> Bool {
        guard let v = v, !(v is NSNull) else { return false }
        if isBool(v) { return v as? Bool ?? false }
        if let n = v as? NSNumber { return n.doubleValue != 0 }
        if let s = v as? String { return !s.isEmpty }
        if let a = v as? [Any] { return !a.isEmpty }
        if let d = v as? [String: Any] { return !d.isEmpty }
        return true
    }

    /// `a or b or c`
    static func or(_ values: Any?...) -> Any? {
        for v in values where truthy(v) { return v }
        return values.last ?? nil
    }

    static func rows(_ v: Any?) -> [Row] { (v as? [Any])?.compactMap { $0 as? Row } ?? [] }
    static func obj(_ v: Any?) -> Row { v as? Row ?? [:] }
    static func list(_ v: Any?) -> [Any] { v as? [Any] ?? [] }
}

/// Display formatting shared by registers, records and reports (Ui.java / Labels.java).
enum Fmt {
    private static let india: NumberFormatter = {
        let f = NumberFormatter()
        f.locale = Locale(identifier: "en_IN")
        f.numberStyle = .decimal
        f.minimumFractionDigits = 0
        return f
    }()

    static func num(_ value: Double, _ maxDecimals: Int = 3) -> String {
        india.maximumFractionDigits = maxDecimals
        return india.string(from: NSNumber(value: value)) ?? String(value)
    }

    static func money(_ value: Double, _ currency: String) -> String {
        let cur = currency.isEmpty || currency.uppercased() == "INR" ? "₹ " : currency.uppercased() + " "
        return cur + num(value, 2)
    }

    /// yyyy-MM-dd (or timestamp) -> dd-MM-yyyy.
    static func date(_ iso: String) -> String {
        guard iso.count >= 10 else { return iso.isEmpty ? "-" : iso }
        let parts = iso.prefix(10).split(separator: "-")
        guard parts.count == 3 else { return iso }
        return "\(parts[2])-\(parts[1])-\(parts[0])"
    }

    static func today() -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: Date())
    }

    /// Ui.pretty: ON_HOLD -> On Hold.
    static func pretty(_ status: String) -> String {
        if status.isEmpty || status == "null" { return "-" }
        return status.replacingOccurrences(of: "_", with: " ").lowercased().split(separator: " ", omittingEmptySubsequences: false)
            .map { $0.prefix(1).uppercased() + $0.dropFirst() }.joined(separator: " ")
    }

    /// Python str.title()
    static func title(_ s: String) -> String {
        var out = ""
        var up = true
        for ch in s.lowercased() {
            out += up ? String(ch).uppercased() : String(ch)
            up = !(ch.isLetter || ch.isNumber)
        }
        return out
    }
}

/// Small status chip.
struct StatusChip: View {
    let text: String
    var body: some View {
        let t = Theme.tone(text)
        Text(Fmt.pretty(text))
            .font(.caption2.weight(.bold))
            .foregroundColor(t.0)
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(t.1)
            .clipShape(Capsule())
            .lineLimit(1)
    }
}

/// Card container used across screens.
struct Card<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 6) { content }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: 14))
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line, lineWidth: 1))
    }
}

/// "label ....... value" row.
struct PairRow: View {
    let label: String
    let value: String
    var valueColor: Color = Theme.text
    var body: some View {
        HStack(alignment: .top) {
            Text(label).font(.caption).foregroundColor(Theme.muted).frame(maxWidth: .infinity, alignment: .leading)
            Text(value.isEmpty ? "-" : value).font(.footnote.weight(.semibold)).foregroundColor(valueColor)
                .multilineTextAlignment(.trailing).frame(maxWidth: .infinity, alignment: .trailing)
                .textSelection(.enabled)
        }
        .padding(.vertical, 3)
    }
}

struct SectionLabel: View {
    let text: String
    var body: some View {
        Text(text.uppercased()).font(.caption.weight(.bold)).foregroundColor(Theme.tealDark).padding(.top, 10)
    }
}

struct ErrorBox: View {
    let message: String
    var retry: (() -> Void)?
    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle").font(.title2).foregroundColor(Theme.red)
            Text(message).font(.footnote).foregroundColor(Theme.red).multilineTextAlignment(.center)
            if let retry = retry { Button("Try again", action: retry).buttonStyle(.bordered) }
        }
        .frame(maxWidth: .infinity).padding(24)
    }
}

extension View {
    /// Teal navigation bar used on every screen.
    func qcmsNavBar() -> some View {
        self.toolbarBackground(Theme.teal, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
    }
}
