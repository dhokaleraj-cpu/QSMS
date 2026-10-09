"""R13 · Admin → System Settings (AI Assistant on/off and system information)."""
from __future__ import annotations

import streamlit as st

from core.auth import current_profile
from core.permissions import is_admin
from core.repository import Repository
from core.system_settings import AI_MODES, ai_mode_record, get_ai_mode, set_ai_mode
from core.ui import page_header, save_success_dialog, section_bar, stage_section


def render() -> None:
    page_header("System Settings", "Administrator controls for QCMS-wide features.", "Admin")
    profile = current_profile() or {}
    if not is_admin(profile):
        st.error("System Settings are restricted to the QCMS System Administrator.")
        return
    repo = Repository()
    mode, source = get_ai_mode(repo)
    from core.config import _secret
    key_ready = bool(str(_secret("ANTHROPIC_API_KEY", "") or "").strip())
    model = str(_secret("QCMS_AI_MODEL", "") or "claude-sonnet-5-5")

    with stage_section("A", "AI ASSISTANT (GLOBAL SEARCH)", "Switch the AI Assistant on or off for the whole company, or keep it for administrators only.", key="system_settings_ai"):
        c1, c2, c3 = st.columns(3, gap="small")
        c1.metric("Current mode", {"ALL": "Enabled · all users", "ADMIN_ONLY": "Admins only", "DISABLED": "Disabled"}[mode])
        c2.metric("Claude API key", "Configured" if key_ready else "Not configured")
        c3.metric("Model", model)
        if source == "secret":
            st.warning("The mode is fixed by the `QCMS_AI_MODE` secret (Streamlit secrets). Remove that line from secrets to manage it here.")
        record = ai_mode_record(repo)
        if record:
            st.caption(f"Last changed: {str(record.get('last_used_at') or record.get('updated_at') or '')[:19].replace('T', ' ')} UTC")
        with st.form("system_settings_ai_form", border=False):
            choice = st.radio("AI Assistant mode", list(AI_MODES), index=list(AI_MODES).index(mode), format_func=lambda v: AI_MODES[v], disabled=source == "secret")
            saved = st.form_submit_button("Save AI Assistant setting", type="primary", width="stretch", disabled=source == "secret")
        if saved:
            try:
                set_ai_mode(repo, choice, profile)
                save_success_dialog("AI Assistant setting saved", f"AI Assistant is now: **{AI_MODES[choice]}**.\n\nUsers see the change on their next page refresh (within about a minute).")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if not key_ready:
            st.info("To use the AI Assistant, the Claude API key must be set once: on the Mac run `bash /Users/dhokaleraj/QSMS/scripts/set_ai_key.sh`; for the online app add it in Streamlit Cloud → Settings → Secrets.")

    section_bar("SYSTEM INFORMATION", "Read-only.")
    from core.config import get_settings
    settings = get_settings()
    cache = str(_secret("QCMS_READ_CACHE_SECONDS", "45") or "45")
    st.markdown(f"- Version **{settings.version}**  \n- Read cache: **{cache} s** per user session (set `QCMS_READ_CACHE_SECONDS` in secrets; 0 = off)  \n- Company: **{settings.company_name}** · Plant **{settings.plant_code}**")
