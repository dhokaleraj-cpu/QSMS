from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_android_v022_restores_v12_style_drawer_and_auto_hides():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    gradle = text("mobile/android_qcms/app/build.gradle")
    assert "QCMSMobile/0.2.2" in java
    assert "versionName '0.2.2'" in gradle
    assert "versionCode 13" in gradle
    assert "USE_STREAMLIT_WEB_NAV = false" in java
    assert "drawerSection" in java and "drawerChildButton" in java
    assert "drawerLayer.setVisibility(View.GONE)" in java
    assert "closeDrawer(); navigate(path)" in java
    for section in ("Masters", "Supply Chain", "RMTC", "Inward", "OSP", "Quality / Inspections", "NPD / APQP", "Complaints", "Reports", "Admin"):
        assert f'\"{section}\"' in java


def test_streamlit_restores_persistent_login_before_login_gate():
    app = text("streamlit_app.py")
    auth = text("core/auth.py")
    assert "restore_persistent_login()" in app
    assert app.index("restore_persistent_login()") < app.index("render_login(); st.stop()")
    assert "service_persistent_auth_bridge" in app
    assert "sync_persistent_login_browser" in app
    assert "st.components.v2.component" in auth
    assert "window.localStorage.getItem(key)" in auth
    assert "window.localStorage.setItem(key, payload)" in auth
    assert "window.localStorage.removeItem(key)" in auth
    assert "client.auth.set_session(access, refresh)" in auth
    assert "_PERSIST_STORAGE_PENDING" in auth
    assert "_qcms_auth_restore_pending" in auth
    assert "_qcms_clear_auth_browser" in auth
    # Legacy cookie fallback is intentionally retained for upgrade compatibility.
    assert "SameSite=Strict" in auth
    # Persistent credentials must never be transported in route query parameters.
    assert "access_token\",\"" not in text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")


def test_android_navigation_uses_canonical_route_and_persists_webview_storage():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    assert 'appendQueryParameter("native_mobile","1")' in java
    assert 'appendQueryParameter("native_nav","native")' in java
    assert "webView.loadUrl(nativeUrl(route))" in java
    assert "ws.setDomStorageEnabled(true)" in java or "ws.setDomStorageEnabled(true);" in java
    assert "CookieManager.getInstance().flush()" in java
    assert "closeDrawer();" in java


def test_native_drawer_streamlit_mode_is_content_only_and_no_footer():
    app = text("streamlit_app.py")
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    assert "elif android_native_drawer:" in app
    native_block = app.split("elif android_native_drawer:", 1)[1].split("elif android_streamlit_nav:", 1)[0]
    assert 'section[data-testid="stSidebar"]' in native_block
    assert "display:none!important" in native_block
    assert "nav.run()" in native_block
    assert 'bottomButton("⌂","Home")' not in java
    assert "LinearLayout bottom=new LinearLayout" not in java


def test_v41446_release_keeps_database_schema_at_v41445():
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] == "4.14.46"
    assert manifest["build"] == "41446-ANDROID-V12-DRAWER-PERSISTENT-AUTH"
    assert manifest["database_schema_required"] == "4.14.45"
    assert manifest["database_migration_required"] is False
