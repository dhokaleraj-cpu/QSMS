"""R38 · Horizontal chemical-analysis and Jominy grids (shared by web pages, PDFs and Excel).

Chemistry: elements are COLUMNS (C, Mn, Si, S, P, Cr, Ni, Mo, V, Al, Cu, Nb, Ti, extras, Al/N2 ratio last);
rows are Min / Max / Actual (or whatever row meaning the caller passes).
Jominy: distances are COLUMNS (J1/16", J2/16", ...); the first data row is the distance in millimetres
(1/16 inch = 1.5875 mm, two decimals) so the inch label and the mm value are both visible; the following
rows are HRC Min / Max / Actual / ...
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence

MM_PER_INCH = 25.4
MM_PER_SIXTEENTH = MM_PER_INCH / 16.0  # 1.5875 mm
ELEMENT_ORDER = ("C", "Mn", "Si", "S", "P", "Cr", "Ni", "Mo", "V", "Al", "Cu", "Nb", "Ti")
RATIO_KEY = "aln2ratio"
JOMINY_MM_ROW = "Distance (mm)"
_ALIASES = {
    "carbon": "c", "manganese": "mn", "silicon": "si", "sulphur": "s", "sulfur": "s", "phosphorus": "p",
    "chromium": "cr", "nickel": "ni", "molybdenum": "mo", "vanadium": "v", "aluminium": "al", "aluminum": "al",
    "copper": "cu", "niobium": "nb", "titanium": "ti", "nitrogen": "n", "alnratio": RATIO_KEY, "aln2ratio": RATIO_KEY,
    "alnitrogenratio": RATIO_KEY,
}


# ----------------------------------------------------------------------------- chemistry
def element_key(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9]", "", str(value or "")).casefold()
    return _ALIASES.get(text, text)


def ordered_elements(rows: Iterable[Mapping[str, Any]], *, field: str = "element") -> list[dict]:
    """Report order: C -> Ti, other configured elements alphabetically, Al/N2 ratio last."""
    rank = {element_key(name): index for index, name in enumerate(ELEMENT_ORDER)}
    normal: list[dict] = []; extras: list[dict] = []; ratio: list[dict] = []
    for source in rows:
        row = dict(source)
        key = element_key(row.get(field))
        (ratio if key == RATIO_KEY else normal if key in rank else extras).append(row)
    normal.sort(key=lambda row: (rank[element_key(row.get(field))], str(row.get(field) or "")))
    extras.sort(key=lambda row: str(row.get(field) or ""))
    ratio.sort(key=lambda row: str(row.get(field) or ""))
    return [*normal, *extras, *ratio]


def element_label(element: Any, unit: Any = "%") -> str:
    text = str(element or "").strip()
    if element_key(text) == RATIO_KEY:
        return "Al/N2 Ratio"
    unit_text = str(unit or "").strip()
    if unit_text in ("", "%"):
        return text if "%" in text else f"{text}%"
    return f"{text} ({unit_text})"


def _cell(value: Any, blank: Any = "-") -> Any:
    if value is None:
        return blank
    try:
        if value != value:  # NaN
            return blank
    except Exception:
        pass
    return blank if value == "" else value


def chemistry_table(
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[tuple[str, Any]],
    *,
    corner: str = "Element",
    element_field: str = "element",
    blank: Any = "-",
) -> list[list[Any]]:
    """[[corner, C%, Mn%, ...], [row title, v, v, ...], ...]. A field may be a key or a callable(row)."""
    ordered = ordered_elements(rows, field=element_field)
    table: list[list[Any]] = [[corner, *[element_label(r.get(element_field), r.get("unit") or "%") for r in ordered]]]
    for title, field in fields:
        line: list[Any] = [title]
        for row in ordered:
            value = field(row) if callable(field) else row.get(field)
            line.append(_cell(value, blank))
        table.append(line)
    return table


def table_frame(table: Sequence[Sequence[Any]]):
    """List-of-lists (first row = header) -> pandas DataFrame with unique column names."""
    import pandas as pd

    header = [str(value) for value in table[0]] if table else []
    seen: dict[str, int] = {}
    unique = []
    for name in header:
        seen[name] = seen.get(name, 0) + 1
        unique.append(name if seen[name] == 1 else f"{name} ({seen[name]})")
    return pd.DataFrame([list(row) for row in table[1:]], columns=unique)


# ----------------------------------------------------------------------------- Jominy
def sixteenth_from(value: Any = None, *, label: Any = None, mm: Any = None) -> int:
    """Resolve a Jominy distance in 1/16 inch from a number, a label (J5, 5/16, J 5/16\") or millimetres."""
    for candidate in (value,):
        try:
            number = int(float(candidate))
            if number > 0:
                return number
        except (TypeError, ValueError):
            pass
    text = str(label or "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*16", text) or re.search(r"J\s*(\d+(?:\.\d+)?)", text, re.I)
    if match:
        try:
            return int(round(float(match.group(1))))
        except ValueError:
            pass
    try:
        millimetres = float(mm)
        if millimetres > 0:
            return int(round(millimetres / MM_PER_SIXTEENTH))
    except (TypeError, ValueError):
        pass
    return 0


def jominy_mm(sixteenth: Any) -> float | None:
    try:
        number = float(sixteenth)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    # Exact decimal arithmetic, half-up: 2/16" = 3.175 -> 3.18 (binary floats would print 3.17).
    from decimal import ROUND_HALF_UP, Decimal
    return float((Decimal(str(number)) * Decimal("1.5875")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def jominy_inch_to_mm(label_or_sixteenth: Any) -> float | None:
    """J5/16" -> 7.94 (mm). Accepts an int (sixteenths) or a label."""
    if isinstance(label_or_sixteenth, (int, float)):
        return jominy_mm(label_or_sixteenth)
    return jominy_mm(sixteenth_from(label=label_or_sixteenth))


def jominy_label(sixteenth: int, fallback: Any = "") -> str:
    return f'J{int(sixteenth)}/16"' if int(sixteenth or 0) > 0 else str(fallback or "-")


def _sixteenth_of(row: Mapping[str, Any]) -> int:
    return sixteenth_from(row.get("distance_16th"), label=row.get("distance_label"), mm=row.get("distance_mm"))


def ordered_jominy(rows: Iterable[Mapping[str, Any]]) -> list[dict]:
    return sorted((dict(r) for r in rows), key=lambda r: (_sixteenth_of(r) or 999, str(r.get("distance_label") or "")))


def jominy_table(
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[tuple[str, Any]],
    *,
    corner: str = 'Distance (inch)',
    blank: Any = "-",
) -> list[list[Any]]:
    """[[corner, J1/16", J2/16", ...], ["Distance (mm)", 1.59, 3.18, ...], [field rows ...]]."""
    ordered = ordered_jominy(rows)
    sixteenths = [_sixteenth_of(r) for r in ordered]
    table: list[list[Any]] = [[corner, *[jominy_label(s, r.get("distance_label")) for s, r in zip(sixteenths, ordered)]]]
    table.append([JOMINY_MM_ROW, *[(f"{jominy_mm(s):.2f}" if jominy_mm(s) is not None else _cell(r.get("distance_mm"), blank)) for s, r in zip(sixteenths, ordered)]])
    for title, field in fields:
        line: list[Any] = [title]
        for row in ordered:
            value = field(row) if callable(field) else row.get(field)
            line.append(_cell(value, blank))
        table.append(line)
    return table


def wide_to_rows(frame, columns: Sequence[str], row_name: str, *, first_column: str = "Row") -> dict[str, Any]:
    """Read one row of a horizontal grid back as {column: value}."""
    if frame is None or getattr(frame, "empty", True) or first_column not in frame.columns:
        return {}
    match = frame[frame[first_column] == row_name]
    if match.empty:
        return {}
    line = match.iloc[0]
    return {column: line.get(column) for column in columns if column in frame.columns}
