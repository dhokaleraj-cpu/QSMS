from __future__ import annotations

from typing import Any, Mapping

GENERAL_METLAB = "GENERAL_METLAB"
BEND_TEST = "BEND_TEST"
METLAB_INSPECTION_METHODS = (
    (GENERAL_METLAB, "General MetLAB"),
    (BEND_TEST, "Bend Test"),
)

# Starter rows mirror the controlled Bend Test report supplied for v4.14.29.
# They are intentionally editable in Layout Master so each Part/customer can
# retain its own controlled specification instead of hard-coding report values.
BEND_TEST_DEFAULT_CHARACTERISTICS = [
    {
        "Sequence": 10,
        "Characteristic No": "1",
        "Parameter": "Baking Temperature",
        "Specification": "400°C / as approved process",
        "Minimum": None,
        "Maximum": None,
        "Unit": "°C",
        "Type": "NUMBER",
        "Checking Aid": "Baking / ageing process record",
        "Sample Size": 1,
        "Allow NA": False,
        "Mandatory": True,
        "Case Depth Traverse": False,
        "Traverse Location": "",
        "Status": "ACTIVE",
    },
    {
        "Sequence": 20,
        "Characteristic No": "2",
        "Parameter": "Baking Time",
        "Specification": "60 Minutes Minimum",
        "Minimum": 60.0,
        "Maximum": None,
        "Unit": "Minutes",
        "Type": "NUMBER",
        "Checking Aid": "Baking / ageing process record",
        "Sample Size": 1,
        "Allow NA": False,
        "Mandatory": True,
        "Case Depth Traverse": False,
        "Traverse Location": "",
        "Status": "ACTIVE",
    },
    {
        "Sequence": 30,
        "Characteristic No": "3",
        "Parameter": "Base Metal Hardness below plating",
        "Specification": "446-544 HV (45-52 HRC) · average of three observations",
        "Minimum": 45.0,
        "Maximum": 52.0,
        "Unit": "HRC",
        "Type": "NUMBER",
        "Checking Aid": "Hardness tester",
        "Sample Size": 3,
        "Allow NA": False,
        "Mandatory": True,
        "Case Depth Traverse": False,
        "Traverse Location": "",
        "Status": "ACTIVE",
    },
    {
        "Sequence": 40,
        "Characteristic No": "4",
        "Parameter": "Load",
        "Specification": "Record achieved test load",
        "Minimum": None,
        "Maximum": None,
        "Unit": "kN",
        "Type": "NUMBER",
        "Checking Aid": "Compression / bend test machine",
        "Sample Size": 1,
        "Allow NA": False,
        "Mandatory": True,
        "Case Depth Traverse": False,
        "Traverse Location": "",
        "Status": "ACTIVE",
    },
    {
        "Sequence": 50,
        "Characteristic No": "5",
        "Parameter": "CHT",
        "Specification": "Record cross head travel",
        "Minimum": None,
        "Maximum": None,
        "Unit": "mm",
        "Type": "NUMBER",
        "Checking Aid": "Compression / bend test machine",
        "Sample Size": 1,
        "Allow NA": False,
        "Mandatory": True,
        "Case Depth Traverse": False,
        "Traverse Location": "",
        "Status": "ACTIVE",
    },
    {
        "Sequence": 60,
        "Characteristic No": "6",
        "Parameter": "Bend Angle",
        "Specification": "Record achieved bend angle",
        "Minimum": None,
        "Maximum": None,
        "Unit": "Degree",
        "Type": "NUMBER",
        "Checking Aid": "Bend test fixture / angle measurement",
        "Sample Size": 1,
        "Allow NA": False,
        "Mandatory": True,
        "Case Depth Traverse": False,
        "Traverse Location": "",
        "Status": "ACTIVE",
    },
    {
        "Sequence": 70,
        "Characteristic No": "7",
        "Parameter": "Bend Test Status",
        "Specification": "Passed",
        "Minimum": None,
        "Maximum": None,
        "Unit": "",
        "Type": "TEXT",
        "Checking Aid": "Visual / test report review",
        "Sample Size": 1,
        "Allow NA": False,
        "Mandatory": True,
        "Case Depth Traverse": False,
        "Traverse Location": "",
        "Status": "ACTIVE",
    },
    {
        "Sequence": 80,
        "Characteristic No": "8",
        "Parameter": "Plating Surface Condition",
        "Specification": "No Peeling, Flaking on the plating surface.",
        "Minimum": None,
        "Maximum": None,
        "Unit": "",
        "Type": "TEXT",
        "Checking Aid": "Visual inspection after bend test",
        "Sample Size": 1,
        "Allow NA": False,
        "Mandatory": True,
        "Case Depth Traverse": False,
        "Traverse Location": "",
        "Status": "ACTIVE",
    },
]


def row_metadata(row: Mapping[str, Any] | None) -> dict[str, Any]:
    value = (row or {}).get("layout_metadata") or {}
    return dict(value) if isinstance(value, Mapping) else {}


def inspection_method_from_rows(rows: list[Mapping[str, Any]] | None, fallback_text: str = "") -> str:
    for row in rows or []:
        method = str(row_metadata(row).get("inspection_method") or "").strip().upper()
        if method in {GENERAL_METLAB, BEND_TEST}:
            return method
    return BEND_TEST if "BEND TEST" in str(fallback_text or "").upper() else GENERAL_METLAB


def characteristic_metadata(
    existing: Mapping[str, Any] | None,
    *,
    inspection_method: str,
    case_depth_traverse: bool = False,
    traverse_location: str | None = None,
) -> dict[str, Any]:
    data = row_metadata(existing)
    data["inspection_method"] = str(inspection_method or GENERAL_METLAB).upper()
    data["case_depth_traverse"] = bool(case_depth_traverse)
    location = str(traverse_location or "").strip()
    if location:
        data["case_depth_location"] = location
    else:
        data.pop("case_depth_location", None)
    return data
