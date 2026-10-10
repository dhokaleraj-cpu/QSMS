from __future__ import annotations

from typing import Any

import streamlit as st
from supabase import Client, create_client

from core.config import Settings, get_settings, is_preview_session


def new_client(settings: Settings | None = None) -> Client:
    settings = settings or get_settings()
    if not settings.supabase_ready:
        raise RuntimeError(
            "Supabase is not configured. Add SUPABASE_URL and "
            "SUPABASE_PUBLISHABLE_KEY to .streamlit/secrets.toml."
        )
    # R19: email sending through the edge function can take 10-20 s (SMTP); the default
    # 5 s functions timeout produced "The read operation timed out".
    try:
        from supabase import ClientOptions
        return create_client(settings.supabase_url, settings.supabase_public_key, options=ClientOptions(function_client_timeout=60))
    except Exception:
        return create_client(settings.supabase_url, settings.supabase_public_key)


def get_session_client() -> Client | None:
    if is_preview_session():
        return None
    client: Any = st.session_state.get("supabase_client")
    if client is None:
        client = new_client()
        st.session_state["supabase_client"] = client
    return client


def clear_session_client() -> None:
    st.session_state.pop("supabase_client", None)


def health_check() -> tuple[bool, str]:
    if is_preview_session():
        return True, "Preview data"
    try:
        client = get_session_client()
        if client is None:
            return False, "No Supabase session"
        client.table("profiles").select("id").limit(1).execute()
        return True, "Live Supabase"
    except Exception as exc:
        return False, str(exc)
