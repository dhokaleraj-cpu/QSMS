from __future__ import annotations

import bisect
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

_DATA = Path(__file__).resolve().parents[1] / "data" / "di_factors.json"


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def chemistry_value(chemistry: Mapping[str, Any], symbol: str, default: float = 0.0) -> float:
    aliases = {
        "C": ("C", "C%", "CARBON"),
        "MN": ("MN", "MN%", "MANGANESE"),
        "CR": ("CR", "CR%", "CHROMIUM"),
        "NI": ("NI", "NI%", "NICKEL"),
        "MO": ("MO", "MO%", "MOLYBDENUM"),
        "SI": ("SI", "SI%", "SILICON"),
        "CU": ("CU", "CU%", "COPPER"),
        "V": ("V", "V%", "VANADIUM"),
    }
    normalized = {str(k).strip().upper(): v for k, v in chemistry.items()}
    for key in aliases.get(symbol.upper(), (symbol.upper(),)):
        value = _num(normalized.get(key))
        if value is not None:
            return value
    return default


def calculate_jominy_curve(chemistry: Mapping[str, Any]) -> dict[int, float]:
    """Implements the formulas in the supplied JUST.xls workbook.

    Inputs are percentages for C, Mn, Cr, Ni and Mo. Output contains J1..J16 HRC.
    """
    c = chemistry_value(chemistry, "C")
    mn = chemistry_value(chemistry, "MN")
    cr = chemistry_value(chemistry, "CR")
    ni = chemistry_value(chemistry, "NI")
    mo = chemistry_value(chemistry, "MO")

    j1 = 37.0 + (c - 0.08) * 60.0
    j4 = 87.0 * c + 16.0 * mn + 13.25 * cr + 5.3 * ni + 28.5 * mo + 22.0 - (21.2 * math.sqrt(4.0) - 2.21 * 4.0)
    j2 = j1 - (j1 - j4) * 0.1
    j3 = j1 - (j1 - j4) * 0.5
    curve = {1: j1, 2: j2, 3: j3, 4: j4}
    for distance in range(5, 17):
        curve[distance] = (
            87.0 * c + 16.0 * mn + 14.0 * cr + 5.3 * ni + 29.0 * mo + 22.0
            - (21.2 * math.sqrt(float(distance)) - 2.21 * float(distance))
        )
    return {key: round(value, 3) for key, value in curve.items()}


@lru_cache(maxsize=1)
def _di_table() -> tuple[list[float], dict[str, list[float | None]]]:
    payload = json.loads(_DATA.read_text(encoding="utf-8"))
    headers = payload["headers"]
    rows = payload["rows"]
    alloy = [float(row[0]) for row in rows]
    columns: dict[str, list[float | None]] = {}
    for index, header in enumerate(headers[1:], start=1):
        columns[str(header)] = [None if row[index] is None else float(row[index]) for row in rows]
    return alloy, columns


def _approx_lookup(value: float, header: str) -> float | None:
    alloy, columns = _di_table()
    values = columns[header]
    pos = bisect.bisect_right(alloy, value) - 1
    if pos < 0:
        pos = 0
    return values[min(pos, len(values) - 1)]


def calculate_di(chemistry: Mapping[str, Any], grain_size: int) -> dict[str, Any]:
    """Implements the approximate VLOOKUP factor product in DI Hardenability.XLSX."""
    if grain_size not in (4, 5, 6, 7, 8):
        return {"value": None, "factors": {}, "error": "Grain size must be between 4 and 8."}
    grain_header = {7: "C(GS 7)", 8: "C(GS 8)", 6: "C(GS 6)", 5: "C(GS 5)", 4: "C(GS 4)"}[grain_size]
    inputs = {
        grain_header: chemistry_value(chemistry, "C"),
        "Mn": chemistry_value(chemistry, "MN"),
        "Si": chemistry_value(chemistry, "SI"),
        "Ni": chemistry_value(chemistry, "NI"),
        "Cr": chemistry_value(chemistry, "CR"),
        "Mo": chemistry_value(chemistry, "MO"),
        "Cu": chemistry_value(chemistry, "CU"),
        "V": chemistry_value(chemistry, "V"),
    }
    factors: dict[str, float | None] = {key: _approx_lookup(value, key) for key, value in inputs.items()}
    missing = [key for key, factor in factors.items() if factor is None]
    if missing:
        return {"value": None, "factors": factors, "error": "Factor unavailable for: " + ", ".join(missing)}
    result = math.prod(float(factor) for factor in factors.values() if factor is not None)
    return {"value": round(result, 4), "factors": factors, "error": None}


def band_status(value: Any, minimum: Any, maximum: Any, applicable: bool = True) -> str:
    if not applicable:
        return "NOT_APPLICABLE"
    number = _num(value)
    if number is None:
        return "NOT_EVALUATED"
    lower = _num(minimum)
    upper = _num(maximum)
    if lower is not None and number < lower:
        return "FAIL"
    if upper is not None and number > upper:
        return "FAIL"
    return "PASS"
