import UIKit

/// Draws an RptDoc as the website's controlled A4 PDF (core/reporting.py _PageNumberCanvas + Design B):
/// FSI logo with the company under it, centred title (or HEAT NUMBER / RMTC NUMBER), plant, printed time and app version
/// on the right, teal rule, footer "Version … | Page i of N". Tables repeat their header rows on a new page and never split a row.
/// Two passes: the first only counts pages. Swift port of the Android RptPdf.
final class RptPdf {
    static let footerText = "QUALITY CONTROL MONITORING SYSTEM | Developed by Rajesh Dhokale | dhokaleraj@icloud.com | Copyrights by STAWN"
    static let mm: CGFloat = 72.0 / 25.4
    static let border = UIColor(rgb: 0xAFC3D4)
    static let mutedColor = UIColor(rgb: 0x617386)
    static let labelColor = UIColor(rgb: 0x333333)
    private let padLR: CGFloat = 2.6, padTB: CGFloat = 3.6
    private static let framePad: CGFloat = 6

    private let d: RptDoc
    private let pw: CGFloat, ph: CGFloat
    private let x0: CGFloat, top: CGFloat, bottom: CGFloat
    private let printed: String

    private var dry = true
    private var pageNo = 0, totalPages = 0
    private var ctx: UIGraphicsPDFRendererContext?
    private var y: CGFloat = 0

    private init(_ d: RptDoc) {
        self.d = d
        let pageW: CGFloat = d.landscape ? 842 : 595
        let pageH: CGFloat = d.landscape ? 595 : 842
        pw = pageW
        ph = pageH
        x0 = d.edgeMm * RptPdf.mm + RptPdf.framePad
        top = d.topMm * RptPdf.mm + RptPdf.framePad
        bottom = pageH - d.bottomMm * RptPdf.mm - RptPdf.framePad
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "dd-MM-yyyy hh:mm a"
        printed = f.string(from: Date())
    }

    static func render(_ d: RptDoc) -> Data {
        let r = RptPdf(d)
        r.dry = true
        r.run()
        r.totalPages = r.pageNo
        r.dry = false
        let renderer = UIGraphicsPDFRenderer(bounds: CGRect(x: 0, y: 0, width: r.pw, height: r.ph), format: {
            let f = UIGraphicsPDFRendererFormat()
            f.documentInfo = [kCGPDFContextTitle as String: d.title, kCGPDFContextAuthor as String: "Four Star Industries - Quality Control Monitoring System",
                              kCGPDFContextCreator as String: "STAWN QCMS iOS"]
            return f
        }())
        return renderer.pdfData { c in
            r.ctx = c
            r.run()
            r.ctx = nil
        }
    }

    private func run() {
        pageNo = 0
        newPage()
        if d.blocks.isEmpty { text("No data recorded for this report.", x0, y + 4, font(9, .regular), RptDoc.ink) }
        for b in d.blocks { draw(b) }
        finishPage()
    }

    // ------------------------------------------------------------------ fonts & primitives
    enum Weight { case regular, bold, italic, boldItalic }

    func font(_ size: CGFloat, _ w: Weight) -> UIFont {
        let name: String
        switch w {
        case .regular: name = "Helvetica"
        case .bold: name = "Helvetica-Bold"
        case .italic: name = "Helvetica-Oblique"
        case .boldItalic: name = "Helvetica-BoldOblique"
        }
        return UIFont(name: name, size: size) ?? UIFont.systemFont(ofSize: size, weight: w == .bold || w == .boldItalic ? .bold : .regular)
    }

    static func width(_ s: String, _ f: UIFont) -> CGFloat { (s as NSString).size(withAttributes: [.font: f]).width }

    /// Draw a line of text whose box top is at `topY`.
    private func text(_ s: String, _ x: CGFloat, _ topY: CGFloat, _ f: UIFont, _ color: UIColor) {
        if dry { return }
        (s as NSString).draw(at: CGPoint(x: x, y: topY), withAttributes: [.font: f, .foregroundColor: color])
    }

    /// Text whose baseline is at `base` (header / footer positions follow ReportLab baselines).
    private func textBase(_ s: String, _ x: CGFloat, _ base: CGFloat, _ f: UIFont, _ color: UIColor) { text(s, x, base - f.ascender, f, color) }
    private func centredBase(_ s: String, _ cx: CGFloat, _ base: CGFloat, _ f: UIFont, _ color: UIColor) { textBase(s, cx - RptPdf.width(s, f) / 2, base, f, color) }
    private func rightBase(_ s: String, _ rx: CGFloat, _ base: CGFloat, _ f: UIFont, _ color: UIColor) { textBase(s, rx - RptPdf.width(s, f), base, f, color) }

    private func line(_ ax: CGFloat, _ ay: CGFloat, _ bx: CGFloat, _ by: CGFloat, _ color: UIColor, _ w: CGFloat) {
        guard !dry, let cg = ctx?.cgContext else { return }
        cg.setStrokeColor(color.cgColor)
        cg.setLineWidth(w)
        cg.move(to: CGPoint(x: ax, y: ay))
        cg.addLine(to: CGPoint(x: bx, y: by))
        cg.strokePath()
    }

    private func rect(_ r: CGRect, _ color: UIColor) {
        guard !dry, let cg = ctx?.cgContext else { return }
        cg.setFillColor(color.cgColor)
        cg.fill(r)
    }

    private func box(_ r: CGRect, _ color: UIColor, _ w: CGFloat) {
        guard !dry, let cg = ctx?.cgContext else { return }
        cg.setStrokeColor(color.cgColor)
        cg.setLineWidth(w)
        cg.stroke(r)
    }

    static func wrap(_ s: String, _ width: CGFloat, _ f: UIFont, _ maxLines: Int) -> [String] {
        var out: [String] = []
        for para in s.components(separatedBy: "\n") {
            var cur = ""
            for word in para.components(separatedBy: " ") {
                let trial = cur.isEmpty ? word : cur + " " + word
                if RptPdf.width(trial, f) <= width { cur = trial; continue }
                if !cur.isEmpty { out.append(cur); cur = "" }
                var rest = word
                while RptPdf.width(rest, f) > width && rest.count > 1 {
                    var n = rest.count
                    while n > 1 && RptPdf.width(String(rest.prefix(n)), f) > width { n -= 1 }
                    out.append(String(rest.prefix(n)))
                    rest = String(rest.dropFirst(n))
                }
                cur = rest
            }
            out.append(cur)
        }
        while out.count > 1 && (out.last ?? "").isEmpty { out.removeLast() }
        if out.count > maxLines {
            var cut = Array(out.prefix(maxLines))
            cut[maxLines - 1] += "…"
            return cut
        }
        return out
    }

    static func fit(_ s: String, _ width: CGFloat, _ f: UIFont) -> String {
        if RptPdf.width(s, f) <= width { return s }
        var t = s
        while t.count > 1 && RptPdf.width(t + "…", f) > width { t.removeLast() }
        return t + "…"
    }

    static func image(_ data: Data?) -> UIImage? {
        guard let data = data, !data.isEmpty, let img = UIImage(data: data) else { return nil }
        let maxSide: CGFloat = 1400
        let w = img.size.width * img.scale, h = img.size.height * img.scale
        if max(w, h) <= maxSide { return img }
        let s = maxSide / max(w, h)
        return img.preparingThumbnail(of: CGSize(width: w * s, height: h * s)) ?? img
    }

    // ------------------------------------------------------------------ pages
    private func newPage() {
        finishPage()
        pageNo += 1
        if !dry { ctx?.beginPage() }
        y = top
    }

    private func finishPage() {
        if pageNo == 0 { return }
        if !dry { headerFooter() }
    }

    private var room: CGFloat { bottom - y }

    private func need(_ h: CGFloat) { if h > room && y > top + 1 { newPage() } }

    private static func cut(_ s: String, _ n: Int) -> String { s.count > n ? String(s.prefix(n)) : s }

    static func splitTitle(_ title: String) -> (String, String) {
        let t = title.trimmingCharacters(in: .whitespaces)
        if let r = t.range(of: " - ") { return (String(t[..<r.lowerBound]).trimmingCharacters(in: .whitespaces), String(t[r.upperBound...]).trimmingCharacters(in: .whitespaces)) }
        if t.count <= 34 { return (t, "") }
        let chars = Array(t)
        var at = -1
        for i in stride(from: 33, through: 0, by: -1) where chars[i] == " " { at = i; break }
        if at < 18 { at = 34 }
        return (String(chars[0..<at]).trimmingCharacters(in: .whitespaces), String(chars[at...]).trimmingCharacters(in: .whitespaces))
    }

    /// _PageNumberCanvas._draw_header_footer.
    private func headerFooter() {
        let mm = RptPdf.mm
        let portrait = ph >= pw
        let edge = (portrait ? 8 : 10) * mm
        let hy = (portrait ? 27 : 29) * mm
        let rightPanel = (portrait ? 48 : 63) * mm
        if let logo = UIImage(named: "FSILogo") {
            let bw = (portrait ? 26 : 28) * mm, bh = 13 * mm
            let boxTop = hy - 6 * mm - bh
            let s = min(bw / logo.size.width, bh / logo.size.height)
            let w = logo.size.width * s, h = logo.size.height * s
            logo.draw(in: CGRect(x: edge + (bw - w) / 2, y: boxTop + (bh - h) / 2, width: w, height: h))
        }
        textBase(d.company.isEmpty ? "FOUR STAR INDUSTRIES" : d.company, edge, hy - 2.6 * mm, font(portrait ? 6.6 : 7.2, .bold), RptDoc.ink)
        let cl = edge + (portrait ? 36 : 40) * mm, cr = pw - edge - rightPanel - 3 * mm, cx = (cl + cr) / 2
        if !d.heatNumber.isEmpty {
            centredBase(RptPdf.cut("HEAT NUMBER: " + d.heatNumber, 40), cx, hy - 12.2 * mm, font(portrait ? 12.5 : 14.5, .bold), RptDoc.ink)
            centredBase(RptPdf.cut(!d.recordNumber.isEmpty ? "RMTC NUMBER: " + d.recordNumber : d.title, 50), cx, hy - 7.0 * mm, font(portrait ? 8.6 : 10, .bold), RptDoc.ink)
            if !d.reportLabel.isEmpty {
                centredBase(RptPdf.cut(d.reportLabel, 55), cx, hy - 3.2 * mm, font(portrait ? 6.6 : 7.4, .regular), UIColor(rgb: 0x555555))
            }
        } else {
            let t = RptPdf.splitTitle(d.title)
            centredBase(RptPdf.cut(t.0, 44), cx, hy - (t.1.isEmpty ? 10.0 : 12.4) * mm, font(portrait ? 11.2 : 14, .bold), RptDoc.ink)
            if !t.1.isEmpty { centredBase(RptPdf.cut(t.1, 50), cx, hy - 7.0 * mm, font(portrait ? 9.0 : 10.5, .bold), RptDoc.ink) }
        }
        let grey = UIColor(rgb: 0x333333)
        rightBase("Plant: " + d.plantCode, pw - edge, hy - 13.2 * mm, font(portrait ? 7.4 : 8, .bold), grey)
        let small = font(portrait ? 6.8 : 7.4, .regular)
        rightBase("Printed: " + printed, pw - edge, hy - 9.0 * mm, small, grey)
        rightBase("App Version: " + AppConfig.webVersion, pw - edge, hy - 4.8 * mm, small, grey)
        line(edge, hy - 1.2 * mm, pw - edge, hy - 1.2 * mm, d.accent, 1.6)

        let fy = ph - 9.2 * mm
        line(edge, fy, pw - edge, fy, RptPdf.border, 0.45)
        let ff = font(portrait ? 6.4 : 7.0, .regular)
        let foot = d.footer.isEmpty ? RptPdf.footerText : d.footer
        let pageText = "Version \(AppConfig.webVersion) | Page \(pageNo) of \(max(totalPages, pageNo))"
        let maxFoot = pw - 2 * edge - RptPdf.width(pageText, ff) - 12
        textBase(RptPdf.fit(foot, maxFoot, ff), edge + 1 * mm, ph - 5.6 * mm, ff, RptPdf.mutedColor)
        rightBase(pageText, pw - edge - 1 * mm, ph - 5.6 * mm, ff, RptPdf.mutedColor)
    }

    // ------------------------------------------------------------------ blocks
    private func draw(_ b: RptBlock) {
        switch b {
        case let x as RptBar: bar(x)
        case let x as RptLabeled: labeled(x)
        case let x as RptGrid: grid(x)
        case let x as RptConclusion: conclusion(x)
        case let x as RptPhotos: photos(x)
        case let x as RptChart: chart(x)
        case let x as RptText: paragraph(x)
        case let x as RptSpace: y += x.mm * RptPdf.mm; if y > bottom { newPage() }
        case let x as RptKeep: need(x.mm * RptPdf.mm)
        case let x as RptBendPanel: bendPanel(x)
        case let x as RptSignatures: signatures(x)
        default: break
        }
    }

    /// _rmtc_section_bar: teal band with white capitals; light = teal text over a teal rule.
    private func bar(_ b: RptBar) {
        var light = b.light
        let style = b.fixedFill ? "fill" : d.barStyle
        let outline = !light && style == "outline"
        var t = b.fixedFill ? b.text : d.relabel(b.text)
        if !light && style == "underline" { light = true; t = t.uppercased() }
        if !b.light && !b.keepCase { t = t.uppercased() }
        let size: CGFloat = b.fixedFill ? 10.5 : (light ? max(8, d.headingPt - 0.9) : d.headingPt)
        let f = font(size, .bold)
        let lead = size + 2.1
        let padL: CGFloat = light ? 1 : 5
        let padT: CGFloat = light ? 3 : (b.fixedFill ? 3.5 : 4.2)
        let padB: CGFloat = light ? 2.4 : (b.fixedFill ? 3.5 : 4.2)
        let w = d.contentMm * RptPdf.mm
        let lines = RptPdf.wrap(t, w - padL - 4, f, 3)
        let h = padT + padB + CGFloat(lines.count) * lead
        y += (b.fixedFill ? 2 : 2.2) * RptPdf.mm
        need(h + 34)
        if light { line(x0, y + h, x0 + w, y + h, d.accent, 0.9) }
        else if outline { box(CGRect(x: x0, y: y, width: w, height: h), d.accent, 0.9) }
        else { rect(CGRect(x: x0, y: y, width: w, height: h), d.accent) }
        var ty = y + padT
        for l in lines { text(l, x0 + padL, ty + (lead - f.lineHeight) / 2, f, light || outline ? d.accent : .white); ty += lead }
        y += h
    }

    private func widths(_ w: [CGFloat]) -> [CGFloat] {
        let sum = w.reduce(0, +)
        let content = d.contentMm * RptPdf.mm
        return w.map { sum <= 1.01 ? $0 * content : $0 * RptPdf.mm }
    }

    struct Cell {
        let text: String
        let font: UIFont
        let color: UIColor
        let align: RptDoc.Align
    }

    private func lineHeight(_ c: Cell, _ lead: CGFloat) -> CGFloat { c.font.pointSize > lead - 1.5 ? c.font.pointSize + 2 : lead }

    private func rowHeight(_ cells: [Cell], _ w: [CGFloat], _ lead: CGFloat, _ padTB: CGFloat, _ padLR: CGFloat? = nil) -> CGFloat {
        let lr = padLR ?? self.padLR
        var h: CGFloat = 0
        for (i, c) in cells.enumerated() where i < w.count {
            let n = max(1, RptPdf.wrap(c.text, w[i] - 2 * lr, c.font, 60).count)
            h = max(h, CGFloat(n) * lineHeight(c, lead) + 2 * padTB)
        }
        return h
    }

    /// Cells vertically centred (VALIGN MIDDLE); text beyond the row height is cut.
    private func drawRow(_ cells: [Cell], _ w: [CGFloat], _ topY: CGFloat, _ lead: CGFloat, _ padTB: CGFloat, _ height: CGFloat? = nil, _ padLR: CGFloat? = nil) {
        if dry { return }
        let lr = padLR ?? self.padLR
        let h = height ?? rowHeight(cells, w, lead, padTB, lr)
        var x = x0
        for (i, c) in cells.enumerated() where i < w.count {
            let cl = lineHeight(c, lead)
            var lines = RptPdf.wrap(c.text, w[i] - 2 * lr, c.font, 60)
            let maxLines = max(1, Int(floor((h - 2 * padTB) / cl + 0.05)))
            if lines.count > maxLines { lines = Array(lines.prefix(maxLines)) }
            var ty = topY + (h - CGFloat(lines.count) * cl) / 2
            for l in lines {
                let tw = RptPdf.width(l, c.font)
                let tx: CGFloat
                switch c.align {
                case .center: tx = x + (w[i] - tw) / 2
                case .right: tx = x + w[i] - lr - tw
                case .left: tx = x + lr
                }
                text(l, tx, ty + (cl - c.font.lineHeight) / 2, c.font, c.color)
                ty += cl
            }
            x += w[i]
        }
    }

    /// _rmtc_labeled_grid.
    private func labeled(_ g: RptLabeled) {
        let w = widths(g.w)
        let size = g.size, lead = size + 2
        let total = w.reduce(0, +)
        for (ri, row) in g.rows.enumerated() {
            var cells: [Cell] = []
            for i in 0..<min(row.count, w.count) {
                let v = row[i]
                if g.labelCols.contains(i) {
                    cells.append(Cell(text: v, font: font(g.labelSize > 0 ? g.labelSize : size, .bold), color: RptPdf.labelColor, align: .left))
                } else {
                    let prev = i > 0 && g.labelCols.contains(i - 1) ? row[i - 1] : ""
                    let pu = prev.uppercased()
                    var weight: Weight = g.valueBold ? .bold : .regular
                    var color = RptDoc.ink
                    if let vc = g.valueColor { color = vc }
                    else if RptDoc.isRemark(prev) { weight = .italic; color = d.remarkColor }
                    else if RptDoc.isConclusion(prev) { weight = .bold; color = d.conclusionColor }
                    else if (pu.contains("DISPOSITION") || pu.contains("DECISION") || pu.contains("RESULT") || pu.contains("STATUS")) && !pu.contains("REASON") {
                        let sc = RptDoc.statusColor(v)
                        if sc != RptDoc.ink { weight = .bold; color = sc }
                    }
                    cells.append(Cell(text: v, font: font(size, weight), color: color, align: g.center ? .center : .left))
                }
            }
            let h = rowHeight(cells, w, lead, padTB)
            if h > room { newPage() }
            if g.ruled && ri == 0 { line(x0, y, x0 + total, y, RptDoc.ink, 1.0) }
            drawRow(cells, w, y, lead, padTB, h)
            y += h
            if g.ruled { line(x0, y, x0 + total, y, RptDoc.ink, 1.0) } else { line(x0, y, x0 + total, y, d.rule, 0.4) }
        }
    }

    /// _rmtc_grid with repeated header rows.
    private func grid(_ g: RptGrid) {
        if g.rows.isEmpty { return }
        let w = widths(g.w)
        let cols = w.count
        let headLead = g.headSize + 1.8, lead = g.cellSize + 2
        let header = g.rows[max(0, g.headerRows - 1)]
        var align: [RptDoc.Align] = []
        var remark = Set<Int>(), concl = Set<Int>()
        for i in 0..<cols {
            let h = i < header.count ? header[i] : ""
            align.append(g.noAlign ? .left : RptDoc.alignment(h))
            let first = i < g.rows[0].count ? g.rows[0][i] : ""
            if RptDoc.isRemark(first) { remark.insert(i) }
            if RptDoc.isConclusion(first) { concl.insert(i) }
        }
        var heads: [[Cell]] = []
        for r in 0..<min(g.headerRows, g.rows.count) {
            var cells: [Cell] = []
            for i in 0..<cols {
                let v = i < g.rows[r].count ? g.rows[r][i] : ""
                let labelCell = g.firstColBold && i == 0
                cells.append(Cell(text: v, font: font(g.headSize, g.plainHeader ? .regular : .bold), color: RptDoc.ink, align: labelCell || g.noAlign ? .left : .center))
            }
            heads.append(cells)
        }
        let headH = heads.reduce(CGFloat(0)) { $0 + rowHeight($1, w, headLead, padTB) }
        let total = w.reduce(0, +)
        var drawn = false
        func drawHeader() {
            if !g.noTopLine { line(x0, y, x0 + total, y, RptDoc.ink, 1.0) }
            for hc in heads {
                let hh = rowHeight(hc, w, headLead, padTB)
                drawRow(hc, w, y, headLead, padTB, hh)
                y += hh
            }
            line(x0, y, x0 + total, y, RptDoc.ink, 1.0)
        }
        if g.rows.count > g.headerRows {
            for r in g.headerRows..<g.rows.count {
                let row = g.rows[r]
                var cells: [Cell] = []
                for i in 0..<cols {
                    let v = i < row.count ? row[i] : ""
                    var weight: Weight = .regular
                    var color = RptDoc.ink
                    if g.firstColBold && i == 0 { weight = .bold }
                    else if g.statusCols.contains(i) { weight = .bold; color = RptDoc.statusColor(v) }
                    else if remark.contains(i) { weight = .italic; color = d.remarkColor }
                    else if concl.contains(i) { weight = .bold; color = d.conclusionColor }
                    var a: RptDoc.Align = g.allCenter && !(g.firstColBold && i == 0) ? .center : align[i]
                    if !g.allCenter && !g.noAlign && a == .left && RptDoc.plainNumber(v) { a = .center }
                    cells.append(Cell(text: v, font: font(g.cellSize, weight), color: color, align: a))
                }
                var h = rowHeight(cells, w, lead, padTB)
                let cap = bottom - top - headH - 4
                if h > cap { h = cap }
                if !drawn {
                    if headH + h > room { newPage() }
                    drawHeader()
                    drawn = true
                } else if h > room {
                    newPage()
                    drawHeader()
                }
                drawRow(cells, w, y, lead, padTB, h)
                y += h
                line(x0, y, x0 + total, y, d.rule, 0.4)
            }
        }
        if !drawn {
            need(headH)
            drawHeader()
        }
    }

    /// _quality_conclusion_table.
    private func conclusion(_ k: RptConclusion) {
        let size = d.bodyPt
        let w: [CGFloat] = [40 * RptPdf.mm, d.contentMm * RptPdf.mm - 40 * RptPdf.mm]
        var rows: [(String, String, String)] = [("Conclusion", k.conclusion, "C")]
        if !k.remark.trimmingCharacters(in: .whitespaces).isEmpty { rows.append(("Conclusion Remark", k.remark, "R")) }
        rows.append(("Final Decision", k.decision, "D"))
        rows.append(("Decision Reason", k.reason, "W"))
        let total = w[0] + w[1]
        need(60)
        line(x0, y, x0 + total, y, RptDoc.ink, 1.0)
        for (i, r) in rows.enumerated() {
            let value = RptDoc.v(r.1)
            let label = Cell(text: r.0, font: font(size, .bold), color: RptPdf.labelColor, align: .left)
            let val: Cell
            switch r.2 {
            case "C": val = Cell(text: value, font: font(size + 1.4, .bold), color: d.conclusionColor, align: .left)
            case "R": val = Cell(text: value, font: font(size + 0.6, .italic), color: d.remarkColor, align: .left)
            case "D": val = Cell(text: value, font: font(size + 1.4, .bold), color: RptDoc.statusColor(r.1), align: .left)
            default: val = value.trimmingCharacters(in: .whitespaces).isEmpty ? Cell(text: value, font: font(size, .regular), color: RptDoc.ink, align: .left)
                : Cell(text: value, font: font(size, .italic), color: d.remarkColor, align: .left)
            }
            let lead = size + 3.6
            let h = rowHeight([label, val], w, lead, 4)
            if h > room { newPage() }
            drawRow([label, val], w, y, lead, 4, h)
            y += h
            let last = i == rows.count - 1
            line(x0, y, x0 + total, y, last ? RptDoc.ink : d.rule, last ? 1.0 : 0.4)
        }
    }

    /// _photo_grid_table / _microstructure_photo_table.
    private func photos(_ p: RptPhotos) {
        let cols = max(1, p.cols)
        let total = d.contentMm * RptPdf.mm
        let colW = total / CGFloat(cols)
        let maxH = p.maxHmm * RptPdf.mm
        let capFont = font(d.bodyPt, .regular)
        let capLead = d.bodyPt + 2
        if p.items.isEmpty {
            let h = capLead + 6
            need(h)
            box(CGRect(x: x0, y: y, width: total, height: h), RptPdf.border, 0.55)
            let msg = "No microstructure photographs recorded"
            text(msg, x0 + total / 2 - RptPdf.width(msg, capFont) / 2, y + 3, capFont, RptDoc.ink)
            y += h
            return
        }
        var start = 0
        while start < p.items.count {
            var rowH: CGFloat = 0
            var imgs: [UIImage?] = Array(repeating: nil, count: cols)
            var imgH: [CGFloat] = Array(repeating: 0, count: cols)
            for i in 0..<cols where start + i < p.items.count {
                let ph = p.items[start + i]
                imgs[i] = ph.has ? RptPdf.image(ph.data) : nil
                let boxW = colW - 6 * RptPdf.mm
                if let im = imgs[i] {
                    let s = min(boxW / im.size.width, maxH / im.size.height)
                    imgH[i] = im.size.height * s
                } else {
                    imgH[i] = p.slots ? min(maxH, 36 * RptPdf.mm) : maxH - 5 * RptPdf.mm
                }
                let capLines = RptPdf.wrap(ph.caption, colW - 6, capFont, 3).count
                rowH = max(rowH, 3 + imgH[i] + 1 * RptPdf.mm + CGFloat(capLines) * capLead + 3)
            }
            need(rowH)
            box(CGRect(x: x0, y: y, width: total, height: rowH), RptPdf.border, 0.55)
            for i in 1..<max(cols, 1) where cols > 1 { line(x0 + CGFloat(i) * colW, y, x0 + CGFloat(i) * colW, y + rowH, RptPdf.border, 0.35) }
            for i in 0..<cols where start + i < p.items.count {
                let ph = p.items[start + i]
                let cx = x0 + CGFloat(i) * colW + colW / 2
                var ty = y + 3
                let boxW = colW - 6 * RptPdf.mm
                if let im = imgs[i] {
                    let s = min(boxW / im.size.width, maxH / im.size.height)
                    let iw = im.size.width * s
                    if !dry { im.draw(in: CGRect(x: cx - iw / 2, y: ty, width: iw, height: imgH[i])) }
                } else {
                    let bw = p.slots ? colW - 6 * RptPdf.mm : colW - 8 * RptPdf.mm
                    box(CGRect(x: cx - bw / 2, y: ty, width: bw, height: imgH[i]), RptPdf.border, 0.5)
                    let msg = "No photograph uploaded"
                    text(msg, cx - RptPdf.width(msg, capFont) / 2, ty + imgH[i] / 2 - capFont.lineHeight / 2, capFont, RptDoc.ink)
                }
                ty += imgH[i] + 1 * RptPdf.mm
                for l in RptPdf.wrap(ph.caption, colW - 6, capFont, 3) {
                    text(l, cx - RptPdf.width(l, capFont) / 2, ty, capFont, RptDoc.ink)
                    ty += capLead
                }
            }
            y += rowH
            start += cols
        }
    }

    /// _case_depth_chart: Distance (mm) vs Hardness (HV).
    private func chart(_ k: RptChart) {
        if k.series.isEmpty { return }
        let width = d.contentMm * RptPdf.mm, height = 58 * RptPdf.mm
        need(height)
        if !dry, let cg = ctx?.cgContext { RptPdf.drawChart(cg, k, CGRect(x: x0, y: y, width: width, height: height)) }
        y += height
    }

    static let palette: [UIColor] = [UIColor(rgb: 0x083B6E), UIColor(rgb: 0x0B76B7), UIColor(rgb: 0x2E8B57), UIColor(rgb: 0x7B3FB8), UIColor(rgb: 0xC55A11), UIColor(rgb: 0x5B6573)]

    static func nice(_ raw: Double) -> Double {
        if raw <= 0 { return 1 }
        let e = pow(10, floor(log10(raw)))
        let f = raw / e
        let n: Double = f < 1.5 ? 1 : (f < 3 ? 2 : (f < 7 ? 5 : 10))
        return n * e
    }

    /// Shared with the on-screen report.
    static func drawChart(_ cg: CGContext, _ k: RptChart, _ r: CGRect) {
        var minX = Double.greatestFiniteMagnitude, maxX = -Double.greatestFiniteMagnitude, minY = Double.greatestFiniteMagnitude, maxY = -Double.greatestFiniteMagnitude
        for s in k.series { for p in s { minX = min(minX, p.0); maxX = max(maxX, p.0); minY = min(minY, p.1); maxY = max(maxY, p.1) } }
        if minX > maxX { return }
        let xMin = max(0, minX), xMax = maxX > minX ? maxX : minX + 0.1
        let pad = max(20.0, (maxY - minY) * 0.1)
        let yMin = max(0, minY - pad), yMax = maxY + pad
        let px = r.minX + 36, plotW = max(80, r.width - 128), plotH = max(70, r.height - 38)
        let py = r.minY + r.height - 22 - plotH
        let small = UIFont(name: "Helvetica", size: 5.5) ?? .systemFont(ofSize: 5.5)
        let boldF = UIFont(name: "Helvetica-Bold", size: 6) ?? .boldSystemFont(ofSize: 6)
        let textColor = UIColor(rgb: 0x17212B)
        cg.setStrokeColor(UIColor.black.cgColor)
        cg.setLineWidth(0.5)
        cg.move(to: CGPoint(x: px, y: py + plotH)); cg.addLine(to: CGPoint(x: px + plotW, y: py + plotH))
        cg.move(to: CGPoint(x: px, y: py)); cg.addLine(to: CGPoint(x: px, y: py + plotH))
        cg.strokePath()
        func draw(_ s: String, _ x: CGFloat, _ baseY: CGFloat, _ f: UIFont) {
            (s as NSString).draw(at: CGPoint(x: x, y: baseY - f.ascender), withAttributes: [.font: f, .foregroundColor: textColor])
        }
        let xStep = nice((xMax - xMin) / 6), yStep = nice((yMax - yMin) / 6)
        var v = (xMin / xStep).rounded(.up) * xStep
        while v <= xMax + 1e-9 {
            let x = px + CGFloat((v - xMin) / (xMax - xMin)) * plotW
            cg.move(to: CGPoint(x: x, y: py + plotH)); cg.addLine(to: CGPoint(x: x, y: py + plotH + 3)); cg.strokePath()
            let s = String(format: "%.2f", v)
            draw(s, x - width(s, small) / 2, py + plotH + 10, small)
            v += xStep
        }
        v = (yMin / yStep).rounded(.up) * yStep
        while v <= yMax + 1e-9 {
            let yy = py + plotH - CGFloat((v - yMin) / (yMax - yMin)) * plotH
            cg.move(to: CGPoint(x: px - 3, y: yy)); cg.addLine(to: CGPoint(x: px, y: yy)); cg.strokePath()
            let s = String(Int(v))
            draw(s, px - 5 - width(s, small), yy + 2, small)
            v += yStep
        }
        for (si, s) in k.series.enumerated() {
            let col = palette[si % palette.count]
            cg.setStrokeColor(col.cgColor)
            cg.setFillColor(col.cgColor)
            cg.setLineWidth(1.3)
            var last: CGPoint? = nil
            for p in s {
                let pt = CGPoint(x: px + CGFloat((p.0 - xMin) / (xMax - xMin)) * plotW, y: py + plotH - CGFloat((p.1 - yMin) / (yMax - yMin)) * plotH)
                if let l = last { cg.move(to: l); cg.addLine(to: pt); cg.strokePath() }
                cg.fillEllipse(in: CGRect(x: pt.x - 1.75, y: pt.y - 1.75, width: 3.5, height: 3.5))
                last = pt
            }
        }
        draw("Distance (mm)", px + plotW / 2 - width("Distance (mm)", boldF) / 2, r.minY + r.height - 2, boldF)
        draw("Hardness (HV)", r.minX + 2, r.minY + 6, boldF)
        let lgx = r.minX + r.width - 86, lgy = r.minY + 18
        for (i, n) in k.names.enumerated() {
            cg.setFillColor(palette[i % palette.count].cgColor)
            cg.fill(CGRect(x: lgx, y: lgy + CGFloat(i) * 8 - 4, width: 5, height: 5))
            draw(n, lgx + 8, lgy + CGFloat(i) * 8 + 1, small)
        }
    }

    private func paragraph(_ t: RptText) {
        var size = d.bodyPt
        var weight: Weight = .regular
        var color = RptDoc.ink
        var centred = false
        switch t.style {
        case .small: size = 7.4
        case .center: centred = true
        case .big: size = 20; centred = true
        case .remark: weight = .boldItalic; color = d.remarkColor; centred = true
        case .heading: weight = .bold
        case .concl: size = 9.6; weight = .bold; color = d.conclusionColor
        case .subtitle: size = 6.2; color = RptPdf.mutedColor; centred = true
        case .normal: break
        }
        let f = font(size, weight)
        let lead: CGFloat = t.style == .big ? 24 : (t.style == .subtitle ? 7.4 : size + 2)
        let w = d.contentMm * RptPdf.mm
        for l in RptPdf.wrap(t.text, w, f, 40) {
            if lead > room { newPage() }
            let tw = RptPdf.width(l, f)
            let tx = centred ? x0 + w / 2 - tw / 2 : x0
            text(l, tx, y + (lead - f.lineHeight) / 2, f, color)
            if t.style == .heading { line(x0, y + lead - 1, x0 + tw, y + lead - 1, color, 0.5) }
            y += lead
        }
        if t.style == .subtitle { y += 2 * RptPdf.mm }
    }

    private func photoHeight(_ ph: RptPhoto?, _ w: CGFloat, _ h: CGFloat, _ placeholder: CGFloat) -> CGFloat {
        guard let ph = ph, ph.has, let im = RptPdf.image(ph.data) else { return min(h, placeholder) }
        return im.size.height * min(w / im.size.width, h / im.size.height)
    }

    @discardableResult
    private func drawPhoto(_ ph: RptPhoto?, _ cx: CGFloat, _ ty: CGFloat, _ w: CGFloat, _ h: CGFloat, _ placeholder: CGFloat) -> CGFloat {
        guard let ph = ph, ph.has, let im = RptPdf.image(ph.data) else {
            let hh = min(h, placeholder)
            box(CGRect(x: cx - w / 2, y: ty, width: w, height: hh), RptPdf.border, 0.4)
            let f = font(d.bodyPt, .regular)
            let msg = "No image uploaded"
            text(msg, cx - RptPdf.width(msg, f) / 2, ty + hh / 2 - f.lineHeight / 2, f, RptDoc.ink)
            return hh
        }
        let s = min(w / im.size.width, h / im.size.height)
        let iw = im.size.width * s, ih = im.size.height * s
        if !dry { im.draw(in: CGRect(x: cx - iw / 2, y: ty, width: iw, height: ih)) }
        return ih
    }

    private func bendPanel(_ b: RptBendPanel) {
        let mm = RptPdf.mm
        let W = d.contentMm * mm, half = W / 2
        let imgW = half - 6 * mm
        let leftH = photoHeight(b.left, imgW, 112 * mm, 30 * mm)
        var rightH = 24 + 2 * mm + photoHeight(b.r1, imgW, 48 * mm, 30 * mm) + 2 * mm + photoHeight(b.r2, imgW, 48 * mm, 30 * mm)
        if let r3 = b.r3, r3.has { rightH += 2 * mm + photoHeight(r3, imgW, 30 * mm, 30 * mm) }
        let sf = font(d.bodyPt, .boldItalic)
        let surface = RptPdf.wrap(b.surface, half - 12, sf, 6)
        rightH += 2 * mm + CGFloat(surface.count) * (d.bodyPt + 2)
        let h = max(leftH, rightH) + 6
        let bf = font(10.5, .bold)
        let bandH: CGFloat = 3.5 * 2 + 12.6
        y += 2 * mm
        need(bandH + min(h, 200))
        rect(CGRect(x: x0, y: y, width: W, height: bandH), d.accent)
        text("Load Vs CHT", x0 + 5, y + 3.5 + (12.6 - bf.lineHeight) / 2, bf, .white)
        text("Bend Test Part", x0 + half + 5, y + 3.5 + (12.6 - bf.lineHeight) / 2, bf, .white)
        y += bandH
        need(h)
        let top0 = y + 3
        drawPhoto(b.left, x0 + half / 2, top0, imgW, 112 * mm, 30 * mm)
        var ry = top0
        let big = font(20, .regular)
        text(b.angle, x0 + half + half / 2 - RptPdf.width(b.angle, big) / 2, ry + (24 - big.lineHeight) / 2, big, RptDoc.ink)
        ry += 24 + 2 * mm
        ry += drawPhoto(b.r1, x0 + half + half / 2, ry, imgW, 48 * mm, 30 * mm) + 2 * mm
        ry += drawPhoto(b.r2, x0 + half + half / 2, ry, imgW, 48 * mm, 30 * mm)
        if let r3 = b.r3, r3.has { ry += 2 * mm; ry += drawPhoto(r3, x0 + half + half / 2, ry, imgW, 30 * mm, 30 * mm) }
        ry += 2 * mm
        for l in surface {
            text(l, x0 + half + half / 2 - RptPdf.width(l, sf) / 2, ry, sf, d.remarkColor)
            ry += d.bodyPt + 2
        }
        y += h
    }

    private func signatures(_ s: RptSignatures) {
        let w = widths(s.w)
        let size = d.bodyPt, lead = size + 1.8
        let vals = s.values.map { Cell(text: $0, font: font(size, .regular), color: RptDoc.ink, align: .left) }
        let labs = s.labels.map { Cell(text: $0, font: font(size, .bold), color: RptDoc.ink, align: .left) }
        let h1 = rowHeight(vals, w, lead, 3, 6), h2 = rowHeight(labs, w, lead, 3, 6)
        need(h1 + h2)
        drawRow(vals, w, y, lead, 3, h1, 6)
        y += h1
        drawRow(labs, w, y, lead, 3, h2, 6)
        y += h2
    }
}
