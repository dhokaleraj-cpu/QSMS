"""R37 · Streamlit control: Preview / Download the print-layout PDF of any record.

``pdf_actions(table, record_id, key=...)`` renders two buttons -

* **Preview** opens a large dialog with the PDF (``st.pdf`` when the streamlit-pdf component is installed, otherwise
  every page rendered to an image with PyMuPDF) plus a download button inside the dialog;
* **Download PDF** downloads the same file.

The PDF comes from ``core.universal_pdf.record_pdf`` (dedicated controlled layout or the Purchase-Order style
controlled record print).  Bytes are cached per record / ``updated_at`` / customer-safe flag in the session, so
reruns do not rebuild the document.  Inside an existing ``st.dialog`` (dialogs cannot be nested) pass
``inline=True``: the preview then opens below the buttons.
"""
from __future__ import annotations

import time
from typing import Any, Mapping

import streamlit as st

_CACHE_KEY = "_qcms_pdf_actions_cache"
_CACHE_SECONDS = 120
_CACHE_SIZE = 16


def _cache_token(table: str, record_id: str, record: Mapping[str, Any] | None, safe: bool) -> str:
    stamp = str((record or {}).get("updated_at") or "")
    return f"{table}:{record_id}:{stamp}:{int(bool(safe))}"


def cached_record_pdf(table: str, record_id: str, *, repo: Any = None, record: Mapping[str, Any] | None = None,
                      customer_safe: bool = False) -> tuple[str, bytes]:
    """``record_pdf`` with a short per-session cache (keyed by record id, ``updated_at`` and customer-safe flag)."""
    from core.universal_pdf import record_pdf
    cache: dict[str, tuple[float, tuple[str, bytes]]] = st.session_state.setdefault(_CACHE_KEY, {})
    token = _cache_token(table, record_id, record, customer_safe)
    hit = cache.get(token)
    stamped = bool((record or {}).get("updated_at"))
    if hit and (stamped or time.time() - hit[0] <= _CACHE_SECONDS):
        return hit[1]
    if len(cache) >= _CACHE_SIZE:
        for old in sorted(cache, key=lambda k: cache[k][0])[: len(cache) - _CACHE_SIZE + 1]:
            cache.pop(old, None)
    value = record_pdf(table, record_id, repo, customer_safe=customer_safe, record=record)
    cache[token] = (time.time(), value)
    return value


def render_pdf(pdf: bytes, *, key: str, height: int = 820, max_pages: int = 12) -> None:
    """Inline PDF viewer: st.pdf (streamlit-pdf component) when installed, else page images via PyMuPDF."""
    import importlib.util
    if hasattr(st, "pdf") and importlib.util.find_spec("streamlit_pdf") is not None:
        try:
            st.pdf(pdf, height=height, key=f"{key}_viewer")
            return
        except Exception:
            pass
    try:
        import fitz
        with fitz.open(stream=pdf, filetype="pdf") as document:
            count = document.page_count
            for index in range(min(max_pages, count)):
                st.image(document[index].get_pixmap(dpi=110).tobytes("png"), width="stretch")
            if count > max_pages:
                st.caption(f"Showing {max_pages} of {count} pages - download the PDF for every page.")
    except Exception:
        st.caption("Inline preview needs PyMuPDF - use Download PDF to open the document.")


@st.dialog("Print layout preview", width="large")
def _preview_dialog(table: str, record_id: str, key: str, safe: bool, record: Mapping[str, Any] | None) -> None:
    try:
        file_name, pdf = cached_record_pdf(table, record_id, record=record, customer_safe=safe)
    except Exception as exc:
        from core.db_errors import db_message
        st.error(f"Print PDF could not be prepared: {db_message(exc)}")
        return
    st.caption(f"{file_name}" + (" · customer-safe copy" if safe else ""))
    st.download_button("Download PDF", data=pdf, file_name=file_name, mime="application/pdf", icon=":material/download:",
                       type="primary", key=f"{key}_dlg_download", on_click="ignore")
    render_pdf(pdf, key=f"{key}_dlg")


def pdf_actions(table: str, record_id: str | None, *, key: str, label: str = "Print layout", repo: Any = None,
                record: Mapping[str, Any] | None = None, customer_safe: bool | None = False, inline: bool = False,
                container: Any = None) -> None:
    """Preview + Download buttons for the print-layout PDF of one record.

    ``customer_safe``: ``False`` internal copy (default), ``True`` always customer-safe (supplier-facing screens),
    ``None`` shows a "Customer-safe copy" toggle.  ``inline=True`` previews below the buttons (use inside a dialog).
    """
    record_id = str(record_id or (record or {}).get("id") or "")
    table = str(table or "")
    if not table or not record_id:
        return
    host = container if container is not None else st
    slot = f"qcms_pdfa_{key}_{table}_{record_id}"
    safe = bool(customer_safe)
    if customer_safe is None:
        safe = bool(host.toggle("Customer-safe copy (for supplier / vendor)", value=False, key=f"{slot}_safe",
                                help="Removes customer name / code / PO / order no / customer part no / delivery date."))
    c1, c2 = host.columns(2, gap="small")
    preview = c1.button(f"Preview {label} PDF", key=f"{slot}_preview", icon=":material/preview:", width="stretch")

    try:
        file_name, pdf = cached_record_pdf(table, record_id, repo=repo, record=record, customer_safe=safe)
    except Exception as exc:
        from core.db_errors import db_message
        host.error(f"Print PDF could not be prepared: {db_message(exc)}")
        return
    c2.download_button(f"Download {label} PDF", data=pdf, file_name=file_name, mime="application/pdf",
                       icon=":material/picture_as_pdf:", width="stretch", key=f"{slot}_download", on_click="ignore")
    if inline:
        show_key = f"{slot}_show"
        if preview:
            st.session_state[show_key] = not st.session_state.get(show_key, False)
        if st.session_state.get(show_key):
            render_pdf(pdf, key=slot)
        return
    if preview:
        # the PDF is already in the session cache, so the dialog never re-reads the record
        _preview_dialog(table, record_id, slot, safe, dict(record) if record else None)


def preview_button(table: str, record_id: str | None, *, key: str, label: str = "Preview print layout",
                   record: Mapping[str, Any] | None = None, customer_safe: bool = False, container: Any = None) -> None:
    """One "Preview print layout" button (dialog with the PDF and its download) for screens that already have a
    Download PDF button - the PDF is only built when the button is clicked."""
    record_id = str(record_id or (record or {}).get("id") or "")
    if not table or not record_id:
        return
    host = container if container is not None else st
    slot = f"qcms_pdfp_{key}_{table}_{record_id}"
    if host.button(label, key=f"{slot}_preview", icon=":material/preview:", width="stretch"):
        _preview_dialog(str(table), record_id, slot, bool(customer_safe), dict(record) if record else None)


def register_actions(frame: Any, title: str, *, key: str, filters_text: str = "") -> None:
    """Preview PDF + Download PDF of a (filtered) register / report table (landscape, totals row)."""
    from core.record_print import register_print_panel
    register_print_panel(frame, title, key=key, filters_text=filters_text)


__all__ = ["pdf_actions", "preview_button", "register_actions", "render_pdf", "cached_record_pdf"]
