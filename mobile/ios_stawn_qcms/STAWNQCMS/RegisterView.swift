import SwiftUI

/// Spreadsheet grid: slide left / right and up / down to see every row and column; header stays on top.
struct SheetGrid: View {
    let columns: [String]
    let rows: [[String]]
    var statusColumns: Set<Int> = []
    var maxHeight: CGFloat? = nil
    var onTap: ((Int) -> Void)? = nil

    private var widths: [CGFloat] {
        columns.indices.map { c in
            var longest = columns[c].count
            for r in rows.prefix(200) where c < r.count { longest = max(longest, min(r[c].count, 48)) }
            return min(280, max(70, CGFloat(longest) * 7.2 + 20))
        }
    }

    var body: some View {
        let w = widths
        ScrollView([.horizontal, .vertical]) {
            LazyVStack(alignment: .leading, spacing: 0, pinnedViews: [.sectionHeaders]) {
                Section(header: header(w)) {
                    ForEach(rows.indices, id: \.self) { i in
                        rowView(i, w)
                            .background(i % 2 == 0 ? Color.white : Theme.bg)
                            .contentShape(Rectangle())
                            .onTapGesture { onTap?(i) }
                    }
                }
            }
        }
        .frame(maxHeight: maxHeight)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lineStrong, lineWidth: 1))
    }

    private func header(_ w: [CGFloat]) -> some View {
        HStack(spacing: 0) {
            ForEach(columns.indices, id: \.self) { c in
                Text(columns[c]).font(.caption.weight(.bold)).foregroundColor(.white).lineLimit(2)
                    .frame(width: w[c], alignment: .leading).padding(.horizontal, 6).padding(.vertical, 8)
            }
        }
        .background(Theme.tealDark)
    }

    private func rowView(_ i: Int, _ w: [CGFloat]) -> some View {
        HStack(spacing: 0) {
            ForEach(columns.indices, id: \.self) { c in
                let v = c < rows[i].count ? rows[i][c] : ""
                Group {
                    if statusColumns.contains(c) && !v.isEmpty && v != "-" { StatusChip(text: v) } else {
                        Text(v).font(.caption).foregroundColor(Theme.text).lineLimit(3)
                    }
                }
                .frame(width: w[c], alignment: .leading).padding(.horizontal, 6).padding(.vertical, 7)
            }
        }
        .overlay(Rectangle().fill(Theme.line).frame(height: 0.5), alignment: .bottom)
    }
}

/// A module register (grid) like the Android RegisterScreen: search, status chips, export, tap a row to open the record.
struct RegisterView: View {
    let module: QModule
    @EnvironmentObject var nav: TabNav
    @State private var rows: [Row] = []
    @State private var fk: [String: [String: String]] = [:]
    @State private var loading = true
    @State private var error: String?
    @State private var query = ""
    @State private var status = ""
    @State private var pdf: PdfItem?
    @State private var busy = false
    @State private var shareURL: URL?

    private var shown: [Row] {
        let q = query.lowercased()
        return rows.filter { r in
            if !status.isEmpty && status.uppercased() != J.str(r[module.statusField]).uppercased() { return false }
            if q.isEmpty { return true }
            return module.cols.map { cell(r, $0) }.joined(separator: " ").lowercased().contains(q)
        }
    }

    private func cell(_ r: Row, _ col: [String]) -> String {
        if col.count > 2 && col[2] == "money" { return Fmt.money(J.double(r[col[0]]), J.str(r["currency"])) }
        return Labels.cell(col[0], r[col[0]], fk[col[0]])
    }

    private var statusCols: Set<Int> {
        Set(module.cols.enumerated().filter { $0.element[0] == module.statusField || $0.element[0].contains("status") || $0.element[0].contains("disposition") || $0.element[0] == "result" }.map { $0.offset })
    }

    var body: some View {
        let data = shown
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "magnifyingglass").foregroundColor(Theme.muted)
                TextField("Search \(module.title.lowercased())…", text: $query).textInputAutocapitalization(.never).autocorrectionDisabled()
            }
            .padding(10).background(Color.white).clipShape(RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lineStrong))
            if !module.statusFilters.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        chip("", "All")
                        ForEach(module.statusFilters, id: \.self) { chip($0, Fmt.pretty($0)) }
                    }
                }
            }
            if let e = error { ErrorBox(message: e) { Task { await load() } } }
            else if loading { ProgressView("Loading \(module.title)…").frame(maxWidth: .infinity).padding(30) }
            else {
                Text("\(data.count)\(data.count == rows.count ? "" : " of \(rows.count)") record(s) · slide ↔ ↕ · tap a row to open")
                    .font(.caption).foregroundColor(Theme.muted)
                if data.isEmpty { Text("No records.").foregroundColor(Theme.muted).frame(maxWidth: .infinity).padding(30) }
                else {
                    SheetGrid(columns: module.cols.map { $0[1] }, rows: data.map { r in module.cols.map { cell(r, $0) } }, statusColumns: statusCols) { i in
                        guard !module.idField.isEmpty, i < data.count else { return }
                        let id = J.str(data[i][module.idField])
                        if !id.isEmpty { nav.push(.record(module.key, id)) }
                    }
                }
            }
        }
        .padding(.horizontal, 10).padding(.top, 6)
        .background(Theme.bg)
        .navigationTitle(module.title)
        .navigationBarTitleDisplayMode(.inline)
        .qcmsNavBar()
        .toolbar {
            ToolbarItemGroup(placement: .navigationBarTrailing) {
                if module.editable && (module.nativeForm || module.hasEditor) {
                    Button { newRecord() } label: { Image(systemName: "plus") }
                }
                Menu {
                    Button { registerPdf() } label: { Label("Register PDF · Print · Email", systemImage: "doc.richtext") }
                    Button { shareCsv() } label: { Label("Share as CSV (Excel)", systemImage: "tablecells") }
                    if let path = WebRoutes.path(for: module.key) {
                        Button { nav.push(.web(module.title, path)) } label: { Label("Open on website", systemImage: "globe") }
                    }
                    Button { nav.push(.search("")) } label: { Label("Global search", systemImage: "magnifyingglass") }
                } label: { Image(systemName: busy ? "hourglass" : "square.and.arrow.down") }
            }
        }
        .sheet(item: $pdf) { PdfViewer(item: $0) }
        .sheet(item: Binding(get: { shareURL.map { ShareFile(url: $0) } }, set: { shareURL = $0?.url })) { ShareSheet(items: [$0.url]) }
        .task { if rows.isEmpty { await load() } }
        .refreshable { await load() }
    }

    private func chip(_ value: String, _ label: String) -> some View {
        let on = status == value
        return Button { status = value } label: {
            Text(label).font(.caption.weight(on ? .bold : .regular)).foregroundColor(on ? .white : Theme.text)
                .padding(.horizontal, 12).padding(.vertical, 7)
                .background(on ? Theme.teal : Color.white).clipShape(Capsule())
                .overlay(Capsule().stroke(on ? Color.clear : Theme.lineStrong))
        }
    }

    private func path(_ all: Bool) -> String {
        let order = module.order.isEmpty ? "" : "&order=\(module.order)"
        return "\(module.table)?select=\(all ? "*" : module.selectList())\(module.filter)\(order)&limit=3000"
    }

    private func load() async {
        loading = rows.isEmpty
        error = nil
        do {
            var data: [Row]
            do { data = try await Api.shared.rows(path(false)) }
            catch let e as ApiError where e.status == 400 { data = try await Api.shared.rows(path(true)) }
            fk = await Labels.resolve(module.table, rows: data, columns: module.cols.map { $0[0] })
            rows = data
        } catch {
            self.error = error.localizedDescription
        }
        loading = false
    }

    private func newRecord() {
        if module.nativeForm { nav.push(.form(module.key, "")) }
        else if let p = WebRoutes.path(for: module.key) { nav.push(.web("New · \(module.title)", p)) }
    }

    private func registerPdf() {
        let data = shown
        let heads = module.cols.map { $0[1] }
        let lines = data.map { r in module.cols.map { cell(r, $0) } }
        busy = true
        Task {
            let doc = await RptReports.register(module.title, columns: heads, rows: lines)
            pdf = PdfItem(title: doc.title, fileName: doc.fileBase, data: RptPdf.render(doc))
            busy = false
        }
    }

    private func shareCsv() {
        func q(_ s: String) -> String { s.contains(",") || s.contains("\"") || s.contains("\n") ? "\"" + s.replacingOccurrences(of: "\"", with: "\"\"") + "\"" : s }
        var csv = module.cols.map { q($0[1]) }.joined(separator: ",") + "\n"
        for r in shown { csv += module.cols.map { q(cell(r, $0)) }.joined(separator: ",") + "\n" }
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(Files.safeName("QCMS_\(module.title)_Register.csv"))
        try? Data(csv.utf8).write(to: url)
        shareURL = url
    }
}

struct ShareFile: Identifiable {
    let url: URL
    var id: String { url.absoluteString }
}

enum Files {
    static func safeName(_ name: String) -> String {
        let bad = CharacterSet(charactersIn: "/\\?%*|\"<>: ")
        return name.components(separatedBy: bad).filter { !$0.isEmpty }.joined(separator: "_")
    }

    static func stamp() -> String {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyyMMdd_HHmm"
        return f.string(from: Date())
    }
}
