import SwiftUI
import PDFKit
import MessageUI
import UIKit

/// PDF viewer with Save to Files, Print (AirPrint), Email and Share - for every report, record and register.
struct PdfViewer: View {
    let item: PdfItem
    @Environment(\.dismiss) private var dismiss
    @State private var showShare = false
    @State private var showMail = false
    @State private var showSave = false
    @State private var note: String?

    private var fileURL: URL {
        let name = Files.safeName("\(item.fileName)_\(Files.stamp()).pdf")
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(name)
        if !FileManager.default.fileExists(atPath: url.path) { try? item.data.write(to: url) }
        return url
    }

    var body: some View {
        NavigationStack {
            PDFKitView(data: item.data)
                .ignoresSafeArea(edges: .bottom)
                .navigationTitle(item.title)
                .navigationBarTitleDisplayMode(.inline)
                .qcmsNavBar()
                .toolbar {
                    ToolbarItem(placement: .navigationBarLeading) { Button("Close") { dismiss() } }
                    ToolbarItemGroup(placement: .bottomBar) {
                        Button { showSave = true } label: { Label("Save", systemImage: "square.and.arrow.down") }
                        Spacer()
                        Button { printPdf() } label: { Label("Print", systemImage: "printer") }
                        Spacer()
                        Button { email() } label: { Label("Email", systemImage: "envelope") }
                        Spacer()
                        Button { showShare = true } label: { Label("Share", systemImage: "square.and.arrow.up") }
                    }
                }
                .sheet(isPresented: $showShare) { ShareSheet(items: [fileURL]) }
                .sheet(isPresented: $showSave) { SaveToFiles(url: fileURL) }
                .sheet(isPresented: $showMail) {
                    MailView(subject: "QCMS · \(item.title)", message: "Dear Sir / Madam,\n\nPlease find attached \(item.title) from STAWN QCMS.\n\nRegards,\n\(Api.shared.fullName)",
                             attachment: item.data, fileName: fileURL.lastPathComponent)
                }
                .alert(note ?? "", isPresented: Binding(get: { note != nil }, set: { if !$0 { note = nil } })) { Button("OK") { note = nil } }
        }
    }

    private func printPdf() {
        let pc = UIPrintInteractionController.shared
        let info = UIPrintInfo(dictionary: nil)
        info.outputType = .general
        info.jobName = "QCMS \(item.title)"
        pc.printInfo = info
        pc.printingItem = item.data
        pc.present(animated: true, completionHandler: nil)
    }

    private func email() {
        if MFMailComposeViewController.canSendMail() { showMail = true } else { showShare = true }
    }
}

struct PDFKitView: UIViewRepresentable {
    let data: Data
    func makeUIView(context: Context) -> PDFView {
        let v = PDFView()
        v.autoScales = true
        v.displayMode = .singlePageContinuous
        v.backgroundColor = UIColor(red: 0.93, green: 0.95, blue: 0.95, alpha: 1)
        v.document = PDFDocument(data: data)
        return v
    }
    func updateUIView(_ v: PDFView, context: Context) {}
}

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    func makeUIViewController(context: Context) -> UIActivityViewController { UIActivityViewController(activityItems: items, applicationActivities: nil) }
    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}

struct SaveToFiles: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> UIDocumentPickerViewController { UIDocumentPickerViewController(forExporting: [url], asCopy: true) }
    func updateUIViewController(_ vc: UIDocumentPickerViewController, context: Context) {}
}

struct MailView: UIViewControllerRepresentable {
    let subject: String
    let message: String
    var attachment: Data? = nil
    var fileName = "QCMS.pdf"
    var recipients: [String] = []
    @Environment(\.dismiss) private var dismiss

    func makeCoordinator() -> Coordinator { Coordinator(dismiss: { dismiss() }) }

    func makeUIViewController(context: Context) -> MFMailComposeViewController {
        let vc = MFMailComposeViewController()
        vc.mailComposeDelegate = context.coordinator
        vc.setSubject(subject)
        vc.setMessageBody(message, isHTML: false)
        if !recipients.isEmpty { vc.setToRecipients(recipients) }
        if let a = attachment { vc.addAttachmentData(a, mimeType: "application/pdf", fileName: fileName) }
        return vc
    }

    func updateUIViewController(_ vc: MFMailComposeViewController, context: Context) {}

    final class Coordinator: NSObject, MFMailComposeViewControllerDelegate {
        let dismiss: () -> Void
        init(dismiss: @escaping () -> Void) { self.dismiss = dismiss }
        func mailComposeController(_ controller: MFMailComposeViewController, didFinishWith result: MFMailComposeResult, error: Error?) { dismiss() }
    }
}

/// "Send Email" module: the phone's mail app with the signed-in user's own mailbox.
struct EmailComposeLauncher: View {
    @State private var show = false
    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "envelope.badge").font(.system(size: 44)).foregroundColor(Theme.teal)
            Text("Send an email from your own mailbox (Mail app). To attach a report, open the record and use Print layout PDF → Email.")
                .font(.footnote).foregroundColor(Theme.muted).multilineTextAlignment(.center)
            Button("Write email") { show = true }.buttonStyle(.borderedProminent).tint(Theme.teal)
                .disabled(!MFMailComposeViewController.canSendMail())
            if !MFMailComposeViewController.canSendMail() { Text("Set up an account in the iOS Mail app first.").font(.caption).foregroundColor(Theme.red) }
        }
        .padding(30)
        .navigationTitle("Send Email")
        .qcmsNavBar()
        .sheet(isPresented: $show) { MailView(subject: "QCMS", message: "") }
    }
}
