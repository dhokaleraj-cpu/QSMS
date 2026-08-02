from __future__ import annotations

import io
from typing import Any

import pandas as pd


def text_value(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def number_value(value: Any) -> float | None:
    if value is None or value == "" or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def find_label(df: pd.DataFrame, label: str) -> str:
    needle = label.casefold()
    for _, row in df.iterrows():
        values = list(row)
        for index, value in enumerate(values):
            if needle in text_value(value).casefold():
                for candidate in values[index + 1 :]:
                    if text_value(candidate):
                        return text_value(candidate)
    return ""


def parse_dimensional_workbook_bytes(content: bytes, source_name: str = "Dimensional Report.xlsx") -> dict[str, Any]:
    """Parse the user's controlled dimensional-report layout into reusable characteristics."""
    df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None, dtype=object)
    header_row: int | None = None
    for index, row in df.iterrows():
        joined = " | ".join(text_value(value).upper() for value in row.tolist())
        if "SR NO" in joined and "PARAMETER" in joined and "SPECIFICATION" in joined:
            header_row = int(index)
            break
    if header_row is None:
        raise ValueError("The workbook does not contain the expected Sr No / Parameter / Specification header row.")

    sample_row = header_row + 1
    sample_size = 0
    if sample_row < len(df):
        for value in df.iloc[sample_row, 5:15].tolist():
            number = number_value(value)
            if number is not None and 1 <= number <= 20:
                sample_size += 1
    sample_size = sample_size or 1

    title = ""
    for value in df.iloc[: max(header_row, 1), :].values.flatten().tolist():
        candidate = text_value(value)
        if "INSPECTION REPORT" in candidate.upper():
            title = candidate
            break

    characteristics: list[dict[str, Any]] = []
    sequence = 0
    for row_index in range(header_row + 2, len(df)):
        row = df.iloc[row_index].tolist()
        sr = text_value(row[0] if len(row) > 0 else "")
        parameter = text_value(row[1] if len(row) > 1 else "")
        if "REMARKS" in (sr + " " + parameter).upper():
            break
        if not parameter:
            continue
        sequence += 1
        min_raw = row[2] if len(row) > 2 else None
        max_raw = row[3] if len(row) > 3 else None
        lower = number_value(min_raw)
        upper = number_value(max_raw)
        min_text = text_value(min_raw)
        max_text = text_value(max_raw)
        if lower is not None and upper is not None:
            specification = f"{lower:g} - {upper:g}"
        else:
            specification = " / ".join(value for value in (min_text, max_text) if value)
        aid = text_value(row[4] if len(row) > 4 else "")
        source_observations = [value for value in row[5 : 5 + sample_size] if text_value(value)]
        variable = lower is not None or upper is not None or any(number_value(value) is not None for value in source_observations)
        combined = f"{parameter} {specification} {aid}".upper()
        characteristics.append(
            {
                "sequence_no": sequence,
                "characteristic_no": sr or str(sequence),
                "characteristic": parameter,
                "specification": specification or None,
                "lower_spec": lower,
                "upper_spec": upper,
                "unit": None,
                "characteristic_type": "VARIABLE" if variable else "ATTRIBUTE",
                "special_class": "CC" if "<CC>" in combined or " CC" in combined else None,
                "checking_aid_text": aid or None,
                "checking_method": aid or None,
                "sample_size": sample_size,
                "frequency": None,
                "reaction_plan": None,
                "report_section": "DIMENSIONAL",
                "is_mandatory": "REF" not in combined,
                "allow_na": "REF" in combined or aid.strip("_").strip() == "",
                "decimal_places": 3,
                "source_row": row_index + 1,
                "layout_metadata": {"example_observations": [text_value(value) for value in source_observations]},
                "status": "ACTIVE",
            }
        )

    return {
        "metadata": {
            "report_title": title or "DIMENSIONAL INSPECTION REPORT",
            "format_number": find_label(df, "FMT NO"),
            "format_revision": find_label(df, "REV. NO"),
            "revision_date": find_label(df, "REV.DATE"),
            "source_template_name": source_name,
            "default_sample_size": sample_size,
            "part_number": find_label(df, "PART NO"),
            "part_name": find_label(df, "PART NAME"),
            "drawing_number": find_label(df, "DRG NO"),
        },
        "characteristics": characteristics,
    }
