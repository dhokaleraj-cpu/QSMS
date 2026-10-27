"""R35: STAWN QCMS iOS app v1.1.0 (build 2) - notifications + APNs push, KPI start dashboard, server global search, licence."""
import plistlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IOS = ROOT / "mobile/ios_stawn_qcms"
SRC = IOS / "STAWNQCMS"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def swift_all() -> str:
    return "".join(read(p) for p in sorted(SRC.glob("*.swift")))


def test_new_files_exist_and_are_in_the_project():
    for name in ("Notifications.swift", "KpiDashboardView.swift", "Licence.swift"):
        assert (SRC / name).exists(), name
    pbx = read(IOS / "STAWNQCMS.xcodeproj/project.pbxproj")
    for p in SRC.glob("*.swift"):
        assert f'path = "{p.name}"' in pbx, p.name
    assert 'path = "STAWNQCMS.entitlements"' in pbx


def test_live_rpc_contracts_are_called():
    code = swift_all()
    for rpc in ("qcms_my_notifications", "qcms_unread_notification_count", "qcms_mark_notifications_read", "qcms_register_push_device",
                "qcms_set_my_whatsapp", "qcms_global_search", "qcms_kpi_dashboard", "qcms_licence_status", "qcms_activate_licence"):
        assert f'"{rpc}"' in code, rpc
    for arg in ('"p_limit"', '"p_unread_only"', '"p_ids"', '"p_platform"', '"p_token"', '"p_app_version"', '"p_opt_in"', '"p_mobile_number"',
                '"p_query"', '"p_department"', '"p_key"'):
        assert arg in code, arg
    assert "service_role" not in code


def test_push_registration_and_platforms():
    n = read(SRC / "Notifications.swift")
    assert "UIApplicationDelegate" in n and "didRegisterForRemoteNotificationsWithDeviceToken" in n
    assert "registerForRemoteNotifications()" in n and "requestAuthorization" in n
    assert re.search(r'#if DEBUG\s+return "IOS_SANDBOX"\s+#else\s+return "IOS"', n)
    assert '%02x' in n and "UNUserNotificationCenterDelegate" in n and '"web_route"' in n and '"notification_id"' in n
    assert "setBadgeCount" in n and "applicationIconBadgeNumber" in n and "#available(iOS 17" in n
    assert "@UIApplicationDelegateAdaptor(AppDelegate.self)" in read(SRC / "App.swift")


def test_entitlements_and_background_mode():
    ent = plistlib.loads((SRC / "STAWNQCMS.entitlements").read_bytes())
    assert ent["aps-environment"] == "development"
    info = plistlib.loads((SRC / "Info.plist").read_bytes())
    assert "remote-notification" in info["UIBackgroundModes"]
    assert info["CFBundleShortVersionString"] == "$(MARKETING_VERSION)"


def test_make_project_version_entitlements_and_team_logic():
    mp = read(IOS / "make_project.py")
    assert 'else "1.2.0"' in mp and 'else "3"' in mp
    assert '"CODE_SIGN_ENTITLEMENTS": "STAWNQCMS/" + ENTITLEMENTS' in mp and 'ENTITLEMENTS = "STAWNQCMS.entitlements"' in mp
    assert "STAWN_APPLE_TEAM_ID" in mp and "~/.stawn_apple_team_id" in mp and "Apple Distribution" in mp
    pbx = read(IOS / "STAWNQCMS.xcodeproj/project.pbxproj")
    assert pbx.count('CODE_SIGN_ENTITLEMENTS = "STAWNQCMS/STAWNQCMS.entitlements"') == 2
    assert 'MARKETING_VERSION = "1.2.0"' in pbx and 'CURRENT_PROJECT_VERSION = "3"' in pbx
    assert pbx.count("{") == pbx.count("}") and pbx.count("(") == pbx.count(")")
    assert 'VERSION="1.2.0"' in read(IOS / "BUILD_STAWN_QCMS_iOS.command")
    assert '"1.2.0"' in read(SRC / "Core.swift")


def test_kpi_dashboard_first_tab_with_auto_switch():
    k = read(SRC / "KpiDashboardView.swift")
    assert "import Charts" in k and "#available(iOS 16, *)" in k and "SectorMark" in k and "@available(iOS 17, *)" in k
    order = [k.index(f'"{d}"') for d in ("QUALITY", "SUPPLY_CHAIN", "PRODUCTION", "NPD", "MANAGEMENT")]
    assert order == sorted(order)
    assert ".transition(.asymmetric(insertion: .move(edge: .trailing), removal: .move(edge: .leading)))" in k and "withAnimation" in k
    assert "autoSeconds: UInt64 = 20" in k and "pauseSeconds: TimeInterval = 60" in k and "pending_tasks" in k
    assert k.index("Pending tasks") < k.index("KPIs")
    main = read(SRC / "MainView.swift")
    assert "if tab == 0 { KpiDashboardView() }" in main and "case .home: HomeView()" in main and "case .notifications: NotificationsView()" in main
    assert ".qcmsBell()" in main and ".qcmsBell()" in read(SRC / "HomeView.swift") and ".qcmsBell()" in k


def test_global_search_merges_server_results_and_modules():
    s = read(SRC / "SearchView.swift")
    assert "GlobalSearch.server(q)" in s and "GlobalSearch.everywhere(q)" in s and "GlobalSearch.merge(" in s and "GlobalSearch.modules(q)" in s
    for f in ('"source_table"', '"record_id"', '"title"', '"subtitle"', '"snippet"', '"record_type"', '"web_route"'):
        assert f in s, f
    assert "Catalog.shared.forTable(r.table)" in s and "nav.push(.web(r.reference, r.webRoute))" in s


def test_licence_block_screen_and_about():
    lic = read(SRC / "Licence.swift")
    assert "business@stawnprecision.com" in read(SRC / "AboutView.swift") and "GenAbout.email" in lic
    assert "!valid && !isStawnDeveloper" in lic and "app.signOut()" in lic and "AboutView()" in lic
    app = read(SRC / "App.swift")
    assert "if app.licenceBlocked { LicenceBlockedView() } else { MainView() }" in app
    # never block when the RPC fails
    assert 'guard let raw = try? await Api.shared.rpc("qcms_licence_status", [:]) else { return }' in app
    about = read(SRC / "AboutView.swift")
    for label in ("Plan", "Status", "Users", "Valid until", "Licence key", "Developer", "App version"):
        assert f'"{label}"' in about, label
    assert "STAWN PRECISION PRIVATE LIMITED" in about


def test_readme_push_section_has_no_secrets():
    readme = read(IOS / "README_IOS.md")
    assert "## Push notifications (APNs)" in readme and "v1.1.0" in readme
    assert 'supabase secrets set APNS_KEY_P8="$(cat AuthKey_XXXX.p8)" APNS_KEY_ID=XXXX APNS_TEAM_ID=XXXX --project-ref xxrxopzxzyjnzumrwuwy' in readme
    assert "BEGIN PRIVATE KEY" not in swift_all() + readme


def test_r36_free_apple_id_mode():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "mobile/ios_stawn_qcms"
    mp = (root / "make_project.py").read_text()
    assert "STAWN_PERSONAL_TEAM" in mp and "com.stawnprecision.qcms.free" in mp and 'target_common.pop("CODE_SIGN_ENTITLEMENTS"' in mp
    cmd = (root / "BUILD_STAWN_QCMS_iOS.command").read_text()
    assert 'if [ "$MODE" = "free" ]' in cmd and "isFreeProvisioningTeam" in cmd and "VPN & Device Management" in cmd
