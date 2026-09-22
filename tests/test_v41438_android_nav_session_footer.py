from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41438_release_identity_and_schema_baseline():
    assert text("VERSION").strip() in {"4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43", "4.14.44", "4.14.45", "4.14.46", "4.14.47"}
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] in {"4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43", "4.14.44", "4.14.45", "4.14.46", "4.14.47"}
    expected_builds = {
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
        "4.14.46": "41446-ANDROID-V12-DRAWER-PERSISTENT-AUTH",
        "4.14.47": "41447-PO-WATERMARK-20-APPROVER-STAMP",
    }
    assert manifest["build"] == expected_builds[manifest["version"]]
    assert manifest["database_schema_required"] == ("4.14.45" if manifest["version"] in {"4.14.45", "4.14.46", "4.14.47"} else "4.14.36")
    assert manifest["schema_change_for_v41438"] is False


def test_streamlit_native_navigation_bridge_uses_session_safe_controls():
    app = text("streamlit_app.py")
    for token in (
        'key="qcms_native_nav_bridge"',
        'st.button(f"QCMS_NAV::{_native_route}"',
        "st.switch_page(_native_page)",
        "QCMS_NAV::",
        'st.query_params.get("native_mobile"',
        'st.session_state["_qcms_native_mobile"]',
    ):
        assert token in app


def test_android_drawer_navigation_preserves_webview_session():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    for token in (
        "__qcmsNativeNavigate",
        "evaluateJavascript",
        "QCMS_NAV_OK",
        "tryNavigate",
        "drawerSection",
        "drawerChildButton",
    ):
        assert token in java
    assert any(v in java for v in ("QCMSMobile/0.1.6", "QCMSMobile/0.1.7", "QCMSMobile/0.1.8", "QCMSMobile/0.1.9", "QCMSMobile/0.2.0", "QCMSMobile/0.2.1", "QCMSMobile/0.2.2"))
    assert 'webView.loadUrl(nativeUrl(""))' in java
    if text("VERSION").strip() in {"4.14.46", "4.14.47"}:
        # v4.14.46 restores the v1.2 native drawer and deliberately uses canonical
        # route loads; persistent Supabase session recovery prevents re-login.
        assert "webView.loadUrl(nativeUrl(route))" in java
        assert "CookieManager.getInstance().flush()" in java
    else:
        # v4.14.38-v4.14.45 kept navigation inside one in-memory Streamlit session.
        assert "webView.loadUrl(nativeUrl(path))" not in java


def test_android_fixed_footer_and_hard_refresh_removed():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    assert "LinearLayout bottom=new LinearLayout" not in java
    assert 'bottomButton("⌂","Home")' not in java
    assert 'bottomButton("⌕","Search")' not in java
    assert 'bottomButton("◇","Complaints")' not in java
    assert "refresh.setOnClickListener" not in java
    assert "hamburger.setOnClickListener" in java


def test_android_v016_build_helpers_are_consistent():
    gradle = text("mobile/android_qcms/app/build.gradle")
    helper = text("mobile/android_qcms/BUILD_AND_INSTALL_SAMSUNG.command")
    readme = text("mobile/android_qcms/README_ANDROID.md")
    assert any(v in gradle for v in ("versionCode 7", "versionCode 8", "versionCode 9", "versionCode 10", "versionCode 11", "versionCode 12", "versionCode 13"))
    assert any(v in gradle for v in ("versionName '0.1.6'", "versionName '0.1.7'", "versionName '0.1.8'", "versionName '0.1.9'", "versionName '0.2.0'", "versionName '0.2.1'", "versionName '0.2.2'"))
    assert "QCMS_Mobile_v${MOBILE_VERSION}_TEST.apk" in helper or "QCMS_Mobile_v0.1.6_TEST.apk" in helper
    assert any(v in readme for v in ("0.1.6", "0.1.7", "0.1.8", "0.1.9", "0.2.0", "0.2.1", "0.2.2"))
