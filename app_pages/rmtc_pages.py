from __future__ import annotations

import re
import uuid
from difflib import SequenceMatcher
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st
from core.ui import portal_table

from core.access import current_permissions
from core.password_edit import password_reopen_for_edit
from core.attachments import MICROSTRUCTURE_IMAGE_TYPES, AttachmentService, AttachmentSlot, new_attachment_uploaders, render_attachment_manager
from core.delete_service import password_delete_panel
from core.calculations import band_status, calculate_di, calculate_jominy_curve
from core.permissions import normalized_role
from core.rmtc_service import RMTCService
from core.notification_service import NotificationService
from core.notification_ui import notification_confirmation, notification_overrides, record_email_sender
from core.reporting import rmtc_record_pdf_bytes
from core.selection_labels import employee_label, part_label, party_label
from core.steel_balance import remaining_planned_steel
from core.ui import (DISPOSITION_EDITOR_OPTIONS, disposition_cards, disposition_label, normalize_disposition, page_header, save_success_popup, section_bar, stage_section, style_status_dataframe, subpage_navigation, template_download_row, workflow_progress)

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
    def _norm_text(value: Any) -> str:
        return ' '.join(re.findall(r'[a-z0-9]+', str(value or '').casefold()))
    expected=_norm_text(req); actual_text=_norm_text(text)
    expected_tokens=set(expected.split()); actual_tokens=set(actual_text.split())
    sequence_score=SequenceMatcher(None,expected,actual_text).ratio() if expected and actual_text else 0.0
    token_score=(len(expected_tokens & actual_tokens)/len(expected_tokens)) if expected_tokens else 0.0
    return 'PASS' if max(sequence_score,token_score)>=0.75 else 'FAIL'


def _employee_map(svc:RMTCService,authority:str)->dict[str,str]:
    return _opts(svc.employees(authority),lambda r:employee_label(r))


def _part_maps(svc:RMTCService):
    rows=svc.parts();return rows,_opts(rows,lambda r:part_label(r))


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
    """Open a genuinely new certificate while preserving only the Heat identity.

    The previous Existing-RMTC selector is explicitly cleared so Streamlit widget state
    cannot make the new certificate appear to still be the old RMTC. Certificate number,
    QCMS RMTC number and covered-part widget values get fresh keys through the nonce.
    """
    st.session_state['rmtc_entry_mode'] = 'new'
    st.session_state['rmtc_heat_search'] = str(heat_number or '').strip()
    st.session_state['rmtc_same_heat_create_mode'] = bool(str(heat_number or '').strip())
    st.session_state['rmtc_same_heat_target'] = str(heat_number or '').strip()
    if str(heat_number or '').strip():
        st.session_state['rmtc_new_tc_flash'] = f"New RMTC / TC entry opened for Heat {str(heat_number).strip()}. Enter a new Supplier RMTC Number and this certificate quantity below."
    st.session_state['rmtc_new_form_nonce'] = int(st.session_state.get('rmtc_new_form_nonce') or 0) + 1
    # Clear every previous certificate/header widget value.  Only the Heat identity is
    # deliberately retained for same-Heat TC creation.  Dynamic nonce keys prevent
    # Streamlit from reusing the old certificate's covered Parts, Supplier TC, source,
    # quantity, prepared-by employee or dates.
    for key in list(st.session_state):
        if key in ('edit_rmtc_id', 'part_rmtc_id', 'rmtc_part_choice', 'new_rmtc_number') or str(key).startswith(('rmtc_direct_edit_selector_', 'rmtc_parts_','rmtc_no_','rmtc_cert_ref_','rmtc_source_','rmtc_mill_','rmtc_qty_','rmtc_prepared_','rmtc_entry_date_','rmtc_cert_date_','rmtc_heat_code_','rmtc_section_','rmtc_route_','rmtc_remarks_','rmtc_micro_title_')):
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
                    type=MICROSTRUCTURE_IMAGE_TYPES,
                    key=f'rmtc_micro_photo_{slot}_{form_token}',
                )
    return uploads, titles

def render_entry()->None:
    subpage_navigation(('masters','Back to Masters',':material/arrow_back:'),('rmtc-records','RMTC Records',':material/table_view:'))
    page_header('RMTC Entry · Header','Create or edit the certificate header, heat, source, covered parts and RMTC attachment.','Step 1')
    template_download_row([('RMTC_Entry_Template.xlsx', 'Download RMTC Entry Template')], key_prefix='rmtc_entry')
    svc=RMTCService();repo=svc.repo;perms=current_permissions('RMTC_ENTRY')
    # DIRECT RMTC EDIT SELECTOR v4.14.5
    section_bar('NEW / EDIT EXISTING RMTC')
    rmtc_rows=svc.list()
    rmtc_labels={'':'— Create New RMTC —'}
    rmtc_labels.update({str(row.get('id')):f"{row.get('rmtc_number') or '-'} · Heat {row.get('heat_number') or '-'} · {row.get('status') or '-'}" for row in rmtc_rows if row.get('id')})
    rmtc_ids=list(rmtc_labels)
    current_edit_id=str(st.session_state.get('edit_rmtc_id') or '')
    selector_nonce=int(st.session_state.get('rmtc_new_form_nonce') or 0)
    selector_key=f'rmtc_direct_edit_selector_{selector_nonce}'
    chosen_rmtc=st.selectbox(
        'Select Existing RMTC to Edit', rmtc_ids,
        index=rmtc_ids.index(current_edit_id) if current_edit_id in rmtc_ids and st.session_state.get('rmtc_entry_mode')=='edit' else 0,
        format_func=lambda value:rmtc_labels[value], key=selector_key,
    )
    re1,re2=st.columns(2,gap='small')
    if re1.button('Load Selected RMTC for Edit',type='primary',width='stretch',disabled=not chosen_rmtc or not perms['can_edit'],key='rmtc_direct_edit_load'):
        st.session_state['edit_rmtc_id']=chosen_rmtc;st.session_state['rmtc_entry_mode']='edit';st.rerun()
    if re2.button('Start New RMTC',width='stretch',key='rmtc_direct_edit_new'):
        _start_new_rmtc_for_heat('');st.rerun()
    if not perms['can_edit']:
        st.caption('Your user does not currently have RMTC Edit permission. Administrator role is not required; module Edit permission is required.')
    if st.session_state.get('rmtc_entry_mode')!='edit':
        st.session_state.pop('edit_rmtc_id',None)
    existing=_header_record(svc) if st.session_state.get('rmtc_entry_mode')=='edit' else {}
    form_token=str(existing.get('id') or f"new_{int(st.session_state.get('rmtc_new_form_nonce') or 0)}")
    existing_parts_rows=svc.covered_parts(str(existing.get('id'))) if existing else []
    workflow_progress(_workflow_steps(existing,existing_parts_rows))
    if existing and str(existing.get('status') or 'DRAFT').upper() != 'DRAFT':
        section_bar('EDIT SELECTED RMTC')
        password_reopen_for_edit(
            repo=svc.repo, table='rmtc_approvals', record=existing, entity_type='RMTC', can_edit=perms['can_edit'],
            key=f"rmtc_password_edit_top_{existing.get('id')}", title='Edit Approved / Final RMTC with Password',
        )
    elif existing:
        st.success(f"Editing RMTC {existing.get('rmtc_number') or existing.get('id')}. Draft header fields are editable with your assigned RMTC Edit permission.")

    with stage_section("A", 'HEAT NUMBER SEARCH', 'Search the Heat Number first. The same Heat may be reused only with a different Supplier RMTC Number.', key="rmtc_pages_render_entry_a"):
        default_heat=str(existing.get('heat_number') or st.session_state.get('rmtc_heat_search') or '')
        h1,h2=st.columns([4,1],gap='small')
        heat_search=h1.text_input('Search / Enter Heat Number',value=default_heat,placeholder='Enter supplier Heat Number',key=f"rmtc_heat_search_input_{form_token}")
        if h2.button('Search Heat',icon=':material/search:',width='stretch'):
            st.session_state['rmtc_heat_search']=heat_search.strip();st.rerun()
        heat_search=heat_search.strip()
        heat_summary=svc.heat_summary(heat_search) if heat_search else {}
        heat_usage=svc.heat_usage(heat_search) if heat_search else []
        if heat_search:
            st.markdown("**GLOBAL HEAT QUANTITY BALANCE & RECORD LIST**")
            st.caption("One Heat Number shares one global steel quantity. The balance and every linked RMTC/Part allocation are shown below.")
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
                portal_table(style_status_dataframe(usage_df[show]),width='stretch',hide_index=True,height=min(360,80+len(usage_df)*36))
        elif heat_search:
            st.caption('New Heat Number. The steel quantity entered below becomes the global Heat steel quantity.')

        canonical_heat_code=svc.canonical_heat_code(heat_search) if heat_summary else ''
        if heat_summary and canonical_heat_code:
            st.info(
                f"Existing Heat detected · Internal Heat Code {canonical_heat_code}. "
                "You can create another QCMS RMTC for the same Heat when the Supplier RMTC Number is different. "
                "The new RMTC will share this Heat Code and the same global Heat steel balance, and can be selected independently in Material Inward after approval."
            )

        if heat_summary:
            hb1,hb2=st.columns(2,gap='small')
            hb1.button(
                'Add New RMTC for This Heat Number', icon=':material/add_circle:', type='primary', width='stretch',
                key=f'new_rmtc_same_heat_{form_token}', on_click=_start_new_rmtc_for_heat, args=(heat_search,),
                help='Starts a separate Supplier TC/RMTC for this Heat. Only the Heat identity and canonical Heat Code are reused; certificate fields are reset.'
            )
            if hb2.button('Open Heat Steel Ledger',icon=':material/table_view:',width='stretch',key=f'open_heat_ledger_{form_token}'):
                st.session_state['heat_ledger_filter']=heat_search
                st.switch_page(st.session_state['_qsms_pages']['heat-ledger'])

        if existing and st.button('Start New RMTC',icon=':material/add:',width='content'):
            _start_new_rmtc_for_heat(heat_search)
            st.rerun()
        writable=(perms['can_edit'] if existing else perms['can_create']) and (not existing or str(existing.get('status') or 'DRAFT').upper()=='DRAFT')
        parts,part_map=_part_maps(svc)
        if not parts:st.warning('Create an active Part Master first.');return
        existing_parts=[str(row.get('part_id')) for row in existing_parts_rows] if existing else []
    with stage_section("B", 'CERTIFICATE & COVERED PARTS', 'Multiple parts are selected here and completed on separate Part Worksheet pages.', key="rmtc_pages_render_entry_b"):
        if st.session_state.get('rmtc_new_tc_flash') and not existing and st.session_state.get('rmtc_same_heat_create_mode'):
            st.success(f"NEW RMTC / TC MODE ACTIVE for Heat {heat_search}. This is a BLANK NEW certificate; the previous RMTC is not being edited.")
        if not existing and st.session_state.get('rmtc_same_heat_create_mode') and heat_summary:
            st.info(
                f"NEW RMTC / TC for existing Heat **{heat_search}**. QCMS will reuse Internal Heat Code **{canonical_heat_code or '-'}** "
                "and the existing global Heat quantity. Enter a NEW Supplier RMTC / TC Number; the previous certificate record remains unchanged and both can be used independently in Material Inward after approval."
            )
        selected_parts=st.multiselect('Part Numbers Covered by this Heat',list(part_map),default=existing_parts,format_func=lambda x:part_map[x],max_selections=30,key=f'rmtc_parts_{form_token}')
        primary_id=selected_parts[0] if selected_parts else str(existing.get('part_id') or next(iter(part_map)))
        sources=svc.source_details(primary_id)
        suppliers=svc.parties('SUPPLIER');mills=svc.parties('STEEL_MILL')
        supplier_map=_opts(suppliers,lambda r:party_label(r));mill_map=_opts(mills,lambda r:party_label(r))
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
        heat_code_default=str(existing.get('heat_code') or canonical_heat_code or '')
        heat_code=c[3].text_input(
            'Internal Heat Code', value=heat_code_default,
            placeholder='Auto on save: Steel Mill initial-0001',
            disabled=bool(canonical_heat_code and not existing),
            help='For an existing Heat Number, QCMS reuses the established Internal Heat Code across all Supplier RMTC certificates.',
            key=f'rmtc_heat_code_{form_token}',
        )
        c=st.columns(4,gap='small')
        heat_global_qty=float(heat_summary.get('global_steel_quantity_kg') or 0) if heat_summary else 0.0
        same_heat_new = bool((not existing) and st.session_state.get('rmtc_same_heat_create_mode') and heat_summary)
        # A second Supplier TC for an existing Heat contributes its own certified quantity
        # to the shared Heat ledger.  Do not reuse/lock the existing Heat total as the new
        # certificate quantity; that previously made the Add New RMTC action look inert and
        # could double-count the old certificate if saved unchanged.
        qty_default=float(existing.get('certificate_quantity') or (0.0 if same_heat_new else heat_global_qty) or 0)
        qty_label='New RMTC / TC Certified Quantity (kg)' if same_heat_new else 'Global Heat Steel Quantity (kg)'
        qty=c[0].number_input(qty_label,min_value=0.0,value=qty_default,step=1.0,disabled=bool(heat_summary and not same_heat_new and not existing),key=f'rmtc_qty_{form_token}',help=('Enter only the quantity certified on this NEW Supplier RMTC/TC. QCMS adds it to the shared global Heat quantity.' if same_heat_new else None))
        if same_heat_new:
            st.caption(f"Existing Heat balance before this TC: {heat_global_qty:,.3f} kg certified. The quantity entered above will be added as a separate certificate allocation after save/approval.")
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
                    final_heat_code=canonical_heat_code or heat_code.strip() or svc.next_heat_code(steel_id)
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
                st.session_state.pop('rmtc_same_heat_create_mode',None)
                st.session_state.pop('rmtc_same_heat_target',None)
                st.session_state.pop('rmtc_new_tc_flash',None)
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
            st.markdown("**RMTC Workflow**")
            validator_map=_employee_map(svc,'RMTC_VALIDATE');approver_map=_employee_map(svc,'RMTC_APPROVE')
            validator_options=['']+list(validator_map);approver_options=['']+list(approver_map)
            current_validator=str(existing.get('validated_by_employee_id') or '')
            current_approver=str(existing.get('approved_by_employee_id') or '')
            w1,w2,w3,w4=st.columns([1,1.4,1.4,1.25],gap='small')
            w1.text_input('Current Status',value=str(existing.get('status') or 'DRAFT').replace('_',' ').title(),disabled=True)
            validator=w2.selectbox('Validator',validator_options,index=validator_options.index(current_validator) if current_validator in validator_options else 0,format_func=lambda x:validator_map.get(x,'— Select —'),key=f'entry_validator_{existing.get("id")}')
            approver=w3.selectbox('Approver',approver_options,index=approver_options.index(current_approver) if current_approver in approver_options else 0,format_func=lambda x:approver_map.get(x,'— Select —'),key=f'entry_approver_{existing.get("id")}')
            rmtc_entry_notify_pref = notification_confirmation(NotificationService(repo), 'RMTC_APPROVAL_PENDING', key=f"rmtc_entry_notify_{existing.get('id')}", context={'rmtc_id':str(existing.get('id')),'next_task':'RMTC Approval'}, default_send=str(existing.get('status'))=='DRAFT') if str(existing.get('status'))=='DRAFT' else {'send':False,'confirmed':True,'preview':{}}
            if str(existing.get('status'))=='DRAFT':
                if w4.button('Submit Draft → Pending',type='primary',disabled=not validator or not approver or (rmtc_entry_notify_pref['send'] and not rmtc_entry_notify_pref['confirmed']),width='stretch'):
                    try:
                        repo.update('rmtc_approvals',str(existing['id']),{'validated_by_employee_id':validator,'approved_by_employee_id':approver})
                        repo.rpc('qsms_submit_rmtc',{'p_rmtc_id':str(existing['id'])})
                        if rmtc_entry_notify_pref['send'] and rmtc_entry_notify_pref['confirmed']:
                            NotificationService(repo).notify(
                                'RMTC_APPROVAL_PENDING',
                            subject=f"QCMS · RMTC approval pending · {existing.get('rmtc_number')}",
                            body_text=(f"RMTC {existing.get('rmtc_number')} is pending validation / approval.\n"
                                       f"Heat Number: {existing.get('heat_number') or '-'}\n"
                                       f"Supplier RMTC: {existing.get('certificate_reference') or '-'}"),
                            related_table='rmtc_approvals', related_id=str(existing['id']),
                            context={'rmtc_id':str(existing['id']),'next_task':'RMTC Approval'},
                            **notification_overrides(rmtc_entry_notify_pref),
                        )
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


    if existing and str(existing.get('status') or '') in ('APPROVED','PARTIALLY_APPROVED') and str(existing.get('disposition') or '') in ('ACCEPTED','ACCEPTED_UNDER_RESERVE'):
        with stage_section("C", 'ADD PART NUMBER TO APPROVED RMTC', 'Add another compatible Part Number to this already-approved RMTC. Existing approved Parts remain available for production while only the new Part goes through worksheet / validation / decision.', key=f"rmtc_add_part_{existing.get('id')}"):
            covered_ids={str(row.get('part_id')) for row in svc.covered_parts(str(existing['id']))}
            compatible=[row for row in svc.parts() if str(row.get('id')) not in covered_ids and str(row.get('material_grade_id') or '')==str(existing.get('material_grade_id') or '')]
            if compatible:
                compat_map={str(row['id']):part_label(row) for row in compatible}
                add_part_id=st.selectbox('New Part Number for this RMTC',list(compat_map),format_func=lambda value:compat_map[value],key=f"rmtc_add_part_select_{existing.get('id')}")
                heat_bal=svc.heat_summary(str(existing.get('heat_number') or '')) or {}
                portal_table(pd.DataFrame([{
                    'RMTC':existing.get('rmtc_number'),'Heat Number':existing.get('heat_number'),
                    'RMTC Steel Qty kg':existing.get('certificate_quantity'),
                    'Inward Used kg':heat_bal.get('inward_steel_quantity_kg'),
                    'Available / Unallocated kg':heat_bal.get('available_unallocated_steel_quantity_kg') or heat_bal.get('available_steel_quantity_kg'),
                }]),hide_index=True,width='stretch',height=105)
                added_part_notify_pref = notification_confirmation(NotificationService(repo), 'RMTC_APPROVAL_PENDING', key=f"rmtc_added_part_notify_{existing.get('id')}", context={'rmtc_id':str(existing.get('id')),'part_id':str(add_part_id),'next_task':'Added Part Worksheet / RMTC Approval'}, default_send=True)
                if st.button('Add Part Number to Approved RMTC',type='primary',width='stretch',disabled=not perms['can_edit'] or (added_part_notify_pref['send'] and not added_part_notify_pref['confirmed']),key=f"rmtc_add_part_button_{existing.get('id')}"):
                    try:
                        svc.add_part_to_approved_rmtc(str(existing['id']),add_part_id)
                        if added_part_notify_pref['send'] and added_part_notify_pref['confirmed']:
                            NotificationService(repo).notify(
                                'RMTC_APPROVAL_PENDING',
                                subject=f"QCMS · Added Part worksheet pending · {existing.get('rmtc_number')}",
                            body_text=f"A new Part Number was added to approved RMTC {existing.get('rmtc_number')}. Complete its Part Worksheet, validation and final decision.",
                            related_table='rmtc_approvals',related_id=str(existing['id']),context={'rmtc_id':str(existing['id']),'part_id':str(add_part_id),'next_task':'Added Part Worksheet / RMTC Approval'},
                            **notification_overrides(added_part_notify_pref),
                        )
                        st.session_state['part_rmtc_id']=str(existing['id']); st.session_state['rmtc_part_choice']=add_part_id
                        save_success_popup('Part Number added to the approved RMTC. Complete the new Part Worksheet and validation; previously accepted Parts remain released.',queue_for_rerun=True)
                        st.switch_page(st.session_state['_qsms_pages']['rmtc-part'])
                    except Exception as exc: st.error(str(exc))
            else:
                st.info('No additional active Part with the same Material Grade is available to add to this RMTC.')



def render_approved_part_worksheet()->None:
    subpage_navigation(('rmtc-entry','RMTC Entry',':material/fact_check:'),('rmtc-part','Part Worksheet',':material/format_list_bulleted:'),('rmtc-approval','Validation & Decision',':material/approval:'))
    page_header('Approved RMTC · Add Part Worksheet','Extend an already Accepted RMTC to another compatible Part Number while existing approved Parts remain released for production.','RMTC')
    svc=RMTCService(); perms=current_permissions('RMTC_ENTRY')
    parts={str(p['id']):p for p in svc.parts()}
    records=[r for r in svc.list() if str(r.get('status') or '') in ('APPROVED','PARTIALLY_APPROVED') and str(r.get('disposition') or '') in ('ACCEPTED','ACCEPTED_UNDER_RESERVE')]
    labels={str(r['id']):f"{r.get('rmtc_number')} · Heat {r.get('heat_number')} · {r.get('certificate_quantity') or 0} kg · {str(r.get('disposition') or '').replace('_',' ').title()}" for r in records}
    if not labels:
        st.info('No Accepted / Accepted Under Reserve RMTC is available to extend to another Part Number.'); return
    rid=st.selectbox('Approved RMTC',list(labels),format_func=lambda v:labels[v],key='approved_rmtc_worksheet_header')
    header=svc.get(rid) or {}; covered=svc.covered_parts(rid); covered_ids={str(r.get('part_id')) for r in covered}
    heat_bal=svc.heat_summary(str(header.get('heat_number') or '')) or {}
    with stage_section('A','APPROVED RMTC & GLOBAL HEAT BALANCE','The original heat/certificate remains unchanged. New Part Worksheets share the same RMTC steel balance and may use the same approved Heat until its global balance is consumed.',key='approved_rmtc_balance'):
        portal_table(pd.DataFrame([{
            'RMTC':header.get('rmtc_number'),'Heat Number':header.get('heat_number'),'Material Grade':(svc.repo.get('material_grades',str(header.get('material_grade_id') or '')) or {}).get('grade_code'),
            'RMTC Steel Qty kg':header.get('certificate_quantity'),'Inward Used kg':heat_bal.get('inward_steel_quantity_kg'),
            'Available / Unallocated kg':heat_bal.get('available_unallocated_steel_quantity_kg') or heat_bal.get('available_steel_quantity_kg'),
            'Covered Parts':len(covered),'Status':header.get('disposition'),
        }]),hide_index=True,width='stretch')
    with stage_section('B','CURRENT COVERED PART WORKSHEETS','Existing approved Part Worksheets remain valid and are not reset when another compatible Part is added.',key='approved_rmtc_current_parts'):
        rows=[]
        for row in covered:
            part=parts.get(str(row.get('part_id'))) or {}
            rows.append({'Part Number':part.get('part_number'),'FSI Part Number':part.get('fsi_part_number'),'Part Description':part.get('part_name'),'Worksheet': 'COMPLETED' if row.get('worksheet_completed_at') else 'PENDING','Automated Validation':row.get('approval_status'),'Final Decision':row.get('disposition'),'Planned pcs':row.get('planned_production_quantity_pcs'),'Planned Steel kg':row.get('planned_steel_quantity_kg')})
        portal_table(style_status_dataframe(pd.DataFrame(rows)),hide_index=True,width='stretch',height=min(420,100+38*max(len(rows),1)))
    with stage_section('C','ADD NEW PART WORKSHEET','Only active Parts with the same Material Grade and not already covered are offered. The new Part then opens in the normal Part Worksheet module for its Part-specific plan and validation.',key='approved_rmtc_add_part'):
        compatible=[p for p in parts.values() if str(p.get('id')) not in covered_ids and str(p.get('material_grade_id') or '')==str(header.get('material_grade_id') or '')]
        if not compatible:
            st.info('No additional active Part with the same Material Grade is available.')
        else:
            compat={str(p['id']):part_label(p) for p in compatible}
            part_id=st.selectbox('New Part Number / FSI Part Number',list(compat),format_func=lambda v:compat[v],key='approved_rmtc_new_part')
            selected=parts.get(part_id) or {}
            portal_table(pd.DataFrame([{'Part Number':selected.get('part_number'),'FSI Part Number':selected.get('fsi_part_number'),'Part Description':selected.get('part_name'),'Material Grade':(svc.repo.get('material_grades',str(selected.get('material_grade_id') or '')) or {}).get('grade_code'),'Drawing':selected.get('drawing_number'),'Revision':selected.get('drawing_revision')}]),hide_index=True,width='stretch')
            if st.button('Add Part Worksheet to Approved RMTC',type='primary',width='stretch',disabled=not perms['can_edit']):
                try:
                    svc.add_part_to_approved_rmtc(rid,part_id)
                    st.session_state['part_rmtc_id']=rid; st.session_state['rmtc_part_choice']=part_id
                    save_success_popup('New Part Worksheet added to the approved RMTC. Existing accepted Parts remain released. Complete the new worksheet and validation for this Part.',queue_for_rerun=True)
                    st.switch_page(st.session_state['_qsms_pages']['rmtc-part'])
                except Exception as exc: st.error(str(exc))

    # v4.14.0: added Parts can be validated and decided without reopening/resetting
    # the already accepted Parts on the same RMTC.
    covered=svc.covered_parts(rid)
    pending_parts=[r for r in covered if str(r.get('disposition') or 'PENDING') not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE')]
    with stage_section('D','VALIDATE & DECIDE ADDED PART WORKSHEET','Validate only the newly added Part against its Part Master requirements, then save its independent final decision. Existing accepted Parts remain released.',key='approved_rmtc_validate_added'):
        if not pending_parts:
            st.success('All covered Part Worksheets already have a released final decision.')
        else:
            pending_labels={str(r.get('part_id')):part_label(parts.get(str(r.get('part_id'))) or {}) for r in pending_parts}
            validate_part_id=st.selectbox('Added Part Worksheet Pending Decision',list(pending_labels),format_func=lambda v:pending_labels[v],key='approved_rmtc_validate_part')
            pending_row=next(r for r in pending_parts if str(r.get('part_id'))==validate_part_id)
            part=parts.get(validate_part_id) or {}
            portal_table(pd.DataFrame([{
                'Part Number':part.get('part_number'),'FSI Part Number':part.get('fsi_part_number'),'Worksheet':'COMPLETED' if pending_row.get('worksheet_completed_at') else 'PENDING',
                'Automated Validation':pending_row.get('approval_status'),'Source':pending_row.get('source_status'),'Material Grade':pending_row.get('material_grade_status'),'Raw Material':pending_row.get('raw_material_status'),
                'Chemistry':pending_row.get('chemistry_status'),'Jominy':pending_row.get('jominy_status'),'Requirements':pending_row.get('requirement_status'),'Current Decision':pending_row.get('disposition')
            }]),hide_index=True,width='stretch')
            c=st.columns(2,gap='small')
            if c[0].button('1 · Validate Added Part Against Masters',type='primary',width='stretch',disabled=not perms['can_edit'] or not pending_row.get('worksheet_completed_at')):
                try:
                    result=svc.validate_added_part(rid,validate_part_id)
                    save_success_popup(f"Added Part validation completed · Recommendation {result.get('approval_status') or result.get('recommendation') or 'updated'}.",queue_for_rerun=True);st.rerun()
                except Exception as exc:st.error(str(exc))
            if c[1].button('Open Part Worksheet',width='stretch'):
                st.session_state['part_rmtc_id']=rid;st.session_state['rmtc_part_choice']=validate_part_id;st.switch_page(st.session_state['_qsms_pages']['rmtc-part'])

            # Final decision controls appear after the worksheet exists; manual decision is independent of automated recommendation.
            employees=[e for e in svc.repo.select('employees',eq={'status':'ACTIVE'},order_by='first_name',limit=2000) if 'RMTC_APPROVE' in (e.get('approval_authorities') or [])]
            emp_labels={str(e.get('id')):f"{e.get('employee_code')} · {e.get('first_name')} {e.get('last_name')} · {e.get('designation') or ''}" for e in employees}
            dcols=st.columns(2,gap='small')
            disposition=dcols[0].selectbox('Final Decision',['PENDING','ACCEPTED','ACCEPTED_UNDER_RESERVE','ON_HOLD','REJECTED'],key='approved_rmtc_added_disposition')
            approver=dcols[1].selectbox('Approved / Decided By',['']+list(emp_labels),format_func=lambda v:emp_labels.get(v,'— Select RMTC Approver —'),key='approved_rmtc_added_approver')
            reason=st.text_area('Decision / Reserve / Hold / Rejection Reason',height=75,key='approved_rmtc_added_reason')
            decision_disabled=not perms.get('can_approve',False) or disposition=='PENDING' or not approver or not pending_row.get('worksheet_completed_at')
            if st.button('2 · Save Added Part Final Decision',type='primary',width='stretch',disabled=decision_disabled):
                try:
                    svc.decide_added_part(rid,validate_part_id,disposition,reason.strip() or None,approver)
                    save_success_popup('Added Part final decision saved. Existing accepted Part releases were not changed.',queue_for_rerun=True);st.rerun()
                except Exception as exc:st.error(str(exc))


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
    labels={str(row.get('part_id')):part_label(parts.get(str(row.get('part_id'))) or {}) for row in part_rows}
    if not labels:st.warning('No covered parts exist.');return
    preferred=str(st.session_state.get('rmtc_part_choice') or '')
    part_id=st.selectbox('Part Worksheet',list(labels),index=list(labels).index(preferred) if preferred in labels else 0,format_func=lambda x:labels[x])
    st.session_state['rmtc_part_choice']=part_id
    part=parts[part_id];part_approval=next(row for row in part_rows if str(row.get('part_id'))==part_id)
    grade_id=part.get('material_grade_id');grade=(repo.select('material_grades',eq={'id':grade_id},limit=1) or [{}])[0]
    existing=svc.details(rid,part_id)
    writable=perms['can_edit'] or perms['can_create']
    with stage_section("A", 'PART & MATERIAL', 'Each selected part is a separate controlled worksheet.', key="rmtc_pages_render_part_a"):
        portal_table(pd.DataFrame([{'RMTC':header.get('rmtc_number'),'Heat Number':header.get('heat_number'),'Internal Heat Code':header.get('heat_code'),'Part Number':part.get('part_number'),'FSI Part Number':part.get('fsi_part_number'),'Part Description':part.get('part_name'),'Material Grade':grade.get('grade_code'),'Status':header.get('status')}]),hide_index=True,width='stretch')

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
    with stage_section("B", 'PRODUCTION PLAN', 'Committed Heat steel equals inward steel already used plus the still-unconsumed portion of every active part plan.', key="rmtc_pages_render_part_b"):
        pcols=st.columns(4,gap='small')
        planned_production_qty=float(pcols[0].number_input('Part Production Quantity (pcs)', min_value=float(0.0), value=float(planned_existing or 0.0), step=float(1.0), key=f'planned_pcs_{rid}_{part_id}'))
        pcols[1].number_input('Input Weight (kg/part)', min_value=float(0.0), value=float(input_weight or 0.0), step=float(0.001), format='%.3f', disabled=True, key=f'plan_weight_{rid}_{part_id}')
        planned_steel=round(float(planned_production_qty)*float(input_weight or 0.0),3)
        pcols[2].number_input('Planned Steel Quantity (kg)', min_value=float(0.0), value=float(planned_steel or 0.0), step=float(0.001), format='%.3f', disabled=True, key=f'planned_steel_{rid}_{part_id}')
        projected_current_remaining=float(remaining_planned_steel(planned_steel,current_part_inward_steel) or 0.0)
        projected_commitment=round(float(max(float(current_heat_commitment or 0.0)-float(current_existing_remaining or 0.0),0.0))+projected_current_remaining,3)
        heat_remaining=float(max(float(global_heat_steel or 0.0)-float(projected_commitment or 0.0),0.0))
        pcols[3].number_input('Heat Steel Balance after Plan (kg)', min_value=float(0.0), value=float(heat_remaining or 0.0), step=float(0.001), format='%.3f', disabled=True, key=f'plan_balance_{rid}_{part_id}')
        st.caption(
            f"Projected committed Heat steel: {projected_commitment:,.3f} kg = Inward {heat_inward_steel:,.3f} kg + "
            f"Remaining active plans {max(projected_commitment-heat_inward_steel,0.0):,.3f} kg."
        )
        plan_exceeds_heat=projected_commitment>global_heat_steel+0.001
        if input_weight<=0:
            st.error('Input Weight is missing in Part Master supplier forging parameters.')
        elif plan_exceeds_heat:
            st.error(f"Committed Heat steel {projected_commitment:,.3f} kg exceeds the Global Heat steel quantity {global_heat_steel:,.3f} kg.")

    with stage_section("C", 'CHEMICAL COMPOSITION', 'Limits come from this Part Master material grade. Actual values are entered from the RMTC.', key="rmtc_pages_render_part_c"):
        templates=svc.chemistry_template(grade_id);existing_chem={str(r.get('material_grade_element_id')):r for r in existing['chemistry']}
        chem_df=pd.DataFrame([{'Element':t.get('element'),'Minimum %':t.get('minimum'),'Maximum %':t.get('maximum'),'Actual %':(existing_chem.get(str(t.get('id'))) or {}).get('actual_value'),'Applicable':(existing_chem.get(str(t.get('id'))) or {}).get('result')!='NOT_APPLICABLE','Status':(existing_chem.get(str(t.get('id'))) or {}).get('result') or 'NOT_EVALUATED','_id':t.get('id'),'Unit':t.get('unit') or '%'} for t in templates])
        chem_edit=st.data_editor(chem_df,hide_index=True,width='stretch',height=350,disabled=['Element','Minimum %','Maximum %','Status','_id','Unit'],column_config={'_id':None,'Actual %':st.column_config.NumberColumn(format='%.4f')},key=f"chem_part_{rid}_{part_id}")
        chemistry_rows=[];chemistry_map={}
        for _,row in chem_edit.iterrows():
            applicable=bool(row.get('Applicable'));actual=None if pd.isna(row.get('Actual %')) else row.get('Actual %');status=band_status(actual,row.get('Minimum %'),row.get('Maximum %'),applicable)
            chemistry_rows.append({'material_grade_element_id':row['_id'],'element':row['Element'],'minimum_value':row['Minimum %'],'maximum_value':row['Maximum %'],'actual_value':actual,'unit':row['Unit'],'result':status})
            if applicable and actual is not None:chemistry_map[str(row['Element'])]=actual
        calculated_curve=calculate_jominy_curve(chemistry_map)

    with stage_section("D", 'JOMINY RESULTS', 'Single grid with Actual Jominy, Actual Status, Calculated Jominy and Calculated Status.', key="rmtc_pages_render_part_d"):
        jtemplates=svc.jominy_template(part_id);existing_j={str(r.get('jominy_distance_id')):r for r in existing['jominy']}
        jrows=[]
        for t in jtemplates:
            old=existing_j.get(str(t.get('jominy_distance_id'))) or {};distance=int(t.get('distance_16th') or 0);applicable=old.get('applicability','APPLICABLE')!='NOT_APPLICABLE';calc=calculated_curve.get(distance) if applicable else None
            jrows.append({'Distance':t.get('distance_label'),'MM':t.get('distance_mm'),'Min HRC':t.get('minimum_hrc'),'Max HRC':t.get('maximum_hrc'),'Actual Jominy':old.get('actual_hrc'),'Actual Jominy Status':band_status(old.get('actual_hrc'),t.get('minimum_hrc'),t.get('maximum_hrc'),applicable),'Calculated Jominy':calc,'Calculated Jominy Status':band_status(calc,t.get('minimum_hrc'),t.get('maximum_hrc'),applicable),'Applicable':applicable,'_distance_id':t.get('jominy_distance_id'),'_distance_16th':distance})
        jedit=st.data_editor(pd.DataFrame(jrows),hide_index=True,width='stretch',height=360,disabled=['Distance','MM','Min HRC','Max HRC','Actual Jominy Status','Calculated Jominy','Calculated Jominy Status','_distance_id','_distance_16th'],column_config={'_distance_id':None,'_distance_16th':None,'Actual Jominy':st.column_config.NumberColumn(format='%.3f')},key=f"jom_part_{rid}_{part_id}")
        jominy_rows=[{'jominy_distance_id':row['_distance_id'],'distance_label':row['Distance'],'distance_mm':row['MM'],'distance_16th':row['_distance_16th'],'minimum_hrc':row['Min HRC'],'maximum_hrc':row['Max HRC'],'actual_hrc':None if pd.isna(row['Actual Jominy']) else row['Actual Jominy'],'applicability':'APPLICABLE' if bool(row['Applicable']) else 'NOT_APPLICABLE'} for _,row in jedit.iterrows()]

    with stage_section("E", 'DI VALUE', 'Actual and calculated DI use the supplied DI Hardenability workbook factor table.', key="rmtc_pages_render_part_e"):
        grain=st.selectbox('Grain Size (ASTM E-112)',[4,5,6,7,8],index=[4,5,6,7,8].index(int(part_approval.get('grain_size') or 6)))
        di_applicable=st.checkbox('DI Applicable',value=str(part_approval.get('calculated_di_status') or '')!='NOT_APPLICABLE')
        actual_di=st.number_input('Actual DI',min_value=0.0,value=float(part_approval.get('actual_di') or 0),step=0.01,disabled=not di_applicable)
        di_calc=calculate_di(chemistry_map,grain) if di_applicable else {'value':None,'error':None,'factors':{}}
        portal_table(pd.DataFrame([{'Grain Size':grain,'Actual DI':actual_di if di_applicable else None,'Calculated DI':di_calc.get('value'),'Calculation Note':di_calc.get('error') or 'DI Hardenability.XLSX factor product'}]),hide_index=True,width='stretch')

    with stage_section("F", 'HEAT TREATMENT & OTHER REQUIREMENTS', 'Not Applicable is available and does not block Draft saving.', key="rmtc_pages_render_part_f"):
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
            if st.button('Open / Edit RMTC Header',icon=':material/edit:',width='stretch',key=f'edit_rmtc_header_{selected}'):
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
        record_email_sender(
            NotificationService(svc.repo), 'RMTC_APPROVAL_PENDING',
            related_table='rmtc_approvals', related_id=selected, key=f'rmtc_record_email_{selected}',
            context={'rmtc_id': selected, 'heat_number': selected_row.get('heat_number'), 'next_task': 'RMTC Review / Approval'},
        )
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
    portal_table(style_status_dataframe(df),hide_index=True,width='stretch',height=600)


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

    with stage_section("A", 'PART VALIDATION & CONTROLLED DECISION', 'Automated results are read-only. Final disposition is selected independently for every Part Number.', key="rmtc_pages_render_approval_a"):
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
        pending_added_parts=[row for row in details['parts'] if normalize_disposition(row.get('disposition') or 'PENDING') in ('PENDING','ON_HOLD')]
        incremental_part_review=str(record.get('status'))=='PARTIALLY_APPROVED' and bool(pending_added_parts)
        finalized=str(record.get('status')) in ('APPROVED','REJECTED') or (str(record.get('status'))=='PARTIALLY_APPROVED' and not incremental_part_review)
        if finalized and role=='ADMIN':
            st.markdown("**Admin Decision Control**")
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
                portal_table(pd.DataFrame([{
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

        if incremental_part_review:
            st.markdown('**Added Part Worksheet · Validation & Final Decision**')
            st.caption('Existing accepted Part Numbers remain released. Only the newly added Pending / On Hold Part Worksheet is validated and decided here.')
            pending_map={str(row.get('part_id')):part_label(parts.get(str(row.get('part_id'))) or {}) for row in pending_added_parts}
            added_part_id=st.selectbox('Pending Added Part Number',list(pending_map),format_func=lambda value:pending_map[value],key=f'incremental_rmtc_part_{rid}')
            added_row=next(row for row in pending_added_parts if str(row.get('part_id'))==str(added_part_id))
            icols=st.columns(3,gap='small')
            added_validator=icols[0].selectbox('Added Part · Validated By',validator_options,index=validator_options.index(current_validator) if current_validator in validator_options else 0,format_func=lambda x:validate_map.get(x,'— Select Validator —'),key=f'incremental_validator_{rid}_{added_part_id}')
            added_approver=icols[1].selectbox('Added Part · Approved / Decided By',approver_options,index=approver_options.index(current_approver) if current_approver in approver_options else 0,format_func=lambda x:approve_map.get(x,'— Select Approver —'),key=f'incremental_approver_{rid}_{added_part_id}')
            worksheet_done=bool(added_row.get('worksheet_completed_at'))
            icols[2].page_link(st.session_state['_qsms_pages']['rmtc-part'],label='Open Part Worksheet',icon=':material/format_list_bulleted:',width='stretch')
            if not worksheet_done:
                st.warning('Complete and save this Part Worksheet before automated validation.')
            b1,b2=st.columns(2,gap='small')
            if b1.button('1 · Validate Added Part Against Masters',type='primary',width='stretch',disabled=not worksheet_done or not added_validator,key=f'incremental_validate_{rid}_{added_part_id}'):
                try:
                    repo.update('rmtc_approvals',rid,{'validated_by_employee_id':added_validator,'approved_by_employee_id':added_approver or None})
                    svc.validate_added_part(rid,added_part_id)
                    save_success_popup('Added Part validation completed. Existing accepted Part releases were not changed.',queue_for_rerun=True);st.rerun()
                except Exception as exc:st.error(str(exc))
            added_disposition=b2.selectbox('2 · Added Part Final Decision',['PENDING','ACCEPTED','ACCEPTED_UNDER_RESERVE','ON_HOLD','REJECTED'],format_func=lambda v:disposition_label(v),key=f'incremental_disposition_{rid}_{added_part_id}')
            added_reason=st.text_area('Added Part Decision / Reserve / Hold / Rejection Reason',height=70,key=f'incremental_reason_{rid}_{added_part_id}')
            if st.button('3 · Save Added Part Final Decision',type='primary',width='stretch',disabled=not can_approve or not worksheet_done or not added_approver or added_disposition=='PENDING',key=f'incremental_decide_{rid}_{added_part_id}'):
                try:
                    svc.decide_added_part(rid,added_part_id,added_disposition,added_reason.strip() or None,added_approver)
                    save_success_popup('Added Part final decision saved. Existing accepted Parts remain released.',queue_for_rerun=True);st.rerun()
                except Exception as exc:st.error(str(exc))

        approval_notify_pref = notification_confirmation(NotificationService(repo), 'RMTC_APPROVAL_PENDING', key=f"rmtc_approval_notify_{rid}", context={'rmtc_id':rid,'next_task':'RMTC Approval'}, default_send=record.get('status')=='DRAFT') if record.get('status')=='DRAFT' else {'send':False,'confirmed':True,'preview':{}}
        workflow=st.columns(3,gap='small')
        submit_disabled=record.get('status')!='DRAFT' or not validated or not approved or (approval_notify_pref['send'] and not approval_notify_pref['confirmed'])
        if workflow[0].button('1 · Submit for Validation',disabled=submit_disabled,width='stretch'):
            try:
                repo.update('rmtc_approvals',rid,{'validated_by_employee_id':validated,'approved_by_employee_id':approved})
                repo.rpc('qsms_submit_rmtc',{'p_rmtc_id':rid})
                if approval_notify_pref['send'] and approval_notify_pref['confirmed']:
                    NotificationService(repo).notify(
                        'RMTC_APPROVAL_PENDING',
                        subject=f"QCMS · RMTC approval pending · {record.get('rmtc_number')}",
                    body_text=(f"RMTC {record.get('rmtc_number')} is pending validation / approval.\n"
                               f"Heat Number: {record.get('heat_number') or '-'}\n"
                               f"Covered Parts: {len(details.get('parts') or [])}"),
                    related_table='rmtc_approvals', related_id=rid,
                    context={'rmtc_id':rid,'next_task':'RMTC Approval'},
                    **notification_overrides(approval_notify_pref),
                )
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
