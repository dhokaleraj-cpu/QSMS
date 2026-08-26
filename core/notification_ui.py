from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from core.notification_service import NotificationService


def notification_confirmation(
    notifier: NotificationService,
    event_key: str,
    *,
    key: str,
    context: Mapping[str, Any] | None = None,
    include_supplier: bool | None = None,
    default_send: bool = True,
) -> dict[str, Any]:
    """Render a controlled entry-level email confirmation block.

    Business transactions may still be saved with email disabled. If email is enabled,
    the user must explicitly confirm the displayed recipients before Save/Create is
    enabled. This keeps email routing visible and intentional without coupling SMTP
    availability to the transaction itself.
    """
    preview = notifier.preview(event_key, context=context, include_supplier=include_supplier)
    send = st.checkbox(
        "Email notification after save",
        value=bool(default_send and preview.get("enabled")),
        key=f"{key}_send",
        help="Untick to save the business transaction without sending this workflow email.",
    )
    confirmed = not send
    if send:
        to_email = str(preview.get("recipient_email") or "").strip()
        to_name = str(preview.get("recipient_name") or "").strip()
        cc_emails = [str(v).strip() for v in (preview.get("cc_emails") or []) if str(v).strip()]
        st.markdown(
            "**Notification recipient preview**  \n"
            f"**To:** {to_name + ' · ' if to_name else ''}{to_email or 'NOT CONFIGURED'}  \n"
            f"**CC:** {', '.join(cc_emails) if cc_emails else '—'}  \n"
            f"**Next stage:** {preview.get('next_stage') or '—'}  \n"
            f"**Template:** {preview.get('template_key') or event_key}"
        )
        if not to_email:
            st.warning("The selected notification route has no recipient email. Configure the responsible Employee / Department in Admin → Email Server & Notifications, or untick email notification.")
        confirmed = st.checkbox(
            "Confirm notification recipient(s)",
            value=False,
            key=f"{key}_confirm",
            help="Required when Email notification after save is enabled.",
        ) and bool(to_email)
    return {"send": bool(send), "confirmed": bool(confirmed), "preview": preview}
