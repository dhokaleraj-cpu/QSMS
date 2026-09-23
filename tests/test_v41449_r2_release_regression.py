from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_r2_keeps_controlled_v41449_identity():
    assert text("VERSION").strip() == "4.14.49"
    manifest = text("DEPLOYMENT_MANIFEST.json")
    assert '"version": "4.14.49"' in manifest
    assert '"build": "41449-ANDROID-SINGLE-NATIVE-DRAWER-V12"' in manifest
    assert '"previous_controlled_release": "4.14.48"' in manifest


def test_r2_android_navigation_is_native_and_clickable():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    assert 'b.setText("MENU")' in java
    assert 'hamburger.setOnClickListener(v -> openDrawer())' in java
    assert 'drawerLayer.setVisibility(View.VISIBLE)' in java
    assert 'drawerLayer.setVisibility(View.GONE)' in java
    assert 'final String route = normalizedRoute.isEmpty() ? "dashboard" : normalizedRoute;' in java
    assert 'webView.loadUrl(nativeUrl(route))' in java


def test_r2_android_helper_restores_sdk_bootstrap_and_signature_guard():
    helper = text("mobile/android_qcms/BUILD_AND_INSTALL_SAMSUNG.command")
    assert "ANDROID SDK / CLI BOOTSTRAP" in helper
    assert "https://dl.google.com/android/cli/latest/" in helper
    assert "QCMS_Mobile_v${MOBILE_VERSION}_TEST.apk" in helper
    assert "APKSIGN_RC=${PIPESTATUS[0]}" in helper
    assert "APK SIGNATURE: PASS (v2 verified)" in helper


def test_r2_android_identity_and_every_release_ci_are_current():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    gradle = text("mobile/android_qcms/app/build.gradle")
    workflow = text(".github/workflows/qcms-android-test-apk.yml")
    assert "QCMSMobile/0.2.4" in java
    assert "versionCode 15" in gradle
    assert "versionName '0.2.4'" in gradle
    assert "workflow_dispatch:" in workflow
    assert "- main" in workflow
    assert "Verify native navigation source before compile" in workflow


def test_r2_docs_explain_release_regression_repair():
    notes = text("RELEASE_NOTES_v4.14.49_R2.md")
    handover = text("QCMS_NEW_CHAT_HANDOVER_v4.14.49_R2.md")
    assert "stale historical non-regression tests" in notes
    assert "608 passed" in notes
    assert "ANDROID SDK / CLI BOOTSTRAP" in handover
