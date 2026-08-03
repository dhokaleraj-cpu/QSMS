-- QSMS 4.8.7 optional attachment controls for RMTC and Material Inward.

create or replace function public.qsms_delete_document_attachment(p_attachment_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  v_tenant uuid := public.current_tenant_id();
  v_role text := coalesce(public.current_app_role(), 'VIEWER');
  v_attachment public.document_attachments%rowtype;
  v_module text;
  v_allowed boolean := false;
begin
  if auth.uid() is null or v_tenant is null then
    raise exception 'An authenticated QSMS session is required';
  end if;

  select * into v_attachment
  from public.document_attachments
  where id = p_attachment_id and tenant_id = v_tenant
  for update;

  if v_attachment.id is null then
    raise exception 'The selected attachment was not found';
  end if;

  v_module := case upper(v_attachment.entity_type)
    when 'RMTC' then 'RMTC_ENTRY'
    when 'MATERIAL_INWARD' then 'MATERIAL_INWARD'
    when 'PART_MASTER' then 'PART_MASTER'
    when 'DIMENSIONAL_REPORT' then 'DIMENSIONAL_REPORT'
    when 'METLAB_REPORT' then 'METLAB_REPORT'
    else null
  end;

  v_allowed := v_role = 'ADMIN' or (
    v_module is not null and exists (
      select 1
      from public.user_module_permissions p
      where p.tenant_id = v_tenant
        and p.profile_id = auth.uid()
        and p.module_key = v_module
        and p.can_view
        and p.can_archive
    )
  );

  if not v_allowed then
    raise exception 'Attachment delete permission is not assigned for this module';
  end if;

  delete from public.document_attachments
  where id = p_attachment_id and tenant_id = v_tenant;

  return jsonb_build_object(
    'deleted', true,
    'id', p_attachment_id,
    'entity_type', v_attachment.entity_type,
    'entity_id', v_attachment.entity_id,
    'object_path', v_attachment.object_path
  );
end;
$$;

revoke all on function public.qsms_delete_document_attachment(uuid) from public, anon;
grant execute on function public.qsms_delete_document_attachment(uuid) to authenticated;

-- Permit controlled storage deletion for users who have archive rights for the
-- corresponding QSMS module. Every operation remains tenant-folder restricted.
drop policy if exists qsms_storage_delete on storage.objects;
create policy qsms_storage_delete on storage.objects
for delete to authenticated
using (
  bucket_id = 'quality-documents'
  and (storage.foldername(name))[1] = public.current_tenant_id()::text
  and (
    public.current_app_role() = 'ADMIN'
    or (
      (storage.foldername(name))[2] = 'rmtc'
      and exists (
        select 1 from public.user_module_permissions p
        where p.tenant_id = public.current_tenant_id()
          and p.profile_id = auth.uid()
          and p.module_key = 'RMTC_ENTRY'
          and p.can_view and p.can_archive
      )
    )
    or (
      (storage.foldername(name))[2] = 'inward'
      and exists (
        select 1 from public.user_module_permissions p
        where p.tenant_id = public.current_tenant_id()
          and p.profile_id = auth.uid()
          and p.module_key = 'MATERIAL_INWARD'
          and p.can_view and p.can_archive
      )
    )
  )
);
