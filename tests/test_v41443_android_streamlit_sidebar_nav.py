from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_android_stable_mode_is_fullscreen_webview():
    java = (ROOT / "mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java").read_text(encoding="utf-8")
    assert "USE_STREAMLIT_WEB_NAV = true" in java
    assert "showStableStreamlitBrowser" in java
    assert "QCMSMobile/0.2.0" in java
    assert 'appendQueryParameter("native_nav","streamlit")' in java
    stable = java[java.index("private void showStableStreamlitBrowser"):java.index("private void showBrowser(String url)")]
    assert "drawerLayer" not in stable
    assert "installMobileChromeSuppressor" not in stable
    assert "navigate(" not in stable

def test_streamlit_owns_android_page_navigation():
    app = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    assert "android_streamlit_nav" in app
    assert '_native_nav_value in {"streamlit", "sidebar", "web"}' in app
    assert 'st.navigation(_mobile_page_groups, position="sidebar", expanded=False)' in app
    assert 'elif android_streamlit_nav:' in app
    android_block = app[app.index("elif android_streamlit_nav:"):app.index("else:\n    # Native-mobile content mode for iPhone/iPad")]
    assert "qcms_native_nav_bridge" not in android_block
    assert "nav.run()" in android_block
    assert 'section[data-testid="stSidebar"]{display:block!important}' in android_block

def test_android_release_identity_is_v020():
    gradle = (ROOT / "mobile/android_qcms/app/build.gradle").read_text(encoding="utf-8")
    assert "versionCode 11" in gradle
    assert "versionName '0.2.0'" in gradle
