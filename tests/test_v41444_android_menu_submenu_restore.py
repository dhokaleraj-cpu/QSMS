from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41444_release_identity_and_database_baseline():
    version = text("VERSION").strip()
    assert version in {"4.14.44", "4.14.45", "4.14.46", "4.14.47", "4.14.48", "4.14.49"}
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] == version
    if version == "4.14.44":
        assert manifest["build"] == "41444-ANDROID-NATIVE-MENU-SUBMENU-RESTORE"
        assert manifest["previous_controlled_release"] == "4.14.43"
        assert manifest["database_schema_required"] == "4.14.36"
    elif version == "4.14.45":
        assert manifest["build"] == "41445-SHARED-RAW-SOURCE-LAYOUT-CONTROL", "41446-ANDROID-V12-DRAWER-PERSISTENT-AUTH"
        assert manifest["previous_controlled_release"] == "4.14.44"
        assert manifest["database_schema_required"] == "4.14.45"
        assert manifest["database_migration_required"] is True
    elif version == "4.14.46":
        assert manifest["build"] == "41446-ANDROID-V12-DRAWER-PERSISTENT-AUTH"
        assert manifest["previous_controlled_release"] == "4.14.45"
        assert manifest["database_schema_required"] == "4.14.45"
    elif version == "4.14.47":
        assert manifest["build"] == "41447-PO-WATERMARK-20-APPROVER-STAMP"
        assert manifest["previous_controlled_release"] == "4.14.46"
        assert manifest["database_schema_required"] == "4.14.45"
        assert manifest["database_migration_required"] is False
    elif version == "4.14.48":
        assert manifest["build"] == "41448-PO-WATERMARK05-APPROVER-SESSION-STABILITY-ANDROID-EVERY-RELEASE"
        assert manifest["previous_controlled_release"] == "4.14.47"
        assert manifest["database_schema_required"] == "4.14.45"
        assert manifest["database_migration_required"] is False
    else:
        assert version == "4.14.49"
        assert manifest["build"] == "41449-ANDROID-SINGLE-NATIVE-DRAWER-V12"
        assert manifest["previous_controlled_release"] == "4.14.48"
        assert manifest["database_schema_required"] == "4.14.45"
        assert manifest["database_migration_required"] is False
    assert manifest["schema_change_for_v41444"] is False


def test_android_v021_restores_permanent_native_menu_button():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    gradle = text("mobile/android_qcms/app/build.gradle")
    if text("VERSION").strip() == "4.14.49":
        assert "QCMSMobile/0.2.4" in java
        assert "versionCode 15" in gradle
        assert "versionName '0.2.4'" in gradle
        assert 'b.setText("MENU")' in java
        assert 'hamburger.setOnClickListener(v -> openDrawer())' in java
        assert "showStableStreamlitBrowser" not in java
        assert "toggleStreamlitSidebar" not in java
        return
    assert "drawerSection" in java

def test_streamlit_sidebar_and_android_submenu_are_visible_and_official():
    app = text("streamlit_app.py")
    assert 'st.navigation(_mobile_page_groups, position="sidebar", expanded=True)' in app
    android_block = app[app.index("elif android_streamlit_nav:"):app.index("else:\n    # Native-mobile content mode for iPhone/iPad")]
    for token in (
        '[data-testid="collapsedControl"]{display:flex!important',
        'stSidebar',
        '[class*="st-key-fsi_module_subnav_"]{display:block!important',
        'module_submenu(current_module, *MODULE_SUBMENUS[current_module], max_columns=2)',
        "nav.run()",
    ):
        assert token in android_block
    assert "qcms_native_nav_bridge" not in android_block


def test_android_footer_remains_removed_and_signature_fix_is_preserved():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    workflow = text(".github/workflows/qcms-android-test-apk.yml")
    helper = text("mobile/android_qcms/BUILD_AND_INSTALL_SAMSUNG.command")
    assert 'LinearLayout bottom=new LinearLayout' not in java
    assert 'bottomButton("⌂","Home")' not in java
    assert 'APKSIGN_RC=${PIPESTATUS[0]}' in workflow
    assert 'Verified using v2 scheme (APK Signature Scheme v2): true' in workflow
    assert 'APKSIGN_RC=${PIPESTATUS[0]}' in helper
