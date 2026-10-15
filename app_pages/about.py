"""R33 · About STAWN QCMS page (version, developer, copyright, licence, security, support)."""
from __future__ import annotations

import html
from pathlib import Path

import streamlit as st

from core import about
from core.config import get_settings
from core.ui import page_header, section_bar


def _rows(pairs) -> str:
    return "".join(
        f"<tr><td style='padding:6px 10px;color:#5C7778;width:34%'>{html.escape(k)}</td>"
        f"<td style='padding:6px 10px;font-weight:600'>{html.escape(v)}</td></tr>" for k, v in pairs
    )


def render() -> None:
    settings = get_settings()
    page_header(f"About {about.PRODUCT}", f"{about.TAGLINE} · developed by {about.COMPANY}", "About")
    icon = Path(__file__).resolve().parents[1] / "assets" / "stawn_qcms_icon.png"
    left, right = st.columns([1, 4], gap="small")
    if icon.exists():
        left.image(str(icon), width=110)
    right.markdown(f"### {about.PRODUCT}\n{about.TAGLINE}\n\n**Website version {settings.version}** · Android app v3.3.0")

    section_bar("DEVELOPER")
    st.markdown(f"<table style='width:100%;border-collapse:collapse'>{_rows(about.DEVELOPER)}</table>", unsafe_allow_html=True)
    section_bar("LICENSED TO")
    st.markdown(f"<table style='width:100%;border-collapse:collapse'>{_rows(about.LICENSEE)}</table>", unsafe_allow_html=True)
    section_bar("COPYRIGHT")
    st.markdown(f"**{about.COPYRIGHT}**")
    for para in about.NOTICE:
        st.caption(para)
    section_bar("DATA & SECURITY")
    st.markdown("\n".join(f"- {line}" for line in about.SECURITY))
    section_bar("SUPPORT")
    st.markdown(f"{about.SUPPORT}  \n[✉ {about.EMAIL}](mailto:{about.EMAIL})")
    st.caption(about.COPYRIGHT)
