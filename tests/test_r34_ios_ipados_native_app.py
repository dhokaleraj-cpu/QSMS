"""R34: native STAWN QCMS iPhone / iPad app (SwiftUI) with the same catalogue, login, PDFs and search as the Android app."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IOS = ROOT / "mobile/ios_stawn_qcms"
SRC = IOS / "STAWNQCMS"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_project_files_and_every_swift_file_in_the_build():
    pbx = read(IOS / "STAWNQCMS.xcodeproj/project.pbxproj")
    swift = sorted(p.name for p in SRC.glob("*.swift"))
    assert len(swift) >= 18
    for name in swift:
        assert f'path = "{name}"' in pbx, name
    assert 'PRODUCT_BUNDLE_IDENTIFIER = "com.stawnprecision.qcms"' in pbx and 'TARGETED_DEVICE_FAMILY = "1,2"' in pbx
    assert 'IPHONEOS_DEPLOYMENT_TARGET = "16.0"' in pbx and "catalog.json" in pbx and "Assets.xcassets" in pbx
    assert (IOS / "STAWNQCMS.xcodeproj/xcshareddata/xcschemes/STAWNQCMS.xcscheme").exists()
    plist = read(SRC / "Info.plist")
    assert "<string>STAWN QCMS</string>" in plist and "NSFaceIDUsageDescription" in plist and "ITSAppUsesNonExemptEncryption" in plist
    assert (SRC / "Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png").exists()
    assert (SRC / "Assets.xcassets/FSILogo.imageset/FSILogo.png").exists()


def test_catalog_matches_android_modules():
    cat = json.loads(read(SRC / "Resources/catalog.json"))
    keys = {m["key"] for m in cat["modules"]}
    android = "".join(read(p) for p in (ROOT / "mobile/android_qcms_app/app/src/main/java/com/fourstar/qcmsapp").glob("Cat*.java"))
    for key in ("purchase_orders", "rmtc", "inward", "metlab_reports", "bend_tests", "dimensional_reports", "customer_complaints", "parts", "about"):
        assert key in keys and f'"{key}"' in android
    assert len(cat["searchSources"]) >= 25 and cat["fk"] and cat["labels"]


def test_security_publishable_key_only_and_keychain():
    api = read(SRC / "Api.swift") + read(SRC / "Core.swift")
    assert "sb_publishable_" in api and "service_role" not in api
    assert "kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly" in api and "refresh_token" in api
    assert "password" not in re.findall(r'Keychain\.set\([^,]*, for: "([^"]+)"\)', api)
    app = read(SRC / "App.swift")
    assert "LAContext" in app and "15 * 60" in app


def test_print_layout_reports_ported():
    rep = read(SRC / "RptReports.swift")
    for t in ("RAW MATERIAL METALLURGICAL TEST REPORT", "METALLURGICAL LABORATORY - BEND TEST REPORT", "FINAL INSPECTION / DIMENSIONAL REPORT",
              "MATERIAL INWARD INSPECTION RECORD", "RMTC HEADER & TRACEABILITY", "DETAILED COMPLAINT ANALYSIS RECORD", "QC CALCULATION RECORD"):
        assert t in rep, t
    pdf = read(SRC / "RptPdf.swift")
    assert "UIGraphicsPDFRenderer" in pdf and "Page \\(pageNo) of" in pdf and "HEAT NUMBER: " in pdf and "Copyrights by STAWN" in pdf
    viewer = read(SRC / "PdfViewer.swift")
    assert "UIPrintInteractionController" in viewer and "MFMailComposeViewController" in viewer and "UIDocumentPickerViewController" in viewer


def test_search_bar_about_and_build_tools():
    main = read(SRC / "MainView.swift")
    assert ".searchable(" in main and "nav.push(.search(q))" in main
    about = read(SRC / "AboutView.swift")
    assert "STAWN PRECISION PRIVATE LIMITED" in about and "Copyright Act, 1957" in about
    cmd = read(IOS / "BUILD_STAWN_QCMS_iOS.command")
    assert "iphonesimulator" in cmd and "testflight" in cmd and "-allowProvisioningUpdates" in cmd
    wf = read(ROOT / ".github/workflows/stawn-qcms-ios.yml")
    assert "macos-14" in wf and "CODE_SIGNING_ALLOWED=NO" in wf
