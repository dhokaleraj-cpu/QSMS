import SwiftUI

enum Route: Hashable {
    case module(String)
    case record(String, String)
    case search(String)
    case web(String, String)
    case reportsCentre
    case recordsCentre
    case universal(String)
    case about
    case account
    case form(String, String)      // module key, id ("" = new record)
    case history(String, String)   // module key, id
    case notifications
    case home
}

/// Navigation path of one tab (lets screens push / pop programmatically).
final class TabNav: ObservableObject {
    @Published var path = NavigationPath()
    func push(_ r: Route) { path.append(r) }
    func pop() { if !path.isEmpty { path.removeLast() } }
}

/// A generated PDF shown in the viewer sheet.
struct PdfItem: Identifiable {
    let id = UUID()
    let title: String
    let fileName: String
    let data: Data
}

struct MainView: View {
    @EnvironmentObject var app: AppState
    @EnvironmentObject var inbox: Inbox
    @State private var tab = 0
    var body: some View {
        TabView(selection: $tab) {
            ForEach(0..<Catalog.tabNames.count, id: \.self) { i in
                TabRoot(tab: i)
                    .tabItem { Label(Catalog.tabNames[i], systemImage: Catalog.tabIcons[i]) }
                    .tag(i)
            }
        }
        .task { await app.postLogin() }
        .onChange(of: inbox.openRequest) { _ in tab = 0 }
    }
}

/// One tab: navigation stack with the global search bar at the top of the root screen.
struct TabRoot: View {
    let tab: Int
    @EnvironmentObject var inbox: Inbox
    @StateObject private var nav = TabNav()
    @State private var query = ""

    var body: some View {
        NavigationStack(path: $nav.path) {
            Group {
                if tab == 0 { KpiDashboardView() } else { SectionView(tab: tab) }
            }
            .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: "Search Part, Heat, RMTC, Batch, PO, Report…")
            .onSubmit(of: .search) {
                let q = query.trimmingCharacters(in: .whitespaces)
                if !q.isEmpty { nav.push(.search(q)); query = "" }
            }
            .navigationDestination(for: Route.self) { RouteView(route: $0) }
        }
        .environmentObject(nav)
        .onAppear { if tab == 0 { openInboxIfRequested() } }
        .onChange(of: inbox.openRequest) { _ in if tab == 0 { openInboxIfRequested() } }
    }

    /// A tapped push notification opens the inbox on the first tab.
    private func openInboxIfRequested() {
        if inbox.consumeOpen() {
            nav.path = NavigationPath()
            nav.push(.notifications)
        }
    }
}

struct RouteView: View {
    let route: Route
    var body: some View {
        switch route {
        case .module(let key):
            if let m = Catalog.shared.module(key) { ModuleEntry(module: m) } else { ErrorBox(message: "Module not available.") }
        case .record(let key, let id):
            if let m = Catalog.shared.module(key) { RecordView(module: m, id: id) } else { ErrorBox(message: "Module not available.") }
        case .search(let q): SearchView(initial: q)
        case .web(let title, let path): WebPageView(title: title, path: path)
        case .reportsCentre: ReportsCentreView()
        case .recordsCentre: RecordsCentreView()
        case .universal(let key):
            if let m = Catalog.shared.module(key) { UniversalView(module: m) } else { ErrorBox(message: "Module not available.") }
        case .about: AboutView()
        case .account: AccountView()
        case .form(let key, let id):
            if let m = Catalog.shared.module(key) { FormScreen(module: m, id: id) } else { ErrorBox(message: "Module not available.") }
        case .history(let key, let id):
            if let m = Catalog.shared.module(key) { HistoryView(module: m, id: id) } else { ErrorBox(message: "Module not available.") }
        case .notifications: NotificationsView()
        case .home: HomeView()
        }
    }
}

/// Opens a catalogue module: native register, a native screen, or the website page for screens that are web-only for now.
struct ModuleEntry: View {
    let module: QModule
    var body: some View {
        switch module.key {
        case "global_search": SearchView(initial: "")
        case "reports_centre": ReportsCentreView()
        case "records_centre": RecordsCentreView()
        case "about": AboutView()
        case "my_account": AccountView()
        case "email_send": EmailComposeLauncher()
        default:
            if module.table.isEmpty || module.cols.isEmpty {
                WebPageView(title: module.title, path: WebRoutes.path(for: module.key) ?? "")
            } else {
                RegisterView(module: module)
            }
        }
    }
}

/// Module list of one tab, grouped by section (Supply / Quality / Masters / More).
struct SectionView: View {
    let tab: Int
    @EnvironmentObject var app: AppState

    var body: some View {
        List {
            if tab == 4 {
                Section("Reports & records") {
                    NavigationLink(value: Route.reportsCentre) { ModuleRow(title: "Reports Centre", detail: "Supply chain, heat, quality, complaints, NPD, APQP", icon: "chart.bar.doc.horizontal") }
                    NavigationLink(value: Route.recordsCentre) { ModuleRow(title: "Records Centre", detail: "Every register and record as PDF (website print layout)", icon: "doc.richtext") }
                    NavigationLink(value: Route.search("")) { ModuleRow(title: "Global Search", detail: "Part, Heat, RMTC, Batch, Supplier, Customer, PO, Report", icon: "magnifyingglass") }
                }
            }
            ForEach(Catalog.shared.sections(tab: tab)) { section in
                Section(section.name) {
                    ForEach(section.modules.filter { !hidden($0) }) { m in
                        NavigationLink(value: Route.module(m.key)) {
                            ModuleRow(title: m.title, detail: m.description, icon: icon(m), web: isWeb(m))
                        }
                    }
                }
            }
            if tab == 4 {
                Section("App") {
                    NavigationLink(value: Route.about) { ModuleRow(title: "About STAWN QCMS", detail: "Version, developer, copyright and licence", icon: "info.circle") }
                    NavigationLink(value: Route.account) { ModuleRow(title: "My Account & Security", detail: "Password, Face ID, sign out", icon: "person.crop.circle") }
                }
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle(Catalog.tabNames[tab])
        .qcmsNavBar()
        .qcmsBell()
    }

    private func hidden(_ m: QModule) -> Bool { ["global_search", "reports_centre", "records_centre", "about", "my_account"].contains(m.key) }
    private func isWeb(_ m: QModule) -> Bool { (m.table.isEmpty || m.cols.isEmpty) && !["email_send", "global_search", "reports_centre", "records_centre", "about", "my_account"].contains(m.key) }

    private func icon(_ m: QModule) -> String {
        let t = m.title.lowercased()
        if t.contains("purchase") || t.contains("order") { return "cart" }
        if t.contains("rmtc") || t.contains("heat") { return "flame" }
        if t.contains("inward") || t.contains("receipt") { return "tray.and.arrow.down" }
        if t.contains("metlab") || t.contains("bend") { return "testtube.2" }
        if t.contains("dimensional") || t.contains("layout") || t.contains("inspection") { return "ruler" }
        if t.contains("complaint") { return "exclamationmark.bubble" }
        if t.contains("calibration") || t.contains("asset") { return "gauge" }
        if t.contains("email") { return "envelope" }
        if t.contains("part") { return "gearshape.2" }
        if t.contains("report") || t.contains("ledger") || t.contains("balance") { return "chart.bar" }
        if t.contains("npd") || t.contains("apqp") || t.contains("pfmea") || t.contains("control") || t.contains("flow") { return "point.3.connected.trianglepath.dotted" }
        if t.contains("employee") || t.contains("user") { return "person.2" }
        return "square.grid.2x2"
    }
}

struct ModuleRow: View {
    let title: String
    let detail: String
    var icon: String = "square.grid.2x2"
    var web = false
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon).font(.system(size: 17, weight: .semibold)).foregroundColor(Theme.teal)
                .frame(width: 34, height: 34).background(Theme.tealSoft).clipShape(RoundedRectangle(cornerRadius: 9))
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(title).font(.subheadline.weight(.semibold)).foregroundColor(Theme.text)
                    if web { Text("WEB").font(.system(size: 9, weight: .bold)).foregroundColor(Theme.amber).padding(.horizontal, 5).padding(.vertical, 1).background(Theme.amberBg).clipShape(Capsule()) }
                }
                if !detail.isEmpty { Text(detail).font(.caption).foregroundColor(Theme.muted).lineLimit(2) }
            }
        }
        .padding(.vertical, 2)
    }
}
