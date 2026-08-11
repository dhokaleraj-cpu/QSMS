from __future__ import annotations

import pandas as pd
import streamlit as st

from core.access import MODULES
from core.database import get_session_client
from core.permissions import is_admin
from core.repository import Repository
from core.ui import page_header, section_bar, subpage_navigation

ROLES=['ADMIN','QUALITY_MANAGER','METLAB_APPROVER','QUALITY_ENGINEER','PRODUCTION','SQA','MASTER_DATA','AUDITOR','VIEWER']


def _invoke(payload):
    client=get_session_client(); response=client.functions.invoke('qsms-user-admin',invoke_options={'body':payload})
    data=getattr(response,'data',response)
    if isinstance(data,bytes):
        import json
        data=json.loads(data.decode())
    return data


def render()->None:
    subpage_navigation(('masters','Back to Masters',':material/arrow_back:'))
    page_header('Users & Access','Create users, link employees and assign module-level create/edit/delete/approve controls.','Administrator')
    profile=st.session_state.get('profile') or {}
    if not is_admin(profile):st.error('Administrator access is required.');return
    repo=Repository(); employees=repo.select('employees',order_by='first_name',limit=2000)
    emp={str(e['id']):f"{e.get('employee_code')} · {e.get('first_name')} {e.get('last_name')}" for e in employees}
    create_tab,access_tab,password_tab=st.tabs(['Create User','Users & Module Permissions','My Password'])
    with create_tab:
        section_bar('CREATE USER','Supabase Auth user, QCMS role and Employee link.')
        with st.form('create_user_v430'):
            c=st.columns(3,gap='small'); full=c[0].text_input('Full Name'); email=c[1].text_input('Company Email'); role=c[2].selectbox('QCMS Role',ROLES)
            c=st.columns(3,gap='small'); employee=c[0].selectbox('Employee Link',['']+list(emp),format_func=lambda x:emp.get(x,'— Not linked —'));status=c[1].selectbox('Access Status',['ACTIVE','INACTIVE','LOCKED']);password=c[2].text_input('Temporary Password',type='password')
            submit=st.form_submit_button('Create User',type='primary',width='stretch')
        if submit:
            try:
                result=_invoke({'action':'create_user','email':email,'password':password,'full_name':full,'role':role,'status':status,'employee_id':employee or None})
                st.success(result.get('message','User created.'))
            except Exception as exc:st.error(str(exc))
    with access_tab:
        try:
            payload=_invoke({'action':'list_users'}); users=payload.get('users',payload if isinstance(payload,list) else [])
        except Exception as exc:st.error(str(exc));users=[]
        if not users:st.info('No users available.');return
        register=pd.DataFrame([{'Email':u.get('email'),'Name':u.get('full_name'),'Role':u.get('role'),'Status':u.get('status'),'Last Sign In':u.get('last_sign_in_at')} for u in users])
        st.dataframe(register,hide_index=True,width='stretch',height=300)
        labels={str(u.get('id')):f"{u.get('email')} · {u.get('role')}" for u in users};uid=st.selectbox('Selected User',list(labels),format_func=lambda x:labels[x])
        current=next(u for u in users if str(u.get('id'))==uid)
        c=st.columns(3,gap='small');role=c[0].selectbox('Role',ROLES,index=ROLES.index(current.get('role','VIEWER')));status=c[1].selectbox('Access Status',['ACTIVE','INACTIVE','LOCKED'],index=['ACTIVE','INACTIVE','LOCKED'].index(current.get('status','ACTIVE')));employee=c[2].selectbox('Employee',['']+list(emp),format_func=lambda x:emp.get(x,'— Not linked —'))
        if st.button('Update User Role / Status',type='primary',width='stretch'):
            try:_invoke({'action':'update_user','user_id':uid,'role':role,'status':status,'employee_id':employee or None});st.success('User access updated.');st.rerun()
            except Exception as exc:st.error(str(exc))

        section_bar('MODULE PERMISSIONS','Selected users can receive edit rights without being an Administrator.')
        existing={str(r.get('module_key')):r for r in repo.select('user_module_permissions',eq={'profile_id':uid},limit=100)}
        rows=[]
        for key,label in MODULES:
            row=existing.get(key,{})
            rows.append({'Module':label,'Module Key':key,'View':bool(row.get('can_view',True)),'Create':bool(row.get('can_create',False)),'Edit':bool(row.get('can_edit',False)),'Delete':bool(row.get('can_archive',False)),'Approve':bool(row.get('can_approve',False))})
        edited=st.data_editor(pd.DataFrame(rows),hide_index=True,width='stretch',height=300,disabled=['Module','Module Key'])
        if st.button('Save Module Permissions',type='primary',width='stretch'):
            try:
                for _,row in edited.iterrows():
                    data={'profile_id':uid,'module_key':row['Module Key'],'can_view':bool(row['View']),'can_create':bool(row['Create']),'can_edit':bool(row['Edit']),'can_archive':bool(row['Delete']),'can_approve':bool(row['Approve'])}
                    repo.upsert_by('user_module_permissions',data,natural_key={'profile_id':uid,'module_key':row['Module Key']})
                st.success('Module permissions saved.');st.rerun()
            except Exception as exc:st.error(str(exc))
        temp=st.text_input('New Temporary Password',type='password')
        if st.button('Reset Selected User Password',width='stretch'):
            try:_invoke({'action':'reset_password','user_id':uid,'password':temp});st.success('Temporary password updated.')
            except Exception as exc:st.error(str(exc))
    with password_tab:
        p1=st.text_input('New Password',type='password');p2=st.text_input('Confirm New Password',type='password')
        if st.button('Change My Password',type='primary',width='stretch'):
            if len(p1)<10:st.error('Use at least 10 characters.')
            elif p1!=p2:st.error('Passwords do not match.')
            else:
                try:get_session_client().auth.update_user({'password':p1});st.success('Password changed successfully.')
                except Exception as exc:st.error(str(exc))
