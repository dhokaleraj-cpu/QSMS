-- QCMS R25 · run once in Supabase → SQL Editor (safe to re-run).
-- Approved transactions can only be deleted after Admin approval; every deleted record stays
-- viewable / printable (Deleted Records archive, from audit_log + deletion requests).

-- 1) What counts as "approved"
create or replace function public.qcms_record_is_approved(p_row jsonb)
returns boolean language sql immutable as $fn$
  select upper(coalesce(p_row->>'approval_status','')) = 'APPROVED'
      or upper(coalesce(p_row->>'status','')) in ('APPROVED','RELEASED','FINAL','CLOSED','COMPLETED')
      or upper(coalesce(p_row->>'confirmation_status','')) = 'CONFIRMED'
$fn$;

-- 2) Deletion requests
create table if not exists public.qcms_delete_requests (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id) on delete cascade,
  table_name text not null,
  record_id uuid not null,
  record_label text,
  reason text not null,
  status text not null default 'PENDING' check (status in ('PENDING','APPROVED','EXECUTED','REJECTED','FAILED','CANCELLED')),
  record_snapshot jsonb,
  requested_by uuid default auth.uid(),
  requested_at timestamptz not null default now(),
  decided_by uuid,
  decided_at timestamptz,
  decision_note text,
  error_text text
);
create index if not exists idx_qcms_delete_requests_tenant on public.qcms_delete_requests (tenant_id, status, requested_at desc);
create index if not exists idx_qcms_delete_requests_record on public.qcms_delete_requests (table_name, record_id);
alter table public.qcms_delete_requests enable row level security;
drop policy if exists qcms_delete_requests_select on public.qcms_delete_requests;
create policy qcms_delete_requests_select on public.qcms_delete_requests for select to authenticated
  using (tenant_id = public.current_tenant_id() and (requested_by = auth.uid() or public.current_app_role() in ('ADMIN','QUALITY_MANAGER')));
grant select on public.qcms_delete_requests to authenticated;

-- 3) Guard: an approved row is never deleted unless an Admin-approved request is executing.
create or replace function public.qcms_guard_approved_delete()
returns trigger language plpgsql as $fn$
begin
  if public.qcms_record_is_approved(to_jsonb(old)) and coalesce(current_setting('qcms.approved_delete', true), '') <> 'on' then
    raise exception 'APPROVED_DELETE_BLOCKED: this % is approved / released and cannot be deleted directly. Send a deletion request - QCMS deletes it only after Admin approval.', replace(tg_table_name, '_', ' ');
  end if;
  return old;
end $fn$;

do $do$
declare t text;
begin
  foreach t in array array['supply_purchase_orders','supply_po_confirmations','supply_rm_purchase_orders','supply_forging_orders',
                           'supply_opening_stock','osp_jobs','rmtc_approvals','inward_lots','inspection_reports','lab_tests',
                           'npd_orders','ppap_projects','pfd_headers','pfmea_headers','control_plan_headers','qc_calculation_records',
                           'quality_complaints','quality_asset_calibration_records','standard_room_inspection_records'] loop
    if to_regclass('public.' || t) is not null then
      execute format('drop trigger if exists trg_qcms_guard_approved_delete on public.%I', t);
      execute format('create trigger trg_qcms_guard_approved_delete before delete on public.%I for each row execute function public.qcms_guard_approved_delete()', t);
    end if;
  end loop;
end $do$;

-- 4) Request a deletion (needs Delete/Archive permission of the module)
create or replace function public.qcms_request_delete(p_table_name text, p_record_id uuid, p_reason text, p_label text default null)
returns jsonb language plpgsql security definer set search_path to 'public', 'auth' as $fn$
declare tid uuid := public.current_tenant_id(); snap jsonb; req public.qcms_delete_requests%rowtype;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if coalesce(btrim(p_reason), '') = '' then raise exception 'Enter the reason for deletion'; end if;
  if to_regclass('public.' || p_table_name) is null then raise exception 'Unknown record type %', p_table_name; end if;
  if not public.qcms_effective_module_permission(public.qsms_module_for_table(p_table_name), 'archive') then
    raise exception 'Delete/Archive permission is not assigned for this module';
  end if;
  execute format('select to_jsonb(t) from public.%I t where t.id = $1 and t.tenant_id = $2', p_table_name) into snap using p_record_id, tid;
  if snap is null then raise exception 'Record not found'; end if;
  if exists (select 1 from public.qcms_delete_requests r where r.tenant_id = tid and r.table_name = p_table_name and r.record_id = p_record_id and r.status = 'PENDING') then
    raise exception 'A deletion request for this record is already waiting for Admin approval';
  end if;
  insert into public.qcms_delete_requests (tenant_id, table_name, record_id, record_label, reason, record_snapshot)
  values (tid, p_table_name, p_record_id, p_label, btrim(p_reason), snap) returning * into req;
  return to_jsonb(req);
end $fn$;
grant execute on function public.qcms_request_delete(text, uuid, text, text) to authenticated;

-- 5) Admin decision: approve (= delete now through the normal controlled delete) or reject
create or replace function public.qcms_decide_delete_request(p_request_id uuid, p_approve boolean, p_note text default null)
returns jsonb language plpgsql security definer set search_path to 'public', 'auth' as $fn$
declare tid uuid := public.current_tenant_id(); req public.qcms_delete_requests%rowtype; err text;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if public.current_app_role() <> 'ADMIN' then raise exception 'Only the QCMS Administrator can approve or reject deletion requests'; end if;
  select * into req from public.qcms_delete_requests where id = p_request_id and tenant_id = tid for update;
  if req.id is null then raise exception 'Deletion request not found'; end if;
  if req.status <> 'PENDING' and req.status <> 'FAILED' then raise exception 'This request is already %', req.status; end if;
  if not p_approve then
    update public.qcms_delete_requests set status = 'REJECTED', decided_by = auth.uid(), decided_at = now(), decision_note = p_note where id = req.id;
    return jsonb_build_object('status', 'REJECTED');
  end if;
  begin
    perform set_config('qcms.approved_delete', 'on', true);
    if req.table_name = 'supply_purchase_orders' then
      perform public.qcms_delete_purchase_order(req.record_id);
    elsif req.table_name = 'supply_customer_orders' then
      perform public.qcms_delete_customer_order(req.record_id);
    else
      perform public.qcms_delete_transaction_row(req.table_name, req.record_id);
    end if;
    perform set_config('qcms.approved_delete', '', true);
  exception when others then
    err := sqlerrm;
    perform set_config('qcms.approved_delete', '', true);
    update public.qcms_delete_requests set status = 'FAILED', decided_by = auth.uid(), decided_at = now(), decision_note = p_note, error_text = err where id = req.id;
    return jsonb_build_object('status', 'FAILED', 'error', err);
  end;
  update public.qcms_delete_requests set status = 'EXECUTED', decided_by = auth.uid(), decided_at = now(), decision_note = p_note, error_text = null where id = req.id;
  return jsonb_build_object('status', 'EXECUTED');
end $fn$;
grant execute on function public.qcms_decide_delete_request(uuid, boolean, text) to authenticated;

-- 6) Deleted Records archive (view / print). Admin & Quality Manager see everything;
--    other users see deletions of modules they can view.
create or replace function public.qcms_deleted_records(p_table_name text default null, p_from date default null, p_to date default null, p_limit integer default 500)
returns jsonb language plpgsql stable security definer set search_path to 'public', 'auth' as $fn$
declare tid uuid := public.current_tenant_id(); privileged boolean;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  privileged := public.current_app_role() in ('ADMIN','QUALITY_MANAGER');
  return coalesce((
    select jsonb_agg(row_to_json(x) order by x.deleted_at desc) from (
      select a.id as audit_id, a.table_name, a.row_id as record_id, a.changed_at as deleted_at, a.changed_by as deleted_by,
             coalesce(nullif(p.full_name,''), p.email, 'System') as deleted_by_name, a.old_data,
             r.reason as delete_reason, r.status as request_status, r.requested_at,
             coalesce(nullif(rq.full_name,''), rq.email) as requested_by_name,
             coalesce(nullif(ap.full_name,''), ap.email) as approved_by_name, r.decision_note
        from public.audit_log a
        left join public.profiles p on p.id = a.changed_by
        left join lateral (select * from public.qcms_delete_requests d where d.tenant_id = tid and d.table_name = a.table_name and d.record_id = a.row_id order by d.requested_at desc limit 1) r on true
        left join public.profiles rq on rq.id = r.requested_by
        left join public.profiles ap on ap.id = r.decided_by
       where a.tenant_id = tid and a.operation = 'DELETE'
         and (p_table_name is null or a.table_name = p_table_name)
         and (p_from is null or a.changed_at >= p_from)
         and (p_to is null or a.changed_at < p_to + 1)
         and (privileged or coalesce(public.qcms_effective_module_permission(public.qsms_module_for_table(a.table_name), 'view'), false))
       order by a.changed_at desc
       limit greatest(1, least(coalesce(p_limit, 500), 5000))
    ) x), '[]'::jsonb);
end $fn$;
grant execute on function public.qcms_deleted_records(text, date, date, integer) to authenticated;

notify pgrst, 'reload schema';
