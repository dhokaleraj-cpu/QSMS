import SwiftUI

/// Global Search (app_pages/global_search.py keyword search): every register, results grouped by module, tap to open the record.
struct SearchView: View {
    let initial: String
    @EnvironmentObject var nav: TabNav
    @State private var query = ""
    @State private var results: [SearchResult] = []
    @State private var running = false
    @State private var searched = ""
    @State private var error: String?

    var body: some View {
        List {
            Section {
                HStack {
                    TextField("Part No, FSI Part No, Heat, RMTC, Batch, supplier, customer, PO, report…", text: $query)
                        .textInputAutocapitalization(.never).autocorrectionDisabled().onSubmit { run() }
                    Button { run() } label: { Image(systemName: "magnifyingglass") }.buttonStyle(.borderedProminent).tint(Theme.teal)
                }
            }
            if running { Section { HStack { ProgressView(); Text("Searching every register…").foregroundColor(Theme.muted) } } }
            if let e = error { Section { Text(e).foregroundColor(Theme.red) } }
            if !running && !searched.isEmpty && results.isEmpty && error == nil { Section { Text("No records found for “\(searched)”.").foregroundColor(Theme.muted) } }
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
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle("Global Search")
        .navigationBarTitleDisplayMode(.inline)
        .qcmsNavBar()
        .onAppear {
            if query.isEmpty && !initial.isEmpty { query = initial; run() }
        }
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
        Task {
            do { results = try await GlobalSearch.everywhere(q) } catch { self.error = error.localizedDescription }
            searched = q
            running = false
        }
    }

    private func open(_ r: SearchResult) {
        if let m = Catalog.shared.forTable(r.table) { nav.push(.record(m.key, r.id)) }
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
