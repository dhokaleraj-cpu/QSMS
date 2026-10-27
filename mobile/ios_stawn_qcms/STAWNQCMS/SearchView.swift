import SwiftUI

/// Global Search (app_pages/global_search.py keyword search): every register, results grouped by module, tap to open the record.
struct SearchView: View {
    let initial: String
    @EnvironmentObject var nav: TabNav
    @State private var query = ""
    @State private var results: [SearchResult] = []
    @State private var modules: [QModule] = []
    @State private var running = false
    @State private var searched = ""
    @State private var error: String?
    /// R37: Print PDF of a hit (touch and hold) - PdfViewer: preview, Save to Files, Print, Email, Share.
    @State private var pdf: PdfItem?
    @State private var printing = false
    @State private var toast: String?
    /// R37: "+" -> New query opens the search with the keyboard up.
    @FocusState private var focused: Bool

    var body: some View {
        List {
            Section {
                HStack {
                    TextField("Part No, FSI Part No, Heat, RMTC, Batch, supplier, customer, PO, report…", text: $query)
                        .textInputAutocapitalization(.never).autocorrectionDisabled().onSubmit { run() }
                        .focused($focused)
                    Button { run() } label: { Image(systemName: "magnifyingglass") }.buttonStyle(.borderedProminent).tint(Theme.teal)
                }
            }
            if running { Section { HStack { ProgressView(); Text("Searching every register…").foregroundColor(Theme.muted) } } }
            if let e = error { Section { Text(e).foregroundColor(Theme.red) } }
            if !running && !searched.isEmpty && results.isEmpty && modules.isEmpty && error == nil { Section { Text("No records found for “\(searched)”.").foregroundColor(Theme.muted) } }
            if !modules.isEmpty {
                Section("Modules & screens (\(modules.count))") {
                    ForEach(modules) { m in
                        NavigationLink(value: Route.module(m.key)) { ModuleRow(title: m.title, detail: m.description, icon: "square.grid.2x2") }
                    }
                }
            }
            ForEach(groups, id: \.self) { g in
                Section("\(g) (\(results.filter { $0.module == g }.count))") {
                    ForEach(results.filter { $0.module == g }) { r in
                        Button { open(r) } label: {
                            VStack(alignment: .leading, spacing: 3) {
                                HStack {
                                    Text(r.reference).font(.subheadline.weight(.semibold)).foregroundColor(Theme.text)
                                    Spacer()
                                    if !r.status.isEmpty { StatusChip(text: r.status) }
                                }
                                Text(r.recordType).font(.caption).foregroundColor(Theme.tealDark)
                                if !r.detail.isEmpty { Text(r.detail).font(.caption).foregroundColor(Theme.muted).lineLimit(2) }
                                if !r.snippet.isEmpty { Text(r.snippet).font(.caption2).foregroundColor(Theme.muted).italic().lineLimit(2) }
                            }
                        }
                        .contextMenu {
                            Button { open(r) } label: { Label("Open record", systemImage: "doc.text") }
                            Button { printPdf(r) } label: { Label("Print PDF · Preview / Save / Share", systemImage: "printer") }
                        }
                        .swipeActions(edge: .trailing) {
                            Button { printPdf(r) } label: { Label("PDF", systemImage: "printer") }.tint(Theme.teal)
                        }
                    }
                }
            }
            if !results.isEmpty {
                Section {
                    Button { resultsPdf() } label: {
                        Label("Results PDF · Preview · Download · Share", systemImage: "doc.richtext").frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent).tint(Theme.teal).disabled(printing)
                    Text("Tap a result to open the record (Print layout PDF on the record) · swipe left or touch and hold for its PDF")
                        .font(.caption).foregroundColor(Theme.muted)
                }
            }
        }
        .navigationTitle("Global Search")
        .navigationBarTitleDisplayMode(.inline)
        .qcmsNavBar()
        .onAppear {
            if query.isEmpty && !initial.isEmpty { query = initial; run() }
            else if initial.isEmpty && results.isEmpty {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { focused = true }
            }
        }
        .overlay(alignment: .bottom) {
            if printing {
                HStack(spacing: 8) { ProgressView(); Text("Preparing the PDF…").font(.footnote) }
                    .padding(10).background(Color.white).clipShape(Capsule()).shadow(radius: 3).padding(.bottom, 16)
            }
        }
        .sheet(item: $pdf) { PdfViewer(item: $0) }
        .alert(toast ?? "", isPresented: Binding(get: { toast != nil }, set: { if !$0 { toast = nil } })) { Button("OK") { toast = nil } }
    }

    private var groups: [String] {
        var out: [String] = []
        for r in results where !out.contains(r.module) { out.append(r.module) }
        return out
    }

    private func run() {
        let q = query.trimmingCharacters(in: .whitespaces)
        guard q.count >= 2, !running else { return }
        running = true
        error = nil
        modules = GlobalSearch.modules(q)
        Task { @MainActor in
            async let server = GlobalSearch.server(q)
            var local: [SearchResult] = []
            var failure: String?
            do { local = try await GlobalSearch.everywhere(q) } catch { failure = error.localizedDescription }
            let remote = await server
            results = GlobalSearch.merge(local, remote)
            self.error = results.isEmpty ? failure : nil
            searched = q
            running = false
        }
    }

    /// R37: print-layout PDF of a hit (dedicated layout, else the Universal Record PDF for any table).
    private func printPdf(_ r: SearchResult) {
        guard !printing else { return }
        printing = true
        Task { @MainActor in
            do { pdf = try await RecordPdf.make(table: r.table, id: r.id) } catch { toast = "Could not create the PDF: \(error.localizedDescription)" }
            printing = false
        }
    }

    /// R37: the search results as a print-layout list PDF (controlled register layout).
    private func resultsPdf() {
        guard !printing else { return }
        printing = true
        let lines = results.map { [$0.module, $0.recordType, $0.reference, $0.detail, $0.status] }
        let title = "Global Search " + searched
        Task { @MainActor in
            let doc = await RptReports.register(title, columns: ["Module", "Record Type", "Reference", "Details", "Status / Result"], rows: lines)
            pdf = PdfItem(title: doc.title, fileName: doc.fileBase, data: RptPdf.render(doc))
            printing = false
        }
    }

    /// In-app record when a module shows the table, else the website page of the hit.
    private func open(_ r: SearchResult) {
        if !r.id.isEmpty, let m = Catalog.shared.forTable(r.table) { nav.push(.record(m.key, r.id)); return }
        if !r.webRoute.isEmpty { nav.push(.web(r.reference, r.webRoute)) }
    }
}

struct SearchResult: Identifiable {
    let id: String
    let module: String
    let recordType: String
    let reference: String
    let detail: String
    let status: String
    let table: String
    var webRoute = ""
    var snippet = ""
}

enum GlobalSearch {
    static let referenceKeys = ["part_number", "fsi_part_number", "party_code", "grade_code", "process_code", "employee_code", "plan_number", "rmtc_number", "inward_number",
                                "batch_code", "osp_job_number", "receipt_number", "report_number", "complaint_number", "master_reference_no", "customer_order_no", "po_number",
                                "supplier_order_no", "dispatch_number", "reference_no", "order_number", "project_code", "asset_code", "certificate_number", "tc_number", "heat_number"]
    static let statusKeys = ["status", "disposition", "overall_result", "inspection_status", "receipt_status", "result", "approval_status"]
    static let linkKeys = ["part_id", "customer_id", "supplier_id", "party_id", "vendor_id", "forging_supplier_id", "rm_supplier_id", "steel_mill_id"]
    static let detailKeys = ["part_name", "party_name", "subject", "heat_number", "heat_code", "vendor_batch_number", "batch_code", "sample_reference", "certificate_reference",
                             "grn_number", "invoice_number", "invoice_no", "asn_no", "drawing_number", "layout_name", "report_title", "remarks"]

    static func ilike(_ columns: [String], _ term: String) -> String {
        let clean = term.replacingOccurrences(of: ",", with: " ").replacingOccurrences(of: "(", with: " ").replacingOccurrences(of: ")", with: " ").trimmingCharacters(in: .whitespaces)
        return "&or=" + Api.enc("(" + columns.map { "\($0).ilike.*\(clean)*" }.joined(separator: ",") + ")")
    }

    static func everywhere(_ query: String, perSource: Int = 40) async throws -> [SearchResult] {
        let api = Api.shared
        let partRows = await api.list("parts?select=*" + ilike(["part_number", "fsi_part_number", "part_name", "drawing_number", "drawing_revision", "remarks"], query) + "&limit=50")
        let partyRows = await api.list("parties?select=*" + ilike(["party_code", "party_name", "country", "state", "city", "contact_person", "email", "remarks"], query) + "&limit=50")
        let partIds = Array(partRows.map { J.str($0["id"]) }.filter { !$0.isEmpty }.prefix(50))
        let partyIds = Array(partyRows.map { J.str($0["id"]) }.filter { !$0.isEmpty }.prefix(50))
        var partMap: [String: String] = [:], partyMap: [String: String] = [:]
        for r in await api.list("parts?select=id,part_number,fsi_part_number,part_name&limit=5000") {
            partMap[J.str(r["id"])] = [J.str(r["part_number"]), J.str(r["fsi_part_number"]), J.str(r["part_name"])].filter { !$0.isEmpty }.joined(separator: " · ")
        }
        for r in await api.list("parties?select=id,party_code,party_name&limit=5000") {
            partyMap[J.str(r["id"])] = [J.str(r["party_code"]), J.str(r["party_name"])].filter { !$0.isEmpty }.joined(separator: " · ")
        }
        let fold = query.lowercased()
        var found: [SearchResult] = []
        var seen = Set<String>()
        for src in Catalog.shared.searchSources {
            var byId: [String: Row] = [:]
            var order: [String] = []
            func merge(_ rows: [Row]) { for r in rows { let id = J.str(r["id"]); if id.isEmpty { continue }; if byId[id] == nil { order.append(id) }; byId[id] = r } }
            do {
                merge(try await api.rows("\(src.table)?select=*" + ilike(src.columns, query) + "&limit=\(perSource)"))
            } catch let e as ApiError where e.status == 0 || e.status == 401 {
                throw e
            } catch { continue }
            let inPart = "(" + partIds.joined(separator: ",") + ")", inParty = "(" + partyIds.joined(separator: ",") + ")"
            for f in src.partFields where !partIds.isEmpty { merge(await api.list("\(src.table)?select=*&\(f)=in.\(Api.enc(inPart))&limit=\(perSource)")) }
            for f in src.partyFields where !partyIds.isEmpty { merge(await api.list("\(src.table)?select=*&\(f)=in.\(Api.enc(inParty))&limit=\(perSource)")) }
            for id in order {
                guard let row = byId[id] else { continue }
                let token = "\(src.table):\(id)"
                if seen.contains(token) { continue }
                seen.insert(token)
                let relation = (src.partFields.map { partMap[J.str(row[$0])] ?? "" } + src.partyFields.map { partyMap[J.str(row[$0])] ?? "" }).joined(separator: " ")
                let text = row.values.map { J.str($0) }.joined(separator: " ").lowercased()
                if !text.contains(fold) && !relation.lowercased().contains(fold) { continue }
                found.append(SearchResult(id: id, module: src.module, recordType: src.recordType, reference: reference(row), detail: detail(row, partMap, partyMap),
                                          status: status(row), table: src.table))
            }
        }
        return found.sorted { ($0.module, $0.recordType, $0.reference.lowercased()) < ($1.module, $1.recordType, $1.reference.lowercased()) }
    }

    /// Live database-wide search (qcms_global_search): every business table and field the user can see. Empty on any error.
    static func server(_ query: String, limit: Int = 200) async -> [SearchResult] {
        guard let raw = try? await Api.shared.rpc("qcms_global_search", ["p_query": query, "p_limit": limit]) else { return [] }
        var out: [SearchResult] = []
        for r in J.rows(raw) {
            let table = J.str(r["source_table"])
            let source = Catalog.shared.searchSources.first { $0.table == table }
            let module = source?.module ?? Catalog.shared.forTable(table)?.title ?? "Other records"
            var recordType = J.str(r["record_type"])
            if recordType.isEmpty { recordType = source?.recordType ?? Fmt.pretty(table) }
            var title = J.str(r["title"])
            if title.isEmpty { title = J.str(r["record_id"]) }
            let field = J.str(r["matched_field"])
            let snippet = J.str(r["snippet"])
            out.append(SearchResult(id: J.str(r["record_id"]), module: module, recordType: recordType, reference: title.isEmpty ? "Record" : title,
                                    detail: J.str(r["subtitle"]), status: "", table: table, webRoute: J.str(r["web_route"]),
                                    snippet: snippet.isEmpty ? "" : (field.isEmpty ? snippet : "\(Fmt.pretty(field)): \(snippet)")))
        }
        return out
    }

    /// Records of both searches, one row per table + id (the app's own row first, server snippet / web route added).
    static func merge(_ local: [SearchResult], _ remote: [SearchResult]) -> [SearchResult] {
        var out = local
        var index: [String: Int] = [:]
        for (i, r) in out.enumerated() { index["\(r.table):\(r.id)"] = i }
        for r in remote {
            let token = "\(r.table):\(r.id)"
            if let i = index[token] {
                if out[i].snippet.isEmpty { out[i].snippet = r.snippet }
                if out[i].webRoute.isEmpty { out[i].webRoute = r.webRoute }
                continue
            }
            index[token] = out.count
            out.append(r)
        }
        return out.sorted { ($0.module, $0.recordType, $0.reference.lowercased()) < ($1.module, $1.recordType, $1.reference.lowercased()) }
    }

    /// Modules / screens whose name or description matches ("bend test" -> Bend Test register, entry, reports).
    static func modules(_ query: String) -> [QModule] {
        let words = query.lowercased().split(separator: " ").map { String($0) }.filter { !$0.isEmpty }
        if words.isEmpty { return [] }
        return Catalog.shared.modules.filter { m in
            let text = (m.title + " " + m.description + " " + m.key.replacingOccurrences(of: "_", with: " ")).lowercased()
            return words.allSatisfy { text.contains($0) }
        }
    }

    static func reference(_ row: Row) -> String {
        for k in referenceKeys { let v = J.str(row[k]); if !v.isEmpty { return v } }
        let id = J.str(row["id"])
        return id.isEmpty ? "Record" : id
    }

    static func status(_ row: Row) -> String {
        for k in statusKeys { let v = J.str(row[k]); if !v.isEmpty { return v } }
        return ""
    }

    static func detail(_ row: Row, _ partMap: [String: String], _ partyMap: [String: String]) -> String {
        var values: [String] = []
        for k in linkKeys {
            let raw = J.str(row[k])
            let label = k == "part_id" ? partMap[raw] : partyMap[raw]
            if let l = label, !l.isEmpty, !values.contains(l) { values.append(l) }
        }
        for k in detailKeys {
            let v = J.str(row[k])
            if !v.isEmpty && !values.contains(v) { values.append(v) }
            if values.count >= 4 { break }
        }
        return values.prefix(4).joined(separator: " · ")
    }
}
