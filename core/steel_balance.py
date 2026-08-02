from __future__ import annotations

from typing import Iterable, Mapping, Any


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def remaining_planned_steel(planned_steel_kg: Any, inward_steel_kg: Any) -> float:
    """Return the unconsumed portion of one RMTC part plan."""
    return round(max(_number(planned_steel_kg) - _number(inward_steel_kg), 0.0), 3)


def committed_heat_steel(inward_steel_kg: Any, remaining_plan_rows: Iterable[Mapping[str, Any]]) -> float:
    """Heat commitment = actual inward steel + unconsumed active plan reservations."""
    remaining = sum(
        remaining_planned_steel(row.get("planned_steel_quantity_kg"), row.get("inward_steel_quantity_kg"))
        for row in remaining_plan_rows
    )
    return round(_number(inward_steel_kg) + remaining, 3)


def projected_part_plan_commitment(
    inward_heat_steel_kg: Any,
    other_remaining_planned_steel_kg: Any,
    planned_steel_kg: Any,
    inward_part_steel_kg: Any,
) -> float:
    """Projected commitment after creating or editing one part production plan."""
    current_remaining = remaining_planned_steel(planned_steel_kg, inward_part_steel_kg)
    return round(_number(inward_heat_steel_kg) + _number(other_remaining_planned_steel_kg) + current_remaining, 3)


def available_for_selected_inward(
    global_heat_steel_kg: Any,
    inward_heat_steel_kg: Any,
    other_remaining_planned_steel_kg: Any,
) -> float:
    """Steel available to the selected plan, including its reserved balance."""
    return round(max(
        _number(global_heat_steel_kg)
        - _number(inward_heat_steel_kg)
        - _number(other_remaining_planned_steel_kg),
        0.0,
    ), 3)
