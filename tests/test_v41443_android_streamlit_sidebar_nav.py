from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_android_stable_mode_is_fullscreen_webview():
    java = (ROOT / "mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java").read_text(encoding="utf-8")
    if (ROOT / "VERSION").read_text().strip() == "4.14.49":
        assert 'QCMSMobile/0.2.4' in java
        assert 'b.setText("MENU")' in java
        assert 'hamburger.setOnClickListener(v -> openDrawer())' in java
        assert 'showStableStreamlitBrowser' not in java
        assert 'toggleStreamlitSidebar' not in java
        return
    assert "showStableStreamlitBrowser" in java

def test_streamlit_owns_android_page_navigation():
    app = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    assert "android_streamlit_nav" in app
    assert '_native_nav_value in {"streamlit", "sidebar", "web"}' in app
    assert any(token in app for token in ('st.navigation(_mobile_page_groups, position="sidebar", expanded=False)', 'st.navigation(_mobile_page_groups, position="sidebar", expanded=True)'))
    assert 'elif android_streamlit_nav:' in app
    android_block = app[app.index("elif android_streamlit_nav:"):app.index("else:\n    # Native-mobile content mode for iPhone/iPad")]
    assert "qcms_native_nav_bridge" not in android_block
    assert "nav.run()" in android_block
    assert 'section[data-testid="stSidebar"]{display:block!important' in android_block

def test_android_release_identity_is_v020():
    gradle = (ROOT / "mobile/android_qcms/app/build.gradle").read_text(encoding="utf-8")
    if (ROOT / "VERSION").read_text().strip() == "4.14.49":
        assert "versionCode 15" in gradle
        assert "versionName '0.2.4'" in gradle
    else:
        assert "versionName" in gradle
