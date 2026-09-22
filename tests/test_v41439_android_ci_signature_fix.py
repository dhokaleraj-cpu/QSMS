from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41439_release_identity_and_no_schema_change():
    assert text("VERSION").strip() == "4.14.39"
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] == "4.14.39"
    assert manifest["build"] == "41439-ANDROID-CI-SIGNATURE-PERMANENT-FIX"
    assert manifest["previous_controlled_release"] == "4.14.38"
    assert manifest["database_schema_required"] == "4.14.36"
    assert manifest["schema_change_for_v41439"] is False


def test_android_ci_derives_version_and_does_not_hardcode_old_apk_names():
    workflow = text(".github/workflows/qcms-android-test-apk.yml")
    for token in (
        "Read Android build identity",
        "QCMS_MOBILE_VERSION",
        "QCMS_MOBILE_VERSION_CODE",
        "QCMS_APK_NAME=QCMS_Mobile_v%s_TEST.apk",
        "ACTUAL_VERSION",
        "ACTUAL_CODE",
        "QCMS-Mobile-TEST-APK",
    ):
        assert token in workflow
    for stale in (
        "QCMS_Mobile_v0.1.4_TEST.apk",
        "QCMS_Mobile_v0.1.5_TEST.apk",
        "QCMS_Mobile_v0.1.6_TEST.apk",
        "versionName='0.1.4'",
        "versionName='0.1.5'",
        "versionName='0.1.6'",
    ):
        assert stale not in workflow


def test_ci_captures_real_apksigner_exit_and_requires_v2_only():
    workflow = text(".github/workflows/qcms-android-test-apk.yml")
    assert 'APKSIGN_RC=${PIPESTATUS[0]}' in workflow
    assert 'Verified using v2 scheme (APK Signature Scheme v2): true' in workflow
    assert "Optional v1/v3/v3.1/v4/SourceStamp" in workflow
    assert "-Werr" not in workflow


def test_local_android_builder_has_same_permanent_signature_guard():
    helper = text("mobile/android_qcms/BUILD_AND_INSTALL_SAMSUNG.command")
    for token in (
        'MOBILE_VERSION="$(sed -n',
        'QCMS_Mobile_v${MOBILE_VERSION}_TEST.apk',
        'APKSIGN_RC=${PIPESTATUS[0]}',
        'Verified using v2 scheme (APK Signature Scheme v2): true',
        'zipalign',
        'APK SIGNATURE: PASS (v2 verified)',
    ):
        assert token in helper


def test_android_v017_preserves_session_safe_navigation_and_removed_footer():
    gradle = text("mobile/android_qcms/app/build.gradle")
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    assert "versionCode 8" in gradle
    assert "versionName '0.1.7'" in gradle
    assert "QCMSMobile/0.1.7" in java
    assert "__qcmsNativeNavigate" in java
    assert "webView.loadUrl(nativeUrl(path))" not in java
    assert "LinearLayout bottom=new LinearLayout" not in java
