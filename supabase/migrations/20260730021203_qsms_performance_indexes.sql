begin;

do $$
declare
  fk record;
  column_list text;
  index_name text;
begin
  for fk in
    select c.conrelid, c.conname, c.conkey, t.relname
    from pg_constraint c
    join pg_class t on t.oid = c.conrelid
    join pg_namespace n on n.oid = t.relnamespace
    where c.contype = 'f'
      and n.nspname = 'public'
      and not exists (
        select 1
        from pg_index i
        where i.indrelid = c.conrelid
          and i.indisvalid
          and i.indisready
          and (i.indkey::smallint[])[1:cardinality(c.conkey)] = c.conkey
      )
  loop
    select string_agg(quote_ident(a.attname), ', ' order by keys.ordinality)
      into column_list
    from unnest(fk.conkey) with ordinality as keys(attnum, ordinality)
    join pg_attribute a
      on a.attrelid = fk.conrelid
     and a.attnum = keys.attnum;

    index_name := left('idx_fk_' || fk.relname || '_' || substr(md5(fk.conname), 1, 10), 63);
    execute format('create index if not exists %I on %s (%s)', index_name, fk.conrelid::regclass, column_list);
  end loop;
end;
$$;

drop policy if exists profile_self_update on public.profiles;
drop policy if exists profile_admin_update on public.profiles;
drop policy if exists profile_update on public.profiles;
create policy profile_update on public.profiles
for update to authenticated
using (
  tenant_id = (select public.current_tenant_id())
  and (
    id = (select auth.uid())
    or (select public.current_app_role()) = 'ADMIN'
  )
)
with check (tenant_id = (select public.current_tenant_id()));

commit;
