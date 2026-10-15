"""R32: app and website are branded STAWN QCMS with the STAWN-mark icon."""
from pathlib import Path
import xml.dom.minidom

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "mobile/android_qcms_app/app/src/main/res"


def test_android_name_and_icon():
    assert '<string name="app_name">STAWN QCMS</string>' in (RES / "values/strings.xml").read_text()
    fg = (RES / "drawable/ic_launcher_foreground.xml").read_text()
    assert "M48.87,31L61.42,44.75L48.87,58.45Z" in fg and "M48.82,58.45L38.58,67.79L48.82,77Z" in fg   # STAWN mark
    assert "#165D91" in (RES / "drawable/ic_launcher_background.xml").read_text()
    icon = (RES / "mipmap-anydpi-v26/ic_launcher.xml").read_text()
    assert "ic_launcher_monochrome" in icon and "ic_launcher_foreground" in icon
    for p in RES.rglob("*.xml"):
        xml.dom.minidom.parse(str(p))
    main = (ROOT / "mobile/android_qcms_app/app/src/main/java/com/fourstar/qcmsapp/MainActivity.java").read_text()
    assert "R.drawable.stawn_qcms_logo" in main and '"STAWN QCMS"' in main


def test_website_brand_and_favicon():
    app = (ROOT / "streamlit_app.py").read_text()
    assert 'page_title=f"STAWN QCMS · {settings.company_name}"' in app and "stawn_qcms_favicon.png" in app
    assert (ROOT / "assets/stawn_qcms_favicon.png").exists() and (ROOT / "assets/stawn_qcms_icon.png").exists()
    assert "STAWN QCMS · QUALITY CONTROL MONITORING SYSTEM" in (ROOT / "core/ui.py").read_text()
    assert "STAWN QCMS · Quality Control Monitoring System" in (ROOT / "core/auth.py").read_text()
