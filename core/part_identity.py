"""Part Number duplicate control (R11).

Two levels of control for Part Master identity:

* EXACT duplicate (always blocked): the Part Number or FSI Part Number is the same
  as an existing Part Number / FSI Part Number after ignoring case, spaces, dashes,
  dots, slashes and other separators ("40-256 626" == "40256626").
* SIMILAR (warn + confirm): four or more consecutive digits match an existing Part
  Number / FSI Part Number ("40256626" vs "40257237" share "4025"). The user must
  review the similar parts and tick "Not a duplicate" before saving.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

MIN_DIGIT_RUN = 4


def normalize_part_identity(value: Any) -> str:
    """Case/separator-insensitive identity used for EXACT duplicate checks."""
    return re.sub(r"[^0-9a-z]", "", str(value or "").casefold())


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def longest_common_digit_run(left: Any, right: Any) -> str:
    """Longest run of consecutive digits shared by both values (separators ignored)."""
    a, b = _digits(left), _digits(right)
    if not a or not b:
        return ""
    best_len = 0; best_end = 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best_len:
                    best_len = cur[j]; best_end = i
        prev = cur
    return a[best_end - best_len:best_end]


def find_part_conflicts(
    part_number: Any,
    fsi_part_number: Any,
    existing_rows: Iterable[Mapping[str, Any]],
    *,
    exclude_id: Any = None,
    min_digits: int = MIN_DIGIT_RUN,
) -> dict[str, list[dict[str, Any]]]:
    """Return {"exact": [...], "similar": [...]} conflicts for a Part being saved."""
    new_values = {
        "Part Number": str(part_number or "").strip(),
        "FSI Part Number": str(fsi_part_number or "").strip(),
    }
    exact: list[dict[str, Any]] = []
    similar: list[dict[str, Any]] = []
    skip = str(exclude_id or "")
    for row in existing_rows:
        if skip and str(row.get("id") or "") == skip:
            continue
        old_values = {
            "Part Number": str(row.get("part_number") or "").strip(),
            "FSI Part Number": str(row.get("fsi_part_number") or "").strip(),
        }
        row_exact: list[str] = []
        best_run = ""; best_pair = ("", "")
        for new_label, new_value in new_values.items():
            if not new_value:
                continue
            norm_new = normalize_part_identity(new_value)
            for old_label, old_value in old_values.items():
                if not old_value:
                    continue
                if norm_new and norm_new == normalize_part_identity(old_value):
                    row_exact.append(f"{new_label} {new_value} = existing {old_label} {old_value}")
                    continue
                run = longest_common_digit_run(new_value, old_value)
                if len(run) > len(best_run):
                    best_run = run; best_pair = (new_label, old_label)
        base = {
            "id": row.get("id"),
            "Part Number": old_values["Part Number"],
            "FSI Part Number": old_values["FSI Part Number"],
            "Part Description": str(row.get("part_name") or ""),
            "Status": str(row.get("status") or ""),
        }
        if row_exact:
            exact.append({**base, "Reason": "; ".join(row_exact)})
        elif len(best_run) >= min_digits:
            similar.append({**base, "Matching Digits": best_run, "Reason": f"{best_pair[0]} shares {len(best_run)} digits '{best_run}' with existing {best_pair[1]}"})
    similar.sort(key=lambda r: (-len(str(r.get("Matching Digits") or "")), str(r.get("Part Number"))))
    return {"exact": exact, "similar": similar}
