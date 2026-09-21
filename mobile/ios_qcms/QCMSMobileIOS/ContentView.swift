import SwiftUI

struct ContentView: View {
    @AppStorage("qcmsURL") private var qcmsURL = ""
    @State private var draftURL = ""
    @State private var menuExpanded = false

    var body: some View {
        Group {
            if qcmsURL.isEmpty {
                setupView
            } else {
                VStack(spacing: 0) {
                    HStack(spacing: 8) {
                        Button {
                            menuExpanded.toggle()
                        } label: {
                            Image(systemName: "line.3.horizontal")
                                .font(.title3.bold())
                                .frame(width: 42, height: 42)
                        }
                        Text("QCMS")
                            .font(.headline.bold())
                        Spacer()
                        Button {
                            NotificationCenter.default.post(name: .qcmsReload, object: nil)
                        } label: {
                            Image(systemName: "arrow.clockwise")
                                .frame(width: 42, height: 42)
                        }
                        Menu {
                            Button("Open in Safari") {
                                if let url = URL(string: qcmsURL) { UIApplication.shared.open(url) }
                            }
                            Button("Change QCMS URL", role: .destructive) {
                                qcmsURL = ""
                                draftURL = ""
                            }
                        } label: {
                            Image(systemName: "ellipsis.circle")
                                .frame(width: 42, height: 42)
                        }
                    }
                    .padding(.horizontal, 8)
                    .frame(height: 54)
                    .foregroundStyle(.white)
                    .background(Color(red: 0.48, green: 0.09, blue: 0.20))

                    QCMSWebView(urlString: qcmsURL, menuExpanded: $menuExpanded)
                }
                .ignoresSafeArea(edges: .bottom)
            }
        }
    }

    private var setupView: some View {
        VStack(alignment: .leading, spacing: 18) {
            Spacer()
            Image("AppIconPreview")
                .resizable().scaledToFit().frame(width: 92, height: 92)
                .clipShape(RoundedRectangle(cornerRadius: 20))
            Text("QCMS Mobile")
                .font(.largeTitle.bold())
            Text("Four Star Industries - secure iPhone / iPad access to the live QCMS application.")
                .foregroundStyle(.secondary)
            TextField("https://your-qcms.streamlit.app", text: $draftURL)
                .textInputAutocapitalization(.never)
                .keyboardType(.URL)
                .autocorrectionDisabled()
                .textFieldStyle(.roundedBorder)
            Button("Save & Open QCMS") {
                let value = draftURL.trimmingCharacters(in: .whitespacesAndNewlines)
                if value.lowercased().hasPrefix("https://"), URL(string: value)?.host != nil {
                    qcmsURL = value.hasSuffix("/") ? String(value.dropLast()) : value
                }
            }
            .buttonStyle(.borderedProminent)
            .tint(Color(red: 0.48, green: 0.09, blue: 0.20))
            Spacer()
        }
        .padding(28)
        .onAppear { draftURL = qcmsURL }
    }
}

extension Notification.Name {
    static let qcmsReload = Notification.Name("qcmsReload")
}
