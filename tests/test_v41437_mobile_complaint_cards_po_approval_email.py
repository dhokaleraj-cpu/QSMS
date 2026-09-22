from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

def test_v41437_release_identity():
    version = text("VERSION").strip()
    assert version in {"4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43", "4.14.44", "4.14.45", "4.14.46", "4.14.47", "4.14.48"}
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] == version
    expected = {
        "4.14.37": "41437-MOBILE-FULL-NAV-COMPLAINT-CARDS-PO-APPROVAL-DRAFT-EMAIL",
        "4.14.38": "41438-ANDROID-NAV-SESSION-BRIDGE-FOOTER-REMOVE",
        "4.14.39": "41439-ANDROID-CI-SIGNATURE-PERMANENT-FIX",
        "4.14.40": "41440-ANDROID-NAV-READY-QUEUE-BUTTON-BRIDGE",
        "4.14.41": "41441-ANDROID-LAMBDA-COMPILE-PERMANENT-FIX",
        "4.14.42": "41442-LOCAL-JAVAC-OPTIONAL-CI-COMPILE-GUARD",
        "4.14.43": "41443-ANDROID-STREAMLIT-SIDEBAR-NAV",
        "4.14.44": "41444-ANDROID-NATIVE-MENU-SUBMENU-RESTORE",
        "4.14.45": "41445-SHARED-RAW-SOURCE-LAYOUT-CONTROL",
        "4.14.46": "41446-ANDROID-V12-DRAWER-PERSISTENT-AUTH",
        "4.14.47": "41447-PO-WATERMARK-20-APPROVER-STAMP",
        "4.14.48": "41448-PO-WATERMARK05-APPROVER-SESSION-STABILITY-ANDROID-EVERY-RELEASE",
    }
    assert manifest["build"] == expected[version]

def test_complaint_dashboard_cards_and_email_attachments_external_copy():
    src = text("app_pages/complaints.py")
    notify = text("core/notification_service.py")
    for token in ("complaint-card-grid", "complaint-card", "complaint-stage-mini", "Send copy to", "include_generated_pdf=True", "include_record_attachments=True", "party_email"):
        assert token in src
    assert '"quality_complaints": "QUALITY_COMPLAINT"' in notify
    assert 'related_table == "quality_complaints"' in notify
    assert "_complaint_pdf" in notify
    assert 'enriched.get("party_email")' in notify

def test_pending_po_approval_grid_count_and_draft_pdf_email():
    src = text("app_pages/supply_chain.py")
    for token in ("def _pending_po_approval_rows", "PENDING APPROVAL WORKLIST", '"Pending Approval", "value": len(pending_rows)', "Email Selected Draft POs to Approver", "Confirm & Email Draft POs for Approval", '"PO_APPROVAL_PENDING"', "include_generated_pdf=True", "include_record_attachments=True", "PENDING APPROVAL watermarked draft PO PDF"):
        assert token in src

def test_native_streamlit_content_only_mode_replaces_web_rails():
    app = text("streamlit_app.py")
    for token in ('st.query_params.get("native_mobile"', 'st.session_state["_qcms_native_mobile"]', "if not native_mobile:", "Native-mobile content mode", ".st-key-fsi_left_rail", '[class*="st-key-fsi_module_subnav_"]', "nav.run()"):
        assert token in app

def test_android_full_expandable_navigation_and_fixed_bottom_bar():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    gradle = text("mobile/android_qcms/app/build.gradle")
    version = text("VERSION").strip()
    if version == "4.14.37":
        assert "versionName '0.1.5'" in gradle
        for token in ("QCMSMobile/0.1.5", "drawerSection", "drawerChildButton", '"Approval / Confirmation"', '"Customer Register"', '"Supplier Register"', '"Email / Reminders"', "native_mobile", '"Home"', '"Search"', '"Complaints"'):
            assert token in java
    elif version == "4.14.38":
        assert "versionName '0.1.6'" in gradle
    elif version == "4.14.39":
        assert "versionName '0.1.7'" in gradle
        for token in ("QCMSMobile/0.1.7", "drawerSection", "drawerChildButton", '"Approval / Confirmation"', '"Customer Register"', '"Supplier Register"', '"Email / Reminders"', "native_mobile", "__qcmsNativeNavigate"):
            assert token in java
        assert "LinearLayout bottom=new LinearLayout" not in java
    elif version == "4.14.40":
        assert "versionName '0.1.8'" in gradle
        for token in ("QCMSMobile/0.1.8", "drawerSection", "drawerChildButton", '"Approval / Confirmation"', '"Customer Register"', '"Supplier Register"', '"Email / Reminders"', "native_mobile", "__qcmsNativeNavigate", "QCMS_NAV_PENDING"):
            assert token in java
        assert "LinearLayout bottom=new LinearLayout" not in java
    elif version in {"4.14.41", "4.14.42"}:
        assert "versionName '0.1.9'" in gradle
        for token in ("QCMSMobile/0.1.9",
                      "drawerSection", "drawerChildButton", '"Approval / Confirmation"', '"Customer Register"', '"Supplier Register"', '"Email / Reminders"', "native_mobile", "__qcmsNativeNavigate", "QCMS_NAV_PENDING"):
            assert token in java
        assert "LinearLayout bottom=new LinearLayout" not in java
    elif version == "4.14.43":
        assert "versionName '0.2.0'" in gradle
        for token in ("QCMSMobile/0.2.0", "drawerSection", "drawerChildButton", '"Approval / Confirmation"', '"Customer Register"', '"Supplier Register"', '"Email / Reminders"', "native_mobile", "__qcmsNativeNavigate", "QCMS_NAV_PENDING"):
            assert token in java
    elif version in {"4.14.44", "4.14.45"}:
        assert "versionName '0.2.1'" in gradle
        for token in ("QCMSMobile/0.2.1", "drawerSection", "drawerChildButton", '"Approval / Confirmation"', '"Customer Register"', '"Supplier Register"', '"Email / Reminders"', "native_mobile", "toggleStreamlitSidebar"):
            assert token in java
        assert "LinearLayout bottom=new LinearLayout" not in java
    else:
        assert version in {"4.14.46", "4.14.47", "4.14.48"}
        assert "versionName '0.2.3'" in gradle
        for token in ("QCMSMobile/0.2.3", "drawerSection", "drawerChildButton", '"Approval / Confirmation"', '"Customer Register"', '"Supplier Register"', '"Email / Reminders"', "native_mobile", 'appendQueryParameter("native_nav","native")', "closeDrawer(); navigate(path)"):
            assert token in java
        assert "LinearLayout bottom=new LinearLayout" not in java

def test_ios_full_expandable_navigation_and_fixed_bottom_bar():
    content = text("mobile/ios_qcms/QCMSMobileIOS/ContentView.swift")
    web = text("mobile/ios_qcms/QCMSMobileIOS/QCMSWebView.swift")
    project = text("mobile/ios_qcms/QCMSMobileIOS.xcodeproj/project.pbxproj")
    assert "QCMSMobileIOS/0.1.2" in web
    assert "MARKETING_VERSION = 0.1.2" in project
    for token in ("expandedSections", "drawerSection", '"Approval / Confirmation"', '"Customer Register"', '"Supplier Register"', '"Email / Reminders"', 'navButton("house", "Home", "dashboard")', 'Text("Search")', 'navButton("exclamationmark.bubble", "Complaints", "complaints-home")'):
        assert token in content
    assert 'URLQueryItem(name: "native_mobile", value: "1")' in web

def test_complaint_reminder_worker_preserves_aliases_and_cadence():
    worker = text("supabase/functions/qcms-overdue-notifier/index.ts")
    for token in ("COMPLAINT_CUSTOMER_OPEN_OVERDUE", "COMPLAINT_SUPPLIER_OPEN_OVERDUE", "COMPLAINT_FOLLOWUP_DUE", "daysBetween", "cadenceDays", "run_every_days"):
        assert token in worker
