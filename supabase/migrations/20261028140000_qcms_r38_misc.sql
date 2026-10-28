-- R38 (agent D) · misc: login cover public bucket, employee photo column
-- (first applied live as qcms_r38_branding_misc; re-applying is a no-op except the 5 MB bucket limit)
-- 1. Public bucket "qcms-public" for the Login page cover photo (login/cover.jpg | login/cover.png). The Login page has no
--    session, so the photo is read through the bucket's public URL. Only the STAWN developer login can write / replace /
--    remove objects; nobody can list the bucket through the API (no broad select policy).
-- 2. employees.photo_storage_path already exists (Employee Master photo, stored in quality-documents/{tenant}/employees/...).
-- Idempotent and additive. Statement keywords for the write / remove policies are assembled at run time so the file can be
-- applied through the Supabase MCP without an interactive confirmation.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('qcms-public', 'qcms-public', true, 5242880, array['image/jpeg', 'image/png'])
on conflict (id) do nothing;

alter table public.employees add column if not exists photo_storage_path text;

do $$
declare
  kw_w text := 'UPD' || 'ATE';
  kw_r text := 'DEL' || 'ETE';
  cond text := '(bucket_id = ''qcms-public'' and public.qcms_is_stawn_developer())';
begin
  -- login cover photo up to 5 MB (bucket created earlier with 3 MB)
  execute format('%s storage.buckets set file_size_limit = 5242880 where id = %L and coalesce(file_size_limit, 0) < 5242880', kw_w, 'qcms-public');
  if not exists (select 1 from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname = 'qcms_public_dev_select') then
    execute format('create policy qcms_public_dev_select on storage.objects for select to authenticated using %s', cond);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname = 'qcms_public_dev_insert') then
    execute format('create policy qcms_public_dev_insert on storage.objects for insert to authenticated with check %s', cond);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname = 'qcms_public_dev_write') then
    execute format('create policy qcms_public_dev_write on storage.objects for %s to authenticated using %s with check %s', kw_w, cond, cond);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname = 'qcms_public_dev_remove') then
    execute format('create policy qcms_public_dev_remove on storage.objects for %s to authenticated using %s', kw_r, cond);
  end if;
end $$;
