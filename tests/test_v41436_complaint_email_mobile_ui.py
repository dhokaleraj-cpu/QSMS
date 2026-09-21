from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41436_release_identity_and_routes():
    assert text("VERSION").strip() in {"4.14.36", "4.14.37", "4.14.38"}
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] in {"4.14.36", "4.14.37", "4.14.38"}
    assert manifest["build"] in {"41436-COMPLAINT-EMAIL-REGISTERS-REMINDERS-MOBILE-DRAWER", "41437-MOBILE-FULL-NAV-COMPLAINT-CARDS-PO-APPROVAL-DRAFT-EMAIL", "41438-ANDROID-NAV-SESSION-BRIDGE-FOOTER-REMOVE"}
    app = text("streamlit_app.py")
    for route in ("customer-complaint-register", "supplier-complaint-register", "complaint-email-settings"):
        assert route in app


def test_v41436_complaint_register_and_confirmed_email_contract():
    source = text("app_pages/complaints.py")
    for token in (
        "def render_customer_register", "def render_supplier_register", "def render_email_configuration",
        "CUSTOMER_COMPLAINT_CREATED", "SUPPLIER_COMPLAINT_CREATED", "COMPLAINT_FOLLOWUP_REMINDER",
        "notification_confirmation", "record_email_sender", "CONFIRMED EMAIL SENDING",
        "COMPLAINT EMAIL DELIVERY REGISTER", "Customer / Supplier Too",
    ):
        assert token in source


def test_v41436_complaint_schedule_migration_and_worker():
    migration = text("supabase/migrations/20260921190000_qcms_v41436_complaint_email_register_mobile.sql")
    worker = text("supabase/functions/qcms-overdue-notifier/index.ts")
    for token in (
        "CUSTOMER_COMPLAINT_CREATED", "SUPPLIER_COMPLAINT_CREATED", "COMPLAINT_OVERDUE_REMINDER",
        "COMPLAINT_CUSTOMER_OPEN_OVERDUE", "COMPLAINT_SUPPLIER_OPEN_OVERDUE", "COMPLAINT_FOLLOWUP_DUE",
    ):
        assert token in migration
    for token in ("COMPLAINT_CUSTOMER_OPEN_OVERDUE", "COMPLAINT_SUPPLIER_OPEN_OVERDUE", "COMPLAINT_FOLLOWUP_DUE", "run_every_days", "cadenceDays"):
        assert token in worker


def test_v41436_android_reference_video_style_navigation():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    gradle = text("mobile/android_qcms/app/build.gradle")
    assert any(v in gradle for v in ("versionName '0.1.4'", "versionName '0.1.5'", "versionName '0.1.6'"))
    for token in ("openDrawer", "closeDrawer", "drawerPanel", "global-search", "complaints-home", "stawn_icon"):
        assert token in java
    assert (ROOT / "mobile/android_qcms/app/src/main/res/drawable-nodpi/stawn_icon.png").exists()


def test_v41436_ios_reference_video_style_navigation():
    content = text("mobile/ios_qcms/QCMSMobileIOS/ContentView.swift")
    web = text("mobile/ios_qcms/QCMSMobileIOS/QCMSWebView.swift")
    project = text("mobile/ios_qcms/QCMSMobileIOS.xcodeproj/project.pbxproj")
    for token in ("drawerOpen", "qcmsNavigate", "global-search", "complaints-home", "AppIconPreview", "Home", "Search", "Complaints"):
        assert token in content
    assert any(v in web for v in ("QCMSMobileIOS/0.1.1", "QCMSMobileIOS/0.1.2"))
    assert any(v in project for v in ("MARKETING_VERSION = 0.1.1", "MARKETING_VERSION = 0.1.2"))
    assert "TARGETED_DEVICE_FAMILY = \"1,2\"" in project
