import SwiftUI
import UIKit
import UserNotifications

/// One row of qcms_my_notifications.
struct QNotification: Identifiable {
    let id: String
    let title: String
    let body: String
    let category: String
    let moduleKey: String
    let relatedTable: String
    let relatedId: String
    let webRoute: String
    let priority: String
    var isRead: Bool
    let createdAt: String

    init(_ r: Row) {
        id = J.str(r["id"])
        title = J.str(r["title"])
        body = J.str(r["body"])
        category = J.str(r["category"]).uppercased()
        moduleKey = J.str(r["module_key"])
        relatedTable = J.str(r["related_table"])
        relatedId = J.str(r["related_id"])
        webRoute = J.str(r["web_route"])
        priority = J.str(r["priority"]).uppercased()
        isRead = J.truthy(r["is_read"])
        createdAt = J.str(r["created_at"])
    }

    var when: String {
        guard createdAt.count >= 10 else { return createdAt }
        let chars = Array(createdAt)
        let time = chars.count >= 16 ? String(chars[11..<16]) : ""
        return time.isEmpty ? Fmt.date(createdAt) : Fmt.date(createdAt) + " " + time
    }

    var icon: String {
        switch category {
        case "APPROVAL": return "checkmark.seal"
        case "TASK": return "checklist"
        case "UPDATE": return "arrow.triangle.2.circlepath"
        case "ALERT": return "exclamationmark.triangle"
        default: return "info.circle"
        }
    }

    var tint: Color {
        switch category {
        case "ALERT": return Theme.red
        case "APPROVAL", "TASK": return Theme.amber
        case "UPDATE": return Theme.brand
        default: return Theme.tealDark
        }
    }
}

/// Where a notification / KPI task / search hit opens inside the app.
enum AppLinks {
    /// Native record when a module shows the table, else the module that owns the website route, else the website page.
    static func route(title: String, table: String, id: String, moduleKey: String, webRoute: String) -> Route? {
        let cat = Catalog.shared
        if !table.isEmpty, !id.isEmpty, let m = cat.forTable(table) { return .record(m.key, id) }
        if !moduleKey.isEmpty {
            if let m = cat.module(moduleKey) ?? cat.module(moduleKey.lowercased()) {
                if !id.isEmpty, !m.table.isEmpty, !m.idField.isEmpty, !m.custom { return .record(m.key, id) }
                return .module(m.key)
            }
            let upper = moduleKey.uppercased()
            if !id.isEmpty, let src = cat.searchSources.first(where: { $0.moduleKey.uppercased() == upper }), let m = cat.forTable(src.table) {
                return .record(m.key, id)
            }
        }
        let path = webRoute.trimmingCharacters(in: CharacterSet(charactersIn: "/ "))
        if !path.isEmpty {
            if let m = cat.modules.first(where: { WebRoutes.path(for: $0.key) == path }) { return .module(m.key) }
            return .web(title.isEmpty ? "QCMS" : title, path)
        }
        return nil
    }
}

/// Notification inbox state: unread count (bell + app icon badge), list, push-tap requests.
@MainActor
final class Inbox: ObservableObject {
    static let shared = Inbox()

    @Published var unread = 0
    @Published var items: [QNotification] = []
    /// Incremented when a push notification was tapped; MainView switches to the first tab and opens the inbox.
    @Published var openRequest = 0
    var pendingOpen = false
    var pendingReadId = ""

    func refreshCount() async {
        guard let raw = try? await Api.shared.rpc("qcms_unread_notification_count", [:]) else { return }
        let n = Int(J.num(raw) ?? 0)
        unread = max(0, n)
        setBadge(unread)
    }

    func load(unreadOnly: Bool) async throws {
        let raw = try await Api.shared.rpc("qcms_my_notifications", ["p_limit": 100, "p_unread_only": unreadOnly])
        items = J.rows(raw).map { QNotification($0) }
    }

    /// nil = mark all of mine read.
    func markRead(_ ids: [String]?) async {
        var args: [String: Any] = [:]
        if let ids = ids { args["p_ids"] = ids } else { args["p_ids"] = NSNull() }
        _ = try? await Api.shared.rpcRaw("qcms_mark_notifications_read", args)
        let wanted: Set<String>? = ids.map { Set($0) }
        for i in items.indices {
            if let w = wanted {
                if w.contains(items[i].id) { items[i].isRead = true }
            } else {
                items[i].isRead = true
            }
        }
        await refreshCount()
    }

    func openFromPush(notificationId: String, webRoute: String) {
        pendingReadId = notificationId
        pendingOpen = true
        openRequest += 1
    }

    /// Returns true once when a push tap is waiting to open the inbox.
    func consumeOpen() -> Bool {
        if pendingOpen { pendingOpen = false; return true }
        return false
    }

    func reset() {
        unread = 0
        items = []
        pendingOpen = false
        pendingReadId = ""
        setBadge(0)
    }

    func setBadge(_ n: Int) {
        if #available(iOS 17.0, *) {
            UNUserNotificationCenter.current().setBadgeCount(n) { _ in }
        } else {
            UIApplication.shared.applicationIconBadgeNumber = n
        }
    }
}

/// APNs registration (token sent with qcms_register_push_device after login).
enum Push {
    static let tokenKey = "apns_device_token"

    static var platform: String {
        #if DEBUG
        return "IOS_SANDBOX"
        #else
        return "IOS"
        #endif
    }

    /// Ask for permission after login and register with APNs (the token arrives in AppDelegate).
    @MainActor
    static func start() async {
        let center = UNUserNotificationCenter.current()
        let granted = (try? await center.requestAuthorization(options: [.alert, .badge, .sound])) ?? false
        if granted { UIApplication.shared.registerForRemoteNotifications() }
    }

    static func upload(_ token: String) async {
        guard !token.isEmpty else { return }
        let args: [String: Any] = ["p_platform": platform, "p_token": token, "p_app_version": AppConfig.appVersion]
        _ = try? await Api.shared.rpcRaw("qcms_register_push_device", args)
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate {
    private let pushDelegate = PushDelegate()

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = pushDelegate
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let hex = deviceToken.map { String(format: "%02x", $0) }.joined()
        UserDefaults.standard.set(hex, forKey: Push.tokenKey)
        Task { await Push.upload(hex) }
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        print("STAWN QCMS: APNs registration failed - \(error.localizedDescription)")
    }
}

/// Shows pushes while the app is open and opens the inbox when one is tapped.
final class PushDelegate: NSObject, UNUserNotificationCenterDelegate {
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        Task { @MainActor in await Inbox.shared.refreshCount() }
        completionHandler([.banner, .list, .sound, .badge])
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        let info = response.notification.request.content.userInfo
        let nested = info["data"] as? [String: Any] ?? [:]
        let route = (info["web_route"] as? String) ?? (nested["web_route"] as? String) ?? ""
        let nid = (info["notification_id"] as? String) ?? (nested["notification_id"] as? String) ?? ""
        Task { @MainActor in Inbox.shared.openFromPush(notificationId: nid, webRoute: route) }
        completionHandler()
    }
}

/// Bell with unread badge (toolbar of the main screens).
struct BellButton: View {
    @EnvironmentObject var nav: TabNav
    @EnvironmentObject var inbox: Inbox

    var body: some View {
        Button { nav.push(.notifications) } label: {
            ZStack(alignment: .topTrailing) {
                Image(systemName: inbox.unread > 0 ? "bell.badge" : "bell")
                    .font(.system(size: 17, weight: .semibold))
                    .padding(.trailing, 4).padding(.top, 2)
                if inbox.unread > 0 {
                    Text(inbox.unread > 99 ? "99+" : "\(inbox.unread)")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(.white)
                        .padding(.horizontal, 4).padding(.vertical, 1)
                        .background(Capsule().fill(Color.red))
                        .offset(x: 8, y: -6)
                }
            }
        }
        .accessibilityLabel(inbox.unread > 0 ? "Notifications, \(inbox.unread) unread" : "Notifications")
    }
}

extension View {
    /// Notification bell at the trailing side of the navigation bar.
    func qcmsBell() -> some View {
        self.toolbar {
            ToolbarItem(placement: .navigationBarTrailing) { BellButton() }
        }
    }
}

struct NotificationsView: View {
    @EnvironmentObject var nav: TabNav
    @EnvironmentObject var inbox: Inbox
    @State private var unreadOnly = true
    @State private var loading = false
    @State private var error: String?
    @State private var waOptIn = UserDefaults.standard.bool(forKey: "wa_opt_in")
    @State private var waNumber = UserDefaults.standard.string(forKey: "wa_number") ?? ""
    @State private var waMessage: String?
    @State private var waBusy = false

    var body: some View {
        List {
            Section {
                Picker("Show", selection: $unreadOnly) {
                    Text("Unread").tag(true)
                    Text("All").tag(false)
                }
                .pickerStyle(.segmented)
            }
            if let e = error {
                Section { Text(e).font(.footnote).foregroundColor(Theme.red) }
            }
            Section(header: Text(unreadOnly ? "Unread (\(inbox.unread))" : "All notifications")) {
                if loading && inbox.items.isEmpty {
                    HStack(spacing: 10) { ProgressView(); Text("Loading notifications…").foregroundColor(Theme.muted) }
                } else if inbox.items.isEmpty {
                    Text(unreadOnly ? "You are all caught up." : "No notifications yet.").foregroundColor(Theme.muted)
                }
                ForEach(inbox.items) { n in
                    Button { open(n) } label: { NotificationRow(n: n) }
                        .swipeActions(edge: .trailing) {
                            if !n.isRead {
                                Button("Read") { Task { await inbox.markRead([n.id]) } }.tint(Theme.teal)
                            }
                        }
                }
            }
            Section {
                Toggle("Send my QCMS alerts on WhatsApp", isOn: $waOptIn)
                TextField("Mobile number with country code, e.g. +91 98…", text: $waNumber)
                    .keyboardType(.phonePad)
                    .textContentType(.telephoneNumber)
                if let m = waMessage { Text(m).font(.footnote).foregroundColor(Theme.muted) }
                Button(waBusy ? "Saving…" : "Save WhatsApp setting") { saveWhatsApp() }
                    .disabled(waBusy || (waOptIn && waNumber.trimmingCharacters(in: .whitespaces).count < 8))
            } header: {
                Text("WhatsApp alerts")
            } footer: {
                Text("Approvals, tasks and alerts can also be sent to your WhatsApp number. You can switch this off at any time.")
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle("Notifications")
        .navigationBarTitleDisplayMode(.inline)
        .qcmsNavBar()
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("Mark all read") {
                    Task {
                        await inbox.markRead(nil)
                        await reload()
                    }
                }
                .disabled(inbox.unread == 0)
            }
        }
        .task(id: unreadOnly) { await reload() }
        .refreshable { await reload() }
    }

    @MainActor private func reload() async {
        loading = true
        if !inbox.pendingReadId.isEmpty {
            let id = inbox.pendingReadId
            inbox.pendingReadId = ""
            await inbox.markRead([id])
        }
        do {
            try await inbox.load(unreadOnly: unreadOnly)
            error = nil
        } catch {
            if !Task.isCancelled { self.error = error.localizedDescription }
        }
        await inbox.refreshCount()
        loading = false
    }

    private func open(_ n: QNotification) {
        if !n.isRead { Task { await inbox.markRead([n.id]) } }
        if let r = AppLinks.route(title: n.title, table: n.relatedTable, id: n.relatedId, moduleKey: n.moduleKey, webRoute: n.webRoute) {
            nav.push(r)
        }
    }

    private func saveWhatsApp() {
        let number = waNumber.trimmingCharacters(in: .whitespaces)
        let optIn = waOptIn
        waBusy = true
        waMessage = nil
        Task { @MainActor in
            do {
                let args: [String: Any] = ["p_opt_in": optIn, "p_mobile_number": number.isEmpty ? NSNull() as Any : number as Any]
                let raw = try await Api.shared.rpc("qcms_set_my_whatsapp", args)
                let res = J.obj(raw)
                UserDefaults.standard.set(optIn, forKey: "wa_opt_in")
                UserDefaults.standard.set(number, forKey: "wa_number")
                let msg = J.str(res["message"])
                waMessage = msg.isEmpty ? (optIn ? "WhatsApp alerts switched on." : "WhatsApp alerts switched off.") : msg
            } catch {
                waMessage = error.localizedDescription
            }
            waBusy = false
        }
    }
}

struct NotificationRow: View {
    let n: QNotification
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: n.icon).font(.system(size: 16, weight: .semibold)).foregroundColor(n.tint)
                .frame(width: 34, height: 34).background(Theme.tealSoft).clipShape(RoundedRectangle(cornerRadius: 9))
            VStack(alignment: .leading, spacing: 3) {
                HStack(alignment: .firstTextBaseline) {
                    Text(n.title.isEmpty ? "QCMS notification" : n.title)
                        .font(.subheadline.weight(n.isRead ? .regular : .semibold))
                        .foregroundColor(Theme.text)
                        .lineLimit(2)
                    Spacer()
                    if !n.isRead { Circle().fill(Theme.teal).frame(width: 8, height: 8) }
                }
                if !n.body.isEmpty { Text(n.body).font(.caption).foregroundColor(Theme.muted).lineLimit(3) }
                HStack(spacing: 6) {
                    Text(Fmt.pretty(n.category)).font(.caption2.weight(.bold)).foregroundColor(n.tint)
                    if n.priority == "HIGH" || n.priority == "URGENT" { StatusChip(text: n.priority) }
                    Spacer()
                    Text(n.when).font(.caption2).foregroundColor(Theme.muted)
                }
            }
        }
        .padding(.vertical, 2)
    }
}
