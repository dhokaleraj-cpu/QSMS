from __future__ import annotations

from typing import Any, Mapping

from core.repository import Repository
from core.record_audit import annotate_transaction_rows


FINAL_ACCEPTED = {"ACCEPTED", "ACCEPTED_UNDER_RESERVE"}


class OSPService:
    """Live Supabase service for OSP genealogy, process groups and quality release."""

    def __init__(self) -> None:
        self.repo = Repository()

    def _enrich_part_identity(self, rows: list[dict]) -> list[dict]:
        part_ids = sorted({str(row.get("part_id")) for row in rows if row.get("part_id")})
        part_rows = self.repo.select("parts", in_={"id": part_ids}, limit=max(len(part_ids), 1) + 10) if part_ids else []
        parts = {str(row.get("id")): row for row in part_rows}
        enriched: list[dict] = []
        for row in rows:
            item = dict(row)
            part = parts.get(str(item.get("part_id"))) or {}
            item["fsi_part_number"] = part.get("fsi_part_number")
            item["part_number"] = item.get("part_number") or part.get("part_number")
            item["part_name"] = item.get("part_name") or part.get("part_name")
            enriched.append(item)
        return enriched

    def register(self) -> list[dict]:
        rows = self._enrich_part_identity(self.repo.select("v_qsms_osp_register", order_by="created_at", desc=True, limit=5000))
        ids = [str(row.get("id") or "") for row in rows if row.get("id")]
        raw = self.repo.select("osp_jobs", in_={"id": ids}, limit=max(len(ids), 1) + 10) if ids else []
        raw_map = {str(row.get("id")): row for row in raw}
        merged=[]
        for row in rows:
            item=dict(row)
            source=raw_map.get(str(item.get("id"))) or {}
            for key in ("created_by","updated_by","created_at","updated_at"):
                item[key]=source.get(key) or item.get(key)
            merged.append(item)
        return annotate_transaction_rows(self.repo, merged)

    def dispatch_candidates(self) -> list[dict]:
        inward_rows = self._enrich_part_identity(self.repo.select("v_qsms_osp_dispatch_candidates", order_by="inward_date", desc=True, limit=5000))
        candidates: list[dict] = []
        for row in inward_rows:
            if float(row.get("osp_available_quantity_pcs") or 0) <= 0:
                continue
            item = dict(row)
            item["source_type"] = "INWARD"
            item["candidate_key"] = f"INWARD:{row.get('inward_lot_id')}"
            candidates.append(item)

        opening = self.repo.select("supply_opening_stock", eq={"status": "ACTIVE"}, order_by="created_at", desc=True, limit=5000)
        eligible_stages = {"MACHINING", "OSP_READY", "FINAL_INSPECTION", "FINISHED_GOODS"}
        opening_rows: list[dict] = []
        for stock in opening:
            if str(stock.get("stage") or "").upper() not in eligible_stages:
                continue
            available = float(stock.get("available_quantity_pcs") or 0)
            if available <= 0:
                continue
            opening_rows.append({
                "source_type": "OPENING_STOCK",
                "candidate_key": f"OPEN:{stock.get('id')}",
                "opening_stock_id": stock.get("id"),
                "inward_lot_id": None,
                "inward_number": stock.get("lot_reference") or "Opening Stock",
                "inward_date": str(stock.get("created_at") or "")[:10],
                "part_id": stock.get("part_id"),
                "heat_number": stock.get("heat_number") or "OPENING",
                "heat_code": stock.get("heat_code") or "OPENING",
                "quality_disposition": "OPENING_STOCK",
                "status": stock.get("status"),
                "supply_chain_stage": stock.get("stage"),
                "osp_available_quantity_pcs": available,
            })
        candidates.extend(self._enrich_part_identity(opening_rows))
        return candidates

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
        common = {
            "p_vendor_id": payload["vendor_id"],
            "p_process_id": payload["process_id"],
            "p_process_specification_id": payload["process_specification_id"],
            "p_dispatch_date": payload["dispatch_date"],
            "p_dispatch_challan": payload["dispatch_challan"],
            "p_quantity_dispatched": payload["quantity_dispatched"],
            "p_expected_return_date": payload.get("expected_return_date"),
            "p_sample_quantity": payload.get("sample_quantity", 1),
            "p_remarks": payload.get("remarks"),
        }
        opening_stock_id = str(payload.get("opening_stock_id") or "").strip()
        if opening_stock_id:
            return self.repo.rpc("qsms_create_osp_dispatch_from_opening_stock", {"p_opening_stock_id": opening_stock_id, **common}) or {}
        return self.repo.rpc("qsms_create_osp_dispatch", {"p_inward_lot_id": payload["inward_lot_id"], **common}) or {}


    def update_material_out(self, payload: Mapping[str, Any]) -> dict:
        return self.repo.rpc("qcms_update_osp_material_out", {
            "p_osp_job_id": payload["osp_job_id"],
            "p_dispatch_date": payload["dispatch_date"],
            "p_dispatch_challan": payload["dispatch_challan"],
            "p_quantity_dispatched": payload["quantity_dispatched"],
            "p_expected_return_date": payload.get("expected_return_date"),
            "p_remarks": payload.get("remarks"),
        }) or {}

    def clear_sample(self, osp_job_id: str) -> dict:
        return self.repo.rpc("qcms_clear_osp_sample", {"p_osp_job_id": osp_job_id}) or {}

    def update_receipt(self, payload: Mapping[str, Any]) -> dict:
        return self.repo.rpc("qcms_update_osp_receipt", {
            "p_receipt_id": payload["receipt_id"],
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
            and float(row.get("quantity_received") or 0) < float(row.get("quantity_dispatched") or 0)
            and str(row.get("status")) not in {"REJECTED", "CANCELLED"}
        ]

    def receipts(self, osp_job_id: str) -> list[dict]:
        return self.repo.select("osp_receipts", eq={"osp_job_id": osp_job_id}, order_by="created_at", desc=True, limit=500)

    def delete_receipt(self, receipt_id: str) -> dict:
        return self.repo.rpc("qcms_delete_osp_receipt", {"p_receipt_id": receipt_id}) or {}

    def delete_transaction(self, osp_job_id: str) -> dict:
        return self.repo.rpc("qcms_delete_osp_transaction", {"p_osp_job_id": osp_job_id}) or {}

    def jobs_for_inspection(self, scope: str, report_type: str) -> list[dict]:
        disposition_key = (
            "sample_dimensional_disposition" if scope == "OSP_SAMPLE" and report_type == "DIMENSIONAL" else
            "sample_metlab_disposition" if scope == "OSP_SAMPLE" else
            "receipt_dimensional_disposition" if report_type == "DIMENSIONAL" else
            "receipt_metlab_disposition"
        )
        rows: list[dict] = []
        requirement_flag = "dimensional_required" if report_type == "DIMENSIONAL" else "metlab_required"
        for row in self.register():
            # A quality queue must include only inspection types selected in the Part + OSP Process group.
            if not bool(row.get(requirement_flag)):
                continue
            ready = bool(row.get("sample_received_date")) if scope == "OSP_SAMPLE" else (float(row.get("quantity_received") or 0) >= float(row.get("quantity_dispatched") or 0) and float(row.get("quantity_dispatched") or 0) > 0)
            pending = str(row.get(disposition_key) or "PENDING") not in {"ACCEPTED", "ACCEPTED_UNDER_RESERVE", "REJECTED"}
            if ready and pending and str(row.get("status")) != "CANCELLED":
                rows.append(row)
        return rows
