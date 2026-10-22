import SwiftUI

struct HomeView: View {
    @EnvironmentObject var nav: TabNav
    @EnvironmentObject var app: AppState
    @State private var kpi: [Int] = [-1, -1, -1, -1, -1, -1]
    @State private var name = Api.shared.fullName

    private let shortcuts: [(String, String, String)] = [
        ("purchase_orders", "Purchase Orders", "cart"), ("po_approval", "PO Approval", "checkmark.seal"), ("customer_orders", "Customer Orders", "list.bullet.rectangle"),
        ("rmtc", "RMTC Approvals", "flame"), ("inward", "Material Inward", "tray.and.arrow.down"), ("metlab_reports", "MetLAB Reports", "testtube.2"),
        ("bend_tests", "Bend Test", "arrow.uturn.down"), ("dimensional_reports", "Dimensional", "ruler"), ("customer_complaints", "Complaints", "exclamationmark.bubble"),
        ("calibration_records", "Calibration", "gauge"), ("osp_register", "OSP Register", "shippingbox"), ("parts", "Part Master", "gearshape.2"),
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 14) {
                    LogoView(size: 56)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(name.isEmpty ? "Welcome" : "Welcome, \(name)").font(.title3.bold()).foregroundColor(Theme.text)
                        Text(Api.shared.employeeLabel.isEmpty ? Api.shared.email : Api.shared.employeeLabel).font(.caption).foregroundColor(Theme.muted)
                        CompanyLine(licence: app.licence)
                    }
                    Spacer()
                }
                .padding(14).background(Color.white).clipShape(RoundedRectangle(cornerRadius: 16))

                SectionLabel(text: "Today")
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 150), spacing: 10)], spacing: 10) {
                    tile(0, "POs awaiting approval", .module("po_approval"), amber: true)
                    tile(1, "Supplier confirmations pending", .module("po_confirmations"))
                    tile(2, "Open customer orders", .module("customer_orders"))
                    tile(3, "Calibrations overdue", .module("calibration_records"), red: true)
                    tile(4, "Calibrations due in 30 days", .module("calibration_records"), amber: true)
                    if Api.shared.isAdmin { tile(5, "Deletion requests (Admin)", .module("deletion_requests"), red: true) }
                }

                SectionLabel(text: "Quick open")
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 104), spacing: 10)], spacing: 10) {
                    ForEach(shortcuts.indices, id: \.self) { i in
                        let s = shortcuts[i]
                        Button { nav.push(.module(s.0)) } label: {
                            VStack(spacing: 6) {
                                Image(systemName: s.2).font(.title3).foregroundColor(Theme.teal)
                                Text(s.1).font(.caption.weight(.semibold)).foregroundColor(Theme.text).multilineTextAlignment(.center).lineLimit(2)
                            }
                            .frame(maxWidth: .infinity, minHeight: 78).background(Color.white).clipShape(RoundedRectangle(cornerRadius: 14))
                            .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
                        }
                    }
                }

                SectionLabel(text: "Reports & records")
                Button { nav.push(.reportsCentre) } label: { ModuleRow(title: "Reports Centre", detail: "All reports like the website", icon: "chart.bar.doc.horizontal") }
                    .padding(10).background(Color.white).clipShape(RoundedRectangle(cornerRadius: 14))
                Button { nav.push(.recordsCentre) } label: { ModuleRow(title: "Records Centre", detail: "Every register and record as PDF", icon: "doc.richtext") }
                    .padding(10).background(Color.white).clipShape(RoundedRectangle(cornerRadius: 14))
            }
            .padding()
        }
        .background(Theme.bg)
        .navigationTitle("Home")
        .qcmsNavBar()
        .qcmsBrand()
        .qcmsBell()
        .task { await load() }
        .refreshable { await load() }
    }

    private func tile(_ i: Int, _ label: String, _ route: Route, amber: Bool = false, red: Bool = false) -> some View {
        let value = kpi[i]
        let color: Color = value > 0 ? (red ? Theme.red : (amber ? Theme.amber : Theme.tealDark)) : Theme.green
        return Button { nav.push(route) } label: {
            VStack(alignment: .leading, spacing: 4) {
                Text(value < 0 ? "…" : "\(value)").font(.title.bold()).foregroundColor(color)
                Text(label).font(.caption).foregroundColor(Theme.muted).multilineTextAlignment(.leading)
            }
            .frame(maxWidth: .infinity, minHeight: 84, alignment: .leading).padding(12)
            .background(Color.white).clipShape(RoundedRectangle(cornerRadius: 14))
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
        }
    }

    private func load() async {
        name = Api.shared.fullName
        let api = Api.shared
        let today = Fmt.today()
        let soon: String = {
            let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd"
            return f.string(from: Date().addingTimeInterval(30 * 86400))
        }()
        async let a = api.count("supply_purchase_orders?select=id&approval_status=eq.PENDING_APPROVAL&status=neq.CANCELLED")
        async let b = api.count("supply_po_confirmations?select=id&confirmation_status=eq.PENDING")
        async let c = api.count("supply_customer_orders?select=id&status=in.(OPEN,IN_PROGRESS)")
        async let d = api.count("quality_assets?select=id&status=eq.ACTIVE&next_due_date=lt.\(today)")
        async let e = api.count("quality_assets?select=id&status=eq.ACTIVE&next_due_date=gte.\(today)&next_due_date=lte.\(soon)")
        var f = 0
        if api.isAdmin { f = await api.count("qcms_delete_requests?select=id&status=eq.PENDING") }
        kpi = await [a, b, c, d, e, f]
    }
}
