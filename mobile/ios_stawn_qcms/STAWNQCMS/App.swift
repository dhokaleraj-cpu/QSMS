import SwiftUI
import LocalAuthentication

@main
struct STAWNQCMSApp: App {
    @StateObject private var app = AppState()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(app)
                .tint(Theme.teal)
                .onChange(of: scenePhase) { phase in app.scene(phase) }
        }
    }
}

@MainActor
final class AppState: ObservableObject {
    enum Phase { case starting, login, locked, ready }
    @Published var phase: Phase = .starting
    @Published var message: String?
    @Published var faceID: Bool = UserDefaults.standard.object(forKey: "face_id") as? Bool ?? false {
        didSet { UserDefaults.standard.set(faceID, forKey: "face_id") }
    }
    private var backgroundAt: Date?
    static let lockAfter: TimeInterval = 15 * 60

    var biometricAvailable: Bool {
        var err: NSError?
        return LAContext().canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &err)
    }

    func start() async {
        if await Api.shared.restore() {
            phase = faceID ? .locked : .ready
            if faceID { unlock() }
        } else {
            phase = .login
        }
    }

    func signIn(email: String, password: String) async {
        message = nil
        do {
            try await Api.shared.signIn(email: email, password: password)
            phase = .ready
        } catch {
            message = error.localizedDescription
        }
    }

    func signOut() {
        Task {
            await Api.shared.signOut()
            await LabelCache.shared.clear()
            phase = .login
        }
    }

    func scene(_ p: ScenePhase) {
        switch p {
        case .background: backgroundAt = Date()
        case .active:
            if phase == .ready, let at = backgroundAt, Date().timeIntervalSince(at) > AppState.lockAfter {
                phase = faceID ? .locked : .login
                message = faceID ? nil : "Locked after 15 minutes in the background. Please sign in."
                if faceID { unlock() }
            }
            backgroundAt = nil
        default: break
        }
    }

    func unlock() {
        let ctx = LAContext()
        ctx.localizedFallbackTitle = "Use passcode"
        ctx.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: "Unlock STAWN QCMS") { ok, _ in
            Task { @MainActor in if ok { self.phase = .ready } }
        }
    }
}

struct RootView: View {
    @EnvironmentObject var app: AppState
    var body: some View {
        Group {
            switch app.phase {
            case .starting: SplashView().task { await app.start() }
            case .login: LoginView()
            case .locked: LockView()
            case .ready: MainView()
            }
        }
        .animation(.easeInOut(duration: 0.2), value: app.phase)
    }
}

struct LogoView: View {
    var size: CGFloat = 84
    var body: some View {
        Image("STAWNLogo").resizable().scaledToFit().frame(width: size, height: size)
            .clipShape(RoundedRectangle(cornerRadius: size * 0.22))
    }
}

struct SplashView: View {
    var body: some View {
        VStack(spacing: 16) {
            LogoView()
            Text("STAWN QCMS").font(.title2.bold()).foregroundColor(Theme.text)
            ProgressView("Opening STAWN QCMS…")
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity).background(Theme.bg)
    }
}

struct LoginView: View {
    @EnvironmentObject var app: AppState
    @State private var email = Api.shared.email
    @State private var password = ""
    @State private var busy = false
    @State private var keep = Api.shared.keepSignedIn

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                Spacer(minLength: 40)
                LogoView(size: 96)
                VStack(spacing: 4) {
                    Text("STAWN QCMS").font(.largeTitle.bold()).foregroundColor(Theme.text)
                    Text("Quality Control Monitoring System").font(.subheadline).foregroundColor(Theme.muted)
                }
                Card {
                    Text("Sign in").font(.headline)
                    TextField("Email", text: $email)
                        .textContentType(.username).keyboardType(.emailAddress).textInputAutocapitalization(.never).autocorrectionDisabled()
                        .padding(12).background(Theme.bg).clipShape(RoundedRectangle(cornerRadius: 10))
                    SecureField("Password", text: $password)
                        .textContentType(.password)
                        .padding(12).background(Theme.bg).clipShape(RoundedRectangle(cornerRadius: 10))
                        .onSubmit { submit() }
                    Toggle("Keep me signed in on this device", isOn: $keep).font(.footnote)
                        .onChange(of: keep) { v in Api.shared.keepSignedIn = v }
                    if let m = app.message { Text(m).font(.footnote).foregroundColor(Theme.red) }
                    Button(action: submit) {
                        HStack { Spacer(); if busy { ProgressView().tint(.white) } else { Text("Sign in").bold() }; Spacer() }
                            .padding(.vertical, 12)
                    }
                    .background(Theme.teal).foregroundColor(.white).clipShape(RoundedRectangle(cornerRadius: 12))
                    .disabled(busy || email.isEmpty || password.isEmpty)
                }
                .frame(maxWidth: 460)
                Text("Same login as the QCMS website. Your password is never stored on this device.")
                    .font(.caption).foregroundColor(Theme.muted).multilineTextAlignment(.center)
                Text(GenAbout.copyright).font(.caption2).foregroundColor(Theme.muted)
            }
            .padding()
            .frame(maxWidth: .infinity)
        }
        .background(Theme.bg.ignoresSafeArea())
    }

    private func submit() {
        guard !busy, !email.isEmpty, !password.isEmpty else { return }
        busy = true
        Task {
            await app.signIn(email: email, password: password)
            password = ""
            busy = false
        }
    }
}

struct LockView: View {
    @EnvironmentObject var app: AppState
    var body: some View {
        VStack(spacing: 18) {
            LogoView()
            Text("STAWN QCMS is locked").font(.title3.bold())
            Button { app.unlock() } label: { Label("Unlock with Face ID / Touch ID", systemImage: "faceid") }
                .buttonStyle(.borderedProminent)
            Button("Sign in with password") { app.phase = .login }.font(.footnote)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity).background(Theme.bg)
    }
}
