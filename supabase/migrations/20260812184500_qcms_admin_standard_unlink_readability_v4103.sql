-- QCMS 4.10.3 — Admin-only Part/Standard unlink enforcement.
-- UI font changes are application CSS only; this migration protects the destructive link removal.

create or replace function public.qcms_admin_only_part_standard_unlink()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
begin
  if auth.uid() is null then
    raise exception 'Authentication required';
  end if;
  if coalesce(public.current_app_role(),'VIEWER') <> 'ADMIN' then
    raise exception 'Only a QCMS Administrator can unlink a Standard / Specification from a Part';
  end if;
  return old;
end;
$$;

drop trigger if exists trg_qcms_admin_part_standard_unlink on public.part_standard_links;
create trigger trg_qcms_admin_part_standard_unlink
before delete on public.part_standard_links
for each row execute function public.qcms_admin_only_part_standard_unlink();

-- Make the RLS delete policy express the same rule explicitly.
drop policy if exists tenant_delete on public.part_standard_links;
create policy tenant_delete on public.part_standard_links
for delete to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

revoke all on function public.qcms_admin_only_part_standard_unlink() from public,anon;
grant execute on function public.qcms_admin_only_part_standard_unlink() to authenticated;
