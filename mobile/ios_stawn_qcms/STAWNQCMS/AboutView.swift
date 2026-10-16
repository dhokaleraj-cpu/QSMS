import SwiftUI
import WebKit

/// About text (same wording as the website's About page, core/about.py, and the Android app).
enum GenAbout {
    static let product = "STAWN QCMS"
    static let tagline = "Quality Control Monitoring System"
    static let company = "STAWN PRECISION PRIVATE LIMITED"
    static let email = "business@stawnprecision.com"
    static let copyright = "© 2026 \(company). All rights reserved."
    static let developer: [(String, String)] = [("Developed by", company), ("Location", "Thane, Maharashtra, India"), ("Product", "\(product) – \(tagline)"),
                                                ("Platforms", "iPhone · iPad · Android app · Web application"), ("Contact", email)]
    static let licensee: [(String, String)] = [("Licensed user", "Four Star Industries Pvt. Ltd."), ("Use", "Internal quality, supply chain and traceability records")]
    static let notice = [
        "STAWN QCMS, the STAWN name and logo, the software, its source code, screen designs, report and print layouts, database design and documentation are the intellectual property of \(company) and are protected by the Copyright Act, 1957 (India) and international copyright laws.",
        "The software is licensed, not sold. Copying, modifying, reverse engineering, redistributing, sub-licensing or reselling the software or any part of it without the prior written permission of \(company) is prohibited.",
        "All business data entered in QCMS (parts, orders, inspection results, reports and documents) belongs to the licensed user.",
        "Other product and company names shown in the records belong to their respective owners."]
    static let security = [
        "Data is stored in the licensed user's own Supabase database with row-level security for every company (tenant).",
        "Passwords are never stored on the device; the session key is kept in the iOS Keychain and the app locks after 15 minutes in the background.",
        "Personal e-mail credentials are visible only to their own user – not to other users or administrators.",
        "Every create, change and deletion is recorded in the record history and user activity log."]
    static let support = "For licences, new features, training or support contact \(company) at \(email)."
}

struct AboutView: View {
    var body: some View {
        List {
            Section {
                VStack(spacing: 8) {
                    LogoView(size: 84)
                    Text(GenAbout.product).font(.title.bold())
                    Text(GenAbout.tagline).font(.subheadline).foregroundColor(Theme.muted)
                    Text("iOS / iPadOS app v\(AppConfig.appVersion) · Website v\(AppConfig.webVersion)").font(.footnote.weight(.semibold)).foregroundColor(Theme.tealDark)
                }
                .frame(maxWidth: .infinity).padding(.vertical, 8)
            }
            Section("Developer") { ForEach(GenAbout.developer.indices, id: \.self) { i in PairRow(label: GenAbout.developer[i].0, value: GenAbout.developer[i].1) } }
            Section("Licensed to") { ForEach(GenAbout.licensee.indices, id: \.self) { i in PairRow(label: GenAbout.licensee[i].0, value: GenAbout.licensee[i].1) } }
            Section("Copyright") {
                Text(GenAbout.copyright).font(.subheadline.bold())
                ForEach(GenAbout.notice, id: \.self) { Text($0).font(.footnote).foregroundColor(Theme.muted) }
            }
            Section("Data & security") { ForEach(GenAbout.security, id: \.self) { Text("• " + $0).font(.footnote) } }
            Section("Support") {
                Text(GenAbout.support).font(.footnote)
                if let url = URL(string: "mailto:\(GenAbout.email)?subject=STAWN%20QCMS%20support") { Link("✉ Email STAWN support", destination: url) }
            }
        }
        .navigationTitle("About STAWN QCMS")
        .qcmsNavBar()
    }
}

struct AccountView: View {
    @EnvironmentObject var app: AppState
    @State private var current = ""
    @State private var new1 = ""
    @State private var new2 = ""
    @State private var message: String?
    @State private var busy = false
    @State private var keep = Api.shared.keepSignedIn

    var body: some View {
        Form {
            Section("Signed in") {
                PairRow(label: "Name", value: Api.shared.fullName)
                PairRow(label: "Email", value: Api.shared.email)
                PairRow(label: "Role", value: Fmt.pretty(Api.shared.role))
                if !Api.shared.employeeLabel.isEmpty { PairRow(label: "Employee", value: Api.shared.employeeLabel) }
            }
            Section("Security") {
                Toggle("Face ID / Touch ID unlock", isOn: $app.faceID).disabled(!app.biometricAvailable)
                Toggle("Keep me signed in on this device", isOn: $keep).onChange(of: keep) { v in Api.shared.keepSignedIn = v }
                Text("The app locks after 15 minutes in the background. Your password is never stored; the session key is kept in the iOS Keychain.")
                    .font(.caption).foregroundColor(Theme.muted)
            }
            Section("Change login password") {
                SecureField("Current password", text: $current)
                SecureField("New password (min. 10 characters)", text: $new1)
                SecureField("Confirm new password", text: $new2)
                if let m = message { Text(m).font(.footnote).foregroundColor(m.hasPrefix("Password changed") ? Theme.green : Theme.red) }
                Button(busy ? "Changing…" : "Change my login password") { change() }.disabled(busy)
            }
            Section { Button("Sign out", role: .destructive) { app.signOut() } }
            Section { Text(GenAbout.copyright).font(.caption).foregroundColor(Theme.muted) }
        }
        .navigationTitle("My Account")
        .qcmsNavBar()
    }

    private func change() {
        guard new1.count >= 10 else { message = "Use a new password with at least 10 characters."; return }
        guard new1 == new2 else { message = "New Password and Confirm New Password do not match."; return }
        busy = true
        Task {
            do {
                try await Api.shared.verifyPassword(current)
                try await Api.shared.changePassword(new1)
                message = "Password changed. Use the new password next time you sign in."
                current = ""; new1 = ""; new2 = ""
            } catch { message = error.localizedDescription }
            busy = false
        }
    }
}

/// Website page inside the app (for entry screens that are not native on iPhone / iPad yet).
struct WebPageView: View {
    let title: String
    let path: String
    @State private var loading = true

    var body: some View {
        ZStack(alignment: .top) {
            WebView(url: URL(string: AppConfig.webURL + (path.isEmpty ? "" : "/" + path)) ?? URL(string: AppConfig.webURL)!, loading: $loading)
            if loading { ProgressView("Opening the QCMS website…").padding().background(.thinMaterial).clipShape(RoundedRectangle(cornerRadius: 12)).padding(.top, 40) }
        }
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
        .qcmsNavBar()
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Link(destination: URL(string: AppConfig.webURL + "/" + path) ?? URL(string: AppConfig.webURL)!) { Image(systemName: "safari") }
            }
        }
    }
}

struct WebView: UIViewRepresentable {
    let url: URL
    @Binding var loading: Bool

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        let v = WKWebView(frame: .zero, configuration: config)
        v.navigationDelegate = context.coordinator
        v.allowsBackForwardNavigationGestures = true
        v.load(URLRequest(url: url))
        return v
    }

    func updateUIView(_ v: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate {
        let parent: WebView
        init(_ p: WebView) { parent = p }
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { parent.loading = false }
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { parent.loading = false }
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { parent.loading = false }
    }
}
