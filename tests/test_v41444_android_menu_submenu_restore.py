from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41444_release_identity_and_database_baseline():
    assert text("VERSION").strip() == "4.14.44"
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] == "4.14.44"
    assert manifest["build"] == "41444-ANDROID-NATIVE-MENU-SUBMENU-RESTORE"
    assert manifest["previous_controlled_release"] == "4.14.43"
    assert manifest["database_schema_required"] == "4.14.36"
    assert manifest["schema_change_for_v41444"] is False


def test_android_v021_restores_permanent_native_menu_button():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    gradle = text("mobile/android_qcms/app/build.gradle")
    assert "QCMSMobile/0.2.1" in java
    assert "versionCode 12" in gradle
    assert "versionName '0.2.1'" in gradle
    stable = java[java.index("private void showStableStreamlitBrowser"):java.index("private void showBrowser(String url)")]
    for token in (
        'Button hamburger = iconButton("☰", 22)',
        'hamburger.setOnClickListener(v -> toggleStreamlitSidebar())',
        "installStreamlitSidebarController()",
        "window.__qcmsToggleSidebar",
        "QCMS_MENU_PENDING",
        'stSidebar',
    ):
        assert token in stable
    assert "navigate(" not in stable
    assert "webView.loadUrl(nativeUrl(path))" not in java


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
