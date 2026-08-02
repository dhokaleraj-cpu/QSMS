from __future__ import annotations

import streamlit as st

from core.ui import page_header, subpage_navigation, template_catalog, template_download_row


def render() -> None:
    subpage_navigation(("dashboard", "Dashboard", ":material/dashboard:"), ("masters", "Masters", ":material/dataset:"), ("inspection-home", "Inspections", ":material/biotech:"))
    page_header("Template Centre")
    catalog = template_catalog()
    for start in range(0, len(catalog), 3):
        row = catalog[start:start + 3]
        cols = st.columns(len(row), gap="medium")
        for index, (filename, title, detail) in enumerate(row):
            with cols[index]:
                with st.container(border=True):
                    st.markdown(f"**{title}**")
                    st.caption(detail)
                    template_download_row([(filename, f"Download {title} Template")], key_prefix=f"centre_{start}_{index}")
