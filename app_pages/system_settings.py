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
    from core.ai_assistant import PROVIDERS, resolve_provider
    provider, provider_key, model = resolve_provider(lambda name, default="": _secret(name, default))
    key_ready = bool(provider_key)

    with stage_section("A", "AI ASSISTANT (GLOBAL SEARCH)", "Switch the AI Assistant on or off for the whole company, or keep it for administrators only.", key="system_settings_ai"):
        c1, c2, c3 = st.columns(3, gap="small")
        c1.metric("Current mode", {"ALL": "Enabled · all users", "ADMIN_ONLY": "Admins only", "DISABLED": "Disabled"}[mode])
        c2.metric("AI engine", (PROVIDERS[provider]["label"].split(" ·")[0] + " · key set") if key_ready else "No key configured")
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
            st.info("To use the AI Assistant, set an API key once: on the Mac run `bash /Users/dhokaleraj/QSMS/scripts/set_ai_key.sh` and pick **Google Gemini (FREE)** or Groq (FREE), Claude or OpenAI (paid); for the online app paste the printed lines in Streamlit Cloud → Settings → Secrets.")
        st.caption("Free tiers (Gemini, Groq) are rate-limited and the provider may use free-tier prompts to improve its services. Only rows the user is allowed to see are sent, but for strictly confidential data use a paid key.")

    from core.system_settings import MS365_CLIENT_KEY, MS365_TENANT_KEY, get_system_value, set_system_value
    with stage_section("B", "MICROSOFT 365 SIGN-IN FOR EMAIL", "One-time setup so every user can connect their own Office 365 mailbox (Email module). These IDs are not passwords.", key="system_settings_ms365"):
        tenant, t_src = get_system_value(repo, MS365_TENANT_KEY, secret_name="QCMS_MS365_TENANT_ID")
        client, c_src = get_system_value(repo, MS365_CLIENT_KEY, secret_name="QCMS_MS365_CLIENT_ID")
        cred_ready = bool(str(_secret("QCMS_CREDENTIAL_KEY", "") or "").strip())
        c1, c2, c3 = st.columns(3, gap="small")
        c1.metric("Tenant ID", "Set" if tenant else "Missing")
        c2.metric("Client ID", "Set" if client else "Missing")
        c3.metric("Encryption key", "Set" if cred_ready else "Missing")
        with st.expander("Step-by-step: register QCMS in Microsoft Entra (Microsoft 365 admin, ~5 minutes)", expanded=not (tenant and client)):
            st.markdown(
                "1. Open **entra.microsoft.com** with a Microsoft 365 administrator account.\n"
                "2. **Identity → Applications → App registrations → New registration**. Name: `QCMS Email`. Supported account types: **Accounts in this organizational directory only**. Redirect URI: leave empty. Click **Register**.\n"
                "3. On the app **Overview** page copy **Application (client) ID** and **Directory (tenant) ID** into the boxes below.\n"
                "4. **Authentication** → *Advanced settings* → **Allow public client flows = Yes** → **Save**.\n"
                "5. **API permissions → Add a permission → Microsoft Graph → Delegated permissions** → tick **Mail.Send**, **User.Read**, **offline_access** → **Add permissions**.\n"
                "6. Click **Grant admin consent for Four Star Industries** → **Yes**.\n"
                "7. Save here. Each user then opens **Email → My Email Settings → Connect Microsoft 365**.\n\n"
                "No client secret is needed — QCMS never receives anyone's Microsoft password."
            )
        with st.form("system_settings_ms365_form", border=False):
            t_in = st.text_input("Directory (tenant) ID", value=tenant, disabled=t_src == "secret")
            c_in = st.text_input("Application (client) ID", value=client, disabled=c_src == "secret")
            ms_saved = st.form_submit_button("Save Microsoft 365 settings", type="primary", width="stretch")
        if ms_saved:
            try:
                import re as _re
                for label, value in (("Tenant ID", t_in), ("Client ID", c_in)):
                    if value.strip() and not _re.fullmatch(r"[0-9a-fA-F-]{36}", value.strip()):
                        raise ValueError(f"{label} must be a 36-character ID like 1a2b3c4d-....")
                if t_src != "secret":
                    set_system_value(repo, MS365_TENANT_KEY, t_in, profile)
                if c_src != "secret":
                    set_system_value(repo, MS365_CLIENT_KEY, c_in, profile)
                save_success_dialog("Microsoft 365 settings saved", "Users can now connect their mailbox in **Email → My Email Settings**.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if not cred_ready:
            st.warning("Encryption key `QCMS_CREDENTIAL_KEY` is missing. The R14 updater adds it to your Mac's secrets automatically; for the online app copy your secrets to Streamlit Cloud (see release notes).")

    section_bar("SYSTEM INFORMATION", "Read-only.")
    from core.config import get_settings
    settings = get_settings()
    cache = str(_secret("QCMS_READ_CACHE_SECONDS", "45") or "45")
    st.markdown(f"- Version **{settings.version}**  \n- Read cache: **{cache} s** per user session (set `QCMS_READ_CACHE_SECONDS` in secrets; 0 = off)  \n- Company: **{settings.company_name}** · Plant **{settings.plant_code}**")
