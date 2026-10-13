"""R24 · One "Sections shown on print" control used everywhere in the Purchase Order module
(PO entry, Order List, Edit PO, PO PDF, batch print and every PO email)."""
from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

import streamlit as st

# (flag, short label) in print order - short labels keep the 3-column grid tidy.
SECTION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("show_plant", "Plant / Company Branch"),
    ("show_vendor", "Vendor"),
    ("show_reference", "Reference Details"),
    ("show_old_po", "Old PO Details"),
    ("show_ship_to", "Ship To"),
    ("show_source_reference", "PO Source Reference"),
    ("show_technical", "RM Details & Technical Data"),
    ("show_price_history", "Price Revision History"),
    ("show_special_instructions", "Comments / Special Instructions"),
    ("show_approval_stamp", "Approval Stamp"),
)


def effective_options(header: Mapping[str, Any] | None = None) -> dict[str, bool]:
    """Saved Print Layout Designer defaults overlaid with this PO's own choice."""
    from core.print_designer import saved_layout
    layout = saved_layout("PURCHASE_ORDER")
    own = dict((header or {}).get("print_options") or {})
    return {flag: bool(own.get(flag, layout.get(flag, True))) for flag, _ in SECTION_OPTIONS}


def section_checkboxes(key: str, current: Mapping[str, Any] | None = None, *, disabled: bool = False, columns: int = 3) -> dict[str, bool]:
    """Checkbox grid like the Print Layout Designer (ticked = printed)."""
    current = dict(current or {})
    cols = st.columns(columns, gap="small")
    out: dict[str, bool] = {}
    for index, (flag, label) in enumerate(SECTION_OPTIONS):
        out[flag] = cols[index % columns].checkbox(label, value=bool(current.get(flag, True)), key=f"{key}_{flag}", disabled=disabled)
    hidden = [label for flag, label in SECTION_OPTIONS if not out[flag]]
    st.caption("Hidden on print: " + (", ".join(hidden) if hidden else "nothing - all sections print"))
    return out


def with_options(header: Mapping[str, Any], options: Mapping[str, Any] | None) -> dict[str, Any]:
    return {**dict(header or {}), "print_options": dict(options or {})}


def po_sections_panel(service: Any, po_id: str, header: Mapping[str, Any], perms: Mapping[str, Any], *, key: str,
                      expanded: bool = False, title: str = "Sections shown on print") -> dict[str, bool]:
    """Checkbox grid + preview + 'Save for this PO'. Returns the ticked options (used by downloads / emails)."""
    from core.purchase_order_reporting import purchase_order_pdf_bytes
    options: dict[str, bool] = {}
    with st.expander(title, expanded=expanded, icon=":material/checklist:"):
        options = section_checkboxes(f"{key}_{po_id}", effective_options(header))
        c1, c2 = st.columns(2, gap="small")
        if c1.button("Preview with these sections", width="stretch", key=f"{key}_{po_id}_preview", icon=":material/preview:"):
            st.session_state[f"{key}_{po_id}_pdf"] = purchase_order_pdf_bytes(with_options(header, options), service.purchase_order_items_for_print(po_id))
        if c2.button("Save for this PO", type="primary", width="stretch", key=f"{key}_{po_id}_save", disabled=not perms.get("can_edit", False), icon=":material/save:"):
            try:
                service.set_purchase_order_print_options(po_id, options)
                st.session_state.pop("_qcms_export_bytes_memo", None)
                st.success("Saved. Downloads, batch prints and emailed PDFs of this PO use these sections.")
            except Exception as exc:
                from core.db_errors import db_message
                st.error(db_message(exc))
        pdf = st.session_state.get(f"{key}_{po_id}_pdf")
        if pdf:
            show_pdf(pdf)
    return options


def show_pdf(pdf: bytes, pages: int = 2) -> None:
    try:
        import fitz
        with fitz.open(stream=pdf, filetype="pdf") as document:
            for index in range(min(pages, document.page_count)):
                st.image(document[index].get_pixmap(dpi=95).tobytes("png"), width="stretch")
    except Exception:
        st.caption("Inline preview needs PyMuPDF - use the download button to open the PDF.")


def email_sections_ui(header: Mapping[str, Any] | None, key: str) -> Callable[[], dict[str, bool]]:
    """Renders the grid inside an email panel and returns a getter for the chosen options."""
    st.markdown("**PO PDF attachment · sections shown on print**")
    options = section_checkboxes(key, effective_options(header))
    return lambda: options


def apply_to_notifier(notifier: Any, options: Mapping[str, Any] | None, po_ids: Sequence[str] | None = None) -> None:
    """The generated PO PDF attached to the next email(s) uses these sections (not saved on the PO)."""
    notifier.po_print_options = dict(options or {})
