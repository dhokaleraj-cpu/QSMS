"""R30: the Android app runs every QCMS module natively (no website pages)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile/android_qcms_app/app/src/main/java/com/fourstar/qcmsapp"


def _all_java() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in SRC.glob("*.java")}


def test_catalog_registers_every_area():
    catalog = (SRC / "Catalog.java").read_text()
    for area in ("CatSupply", "CatIncoming", "CatInspection", "CatCalib", "CatMasters", "CatMore", "CatGeneral", "CatEmail", "CatAdmin"):
        assert f"{area}.register(list);" in catalog, area
        assert (SRC / f"{area}.java").exists(), area


def test_module_keys_unique_and_many():
    keys = []
    for name, text in _all_java().items():
        if name.startswith("Cat"):
            keys += re.findall(r'new Module\(\s*"([a-z0-9_]+)"', text)
    assert len(keys) >= 60
    assert len(keys) == len(set(keys)), sorted(k for k in keys if keys.count(k) > 1)


def test_no_module_opens_the_website():
    for name, text in _all_java().items():
        if name in {"MainActivity.java", "MoreScreen.java", "WebScreen.java", "AdmSettings.java"}:
            continue
        assert "openWeb(" not in text, name


def test_password_change_and_native_po_pdf():
    api = (SRC / "Api.java").read_text()
    assert "public void changePassword(String newPassword)" in api and '"/auth/v1/user"' in api
    assert "class SndPoPdf" in (SRC / "SndPoPdf.java").read_text()


def test_part_rows_never_move_between_parts_in_app():
    save = (SRC / "MstSave.java").read_text()
    assert 'keys.add("part_id")' in save and "belongs to" in save.lower() or "another part" in save.lower()


def test_no_secrets_in_app():
    for name, text in _all_java().items():
        assert "service_role" not in text, name
