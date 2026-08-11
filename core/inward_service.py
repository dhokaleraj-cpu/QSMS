from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from core.database import get_session_client
from core.repository import Repository


class InwardService:
    def __init__(self) -> None:
        self.repo = Repository()

    def accepted_rmtc_parts(self) -> list[dict]:
        rows = self.repo.select(
            "v_qsms_accepted_rmtc_parts",
            order_by="certificate_date",
            desc=True,
            limit=3000,
        )
        return rows

    def list(self) -> list[dict]:
        return self.repo.select("v_qsms_inward_register", order_by="created_at", desc=True, limit=3000)

    def get(self, record_id: str) -> dict | None:
        return self.repo.get("inward_lots", record_id)

    def report_payload(self, record_id: str) -> dict:
        record = self.get(record_id) or {}
        if not record:
            raise ValueError("Material Inward record not found.")
        register_rows = self.repo.select("v_qsms_inward_register", eq={"id": record_id}, limit=1)
        register = register_rows[0] if register_rows else {}
        part = self.repo.get("parts", str(record.get("part_id") or "")) or {}
        supplier = self.repo.get("parties", str(record.get("supplier_id") or "")) or {}
        rmtc = self.repo.get("rmtc_approvals", str(record.get("rmtc_approval_id") or "")) or {}
        employee_ids = [str(value) for value in (record.get("prepared_by_employee_id"), record.get("validated_by_employee_id")) if value]
        employee_rows = self.repo.select("employees", in_={"id": employee_ids}, limit=20) if employee_ids else []
        employees = {str(row.get("id")): row for row in employee_rows}
        metlab = self.repo.select("lab_tests", eq={"inward_lot_id": record_id, "test_type": "METLAB"}, order_by="updated_at", desc=True, limit=1)
        dimensional = self.repo.select("inspection_reports", eq={"inward_lot_id": record_id, "report_type": "DIMENSIONAL"}, order_by="updated_at", desc=True, limit=1)
        return {
            "record": record, "register": register, "part": part, "supplier": supplier, "rmtc": rmtc, "employees": employees,
            "metlab": metlab[0] if metlab else {}, "dimensional": dimensional[0] if dimensional else {},
        }

    def next_number(self) -> str:
        return str(self.repo.rpc("qsms_next_document_number", {"p_sequence_code": "INWARD"}) or "")

    def employees(self, authority: str | None = None) -> list[dict]:
        rows = self.repo.select("employees", eq={"status": "ACTIVE"}, order_by="first_name", limit=2000)
        if authority:
            filtered = [r for r in rows if authority in (r.get("approval_authorities") or [])]
            return filtered or rows
        return rows

    def save(self, payload: dict[str, Any], record_id: str | None = None) -> dict:
        if record_id:
            return self.repo.update("inward_lots", record_id, payload)
        return self.repo.insert("inward_lots", payload)

    def upload_copy(self, inward_id: str, file: Any) -> str:
        client = get_session_client()
        if client is None:
            raise RuntimeError("Live Supabase session is required for inward attachment upload.")
        ext = Path(file.name).suffix.lower() or ".bin"
        content = file.getvalue()
        digest = hashlib.sha1(file.name.encode("utf-8")).hexdigest()[:8]
        path = f"{self.repo.tenant_id}/inward/{inward_id}/inward_copy_{digest}{ext}"
        client.storage.from_("quality-documents").upload(
            path,
            content,
            {"content-type": file.type or "application/octet-stream", "upsert": "true"},
        )
        existing = self.repo.find_one(
            "document_attachments",
            eq={"entity_type": "MATERIAL_INWARD", "entity_id": inward_id, "document_type": "INWARD_COPY"},
        )
        attachment = {
            "entity_type": "MATERIAL_INWARD",
            "entity_id": inward_id,
            "document_type": "INWARD_COPY",
            "file_name": file.name,
            "object_path": path,
            "mime_type": file.type,
            "size_bytes": len(content),
            "checksum": hashlib.sha256(content).hexdigest(),
            "status": "ACTIVE",
        }
        if existing:
            self.repo.update("document_attachments", str(existing["id"]), attachment)
        else:
            self.repo.insert("document_attachments", attachment)
        self.repo.update("inward_lots", inward_id, {"inward_copy_path": path})
        return path
