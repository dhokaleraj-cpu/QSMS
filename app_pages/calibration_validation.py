from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.attachments import AttachmentSlot, render_attachment_manager
from core.delete_service import password_delete_panel
from core.record_audit import annotate_transaction_rows
from core.reporting import controlled_record_pdf_bytes, safe_excel_sheet_name
from core.repository import Repository
from core.ui import kpi_grid, page_header, portal_table, record_widget_token, save_success_popup, section_bar, stage_section


FREQUENCIES = {
    "1 Month": 30,
    "3 Months": 90,
    "6 Months": 180,
    "1 Year": 365,
    "2 Years": 730,
    "Custom": 0,
}
STANDARD_ROOM_INSTRUMENTS = (
    "CMM", "COUNTER", "VMM", "ROUGHNESS TESTER", "HEIGHT GAUGE", "PROFILE PROJECTOR",
    "ROUNDNESS TESTER", "CONTOUR TRACER", "HARDNESS TESTER", "OTHER",
)


def _date_value(value: Any, default: date | None = None) -> date | None:
    if isinstance(value, date):
        return value
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text) if text else default
    except ValueError:
        return default


def _label(row: Mapping[str, Any], *fields: str) -> str:
    vals = [str(row.get(f) or "").strip() for f in fields]
    vals = [v for v in vals if v]
    return " · ".join(vals) or str(row.get("id") or "-")


def _excel_bytes(title: str, rows: list[Mapping[str, Any]]) -> bytes:
    buf = BytesIO()
    frame = pd.DataFrame(rows)
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=safe_excel_sheet_name(title))
    return buf.getvalue()


def _calibration_pdf(
    record: Mapping[str, Any], *, asset: Mapping[str, Any], part: Mapping[str, Any] | None = None,
    process: Mapping[str, Any] | None = None, employee: Mapping[str, Any] | None = None,
) -> bytes:
    header = {
        "Asset Code": asset.get("asset_code"), "Asset": asset.get("asset_name"), "Asset Type": asset.get("asset_type"),
        "Part Number": (part or {}).get("part_number"), "Process": (process or {}).get("process_name"),
        "Record Type": record.get("record_type"), "Service Date": record.get("service_date"),
        "Next Due Date": record.get("next_due_date"), "Result": record.get("result"), "Status": record.get("status"),
    }
    sections = [
        ("CALIBRATION / VALIDATION DETAILS", {
            "Report Number": record.get("report_number"), "Certificate Number": record.get("certificate_number"),
            "Calibration / Validation Agency": record.get("calibration_agency"),
            "Performed By": _label(employee or {}, "employee_code", "first_name", "last_name"),
            "Remarks": record.get("remarks"),
        }),
        ("ASSET MASTER CONTEXT", {
            "Manufacturer": asset.get("manufacturer"), "Model": asset.get("model"), "Serial Number": asset.get("serial_number"),
            "Range": asset.get("range_text"), "Least Count": asset.get("least_count"), "Location": asset.get("location"),
        }),
    ]
    return controlled_record_pdf_bytes(
        "GAUGE / FIXTURE CALIBRATION & VALIDATION RECORD", header, sections,
        record_number=str(record.get("report_number") or record.get("certificate_number") or record.get("id") or ""),
        subtitle="Part-wise · Process-wise controlled calibration / validation genealogy",
    )


def _standard_room_pdf(
    record: Mapping[str, Any], *, asset: Mapping[str, Any] | None, part: Mapping[str, Any] | None,
    process: Mapping[str, Any] | None, employee: Mapping[str, Any] | None,
) -> bytes:
    header = {
        "Inspection Date": record.get("inspection_date"), "Report Number": record.get("report_number"),
        "Instrument": (asset or {}).get("asset_name") or record.get("instrument_type"),
        "Instrument Code": (asset or {}).get("asset_code"), "Part Number": (part or {}).get("part_number"),
        "Part Name": (part or {}).get("part_name"), "Process": (process or {}).get("process_name"),
        "Heat Number": record.get("heat_number"), "Batch Code": record.get("batch_code"),
        "Status": record.get("inspection_status"),
    }
    sections = [("STANDARD ROOM INSPECTION", {
        "Instrument Type": record.get("instrument_type"), "Program / Method Reference": record.get("program_reference"),
        "Quantity Inspected": record.get("quantity_inspected"),
        "Operator": _label(employee or {}, "employee_code", "first_name", "last_name"),
        "Remarks": record.get("remarks"), "Record Status": record.get("status"),
    })]
    return controlled_record_pdf_bytes(
        "STANDARD ROOM PART INSPECTION RECORD", header, sections,
        record_number=str(record.get("report_number") or record.get("id") or ""),
        subtitle="CMM · VMM · Roughness · Counter · Standard Room Instrument Inspection",
    )


def render_calibration_validation() -> None:
    page_header(
        "Calibration & Validation", "Process-wise gauge / fixture control with drawings, photographs, service history and due-date reminders.",
        "Calibration & Validation",
    )
    repo = Repository(); perms = current_permissions("CALIBRATION_VALIDATION")
    assets = repo.select("quality_assets", eq={"status": "ACTIVE"}, order_by="asset_code", limit=5000)
    parts = repo.select("parts", eq={"status": "ACTIVE"}, order_by="part_number", limit=5000)
    processes = repo.select("processes", eq={"status": "ACTIVE"}, order_by="process_code", limit=5000)
    employees = repo.select("employees", eq={"status": "ACTIVE"}, order_by="first_name", limit=5000)
    asset_map = {str(r["id"]): r for r in assets}; part_map = {str(r["id"]): r for r in parts}; process_map = {str(r["id"]): r for r in processes}; employee_map = {str(r["id"]): r for r in employees}

    links = repo.select("quality_asset_part_process_links", order_by="next_due_date", limit=10000)
    today = date.today(); due30 = today + timedelta(days=30)
    overdue = [r for r in links if str(r.get("status")) == "ACTIVE" and _date_value(r.get("next_due_date")) and _date_value(r.get("next_due_date")) < today]
    due = [r for r in links if str(r.get("status")) == "ACTIVE" and _date_value(r.get("next_due_date")) and today <= _date_value(r.get("next_due_date")) <= due30]
    valid = [r for r in links if str(r.get("status")) == "ACTIVE" and _date_value(r.get("next_due_date")) and _date_value(r.get("next_due_date")) > due30]
    kpi_grid([
        {"label":"Overdue Calibration / Validation","value":len(overdue),"foot":"Immediate Quality action required","color":"#B91C1C","background":"#FEF2F2"},
        {"label":"Due within 30 days","value":len(due),"foot":"Daily reminder window","color":"#C2410C","background":"#FFF7ED"},
        {"label":"Valid beyond 30 days","value":len(valid),"foot":"Current controlled assets","color":"#15803D","background":"#F0FDF4"},
        {"label":"Part / Process Links","value":len(links),"foot":"Gauge / Fixture applicability","color":"#075985","background":"#F0F9FF"},
    ])

    with stage_section("A", "PART / PROCESS → GAUGE / FIXTURE CONTROL", "Link each controlled Quality Asset to the exact Part and Process. The frequency drives the reminder and next service due date.", key="calibration_links"):
        link_labels = {str(r["id"]): f"{(asset_map.get(str(r.get('asset_id'))) or {}).get('asset_code') or '-'} · {(part_map.get(str(r.get('part_id'))) or {}).get('part_number') or '-'} · {(process_map.get(str(r.get('process_id'))) or {}).get('process_name') or 'General'}" for r in links}
        choice = st.selectbox("Create New / Edit Existing Link", [""] + list(link_labels), format_func=lambda v: "＋ New Part / Process Gauge-Fixture Link" if not v else link_labels[v], key="cal_link_choice")
        existing = next((r for r in links if str(r.get("id")) == choice), None)
        token = record_widget_token(existing, prefix="cal_link") if existing else "cal_link_new"
        a1,a2,a3 = st.columns(3, gap="small")
        asset_ids = list(asset_map); part_ids = list(part_map); process_ids = [""] + list(process_map)
        asset_default = str((existing or {}).get("asset_id") or ""); part_default = str((existing or {}).get("part_id") or ""); process_default = str((existing or {}).get("process_id") or "")
        asset_id = a1.selectbox("Gauge / Fixture / Instrument", asset_ids, index=asset_ids.index(asset_default) if asset_default in asset_ids else 0, format_func=lambda v: _label(asset_map[v],"asset_code","asset_name","asset_type"), disabled=not perms["can_edit"] if existing else not perms["can_create"], key=f"{token}_asset") if asset_ids else ""
        part_id = a2.selectbox("Part Number", part_ids, index=part_ids.index(part_default) if part_default in part_ids else 0, format_func=lambda v: _label(part_map[v],"part_number","fsi_part_number","part_name"), disabled=not perms["can_edit"] if existing else not perms["can_create"], key=f"{token}_part") if part_ids else ""
        process_id = a3.selectbox("Process", process_ids, index=process_ids.index(process_default) if process_default in process_ids else 0, format_func=lambda v: "General / All Processes" if not v else _label(process_map[v],"process_code","process_name"), disabled=not perms["can_edit"] if existing else not perms["can_create"], key=f"{token}_process")
        b1,b2,b3,b4 = st.columns(4, gap="small")
        service_type = b1.selectbox("Control Type", ["CALIBRATION","VALIDATION","BOTH"], index=["CALIBRATION","VALIDATION","BOTH"].index(str((existing or {}).get("service_type") or "CALIBRATION")), key=f"{token}_stype")
        existing_days = int((existing or {}).get("frequency_days") or 365)
        default_freq = next((name for name,days in FREQUENCIES.items() if days == existing_days), "Custom")
        freq_name = b2.selectbox("Frequency", list(FREQUENCIES), index=list(FREQUENCIES).index(default_freq), key=f"{token}_freq")
        frequency_days = b3.number_input("Frequency Days", min_value=1, max_value=3650, value=existing_days if freq_name == "Custom" else FREQUENCIES[freq_name], step=1, key=f"{token}_days", disabled=freq_name != "Custom")
        responsible_ids = [""] + list(employee_map); emp_default = str((existing or {}).get("responsible_employee_id") or "")
        responsible = b4.selectbox("Responsible Employee", responsible_ids, index=responsible_ids.index(emp_default) if emp_default in responsible_ids else 0, format_func=lambda v: "Quality Department Default" if not v else _label(employee_map[v],"employee_code","first_name","last_name"), key=f"{token}_resp")
        c1,c2 = st.columns(2, gap="small")
        characteristic = c1.text_input("Gauge / Fixture Use / Characteristic", value=str((existing or {}).get("characteristic_use") or ""), key=f"{token}_use")
        next_due = c2.date_input("Next Calibration / Validation Due", value=_date_value((existing or {}).get("next_due_date"), today + timedelta(days=int(frequency_days))) or today, key=f"{token}_due")
        remarks = st.text_area("Remarks", value=str((existing or {}).get("remarks") or ""), key=f"{token}_remarks")
        can_save = perms["can_edit"] if existing else perms["can_create"]
        if st.button("Update Part / Process Gauge-Fixture Link" if existing else "Create Part / Process Gauge-Fixture Link", type="primary", width="stretch", disabled=not can_save or not asset_id or not part_id, key=f"{token}_save"):
            payload={"asset_id":asset_id,"part_id":part_id,"process_id":process_id or None,"service_type":service_type,"frequency_days":int(frequency_days),"characteristic_use":characteristic.strip() or None,"next_due_date":next_due.isoformat(),"responsible_employee_id":responsible or None,"status":str((existing or {}).get("status") or "ACTIVE"),"remarks":remarks.strip() or None}
            if existing: repo.update("quality_asset_part_process_links", str(existing["id"]), payload)
            else: repo.insert("quality_asset_part_process_links", payload)
            save_success_popup("Gauge / Fixture applicability saved.", queue_for_rerun=True); st.rerun()

        if asset_id:
            render_attachment_manager(
                repo=repo, entity_type="QUALITY_ASSET", entity_id=asset_id, folder="quality_assets",
                slots=(
                    AttachmentSlot("GAUGE_FIXTURE_DRAWING","Gauge / Fixture Drawing","PDF, DWG, DXF or image drawing"),
                    AttachmentSlot("ASSET_PHOTOGRAPH","Gauge / Fixture Photograph","Controlled asset photograph"),
                    AttachmentSlot("ASSET_REFERENCE_DOCUMENT","Reference / Instruction","Optional controlled instruction or specification"),
                ),
                key_prefix=f"asset_docs_{asset_id}", can_add_or_replace=perms["can_edit"] or perms["can_create"], can_delete=perms["can_archive"], title="GAUGE / FIXTURE DRAWINGS & PHOTOGRAPHS",
            )

    with stage_section("B", "CALIBRATION / VALIDATION ENTRY", "Complete a service record. The next due date is calculated from the controlled frequency and the daily reminder stops automatically when the new valid record updates the link.", key="calibration_service"):
        current_links = repo.select("quality_asset_part_process_links", eq={"status":"ACTIVE"}, order_by="next_due_date", limit=10000)
        link_map = {str(r["id"]): r for r in current_links}
        link_labels = {lid: f"{_label(asset_map.get(str(r.get('asset_id'))) or {},'asset_code','asset_name')} · {_label(part_map.get(str(r.get('part_id'))) or {},'part_number','part_name')} · {_label(process_map.get(str(r.get('process_id'))) or {},'process_code','process_name')} · Due {r.get('next_due_date') or '-'}" for lid,r in link_map.items()}
        records = repo.select("quality_asset_calibration_records", order_by="service_date", desc=True, limit=10000)
        record_labels = {str(r["id"]): f"{r.get('record_type')} · {r.get('report_number') or r.get('certificate_number') or str(r.get('id'))[:8]} · {r.get('service_date')}" for r in records}
        rec_choice = st.selectbox("New / Edit Calibration-Validation Record", [""]+list(record_labels), format_func=lambda v: "＋ New Calibration / Validation Record" if not v else record_labels[v], key="cal_rec_choice")
        existing_rec = next((r for r in records if str(r.get("id")) == rec_choice), None)
        rec_token = record_widget_token(existing_rec,prefix="cal_rec") if existing_rec else "cal_rec_new"
        link_ids=list(link_map); link_default=str((existing_rec or {}).get("link_id") or "")
        selected_link=st.selectbox("Part / Process Gauge-Fixture Link",link_ids,index=link_ids.index(link_default) if link_default in link_ids else 0,format_func=lambda v:link_labels[v],key=f"{rec_token}_link") if link_ids else ""
        link=link_map.get(selected_link) or {}; frequency=int(link.get("frequency_days") or 365); asset=asset_map.get(str(link.get("asset_id"))) or {}
        r1,r2,r3,r4=st.columns(4,gap="small")
        record_type=r1.selectbox("Record Type",["CALIBRATION","VALIDATION"],index=["CALIBRATION","VALIDATION"].index(str((existing_rec or {}).get("record_type") or ("VALIDATION" if str(link.get("service_type"))=="VALIDATION" else "CALIBRATION"))),key=f"{rec_token}_type")
        service_date=r2.date_input("Service Date",value=_date_value((existing_rec or {}).get("service_date"),today) or today,key=f"{rec_token}_date")
        result=r3.selectbox("Result",["ACCEPTED","LIMITED_USE","REJECTED","PENDING"],index=["ACCEPTED","LIMITED_USE","REJECTED","PENDING"].index(str((existing_rec or {}).get("result") or "ACCEPTED")),key=f"{rec_token}_result")
        calculated_due=service_date+timedelta(days=frequency)
        next_service_due=r4.date_input("Next Due Date",value=_date_value((existing_rec or {}).get("next_due_date"),calculated_due) or calculated_due,key=f"{rec_token}_next")
        q1,q2,q3=st.columns(3,gap="small")
        report_no=q1.text_input("Report Number",value=str((existing_rec or {}).get("report_number") or ""),key=f"{rec_token}_report")
        cert_no=q2.text_input("Certificate Number",value=str((existing_rec or {}).get("certificate_number") or ""),key=f"{rec_token}_cert")
        agency=q3.text_input("Calibration / Validation Agency",value=str((existing_rec or {}).get("calibration_agency") or ""),key=f"{rec_token}_agency")
        emp_ids=[""]+list(employee_map); performed_default=str((existing_rec or {}).get("performed_by_employee_id") or "")
        performed=st.selectbox("Performed / Verified By",emp_ids,index=emp_ids.index(performed_default) if performed_default in emp_ids else 0,format_func=lambda v:"External / Not Assigned" if not v else _label(employee_map[v],"employee_code","first_name","last_name"),key=f"{rec_token}_performed")
        rec_remarks=st.text_area("Service Remarks",value=str((existing_rec or {}).get("remarks") or ""),key=f"{rec_token}_remarks")
        can_rec_save=perms["can_edit"] if existing_rec else perms["can_create"]
        if st.button("Update Calibration / Validation Record" if existing_rec else "Save Calibration / Validation Record",type="primary",width="stretch",disabled=not can_rec_save or not selected_link,key=f"{rec_token}_save"):
            rec_payload={"link_id":selected_link,"asset_id":str(link.get("asset_id") or ""),"record_type":record_type,"service_date":service_date.isoformat(),"result":result,"report_number":report_no.strip() or None,"certificate_number":cert_no.strip() or None,"calibration_agency":agency.strip() or None,"performed_by_employee_id":performed or None,"next_due_date":next_service_due.isoformat(),"status":"VALID" if result in {"ACCEPTED","LIMITED_USE"} else ("REJECTED" if result=="REJECTED" else "PENDING"),"remarks":rec_remarks.strip() or None}
            saved=repo.update("quality_asset_calibration_records",str(existing_rec["id"]),rec_payload) if existing_rec else repo.insert("quality_asset_calibration_records",rec_payload)
            if result in {"ACCEPTED","LIMITED_USE"}:
                repo.update("quality_asset_part_process_links",selected_link,{"last_service_date":service_date.isoformat(),"next_due_date":next_service_due.isoformat()})
                asset_update={"next_due_date":next_service_due.isoformat()}
                if record_type=="CALIBRATION": asset_update["last_calibration_date"]=service_date.isoformat()
                else: asset_update.update({"last_validation_date":service_date.isoformat(),"next_validation_due_date":next_service_due.isoformat()})
                repo.update("quality_assets",str(link.get("asset_id")),asset_update)
            st.session_state["selected_calibration_record_id"]=str(saved.get("id") or "")
            save_success_popup("Calibration / Validation record saved and next due date updated.",queue_for_rerun=True);st.rerun()

        selected_rec_id=str(existing_rec.get("id") if existing_rec else st.session_state.get("selected_calibration_record_id") or "")
        selected_rec=next((r for r in records if str(r.get("id"))==selected_rec_id),existing_rec)
        if selected_rec:
            render_attachment_manager(repo=repo,entity_type="CALIBRATION_RECORD",entity_id=str(selected_rec["id"]),folder="calibration_records",slots=(AttachmentSlot("CALIBRATION_VALIDATION_REPORT","Calibration / Validation Report"),AttachmentSlot("CALIBRATION_CERTIFICATE","Calibration Certificate")),key_prefix=f"cal_docs_{selected_rec['id']}",can_add_or_replace=perms["can_edit"],can_delete=perms["can_archive"],title="CALIBRATION / VALIDATION REPORTS")
            selected_link_row=link_map.get(str(selected_rec.get("link_id"))) or {}; a=asset_map.get(str(selected_rec.get("asset_id"))) or {}; p=part_map.get(str(selected_link_row.get("part_id"))) or {}; pr=process_map.get(str(selected_link_row.get("process_id"))) or {}; e=employee_map.get(str(selected_rec.get("performed_by_employee_id"))) or {}
            x1,x2=st.columns(2,gap="small")
            x1.download_button("Download Calibration / Validation PDF",_calibration_pdf(selected_rec,asset=a,part=p,process=pr,employee=e),file_name=f"{selected_rec.get('report_number') or selected_rec.get('certificate_number') or selected_rec.get('id')}.pdf",mime="application/pdf",width="stretch",key=f"cal_pdf_{selected_rec['id']}")
            x2.download_button("Download Calibration / Validation Excel",_excel_bytes("Calibration Record",[selected_rec]),file_name=f"{selected_rec.get('report_number') or selected_rec.get('id')}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",width="stretch",key=f"cal_xlsx_{selected_rec['id']}")
            if password_delete_panel(repo=repo,table="quality_asset_calibration_records",rows=[selected_rec],labeler=lambda r:record_labels.get(str(r.get("id")),str(r.get("id"))),key=f"cal_delete_{selected_rec['id']}",can_delete=perms["can_archive"],title="Delete Calibration / Validation Record",help_text="Permanent deletion requires your current QCMS password. Linked genealogy blocks unsafe deletion."):
                st.rerun()

    with stage_section("C", "CALIBRATION / VALIDATION REGISTER", "Due/overdue status remains visible until a new accepted record updates the controlled next due date.", key="calibration_register"):
        link_rows=[]
        for row in annotate_transaction_rows(repo,repo.select("quality_asset_part_process_links",order_by="next_due_date",limit=10000)):
            due_date=_date_value(row.get("next_due_date")); due_state="OVERDUE" if due_date and due_date<today else ("DUE <= 30 DAYS" if due_date and due_date<=due30 else "VALID")
            link_rows.append({"Asset":_label(asset_map.get(str(row.get("asset_id"))) or {},"asset_code","asset_name"),"Part":_label(part_map.get(str(row.get("part_id"))) or {},"part_number","fsi_part_number"),"Process":_label(process_map.get(str(row.get("process_id"))) or {},"process_code","process_name"),"Control":row.get("service_type"),"Frequency Days":row.get("frequency_days"),"Last Service":row.get("last_service_date"),"Next Due":row.get("next_due_date"),"Due Status":due_state,"Responsible":_label(employee_map.get(str(row.get("responsible_employee_id"))) or {},"first_name","last_name"),"Created By User":row.get("Created By User"),"Last Modified By User":row.get("Last Modified By User"),"Data Entry Status":row.get("Data Entry Status")})
        if link_rows:
            portal_table(pd.DataFrame(link_rows),hide_index=True,width="stretch",height=360)
            st.download_button("Download Calibration / Validation Due Register Excel",_excel_bytes("Calibration Due Register",link_rows),file_name=f"QCMS_Calibration_Validation_Due_Register_{today}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",width="stretch")


def render_standard_room() -> None:
    page_header("Standard Room Inspection Records", "CMM, Counter, VMM, Roughness Tester and other controlled instrument inspection history by Part / Heat / Batch.", "Calibration & Validation")
    repo=Repository(); perms=current_permissions("CALIBRATION_VALIDATION")
    assets=repo.select("quality_assets",eq={"status":"ACTIVE"},order_by="asset_code",limit=5000); parts=repo.select("parts",eq={"status":"ACTIVE"},order_by="part_number",limit=5000); processes=repo.select("processes",eq={"status":"ACTIVE"},order_by="process_code",limit=5000); employees=repo.select("employees",eq={"status":"ACTIVE"},order_by="first_name",limit=5000)
    asset_map={str(r["id"]):r for r in assets}; part_map={str(r["id"]):r for r in parts}; process_map={str(r["id"]):r for r in processes}; employee_map={str(r["id"]):r for r in employees}
    rows=repo.select("standard_room_inspection_records",order_by="inspection_date",desc=True,limit=10000)
    labels={str(r["id"]):f"{r.get('report_number') or str(r.get('id'))[:8]} · {r.get('inspection_date')} · {(part_map.get(str(r.get('part_id'))) or {}).get('part_number') or '-'} · {r.get('inspection_status')}" for r in rows}
    choice=st.selectbox("Create New / Edit Standard Room Inspection",[""]+list(labels),format_func=lambda v:"＋ New Standard Room Inspection" if not v else labels[v],key="std_room_choice")
    existing=next((r for r in rows if str(r.get("id"))==choice),None); token=record_widget_token(existing,prefix="std_room") if existing else "std_room_new"
    with stage_section("A","STANDARD ROOM INSPECTION ENTRY","Select the controlled instrument and Part. Heat/Batch provide traceability to the inspected production lot.",key="std_room_entry"):
        c1,c2,c3,c4=st.columns(4,gap="small")
        inspect_date=c1.date_input("Inspection Date",value=_date_value((existing or {}).get("inspection_date"),date.today()) or date.today(),key=f"{token}_date")
        report_no=c2.text_input("Report Number",value=str((existing or {}).get("report_number") or ""),key=f"{token}_report")
        asset_ids=[""]+list(asset_map); asset_default=str((existing or {}).get("instrument_asset_id") or "")
        asset_id=c3.selectbox("Standard Room Instrument",asset_ids,index=asset_ids.index(asset_default) if asset_default in asset_ids else 0,format_func=lambda v:"Manual / Other Instrument" if not v else _label(asset_map[v],"asset_code","asset_name","asset_type"),key=f"{token}_asset")
        instrument_type=c4.selectbox("Instrument Type",list(STANDARD_ROOM_INSTRUMENTS),index=list(STANDARD_ROOM_INSTRUMENTS).index(str((existing or {}).get("instrument_type") or "CMM")) if str((existing or {}).get("instrument_type") or "CMM") in STANDARD_ROOM_INSTRUMENTS else 0,key=f"{token}_itype")
        d1,d2,d3=st.columns(3,gap="small")
        part_ids=list(part_map); part_default=str((existing or {}).get("part_id") or "")
        part_id=d1.selectbox("Part Number",part_ids,index=part_ids.index(part_default) if part_default in part_ids else 0,format_func=lambda v:_label(part_map[v],"part_number","fsi_part_number","part_name"),key=f"{token}_part") if part_ids else ""
        process_ids=[""]+list(process_map); proc_default=str((existing or {}).get("process_id") or "")
        process_id=d2.selectbox("Process",process_ids,index=process_ids.index(proc_default) if proc_default in process_ids else 0,format_func=lambda v:"General / Final Inspection" if not v else _label(process_map[v],"process_code","process_name"),key=f"{token}_process")
        status=d3.selectbox("Inspection Status",["PASS","FAIL","HOLD","PENDING"],index=["PASS","FAIL","HOLD","PENDING"].index(str((existing or {}).get("inspection_status") or "PENDING")),key=f"{token}_status")
        e1,e2,e3=st.columns(3,gap="small")
        heat=e1.text_input("Heat Number",value=str((existing or {}).get("heat_number") or ""),key=f"{token}_heat")
        batch=e2.text_input("Batch Code",value=str((existing or {}).get("batch_code") or ""),key=f"{token}_batch")
        qty=e3.number_input("Quantity Inspected",min_value=0.0,value=float((existing or {}).get("quantity_inspected") or 1),step=1.0,key=f"{token}_qty")
        f1,f2=st.columns(2,gap="small")
        program=f1.text_input("CMM / VMM Program / Method Reference",value=str((existing or {}).get("program_reference") or ""),key=f"{token}_program")
        emp_ids=[""]+list(employee_map); emp_default=str((existing or {}).get("operator_employee_id") or "")
        operator=f2.selectbox("Inspector / Operator",emp_ids,index=emp_ids.index(emp_default) if emp_default in emp_ids else 0,format_func=lambda v:"Not Assigned" if not v else _label(employee_map[v],"employee_code","first_name","last_name"),key=f"{token}_operator")
        remarks=st.text_area("Inspection Remarks",value=str((existing or {}).get("remarks") or ""),key=f"{token}_remarks")
        can_save=perms["can_edit"] if existing else perms["can_create"]
        if st.button("Update Standard Room Inspection" if existing else "Save Standard Room Inspection",type="primary",width="stretch",disabled=not can_save or not part_id,key=f"{token}_save"):
            payload={"inspection_date":inspect_date.isoformat(),"instrument_asset_id":asset_id or None,"instrument_type":instrument_type,"part_id":part_id,"process_id":process_id or None,"heat_number":heat.strip() or None,"batch_code":batch.strip() or None,"report_number":report_no.strip() or None,"quantity_inspected":qty,"inspection_status":status,"program_reference":program.strip() or None,"operator_employee_id":operator or None,"remarks":remarks.strip() or None,"status":"ACTIVE"}
            saved=repo.update("standard_room_inspection_records",str(existing["id"]),payload) if existing else repo.insert("standard_room_inspection_records",payload)
            st.session_state["selected_standard_room_id"]=str(saved.get("id") or "")
            save_success_popup("Standard Room inspection record saved.",queue_for_rerun=True);st.rerun()

    selected_id=str(existing.get("id") if existing else st.session_state.get("selected_standard_room_id") or "")
    selected=next((r for r in rows if str(r.get("id"))==selected_id),existing)
    if selected:
        with stage_section("B","REPORT / ATTACHMENTS / PRINT","Attach the controlled inspection report or instrument printout directly to this Standard Room record.",key="std_room_report"):
            render_attachment_manager(repo=repo,entity_type="STANDARD_ROOM_INSPECTION",entity_id=str(selected["id"]),folder="standard_room_inspections",slots=(AttachmentSlot("STANDARD_ROOM_REPORT","Inspection Report / CMM-VMM Output"),AttachmentSlot("STANDARD_ROOM_PHOTOGRAPH","Inspection / Setup Photograph")),key_prefix=f"std_room_docs_{selected['id']}",can_add_or_replace=perms["can_edit"],can_delete=perms["can_archive"],title="STANDARD ROOM REPORTS & PHOTOGRAPHS")
            a=asset_map.get(str(selected.get("instrument_asset_id"))) or {}; p=part_map.get(str(selected.get("part_id"))) or {}; pr=process_map.get(str(selected.get("process_id"))) or {}; e=employee_map.get(str(selected.get("operator_employee_id"))) or {}
            z1,z2=st.columns(2,gap="small")
            z1.download_button("Download Standard Room Inspection PDF",_standard_room_pdf(selected,asset=a,part=p,process=pr,employee=e),file_name=f"{selected.get('report_number') or selected.get('id')}.pdf",mime="application/pdf",width="stretch")
            z2.download_button("Download Standard Room Inspection Excel",_excel_bytes("Standard Room",[selected]),file_name=f"{selected.get('report_number') or selected.get('id')}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",width="stretch")
            if password_delete_panel(repo=repo,table="standard_room_inspection_records",rows=[selected],labeler=lambda r:labels.get(str(r.get("id")),str(r.get("id"))),key=f"std_delete_{selected['id']}",can_delete=perms["can_archive"],title="Delete Standard Room Inspection",help_text="Permanent deletion requires your current QCMS password and is blocked when genealogy depends on this record."):
                st.rerun()

    with stage_section("C","STANDARD ROOM INSPECTION REGISTER","All Part inspections remain searchable by date, Heat, Batch, instrument and status.",key="std_room_register"):
        display=[]
        for r in annotate_transaction_rows(repo,rows):
            display.append({"Date":r.get("inspection_date"),"Report":r.get("report_number"),"Instrument":_label(asset_map.get(str(r.get("instrument_asset_id"))) or {},"asset_code","asset_name") or r.get("instrument_type"),"Type":r.get("instrument_type"),"Part":_label(part_map.get(str(r.get("part_id"))) or {},"part_number","fsi_part_number"),"Process":_label(process_map.get(str(r.get("process_id"))) or {},"process_code","process_name"),"Heat":r.get("heat_number"),"Batch":r.get("batch_code"),"Qty":r.get("quantity_inspected"),"Inspection Status":r.get("inspection_status"),"User":r.get("Last Modified By User"),"Data Entry Status":r.get("Data Entry Status")})
        if display:
            portal_table(pd.DataFrame(display),hide_index=True,width="stretch",height=420)
            st.download_button("Download Standard Room Register Excel",_excel_bytes("Standard Room Register",display),file_name=f"QCMS_Standard_Room_Inspection_Register_{date.today()}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",width="stretch")
        else:
            st.info("No Standard Room inspection records are available yet.")
