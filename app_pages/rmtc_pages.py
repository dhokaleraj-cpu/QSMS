from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.attachments import AttachmentService, AttachmentSlot, new_attachment_uploaders, render_attachment_manager
from core.delete_service import password_delete_panel
from core.calculations import band_status, calculate_di, calculate_jominy_curve
from core.permissions import normalized_role
from core.rmtc_service import RMTCService
from core.reporting import rmtc_record_pdf_bytes
from core.steel_balance import remaining_planned_steel
from core.ui import (DISPOSITION_EDITOR_OPTIONS, disposition_cards, disposition_label, normalize_disposition, page_header, save_success_popup, section_bar, style_status_dataframe, subpage_navigation, template_download_row, workflow_progress)

STATUS_OPTIONS=['PASS','FAIL','NOT_EVALUATED','NOT_APPLICABLE']

RMTC_ATTACHMENT_SLOTS = (
    AttachmentSlot('RMTC_COPY', 'Attachment 1 · RMTC Certificate / Copy', 'Optional supplier RMTC certificate or report copy', 'rmtc_approvals', 'rmtc_copy_path'),
    AttachmentSlot('RMTC_ATTACHMENT_2', 'Attachment 2 · Supporting Document', 'Optional supporting certificate, test report or correspondence'),
    AttachmentSlot('RMTC_ATTACHMENT_3', 'Attachment 3 · Additional Document', 'Optional additional controlled document'),
)

RMTC_MICROSTRUCTURE_SLOTS = tuple(
    AttachmentSlot(
        f'RMTC_MICROSTRUCTURE_{slot}',
        f'Microstructure Photo {slot}',
        'Controlled RMTC microstructure photograph (PNG/JPG/JPEG)',
    )
    for slot in range(1, 4)
)


def _opts(rows:list[dict],label)->dict[str,str]:
    return {str(r['id']):label(r) for r in rows}


def _number(value:Any):
    if value in (None,'') or pd.isna(value):return None
    try:return float(value)
    except Exception:return None


def _requirement_result(actual:Any,requirement:Any,applicable:bool=True)->str:
    if not applicable:return 'NOT_APPLICABLE'
    text=str(actual or '').strip(); req=str(requirement or '').strip()
    if not text:return 'NOT_EVALUATED'
    nums=[float(x) for x in re.findall(r'-?\d+(?:\.\d+)?',req)]
    match=re.search(r'-?\d+(?:\.\d+)?',text); actual_num=_number(match.group(0) if match else None)
    if actual_num is not None and len(nums)>=2:return 'PASS' if min(nums[0],nums[1])<=actual_num<=max(nums[0],nums[1]) else 'FAIL'
    if actual_num is not None and len(nums)==1 and ':' not in req:return 'PASS' if abs(actual_num-nums[0])<1e-9 else 'FAIL'
    return 'PASS' if text.casefold()==req.casefold() else 'FAIL'


def _employee_map(svc:RMTCService,authority:str)->dict[str,str]:
    return _opts(svc.employees(authority),lambda r:f"{r.get('employee_code')} · {r.get('first_name')} {r.get('last_name')}")


def _part_maps(svc:RMTCService):
    rows=svc.parts();return rows,_opts(rows,lambda r:f"{r.get('part_number')} · {r.get('part_name')}")


def _valid_uuid(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return str(uuid.UUID(text))
    except (ValueError, TypeError, AttributeError):
        return ""


def _header_record(svc:RMTCService)->dict:
    # Keep the selected Draft RMTC across Streamlit reruns.  The previous
    # pop() removed the selection and then sent an empty string to a UUID filter.
    rid = _valid_uuid(st.session_state.get('edit_rmtc_id'))
    if not rid:
        st.session_state.pop('edit_rmtc_id', None)
        return {}
    record = svc.get(rid) or {}
    if not record:
        st.session_state.pop('edit_rmtc_id', None)
    return record


def _workflow_steps(record: dict | None, part_rows: list[dict] | None = None) -> list[dict]:
    record = record or {}
    part_rows = part_rows or []
    final = str(record.get('status') or '') in ('APPROVED','PARTIALLY_APPROVED','REJECTED')
    hold = str(record.get('disposition') or '') == 'ON_HOLD'
    entry_done = bool(record.get('id'))
    worksheet_count = sum(1 for row in part_rows if row.get('worksheet_completed_at'))
    worksheet_done = bool(part_rows) and worksheet_count == len(part_rows)
    validated = bool(record.get('validated_at'))
    if final:
        decision_state = 'rejected' if str(record.get('disposition')) == 'REJECTED' else 'complete'
    elif hold:
        decision_state = 'hold'
    elif validated:
        decision_state = 'current'
    else:
        decision_state = 'pending'
    return [
        {'label':'RMTC Entry','state':'complete' if entry_done else 'current','detail':'Done' if entry_done else 'Current step'},
        {'label':'Part Worksheet','state':'complete' if worksheet_done else ('current' if entry_done else 'pending'),'detail':f'{worksheet_count}/{len(part_rows)} done' if part_rows else ('Current step' if entry_done else 'Pending')},
        {'label':'Validation','state':'complete' if validated else ('current' if worksheet_done else 'pending'),'detail':'Done' if validated else ('Submit / validate' if worksheet_done else 'Pending')},
        {'label':'Final Decision','state':decision_state,'detail':str(record.get('disposition') or 'Pending').replace('_',' ').title()},
    ]


def _open_rmtc_header_for_edit(rmtc_id: str) -> None:
    st.session_state['edit_rmtc_id'] = rmtc_id
    st.session_state['rmtc_entry_mode'] = 'edit'
    st.switch_page(st.session_state['_qsms_pages']['rmtc-entry'])


def _start_new_rmtc_for_heat(heat_number: str = "") -> None:
    st.session_state['rmtc_entry_mode'] = 'new'
    st.session_state['rmtc_heat_search'] = str(heat_number or '').strip()
    st.session_state['rmtc_new_form_nonce'] = int(st.session_state.get('rmtc_new_form_nonce') or 0) + 1
    for key in ('edit_rmtc_id', 'part_rmtc_id', 'rmtc_part_choice', 'new_rmtc_number'):
        st.session_state.pop(key, None)


def _render_rmtc_microstructure_inputs(existing: dict, repo: Repository, form_token: str) -> tuple[dict[str, Any], dict[int, str]]:
    """Render three controlled RMTC microstructure photo slots with user-defined titles."""
    section_bar('MICROSTRUCTURE PHOTOGRAPHS', 'Add up to three photographs and a descriptive title for each photograph.')
    st.caption('For an existing RMTC, the photograph file can be replaced/deleted below after saving; photograph titles are editable here.')
    attachment_service = AttachmentService(repo)
    existing_attachments: dict[str, dict] = {}
    if existing and existing.get('id'):
        try:
            existing_attachments = {
                str(row.get('document_type')): row
                for row in attachment_service.list_active('RMTC', str(existing['id']))
                if str(row.get('document_type') or '').startswith('RMTC_MICROSTRUCTURE_')
            }
        except Exception:
            existing_attachments = {}

    uploads: dict[str, Any] = {}
    titles: dict[int, str] = {}
    cols = st.columns(3, gap='small')
    for slot, col in enumerate(cols, start=1):
        document_type = f'RMTC_MICROSTRUCTURE_{slot}'
        with col:
            title_default = str(existing.get(f'microstructure_caption_{slot}') or f'Microstructure Photo {slot}') if existing else f'Microstructure Photo {slot}'
            attachment = existing_attachments.get(document_type)
            if attachment:
                try:
                    image_bytes = attachment_service.download(attachment)
                    if image_bytes:
                        st.image(image_bytes, caption=title_default, width=260)
                except Exception as exc:
                    st.caption(f'Photo {slot} preview unavailable: {exc}')
            elif existing:
                st.caption(f'Photo {slot}: no image uploaded')
            titles[slot] = st.text_input(
                f'Photo {slot} Title', value=title_default,
                key=f'rmtc_micro_title_{slot}_{form_token}',
            ).strip()
            if not existing:
                uploads[document_type] = st.file_uploader(
                    f'Upload Microstructure Photo {slot}',
                    type=['png', 'jpg', 'jpeg'],
                    key=f'rmtc_micro_photo_{slot}_{form_token}',
                )
    return uploads, titles

def render_entry()->None:
    subpage_navigation(('masters','Back to Masters',':material/arrow_back:'),('rmtc-records','RMTC Records',':material/table_view:'))
    page_header('RMTC Entry · Header','Create or edit the certificate header, heat, source, covered parts and RMTC attachment.','Step 1')
    template_download_row([('RMTC_Entry_Template.xlsx', 'Download RMTC Entry Template')], key_prefix='rmtc_entry')
    svc=RMTCService();repo=svc.repo;perms=current_permissions('RMTC_ENTRY')
    if st.session_state.get('rmtc_entry_mode')!='edit':
        st.session_state.pop('edit_rmtc_id',None)
    existing=_header_record(svc) if st.session_state.get('rmtc_entry_mode')=='edit' else {}
    form_token=str(existing.get('id') or f"new_{int(st.session_state.get('rmtc_new_form_nonce') or 0)}")
    existing_parts_rows=svc.covered_parts(str(existing.get('id'))) if existing else []
    workflow_progress(_workflow_steps(existing,existing_parts_rows))

    section_bar('HEAT NUMBER SEARCH','Search the Heat Number first. The same Heat may be reused only with a different Supplier RMTC Number.')
    default_heat=str(existing.get('heat_number') or st.session_state.get('rmtc_heat_search') or '')
    h1,h2=st.columns([4,1],gap='small')
    heat_search=h1.text_input('Search / Enter Heat Number',value=default_heat,placeholder='Enter supplier Heat Number',key=f"rmtc_heat_search_input_{form_token}")
    if h2.button('Search Heat',icon=':material/search:',width='stretch'):
        st.session_state['rmtc_heat_search']=heat_search.strip();st.rerun()
    heat_search=heat_search.strip()
    heat_summary=svc.heat_summary(heat_search) if heat_search else {}
    heat_usage=svc.heat_usage(heat_search) if heat_search else []
    if heat_search:
        section_bar(
            'GLOBAL HEAT QUANTITY BALANCE & RECORD LIST',
            'One Heat Number shares one global steel quantity. The balance and every linked RMTC/Part allocation are shown below.',
        )
    if heat_summary:
        k1,k2,k3,k4=st.columns(4,gap='small')
        k1.metric('Global Heat Steel',f"{float(heat_summary.get('global_steel_quantity_kg') or 0):,.3f} kg")
        k2.metric('Inward Steel Used',f"{float(heat_summary.get('inward_steel_quantity_kg') or 0):,.3f} kg")
        k3.metric('Remaining Planned Steel',f"{float(heat_summary.get('remaining_planned_steel_quantity_kg') or 0):,.3f} kg")
        k4.metric('Unallocated Heat Balance',f"{float(heat_summary.get('available_unallocated_steel_quantity_kg') or heat_summary.get('available_steel_quantity_kg') or 0):,.3f} kg")
        st.caption(
            f"Committed Heat steel: {float(heat_summary.get('committed_steel_quantity_kg') or 0):,.3f} kg = "
            f"Inward {float(heat_summary.get('inward_steel_quantity_kg') or 0):,.3f} kg + "
            f"Remaining planned {float(heat_summary.get('remaining_planned_steel_quantity_kg') or 0):,.3f} kg."
        )
        if int(heat_summary.get('active_rmtc_count') or 0)==0 and int(heat_summary.get('rejected_rmtc_count') or 0)>0:
            st.success('The previous RMTC record(s) for this Heat Number are rejected. Create another RMTC using a different Supplier RMTC Number.')
        else:
            st.info('This Heat Number already exists. Supplier and Part may be reused, but every RMTC must have a different Supplier RMTC Number.')
        if heat_usage:
            usage_df=pd.DataFrame(heat_usage).rename(columns={
                'rmtc_number':'RMTC Number','rmtc_status':'RMTC Status','rmtc_disposition':'RMTC Disposition',
                'supplier_rmtc_number':'Supplier RMTC Number','supplier_name':'Supplier','part_number':'Part Number','part_name':'Part Description',
                'planned_production_quantity_pcs':'Planned Qty (pcs)','input_weight_kg':'Input Wt (kg)',
                'planned_steel_quantity_kg':'Planned Steel (kg)','inward_production_quantity_pcs':'Inward Qty (pcs)',
                'inward_steel_quantity_kg':'Inward Steel (kg)','remaining_planned_steel_quantity_kg':'Remaining Plan (kg)',
                'automated_validation':'Automated Validation','part_disposition':'Part Decision'
            })
            show=[c for c in ['RMTC Number','Supplier RMTC Number','RMTC Status','RMTC Disposition','Supplier','Part Number','Part Description','Planned Qty (pcs)','Input Wt (kg)','Planned Steel (kg)','Inward Qty (pcs)','Inward Steel (kg)','Remaining Plan (kg)','Automated Validation','Part Decision'] if c in usage_df.columns]
            st.dataframe(style_status_dataframe(usage_df[show]),width='stretch',hide_index=True,height=min(360,80+len(usage_df)*36))
    elif heat_search:
        st.caption('New Heat Number. The steel quantity entered below becomes the global Heat steel quantity.')

    if heat_summary:
        hb1,hb2=st.columns(2,gap='small')
        if hb1.button('Add New RMTC for This Heat Number', icon=':material/add_circle:', type='primary', width='stretch', key=f'new_rmtc_same_heat_{form_token}'):
            _start_new_rmtc_for_heat(heat_search)
            st.rerun()
        if hb2.button('Open Heat Steel Ledger',icon=':material/table_view:',width='stretch',key=f'open_heat_ledger_{form_token}'):
            st.session_state['heat_ledger_filter']=heat_search
            st.switch_page(st.session_state['_qsms_pages']['heat-ledger'])

    if existing and st.button('Start New RMTC',icon=':material/add:',width='content'):
        _start_new_rmtc_for_heat(heat_search)
        st.rerun()
    writable=perms['can_edit'] if existing else perms['can_create']
    parts,part_map=_part_maps(svc)
    if not parts:st.warning('Create an active Part Master first.');return
    existing_parts=[str(row.get('part_id')) for row in existing_parts_rows] if existing else []
    section_bar('CERTIFICATE & COVERED PARTS','Multiple parts are selected here and completed on separate Part Worksheet pages.')
    selected_parts=st.multiselect('Part Numbers Covered by this Heat',list(part_map),default=existing_parts,format_func=lambda x:part_map[x],max_selections=30,key=f'rmtc_parts_{form_token}')
    primary_id=selected_parts[0] if selected_parts else str(existing.get('part_id') or next(iter(part_map)))
    sources=svc.source_details(primary_id)
    suppliers=svc.parties('SUPPLIER');mills=svc.parties('STEEL_MILL')
    supplier_map=_opts(suppliers,lambda r:r.get('party_name'));mill_map=_opts(mills,lambda r:r.get('party_name'))
    source_map={str(s['id']):f"{supplier_map.get(str(s.get('supplier_id')),'Supplier')} · {s.get('section_size') or '-'} · {s.get('forging_route') or '-'}" for s in sources}
    current_source=str(existing.get('selected_source_detail_id') or '')
    prepared_map=_employee_map(svc,'RMTC_PREPARE')

    c=st.columns(4,gap='small')
    suggested=st.session_state.setdefault('new_rmtc_number',f"RMTC-D9-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    rmtc_no=c[0].text_input('QCMS RMTC Number',value=str(existing.get('rmtc_number') or suggested),key=f'rmtc_no_{form_token}')
    entry_date=c[1].date_input('Entry Date',value=date.fromisoformat(str(existing.get('entry_date'))[:10]) if existing.get('entry_date') else date.today(),format='DD-MM-YYYY',key=f'rmtc_entry_date_{form_token}')
    cert_ref=c[2].text_input('Supplier RMTC Number',value=str(existing.get('certificate_reference') or ''),key=f'rmtc_cert_ref_{form_token}')
    cert_date=c[3].date_input('RMTC Date',value=date.fromisoformat(str(existing.get('certificate_date'))[:10]) if existing.get('certificate_date') else date.today(),format='DD-MM-YYYY',key=f'rmtc_cert_date_{form_token}')
    duplicate_supplier_rmtc=svc.supplier_rmtc_duplicate(heat_search,cert_ref,str(existing.get('id') or '')) if heat_search and cert_ref.strip() else None
    if duplicate_supplier_rmtc:
        st.error(
            f"Heat {heat_search} already uses Supplier RMTC Number {cert_ref.strip()} "
            f"in {duplicate_supplier_rmtc.get('rmtc_number')}. Enter a different Supplier RMTC Number."
        )
    c=st.columns(4,gap='small')
    source_id=c[0].selectbox('Approved Raw Material Source',['']+list(source_map),index=(['']+list(source_map)).index(current_source) if current_source in source_map else 0,format_func=lambda x:source_map.get(x,'— Select —'),key=f'rmtc_source_{form_token}')
    source=next((s for s in sources if str(s['id'])==source_id),{})
    steel_options=['']+list(mill_map); current_steel=str(existing.get('steel_mill_id') or '')
    steel_id=c[1].selectbox('Steel Mill',steel_options,index=steel_options.index(current_steel) if current_steel in steel_options else 0,format_func=lambda x:mill_map.get(x,'— Select —'),key=f'rmtc_mill_{form_token}')
    c[2].text_input('Selected Heat Number',value=heat_search,disabled=True,key=f'rmtc_selected_heat_{form_token}')
    heat=heat_search
    heat_code=c[3].text_input('Internal Heat Code',value=str(existing.get('heat_code') or ''),placeholder='Auto on save: Steel Mill initial-0001',key=f'rmtc_heat_code_{form_token}')
    c=st.columns(4,gap='small')
    heat_global_qty=float(heat_summary.get('global_steel_quantity_kg') or 0) if heat_summary else 0.0
    qty_default=float(existing.get('certificate_quantity') or heat_global_qty or 0)
    qty=c[0].number_input('Global Heat Steel Quantity (kg)',min_value=0.0,value=qty_default,step=1.0,disabled=bool(heat_summary),key=f'rmtc_qty_{form_token}')
    c[1].text_input('RM Section',value=str(source.get('section_size') or existing.get('rm_section') or ''),disabled=True,key=f'rmtc_section_{form_token}')
    c[2].text_input('Forging Route / Root',value=str(source.get('forging_route') or existing.get('forging_route') or ''),disabled=True,key=f'rmtc_route_{form_token}')
    prepared_options=['']+list(prepared_map);current_prepared=str(existing.get('prepared_by_employee_id') or '')
    prepared_id=c[3].selectbox('Prepared By',prepared_options,index=prepared_options.index(current_prepared) if current_prepared in prepared_options else 0,format_func=lambda x:prepared_map.get(x,'— Select —'),key=f'rmtc_prepared_{form_token}')
    remarks=st.text_area('RMTC Remarks',value=str(existing.get('remarks') or ''),height=70,key=f'rmtc_remarks_{form_token}')
    microstructure_uploads, microstructure_titles = _render_rmtc_microstructure_inputs(existing, repo, form_token)
    new_attachments = {} if existing else new_attachment_uploaders(
        RMTC_ATTACHMENT_SLOTS, key_prefix=f'rmtc_{form_token}', title='OPTIONAL RMTC ATTACHMENTS'
    )

    if st.button('Save RMTC Header & Continue',type='primary',disabled=not writable,width='stretch'):
        try:
            if not heat.strip(): raise ValueError('Search or enter the Heat Number first.')
            if not selected_parts: raise ValueError('Select at least one Part Number.')
            if duplicate_supplier_rmtc:
                raise ValueError(f"Heat {heat.strip()} already uses Supplier RMTC Number {cert_ref.strip()}. Enter a different Supplier RMTC Number.")
            if not all([rmtc_no.strip(),cert_ref.strip(),source_id,steel_id,heat.strip(),prepared_id]) or qty<=0:
                raise ValueError('Complete all mandatory certificate, source, heat, quantity and employee fields.')
            with st.spinner('Saving RMTC and preparing Part Worksheets...'):
                final_heat_code=heat_code.strip() or svc.next_heat_code(steel_id)
                supplier_id=str(source.get('supplier_id') or '')
                part=next(row for row in parts if str(row['id'])==primary_id)
                payload={'rmtc_number':rmtc_no.strip(),'entry_date':entry_date.isoformat(),'certificate_reference':cert_ref.strip(),'certificate_date':cert_date.isoformat(),'part_id':primary_id,'supplier_id':supplier_id,'steel_mill_id':steel_id,'material_grade_id':part.get('material_grade_id'),'heat_number':heat.strip(),'heat_code':final_heat_code,'certificate_quantity':qty,'chemistry_results':{},'chemistry_compliance':'NOT_EVALUATED','chemistry_failures':[],'mechanical_results':{},'status':str(existing.get('status') or 'DRAFT'),'selected_source_detail_id':source_id,'rm_section':source.get('section_size'),'forging_route':source.get('forging_route'),'prepared_by_employee_id':prepared_id,'prepared_at':existing.get('prepared_at') or datetime.now().isoformat(),'remarks':remarks.strip() or None,**{f'microstructure_caption_{slot}': (microstructure_titles.get(slot) or None) for slot in range(1,4)}}
                saved=svc.save_header(payload,selected_parts,str(existing['id']) if existing else None)
                # The legacy atomic RMTC header RPC predates photo titles, so persist the title columns explicitly.
                repo.update('rmtc_approvals', str(saved['id']), {
                    f'microstructure_caption_{slot}': (microstructure_titles.get(slot) or None)
                    for slot in range(1, 4)
                })
                attachment_service = AttachmentService(repo)
                for slot in RMTC_ATTACHMENT_SLOTS:
                    selected_file = new_attachments.get(slot.document_type)
                    if selected_file is not None:
                        attachment_service.upload(
                            entity_type='RMTC', entity_id=str(saved['id']), folder='rmtc',
                            slot=slot, file=selected_file,
                        )
                for slot in RMTC_MICROSTRUCTURE_SLOTS:
                    selected_file = microstructure_uploads.get(slot.document_type)
                    if selected_file is not None:
                        attachment_service.upload(
                            entity_type='RMTC', entity_id=str(saved['id']), folder='rmtc-microstructure',
                            slot=slot, file=selected_file,
                        )
            st.session_state['edit_rmtc_id']=str(saved['id'])
            st.session_state['rmtc_entry_mode']='edit'
            st.session_state['rmtc_part_choice']=selected_parts[0]
            st.session_state.pop('new_rmtc_number',None)
            st.session_state['part_rmtc_id']=str(saved['id'])
            st.session_state['rmtc_flash_success']=f"RMTC {saved.get('rmtc_number')} saved successfully. Internal Heat Code: {final_heat_code}."
            st.switch_page(st.session_state['_qsms_pages']['rmtc-part'])
        except Exception as exc: st.error(str(exc))
    if existing:
        st.session_state['part_rmtc_id']=str(existing['id'])
        render_attachment_manager(
            repo=repo, entity_type='RMTC', entity_id=str(existing['id']), folder='rmtc',
            slots=RMTC_ATTACHMENT_SLOTS, key_prefix=f'rmtc_entry_{existing.get("id")}',
            can_add_or_replace=perms['can_edit'], can_delete=perms['can_archive'],
            title='RMTC ATTACHMENTS',
        )
        render_attachment_manager(
            repo=repo, entity_type='RMTC', entity_id=str(existing['id']), folder='rmtc-microstructure',
            slots=RMTC_MICROSTRUCTURE_SLOTS, key_prefix=f'rmtc_microstructure_{existing.get("id")}',
            can_add_or_replace=perms['can_edit'], can_delete=perms['can_archive'],
            title='RMTC MICROSTRUCTURE PHOTO FILES',
        )
        section_bar('RMTC WORKFLOW')
        validator_map=_employee_map(svc,'RMTC_VALIDATE');approver_map=_employee_map(svc,'RMTC_APPROVE')
        validator_options=['']+list(validator_map);approver_options=['']+list(approver_map)
        current_validator=str(existing.get('validated_by_employee_id') or '')
        current_approver=str(existing.get('approved_by_employee_id') or '')
        w1,w2,w3,w4=st.columns([1,1.4,1.4,1.25],gap='small')
        w1.text_input('Current Status',value=str(existing.get('status') or 'DRAFT').replace('_',' ').title(),disabled=True)
        validator=w2.selectbox('Validator',validator_options,index=validator_options.index(current_validator) if current_validator in validator_options else 0,format_func=lambda x:validator_map.get(x,'— Select —'),key=f'entry_validator_{existing.get("id")}')
        approver=w3.selectbox('Approver',approver_options,index=approver_options.index(current_approver) if current_approver in approver_options else 0,format_func=lambda x:approver_map.get(x,'— Select —'),key=f'entry_approver_{existing.get("id")}')
        if str(existing.get('status'))=='DRAFT':
            if w4.button('Submit Draft → Pending',type='primary',disabled=not validator or not approver,width='stretch'):
                try:
                    repo.update('rmtc_approvals',str(existing['id']),{'validated_by_employee_id':validator,'approved_by_employee_id':approver})
                    repo.rpc('qsms_submit_rmtc',{'p_rmtc_id':str(existing['id'])})
                    save_success_popup('RMTC moved to Approval Pending.', queue_for_rerun=True);st.rerun()
                except Exception as exc:st.error(str(exc))
        else:
            w4.page_link(st.session_state['_qsms_pages']['rmtc-approval'],label='Open Approval',icon=':material/approval:',width='stretch')
        n1,n2=st.columns(2,gap='small')
        with n1:st.page_link(st.session_state['_qsms_pages']['rmtc-part'],label='Part Worksheets',icon=':material/format_list_bulleted:',width='stretch')
        with n2:st.page_link(st.session_state['_qsms_pages']['rmtc-approval'],label='Validation & Decision',icon=':material/approval:',width='stretch')
        if password_delete_panel(
            repo=repo, table='rmtc_approvals', rows=[existing],
            labeler=lambda row: f"{row.get('rmtc_number')} · Heat {row.get('heat_number')}",
            key=f"delete_rmtc_entry_{existing.get('id')}", can_delete=perms['can_archive'],
            title='Delete This RMTC Entry',
            help_text='Permanent deletion requires your current QCMS password and RMTC Delete permission. Linked Material Inward records will prevent deletion.',
        ):
            _start_new_rmtc_for_heat(''); st.rerun()


def render_part()->None:
    subpage_navigation(('rmtc-records','RMTC Records',':material/table_view:'),('rmtc-approval','Validation & Approval',':material/approval:'))
    page_header('RMTC Entry · Part Worksheet','Chemical composition, Actual/Calculated Jominy, DI and properties for one covered part.','Step 2')
    flash=st.session_state.pop('rmtc_flash_success',None)
    if flash: save_success_popup(flash)
    svc=RMTCService();repo=svc.repo;perms=current_permissions('RMTC_ENTRY')
    rid=_valid_uuid(st.session_state.get('part_rmtc_id') or st.session_state.get('edit_rmtc_id'))
    if not rid:
        records=svc.list();labels={str(r['id']):f"{r.get('rmtc_number')} · {r.get('heat_number')}" for r in records}
        if not labels:st.info('Create an RMTC Header first.');return
        rid=st.selectbox('RMTC',list(labels),format_func=lambda x:labels[x]);st.session_state['part_rmtc_id']=rid
    header=svc.get(rid)
    if not header:st.error('RMTC record not found.');return
    part_rows=svc.covered_parts(rid);parts={str(p['id']):p for p in svc.parts()}
    workflow_progress(_workflow_steps(header,part_rows))
    if st.button('Back to RMTC Header',icon=':material/arrow_back:',width='content'):
        _open_rmtc_header_for_edit(rid)
    labels={str(row.get('part_id')):f"{(parts.get(str(row.get('part_id'))) or {}).get('part_number')} · {(parts.get(str(row.get('part_id'))) or {}).get('part_name')}" for row in part_rows}
    if not labels:st.warning('No covered parts exist.');return
    preferred=str(st.session_state.get('rmtc_part_choice') or '')
    part_id=st.selectbox('Part Worksheet',list(labels),index=list(labels).index(preferred) if preferred in labels else 0,format_func=lambda x:labels[x])
    st.session_state['rmtc_part_choice']=part_id
    part=parts[part_id];part_approval=next(row for row in part_rows if str(row.get('part_id'))==part_id)
    grade_id=part.get('material_grade_id');grade=(repo.select('material_grades',eq={'id':grade_id},limit=1) or [{}])[0]
    existing=svc.details(rid,part_id)
    writable=perms['can_edit'] or perms['can_create']
    section_bar('PART & MATERIAL','Each selected part is a separate controlled worksheet.')
    st.dataframe(pd.DataFrame([{'RMTC':header.get('rmtc_number'),'Heat Number':header.get('heat_number'),'Internal Heat Code':header.get('heat_code'),'Part Number':part.get('part_number'),'Part Description':part.get('part_name'),'Material Grade':grade.get('grade_code'),'Status':header.get('status')}]),hide_index=True,width='stretch')

    source_rows=svc.source_details(part_id)
    production_source=next((row for row in source_rows if str(row.get('supplier_id'))==str(header.get('supplier_id'))),{})
    input_weight=float(part_approval.get('input_weight_kg') or production_source.get('input_weight_kg') or production_source.get('gross_weight_kg') or production_source.get('forging_weight_kg') or 0)
    planned_existing=float(part_approval.get('planned_production_quantity_pcs') or 0)
    heat_summary=svc.heat_summary(str(header.get('heat_number') or ''))
    heat_usage=svc.heat_usage(str(header.get('heat_number') or ''))
    current_usage=next((row for row in heat_usage if str(row.get('rmtc_part_approval_id'))==str(part_approval.get('id'))),{})
    current_part_inward_steel=float(current_usage.get('inward_steel_quantity_kg') or 0)
    current_existing_remaining=remaining_planned_steel(part_approval.get('planned_steel_quantity_kg'),current_part_inward_steel)
    global_heat_steel=float(heat_summary.get('global_steel_quantity_kg') or header.get('certificate_quantity') or 0)
    current_heat_commitment=float(heat_summary.get('committed_steel_quantity_kg') or 0)
    heat_inward_steel=float(heat_summary.get('inward_steel_quantity_kg') or 0)
    section_bar('PRODUCTION PLAN','Committed Heat steel equals inward steel already used plus the still-unconsumed portion of every active part plan.')
    pcols=st.columns(4,gap='small')
    planned_production_qty=pcols[0].number_input('Part Production Quantity (pcs)',min_value=0.0,value=planned_existing,step=1.0,key=f'planned_pcs_{rid}_{part_id}')
    pcols[1].number_input('Input Weight (kg/part)',min_value=0.0,value=input_weight,step=0.001,format='%.3f',disabled=True,key=f'plan_weight_{rid}_{part_id}')
    planned_steel=round(float(planned_production_qty)*input_weight,3)
    pcols[2].number_input('Planned Steel Quantity (kg)',min_value=0.0,value=planned_steel,step=0.001,format='%.3f',disabled=True,key=f'planned_steel_{rid}_{part_id}')
    projected_current_remaining=remaining_planned_steel(planned_steel,current_part_inward_steel)
    projected_commitment=round(max(current_heat_commitment-current_existing_remaining,0)+projected_current_remaining,3)
    heat_remaining=max(global_heat_steel-projected_commitment,0)
    pcols[3].number_input('Heat Steel Balance after Plan (kg)',min_value=0.0,value=heat_remaining,step=0.001,format='%.3f',disabled=True,key=f'plan_balance_{rid}_{part_id}')
    st.caption(
        f"Projected committed Heat steel: {projected_commitment:,.3f} kg = Inward {heat_inward_steel:,.3f} kg + "
        f"Remaining active plans {max(projected_commitment-heat_inward_steel,0):,.3f} kg."
    )
    plan_exceeds_heat=projected_commitment>global_heat_steel+0.001
    if input_weight<=0:
        st.error('Input Weight is missing in Part Master supplier forging parameters.')
    elif plan_exceeds_heat:
        st.error(f"Committed Heat steel {projected_commitment:,.3f} kg exceeds the Global Heat steel quantity {global_heat_steel:,.3f} kg.")

    section_bar('CHEMICAL COMPOSITION','Limits come from this Part Master material grade. Actual values are entered from the RMTC.')
    templates=svc.chemistry_template(grade_id);existing_chem={str(r.get('material_grade_element_id')):r for r in existing['chemistry']}
    chem_df=pd.DataFrame([{'Element':t.get('element'),'Minimum %':t.get('minimum'),'Maximum %':t.get('maximum'),'Actual %':(existing_chem.get(str(t.get('id'))) or {}).get('actual_value'),'Applicable':(existing_chem.get(str(t.get('id'))) or {}).get('result')!='NOT_APPLICABLE','Status':(existing_chem.get(str(t.get('id'))) or {}).get('result') or 'NOT_EVALUATED','_id':t.get('id'),'Unit':t.get('unit') or '%'} for t in templates])
    chem_edit=st.data_editor(chem_df,hide_index=True,width='stretch',height=350,disabled=['Element','Minimum %','Maximum %','Status','_id','Unit'],column_config={'_id':None,'Actual %':st.column_config.NumberColumn(format='%.4f')},key=f"chem_part_{rid}_{part_id}")
    chemistry_rows=[];chemistry_map={}
    for _,row in chem_edit.iterrows():
        applicable=bool(row.get('Applicable'));actual=None if pd.isna(row.get('Actual %')) else row.get('Actual %');status=band_status(actual,row.get('Minimum %'),row.get('Maximum %'),applicable)
        chemistry_rows.append({'material_grade_element_id':row['_id'],'element':row['Element'],'minimum_value':row['Minimum %'],'maximum_value':row['Maximum %'],'actual_value':actual,'unit':row['Unit'],'result':status})
        if applicable and actual is not None:chemistry_map[str(row['Element'])]=actual
    calculated_curve=calculate_jominy_curve(chemistry_map)

    section_bar('JOMINY RESULTS','Single grid with Actual Jominy, Actual Status, Calculated Jominy and Calculated Status.')
    jtemplates=svc.jominy_template(part_id);existing_j={str(r.get('jominy_distance_id')):r for r in existing['jominy']}
    jrows=[]
    for t in jtemplates:
        old=existing_j.get(str(t.get('jominy_distance_id'))) or {};distance=int(t.get('distance_16th') or 0);applicable=old.get('applicability','APPLICABLE')!='NOT_APPLICABLE';calc=calculated_curve.get(distance) if applicable else None
        jrows.append({'Distance':t.get('distance_label'),'MM':t.get('distance_mm'),'Min HRC':t.get('minimum_hrc'),'Max HRC':t.get('maximum_hrc'),'Actual Jominy':old.get('actual_hrc'),'Actual Jominy Status':band_status(old.get('actual_hrc'),t.get('minimum_hrc'),t.get('maximum_hrc'),applicable),'Calculated Jominy':calc,'Calculated Jominy Status':band_status(calc,t.get('minimum_hrc'),t.get('maximum_hrc'),applicable),'Applicable':applicable,'_distance_id':t.get('jominy_distance_id'),'_distance_16th':distance})
    jedit=st.data_editor(pd.DataFrame(jrows),hide_index=True,width='stretch',height=360,disabled=['Distance','MM','Min HRC','Max HRC','Actual Jominy Status','Calculated Jominy','Calculated Jominy Status','_distance_id','_distance_16th'],column_config={'_distance_id':None,'_distance_16th':None,'Actual Jominy':st.column_config.NumberColumn(format='%.3f')},key=f"jom_part_{rid}_{part_id}")
    jominy_rows=[{'jominy_distance_id':row['_distance_id'],'distance_label':row['Distance'],'distance_mm':row['MM'],'distance_16th':row['_distance_16th'],'minimum_hrc':row['Min HRC'],'maximum_hrc':row['Max HRC'],'actual_hrc':None if pd.isna(row['Actual Jominy']) else row['Actual Jominy'],'applicability':'APPLICABLE' if bool(row['Applicable']) else 'NOT_APPLICABLE'} for _,row in jedit.iterrows()]

    section_bar('DI VALUE','Actual and calculated DI use the supplied DI Hardenability workbook factor table.')
    grain=st.selectbox('Grain Size (ASTM E-112)',[4,5,6,7,8],index=[4,5,6,7,8].index(int(part_approval.get('grain_size') or 6)))
    di_applicable=st.checkbox('DI Applicable',value=str(part_approval.get('calculated_di_status') or '')!='NOT_APPLICABLE')
    actual_di=st.number_input('Actual DI',min_value=0.0,value=float(part_approval.get('actual_di') or 0),step=0.01,disabled=not di_applicable)
    di_calc=calculate_di(chemistry_map,grain) if di_applicable else {'value':None,'error':None,'factors':{}}
    st.dataframe(pd.DataFrame([{'Grain Size':grain,'Actual DI':actual_di if di_applicable else None,'Calculated DI':di_calc.get('value'),'Calculation Note':di_calc.get('error') or 'DI Hardenability.XLSX factor product'}]),hide_index=True,width='stretch')

    section_bar('HEAT TREATMENT & OTHER REQUIREMENTS','Not Applicable is available and does not block Draft saving.')
    templates=svc.requirements(part_id);existing_req={str(r.get('source_requirement_id')):r for r in existing['requirements']}
    req_rows=[]
    for t in templates:
        old=existing_req.get(str(t.get('id'))) or {};applicable=old.get('result')!='NOT_APPLICABLE'
        req_rows.append({'Property / Requirement':t.get('parameter_name'),'Part Master Value':t.get('requirement_value'),'RMTC Actual / Observation':old.get('actual_value') or '','Applicable':applicable,'Status':_requirement_result(old.get('actual_value'),t.get('requirement_value'),applicable),'_id':t.get('id'),'_seq':t.get('sequence_no')})
    req_edit=st.data_editor(pd.DataFrame(req_rows),hide_index=True,width='stretch',height=360,disabled=['Property / Requirement','Part Master Value','Status','_id','_seq'],column_config={'_id':None,'_seq':None},key=f"req_part_{rid}_{part_id}")
    requirement_rows=[{'source_requirement_id':row['_id'],'requirement_name':row['Property / Requirement'],'requirement_value':row['Part Master Value'],'actual_value':row['RMTC Actual / Observation'],'result':_requirement_result(row['RMTC Actual / Observation'],row['Part Master Value'],bool(row['Applicable'])),'sequence_no':row['_seq']} for _,row in req_edit.iterrows()]
    if st.button('Save Part Worksheet',type='primary',disabled=not writable or planned_production_qty<=0 or input_weight<=0 or plan_exceeds_heat,width='stretch'):
        try:
            result=svc.save_part_worksheet(rid,part_id,chemistry_rows,jominy_rows,requirement_rows,grain,actual_di if di_applicable else None,di_applicable,planned_production_qty,input_weight)
            refreshed=svc.covered_parts(rid)
            pending=[str(row.get('part_id')) for row in refreshed if not row.get('worksheet_completed_at')]
            if pending:
                st.session_state['rmtc_part_choice']=pending[0]
                st.session_state['rmtc_flash_success']=f"Part Worksheet saved. Calculated DI: {result['di'].get('value')}. Continue with the next Part Number."
                st.rerun()
            st.session_state['rmtc_flash_success']=f"All Part Worksheets are saved. Calculated DI: {result['di'].get('value')}."
            st.switch_page(st.session_state['_qsms_pages']['rmtc-approval'])
        except Exception as exc:st.error(str(exc))
    st.page_link(st.session_state['_qsms_pages']['rmtc-records'],label='Open RMTC Records',icon=':material/table_view:',width='stretch')


def render_records()->None:
    subpage_navigation(
        ('dashboard','Back to Dashboard',':material/arrow_back:'),
        ('records-center','Records Centre',':material/table_view:'),
        ('heat-ledger','Heat Steel Ledger',':material/table_view:'),
        ('inward-entry','Material Inward',':material/input:'),
    )
    page_header('RMTC · Records','Select the RMTC above the register, then open its header, part worksheets or approval page.','Records')
    svc=RMTCService();perms=current_permissions('RMTC_ENTRY');rows=svc.list();parts={str(p['id']):p for p in svc.parts()};suppliers={str(p['id']):p for p in svc.parties('SUPPLIER')};mills={str(p['id']):p for p in svc.parties('STEEL_MILL')}
    if st.button('Start New RMTC',icon=':material/add:',type='primary',width='content'):
        _start_new_rmtc_for_heat('');st.switch_page(st.session_state['_qsms_pages']['rmtc-entry'])
    search=st.text_input('Search RMTC, Heat Number, Heat Code or Supplier RMTC')
    filtered=[r for r in rows if not search or search.casefold() in ' '.join(str(r.get(k) or '') for k in ('rmtc_number','certificate_reference','heat_number','heat_code')).casefold()]

    selected=''
    if filtered:
        labels={str(r['id']):f"{r.get('rmtc_number')} · {r.get('heat_number')} · {str(r.get('disposition') or 'PENDING').replace('_',' ').title()}" for r in filtered}
        selected=st.selectbox('Select RMTC record',list(labels),format_func=lambda x:labels[x])
        selected_row=next(r for r in filtered if str(r.get('id'))==selected)
        st.session_state['edit_rmtc_id']=selected;st.session_state['part_rmtc_id']=selected
        disposition_cards([
            {'label':'Workflow Status','value':selected_row.get('status') or 'DRAFT'},
            {'label':'Final Disposition','value':selected_row.get('disposition') or 'PENDING'},
            {'label':'Validation','value':selected_row.get('validation_result') or 'NOT_EVALUATED'},
            {'label':'Heat Code','value':selected_row.get('heat_code') or '-'},
        ])
        c=st.columns(4,gap='small')
        with c[0]:
            if st.button('Edit Header',icon=':material/edit:',width='stretch',key=f'edit_rmtc_header_{selected}'):
                _open_rmtc_header_for_edit(selected)
        with c[1]:st.page_link(st.session_state['_qsms_pages']['rmtc-part'],label='Part Worksheets',icon=':material/format_list_bulleted:',width='stretch')
        with c[2]:st.page_link(st.session_state['_qsms_pages']['rmtc-approval'],label='Validation & Decision',icon=':material/approval:',width='stretch')
        with c[3]:
            if st.button('Heat Steel Ledger',icon=':material/table_view:',width='stretch',key=f'heat_ledger_{selected}'):
                st.session_state['heat_ledger_filter']=str(selected_row.get('heat_number') or '')
                st.switch_page(st.session_state['_qsms_pages']['heat-ledger'])
        try:
            pdf_payload=svc.report_payload(selected)
            pdf_bytes=rmtc_record_pdf_bytes(pdf_payload)
            pdf_name=re.sub(r'[^A-Za-z0-9_.-]+','_',str(selected_row.get('rmtc_number') or 'RMTC_Record')).strip('_')+'.pdf'
            st.download_button(
                'Download RMTC Record PDF',data=pdf_bytes,file_name=pdf_name,mime='application/pdf',
                icon=':material/picture_as_pdf:',width='content',key=f'rmtc_pdf_{selected}',
            )
        except Exception as exc:
            st.warning(f'RMTC PDF could not be prepared: {exc}')
        if password_delete_panel(
            repo=svc.repo,table='rmtc_approvals',rows=[selected_row],
            labeler=lambda r:f"{r.get('rmtc_number')} · {r.get('heat_number')}",
            key=f'delete_rmtc_{selected}',can_delete=perms['can_archive'],
            title='Delete Selected RMTC',
            help_text='Deletion requires your current password. Linked Material Inward records will block deletion.',
        ):
            st.session_state.pop('edit_rmtc_id',None);st.session_state.pop('part_rmtc_id',None);st.rerun()
        render_attachment_manager(
            repo=svc.repo, entity_type='RMTC', entity_id=selected, folder='rmtc',
            slots=RMTC_ATTACHMENT_SLOTS, key_prefix=f'rmtc_records_{selected}',
            can_add_or_replace=perms['can_edit'], can_delete=perms['can_archive'],
            title='SELECTED RMTC ATTACHMENTS',
        )
    else:
        st.info('No RMTC records match the search.')

    section_bar('RMTC REGISTER','The selected record and actions are placed above this full-width table.')
    df=pd.DataFrame([{'QCMS RMTC':r.get('rmtc_number'),'Supplier RMTC':r.get('certificate_reference'),'RMTC Date':r.get('certificate_date'),'Primary Part':(parts.get(str(r.get('part_id'))) or {}).get('part_number'),'Supplier':(suppliers.get(str(r.get('supplier_id'))) or {}).get('party_name'),'Steel Mill':(mills.get(str(r.get('steel_mill_id'))) or {}).get('party_name'),'Heat Number':r.get('heat_number'),'Internal Heat Code':r.get('heat_code'),'Steel Quantity kg':r.get('certificate_quantity'),'Validation':r.get('validation_result'),'Workflow':r.get('status'),'Disposition':r.get('disposition'),'Decision Date':r.get('decision_at')} for r in filtered])
    st.dataframe(style_status_dataframe(df),hide_index=True,width='stretch',height=600)


def render_approval()->None:
    subpage_navigation(
        ('dashboard','Back to Dashboard',':material/arrow_back:'),
        ('rmtc-records','RMTC Records',':material/table_view:'),
        ('rmtc-part','Part Worksheets',':material/format_list_bulleted:'),
        ('inward-entry','Material Inward',':material/input:'),
    )
    page_header('RMTC · Validation & Decision','Submit, validate, then select Pending, On Hold, Accepted, Accepted Under Reserve or Rejected.','Controlled workflow')
    svc=RMTCService();repo=svc.repo;role=normalized_role(st.session_state.get('profile'));perms=current_permissions('RMTC_ENTRY')
    rows=svc.list();labels={str(r['id']):f"{r.get('rmtc_number')} · {r.get('heat_number')} · {str(r.get('status') or '').replace('_',' ').title()}" for r in rows}
    if not labels:st.info('No RMTC records available.');return
    default=str(st.session_state.get('part_rmtc_id') or '')
    rid=st.selectbox('RMTC for Review',list(labels),index=list(labels).index(default) if default in labels else 0,format_func=lambda x:labels[x])
    st.session_state['part_rmtc_id']=rid
    record=next(r for r in rows if str(r['id'])==rid);details=svc.details(rid);parts={str(p['id']):p for p in svc.parts()}
    workflow_progress(_workflow_steps(record,details['parts']))

    disposition_cards([
        {'label':'Workflow','value':record.get('status') or 'DRAFT','foot':'Draft → Approval Pending → Final'},
        {'label':'Validation','value':record.get('validation_result') or 'NOT_EVALUATED','foot':'Automated master comparison'},
        {'label':'Final Disposition','value':record.get('disposition') or 'PENDING','foot':'Controls Material Inward eligibility'},
        {'label':'Covered Parts','value':len(details['parts']),'foot':record.get('rmtc_number')},
    ])

    section_bar('PART VALIDATION & CONTROLLED DECISION','Automated results are read-only. Final disposition is selected independently for every Part Number.')
    decision_rows=[]
    for r in details['parts']:
        disposition=disposition_label(r.get('disposition') or 'PENDING')
        decision_rows.append({
            'Part Number':(parts.get(str(r.get('part_id'))) or {}).get('part_number'),
            'Automated Recommendation':r.get('approval_status'),
            'Source':r.get('source_status'),
            'Material Grade':r.get('material_grade_status'),
            'Raw Material':r.get('raw_material_status'),
            'Chemistry':r.get('chemistry_status'),
            'Jominy':r.get('jominy_status'),
            'Requirements':r.get('requirement_status'),
            'Actual DI Status':r.get('actual_di_status'),
            'Calculated DI Status':r.get('calculated_di_status'),
            'Final Decision':disposition,
            'Decision / Reserve Reason':r.get('decision_reason') or '',
            '_part_id':str(r.get('part_id')),
        })
    finalized=str(record.get('status')) in ('APPROVED','PARTIALLY_APPROVED','REJECTED')
    if finalized and role=='ADMIN':
        section_bar('ADMIN DECISION CONTROL')
        revisions=svc.decision_revisions(rid)
        reopen_reason=st.text_area(
            'Reason for reopening the final RMTC decision',height=70,
            placeholder='Mandatory: explain why the approved/rejected decision must be changed.',
            key=f'admin_reopen_reason_{rid}',
        )
        if st.button('Admin · Reopen Decision for Change',type='primary',disabled=not reopen_reason.strip(),width='stretch'):
            try:
                repo.rpc('qsms_admin_reopen_rmtc',{'p_rmtc_id':rid,'p_reason':reopen_reason.strip()})
                save_success_popup('RMTC reopened to Approval Pending. The administrator may now change and save the decisions.', queue_for_rerun=True);st.rerun()
            except Exception as exc: st.error(str(exc))
        if revisions:
            st.dataframe(pd.DataFrame([{
                'Reopened At':r.get('reopened_at'),'Reason':r.get('reason'),
                'Previous Status':r.get('previous_status'),'Previous Disposition':r.get('previous_disposition')
            } for r in revisions]),hide_index=True,width='stretch',height=min(240,70+len(revisions)*35))

    decision_grid=st.data_editor(
        pd.DataFrame(decision_rows),
        hide_index=True,
        width='stretch',
        height=max(250,min(520,85+len(decision_rows)*38)),
        disabled=True if finalized else [
            'Part Number','Automated Recommendation','Source','Material Grade','Raw Material','Chemistry','Jominy','Requirements','Actual DI Status','Calculated DI Status','_part_id'
        ],
        column_config={
            '_part_id':None,
            'Final Decision':st.column_config.SelectboxColumn(options=list(DISPOSITION_EDITOR_OPTIONS),required=True),
        },
        key=f'rmtc_decisions_{rid}_{record.get("updated_at")}',
    )

    validate_map=_employee_map(svc,'RMTC_VALIDATE');approve_map=_employee_map(svc,'RMTC_APPROVE')
    c=st.columns(2,gap='small')
    current_validator=str(record.get('validated_by_employee_id') or '')
    validator_options=['']+list(validate_map)
    validated=c[0].selectbox('Validated By',validator_options,index=validator_options.index(current_validator) if current_validator in validator_options else 0,format_func=lambda x:validate_map.get(x,'— Select Validator —'),disabled=finalized)
    current_approver=str(record.get('approved_by_employee_id') or record.get('decision_by_employee_id') or '')
    approver_options=['']+list(approve_map)
    approved=c[1].selectbox('Approved / Decided By',approver_options,index=approver_options.index(current_approver) if current_approver in approver_options else 0,format_func=lambda x:approve_map.get(x,'— Select Approver —'),disabled=finalized)

    can_approve=perms['can_approve'] or role in ('ADMIN','QUALITY_MANAGER','METLAB_APPROVER')
    workflow=st.columns(3,gap='small')
    submit_disabled=record.get('status')!='DRAFT' or not validated or not approved
    if workflow[0].button('1 · Submit for Validation',disabled=submit_disabled,width='stretch'):
        try:
            repo.update('rmtc_approvals',rid,{'validated_by_employee_id':validated,'approved_by_employee_id':approved})
            repo.rpc('qsms_submit_rmtc',{'p_rmtc_id':rid})
            save_success_popup('RMTC submitted and moved to Approval Pending.', queue_for_rerun=True);st.rerun()
        except Exception as exc:st.error(str(exc))

    validate_disabled=record.get('status')!='APPROVAL_PENDING' or not validated or finalized
    if workflow[1].button('2 · Validate Against Masters',disabled=validate_disabled,width='stretch'):
        try:
            repo.update('rmtc_approvals',rid,{'validated_by_employee_id':validated,'approved_by_employee_id':approved or None})
            repo.rpc('qsms_validate_rmtc',{'p_rmtc_id':rid})
            save_success_popup('RMTC validation completed. Select the final decision for every Part Number.', queue_for_rerun=True);st.rerun()
        except Exception as exc:st.error(str(exc))

    all_decided=all(normalize_disposition(row.get('Final Decision')) in ('PENDING','ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED') for _,row in decision_grid.iterrows())
    decision_disabled=(
        not can_approve or finalized or record.get('status')!='APPROVAL_PENDING'
        or not record.get('validated_at') or not approved or not all_decided
    )
    if workflow[2].button('3 · Save Decisions',type='primary',disabled=decision_disabled,width='stretch'):
        try:
            decisions=[]
            for _,row in decision_grid.iterrows():
                disposition=normalize_disposition(row.get('Final Decision'))
                reason=str(row.get('Decision / Reserve Reason') or '').strip()
                automated=str(row.get('Automated Recommendation') or '').upper()
                if disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE','REJECTED') and not reason:
                    raise ValueError(f"Reason is mandatory for {str(row.get('Part Number'))}: {disposition.replace('_',' ').title()}.")
                if disposition=='ACCEPTED' and automated!='APPROVED' and not reason:
                    raise ValueError(f"Manual acceptance reason is mandatory for {str(row.get('Part Number'))}.")
                decisions.append({'part_id':str(row.get('_part_id')),'disposition':disposition,'reason':reason or None})
            result=repo.rpc('qsms_decide_rmtc',{'p_rmtc_id':rid,'p_decisions':decisions,'p_approved_by_employee_id':approved})
            save_success_popup(f"RMTC decision saved as {str((result or {}).get('disposition') or '').replace('_',' ').title()}.", queue_for_rerun=True);st.rerun()
        except Exception as exc:st.error(str(exc))

    if finalized:
        st.success(f"Final disposition: {str(record.get('disposition') or '').replace('_',' ').title()}")
