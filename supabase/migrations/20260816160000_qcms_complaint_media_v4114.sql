-- QCMS 4.11.4 — titled complaint photographs and repeatable multiple attachments.
-- Additive only: no complaint, attachment, storage object or transaction is reset.
begin;

alter table public.document_attachments
  add column if not exists document_title text;

create index if not exists idx_document_attachments_complaint_media
on public.document_attachments(tenant_id, entity_id, document_type, created_at desc)
where entity_type='QUALITY_COMPLAINT'
  and document_type in ('COMPLAINT_PHOTO','COMPLAINT_ATTACHMENT');

-- Preserve existing module mapping and ensure complaint attachments resolve to
-- Complaint Management permissions.
create or replace function public.qsms_attachment_module(p_entity_type text)
returns text
language sql
immutable
set search_path=public
as $$
select case upper(coalesce(p_entity_type, ''))
  when 'RMTC' then 'RMTC_ENTRY'
  when 'MATERIAL_INWARD' then 'MATERIAL_INWARD'
  when 'PART_MASTER' then 'PART_MASTER'
  when 'PART_PROCESS_SPEC' then 'PART_MASTER'
  when 'CUSTOMER_STANDARD' then 'REFERENCE_MASTERS'
  when 'QUALITY_COMPLAINT' then 'COMPLAINT_MANAGEMENT'
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
set search_path=public,auth
as $$
declare
  v_role text := coalesce(public.current_app_role(), 'VIEWER');
  v_module text := public.qsms_attachment_module(p_entity_type);
  v_action text := upper(coalesce(p_action, 'EDIT'));
begin
  if auth.uid() is null or public.current_tenant_id() is null then return false; end if;
  if v_role='ADMIN' then return true; end if;
  if v_module is null then return false; end if;

  if exists(
    select 1 from public.user_module_permissions p
    where p.tenant_id=public.current_tenant_id()
      and p.profile_id=auth.uid()
      and p.module_key=v_module
      and p.can_view
      and case
        when v_action='CREATE' then p.can_create
        when v_action='ARCHIVE' then p.can_archive
        else p.can_edit
      end
  ) then return true; end if;

  return case v_module
    when 'PART_MASTER' then v_role in ('QUALITY_MANAGER','MASTER_DATA')
    when 'RMTC_ENTRY' then v_role in ('QUALITY_MANAGER','METLAB_APPROVER','SQA')
    when 'MATERIAL_INWARD' then v_role in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION')
    when 'DIMENSIONAL_REPORT' then v_role in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA')
    when 'METLAB_REPORT' then v_role in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER')
    when 'COMPLAINT_MANAGEMENT' then v_role in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION')
    else false
  end;
end;
$$;

revoke all on function public.qsms_attachment_module(text) from public,anon;
revoke all on function public.qsms_can_manage_attachment(text,text) from public,anon;
grant execute on function public.qsms_attachment_module(text) to authenticated;
grant execute on function public.qsms_can_manage_attachment(text,text) to authenticated;

-- Allow controlled complaint storage deletion for users who have Complaint
-- Management archive permission. Other historical storage rules remain intact.
drop policy if exists qsms_storage_delete on storage.objects;
create policy qsms_storage_delete on storage.objects
for delete to authenticated
using (
  bucket_id='quality-documents'
  and (storage.foldername(name))[1]=public.current_tenant_id()::text
  and (
    public.current_app_role()='ADMIN'
    or (
      (storage.foldername(name))[2] in ('parts','osp_process_drawings')
      and exists(select 1 from public.user_module_permissions p
        where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid()
          and p.module_key='PART_MASTER' and p.can_view and p.can_archive)
    )
    or (
      (storage.foldername(name))[2]='rmtc'
      and exists(select 1 from public.user_module_permissions p
        where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid()
          and p.module_key='RMTC_ENTRY' and p.can_view and p.can_archive)
    )
    or (
      (storage.foldername(name))[2]='inward'
      and exists(select 1 from public.user_module_permissions p
        where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid()
          and p.module_key='MATERIAL_INWARD' and p.can_view and p.can_archive)
    )
    or (
      (storage.foldername(name))[2]='complaints'
      and exists(select 1 from public.user_module_permissions p
        where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid()
          and p.module_key='COMPLAINT_MANAGEMENT' and p.can_view and p.can_archive)
    )
  )
);

commit;
