from __future__ import annotations

from typing import Any, Mapping

from core.repository import Repository


FINAL_ACCEPTED = {"ACCEPTED", "ACCEPTED_UNDER_RESERVE"}


class OSPService:
    """Live Supabase service for OSP genealogy, process groups and quality release."""

    def __init__(self) -> None:
        self.repo = Repository()

    def register(self) -> list[dict]:
        return self.repo.select("v_qsms_osp_register", order_by="created_at", desc=True, limit=5000)

    def dispatch_candidates(self) -> list[dict]:
        rows = self.repo.select("v_qsms_osp_dispatch_candidates", order_by="inward_date", desc=True, limit=5000)
        return [row for row in rows if float(row.get("osp_available_quantity_pcs") or 0) > 0]

    def vendors(self) -> list[dict]:
        rows = self.repo.select(
            "parties", contains={"party_types": ["OSP_VENDOR"]}, eq={"status": "ACTIVE"},
            order_by="party_name", limit=2000,
        )
        return [row for row in rows if str(row.get("approval_status") or "APPROVED") == "APPROVED"]

    def specifications(self, part_id: str | None = None, process_id: str | None = None) -> list[dict]:
        eq: dict[str, Any] = {"inward_type": "OSP_PROCESS", "status": "ACTIVE"}
        if part_id:
            eq["part_id"] = part_id
        if process_id:
            eq["process_id"] = process_id
        return self.repo.select("part_process_specifications", eq=eq, order_by="sequence_no", limit=2000)

    def get_specification(self, specification_id: str | None) -> dict | None:
        return self.repo.get("part_process_specifications", specification_id)

    def parameter_specs(
        self,
        process_specification_id: str | None = None,
        *,
        part_id: str | None = None,
        process_id: str | None = None,
        inspection_type: str | None = None,
        active_only: bool = False,
    ) -> list[dict]:
        eq: dict[str, Any] = {}
        if process_specification_id:
            eq["process_specification_id"] = process_specification_id
        if part_id:
            eq["part_id"] = part_id
        if process_id:
            eq["process_id"] = process_id
        if inspection_type:
            eq["inspection_type"] = inspection_type
        if active_only:
            eq["status"] = "ACTIVE"
        return self.repo.select(
            "part_process_parameter_specifications", eq=eq,
            order_by="sequence_no", limit=3000,
        )

    def parameter_options(self, process_id: str, inspection_type: str | None = None) -> list[dict]:
        eq: dict[str, Any] = {"process_id": process_id}
        if inspection_type:
            eq["inspection_type"] = inspection_type
        return self.repo.select("v_qsms_osp_parameter_options", eq=eq, order_by="parameter_name", limit=2000)

    def generated_layouts(self, process_specification_id: str) -> list[dict]:
        return self.repo.select(
            "inspection_plans",
            eq={"source_process_specification_id": process_specification_id},
            order_by="layout_type",
            limit=100,
        )

    def generate_layouts(self, process_specification_id: str) -> dict:
        return self.repo.rpc(
            "qsms_generate_osp_inspection_layouts",
            {"p_process_specification_id": process_specification_id},
        ) or {}

    def processes(self) -> dict[str, dict]:
        rows = self.repo.select(
            "processes", eq={"status": "ACTIVE", "process_type": "OUTSOURCED"},
            order_by="process_name", limit=2000,
        )
        return {str(row["id"]): row for row in rows}

    def create_dispatch(self, payload: Mapping[str, Any]) -> dict:
        return self.repo.rpc("qsms_create_osp_dispatch", {
            "p_inward_lot_id": payload["inward_lot_id"],
            "p_vendor_id": payload["vendor_id"],
            "p_process_id": payload["process_id"],
            "p_process_specification_id": payload["process_specification_id"],
            "p_dispatch_date": payload["dispatch_date"],
            "p_dispatch_challan": payload["dispatch_challan"],
            "p_quantity_dispatched": payload["quantity_dispatched"],
            "p_expected_return_date": payload.get("expected_return_date"),
            "p_sample_quantity": payload.get("sample_quantity", 1),
            "p_remarks": payload.get("remarks"),
        }) or {}

    def record_sample(self, payload: Mapping[str, Any]) -> dict:
        return self.repo.rpc("qsms_record_osp_sample", {
            "p_osp_job_id": payload["osp_job_id"],
            "p_sample_received_date": payload["sample_received_date"],
            "p_sample_reference": payload["sample_reference"],
            "p_vendor_batch_number": payload["vendor_batch_number"],
            "p_sample_quantity": payload.get("sample_quantity", 1),
        }) or {}

    def receive_batch(self, payload: Mapping[str, Any]) -> dict:
        return self.repo.rpc("qsms_receive_osp_batch", {
            "p_osp_job_id": payload["osp_job_id"],
            "p_receipt_date": payload["receipt_date"],
            "p_receipt_challan": payload["receipt_challan"],
            "p_vendor_invoice_number": payload["vendor_invoice_number"],
            "p_vendor_invoice_date": payload["vendor_invoice_date"],
            "p_tc_number": payload["tc_number"],
            "p_tc_date": payload["tc_date"],
            "p_vendor_batch_number": payload["vendor_batch_number"],
            "p_quantity_received": payload["quantity_received"],
            "p_remarks": payload.get("remarks"),
        }) or {}

    def jobs_for_sample_receipt(self) -> list[dict]:
        return [
            row for row in self.register()
            if float(row.get("quantity_received") or 0) <= 0
            and str(row.get("status")) not in {"REJECTED", "CANCELLED"}
        ]

    def jobs_for_full_receipt(self) -> list[dict]:
        return [
            row for row in self.register()
            if str(row.get("sample_gate_status")) in FINAL_ACCEPTED
            and float(row.get("quantity_received") or 0) <= 0
            and str(row.get("status")) not in {"REJECTED", "CANCELLED"}
        ]

    def jobs_for_inspection(self, scope: str, report_type: str) -> list[dict]:
        disposition_key = (
            "sample_dimensional_disposition" if scope == "OSP_SAMPLE" and report_type == "DIMENSIONAL" else
            "sample_metlab_disposition" if scope == "OSP_SAMPLE" else
            "receipt_dimensional_disposition" if report_type == "DIMENSIONAL" else
            "receipt_metlab_disposition"
        )
        rows: list[dict] = []
        for row in self.register():
            ready = bool(row.get("sample_received_date")) if scope == "OSP_SAMPLE" else float(row.get("quantity_received") or 0) > 0
            pending = str(row.get(disposition_key) or "PENDING") not in {"ACCEPTED", "ACCEPTED_UNDER_RESERVE", "REJECTED"}
            if ready and pending and str(row.get("status")) != "CANCELLED":
                rows.append(row)
        return rows
