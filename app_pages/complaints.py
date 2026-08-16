from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.attachments import ALLOWED_ATTACHMENT_TYPES, AttachmentService, AttachmentSlot, render_attachment_manager
from core.delete_service import password_delete_panel
from core.reporting import controlled_record_pdf_bytes
from core.repository import Repository
from core.selection_labels import employee_label, part_label, party_label, process_label
from core.ui import kpi_grid, page_header, save_success_popup, section_bar, workflow_progress


STATUSES = ["OPEN", "CONTAINMENT", "ROOT_CAUSE", "CORRECTIVE_ACTION", "VERIFICATION", "CLOSED", "CANCELLED"]
SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
DEBIT_STATUSES = ["NOT_REQUIRED", "PENDING", "RELEASED", "PARTIALLY_SETTLED", "SETTLED", "WAIVED"]
FOLLOWUP_TYPES = ["FOLLOW_UP", "CUSTOMER_UPDATE", "SUPPLIER_UPDATE", "INTERNAL_REVIEW", "COMMERCIAL", "CLOSURE_REVIEW"]
ANALYSIS_METHODS = ["5_WHY", "FISHBONE", "8D", "PARETO", "OTHER"]
ACTION_TYPES = ["CORRECTION", "CONTAINMENT", "OCCURRENCE_CORRECTIVE", "ESCAPE_CORRECTIVE", "SYSTEMIC_PREVENTIVE", "VERIFICATION"]
ACTION_STATUSES = ["OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"]
COMPLAINT_ATTACHMENT_SLOTS = (
    AttachmentSlot("COMPLAINT_SOURCE", "Complaint / Claim Document", "Customer or supplier complaint, claim or email record"),
    AttachmentSlot("ANALYSIS_EVIDENCE", "Analysis Evidence", "Photos, measurements, 5-Why/Fishbone evidence or supporting data"),
    AttachmentSlot("CLOSURE_REPORT", "8D / Closure Report", "Final 8D, corrective-action report or closure evidence"),
)

COMPLAINT_PHOTO_TYPE = "COMPLAINT_PHOTO"
COMPLAINT_MULTI_ATTACHMENT_TYPE = "COMPLAINT_ATTACHMENT"
COMPLAINT_PHOTO_EXTENSIONS = ["png", "jpg", "jpeg", "webp"]


def _complaint_entry_styles() -> None:
    """High-visibility pastel grading for Customer and Supplier complaint sections."""
    st.markdown(
        r"""
<style>
/* QCMS 4.11.7 — staged collapsible complaint workflow with high-visibility color grading.
   Style the keyed Streamlit container itself AND its first border wrapper so
   the background remains visible across Streamlit DOM revisions. */

/* ---------- CUSTOMER COMPLAINT ---------- */
div[class*="st-key-complaint_customer_details"]{
  background:linear-gradient(135deg,#E7F3FF 0%,#F4FAFF 100%)!important;
  border:1px solid #A9CCE9!important;border-left:5px solid #287DB9!important;
  border-radius:12px!important;padding:.68rem .78rem!important;margin-bottom:.52rem!important;
}
div[class*="st-key-complaint_customer_responsibility"]{
  background:linear-gradient(135deg,#E7F8F3 0%,#F3FBF8 100%)!important;
  border:1px solid #A9DCCB!important;border-left:5px solid #16866F!important;
  border-radius:12px!important;padding:.68rem .78rem!important;margin-bottom:.52rem!important;
}
div[class*="st-key-complaint_customer_evidence"]{
  background:linear-gradient(135deg,#F0EBFF 0%,#F8F6FF 100%)!important;
  border:1px solid #C8BDEB!important;border-left:5px solid #6C50B8!important;
  border-radius:12px!important;padding:.68rem .78rem!important;margin-bottom:.52rem!important;
}
div[class*="st-key-complaint_customer_action"]{
  background:linear-gradient(135deg,#FFF1D6 0%,#FFF9EC 100%)!important;
  border:1px solid #E8CA8E!important;border-left:5px solid #C88912!important;
  border-radius:12px!important;padding:.68rem .78rem!important;margin-bottom:.52rem!important;
}
div[class*="st-key-complaint_customer_commercial"]{
  background:linear-gradient(135deg,#FCE9EE 0%,#FFF5F7 100%)!important;
  border:1px solid #E8B9C5!important;border-left:5px solid #B94D67!important;
  border-radius:12px!important;padding:.68rem .78rem!important;margin-bottom:.52rem!important;
}

div[class*="st-key-complaint_customer_followup"]{
  background:linear-gradient(135deg,#E9F7EC 0%,#F5FBF6 100%)!important;
  border:1px solid #B8DCC0!important;border-left:5px solid #438D5A!important;
  border-radius:12px!important;padding:.68rem .78rem!important;margin-bottom:.52rem!important;
}

/* ---------- SUPPLIER COMPLAINT ---------- */
div[class*="st-key-complaint_supplier_details"]{
  background:linear-gradient(135deg,#EEE9FF 0%,#F8F5FF 100%)!important;
  border:1px solid #C7B9E8!important;border-left:5px solid #7351B2!important;
  border-radius:12px!important;padding:.68rem .78rem!important;margin-bottom:.52rem!important;
}
div[class*="st-key-complaint_supplier_responsibility"]{
  background:linear-gradient(135deg,#E8F7EC 0%,#F3FBF5 100%)!important;
  border:1px solid #AED8B9!important;border-left:5px solid #3B8955!important;
  border-radius:12px!important;padding:.68rem .78rem!important;margin-bottom:.52rem!important;
}
div[class*="st-key-complaint_supplier_evidence"]{
  background:linear-gradient(135deg,#E6F5FA 0%,#F2FBFD 100%)!important;
  border:1px solid #ADD5E0!important;border-left:5px solid #277F9B!important;
  border-radius:12px!important;padding:.68rem .78rem!important;margin-bottom:.52rem!important;
}
div[class*="st-key-complaint_supplier_action"]{
  background:linear-gradient(135deg,#FFEBD9 0%,#FFF7F0 100%)!important;
  border:1px solid #E9C19F!important;border-left:5px solid #C66B29!important;
  border-radius:12px!important;padding:.68rem .78rem!important;margin-bottom:.52rem!important;
}
div[class*="st-key-complaint_supplier_commercial"]{
  background:linear-gradient(135deg,#EAF0F5 0%,#F7F9FB 100%)!important;
  border:1px solid #BBCAD5!important;border-left:5px solid #5A7181!important;
  border-radius:12px!important;padding:.68rem .78rem!important;margin-bottom:.52rem!important;
}

div[class*="st-key-complaint_supplier_followup"]{
  background:linear-gradient(135deg,#F2F6E4 0%,#FAFBF3 100%)!important;
  border:1px solid #CFD9A9!important;border-left:5px solid #748A37!important;
  border-radius:12px!important;padding:.68rem .78rem!important;margin-bottom:.52rem!important;
}

/* Remove the white border-wrapper fill that can hide the keyed container tone. */
div[class*="st-key-complaint_customer_details"] > div[data-testid="stVerticalBlockBorderWrapper"],
div[class*="st-key-complaint_customer_responsibility"] > div[data-testid="stVerticalBlockBorderWrapper"],
div[class*="st-key-complaint_customer_evidence"] > div[data-testid="stVerticalBlockBorderWrapper"],
div[class*="st-key-complaint_customer_action"] > div[data-testid="stVerticalBlockBorderWrapper"],
div[class*="st-key-complaint_customer_commercial"] > div[data-testid="stVerticalBlockBorderWrapper"],
div[class*="st-key-complaint_customer_followup"] > div[data-testid="stVerticalBlockBorderWrapper"],
div[class*="st-key-complaint_supplier_details"] > div[data-testid="stVerticalBlockBorderWrapper"],
div[class*="st-key-complaint_supplier_responsibility"] > div[data-testid="stVerticalBlockBorderWrapper"],
div[class*="st-key-complaint_supplier_evidence"] > div[data-testid="stVerticalBlockBorderWrapper"],
div[class*="st-key-complaint_supplier_action"] > div[data-testid="stVerticalBlockBorderWrapper"],
div[class*="st-key-complaint_supplier_commercial"] > div[data-testid="stVerticalBlockBorderWrapper"],
div[class*="st-key-complaint_supplier_followup"] > div[data-testid="stVerticalBlockBorderWrapper"]{
  background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important;
}

/* Section title strips make the five form zones immediately distinguishable. */
div[class*="st-key-complaint_customer_details"] .fsi-section-bar{background:#D7EAFA!important;color:#0B4F7E!important;border-color:#9EC7E4!important;}
div[class*="st-key-complaint_customer_responsibility"] .fsi-section-bar{background:#D7F0E8!important;color:#126D5B!important;border-color:#9CD2C0!important;}
div[class*="st-key-complaint_customer_evidence"] .fsi-section-bar{background:#E3DBFA!important;color:#533D97!important;border-color:#BAAAE4!important;}
div[class*="st-key-complaint_customer_action"] .fsi-section-bar{background:#F8E5B9!important;color:#8A5A05!important;border-color:#DFC17D!important;}
div[class*="st-key-complaint_customer_commercial"] .fsi-section-bar{background:#F6D9E0!important;color:#963A52!important;border-color:#DDAAB7!important;}
div[class*="st-key-complaint_customer_followup"] .fsi-section-bar{background:#DBEFDF!important;color:#357248!important;border-color:#ADD2B5!important;}

div[class*="st-key-complaint_supplier_details"] .fsi-section-bar{background:#E0D7F6!important;color:#55398C!important;border-color:#BBA9DF!important;}
div[class*="st-key-complaint_supplier_responsibility"] .fsi-section-bar{background:#D9EFDE!important;color:#2E7146!important;border-color:#A2D0AE!important;}
div[class*="st-key-complaint_supplier_evidence"] .fsi-section-bar{background:#D5EDF4!important;color:#206B82!important;border-color:#9DCFD9!important;}
div[class*="st-key-complaint_supplier_action"] .fsi-section-bar{background:#F7DEC7!important;color:#954C17!important;border-color:#DEB38F!important;}
div[class*="st-key-complaint_supplier_commercial"] .fsi-section-bar{background:#DDE6EC!important;color:#425C6D!important;border-color:#AEBFCC!important;}
div[class*="st-key-complaint_supplier_followup"] .fsi-section-bar{background:#E6EDCF!important;color:#5F742D!important;border-color:#C4D195!important;}

/* Keep labels and field text high contrast on all pastel panels. */
div[class*="st-key-complaint_customer_"],div[class*="st-key-complaint_supplier_"]{color:#12293B!important;}
div[class*="st-key-complaint_customer_"] label,div[class*="st-key-complaint_supplier_"] label{color:#17384F!important;font-weight:700!important;}
div[class*="st-key-complaint_customer_"] div[data-testid="stVerticalBlock"],
div[class*="st-key-complaint_supplier_"] div[data-testid="stVerticalBlock"]{gap:.45rem!important;}

/* QCMS 4.11.7 — A→E staged expandable complaint workflow.
   Section header font is intentionally 26px: 100% larger than the historic
   13px section-bar title. */
div[class*="st-key-complaint_customer_"] div[data-testid="stExpander"] details,
div[class*="st-key-complaint_supplier_"] div[data-testid="stExpander"] details{
  background:transparent!important;border:0!important;box-shadow:none!important;border-radius:10px!important;
}
div[class*="st-key-complaint_customer_"] div[data-testid="stExpander"] summary,
div[class*="st-key-complaint_supplier_"] div[data-testid="stExpander"] summary{
  min-height:64px!important;padding:.70rem .90rem!important;border-radius:9px!important;
  display:flex!important;align-items:center!important;
}
div[class*="st-key-complaint_customer_"] div[data-testid="stExpander"] summary p,
div[class*="st-key-complaint_supplier_"] div[data-testid="stExpander"] summary p{
  font-size:26px!important;font-weight:900!important;line-height:1.10!important;letter-spacing:.01em!important;margin:0!important;
}
div[class*="st-key-complaint_customer_"] div[data-testid="stExpander"] summary svg,
div[class*="st-key-complaint_supplier_"] div[data-testid="stExpander"] summary svg{
  width:1.45rem!important;height:1.45rem!important;flex:0 0 1.45rem!important;
}

/* Stage header colors follow each complaint section palette. */
div[class*="st-key-complaint_customer_details"] summary{background:#D7EAFA!important;color:#0B4F7E!important;}
div[class*="st-key-complaint_customer_responsibility"] summary{background:#D7F0E8!important;color:#126D5B!important;}
div[class*="st-key-complaint_customer_evidence"] summary{background:#E3DBFA!important;color:#533D97!important;}
div[class*="st-key-complaint_customer_action"] summary{background:#F8E5B9!important;color:#8A5A05!important;}
div[class*="st-key-complaint_customer_commercial"] summary{background:#F6D9E0!important;color:#963A52!important;}

div[class*="st-key-complaint_supplier_details"] summary{background:#E0D7F6!important;color:#55398C!important;}
div[class*="st-key-complaint_supplier_responsibility"] summary{background:#D9EFDE!important;color:#2E7146!important;}
div[class*="st-key-complaint_supplier_evidence"] summary{background:#D5EDF4!important;color:#206B82!important;}
div[class*="st-key-complaint_supplier_action"] summary{background:#F7DEC7!important;color:#954C17!important;}
div[class*="st-key-complaint_supplier_commercial"] summary{background:#DDE6EC!important;color:#425C6D!important;}

/* Keep stage header text color fixed even when Streamlit injects nested paragraph styles. */
div[class*="st-key-complaint_customer_details"] summary p{color:#0B4F7E!important;}
div[class*="st-key-complaint_customer_responsibility"] summary p{color:#126D5B!important;}
div[class*="st-key-complaint_customer_evidence"] summary p{color:#533D97!important;}
div[class*="st-key-complaint_customer_action"] summary p{color:#8A5A05!important;}
div[class*="st-key-complaint_customer_commercial"] summary p{color:#963A52!important;}
div[class*="st-key-complaint_supplier_details"] summary p{color:#55398C!important;}
div[class*="st-key-complaint_supplier_responsibility"] summary p{color:#2E7146!important;}
div[class*="st-key-complaint_supplier_evidence"] summary p{color:#206B82!important;}
div[class*="st-key-complaint_supplier_action"] summary p{color:#954C17!important;}
div[class*="st-key-complaint_supplier_commercial"] summary p{color:#425C6D!important;}
</style>
""",
        unsafe_allow_html=True,
    )


def _stage_new_complaint_media(complaint_type: str, writable: bool, *, show_heading: bool = True) -> dict[str, Any]:
    """Render evidence uploaders before the first complaint save and return selected files/titles."""
    result: dict[str, Any] = {"photos": [], "attachments": [], "attachment_group": ""}
    if show_heading:
        section_bar("PHOTOGRAPHS & MULTIPLE ATTACHMENTS")
    st.caption("You may add titled photographs and multiple supporting files before saving the complaint. They are uploaded immediately after the complaint record is created.")
    photo_col, attachment_col = st.columns(2, gap="small")
    with photo_col:
        st.markdown("**Titled Photographs**")
        photo_files = st.file_uploader(
            "Select one or multiple photographs",
            type=COMPLAINT_PHOTO_EXTENSIONS,
            accept_multiple_files=True,
            disabled=not writable,
            key=f"{complaint_type}_new_photo_files",
        )
        staged_photos: list[tuple[str, Any]] = []
        for index, photo in enumerate(photo_files or [], start=1):
            default_title = Path(str(photo.name)).stem.replace("_", " ").strip() or f"Photograph {index}"
            title = st.text_input(
                f"Photograph {index} Title",
                value=default_title,
                disabled=not writable,
                key=f"{complaint_type}_new_photo_title_{index}",
            )
            st.image(photo, caption=title.strip() or str(photo.name), width="stretch")
            staged_photos.append((title.strip(), photo))
        result["photos"] = staged_photos
    with attachment_col:
        st.markdown("**Supporting Attachments**")
        result["attachment_group"] = st.text_input(
            "Attachment Title / Group",
            placeholder="Optional; each file name is retained",
            disabled=not writable,
            key=f"{complaint_type}_new_attachment_group",
        ).strip()
        result["attachments"] = st.file_uploader(
            "Select one or multiple supporting files",
            type=ALLOWED_ATTACHMENT_TYPES,
            accept_multiple_files=True,
            disabled=not writable,
            key=f"{complaint_type}_new_attachment_files",
        ) or []
        if result["attachments"]:
            st.caption(f"{len(result['attachments'])} supporting file(s) selected")
    return result


def _upload_staged_complaint_media(repo: Repository, complaint_id: str, staged: Mapping[str, Any]) -> tuple[int, list[str]]:
    service = AttachmentService(repo)
    added = 0
    errors: list[str] = []
    for title, photo in staged.get("photos") or []:
        if not str(title or "").strip():
            errors.append(f"{getattr(photo, 'name', 'Photograph')}: Photograph Title is mandatory")
            continue
        try:
            service.upload_additional(
                entity_type="QUALITY_COMPLAINT", entity_id=complaint_id, folder="complaints",
                document_type=COMPLAINT_PHOTO_TYPE, title=str(title).strip(), file=photo,
            )
            added += 1
        except Exception as exc:
            errors.append(f"{getattr(photo, 'name', 'Photograph')}: {exc}")
    attachment_group = str(staged.get("attachment_group") or "").strip()
    attachments = list(staged.get("attachments") or [])
    for file in attachments:
        file_title = Path(str(file.name)).stem or str(file.name)
        final_title = f"{attachment_group} · {file_title}" if attachment_group and len(attachments) > 1 else (attachment_group or file_title)
        try:
            service.upload_additional(
                entity_type="QUALITY_COMPLAINT", entity_id=complaint_id, folder="complaints",
                document_type=COMPLAINT_MULTI_ATTACHMENT_TYPE, title=final_title, file=file,
            )
            added += 1
        except Exception as exc:
            errors.append(f"{file.name}: {exc}")
    return added, errors


def _as_date(value: Any, fallback: date | None = None) -> date:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if text:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
    return fallback or date.today()


def _party_rows(repo: Repository, complaint_type: str) -> list[dict]:
    party_type = "CUSTOMER" if complaint_type == "CUSTOMER" else "SUPPLIER"
    return repo.select("parties", contains={"party_types": [party_type]}, eq={"status": "ACTIVE"}, order_by="party_name", limit=3000)


def _parts(repo: Repository) -> list[dict]:
    return repo.select("parts", eq={"status": "ACTIVE"}, order_by="part_number", limit=5000)


def _employees(repo: Repository) -> list[dict]:
    return repo.select("employees", eq={"status": "ACTIVE"}, order_by="first_name", limit=3000)


def _complaint_label(row: Mapping[str, Any], parties: Mapping[str, Mapping[str, Any]] | None = None) -> str:
    party = (parties or {}).get(str(row.get("party_id"))) or {}
    return " · ".join(
        value for value in (
            str(row.get("complaint_number") or ""),
            str(row.get("complaint_type") or "").replace("_", " ").title(),
            str(party.get("party_name") or ""),
            str(row.get("subject") or ""),
            str(row.get("status") or "").replace("_", " ").title(),
        ) if value
    )


def _is_closed(row: Mapping[str, Any]) -> bool:
    return str(row.get("status") or "").upper() in {"CLOSED", "CANCELLED"}


def _is_overdue(row: Mapping[str, Any]) -> bool:
    if _is_closed(row) or not row.get("target_closure_date"):
        return False
    return _as_date(row.get("target_closure_date")) < date.today()


def _action_overdue(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("status") or "OPEN") not in {"COMPLETED", "CANCELLED"}
        and bool(row.get("target_date"))
        and _as_date(row.get("target_date")) < date.today()
    )


def _analysis_progress(complaint: Mapping[str, Any], actions: list[Mapping[str, Any]]) -> list[dict[str, str]]:
    containment_done = bool(complaint.get("containment_completed_date") or complaint.get("containment_effectiveness"))
    rca_done = bool(complaint.get("root_cause_confirmed"))
    action_rows = [row for row in actions if str(row.get("status") or "") != "CANCELLED"]
    actions_done = bool(action_rows) and all(str(row.get("status")) == "COMPLETED" for row in action_rows)
    verification_done = bool(complaint.get("effectiveness_verified"))
    closed = str(complaint.get("status") or "") == "CLOSED"
    if closed:
        states = ["complete"] * 6
    elif verification_done:
        states = ["complete", "complete", "complete", "complete" if actions_done else "current", "current", "pending"]
    elif rca_done:
        states = ["complete", "complete" if containment_done else "current", "complete", "current", "pending", "pending"]
    elif containment_done or complaint.get("why_1") or complaint.get("occurrence_root_cause"):
        states = ["complete", "complete" if containment_done else "current", "current", "pending", "pending", "pending"]
    else:
        states = ["complete", "current", "pending", "pending", "pending", "pending"]
    labels = [
        ("Complaint", "Registered"),
        ("Containment", "Immediate control"),
        ("Root Cause", "5-Why / evidence"),
        ("Corrective Action", "Owned action plan"),
        ("Verification", "Effectiveness check"),
        ("Closure", "Final approval"),
    ]
    return [{"label": label, "detail": detail, "state": state} for (label, detail), state in zip(labels, states)]


def _closure_readiness(complaint: Mapping[str, Any], actions: list[Mapping[str, Any]]) -> tuple[bool, list[str]]:
    gaps: list[str] = []
    if not complaint.get("root_cause_confirmed"):
        gaps.append("Root cause confirmation is pending")
    if not complaint.get("effectiveness_verified"):
        gaps.append("Corrective-action effectiveness verification is pending")
    open_actions = [row for row in actions if str(row.get("status") or "") not in {"COMPLETED", "CANCELLED"}]
    if open_actions:
        gaps.append(f"{len(open_actions)} action-plan item(s) are still open")
    if not complaint.get("closure_date"):
        gaps.append("Actual Closure Date is not recorded")
    return not gaps, gaps



def _complaint_media_rows(repo: Repository, complaint_id: str) -> list[dict]:
    rows = repo.select(
        "document_attachments",
        eq={"entity_type": "QUALITY_COMPLAINT", "entity_id": complaint_id, "status": "ACTIVE"},
        order_by="created_at",
        desc=True,
        limit=250,
    )
    return [
        row for row in rows
        if str(row.get("document_type") or "") in {COMPLAINT_PHOTO_TYPE, COMPLAINT_MULTI_ATTACHMENT_TYPE}
    ]


def _media_title(row: Mapping[str, Any]) -> str:
    return str(row.get("document_title") or row.get("file_name") or "Attachment").strip()


def _render_media_delete(
    service: AttachmentService,
    row: Mapping[str, Any],
    complaint_id: str,
    *,
    can_delete: bool,
    key_prefix: str,
) -> None:
    if not can_delete:
        return
    with st.expander("Delete", expanded=False):
        password = st.text_input(
            "Current QCMS password",
            type="password",
            key=f"{key_prefix}_password_{row.get('id')}",
        )
        confirm = st.checkbox(
            "Permanently delete this file",
            key=f"{key_prefix}_confirm_{row.get('id')}",
        )
        if st.button(
            "Delete file",
            type="primary",
            width="stretch",
            key=f"{key_prefix}_button_{row.get('id')}",
            disabled=not password or not confirm,
        ):
            try:
                service.delete(
                    attachment=row,
                    entity_id=complaint_id,
                    slot=AttachmentSlot(str(row.get("document_type") or "COMPLAINT_ATTACHMENT"), _media_title(row)),
                    password=password,
                )
                save_success_popup("Complaint file deleted successfully.", queue_for_rerun=True)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _render_complaint_media(
    repo: Repository,
    complaint: Mapping[str, Any],
    perms: Mapping[str, bool],
    *,
    allow_upload: bool = True,
    title: str = "PHOTOGRAPHS & MULTIPLE ATTACHMENTS",
    show_heading: bool = True,
) -> None:
    complaint_id = str(complaint.get("id") or "")
    if not complaint_id:
        return
    if show_heading:
        section_bar(title)
    st.caption(
        "Photographs are stored with a mandatory title. Supporting documents are repeatable: upload one or many files without replacing earlier complaint evidence."
    )
    service = AttachmentService(repo)

    if allow_upload and perms.get("can_edit"):
        photo_col, attachment_col = st.columns(2, gap="small")
        with photo_col:
            with st.container(border=True, key=f"complaint_photo_upload_{complaint_id}"):
                st.markdown("**Add Photograph**")
                photo_files = st.file_uploader(
                    "Select one or multiple photographs",
                    type=COMPLAINT_PHOTO_EXTENSIONS,
                    accept_multiple_files=True,
                    key=f"complaint_photo_files_{complaint_id}",
                )
                titled_photos: list[tuple[str, Any]] = []
                for index, photo_file in enumerate(photo_files or [], start=1):
                    default_title = Path(str(photo_file.name)).stem.replace("_", " ").strip() or f"Photograph {index}"
                    photo_title = st.text_input(
                        f"Photograph {index} Title",
                        value=default_title,
                        key=f"complaint_photo_title_{complaint_id}_{index}",
                    )
                    st.image(photo_file, caption=photo_title.strip() or str(photo_file.name), width="stretch")
                    titled_photos.append((photo_title.strip(), photo_file))
                if st.button(
                    "Add Selected Photographs",
                    type="primary",
                    width="stretch",
                    key=f"complaint_photo_add_{complaint_id}",
                    disabled=not titled_photos,
                ):
                    errors: list[str] = []
                    added = 0
                    for photo_title, photo_file in titled_photos:
                        if not photo_title:
                            errors.append(f"{photo_file.name}: Photograph Title is mandatory")
                            continue
                        try:
                            service.upload_additional(
                                entity_type="QUALITY_COMPLAINT",
                                entity_id=complaint_id,
                                folder="complaints",
                                document_type=COMPLAINT_PHOTO_TYPE,
                                title=photo_title,
                                file=photo_file,
                            )
                            added += 1
                        except Exception as exc:
                            errors.append(f"{photo_file.name}: {exc}")
                    if errors:
                        st.error("Some photographs could not be added: " + " | ".join(errors))
                    if added:
                        save_success_popup(f"{added} complaint photograph(s) added successfully.", queue_for_rerun=True)
                        st.rerun()

        with attachment_col:
            with st.container(border=True, key=f"complaint_multi_attachment_upload_{complaint_id}"):
                st.markdown("**Add Supporting Attachments**")
                attachment_title = st.text_input(
                    "Attachment Title / Group",
                    key=f"complaint_attachment_title_{complaint_id}",
                    placeholder="Optional; file name is used when blank",
                )
                attachment_files = st.file_uploader(
                    "Select one or multiple files",
                    type=ALLOWED_ATTACHMENT_TYPES,
                    accept_multiple_files=True,
                    key=f"complaint_attachment_files_{complaint_id}",
                )
                if attachment_files:
                    st.caption(f"{len(attachment_files)} file(s) selected")
                if st.button(
                    "Add Selected Attachments",
                    type="primary",
                    width="stretch",
                    key=f"complaint_attachment_add_{complaint_id}",
                    disabled=not attachment_files,
                ):
                    errors: list[str] = []
                    added = 0
                    for file in attachment_files or []:
                        base_title = attachment_title.strip()
                        file_title = Path(str(file.name)).stem or str(file.name)
                        if base_title and len(attachment_files) == 1:
                            final_title = base_title
                        elif base_title:
                            final_title = f"{base_title} · {file_title}"
                        else:
                            final_title = file_title
                        try:
                            service.upload_additional(
                                entity_type="QUALITY_COMPLAINT",
                                entity_id=complaint_id,
                                folder="complaints",
                                document_type=COMPLAINT_MULTI_ATTACHMENT_TYPE,
                                title=final_title,
                                file=file,
                            )
                            added += 1
                        except Exception as exc:
                            errors.append(f"{file.name}: {exc}")
                    if errors:
                        st.error("Some attachments could not be added: " + " | ".join(errors))
                    if added:
                        save_success_popup(f"{added} complaint attachment(s) added successfully.", queue_for_rerun=True)
                        st.rerun()

    rows = _complaint_media_rows(repo, complaint_id)
    photos = [row for row in rows if str(row.get("document_type")) == COMPLAINT_PHOTO_TYPE]
    attachments = [row for row in rows if str(row.get("document_type")) == COMPLAINT_MULTI_ATTACHMENT_TYPE]

    st.markdown(f"**Photograph Register ({len(photos)})**")
    if not photos:
        st.caption("No complaint photographs uploaded yet.")
    else:
        photo_cols = st.columns(3, gap="small")
        for index, row in enumerate(photos):
            with photo_cols[index % 3]:
                with st.container(border=True, key=f"complaint_photo_card_{row.get('id')}"):
                    st.markdown(f"**{_media_title(row)}**")
                    try:
                        photo_bytes = service.download(row)
                        st.image(photo_bytes, caption=str(row.get("file_name") or "Photograph"), width="stretch")
                        st.download_button(
                            "Download Photograph",
                            data=photo_bytes,
                            file_name=str(row.get("file_name") or "complaint_photo"),
                            mime=str(row.get("mime_type") or "application/octet-stream"),
                            width="stretch",
                            key=f"complaint_photo_download_{row.get('id')}",
                        )
                    except Exception as exc:
                        st.error(f"Photograph unavailable: {exc}")
                    st.caption(f"Uploaded: {str(row.get('created_at') or '')[:16] or '-'}")
                    _render_media_delete(service, row, complaint_id, can_delete=bool(perms.get("can_archive")), key_prefix="delete_complaint_photo")

    st.markdown(f"**Attachment Register ({len(attachments)})**")
    if not attachments:
        st.caption("No additional complaint attachments uploaded yet.")
    else:
        for row in attachments:
            with st.container(border=True, key=f"complaint_attachment_row_{row.get('id')}"):
                c1, c2, c3 = st.columns([2.0, 1.4, 1.0], gap="small", vertical_alignment="center")
                c1.markdown(f"**{_media_title(row)}**")
                c1.caption(str(row.get("file_name") or "Attachment"))
                c2.caption(f"Uploaded {str(row.get('created_at') or '')[:16] or '-'}")
                try:
                    file_bytes = service.download(row)
                    c3.download_button(
                        "Download",
                        data=file_bytes,
                        file_name=str(row.get("file_name") or "complaint_attachment"),
                        mime=str(row.get("mime_type") or "application/octet-stream"),
                        width="stretch",
                        key=f"complaint_attachment_download_{row.get('id')}",
                    )
                except Exception as exc:
                    c3.error(str(exc))
                _render_media_delete(service, row, complaint_id, can_delete=bool(perms.get("can_archive")), key_prefix="delete_complaint_attachment")



def _complaint_pdf(repo: Repository, complaint: Mapping[str, Any]) -> bytes:
    parties = {str(row["id"]): row for row in repo.select("parties", limit=5000)}
    parts = {str(row["id"]): row for row in repo.select("parts", limit=5000)}
    employees = {str(row["id"]): row for row in repo.select("employees", limit=5000)}
    processes = {str(row["id"]): row for row in repo.select("processes", limit=5000)}
    followups = repo.select("quality_complaint_followups", eq={"complaint_id": complaint.get("id")}, order_by="followup_date", limit=5000)
    actions = repo.select("quality_complaint_actions", eq={"complaint_id": complaint.get("id")}, order_by="action_no", limit=5000)
    complaint_media = _complaint_media_rows(repo, str(complaint.get("id") or ""))
    party = parties.get(str(complaint.get("party_id"))) or {}
    part = parts.get(str(complaint.get("part_id"))) or {}
    process = processes.get(str(complaint.get("process_id"))) or {}
    coordinator = employees.get(str(complaint.get("fourstar_responsible_employee_id"))) or {}
    containment_owner = employees.get(str(complaint.get("containment_responsible_employee_id"))) or {}
    rca_owner = employees.get(str(complaint.get("root_cause_responsible_employee_id"))) or {}
    verifier = employees.get(str(complaint.get("effectiveness_verified_by_employee_id"))) or {}
    closure_approver = employees.get(str(complaint.get("closure_approved_by_employee_id"))) or {}

    header = {
        "Complaint No.": complaint.get("complaint_number"),
        "Complaint Type": str(complaint.get("complaint_type") or "").title(),
        "Complaint Date": complaint.get("complaint_date"),
        "Status": str(complaint.get("status") or "").replace("_", " ").title(),
        "Party": party_label(party),
        "Part": part_label(part) if part else "Not linked",
        "Process": process_label(process) if process else "Not linked",
        "External Reference": complaint.get("external_reference") or "-",
        "Severity": complaint.get("severity"),
        "Target Closure": complaint.get("target_closure_date") or "-",
        "Actual Closure": complaint.get("closure_date") or "-",
    }
    sections = {
        "PROBLEM DEFINITION / COMPLAINT ANALYSIS": {
            "Subject": complaint.get("subject"),
            "Complaint Description": complaint.get("description"),
            "Defect / Failure Mode": complaint.get("defect_mode") or "-",
            "What happened?": complaint.get("problem_what") or "-",
            "Where detected / occurred?": complaint.get("problem_where") or "-",
            "When / under what condition?": complaint.get("problem_when") or "-",
            "Detection Point": complaint.get("detection_point") or "-",
            "Occurrence Pattern / Frequency": complaint.get("occurrence_pattern") or "-",
            "Lot / Batch": complaint.get("lot_batch_number") or "-",
            "Heat Number": complaint.get("heat_number") or "-",
            "Affected Quantity": complaint.get("affected_quantity"),
            "Impact / Risk Summary": complaint.get("impact_summary") or "-",
        },
        "RESPONSIBILITY MATRIX": {
            "Complaint Coordinator": employee_label(coordinator) if coordinator else "-",
            "Containment Owner": employee_label(containment_owner) if containment_owner else "-",
            "Root Cause Analysis Owner": employee_label(rca_owner) if rca_owner else "-",
            "Effectiveness Verified By": employee_label(verifier) if verifier else "-",
            "Closure Approved By": employee_label(closure_approver) if closure_approver else "-",
            "Customer / Supplier Responsible": complaint.get("external_responsible_name") or "-",
            "External Email": complaint.get("external_responsible_email") or "-",
            "External Phone": complaint.get("external_responsible_phone") or "-",
        },
        "IMMEDIATE CORRECTION & CONTAINMENT": {
            "Immediate Correction": complaint.get("immediate_correction") or "-",
            "Containment Action": complaint.get("containment_action") or "-",
            "Containment Due Date": complaint.get("containment_due_date") or "-",
            "Containment Completed Date": complaint.get("containment_completed_date") or "-",
            "Containment Effectiveness": complaint.get("containment_effectiveness") or "-",
        },
        "ROOT CAUSE ANALYSIS": {
            "Analysis Method": str(complaint.get("analysis_method") or "-").replace("_", " ").title(),
            "Why 1": complaint.get("why_1") or "-",
            "Why 2": complaint.get("why_2") or "-",
            "Why 3": complaint.get("why_3") or "-",
            "Why 4": complaint.get("why_4") or "-",
            "Why 5": complaint.get("why_5") or "-",
            "Occurrence Root Cause": complaint.get("occurrence_root_cause") or complaint.get("root_cause") or "-",
            "Escape / Detection Root Cause": complaint.get("escape_root_cause") or "-",
            "Systemic Root Cause": complaint.get("systemic_root_cause") or "-",
            "Evidence / Validation": complaint.get("root_cause_evidence") or "-",
            "Root Cause Confirmed": "Yes" if complaint.get("root_cause_confirmed") else "No",
            "Confirmed Date": complaint.get("root_cause_confirmed_date") or "-",
        },
        "CORRECTIVE / PREVENTIVE ACTION PLAN": [
            {
                "Action No.": row.get("action_no"),
                "Action Type": str(row.get("action_type") or "").replace("_", " ").title(),
                "Action": row.get("action_description"),
                "Four Star Owner": employee_label(employees.get(str(row.get("owner_employee_id"))) or {}) or "-",
                "External Owner": row.get("external_owner_name") or "-",
                "Target Date": row.get("target_date") or "-",
                "Completion Date": row.get("completion_date") or "-",
                "Status": "Overdue" if _action_overdue(row) else str(row.get("status") or "").replace("_", " ").title(),
                "Evidence": row.get("evidence") or "-",
                "Effectiveness": row.get("effectiveness_result") or "-",
            }
            for row in actions
        ],
        "EFFECTIVENESS VERIFICATION & CLOSURE": {
            "Verification Plan": complaint.get("verification_plan") or "-",
            "Effectiveness Criteria": complaint.get("effectiveness_criteria") or "-",
            "Verification Result": complaint.get("verification_result") or "-",
            "Effectiveness Verified": "Yes" if complaint.get("effectiveness_verified") else "No",
            "Verified Date": complaint.get("effectiveness_verified_date") or "-",
            "Recurrence Check": complaint.get("recurrence_check_result") or "-",
            "Closure Remarks": complaint.get("closure_remarks") or "-",
            "Closure Approval Date": complaint.get("closure_approved_date") or "-",
        },
        "DEBIT NOTE / COMMERCIAL STATUS": {
            "Debit Note Required": "Yes" if complaint.get("debit_note_required") else "No",
            "Debit Note Status": str(complaint.get("debit_note_status") or "").replace("_", " ").title(),
            "Debit Note Number": complaint.get("debit_note_number") or "-",
            "Debit Note Date": complaint.get("debit_note_date") or "-",
            "Debit Note Amount": f"{complaint.get('currency') or 'INR'} {float(complaint.get('debit_note_amount') or 0):,.2f}",
            "Settled Amount": f"{complaint.get('currency') or 'INR'} {float(complaint.get('debit_note_settled_amount') or 0):,.2f}",
            "Settled Date": complaint.get("debit_note_settled_date") or "-",
            "Commercial Remarks": complaint.get("commercial_remarks") or "-",
        },
        "PHOTOGRAPHS & ATTACHMENTS REGISTER": [
            {
                "Type": "Photograph" if str(row.get("document_type")) == COMPLAINT_PHOTO_TYPE else "Attachment",
                "Title": _media_title(row),
                "File Name": row.get("file_name") or "-",
                "Uploaded At": str(row.get("created_at") or "")[:16] or "-",
            }
            for row in complaint_media
        ],
        "FOLLOW-UP HISTORY": [
            {
                "Date": row.get("followup_date"),
                "Type": str(row.get("followup_type") or "").replace("_", " ").title(),
                "Follow-up / Remarks": row.get("remarks"),
                "Next Follow-up": row.get("next_followup_date") or "-",
                "Status": str(row.get("status_after_followup") or "").replace("_", " ").title() or "-",
                "Responsible": employee_label(employees.get(str(row.get("responsible_employee_id"))) or {}) or "-",
            }
            for row in followups
        ],
    }
    return controlled_record_pdf_bytes(
        "DETAILED COMPLAINT ANALYSIS RECORD",
        header,
        sections,
        record_number=str(complaint.get("complaint_number") or ""),
        subtitle="Problem Definition · Root Cause · Corrective Action · Responsibility · Verification · Commercial Closure",
    )


def render_home() -> None:
    page_header("Complaint Management", "Customer and supplier complaints, follow-ups, closure and debit-note settlement.", "Complaints")
    repo = Repository()
    rows = repo.select("quality_complaints", order_by="complaint_date", desc=True, limit=5000)
    open_rows = [row for row in rows if not _is_closed(row)]
    followups = repo.select("quality_complaint_followups", order_by="followup_date", desc=True, limit=10000)
    latest_followup: dict[str, dict] = {}
    for followup in followups:
        complaint_id = str(followup.get("complaint_id") or "")
        if complaint_id and complaint_id not in latest_followup:
            latest_followup[complaint_id] = followup
    customer_open = sum(str(row.get("complaint_type")) == "CUSTOMER" for row in open_rows)
    supplier_open = sum(str(row.get("complaint_type")) == "SUPPLIER" for row in open_rows)
    overdue = sum(_is_overdue(row) for row in open_rows)
    followups_due = sum(
        bool((latest_followup.get(str(row.get("id"))) or {}).get("next_followup_date"))
        and _as_date((latest_followup.get(str(row.get("id"))) or {}).get("next_followup_date")) < date.today()
        for row in open_rows
    )
    debit_pending = sum(bool(row.get("debit_note_required")) and str(row.get("debit_note_status")) not in {"SETTLED", "WAIVED"} for row in rows)
    closed = sum(str(row.get("status")) == "CLOSED" for row in rows)
    root_cause_pending = sum(not bool(row.get("root_cause_confirmed")) for row in open_rows)
    action_rows = repo.select("quality_complaint_actions", limit=10000)
    action_overdue = sum(_action_overdue(row) for row in action_rows)
    kpi_grid([
        {"label": "Open Customer Complaints", "value": customer_open, "foot": "Customer issues requiring action", "color": "#2563EB", "background": "#EFF6FF"},
        {"label": "Open Supplier Complaints", "value": supplier_open, "foot": "Supplier issues requiring action", "color": "#7C3AED", "background": "#F5F3FF"},
        {"label": "Overdue Complaints", "value": overdue, "foot": "Target closure date exceeded", "color": "#B91C1C", "background": "#FEF2F2"},
        {"label": "Follow-ups Due", "value": followups_due, "foot": "Next follow-up date exceeded", "color": "#C2410C", "background": "#FFF7ED"},
        {"label": "Root Cause Pending", "value": root_cause_pending, "foot": "Open complaints without confirmed RCA", "color": "#7C3AED", "background": "#F5F3FF"},
        {"label": "Overdue Actions", "value": action_overdue, "foot": "Corrective / preventive actions past due", "color": "#B91C1C", "background": "#FEF2F2"},
        {"label": "Debit Notes Pending", "value": debit_pending, "foot": "Required but not fully settled", "color": "#D97706", "background": "#FFFBEB"},
        {"label": "Closed Complaints", "value": closed, "foot": "Complaint closure completed", "color": "#15803D", "background": "#F0FDF4"},
    ])

    section_bar("OPEN COMPLAINT FOLLOW-UP")
    if not open_rows:
        st.info("No open Customer or Supplier complaints are recorded.")
        return
    parties = {str(row["id"]): row for row in repo.select("parties", limit=5000)}
    employees = {str(row["id"]): row for row in repo.select("employees", limit=5000)}
    open_action_count: dict[str, int] = {}
    for action in action_rows:
        if str(action.get("status") or "") not in {"COMPLETED", "CANCELLED"}:
            cid = str(action.get("complaint_id") or "")
            open_action_count[cid] = open_action_count.get(cid, 0) + 1
    frame = pd.DataFrame([
        {
            "Complaint No.": row.get("complaint_number"),
            "Type": str(row.get("complaint_type") or "").title(),
            "Party": (parties.get(str(row.get("party_id"))) or {}).get("party_name"),
            "Subject": row.get("subject"),
            "Severity": row.get("severity"),
            "Responsible": employee_label(employees.get(str(row.get("fourstar_responsible_employee_id"))) or {}),
            "Target Closure": row.get("target_closure_date"),
            "Next Follow-up": (latest_followup.get(str(row.get("id"))) or {}).get("next_followup_date") or "-",
            "Root Cause": "CONFIRMED" if row.get("root_cause_confirmed") else "PENDING",
            "Open Actions": open_action_count.get(str(row.get("id")), 0),
            "Status": "OVERDUE" if _is_overdue(row) else str(row.get("status") or "").replace("_", " ").title(),
            "Debit Note": str(row.get("debit_note_status") or "").replace("_", " ").title(),
        }
        for row in open_rows
    ])
    st.dataframe(frame, hide_index=True, width="stretch", height=min(560, 65 + 36 * len(frame)))


def render_customer_entry() -> None:
    _render_entry("CUSTOMER")


def render_supplier_entry() -> None:
    _render_entry("SUPPLIER")


def _render_entry(complaint_type: str) -> None:
    party_word = "Customer" if complaint_type == "CUSTOMER" else "Supplier"
    _complaint_entry_styles()
    page_header(f"{party_word} Complaint", f"Controlled {party_word.lower()} complaint entry, evidence, action and follow-up.", "Complaints")
    repo = Repository(); perms = current_permissions("COMPLAINT_MANAGEMENT")
    parties = _party_rows(repo, complaint_type); parts = _parts(repo); employees = _employees(repo)
    party_labels = {str(row["id"]): party_label(row, include_type=True) for row in parties}
    part_labels = {"": "— Not linked to a Part —", **{str(row["id"]): part_label(row) for row in parts}}
    employee_labels = {str(row["id"]): employee_label(row) for row in employees}

    pending_error_key = f"{complaint_type}_media_upload_error"
    pending_info_key = f"{complaint_type}_media_upload_info"
    if st.session_state.pop(pending_error_key, None):
        st.error(st.session_state.pop(f"{pending_error_key}_message", "Some complaint evidence could not be uploaded."))
    info_message = st.session_state.pop(pending_info_key, None)
    if info_message:
        st.success(info_message)

    records = repo.select("quality_complaints", eq={"complaint_type": complaint_type}, order_by="created_at", desc=True, limit=5000)
    record_labels = {"": "＋ New Complaint", **{str(row["id"]): _complaint_label(row, {str(p["id"]): p for p in parties}) for row in records}}
    preferred = str(st.session_state.get(f"selected_{complaint_type.lower()}_complaint") or "")
    if preferred not in record_labels: preferred = ""
    selected_id = st.selectbox("Open Complaint Record", list(record_labels), index=list(record_labels).index(preferred), format_func=lambda value: record_labels[value], key=f"{complaint_type}_complaint_selector")
    existing = next((row for row in records if str(row.get("id")) == selected_id), None)
    writable = perms["can_edit"] if existing else perms["can_create"]

    st.caption("Stage sequence: A Complaint Details → B Responsibility → C Photographs & Attachments → D Containment / Root Cause / Corrective Action → E Debit Note / Commercial Settlement")

    with st.container(border=False, key=f"complaint_{complaint_type.lower()}_details"):
        with st.expander("A - COMPLAINT DETAILS", expanded=True):
            c1, c2, c3, c4 = st.columns(4, gap="small")
            c1.text_input("Complaint Number", value=str((existing or {}).get("complaint_number") or "Auto on Save"), disabled=True, key=f"{complaint_type}_number")
            complaint_date = c2.date_input("Complaint Date", value=_as_date((existing or {}).get("complaint_date")), disabled=not writable, key=f"{complaint_type}_date")
            severity = c3.selectbox("Severity", SEVERITIES, index=SEVERITIES.index(str((existing or {}).get("severity") or "MEDIUM")) if str((existing or {}).get("severity") or "MEDIUM") in SEVERITIES else 1, disabled=not writable, key=f"{complaint_type}_severity")
            current_status = str((existing or {}).get("status") or "OPEN")
            entry_statuses = ["OPEN", "CONTAINMENT", "ROOT_CAUSE", "CORRECTIVE_ACTION", "VERIFICATION", "CANCELLED"]
            if current_status == "CLOSED": entry_statuses.append("CLOSED")
            status = c4.selectbox("Complaint Status", entry_statuses, index=entry_statuses.index(current_status) if current_status in entry_statuses else 0, disabled=not writable or current_status == "CLOSED", key=f"{complaint_type}_status", help="Final CLOSED status is controlled from Detailed Complaint Analysis after RCA, actions and effectiveness verification are complete.")

            p1, p2, p3 = st.columns([1.2, 1.2, 1], gap="small")
            default_party = str((existing or {}).get("party_id") or "")
            party_id = p1.selectbox(party_word, list(party_labels), index=list(party_labels).index(default_party) if default_party in party_labels else 0, format_func=lambda value: party_labels[value], disabled=not writable or not party_labels, key=f"{complaint_type}_party") if party_labels else ""
            default_part = str((existing or {}).get("part_id") or "")
            part_id = p2.selectbox("Part Number", list(part_labels), index=list(part_labels).index(default_part) if default_part in part_labels else 0, format_func=lambda value: part_labels[value], disabled=not writable, key=f"{complaint_type}_part")
            external_reference = p3.text_input(f"{party_word} Complaint / Reference No.", value=str((existing or {}).get("external_reference") or ""), disabled=not writable, key=f"{complaint_type}_external_ref")
            subject = st.text_input("Complaint Subject", value=str((existing or {}).get("subject") or ""), disabled=not writable, key=f"{complaint_type}_subject")
            description = st.text_area("Complaint Description", value=str((existing or {}).get("description") or ""), height=100, disabled=not writable, key=f"{complaint_type}_description")
            q1, q2 = st.columns(2, gap="small")
            affected_qty = q1.number_input("Affected Quantity", min_value=0.0, value=float((existing or {}).get("affected_quantity") or 0.0), step=1.0, disabled=not writable, key=f"{complaint_type}_qty")
            target_closure = q2.date_input("Target Closure Date", value=_as_date((existing or {}).get("target_closure_date"), date.today()), disabled=not writable, key=f"{complaint_type}_target")

    with st.container(border=False, key=f"complaint_{complaint_type.lower()}_responsibility"):
        with st.expander("B - RESPONSIBILITY", expanded=False):
            r1, r2 = st.columns(2, gap="small")
            default_emp = str((existing or {}).get("fourstar_responsible_employee_id") or "")
            fourstar_employee_id = r1.selectbox("Four Star Responsible Person", list(employee_labels), index=list(employee_labels).index(default_emp) if default_emp in employee_labels else 0, format_func=lambda value: employee_labels[value], disabled=not writable or not employee_labels, key=f"{complaint_type}_fsi_resp") if employee_labels else ""
            external_name = r2.text_input(f"{party_word} Responsible Person", value=str((existing or {}).get("external_responsible_name") or ""), disabled=not writable, key=f"{complaint_type}_external_name")
            r3, r4 = st.columns(2, gap="small")
            external_email = r3.text_input(f"{party_word} Responsible Email", value=str((existing or {}).get("external_responsible_email") or ""), disabled=not writable, key=f"{complaint_type}_external_email")
            external_phone = r4.text_input(f"{party_word} Responsible Phone", value=str((existing or {}).get("external_responsible_phone") or ""), disabled=not writable, key=f"{complaint_type}_external_phone")

    with st.container(border=False, key=f"complaint_{complaint_type.lower()}_evidence"):
        with st.expander("C - PHOTOGRAPHS & MULTIPLE ATTACHMENTS", expanded=False):
            if existing:
                staged_media: dict[str, Any] = {}
                _render_complaint_media(repo, existing, perms, allow_upload=True, title="PHOTOGRAPHS & MULTIPLE ATTACHMENTS", show_heading=False)
            else:
                staged_media = _stage_new_complaint_media(complaint_type, writable, show_heading=False)

    with st.container(border=False, key=f"complaint_{complaint_type.lower()}_action"):
        with st.expander("D - CONTAINMENT / ROOT CAUSE / CORRECTIVE ACTION", expanded=False):
            containment = st.text_area("Containment Action", value=str((existing or {}).get("containment_action") or ""), height=75, disabled=not writable, key=f"{complaint_type}_containment")
            root_cause = st.text_area("Root Cause", value=str((existing or {}).get("root_cause") or ""), height=75, disabled=not writable, key=f"{complaint_type}_root")
            corrective = st.text_area("Corrective Action", value=str((existing or {}).get("corrective_action") or ""), height=75, disabled=not writable, key=f"{complaint_type}_corrective")
            verification = st.text_area("Effectiveness / Verification Result", value=str((existing or {}).get("verification_result") or ""), height=75, disabled=not writable, key=f"{complaint_type}_verification")
            close1, close2 = st.columns(2, gap="small")
            closure_date = close1.date_input("Actual Closure Date", value=_as_date((existing or {}).get("closure_date"), date.today()), disabled=not writable or status != "CLOSED", key=f"{complaint_type}_closure_date")
            closure_remarks = close2.text_area("Closure Remarks", value=str((existing or {}).get("closure_remarks") or ""), height=75, disabled=not writable, key=f"{complaint_type}_closure_remarks")

    with st.container(border=False, key=f"complaint_{complaint_type.lower()}_commercial"):
        with st.expander("E - DEBIT NOTE / COMMERCIAL SETTLEMENT", expanded=False):
            debit_required = st.checkbox("Debit Note Required", value=bool((existing or {}).get("debit_note_required")), disabled=not writable, key=f"{complaint_type}_debit_required")
            d1, d2, d3, d4 = st.columns(4, gap="small")
            default_debit_status = str((existing or {}).get("debit_note_status") or ("PENDING" if debit_required else "NOT_REQUIRED"))
            if default_debit_status not in DEBIT_STATUSES: default_debit_status = "PENDING" if debit_required else "NOT_REQUIRED"
            debit_status = d1.selectbox("Debit Note Status", DEBIT_STATUSES, index=DEBIT_STATUSES.index(default_debit_status), disabled=not writable or not debit_required, key=f"{complaint_type}_debit_status")
            debit_number = d2.text_input("Debit Note Number", value=str((existing or {}).get("debit_note_number") or ""), disabled=not writable or not debit_required, key=f"{complaint_type}_debit_no")
            debit_date = d3.date_input("Debit Note Date", value=_as_date((existing or {}).get("debit_note_date"), date.today()), disabled=not writable or not debit_required, key=f"{complaint_type}_debit_date")
            currencies = ["INR", "EUR", "USD", "GBP", "JPY"]
            current_currency = str((existing or {}).get("currency") or "INR")
            currency = d4.selectbox("Currency", currencies, index=currencies.index(current_currency) if current_currency in currencies else 0, disabled=not writable or not debit_required, key=f"{complaint_type}_currency")
            a1, a2, a3 = st.columns(3, gap="small")
            debit_amount = a1.number_input("Debit Note Amount", min_value=0.0, value=float((existing or {}).get("debit_note_amount") or 0.0), step=0.01, disabled=not writable or not debit_required, key=f"{complaint_type}_debit_amount")
            settled_amount = a2.number_input("Settled Amount", min_value=0.0, value=float((existing or {}).get("debit_note_settled_amount") or 0.0), step=0.01, disabled=not writable or not debit_required, key=f"{complaint_type}_settled_amount")
            settled_date = a3.date_input("Settled Date", value=_as_date((existing or {}).get("debit_note_settled_date"), date.today()), disabled=not writable or debit_status != "SETTLED", key=f"{complaint_type}_settled_date")
            commercial_remarks = st.text_area("Commercial / Debit Note Remarks", value=str((existing or {}).get("commercial_remarks") or ""), height=70, disabled=not writable, key=f"{complaint_type}_commercial")
            debit_balance = max(float(debit_amount or 0.0) - float(settled_amount or 0.0), 0.0) if debit_required else 0.0
            if debit_required:
                st.caption(f"Debit Note Settlement Balance: {currency} {debit_balance:,.2f}")

    if st.button("Update Complaint" if existing else "Save Complaint", type="primary", width="stretch", disabled=not writable, key=f"save_{complaint_type}_complaint"):
        staged_photo_gaps = [str(getattr(photo, "name", "Photograph")) for title, photo in (staged_media.get("photos") or []) if not str(title or "").strip()] if not existing else []
        if not party_id or not subject.strip() or not description.strip() or not fourstar_employee_id:
            st.error(f"{party_word}, Complaint Subject, Complaint Description and Four Star Responsible Person are mandatory.")
        elif staged_photo_gaps:
            st.error("Every selected photograph requires a title before the complaint can be saved: " + ", ".join(staged_photo_gaps))
        elif debit_required and float(settled_amount or 0.0) > float(debit_amount or 0.0) + 0.001:
            st.error("Settled Amount cannot be greater than the Debit Note Amount.")
        elif debit_required and debit_status == "SETTLED" and float(debit_amount or 0.0) > 0 and float(settled_amount or 0.0) + 0.001 < float(debit_amount or 0.0):
            st.error("Debit Note Status cannot be SETTLED until the full Debit Note Amount is settled.")
        elif debit_required and debit_status in {"RELEASED", "PARTIALLY_SETTLED", "SETTLED"} and not debit_number.strip():
            st.error("Debit Note Number is required when the Debit Note has been released or settled.")
        else:
            number = str((existing or {}).get("complaint_number") or "")
            if not number:
                number = str(repo.rpc("qcms_next_complaint_number", {"p_complaint_type": complaint_type}) or "")
            payload = {
                "complaint_number": number, "complaint_type": complaint_type, "complaint_date": complaint_date,
                "party_id": party_id, "part_id": part_id or None, "external_reference": external_reference.strip() or None,
                "subject": subject.strip(), "description": description.strip(), "affected_quantity": float(affected_qty), "severity": severity,
                "fourstar_responsible_employee_id": fourstar_employee_id, "external_responsible_name": external_name.strip() or None,
                "external_responsible_email": external_email.strip() or None, "external_responsible_phone": external_phone.strip() or None,
                "target_closure_date": target_closure, "status": status, "containment_action": containment.strip() or None,
                "root_cause": root_cause.strip() or None, "corrective_action": corrective.strip() or None,
                "verification_result": verification.strip() or None, "closure_date": closure_date if status == "CLOSED" else None,
                "closure_remarks": closure_remarks.strip() or None, "debit_note_required": bool(debit_required),
                "debit_note_status": debit_status if debit_required else "NOT_REQUIRED", "debit_note_number": debit_number.strip() or None if debit_required else None,
                "debit_note_date": debit_date if debit_required else None, "debit_note_amount": float(debit_amount) if debit_required else 0.0,
                "currency": currency, "debit_note_settled_amount": float(settled_amount) if debit_required else 0.0,
                "debit_note_settled_date": settled_date if debit_required and debit_status == "SETTLED" else None,
                "commercial_remarks": commercial_remarks.strip() or None,
            }
            saved = repo.update("quality_complaints", str(existing["id"]), payload) if existing else repo.insert("quality_complaints", payload)
            saved_id = str(saved["id"])
            st.session_state[f"selected_{complaint_type.lower()}_complaint"] = saved_id
            if not existing and staged_media:
                added, media_errors = _upload_staged_complaint_media(repo, saved_id, staged_media)
                if media_errors:
                    st.session_state[pending_error_key] = True
                    st.session_state[f"{pending_error_key}_message"] = "Complaint saved, but some evidence could not be uploaded: " + " | ".join(media_errors)
                if added:
                    st.session_state[pending_info_key] = f"{added} photograph/attachment file(s) uploaded with the complaint."
            save_success_popup(f"{party_word} complaint {number} saved successfully.", queue_for_rerun=True)
            st.rerun()

    if existing:
        st.session_state["complaint_analysis_id"] = str(existing.get("id"))
        analysis_page = (st.session_state.get("_qsms_pages") or {}).get("complaint-analysis")
        if analysis_page is not None and st.button("Open Detailed Complaint Analysis & CAPA", type="primary", width="stretch", key=f"open_analysis_{complaint_type}_{selected_id}"):
            st.switch_page(analysis_page)
        with st.container(border=True, key=f"complaint_{complaint_type.lower()}_followup"):
            _render_followups(repo, existing, employees, employee_labels, perms)
        section_bar("PRINT / DELETE")
        pdf = _complaint_pdf(repo, existing)
        p1, p2 = st.columns(2, gap="small")
        p1.download_button("Download Complaint PDF", data=pdf, file_name=f"{existing.get('complaint_number')}.pdf", mime="application/pdf", width="stretch", key=f"pdf_{complaint_type}_{selected_id}")
        with p2:
            if password_delete_panel(repo=repo, table="quality_complaints", rows=[existing], labeler=lambda row: _complaint_label(row), key=f"delete_{complaint_type}_{selected_id}", can_delete=perms["can_archive"], title="Delete Selected Complaint", help_text="Permanent deletion of the complaint and its follow-up history requires your current QCMS password."):
                st.session_state.pop(f"selected_{complaint_type.lower()}_complaint", None)
                st.rerun()


def _render_followups(repo: Repository, complaint: Mapping[str, Any], employees: list[dict], employee_labels: Mapping[str, str], perms: Mapping[str, bool]) -> None:
    section_bar("COMPLAINT FOLLOW-UP & CLOSURE TRACKING")
    f1, f2, f3, f4 = st.columns(4, gap="small")
    followup_date = f1.date_input("Follow-up Date", value=date.today(), disabled=not perms["can_edit"], key=f"follow_date_{complaint.get('id')}")
    followup_type = f2.selectbox("Follow-up Type", FOLLOWUP_TYPES, format_func=lambda x: x.replace("_", " ").title(), disabled=not perms["can_edit"], key=f"follow_type_{complaint.get('id')}")
    default_emp = str(complaint.get("fourstar_responsible_employee_id") or "")
    responsible = f3.selectbox("Responsible Employee", list(employee_labels), index=list(employee_labels).index(default_emp) if default_emp in employee_labels else 0, format_func=lambda value: employee_labels[value], disabled=not perms["can_edit"] or not employee_labels, key=f"follow_emp_{complaint.get('id')}") if employee_labels else ""
    next_followup = f4.date_input("Next Follow-up Date", value=date.today(), disabled=not perms["can_edit"], key=f"follow_next_{complaint.get('id')}")
    status_after = st.selectbox("Status after Follow-up", ["NO_CHANGE", *STATUSES], format_func=lambda x: x.replace("_", " ").title(), disabled=not perms["can_edit"], key=f"follow_status_{complaint.get('id')}")
    remarks = st.text_area("Follow-up Remarks / Action Update", height=80, disabled=not perms["can_edit"], key=f"follow_remarks_{complaint.get('id')}")
    if st.button("Add Follow-up", type="primary", width="stretch", disabled=not perms["can_edit"], key=f"add_followup_{complaint.get('id')}"):
        if not remarks.strip() or not responsible:
            st.error("Follow-up Remarks and Responsible Employee are mandatory.")
        else:
            repo.insert("quality_complaint_followups", {
                "complaint_id": complaint.get("id"), "followup_date": followup_date, "followup_type": followup_type,
                "remarks": remarks.strip(), "next_followup_date": next_followup, "responsible_employee_id": responsible,
                "status_after_followup": None if status_after == "NO_CHANGE" else status_after,
            })
            if status_after != "NO_CHANGE":
                changes: dict[str, Any] = {"status": status_after}
                if status_after == "CLOSED": changes["closure_date"] = followup_date
                repo.update("quality_complaints", str(complaint.get("id")), changes)
            save_success_popup("Complaint follow-up saved successfully.", queue_for_rerun=True)
            st.rerun()

    followups = repo.select("quality_complaint_followups", eq={"complaint_id": complaint.get("id")}, order_by="followup_date", desc=True, limit=5000)
    if not followups:
        st.caption("No follow-up records yet.")
        return
    emp_map = {str(row["id"]): row for row in employees}
    st.dataframe(pd.DataFrame([
        {"Date": row.get("followup_date"), "Type": str(row.get("followup_type") or "").replace("_", " ").title(), "Remarks / Update": row.get("remarks"), "Next Follow-up": row.get("next_followup_date"), "Responsible": employee_label(emp_map.get(str(row.get("responsible_employee_id"))) or {}), "Status": str(row.get("status_after_followup") or "No Change").replace("_", " ").title()}
        for row in followups
    ]), hide_index=True, width="stretch", height=min(400, 65 + len(followups) * 34))
    if password_delete_panel(repo=repo, table="quality_complaint_followups", rows=followups, labeler=lambda row: f"{row.get('followup_date')} · {str(row.get('followup_type') or '').replace('_',' ').title()} · {str(row.get('remarks') or '')[:70]}", key=f"delete_followup_{complaint.get('id')}", can_delete=perms["can_archive"], title="Delete Selected Follow-up", help_text="Deleting a follow-up requires your current QCMS password."):
        st.rerun()



def render_analysis() -> None:
    page_header(
        "Detailed Complaint Analysis & CAPA",
        "Structured problem definition, containment, 5-Why/root-cause analysis, corrective actions, responsibility and effectiveness closure.",
        "Complaints",
    )
    st.caption("QCMS 4.10.9 · Detailed RCA/CAPA workflow · Build 4109-LOGIN-IMPORT-GUARD")
    repo = Repository(); perms = current_permissions("COMPLAINT_MANAGEMENT")
    complaints = repo.select("quality_complaints", order_by="complaint_date", desc=True, limit=10000)
    if not complaints:
        st.info("Create a Customer or Supplier Complaint before starting detailed analysis.")
        return
    parties = {str(row["id"]): row for row in repo.select("parties", limit=5000)}
    parts = {str(row["id"]): row for row in repo.select("parts", limit=5000)}
    processes = repo.select("processes", eq={"status": "ACTIVE"}, order_by="process_name", limit=5000)
    process_labels = {"": "— Process not linked —", **{str(row["id"]): process_label(row) for row in processes}}
    employees = _employees(repo)
    employee_labels = {str(row["id"]): employee_label(row) for row in employees}
    emp_map = {str(row["id"]): row for row in employees}
    labels = {str(row["id"]): _complaint_label(row, parties) for row in complaints}
    preferred = str(st.session_state.get("complaint_analysis_id") or "")
    if preferred not in labels: preferred = next(iter(labels))
    complaint_id = st.selectbox(
        "Select Complaint for Detailed Analysis",
        list(labels),
        index=list(labels).index(preferred),
        format_func=lambda value: labels[value],
        key="complaint_analysis_selector",
    )
    st.session_state["complaint_analysis_id"] = complaint_id
    complaint = next(row for row in complaints if str(row.get("id")) == complaint_id)
    actions = repo.select("quality_complaint_actions", eq={"complaint_id": complaint_id}, order_by="action_no", limit=5000)
    workflow_progress(_analysis_progress(complaint, actions))

    open_actions = [row for row in actions if str(row.get("status") or "") not in {"COMPLETED", "CANCELLED"}]
    overdue_actions = [row for row in open_actions if _action_overdue(row)]
    debit_balance = max(float(complaint.get("debit_note_amount") or 0) - float(complaint.get("debit_note_settled_amount") or 0), 0.0)
    kpi_grid([
        {"label": "Complaint Status", "value": str(complaint.get("status") or "OPEN").replace("_", " ").title(), "foot": complaint.get("complaint_number"), "color": "#0B6FAE", "background": "#EFF8FF"},
        {"label": "Root Cause", "value": "CONFIRMED" if complaint.get("root_cause_confirmed") else "PENDING", "foot": "Occurrence + escape + systemic analysis", "color": "#15803D" if complaint.get("root_cause_confirmed") else "#D97706", "background": "#F0FDF4" if complaint.get("root_cause_confirmed") else "#FFFBEB"},
        {"label": "Open Actions", "value": len(open_actions), "foot": f"{len(overdue_actions)} overdue", "color": "#B91C1C" if overdue_actions else "#2563EB", "background": "#FEF2F2" if overdue_actions else "#EFF6FF"},
        {"label": "Effectiveness", "value": "VERIFIED" if complaint.get("effectiveness_verified") else "PENDING", "foot": complaint.get("effectiveness_verified_date") or "Verification not completed", "color": "#15803D" if complaint.get("effectiveness_verified") else "#7C3AED", "background": "#F0FDF4" if complaint.get("effectiveness_verified") else "#F5F3FF"},
        {"label": "Debit Balance", "value": f"{complaint.get('currency') or 'INR'} {debit_balance:,.2f}", "foot": str(complaint.get("debit_note_status") or "NOT_REQUIRED").replace("_", " ").title(), "color": "#C2410C" if debit_balance else "#15803D", "background": "#FFF7ED" if debit_balance else "#F0FDF4"},
    ])

    part = parts.get(str(complaint.get("part_id"))) or {}
    party = parties.get(str(complaint.get("party_id"))) or {}
    section_bar("COMPLAINT TRACEABILITY")
    st.dataframe(pd.DataFrame([{
        "Complaint No.": complaint.get("complaint_number"),
        "Type": str(complaint.get("complaint_type") or "").title(),
        "Customer / Supplier": party_label(party),
        "Part": part_label(part) if part else "Not linked",
        "Subject": complaint.get("subject"),
        "Severity": complaint.get("severity"),
        "Target Closure": complaint.get("target_closure_date"),
    }]), hide_index=True, width="stretch")

    writable = perms["can_edit"]
    section_bar("1. PROBLEM DEFINITION & IMPACT", "Define the issue with enough detail to distinguish occurrence, detection and customer/supplier impact.")
    p1, p2, p3 = st.columns([1.15, 1, 1], gap="small")
    current_process = str(complaint.get("process_id") or "")
    process_id = p1.selectbox("Related Process", list(process_labels), index=list(process_labels).index(current_process) if current_process in process_labels else 0, format_func=lambda value: process_labels[value], disabled=not writable, key=f"analysis_process_{complaint_id}")
    defect_mode = p2.text_input("Defect / Failure Mode", value=str(complaint.get("defect_mode") or ""), disabled=not writable, key=f"analysis_defect_{complaint_id}")
    lot_batch = p3.text_input("Lot / Batch Number", value=str(complaint.get("lot_batch_number") or ""), disabled=not writable, key=f"analysis_lot_{complaint_id}")
    q1, q2 = st.columns(2, gap="small")
    heat_number = q1.text_input("Heat Number", value=str(complaint.get("heat_number") or ""), disabled=not writable, key=f"analysis_heat_{complaint_id}")
    detection_point = q2.text_input("Detection Point / Inspection Stage", value=str(complaint.get("detection_point") or ""), disabled=not writable, key=f"analysis_detect_{complaint_id}")
    problem_what = st.text_area("What exactly happened?", value=str(complaint.get("problem_what") or complaint.get("description") or ""), height=78, disabled=not writable, key=f"analysis_what_{complaint_id}")
    w1, w2 = st.columns(2, gap="small")
    problem_where = w1.text_area("Where did it occur / where was it detected?", value=str(complaint.get("problem_where") or ""), height=72, disabled=not writable, key=f"analysis_where_{complaint_id}")
    problem_when = w2.text_area("When / under what operating or inspection condition?", value=str(complaint.get("problem_when") or ""), height=72, disabled=not writable, key=f"analysis_when_{complaint_id}")
    x1, x2 = st.columns(2, gap="small")
    occurrence_pattern = x1.text_area("Occurrence Pattern / Frequency", value=str(complaint.get("occurrence_pattern") or ""), height=72, disabled=not writable, key=f"analysis_pattern_{complaint_id}")
    impact_summary = x2.text_area("Customer / Supplier / Production Impact & Risk", value=str(complaint.get("impact_summary") or ""), height=72, disabled=not writable, key=f"analysis_impact_{complaint_id}")

    section_bar("2. IMMEDIATE CORRECTION & CONTAINMENT")
    immediate_correction = st.text_area("Immediate Correction / Disposition", value=str(complaint.get("immediate_correction") or ""), height=75, disabled=not writable, key=f"analysis_correction_{complaint_id}")
    containment_action = st.text_area("Containment Action", value=str(complaint.get("containment_action") or ""), height=85, disabled=not writable, key=f"analysis_containment_{complaint_id}")
    c1, c2, c3 = st.columns(3, gap="small")
    current_cont_owner = str(complaint.get("containment_responsible_employee_id") or complaint.get("fourstar_responsible_employee_id") or "")
    containment_owner = c1.selectbox("Containment Responsible", list(employee_labels), index=list(employee_labels).index(current_cont_owner) if current_cont_owner in employee_labels else 0, format_func=lambda value: employee_labels[value], disabled=not writable or not employee_labels, key=f"analysis_cont_owner_{complaint_id}") if employee_labels else ""
    containment_due = c2.date_input("Containment Due Date", value=_as_date(complaint.get("containment_due_date"), date.today()), disabled=not writable, key=f"analysis_cont_due_{complaint_id}")
    containment_completed = c3.date_input("Containment Completed Date", value=_as_date(complaint.get("containment_completed_date"), date.today()), disabled=not writable, key=f"analysis_cont_completed_{complaint_id}")
    containment_effectiveness = st.text_area("Containment Effectiveness / Evidence", value=str(complaint.get("containment_effectiveness") or ""), height=72, disabled=not writable, key=f"analysis_cont_effect_{complaint_id}")

    section_bar("3. ROOT CAUSE ANALYSIS", "Separate why the defect occurred from why the control system allowed it to escape.")
    r1, r2, r3 = st.columns([1, 1.15, 1], gap="small")
    analysis_method = r1.selectbox("Analysis Method", ANALYSIS_METHODS, index=ANALYSIS_METHODS.index(str(complaint.get("analysis_method") or "5_WHY")) if str(complaint.get("analysis_method") or "5_WHY") in ANALYSIS_METHODS else 0, format_func=lambda x: x.replace("_", " ").title(), disabled=not writable, key=f"analysis_method_{complaint_id}")
    current_rca_owner = str(complaint.get("root_cause_responsible_employee_id") or complaint.get("fourstar_responsible_employee_id") or "")
    rca_owner = r2.selectbox("Root Cause Analysis Responsible", list(employee_labels), index=list(employee_labels).index(current_rca_owner) if current_rca_owner in employee_labels else 0, format_func=lambda value: employee_labels[value], disabled=not writable or not employee_labels, key=f"analysis_rca_owner_{complaint_id}") if employee_labels else ""
    root_confirmed = r3.checkbox("Root Cause Confirmed", value=bool(complaint.get("root_cause_confirmed")), disabled=not writable, key=f"analysis_rc_confirmed_{complaint_id}")
    why_values = []
    for index in range(1, 6):
        why_values.append(st.text_area(f"Why {index}", value=str(complaint.get(f"why_{index}") or ""), height=62, disabled=not writable, key=f"analysis_why_{index}_{complaint_id}"))
    rc1, rc2, rc3 = st.columns(3, gap="small")
    occurrence_root = rc1.text_area("Occurrence Root Cause - Why defect happened", value=str(complaint.get("occurrence_root_cause") or complaint.get("root_cause") or ""), height=105, disabled=not writable, key=f"analysis_occ_root_{complaint_id}")
    escape_root = rc2.text_area("Escape / Detection Root Cause - Why it was not detected", value=str(complaint.get("escape_root_cause") or ""), height=105, disabled=not writable, key=f"analysis_escape_root_{complaint_id}")
    systemic_root = rc3.text_area("Systemic Root Cause - Why system allowed recurrence", value=str(complaint.get("systemic_root_cause") or ""), height=105, disabled=not writable, key=f"analysis_systemic_root_{complaint_id}")
    root_evidence = st.text_area("Root Cause Evidence / Validation", value=str(complaint.get("root_cause_evidence") or ""), height=80, disabled=not writable, key=f"analysis_root_evidence_{complaint_id}")
    root_confirmed_date = st.date_input("Root Cause Confirmation Date", value=_as_date(complaint.get("root_cause_confirmed_date"), date.today()), disabled=not writable or not root_confirmed, key=f"analysis_root_date_{complaint_id}")

    section_bar("4. EFFECTIVENESS VERIFICATION")
    v1, v2 = st.columns(2, gap="small")
    verification_plan = v1.text_area("Verification Plan", value=str(complaint.get("verification_plan") or ""), height=85, disabled=not writable, key=f"analysis_ver_plan_{complaint_id}")
    effectiveness_criteria = v2.text_area("Acceptance / Effectiveness Criteria", value=str(complaint.get("effectiveness_criteria") or ""), height=85, disabled=not writable, key=f"analysis_eff_criteria_{complaint_id}")
    verification_result = st.text_area("Verification Result / Evidence", value=str(complaint.get("verification_result") or ""), height=85, disabled=not writable, key=f"analysis_ver_result_{complaint_id}")
    vv1, vv2, vv3 = st.columns([1, 1, 1.25], gap="small")
    effectiveness_verified = vv1.checkbox("Effectiveness Verified", value=bool(complaint.get("effectiveness_verified")), disabled=not writable, key=f"analysis_effect_verified_{complaint_id}")
    effectiveness_date = vv2.date_input("Effectiveness Verified Date", value=_as_date(complaint.get("effectiveness_verified_date"), date.today()), disabled=not writable or not effectiveness_verified, key=f"analysis_effect_date_{complaint_id}")
    current_verifier = str(complaint.get("effectiveness_verified_by_employee_id") or "")
    verifier_id = vv3.selectbox("Verified By", list(employee_labels), index=list(employee_labels).index(current_verifier) if current_verifier in employee_labels else 0, format_func=lambda value: employee_labels[value], disabled=not writable or not effectiveness_verified or not employee_labels, key=f"analysis_verifier_{complaint_id}") if employee_labels else ""
    recurrence_check = st.text_area("Recurrence Check / Similar-Part Review", value=str(complaint.get("recurrence_check_result") or ""), height=72, disabled=not writable, key=f"analysis_recurrence_{complaint_id}")

    if st.button("Save Detailed Complaint Analysis", type="primary", width="stretch", disabled=not writable, key=f"save_analysis_{complaint_id}"):
        if root_confirmed and (not occurrence_root.strip() or not root_evidence.strip() or not rca_owner):
            st.error("Confirmed Root Cause requires Occurrence Root Cause, supporting evidence and a responsible employee.")
        elif effectiveness_verified and (not verification_result.strip() or not effectiveness_criteria.strip() or not verifier_id):
            st.error("Effectiveness verification requires criteria, result/evidence and the verifying employee.")
        else:
            calculated_status = str(complaint.get("status") or "OPEN")
            if calculated_status not in {"CLOSED", "CANCELLED"}:
                if effectiveness_verified: calculated_status = "VERIFICATION"
                elif root_confirmed: calculated_status = "CORRECTIVE_ACTION"
                elif why_values[0].strip() or occurrence_root.strip(): calculated_status = "ROOT_CAUSE"
                elif containment_action.strip(): calculated_status = "CONTAINMENT"
            repo.update("quality_complaints", complaint_id, {
                "process_id": process_id or None, "defect_mode": defect_mode.strip() or None, "lot_batch_number": lot_batch.strip() or None,
                "heat_number": heat_number.strip() or None, "problem_what": problem_what.strip() or None, "problem_where": problem_where.strip() or None,
                "problem_when": problem_when.strip() or None, "detection_point": detection_point.strip() or None, "occurrence_pattern": occurrence_pattern.strip() or None,
                "impact_summary": impact_summary.strip() or None, "immediate_correction": immediate_correction.strip() or None,
                "containment_action": containment_action.strip() or None, "containment_responsible_employee_id": containment_owner or None,
                "containment_due_date": containment_due, "containment_completed_date": containment_completed if containment_action.strip() else None,
                "containment_effectiveness": containment_effectiveness.strip() or None, "analysis_method": analysis_method,
                "why_1": why_values[0].strip() or None, "why_2": why_values[1].strip() or None, "why_3": why_values[2].strip() or None,
                "why_4": why_values[3].strip() or None, "why_5": why_values[4].strip() or None,
                "occurrence_root_cause": occurrence_root.strip() or None, "root_cause": occurrence_root.strip() or None,
                "escape_root_cause": escape_root.strip() or None, "systemic_root_cause": systemic_root.strip() or None,
                "root_cause_evidence": root_evidence.strip() or None, "root_cause_confirmed": bool(root_confirmed),
                "root_cause_confirmed_date": root_confirmed_date if root_confirmed else None, "root_cause_responsible_employee_id": rca_owner or None,
                "verification_plan": verification_plan.strip() or None, "effectiveness_criteria": effectiveness_criteria.strip() or None,
                "verification_result": verification_result.strip() or None, "effectiveness_verified": bool(effectiveness_verified),
                "effectiveness_verified_date": effectiveness_date if effectiveness_verified else None, "effectiveness_verified_by_employee_id": verifier_id or None,
                "recurrence_check_result": recurrence_check.strip() or None, "status": calculated_status,
            })
            save_success_popup("Detailed Complaint Analysis saved successfully.", queue_for_rerun=True)
            st.rerun()

    section_bar("5. CORRECTIVE / PREVENTIVE ACTION PLAN & RESPONSIBILITY", "Each action has an accountable owner, target date, completion status, evidence and effectiveness result.")
    actions = repo.select("quality_complaint_actions", eq={"complaint_id": complaint_id}, order_by="action_no", limit=5000)
    action_labels = {"": "＋ New Action", **{str(row["id"]): f"A{int(row.get('action_no') or 0):02d} · {str(row.get('action_type') or '').replace('_',' ').title()} · {str(row.get('action_description') or '')[:70]}" for row in actions}}
    selected_action_id = st.selectbox("Action Plan Item", list(action_labels), format_func=lambda value: action_labels[value], key=f"analysis_action_select_{complaint_id}")
    selected_action = next((row for row in actions if str(row.get("id")) == selected_action_id), None)
    next_action_no = max([int(row.get("action_no") or 0) for row in actions] or [0]) + 1
    a1, a2, a3 = st.columns([.65, 1.2, 1.15], gap="small")
    action_no = a1.number_input("Action No.", min_value=1, value=int((selected_action or {}).get("action_no") or next_action_no), step=1, disabled=bool(selected_action) or not writable, key=f"action_no_{complaint_id}_{selected_action_id}")
    action_type = a2.selectbox("Action Type", ACTION_TYPES, index=ACTION_TYPES.index(str((selected_action or {}).get("action_type") or "OCCURRENCE_CORRECTIVE")) if str((selected_action or {}).get("action_type") or "OCCURRENCE_CORRECTIVE") in ACTION_TYPES else 2, format_func=lambda x: x.replace("_", " ").title(), disabled=not writable, key=f"action_type_{complaint_id}_{selected_action_id}")
    action_status = a3.selectbox("Action Status", ACTION_STATUSES, index=ACTION_STATUSES.index(str((selected_action or {}).get("status") or "OPEN")) if str((selected_action or {}).get("status") or "OPEN") in ACTION_STATUSES else 0, format_func=lambda x: x.replace("_", " ").title(), disabled=not writable, key=f"action_status_{complaint_id}_{selected_action_id}")
    action_description = st.text_area("Action Description", value=str((selected_action or {}).get("action_description") or ""), height=75, disabled=not writable, key=f"action_desc_{complaint_id}_{selected_action_id}")
    ac1, ac2, ac3 = st.columns([1.3, 1, 1], gap="small")
    current_owner = str((selected_action or {}).get("owner_employee_id") or "")
    action_owner = ac1.selectbox("Four Star Responsible Person", list(employee_labels), index=list(employee_labels).index(current_owner) if current_owner in employee_labels else 0, format_func=lambda value: employee_labels[value], disabled=not writable or not employee_labels, key=f"action_owner_{complaint_id}_{selected_action_id}") if employee_labels else ""
    external_owner = ac2.text_input("Customer / Supplier Responsible", value=str((selected_action or {}).get("external_owner_name") or complaint.get("external_responsible_name") or ""), disabled=not writable, key=f"action_external_{complaint_id}_{selected_action_id}")
    action_target = ac3.date_input("Target Date", value=_as_date((selected_action or {}).get("target_date"), date.today()), disabled=not writable, key=f"action_target_{complaint_id}_{selected_action_id}")
    ad1, ad2 = st.columns(2, gap="small")
    completion_date = ad1.date_input("Completion Date", value=_as_date((selected_action or {}).get("completion_date"), date.today()), disabled=not writable or action_status != "COMPLETED", key=f"action_completed_{complaint_id}_{selected_action_id}")
    evidence = ad2.text_area("Implementation Evidence / Reference", value=str((selected_action or {}).get("evidence") or ""), height=70, disabled=not writable, key=f"action_evidence_{complaint_id}_{selected_action_id}")
    effectiveness = st.text_area("Action Effectiveness Result", value=str((selected_action or {}).get("effectiveness_result") or ""), height=70, disabled=not writable, key=f"action_effect_{complaint_id}_{selected_action_id}")
    if st.button("Update Action" if selected_action else "Add Action to Plan", type="primary", width="stretch", disabled=not writable, key=f"save_action_{complaint_id}_{selected_action_id}"):
        if not action_description.strip() or not action_owner:
            st.error("Action Description and Four Star Responsible Person are mandatory.")
        elif action_status == "COMPLETED" and not evidence.strip():
            st.error("Implementation Evidence / Reference is required before an action can be marked Completed.")
        else:
            payload = {
                "complaint_id": complaint_id, "action_no": int(action_no), "action_type": action_type, "action_description": action_description.strip(),
                "owner_employee_id": action_owner, "external_owner_name": external_owner.strip() or None, "target_date": action_target,
                "completion_date": completion_date if action_status == "COMPLETED" else None, "status": action_status,
                "evidence": evidence.strip() or None, "effectiveness_result": effectiveness.strip() or None,
            }
            if selected_action:
                repo.update("quality_complaint_actions", str(selected_action["id"]), payload)
            else:
                repo.insert("quality_complaint_actions", payload)
            save_success_popup("Complaint Action Plan item saved successfully.", queue_for_rerun=True)
            st.rerun()

    actions = repo.select("quality_complaint_actions", eq={"complaint_id": complaint_id}, order_by="action_no", limit=5000)
    if actions:
        action_frame = pd.DataFrame([{
            "Action No.": row.get("action_no"), "Type": str(row.get("action_type") or "").replace("_", " ").title(), "Action": row.get("action_description"),
            "Four Star Owner": employee_label(emp_map.get(str(row.get("owner_employee_id"))) or {}), "External Owner": row.get("external_owner_name") or "-",
            "Target": row.get("target_date"), "Completion": row.get("completion_date") or "-", "Status": "OVERDUE" if _action_overdue(row) else str(row.get("status") or "").replace("_", " ").title(),
            "Evidence": row.get("evidence") or "-", "Effectiveness": row.get("effectiveness_result") or "-",
        } for row in actions])
        st.dataframe(action_frame, hide_index=True, width="stretch", height=min(500, 70 + len(action_frame) * 38))
        if password_delete_panel(repo=repo, table="quality_complaint_actions", rows=actions, labeler=lambda row: f"A{int(row.get('action_no') or 0):02d} · {str(row.get('action_type') or '').replace('_',' ').title()} · {str(row.get('action_description') or '')[:75]}", key=f"delete_action_{complaint_id}", can_delete=perms["can_archive"], title="Delete Selected Action Plan Item", help_text="Permanent deletion requires your current QCMS password."):
            st.rerun()

    _render_complaint_media(
        repo, complaint, perms, allow_upload=False,
        title="6A. COMPLAINT ENTRY PHOTOGRAPHS & MULTIPLE ATTACHMENTS",
    )

    render_attachment_manager(
        repo=repo, entity_type="QUALITY_COMPLAINT", entity_id=complaint_id, folder="complaints",
        slots=COMPLAINT_ATTACHMENT_SLOTS, key_prefix=f"complaint_{complaint_id}",
        can_add_or_replace=perms["can_edit"], can_delete=perms["can_archive"],
        title="6B. ANALYSIS / CLOSURE CONTROLLED ATTACHMENTS",
    )

    section_bar("7. FINAL CLOSURE & APPROVAL")
    refreshed = (repo.select("quality_complaints", eq={"id": complaint_id}, limit=1) or [complaint])[0]
    refreshed_actions = repo.select("quality_complaint_actions", eq={"complaint_id": complaint_id}, order_by="action_no", limit=5000)
    closure_date = st.date_input("Actual Closure Date", value=_as_date(refreshed.get("closure_date"), date.today()), disabled=not writable, key=f"final_closure_date_{complaint_id}")
    close1, close2 = st.columns([1.2, 1], gap="small")
    closure_remarks = close1.text_area("Final Closure Remarks", value=str(refreshed.get("closure_remarks") or ""), height=85, disabled=not writable, key=f"final_closure_remarks_{complaint_id}")
    current_approver = str(refreshed.get("closure_approved_by_employee_id") or "")
    closure_approver = close2.selectbox("Closure Approved By", list(employee_labels), index=list(employee_labels).index(current_approver) if current_approver in employee_labels else 0, format_func=lambda value: employee_labels[value], disabled=not writable or not employee_labels, key=f"closure_approver_{complaint_id}") if employee_labels else ""
    closure_approval_date = st.date_input("Closure Approval Date", value=_as_date(refreshed.get("closure_approved_date"), date.today()), disabled=not writable, key=f"closure_approval_date_{complaint_id}")
    candidate = dict(refreshed); candidate["closure_date"] = closure_date
    ready, gaps = _closure_readiness(candidate, refreshed_actions)
    if ready:
        st.success("Complaint is ready for final quality closure. Commercial Debit Note settlement may continue independently if still pending.")
    else:
        st.warning("Closure pending: " + " · ".join(gaps))
    f1, f2 = st.columns(2, gap="small")
    if f1.button("Save Closure Details", width="stretch", disabled=not writable, key=f"save_closure_details_{complaint_id}"):
        repo.update("quality_complaints", complaint_id, {
            "closure_date": closure_date, "closure_remarks": closure_remarks.strip() or None,
            "closure_approved_by_employee_id": closure_approver or None, "closure_approved_date": closure_approval_date,
        })
        save_success_popup("Complaint closure details saved.", queue_for_rerun=True); st.rerun()
    if f2.button("Close Complaint", type="primary", width="stretch", disabled=not writable or not ready or str(refreshed.get("status")) == "CLOSED", key=f"close_complaint_{complaint_id}"):
        if not closure_approver:
            st.error("Closure Approved By is mandatory.")
        else:
            repo.update("quality_complaints", complaint_id, {
                "closure_date": closure_date, "closure_remarks": closure_remarks.strip() or None,
                "closure_approved_by_employee_id": closure_approver, "closure_approved_date": closure_approval_date, "status": "CLOSED",
            })
            save_success_popup("Complaint closed successfully after RCA, action and effectiveness verification.", queue_for_rerun=True); st.rerun()

    section_bar("PRINT")
    latest = (repo.select("quality_complaints", eq={"id": complaint_id}, limit=1) or [refreshed])[0]
    st.download_button("Download Detailed Complaint Analysis PDF", _complaint_pdf(repo, latest), file_name=f"{latest.get('complaint_number')}_Detailed_Analysis.pdf", mime="application/pdf", width="stretch", key=f"analysis_pdf_{complaint_id}")


def render_records() -> None:
    page_header("Complaint Records", "Search, review, print and follow up Customer and Supplier complaints.", "Complaints")
    repo = Repository(); perms = current_permissions("COMPLAINT_MANAGEMENT")
    rows = repo.select("quality_complaints", order_by="complaint_date", desc=True, limit=10000)
    parties = {str(row["id"]): row for row in repo.select("parties", limit=5000)}
    employees = {str(row["id"]): row for row in repo.select("employees", limit=5000)}
    c1, c2, c3 = st.columns([1.8, 1, 1], gap="small")
    search = c1.text_input("Search Complaint No., Party, Subject or Reference")
    type_filter = c2.selectbox("Complaint Type", ["ALL", "CUSTOMER", "SUPPLIER"])
    status_filter = c3.selectbox("Status", ["ALL", "OVERDUE", *STATUSES])
    filtered = []
    for row in rows:
        if type_filter != "ALL" and str(row.get("complaint_type")) != type_filter: continue
        if status_filter == "OVERDUE" and not _is_overdue(row): continue
        if status_filter not in {"ALL", "OVERDUE"} and str(row.get("status")) != status_filter: continue
        haystack = " ".join([str(row.get("complaint_number") or ""), str(row.get("external_reference") or ""), str(row.get("subject") or ""), str((parties.get(str(row.get("party_id"))) or {}).get("party_name") or "")]).casefold()
        if search and search.casefold() not in haystack: continue
        filtered.append(row)
    if not filtered:
        st.info("No Complaint records match the selected filters.")
        return
    labels = {str(row["id"]): _complaint_label(row, parties) for row in filtered}
    selected_id = st.selectbox("Select Complaint Record", list(labels), format_func=lambda value: labels[value])
    selected = next(row for row in filtered if str(row.get("id")) == selected_id)
    p1, p2, p3 = st.columns(3, gap="small")
    p1.download_button("Download Selected Complaint PDF", _complaint_pdf(repo, selected), file_name=f"{selected.get('complaint_number')}.pdf", mime="application/pdf", width="stretch")
    analysis_page = (st.session_state.get("_qsms_pages") or {}).get("complaint-analysis")
    if p2.button("Open Detailed Analysis & CAPA", width="stretch", disabled=analysis_page is None, key=f"record_analysis_{selected_id}"):
        st.session_state["complaint_analysis_id"] = selected_id
        st.switch_page(analysis_page)
    with p3:
        if password_delete_panel(repo=repo, table="quality_complaints", rows=[selected], labeler=lambda row: _complaint_label(row, parties), key=f"delete_complaint_record_{selected_id}", can_delete=perms["can_archive"], title="Delete Selected Complaint", help_text="Permanent deletion requires your current QCMS password."):
            st.rerun()
    section_bar("COMPLAINT REGISTER")
    action_rows = repo.select("quality_complaint_actions", limit=10000)
    open_action_count: dict[str, int] = {}
    for action in action_rows:
        if str(action.get("status") or "") not in {"COMPLETED", "CANCELLED"}:
            cid = str(action.get("complaint_id") or "")
            open_action_count[cid] = open_action_count.get(cid, 0) + 1
    frame = pd.DataFrame([
        {
            "Complaint No.": row.get("complaint_number"), "Date": row.get("complaint_date"), "Type": str(row.get("complaint_type") or "").title(),
            "Party": (parties.get(str(row.get("party_id"))) or {}).get("party_name"), "Subject": row.get("subject"), "Severity": row.get("severity"),
            "Four Star Responsible": employee_label(employees.get(str(row.get("fourstar_responsible_employee_id"))) or {}),
            "Root Cause": "CONFIRMED" if row.get("root_cause_confirmed") else "PENDING", "Open Actions": open_action_count.get(str(row.get("id")), 0),
            "Effectiveness": "VERIFIED" if row.get("effectiveness_verified") else "PENDING",
            "Target Closure": row.get("target_closure_date"), "Status": "OVERDUE" if _is_overdue(row) else str(row.get("status") or "").replace("_", " ").title(),
            "Debit Note Required": "YES" if row.get("debit_note_required") else "NO", "Debit Note Status": str(row.get("debit_note_status") or "").replace("_", " ").title(),
        }
        for row in filtered
    ])
    st.dataframe(frame, hide_index=True, width="stretch", height=560)
