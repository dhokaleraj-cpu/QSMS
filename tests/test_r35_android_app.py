"""R35: native Android app v3.4.0 - notifications, KPI start dashboard, server-wide search, licence."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "mobile/android_qcms_app"
SRC = APP / "app/src/main/java/com/fourstar/qcmsapp"
MANIFEST = APP / "app/src/main/AndroidManifest.xml"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def all_sources() -> str:
    return "\n".join(read(p) for p in sorted(SRC.glob("*.java")))


def test_version_340():
    gradle = read(APP / "app/build.gradle")
    assert "versionCode 370" in gradle and "versionName '3.7.0'" in gradle  # R38 bump
    assert "3.3.0" not in gradle
    assert "implementation" not in gradle  # still framework only (no AndroidX / Firebase SDK)
    assert "service_role" not in gradle


def test_new_files_exist():
    for name in ("Notif.java", "NotifScreen.java", "NotifJob.java", "BootReceiver.java",
                 "KpiHomeScreen.java", "Licence.java"):
        assert (SRC / name).exists(), name


def test_manifest_permissions_job_and_boot():
    m = read(MANIFEST)
    assert "android.permission.POST_NOTIFICATIONS" in m
    assert "android.permission.RECEIVE_BOOT_COMPLETED" in m
    assert re.search(r'<service\s+android:name="\.NotifJob"[^>]*android:permission="android.permission.BIND_JOB_SERVICE"', m, re.S)
    assert 'android:name=".BootReceiver"' in m and "android.intent.action.BOOT_COMPLETED" in m
    assert 'android:launchMode="singleTop"' in m


def test_live_rpcs_are_used():
    src = all_sources()
    for rpc in ("qcms_my_notifications", "qcms_unread_notification_count", "qcms_mark_notifications_read",
                "qcms_set_my_whatsapp", "qcms_kpi_dashboard", "qcms_global_search",
                "qcms_licence_status", "qcms_activate_licence"):
        assert f'"{rpc}"' in src, rpc
    assert "service_role" not in src


def test_notifications_job_channel_and_permission():
    notif = read(SRC / "Notif.java")
    job = read(SRC / "NotifJob.java")
    main = read(SRC / "MainActivity.java")
    assert "extends JobService" in job and "Notif.check(" in job
    assert "JobScheduler" in notif and "setPeriodic(PERIOD_MS)" in notif and "15L * 60L * 1000L" in notif
    assert '"qcms_alerts"' in notif and "IMPORTANCE_HIGH" in notif and "APPROVAL" in notif
    assert "p_unread_only" in notif and "ensureSession()" in notif
    assert "last_shown_at" in notif and "NotificationManager" in notif and "PendingIntent" in notif
    assert "POST_NOTIFICATIONS" in main and "SDK_INT < 33" in main
    assert "new NotifScreen(" in main and "refreshBell" in main and "onNewIntent" in main
    assert "Notif.schedule(" in read(SRC / "BootReceiver.java")
    api = read(SRC / "Api.java")
    assert "public synchronized boolean ensureSession()" in api and 'secure.get("refresh_token")' in api


def test_inbox_mark_read_and_whatsapp():
    screen = read(SRC / "NotifScreen.java")
    assert "Mark all read" in screen and '"Unread", "All"' in screen
    assert "Notif.markRead(api, null)" in screen and "Notif.open(" in screen
    assert "WhatsApp" in screen and "Notif.setWhatsapp(" in screen


def test_kpi_start_dashboard():
    kpi = read(SRC / "KpiHomeScreen.java")
    main = read(SRC / "MainActivity.java")
    assert '{"QUALITY", "SUPPLY_CHAIN", "PRODUCTION", "NPD", "MANAGEMENT"}' in kpi
    assert "AUTO_MS = 20_000L" in kpi and "IDLE_MS = 60_000L" in kpi
    assert "ObjectAnimator" in kpi and "new GenChart(" in kpi
    assert kpi.index("pending_tasks") < kpi.index('optJSONArray("cards")') < kpi.index('optJSONArray("charts")')
    assert "new HomeScreen(a)" in kpi  # the old Home stays reachable
    assert "new KpiHomeScreen(this)" in main


def test_global_search_merges_server_rows_and_modules():
    search = read(SRC / "GenSearch.java")
    screen = read(SRC / "GenSearchScreen.java")
    assert "qcms_global_search" in search and "p_query" in search
    for field in ("source_table", "record_id", "matched_field", "snippet", "web_route", "record_type", "subtitle"):
        assert f'"{field}"' in search, field
    assert "static List<Result> modules(" in search and "static List<Result> merge(" in search
    assert "GenSearch.server(" in screen and "GenSearch.everywhere(" in screen and "GenSearch.merge(" in screen
    # R39: hits open via GenTarget (child row -> parent record, then Notif.open)
    assert "Notif.open(a, r.table, r.recordId, r.route" in screen or "GenTarget.open(a, r.table, r.recordId, r.route" in screen


def test_licence_block_and_about():
    lic = read(SRC / "Licence.java")
    main = read(SRC / "MainActivity.java")
    about = read(SRC / "GenCentres.java")
    assert "is_stawn_developer" in lic and 'optBoolean("valid"' in lic and "is_company_admin" in lic
    assert "business@stawnprecision.com" in about and "GenCentres.About.EMAIL" in lic
    assert "Sign out" in lic and "About STAWN QCMS" in lic
    # never block when the RPC fails
    m = re.search(r"void checkLicence\(boolean fromBlockScreen\) \{(.*?)\n    \}", main, re.S)
    assert m and "if (err != null)" in m.group(1) and "showLicenceBlocked" in m.group(1)
    assert "Licence.detailsCard(" in about
    for k in ("plan", "used_users", "max_users", "expires_on", "licence_key_masked"):
        assert f'"{k}"' in lic, k
    assert "STAWN QCMS" in main and "Licence.company(api)" in main
