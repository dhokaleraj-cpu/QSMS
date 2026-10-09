"""R13 · System settings controlled by the QCMS Administrator.

Stored in the existing tenant-scoped ``master_value_catalog`` table (no SQL migration):
field_key ``qcms.system.ai_assistant_mode`` holds one ACTIVE row whose value is the
current mode. A secret ``QCMS_AI_MODE`` (ALL / ADMIN_ONLY / DISABLED) overrides the
database value for emergency switch-off from Streamlit Cloud secrets.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

AI_MODE_KEY = "qcms.system.ai_assistant_mode"
AI_MODES = {
    "ALL": "Enabled for all users (module View permissions still apply)",
    "ADMIN_ONLY": "Enabled for System Administrators only",
    "DISABLED": "Disabled for everyone",
}
DEFAULT_AI_MODE = "ALL"


def _secret_mode() -> str:
    try:
        from core.config import _secret
        value = str(_secret("QCMS_AI_MODE", "") or "").strip().upper()
    except Exception:
        value = ""
    return value if value in AI_MODES else ""


def ai_mode_record(repo: Any) -> dict | None:
    try:
        rows = repo.select("master_value_catalog", eq={"field_key": AI_MODE_KEY, "status": "ACTIVE"}, order_by="last_used_at", desc=True, limit=5)
    except Exception:
        return None
    for row in rows or []:
        if str(row.get("value_text") or "").strip().upper() in AI_MODES:
            return dict(row)
    return None


def get_ai_mode(repo: Any) -> tuple[str, str]:
    """Return (mode, source) where source is 'secret', 'admin' or 'default'."""
    secret = _secret_mode()
    if secret:
        return secret, "secret"
    row = ai_mode_record(repo)
    if row:
        return str(row.get("value_text")).strip().upper(), "admin"
    return DEFAULT_AI_MODE, "default"


def ai_allowed(mode: str, profile: Mapping[str, Any] | None) -> bool:
    from core.permissions import is_admin
    mode = str(mode or DEFAULT_AI_MODE).upper()
    if mode == "DISABLED":
        return False
    if mode == "ADMIN_ONLY":
        return is_admin(profile)
    return True


def set_ai_mode(repo: Any, mode: str, profile: Mapping[str, Any] | None) -> dict:
    from core.permissions import is_admin
    mode = str(mode or "").strip().upper()
    if mode not in AI_MODES:
        raise ValueError("Select a valid AI Assistant mode.")
    if not is_admin(profile):
        raise PermissionError("Only the QCMS System Administrator can change the AI Assistant setting.")
    now = datetime.now(timezone.utc).isoformat()
    rows = repo.select("master_value_catalog", eq={"field_key": AI_MODE_KEY}, limit=20, require_live=True)
    target = None
    for row in rows:
        value = str(row.get("value_text") or "").strip().upper()
        if value == mode:
            target = row
        elif str(row.get("status") or "") == "ACTIVE":
            repo.update("master_value_catalog", str(row["id"]), {"status": "INACTIVE", "updated_at": now})
    if target:
        return repo.update("master_value_catalog", str(target["id"]), {"status": "ACTIVE", "last_used_at": now, "updated_at": now, "usage_count": int(target.get("usage_count") or 0) + 1})
    return repo.insert("master_value_catalog", {"field_key": AI_MODE_KEY, "value_text": mode, "status": "ACTIVE", "last_used_at": now})


# ----------------------------------------------------------------------------- generic single values
MS365_TENANT_KEY = "qcms.system.ms365_tenant_id"
MS365_CLIENT_KEY = "qcms.system.ms365_client_id"


def get_system_value(repo: Any, field_key: str, *, secret_name: str = "") -> tuple[str, str]:
    """Return (value, source) for a single admin-managed value (secret overrides)."""
    if secret_name:
        try:
            from core.config import _secret
            value = str(_secret(secret_name, "") or "").strip()
        except Exception:
            value = ""
        if value:
            return value, "secret"
    try:
        rows = repo.select("master_value_catalog", eq={"field_key": field_key, "status": "ACTIVE"}, order_by="last_used_at", desc=True, limit=1)
    except Exception:
        rows = []
    if rows:
        return str(rows[0].get("value_text") or "").strip(), "admin"
    return "", "default"


def set_system_value(repo: Any, field_key: str, value: str, profile: Mapping[str, Any] | None) -> dict | None:
    from core.permissions import is_admin
    if not is_admin(profile):
        raise PermissionError("Only the QCMS System Administrator can change system settings.")
    value = str(value or "").strip()
    now = datetime.now(timezone.utc).isoformat()
    rows = repo.select("master_value_catalog", eq={"field_key": field_key}, limit=50, require_live=True)
    target = None
    for row in rows:
        if str(row.get("value_text") or "").strip().casefold() == value.casefold() and value:
            target = row
        elif str(row.get("status") or "") == "ACTIVE":
            repo.update("master_value_catalog", str(row["id"]), {"status": "INACTIVE", "updated_at": now})
    if not value:
        return None
    if target:
        return repo.update("master_value_catalog", str(target["id"]), {"status": "ACTIVE", "last_used_at": now, "updated_at": now})
    return repo.insert("master_value_catalog", {"field_key": field_key, "value_text": value, "status": "ACTIVE", "last_used_at": now})
