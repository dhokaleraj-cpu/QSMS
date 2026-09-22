from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import textwrap
import pytest

ROOT = Path(__file__).resolve().parents[1]

def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41441_release_identity_and_no_schema_change():
    assert text("VERSION").strip() in {"4.14.41", "4.14.42", "4.14.43", "4.14.44", "4.14.45"}
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] in {"4.14.41", "4.14.42", "4.14.43", "4.14.44", "4.14.45"}
    assert manifest["build"] in {"41441-ANDROID-LAMBDA-COMPILE-PERMANENT-FIX", "41442-LOCAL-JAVAC-OPTIONAL-CI-COMPILE-GUARD", "41443-ANDROID-STREAMLIT-SIDEBAR-NAV", "41444-ANDROID-NATIVE-MENU-SUBMENU-RESTORE", "41445-SHARED-RAW-SOURCE-LAYOUT-CONTROL"}
    assert manifest["previous_controlled_release"] in {"4.14.40", "4.14.41", "4.14.42", "4.14.43", "4.14.44", "4.14.45"}
    assert manifest["schema_change_for_v41441"] is False


def test_android_route_captured_as_final_after_normalization():
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    assert 'String normalizedRoute = path == null ? "dashboard" : path.trim();' in java
    assert 'final String route = normalizedRoute.isEmpty() ? "dashboard" : normalizedRoute;' in java
    assert 'String route = path == null ? "dashboard" : path.trim();' not in java
    assert 'if(route.isEmpty()) route = "dashboard";' not in java
    assert 'postDelayed(() -> tryNavigate(route, token, 0), 60)' in java
    assert any(v in java for v in ('QCMSMobile/0.1.9', 'QCMSMobile/0.2.0', 'QCMSMobile/0.2.1'))


def _functional_javac_command():
    candidates = []
    java_home = os.environ.get("JAVA_HOME", "").strip()
    if java_home:
        candidates.append(str(Path(java_home) / "bin" / "javac"))
    if sys.platform == "darwin":
        helper = Path("/usr/libexec/java_home")
        if helper.exists():
            home = subprocess.run([str(helper)], capture_output=True, text=True)
            if home.returncode == 0 and home.stdout.strip():
                candidates.append(str(Path(home.stdout.strip()) / "bin" / "javac"))
        path_javac = shutil.which("javac")
        # /usr/bin/javac is only an Apple launcher when no JDK is installed; do not invoke it.
        if path_javac and Path(path_javac).resolve() != Path("/usr/bin/javac"):
            candidates.append(path_javac)
    else:
        path_javac = shutil.which("javac")
        if path_javac:
            candidates.append(path_javac)
    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen or not Path(candidate).exists():
            continue
        seen.add(candidate)
        probe = subprocess.run([candidate, "-version"], capture_output=True, text=True)
        if probe.returncode == 0:
            return candidate
    return None


def test_lambda_capture_pattern_compiles_with_javac(tmp_path):
    javac = _functional_javac_command()
    if not javac:
        pytest.skip("No functional local JDK is installed; GitHub Android CI performs the authoritative Java/Gradle compile with Temurin 17.")
    src = tmp_path / "LambdaCaptureGuard.java"
    src.write_text(textwrap.dedent("""
        public class LambdaCaptureGuard {
            static void tryNavigate(String route, int token, int attempt) {}
            static void postDelayed(Runnable r, long ms) { r.run(); }
            static void navigate(String path) {
                String normalizedRoute = path == null ? "dashboard" : path.trim();
                final String route = normalizedRoute.isEmpty() ? "dashboard" : normalizedRoute;
                final int token = 1;
                postDelayed(() -> tryNavigate(route, token, 0), 60);
            }
        }
    """), encoding="utf-8")
    result = subprocess.run([javac, str(src)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_android_v019_identity_and_prior_navigation_fixes_preserved():
    gradle = text("mobile/android_qcms/app/build.gradle")
    java = text("mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java")
    assert any(v in gradle for v in ("versionCode 10", "versionCode 11", "versionCode 12"))
    assert any(v in gradle for v in ("versionName '0.1.9'", "versionName '0.2.0'", "versionName '0.2.1'"))
    for token in ('__qcmsNativePendingRoute', 'QCMS_NAV_PENDING', 'MutationObserver', '__qcmsNativeNavTimer'):
        assert token in java
    assert 'QCMS navigation is still loading. Please try the menu again.' not in java
    assert 'LinearLayout bottom=new LinearLayout' not in java
