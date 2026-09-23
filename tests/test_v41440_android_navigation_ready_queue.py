from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41440_release_identity_and_schema_baseline():
    assert text("VERSION").strip() in {"4.14.40", "4.14.41", "4.14.42", "4.14.43", "4.14.44", "4.14.45", "4.14.46", "4.14.47", "4.14.48", "4.14.49"}
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] in {"4.14.40", "4.14.41", "4.14.42", "4.14.43", "4.14.44", "4.14.45", "4.14.46", "4.14.47", "4.14.48", "4.14.49"}
    assert manifest["build"] in {"41440-ANDROID-NAV-READY-QUEUE-BUTTON-BRIDGE", "41441-ANDROID-LAMBDA-COMPILE-PERMANENT-FIX", "41442-LOCAL-JAVAC-OPTIONAL-CI-COMPILE-GUARD", "41443-ANDROID-STREAMLIT-SIDEBAR-NAV", "41444-ANDROID-NATIVE-MENU-SUBMENU-RESTORE", "41445-SHARED-RAW-SOURCE-LAYOUT-CONTROL", "41446-ANDROID-V12-DRAWER-PERSISTENT-AUTH", "41447-PO-WATERMARK-20-APPROVER-STAMP", "41448-PO-WATERMARK05-APPROVER-SESSION-STABILITY-ANDROID-EVERY-RELEASE", "41449-ANDROID-SINGLE-NATIVE-DRAWER-V12"}
    assert manifest["previous_controlled_release"] in {"4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43", "4.14.44", "4.14.45", "4.14.46", "4.14.47", "4.14.48"}
    assert manifest["database_schema_required"] == ("4.14.45" if manifest["version"] in {"4.14.45", "4.14.46", "4.14.47", "4.14.48", "4.14.49"} else "4.14.36")
    assert manifest["schema_change_for_v41440"] is False


def test_native_streamlit_bridge_is_button_and_switch_page_based():
    app = text("streamlit_app.py")
    for token in (
        'key="qcms_native_nav_bridge"',
        'id="qcms-native-nav-ready"',
        'st.button(f"QCMS_NAV::{_native_route}"',
        'st.switch_page(_native_page)',
        '_qcms_native_last_route',
    ):
        assert token in app
    assert 'st.page_link(_native_page, label=f"QCMS_NAV::' not in app


def test_android_queues_pending_navigation_until_streamlit_dom_ready():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    if text("VERSION").strip() == "4.14.49":
        for token in ('QCMSMobile/0.2.4', 'drawerSection', 'drawerChildButton', 'hamburger.setOnClickListener(v -> openDrawer())', 'CookieManager.getInstance().flush()'):
            assert token in java
        assert '__qcmsNativePendingRoute' not in java
    elif text("VERSION").strip() in {"4.14.46", "4.14.47", "4.14.48"}:
        assert 'drawerSection' in java
    else:
        for token in (
            'QCMSMobile/0.2.1', '__qcmsNativePendingRoute', 'QCMS_NAV_PENDING',
            'MutationObserver', '__qcmsNativeNavTimer', 'setInterval(function(){drain();},250)',
            'installMobileChromeSuppressor();', 'tryNavigate(route, token, 0)',
            "root.querySelectorAll('button,[role=", 'data-testid=',
        ):
            assert token in java
        assert 'webView.loadUrl(nativeUrl(path))' not in java
    assert 'QCMS navigation is still loading. Please try the menu again.' not in java

def test_android_v018_identity_and_footer_remains_removed():
    gradle = text("mobile/android_qcms/app/build.gradle")
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    assert any(v in gradle for v in ("versionCode 9", "versionCode 10", "versionCode 11", "versionCode 12", "versionCode 13", "versionCode 14", "versionCode 15"))
    assert any(v in gradle for v in ("versionName '0.1.8'", "versionName '0.1.9'", "versionName '0.2.0'", "versionName '0.2.1'", "versionName '0.2.2'", "versionName '0.2.3'", "versionName '0.2.4'"))
    assert 'LinearLayout bottom=new LinearLayout' not in java
    assert 'bottomButton("⌂","Home")' not in java
    assert 'bottomButton("⌕","Search")' not in java
    assert 'bottomButton("◇","Complaints")' not in java


def test_v41439_signature_fix_is_preserved():
    workflow = text(".github/workflows/qcms-android-test-apk.yml")
    helper = text("mobile/android_qcms/BUILD_AND_INSTALL_SAMSUNG.command")
    assert 'APKSIGN_RC=${PIPESTATUS[0]}' in workflow
    assert 'Verified using v2 scheme (APK Signature Scheme v2): true' in workflow
    assert 'QCMS_APK_NAME=QCMS_Mobile_v%s_TEST.apk' in workflow
    assert 'APKSIGN_RC=${PIPESTATUS[0]}' in helper
