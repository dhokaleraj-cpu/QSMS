-- QSMS 4.8.7 module-aware insert/update permissions for document attachments.

create or replace function public.qsms_attachment_module(p_entity_type text)
returns text
language sql
immutable
as $$
select case upper(coalesce(p_entity_type, ''))
  when 'RMTC' then 'RMTC_ENTRY'
  when 'MATERIAL_INWARD' then 'MATERIAL_INWARD'
  when 'PART_MASTER' then 'PART_MASTER'
  when 'DIMENSIONAL_REPORT' then 'DIMENSIONAL_REPORT'
  when 'METLAB_REPORT' then 'METLAB_REPORT'
  else null
end;
$$;

create or replace function public.qsms_can_manage_attachment(p_entity_type text, p_action text default 'EDIT')
returns boolean
language plpgsql
stable
security definer
set search_path = public, auth
as $$
declare
  v_role text := coalesce(public.current_app_role(), 'VIEWER');
  v_module text := public.qsms_attachment_module(p_entity_type);
  v_action text := upper(coalesce(p_action, 'EDIT'));
begin
  if auth.uid() is null or public.current_tenant_id() is null then
    return false;
  end if;
  if v_role = 'ADMIN' then
    return true;
  end if;
  if v_module is null then
    return false;
  end if;

  if exists (
    select 1
    from public.user_module_permissions p
    where p.tenant_id = public.current_tenant_id()
      and p.profile_id = auth.uid()
      and p.module_key = v_module
      and p.can_view
      and case
        when v_action = 'CREATE' then p.can_create
        when v_action = 'ARCHIVE' then p.can_archive
        else p.can_edit
      end
  ) then
    return true;
  end if;

  return case v_module
    when 'PART_MASTER' then v_role in ('QUALITY_MANAGER', 'MASTER_DATA')
    when 'RMTC_ENTRY' then v_role in ('QUALITY_MANAGER', 'METLAB_APPROVER', 'SQA')
    when 'MATERIAL_INWARD' then v_role in ('QUALITY_MANAGER', 'QUALITY_ENGINEER', 'SQA', 'PRODUCTION')
    when 'DIMENSIONAL_REPORT' then v_role in ('QUALITY_MANAGER', 'QUALITY_ENGINEER', 'SQA')
    when 'METLAB_REPORT' then v_role in ('QUALITY_MANAGER', 'QUALITY_ENGINEER', 'METLAB_APPROVER')
    else false
  end;
end;
$$;

revoke all on function public.qsms_attachment_module(text) from public, anon;
revoke all on function public.qsms_can_manage_attachment(text, text) from public, anon;
grant execute on function public.qsms_attachment_module(text) to authenticated;
grant execute on function public.qsms_can_manage_attachment(text, text) to authenticated;

-- Override the generic table policies only for the attachment register so RMTC
-- and Inward users do not require unrelated Part Master permissions.
drop policy if exists tenant_insert on public.document_attachments;
create policy tenant_insert on public.document_attachments
for insert to authenticated
with check (
  tenant_id = public.current_tenant_id()
  and public.qsms_can_manage_attachment(entity_type, 'CREATE')
);

drop policy if exists tenant_update on public.document_attachments;
create policy tenant_update on public.document_attachments
for update to authenticated
using (
  tenant_id = public.current_tenant_id()
  and public.qsms_can_manage_attachment(entity_type, 'EDIT')
)
with check (
  tenant_id = public.current_tenant_id()
  and public.qsms_can_manage_attachment(entity_type, 'EDIT')
);
