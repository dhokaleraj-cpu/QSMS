import SwiftUI
import UIKit

/// qcms_licence_status() answer.
struct LicenceInfo {
    let raw: Row

    init(_ raw: Row) { self.raw = raw }

    var product: String { J.str(raw["product"]) }
    var companyName: String { J.str(raw["company_name"]) }
    var companyLegalName: String { J.str(raw["company_legal_name"]) }
    var logoPath: String { J.str(raw["company_logo_path"]) }
    var keyMasked: String { J.str(raw["licence_key_masked"]) }
    var plan: String { J.str(raw["plan"]) }
    var status: String { J.str(raw["status"]).uppercased() }
    var reason: String { J.str(raw["reason"]) }
    var expiresOn: String { J.str(raw["expires_on"]) }
    var maxUsers: String { J.str(raw["max_users"]) }
    var usedUsers: String { J.str(raw["used_users"]) }
    var valid: Bool { J.truthy(raw["valid"]) }
    var isStawnDeveloper: Bool { J.truthy(raw["is_stawn_developer"]) }
    var isCompanyAdmin: Bool { J.truthy(raw["is_company_admin"]) }
    var developer: Row { J.obj(raw["developer"]) }

    /// Name shown under "STAWN QCMS" on Home / Dashboard.
    var displayName: String { companyName.isEmpty ? companyLegalName : companyName }

    var usersText: String {
        if usedUsers.isEmpty && maxUsers.isEmpty { return "" }
        if maxUsers.isEmpty { return usedUsers }
        return "\(usedUsers.isEmpty ? "0" : usedUsers) of \(maxUsers)"
    }

    /// Block only on an explicit "valid = false" answer for a user who is not a STAWN developer.
    var blocks: Bool {
        if J.isNull(raw["valid"]) || status.isEmpty { return false }
        return !valid && !isStawnDeveloper
    }
}

/// Small company logo + name (licensed company) for the Home / Dashboard header.
struct CompanyLine: View {
    let licence: LicenceInfo?
    @State private var logo: UIImage?

    var body: some View {
        if let l = licence, !l.displayName.isEmpty {
            HStack(spacing: 6) {
                if let img = logo {
                    Image(uiImage: img).resizable().scaledToFit().frame(width: 18, height: 18).clipShape(RoundedRectangle(cornerRadius: 4))
                } else {
                    Image(systemName: "building.2").font(.caption).foregroundColor(Theme.tealDark)
                }
                Text(l.displayName).font(.caption.weight(.semibold)).foregroundColor(Theme.tealDark).lineLimit(1)
            }
            .task(id: l.logoPath) { await loadLogo(l.logoPath) }
        }
    }

    @MainActor private func loadLogo(_ path: String) async {
        guard !path.isEmpty, logo == nil else { return }
        if let data = try? await Api.shared.download(path), let img = UIImage(data: data) { logo = img }
    }
}

/// Full-screen STAWN screen shown when the company licence is not valid.
struct LicenceBlockedView: View {
    @EnvironmentObject var app: AppState
    @State private var key = ""
    @State private var busy = false
    @State private var message: String?
    @State private var showAbout = false

    private var licence: LicenceInfo? { app.licence }
    private var canActivate: Bool { (licence?.isCompanyAdmin ?? false) || Api.shared.isAdmin }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                Spacer(minLength: 30)
                LogoView(size: 96)
                VStack(spacing: 4) {
                    Text("STAWN QCMS").font(.largeTitle.bold()).foregroundColor(Theme.text)
                    Text(GenAbout.tagline).font(.subheadline).foregroundColor(Theme.muted)
                }
                Card {
                    HStack {
                        Image(systemName: "lock.shield").foregroundColor(Theme.red)
                        Text("Licence not active").font(.headline).foregroundColor(Theme.red)
                        Spacer()
                        if let s = licence?.status, !s.isEmpty { StatusChip(text: s) }
                    }
                    Text(reasonText).font(.footnote).foregroundColor(Theme.text)
                    if let l = licence {
                        if !l.displayName.isEmpty { PairRow(label: "Company", value: l.displayName) }
                        if !l.plan.isEmpty { PairRow(label: "Plan", value: Fmt.pretty(l.plan)) }
                        if !l.expiresOn.isEmpty { PairRow(label: "Valid until", value: Fmt.date(l.expiresOn)) }
                        if !l.keyMasked.isEmpty { PairRow(label: "Licence key", value: l.keyMasked) }
                    }
                }
                Card {
                    Text("Renew or activate your licence").font(.subheadline.weight(.semibold))
                    Text("Contact \(GenAbout.company) at \(GenAbout.email) to renew, upgrade or activate STAWN QCMS for your company.")
                        .font(.footnote).foregroundColor(Theme.muted)
                    if let url = URL(string: "mailto:\(GenAbout.email)?subject=STAWN%20QCMS%20licence") {
                        Link(destination: url) { Label(GenAbout.email, systemImage: "envelope") }.font(.footnote.weight(.semibold))
                    }
                }
                if canActivate {
                    Card {
                        Text("Activate licence key (company administrator)").font(.subheadline.weight(.semibold))
                        TextField("Licence key", text: $key)
                            .textInputAutocapitalization(.characters).autocorrectionDisabled()
                            .padding(10).background(Theme.bg).clipShape(RoundedRectangle(cornerRadius: 10))
                        Button(action: activate) {
                            HStack { Spacer(); if busy { ProgressView().tint(.white) } else { Text("Activate").bold() }; Spacer() }
                                .padding(.vertical, 10)
                        }
                        .background(Theme.teal).foregroundColor(.white).clipShape(RoundedRectangle(cornerRadius: 10))
                        .disabled(busy || key.trimmingCharacters(in: .whitespaces).isEmpty)
                    }
                }
                if let m = message { Text(m).font(.footnote).foregroundColor(Theme.red).multilineTextAlignment(.center) }
                HStack(spacing: 12) {
                    Button { Task { await app.checkLicence() } } label: { Label("Check again", systemImage: "arrow.clockwise") }
                        .buttonStyle(.bordered)
                    Button { showAbout = true } label: { Label("About", systemImage: "info.circle") }
                        .buttonStyle(.bordered)
                    Button(role: .destructive) { app.signOut() } label: { Label("Sign out", systemImage: "rectangle.portrait.and.arrow.right") }
                        .buttonStyle(.bordered)
                }
                Text(GenAbout.copyright).font(.caption2).foregroundColor(Theme.muted)
            }
            .padding()
            .frame(maxWidth: 520)
            .frame(maxWidth: .infinity)
        }
        .background(Theme.bg.ignoresSafeArea())
        .sheet(isPresented: $showAbout) {
            NavigationStack {
                AboutView()
                    .toolbar {
                        ToolbarItem(placement: .confirmationAction) { Button("Done") { showAbout = false } }
                    }
            }
            .environmentObject(app)
        }
    }

    private var reasonText: String {
        if let r = licence?.reason, !r.isEmpty { return r }
        return "The STAWN QCMS licence for your company is not active, so the app cannot be used right now."
    }

    private func activate() {
        let k = key.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !k.isEmpty, !busy else { return }
        busy = true
        message = nil
        Task { @MainActor in
            do {
                let raw = try await Api.shared.rpc("qcms_activate_licence", ["p_key": k])
                let res = J.obj(raw)
                await app.checkLicence()
                if app.licenceBlocked {
                    let m = J.str(J.or(res["message"], res["reason"], res["error"]))
                    message = m.isEmpty ? "The licence key was not accepted." : m
                } else {
                    key = ""
                }
            } catch {
                message = error.localizedDescription
            }
            busy = false
        }
    }
}
