from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_release_identity_and_schema_baseline():
    assert text("VERSION").strip() == "4.14.49"
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] == "4.14.49"
    assert manifest["build"] == "41449-ANDROID-SINGLE-NATIVE-DRAWER-V12"
    assert manifest["database_schema_required"] == "4.14.45"
    assert manifest["database_migration_required"] is False
    assert manifest["schema_change_for_v41449"] is False


def test_android_has_exactly_one_native_navigation_architecture():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    assert 'MOBILE_USER_AGENT = "QCMSMobile/0.2.4"' in java
    assert java.count("private void showBrowser(String url)") == 1
    for obsolete in (
        "showStableStreamlitBrowser",
        "toggleStreamlitSidebar",
        "installStreamlitSidebarController",
        "tryNavigate(",
        "installMobileChromeSuppressor",
        "__qcmsNativeNavigate",
        "__qcmsNativePendingRoute",
        "QCMS_NAV_PENDING",
        "USE_STREAMLIT_WEB_NAV",
    ):
        assert obsolete not in java


def test_native_menu_is_visible_outside_webview_and_click_opens_drawer():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    for token in (
        'b.setText("MENU")',
        'R.drawable.ic_qcms_menu',
        'hamburger.setOnClickListener(v -> openDrawer())',
        'drawerLayer.setVisibility(View.VISIBLE)',
        'drawerLayer.bringToFront()',
        'top.setVisibility(View.VISIBLE)',
        'top.bringToFront()',
        'main.addView(top',
        'main.addView(webView',
    ):
        assert token in java
    assert java.index('main.addView(top') < java.index('main.addView(webView')
    assert (ROOT / "mobile/android_qcms/app/src/main/res/drawable/ic_qcms_menu.xml").exists()


def test_native_drawer_has_required_groups_submenus_and_autohide():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    for group in (
        "Dashboard", "Masters", "Supply Chain", "RMTC", "Inward", "OSP",
        "Quality / Inspections", "NPD / APQP", "Complaints", "Search",
        "Records", "Reports", "Templates", "Admin",
    ):
        assert f'"{group}"' in java
    for route in (
        "part-entry", "supply-purchase-orders", "supply-po-approval", "rmtc-entry",
        "osp-dimensional", "inspection-layout-entry", "customer-complaint",
        "global-search", "reports-home", "user-access",
    ):
        assert f'"{route}"' in java
    assert 'closeDrawer();\n            navigate(path);' in java
    assert 'drawerScrim.setOnClickListener(v -> closeDrawer())' in java
    assert 'if (drawerLayer != null && drawerLayer.getVisibility() == View.VISIBLE)' in java


def test_server_native_mode_is_generic_not_android_version_hardcoded():
    app = text("streamlit_app.py")
    assert '_native_android = "QCMSMobile/" in _native_user_agent' in app
    assert '_android_streamlit_requested = _native_nav_value in {"streamlit", "sidebar", "web"}' in app
    assert 'android_native_drawer = bool(native_mobile and _native_android and not _android_streamlit_requested)' in app
    detection = app[app.index('_native_android ='):app.index('# Keep an explicit route-to-Page registry')]
    assert 'QCMSMobile/0.2.2' not in detection
    assert 'QCMSMobile/0.2.3' not in detection
    assert 'QCMSMobile/0.2.4' not in detection


def test_install_helper_verifies_and_launches_exact_package():
    helper = text("mobile/android_qcms/BUILD_AND_INSTALL_SAMSUNG.command")
    for token in (
        'PACKAGE="com.fourstar.qcms.test"',
        'versionName=$MOBILE_VERSION',
        'versionCode=${MOBILE_CODE}',
        'shell am force-stop "$PACKAGE"',
        'shell am start -n "$PACKAGE/$ACTIVITY"',
        'maroon top bar must show MENU',
    ):
        assert token in helper


def test_android_identity_and_github_build_every_release():
    gradle = text("mobile/android_qcms/app/build.gradle")
    manifest = text("mobile/android_qcms/app/src/main/AndroidManifest.xml")
    strings = text("mobile/android_qcms/app/src/main/res/values/strings.xml")
    workflow = text(".github/workflows/qcms-android-test-apk.yml")
    assert "versionCode 15" in gradle
    assert "versionName '0.2.4'" in gradle
    assert 'android:label="@string/app_name"' in manifest
    assert 'QCMS Mobile 0.2.4' in strings
    assert 'workflow_dispatch:' in workflow
    assert 'branches:' in workflow and '- main' in workflow
    assert 'Verify native navigation source before compile' in workflow
    assert "Legacy dual-navigation code detected" in workflow
    assert 'QCMS-Mobile-TEST-APK' in workflow


def test_bottom_footer_remains_removed():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    assert 'bottomButton(' not in java
    assert 'LinearLayout bottom=' not in java
