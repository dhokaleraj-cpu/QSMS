from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41438_release_identity_and_schema_baseline():
    assert text("VERSION").strip() == "4.14.38"
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] == "4.14.38"
    assert manifest["build"] == "41438-ANDROID-NAV-SESSION-BRIDGE-FOOTER-REMOVE"
    assert manifest["database_schema_required"] == "4.14.36"
    assert manifest["schema_change_for_v41438"] is False


def test_streamlit_native_navigation_bridge_uses_page_link():
    app = text("streamlit_app.py")
    for token in (
        'key="qcms_native_nav_bridge"',
        "st.page_link(_native_page",
        "QCMS_NAV::",
        'st.query_params.get("native_mobile"',
        'st.session_state["_qcms_native_mobile"]',
    ):
        assert token in app


def test_android_drawer_navigation_preserves_webview_session():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    for token in (
        "QCMSMobile/0.1.6",
        "__qcmsNativeNavigate",
        "evaluateJavascript",
        "QCMS_NAV_OK",
        "tryNavigate",
        "drawerSection",
        "drawerChildButton",
    ):
        assert token in java
    # Initial app load is valid. Drawer/menu navigation must not hard-load a new URL,
    # because that would discard Streamlit's in-memory authenticated session.
    assert 'webView.loadUrl(nativeUrl(""))' in java
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
    assert "versionCode 7" in gradle
    assert "versionName '0.1.6'" in gradle
    assert "QCMS_Mobile_v0.1.6_TEST.apk" in helper
    assert "0.1.6" in readme
