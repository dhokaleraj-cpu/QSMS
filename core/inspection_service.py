from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from core.database import get_session_client
from core.attachments import AttachmentService
from core.dimensional_import import parse_dimensional_workbook_bytes
from core.inspection_queue import build_inspection_queue, pending_rows
from core.repository import Repository

FINAL_DISPOSITIONS = ("ON_HOLD", "ACCEPTED", "ACCEPTED_UNDER_RESERVE", "REJECTED")
RESULT_OPTIONS = ("PASS", "FAIL", "NOT_EVALUATED", "NOT_APPLICABLE")


def _text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _number(value: Any) -> float | None:
    if value is None or value == "" or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _attribute_pass(value: Any) -> bool:
    text = _text(value).upper()
    if not text:
        return False
    accepted = ("OK", "PASS", "ACCEPTED", "FOUND OK", "YES", "CONFORM", "SATISFACTORY", "FOR REF")
    return any(token in text for token in accepted)


class InspectionService:
    def __init__(self) -> None:
        self.repo = Repository()

    def parts(self) -> list[dict]:
        return self.repo.select("parts", eq={"status": "ACTIVE"}, order_by="part_number", limit=3000)

    def processes(self) -> list[dict]:
        return self.repo.select("processes", eq={"status": "ACTIVE"}, order_by="process_name", limit=1000)

    def stages(self) -> list[dict]:
        return self.repo.select("inspection_stages", eq={"status": "ACTIVE"}, order_by="sequence_no", limit=1000)

    def parties(self) -> list[dict]:
        return self.repo.select("parties", eq={"status": "ACTIVE"}, order_by="party_name", limit=3000)

    def material_grades(self) -> list[dict]:
        return self.repo.select("material_grades", eq={"status": "ACTIVE"}, order_by="grade_code", limit=1000)

    def employees(self, authority: str | None = None) -> list[dict]:
        rows = self.repo.select("employees", eq={"status": "ACTIVE"}, order_by="first_name", limit=3000)
        if authority:
            filtered = [row for row in rows if authority in (row.get("approval_authorities") or [])]
            return filtered or rows
        return rows

    def inward_lots(self) -> list[dict]:
        rows = self.repo.select("inward_lots", order_by="created_at", desc=True, limit=4000)
        return [
            row for row in rows
            if str(row.get("receipt_disposition") or "") in ("ACCEPTED", "ACCEPTED_UNDER_RESERVE")
            and str(row.get("status") or "") != "REJECTED"
        ]

    def inspection_queue(self) -> list[dict]:
        return build_inspection_queue(
            self.inward_lots(),
            self.dimensional_reports(),
            self.metlab_reports(),
        )

    def pending_inward_lots(self, report_type: str) -> list[dict]:
        return pending_rows(self.inspection_queue(), report_type)

    def plans(
        self,
        layout_type: str | None = None,
        part_id: str | None = None,
        approved_only: bool = False,
        process_id: str | None = None,
        stage_id: str | None = None,
        inward_type: str | None = None,
    ) -> list[dict]:
        eq: dict[str, Any] = {}
        if layout_type:
            eq["layout_type"] = layout_type
        if part_id:
            eq["part_id"] = part_id
        if approved_only:
            eq["status"] = "APPROVED"
        if process_id:
            eq["process_id"] = process_id
        if stage_id:
            eq["inspection_stage_id"] = stage_id
        if inward_type:
            eq["inward_type"] = inward_type
        return self.repo.select("inspection_plans", eq=eq, order_by="plan_number", limit=3000)

    def ranked_plans(
        self,
        layout_type: str,
        part_id: str,
        process_id: str | None = None,
        stage_id: str | None = None,
        inward_type: str | None = None,
    ) -> list[dict]:
        """Return approved plans with exact part/process/stage match first."""
        plans = self.plans(layout_type, part_id, approved_only=True, inward_type=inward_type)

        def score(row: dict) -> tuple[int, str, str]:
            process_match = not process_id or str(row.get("process_id") or "") == str(process_id)
            stage_match = not stage_id or str(row.get("inspection_stage_id") or "") == str(stage_id)
            exact = int(process_match) + int(stage_match)
            effective = str(row.get("effective_date") or "")
            revision = str(row.get("revision") or "")
            return exact, effective, revision

        return sorted(plans, key=score, reverse=True)

    def get_plan(self, plan_id: str | None) -> dict | None:
        return self.repo.get("inspection_plans", plan_id)

    def plan_characteristics(self, plan_id: str) -> list[dict]:
        return self.repo.select(
            "inspection_plan_characteristics",
            eq={"inspection_plan_id": plan_id, "status": "ACTIVE"},
            order_by="sequence_no",
            limit=1000,
        )

    def osp_parameter_characteristics(
        self,
        part_id: str,
        process_id: str,
        layout_type: str,
    ) -> tuple[dict | None, list[dict]]:
        """Return the active Part + OSP Process group and its layout-ready parameters."""
        groups = self.repo.select(
            "part_process_specifications",
            eq={
                "part_id": part_id,
                "process_id": process_id,
                "inward_type": "OSP_PROCESS",
                "status": "ACTIVE",
            },
            order_by="sequence_no",
            limit=20,
        )
        group = groups[0] if groups else None
        if not group:
            return None, []
        rows = self.repo.select(
            "part_process_parameter_specifications",
            eq={
                "process_specification_id": str(group["id"]),
                "inspection_type": layout_type,
                "status": "ACTIVE",
            },
            order_by="sequence_no",
            limit=1000,
        )
        characteristics = [
            {
                "sequence_no": row.get("sequence_no"),
                "characteristic_no": str(index),
                "characteristic": row.get("parameter_name"),
                "specification": row.get("specification_text"),
                "lower_spec": row.get("minimum_spec"),
                "upper_spec": row.get("maximum_spec"),
                "unit": row.get("unit"),
                "characteristic_type": row.get("characteristic_type") or "VARIABLE",
                "checking_method": row.get("checking_method"),
                "checking_aid_text": row.get("checking_method"),
                "sample_size": row.get("sample_size") or group.get("sample_quantity") or 1,
                "is_mandatory": bool(row.get("is_mandatory", True)),
                "allow_na": bool(row.get("allow_na", False)),
                "report_section": layout_type,
                "status": row.get("status") or "ACTIVE",
                "layout_metadata": {
                    "source": "PART_MASTER_OSP_PROCESS_GROUP",
                    "process_specification_id": str(group["id"]),
                    "parameter_specification_id": str(row.get("id") or ""),
                    "drawing_number": group.get("drawing_number"),
                    "drawing_revision": group.get("drawing_revision"),
                },
            }
            for index, row in enumerate(rows, start=1)
        ]
        return group, characteristics

    def save_plan(self, payload: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], plan_id: str | None = None) -> dict:
        plan = self.repo.update("inspection_plans", plan_id, payload) if plan_id else self.repo.insert("inspection_plans", payload)
        pid = str(plan["id"])
        existing = {
            int(row.get("sequence_no") or 0): row
            for row in self.repo.select("inspection_plan_characteristics", eq={"inspection_plan_id": pid}, limit=2000)
        }
        prepared: list[dict] = []
        for position, source in enumerate(rows, start=1):
            characteristic = _text(source.get("characteristic") or source.get("Parameter"))
            if not characteristic:
                continue
            sequence = int(source.get("sequence_no") or source.get("Sequence") or position)
            payload_row = {
                "id": str((existing.get(sequence) or {}).get("id") or source.get("id") or "") or None,
                "inspection_plan_id": pid,
                "sequence_no": sequence,
                "characteristic_no": _text(source.get("characteristic_no") or source.get("Characteristic No")) or None,
                "characteristic": characteristic,
                "specification": _text(source.get("specification") or source.get("Specification")) or None,
                "lower_spec": _number(source.get("lower_spec") if "lower_spec" in source else source.get("Minimum")),
                "upper_spec": _number(source.get("upper_spec") if "upper_spec" in source else source.get("Maximum")),
                "unit": _text(source.get("unit") or source.get("Unit")) or None,
                "characteristic_type": _text(source.get("characteristic_type") or source.get("Type") or "VARIABLE").upper(),
                "special_class": _text(source.get("special_class") or source.get("Special Class")) or None,
                "checking_method": _text(source.get("checking_method") or source.get("Checking Method")) or None,
                "checking_aid_text": _text(source.get("checking_aid_text") or source.get("Checking Aid")) or None,
                "sample_size": int(source.get("sample_size") or source.get("Sample Size") or payload.get("default_sample_size") or 1),
                "frequency": _text(source.get("frequency") or source.get("Frequency")) or None,
                "reaction_plan": _text(source.get("reaction_plan") or source.get("Reaction Plan")) or None,
                "report_section": _text(source.get("report_section") or source.get("Section") or payload.get("layout_type")) or None,
                "is_mandatory": bool(source.get("is_mandatory", source.get("Mandatory", True))),
                "allow_na": bool(source.get("allow_na", source.get("Allow NA", False))),
                "decimal_places": int(source.get("decimal_places") or source.get("Decimal Places") or 3),
                "source_row": int(source.get("source_row") or source.get("Source Row") or 0) or None,
                "layout_metadata": source.get("layout_metadata") or {},
                "status": _text(source.get("status") or source.get("Status") or "ACTIVE").upper(),
            }
            if not payload_row["id"]:
                payload_row.pop("id")
            prepared.append(payload_row)
        self.repo.bulk_upsert("inspection_plan_characteristics", prepared, on_conflict="id")
        return plan

    def parse_dimensional_workbook(self, uploaded: Any) -> dict[str, Any]:
        content = uploaded.getvalue() if hasattr(uploaded, "getvalue") else uploaded.read()
        return parse_dimensional_workbook_bytes(content, getattr(uploaded, "name", "Dimensional Report.xlsx"))

    def next_number(self, layout_type: str) -> str:
        code = "DIMENSIONAL_REPORT" if layout_type == "DIMENSIONAL" else "METLAB_REPORT"
        return str(self.repo.rpc("qsms_next_document_number", {"p_sequence_code": code}) or "")

    def dimensional_reports(self) -> list[dict]:
        return self.repo.select("inspection_reports", eq={"report_type": "DIMENSIONAL"}, order_by="created_at", desc=True, limit=4000)

    def get_dimensional(self, report_id: str | None) -> dict | None:
        return self.repo.get("inspection_reports", report_id)

    def dimensional_results(self, report_id: str) -> list[dict]:
        return self.repo.select("inspection_results", eq={"inspection_report_id": report_id}, order_by="sequence_no", limit=2000)

    def save_dimensional(self, payload: Mapping[str, Any], result_rows: Sequence[Mapping[str, Any]], report_id: str | None = None) -> dict:
        report = self.repo.update("inspection_reports", report_id, payload) if report_id else self.repo.insert("inspection_reports", payload)
        rid = str(report["id"])
        existing = {
            str(row.get("inspection_plan_characteristic_id") or row.get("sequence_no") or ""): row
            for row in self.dimensional_results(rid)
        }
        prepared: list[dict] = []
        for position, row in enumerate(result_rows, start=1):
            key = str(row.get("inspection_plan_characteristic_id") or row.get("sequence_no") or position)
            payload_row = {
                "id": str((existing.get(key) or {}).get("id") or "") or None,
                "inspection_report_id": rid,
                "inspection_plan_characteristic_id": row.get("inspection_plan_characteristic_id") or None,
                "sequence_no": int(row.get("sequence_no") or position),
                "characteristic_no": _text(row.get("characteristic_no")) or None,
                "characteristic": _text(row.get("characteristic")),
                "specification": _text(row.get("specification")) or None,
                "lower_spec": _number(row.get("lower_spec")),
                "upper_spec": _number(row.get("upper_spec")),
                "unit": _text(row.get("unit")) or None,
                "checking_aid": _text(row.get("checking_aid")) or None,
                "observations": list(row.get("observations") or []),
                "attribute_result": _text(row.get("attribute_result")) or None,
                "result": _text(row.get("result") or "NOT_EVALUATED").upper(),
                "remarks": _text(row.get("remarks")) or None,
                "applicability": _text(row.get("applicability") or "APPLICABLE").upper(),
                "report_section": _text(row.get("report_section") or payload.get("layout_type_name") or "DIMENSIONAL") or None,
                "observation_count": max(1, len(list(row.get("observations") or []))),
            }
            if not payload_row["id"]:
                payload_row.pop("id")
            prepared.append(payload_row)
        self.repo.bulk_upsert("inspection_results", prepared, on_conflict="id")
        return report

    def metlab_reports(self) -> list[dict]:
        return self.repo.select("lab_tests", eq={"test_type": "METLAB"}, order_by="created_at", desc=True, limit=4000)

    def get_metlab(self, report_id: str | None) -> dict | None:
        return self.repo.get("lab_tests", report_id)

    def rmtc_material_snapshot(self, inward: Mapping[str, Any]) -> dict[str, Any]:
        rmtc_id = str(inward.get("rmtc_approval_id") or "")
        part_id = str(inward.get("part_id") or "")
        rmtc = self.repo.get("rmtc_approvals", rmtc_id) or {}
        part = self.repo.get("parts", part_id) or {}
        chemistry = self.repo.select("rmtc_chemistry_results", eq={"rmtc_approval_id": rmtc_id, "part_id": part_id}, order_by="element", limit=200)
        jominy = self.repo.select("rmtc_jominy_results", eq={"rmtc_approval_id": rmtc_id, "part_id": part_id}, order_by="distance_mm", limit=200)
        jominy_requirements = self.repo.select("part_jominy_requirements", eq={"part_id": part_id, "status": "ACTIVE"}, order_by="sequence_no", limit=200)
        jominy_band = {str(row.get("jominy_distance_id")): row for row in jominy_requirements}
        jominy = [{**row, "minimum_hrc": (jominy_band.get(str(row.get("jominy_distance_id"))) or {}).get("minimum_hrc"), "maximum_hrc": (jominy_band.get(str(row.get("jominy_distance_id"))) or {}).get("maximum_hrc")} for row in jominy]
        requirements = self.repo.select("rmtc_requirement_results", eq={"rmtc_approval_id": rmtc_id, "part_id": part_id}, order_by="sequence_no", limit=300)
        grade = self.repo.get("material_grades", str(part.get("material_grade_id") or "")) or {}
        supplier = self.repo.get("parties", str(inward.get("supplier_id") or "")) or {}
        steel_mill = self.repo.get("parties", str(rmtc.get("steel_mill_id") or "")) or {}
        return {"rmtc": rmtc, "part": part, "grade": grade, "supplier": supplier, "steel_mill": steel_mill, "chemistry": chemistry, "jominy": jominy, "requirements": requirements, "chemistry_rows": chemistry, "jominy_rows": jominy, "requirement_rows": requirements}

    def save_metlab(self, payload: Mapping[str, Any], results: Mapping[str, Sequence[Mapping[str, Any]]] | Sequence[Mapping[str, Any]], report_id: str | None = None) -> dict:
        full_payload = dict(payload)
        if isinstance(results, Mapping):
            # Keep stable RMTC-style section keys for database validation and reporting.
            full_payload["results"] = {
                "rows": [dict(row) for row in results.get("rows", [])],
                "chemistry_rows": [dict(row) for row in results.get("chemistry_rows", [])],
                "jominy_rows": [dict(row) for row in results.get("jominy_rows", [])],
                "requirement_rows": [dict(row) for row in results.get("requirement_rows", [])],
            }
        else:
            full_payload["results"] = {"rows": [dict(row) for row in results], "chemistry_rows": [], "jominy_rows": [], "requirement_rows": []}
        return self.repo.update("lab_tests", report_id, full_payload) if report_id else self.repo.insert("lab_tests", full_payload)

    def _report_employees(self, record: Mapping[str, Any]) -> dict[str, dict]:
        ids = [str(value) for value in (
            record.get("prepared_by_employee_id"), record.get("validated_by_employee_id"), record.get("approved_by_employee_id")
        ) if value]
        rows = self.repo.select("employees", in_={"id": ids}, limit=20) if ids else []
        return {str(row.get("id")): row for row in rows}

    def _report_microstructure_images(self, entity_type: str, entity_id: str, record: Mapping[str, Any], slots: int = 4) -> list[dict]:
        images: list[dict] = []
        try:
            service = AttachmentService(self.repo)
            attachments = service.list_active(entity_type, entity_id)
            by_type = {str(row.get("document_type") or ""): row for row in attachments}
            for slot in range(1, slots + 1):
                attachment = by_type.get(f"MICROSTRUCTURE_{slot}")
                data = b""
                if attachment:
                    try:
                        data = service.download(attachment)
                    except Exception:
                        data = b""
                images.append({
                    "slot": slot,
                    "caption": record.get(f"microstructure_caption_{slot}") or f"Microstructure Photo {slot}",
                    "bytes": data,
                    "file_name": (attachment or {}).get("file_name"),
                })
        except Exception:
            images = [{"slot": slot, "caption": record.get(f"microstructure_caption_{slot}") or f"Microstructure Photo {slot}", "bytes": b""} for slot in range(1, slots + 1)]
        return images

    def metlab_report_payload(self, report_id: str) -> dict:
        record = self.get_metlab(report_id) or {}
        if not record:
            raise ValueError("MetLAB report not found.")
        part = self.repo.get("parts", str(record.get("part_id") or "")) or {}
        inward = self.repo.get("inward_lots", str(record.get("inward_lot_id") or "")) or {}
        supplier = self.repo.get("parties", str(record.get("supplier_id") or inward.get("supplier_id") or "")) or {}
        steel_mill = self.repo.get("parties", str(record.get("steel_mill_id") or "")) or {}
        grade = self.repo.get("material_grades", str(record.get("material_grade_id") or part.get("material_grade_id") or "")) or {}
        process = self.repo.get("processes", str(record.get("process_id") or "")) or {}
        stage = self.repo.get("inspection_stages", str(record.get("inspection_stage_id") or "")) or {}
        osp_rows = self.repo.select("v_qsms_osp_register", eq={"id": str(record.get("osp_job_id"))}, limit=1) if record.get("osp_job_id") else []
        osp_job = osp_rows[0] if osp_rows else {}
        return {
            "record": record, "part": part, "inward": inward, "supplier": supplier, "steel_mill": steel_mill,
            "material_grade": grade, "process": process, "stage": stage, "osp_job": osp_job,
            "employees": self._report_employees(record),
            "results": dict(record.get("results") or {}),
            "microstructure_images": self._report_microstructure_images("METLAB_REPORT", report_id, record, 4),
        }

    def dimensional_report_payload(self, report_id: str) -> dict:
        record = self.get_dimensional(report_id) or {}
        if not record:
            raise ValueError("Dimensional report not found.")
        part = self.repo.get("parts", str(record.get("part_id") or "")) or {}
        inward = self.repo.get("inward_lots", str(record.get("inward_lot_id") or "")) or {}
        supplier = self.repo.get("parties", str(record.get("supplier_id") or inward.get("supplier_id") or "")) or {}
        process = self.repo.get("processes", str(record.get("process_id") or "")) or {}
        stage = self.repo.get("inspection_stages", str(record.get("inspection_stage_id") or "")) or {}
        osp_rows = self.repo.select("v_qsms_osp_register", eq={"id": str(record.get("osp_job_id"))}, limit=1) if record.get("osp_job_id") else []
        osp_job = osp_rows[0] if osp_rows else {}
        return {
            "record": record, "part": part, "inward": inward, "supplier": supplier, "process": process, "stage": stage,
            "osp_job": osp_job, "employees": self._report_employees(record), "results": self.dimensional_results(report_id),
        }

    def finalize_dimensional(self, report_id: str, disposition: str, reason: str, validator: str, approver: str) -> dict:
        return self.repo.rpc("qsms_finalize_dimensional_report", {
            "p_report_id": report_id,
            "p_disposition": disposition,
            "p_reason": reason or None,
            "p_validated_by_employee_id": validator,
            "p_approved_by_employee_id": approver,
        }) or {}

    def finalize_metlab(self, report_id: str, disposition: str, reason: str, validator: str, approver: str) -> dict:
        return self.repo.rpc("qsms_finalize_metlab_report", {
            "p_report_id": report_id,
            "p_disposition": disposition,
            "p_reason": reason or None,
            "p_validated_by_employee_id": validator,
            "p_approved_by_employee_id": approver,
        }) or {}

    @staticmethod
    def evaluate_characteristic(row: Mapping[str, Any], observations: Sequence[Any], not_applicable: bool = False) -> str:
        if not_applicable:
            return "NOT_APPLICABLE"
        values = [value for value in observations if _text(value)]
        if not values:
            return "NOT_EVALUATED"
        characteristic_type = _text(row.get("characteristic_type") or "VARIABLE").upper()
        if characteristic_type == "ATTRIBUTE":
            return "PASS" if all(_attribute_pass(value) for value in values) else "FAIL"
        lower = _number(row.get("lower_spec"))
        upper = _number(row.get("upper_spec"))
        numeric = [_number(value) for value in values]
        if any(value is None for value in numeric):
            return "FAIL"
        for value in numeric:
            if lower is not None and float(value) < lower:
                return "FAIL"
            if upper is not None and float(value) > upper:
                return "FAIL"
        return "PASS"

    def upload_attachment(self, entity_type: str, entity_id: str, document_type: str, file: Any, table: str, field: str) -> str:
        client = get_session_client()
        if client is None:
            raise RuntimeError("Live Supabase session is required for attachment upload.")
        ext = Path(file.name).suffix.lower() or ".bin"
        content = file.getvalue()
        folder = entity_type.lower().replace("_", "-")
        path = f"{self.repo.tenant_id}/{folder}/{entity_id}/{document_type.lower()}_{hashlib.sha1(file.name.encode()).hexdigest()[:8]}{ext}"
        client.storage.from_("quality-documents").upload(path, content, {"content-type": file.type or "application/octet-stream", "upsert": "true"})
        attachment = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "document_type": document_type,
            "file_name": file.name,
            "object_path": path,
            "mime_type": file.type,
            "size_bytes": len(content),
            "checksum": hashlib.sha256(content).hexdigest(),
            "status": "ACTIVE",
        }
        existing = self.repo.find_one("document_attachments", eq={"entity_type": entity_type, "entity_id": entity_id, "document_type": document_type})
        if existing:
            self.repo.update("document_attachments", str(existing["id"]), attachment)
        else:
            self.repo.insert("document_attachments", attachment)
        self.repo.update(table, entity_id, {field: path})
        return path
