from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.database import get_session_client
from core.repository import Repository


_ENTITY_TYPES = {
    "rmtc_approvals": "RMTC",
    "inspection_reports": "DIMENSIONAL_REPORT",
    "lab_tests": "METLAB_REPORT",
    "inward_lots": "MATERIAL_INWARD",
    "supply_customer_orders": "SUPPLY_CUSTOMER_ORDER",
    "supply_purchase_orders": "SUPPLY_PURCHASE_ORDER",
    "supply_po_confirmations": "PO_CONFIRMATION",
    "osp_jobs": "OSP_JOB",
}


class _SafeTemplate(dict):
    def __missing__(self, key: str) -> str:
        return "-"


def _normalize_department(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())




def _quantity_text(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return str(value or "-")
    if abs(number - round(number)) < 1e-9:
        return f"{number:,.0f}"
    return f"{number:,.3f}".rstrip("0").rstrip(".")

def _template_text(value: Any, context: Mapping[str, Any]) -> str:
    text = str(value or "")
    # User-facing templates use {{ field }}. Convert to format_map tokens while
    # keeping unknown placeholders visible as '-'.
    text = re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", r"{\1}", text)
    try:
        return text.format_map(_SafeTemplate({k: "-" if v in (None, "") else v for k, v in context.items()}))
    except Exception:
        return text


class NotificationService:
    """Controlled workflow email, template, routing and attachment service.

    Notifications are first written to the outbox. Workflow execution must never
    roll back because email delivery fails. SMTP errors never roll back a QCMS
    business transaction. v4.14.7 adds template-driven subjects/bodies,
    employee + department responsibility routing, supplier copies, generated PDF
    attachments and existing controlled document attachments.
    """

    bucket = "quality-documents"

    def __init__(self, repo: Repository | None = None) -> None:
        self.repo = repo or Repository()

    # ---------------------------------------------------------------- routing/templates
    def route(self, event_key: str) -> dict | None:
        rows = self.repo.select(
            "qcms_notification_routes",
            eq={"event_key": str(event_key).upper(), "enabled": True},
            limit=1,
        )
        return rows[0] if rows else None

    def template(self, template_key: str | None, event_key: str) -> dict | None:
        key = str(template_key or event_key or "").strip().upper()
        if not key:
            return None
        try:
            rows = self.repo.select(
                "qcms_email_templates",
                eq={"template_key": key, "enabled": True},
                limit=1,
            )
            return rows[0] if rows else None
        except Exception:
            # Backward-compatible until the additive v4.14.7 migration is applied.
            return None

    def _employee(self, employee_id: Any) -> dict:
        value = str(employee_id or "").strip()
        return self.repo.get("employees", value) or {} if value else {}

    @staticmethod
    def _employee_email(employee: Mapping[str, Any]) -> tuple[str, str]:
        email = str(employee.get("email") or "").strip()
        name = " ".join(
            v for v in (
                str(employee.get("first_name") or "").strip(),
                str(employee.get("last_name") or "").strip(),
            ) if v
        )
        return email, name or str(employee.get("employee_code") or "").strip()

    def department_emails(self, department: str | None, *, exclude: Sequence[str] = ()) -> list[str]:
        target = _normalize_department(department)
        if not target:
            return []
        excluded = {str(v or "").casefold() for v in exclude}
        rows = self.repo.select("employees", eq={"status": "ACTIVE"}, order_by="first_name", limit=5000)
        result: list[str] = []
        for row in rows:
            if _normalize_department(row.get("department")) != target:
                continue
            email = str(row.get("email") or "").strip()
            if email and email.casefold() not in excluded and email.casefold() not in {v.casefold() for v in result}:
                result.append(email)
        return result

    @staticmethod
    def _party_notification_emails(party: Mapping[str, Any]) -> list[str]:
        raw = [str(party.get("email") or "")]
        raw.append(str(party.get("notification_emails") or ""))
        values: list[str] = []
        for source in raw:
            for token in re.split(r"[;,\n]+", source):
                email = token.strip()
                if email and "@" in email and email.casefold() not in {v.casefold() for v in values}:
                    values.append(email)
        return values

    def recipient_for_route(self, route: Mapping[str, Any]) -> tuple[str, str]:
        employee = self._employee(route.get("employee_id"))
        email, name = self._employee_email(employee)
        if email:
            return email, name
        # If an employee is not explicitly assigned, choose the first active employee
        # in the configured department. The remaining department recipients are CC'd.
        department = str(route.get("department") or "").strip()
        if department:
            dept_rows = [
                row for row in self.repo.select("employees", eq={"status": "ACTIVE"}, order_by="first_name", limit=5000)
                if _normalize_department(row.get("department")) == _normalize_department(department)
                and str(row.get("email") or "").strip()
            ]
            if dept_rows:
                return self._employee_email(dept_rows[0])
        return str(route.get("fallback_email") or "").strip(), str(route.get("route_label") or "").strip()

    # ---------------------------------------------------------------- context
    def _record_context(self, related_table: str | None, related_id: str | None) -> dict[str, Any]:
        table = str(related_table or "").strip()
        rid = str(related_id or "").strip()
        if not table or not rid:
            return {}
        try:
            record = self.repo.get(table, rid) or {}
        except Exception:
            return {}
        ctx: dict[str, Any] = {"record_id": rid, "related_table": table}
        ctx.update({k: v for k, v in record.items() if isinstance(v, (str, int, float, bool)) or v is None})

        part_id = record.get("part_id")
        if part_id:
            part = self.repo.get("parts", str(part_id)) or {}
            ctx.update({
                "part_number": part.get("part_number"),
                "fsi_part_number": part.get("fsi_part_number"),
                "part_description": part.get("part_name"),
            })
        supplier_id = record.get("supplier_id") or record.get("rm_supplier_id") or record.get("forging_supplier_id") or record.get("vendor_id")
        if supplier_id:
            supplier = self.repo.get("parties", str(supplier_id)) or {}
            ctx.update({
                "supplier_id": str(supplier_id),
                "supplier_name": supplier.get("party_name"),
                "supplier_code": supplier.get("party_code"),
                "supplier_email": supplier.get("email"),
            })
        customer_id = record.get("customer_id")
        if customer_id:
            customer = self.repo.get("parties", str(customer_id)) or {}
            ctx.update({"customer_name": customer.get("party_name"), "customer_code": customer.get("party_code")})

        if table == "rmtc_approvals":
            ctx.update({"document_no": record.get("rmtc_number"), "document_type": "RMTC", "due_date": record.get("certificate_date")})
        elif table == "inspection_reports":
            ctx.update({"document_no": record.get("report_number"), "document_type": "Dimensional Report", "due_date": record.get("inspection_date")})
        elif table == "lab_tests":
            ctx.update({"document_no": record.get("report_number"), "document_type": "MetLAB Report", "due_date": record.get("test_date")})
        elif table == "supply_customer_orders":
            ctx.update({"document_no": record.get("master_reference_no"), "document_type": "Customer Order / Schedule", "due_date": record.get("customer_delivery_date")})
        elif table == "supply_purchase_orders":
            ctx.update({
                "document_no": record.get("po_number"),
                "document_type": "Purchase Order",
                "po_number": record.get("po_number"),
                "order_date": record.get("order_date"),
                "delivery_date": record.get("delivery_date"),
                "due_date": record.get("delivery_date"),
                "requisitioner": record.get("requisitioner"),
                "payment_term": record.get("payment_term"),
                "incoterm": record.get("incoterm"),
                "quotation_reference": record.get("quotation_reference"),
            })
            supplier_id = record.get("supplier_id")
            if supplier_id:
                supplier = self.repo.get("parties", str(supplier_id)) or {}
                ctx.update({"supplier_id": str(supplier_id), "supplier_name": supplier.get("party_name"), "supplier_code": supplier.get("party_code"), "supplier_email": supplier.get("email")})
            try:
                items = self.repo.select("supply_purchase_order_items", eq={"purchase_order_id": rid}, order_by="created_at", limit=500)
            except Exception:
                items = []
            if items:
                supplier_parts: list[str] = []
                original_parts: list[str] = []
                descriptions: list[str] = []
                uoms: list[str] = []
                total_quantity = 0.0
                for item in items:
                    supplier_part = str(item.get("fsi_part_number_snapshot") or item.get("item_no") or "").strip()
                    original_part = str(item.get("original_part_number_snapshot") or "").strip()
                    description = str(item.get("item_description") or "").strip()
                    uom = str(item.get("uom") or "").strip().upper()
                    if supplier_part and supplier_part.casefold() not in {v.casefold() for v in supplier_parts}: supplier_parts.append(supplier_part)
                    if original_part and original_part.casefold() not in {v.casefold() for v in original_parts}: original_parts.append(original_part)
                    if description and description.casefold() not in {v.casefold() for v in descriptions}: descriptions.append(description)
                    if uom and uom.casefold() not in {v.casefold() for v in uoms}: uoms.append(uom)
                    try: total_quantity += float(item.get("quantity") or 0)
                    except (TypeError, ValueError): pass
                uom_text = ", ".join(uoms) if uoms else ""
                qty_value = _quantity_text(total_quantity)
                ctx.update({
                    "part_number": ", ".join(supplier_parts) or ", ".join(original_parts) or "-",
                    "fsi_part_number": ", ".join(supplier_parts) or "-",
                    "original_part_number": ", ".join(original_parts) or "-",
                    "part_description": "; ".join(descriptions) or "-",
                    "item_description": "; ".join(descriptions) or "-",
                    "quantity_value": qty_value,
                    "uom": uom_text or "-",
                    "quantity": f"{qty_value} {uom_text}".strip(),
                    "line_count": len(items),
                })
        elif table == "supply_po_confirmations":
            po_id = str(record.get("purchase_order_id") or "")
            po = self.repo.get("supply_purchase_orders", po_id) or {} if po_id else {}
            supplier_id = record.get("supplier_id") or po.get("supplier_id")
            supplier = self.repo.get("parties", str(supplier_id)) or {} if supplier_id else {}
            ctx.update({
                "document_no": po.get("po_number") or record.get("confirmation_reference") or "PO Confirmation",
                "document_type": "Supplier PO Confirmation",
                "due_date": po.get("delivery_date") or record.get("confirmation_date") or record.get("requested_at"),
                "confirmation_reference": record.get("confirmation_reference"),
                "confirmation_status": record.get("confirmation_status"),
                "confirmed_delivery_date": record.get("confirmed_delivery_date"),
                "supplier_id": str(supplier_id or ""),
                "supplier_name": supplier.get("party_name"),
                "supplier_code": supplier.get("party_code"),
                "supplier_email": supplier.get("email"),
                "purchase_order_id": po_id,
            })
        elif table == "osp_jobs":
            ctx.update({"document_no": record.get("osp_job_number"), "document_type": "OSP Job", "due_date": record.get("expected_return_date")})
        return ctx

    # ---------------------------------------------------------------- attachments
    def _storage_client(self):
        return get_session_client()

    def _persist_generated_pdf(self, file_name: str, content: bytes) -> dict | None:
        client = self._storage_client()
        if client is None or not content:
            return None
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(file_name or "QCMS_Report.pdf")).strip("_") or "QCMS_Report.pdf"
        path = f"{self.repo.tenant_id}/notification_exports/{uuid.uuid4().hex}/{safe_name}"
        client.storage.from_(self.bucket).upload(
            path,
            content,
            {"content-type": "application/pdf", "upsert": "false"},
        )
        return {"bucket": self.bucket, "object_path": path, "file_name": safe_name, "mime_type": "application/pdf", "generated": True}

    def _generated_report(self, related_table: str, related_id: str) -> tuple[str, bytes] | None:
        try:
            if related_table == "rmtc_approvals":
                from core.reporting import rmtc_record_pdf_bytes
                from core.rmtc_service import RMTCService
                service = RMTCService(); service.repo = self.repo
                payload = service.report_payload(related_id)
                number = (payload.get("rmtc") or {}).get("rmtc_number") or "RMTC"
                return f"{number}.pdf", rmtc_record_pdf_bytes(payload)
            if related_table == "inspection_reports":
                from core.inspection_service import InspectionService
                from core.reporting import dimensional_record_pdf_bytes
                service = InspectionService(); service.repo = self.repo
                payload = service.dimensional_report_payload(related_id)
                number = (payload.get("report") or {}).get("report_number") or "Dimensional_Report"
                return f"{number}.pdf", dimensional_record_pdf_bytes(payload)
            if related_table == "lab_tests":
                from core.inspection_service import InspectionService
                from core.reporting import metlab_record_pdf_bytes
                service = InspectionService(); service.repo = self.repo
                payload = service.metlab_report_payload(related_id)
                number = (payload.get("report") or {}).get("report_number") or "MetLAB_Report"
                return f"{number}.pdf", metlab_record_pdf_bytes(payload)
            if related_table == "supply_purchase_orders":
                from core.purchase_order_reporting import purchase_order_pdf_bytes
                from core.supply_chain_service import SupplyChainService
                service = SupplyChainService(self.repo)
                header = service.purchase_order(related_id) or {}
                items = service.purchase_order_items_for_print(related_id)
                if not header:
                    return None
                return f"{header.get('po_number') or 'Purchase_Order'}.pdf", purchase_order_pdf_bytes(header, items)
            if related_table == "supply_po_confirmations":
                from core.purchase_order_reporting import purchase_order_pdf_bytes
                from core.supply_chain_service import SupplyChainService
                confirmation = self.repo.get("supply_po_confirmations", related_id) or {}
                po_id = str(confirmation.get("purchase_order_id") or "")
                if not po_id:
                    return None
                service = SupplyChainService(self.repo)
                header = service.purchase_order(po_id) or {}
                items = service.purchase_order_items_for_print(po_id)
                if not header:
                    return None
                return f"{header.get('po_number') or 'Purchase_Order'}.pdf", purchase_order_pdf_bytes(header, items)
            if related_table == "inward_lots":
                from core.inward_service import InwardService
                from core.reporting import material_inward_record_pdf_bytes
                service = InwardService(); service.repo = self.repo
                payload = service.report_payload(related_id)
                number = (payload.get("inward") or {}).get("inward_number") or "Material_Inward"
                return f"{number}.pdf", material_inward_record_pdf_bytes(payload)
        except Exception:
            return None
        return None

    def _record_attachments(self, related_table: str, related_id: str) -> list[dict]:
        entity_type = _ENTITY_TYPES.get(related_table)
        if not entity_type:
            return []
        try:
            rows = self.repo.select(
                "document_attachments",
                eq={"entity_type": entity_type, "entity_id": related_id, "status": "ACTIVE"},
                order_by="created_at",
                limit=25,
            )
        except Exception:
            return []
        return [
            {
                "bucket": self.bucket,
                "object_path": row.get("object_path"),
                "file_name": row.get("file_name") or row.get("document_title") or "attachment",
                "mime_type": row.get("mime_type") or "application/octet-stream",
                "generated": False,
            }
            for row in rows if row.get("object_path")
        ]

    def attachment_manifest(
        self,
        related_table: str | None,
        related_id: str | None,
        *,
        include_generated_pdf: bool,
        include_record_attachments: bool,
    ) -> list[dict]:
        table = str(related_table or "").strip(); rid = str(related_id or "").strip()
        if not table or not rid:
            return []
        manifest: list[dict] = []
        if include_generated_pdf:
            generated = self._generated_report(table, rid)
            if generated:
                stored = self._persist_generated_pdf(generated[0], generated[1])
                if stored:
                    manifest.append(stored)
        if include_record_attachments:
            manifest.extend(self._record_attachments(table, rid))
        seen: set[tuple[str, str]] = set(); unique: list[dict] = []
        for row in manifest:
            key = (str(row.get("bucket") or ""), str(row.get("object_path") or ""))
            if key[1] and key not in seen:
                seen.add(key); unique.append(row)
        return unique


    def preview(
        self,
        event_key: str,
        *,
        context: Mapping[str, Any] | None = None,
        include_supplier: bool | None = None,
    ) -> dict[str, Any]:
        """Return the entry-page notification recipients/template before a record is saved.

        This is deliberately side-effect free: no outbox row is created and no email is
        sent.  Entry pages use it to show To / CC / next-stage details and require the
        user to confirm the notification before the business transaction is posted.
        """
        event = str(event_key or "").strip().upper()
        route = self.route(event) if event else None
        template = self.template((route or {}).get("template_key"), event) if event else None
        enriched = dict(context or {})
        enriched.setdefault("event_key", event)
        enriched.setdefault("next_stage", str((route or {}).get("next_stage") or enriched.get("next_task") or "Next QCMS stage"))
        enriched.setdefault("department", str((route or {}).get("department") or ""))
        email = name = ""
        if route:
            email, name = self.recipient_for_route(route)
        cc: list[str] = []
        if route and bool(route.get("department_cc")):
            cc.extend(self.department_emails(str(route.get("department") or ""), exclude=[email]))
        supplier_flag = bool((template or {}).get("include_supplier")) if include_supplier is None else bool(include_supplier)
        if route and include_supplier is None:
            supplier_flag = supplier_flag or bool(route.get("send_to_supplier"))
        if supplier_flag:
            supplier_id = str(enriched.get("supplier_id") or "").strip()
            if supplier_id:
                supplier = self.repo.get("parties", supplier_id) or {}
                cc.extend(self._party_notification_emails(supplier))
            elif str(enriched.get("supplier_email") or "").strip():
                cc.append(str(enriched.get("supplier_email") or "").strip())
        final_cc: list[str] = []
        for value in cc:
            value = str(value or "").strip()
            if value and value.casefold() != email.casefold() and value.casefold() not in {x.casefold() for x in final_cc}:
                final_cc.append(value)
        subject_template = (template or {}).get("subject_template") or (route or {}).get("subject_template")
        return {
            "event_key": event,
            "enabled": bool(route),
            "recipient_email": email,
            "recipient_name": name,
            "cc_emails": final_cc,
            "department": str((route or {}).get("department") or ""),
            "next_stage": enriched.get("next_stage"),
            "template_key": str((template or {}).get("template_key") or (route or {}).get("template_key") or event),
            "subject": _template_text(subject_template, enriched) if subject_template else f"QCMS · {event.replace('_', ' ').title()}",
            "include_supplier": supplier_flag,
        }

    # ---------------------------------------------------------------- enqueue/send
    def enqueue(
        self,
        event_key: str,
        *,
        subject: str | None = None,
        body_text: str | None = None,
        related_table: str | None = None,
        related_id: str | None = None,
        context: Mapping[str, Any] | None = None,
        recipient_email: str | None = None,
        recipient_name: str | None = None,
        cc_emails: Sequence[str] | None = None,
        template_key: str | None = None,
        include_generated_pdf: bool | None = None,
        include_record_attachments: bool | None = None,
        include_supplier: bool | None = None,
        dedupe_key: str | None = None,
        automatic: bool = False,
    ) -> dict | None:
        event = str(event_key or "").strip().upper()
        if not event:
            return None
        route = self.route(event)
        template = self.template(template_key or (route or {}).get("template_key"), event)
        if not route and not recipient_email:
            return None

        enriched = self._record_context(related_table, related_id)
        enriched.update(dict(context or {}))
        enriched.setdefault("event_key", event)
        enriched.setdefault("next_stage", str((route or {}).get("next_stage") or enriched.get("next_task") or "Next QCMS stage"))
        enriched.setdefault("department", str((route or {}).get("department") or ""))

        email, name = (recipient_email or "").strip(), (recipient_name or "").strip()
        if not email and route:
            email, name = self.recipient_for_route(route)
        if not email:
            return None

        template_subject = (template or {}).get("subject_template") or (route or {}).get("subject_template")
        template_body = (template or {}).get("body_template")
        final_subject = _template_text(template_subject, enriched) if template_subject else str(subject or f"QCMS · {event.replace('_', ' ').title()}").strip()
        final_body = _template_text(template_body, enriched) if template_body else str(body_text or "").strip()
        if not final_body:
            final_body = f"QCMS workflow notification\nDocument: {enriched.get('document_no') or '-'}\nNext stage: {enriched.get('next_stage') or '-'}"

        cc = [str(v).strip() for v in (cc_emails or []) if str(v).strip()]
        if route and bool(route.get("department_cc")):
            cc.extend(self.department_emails(str(route.get("department") or ""), exclude=[email]))
        supplier_flag = bool((template or {}).get("include_supplier")) if include_supplier is None else bool(include_supplier)
        if route and include_supplier is None:
            supplier_flag = supplier_flag or bool(route.get("send_to_supplier"))
        if supplier_flag:
            supplier_id = str(enriched.get("supplier_id") or "").strip()
            if supplier_id:
                supplier = self.repo.get("parties", supplier_id) or {}
                cc.extend(self._party_notification_emails(supplier))
            elif str(enriched.get("supplier_email") or "").strip():
                cc.append(str(enriched.get("supplier_email")).strip())
        # Do not duplicate the primary recipient in CC.
        final_cc: list[str] = []
        for value in cc:
            if value and value.casefold() != email.casefold() and value.casefold() not in {x.casefold() for x in final_cc}:
                final_cc.append(value)

        pdf_flag = bool((template or {}).get("include_generated_pdf", True)) if include_generated_pdf is None else bool(include_generated_pdf)
        docs_flag = bool((template or {}).get("include_record_attachments", True)) if include_record_attachments is None else bool(include_record_attachments)
        manifest = self.attachment_manifest(related_table, related_id, include_generated_pdf=pdf_flag, include_record_attachments=docs_flag)

        payload = {
            "event_key": event,
            "recipient_email": email,
            "recipient_name": name or None,
            "cc_emails": final_cc,
            "subject": final_subject,
            "body_text": final_body,
            "body_html": "<br>".join(str(final_body).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").splitlines()),
            "related_table": related_table or None,
            "related_id": related_id or None,
            "context": enriched,
            "template_key": str((template or {}).get("template_key") or template_key or event).upper(),
            "attachment_manifest": manifest,
            "dedupe_key": dedupe_key or None,
            "is_automatic": bool(automatic),
            "status": "PENDING",
        }
        try:
            return self.repo.insert("qcms_notification_outbox", payload)
        except Exception as exc:
            # A scheduled dedupe key may already exist. Treat that as a safe skip.
            if dedupe_key and "duplicate" in str(exc).casefold():
                return None
            raise

    @staticmethod
    def _invoke(outbox_ids: list[str]) -> dict:
        if not outbox_ids:
            return {"processed": 0}
        client = get_session_client()
        if client is None:
            return {"processed": 0, "message": "Preview mode"}
        response = client.functions.invoke(
            "qcms-send-email",
            invoke_options={"body": {"outbox_ids": outbox_ids}},
        )
        data = getattr(response, "data", response)
        if isinstance(data, bytes):
            import json
            return json.loads(data.decode("utf-8"))
        return dict(data or {}) if isinstance(data, Mapping) else {"result": data}

    def dispatch(self, rows: list[Mapping[str, Any]]) -> dict:
        ids = [str(row.get("id")) for row in rows if row and row.get("id")]
        try:
            return self._invoke(ids)
        except Exception as exc:
            return {"processed": 0, "error": str(exc)}

    def notify(self, event_key: str, **kwargs: Any) -> dict | None:
        try:
            row = self.enqueue(event_key, **kwargs)
            if row:
                self.dispatch([row])
            return row
        except Exception:
            # Email delivery must never break a business transaction.
            return None

    def retry_pending(self, *, limit: int = 50) -> dict:
        pending = self.repo.select("qcms_notification_outbox", eq={"status": "PENDING"}, order_by="created_at", limit=limit)
        failed = self.repo.select("qcms_notification_outbox", eq={"status": "FAILED"}, order_by="created_at", limit=limit)
        rows = (pending + failed)[:limit]
        return self.dispatch(rows)
