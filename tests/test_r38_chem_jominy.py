"""R38 (A2 + E): horizontal chemistry / Jominy grids everywhere, Jominy in inch AND mm, mobile v3.6.0 / iOS 1.3.0 (4)."""
import io
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "mobile/android_qcms_app/app/src/main/java/com/fourstar/qcmsapp"
IOS = ROOT / "mobile/ios_stawn_qcms"
SWIFT = IOS / "STAWNQCMS"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def balanced(src: str) -> bool:
    return src.count("{") == src.count("}") and src.count("(") == src.count(")") and src.count("[") == src.count("]")


def _pdf_words(pdf: bytes) -> list[str]:
    from pypdf import PdfReader
    text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    return [w.strip() for w in text.split("\n") if w.strip()]


# ----------------------------------------------------------------------------- conversion
@pytest.mark.parametrize("value, mm", [
    ("J1/16", 1.59), ('J1/16"', 1.59), ('J5/16"', 7.94), ("J8/16", 12.7), ('J16/16"', 25.4), ("J3", 4.76),
    ("J 5", 7.94), ("5", 7.94), (5, 7.94), ('5/16"', 7.94), ("J2/16", 3.18), ("J 9/16", 14.29),
])
def test_jominy_inch_to_mm(value, mm):
    from core.chem_grid import jominy_inch_to_mm
    assert jominy_inch_to_mm(value) == mm


def test_jominy_mm_to_inch_and_blank_inputs():
    from core.chem_grid import jominy_distance_mm, jominy_inch_to_mm, jominy_inches, mm_to_inches, mm_to_sixteenths, parse_sixteenths
    assert jominy_inches('J5/16"') == 0.3125 and jominy_inches("J8/16") == 0.5 and jominy_inches("J16/16") == 1.0
    assert mm_to_inches(25.4) == 1.0 and mm_to_inches(7.9375) == 0.3125 and mm_to_inches("12.7 mm") == 0.5
    assert mm_to_sixteenths(7.94) == 5.0 and mm_to_sixteenths(1.5875) == 1.0
    for blank in (None, "", "abc", 0, -2, "J1.5mm"):
        assert jominy_inch_to_mm(blank) is None
    assert parse_sixteenths("J1.5mm") is None and parse_sixteenths("J 3") == 3
    assert jominy_distance_mm({"distance_label": "J1.5mm"}) == 1.5
    assert jominy_distance_mm({"distance_label": "x", "distance_mm": 7.9375}) == 7.94
    assert jominy_distance_mm({"distance_16th": 5, "distance_mm": 99}) == 7.94  # sixteenths win over a stale mm value


def test_jominy_scale_rows_show_both_scales():
    from core.chem_grid import jominy_scale_rows
    rows = jominy_scale_rows([{"distance_label": 'J1/16"'}, {"distance_16th": 5}, {"distance_label": "J1.5mm"}])
    assert rows[0] == ["Distance (in)", "0.0625", "0.3125", "0.0591"]
    assert rows[1] == ["Distance (mm)", "1.59", "7.94", "1.50"]


# ----------------------------------------------------------------------------- transpose round trip
def test_transpose_round_trip_keeps_stored_shape():
    from core.chem_grid import from_horizontal, ordered_elements, to_horizontal
    stored = [{"id": "2", "element": "Mn", "minimum_value": 1.1, "maximum_value": 1.4, "actual_value": 1.2, "unit": "%", "extra": {"a": 1}},
              {"id": "1", "element": "C", "minimum_value": 0.17, "maximum_value": 0.22, "actual_value": None, "unit": "%"},
              {"id": "3", "element": "Cr", "minimum_value": None, "maximum_value": 1.3, "actual_value": 1.0, "unit": "%"}]
    rows = ordered_elements(stored)
    fields = [("Minimum %", "minimum_value"), ("Maximum %", "maximum_value"), ("Actual %", "actual_value")]
    frame = to_horizontal(rows, fields)
    assert list(frame.columns) == ["Row", "C", "Mn", "Cr"]
    assert frame["Row"].tolist() == ["Minimum %", "Maximum %", "Actual %"]
    back = from_horizontal(frame, rows, fields)
    assert back == [dict(r) for r in rows]  # unchanged round trip, every other key kept
    frame.loc[frame["Row"] == "Actual %", "C"] = 0.19
    edited = from_horizontal(frame, rows, fields)
    assert edited[0]["actual_value"] == 0.19 and edited[0]["id"] == "1" and edited[1]["extra"] == {"a": 1}
    assert set(edited[0]) == set(rows[0])


def test_transpose_jominy_with_label_callable_and_duplicates():
    from core.chem_grid import from_horizontal, to_horizontal
    rows = [{"distance_label": '1/16"', "distance_16th": 1, "actual_hrc": 47.0},
            {"distance_label": '1/16"', "distance_16th": 1, "actual_hrc": None}]
    fields = [("Actual HRC", "actual_hrc")]
    frame = to_horizontal(rows, fields, column_label=lambda r: f'J{r["distance_16th"]}/16"')
    assert list(frame.columns) == ["Row", 'J1/16"', 'J1/16" (2)']
    assert from_horizontal(frame, rows, fields, column_label=lambda r: f'J{r["distance_16th"]}/16"') == rows


def test_split_bands_repeat_row_titles():
    from core.chem_grid import split_bands
    table = [["Element", *[f"E{i}" for i in range(30)]], ["Min", *range(30)]]
    bands = split_bands(table, 14)
    assert len(bands) == 3 and [len(b[0]) for b in bands] == [15, 15, 3]
    assert all(b[0][0] == "Element" and b[1][0] == "Min" for b in bands)
    assert split_bands(table[:1], 40) == [table[:1]]


def test_jominy_curve_table_horizontal():
    from core.chem_grid import jominy_curve_table
    table = jominy_curve_table({1: 44.2, "2": 43.8, 5: 38.3})
    assert table[0] == ["Distance (inch)", 'J1/16"', 'J2/16"', 'J5/16"']
    assert table[1] == ["Distance (mm)", "1.59", "3.18", "7.94"]
    assert table[2] == ["Calculated HRC", 44.2, 43.8, 38.3]


# ----------------------------------------------------------------------------- prints
def test_metlab_pdf_chemistry_one_header_row_and_jominy_both_scales():
    pytest.importorskip("pypdf")
    from core import print_samples, reporting
    payload = print_samples.metlab_sample()
    elements = ["C", "Mn", "Si", "S", "P", "Cr", "Ni", "Mo", "V", "Al", "Cu", "Nb", "Ti", "B", "N", "Ca", "Pb", "Sn", "W", "Co"]
    payload["results"]["chemistry_rows"] = [{"element": e, "minimum_value": 0.01, "maximum_value": 0.5, "actual_value": 0.2} for e in elements]
    payload["results"]["jominy_rows"] = [{"distance_label": '5/16"', "distance_16th": 5, "minimum_hrc": 30, "actual_value": 40},
                                         {"distance_label": 'J1/16"', "minimum_hrc": 40, "actual_value": 47}]
    fn = getattr(reporting.metlab_record_pdf_bytes, "__wrapped_uncached__", reporting.metlab_record_pdf_bytes)
    words = _pdf_words(fn(payload))
    start = words.index("Element")
    assert words[start + 1:start + 6] == ["C%", "Mn%", "Si%", "S%", "P%"]  # element symbols across one header row
    assert words.count("Spec. Min") == 2  # 20 elements wrap into two A4 bands, row titles repeated
    jom = words.index("Distance (inch)")
    assert words[jom + 1:jom + 3] == ['J1/16"', 'J5/16"']
    mm = words.index("Distance (mm)", jom)
    assert words[mm + 1:mm + 3] == ["1.59", "7.94"]


def test_qc_calculation_pdf_jominy_curve_horizontal():
    pytest.importorskip("pypdf")
    from core import reporting
    payload = {"record": {"calculation_number": "QCT-1", "calculation_type": "JOMINY", "result_payload": {"curve": {"1": 44.2, "2": 43.8, "5": 38.3}}}}
    fn = getattr(reporting.qc_calculation_pdf_bytes, "__wrapped_uncached__", reporting.qc_calculation_pdf_bytes)
    words = _pdf_words(fn(payload))
    i = words.index("Distance (inch)")
    assert words[i + 1:i + 4] == ['J1/16"', 'J2/16"', 'J5/16"']
    assert "Distance (mm)" in words and "7.94" in words and "Distance (1/16 in.)" not in words


def test_generic_print_rmtc_jominy_horizontal():
    from core.record_print import CHILD_SECTIONS, _analysis_frame

    class _Resolver:
        def label(self, *a):
            return "P-1"
    assert ("rmtc_jominy_results", "rmtc_approval_id", "id", "JOMINY RESULTS") in CHILD_SECTIONS["rmtc_approvals"]
    frame = _analysis_frame("rmtc_jominy_results", [
        {"part_id": "p", "distance_label": '2/16"', "distance_16th": 2, "actual_hrc": 44, "result": "PASS"},
        {"part_id": "p", "distance_label": '1/16"', "distance_16th": 1, "actual_hrc": 47, "result": "PASS"}], _Resolver())
    assert list(frame.columns) == ["Distance (inch)", 'J1/16"', 'J2/16"']
    assert frame.iloc[0].tolist() == ["Distance (mm)", "1.59", "3.18"] and frame.iloc[1].tolist() == ["Actual HRC", 47, 44]


def test_web_pages_show_both_scales():
    rmtc = read(ROOT / "app_pages/rmtc_pages.py")
    assert "jominy_scale_rows" in rmtc and "('Distance (in)','Distance (in)'),('Distance (mm)','Distance (mm)')" in rmtc
    qct = read(ROOT / "app_pages/qc_calculation_tools.py")
    assert "jominy_curve_table(curve)" in qct and '"Distance (1/16 in.)"' not in qct
    reporting = read(ROOT / "core/reporting.py")
    assert '{"Distance (1/16 in.)": key' not in reporting
    assert "_horizontal_analysis_grid(rows, content_width, styles[\"header\"], styles[\"small\"], first_width=26 * mm)" in reporting


# ----------------------------------------------------------------------------- mobile
def test_android_chem_grid_and_versions():
    gradle = read(ROOT / "mobile/android_qcms_app/app/build.gradle")
    assert "versionCode 371" in gradle and "versionName '3.7.1'" in gradle
    grid = read(JAVA / "ChemGrid.java")
    assert balanced(grid)
    for token in ('"1.5875"', '"25.4"', "static double sixteenths(", "static List<List<String[]>> bands(", "PDF_BAND_COLUMNS = 14",
                  '"material_grade_elements"', '"part_jominy_requirements"', '"rmtc_chemistry_results"', '"rmtc_jominy_results"'):
        assert token in grid
    rpt = read(JAVA / "RptReports.java")
    assert rpt.count("ChemGrid.bands(") == 4 and "ChemGrid.horizontal(child.table, rows, cfk.get(\"part_id\"))" in rpt
    assert "return ChemGrid.sixteenthOf(r);" in rpt
    rec = read(JAVA / "RecordScreen.java")
    assert "ChemGrid.handles(child.table)" in rec and "ChemGrid.headers(e.getValue())" in rec
    assert "## v3.6.0 (R38)" in read(ROOT / "mobile/android_qcms_app/README_ANDROID_APP.md")


def test_android_compiles():
    script = Path("/tmp/r30/compile.sh")
    if not script.exists():
        pytest.skip("Android stub compiler not available here")
    out = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=600)
    text = out.stdout + out.stderr
    assert "COMPILE DONE" in text and " error:" not in text and "error:" not in text.replace("Xmaxerrs", "")


def test_ios_chem_grid_and_versions():
    grid = read(SWIFT / "ChemGrid.swift")
    assert balanced(grid) and "enum ChemGrid" in grid and '"1.5875"' in grid and "25.4" in grid
    assert "static func bands(" in grid and "static func combined(" in grid and "static func sixteenths(" in grid
    rpt = read(SWIFT / "RptReports.swift")
    assert balanced(rpt) and rpt.count("ChemGrid.bands(") == 4 and "return ChemGrid.sixteenthOf(r)" in rpt
    assert "ChemGrid.horizontal(child.table, rows, cfk[\"part_id\"])" in rpt
    rec = read(SWIFT / "RecordView.swift")
    assert balanced(rec) and "ChemGrid.combined(child.table, rows, cfk[\"part_id\"])" in rec
    pbx = read(IOS / "STAWNQCMS.xcodeproj/project.pbxproj")
    assert '"ChemGrid.swift"' in pbx and 'MARKETING_VERSION = "1.3.0"' in pbx and 'CURRENT_PROJECT_VERSION = "4"' in pbx
    assert 'DEVELOPMENT_TEAM = ""' in pbx and pbx.count("{") == pbx.count("}")
    mp = read(IOS / "make_project.py")
    assert 'else "1.3.0"' in mp and 'else "4"' in mp and "STAWN_PERSONAL_TEAM" in mp and "STAWN_APPLE_TEAM_ID" in mp
    assert 'VERSION="1.3.0"' in read(IOS / "BUILD_STAWN_QCMS_iOS.command")
    core = read(SWIFT / "Core.swift")
    assert '?? "1.3.0"' in core and '?? "4"' in core
    assert "## New in v1.3.0 (build 4, R38)" in read(IOS / "README_IOS.md")
    # conservative Swift: no Swift 5.9+ constructs (if/switch expressions, macros, Observation)
    for src in (grid,):
        assert "@Observable" not in src and "#Preview" not in src and "= if " not in src and "= switch " not in src


def test_about_versions():
    about = read(ROOT / "core/about.py")
    assert 'ANDROID_VERSION = "3.7.1"' in about and 'IOS_VERSION = "1.3.0"' in about
