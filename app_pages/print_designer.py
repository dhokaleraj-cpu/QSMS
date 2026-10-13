"""QCMS R21 · Print Layout Designer (design selector + layout editor with live preview)."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from core.auth import current_profile
from core.permissions import is_admin
from core.print_designer import (
    BAR_STYLES, DOCUMENTS, PO_SECTIONS, PRESET_NAMES, PRESETS, default_layout, layout_history,
    normalize_layout, read_layout, save_layout,
)
from core.repository import Repository
from core.ui import page_header, section_bar
from core.db_errors import db_message

REPORT_HEADINGS = {
    "RMTC": ["RMTC HEADER & TRACEABILITY", "GLOBAL HEAT QUANTITY BALANCE & RECORD LIST", "COVERED PART WORKSHEET REGISTER", "SUPPLIER RMTC MECHANICAL PROPERTIES", "Chemical Composition", "Jominy Results", "DI / Hardenability", "Mechanical Properties"],
    "METLAB": ["RAW MATERIAL METALLURGICAL TEST", "METALLURGICAL TEST RESULTS", "MICROSTRUCTURE PHOTOGRAPHS"],
    "DIMENSIONAL": ["OSP DIMENSIONAL INSPECTION REPORT", "INSPECTION RESULTS"],
    "BEND_TEST": [],
    "MATERIAL_INWARD": ["MATERIAL INWARD DETAILS"],
    "QUALITY_RECORD": ["RECORD DETAILS", "PHOTOGRAPHS"],
}


def _preview_images(pdf: bytes, pages: int = 2) -> list[bytes]:
    try:
        import fitz
    except Exception:
        return []
    out = []
    with fitz.open(stream=pdf, filetype="pdf") as document:
        for index in range(min(pages, document.page_count)):
            out.append(document[index].get_pixmap(dpi=90).tobytes("png"))
    return out


def _state_key(doc: str) -> str:
    return f"pd_layout_{doc}"


def render() -> None:
    page_header("Print Layout Designer", "Choose a design and change colours, headings, sections and text of every QCMS print.", "Admin")
    repo = Repository(); profile = current_profile() or {}
    admin = is_admin(profile)
    if not admin:
        st.info("View only — only the QCMS System Administrator can save print layouts.")

    c1, c2 = st.columns([2, 3])
    doc = c1.selectbox("Document", list(DOCUMENTS), format_func=lambda d: DOCUMENTS[d], key="pd_doc")
    key = _state_key(doc)
    if key not in st.session_state:
        st.session_state[key] = read_layout(repo, doc)
    layout = dict(st.session_state[key])
    is_po = doc == "PURCHASE_ORDER"

    # --- A. Design selector -------------------------------------------------
    section_bar("A · DESIGN SELECTOR")
    preset = c2.radio("Design", list(PRESETS), index=list(PRESETS).index(layout.get("preset", "B5")) if layout.get("preset") in PRESETS else 0,
                      format_func=lambda p: PRESET_NAMES[p], horizontal=True, key=f"pd_preset_{doc}")
    if preset != layout.get("preset"):
        layout = normalize_layout(doc, {**{k: v for k, v in layout.items() if k not in PRESETS["B1"]}, "preset": preset})
        st.session_state[key] = layout
        for suffix in ("accent", "rule", "remark", "conclusion", "head_fill", "label_fill", "remark_fill", "bar"):
            st.session_state.pop(f"pd_{suffix}_{doc}", None)

    left, right = st.columns([1.05, 1], gap="large")
    with left:
        # --- B. Theme --------------------------------------------------------
        section_bar("B · COLOURS & STYLE")
        t1, t2, t3, t4 = st.columns(4)
        layout["accent"] = t1.color_picker("Heading colour", layout["accent"], key=f"pd_accent_{doc}")
        layout["rule"] = t2.color_picker("Table lines", layout["rule"], key=f"pd_rule_{doc}")
        layout["remark"] = t3.color_picker("Remarks text", layout["remark"], key=f"pd_remark_{doc}")
        layout["conclusion"] = t4.color_picker("Conclusion text", layout.get("conclusion") or "#166534", key=f"pd_conclusion_{doc}")
        layout["bar"] = st.radio("Heading style", list(BAR_STYLES), index=list(BAR_STYLES).index(layout.get("bar", "fill")), format_func=lambda b: BAR_STYLES[b], horizontal=True, key=f"pd_bar_{doc}")
        if is_po:
            f1, f2, f3 = st.columns(3)
            for col, name, label in ((f1, "head_fill", "Table header fill"), (f2, "label_fill", "Label cell fill"), (f3, "remark_fill", "Remarks box fill")):
                use = col.checkbox(f"{label}", value=bool(layout.get(name)), key=f"pd_use_{name}_{doc}")
                layout[name] = col.color_picker(f"{label} colour", layout.get(name) or "#F3F8F8", key=f"pd_{name}_{doc}", label_visibility="collapsed") if use else ""
        else:
            s1, s2 = st.columns(2)
            layout["body_pt"] = s1.slider("Body text size (pt)", 7.0, 12.0, float(layout.get("body_pt") or 8.6), 0.2, key=f"pd_body_{doc}")
            layout["heading_pt"] = s2.slider("Heading size (pt)", 8.0, 14.0, float(layout.get("heading_pt") or 10.5), 0.5, key=f"pd_heading_{doc}")

        # --- C. Texts -----------------------------------------------------------
        section_bar("C · TITLE, COMPANY & FOOTER")
        if is_po:
            layout["title"] = st.text_input("Document title", layout.get("title") or "PURCHASE ORDER", key=f"pd_title_{doc}")
        layout["company_name"] = st.text_input("Company name on print" + (" (signatory)" if is_po else " (header)"), layout.get("company_name") or "", placeholder="Leave blank for the default", key=f"pd_company_{doc}")
        layout["footer_text"] = st.text_input("Footer text", layout.get("footer_text") or "", placeholder="Leave blank for the default", key=f"pd_footer_{doc}")

        # --- D. Sections -------------------------------------------------------
        if is_po:
            section_bar("D · SECTIONS SHOWN ON PRINT")
            cols = st.columns(3)
            for index, (title, flag) in enumerate({**PO_SECTIONS, "APPROVAL STAMP": "show_approval_stamp"}.items()):
                layout[flag] = cols[index % 3].checkbox(title.title(), value=bool(layout.get(flag, True)), key=f"pd_{flag}_{doc}")

        # --- E. Headings ---------------------------------------------------------
        section_bar("E · RENAME HEADINGS")
        headings = list(PO_SECTIONS) + ["ITEM #", "REQUISITIONER", "SHIP VIA", "INCOTERM", "DELIVERY DATE", "PAYMENT TERM"] if is_po else REPORT_HEADINGS.get(doc, [])
        labels = dict(layout.get("labels") or {})
        frame = pd.DataFrame([{"Original heading": h, "New heading": labels.get(h, "")} for h in dict.fromkeys([*headings, *labels])])
        edited = st.data_editor(frame, hide_index=True, width="stretch", num_rows="dynamic", key=f"pd_labels_{doc}",
                                column_config={"Original heading": st.column_config.TextColumn(required=True), "New heading": st.column_config.TextColumn(help="Leave blank to keep the original")})
        layout["labels"] = {str(r["Original heading"]).strip(): str(r["New heading"]).strip() for r in edited.to_dict("records") if str(r.get("Original heading") or "").strip() and str(r.get("New heading") or "").strip() and str(r.get("New heading")) != "None"}

    layout = normalize_layout(doc, layout)
    st.session_state[key] = layout

    with right:
        section_bar("LIVE PREVIEW (sample data)")
        try:
            from core.print_samples import sample_pdf
            pdf = sample_pdf(doc, layout)
            images = _preview_images(pdf)
            if images:
                for image in images:
                    st.image(image, width="stretch")
            else:
                st.caption("Preview images need PyMuPDF; download the sample PDF instead.")
            st.download_button("Download sample PDF", pdf, file_name=f"QCMS_{doc}_layout_preview.pdf", mime="application/pdf", icon=":material/picture_as_pdf:", width="stretch", key=f"pd_pdf_{doc}")
        except Exception as exc:
            st.error(f"Preview could not be rendered: {exc}")

    # --- Save / reset / history ---------------------------------------------------
    section_bar("SAVE")
    b1, b2, b3 = st.columns(3)
    if b1.button("Save layout", type="primary", width="stretch", disabled=not admin, key=f"pd_save_{doc}", icon=":material/save:"):
        try:
            save_layout(repo, doc, layout, profile)
            st.success(f"{DOCUMENTS[doc]} layout saved. All new prints use it now.")
        except Exception as exc:
            st.error(f"Could not save: {exc}")
    if b2.button("Reset to approved default", width="stretch", disabled=not admin, key=f"pd_reset_{doc}", icon=":material/restart_alt:"):
        st.session_state[key] = default_layout(doc)
        for k in [k for k in st.session_state if str(k).startswith("pd_") and str(k).endswith(f"_{doc}")]:
            st.session_state.pop(k, None)
        st.rerun()
    b3.download_button("Export layout (JSON)", json.dumps(layout, indent=2), file_name=f"QCMS_{doc}_layout.json", mime="application/json", width="stretch", key=f"pd_json_{doc}")

    with st.expander("Layout versions (restore an earlier layout)", icon=":material/history:"):
        rows = layout_history(repo, doc)
        if not rows:
            st.caption("No saved versions yet.")
        for row in rows:
            r1, r2 = st.columns([4, 1])
            r1.markdown(f"**{str(row.get('updated_at') or row.get('created_at') or '')[:16]}** · {row.get('status')}")
            if r2.button("Load", key=f"pd_restore_{row.get('id')}", disabled=not admin):
                try:
                    st.session_state[key] = normalize_layout(doc, json.loads(str(row.get("value_text") or "{}")))
                    for k in [k for k in st.session_state if str(k).startswith("pd_") and str(k).endswith(f"_{doc}")]:
                        st.session_state.pop(k, None)
                    st.rerun()
                except Exception as exc:
                    st.error(db_message(exc))
