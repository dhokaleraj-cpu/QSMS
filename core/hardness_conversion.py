from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parents[1] / "data" / "astm_e140_table1.json"

SCALE_LABELS = {
    "HRC": "Rockwell C (HRC)",
    "HV": "Vickers (HV)",
    "HBS": "Brinell - standard ball 3000 kgf (HBS)",
    "HBW": "Brinell - carbide ball 3000 kgf (HBW)",
    "HK": "Knoop 500 gf and over (HK)",
    "HRA": "Rockwell A (HRA)",
    "HRD": "Rockwell D (HRD)",
    "HR15N": "Rockwell 15-N (HR15N)",
    "HR30N": "Rockwell 30-N (HR30N)",
    "HR45N": "Rockwell 45-N (HR45N)",
    "HSc": "Scleroscope hardness (HSc)",
}


@lru_cache(maxsize=1)
def table_payload() -> dict[str, Any]:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def table_rows() -> list[dict[str, Any]]:
    return [dict(row) for row in table_payload().get("rows", [])]


def _valid_rows(scale: str) -> list[dict[str, Any]]:
    return [row for row in table_rows() if row.get(scale) is not None]


def convert_hardness(value: float, source_scale: str, target_scale: str) -> dict[str, Any]:
    """Convert using ASTM E 140-02 Table 1 supplied by the user.

    The source table is explicitly for non-austenitic steels in the Rockwell C
    hardness range. Values are approximate. For values between two published
    rows, linear interpolation is used only where both source and target values
    exist. No extrapolation is performed outside the published source range.
    """
    source_scale = str(source_scale or "").strip()
    target_scale = str(target_scale or "").strip()
    if source_scale not in SCALE_LABELS or target_scale not in SCALE_LABELS:
        raise ValueError("Select a supported ASTM E140 Table 1 hardness scale.")
    number = float(value)
    if source_scale == target_scale:
        return {
            "source_value": number,
            "source_scale": source_scale,
            "target_value": number,
            "target_scale": target_scale,
            "method": "No conversion - identical scale",
            "standard": "ASTM E 140-02 Table 1",
            "warning": "Hardness conversion values are approximate and material-specific.",
            "bracket": None,
            "outside_recommended": False,
        }

    candidates = [row for row in table_rows() if row.get(source_scale) is not None and row.get(target_scale) is not None]
    if not candidates:
        raise ValueError(f"No Table 1 conversion relationship is available from {source_scale} to {target_scale}.")

    exact = [row for row in candidates if abs(float(row[source_scale]) - number) < 1e-9]
    if exact:
        row = exact[0]
        restricted = target_scale in set(row.get("_outside_recommended") or []) or source_scale in set(row.get("_outside_recommended") or [])
        return {
            "source_value": number,
            "source_scale": source_scale,
            "target_value": float(row[target_scale]),
            "target_scale": target_scale,
            "method": "ASTM E140 Table 1 direct lookup",
            "standard": "ASTM E 140-02 Table 1",
            "warning": (
                "Approximate conversion. A parenthesized Brinell value is outside the recommended Brinell testing range."
                if restricted else "Approximate conversion; use only for the material scope of ASTM E140 Table 1."
            ),
            "bracket": {source_scale: [number, number], target_scale: [float(row[target_scale]), float(row[target_scale])]},
            "outside_recommended": restricted,
        }

    ordered = sorted(candidates, key=lambda row: float(row[source_scale]))
    minimum = float(ordered[0][source_scale]); maximum = float(ordered[-1][source_scale])
    if number < minimum or number > maximum:
        raise ValueError(f"{number:g} {source_scale} is outside the supported Table 1 range {minimum:g} to {maximum:g} {source_scale}. Extrapolation is not permitted.")

    lower = upper = None
    for left, right in zip(ordered, ordered[1:]):
        x1 = float(left[source_scale]); x2 = float(right[source_scale])
        if x1 <= number <= x2:
            lower, upper = left, right
            break
    if lower is None or upper is None:
        raise ValueError("A valid ASTM E140 Table 1 interpolation bracket could not be found.")

    x1 = float(lower[source_scale]); x2 = float(upper[source_scale])
    y1 = float(lower[target_scale]); y2 = float(upper[target_scale])
    ratio = 0.0 if x2 == x1 else (number - x1) / (x2 - x1)
    target = y1 + ratio * (y2 - y1)
    restricted = any(
        scale in set(row.get("_outside_recommended") or [])
        for row in (lower, upper) for scale in (source_scale, target_scale)
    )
    return {
        "source_value": number,
        "source_scale": source_scale,
        "target_value": round(target, 3),
        "target_scale": target_scale,
        "method": "ASTM E140 Table 1 linear interpolation",
        "standard": "ASTM E 140-02 Table 1",
        "warning": (
            "Approximate interpolated conversion. The bracket includes a parenthesized Brinell value outside the recommended Brinell testing range."
            if restricted else "Approximate interpolated conversion; use only for the material scope of ASTM E140 Table 1."
        ),
        "bracket": {source_scale: [x1, x2], target_scale: [y1, y2]},
        "outside_recommended": restricted,
    }
