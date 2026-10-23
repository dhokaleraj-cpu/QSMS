-- QCMS R36b: APQP load / save / edit fix (additive, idempotent, no data changes).
-- Root cause of "APQP cannot retrieve / save records" was in the web page (selector was reset to
-- "New APQP Project" on every rerun). The schema, RLS and grants were verified live and are correct.
-- This migration only adds defence in depth so an APQP insert never fails on tenant_id when a
-- client omits it (same pattern as calculation_rules / audit_plans / customer_report_packages).

alter table if exists public.ppap_projects alter column tenant_id set default public.current_tenant_id();
alter table if exists public.ppap_documents alter column tenant_id set default public.current_tenant_id();

create index if not exists idx_ppap_projects_tenant_status on public.ppap_projects (tenant_id, status);

do $$
begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'ppap_projects' and policyname = 'tenant_insert') then
    execute 'create policy tenant_insert on public.ppap_projects for insert to authenticated with check ((tenant_id = public.current_tenant_id()) and public.can_write_table(''ppap_projects''))';
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'ppap_projects' and policyname = 'tenant_update') then
    execute 'create policy tenant_update on public.ppap_projects for update to authenticated using ((tenant_id = public.current_tenant_id()) and public.can_write_table(''ppap_projects'')) with check ((tenant_id = public.current_tenant_id()) and public.can_write_table(''ppap_projects''))';
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'ppap_documents' and policyname = 'tenant_insert') then
    execute 'create policy tenant_insert on public.ppap_documents for insert to authenticated with check ((tenant_id = public.current_tenant_id()) and public.can_write_table(''ppap_documents''))';
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'ppap_documents' and policyname = 'tenant_update') then
    execute 'create policy tenant_update on public.ppap_documents for update to authenticated using ((tenant_id = public.current_tenant_id()) and public.can_write_table(''ppap_documents'')) with check ((tenant_id = public.current_tenant_id()) and public.can_write_table(''ppap_documents''))';
  end if;
end $$;

grant select, insert, update, delete on public.ppap_projects, public.ppap_documents to authenticated;

notify pgrst, 'reload schema';
