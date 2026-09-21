import SwiftUI

struct ContentView: View {
    @AppStorage("qcmsURL") private var qcmsURL = ""
    @State private var draftURL = ""
    @State private var drawerOpen = false

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
                        }.padding(18)
                        Divider()
                        drawerItem("square.grid.2x2", "Dashboard", "dashboard")
                        drawerItem("square.grid.3x3", "Masters", "masters")
                        drawerItem("truck.box", "Supply Chain", "supply-chain-home")
                        drawerItem("checklist", "RMTC", "rmtc-entry")
                        drawerItem("arrow.right.square", "Inward", "inward-entry")
                        drawerItem("building.2", "OSP", "osp-home")
                        drawerItem("checkmark.shield", "Quality / Inspections", "inspection-home")
                        drawerItem("exclamationmark.bubble", "Complaints", "complaints-home")
                        drawerItem("magnifyingglass", "Search", "global-search")
                        drawerItem("tray.full", "Records", "records-center")
                        drawerItem("chart.bar", "Reports", "reports-home")
                        drawerItem("gearshape", "Admin", "email-settings")
                    }
                }
                .frame(width: min(proxy.size.width * 0.84, 430)).background(Color(.systemBackground)).shadow(radius: 12)
            }
        }
        .transition(.opacity)
    }

    private func drawerItem(_ icon: String, _ title: String, _ path: String) -> some View {
        Button { navigate(path) } label: {
            HStack(spacing: 14) { Image(systemName: icon).frame(width: 26); Text(title).font(.body); Spacer(); Image(systemName: "chevron.right").font(.caption).foregroundStyle(.secondary) }
                .padding(.horizontal, 20).frame(height: 54).contentShape(Rectangle())
        }
        .buttonStyle(.plain)
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
