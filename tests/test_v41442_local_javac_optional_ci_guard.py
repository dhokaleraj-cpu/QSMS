from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_v41442_identity_and_no_schema_change():
    assert text("VERSION").strip() in {"4.14.42", "4.14.43", "4.14.44"}
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] in {"4.14.42", "4.14.43", "4.14.44"}
    assert manifest["build"] in {"41442-LOCAL-JAVAC-OPTIONAL-CI-COMPILE-GUARD", "41443-ANDROID-STREAMLIT-SIDEBAR-NAV", "41444-ANDROID-NATIVE-MENU-SUBMENU-RESTORE"}
    expected_previous = {"4.14.42": "4.14.41", "4.14.43": "4.14.42", "4.14.44": "4.14.43"}
    assert manifest["previous_controlled_release"] == expected_previous[manifest["version"]]
    assert manifest["schema_change_for_v41442"] is False

def test_local_javac_regression_is_capability_gated():
    guard = text("tests/test_v41441_android_lambda_compile_fix.py")
    assert 'def _functional_javac_command()' in guard
    assert '/usr/libexec/java_home' in guard
    assert 'Path("/usr/bin/javac")' in guard
    assert 'pytest.skip(' in guard

def test_android_ci_still_performs_authoritative_java_gradle_compile():
    workflow = text(".github/workflows/qcms-android-test-apk.yml")
    assert "actions/setup-java@v4" in workflow
    assert "java-version: '17'" in workflow
    assert ":app:assembleDebug :app:lintDebug" in workflow
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    assert 'final String route = normalizedRoute.isEmpty() ? "dashboard" : normalizedRoute;' in java
