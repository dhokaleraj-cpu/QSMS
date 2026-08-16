-- QCMS 4.11.3 — Controlled Drawing revision history.
-- Additive only: preserves all existing document attachments and Part Master data.
begin;

alter table public.document_attachments add column if not exists drawing_number text;
alter table public.document_attachments add column if not exists revision_date date;
alter table public.document_attachments add column if not exists superseded_at timestamptz;
alter table public.document_attachments add column if not exists superseded_by uuid references public.profiles(id) on delete set null;

create index if not exists idx_document_attachments_part_drawing_history
on public.document_attachments(tenant_id, entity_id, document_type, created_at desc)
where entity_type='PART_MASTER' and document_type in ('FINISH_DRAWING','FORGING_DRAWING','HEAT_TREATMENT_DRAWING');

create unique index if not exists ux_document_attachments_part_drawing_revision
on public.document_attachments(tenant_id, entity_id, document_type, lower(drawing_number), lower(revision))
where entity_type='PART_MASTER'
  and document_type in ('FINISH_DRAWING','FORGING_DRAWING','HEAT_TREATMENT_DRAWING')
  and drawing_number is not null and revision is not null;

create unique index if not exists ux_document_attachments_one_active_part_drawing
on public.document_attachments(tenant_id, entity_id, document_type)
where entity_type='PART_MASTER'
  and document_type in ('FINISH_DRAWING','FORGING_DRAWING','HEAT_TREATMENT_DRAWING')
  and status='ACTIVE';

create or replace function public.qcms_activate_part_drawing_revision(
  p_part_id uuid,
  p_document_type text,
  p_drawing_number text,
  p_revision text,
  p_revision_date date,
  p_file_name text,
  p_object_path text,
  p_mime_type text,
  p_size_bytes bigint,
  p_checksum text
) returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  tid uuid := public.current_tenant_id();
  dtype text := upper(trim(coalesce(p_document_type,'')));
  drawing_no text := trim(coalesce(p_drawing_number,''));
  rev_no text := trim(coalesce(p_revision,''));
  new_row public.document_attachments%rowtype;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if not public.can_write_table('parts') then raise exception 'Part Master create/edit permission is required'; end if;
  if dtype not in ('FINISH_DRAWING','FORGING_DRAWING','HEAT_TREATMENT_DRAWING') then
    raise exception 'Unsupported controlled drawing type';
  end if;
  if drawing_no='' then raise exception 'Drawing Number is required'; end if;
  if rev_no='' then raise exception 'Revision Number is required'; end if;
  if p_revision_date is null then raise exception 'Revision Date is required'; end if;
  if trim(coalesce(p_file_name,''))='' or trim(coalesce(p_object_path,''))='' then raise exception 'Controlled drawing file is required'; end if;
  if not exists(select 1 from public.parts p where p.id=p_part_id and p.tenant_id=tid) then
    raise exception 'Part Master record was not found for the current tenant';
  end if;
  if exists(
    select 1 from public.document_attachments da
    where da.tenant_id=tid and da.entity_type='PART_MASTER' and da.entity_id=p_part_id
      and da.document_type=dtype and lower(coalesce(da.drawing_number,''))=lower(drawing_no)
      and lower(coalesce(da.revision,''))=lower(rev_no)
  ) then
    raise exception 'This Drawing Number and Revision Number already exist in revision history';
  end if;

  update public.document_attachments
     set status='INACTIVE', superseded_at=now(), superseded_by=auth.uid(), updated_at=now(), updated_by=auth.uid()
   where tenant_id=tid and entity_type='PART_MASTER' and entity_id=p_part_id
     and document_type=dtype and status='ACTIVE';

  insert into public.document_attachments(
    tenant_id, entity_type, entity_id, document_type, file_name, object_path,
    mime_type, size_bytes, checksum, revision, drawing_number, revision_date,
    status, created_by, updated_by
  ) values (
    tid, 'PART_MASTER', p_part_id, dtype, trim(p_file_name), trim(p_object_path),
    nullif(trim(coalesce(p_mime_type,'')),''), p_size_bytes, nullif(trim(coalesce(p_checksum,'')),''),
    rev_no, drawing_no, p_revision_date, 'ACTIVE', auth.uid(), auth.uid()
  ) returning * into new_row;

  if dtype='FINISH_DRAWING' then
    update public.parts
       set drawing_number=drawing_no, drawing_revision=rev_no, updated_at=now(), updated_by=auth.uid()
     where id=p_part_id and tenant_id=tid;
  end if;

  return to_jsonb(new_row);
end;
$$;

revoke all on function public.qcms_activate_part_drawing_revision(uuid,text,text,text,date,text,text,text,bigint,text) from public,anon;
grant execute on function public.qcms_activate_part_drawing_revision(uuid,text,text,text,date,text,text,text,bigint,text) to authenticated;

commit;
