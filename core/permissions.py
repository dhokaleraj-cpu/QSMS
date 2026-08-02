from __future__ import annotations

from typing import Mapping, Any

MASTER_WRITE_ROLES = {"ADMIN", "QUALITY_MANAGER", "MASTER_DATA"}
ADMIN_ROLES = {"ADMIN"}


def normalized_role(profile: Mapping[str, Any] | None) -> str:
    return str((profile or {}).get("role") or "VIEWER").strip().upper().replace(" ", "_")


def role_label(profile: Mapping[str, Any] | None) -> str:
    return normalized_role(profile).replace("_", " ").title()


def can_manage_masters(profile: Mapping[str, Any] | None) -> bool:
    return normalized_role(profile) in MASTER_WRITE_ROLES


def can_deactivate_records(profile: Mapping[str, Any] | None) -> bool:
    return normalized_role(profile) in MASTER_WRITE_ROLES


def is_admin(profile: Mapping[str, Any] | None) -> bool:
    return normalized_role(profile) in ADMIN_ROLES
