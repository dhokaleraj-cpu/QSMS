from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

import streamlit as st

from core.notification_service import NotificationService


def _split_emails(value: Any) -> list[str]:
    result: list[str] = []
    for token in re.split(r"[;,\n]+", str(value or "")):
        email = token.strip()
        if email and "@" in email and email.casefold() not in {item.casefold() for item in result}:
            result.append(email)
    return result


def _confirm_signature(to_email: str, cc_emails: Sequence[str], event_key: str) -> str:
    return "|".join([str(event_key).upper(), to_email.casefold(), *(email.casefold() for email in cc_emails)])


def _confirmation_dialog(*, title: str, to_email: str, cc_emails: Sequence[str], subject: str, on_confirm) -> None:
    @st.dialog(title)
    def _dialog() -> None:
        st.markdown(
            f"**To:** {to_email or 'NOT CONFIGURED'}  \n"
            f"**CC:** {', '.join(cc_emails) if cc_emails else '—'}  \n"
            f"**Subject:** {subject or 'QCMS Notification'}"
        )
        st.warning("Confirm the recipients before QCMS releases this email notification.")
        c1, c2 = st.columns(2, gap="small")
        if c1.button("Confirm Email", type="primary", width="stretch"):
            on_confirm()
        if c2.button("Cancel", width="stretch"):
            st.rerun()
    _dialog()


def notification_confirmation(
    notifier: NotificationService,
    event_key: str,
    *,
    key: str,
    context: Mapping[str, Any] | None = None,
    include_supplier: bool | None = None,
    default_send: bool = True,
) -> dict[str, Any]:
    """Entry-level email confirmation with editable recipients and a modal confirm.

    The transaction can always be saved with email disabled. If email is enabled,
    To / CC are editable on the entry page and QCMS requires a confirmation dialog
    before the Save/Create action becomes available.
    """
    preview = notifier.preview(event_key, context=context, include_supplier=include_supplier)
    send = st.checkbox(
        "Email notification after save",
        value=bool(default_send and preview.get("enabled")),
        key=f"{key}_send",
        help="Untick to save the business transaction without sending this workflow email.",
    )
    if not send:
        return {
            "send": False, "confirmed": True, "preview": preview,
            "recipient_email": "", "cc_emails": [],
        }

    default_to = str(preview.get("recipient_email") or "").strip()
    default_cc = "; ".join(str(v).strip() for v in (preview.get("cc_emails") or []) if str(v).strip())
    c1, c2 = st.columns(2, gap="small")
    to_email = c1.text_input(
        "Notification To",
        value=str(st.session_state.get(f"{key}_to", default_to)),
        key=f"{key}_to",
        help="You may edit the responsible recipient for this transaction before confirmation.",
    ).strip()
    cc_text = c2.text_input(
        "Notification CC",
        value=str(st.session_state.get(f"{key}_cc", default_cc)),
        key=f"{key}_cc",
        help="Separate multiple email addresses with semicolon or comma.",
    )
    cc_emails = _split_emails(cc_text)
    subject = str(preview.get("subject") or f"QCMS · {event_key.replace('_', ' ').title()}")
    st.markdown(
        f"**Responsible Department:** {preview.get('department') or '—'}  \n"
        f"**Next stage:** {preview.get('next_stage') or '—'}  \n"
        f"**Template:** {preview.get('template_key') or event_key}"
    )
    if not to_email or "@" not in to_email:
        st.warning("Enter a valid primary recipient email or untick Email notification after save.")

    signature = _confirm_signature(to_email, cc_emails, event_key)
    confirmed_signature = str(st.session_state.get(f"{key}_confirmed_signature") or "")
    confirmed = bool(to_email and "@" in to_email and signature == confirmed_signature)
    if confirmed:
        st.success("Email recipients confirmed. Any recipient change will require confirmation again.")
    else:
        def _mark_confirmed() -> None:
            st.session_state[f"{key}_confirmed_signature"] = signature
            st.rerun()
        if st.button("Review & Confirm Email Recipients", key=f"{key}_review", width="stretch", disabled=not to_email or "@" not in to_email):
            _confirmation_dialog(
                title="Confirm Email Notification",
                to_email=to_email,
                cc_emails=cc_emails,
                subject=subject,
                on_confirm=_mark_confirmed,
            )

    return {
        "send": True,
        "confirmed": confirmed,
        "preview": preview,
        "recipient_email": to_email,
        "cc_emails": cc_emails,
    }


def notification_overrides(preference: Mapping[str, Any] | None) -> dict[str, Any]:
    pref = dict(preference or {})
    return {
        "recipient_email": str(pref.get("recipient_email") or "").strip() or None,
        "cc_emails": [str(v).strip() for v in (pref.get("cc_emails") or []) if str(v).strip()],
    }


def record_email_sender(
    notifier: NotificationService,
    event_key: str,
    *,
    related_table: str,
    related_id: str,
    key: str,
    context: Mapping[str, Any] | None = None,
    include_supplier: bool | None = None,
    title: str = "SEND EMAIL NOTIFICATION FOR THIS RECORD",
) -> None:
    """Send one controlled notification for a selected saved record.

    Recipients are editable and the email cannot be dispatched until a modal
    confirmation is completed. The normal template, generated PDF and controlled
    record attachments remain in force.
    """
    with st.expander(title, expanded=False):
        preview = notifier.preview(event_key, context=context, include_supplier=include_supplier)
        c1, c2 = st.columns(2, gap="small")
        to_email = c1.text_input(
            "To",
            value=str(preview.get("recipient_email") or ""),
            key=f"{key}_record_to",
        ).strip()
        cc_text = c2.text_input(
            "CC",
            value="; ".join(preview.get("cc_emails") or []),
            key=f"{key}_record_cc",
        )
        cc_emails = _split_emails(cc_text)
        st.markdown(
            f"**Template:** {preview.get('template_key') or event_key}  \n"
            f"**Next stage:** {preview.get('next_stage') or '—'}  \n"
            "**Attachments:** generated QCMS PDF + available controlled record documents (as enabled by the template)."
        )
        subject = str(preview.get("subject") or f"QCMS · {event_key.replace('_', ' ').title()}")

        def _send() -> None:
            try:
                row = notifier.enqueue(
                    event_key,
                    related_table=related_table,
                    related_id=related_id,
                    context=context,
                    recipient_email=to_email,
                    cc_emails=cc_emails,
                    include_supplier=include_supplier,
                )
                result = notifier.dispatch([row] if row else [])
                if not row:
                    st.session_state[f"{key}_record_send_message"] = "Notification could not be queued. Check the route/template and recipient."
                elif result.get("error"):
                    st.session_state[f"{key}_record_send_message"] = f"Notification queued; delivery returned: {result.get('error')}"
                else:
                    st.session_state[f"{key}_record_send_message"] = "Email notification queued / delivery requested successfully."
            except Exception as exc:
                st.session_state[f"{key}_record_send_message"] = str(exc)
            st.rerun()

        if st.button("Review & Send Email", type="primary", width="stretch", key=f"{key}_record_review", disabled=not to_email or "@" not in to_email):
            _confirmation_dialog(
                title="Confirm Record Email",
                to_email=to_email,
                cc_emails=cc_emails,
                subject=subject,
                on_confirm=_send,
            )
        message = str(st.session_state.pop(f"{key}_record_send_message", "") or "")
        if message:
            st.info(message)


def template_test_sender(
    notifier: NotificationService,
    template_key: str,
    *,
    key: str,
    default_recipient: str = "",
    context: Mapping[str, Any] | None = None,
) -> None:
    """Test a selected email template with a manually entered recipient."""
    st.markdown("**Test this template with a manual recipient**")
    c1, c2 = st.columns(2, gap="small")
    to_email = c1.text_input("Manual Test Recipient", value=default_recipient, key=f"{key}_test_to").strip()
    cc_text = c2.text_input("Manual Test CC", value="", key=f"{key}_test_cc")
    cc_emails = _split_emails(cc_text)
    sample = {
        "document_no": "TEST-0001",
        "document_type": "QCMS TEMPLATE TEST",
        "part_number": "TEST-PART",
        "fsi_part_number": "FSI-TEST",
        "part_description": "Template test record",
        "heat_number": "TEST-HEAT",
        "supplier_name": "Test Supplier",
        "customer_name": "Test Customer",
        "due_date": "DD-MM-YYYY",
        "next_stage": "Template Test / Next Stage",
        "department": "Test Department",
        "report_date": "DD-MM-YYYY",
        "open_count": 1,
        "overdue_count": 0,
        **dict(context or {}),
    }
    preview = notifier.preview(template_key, context=sample)
    subject = str(preview.get("subject") or f"QCMS · {template_key.replace('_', ' ').title()}")

    def _send_test() -> None:
        try:
            row = notifier.enqueue(
                template_key,
                recipient_email=to_email,
                recipient_name="QCMS Template Test",
                cc_emails=cc_emails,
                template_key=template_key,
                context=sample,
                include_generated_pdf=False,
                include_record_attachments=False,
                include_supplier=False,
            )
            result = notifier.dispatch([row] if row else [])
            if not row:
                st.session_state[f"{key}_template_test_message"] = "Template test could not be queued."
            elif result.get("error"):
                st.session_state[f"{key}_template_test_message"] = f"Template test queued; delivery returned: {result.get('error')}"
            else:
                st.session_state[f"{key}_template_test_message"] = "Template test email queued / delivery requested successfully."
        except Exception as exc:
            st.session_state[f"{key}_template_test_message"] = str(exc)
        st.rerun()

    if st.button("Review & Send Template Test", width="stretch", key=f"{key}_test_review", disabled=not to_email or "@" not in to_email):
        _confirmation_dialog(
            title="Confirm Template Test Email",
            to_email=to_email,
            cc_emails=cc_emails,
            subject=subject,
            on_confirm=_send_test,
        )
    message = str(st.session_state.pop(f"{key}_template_test_message", "") or "")
    if message:
        st.info(message)
