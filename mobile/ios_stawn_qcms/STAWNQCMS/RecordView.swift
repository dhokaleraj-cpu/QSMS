import SwiftUI
import PhotosUI
import UniformTypeIdentifiers

/// One record: print-layout PDF, full report (as printed), details, child tables, photos & documents, history, delete.
struct RecordView: View {
    let module: QModule
    let id: String
    @EnvironmentObject var nav: TabNav
    @State private var row: Row?
    @State private var keys: [String] = []
    @State private var fk: [String: [String: String]] = [:]
    @State private var error: String?
    @State private var report: RptDoc?
    @State private var reportError: String?
    @State private var children: [String: ([String], [[String]], [Row])] = [:]
    @State private var files: [Row] = []
    @State private var pdf: PdfItem?
    @State private var busy = false
    @State private var toast: String?
    @State private var confirmDelete = false
    @State private var deleteReason = ""
    @State private var askReason = false
    @State private var photoItem: PhotosPickerItem?
    @State private var pickSlot = ""
    @State private var showPhotoPicker = false
    @State private var showFilePicker = false
    @State private var attachTitle = ""
    @State private var askTitle = false
    @State private var pendingFile: (Data, String, String)?
    @State private var poRemarks = ""
    @State private var askCancel = false
    @State private var cancelReason = ""

    static let fullReport: Set<String> = ["lab_tests", "inspection_reports", "rmtc_approvals", "inward_lots", "qc_calculation_records", "quality_complaints"]
    static let transactionTables: Set<String> = ["supply_customer_orders", "supply_purchase_orders", "supply_po_confirmations", "supply_rm_purchase_orders", "supply_rm_receipts",
        "supply_rm_dispatches", "supply_forging_orders", "supply_forging_receipts", "supply_downstream_events", "supply_opening_stock", "osp_jobs", "osp_receipts", "rmtc_approvals",
        "inward_lots", "inspection_reports", "lab_tests", "npd_orders", "npd_process_flows", "ppap_projects", "pfd_headers", "pfmea_headers", "control_plan_headers", "spc_studies",
        "msa_studies", "capacity_studies", "qc_calculation_records", "quality_complaints", "quality_asset_part_process_links", "quality_asset_calibration_records",
        "standard_room_inspection_records"]
    static let hidden: Set<String> = ["id", "tenant_id", "created_by", "updated_by", "search_vector", "search_text"]

    private var title: String { row.map { module.recordTitle($0) } ?? module.title }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                if let e = error { ErrorBox(message: e) { Task { await load() } } }
                else if let r = row { content(r) }
                else { ProgressView("Loading…").frame(maxWidth: .infinity).padding(40) }
            }
            .padding(12)
        }
        .background(Theme.bg)
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
        .qcmsNavBar()
        .toolbar {
            ToolbarItemGroup(placement: .navigationBarTrailing) {
                Button { printLayout() } label: { Image(systemName: busy ? "hourglass" : "printer") }
                Button { nav.push(.search("")) } label: { Image(systemName: "magnifyingglass") }
            }
        }
        .sheet(item: $pdf) { PdfViewer(item: $0) }
        .photosPicker(isPresented: $showPhotoPicker, selection: $photoItem, matching: .images)
        .onChange(of: photoItem) { item in
            guard let item = item else { return }
            Task {
                if let data = try? await item.loadTransferable(type: Data.self) {
                    let jpeg = UIImage(data: data)?.jpegData(compressionQuality: 0.85) ?? data
                    gotFile(jpeg, "photo_\(Files.stamp()).jpg", "image/jpeg")
                }
                photoItem = nil
            }
        }
        .fileImporter(isPresented: $showFilePicker, allowedContentTypes: [.pdf, .image, .data]) { result in
            if case .success(let url) = result {
                let ok = url.startAccessingSecurityScopedResource()
                defer { if ok { url.stopAccessingSecurityScopedResource() } }
                if let data = try? Data(contentsOf: url) {
                    let mime = UTType(filenameExtension: url.pathExtension)?.preferredMIMEType ?? "application/octet-stream"
                    gotFile(data, url.lastPathComponent, mime)
                }
            }
        }
        .alert("Title of this file", isPresented: $askTitle) {
            TextField("e.g. Damaged thread close-up", text: $attachTitle)
            Button("Upload") { if let f = pendingFile { upload(f.0, f.1, f.2, attachTitle.isEmpty ? f.1 : attachTitle) } }
            Button("Cancel", role: .cancel) { pendingFile = nil }
        }
        .alert("Delete \(title)?", isPresented: $confirmDelete) {
            SecureField("Your password", text: $deleteReason)
            Button("Delete", role: .destructive) { deleteRecord(password: deleteReason) }
            Button("Cancel", role: .cancel) { deleteReason = "" }
        } message: { Text("Deletion is permanent. Confirm with your password.") }
        .alert("Approved record · deletion request", isPresented: $askReason) {
            TextField("Reason for deletion (sent to the Admin)", text: $deleteReason)
            Button("Send request") { requestDelete(deleteReason) }
            Button("Cancel", role: .cancel) { deleteReason = "" }
        }
        .alert("Cancel this Purchase Order?", isPresented: $askCancel) {
            TextField("Reason for cancellation", text: $cancelReason)
            Button("Cancel PO", role: .destructive) { cancelPo(cancelReason) }
            Button("Back", role: .cancel) { }
        } message: { Text("Its Customer Orders become free for a new PO.") }
        .overlay(alignment: .bottom) {
            if let t = toast {
                Text(t).font(.footnote).foregroundColor(.white).padding(12).background(Color.black.opacity(0.8)).clipShape(RoundedRectangle(cornerRadius: 12))
                    .padding(.bottom, 20).padding(.horizontal)
                    .onTapGesture { toast = nil }
            }
        }
        .task { if row == nil { await load() } }
        .refreshable { await load() }
    }

    // ------------------------------------------------------------------ content
    @ViewBuilder private func content(_ r: Row) -> some View {
        Card {
            HStack(alignment: .top) {
                Text(title).font(.title3.bold()).foregroundColor(Theme.text)
                Spacer()
                let st = module.statusField.isEmpty ? "" : J.str(r[module.statusField])
                if !st.isEmpty { StatusChip(text: st) }
            }
            Text(module.title).font(.caption).foregroundColor(Theme.muted)
        }

        Button { printLayout() } label: {
            Label(busy ? "Preparing PDF…" : "Print layout PDF · Preview · Save · Share · Email", systemImage: "printer.fill")
                .frame(maxWidth: .infinity).padding(.vertical, 12)
        }
        .buttonStyle(.borderedProminent).tint(Theme.teal)

        actions(r)

        if RecordView.fullReport.contains(module.table) {
            SectionLabel(text: "Full report (as printed)")
            if let doc = report { RptView(doc: doc) }
            else if let e = reportError { Text("Could not load the report: \(e)").font(.footnote).foregroundColor(Theme.red) }
            else { ProgressView("Loading every entry of this report…").frame(maxWidth: .infinity).padding(20) }
        }

        SectionLabel(text: "Details")
        Card {
            ForEach(keys, id: \.self) { k in
                let text = detailText(r, k)
                if !text.isEmpty { PairRow(label: Labels.header(k), value: text) }
            }
        }

        ForEach(module.children.indices, id: \.self) { i in
            let child = module.children[i]
            SectionLabel(text: child.title)
            if let c = children[child.table + child.fk] {
                if c.1.isEmpty { Text("No rows.").font(.footnote).foregroundColor(Theme.muted) }
                else {
                    SheetGrid(columns: c.0, rows: c.1, maxHeight: 320) { idx in
                        guard idx < c.2.count else { return }
                        let target = Catalog.shared.forTable(child.table)
                        if let t = target { nav.push(.record(t.key, J.str(c.2[idx]["id"]))) }
                    }
                    .frame(height: min(320, CGFloat(c.1.count) * 34 + 44))
                }
            } else { ProgressView() }
        }

        if !module.attachEntity.isEmpty {
            SectionLabel(text: "Photos & documents")
            Card {
                if files.isEmpty { Text("No photos or documents yet.").font(.footnote).foregroundColor(Theme.muted) }
                ForEach(files.indices, id: \.self) { i in
                    let f = files[i]
                    HStack {
                        VStack(alignment: .leading) {
                            let t = J.str(f["document_title"])
                            Text(t.isEmpty ? Fmt.pretty(J.str(f["document_type"])) : t).font(.subheadline.weight(.semibold))
                            Text("\(J.str(f["file_name"])) · \(Fmt.date(J.str(f["created_at"])))").font(.caption).foregroundColor(Theme.muted)
                        }
                        Spacer()
                        Button("Open") { openFile(f) }.font(.footnote.weight(.bold))
                    }
                    Divider()
                }
                if !module.attachSlots.isEmpty || module.attachMulti {
                    Menu {
                        ForEach(slots, id: \.self) { slot in
                            Button("\(Fmt.pretty(slot)) · photo") { pickSlot = slot; showPhotoPicker = true }
                            Button("\(Fmt.pretty(slot)) · file") { pickSlot = slot; showFilePicker = true }
                        }
                    } label: { Label("Add photo / document", systemImage: "paperclip").frame(maxWidth: .infinity).padding(.vertical, 8) }
                        .buttonStyle(.bordered)
                }
            }
        }

        Button { nav.push(.history(module.key, id)) } label: { Label("Record history (who changed what)", systemImage: "clock.arrow.circlepath").frame(maxWidth: .infinity) }
            .buttonStyle(.bordered).padding(.top, 8)
        if module.deletable && !module.idField.isEmpty && !module.table.hasPrefix("v_") {
            Button(role: .destructive) { startDelete(r) } label: { Label("Delete", systemImage: "trash").frame(maxWidth: .infinity) }
                .buttonStyle(.bordered)
        }
    }

    private var slots: [String] { module.attachSlots.isEmpty ? ["PHOTO"] : module.attachSlots }

    /// Workflow buttons: native for Purchase Order approval / cancel; other entry and workflow steps open the website page.
    @ViewBuilder private func actions(_ r: Row) -> some View {
        if module.table == "supply_purchase_orders" {
            let approval = J.str(r["approval_status"]).uppercased()
            let st = J.str(r["status"]).uppercased()
            if approval == "PENDING_APPROVAL" && st != "CANCELLED" {
                Card {
                    Text("Purchase Order approval").font(.headline)
                    TextField("Approval remarks (optional)", text: $poRemarks).textFieldStyle(.roundedBorder)
                    Button { approvePo() } label: { Label("Approve Purchase Order", systemImage: "checkmark.seal.fill").frame(maxWidth: .infinity).padding(.vertical, 6) }
                        .buttonStyle(.borderedProminent).tint(Theme.green)
                    Text("After approval use “Print layout PDF → Email” or the website to send the PO to the supplier.").font(.caption).foregroundColor(Theme.muted)
                }
            }
            if st != "CANCELLED" {
                Button(role: .destructive) { askCancel = true } label: { Label("Cancel Purchase Order", systemImage: "xmark.octagon").frame(maxWidth: .infinity) }.buttonStyle(.bordered)
            }
        }
        if module.editable && module.nativeForm {
            Button { nav.push(.form(module.key, id)) } label: { Label("Edit", systemImage: "pencil").frame(maxWidth: .infinity) }.buttonStyle(.bordered)
        } else if (module.hasEditor || !module.actions.isEmpty), let p = WebRoutes.path(for: module.key) {
            Button { nav.push(.web(module.title, p)) } label: {
                Label(module.actions.isEmpty ? "Edit on website" : "Edit / workflow steps on website", systemImage: "globe").frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
        }
    }

    private func detailText(_ r: Row, _ k: String) -> String {
        if RecordView.hidden.contains(k) || k.hasSuffix("_path") { return "" }
        let v = r[k]
        if let d = v as? [String: Any], d.count > 6 { return "" }
        if k.hasSuffix("_snapshot") && v is [String: Any] { return "" }
        return Labels.cell(k, v, fk[k])
    }

    // ------------------------------------------------------------------ data
    private func load() async {
        error = nil
        do {
            let idField = module.idField.isEmpty ? "id" : module.idField
            guard let r = try await Api.shared.rows("\(module.table)?select=*&\(idField)=eq.\(Api.enc(id))").first else {
                throw ApiError(status: 404, message: "Record not found or not visible for your role.")
            }
            let k = r.keys.sorted()
            fk = await Labels.resolve(module.table, rows: [r], columns: k)
            keys = k
            row = r
        } catch {
            self.error = error.localizedDescription
            return
        }
        if RecordView.fullReport.contains(module.table) {
            do { report = try await RptReports.forRecord(module, id) } catch { reportError = error.localizedDescription }
        }
        for child in module.children {
            let order = child.order.isEmpty ? "" : "&order=\(child.order)"
            let rows = await Api.shared.list("\(child.table)?select=*&\(child.fk)=eq.\(Api.enc(id))\(order)&limit=2000")
            let cfk = await Labels.resolve(child.table, rows: rows, columns: child.cols.map { $0[0] })
            children[child.table + child.fk] = (child.cols.map { $0[1] }, rows.map { r in child.cols.map { Labels.cell($0[0], r[$0[0]], cfk[$0[0]]) } }, rows)
        }
        if !module.attachEntity.isEmpty { files = (try? await Api.shared.attachments(entity: module.attachEntity, id: id)) ?? [] }
    }

    private func printLayout() {
        guard !busy else { return }
        busy = true
        Task {
            do {
                let doc = try await RptReports.forRecord(module, id)
                pdf = PdfItem(title: doc.title, fileName: doc.fileBase, data: RptPdf.render(doc))
            } catch {
                toast = "Could not create the PDF: \(error.localizedDescription)"
            }
            busy = false
        }
    }

    private func openFile(_ f: Row) {
        Task {
            do {
                let url = try await Api.shared.signedURL(J.str(f["object_path"]))
                await UIApplication.shared.open(url)
            } catch { toast = error.localizedDescription }
        }
    }

    private func gotFile(_ data: Data, _ name: String, _ mime: String) {
        if module.attachMulti { pendingFile = (data, name, mime); attachTitle = ""; askTitle = true }
        else { upload(data, name, mime, nil) }
    }

    private func upload(_ data: Data, _ name: String, _ mime: String, _ title: String?) {
        toast = "Uploading \(name) (\(data.count / 1024) KB)…"
        let slot = pickSlot.isEmpty ? slots[0] : pickSlot
        Task {
            do {
                try await Api.shared.uploadAttachment(entity: module.attachEntity, id: id, folder: module.attachFolder.isEmpty ? module.table : module.attachFolder,
                                                     docType: slot, data: data, fileName: name, mime: mime, title: title)
                toast = "Uploaded."
                files = (try? await Api.shared.attachments(entity: module.attachEntity, id: id)) ?? files
            } catch { toast = "Upload failed: \(error.localizedDescription)" }
            pendingFile = nil
        }
    }

    private func approved(_ r: Row) -> Bool {
        J.str(r["approval_status"]).uppercased() == "APPROVED" || ["APPROVED", "RELEASED", "FINAL", "CLOSED", "COMPLETED"].contains(J.str(r["status"]).uppercased())
            || J.str(r["confirmation_status"]).uppercased() == "CONFIRMED"
    }

    private func startDelete(_ r: Row) {
        deleteReason = ""
        if approved(r) && !Api.shared.isAdmin { askReason = true } else { confirmDelete = true }
    }

    private func requestDelete(_ reason: String) {
        Task {
            do {
                _ = try await Api.shared.rpc("qcms_request_delete", ["p_table_name": module.table, "p_record_id": id, "p_reason": reason, "p_label": title])
                toast = "Deletion request sent to the Admin."
            } catch { toast = error.localizedDescription }
            deleteReason = ""
        }
    }

    private func deleteRecord(password: String) {
        let r = row ?? [:]
        Task {
            do {
                try await Api.shared.verifyPassword(password)
                let api = Api.shared
                if approved(r) {
                    let req = J.obj(try await api.rpc("qcms_request_delete", ["p_table_name": module.table, "p_record_id": id, "p_reason": "Deleted by Admin from the QCMS iOS app", "p_label": title]))
                    let res = J.obj(try await api.rpc("qcms_decide_delete_request", ["p_request_id": J.str(req["id"]), "p_approve": true, "p_note": "Approved from the QCMS iOS app"]))
                    if J.str(res["status"]) == "FAILED" { throw ApiError(status: 409, message: J.str(res["error"])) }
                } else if module.table == "supply_purchase_orders" {
                    _ = try await api.rpc("qcms_delete_purchase_order", ["p_purchase_order_id": id])
                } else if module.table == "supply_customer_orders" {
                    _ = try await api.rpc("qcms_delete_customer_order", ["p_customer_order_id": id])
                } else if RecordView.transactionTables.contains(module.table) {
                    _ = try await api.rpc("qcms_delete_transaction_row", ["p_table_name": module.table, "p_record_id": id])
                } else {
                    _ = try await api.rpc("qsms_delete_master_row", ["p_table_name": module.table, "p_record_id": id])
                }
                deleteReason = ""
                nav.pop()
            } catch {
                toast = "Deletion blocked: \(error.localizedDescription)"
                deleteReason = ""
            }
        }
    }

    private func approvePo() {
        Task {
            do {
                var args: [String: Any] = ["p_purchase_order_id": id]
                args["p_remarks"] = poRemarks.isEmpty ? NSNull() as Any : poRemarks as Any
                _ = try await Api.shared.rpc("qcms_approve_purchase_order", args)
                _ = try? await Api.shared.rpc("qcms_ensure_po_confirmation", ["p_purchase_order_id": id])
                toast = "Purchase Order approved."
                await load()
            } catch { toast = error.localizedDescription }
        }
    }

    private func cancelPo(_ reason: String) {
        Task {
            do {
                _ = try await Api.shared.rpc("qcms_cancel_purchase_order", ["p_purchase_order_id": id, "p_reason": reason])
                toast = "PO cancelled. Its Customer Orders are free for a new PO."
                await load()
            } catch { toast = error.localizedDescription }
        }
    }
}

/// Audit trail of one record (qcms_record_history).
struct HistoryView: View {
    let module: QModule
    let id: String
    @State private var rows: [[String]] = []
    @State private var loading = true

    var body: some View {
        VStack(alignment: .leading) {
            if loading { ProgressView().frame(maxWidth: .infinity).padding(40) }
            else if rows.isEmpty { Text("No history recorded.").foregroundColor(Theme.muted).padding() }
            else { SheetGrid(columns: ["When", "Action", "By", "Changes"], rows: rows) }
        }
        .padding(10)
        .background(Theme.bg)
        .navigationTitle("History")
        .qcmsNavBar()
        .task { await load() }
    }

    private func load() async {
        var data: [Row] = []
        if let v = try? await Api.shared.rpc("qcms_record_history", ["p_table_name": module.table, "p_row_id": id]) { data = J.rows(v) }
        if data.isEmpty {
            data = await Api.shared.list("audit_log?select=changed_at,operation,changed_by,old_data,new_data&table_name=eq.\(module.table)&row_id=eq.\(id)&order=changed_at.desc&limit=200")
        }
        rows = data.map { r in
            let old = J.obj(r["old_data"]), new = J.obj(r["new_data"])
            var ch: [String] = []
            for k in new.keys.sorted() where k != "updated_at" && k != "search_vector" {
                let o = J.str(old[k]), n = J.str(new[k])
                if o != n { ch.append("\(Labels.header(k)): \(o.isEmpty ? "-" : o) → \(n.isEmpty ? "-" : n)") }
            }
            let at = J.str(r["changed_at"])
            var by = J.str(r["changed_by_name"])
            if by.isEmpty { by = J.str(r["changed_by"]) }
            return ["\(Fmt.date(at)) \(at.count > 16 ? String(Array(at)[11..<16]) : "")", Fmt.pretty(J.str(r["operation"])), by, ch.isEmpty ? "-" : ch.joined(separator: "; ")]
        }
        loading = false
    }
}
