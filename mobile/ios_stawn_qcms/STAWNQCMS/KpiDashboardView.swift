import SwiftUI
import Charts

/// Department of the KPI start dashboard (qcms_kpi_dashboard p_department), Quality first.
struct KpiDept: Identifiable {
    let key: String
    let short: String
    let title: String
    var id: String { key }

    static let all: [KpiDept] = [
        KpiDept(key: "QUALITY", short: "Quality", title: "Quality"),
        KpiDept(key: "SUPPLY_CHAIN", short: "Supply", title: "Supply Chain"),
        KpiDept(key: "PRODUCTION", short: "Production", title: "Production"),
        KpiDept(key: "NPD", short: "NPD", title: "NPD"),
        KpiDept(key: "MANAGEMENT", short: "Mgmt", title: "Management"),
    ]

    static func titleFor(_ key: String) -> String { all.first { $0.key == key }?.title ?? Fmt.pretty(key) }
}

struct KpiCard: Identifiable {
    let id: Int
    let label: String
    let value: String
    let unit: String
    let tone: String
    let route: String
}

struct KpiSeries {
    let name: String
    let values: [Double]
}

struct KpiPoint: Identifiable {
    let id: String
    let label: String
    let series: String
    let value: Double
}

struct KpiChart: Identifiable {
    let id: Int
    let title: String
    let type: String
    let labels: [String]
    let series: [KpiSeries]

    /// Every (label, series, value) for bar / line charts.
    var points: [KpiPoint] {
        var out: [KpiPoint] = []
        for (si, s) in series.enumerated() {
            for (i, label) in labels.enumerated() where i < s.values.count {
                out.append(KpiPoint(id: "\(si)-\(i)", label: label, series: s.name.isEmpty ? title : s.name, value: s.values[i]))
            }
        }
        return out
    }

    /// First series only, one slice per label (donut).
    var slices: [KpiPoint] {
        guard let s = series.first else { return [] }
        var out: [KpiPoint] = []
        for (i, label) in labels.enumerated() where i < s.values.count {
            out.append(KpiPoint(id: "d-\(i)", label: label, series: label, value: s.values[i]))
        }
        return out
    }
}

struct KpiTask: Identifiable {
    let id: Int
    let title: String
    let moduleKey: String
    let relatedId: String
    let due: String
    let webRoute: String

    var overdue: Bool { due.count >= 10 && String(due.prefix(10)) < Fmt.today() }
}

/// Parsed qcms_kpi_dashboard answer.
struct KpiData {
    let cards: [KpiCard]
    let charts: [KpiChart]
    let tasks: [KpiTask]

    init(_ row: Row) {
        var cards: [KpiCard] = []
        for (i, c) in J.rows(row["cards"]).enumerated() {
            cards.append(KpiCard(id: i, label: J.str(c["label"]), value: J.str(c["value"]), unit: J.str(c["unit"]),
                                 tone: J.str(c["tone"]).lowercased(), route: J.str(c["route"])))
        }
        var charts: [KpiChart] = []
        for (i, c) in J.rows(row["charts"]).enumerated() {
            let labels = J.list(c["labels"]).map { J.str($0) }
            var series: [KpiSeries] = []
            for s in J.rows(c["series"]) {
                series.append(KpiSeries(name: J.str(s["name"]), values: J.list(s["values"]).map { J.num($0) ?? 0 }))
            }
            charts.append(KpiChart(id: i, title: J.str(c["title"]), type: J.str(c["type"]).lowercased(), labels: labels, series: series))
        }
        var tasks: [KpiTask] = []
        for (i, t) in J.rows(row["pending_tasks"]).enumerated() {
            tasks.append(KpiTask(id: i, title: J.str(t["title"]), moduleKey: J.str(t["module_key"]), relatedId: J.str(t["related_id"]),
                                 due: J.str(t["due"]), webRoute: J.str(t["web_route"])))
        }
        self.cards = cards
        self.charts = charts
        self.tasks = tasks
    }
}

/// KPI start dashboard: pending tasks first, KPI cards and charts per department, auto-switching every 20 s.
struct KpiDashboardView: View {
    @EnvironmentObject var nav: TabNav
    @EnvironmentObject var app: AppState
    @EnvironmentObject var inbox: Inbox
    @State private var dept = "QUALITY"
    @State private var cache: [String: KpiData] = [:]
    /// When each department was last fetched (in-memory cache, reused for cacheSeconds).
    @State private var loadedAt: [String: Date] = [:]
    @State private var errors: [String: String] = [:]
    @State private var loading = false
    @State private var pausedUntil = Date.distantPast

    static let autoSeconds: UInt64 = 20
    static let pauseSeconds: TimeInterval = 60
    static let cacheSeconds: TimeInterval = 5 * 60

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                header
                Picker("Department", selection: deptBinding) {
                    ForEach(KpiDept.all) { d in Text(d.short).tag(d.key) }
                }
                .pickerStyle(.segmented)
                ZStack(alignment: .top) {
                    KpiPage(title: KpiDept.titleFor(dept), data: cache[dept], error: errors[dept])
                        .id(dept)
                        .transition(.asymmetric(insertion: .move(edge: .trailing), removal: .move(edge: .leading)))
                }
                .frame(maxWidth: .infinity, alignment: .top)
                .clipped()
                links
            }
            .padding()
        }
        .background(Theme.bg)
        .navigationTitle("Dashboard")
        .qcmsNavBar()
        .qcmsBrand()
        .toolbar {
            ToolbarItemGroup(placement: .navigationBarTrailing) {
                Button { nav.push(.home) } label: { Image(systemName: "house") }.accessibilityLabel("Home")
                Button { Task { await load(dept, force: true) } } label: { Image(systemName: "arrow.clockwise") }
                    .accessibilityLabel("Refresh").disabled(loading)
            }
        }
        .qcmsBell()
        .refreshable {
            await load(dept, force: true)
            await inbox.refreshCount()
        }
        .task(id: dept) { await cycle() }
    }

    private var header: some View {
        HStack(spacing: 14) {
            LogoView(size: 52)
            VStack(alignment: .leading, spacing: 2) {
                Text(Api.shared.fullName.isEmpty ? "Welcome" : "Welcome, \(Api.shared.fullName)").font(.headline).foregroundColor(Theme.text)
                CompanyLine(licence: app.licence)
                Text(Date() < pausedUntil ? "Auto-switch paused · resumes after 60 s" : "Departments switch every 20 s")
                    .font(.caption2).foregroundColor(Theme.muted)
            }
            Spacer()
            if loading { ProgressView() }
        }
        .padding(12).background(Color.white).clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private var links: some View {
        VStack(spacing: 10) {
            SectionLabel(text: "More")
            Button { nav.push(.home) } label: { ModuleRow(title: "Home", detail: "Today counters and quick open of every register", icon: "house") }
                .padding(10).background(Color.white).clipShape(RoundedRectangle(cornerRadius: 14))
            Button { nav.push(.notifications) } label: {
                ModuleRow(title: "Notifications", detail: inbox.unread > 0 ? "\(inbox.unread) unread" : "Approvals, tasks and alerts", icon: "bell")
            }
            .padding(10).background(Color.white).clipShape(RoundedRectangle(cornerRadius: 14))
            Button { nav.push(.reportsCentre) } label: { ModuleRow(title: "Reports Centre", detail: "All reports like the website", icon: "chart.bar.doc.horizontal") }
                .padding(10).background(Color.white).clipShape(RoundedRectangle(cornerRadius: 14))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// User picked a tab: switch with animation and pause the auto-switch for 60 s.
    private var deptBinding: Binding<String> {
        Binding(get: { dept }, set: { value in
            pausedUntil = Date().addingTimeInterval(KpiDashboardView.pauseSeconds)
            if value != dept { withAnimation(.easeInOut(duration: 0.45)) { dept = value } }
        })
    }

    /// Loads the shown department, then moves to the next one after 20 s unless paused (restarts on every department change).
    @MainActor private func cycle() async {
        await load(dept)
        await inbox.refreshCount()
        while !Task.isCancelled {
            try? await Task.sleep(nanoseconds: KpiDashboardView.autoSeconds * 1_000_000_000)
            if Task.isCancelled { return }
            if Date() >= pausedUntil {
                advance()
                return
            }
        }
    }

    @MainActor private func advance() {
        let keys = KpiDept.all.map { $0.key }
        let i = keys.firstIndex(of: dept) ?? 0
        let next = keys[(i + 1) % keys.count]
        withAnimation(.easeInOut(duration: 0.6)) { dept = next }
    }

    /// Reuses data younger than 5 minutes (auto-switch); force = refresh button / pull to refresh.
    @MainActor private func load(_ d: String, force: Bool = false) async {
        if !force, cache[d] != nil, let at = loadedAt[d], Date().timeIntervalSince(at) < KpiDashboardView.cacheSeconds { return }
        loading = true
        do {
            let raw = try await Api.shared.rpc("qcms_kpi_dashboard", ["p_department": d])
            cache[d] = KpiData(J.obj(raw))
            loadedAt[d] = Date()
            errors[d] = nil
        } catch {
            if !Task.isCancelled && cache[d] == nil { errors[d] = error.localizedDescription }
        }
        loading = false
    }
}

/// One department page (pending tasks, cards, charts).
struct KpiPage: View {
    let title: String
    let data: KpiData?
    let error: String?
    @EnvironmentObject var nav: TabNav

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let data = data {
                SectionLabel(text: "Pending tasks (\(data.tasks.count))")
                if data.tasks.isEmpty {
                    Text("No pending tasks for \(title).").font(.footnote).foregroundColor(Theme.muted)
                        .frame(maxWidth: .infinity, alignment: .leading).padding(12)
                        .background(Color.white).clipShape(RoundedRectangle(cornerRadius: 14))
                } else {
                    VStack(spacing: 0) {
                        ForEach(data.tasks) { t in
                            Button { openTask(t) } label: { taskRow(t) }
                            if t.id != data.tasks.last?.id { Divider() }
                        }
                    }
                    .background(Color.white).clipShape(RoundedRectangle(cornerRadius: 14))
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
                }

                SectionLabel(text: "\(title) KPIs")
                if data.cards.isEmpty {
                    Text("No KPI figures yet.").font(.footnote).foregroundColor(Theme.muted)
                } else {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 150), spacing: 10)], spacing: 10) {
                        ForEach(data.cards) { c in
                            Button { openRoute(c.route, c.label) } label: { cardView(c) }.buttonStyle(.plain)
                        }
                    }
                }

                ForEach(data.charts) { ch in KpiChartCard(chart: ch) }
            } else if let e = error {
                ErrorBox(message: e)
            } else {
                ProgressView("Loading \(title) dashboard…").frame(maxWidth: .infinity).padding(30)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func taskRow(_ t: KpiTask) -> some View {
        HStack(spacing: 10) {
            Image(systemName: t.overdue ? "exclamationmark.circle.fill" : "checklist")
                .foregroundColor(t.overdue ? Theme.red : Theme.amber)
            VStack(alignment: .leading, spacing: 2) {
                Text(t.title.isEmpty ? "Task" : t.title).font(.subheadline.weight(.semibold)).foregroundColor(Theme.text)
                    .multilineTextAlignment(.leading).lineLimit(2)
                if !t.due.isEmpty {
                    Text((t.overdue ? "Overdue · due " : "Due ") + Fmt.date(t.due)).font(.caption)
                        .foregroundColor(t.overdue ? Theme.red : Theme.muted)
                }
            }
            Spacer()
            Image(systemName: "chevron.right").font(.caption).foregroundColor(Theme.muted)
        }
        .padding(12)
        .contentShape(Rectangle())
    }

    private func cardView(_ c: KpiCard) -> some View {
        let color = KpiPage.toneColor(c.tone)
        return VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text(c.value.isEmpty ? "-" : c.value).font(.title.bold()).foregroundColor(color).lineLimit(1).minimumScaleFactor(0.6)
                if !c.unit.isEmpty { Text(c.unit).font(.caption.weight(.semibold)).foregroundColor(Theme.muted) }
            }
            Text(c.label).font(.caption).foregroundColor(Theme.muted).multilineTextAlignment(.leading).lineLimit(2)
        }
        .frame(maxWidth: .infinity, minHeight: 84, alignment: .leading).padding(12)
        .background(Color.white).clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
    }

    static func toneColor(_ tone: String) -> Color {
        switch tone {
        case "good", "ok", "success", "green", "positive": return Theme.green
        case "warn", "warning", "amber", "attention": return Theme.amber
        case "bad", "danger", "red", "critical", "negative", "error": return Theme.red
        case "info", "blue": return Theme.brand
        default: return Theme.tealDark
        }
    }

    private func openTask(_ t: KpiTask) {
        if let r = AppLinks.route(title: t.title, table: "", id: t.relatedId, moduleKey: t.moduleKey, webRoute: t.webRoute) { nav.push(r) }
    }

    private func openRoute(_ route: String, _ title: String) {
        if let r = AppLinks.route(title: title, table: "", id: "", moduleKey: "", webRoute: route) { nav.push(r) }
    }
}

struct KpiChartCard: View {
    let chart: KpiChart

    var body: some View {
        Card {
            Text(chart.title.isEmpty ? "Chart" : chart.title).font(.subheadline.weight(.semibold)).foregroundColor(Theme.text)
            if (chart.type == "donut" || chart.type == "pie" ? chart.slices : chart.points).isEmpty {
                Text("No data yet.").font(.caption).foregroundColor(Theme.muted)
            } else {
                chartView
            }
        }
    }

    @ViewBuilder private var chartView: some View {
        if #available(iOS 16, *) {
            KpiChartBody(chart: chart).frame(height: 210)
        } else {
            Text("Charts need iOS 16 or newer.").font(.caption).foregroundColor(Theme.muted)
        }
    }
}

/// Swift Charts rendering: bar (grouped), line, donut (iOS 17; bars on iOS 16).
struct KpiChartBody: View {
    let chart: KpiChart

    var body: some View {
        if chart.type == "donut" || chart.type == "pie" {
            if #available(iOS 17, *) {
                KpiDonutChart(points: chart.slices)
            } else {
                KpiBarChart(points: chart.slices, showLegend: false)
            }
        } else if chart.type == "line" {
            KpiLineChart(points: chart.points, showLegend: chart.series.count > 1)
        } else {
            KpiBarChart(points: chart.points, showLegend: chart.series.count > 1)
        }
    }
}

struct KpiBarChart: View {
    let points: [KpiPoint]
    let showLegend: Bool

    var body: some View {
        Chart(points) { p in
            BarMark(x: .value("Label", p.label), y: .value("Value", p.value))
                .foregroundStyle(by: .value("Series", p.series))
                .position(by: .value("Series", p.series))
        }
        .chartLegend(showLegend ? .visible : .hidden)
    }
}

struct KpiLineChart: View {
    let points: [KpiPoint]
    let showLegend: Bool

    var body: some View {
        Chart(points) { p in
            LineMark(x: .value("Label", p.label), y: .value("Value", p.value))
                .foregroundStyle(by: .value("Series", p.series))
                .symbol(by: .value("Series", p.series))
        }
        .chartLegend(showLegend ? .visible : .hidden)
    }
}

@available(iOS 17, *)
struct KpiDonutChart: View {
    let points: [KpiPoint]

    var body: some View {
        Chart(points) { p in
            SectorMark(angle: .value("Value", p.value), innerRadius: .ratio(0.6), angularInset: 1.5)
                .foregroundStyle(by: .value("Label", p.label))
        }
        .chartLegend(.visible)
    }
}
