from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _secret(name: str, default: str = "") -> str:
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
        for section in ("supabase", "app", "portal"):
            if section in st.secrets and name in st.secrets[section]:
                return str(st.secrets[section][name])
    except Exception:
        pass
    return os.getenv(name, default)


def _bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    company_name: str
    plant_code: str
    environment: str
    version: str
    timezone: str
    allow_preview: bool
    supabase_url: str
    supabase_public_key: str
    supabase_project_ref: str
    portal_url: str
    qsms_url: str
    export_shipment_url: str
    hrms_url: str

    @property
    def supabase_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_public_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        version = (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
    except Exception:
        version = "4.0.0-phase1"

    return Settings(
        app_name=_secret("QSMS_APP_NAME", "Quality Control Monitoring System"),
        company_name=_secret("QSMS_COMPANY_NAME", "Four Star Industries Pvt. Ltd."),
        plant_code=_secret("QSMS_PLANT_CODE", "D9"),
        environment=_secret("QSMS_ENVIRONMENT", "Phase 1 - Masters and Traceability"),
        version=version,
        timezone=_secret("QSMS_TIMEZONE", "Asia/Kolkata"),
        allow_preview=_bool(_secret("QSMS_ALLOW_PREVIEW", "true"), True),
        supabase_url=_secret("SUPABASE_URL"),
        supabase_public_key=(
            _secret("SUPABASE_PUBLISHABLE_KEY")
            or _secret("SUPABASE_ANON_KEY")
            or _secret("SUPABASE_KEY")
        ),
        supabase_project_ref=_secret("QSMS_PROJECT_REF", "xxrxopzxzyjnzumrwuwy"),
        portal_url=_secret("FSI_PORTAL_URL", "http://localhost:8500"),
        qsms_url=_secret("QSMS_APP_URL", "http://localhost:8510"),
        export_shipment_url=_secret("EXPORT_SHIPMENT_APP_URL", "http://localhost:8501"),
        hrms_url=_secret("HRMS_APP_URL", "http://localhost:8520"),
    )


def is_preview_session() -> bool:
    try:
        import streamlit as st

        return bool(st.session_state.get("_qsms_preview"))
    except Exception:
        return False
