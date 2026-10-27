import SwiftUI

// R37 (iOS v1.2.0 build 3): KPI drill-down lists, module infographic cards, "+" quick actions and Print PDF of any record.
// Every RPC is optional: when qcms_kpi_records / qcms_module_cards are missing or fail, the app opens the module instead.

extension QModule {
    /// Read-only module for any table (Universal Record PDF of tables the app has no module for).
    static func adhoc(table: String) -> QModule? {
        let empty: [Any] = []
        let dict: [String: Any] = [
            "key": "adhoc_" + table, "title": Fmt.title(table.replacingOccurrences(of: "_", with: " ")), "tab": 4, "section": "Records",
            "table": table, "filter": "", "order": "", "description": "", "titleField": "", "statusField": "", "idField": "id",
            "deletable": false, "editable": false, "hasEditor": false, "custom": false, "attachEntity": "", "attachFolder": "",
            "attachSlots": empty, "attachMulti": false, "search": empty, "statusFilters": empty, "numberField": "", "numberRpc": "",
            "numberArgs": "", "hooks": false, "cols": empty, "children": empty, "actions": empty, "form": empty,
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: dict) else { return nil }
        return try? JSONDecoder().decode(QModule.self, from: data)
    }
}

/// Print-layout PDF of one record (dedicated layout, else Universal Record PDF) for the PdfViewer sheet
/// (preview, Save to Files, Print, Email, Share).
enum RecordPdf {
    static func make(table: String, id: String) async throws -> PdfItem {
        if table.isEmpty || id.isEmpty {
            throw ApiError(status: 400, message: "This row has no record to print.")
        }
        var module: QModule? = Catalog.shared.forTable(table)
        if let m = module, m.idField != "id" { module = nil }
        if module == nil { module = QModule.adhoc(table: table) }
        guard let m = module else { throw ApiError(status: 400, message: "This record cannot be printed.") }
        let doc = try await RptReports.forRecord(m, id)
        return PdfItem(title: doc.title, fileName: doc.fileBase, data: RptPdf.render(doc))
    }
}

// MARK: - KPI records behind a number (qcms_kpi_records)

struct KpiRecord: Identifiable {
    let id: Int
    let table: String
    let recordId: String
    let reference: String
    let part: String
    let party: String
    let status: String
    let date: String
    let detail: String

    init(_ i: Int, _ r: Row) {
        id = i
        table = J.str(r["source_table"])
        recordId = J.str(r["record_id"])
        reference = J.str(r["reference"])
        part = J.str(r["part"])
        party = J.str(r["party"])
        status = J.str(r["status"])
        date = J.str(r["record_date"])
        detail = J.str(r["detail"])
    }

    var line: String {
        var parts: [String] = []
        if !part.isEmpty { parts.append(part) }
        if !party.isEmpty { parts.append(party) }
        if !date.isEmpty { parts.append(Fmt.date(date)) }
        return parts.joined(separator: " · ")
    }

    var haystack: String { [reference, part, party, status, detail].joined(separator: " ").lowercased() }

    /// Any table row (card "drill" table / fallback query) in the drill-down shape.
    init(_ i: Int, table: String, generic r: Row) {
        id = i
        self.table = table
        recordId = J.str(r["id"])
        reference = KpiRecord.first(r, ["report_number", "report_no", "rmtc_number", "certificate_reference", "inward_number", "grn_number",
                                        "complaint_number", "po_number", "order_number", "order_no", "asset_code", "asset_number", "plan_number",
                                        "reference", "code", "name", "title"])
        part = KpiRecord.first(r, ["part_number", "part_no", "fsi_part_number"])
        party = KpiRecord.first(r, ["supplier_name", "customer_name", "party_name", "vendor_name"])
        status = KpiRecord.first(r, ["status", "inspection_status"])
        date = KpiRecord.first(r, ["test_date", "inspection_date", "inward_date", "complaint_date", "certificate_date", "next_due_date", "order_date", "created_at"])
        let heat = J.str(r["heat_number"])
        detail = KpiRecord.first(r, ["subject", "asset_name", "layout_name", "description"]) + (heat.isEmpty ? "" : " · Heat " + heat)
    }

    static func first(_ r: Row, _ keys: [String]) -> String {
        for k in keys {
            let v = J.str(r[k])
            if v.isEmpty { continue }
            if v.count > 10 && v.range(of: "^\\d{4}-\\d{2}-\\d{2}T", options: .regularExpression) != nil { return String(v.prefix(10)) }
            return v
        }
        return ""
    }

    /// PostgREST rows of a table with an encoded filter ("&col=op.value…").
    static func loadDrill(_ table: String, _ query: String) async throws -> [KpiRecord] {
        let raw = try await Api.shared.rows(table + "?select=*" + query + "&limit=500")
        var out: [KpiRecord] = []
        for (i, r) in raw.enumerated() { out.append(KpiRecord(i, table: table, generic: r)) }
        return out
    }
}

struct KpiRecordsView: View {
    let key: String
    let department: String
    let title: String
    let route: String
    /// Card "drill" object: table + encoded PostgREST filter (instead of qcms_kpi_records).
    var drillTable: String = ""
    var drillQuery: String = ""
    @EnvironmentObject var nav: TabNav
    @State private var rows: [KpiRecord] = []
    @State private var loaded = false
    @State private var error: String?
    @State private var filter = ""
    @State private var pdf: PdfItem?
    @State private var busy = false
    @State private var toast: String?

    private var shown: [KpiRecord] {
        let f = filter.trimmingCharacters(in: .whitespaces).lowercased()
        if f.isEmpty { return rows }
        return rows.filter { $0.haystack.contains(f) }
    }

    var body: some View {
        List {
            Section {
                HStack {
                    Text(title).font(.headline).foregroundColor(Theme.text)
                    Spacer()
                    if loaded { StatusChip(text: "\(rows.count)") }
                    if busy { ProgressView() }
                }
                Text("Tap a record to open it · touch and hold for Print PDF (Preview / Save / Share)")
                    .font(.caption).foregroundColor(Theme.muted)
                if rows.count > 8 {
                    TextField("Filter: reference, part, party, status…", text: $filter)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                }
            }
            if let e = error {
                Section { ErrorBox(message: e) { Task { await load() } } }
            } else if !loaded {
                Section { HStack { ProgressView(); Text("Loading records…").foregroundColor(Theme.muted) } }
            } else if shown.isEmpty {
                Section { Text(rows.isEmpty ? "No records behind this number right now." : "No record matches the filter.").foregroundColor(Theme.muted) }
            } else {
                Section("Records (\(shown.count))") {
                    ForEach(shown) { r in
                        Button { open(r) } label: { rowView(r) }
                            .contextMenu {
                                Button { open(r) } label: { Label("Open record", systemImage: "doc.text") }
                                Button { printPdf(r) } label: { Label("Print PDF · Preview / Save / Share", systemImage: "printer") }
                            }
                            .swipeActions(edge: .trailing) {
                                Button { printPdf(r) } label: { Label("Print PDF", systemImage: "printer") }.tint(Theme.teal)
                            }
                    }
                }
            }
            if !route.isEmpty {
                Section {
                    Button { openModule() } label: { Label("Open the module", systemImage: "square.grid.2x2") }
                }
            }
        }
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
        .qcmsNavBar()
        .task { if !loaded { await load() } }
        .refreshable { await load() }
        .sheet(item: $pdf) { PdfViewer(item: $0) }
        .alert(toast ?? "", isPresented: Binding(get: { toast != nil }, set: { if !$0 { toast = nil } })) { Button("OK") { toast = nil } }
    }

    private func rowView(_ r: KpiRecord) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack {
                Text(r.reference.isEmpty ? Fmt.pretty(r.table) : r.reference).font(.subheadline.weight(.semibold)).foregroundColor(Theme.text)
                Spacer()
                if !r.status.isEmpty { StatusChip(text: r.status) }
            }
            if !r.line.isEmpty { Text(r.line).font(.caption).foregroundColor(Theme.tealDark) }
            if !r.detail.isEmpty { Text(r.detail).font(.caption).foregroundColor(Theme.muted).lineLimit(3) }
        }
        .padding(.vertical, 2)
    }

    @MainActor private func load() async {
        error = nil
        var args: [String: Any] = ["p_card_key": key, "p_limit": 500]
        if !department.isEmpty { args["p_department"] = department }
        do {
            var out: [KpiRecord] = []
            if !drillTable.isEmpty {
                out = try await KpiRecord.loadDrill(drillTable, drillQuery)
            } else {
                do {
                    let raw = try await Api.shared.rpc("qcms_kpi_records", args)
                    for (i, r) in J.rows(raw).enumerated() { out.append(KpiRecord(i, r)) }
                } catch let e as ApiError where e.status == 401 {
                    throw e
                } catch {
                    // older database: the same records straight from the module table (status filter)
                    guard let fb = QuickActions.fallbackDrill(key) else { throw error }
                    out = try await KpiRecord.loadDrill(fb.table, QuickActions.encodeQuery(fb.query))
                }
            }
            rows = out
            loaded = true
        } catch {
            if !route.isEmpty && rows.isEmpty {
                // older database / RPC failed: open the module like before
                openModule(replace: true)
                return
            }
            self.error = error.localizedDescription
        }
    }

    private func open(_ r: KpiRecord) {
        if let target = AppLinks.route(title: r.reference, table: r.table, id: r.recordId, moduleKey: "", webRoute: route) {
            nav.push(target)
        } else {
            toast = "Nothing to open for this record."
        }
    }

    private func openModule(replace: Bool = false) {
        guard let target = AppLinks.route(title: title, table: "", id: "", moduleKey: "", webRoute: route) else { return }
        if replace { nav.pop() }
        nav.push(target)
    }

    private func printPdf(_ r: KpiRecord) {
        guard !busy else { return }
        busy = true
        Task { @MainActor in
            do { pdf = try await RecordPdf.make(table: r.table, id: r.recordId) } catch { toast = "Could not create the PDF: \(error.localizedDescription)" }
            busy = false
        }
    }
}

// MARK: - Module infographic cards (qcms_module_cards)

struct ModuleCardFigure: Identifiable {
    let id: Int
    let label: String
    let value: String
}

struct ModuleCard: Identifiable {
    var id: Int
    let key: String
    let title: String
    let value: String
    let unit: String
    let tone: String
    let route: String
    let figures: [ModuleCardFigure]
    let drillTable: String
    let drillQuery: String

    init(_ i: Int, _ c: Row) {
        id = i
        key = J.str(c["key"])
        let drill = J.obj(c["drill"])
        drillTable = J.str(drill["table"])
        drillQuery = QuickActions.filterQuery(J.obj(drill["filter"]))
        var t = J.str(c["title"])
        if t.isEmpty { t = J.str(c["label"]) }
        title = t
        value = ModuleCard.fmt(c["value"])
        unit = J.str(c["unit"])
        tone = J.str(c["tone"]).lowercased()
        route = J.str(c["route"])
        var figs: [ModuleCardFigure] = []
        for k in ["sub_figures", "subs", "sub", "figures", "subfigures", "breakdown", "details"] {
            if !figs.isEmpty { break }
            let arr = J.rows(c[k])
            if !arr.isEmpty {
                for f in arr {
                    var label = J.str(f["label"])
                    if label.isEmpty { label = J.str(f["title"]) }
                    if label.isEmpty { label = J.str(f["name"]) }
                    let u = J.str(f["unit"])
                    figs.append(ModuleCardFigure(id: figs.count, label: label, value: ModuleCard.fmt(f["value"]) + (u.isEmpty ? "" : " " + u)))
                }
            } else if let obj = c[k] as? Row {
                for name in obj.keys.sorted() {
                    figs.append(ModuleCardFigure(id: figs.count, label: Fmt.pretty(name), value: ModuleCard.fmt(obj[name])))
                }
            }
        }
        figures = figs
    }

    static func fmt(_ v: Any?) -> String {
        if let n = v as? NSNumber, !J.isBool(v) { return Fmt.num(n.doubleValue, 2) }
        return J.str(v)
    }

    /// Cards of qcms_module_cards: plain array or {"cards": [...]}.
    static func parse(_ raw: Any?) -> [ModuleCard] {
        var list = J.rows(raw)
        if list.isEmpty {
            let o = J.obj(raw)
            for k in ["cards", "modules", "items"] where list.isEmpty { list = J.rows(o[k]) }
        }
        var out: [ModuleCard] = []
        for (i, c) in list.enumerated() { out.append(ModuleCard(i, c)) }
        return out
    }
}

struct ModuleCardsStrip: View {
    let cards: [ModuleCard]
    let department: String
    var onTap: (() -> Void)?
    @EnvironmentObject var nav: TabNav

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            SectionLabel(text: "Modules · tap a card for its records")
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(alignment: .top, spacing: 10) {
                    ForEach(cards) { c in
                        Button { open(c) } label: { cardView(c) }.buttonStyle(.plain)
                    }
                }
                .padding(.vertical, 2)
            }
        }
    }

    private func cardView(_ c: ModuleCard) -> some View {
        let color = KpiPage.toneColor(c.tone)
        return VStack(alignment: .leading, spacing: 4) {
            Rectangle().fill(color).frame(height: 4).clipShape(Capsule())
            Text(c.title.uppercased()).font(.caption2.weight(.bold)).foregroundColor(Theme.muted).lineLimit(1)
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text(c.value.isEmpty ? "-" : c.value).font(.title2.bold()).foregroundColor(color).lineLimit(1).minimumScaleFactor(0.6)
                if !c.unit.isEmpty { Text(c.unit).font(.caption.weight(.semibold)).foregroundColor(Theme.muted) }
            }
            ForEach(Array(c.figures.prefix(4))) { f in
                HStack {
                    Text(f.label).font(.caption).foregroundColor(Theme.muted).lineLimit(1)
                    Spacer()
                    Text(f.value).font(.caption.weight(.semibold)).foregroundColor(Theme.text)
                }
            }
            Text("View records ›").font(.caption.weight(.semibold)).foregroundColor(Theme.tealDark).padding(.top, 2)
        }
        .frame(width: 200, alignment: .leading)
        .padding(12)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
    }

    private func open(_ c: ModuleCard) {
        onTap?()
        QuickActions.openCard(nav: nav, key: c.key, department: department, title: c.title, route: c.route,
                              drillTable: c.drillTable, drillQuery: c.drillQuery)
    }
}

// MARK: - "+" quick actions

struct QuickTransaction: Identifiable {
    let label: String
    let moduleKey: String
    let route: String
    var permission: String = ""   // core.access module key (Create permission)
    var id: String { label }
}

enum QuickActions {
    /// Entry transactions: native New form when the app has one, else the website entry page.
    static let transactions: [QuickTransaction] = [
        QuickTransaction(label: "RMTC entry", moduleKey: "rmtc", route: "rmtc-entry", permission: "RMTC_ENTRY"),
        QuickTransaction(label: "Material inward", moduleKey: "inward", route: "inward-entry", permission: "MATERIAL_INWARD"),
        QuickTransaction(label: "Dimensional report", moduleKey: "dimensional_reports", route: "dimensional-entry", permission: "DIMENSIONAL_REPORT"),
        QuickTransaction(label: "MetLAB report", moduleKey: "metlab_reports", route: "metlab-entry", permission: "METLAB_REPORT"),
        QuickTransaction(label: "Bend test report", moduleKey: "bend_tests", route: "bend-test-entry", permission: "METLAB_REPORT"),
        QuickTransaction(label: "Inspection layout", moduleKey: "inspection_layouts", route: "inspection-layout-entry", permission: "INSPECTION_LAYOUTS"),
        QuickTransaction(label: "OSP material out", moduleKey: "osp_material_out", route: "osp-material-out", permission: "OSP_TRANSACTIONS"),
        QuickTransaction(label: "OSP material inward", moduleKey: "osp_receipts", route: "osp-inward", permission: "OSP_TRANSACTIONS"),
        QuickTransaction(label: "Customer complaint", moduleKey: "customer_complaints", route: "customer-complaint", permission: "COMPLAINT_MANAGEMENT"),
        QuickTransaction(label: "Supplier complaint", moduleKey: "supplier_complaints", route: "supplier-complaint", permission: "COMPLAINT_MANAGEMENT"),
        QuickTransaction(label: "Calibration / validation", moduleKey: "calibration_records", route: "calibration-validation", permission: "CALIBRATION_VALIDATION"),
        QuickTransaction(label: "Standard room inspection", moduleKey: "standard_room", route: "standard-room-inspection", permission: "CALIBRATION_VALIDATION"),
        QuickTransaction(label: "Purchase order", moduleKey: "purchase_orders", route: "supply-purchase-orders", permission: "SUPPLY_CHAIN"),
        QuickTransaction(label: "Customer order", moduleKey: "customer_orders", route: "supply-customer-orders", permission: "SUPPLY_CHAIN"),
        QuickTransaction(label: "RM receipt", moduleKey: "rm_receipts", route: "supply-rm-receipt", permission: "SUPPLY_CHAIN"),
        QuickTransaction(label: "RM dispatch", moduleKey: "rm_dispatches", route: "supply-rm-dispatch", permission: "SUPPLY_CHAIN"),
        QuickTransaction(label: "Forging order", moduleKey: "forging_orders", route: "supply-forging", permission: "SUPPLY_CHAIN"),
        QuickTransaction(label: "NPD order", moduleKey: "npd_orders", route: "npd-status", permission: "NPD_APQP"),
        QuickTransaction(label: "APQP project", moduleKey: "apqp_projects", route: "apqp", permission: "NPD_APQP"),
        QuickTransaction(label: "QC calculation", moduleKey: "qc_calculations", route: "qc-tools", permission: "QC_CALCULATION_TOOLS"),
    ]

    static func isNative(_ t: QuickTransaction) -> Bool {
        guard let m = Catalog.shared.module(t.moduleKey) else { return false }
        return m.nativeForm
    }

    static func open(_ t: QuickTransaction, nav: TabNav) {
        if isNative(t) { nav.push(.form(t.moduleKey, "")) } else { nav.push(.web(t.label, t.route)) }
    }

    static func newEmail(nav: TabNav) {
        if Catalog.shared.module("email_send") != nil { nav.push(.module("email_send")) } else { nav.push(.web("Send Email", "email-send")) }
    }

    /// KPI / module card: "drill" table + filter first, else the records list of the card key (label -> key for
    /// older databases), else its module / website page.
    static func openCard(nav: TabNav, key: String, department: String, title: String, route: String,
                         drillTable: String = "", drillQuery: String = "") {
        if !drillTable.isEmpty {
            nav.push(.kpiDrill(drillTable, drillQuery, title, route))
            return
        }
        let k = key.isEmpty ? keyForLabel(title) : key
        if !k.isEmpty {
            nav.push(.kpiRecords(k, department, title, route))
        } else if let r = AppLinks.route(title: title, table: "", id: "", moduleKey: "", webRoute: route) {
            nav.push(r)
        }
    }

    /// Card key of a KPI label (same list as the R37 migration) - for dashboards returned without keys.
    static let labelKeys: [String: String] = [
        "inward on quality hold": "inward_hold", "metlab pending": "metlab_pending", "bend test pending": "bend_pending",
        "dimensional pending": "dimensional_pending", "reports finalized this month": "reports_final_month",
        "rejection (180 days)": "rejection_180d", "rmtc pending": "rmtc_pending", "complaints open": "complaints_open",
        "calibration overdue": "calibration_overdue", "calibration due ≤ 30 days": "calibration_due_30",
        "open customer orders": "customer_orders_open", "open order quantity": "customer_order_qty_open",
        "po pending approval": "po_pending_approval", "open purchase orders": "po_open", "rm on order": "rm_on_order",
        "rm received this month": "rm_received_month", "forging orders open": "forging_orders_open",
        "dispatched this month": "dispatched_month", "pieces available in batches": "batch_pcs_available",
        "active production batches": "batches_active", "osp at vendor": "osp_at_vendor", "osp sample pending": "osp_sample_pending",
        "osp receipt quality pending": "osp_receipt_pending", "machined this month": "machined_month",
        "finished goods this month": "fg_month", "npd open": "npd_open", "npd in progress": "npd_in_progress", "npd late": "npd_late",
        "apqp / ppap active": "apqp_active", "apqp average completion": "apqp_completion", "npd steps open": "npd_steps_open",
        "npd steps overdue": "npd_steps_overdue", "first-pass yield (final reports)": "fpy_final_reports",
        "open po value": "po_open_value", "heats released this month": "heats_released_month",
    ]

    static func keyForLabel(_ label: String) -> String {
        labelKeys[label.trimmingCharacters(in: .whitespaces).lowercased()] ?? ""
    }

    private static func day(_ offset: Int) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        let d = Calendar.current.date(byAdding: .day, value: offset, to: Date()) ?? Date()
        return f.string(from: d)
    }

    /// Client-side drill when qcms_kpi_records is missing / failing: table + raw PostgREST filter (Quality cards).
    static func fallbackDrill(_ key: String) -> (table: String, query: String)? {
        let today = day(0), in30 = day(30)
        switch key {
        case "inward_hold", "mod_inward": return ("inward_lots", "status=eq.HOLD_PENDING_INSPECTION")
        case "metlab_pending", "mod_metlab":
            return ("lab_tests", "status=neq.FINAL&or=(results->>inspection_method.is.null,results->>inspection_method.neq.BEND_TEST)")
        case "bend_pending", "mod_bend": return ("lab_tests", "status=neq.FINAL&results->>inspection_method=eq.BEND_TEST")
        case "dimensional_pending", "mod_dimensional": return ("inspection_reports", "status=neq.FINAL")
        case "rmtc_pending", "mod_rmtc": return ("rmtc_approvals", "status=not.in.(APPROVED,REJECTED,CANCELLED)")
        case "complaints_open": return ("quality_complaints", "status=not.in.(CLOSED,CANCELLED)")
        case "mod_customer_complaints": return ("quality_complaints", "status=not.in.(CLOSED,CANCELLED)&complaint_type=eq.CUSTOMER")
        case "mod_supplier_complaints": return ("quality_complaints", "status=not.in.(CLOSED,CANCELLED)&complaint_type=eq.SUPPLIER")
        case "calibration_overdue": return ("quality_assets", "or=(next_due_date.lt.\(today),next_validation_due_date.lt.\(today))")
        case "calibration_due_30", "mod_calibration":
            return ("quality_assets", "or=(and(next_due_date.gte.\(today),next_due_date.lte.\(in30)),and(next_validation_due_date.gte.\(today),next_validation_due_date.lte.\(in30)))")
        case "npd_open": return ("npd_orders", "status=eq.OPEN")
        case "npd_in_progress": return ("npd_orders", "status=eq.IN_PROGRESS")
        default: return nil
        }
    }

    /// "a=eq.X&or=(..)" -> "&a=eq.X&or=%28..%29" (each name / value URL-encoded).
    static func encodeQuery(_ raw: String) -> String {
        var q = ""
        for part in raw.split(separator: "&") {
            guard let eq = part.firstIndex(of: "=") else { continue }
            let name = String(part[part.startIndex..<eq])
            let value = String(part[part.index(after: eq)...])
            if name.isEmpty { continue }
            q += "&" + Api.enc(name) + "=" + Api.enc(value)
        }
        return q
    }

    /// drill.filter {"col": "eq.X" | "X" | ["A","B"] | null, "or": "(...)"} -> encoded PostgREST query.
    static func filterQuery(_ filter: Row) -> String {
        var q = ""
        for col in filter.keys.sorted() {
            let v = filter[col]
            var expr = ""
            if let arr = v as? [Any] {
                expr = "in.(" + arr.map { J.str($0) }.joined(separator: ",") + ")"
            } else if J.isNull(v) {
                expr = "is.null"
            } else {
                let sv = J.str(v)
                let pattern = "^(not\\.)?(eq|neq|lt|lte|gt|gte|like|ilike|is|in|cs|cd|fts|plfts|phfts|wfts)\\."
                let raw = col == "or" || col == "and" || sv.range(of: pattern, options: .regularExpression) != nil
                expr = raw ? sv : "eq." + sv
            }
            q += "&" + Api.enc(col) + "=" + Api.enc(expr)
        }
        return q
    }

    /// Departments of qcms_module_cards shown on a section tab (1 Supply, 2 Quality, 3 Masters, 4 More).
    static func departments(tab: Int) -> [String] {
        switch tab {
        case 1: return ["SUPPLY_CHAIN", "PRODUCTION"]
        case 2: return ["QUALITY"]
        case 3: return ["MANAGEMENT"]
        case 4: return ["NPD"]
        default: return []
        }
    }

    // MARK: Create permission (core.access.module_permissions: admin -> user -> role -> department -> legacy role)

    private static var permCache: [String: Bool] = [:]
    private static var permUser = ""
    private static var permAt = Date.distantPast

    /// Permission module keys the signed-in user may create in (cached 5 min).
    static func creatable() async -> Set<String> {
        let api = Api.shared
        if permUser != api.userId || Date().timeIntervalSince(permAt) > 300 {
            permCache = [:]
            permUser = api.userId
            permAt = Date()
        }
        var out = Set<String>()
        for t in transactions where !t.permission.isEmpty {
            if out.contains(t.permission) { continue }
            var ok = false
            if let hit = permCache[t.permission] {
                ok = hit
            } else {
                ok = await canCreate(t.permission)
                permCache[t.permission] = ok
            }
            if ok { out.insert(t.permission) }
        }
        return out
    }

    static func canCreate(_ moduleKey: String) async -> Bool {
        let api = Api.shared
        if api.isAdmin { return true }
        let key = Api.enc(moduleKey)
        let own = await api.list("user_module_permissions?select=*&profile_id=eq.\(Api.enc(api.userId))&module_key=eq.\(key)&limit=1")
        if let r = own.first { return J.truthy(r["can_create"]) }
        let role = (api.role.isEmpty ? "VIEWER" : api.role).uppercased().replacingOccurrences(of: " ", with: "_")
        let byRole = await api.list("role_module_defaults?select=*&role=eq.\(Api.enc(role))&module_key=eq.\(key)&status=eq.ACTIVE&limit=1")
        if let r = byRole.first { return J.truthy(r["can_create"]) }
        let dept = await department()
        if !dept.isEmpty {
            let byDept = await api.list("department_module_defaults?select=*&department=eq.\(Api.enc(dept))&module_key=eq.\(key)&status=eq.ACTIVE&limit=1")
            if let r = byDept.first { return J.truthy(r["can_create"]) }
        }
        return legacyCreate(role, moduleKey)
    }

    private static func department() async -> String {
        let api = Api.shared
        let rows = await api.list("employees?select=profile_id,email,department&status=eq.ACTIVE&limit=5000")
        for r in rows where !api.userId.isEmpty && J.str(r["profile_id"]) == api.userId {
            return J.str(r["department"]).trimmingCharacters(in: .whitespaces)
        }
        let mail = api.email.trimmingCharacters(in: .whitespaces).lowercased()
        for r in rows where !mail.isEmpty && J.str(r["email"]).trimmingCharacters(in: .whitespaces).lowercased() == mail {
            return J.str(r["department"]).trimmingCharacters(in: .whitespaces)
        }
        return ""
    }

    /// Legacy role fallback of core/access.py (same as the Android app).
    static func legacyCreate(_ role: String, _ moduleKey: String) -> Bool {
        if role == "VIEWER" || role == "AUDITOR" { return false }
        let supply: Set<String> = ["SUPPLY_CHAIN", "PROCUREMENT", "PRODUCTION", "MANAGEMENT"]
        let quality: Set<String> = ["QUALITY_MANAGER", "QUALITY_ENGINEER", "METLAB_APPROVER", "SQA"]
        if moduleKey == "SUPPLY_CHAIN" { return supply.contains(role) || role == "QUALITY_MANAGER" || role == "MASTER_DATA" }
        if ["RMTC_ENTRY", "MATERIAL_INWARD", "DIMENSIONAL_REPORT", "METLAB_REPORT", "OSP_TRANSACTIONS"].contains(moduleKey) {
            return quality.contains(role) || role == "PRODUCTION" || role == "MANAGEMENT"
        }
        if moduleKey == "NPD_APQP" {
            return quality.contains(role) || ["PRODUCTION", "BUSINESS_DEVELOPMENT", "MANAGEMENT", "MASTER_DATA"].contains(role)
        }
        if moduleKey == "CALIBRATION_VALIDATION" { return quality.contains(role) || role == "MANAGEMENT" || role == "MASTER_DATA" }
        return quality.contains(role) || role == "MASTER_DATA" || role == "MANAGEMENT"
    }
}

/// Top-right "+" of the main screens.
struct QuickAddMenu: View {
    @EnvironmentObject var nav: TabNav
    /// Permission module keys with Create permission (nil while loading).
    @State private var allowed: Set<String>?

    private var allowedList: [QuickTransaction] {
        guard let ok = allowed else { return [] }
        return QuickActions.transactions.filter { $0.permission.isEmpty || ok.contains($0.permission) }
    }

    var body: some View {
        Menu {
            Menu {
                if allowed == nil {
                    Text("Checking your permissions…")
                } else if allowedList.isEmpty {
                    Text("No Create permission on any transaction")
                } else {
                    ForEach(allowedList) { t in
                        Button(QuickActions.isNative(t) ? t.label : t.label + " (website)") { QuickActions.open(t, nav: nav) }
                    }
                }
            } label: { Label("New transaction", systemImage: "plus.square.on.square") }
            Button { QuickActions.newEmail(nav: nav) } label: { Label("New e-mail", systemImage: "envelope") }
            Button { nav.push(.search("")) } label: { Label("New query (global search)", systemImage: "magnifyingglass") }
            Button { nav.push(.web("Search & AI", "global-search")) } label: { Label("Ask QCMS AI (Search & AI)", systemImage: "sparkles") }
        } label: {
            Image(systemName: "plus").font(.system(size: 18, weight: .semibold))
        }
        .accessibilityLabel("Quick actions: new transaction, e-mail, query")
        .task { allowed = await QuickActions.creatable() }
    }
}
