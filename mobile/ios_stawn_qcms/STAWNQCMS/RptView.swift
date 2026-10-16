import SwiftUI

/// Shows an RptDoc on screen: every section, result table, conclusion and photograph of the report in the printed order.
struct RptView: View {
    let doc: RptDoc

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(doc.heatNumber.isEmpty ? doc.title : "HEAT NUMBER: \(doc.heatNumber)\(doc.recordNumber.isEmpty ? "" : " · \(doc.recordNumber)")")
                .font(.headline).foregroundColor(Theme.text)
            ForEach(Array(doc.blocks.enumerated()), id: \.offset) { pair in
                block(pair.element, index: pair.offset)
            }
        }
    }

    private func lastBar(before index: Int) -> String {
        var i = index - 1
        while i >= 0 {
            if let b = doc.blocks[i] as? RptBar { return b.fixedFill ? b.text : doc.relabel(b.text) }
            i -= 1
        }
        return doc.title
    }

    @ViewBuilder private func block(_ b: RptBlock, index: Int) -> some View {
        if let bar = b as? RptBar {
            let text = bar.fixedFill ? bar.text : doc.relabel(bar.text)
            if bar.light {
                Text(text).font(.subheadline.weight(.bold)).foregroundColor(Color(doc.accent)).padding(.top, 6)
            } else {
                Text(bar.keepCase ? text : text.uppercased()).font(.subheadline.weight(.bold)).foregroundColor(.white)
                    .padding(.horizontal, 10).padding(.vertical, 7).frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(doc.accent)).clipShape(RoundedRectangle(cornerRadius: 6)).padding(.top, 8)
            }
        } else if let g = b as? RptLabeled {
            Card {
                ForEach(pairs(g).indices, id: \.self) { i in
                    let p = pairs(g)[i]
                    PairRow(label: p.0, value: p.1, valueColor: p.2)
                }
            }
        } else if let g = b as? RptGrid {
            if !g.rows.isEmpty {
                let head = g.rows[max(0, g.headerRows - 1)].map { $0.isEmpty ? " " : $0 }
                let data = Array(g.rows.dropFirst(g.headerRows)).map { r in head.indices.map { $0 < r.count ? r[$0] : "" } }
                VStack(alignment: .leading, spacing: 2) {
                    SheetGrid(columns: head, rows: data, statusColumns: g.statusCols, maxHeight: 360)
                        .frame(height: min(360, CGFloat(data.count) * 34 + 44))
                    Text(lastBar(before: index)).font(.caption2).foregroundColor(Theme.muted)
                }
            }
        } else if let k = b as? RptConclusion {
            Card {
                line("Conclusion", RptDoc.v(k.conclusion), Color(doc.conclusionColor), bold: true)
                if !k.remark.trimmingCharacters(in: .whitespaces).isEmpty { line("Conclusion Remark", k.remark, Color(doc.remarkColor), bold: false) }
                line("Final Decision", RptDoc.v(k.decision), Color(RptDoc.statusColor(k.decision)), bold: true)
                line("Decision Reason", RptDoc.v(k.reason), Color(doc.remarkColor), bold: false)
            }
        } else if let p = b as? RptPhotos {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 150), spacing: 8)], spacing: 8) {
                ForEach(p.items.indices, id: \.self) { i in photo(p.items[i]) }
            }
        } else if let p = b as? RptBendPanel {
            Text("Bend angle \(p.angle)").font(.title2).frame(maxWidth: .infinity)
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 150), spacing: 8)], spacing: 8) {
                ForEach(Array([p.left, p.r1, p.r2, p.r3].compactMap { $0 }.filter { $0.has }.enumerated()), id: \.offset) { pair in photo(pair.element) }
            }
            if !p.surface.isEmpty { Text(p.surface).font(.footnote.bold().italic()).foregroundColor(Color(doc.remarkColor)) }
        } else if let c = b as? RptChart {
            ChartImage(chart: c).frame(height: 190)
        } else if let t = b as? RptText {
            Text(t.text).font(t.style == .small || t.style == .subtitle ? .caption : .footnote)
                .fontWeight(t.style == .heading || t.style == .concl ? .bold : .regular)
                .foregroundColor(t.style == .concl ? Color(doc.conclusionColor) : (t.style == .remark ? Color(doc.remarkColor) : Theme.text))
        } else if let s = b as? RptSignatures {
            Card {
                ForEach(s.labels.indices, id: \.self) { i in PairRow(label: s.labels[i], value: i < s.values.count ? s.values[i] : "") }
            }
        }
    }

    private func pairs(_ g: RptLabeled) -> [(String, String, Color)] {
        var out: [(String, String, Color)] = []
        for row in g.rows {
            for i in row.indices where g.labelCols.contains(i) {
                let label = row[i]
                let value = i + 1 < row.count ? row[i + 1] : ""
                if label.isEmpty && value.isEmpty { continue }
                var color = Theme.text
                let lu = label.uppercased()
                if let vc = g.valueColor, vc != RptDoc.ink { color = Color(vc) }
                else if RptDoc.isRemark(label) { color = Color(doc.remarkColor) }
                else if RptDoc.isConclusion(label) { color = Color(doc.conclusionColor) }
                else if (lu.contains("DISPOSITION") || lu.contains("DECISION") || lu.contains("RESULT") || lu.contains("STATUS")) && !lu.contains("REASON") {
                    let c = RptDoc.statusColor(value.replacingOccurrences(of: " ", with: "_"))
                    if c != RptDoc.ink { color = Color(c) }
                }
                out.append((label, value, color))
            }
        }
        return out
    }

    private func line(_ label: String, _ value: String, _ color: Color, bold: Bool) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.caption.weight(.bold)).foregroundColor(Theme.muted)
            Text(value.isEmpty ? "-" : value).font(bold ? .body.weight(.bold) : .footnote).foregroundColor(color)
        }
        .padding(.vertical, 3)
    }

    private func photo(_ p: RptPhoto) -> some View {
        VStack(spacing: 4) {
            if p.has, let img = RptPdf.image(p.data) {
                Image(uiImage: img).resizable().scaledToFit().clipShape(RoundedRectangle(cornerRadius: 8))
            } else {
                Text("No photograph uploaded").font(.caption).foregroundColor(Theme.muted)
                    .frame(maxWidth: .infinity, minHeight: 90).background(Color.white)
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.lineStrong))
            }
            Text(p.caption).font(.caption2).foregroundColor(Theme.muted).multilineTextAlignment(.center)
        }
    }
}

/// Case-depth chart drawn with the same code as the PDF.
struct ChartImage: View {
    let chart: RptChart
    var body: some View {
        let image = UIGraphicsImageRenderer(size: CGSize(width: 560, height: 170)).image { ctx in
            UIColor.white.setFill()
            ctx.fill(CGRect(x: 0, y: 0, width: 560, height: 170))
            RptPdf.drawChart(ctx.cgContext, chart, CGRect(x: 0, y: 0, width: 560, height: 165))
        }
        Image(uiImage: image).resizable().scaledToFit()
    }
}
