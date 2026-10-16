import SwiftUI

/// Reports Centre like the website (app_pages/reports.py render_home).
struct ReportsCentreView: View {
    @EnvironmentObject var nav: TabNav
    @State private var kpi: [String] = ["…", "…", "…", "…"]

    static let operational: [[String]] = [
        ["customer_orders", "Supply Chain Order / Dispatch MIS", "Customer, part, monthly schedule, dispatch, pending quantity"],
        ["purchase_orders", "Purchase Order Reports", "Pending POs, RM orders, supplier and part procurement"],
        ["rep_global_balance", "Heat Number Global Balance", "RMTC plan, inward, OSP movement and global steel balance"],
        ["rep_heat_transactions", "Heat Transaction Report", "Every steel / production movement per heat"],
        ["rep_osp_balance", "OSP Heat Movement", "OSP outward, inward, material at vendor, balance to send"],
        ["rmtc", "RMTC Register", "RMTC records, heat details, validation and decision history"]]
    static let quality: [[String]] = [
        ["inward", "Material Inward", "Material inward, supplier, heat, RMTC and quantity records"],
        ["dimensional_reports", "Dimensional Inspection", "Results, conclusion, final decision, print layout PDF"],
        ["metlab_reports", "MetLAB", "Metallurgical results, conclusion, final decision, print layout PDF"],
        ["bend_tests", "Bend Test", "Bend test register, report and print layout PDF"],
        ["customer_complaints", "Customer Complaints", "Analysis, RCA and CAPA records"],
        ["supplier_complaints", "Supplier Complaints", "Analysis, RCA and CAPA records"]]
    static let management: [[String]] = [
        ["traceability", "Supply Chain Traceability", "Order-to-dispatch genealogy, heat / RMTC lineage"],
        ["npd_orders", "NPD Status", "Part development status, target dates and completion"],
        ["apqp_projects", "APQP Status", "APQP gate status, responsibility and completion"],
        ["qc_calculations", "QC Calculations", "Saved quality-tool calculations and results"],
        ["inspection_layouts", "Inspection Layouts", "Dimensional / MetLAB layout definitions and revisions"],
        ["customer_standards", "Customer Standards", "Customer standards / specifications bank"],
        ["rep_steel_ledger", "Heat Steel Ledger", "Steel balance per heat, RMTC and part"],
        ["rep_heat_production", "Heat Production Summary", "Accepted / rejected / hold pieces per heat"],
        ["rep_inward_register", "Inward Register", "Material inward with RMTC and quality status"],
        ["rep_rmtc_usage", "Heat RMTC Usage", "Planned vs inward steel per RMTC part"],
        ["kpi_dashboards", "KPI Dashboards", "Management dashboards with charts"],
        ["report_builder", "Report Builder", "Build any report with filters, totals and charts"],
        ["master_lists", "Master Lists", "Clean lists of every master"]]

    var body: some View {
        List {
            Section {
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                    kpiTile(kpi[0], "Heat Numbers", Theme.green)
                    kpiTile(kpi[1], "Global Heat Balance kg", Theme.amber)
                    kpiTile(kpi[2], "OSP Out pcs", Color(hex: 0x1479CC))
                    kpiTile(kpi[3], "Balance to Send OSP pcs", Theme.red)
                }
                .padding(.vertical, 4)
            }
            group("Operational & Supply Chain Reports", ReportsCentreView.operational)
            group("Quality & Material Reports", ReportsCentreView.quality)
            group("Management, Traceability & Control Reports", ReportsCentreView.management)
            Section { NavigationLink(value: Route.recordsCentre) { ModuleRow(title: "Records Centre", detail: "Registers, Universal record PDFs, deletion requests, history", icon: "doc.richtext") } }
        }
        .navigationTitle("Reports Centre")
        .qcmsNavBar()
        .task { await load() }
    }

    private func kpiTile(_ value: String, _ label: String, _ color: Color) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value).font(.title3.bold()).foregroundColor(color)
            Text(label).font(.caption).foregroundColor(Theme.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder private func group(_ title: String, _ items: [[String]]) -> some View {
        Section(title) {
            ForEach(items.filter { Catalog.shared.module($0[0]) != nil }, id: \.self) { it in
                NavigationLink(value: Route.module(it[0])) { ModuleRow(title: it[1], detail: it[2], icon: "chart.bar.doc.horizontal") }
            }
        }
    }

    private func load() async {
        let heat = await Api.shared.list("v_qsms_heat_global_balance_report?select=*&limit=5000")
        let osp = await Api.shared.list("v_qsms_heat_osp_balance_report?select=*&limit=5000")
        let bal = heat.reduce(0.0) { $0 + J.double($1["available_unallocated_steel_quantity_kg"]) }
        let out = heat.reduce(0.0) { $0 + J.double($1["osp_out_quantity_pcs"]) }
        let send = osp.reduce(0.0) { $0 + J.double($1["balance_to_send_osp_pcs"]) }
        kpi = [Fmt.num(Double(heat.count), 0), Fmt.num(bal, 3), Fmt.num(out, 0), Fmt.num(send, 0)]
    }
}

/// Records Centre (app_pages/records_center.py): every register, Universal record PDFs, control registers.
struct RecordsCentreView: View {
    var body: some View {
        List {
            Section { Text("Select any register: download the full register PDF, or tap a record for its controlled print layout PDF (view, save, print, email, share).").font(.footnote).foregroundColor(Theme.muted) }
            ForEach(areas) { area in
                Section(area.name) {
                    ForEach(area.modules) { m in
                        NavigationLink(value: Route.universal(m.key)) {
                            ModuleRow(title: m.title, detail: RptReports.dedicated(m.table) ? "Website print layout report" : "Universal record PDF", icon: "doc.text")
                        }
                    }
                }
            }
            Section("Control") {
                ForEach(["deletion_requests", "deleted_records", "activity_log", "email_outbox"], id: \.self) { key in
                    if let m = Catalog.shared.module(key) {
                        NavigationLink(value: Route.module(key)) { ModuleRow(title: m.title, detail: m.description, icon: "checklist") }
                    }
                }
            }
        }
        .navigationTitle("Records Centre")
        .qcmsNavBar()
    }

    private var areas: [ModuleSection] {
        let names = ["Supply", "Quality", "Masters", "More"]
        var out: [ModuleSection] = []
        for m in Catalog.shared.modules where !m.table.isEmpty && !m.idField.isEmpty && !m.cols.isEmpty && !["deletion_requests", "activity_log", "email_outbox"].contains(m.key) {
            let area = (1...4).contains(m.tab) ? names[m.tab - 1] : "More"
            let key = "\(area) · \(m.section)"
            if let i = out.firstIndex(where: { $0.name == key }) { out[i].modules.append(m) } else { out.append(ModuleSection(name: key, modules: [m])) }
        }
        return out
    }
}

/// One register in the Records Centre: search, full register PDF, tap a record for its print layout PDF.
struct UniversalView: View {
    let module: QModule
    @EnvironmentObject var nav: TabNav
    @State private var rows: [Row] = []
    @State private var fk: [String: [String: String]] = [:]
    @State private var loading = true
    @State private var error: String?
    @State private var search = ""
    @State private var pdf: PdfItem?
    @State private var busy = false
    @State private var chosen: Row?

    private var visible: [Row] {
        let q = search.lowercased()
        if q.isEmpty { return rows }
        return rows.filter { r in lines([r])[0].joined(separator: " ").lowercased().contains(q) || r.values.map { J.str($0) }.joined(separator: " ").lowercased().contains(q) }
    }

    private func lines(_ list: [Row]) -> [[String]] { list.map { r in module.cols.map { Labels.cell($0[0], r[$0[0]], fk[$0[0]]) } } }

    var body: some View {
        let list = visible
        VStack(alignment: .leading, spacing: 8) {
            TextField("Search this register", text: $search).textFieldStyle(.roundedBorder)
            Button { registerPdf(list) } label: { Label(busy ? "Preparing…" : "Download Full Register PDF", systemImage: "doc.richtext").frame(maxWidth: .infinity) }
                .buttonStyle(.bordered).disabled(busy || list.isEmpty)
            if let e = error { ErrorBox(message: e) { Task { await load() } } }
            else if loading { ProgressView().frame(maxWidth: .infinity).padding(30) }
            else {
                Text("\(list.count) record(s) · tap a row for its print layout PDF").font(.caption).foregroundColor(Theme.muted)
                SheetGrid(columns: module.cols.map { $0[1] }, rows: lines(list)) { i in if i < list.count { chosen = list[i] } }
            }
        }
        .padding(10)
        .background(Theme.bg)
        .navigationTitle(module.title)
        .navigationBarTitleDisplayMode(.inline)
        .qcmsNavBar()
        .confirmationDialog(chosen.map { module.recordTitle($0) } ?? "", isPresented: Binding(get: { chosen != nil }, set: { if !$0 { chosen = nil } }), titleVisibility: .visible) {
            Button("Print layout PDF · Save · Print · Email") { if let r = chosen { layoutPdf(J.str(r[module.idField])) } }
            Button("Open record") { if let r = chosen { nav.push(.record(module.key, J.str(r[module.idField]))) } }
        }
        .sheet(item: $pdf) { PdfViewer(item: $0) }
        .task { if rows.isEmpty { await load() } }
    }

    private func load() async {
        error = nil
        do {
            let order = module.order.isEmpty ? "" : "&order=\(module.order)"
            let data = try await Api.shared.rows("\(module.table)?select=*\(module.filter)\(order)&limit=2000")
            fk = await Labels.resolve(module.table, rows: data, columns: module.cols.map { $0[0] })
            rows = data
        } catch { self.error = error.localizedDescription }
        loading = false
    }

    private func layoutPdf(_ id: String) {
        busy = true
        Task {
            do {
                let doc = try await RptReports.forRecord(module, id)
                pdf = PdfItem(title: doc.title, fileName: doc.fileBase, data: RptPdf.render(doc))
            } catch { self.error = error.localizedDescription }
            busy = false
        }
    }

    private func registerPdf(_ list: [Row]) {
        busy = true
        let heads = module.cols.map { $0[1] }
        let data = lines(list)
        Task {
            let doc = await RptReports.register(module.title, columns: heads, rows: data)
            pdf = PdfItem(title: doc.title, fileName: doc.fileBase, data: RptPdf.render(doc))
            busy = false
        }
    }
}
