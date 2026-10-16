import Foundation

/// Scalar default value of a form field (text, number or yes/no).
struct Scalar: Decodable {
    let value: Any?
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { value = nil }
        else if let b = try? c.decode(Bool.self) { value = b }
        else if let i = try? c.decode(Int.self) { value = i }
        else if let d = try? c.decode(Double.self) { value = d }
        else if let s = try? c.decode(String.self) { value = s }
        else { value = nil }
    }
}

struct QLookup: Decodable {
    let table: String
    let select: String
    let filter: String
    let order: String
    let label: String
}

struct QField: Decodable, Identifiable {
    let key: String
    let label: String
    let type: String
    let required: Bool
    let readOnly: Bool
    let hint: String
    let options: [String]
    let optionLabels: [String]?
    let def: Scalar?
    let min: Double?
    let max: Double?
    let lookup: QLookup?
    var id: String { key }

    func optionLabel(_ value: String) -> String {
        if let labels = optionLabels, let i = options.firstIndex(of: value), i < labels.count { return labels[i] }
        return Fmt.pretty(value)
    }
}

struct QChild: Decodable {
    let title: String
    let table: String
    let fk: String
    let order: String
    let cols: [[String]]
}

struct QAction: Decodable {
    let label: String
    let when: String
}

/// One QCMS module (register + record + entry), generated from the Android app's catalogue (Cat*.java).
struct QModule: Decodable, Identifiable, Hashable {
    let key: String
    let title: String
    let tab: Int
    let section: String
    let table: String
    let filter: String
    let order: String
    let description: String
    let titleField: String
    let statusField: String
    let idField: String
    let deletable: Bool
    let editable: Bool
    let hasEditor: Bool
    let custom: Bool
    let attachEntity: String
    let attachFolder: String
    let attachSlots: [String]
    let attachMulti: Bool
    let search: [String]
    let statusFilters: [String]
    let numberField: String
    let numberRpc: String
    let numberArgs: String
    let hooks: Bool
    let cols: [[String]]
    let children: [QChild]
    let actions: [QAction]
    let form: [QField]

    var id: String { key }
    static func == (l: QModule, r: QModule) -> Bool { l.key == r.key }
    func hash(into h: inout Hasher) { h.combine(key) }

    /// Native generic form in the app (like the Android EditScreen); other entry screens open the website page.
    var nativeForm: Bool { !form.isEmpty && !hasEditor && editable && !idField.isEmpty }

    func selectList() -> String {
        var fields: [String] = []
        func add(_ f: String) { if !f.isEmpty && !fields.contains(f) { fields.append(f) } }
        add(idField.isEmpty ? (cols.first?.first ?? "*") : idField)
        add(titleField)
        for c in cols { add(c[0]) }
        add(statusField)
        return fields.joined(separator: ",")
    }

    func recordTitle(_ row: Row) -> String {
        var t = titleField.isEmpty ? "" : J.str(row[titleField])
        if t.isEmpty, let first = cols.first?.first { t = J.str(row[first]) }
        return t.isEmpty ? title : t
    }
}

struct ModuleSection: Identifiable {
    let name: String
    var modules: [QModule]
    var id: String { name }
}

struct SearchSource: Decodable {
    let table: String
    let recordType: String
    let module: String
    let moduleKey: String
    let columns: [String]
    let partFields: [String]
    let partyFields: [String]
}

struct Catalog: Decodable {
    let modules: [QModule]
    let fk: [String: [String: String]]
    let labels: [String: [String]]
    let tenantTables: [String]
    let moduleKeys: [String: String]
    let searchSources: [SearchSource]

    static let tabNames = ["Home", "Supply", "Quality", "Masters", "More"]
    static let tabIcons = ["house.fill", "shippingbox.fill", "checkmark.seal.fill", "square.stack.3d.up.fill", "ellipsis.circle.fill"]

    static let shared: Catalog = {
        guard let url = Bundle.main.url(forResource: "catalog", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let c = try? JSONDecoder().decode(Catalog.self, from: data) else {
            return Catalog(modules: [], fk: [:], labels: [:], tenantTables: [], moduleKeys: [:], searchSources: [])
        }
        return c
    }()

    func module(_ key: String) -> QModule? { modules.first { $0.key == key } }

    /// First module that shows this table (used to open child rows and search results).
    func forTable(_ table: String) -> QModule? { modules.first { $0.table == table && !$0.idField.isEmpty && !$0.custom } }

    /// Modules of one bottom tab grouped by section, in catalogue order.
    func sections(tab: Int) -> [ModuleSection] {
        var out: [ModuleSection] = []
        for m in modules where m.tab == tab {
            if let i = out.firstIndex(where: { $0.name == m.section }) { out[i].modules.append(m) } else { out.append(ModuleSection(name: m.section, modules: [m])) }
        }
        return out
    }
}

/// Website pages used for the entry screens that are not native in the iPhone / iPad app yet.
enum WebRoutes {
    static let map: [String: String] = [
        "customer_orders": "supply-customer-orders", "po_approval": "supply-po-approval", "purchase_orders": "supply-purchase-orders",
        "po_confirmations": "supply-purchase-orders", "rm_po_stages": "supply-rm-procurement", "rm_receipts": "supply-rm-receipt",
        "rm_dispatches": "supply-rm-dispatch", "forging_orders": "supply-forging", "forging_receipts": "supply-forging",
        "downstream_events": "supply-downstream", "opening_stock": "supply-opening-stock", "trace_events": "supply-traceability",
        "rmtc": "rmtc-entry", "inward": "inward-entry", "heat_ledger": "heat-ledger", "dimensional_reports": "dimensional-entry",
        "metlab_reports": "metlab-entry", "bend_tests": "bend-test-entry", "inspection_layouts": "inspection-layout-entry",
        "osp_material_out": "osp-material-out", "osp_register": "osp-home", "osp_receipts": "osp-inward",
        "asset_status": "calibration-validation", "quality_assets": "calibration-validation", "calibration_records": "calibration-validation",
        "asset_part_links": "calibration-validation", "standard_room": "standard-room-inspection",
        "customer_complaints": "customer-complaint", "supplier_complaints": "supplier-complaint",
        "parts": "part-entry", "part_rm_viewer": "part-entry", "material_grades": "grade-entry", "jominy_distances": "grade-entry",
        "processes": "process-entry", "inspection_stages": "reference-entry", "customers": "reference-entry", "suppliers": "reference-entry",
        "steel_mills": "reference-entry", "osp_vendors": "reference-entry", "company_branches": "company-branch-entry",
        "employees": "employee-entry", "customer_standards": "standards-entry",
        "npd_flows": "npd-process-flow", "npd_orders": "npd-status", "apqp_projects": "apqp", "pfd": "apqp", "pfmea": "apqp", "control_plans": "apqp",
        "qc_calculations": "qc-tools", "deletion_requests": "records-center", "deleted_records": "records-center",
        "kpi_dashboards": "kpi-dashboards", "report_builder": "report-builder", "master_lists": "master-lists", "traceability": "supply-traceability",
        "email_send": "email-send", "email_sent": "email-sent", "email_groups": "email-groups", "user_access": "user-access",
        "system_settings": "system-settings", "email_server": "email-settings", "print_designer": "print-designer", "master_import": "master-import",
    ]

    static func path(for key: String) -> String? { map[key] }
}
