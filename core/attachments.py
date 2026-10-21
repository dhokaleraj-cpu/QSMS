from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import streamlit as st

from core.auth import verify_current_password
from core.database import get_session_client
from core.repository import Repository
from core.ui import section_bar
from core.db_errors import db_message


MICROSTRUCTURE_IMAGE_TYPES = ["png", "jpg", "jpeg", "bmp", "tif", "tiff", "webp", "gif"]

ALLOWED_ATTACHMENT_TYPES = [
    "pdf", "xlsx", "xls", "docx", "doc", "csv", "txt",
    *MICROSTRUCTURE_IMAGE_TYPES, "dwg", "dxf", "zip",
]


@dataclass(frozen=True)
class AttachmentSlot:
    document_type: str
    label: str
    help_text: str = "Optional supporting document"
    parent_table: str | None = None
    parent_field: str | None = None


class AttachmentService:
    """Private Supabase Storage operations for controlled QCMS attachments."""

    bucket = "quality-documents"

    def __init__(self, repo: Repository | None = None) -> None:
        self.repo = repo or Repository()

    def list_active(self, entity_type: str, entity_id: str) -> list[dict]:
        if not entity_id:
            return []
        return self.repo.select(
            "document_attachments",
            eq={"entity_type": entity_type, "entity_id": entity_id, "status": "ACTIVE"},
            order_by="created_at",
            limit=250,
        )

    def existing_by_path(self, object_path: str) -> dict | None:
        """Any attachment row (ACTIVE or archived) already holding this storage path."""
        if not object_path:
            return None
        try:
            rows = self.repo.select("document_attachments", eq={"object_path": object_path}, limit=1)
        except Exception:
            return None
        return rows[0] if rows else None

    def _client(self):
        client = get_session_client()
        if client is None:
            raise RuntimeError("Live Supabase session is required for attachment access.")
        return client

    @staticmethod
    def _safe_token(value: str) -> str:
        token = re.sub(r"[^a-z0-9]+", "_", str(value or "").casefold()).strip("_")
        return token or "attachment"

    @staticmethod
    def _bytes(file: Any) -> bytes:
        data = file.getvalue()
        if not data:
            raise ValueError("The selected attachment is empty.")
        return data

    def upload(
        self,
        *,
        entity_type: str,
        entity_id: str,
        folder: str,
        slot: AttachmentSlot,
        file: Any,
        existing: Mapping[str, Any] | None = None,
        password: str = "",
    ) -> dict:
        if not entity_id:
            raise ValueError("Save the QCMS record before uploading an attachment.")
        if existing:
            verify_current_password(password)

        client = self._client()
        content = self._bytes(file)
        object_path = str((existing or {}).get("object_path") or "").strip()
        if not object_path:
            object_path = (
                f"{self.repo.tenant_id}/{self._safe_token(folder)}/{entity_id}/"
                f"{self._safe_token(slot.document_type)}"
            )

        client.storage.from_(self.bucket).upload(
            object_path,
            content,
            {
                "content-type": getattr(file, "type", None) or "application/octet-stream",
                "upsert": "true",
            },
        )
        payload = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "document_type": slot.document_type,
            "file_name": str(getattr(file, "name", "attachment")),
            "object_path": object_path,
            "mime_type": getattr(file, "type", None),
            "size_bytes": len(content),
            "checksum": hashlib.sha256(content).hexdigest(),
            "status": "ACTIVE",
        }
        # R35: the storage path is fixed per record + slot, so a re-upload (for example at
        # report finalization, or after an earlier file was archived) must reuse the same
        # attachment row instead of inserting a duplicate object_path (unique per tenant).
        row = existing or self.existing_by_path(object_path)
        if row:
            saved = self.repo.update("document_attachments", str(row["id"]), payload)
        else:
            saved = self.repo.insert("document_attachments", payload)

        if slot.parent_table and slot.parent_field:
            self.repo.update(slot.parent_table, entity_id, {slot.parent_field: object_path})
        return saved

    def upload_additional(
        self,
        *,
        entity_type: str,
        entity_id: str,
        folder: str,
        document_type: str,
        title: str,
        file: Any,
    ) -> dict:
        """Append a uniquely stored controlled attachment without replacing earlier files."""
        if not entity_id:
            raise ValueError("Save the QCMS record before uploading an attachment.")
        title = str(title or "").strip()
        if not title:
            raise ValueError("Attachment / Photograph Title is mandatory.")
        content = self._bytes(file)
        client = self._client()
        original_name = str(getattr(file, "name", "attachment"))
        suffix = Path(original_name).suffix.casefold() or ".bin"
        stem = self._safe_token(Path(original_name).stem)
        object_path = (
            f"{self.repo.tenant_id}/{self._safe_token(folder)}/{entity_id}/"
            f"{self._safe_token(document_type)}/{uuid.uuid4().hex[:12]}_{stem}{suffix}"
        )
        client.storage.from_(self.bucket).upload(
            object_path,
            content,
            {
                "content-type": getattr(file, "type", None) or "application/octet-stream",
                "upsert": "false",
            },
        )
        try:
            return self.repo.insert(
                "document_attachments",
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "document_type": document_type,
                    "document_title": title,
                    "file_name": original_name,
                    "object_path": object_path,
                    "mime_type": getattr(file, "type", None),
                    "size_bytes": len(content),
                    "checksum": hashlib.sha256(content).hexdigest(),
                    "status": "ACTIVE",
                },
            )
        except Exception:
            try:
                client.storage.from_(self.bucket).remove([object_path])
            except Exception:
                pass
            raise

    def download(self, attachment: Mapping[str, Any]) -> bytes:
        path = str(attachment.get("object_path") or "").strip()
        if not path:
            raise ValueError("Attachment storage path is missing.")
        return bytes(self._client().storage.from_(self.bucket).download(path))

    def delete(
        self,
        *,
        attachment: Mapping[str, Any],
        entity_id: str,
        slot: AttachmentSlot,
        password: str,
    ) -> None:
        verify_current_password(password)
        attachment_id = str(attachment.get("id") or "").strip()
        if not attachment_id:
            raise ValueError("Attachment record is missing.")

        result = self.repo.rpc(
            "qsms_delete_document_attachment",
            {"p_attachment_id": attachment_id},
        )
        object_path = str((result or {}).get("object_path") or attachment.get("object_path") or "").strip()
        if object_path:
            self._client().storage.from_(self.bucket).remove([object_path])
        if slot.parent_table and slot.parent_field:
            try:
                self.repo.update(slot.parent_table, entity_id, {slot.parent_field: None})
            except Exception:
                # The attachment register is authoritative. A legacy path column must
                # never block a controlled attachment deletion.
                pass


def _file_size_text(value: Any) -> str:
    try:
        size = float(value or 0)
    except (TypeError, ValueError):
        size = 0
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):,.2f} MB"
    if size >= 1024:
        return f"{size / 1024:,.1f} KB"
    return f"{size:,.0f} bytes"


def new_attachment_uploaders(
    slots: Sequence[AttachmentSlot],
    *,
    key_prefix: str,
    title: str = "OPTIONAL ATTACHMENTS",
) -> dict[str, Any]:
    """Return up to three optional UploadedFile values for a not-yet-saved record."""
    section_bar(title)
    st.caption("Up to three files may be attached. All attachment slots are optional.")
    uploads: dict[str, Any] = {}
    cols = st.columns(len(slots), gap="small")
    for index, (col, slot) in enumerate(zip(cols, slots), start=1):
        with col:
            uploads[slot.document_type] = st.file_uploader(
                slot.label,
                type=ALLOWED_ATTACHMENT_TYPES,
                key=f"{key_prefix}_new_attachment_{index}",
                help=slot.help_text,
            )
    return uploads


def render_attachment_manager(
    *,
    repo: Repository,
    entity_type: str,
    entity_id: str,
    folder: str,
    slots: Sequence[AttachmentSlot],
    key_prefix: str,
    can_add_or_replace: bool,
    can_delete: bool,
    title: str = "ATTACHMENTS",
) -> None:
    """Render download, optional add, password replace and password delete controls."""
    if not entity_id:
        return
    section_bar(title)
    st.caption(
        "Download attachments at any time. Adding an empty slot is permitted; replacing or deleting an existing file requires your current QCMS password."
    )
    service = AttachmentService(repo)
    attachments = service.list_active(entity_type, entity_id)
    by_type = {str(row.get("document_type")): row for row in attachments}
    cols = st.columns(len(slots), gap="small")

    for index, (col, slot) in enumerate(zip(cols, slots), start=1):
        existing = by_type.get(slot.document_type)
        with col:
            with st.container(border=True, key=f"{key_prefix}_attachment_card_{index}"):
                st.markdown(f"**{slot.label}**")
                if existing:
                    st.caption(
                        f"{existing.get('file_name') or 'Attachment'} · "
                        f"{_file_size_text(existing.get('size_bytes'))}"
                    )
                    try:
                        file_bytes = service.download(existing)
                        st.download_button(
                            "Download",
                            data=file_bytes,
                            file_name=str(existing.get("file_name") or f"attachment_{index}"),
                            mime=str(existing.get("mime_type") or "application/octet-stream"),
                            key=f"{key_prefix}_download_{index}_{existing.get('id')}",
                            width="stretch",
                        )
                    except Exception as exc:
                        st.error(f"Download unavailable: {exc}")

                    with st.expander("Replace / Delete", expanded=False):
                        replacement = st.file_uploader(
                            "Replacement file",
                            type=ALLOWED_ATTACHMENT_TYPES,
                            key=f"{key_prefix}_replace_file_{index}_{existing.get('id')}",
                            disabled=not can_add_or_replace,
                        )
                        replace_password = st.text_input(
                            "Current QCMS password for replacement",
                            type="password",
                            key=f"{key_prefix}_replace_password_{index}_{existing.get('id')}",
                            disabled=not can_add_or_replace,
                        )
                        if st.button(
                            "Replace attachment",
                            key=f"{key_prefix}_replace_button_{index}_{existing.get('id')}",
                            disabled=not can_add_or_replace or replacement is None or not replace_password,
                            width="stretch",
                        ):
                            try:
                                service.upload(
                                    entity_type=entity_type,
                                    entity_id=entity_id,
                                    folder=folder,
                                    slot=slot,
                                    file=replacement,
                                    existing=existing,
                                    password=replace_password,
                                )
                                st.success("Attachment replaced successfully.")
                                st.rerun()
                            except Exception as exc:
                                st.error(db_message(exc))

                        st.divider()
                        delete_password = st.text_input(
                            "Current QCMS password for deletion",
                            type="password",
                            key=f"{key_prefix}_delete_password_{index}_{existing.get('id')}",
                            disabled=not can_delete,
                        )
                        confirm = st.checkbox(
                            "Permanently delete this attachment",
                            key=f"{key_prefix}_delete_confirm_{index}_{existing.get('id')}",
                            disabled=not can_delete,
                        )
                        if st.button(
                            "Delete attachment",
                            type="primary",
                            key=f"{key_prefix}_delete_button_{index}_{existing.get('id')}",
                            disabled=not can_delete or not delete_password or not confirm,
                            width="stretch",
                        ):
                            try:
                                service.delete(
                                    attachment=existing,
                                    entity_id=entity_id,
                                    slot=slot,
                                    password=delete_password,
                                )
                                st.success("Attachment deleted successfully.")
                                st.rerun()
                            except Exception as exc:
                                st.error(db_message(exc))
                else:
                    st.caption("No file attached")
                    new_file = st.file_uploader(
                        "Add optional file",
                        type=ALLOWED_ATTACHMENT_TYPES,
                        key=f"{key_prefix}_add_file_{index}",
                        disabled=not can_add_or_replace,
                    )
                    if st.button(
                        "Upload attachment",
                        key=f"{key_prefix}_add_button_{index}",
                        disabled=not can_add_or_replace or new_file is None,
                        width="stretch",
                    ):
                        try:
                            service.upload(
                                entity_type=entity_type,
                                entity_id=entity_id,
                                folder=folder,
                                slot=slot,
                                file=new_file,
                            )
                            st.success("Attachment uploaded successfully.")
                            st.rerun()
                        except Exception as exc:
                            st.error(db_message(exc))


def saved_photo_preview(record: Mapping[str, Any] | None, slot: int, *, field_prefix: str = "microstructure_image_", caption_prefix: str = "microstructure_caption_") -> bool:
    """R35: show the already-saved photograph of a report slot as a thumbnail.

    Users no longer need to upload photographs again at finalization: the saved file is shown
    here and is kept unless a new file is chosen to replace it. Returns True when a photo exists."""
    path = str((record or {}).get(f"{field_prefix}{slot}_path") or "").strip()
    if not path:
        return False
    cache = st.session_state.setdefault("_qcms_photo_preview_cache", {})
    data = cache.get(path)
    if data is None:
        try:
            data = AttachmentService().download({"object_path": path})
            if len(cache) > 40:
                cache.clear()
            cache[path] = data
        except Exception:
            data = b""
    title = str((record or {}).get(f"{caption_prefix}{slot}") or "").strip()
    if data:
        try:
            st.image(data, caption=f"Saved · {title}" if title else "Saved photo", width="stretch")
        except Exception:
            st.caption(f"Photo {slot} saved" + (f" · {title}" if title else ""))
    else:
        st.caption(f"Photo {slot} saved" + (f" · {title}" if title else "") + " (preview not available)")
    st.caption("Kept automatically – choose a new file only to replace it.")
    return True
