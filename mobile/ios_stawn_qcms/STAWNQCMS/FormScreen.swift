import SwiftUI

/// Native entry form for modules with a generic form (Android EditScreen): text, number, date, yes/no, list and lookup fields.
struct FormScreen: View {
    let module: QModule
    let id: String
    @EnvironmentObject var nav: TabNav
    @State private var values: [String: String] = [:]
    @State private var flags: [String: Bool] = [:]
    @State private var dates: [String: Date] = [:]
    @State private var lookups: [String: [LookupOption]] = [:]
    @State private var loaded = false
    @State private var saving = false
    @State private var message: String?

    private var isNew: Bool { id.isEmpty }

    var body: some View {
        Form {
            if !loaded { ProgressView() }
            else {
                ForEach(module.form) { f in field(f) }
                if let m = message { Section { Text(m).foregroundColor(Theme.red).font(.footnote) } }
                Section {
                    Button { save() } label: { HStack { Spacer(); Text(saving ? "Saving…" : (isNew ? "Save new record" : "Save changes")).bold(); Spacer() } }
                        .disabled(saving)
                }
            }
        }
        .navigationTitle(isNew ? "New · \(module.title)" : "Edit · \(module.title)")
        .navigationBarTitleDisplayMode(.inline)
        .qcmsNavBar()
        .task { if !loaded { await load() } }
    }

    @ViewBuilder private func field(_ f: QField) -> some View {
        let label = f.label + (f.required ? " *" : "")
        switch f.type {
        case "bool":
            Toggle(label, isOn: Binding(get: { flags[f.key] ?? false }, set: { flags[f.key] = $0 })).disabled(f.readOnly)
        case "date":
            VStack(alignment: .leading) {
                Toggle(label, isOn: Binding(get: { dates[f.key] != nil }, set: { dates[f.key] = $0 ? (dates[f.key] ?? Date()) : nil }))
                if dates[f.key] != nil {
                    DatePicker("", selection: Binding(get: { dates[f.key] ?? Date() }, set: { dates[f.key] = $0 }), displayedComponents: .date).labelsHidden()
                }
            }
        case "select":
            Picker(label, selection: Binding(get: { values[f.key] ?? "" }, set: { values[f.key] = $0 })) {
                Text("-").tag("")
                ForEach(f.options, id: \.self) { Text(f.optionLabel($0)).tag($0) }
            }
            .disabled(f.readOnly)
        case "lookup":
            Picker(label, selection: Binding(get: { values[f.key] ?? "" }, set: { values[f.key] = $0 })) {
                Text(f.hint.isEmpty ? "-" : f.hint).tag("")
                ForEach(lookups[f.key] ?? []) { Text($0.label).tag($0.id) }
            }
            .pickerStyle(.navigationLink)
            .disabled(f.readOnly)
        case "area":
            VStack(alignment: .leading) {
                Text(label).font(.caption).foregroundColor(Theme.muted)
                TextEditor(text: Binding(get: { values[f.key] ?? "" }, set: { values[f.key] = $0 })).frame(minHeight: 80).disabled(f.readOnly)
            }
        default:
            VStack(alignment: .leading, spacing: 2) {
                Text(label).font(.caption).foregroundColor(Theme.muted)
                TextField(f.hint, text: Binding(get: { values[f.key] ?? "" }, set: { values[f.key] = $0 }))
                    .keyboardType(f.type == "int" ? .numberPad : (f.type == "num" ? .decimalPad : .default))
                    .disabled(f.readOnly || f.type == "info")
            }
        }
    }

    private func load() async {
        var existing: Row = [:]
        if !isNew {
            existing = await Api.shared.list("\(module.table)?select=*&id=eq.\(Api.enc(id))&limit=1").first ?? [:]
        }
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        df.dateFormat = "yyyy-MM-dd"
        for f in module.form {
            let v: Any? = isNew ? f.def?.value : existing[f.key]
            switch f.type {
            case "bool": flags[f.key] = J.truthy(v)
            case "date":
                let s = J.str(v)
                if s == "TODAY" { dates[f.key] = Date() } else if s.count >= 10, let d = df.date(from: String(s.prefix(10))) { dates[f.key] = d }
            case "multi": values[f.key] = J.list(v).map { J.str($0) }.joined(separator: ", ")
            default: values[f.key] = J.str(v)
            }
            if f.type == "lookup", let l = f.lookup {
                let order = l.order.isEmpty ? "" : "&order=\(l.order)"
                let rows = await Api.shared.list("\(l.table)?select=\(l.select)\(l.filter)\(order)&limit=5000")
                var opts = rows.map { LookupOption(id: J.str($0["id"]), label: LookupLabel.of(l.label, $0)) }
                let current = values[f.key] ?? ""
                if !current.isEmpty && !opts.contains(where: { $0.id == current }) {
                    let fk = await LabelCache.shared.load(l.table, ids: [current])
                    opts.insert(LookupOption(id: current, label: fk[current] ?? current), at: 0)
                }
                lookups[f.key] = opts
            }
        }
        loaded = true
    }

    private func save() {
        message = nil
        var out: Row = [:]
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        df.dateFormat = "yyyy-MM-dd"
        for f in module.form where !f.readOnly && f.type != "info" {
            switch f.type {
            case "bool": out[f.key] = flags[f.key] ?? false
            case "date":
                if let d = dates[f.key] { out[f.key] = df.string(from: d) } else if f.required { message = "\(f.label) is required."; return } else { out[f.key] = NSNull() }
            case "int", "num":
                let t = (values[f.key] ?? "").trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ",", with: "")
                if t.isEmpty { if f.required { message = "\(f.label) is required."; return }; out[f.key] = NSNull(); continue }
                guard let n = Double(t) else { message = "\(f.label) must be a number."; return }
                if let lo = f.min, n < lo { message = "\(f.label) must be at least \(Fmt.num(lo))."; return }
                if let hi = f.max, n > hi { message = "\(f.label) must be at most \(Fmt.num(hi))."; return }
                if f.type == "int" { out[f.key] = Int(n) } else { out[f.key] = n }
            case "multi":
                out[f.key] = (values[f.key] ?? "").split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
            default:
                let t = (values[f.key] ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
                if t.isEmpty { if f.required { message = "\(f.label) is required."; return }; out[f.key] = NSNull() } else { out[f.key] = t }
            }
        }
        if module.key == "standard_room" { out["status"] = "ACTIVE" }   // website writes status ACTIVE on every save
        saving = true
        let payload = out   // a captured `var` cannot be mutated inside the @Sendable Task closure
        Task {
            var out = payload
            do {
                if !module.numberField.isEmpty, !module.numberRpc.isEmpty, isNew, J.str(out[module.numberField]).isEmpty {
                    let args = (try? JSONSerialization.jsonObject(with: Data(module.numberArgs.utf8))) as? Row ?? [:]
                    out[module.numberField] = J.str(try await Api.shared.rpc(module.numberRpc, args))
                }
                let saved: Row
                if isNew { saved = try await Api.shared.insert(module.table, out) } else { saved = try await Api.shared.update(module.table, id, out) }
                saving = false
                nav.pop()
                if isNew { nav.push(.record(module.key, J.str(saved["id"]))) }
            } catch {
                message = error.localizedDescription
                saving = false
            }
        }
    }
}

struct LookupOption: Identifiable, Hashable {
    let id: String
    let label: String
}
