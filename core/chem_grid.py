"""R38 · Shared horizontal chemistry / Jominy grid helpers (web pages, prints, tests).

Builds on ``core.analysis_grids`` (element order, ``chemistry_table`` / ``jominy_table``) and adds:

* Jominy J-notation parsing in sixteenths of an inch - ``J5/16"``, ``5/16"``, ``J 5``, ``J3``, ``5`` - and the
  inch <-> millimetre conversion (n/16 x 25.4 mm, two decimals half-up: J5/16" = 7.94 mm). Stored values are
  never changed; the mm / inch figures are display rows only.
* ``to_horizontal`` / ``from_horizontal``: transpose a list of stored row dicts (one row per element or distance)
  into a horizontal editor frame (elements / distances are COLUMNS) and back again, so ``st.data_editor`` can show
  a horizontal grid while the saved JSON / table rows keep exactly their existing shape.
* ``split_bands``: wide grids are cut into stacked bands (row titles repeated) so a print fits A4.
* ``reportlab_grid``: ReportLab flowables (one Table per band) for any horizontal grid, Design B look.

Public API (stable - agent D / Part Master, MetLAB, RMTC and prints import these)::

    ELEMENT_ORDER, ordered_elements(rows, field="element"), element_label(element, unit), element_key(name)
    chemistry_table(rows, [(title, key|callable)...]) -> [[ "Element", C%, Mn%...], [title, v...]...]
    jominy_table(rows, fields) -> [["Distance (inch)", 'J1/16"'...], ["Distance (mm)", "1.59"...], [title, v...]...]
    table_frame(table) -> DataFrame (unique column names; feed portal_table / st.data_editor)
    to_horizontal(rows, fields, column_label="element"|callable) -> editor DataFrame (column "Row" = line titles)
    from_horizontal(frame, rows, fields, column_label=...) -> copies of rows with edited fields (same stored shape)
    parse_sixteenths(v) / jominy_inch_to_mm(v) / jominy_distance_mm(row|label) / jominy_inches(v) / mm_to_sixteenths(mm)
        'J5/16"', 'J 5/16', '5/16"', 'J5', 5 -> 7.94 mm ; 'J1' -> 1.59 ; 'J20' -> 31.75 ; '7.9 mm' -> 7.9
    jominy_scale_rows(rows) -> [["Distance (in)", ...], ["Distance (mm)", ...]]
    split_bands(table, per_band=14), jominy_curve_table(curve), reportlab_grid(table, width, ...)
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable, Iterable, Mapping, Sequence

from core.analysis_grids import (  # noqa: F401 - re-exported for callers of the shared module
    ELEMENT_ORDER,
    JOMINY_MM_ROW,
    MM_PER_INCH,
    MM_PER_SIXTEENTH,
    chemistry_table,
    element_key,
    element_label,
    jominy_label,
    jominy_mm,
    jominy_table,
    ordered_elements,
    ordered_jominy,
    table_frame,
)

JOMINY_INCH_ROW = "Distance (in)"
ROW_TITLE = "Row"
PDF_BAND_COLUMNS = 14

_MM_LABEL = re.compile(r"^\s*J?\s*(\d+(?:\.\d+)?)\s*mm\s*$", re.I)
_FRACTION = re.compile(r"(\d+(?:\.\d+)?)\s*/\s*16")
_J_NUMBER = re.compile(r"^\s*J\s*(\d+(?:\.\d+)?)\s*(?:\"|in|inch)?\s*$", re.I)
_PLAIN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*$")


def _round(value: float, digits: int) -> float:
    quantum = Decimal(1).scaleb(-digits)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


# ----------------------------------------------------------------------------- Jominy scales
def parse_sixteenths(value: Any) -> float | None:
    """Jominy distance in sixteenths of an inch from J-notation; None when blank / a millimetre label.

    ``J5/16"`` -> 5, ``5/16"`` -> 5, ``J 5`` -> 5, ``J3`` -> 3, ``"5"`` -> 5, ``5`` -> 5, ``J1.5mm`` -> None.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value == value and value > 0 else None
    text = str(value).strip().replace("″", '"').replace("''", '"')
    if not text or _MM_LABEL.match(text):
        return None
    for pattern in (_FRACTION, _J_NUMBER, _PLAIN):
        match = pattern.search(text)
        if match:
            number = float(match.group(1))
            return number if number > 0 else None
    return None


def jominy_inch_to_mm(value: Any) -> float | None:
    """J-notation (sixteenths of an inch) -> millimetres, n / 16 x 25.4, two decimals (J5/16" = 7.94)."""
    sixteenths = parse_sixteenths(value)
    return jominy_mm(sixteenths) if sixteenths else None


def jominy_inches(value: Any, digits: int = 4) -> float | None:
    """J-notation -> decimal inches (J5/16" = 0.3125)."""
    sixteenths = parse_sixteenths(value)
    return _round(sixteenths / 16.0, digits) if sixteenths else None


def mm_to_inches(mm: Any, digits: int = 4) -> float | None:
    """Millimetres -> decimal inches (7.9375 mm = 0.3125 in)."""
    try:
        number = float(str(mm).lower().replace("mm", "").replace("j", "").strip()) if isinstance(mm, str) else float(mm)
    except (TypeError, ValueError):
        return None
    return _round(number / MM_PER_INCH, digits) if number > 0 else None


def mm_to_sixteenths(mm: Any, digits: int = 2) -> float | None:
    """Millimetres -> sixteenths of an inch (7.94 mm = 5.0, J1.5mm = 0.94)."""
    inches = mm_to_inches(mm, 8)
    return _round(inches * 16.0, digits) if inches else None


def jominy_distance_mm(row_or_label: Any) -> float | None:
    """Millimetre value of a stored Jominy row / label: sixteenths first, then a ``J1.5mm`` label, then distance_mm."""
    if isinstance(row_or_label, Mapping):
        row = row_or_label
        for candidate in (row.get("distance_16th"), row.get("distance_label")):
            mm = jominy_inch_to_mm(candidate)
            if mm is not None:
                return mm
        label = str(row.get("distance_label") or "")
        match = _MM_LABEL.match(label)
        if match:
            return _round(float(match.group(1)), 2)
        try:
            value = float(row.get("distance_mm"))
            return _round(value, 2) if value > 0 else None
        except (TypeError, ValueError):
            return None
    match = _MM_LABEL.match(str(row_or_label or ""))
    if match:
        return _round(float(match.group(1)), 2)
    return jominy_inch_to_mm(row_or_label)


def jominy_scale_rows(rows: Sequence[Mapping[str, Any]], *, blank: Any = "-") -> list[list[Any]]:
    """[["Distance (in)", 0.0625, ...], ["Distance (mm)", "1.59", ...]] for already ordered Jominy rows."""
    inch_line: list[Any] = [JOMINY_INCH_ROW]
    mm_line: list[Any] = [JOMINY_MM_ROW]
    for row in rows:
        mm = jominy_distance_mm(row)
        sixteenths = parse_sixteenths(row.get("distance_16th")) or parse_sixteenths(row.get("distance_label"))
        inches = _round(sixteenths / 16.0, 4) if sixteenths else (mm_to_inches(mm) if mm else None)
        inch_line.append(f"{inches:g}" if inches is not None else blank)
        mm_line.append(f"{mm:.2f}" if mm is not None else blank)
    return [inch_line, mm_line]


# ----------------------------------------------------------------------------- transpose (editor grids)
def unique_labels(labels: Iterable[Any]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for label in labels:
        text = str(label if label not in (None, "") else "-")
        seen[text] = seen.get(text, 0) + 1
        out.append(text if seen[text] == 1 else f"{text} ({seen[text]})")
    return out


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        if value != value:  # NaN
            return True
    except Exception:
        pass
    return isinstance(value, str) and not value.strip()


def to_horizontal(
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[tuple[str, str]],
    *,
    column_label: Callable[[Mapping[str, Any]], Any] | str = "element",
    row_title: str = ROW_TITLE,
):
    """Stored vertical rows -> horizontal DataFrame: one column per row (element / distance), one line per field.

    ``fields`` = [(line title, stored key), ...]. Columns follow the order of ``rows`` (order them first).
    """
    import pandas as pd

    labeler = column_label if callable(column_label) else (lambda r, key=column_label: r.get(key))
    columns = unique_labels(labeler(r) for r in rows)
    lines = []
    for title, key in fields:
        lines.append({row_title: title, **{column: row.get(key) for column, row in zip(columns, rows)}})
    return pd.DataFrame(lines, columns=[row_title, *columns])


def from_horizontal(
    frame,
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[tuple[str, str]],
    *,
    column_label: Callable[[Mapping[str, Any]], Any] | str = "element",
    row_title: str = ROW_TITLE,
    blank_to_none: bool = True,
) -> list[dict]:
    """Inverse of ``to_horizontal``: copies of ``rows`` with each field read back from the edited frame.

    Every other key of a stored row is kept untouched, so the saved JSON / table shape never changes.
    """
    labeler = column_label if callable(column_label) else (lambda r, key=column_label: r.get(key))
    columns = unique_labels(labeler(r) for r in rows)
    out = [dict(r) for r in rows]
    if frame is None or getattr(frame, "empty", True) or row_title not in getattr(frame, "columns", []):
        return out
    lines = {str(line.get(row_title)): line for _, line in frame.iterrows()}
    for title, key in fields:
        line = lines.get(str(title))
        if line is None:
            continue
        for column, row in zip(columns, out):
            if column not in frame.columns:
                continue
            value = line.get(column)
            row[key] = None if blank_to_none and _is_blank(value) else (value.item() if hasattr(value, "item") else value)
    return out


# ----------------------------------------------------------------------------- print bands
def split_bands(table: Sequence[Sequence[Any]], per_band: int = PDF_BAND_COLUMNS) -> list[list[list[Any]]]:
    """Cut a horizontal grid (column 0 = row titles) into bands of ``per_band`` value columns."""
    rows = [list(row) for row in table]
    if not rows:
        return []
    values = max(len(row) for row in rows) - 1
    if values <= per_band:
        return [rows]
    bands = []
    for start in range(1, values + 1, per_band):
        bands.append([[row[0], *row[start:start + per_band]] for row in rows])
    return bands


def jominy_curve_table(curve: Mapping[Any, Any], *, title: str = "Calculated HRC") -> list[list[Any]]:
    """QC Calculation Tools curve {sixteenth: HRC} -> horizontal table with inch header + Distance (mm) row."""
    rows = []
    for key, value in dict(curve or {}).items():
        sixteenths = parse_sixteenths(key)
        if sixteenths:
            rows.append({"distance_16th": int(sixteenths) if float(sixteenths).is_integer() else sixteenths, "value": value})
    return jominy_table(rows, [(title, "value")])


def reportlab_grid(
    table: Sequence[Sequence[Any]],
    width: float,
    *,
    per_band: int = PDF_BAND_COLUMNS,
    first_width: float | None = None,
    font_size: float = 6.8,
    mm_row_titles: Sequence[str] = (JOMINY_MM_ROW, JOMINY_INCH_ROW),
) -> list:
    """Horizontal grid -> list of ReportLab Tables (bands of ``per_band`` value columns, row titles repeated).

    Navy header row (Design B), row titles bold, the Jominy mm / inch rows tinted so both scales read at a glance.
    """
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm as MM
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    navy = colors.HexColor("#0B2A4A")
    cell = ParagraphStyle("ChemGridCell", fontName="Helvetica", fontSize=font_size, leading=font_size + 1.6, alignment=1)
    head = ParagraphStyle("ChemGridHead", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)
    title = ParagraphStyle("ChemGridTitle", parent=cell, fontName="Helvetica-Bold", alignment=0)
    out: list = []
    first = first_width or 24 * MM
    for band in split_bands(table, per_band):
        values = max(len(row) for row in band) - 1
        col = (width - first) / max(values, 1)
        data = []
        for r_index, row in enumerate(band):
            padded = list(row) + [""] * (values + 1 - len(row))
            style_first = head if r_index == 0 else title
            data.append([Paragraph(str(padded[0]), style_first),
                         *[Paragraph("" if v is None else str(v), head if r_index == 0 else cell) for v in padded[1:]]])
        grid = Table(data, colWidths=[first, *([col] * values)], repeatRows=1, hAlign="LEFT")
        commands = [
            ("BACKGROUND", (0, 0), (-1, 0), navy), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#9AA9BA")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 1), ("RIGHTPADDING", (0, 0), (-1, -1), 1),
        ]
        for r_index, row in enumerate(band):
            if r_index and str(row[0]) in mm_row_titles:
                commands.append(("BACKGROUND", (0, r_index), (-1, r_index), colors.HexColor("#E8F0F8")))
        grid.setStyle(TableStyle(commands))
        out.extend([grid, Spacer(1, 2 * MM)])
    return out
