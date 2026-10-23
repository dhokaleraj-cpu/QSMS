-- QCMS v4.14.49 R36 · STAWN developer purge of TRIAL / TEST data.
-- Only the STAWN developer login (public.qcms_is_stawn_developer()) can preview or execute.
-- Additive and safe to re-run. This file never deletes data by itself: rows are removed only when
-- the developer calls public.qcms_dev_purge_execute(...) with the confirmation phrase and a reason.
--
-- How the purge set is built (current tenant only):
--   * roots      : selected rows of ONE allow-listed transaction table
--   * downstream : every row that references a row in the set through a real foreign key
--                  (recursive, de-duplicated, cycle-safe, depth limit 15) plus soft links
--                  (document_attachments / document_approvals / customer_report_package_items .entity_id,
--                   qcms_delete_requests.record_id, qcms_notification_outbox / qcms_user_notifications .related_id,
--                   qcms_password_edit_audit.entity_id)
--   * masters    : parts, parties, grades, processes, employees, profiles, tenants, layouts, part_* and qcms_*
--                  system tables are never added. A master row that still points at a purged row through a
--                  nullable column is set to NULL (archived first); a NOT NULL pointer blocks the purge.
--   * audit_log and qcms_user_activity_log are kept (they also record the purge itself).
-- Every purged / nulled row is archived to public.qcms_purge_archive (to_jsonb) before it is touched.

create schema if not exists qcms_private;
revoke all on schema qcms_private from public, anon, authenticated;

-- =====================================================================================
-- 1) Run log + archive (developer read-only through RLS; written only by the definer functions)
-- =====================================================================================
create table if not exists public.qcms_purge_runs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  root_table text not null,
  root_ids uuid[] not null default '{}',
  reason text not null,
  deleted_counts jsonb not null default '{}'::jsonb,
  nullified jsonb not null default '[]'::jsonb,
  storage_paths text[] not null default '{}',
  executed_by uuid default auth.uid(),
  executed_at timestamptz not null default now()
);
alter table public.qcms_purge_runs add column if not exists nullified jsonb not null default '[]'::jsonb;
create index if not exists qcms_purge_runs_tenant_idx on public.qcms_purge_runs (tenant_id, executed_at desc);

create table if not exists public.qcms_purge_archive (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.qcms_purge_runs(id) on delete cascade,
  tenant_id uuid not null,
  table_name text not null,
  record_id uuid not null,
  action text not null default 'DELETED',
  row_data jsonb not null,
  archived_at timestamptz not null default now()
);
alter table public.qcms_purge_archive add column if not exists action text not null default 'DELETED';
create index if not exists qcms_purge_archive_run_idx on public.qcms_purge_archive (run_id);
create index if not exists qcms_purge_archive_record_idx on public.qcms_purge_archive (table_name, record_id);

alter table public.qcms_purge_runs enable row level security;
alter table public.qcms_purge_archive enable row level security;
revoke all on public.qcms_purge_runs from anon, public;
revoke all on public.qcms_purge_archive from anon, public;
revoke insert, update, delete, truncate on public.qcms_purge_runs from authenticated;
revoke insert, update, delete, truncate on public.qcms_purge_archive from authenticated;
grant select on public.qcms_purge_runs to authenticated;
grant select on public.qcms_purge_archive to authenticated;

do $pol$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'qcms_purge_runs' and policyname = 'qcms_purge_runs_dev_select') then
    create policy qcms_purge_runs_dev_select on public.qcms_purge_runs for select to authenticated
      using ((select public.qcms_is_stawn_developer()));
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'qcms_purge_archive' and policyname = 'qcms_purge_archive_dev_select') then
    create policy qcms_purge_archive_dev_select on public.qcms_purge_archive for select to authenticated
      using ((select public.qcms_is_stawn_developer()));
  end if;
end $pol$;

-- =====================================================================================
-- 2) Internal helpers (schema qcms_private is not exposed through the REST API)
-- =====================================================================================

-- Transaction tables that may be chosen as purge roots.
create or replace function qcms_private.qcms_dev_purge_root_tables()
returns text[] language sql immutable set search_path = public as $$
  select array[
    'supply_customer_orders','supply_purchase_orders','supply_po_confirmations','supply_rm_purchase_orders',
    'supply_rm_receipts','supply_rm_dispatches','supply_forging_orders','supply_forging_receipts',
    'supply_downstream_events','supply_opening_stock','inward_lots','rmtc_approvals','lab_tests',
    'inspection_reports','osp_jobs','osp_receipts','osp_material_outs','production_batches','dispatches',
    'quality_complaints','npd_orders','qc_calculation_records','quality_asset_calibration_records',
    'standard_room_inspection_records'
  ]::text[]
$$;

-- Soft-linked rows that describe a record and go with it (matched on the uuid only; uuids are unique).
create or replace function qcms_private.qcms_dev_purge_soft_links()
returns table(child text, col text) language sql immutable set search_path = public as $$
  values ('document_attachments','entity_id'), ('document_approvals','entity_id'),
         ('customer_report_package_items','entity_id'), ('qcms_delete_requests','record_id'),
         ('qcms_notification_outbox','related_id'), ('qcms_user_notifications','related_id'),
         ('qcms_password_edit_audit','entity_id')
$$;

-- Master / system tables: never added to a purge set.
create or replace function qcms_private.qcms_dev_purge_protected(p_table text)
returns boolean language sql immutable set search_path = public as $$
  select p_table = any (array[
      'tenants','profiles','employees','parts','parties','processes','material_grades','material_grade_elements',
      'company_branches','quality_assets','standard_room_instruments','customer_standards','standards_register',
      'inspection_stages','inspection_plans','inspection_plan_characteristics','test_plans','calculation_rules',
      'jominy_distances','master_value_catalog','number_sequences','heat_code_sequences','supply_po_sequences',
      'supply_po_series_v41411','supply_stage_responsibilities','role_module_defaults','department_module_defaults',
      'user_module_permissions','user_section_permissions','gauge_fixture_assets','quality_asset_part_process_links',
      'npd_process_flows','npd_process_flow_steps','npd_process_flow_points','audit_log','qcms_purge_runs','qcms_purge_archive'
    ]::text[])
    or p_table like 'part\_%'
    or p_table like 'qsms\_%'
    or (p_table like 'qcms\_%' and p_table not in (select s.child from qcms_private.qcms_dev_purge_soft_links() s))
$$;

-- Short readable label for a row.
create or replace function qcms_private.qcms_dev_purge_label(r jsonb)
returns text language sql immutable set search_path = public as $$
  select coalesce(
    (select nullif(btrim(r ->> k), '')
       from unnest(array[
         'po_number','master_reference_no','customer_order_no','inward_number','rmtc_number','report_number',
         'osp_job_number','material_out_number','receipt_number','dispatch_number','supplier_order_no','reference_no',
         'complaint_number','order_number','calculation_number','certificate_number','confirmation_reference',
         'lot_reference','vendor_batch_number','batch_number','file_name','document_title','title','subject',
         'event_type','heat_number','item_no'
       ]) with ordinality u(k, o)
      where nullif(btrim(r ->> k), '') is not null
      order by o limit 1),
    left(r ->> 'id', 8))
$$;

-- Builds pg_temp._qcms_purge_walk / _qcms_purge_set / _qcms_purge_edges. Returns true when the depth limit was reached.
create or replace function qcms_private.qcms_dev_purge_collect(p_table text, p_ids uuid[], p_tenant uuid)
returns boolean language plpgsql security definer set search_path = public, pg_temp as $fn$
declare
  v_max constant int := 15;
  v_depth int;
  v_found int;
  v_wanted int;
  v_more boolean := false;
  e record;
begin
  if not public.qcms_is_stawn_developer() then
    raise exception 'DEV_PURGE_DENIED: only the STAWN developer login can purge trial data.' using errcode = '42501';
  end if;
  if p_tenant is null then
    raise exception 'DEV_PURGE: no active company for this login.';
  end if;
  if p_table is null or not (p_table = any (qcms_private.qcms_dev_purge_root_tables())) then
    raise exception 'DEV_PURGE: % is not a transaction table that can be purged.', coalesce(p_table, '(none)');
  end if;
  if to_regclass('public.' || quote_ident(p_table)) is null then
    raise exception 'DEV_PURGE: table % does not exist.', p_table;
  end if;
  v_wanted := (select count(distinct x) from unnest(coalesce(p_ids, '{}'::uuid[])) x where x is not null);
  if v_wanted = 0 then
    raise exception 'DEV_PURGE: select at least one record.';
  end if;

  -- _qcms_purge_walk keeps every (row, path length) pair reached; _qcms_purge_set keeps each row once
  -- with its LONGEST path from a root, so children always come before their parents in the purge order.
  create temp table if not exists _qcms_purge_walk (tbl text not null, id uuid not null, depth int not null, primary key (tbl, id, depth)) on commit drop;
  create temp table if not exists _qcms_purge_set (tbl text not null, id uuid not null, depth int not null, primary key (tbl, id)) on commit drop;
  create temp table if not exists _qcms_purge_edges (child text not null, col text not null, parent text, nullable boolean not null, follow boolean not null) on commit drop;
  truncate pg_temp._qcms_purge_walk;
  truncate pg_temp._qcms_purge_set;
  truncate pg_temp._qcms_purge_edges;

  -- real single-column foreign keys whose parent can be in a purge set
  insert into pg_temp._qcms_purge_edges (child, col, parent, nullable, follow)
  select distinct cl.relname::text, a.attname::text, pc.relname::text, not a.attnotnull,
         (not qcms_private.qcms_dev_purge_protected(cl.relname::text))
         and not (cl.relname = 'supply_purchase_orders' and a.attname = 'replacement_purchase_order_id')
    from pg_constraint con
    join pg_class cl on cl.oid = con.conrelid
    join pg_namespace cn on cn.oid = cl.relnamespace and cn.nspname = 'public'
    join pg_class pc on pc.oid = con.confrelid
    join pg_namespace pn on pn.oid = pc.relnamespace and pn.nspname = 'public'
    join pg_attribute a on a.attrelid = con.conrelid and a.attnum = con.conkey[1]
   where con.contype = 'f' and array_length(con.conkey, 1) = 1
     and not qcms_private.qcms_dev_purge_protected(pc.relname::text)
     and exists (select 1 from pg_attribute x where x.attrelid = cl.oid and x.attname = 'id' and not x.attisdropped)
     and exists (select 1 from pg_attribute x where x.attrelid = cl.oid and x.attname = 'tenant_id' and not x.attisdropped);

  -- soft links (no foreign key)
  insert into pg_temp._qcms_purge_edges (child, col, parent, nullable, follow)
  select s.child, s.col, null, true, true
    from qcms_private.qcms_dev_purge_soft_links() s
   where to_regclass('public.' || quote_ident(s.child)) is not null
     and exists (select 1 from information_schema.columns c where c.table_schema = 'public' and c.table_name = s.child and c.column_name = s.col);

  -- roots
  execute format('insert into pg_temp._qcms_purge_walk (tbl, id, depth) select %L, t.id, 0 from public.%I t where t.id = any ($1) and t.tenant_id = $2 on conflict do nothing', p_table, p_table)
    using p_ids, p_tenant;
  get diagnostics v_found = row_count;
  if v_found <> v_wanted then
    raise exception 'DEV_PURGE: % of % selected record(s) were not found in this company.', v_wanted - v_found, v_wanted;
  end if;

  -- level-by-level walk (cycle-safe: bounded by v_max levels)
  for v_depth in 0 .. v_max loop
    exit when not exists (select 1 from pg_temp._qcms_purge_walk w where w.depth = v_depth);
    for e in select * from pg_temp._qcms_purge_edges where follow order by child, col loop
      if e.parent is not null then
        continue when not exists (select 1 from pg_temp._qcms_purge_walk w where w.tbl = e.parent and w.depth = v_depth);
        execute format(
          'insert into pg_temp._qcms_purge_walk (tbl, id, depth)
             select %L, c.id, $1 + 1 from public.%I c
              where c.tenant_id = $2 and c.%I in (select w.id from pg_temp._qcms_purge_walk w where w.tbl = %L and w.depth = $1)
           on conflict do nothing',
          e.child, e.child, e.col, e.parent) using v_depth, p_tenant;
      else
        execute format(
          'insert into pg_temp._qcms_purge_walk (tbl, id, depth)
             select %L, c.id, $1 + 1 from public.%I c
              where c.tenant_id = $2 and c.%I in (select w.id from pg_temp._qcms_purge_walk w where w.depth = $1)
           on conflict do nothing',
          e.child, e.child, e.col) using v_depth, p_tenant;
      end if;
    end loop;
  end loop;

  insert into pg_temp._qcms_purge_set (tbl, id, depth)
  select w.tbl, w.id, max(w.depth) from pg_temp._qcms_purge_walk w group by w.tbl, w.id;

  -- anything still linked below the deepest level? (very deep chain or a data cycle)
  if exists (select 1 from pg_temp._qcms_purge_walk w where w.depth > v_max) then
    for e in select * from pg_temp._qcms_purge_edges where follow loop
      if e.parent is not null then
        execute format('select exists (select 1 from public.%I c where c.%I in (select w.id from pg_temp._qcms_purge_walk w where w.tbl = %L and w.depth > %s))',
                       e.child, e.col, e.parent, v_max) into v_more;
      else
        execute format('select exists (select 1 from public.%I c where c.%I in (select w.id from pg_temp._qcms_purge_walk w where w.depth > %s))',
                       e.child, e.col, v_max) into v_more;
      end if;
      exit when v_more;
    end loop;
  end if;
  return v_more;
end $fn$;

-- Summary of the collected set (tables, counts, samples, optional full rows, nulled links, blockers, storage paths).
create or replace function qcms_private.qcms_dev_purge_summary(p_table text, p_truncated boolean, p_include_rows boolean)
returns jsonb language plpgsql security definer set search_path = public, pg_temp as $fn$
declare
  t record;
  e record;
  v_tables jsonb := '[]'::jsonb;
  v_samples jsonb;
  v_rows jsonb;
  v_nullify jsonb := '[]'::jsonb;
  v_blockers jsonb := '[]'::jsonb;
  v_paths text[] := '{}';
  v_part text[];
  v_n bigint;
begin
  if not public.qcms_is_stawn_developer() then
    raise exception 'DEV_PURGE_DENIED: only the STAWN developer login can purge trial data.' using errcode = '42501';
  end if;
  for t in select s.tbl, count(*) as n, min(s.depth) as min_depth, max(s.depth) as max_depth
             from pg_temp._qcms_purge_set s group by s.tbl order by max(s.depth), s.tbl loop
    execute format(
      'select coalesce(jsonb_agg(q.x order by q.x ->> ''created_at''), ''[]''::jsonb) from (
         select jsonb_build_object(''id'', r.id, ''label'', qcms_private.qcms_dev_purge_label(to_jsonb(r)),
                  ''status'', coalesce(to_jsonb(r) ->> ''status'', to_jsonb(r) ->> ''approval_status'', to_jsonb(r) ->> ''confirmation_status''),
                  ''created_at'', to_jsonb(r) ->> ''created_at'', ''created_by'', to_jsonb(r) ->> ''created_by'', ''depth'', s.depth) as x
           from public.%I r join pg_temp._qcms_purge_set s on s.tbl = %L and s.id = r.id
          order by s.depth, r.id limit 50) q', t.tbl, t.tbl) into v_samples;
    v_rows := null;
    if p_include_rows then
      execute format('select coalesce(jsonb_agg(to_jsonb(r)), ''[]''::jsonb) from public.%I r where r.id in (select s.id from pg_temp._qcms_purge_set s where s.tbl = %L)', t.tbl, t.tbl)
        into v_rows;
    end if;
    v_tables := v_tables || jsonb_build_array(jsonb_build_object(
      'table', t.tbl, 'count', t.n, 'min_depth', t.min_depth, 'max_depth', t.max_depth,
      'is_root_table', t.tbl = p_table, 'samples', v_samples)
      || case when p_include_rows then jsonb_build_object('rows', v_rows) else '{}'::jsonb end);
    -- storage objects: any *_path column of the purged rows (attachment_path, object_path, microstructure_image_N_path ...)
    execute format(
      'select coalesce(array_agg(distinct kv.value), ''{}''::text[]) from public.%I r cross join lateral jsonb_each_text(to_jsonb(r)) kv
        where r.id in (select s.id from pg_temp._qcms_purge_set s where s.tbl = %L)
          and right(kv.key, 5) = ''_path'' and coalesce(btrim(kv.value), '''') <> ''''', t.tbl, t.tbl) into v_part;
    v_paths := v_paths || coalesce(v_part, '{}');
  end loop;

  -- keep files that an attachment row OUTSIDE the set still uses
  select coalesce(array_agg(distinct p order by p), '{}') into v_paths
    from unnest(v_paths) p
   where not exists (select 1 from public.document_attachments a
                      where a.object_path = p
                        and not exists (select 1 from pg_temp._qcms_purge_set s where s.tbl = 'document_attachments' and s.id = a.id));

  -- rows outside the set (masters / back-pointers) that still reference it
  for e in select * from pg_temp._qcms_purge_edges where not follow and parent is not null order by child, col loop
    continue when not exists (select 1 from pg_temp._qcms_purge_set s where s.tbl = e.parent);
    execute format('select count(*) from public.%I c where c.%I in (select s.id from pg_temp._qcms_purge_set s where s.tbl = %L)
                      and not exists (select 1 from pg_temp._qcms_purge_set s2 where s2.tbl = %L and s2.id = c.id)',
                   e.child, e.col, e.parent, e.child) into v_n;
    if v_n > 0 then
      if e.nullable then
        v_nullify := v_nullify || jsonb_build_array(jsonb_build_object('table', e.child, 'column', e.col, 'references', e.parent, 'count', v_n));
      else
        v_blockers := v_blockers || jsonb_build_array(jsonb_build_object('table', e.child, 'column', e.col, 'references', e.parent, 'count', v_n));
      end if;
    end if;
  end loop;

  return jsonb_build_object(
    'root_table', p_table,
    'root_count', (select count(*) from pg_temp._qcms_purge_set s where s.tbl = p_table and s.depth = 0),
    'total_rows', (select count(*) from pg_temp._qcms_purge_set),
    'tables', v_tables,
    'nullify', v_nullify,
    'blockers', v_blockers,
    'storage_paths', to_jsonb(v_paths),
    'depth_limit_reached', coalesce(p_truncated, false),
    'kept', jsonb_build_array('audit_log', 'qcms_user_activity_log', 'master tables (parts, parties, grades, processes, employees, layouts, part_*, qcms_* settings)')
  );
end $fn$;

revoke all on function qcms_private.qcms_dev_purge_root_tables() from public, anon, authenticated;
revoke all on function qcms_private.qcms_dev_purge_soft_links() from public, anon, authenticated;
revoke all on function qcms_private.qcms_dev_purge_protected(text) from public, anon, authenticated;
revoke all on function qcms_private.qcms_dev_purge_label(jsonb) from public, anon, authenticated;
revoke all on function qcms_private.qcms_dev_purge_collect(text, uuid[], uuid) from public, anon, authenticated;
revoke all on function qcms_private.qcms_dev_purge_summary(text, boolean, boolean) from public, anon, authenticated;

-- =====================================================================================
-- 3) Public RPCs
-- =====================================================================================
create or replace function public.qcms_dev_purge_preview(p_table text, p_ids uuid[], p_include_rows boolean default false)
returns jsonb language plpgsql security definer set search_path = public, pg_temp as $fn$
declare
  v_tenant uuid := public.current_tenant_id();
  v_truncated boolean;
begin
  if not public.qcms_is_stawn_developer() then
    raise exception 'DEV_PURGE_DENIED: only the STAWN developer login can purge trial data.' using errcode = '42501';
  end if;
  v_truncated := qcms_private.qcms_dev_purge_collect(p_table, p_ids, v_tenant);
  return qcms_private.qcms_dev_purge_summary(p_table, v_truncated, coalesce(p_include_rows, false))
         || jsonb_build_object('tenant_id', v_tenant, 'preview_only', true);
end $fn$;

create or replace function public.qcms_dev_purge_execute(p_table text, p_ids uuid[], p_confirm text, p_reason text)
returns jsonb language plpgsql security definer set search_path = public, pg_temp as $fn$
declare
  v_tenant uuid := public.current_tenant_id();
  v_truncated boolean;
  v_summary jsonb;
  v_run uuid;
  v_counts jsonb := '{}'::jsonb;
  v_paths text[];
  v_n bigint;
  v_total bigint := 0;
  t record;
  e record;
begin
  if not public.qcms_is_stawn_developer() then
    raise exception 'DEV_PURGE_DENIED: only the STAWN developer login can purge trial data.' using errcode = '42501';
  end if;
  if coalesce(p_confirm, '') <> 'DELETE TRIAL DATA' then
    raise exception 'DEV_PURGE: type DELETE TRIAL DATA exactly to confirm.';
  end if;
  if length(btrim(coalesce(p_reason, ''))) < 5 then
    raise exception 'DEV_PURGE: a reason (at least 5 characters) is mandatory.';
  end if;

  v_truncated := qcms_private.qcms_dev_purge_collect(p_table, p_ids, v_tenant);
  if v_truncated then
    raise exception 'DEV_PURGE: the linked chain is deeper than 15 levels (or contains a loop). Purge a lower-level transaction first.';
  end if;
  v_summary := qcms_private.qcms_dev_purge_summary(p_table, v_truncated, false);
  if jsonb_array_length(v_summary -> 'blockers') > 0 then
    raise exception 'DEV_PURGE_BLOCKED: master records still require these trial records: %', v_summary -> 'blockers';
  end if;
  select coalesce(array_agg(x), '{}') into v_paths from jsonb_array_elements_text(v_summary -> 'storage_paths') x;

  -- bypass the delete / update guards for THIS transaction only (see the patched trigger functions below)
  perform set_config('qcms.dev_purge', 'on', true);

  insert into public.qcms_purge_runs (tenant_id, root_table, root_ids, reason, executed_by)
  values (v_tenant, p_table, (select array_agg(distinct x) from unnest(p_ids) x where x is not null), btrim(p_reason), auth.uid())
  returning id into v_run;

  -- 1. archive every row of the set BEFORE anything is changed
  for t in select distinct s.tbl from pg_temp._qcms_purge_set s order by 1 loop
    execute format('insert into public.qcms_purge_archive (run_id, tenant_id, table_name, record_id, action, row_data)
                    select $1, $2, %L, r.id, ''DELETED'', to_jsonb(r) from public.%I r
                     where r.id in (select s.id from pg_temp._qcms_purge_set s where s.tbl = %L)', t.tbl, t.tbl, t.tbl)
      using v_run, v_tenant;
  end loop;

  -- 2. rows outside the set that point at it through a nullable column: archive, then set the column to NULL
  for e in select * from pg_temp._qcms_purge_edges where not follow and parent is not null and nullable order by child, col loop
    continue when not exists (select 1 from pg_temp._qcms_purge_set s where s.tbl = e.parent);
    execute format('insert into public.qcms_purge_archive (run_id, tenant_id, table_name, record_id, action, row_data)
                    select $1, $2, %L, c.id, %L, to_jsonb(c) from public.%I c
                     where c.%I in (select s.id from pg_temp._qcms_purge_set s where s.tbl = %L)
                       and not exists (select 1 from pg_temp._qcms_purge_set s2 where s2.tbl = %L and s2.id = c.id)',
                   e.child, 'NULLIFIED:' || e.col, e.child, e.col, e.parent, e.child)
      using v_run, v_tenant;
    execute format('update public.%I c set %I = null
                     where c.%I in (select s.id from pg_temp._qcms_purge_set s where s.tbl = %L)
                       and not exists (select 1 from pg_temp._qcms_purge_set s2 where s2.tbl = %L and s2.id = c.id)',
                   e.child, e.col, e.col, e.parent, e.child);
  end loop;

  -- 3. delete leaves first (deepest level first), all inside this one transaction
  for t in select s.tbl, s.depth from pg_temp._qcms_purge_set s group by s.tbl, s.depth order by s.depth desc, s.tbl loop
    execute format('delete from public.%I where id in (select s.id from pg_temp._qcms_purge_set s where s.tbl = %L and s.depth = $1)', t.tbl, t.tbl)
      using t.depth;
    get diagnostics v_n = row_count;
    v_counts := jsonb_set(v_counts, array[t.tbl], to_jsonb(coalesce((v_counts ->> t.tbl)::bigint, 0) + v_n));
    v_total := v_total + v_n;
  end loop;

  update public.qcms_purge_runs
     set deleted_counts = v_counts, nullified = v_summary -> 'nullify', storage_paths = v_paths
   where id = v_run;

  perform set_config('qcms.dev_purge', 'off', true);
  return jsonb_build_object(
    'run_id', v_run, 'root_table', p_table, 'deleted_counts', v_counts, 'total_deleted', v_total,
    'nullified', v_summary -> 'nullify', 'storage_paths', to_jsonb(v_paths));
end $fn$;

revoke all on function public.qcms_dev_purge_preview(text, uuid[], boolean) from public, anon;
revoke all on function public.qcms_dev_purge_execute(text, uuid[], text, text) from public, anon;
grant execute on function public.qcms_dev_purge_preview(text, uuid[], boolean) to authenticated;
grant execute on function public.qcms_dev_purge_execute(text, uuid[], text, text) to authenticated;

-- =====================================================================================
-- 4) Guard trigger functions: re-created from their LIVE definition with one early bypass line
--    that is active only inside qcms_dev_purge_execute (qcms.dev_purge = on, transaction-local)
--    and only for the STAWN developer login.
--      BEFORE DELETE : qcms_guard_approved_delete                      -> return old
--      BEFORE UPDATE : enforce_batch_genealogy (dispatch quantity give-back),
--                      qcms_guard_part_supplier_price_history, qcms_control_supply_po_identity
--                      (master / back-pointer columns set to NULL)      -> return new (UPDATE only)
-- =====================================================================================
do $patch$
declare
  v_fn text;
  v_def text;
  v_new text;
  v_line text;
begin
  foreach v_fn in array array['qcms_guard_approved_delete','enforce_batch_genealogy','qcms_guard_part_supplier_price_history','qcms_control_supply_po_identity'] loop
    select pg_get_functiondef(p.oid) into v_def
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname = v_fn and p.pronargs = 0 and p.prorettype = 'trigger'::regtype
     limit 1;
    if v_def is null then
      raise notice 'R36 dev purge: trigger function public.% not found - skipped', v_fn;
      continue;
    end if;
    if position('qcms.dev_purge' in v_def) > 0 then
      continue; -- already patched
    end if;
    if v_fn = 'qcms_guard_approved_delete' then
      v_line := E'\n  if current_setting(''qcms.dev_purge'', true) = ''on'' and public.qcms_is_stawn_developer() then return old; end if;';
    else
      v_line := E'\n  if tg_op = ''UPDATE'' and current_setting(''qcms.dev_purge'', true) = ''on'' and public.qcms_is_stawn_developer() then return new; end if;';
    end if;
    -- first "begin" line of the body only
    v_new := regexp_replace(v_def, E'\\nbegin[ \\t]*\\n', E'\nbegin' || v_line || E'\n', 'i');
    if v_new = v_def then
      raise notice 'R36 dev purge: could not place the bypass line in public.% - skipped', v_fn;
      continue;
    end if;
    execute v_new;
  end loop;
end $patch$;
