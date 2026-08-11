from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.catalog import LearnedValueCatalog
from core.database import get_session_client
from core.delete_service import password_delete_panel
from core.employee_service import AUTHORITIES, EmployeeService
from core.reporting import controlled_record_pdf_bytes
from core.ui import page_header, save_success_popup, section_bar, subpage_navigation, template_download_row


def _labels(rows:list[dict])->dict[str,str]:
    return {str(r['id']):f"{r.get('employee_code')} · {r.get('first_name')} {r.get('last_name')}" for r in rows}


def _learned_select(catalog:LearnedValueCatalog,label:str,field_key:str,value:str,key:str):
    suggestions=catalog.suggestions(field_key)
    options=[]
    if value: options.append(value)
    options += [item for item in suggestions if item not in options]
    return st.selectbox(label,options,index=0,accept_new_options=True,key=key) if options else st.text_input(label,value=value,key=key)


def render_entry()->None:
    subpage_navigation(("masters","Back to Masters",":material/arrow_back:"),("employee-records","Employee Records",":material/groups:"))
    page_header("Employee Master · Entry", "Employee code, reporting line, experience and approval authority.", "New / edit")
    template_download_row([("Employee_Master_Template.xlsx", "Download Employee Master Template")], key_prefix="employee_master")
    svc=EmployeeService(); repo=svc.repo; catalog=LearnedValueCatalog(repo); perms=current_permissions("EMPLOYEE_MASTER")
    rows=svc.list(False); labels=_labels(rows)
    requested=str(st.session_state.pop('edit_employee_id','') or '')
    options=['__new__']+list(labels); index=options.index(requested) if requested in options else 0
    selected=st.selectbox('Employee record',options,index=index,format_func=lambda x:'＋ New Employee' if x=='__new__' else labels[x])
    existing=next((r for r in rows if str(r['id'])==selected),{})
    writable=perms['can_edit'] if existing else perms['can_create']
    managers={'': '— No reporting manager —',**labels}

    section_bar('EMPLOYEE DETAILS','Employee code is generated automatically when blank and remains manually editable.')
    with st.form('employee_entry_form'):
        c=st.columns(4,gap='small')
        code=c[0].text_input('Employee Code',value=str(existing.get('employee_code') or ''),placeholder='Auto on save (EMP-0001)')
        first=c[1].text_input('First Name',value=str(existing.get('first_name') or ''))
        last=c[2].text_input('Last Name',value=str(existing.get('last_name') or ''))
        email=c[3].text_input('Email',value=str(existing.get('email') or ''))
        c=st.columns(4,gap='small')
        with c[0]:
            department=_learned_select(catalog,'Department','employee.department',str(existing.get('department') or ''),'emp_dept')
        with c[1]:
            designation=_learned_select(catalog,'Designation','employee.designation',str(existing.get('designation') or ''),'emp_desig')
        with c[2]:
            plant=_learned_select(catalog,'Plant','employee.plant',str(existing.get('plant') or 'D9'),'emp_plant')
        mobile=c[3].text_input('Mobile Number',value=str(existing.get('mobile_number') or ''))
        c=st.columns(3,gap='small')
        reports=c[0].selectbox('Reports To',list(managers),format_func=lambda x:managers[x],index=list(managers).index(str(existing.get('reports_to_employee_id') or '')) if str(existing.get('reports_to_employee_id') or '') in managers else 0)
        start_value=date.fromisoformat(str(existing.get('experience_start_date'))[:10]) if existing.get('experience_start_date') else date.today()
        exp_start=c[1].date_input('Experience Start Date',value=start_value,format='DD-MM-YYYY')
        status=c[2].selectbox('Status',['ACTIVE','INACTIVE','LEFT'],index=['ACTIVE','INACTIVE','LEFT'].index(str(existing.get('status') or 'ACTIVE')))
        authorities=st.multiselect('Authority for Approval',AUTHORITIES,default=existing.get('approval_authorities') or [])
        remarks=st.text_area('Remarks',value=str(existing.get('remarks') or ''),height=70)
        save=st.form_submit_button('Save Employee',type='primary',disabled=not writable,width='stretch')
    st.caption(f"Experience automatically calculated: {svc.years(exp_start.isoformat())} completed years")
    photo=st.file_uploader('Employee Photo',type=['png','jpg','jpeg'],key=f"employee_photo_{selected}")
    if save:
        try:
            final_code=code.strip()
            if not final_code:
                final_code=str(repo.rpc('qsms_next_employee_code') or '')
            payload={'employee_code':final_code,'first_name':first.strip(),'last_name':last.strip(),'email':email.strip().lower(),'department':str(department).strip(),'designation':str(designation).strip(),'plant':str(plant).strip(),'mobile_number':mobile.strip() or None,'approval_authorities':authorities,'reports_to_employee_id':reports or None,'experience_start_date':exp_start.isoformat(),'status':status,'remarks':remarks.strip() or None,'source_system':'QSMS'}
            saved=svc.save(payload,None if selected=='__new__' else selected)
            catalog.remember_many('employee.department',[department]);catalog.remember_many('employee.designation',[designation]);catalog.remember_many('employee.plant',[plant])
            st.session_state['edit_employee_id']=str(saved['id']);save_success_popup(f"Employee saved with code {saved.get('employee_code')}.", queue_for_rerun=True);st.rerun()
        except Exception as exc:st.error(str(exc))
    if existing and photo is not None and writable:
        if st.button('Upload Employee Photo',type='primary',width='stretch'):
            try:
                client=get_session_client(); ext=photo.name.rsplit('.',1)[-1].lower(); path=f"{repo.tenant_id}/employees/{existing['id']}/photo_{existing['id']}.{ext}"
                client.storage.from_('quality-documents').upload(path,photo.getvalue(),{'content-type':photo.type,'upsert':'true'})
                repo.update('employees',str(existing['id']),{'photo_storage_path':path});save_success_popup('Employee photo uploaded successfully.', queue_for_rerun=True);st.rerun()
            except Exception as exc:st.error(str(exc))


def render_records()->None:
    subpage_navigation(
        ("dashboard","Back to Dashboard",":material/arrow_back:"),
        ("masters","Back to Masters",":material/dataset:"),
        ("employee-entry","New Employee / Edit",":material/person_add:"),
    )
    page_header("Employee Master · Records", "Select an employee above the register for editing or controlled deletion.", "Records")
    svc=EmployeeService(); perms=current_permissions("EMPLOYEE_MASTER"); rows=svc.list(False); manager={str(r['id']):f"{r.get('first_name')} {r.get('last_name')}" for r in rows}
    search=st.text_input('Search employee, email, department or designation')
    filtered=[r for r in rows if not search or search.casefold() in ' '.join(str(r.get(k) or '') for k in ('employee_code','first_name','last_name','email','department','designation','plant')).casefold()]

    if filtered:
        labels=_labels(filtered); selected=st.selectbox('Select Employee record',list(labels),format_func=lambda x:labels[x])
        st.session_state['edit_employee_id']=selected
        selected_row=next(row for row in filtered if str(row.get('id'))==selected)
        c1,c2,c3=st.columns(3,gap='small')
        with c1:
            st.page_link(st.session_state['_qsms_pages']['employee-entry'],label='Open Selected Employee',icon=':material/edit:',width='stretch')
        with c2:
            pdf=controlled_record_pdf_bytes(
                'EMPLOYEE MASTER RECORD',
                {'Employee Code':selected_row.get('employee_code'),'Employee':f"{selected_row.get('first_name') or ''} {selected_row.get('last_name') or ''}".strip(),'Email':selected_row.get('email'),'Department':selected_row.get('department'),'Designation':selected_row.get('designation'),'Plant':selected_row.get('plant'),'Mobile':selected_row.get('mobile_number'),'Reports To':manager.get(str(selected_row.get('reports_to_employee_id')),''),'Experience Start Date':selected_row.get('experience_start_date'),'Experience Years':svc.years(selected_row.get('experience_start_date')),'Approval Authorities':', '.join(selected_row.get('approval_authorities') or []),'Status':selected_row.get('status'),'Remarks':selected_row.get('remarks')},
                record_number=str(selected_row.get('employee_code') or ''),
            )
            st.download_button('Download Employee PDF',pdf,file_name=f"Employee_{selected_row.get('employee_code')}.pdf",mime='application/pdf',width='stretch')
        with c3:
            if password_delete_panel(repo=svc.repo,table='employees',rows=[selected_row],labeler=lambda r:f"{r.get('employee_code')} · {r.get('first_name')} {r.get('last_name')}",key=f"delete_employee_{selected}",can_delete=perms['can_archive'],title='Delete Selected Employee',help_text='Permanent deletion requires your current password. Employees linked to users or approvals may need to be set Inactive instead.'):
                st.rerun()
    else:
        st.info('No Employee records match the search.')

    section_bar('EMPLOYEE REGISTER','The selected employee and actions are positioned above the table.')
    df=pd.DataFrame([{'Employee Code':r.get('employee_code'),'Employee':f"{r.get('first_name')} {r.get('last_name')}",'Email':r.get('email'),'Department':r.get('department'),'Designation':r.get('designation'),'Plant':r.get('plant'),'Mobile':r.get('mobile_number'),'Reports To':manager.get(str(r.get('reports_to_employee_id')),''),'Experience Years':svc.years(r.get('experience_start_date')),'Approval Authorities':', '.join(r.get('approval_authorities') or []),'Status':r.get('status')} for r in filtered])
    st.dataframe(df,hide_index=True,width='stretch',height=620)
