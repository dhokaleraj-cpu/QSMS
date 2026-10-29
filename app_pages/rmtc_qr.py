"""R40 · RMTC QR Codes (route ``rmtc-qr``, RMTC navigation group directly below the RMTC pages).

Approved RMTC list with search / filters (supplier, grade, heat, approval date), the PUBLIC QR of the selected RMTC
(no login: anyone with the QR opens and downloads all RMTC documents through the Edge Function
``qcms-rmtc-certificate``), the document list exactly as the scan PDF shows it (scan = one PDF: index page + all documents), downloads (QR PNG / JPEG / PDF,
100 x 60 mm label, ZIP of all documents, combined PDF), refresh / revoke, and the bulk actions
"Create public QR + certificate for all approved RMTCs without one" and "Print labels for selected".
Permission module RMTC_ENTRY (view = page, edit / approve = create, refresh, revoke).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.db_errors import db_message
from core.qr_codes import is_rmtc_approved, safe_file_token, valid_token, certificate_url
from core.rmtc_qr import (PUBLIC_NOTICE, RMTCQRLabelService, labels_pdf_bytes, qr_jpeg, qr_pdf)
from core.ui import page_header, portal_table, section_bar


def _date(value: Any) -> date | None:
    try:
        return datetime.fromisoformat(str(value or "").replace("Z", "+00:00")).date()
    except Exception:
        return None


def _load(repo: Any) -> tuple[list[dict], dict[str, str], dict[str, str], dict[str, dict]]:
    rows = [dict(r) for r in repo.select("rmtc_approvals", order_by="decision_at", desc=True, limit=5000) or [] if is_rmtc_approved(r)]
    grades = {str(g.get("id")): str(g.get("grade_code") or g.get("grade_name") or "") for g in repo.select("material_grades", limit=5000) or []}
    suppliers = {str(p.get("id")): str(p.get("party_name") or "") for p in repo.select("parties", limit=10000) or []}
    tokens: dict[str, dict] = {}
    try:
        for t in repo.select("rmtc_qr_tokens", eq={"revoked": False}, order_by="created_at", desc=True, limit=10000) or []:
            tokens.setdefault(str(t.get("rmtc_approval_id")), dict(t))
    except Exception:
        tokens = {}
    return rows, grades, suppliers, tokens


def render() -> None:
    page_header("RMTC QR Codes", "Public material-location QR codes of approved RMTCs. " + PUBLIC_NOTICE, "RMTC")
    perms = current_permissions("RMTC_ENTRY")
    can_manage = bool(perms.get("can_edit") or perms.get("can_approve"))
    service = RMTCQRLabelService()
    repo = service.repo
    for note in st.session_state.pop("rmtc_qr_flash", None) or []:
        (st.warning if any(w in note for w in ("could not", "No active", "not ")) else st.info)(note)
    try:
        rows, grades, suppliers, tokens = _load(repo)
    except Exception as exc:
        st.error(db_message(exc)); return
    if not rows:
        st.info("No approved RMTC yet. QR codes are created when an RMTC is approved."); return

    # ------------------------------------------------------------------ filters
    f1, f2, f3, f4 = st.columns([2, 1.4, 1.2, 1.4], gap="small")
    search = f1.text_input("Search RMTC / Heat / Heat Code / Supplier RMTC", key="rmtc_qr_search")
    supplier_options = sorted({suppliers.get(str(r.get("supplier_id")), "") for r in rows} - {""})
    grade_options = sorted({grades.get(str(r.get("material_grade_id")), "") for r in rows} - {""})
    supplier = f2.selectbox("Supplier", ["All"] + supplier_options, key="rmtc_qr_supplier")
    grade = f3.selectbox("Grade", ["All"] + grade_options, key="rmtc_qr_grade")
    status = f4.selectbox("Public QR", ["All", "With public QR + certificate", "Without public QR / certificate"], key="rmtc_qr_status")
    d1, d2, _ = st.columns([1, 1, 2.6], gap="small")
    dates = [d for d in (_date(r.get("decision_at") or r.get("approved_at")) for r in rows) if d]
    date_from = d1.date_input("Approved from", value=min(dates) if dates else None, format="DD-MM-YYYY", key="rmtc_qr_from")
    date_to = d2.date_input("Approved to", value=max(dates) if dates else None, format="DD-MM-YYYY", key="rmtc_qr_to")

    def has_public(r: dict) -> bool:
        tok = tokens.get(str(r.get("id"))) or {}
        return valid_token(tok.get("token")) and bool(str(tok.get("certificate_path") or "").strip())

    def keep(r: dict) -> bool:
        text = " ".join(str(r.get(k) or "") for k in ("rmtc_number", "heat_number", "heat_code", "certificate_reference")).casefold()
        if search and search.casefold() not in text:
            return False
        if supplier != "All" and suppliers.get(str(r.get("supplier_id")), "") != supplier:
            return False
        if grade != "All" and grades.get(str(r.get("material_grade_id")), "") != grade:
            return False
        approved = _date(r.get("decision_at") or r.get("approved_at"))
        if approved and date_from and approved < date_from:
            return False
        if approved and date_to and approved > date_to:
            return False
        if status.startswith("With ") and not has_public(r):
            return False
        if status.startswith("Without") and has_public(r):
            return False
        return True

    filtered = [r for r in rows if keep(r)]
    frame = pd.DataFrame([{
        "RMTC": r.get("rmtc_number"), "Heat": r.get("heat_number"), "Heat Code": r.get("heat_code"),
        "Grade": grades.get(str(r.get("material_grade_id")), ""), "Supplier": suppliers.get(str(r.get("supplier_id")), ""),
        "Approved": (_date(r.get("decision_at") or r.get("approved_at")) or "").__str__(),
        "Disposition": str(r.get("disposition") or "").replace("_", " ").title(),
        "Public QR": "Yes" if has_public(r) else "No",
    } for r in filtered])
    section_bar("APPROVED RMTC", f"{len(filtered)} of {len(rows)} approved RMTC(s) · {sum(1 for r in rows if has_public(r))} with public QR + certificate")
    if frame.empty:
        st.info("No approved RMTC matches the filters.")
    else:
        portal_table(frame, hide_index=True, width="stretch", height=min(420, 40 + 32 * len(frame)))

    # ------------------------------------------------------------------ bulk actions
    with st.expander("Bulk actions", expanded=False, icon=":material/library_add_check:"):
        missing = [r for r in rows if not has_public(r)]
        st.caption(f"{len(missing)} approved RMTC(s) without a public QR + certificate. Existing codes are kept (skipped).")
        if st.button("Create public QR + certificate for all approved RMTCs without one", icon=":material/qr_code_2:",
                     type="primary", disabled=not can_manage or not missing, key="rmtc_qr_bulk_create"):
            bar = st.progress(0.0, text="Starting…")
            summary = service.bulk_create_missing(missing, progress=lambda i, n, no: bar.progress(min(i / max(n, 1), 1.0), text=f"{i} / {n} · RMTC {no}"))
            notes = [f"Public QR + certificate created for {summary['created']} RMTC(s); {summary['skipped']} skipped (already had one); {summary['failed']} failed."]
            notes.extend(summary.get("warnings") or [])
            st.session_state["rmtc_qr_flash"] = notes
            st.rerun()
        labels = {str(r["id"]): f"{r.get('rmtc_number')} · {r.get('heat_number')}" for r in filtered}
        chosen = st.multiselect("RMTCs for label printing", list(labels), format_func=lambda x: labels[x], key="rmtc_qr_label_pick",
                                placeholder="Select RMTCs (filtered list)")
        if chosen:
            try:
                items = []
                for rid in chosen:
                    record = next(r for r in filtered if str(r["id"]) == rid)
                    assets = service.assets(record)
                    items.append((assets["url"], assets["lines"]))
                st.download_button(f"Print labels for selected ({len(items)}) · 100 x 60 mm PDF", labels_pdf_bytes(items),
                                   file_name=f"RMTC_QR_Labels_{datetime.now():%Y%m%d_%H%M}.pdf", mime="application/pdf",
                                   icon=":material/print:", width="stretch", key="rmtc_qr_labels_pdf")
                if any(not tokens.get(rid) for rid in chosen):
                    st.caption("Some selected RMTCs have no public QR yet - their labels open QCMS (login). Create the public QR first.")
            except Exception as exc:
                st.warning(f"Labels could not be prepared: {exc}")

    # ------------------------------------------------------------------ selected RMTC
    if not filtered:
        return
    options = {str(r["id"]): f"{r.get('rmtc_number')} · {r.get('heat_number')} · {suppliers.get(str(r.get('supplier_id')), '')}" for r in filtered}
    rid = st.selectbox("Selected RMTC", list(options), format_func=lambda x: options[x], key="rmtc_qr_selected")
    record = next(r for r in filtered if str(r["id"]) == rid)
    _render_selected(service, record, tokens.get(rid) or {}, can_manage=can_manage)


def _render_selected(service: RMTCQRLabelService, record: dict, token_row: dict, *, can_manage: bool) -> None:
    rid = str(record.get("id"))
    number = record.get("rmtc_number") or "-"
    section_bar(f"RMTC {number} · PUBLIC QR", PUBLIC_NOTICE)
    try:
        assets = service.assets(record)
    except Exception as exc:
        st.warning(f"QR could not be prepared: {exc}"); return
    public_url = certificate_url(str(token_row.get("token"))) if valid_token(token_row.get("token")) else ""
    c1, c2 = st.columns([1, 2], gap="medium")
    with c1:
        st.image(assets["png"], width=250)
    with c2:
        st.markdown("\n\n".join(f"**{line}**" if i == 0 else line for i, line in enumerate(assets["lines"])))
        if public_url:
            st.markdown("**Public link (copy):**")
            st.code(public_url, language=None)
            st.link_button("Open what the scan shows (all documents in one PDF)", public_url, icon=":material/open_in_new:", width="content")
            st.caption("Scanning the QR opens one PDF: page 1 lists the RMTC data and every document (with Download / ZIP links), followed by the certificate and all PDF / image attachments.")
        else:
            st.warning("No public QR code yet - the QR below opens QCMS (login required). Press \"Refresh public QR / certificate\".")
            st.code(assets["url"], language=None)
        if public_url and not str(token_row.get("certificate_path") or "").strip():
            st.caption("The customer-safe certificate PDF is not stored yet - press \"Refresh public QR / certificate\".")
    stem = assets["file_stem"]
    b1, b2, b3, b4 = st.columns(4, gap="small")
    b1.download_button("QR PNG", assets["png"], file_name=f"{stem}_QR.png", mime="image/png", icon=":material/image:", width="stretch", key=f"rq_png_{rid}")
    try:
        b2.download_button("QR JPEG", qr_jpeg(assets["url"], assets["lines"]), file_name=f"{stem}_QR.jpg", mime="image/jpeg", icon=":material/photo:", width="stretch", key=f"rq_jpg_{rid}")
    except Exception as exc:
        b2.caption(f"JPEG not available: {exc}")
    try:
        b3.download_button("QR PDF (A6)", qr_pdf(assets["url"], assets["lines"], title=f"RMTC {number} QR"), file_name=f"{stem}_QR.pdf", mime="application/pdf", icon=":material/picture_as_pdf:", width="stretch", key=f"rq_pdf_{rid}")
    except Exception as exc:
        b3.caption(f"PDF not available: {exc}")
    b4.download_button("Label 100 x 60 mm", assets["label_pdf"], file_name=f"{stem}_QR_Label.pdf", mime="application/pdf", icon=":material/print:", width="stretch", key=f"rq_label_{rid}")

    # ---- documents exactly as the public page lists them
    docs = service.public_documents(record, token_row)
    section_bar("DOCUMENTS IN THE SCAN PDF", "Page 1 lists these; then the certificate PDF and every RMTC attachment follow (the QR label itself is not included).")
    if docs:
        portal_table(pd.DataFrame([{"#": i, "Document": d["label"], "File": d["file_name"]} for i, d in enumerate(docs, start=1)]), hide_index=True, width="stretch")
    else:
        st.info("No document is stored for this RMTC yet.")
    z1, z2 = st.columns(2, gap="small")
    if public_url:
        z1.link_button("Download all (ZIP) - public link", f"{public_url}&f=zip", icon=":material/folder_zip:", width="stretch")
        z2.link_button("Download all as one PDF - public link", f"{public_url}&f=pdf", icon=":material/picture_as_pdf:", width="stretch")
    if docs:
        y1, y2 = st.columns(2, gap="small")
        if y1.button("Build ZIP of all documents here", icon=":material/folder_zip:", width="stretch", key=f"rq_zip_build_{rid}"):
            with st.spinner("Building ZIP…"):
                st.session_state[f"rq_zip_{rid}"] = service.documents_zip(record, docs)
        if y2.button("Build combined PDF here", icon=":material/picture_as_pdf:", width="stretch", key=f"rq_cpdf_build_{rid}"):
            with st.spinner("Merging documents…"):
                st.session_state[f"rq_cpdf_{rid}"] = service.documents_combined_pdf(record, docs)
        zipped = st.session_state.get(f"rq_zip_{rid}")
        if zipped:
            y1.download_button("Save ZIP", zipped[0], file_name=f"RMTC_{safe_file_token(number)}_documents.zip", mime="application/zip", icon=":material/download:", width="stretch", key=f"rq_zip_dl_{rid}")
            if zipped[1]:
                y1.caption("Not included: " + "; ".join(zipped[1]))
        combined = st.session_state.get(f"rq_cpdf_{rid}")
        if combined:
            y2.download_button("Save combined PDF", combined[0], file_name=f"RMTC_{safe_file_token(number)}_all_documents.pdf", mime="application/pdf", icon=":material/download:", width="stretch", key=f"rq_cpdf_dl_{rid}")
            if combined[1]:
                y2.caption("Not merged: " + "; ".join(combined[1]))

    # ---- refresh / revoke (RMTC edit / approve rights)
    section_bar("MANAGE PUBLIC QR", "Refresh after an edit / added Part; revoke when a label was lost or shared by mistake.")
    m1, m2 = st.columns(2, gap="small")
    if m1.button("Refresh public QR / certificate", icon=":material/sync:", type="primary", width="stretch", disabled=not can_manage, key=f"rq_refresh_{rid}"):
        with st.spinner("Refreshing public QR, certificate and label…"):
            result = service.refresh_public(rid)
        notes = list(result.get("warnings") or [])
        if result.get("ok"):
            notes.insert(0, "Public QR + customer-safe certificate refreshed." if result.get("public") else "QR label refreshed (public QR not available).")
        st.session_state["rmtc_qr_flash"] = notes
        _clear_bundles(rid)
        st.rerun()
    with m2:
        if can_manage:
            confirm = st.checkbox("I understand: the old printed QR label stops working.", key=f"rq_revoke_ok_{rid}")
            if st.button("Revoke QR (new code)", icon=":material/block:", width="stretch", disabled=not confirm, key=f"rq_revoke_{rid}"):
                with st.spinner("Revoking the QR code and creating a new one…"):
                    result = service.revoke_and_renew(rid)
                notes = list(result.get("warnings") or [])
                if result.get("ok"):
                    notes.insert(0, f"QR code revoked ({result.get('revoked', 0)} old code(s)); new public QR created - print and stick the new label.")
                st.session_state["rmtc_qr_flash"] = notes
                _clear_bundles(rid)
                st.rerun()
        else:
            st.caption("Refresh / revoke need RMTC edit or approve rights.")


def _clear_bundles(rid: str) -> None:
    for key in (f"rq_zip_{rid}", f"rq_cpdf_{rid}"):
        st.session_state.pop(key, None)


__all__ = ["render"]
