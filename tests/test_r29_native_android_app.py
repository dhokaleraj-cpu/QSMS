"""R29: native QCMS Android app (v2.0.0) built from the approved R28 designs."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "mobile/android_qcms_app"
SRC = APP / "app/src/main/java/com/fourstar/qcmsapp"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_project_and_gradle():
    gradle = read(APP / "app/build.gradle")
    assert "applicationId 'com.fourstar.qcmsapp'" in gradle and "minSdk 26" in gradle and "targetSdk 35" in gradle
    assert "versionName '3.2.0'" in gradle and "signingConfig signingConfigs.qcms" in gradle
    assert '"https://xxrxopzxzyjnzumrwuwy.supabase.co"' in gradle
    assert "sb_publishable_" in gradle and "service_role" not in gradle
    assert (APP / "app/qcms-debug.keystore").exists()
    assert "implementation" not in gradle  # framework only, no third-party libraries
    assert "!mobile/android_qcms_app/app/qcms-debug.keystore" in read(ROOT / ".gitignore")


def test_all_designed_screens_exist():
    for name in ("MainActivity", "HomeScreen", "OrdersScreen", "PoDetailScreen", "OrderTrackerScreen", "Catalog", "SectionScreen",
                 "RegisterScreen", "RecordScreen", "EditScreen", "AssetsScreen", "AssetDetailScreen", "MoreScreen", "PartRmScreen",
                 "DataGrid", "SheetView", "Api", "SecureStore", "Ui"):
        assert (SRC / f"{name}.java").exists(), name
    main = read(SRC / "MainActivity.java")
    assert "TABS = Catalog.TAB_NAMES" in main
    assert 'TAB_NAMES = {"Home", "Supply", "Quality", "Masters", "More"}' in read(SRC / "Catalog.java")
    assert "BiometricPrompt" in main and "LOCK_AFTER_MS = 15L * 60L * 1000L" in main


def test_manifest_permissions_and_security():
    manifest = read(APP / "app/src/main/AndroidManifest.xml")
    assert 'android:usesCleartextTraffic="false"' in manifest and 'android:allowBackup="false"' in manifest
    assert "USE_BIOMETRIC" in manifest and "INTERNET" in manifest
    store = read(SRC / "SecureStore.java")
    assert "AndroidKeyStore" in store and "AES/GCM/NoPadding" in store
    api = read(SRC / "Api.java")
    assert "/auth/v1/token?grant_type=password" in api and "grant_type=refresh_token" in api
    assert 'secure.put("password"' not in api and 'putString("password"' not in api   # password never stored


def test_po_approval_matches_website():
    po = read(SRC / "PoDetailScreen.java")
    for rpc in ("qcms_approve_purchase_order", "qcms_ensure_po_confirmation", "qcms_cancel_purchase_order"):
        assert rpc in po
    from core.po_print_ui import SECTION_OPTIONS
    for flag, label in SECTION_OPTIONS:
        assert f'{{"{flag}", "{label}"}}' in po
    assert "Approve & send to supplier" in po and "Approve, do not send" in po
    assert "SndPoSend.open(a, id)" in po and "SndPdfView.forPo(a, id)" in po   # R30: native PDF + send
    web = read(ROOT / "app_pages/supply_chain.py")
    assert 'st.query_params.get("po")' in web


def test_grids_scroll_both_ways_with_frozen_panes():
    grid = read(SRC / "SheetView.java")   # R30: canvas spreadsheet grid replaces the nested scroll views
    assert "GestureDetector" in grid and "ScaleGestureDetector" in grid and "fling" in grid
    assert "requestDisallowInterceptTouchEvent" in grid and "frozen first column" in grid


def test_ci_workflow_builds_native_apk():
    wf = read(ROOT / ".github/workflows/qcms-native-app-apk.yml")
    assert "working-directory: mobile/android_qcms_app" in wf and "QCMS-NATIVE-APP-APK" in wf
    assert "assembleDebug" in wf and "apksigner" in wf
    assert (ROOT / ".github/workflows/qcms-first-app-apk.yml").exists()   # old WebView app unchanged


def test_resources_are_wellformed_and_edge_to_edge_handled():
    import xml.dom.minidom
    for path in (APP / "app/src/main").rglob("*.xml"):
        xml.dom.minidom.parse(str(path))
    assert "windowOptOutEdgeToEdgeEnforcement" in read(APP / "app/src/main/res/values-v35/themes.xml")
