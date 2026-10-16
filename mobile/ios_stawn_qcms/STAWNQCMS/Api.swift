import Foundation
import Security
import CryptoKit

struct ApiError: LocalizedError {
    let status: Int
    let message: String
    var errorDescription: String? { message }
}

/// Refresh token in the iOS Keychain (this device only; never synced, never the password).
enum Keychain {
    private static let service = "com.stawn.qcms"

    static func set(_ value: String?, for account: String) {
        let base: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: account]
        SecItemDelete(base as CFDictionary)
        guard let value = value, let data = value.data(using: .utf8) else { return }
        var add = base
        add[kSecValueData as String] = data
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(add as CFDictionary, nil)
    }

    static func get(_ account: String) -> String? {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: account,
                                kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var out: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let data = out as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
}

/// Access and refresh tokens; one refresh at a time.
actor TokenStore {
    var access: String?
    var refresh: String?
    var expires = Date.distantPast

    func set(access: String, refresh: String?, expiresIn: Double) {
        self.access = access
        if let r = refresh, !r.isEmpty { self.refresh = r }
        self.expires = Date().addingTimeInterval(expiresIn)
    }

    func setRefresh(_ r: String?) { refresh = r }
    func clear() { access = nil; refresh = nil; expires = .distantPast }
    func valid() -> String? { if let a = access, Date() < expires.addingTimeInterval(-60) { return a }; return nil }
    func refreshToken() -> String? { refresh }
}

/// Supabase REST / Auth / Storage client - the same calls as the website's Repository and the Android app.
final class Api {
    static let shared = Api()
    private let tokens = TokenStore()
    private let session: URLSession = {
        let c = URLSessionConfiguration.default
        c.timeoutIntervalForRequest = 40
        c.timeoutIntervalForResource = 120
        return URLSession(configuration: c)
    }()

    // signed-in user (set after sign in / restore)
    var userId = ""
    var email = UserDefaults.standard.string(forKey: "email") ?? ""
    var fullName = ""
    var role = ""
    var tenantId = ""
    var employeeId = ""
    var employeeLabel = ""
    var isAdmin: Bool { role.uppercased() == "ADMIN" }

    var keepSignedIn: Bool {
        get { UserDefaults.standard.object(forKey: "keep_signed_in") as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: "keep_signed_in") }
    }

    static func enc(_ v: String) -> String {
        var allowed = CharacterSet.alphanumerics
        allowed.insert(charactersIn: "-._~")
        return v.addingPercentEncoding(withAllowedCharacters: allowed) ?? v
    }

    // ------------------------------------------------------------------ auth
    func signIn(email: String, password: String) async throws {
        let body = try JSONSerialization.data(withJSONObject: ["email": email.trimmingCharacters(in: .whitespaces), "password": password])
        let (data, _) = try await send("POST", "/auth/v1/token?grant_type=password", body: body, bearer: nil)
        try await storeTokens(data)
        await loadProfile()
    }

    func restore() async -> Bool {
        guard let saved = Keychain.get("refresh_token") else { return false }
        await tokens.setRefresh(saved)
        do {
            try await refresh()
            await loadProfile()
            return true
        } catch let e as ApiError where [400, 401, 403].contains(e.status) {
            Keychain.set(nil, for: "refresh_token")
            return false
        } catch {
            return false
        }
    }

    func verifyPassword(_ password: String) async throws { try await signIn(email: email, password: password) }

    func changePassword(_ newPassword: String) async throws {
        let body = try JSONSerialization.data(withJSONObject: ["password": newPassword])
        let (data, _) = try await authed("PUT", "/auth/v1/user", body: body)
        let json = (try? JSONSerialization.jsonObject(with: data)) as? Row ?? [:]
        if J.str(json["id"]).isEmpty { throw ApiError(status: 500, message: "Supabase did not confirm the password change.") }
    }

    func signOut() async {
        let token = await tokens.valid()
        await tokens.clear()
        Keychain.set(nil, for: "refresh_token")
        fullName = ""; role = ""; tenantId = ""; employeeId = ""; employeeLabel = ""
        if let t = token { _ = try? await send("POST", "/auth/v1/logout", body: Data("{}".utf8), bearer: t) }
    }

    private func refresh() async throws {
        guard let r = await tokens.refreshToken() else { throw ApiError(status: 401, message: "Please sign in again.") }
        let body = try JSONSerialization.data(withJSONObject: ["refresh_token": r])
        let (data, _) = try await send("POST", "/auth/v1/token?grant_type=refresh_token", body: body, bearer: nil)
        try await storeTokens(data)
    }

    private func storeTokens(_ data: Data) async throws {
        guard let json = try JSONSerialization.jsonObject(with: data) as? Row, let access = json["access_token"] as? String else {
            throw ApiError(status: 500, message: "Unexpected sign-in answer.")
        }
        let refresh = json["refresh_token"] as? String
        await tokens.set(access: access, refresh: refresh, expiresIn: J.num(json["expires_in"]) ?? 3600)
        if let user = json["user"] as? Row {
            userId = J.str(user["id"])
            email = J.str(user["email"])
            UserDefaults.standard.set(email, forKey: "email")
        }
        let savedRefresh = await tokens.refreshToken()
        Keychain.set(keepSignedIn ? savedRefresh : nil, for: "refresh_token")
    }

    private func loadProfile() async {
        if let p = try? await rows("profiles?select=full_name,role,email,tenant_id&id=eq.\(userId)").first {
            fullName = J.str(p["full_name"]); role = J.str(p["role"]); tenantId = J.str(p["tenant_id"])
        }
        if let raw = try? await rpcRaw("qcms_current_login_employee_id", [:]) {
            let emp = String(data: raw, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines).replacingOccurrences(of: "\"", with: "") ?? ""
            employeeId = emp == "null" ? "" : emp
            if !employeeId.isEmpty, let e = try? await rows("employees?select=employee_code,first_name,last_name&id=eq.\(employeeId)").first {
                employeeLabel = "\(J.str(e["employee_code"])) · \(J.str(e["first_name"])) \(J.str(e["last_name"]))".trimmingCharacters(in: .whitespaces)
            }
        }
    }

    private func token() async throws -> String {
        if let t = await tokens.valid() { return t }
        try await refresh()
        if let t = await tokens.valid() { return t }
        throw ApiError(status: 401, message: "Session expired - please sign in again.")
    }

    // ------------------------------------------------------------------ HTTP
    private func send(_ method: String, _ path: String, body: Data?, bearer: String?, contentType: String = "application/json; charset=utf-8",
                      prefer: String? = nil, headers: [String: String] = [:]) async throws -> (Data, HTTPURLResponse) {
        guard let url = URL(string: AppConfig.supabaseURL + path) else { throw ApiError(status: 0, message: "Bad address \(path)") }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue(AppConfig.supabaseKey, forHTTPHeaderField: "apikey")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        req.setValue("qcms-ios/\(AppConfig.appVersion)", forHTTPHeaderField: "X-Client-Info")
        if let b = bearer { req.setValue("Bearer \(b)", forHTTPHeaderField: "Authorization") }
        if let p = prefer { req.setValue(p, forHTTPHeaderField: "Prefer") }
        for (k, v) in headers { req.setValue(v, forHTTPHeaderField: k) }
        if let body = body { req.httpBody = body; req.setValue(contentType, forHTTPHeaderField: "Content-Type") }
        let result: (Data, URLResponse)
        do {
            result = try await session.data(for: req)
        } catch {
            throw ApiError(status: 0, message: "No internet connection. Connect and try again.")
        }
        let data = result.0
        let response = result.1
        guard let http = response as? HTTPURLResponse else { throw ApiError(status: 0, message: "No answer from the server.") }
        if http.statusCode >= 400 { throw ApiError(status: http.statusCode, message: Api.friendly(http.statusCode, data)) }
        return (data, http)
    }

    private func authed(_ method: String, _ path: String, body: Data? = nil, contentType: String = "application/json; charset=utf-8",
                        prefer: String? = nil, headers: [String: String] = [:]) async throws -> (Data, HTTPURLResponse) {
        do {
            return try await send(method, path, body: body, bearer: try await token(), contentType: contentType, prefer: prefer, headers: headers)
        } catch let e as ApiError where e.status == 401 {
            try await refresh()
            return try await send(method, path, body: body, bearer: try await token(), contentType: contentType, prefer: prefer, headers: headers)
        }
    }

    static func friendly(_ code: Int, _ data: Data) -> String {
        let text = String(data: data, encoding: .utf8) ?? ""
        var message = text
        if let json = (try? JSONSerialization.jsonObject(with: data)) as? Row {
            for k in ["message", "msg", "error_description", "error"] where !J.str(json[k]).isEmpty { message = J.str(json[k]); break }
        }
        let low = message.lowercased()
        if low.contains("invalid login credentials") { return "Email or password is not correct." }
        if low.contains("email not confirmed") { return "This login is not confirmed yet. Ask the QCMS administrator." }
        if low.contains("jwt expired") { return "Session expired - please sign in again." }
        if low.contains("permission denied") || low.contains("row-level security") { return "Your QCMS role does not have permission for this action." }
        if message.isEmpty { return "Server error \(code)." }
        return message
    }

    // ------------------------------------------------------------------ REST
    func rows(_ path: String) async throws -> [Row] {
        let (data, _) = try await authed("GET", "/rest/v1/" + path)
        return J.rows(try JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed]))
    }

    /// Like rows() but never throws (empty list on any error).
    func list(_ path: String) async -> [Row] { (try? await rows(path)) ?? [] }

    func one(_ table: String, _ id: Any?) async -> Row {
        let s = J.str(id)
        if s.isEmpty { return [:] }
        return await list("\(table)?select=*&id=eq.\(Api.enc(s))&limit=1").first ?? [:]
    }

    func count(_ path: String) async -> Int {
        let sep = path.contains("?") ? "&" : "?"
        guard let res = try? await authed("GET", "/rest/v1/" + path + sep + "limit=1", prefer: "count=exact") else { return 0 }
        let range = res.1.value(forHTTPHeaderField: "Content-Range") ?? ""
        guard let slash = range.lastIndex(of: "/") else { return 0 }
        return Int(range[range.index(after: slash)...]) ?? 0
    }

    func rpcRaw(_ function: String, _ args: [String: Any]) async throws -> Data {
        let body = try JSONSerialization.data(withJSONObject: args)
        return try await authed("POST", "/rest/v1/rpc/" + function, body: body).0
    }

    func rpc(_ function: String, _ args: [String: Any]) async throws -> Any? {
        let data = try await rpcRaw(function, args)
        if data.isEmpty { return nil }
        return try? JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])
    }

    func insert(_ table: String, _ values: Row) async throws -> Row {
        var v = values
        if J.isNull(v["id"]) { v["id"] = UUID().uuidString.lowercased() }
        if !tenantId.isEmpty, Catalog.shared.tenantTables.contains(table), J.isNull(v["tenant_id"]) { v["tenant_id"] = tenantId }
        let body = try JSONSerialization.data(withJSONObject: v)
        let (data, _) = try await authed("POST", "/rest/v1/" + table, body: body, prefer: "return=representation")
        let saved = J.rows(try JSONSerialization.jsonObject(with: data)).first ?? v
        await logActivity("CREATE", table, J.str(saved["id"]))
        return saved
    }

    func update(_ table: String, _ id: String, _ values: Row) async throws -> Row {
        let body = try JSONSerialization.data(withJSONObject: values)
        let (data, _) = try await authed("PATCH", "/rest/v1/\(table)?id=eq.\(Api.enc(id))", body: body, prefer: "return=representation")
        guard let row = J.rows(try JSONSerialization.jsonObject(with: data)).first else {
            throw ApiError(status: 403, message: "The record was not saved - it is not visible / editable for your role.")
        }
        await logActivity("UPDATE", table, id)
        return row
    }

    func upsertBy(_ table: String, _ values: Row, keys: [String]) async throws -> Row {
        var q = "\(table)?select=id&limit=1"
        for k in keys { q += J.isNull(values[k]) ? "&\(k)=is.null" : "&\(k)=eq.\(Api.enc(J.str(values[k])))" }
        if let found = try await rows(q).first { return try await update(table, J.str(found["id"]), values) }
        return try await insert(table, values)
    }

    private func logActivity(_ action: String, _ table: String, _ rowId: String) async {
        var args: [String: Any] = ["p_action": action, "p_section_key": NSNull(), "p_table_name": table, "p_details": ["source": "ios_app"]]
        if let mk = Catalog.shared.moduleKeys[table] { args["p_module_key"] = mk } else { args["p_module_key"] = NSNull() }
        if rowId.isEmpty { args["p_row_id"] = NSNull() } else { args["p_row_id"] = rowId }
        _ = try? await rpcRaw("qcms_log_user_activity", args)
    }

    // ------------------------------------------------------------------ storage (bucket quality-documents)
    private static func encPath(_ path: String) -> String {
        path.split(separator: "/", omittingEmptySubsequences: false).map { enc(String($0)) }.joined(separator: "/")
    }

    func upload(_ path: String, _ data: Data, mime: String, upsert: Bool) async throws {
        _ = try await authed("POST", "/storage/v1/object/\(AppConfig.bucket)/\(Api.encPath(path))", body: data, contentType: mime,
                             headers: ["x-upsert": upsert ? "true" : "false", "cache-control": "3600"])
    }

    func removeObject(_ path: String) async { _ = try? await authed("DELETE", "/storage/v1/object/\(AppConfig.bucket)/\(Api.encPath(path))") }

    func download(_ path: String) async throws -> Data {
        try await authed("GET", "/storage/v1/object/authenticated/\(AppConfig.bucket)/\(Api.encPath(path))").0
    }

    func signedURL(_ path: String, seconds: Int = 900) async throws -> URL {
        let body = try JSONSerialization.data(withJSONObject: ["expiresIn": seconds])
        let (data, _) = try await authed("POST", "/storage/v1/object/sign/\(AppConfig.bucket)/\(Api.encPath(path))", body: body)
        let json = J.obj(try JSONSerialization.jsonObject(with: data))
        var rel = J.str(json["signedURL"])
        if rel.isEmpty { rel = J.str(json["signedUrl"]) }
        if rel.isEmpty { throw ApiError(status: 404, message: "File link not available.") }
        let full = rel.hasPrefix("http") ? rel : AppConfig.supabaseURL + "/storage/v1" + (rel.hasPrefix("/") ? rel : "/" + rel)
        guard let url = URL(string: full) else { throw ApiError(status: 404, message: "File link not available.") }
        return url
    }

    // ------------------------------------------------------------------ attachments (core/attachments.py)
    static func safe(_ v: String) -> String {
        let lower = v.lowercased()
        var out = ""
        var lastUnderscore = false
        for ch in lower.unicodeScalars {
            if CharacterSet.alphanumerics.contains(ch) && ch.isASCII { out.unicodeScalars.append(ch); lastUnderscore = false }
            else if !lastUnderscore { out += "_"; lastUnderscore = true }
        }
        let trimmed = out.trimmingCharacters(in: CharacterSet(charactersIn: "_"))
        return trimmed.isEmpty ? "file" : trimmed
    }

    static func sha256(_ d: Data) -> String { SHA256.hash(data: d).map { String(format: "%02x", $0) }.joined() }

    func attachments(entity: String, id: String) async throws -> [Row] {
        try await rows("document_attachments?select=id,document_type,document_title,file_name,object_path,mime_type,size_bytes,created_at"
                       + "&entity_type=eq.\(entity)&entity_id=eq.\(Api.enc(id))&status=eq.ACTIVE&order=created_at.asc")
    }

    /// Fixed slot (AttachmentService.upload) or titled extra file (upload_additional).
    func uploadAttachment(entity: String, id: String, folder: String, docType: String, data: Data, fileName: String, mime: String, title: String?) async throws {
        let ext = (fileName as NSString).pathExtension.isEmpty ? (mime.contains("png") ? "png" : mime.contains("pdf") ? "pdf" : "jpg") : (fileName as NSString).pathExtension.lowercased()
        let stem = (fileName as NSString).deletingPathExtension
        var row: Row = ["entity_type": entity, "entity_id": id, "document_type": docType, "file_name": fileName, "mime_type": mime,
                        "size_bytes": data.count, "checksum": Api.sha256(data), "status": "ACTIVE"]
        if let title = title {
            let path = "\(tenantId)/\(Api.safe(folder))/\(id)/\(Api.safe(docType))/\(UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(12).lowercased())_\(Api.safe(stem)).\(ext)"
            try await upload(path, data, mime: mime, upsert: false)
            row["object_path"] = path
            row["document_title"] = title
            do { _ = try await insert("document_attachments", row) } catch { await removeObject(path); throw error }
        } else {
            let path = "\(tenantId)/\(Api.safe(folder))/\(id)/\(Api.safe(docType))"
            try await upload(path, data, mime: mime, upsert: true)
            row["object_path"] = path
            _ = try await upsertBy("document_attachments", row, keys: ["entity_type", "entity_id", "document_type"])
        }
    }
}
