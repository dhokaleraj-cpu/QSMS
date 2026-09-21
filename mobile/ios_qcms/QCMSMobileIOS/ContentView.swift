import SwiftUI

struct ContentView: View {
    @AppStorage("qcmsURL") private var qcmsURL = ""
    @State private var draftURL = ""
    @State private var drawerOpen = false
    @State private var expandedSections: Set<String> = []

    private let bar = Color(red: 0.10, green: 0.11, blue: 0.13)
    private let accent = Color(red: 0.10, green: 0.42, blue: 0.72)

    var body: some View {
        Group {
            if qcmsURL.isEmpty {
                setupView
            } else {
                ZStack(alignment: .leading) {
                    VStack(spacing: 0) {
                        topBar
                        QCMSWebView(urlString: qcmsURL)
                        bottomBar
                    }
                    .background(Color(.systemBackground))
                    if drawerOpen { drawer }
                }
                .ignoresSafeArea(edges: .bottom)
            }
        }
    }

    private var topBar: some View {
        HStack(spacing: 6) {
            Button { withAnimation(.easeOut(duration: 0.18)) { drawerOpen.toggle() } } label: {
                Image(systemName: "line.3.horizontal").font(.title3.bold()).frame(width: 44, height: 44)
            }
            Image("AppIconPreview").resizable().scaledToFit().frame(width: 30, height: 30).clipShape(RoundedRectangle(cornerRadius: 6))
            Text("QCMS").font(.headline.bold())
            Spacer()
            Button { NotificationCenter.default.post(name: .qcmsReload, object: nil) } label: {
                Image(systemName: "arrow.clockwise").frame(width: 44, height: 44)
            }
            Menu {
                Button("Open in Safari") { if let url = URL(string: qcmsURL) { UIApplication.shared.open(url) } }
                Button("Change QCMS URL", role: .destructive) { qcmsURL = ""; draftURL = "" }
            } label: { Image(systemName: "ellipsis").frame(width: 44, height: 44) }
        }
        .padding(.horizontal, 8).frame(height: 56).foregroundStyle(.white).background(bar)
    }

    private var bottomBar: some View {
        HStack(spacing: 0) {
            navButton("house", "Home", "dashboard")
            Button { navigate("global-search") } label: {
                VStack(spacing: 2) {
                    ZStack { Circle().fill(accent).frame(width: 54, height: 54); Image(systemName: "magnifyingglass").font(.title2.bold()).foregroundStyle(.white) }
                    Text("Search").font(.caption2).foregroundStyle(.primary)
                }
                .frame(maxWidth: .infinity)
            }
            navButton("exclamationmark.bubble", "Complaints", "complaints-home")
        }
        .padding(.horizontal, 6).padding(.top, 5).padding(.bottom, 4).background(.ultraThinMaterial)
    }

    private func navButton(_ icon: String, _ title: String, _ path: String) -> some View {
        Button { navigate(path) } label: {
            VStack(spacing: 4) { Image(systemName: icon).font(.title3); Text(title).font(.caption2) }
                .frame(maxWidth: .infinity).foregroundStyle(.primary)
        }
    }

    private var drawer: some View {
        GeometryReader { proxy in
            ZStack(alignment: .leading) {
                Color.black.opacity(0.35).ignoresSafeArea().onTapGesture { withAnimation(.easeIn(duration: 0.16)) { drawerOpen = false } }
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        HStack(spacing: 12) {
                            Image("AppIconPreview").resizable().scaledToFit().frame(width: 52, height: 52).clipShape(RoundedRectangle(cornerRadius: 12))
                            VStack(alignment: .leading, spacing: 2) { Text("QCMS").font(.title2.bold()); Text("Four Star Industries").font(.caption).foregroundStyle(.secondary) }
                            Spacer()
                            Button { withAnimation(.easeIn(duration: 0.14)) { drawerOpen = false } } label: { Image(systemName: "xmark").frame(width: 38, height: 38) }
                        }.padding(18)
                        Divider()
                        drawerSection("square.grid.2x2", "Dashboard", "dashboard", [])
                        drawerSection("square.grid.3x3", "Masters", "masters", [("Masters Home","masters"),("Company Branch","company-branch-entry"),("Part Entry","part-entry"),("Process Entry","process-entry"),("Material Grade","grade-entry"),("Reference Entry","reference-entry"),("Employee Entry","employee-entry"),("Standards Bank","standards-entry"),("Master Import","master-import")])
                        drawerSection("truck.box", "Supply Chain", "supply-chain-home", [("Supply Chain Home","supply-chain-home"),("Customer Orders","supply-customer-orders"),("Opening Stock & Import","supply-opening-stock"),("RM Procurement","supply-rm-procurement"),("Purchase Orders","supply-purchase-orders"),("PO Order List","supply-po-order-list"),("Edit Purchase Order","supply-po-edit"),("Purchase Order PDF","supply-po-pdf"),("Approval / Confirmation","supply-po-approval"),("RM Receipt","supply-rm-receipt"),("RM to Forging","supply-rm-dispatch"),("Forging","supply-forging"),("Machining / FG / Dispatch","supply-downstream"),("Traceability","supply-traceability"),("Monthly Schedule / MIS","supply-order-mis")])
                        drawerSection("checklist", "RMTC", "rmtc-entry", [("RMTC Entry","rmtc-entry"),("Add Part Worksheet","rmtc-approved-worksheet"),("Part Worksheet","rmtc-part"),("Validation & Decision","rmtc-approval"),("RMTC Reports","rmtc-report")])
                        drawerSection("arrow.right.square", "Inward", "inward-entry", [("Material Inward","inward-entry"),("MetLAB Report","metlab-entry"),("Dimensional Report","dimensional-entry"),("Inward Reports","inward-report")])
                        drawerSection("building.2", "OSP", "osp-home", [("OSP Home","osp-home"),("Material Out","osp-material-out"),("Sample Receipt","osp-sample-receipt"),("OSP Dimensional","osp-dimensional"),("OSP MetLAB","osp-metlab"),("OSP Inward","osp-inward"),("OSP Reports","osp-balance-report")])
                        drawerSection("checkmark.shield", "Quality / Inspections", "inspection-home", [("Inspection Home","inspection-home"),("Layout Entry","inspection-layout-entry"),("Dimensional Entry","dimensional-entry"),("MetLAB Entry","metlab-entry"),("Bend Test Entry","bend-test-entry"),("Dimensional Reports","dimensional-report"),("MetLAB Reports","metlab-report"),("Bend Test Reports","bend-test-report")])
                        drawerSection("chart.xyaxis.line", "NPD / APQP", "npd-status", [("Process Flow Designer","npd-process-flow"),("NPD Status","npd-status"),("APQP","apqp"),("NPD Reports","npd-report"),("APQP Reports","apqp-report")])
                        drawerSection("exclamationmark.bubble", "Complaints", "complaints-home", [("Complaint Dashboard","complaints-home"),("Customer Complaint","customer-complaint"),("Supplier Complaint","supplier-complaint"),("Customer Register","customer-complaint-register"),("Supplier Register","supplier-complaint-register"),("Analysis & CAPA","complaint-analysis"),("Email / Reminders","complaint-email-settings"),("Complaint Reports","complaints-report")])
                        drawerSection("magnifyingglass", "Search", "global-search", [])
                        drawerSection("tray.full", "Records", "records-center", [("Records Centre","records-center"),("RMTC","rmtc-records"),("Material Inward","inward-records"),("OSP","osp-records"),("Dimensional","dimensional-records"),("MetLAB","metlab-records"),("Bend Test","bend-test-records"),("Complaints","complaint-records"),("Heat Ledger","heat-ledger")])
                        drawerSection("chart.bar", "Reports", "reports-home", [("Reports Home","reports-home"),("Supply Chain MIS","supply-chain-report"),("Heat Global Balance","heat-transaction-report"),("OSP Heat Balance","osp-balance-report"),("RMTC","rmtc-report"),("Material Inward","inward-report"),("Dimensional","dimensional-report"),("MetLAB","metlab-report"),("Complaints","complaints-report"),("Traceability","traceability-report")])
                        drawerSection("arrow.down.doc", "Templates", "templates", [])
                        drawerSection("gearshape", "Admin", "user-access", [("Users & Access","user-access"),("Email Server & Notifications","email-settings"),("Deployment Diagnostics","deployment-diagnostics")])
                    }
                }
                .frame(width: min(proxy.size.width * 0.86, 430)).background(Color(.systemBackground)).shadow(radius: 12)
            }
        }
        .transition(.opacity)
    }

    @ViewBuilder
    private func drawerSection(_ icon: String, _ title: String, _ landingPath: String, _ children: [(String, String)]) -> some View {
        if children.isEmpty {
            Button { navigate(landingPath) } label: {
                HStack(spacing: 14) { Image(systemName: icon).frame(width: 26); Text(title).font(.body); Spacer(); Image(systemName: "chevron.right").font(.caption).foregroundStyle(.secondary) }
                    .padding(.horizontal, 20).frame(height: 52).contentShape(Rectangle())
            }.buttonStyle(.plain)
        } else {
            VStack(spacing: 0) {
                Button {
                    withAnimation(.easeInOut(duration: 0.16)) {
                        if expandedSections.contains(title) { expandedSections.remove(title) } else { expandedSections.insert(title) }
                    }
                } label: {
                    HStack(spacing: 14) {
                        Image(systemName: icon).frame(width: 26); Text(title).font(.body); Spacer()
                        Image(systemName: expandedSections.contains(title) ? "chevron.up" : "chevron.down").font(.caption).foregroundStyle(.secondary)
                    }.padding(.horizontal, 20).frame(height: 52).contentShape(Rectangle())
                }.buttonStyle(.plain)
                if expandedSections.contains(title) {
                    VStack(spacing: 0) {
                        ForEach(Array(children.enumerated()), id: \.offset) { _, child in
                            Button { navigate(child.1) } label: {
                                HStack { Text(child.0).font(.subheadline); Spacer(); Image(systemName: "chevron.right").font(.caption2).foregroundStyle(.tertiary) }
                                    .padding(.leading, 58).padding(.trailing, 18).frame(height: 44).contentShape(Rectangle())
                            }.buttonStyle(.plain)
                        }
                    }.background(Color(.secondarySystemBackground))
                }
            }
        }
    }

    private func navigate(_ path: String) {
        withAnimation(.easeIn(duration: 0.14)) { drawerOpen = false }
        NotificationCenter.default.post(name: .qcmsNavigate, object: path)
    }

    private var setupView: some View {
        VStack(alignment: .leading, spacing: 18) {
            Spacer()
            Image("AppIconPreview").resizable().scaledToFit().frame(width: 92, height: 92).clipShape(RoundedRectangle(cornerRadius: 20))
            Text("QCMS Mobile").font(.largeTitle.bold())
            Text("Four Star Industries - secure iPhone / iPad access to the live QCMS application.").foregroundStyle(.secondary)
            TextField("https://your-qcms.streamlit.app", text: $draftURL).textInputAutocapitalization(.never).keyboardType(.URL).autocorrectionDisabled().textFieldStyle(.roundedBorder)
            Button("Save & Open QCMS") {
                let value = draftURL.trimmingCharacters(in: .whitespacesAndNewlines)
                if value.lowercased().hasPrefix("https://"), URL(string: value)?.host != nil { qcmsURL = value.hasSuffix("/") ? String(value.dropLast()) : value }
            }.buttonStyle(.borderedProminent).tint(accent)
            Spacer()
        }.padding(28).onAppear { draftURL = qcmsURL }
    }
}

extension Notification.Name {
    static let qcmsReload = Notification.Name("qcmsReload")
    static let qcmsNavigate = Notification.Name("qcmsNavigate")
}
