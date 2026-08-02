-- QSMS 4.7.2 reliability and controlled RMTC decision revision.
-- Live project migration applied without deleting existing data.

begin;

create or replace function public.qsms_remember_master_value(p_field_key text,p_value_text text)
returns text
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  tid uuid:=public.current_tenant_id();
  key_text text:=btrim(coalesce(p_field_key,''));
  cleaned text:=btrim(coalesce(p_value_text,''));
  changed integer:=0;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if tid is null then raise exception 'Active QSMS tenant is required'; end if;
  if key_text='' or cleaned='' then return cleaned; end if;
  update public.master_value_catalog
     set value_text=cleaned,usage_count=usage_count+1,last_used_at=now(),
         status='ACTIVE',updated_at=now(),updated_by=auth.uid()
   where tenant_id=tid and field_key=key_text and normalized_value=lower(cleaned);
  get diagnostics changed=row_count;
  if changed=0 then
    begin
      insert into public.master_value_catalog(tenant_id,field_key,value_text)
      values(tid,key_text,cleaned);
    exception when unique_violation then
      update public.master_value_catalog
         set value_text=cleaned,usage_count=usage_count+1,last_used_at=now(),
             status='ACTIVE',updated_at=now(),updated_by=auth.uid()
       where tenant_id=tid and field_key=key_text and normalized_value=lower(cleaned);
    end;
  end if;
  return cleaned;
end;
$$;

do $$
declare t record; e text;
begin
  for t in select id from public.tenants loop
    foreach e in array array['C','Si','Mn','P','S','Cr','Mo','Ni'] loop
      if not exists(
        select 1 from public.master_value_catalog
         where tenant_id=t.id and field_key='material.element' and normalized_value=lower(e)
      ) then
        insert into public.master_value_catalog(tenant_id,field_key,value_text)
        values(t.id,'material.element',e);
      end if;
    end loop;
  end loop;
end $$;

create table if not exists public.rmtc_decision_revisions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  rmtc_approval_id uuid not null references public.rmtc_approvals(id) on delete cascade,
  reason text not null,
  previous_status text not null,
  previous_disposition text not null,
  previous_decisions jsonb not null default '[]'::jsonb,
  reopened_by uuid default auth.uid(),
  reopened_at timestamptz not null default now()
);
create index if not exists idx_rmtc_decision_revisions_rmtc
  on public.rmtc_decision_revisions(rmtc_approval_id,reopened_at desc);
alter table public.rmtc_decision_revisions enable row level security;
drop policy if exists tenant_select on public.rmtc_decision_revisions;
create policy tenant_select on public.rmtc_decision_revisions for select to authenticated
using (tenant_id=public.current_tenant_id());

create or replace function public.qsms_admin_reopen_rmtc(p_rmtc_id uuid,p_reason text)
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_header public.rmtc_approvals%rowtype;
  v_reason text:=btrim(coalesce(p_reason,''));
  v_decisions jsonb;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if public.current_app_role()<>'ADMIN' then raise exception 'Only the QSMS Administrator can reopen a final RMTC decision'; end if;
  if v_reason='' then raise exception 'Reason for changing the RMTC decision is mandatory'; end if;
  select * into v_header from public.rmtc_approvals
   where id=p_rmtc_id and tenant_id=public.current_tenant_id() for update;
  if v_header.id is null then raise exception 'RMTC record was not found'; end if;
  if v_header.status not in ('APPROVED','PARTIALLY_APPROVED','REJECTED') then
    raise exception 'Only a finalized RMTC decision can be reopened';
  end if;
  if exists(select 1 from public.inward_lots where rmtc_approval_id=p_rmtc_id) then
    raise exception 'This RMTC is already linked to Material Inward. Delete or close the linked inward transaction before changing the RMTC decision.';
  end if;
  select coalesce(jsonb_agg(jsonb_build_object(
    'part_id',part_id,'disposition',disposition,'decision_reason',decision_reason,
    'decision_at',decision_at,'decision_by_employee_id',decision_by_employee_id
  ) order by created_at),'[]'::jsonb)
  into v_decisions from public.rmtc_part_approvals where rmtc_approval_id=p_rmtc_id;
  insert into public.rmtc_decision_revisions(
    tenant_id,rmtc_approval_id,reason,previous_status,previous_disposition,previous_decisions,reopened_by
  ) values(
    v_header.tenant_id,v_header.id,v_reason,v_header.status,coalesce(v_header.disposition,'PENDING'),v_decisions,auth.uid()
  );
  update public.rmtc_part_approvals
     set disposition='PENDING',decision_reason=null,decision_at=null,decision_by_employee_id=null,
         updated_at=now(),updated_by=auth.uid()
   where rmtc_approval_id=p_rmtc_id;
  update public.rmtc_approvals
     set status='APPROVAL_PENDING',disposition='PENDING',disposition_reason=null,
         decision_at=null,decision_by_employee_id=null,approved_at=null,approved_by=null,
         rejection_reason=null,
         validation_summary=coalesce(validation_summary,'{}'::jsonb)||jsonb_build_object(
           'admin_reopened_at',now(),'admin_reopen_reason',v_reason,'admin_reopened_by',auth.uid()
         ),updated_at=now(),updated_by=auth.uid()
   where id=p_rmtc_id;
  return jsonb_build_object('status','APPROVAL_PENDING','disposition','PENDING','reopen_reason',v_reason);
end;
$$;

revoke all on function public.qsms_admin_reopen_rmtc(uuid,text) from public,anon;
grant execute on function public.qsms_admin_reopen_rmtc(uuid,text) to authenticated;

commit;
