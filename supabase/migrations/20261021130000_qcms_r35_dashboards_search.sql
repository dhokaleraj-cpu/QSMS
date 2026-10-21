-- QCMS v4.14.49 R35 · KPI start dashboard (department RPC), custom user dashboards, database-wide Global Search.
-- Safe to re-run: create table if not exists / create or replace / drop policy if exists.

-- ---------------------------------------------------------------------------------------------
-- 1. Custom KPI dashboards per user (multiple dashboards, widgets stored as layout jsonb)
-- ---------------------------------------------------------------------------------------------
create table if not exists public.qcms_user_dashboards (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id(),
  owner_profile_id uuid not null default auth.uid(),
  name text not null,
  description text,
  is_default boolean not null default false,
  shared_with_tenant boolean not null default false,
  layout jsonb not null default '{"widgets": []}'::jsonb,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists qcms_user_dashboards_owner_idx on public.qcms_user_dashboards (tenant_id, owner_profile_id, sort_order);
alter table public.qcms_user_dashboards enable row level security;
drop policy if exists qcms_user_dashboards_read on public.qcms_user_dashboards;
create policy qcms_user_dashboards_read on public.qcms_user_dashboards for select to authenticated
  using (tenant_id = public.current_tenant_id() and (owner_profile_id = (select auth.uid()) or shared_with_tenant));
drop policy if exists qcms_user_dashboards_insert on public.qcms_user_dashboards;
create policy qcms_user_dashboards_insert on public.qcms_user_dashboards for insert to authenticated
  with check (tenant_id = public.current_tenant_id() and owner_profile_id = (select auth.uid()));
drop policy if exists qcms_user_dashboards_update on public.qcms_user_dashboards;
create policy qcms_user_dashboards_update on public.qcms_user_dashboards for update to authenticated
  using (tenant_id = public.current_tenant_id() and owner_profile_id = (select auth.uid()))
  with check (tenant_id = public.current_tenant_id() and owner_profile_id = (select auth.uid()));
drop policy if exists qcms_user_dashboards_delete on public.qcms_user_dashboards;
create policy qcms_user_dashboards_delete on public.qcms_user_dashboards for delete to authenticated
  using (tenant_id = public.current_tenant_id() and owner_profile_id = (select auth.uid()));
grant select, insert, update, delete on public.qcms_user_dashboards to authenticated;
revoke all on public.qcms_user_dashboards from anon;

-- ---------------------------------------------------------------------------------------------
-- 2. KPI helpers + department dashboard RPC (security invoker: base-table RLS applies)
-- ---------------------------------------------------------------------------------------------
-- p_rows = [{"l": label, "s": series, "v": value}, ...]  ->  {"title","type","labels":[...],"series":[{"name","values":[...]}]}
create or replace function public.qcms_kpi_chart(p_title text, p_type text, p_rows jsonb)
returns jsonb language sql immutable set search_path = public as $$
  with r as (
    select coalesce(e->>'l', '-') as l, coalesce(nullif(e->>'s', ''), 'Value') as s,
           coalesce(nullif(e->>'v', '')::numeric, 0) as v, ord
    from jsonb_array_elements(coalesce(p_rows, '[]'::jsonb)) with ordinality as x(e, ord)
  ), labels as (select l, min(ord) as o from r group by l),
     series as (select s, min(ord) as o from r group by s)
  select jsonb_build_object(
    'title', p_title, 'type', p_type,
    'labels', coalesce((select jsonb_agg(l order by o) from labels), '[]'::jsonb),
    'series', coalesce((select jsonb_agg(jsonb_build_object('name', se.s, 'values',
        (select jsonb_agg(coalesce((select sum(r.v) from r where r.l = lb.l and r.s = se.s), 0) order by lb.o) from labels lb))
        order by se.o) from series se), '[]'::jsonb))
$$;

create or replace function public.qcms_kpi_card(p_label text, p_value numeric, p_unit text default '', p_tone text default 'neutral', p_route text default null)
returns jsonb language sql immutable set search_path = public as $$
  select jsonb_build_object('label', p_label, 'value', coalesce(p_value, 0), 'unit', coalesce(p_unit, ''), 'tone', coalesce(p_tone, 'neutral'), 'web_route', p_route)
$$;

-- Tasks waiting for the signed-in user (approvals, validations, assigned work).
create or replace function public.qcms_my_pending_tasks(p_limit integer default 40)
returns jsonb language plpgsql stable security invoker set search_path = public as $$
declare
  v_emp uuid;
  v_tasks jsonb := '[]'::jsonb;
  v_part jsonb;
  v_is_admin boolean := false;
begin
  begin v_emp := public.qcms_current_login_employee_id(); exception when others then v_emp := null; end;
  begin v_is_admin := coalesce(public.current_app_role(), '') = 'ADMIN'; exception when others then v_is_admin := false; end;

  if v_emp is not null then
    select coalesce(jsonb_agg(jsonb_build_object('title', 'Approve Purchase Order ' || coalesce(po_number, ''), 'category', 'APPROVAL',
             'module_key', 'SUPPLY_CHAIN', 'related_table', 'supply_purchase_orders', 'related_id', id, 'due', delivery_date,
             'web_route', 'supply-po-approval') order by submitted_at nulls last), '[]'::jsonb)
      into v_part from public.supply_purchase_orders
     where approver_employee_id = v_emp and coalesce(approval_status, '') = 'PENDING_APPROVAL';
    v_tasks := v_tasks || v_part;

    select coalesce(jsonb_agg(jsonb_build_object('title',
             case when coalesce(results->>'inspection_method', '') = 'BEND_TEST' then 'Bend Test ' else 'MetLAB ' end || coalesce(report_number, '') || ' · '
             || case when validated_by_employee_id = v_emp and validated_at is null then 'validate' else 'approve / finalize' end,
             'category', 'APPROVAL', 'module_key', 'METLAB_REPORT', 'related_table', 'lab_tests', 'related_id', id, 'due', test_date,
             'web_route', case when coalesce(results->>'inspection_method', '') = 'BEND_TEST' then 'bend-test-entry' else 'metlab-entry' end)
             order by created_at), '[]'::jsonb)
      into v_part from public.lab_tests
     where coalesce(status, '') <> 'FINAL' and (validated_by_employee_id = v_emp or approved_by_employee_id = v_emp);
    v_tasks := v_tasks || v_part;

    select coalesce(jsonb_agg(jsonb_build_object('title', 'Dimensional report ' || coalesce(report_number, '') || ' · '
             || case when validated_by_employee_id = v_emp and validated_at is null then 'validate' else 'approve / finalize' end,
             'category', 'APPROVAL', 'module_key', 'DIMENSIONAL_REPORT', 'related_table', 'inspection_reports', 'related_id', id,
             'due', inspection_date, 'web_route', 'dimensional-entry') order by created_at), '[]'::jsonb)
      into v_part from public.inspection_reports
     where coalesce(status, '') <> 'FINAL' and (validated_by_employee_id = v_emp or approved_by_employee_id = v_emp);
    v_tasks := v_tasks || v_part;

    select coalesce(jsonb_agg(jsonb_build_object('title', 'RMTC ' || coalesce(rmtc_number, heat_number, '') || ' · validation / decision',
             'category', 'APPROVAL', 'module_key', 'RMTC_ENTRY', 'related_table', 'rmtc_approvals', 'related_id', id,
             'due', certificate_date, 'web_route', 'rmtc-approval') order by created_at), '[]'::jsonb)
      into v_part from public.rmtc_approvals
     where coalesce(status, '') not in ('APPROVED', 'REJECTED', 'CANCELLED')
       and (validated_by_employee_id = v_emp or approved_by_employee_id = v_emp or decision_by_employee_id = v_emp);
    v_tasks := v_tasks || v_part;

    select coalesce(jsonb_agg(jsonb_build_object('title', 'Complaint ' || coalesce(complaint_number, '') || ' · ' || coalesce(left(subject, 60), ''),
             'category', 'TASK', 'module_key', 'COMPLAINT_MANAGEMENT', 'related_table', 'quality_complaints', 'related_id', id,
             'due', coalesce(containment_due_date, target_closure_date), 'web_route', 'complaint-analysis') order by target_closure_date nulls last), '[]'::jsonb)
      into v_part from public.quality_complaints
     where coalesce(status, '') not in ('CLOSED', 'CANCELLED')
       and (fourstar_responsible_employee_id = v_emp or containment_responsible_employee_id = v_emp or root_cause_responsible_employee_id = v_emp);
    v_tasks := v_tasks || v_part;

    select coalesce(jsonb_agg(jsonb_build_object('title', 'NPD step OP ' || coalesce(s.operation_no::text, '') || ' · ' || coalesce(s.process_name, '')
             || ' · ' || coalesce(o.order_number, ''), 'category', 'TASK', 'module_key', 'NPD_APQP', 'related_table', 'npd_order_steps',
             'related_id', s.id, 'due', s.target_date, 'web_route', 'npd-status') order by s.target_date nulls last), '[]'::jsonb)
      into v_part from public.npd_order_steps s left join public.npd_orders o on o.id = s.npd_order_id
     where s.responsible_employee_id = v_emp and coalesce(s.status, '') not in ('COMPLETED', 'DONE', 'CLOSED', 'CANCELLED');
    v_tasks := v_tasks || v_part;

    select coalesce(jsonb_agg(jsonb_build_object('title', 'APQP / PPAP ' || coalesce(project_code, ''), 'category', 'TASK',
             'module_key', 'NPD_APQP', 'related_table', 'ppap_projects', 'related_id', id, 'due', target_submission_date,
             'web_route', 'apqp') order by target_submission_date nulls last), '[]'::jsonb)
      into v_part from public.ppap_projects
     where coalesce(coordinator_employee_id::text, '') = v_emp::text and coalesce(status, '') not in ('COMPLETED', 'CLOSED', 'CANCELLED', 'APPROVED');
    v_tasks := v_tasks || v_part;

    select coalesce(jsonb_agg(jsonb_build_object('title', 'Customer order ' || coalesce(customer_order_no, master_reference_no, '')
             || coalesce(' / ' || order_position, ''), 'category', 'TASK', 'module_key', 'SUPPLY_CHAIN', 'related_table', 'supply_customer_orders',
             'related_id', id, 'due', customer_delivery_date, 'web_route', 'supply-customer-orders') order by customer_delivery_date nulls last), '[]'::jsonb)
      into v_part from public.supply_customer_orders
     where responsible_employee_id = v_emp and coalesce(status, '') = 'OPEN';
    v_tasks := v_tasks || v_part;
  end if;

  if v_is_admin then
    select coalesce(jsonb_agg(jsonb_build_object('title', 'Deletion request · ' || coalesce(record_label, table_name), 'category', 'APPROVAL',
             'module_key', 'ADMIN', 'related_table', 'qcms_delete_requests', 'related_id', id, 'due', requested_at::date,
             'web_route', 'records-center') order by requested_at), '[]'::jsonb)
      into v_part from public.qcms_delete_requests where coalesce(status, '') = 'PENDING';
    v_tasks := v_tasks || v_part;
  end if;

  select coalesce(jsonb_agg(e), '[]'::jsonb) into v_tasks
    from (select e from jsonb_array_elements(v_tasks) e limit greatest(1, coalesce(p_limit, 40))) x;
  return v_tasks;
end $$;

create or replace function public.qcms_kpi_dashboard(p_department text default 'QUALITY')
returns jsonb language plpgsql stable security invoker set search_path = public as $$
declare
  v_dept text := upper(coalesce(nullif(trim(p_department), ''), 'QUALITY'));
  v_month date := date_trunc('month', current_date)::date;
  v_from date := (date_trunc('month', current_date) - interval '5 months')::date;
  v_cards jsonb := '[]'::jsonb;
  v_charts jsonb := '[]'::jsonb;
  v_rows jsonb;
  n1 numeric; n2 numeric; n3 numeric; n4 numeric; n5 numeric; n6 numeric; n7 numeric; n8 numeric;
  v_unread integer := 0;
begin
  if v_dept in ('SUPPLY', 'SCM', 'SUPPLYCHAIN') then v_dept := 'SUPPLY_CHAIN'; end if;
  if v_dept in ('APQP', 'NPD_APQP') then v_dept := 'NPD'; end if;

  if v_dept = 'QUALITY' then
    select count(*) into n1 from public.inward_lots where status = 'HOLD_PENDING_INSPECTION';
    select count(*) filter (where coalesce(results->>'inspection_method', '') <> 'BEND_TEST' and status <> 'FINAL'),
           count(*) filter (where coalesce(results->>'inspection_method', '') = 'BEND_TEST' and status <> 'FINAL'),
           count(*) filter (where status = 'FINAL' and coalesce(decision_at, updated_at) >= v_month)
      into n2, n3, n4 from public.lab_tests;
    select count(*) filter (where status <> 'FINAL'), count(*) filter (where status = 'FINAL' and coalesce(decision_at, updated_at) >= v_month)
      into n5, n6 from public.inspection_reports;
    n4 := n4 + n6;
    select case when sum(coalesce(accepted_production_quantity_pcs, 0) + coalesce(rejected_production_quantity_pcs, 0)) > 0
                then round(100 * sum(coalesce(rejected_production_quantity_pcs, 0)) / sum(coalesce(accepted_production_quantity_pcs, 0) + coalesce(rejected_production_quantity_pcs, 0)), 2)
                else 0 end into n6
      from public.inward_lots where created_at >= current_date - 180;
    select count(*) into n7 from public.rmtc_approvals where coalesce(status, '') not in ('APPROVED', 'REJECTED', 'CANCELLED');
    select count(*) into n8 from public.quality_complaints where coalesce(status, '') not in ('CLOSED', 'CANCELLED');
    v_cards := jsonb_build_array(
      public.qcms_kpi_card('Inward on quality hold', n1, 'lots', case when n1 > 0 then 'warning' else 'good' end, 'inward-records'),
      public.qcms_kpi_card('MetLAB pending', n2, 'reports', case when n2 > 10 then 'critical' when n2 > 0 then 'warning' else 'good' end, 'metlab-records'),
      public.qcms_kpi_card('Bend Test pending', n3, 'reports', case when n3 > 0 then 'warning' else 'good' end, 'bend-test-records'),
      public.qcms_kpi_card('Dimensional pending', n5, 'reports', case when n5 > 10 then 'critical' when n5 > 0 then 'warning' else 'good' end, 'dimensional-records'),
      public.qcms_kpi_card('Reports finalized this month', n4, 'reports', 'good', 'records-center'),
      public.qcms_kpi_card('Rejection (180 days)', n6, '%', case when n6 > 2 then 'critical' when n6 > 0.5 then 'warning' else 'good' end, 'inward-records'),
      public.qcms_kpi_card('RMTC pending', n7, 'certificates', case when n7 > 0 then 'warning' else 'good' end, 'rmtc-records'),
      public.qcms_kpi_card('Complaints open', n8, 'complaints', case when n8 > 5 then 'critical' when n8 > 0 then 'warning' else 'good' end, 'complaint-records'));
    select count(*) filter (where least(next_due_date, next_validation_due_date) < current_date),
           count(*) filter (where least(next_due_date, next_validation_due_date) between current_date and current_date + 30)
      into n1, n2 from public.quality_assets where coalesce(status, 'ACTIVE') = 'ACTIVE';
    v_cards := v_cards || jsonb_build_array(
      public.qcms_kpi_card('Calibration overdue', n1, 'assets', case when n1 > 0 then 'critical' else 'good' end, 'calibration-validation'),
      public.qcms_kpi_card('Calibration due ≤ 30 days', n2, 'assets', case when n2 > 0 then 'warning' else 'good' end, 'calibration-validation'));

    -- Accept / reject trend: finalized reports per month by decision
    select coalesce(jsonb_agg(jsonb_build_object('l', to_char(m, 'Mon YY'), 's', d, 'v', c) order by m, d), '[]'::jsonb) into v_rows from (
      select gs.m, coalesce(x.d, 'Accepted') d, coalesce(x.c, 0) c
        from generate_series(v_from, v_month, interval '1 month') gs(m)
        left join (
          select date_trunc('month', coalesce(decision_at, updated_at))::date mm, initcap(replace(coalesce(disposition, 'PENDING'), '_', ' ')) d, count(*) c
            from (select decision_at, updated_at, disposition from public.lab_tests where status = 'FINAL'
                  union all select decision_at, updated_at, disposition from public.inspection_reports where status = 'FINAL') u
           where coalesce(decision_at, updated_at) >= v_from group by 1, 2) x on x.mm = gs.m) y;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('Finalized reports by decision (6 months)', 'bar', v_rows));

    select coalesce(jsonb_agg(jsonb_build_object('l', l, 's', s, 'v', c) order by o, s), '[]'::jsonb) into v_rows from (
      select case when coalesce(results->>'inspection_method', '') = 'BEND_TEST' then 'Bend Test' else 'MetLAB' end l,
             case when coalesce(results->>'inspection_method', '') = 'BEND_TEST' then 2 else 1 end o,
             case when status = 'FINAL' then 'Final' else 'Draft / pending' end s, count(*) c from public.lab_tests group by 1, 2, 3
      union all
      select 'Dimensional', 3, case when status = 'FINAL' then 'Final' else 'Draft / pending' end, count(*) from public.inspection_reports group by 3) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('Inspection reports by status', 'bar', v_rows));

    select coalesce(jsonb_agg(jsonb_build_object('l', l, 's', 'Open complaints', 'v', c) order by c desc), '[]'::jsonb) into v_rows from (
      select coalesce(p.party_name, p.party_code, 'Unassigned') l, count(*) c
        from public.quality_complaints q left join public.parties p on p.id = q.party_id
       where coalesce(q.status, '') not in ('CLOSED', 'CANCELLED') group by 1 order by 2 desc limit 8) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('Open complaints by customer / supplier', 'donut', v_rows));

    select coalesce(jsonb_agg(jsonb_build_object('l', l, 's', 'Assets due', 'v', c) order by o), '[]'::jsonb) into v_rows from (
      select 'Overdue' l, 0 o, count(*) c from public.quality_assets
       where coalesce(status, 'ACTIVE') = 'ACTIVE' and least(next_due_date, next_validation_due_date) < current_date
      union all
      select to_char(gs.m, 'Mon YY'), 1 + row_number() over (order by gs.m), (select count(*) from public.quality_assets a
              where coalesce(a.status, 'ACTIVE') = 'ACTIVE' and date_trunc('month', least(a.next_due_date, a.next_validation_due_date)) = gs.m
                and least(a.next_due_date, a.next_validation_due_date) >= current_date)
        from generate_series(v_month, v_month + interval '5 months', interval '1 month') gs(m)) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('Calibration / validation due', 'bar', v_rows));

  elsif v_dept = 'SUPPLY_CHAIN' then
    select count(*) filter (where status in ('OPEN', 'IN_PROGRESS')), coalesce(sum(order_qty_pcs) filter (where status in ('OPEN', 'IN_PROGRESS')), 0)
      into n1, n2 from public.supply_customer_orders;
    select count(*) filter (where approval_status = 'PENDING_APPROVAL'), count(*) filter (where status in ('OPEN', 'PARTIAL'))
      into n3, n4 from public.supply_purchase_orders;
    select coalesce(sum(ordered_qty_kg) filter (where status = 'OPEN'), 0) into n5 from public.supply_rm_purchase_orders;
    select coalesce(sum(received_qty_kg), 0) into n6 from public.supply_rm_receipts where receipt_date >= v_month;
    select count(*) filter (where status = 'OPEN') into n7 from public.supply_forging_orders;
    select coalesce(sum(qty_pcs), 0) into n8 from public.supply_downstream_events where event_type = 'CUSTOMER_DISPATCH' and event_date >= v_month;
    v_cards := jsonb_build_array(
      public.qcms_kpi_card('Open customer orders', n1, 'orders', 'neutral', 'supply-customer-orders'),
      public.qcms_kpi_card('Open order quantity', n2, 'pcs', 'neutral', 'supply-order-mis'),
      public.qcms_kpi_card('PO pending approval', n3, 'POs', case when n3 > 0 then 'warning' else 'good' end, 'supply-po-approval'),
      public.qcms_kpi_card('Open purchase orders', n4, 'POs', 'neutral', 'supply-po-order-list'),
      public.qcms_kpi_card('RM on order', n5, 'kg', 'neutral', 'supply-rm-procurement'),
      public.qcms_kpi_card('RM received this month', n6, 'kg', 'good', 'supply-rm-receipt'),
      public.qcms_kpi_card('Forging orders open', n7, 'orders', 'neutral', 'supply-forging'),
      public.qcms_kpi_card('Dispatched this month', n8, 'pcs', 'good', 'supply-downstream'));

    select coalesce(jsonb_agg(jsonb_build_object('l', l, 's', 'POs', 'v', c) order by c desc), '[]'::jsonb) into v_rows from (
      select initcap(replace(coalesce(status, 'DRAFT'), '_', ' ')) l, count(*) c from public.supply_purchase_orders group by 1) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('Purchase orders by status', 'donut', v_rows));

    select coalesce(jsonb_agg(jsonb_build_object('l', to_char(m, 'Mon YY'), 's', s, 'v', v) order by m, s), '[]'::jsonb) into v_rows from (
      select gs.m, 'RM ordered kg' s, coalesce((select sum(ordered_qty_kg) from public.supply_rm_purchase_orders where status <> 'CANCELLED' and date_trunc('month', order_date) = gs.m), 0) v
        from generate_series(v_from, v_month, interval '1 month') gs(m)
      union all
      select gs.m, 'RM received kg', coalesce((select sum(received_qty_kg) from public.supply_rm_receipts where date_trunc('month', receipt_date) = gs.m), 0)
        from generate_series(v_from, v_month, interval '1 month') gs(m)) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('RM ordered vs received (kg)', 'line', v_rows));

    select coalesce(jsonb_agg(jsonb_build_object('l', l, 's', s, 'v', v) order by l, s), '[]'::jsonb) into v_rows from (
      select coalesce(p.party_name, p.party_code, 'Unassigned') l, 'Ordered pcs' s, sum(f.order_qty_pcs) v
        from public.supply_forging_orders f left join public.parties p on p.id = f.forging_supplier_id where f.status <> 'CANCELLED' group by 1
      union all
      select coalesce(p.party_name, p.party_code, 'Unassigned'), 'Received pcs', sum(r.received_qty_pcs)
        from public.supply_forging_receipts r left join public.parties p on p.id = r.forging_supplier_id group by 1) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('Forging ordered vs received by supplier', 'bar', v_rows));

    select coalesce(jsonb_agg(jsonb_build_object('l', to_char(m, 'Mon YY'), 's', s, 'v', v) order by m, s), '[]'::jsonb) into v_rows from (
      select gs.m, 'Schedule pcs' s, coalesce((select sum(order_qty_pcs) from public.supply_customer_orders where status <> 'CANCELLED' and date_trunc('month', coalesce(schedule_month, customer_delivery_date)) = gs.m), 0) v
        from generate_series(v_from, v_month + interval '2 months', interval '1 month') gs(m)
      union all
      select gs.m, 'Dispatched pcs', coalesce((select sum(qty_pcs) from public.supply_downstream_events where event_type = 'CUSTOMER_DISPATCH' and date_trunc('month', event_date) = gs.m), 0)
        from generate_series(v_from, v_month + interval '2 months', interval '1 month') gs(m)) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('Customer schedule vs dispatch (pcs)', 'bar', v_rows));

  elsif v_dept = 'PRODUCTION' then
    select coalesce(sum(quantity_available), 0), count(*) filter (where coalesce(status, '') not in ('CLOSED', 'CONSUMED', 'CANCELLED'))
      into n1, n2 from public.production_batches;
    select count(*) filter (where status = 'AT_VENDOR'), count(*) filter (where coalesce(sample_gate_status, '') in ('PENDING', 'ON_HOLD')),
           count(*) filter (where coalesce(receipt_quality_disposition, '') in ('PENDING', 'ON_HOLD') and coalesce(quantity_received, 0) > 0)
      into n3, n4, n5 from public.osp_jobs;
    select coalesce(sum(qty_pcs) filter (where event_type = 'MACHINING'), 0), coalesce(sum(qty_pcs) filter (where event_type = 'FINISHED_GOODS'), 0),
           coalesce(sum(qty_pcs) filter (where event_type = 'CUSTOMER_DISPATCH'), 0)
      into n6, n7, n8 from public.supply_downstream_events where event_date >= v_month;
    v_cards := jsonb_build_array(
      public.qcms_kpi_card('Pieces available in batches', n1, 'pcs', 'neutral', 'osp-records'),
      public.qcms_kpi_card('Active production batches', n2, 'batches', 'neutral', 'osp-records'),
      public.qcms_kpi_card('OSP at vendor', n3, 'jobs', 'neutral', 'osp-home'),
      public.qcms_kpi_card('OSP sample pending', n4, 'jobs', case when n4 > 0 then 'warning' else 'good' end, 'osp-sample-receipt'),
      public.qcms_kpi_card('OSP receipt quality pending', n5, 'jobs', case when n5 > 0 then 'warning' else 'good' end, 'osp-dimensional'),
      public.qcms_kpi_card('Machined this month', n6, 'pcs', 'good', 'supply-downstream'),
      public.qcms_kpi_card('Finished goods this month', n7, 'pcs', 'good', 'supply-downstream'),
      public.qcms_kpi_card('Dispatched this month', n8, 'pcs', 'good', 'supply-downstream'));
    select coalesce(jsonb_agg(jsonb_build_object('l', l, 's', 'OSP jobs', 'v', c) order by c desc), '[]'::jsonb) into v_rows from (
      select initcap(replace(coalesce(status, 'OPEN'), '_', ' ')) l, count(*) c from public.osp_jobs group by 1) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('OSP jobs by status', 'donut', v_rows));
    select coalesce(jsonb_agg(jsonb_build_object('l', to_char(m, 'Mon YY'), 's', s, 'v', v) order by m, s), '[]'::jsonb) into v_rows from (
      select gs.m, initcap(replace(t.e, '_', ' ')) s,
             coalesce((select sum(qty_pcs) from public.supply_downstream_events d where d.event_type = t.e and date_trunc('month', d.event_date) = gs.m), 0) v
        from generate_series(v_from, v_month, interval '1 month') gs(m)
        cross join (values ('MACHINING'), ('FINISHED_GOODS'), ('CUSTOMER_DISPATCH')) t(e)) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('Machining / FG / dispatch (pcs)', 'bar', v_rows));
    select coalesce(jsonb_agg(jsonb_build_object('l', l, 's', 'Pieces', 'v', v) order by v desc), '[]'::jsonb) into v_rows from (
      select coalesce(p.part_number, 'Unassigned') l, sum(b.quantity_available) v from public.production_batches b
        left join public.parts p on p.id = b.part_id where coalesce(b.quantity_available, 0) > 0 group by 1 order by 2 desc limit 10) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('Top parts available in batches (pcs)', 'bar', v_rows));

  elsif v_dept = 'NPD' then
    select count(*) filter (where status = 'OPEN'), count(*) filter (where status = 'IN_PROGRESS'),
           count(*) filter (where coalesce(status, '') not in ('COMPLETED', 'CLOSED', 'CANCELLED') and delivery_date < current_date)
      into n1, n2, n3 from public.npd_orders;
    select count(*) filter (where coalesce(status, '') not in ('COMPLETED', 'CLOSED', 'CANCELLED', 'APPROVED')),
           coalesce(round(avg(completion_percent), 1), 0) into n4, n5 from public.ppap_projects;
    select count(*) filter (where coalesce(status, '') not in ('COMPLETED', 'DONE', 'CLOSED', 'CANCELLED') and target_date < current_date),
           count(*) filter (where coalesce(status, '') not in ('COMPLETED', 'DONE', 'CLOSED', 'CANCELLED'))
      into n6, n7 from public.npd_order_steps;
    v_cards := jsonb_build_array(
      public.qcms_kpi_card('NPD open', n1, 'orders', 'neutral', 'npd-status'),
      public.qcms_kpi_card('NPD in progress', n2, 'orders', 'neutral', 'npd-status'),
      public.qcms_kpi_card('NPD late', n3, 'orders', case when n3 > 0 then 'critical' else 'good' end, 'npd-status'),
      public.qcms_kpi_card('APQP / PPAP active', n4, 'projects', 'neutral', 'apqp'),
      public.qcms_kpi_card('APQP average completion', n5, '%', case when n5 >= 80 then 'good' when n5 >= 40 then 'warning' else 'neutral' end, 'apqp'),
      public.qcms_kpi_card('NPD steps open', n7, 'steps', 'neutral', 'npd-status'),
      public.qcms_kpi_card('NPD steps overdue', n6, 'steps', case when n6 > 0 then 'critical' else 'good' end, 'npd-status'));
    select coalesce(jsonb_agg(jsonb_build_object('l', l, 's', 'NPD orders', 'v', c)), '[]'::jsonb) into v_rows from (
      select initcap(replace(coalesce(status, 'OPEN'), '_', ' ')) l, count(*) c from public.npd_orders group by 1) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('NPD orders by status', 'donut', v_rows));
    select coalesce(jsonb_agg(jsonb_build_object('l', l, 's', 'Steps', 'v', c)), '[]'::jsonb) into v_rows from (
      select initcap(replace(coalesce(status, 'PENDING'), '_', ' ')) l, count(*) c from public.npd_order_steps group by 1) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('NPD steps by status', 'bar', v_rows));
    select coalesce(jsonb_agg(jsonb_build_object('l', l, 's', 'Completion %', 'v', v)), '[]'::jsonb) into v_rows from (
      select coalesce(project_code, '-') l, coalesce(completion_percent, 0) v from public.ppap_projects order by target_submission_date nulls last limit 12) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('APQP / PPAP completion', 'bar', v_rows));

  else  -- MANAGEMENT
    v_dept := 'MANAGEMENT';
    select count(*) filter (where status = 'FINAL'), count(*) filter (where status = 'FINAL' and disposition = 'ACCEPTED')
      into n1, n2 from (select status, disposition from public.lab_tests union all select status, disposition from public.inspection_reports) u;
    select coalesce(sum(grand_total) filter (where status in ('OPEN', 'PARTIAL')), 0) into n3 from public.supply_purchase_orders;
    select count(*) into n4 from public.quality_complaints where coalesce(status, '') not in ('CLOSED', 'CANCELLED');
    select count(*) into n5 from public.inward_lots where status = 'RELEASED' and coalesce(released_at, updated_at) >= v_month;
    select count(*) into n6 from public.quality_assets where coalesce(status, 'ACTIVE') = 'ACTIVE' and least(next_due_date, next_validation_due_date) < current_date;
    select count(*) filter (where status in ('OPEN', 'IN_PROGRESS')) into n7 from public.supply_customer_orders;
    n8 := case when n1 > 0 then round(100 * n2 / n1, 1) else 0 end;
    v_cards := jsonb_build_array(
      public.qcms_kpi_card('First-pass yield (final reports)', n8, '%', case when n8 >= 98 then 'good' when n8 >= 95 then 'warning' else 'critical' end, 'records-center'),
      public.qcms_kpi_card('Open PO value', n3, 'INR', 'neutral', 'supply-po-order-list'),
      public.qcms_kpi_card('Open customer orders', n7, 'orders', 'neutral', 'supply-customer-orders'),
      public.qcms_kpi_card('Complaints open', n4, 'complaints', case when n4 > 0 then 'warning' else 'good' end, 'complaint-records'),
      public.qcms_kpi_card('Heats released this month', n5, 'lots', 'good', 'inward-records'),
      public.qcms_kpi_card('Calibration overdue', n6, 'assets', case when n6 > 0 then 'critical' else 'good' end, 'calibration-validation'));
    select coalesce(jsonb_agg(jsonb_build_object('l', to_char(m, 'Mon YY'), 's', s, 'v', v) order by m, s), '[]'::jsonb) into v_rows from (
      select gs.m, 'Raised' s, (select count(*) from public.quality_complaints where date_trunc('month', complaint_date) = gs.m) v
        from generate_series(v_from, v_month, interval '1 month') gs(m)
      union all
      select gs.m, 'Closed', (select count(*) from public.quality_complaints where date_trunc('month', closure_date) = gs.m)
        from generate_series(v_from, v_month, interval '1 month') gs(m)) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('Complaints raised vs closed', 'line', v_rows));
    select coalesce(jsonb_agg(jsonb_build_object('l', l, 's', 'Open PO value', 'v', v) order by v desc), '[]'::jsonb) into v_rows from (
      select coalesce(p.party_name, p.party_code, 'Unassigned') l, sum(o.grand_total) v from public.supply_purchase_orders o
        left join public.parties p on p.id = o.supplier_id where o.status in ('OPEN', 'PARTIAL') group by 1 order by 2 desc limit 8) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('Open PO value by supplier', 'bar', v_rows));
    select coalesce(jsonb_agg(jsonb_build_object('l', l, 's', 'Reports', 'v', c) order by c desc), '[]'::jsonb) into v_rows from (
      select initcap(replace(coalesce(disposition, 'PENDING'), '_', ' ')) l, count(*) c
        from (select disposition from public.lab_tests where status = 'FINAL' union all select disposition from public.inspection_reports where status = 'FINAL') u group by 1) z;
    v_charts := v_charts || jsonb_build_array(public.qcms_kpi_chart('Final quality decisions', 'donut', v_rows));
  end if;

  if to_regclass('public.qcms_user_notifications') is not null then
    begin
      execute 'select count(*) from public.qcms_user_notifications where recipient_profile_id = auth.uid() and not coalesce(is_read, false)' into v_unread;
    exception when others then v_unread := 0;
    end;
  end if;

  return jsonb_build_object('department', v_dept, 'generated_at', now(), 'cards', v_cards, 'charts', v_charts,
                            'pending_tasks', public.qcms_my_pending_tasks(40), 'unread_notifications', coalesce(v_unread, 0));
end $$;

-- ---------------------------------------------------------------------------------------------
-- 3. Database-wide Global Search (security invoker: RLS decides what each user can see)
-- ---------------------------------------------------------------------------------------------
create or replace function public.qcms_search_table_map()
returns jsonb language sql immutable set search_path = public as $$
  select '{
    "parts": ["PART_MASTER", "Part Master", "part-records"],
    "part_raw_material_details": ["PART_MASTER", "Part Raw Material", "part-records"],
    "part_raw_material_technical_data": ["PART_MASTER", "Part RM Technical Data", "part-records"],
    "part_supplier_links": ["PART_MASTER", "Part Supplier", "part-records"],
    "part_supplier_price_history": ["PART_MASTER", "Part Supplier Price", "part-records"],
    "part_process_specifications": ["PART_MASTER", "Part Process Specification", "part-records"],
    "part_process_parameter_specifications": ["PART_MASTER", "Part Process Parameter", "part-records"],
    "part_metallurgical_requirements": ["PART_MASTER", "Part Metallurgical Requirement", "part-records"],
    "part_heat_treatment_details": ["PART_MASTER", "Part Heat Treatment", "part-records"],
    "part_rmtc_requirements": ["PART_MASTER", "Part RMTC Requirement", "part-records"],
    "parties": ["REFERENCE_MASTERS", "Customer / Supplier / Vendor", "reference-records"],
    "company_branches": ["REFERENCE_MASTERS", "Company Branch", "company-branch-records"],
    "material_grades": ["MATERIAL_GRADE", "Material Grade", "grade-records"],
    "processes": ["REFERENCE_MASTERS", "Process Master", "process-records"],
    "inspection_stages": ["REFERENCE_MASTERS", "Inspection Stage", "reference-records"],
    "employees": ["EMPLOYEE_MASTER", "Employee", "employee-records"],
    "inspection_plans": ["INSPECTION_LAYOUTS", "Inspection Layout", "inspection-layout-records"],
    "inspection_plan_characteristics": ["INSPECTION_LAYOUTS", "Layout Characteristic", "inspection-layout-records"],
    "rmtc_approvals": ["RMTC_ENTRY", "RMTC", "rmtc-records"],
    "rmtc_part_approvals": ["RMTC_ENTRY", "RMTC Part Approval", "rmtc-records"],
    "inward_lots": ["MATERIAL_INWARD", "Material Inward", "inward-records"],
    "production_batches": ["OSP_TRANSACTIONS", "Production / FSI Batch", "osp-records"],
    "osp_jobs": ["OSP_TRANSACTIONS", "OSP Job / Material Out", "osp-records"],
    "osp_receipts": ["OSP_TRANSACTIONS", "OSP Inward Receipt", "osp-records"],
    "osp_material_outs": ["OSP_TRANSACTIONS", "OSP Material Out", "osp-records"],
    "inspection_reports": ["DIMENSIONAL_REPORT", "Dimensional Report", "dimensional-records"],
    "inspection_results": ["DIMENSIONAL_REPORT", "Dimensional Result", "dimensional-records"],
    "lab_tests": ["METLAB_REPORT", "MetLAB / Bend Test Report", "metlab-records"],
    "quality_complaints": ["COMPLAINT_MANAGEMENT", "Quality Complaint", "complaint-records"],
    "quality_complaint_actions": ["COMPLAINT_MANAGEMENT", "Complaint Action", "complaint-records"],
    "quality_complaint_followups": ["COMPLAINT_MANAGEMENT", "Complaint Follow-up", "complaint-records"],
    "supply_customer_orders": ["SUPPLY_CHAIN", "Customer Order / Schedule", "supply-customer-orders"],
    "supply_purchase_orders": ["SUPPLY_CHAIN", "Purchase Order", "supply-po-order-list"],
    "supply_purchase_order_items": ["SUPPLY_CHAIN", "Purchase Order Item", "supply-po-order-list"],
    "supply_rm_purchase_orders": ["SUPPLY_CHAIN", "RM Procurement Order", "supply-rm-procurement"],
    "supply_rm_receipts": ["SUPPLY_CHAIN", "RM Receipt", "supply-rm-receipt"],
    "supply_rm_dispatches": ["SUPPLY_CHAIN", "RM to Forging", "supply-rm-dispatch"],
    "supply_forging_orders": ["SUPPLY_CHAIN", "Forging Order", "supply-forging"],
    "supply_forging_receipts": ["SUPPLY_CHAIN", "Forging Receipt", "supply-forging"],
    "supply_downstream_events": ["SUPPLY_CHAIN", "Machining / FG / Dispatch", "supply-downstream"],
    "supply_opening_stock": ["SUPPLY_CHAIN", "Opening Stock", "supply-opening-stock"],
    "supply_po_confirmations": ["SUPPLY_CHAIN", "PO Confirmation", "supply-po-order-list"],
    "npd_orders": ["NPD_APQP", "NPD Order", "npd-status"],
    "npd_order_steps": ["NPD_APQP", "NPD Step", "npd-status"],
    "npd_process_flows": ["NPD_APQP", "Process Flow", "npd-process-flow"],
    "npd_process_flow_steps": ["NPD_APQP", "Process Flow Step", "npd-process-flow"],
    "ppap_projects": ["NPD_APQP", "APQP / PPAP Project", "apqp"],
    "ppap_documents": ["NPD_APQP", "PPAP Document", "apqp"],
    "quality_assets": ["CALIBRATION_VALIDATION", "Gauge / Fixture / Instrument", "calibration-validation"],
    "quality_asset_calibration_records": ["CALIBRATION_VALIDATION", "Calibration / Validation Record", "calibration-validation"],
    "standard_room_inspection_records": ["CALIBRATION_VALIDATION", "Standard Room Inspection", "standard-room-inspection"],
    "standard_room_inspections": ["CALIBRATION_VALIDATION", "Standard Room Inspection", "standard-room-inspection"],
    "standard_room_instruments": ["CALIBRATION_VALIDATION", "Standard Room Instrument", "standard-room-inspection"],
    "customer_standards": ["REFERENCE_MASTERS", "Customer Standard", "standards-records"],
    "standards_register": ["REFERENCE_MASTERS", "Standards Register", "standards-records"],
    "qc_calculation_records": ["QC_CALCULATION_TOOLS", "QC Calculation", "qc-calculation-records"],
    "document_attachments": [null, "Attachment / Photo", "records-center"],
    "qcms_delete_requests": [null, "Deletion Request", "records-center"]
  }'::jsonb
$$;

create or replace function public.qcms_global_search(p_query text, p_limit integer default 200)
returns table(source_table text, record_id uuid, module_key text, title text, subtitle text, matched_field text, snippet text, web_route text, record_type text)
language plpgsql volatile security invoker set search_path = public set statement_timeout = '15s' as $$
declare
  v_q text := btrim(coalesce(p_query, ''));
  v_pat text;
  v_limit integer := least(greatest(coalesce(p_limit, 200), 10), 1000);
  v_per integer;
  v_map jsonb := public.qcms_search_table_map();
  v_out jsonb := '[]'::jsonb;
  v_chunk jsonb;
  v_part_ids uuid[] := '{}';
  v_party_ids uuid[] := '{}';
  t record;
  v_cols text[];
  v_title text;
  v_sub text;
  v_where text;
  v_case_f text;
  v_case_s text;
  v_sql text;
  v_entry jsonb;
  v_rel text[];
  c text;
begin
  if length(v_q) < 2 then return; end if;
  v_pat := '%' || replace(replace(replace(v_q, '\', '\\'), '%', '\%'), '_', '\_') || '%';
  v_per := least(greatest(v_limit / 8, 8), 40);

  select coalesce(array_agg(id), '{}') into v_part_ids from (
    select id from public.parts where part_number ilike v_pat or fsi_part_number ilike v_pat or part_name ilike v_pat or drawing_number ilike v_pat limit 50) x;
  select coalesce(array_agg(id), '{}') into v_party_ids from (
    select id from public.parties where party_code ilike v_pat or party_name ilike v_pat limit 50) x;

  for t in
    select cl.relname::text as tbl, cl.oid
      from pg_class cl join pg_namespace n on n.oid = cl.relnamespace
     where n.nspname = 'public' and cl.relkind = 'r'
       and exists (select 1 from pg_attribute a where a.attrelid = cl.oid and a.attname = 'id' and a.atttypid = 'uuid'::regtype and not a.attisdropped)
       and exists (select 1 from pg_attribute a where a.attrelid = cl.oid and a.attname = 'tenant_id' and not a.attisdropped)
       and has_table_privilege(cl.oid, 'SELECT')
       and cl.relname not in ('audit_log', 'qcms_user_mail_accounts', 'qcms_email_settings', 'qcms_email_templates', 'qcms_mail_groups',
           'qcms_mail_sent_log', 'qcms_notification_outbox', 'qcms_notification_routes', 'qcms_notification_schedules',
           'qcms_notification_scheduler_config', 'qcms_password_edit_audit', 'qcms_user_activity_log', 'qcms_module_approval_routes',
           'number_sequences', 'heat_code_sequences', 'master_value_catalog', 'profiles', 'user_module_permissions',
           'user_section_permissions', 'role_module_defaults', 'department_module_defaults', 'qcms_user_dashboards',
           'qcms_user_notifications', 'qcms_push_devices', 'supply_stage_responsibilities')
       and cl.relname not like 'stawn\_%' and cl.relname not like '%licen%' and cl.relname not like '%whatsapp%'
     order by case when v_map ? cl.relname then 0 else 1 end, cl.relname
  loop
    exit when jsonb_array_length(v_out) >= v_limit;
    select coalesce(array_agg(a.attname::text order by a.attnum), '{}') into v_cols
      from pg_attribute a
     where a.attrelid = t.oid and a.attnum > 0 and not a.attisdropped
       and a.atttypid in ('text'::regtype, 'varchar'::regtype, 'bpchar'::regtype)
       and a.attname not like '%password%' and a.attname not like '%secret%' and a.attname not like '%token%'
       and a.attname not like '%\_path' and a.attname not in ('checksum', 'api_key', 'smtp_password', 'mime_type');
    v_entry := coalesce(v_map -> t.tbl, jsonb_build_array(null, initcap(replace(t.tbl, '_', ' ')), 'records-center'));

    -- title / subtitle from the best reference columns this table has
    select coalesce('coalesce(' || string_agg(format('nullif(btrim(t.%I::text), %L)', col, ''), ', ' order by ord) || ', t.id::text)', 't.id::text') into v_title
      from unnest(array['part_number', 'po_number', 'report_number', 'rmtc_number', 'inward_number', 'complaint_number', 'osp_job_number',
                        'receipt_number', 'dispatch_number', 'batch_code', 'customer_order_no', 'master_reference_no', 'supplier_order_no',
                        'order_number', 'project_code', 'plan_number', 'asset_code', 'asset_number', 'party_code', 'grade_code',
                        'process_code', 'employee_code', 'certificate_number', 'reference_no', 'document_title', 'file_name',
                        'record_label', 'standard_number', 'heat_number', 'name', 'title', 'code']) with ordinality u(col, ord)
     where col = any(v_cols);
    select coalesce('concat_ws('' · '', ' || string_agg(format('nullif(btrim(t.%I::text), %L)', col, ''), ', ' order by ord) || ')', '''''') into v_sub
      from unnest(array['part_name', 'party_name', 'layout_name', 'asset_name', 'subject', 'heat_number', 'process_name', 'first_name',
                        'last_name', 'test_type', 'report_type', 'event_type', 'status']) with ordinality u(col, ord)
     where col = any(v_cols);

    v_rel := '{}';
    if v_part_ids <> '{}' and exists (select 1 from pg_attribute a where a.attrelid = t.oid and a.attname = 'part_id' and a.atttypid = 'uuid'::regtype and not a.attisdropped)
       and t.tbl <> 'parts' then
      v_rel := array_append(v_rel, 't.part_id = any($2)'::text);
    end if;
    if v_party_ids <> '{}' then
      for c in select a.attname::text from pg_attribute a where a.attrelid = t.oid and not a.attisdropped and a.atttypid = 'uuid'::regtype
                 and a.attname in ('customer_id', 'supplier_id', 'party_id', 'vendor_id', 'forging_supplier_id', 'rm_supplier_id', 'steel_mill_id', 'osp_vendor_id', 'ship_to_party_id')
      loop
        v_rel := array_append(v_rel, format('t.%I = any($3)', c));
      end loop;
    end if;

    if coalesce(array_length(v_cols, 1), 0) = 0 and coalesce(array_length(v_rel, 1), 0) = 0 then continue; end if;

    select string_agg(format('t.%I ilike $1', col), ' or ') into v_where from unnest(v_cols) col;
    select 'case ' || string_agg(format('when t.%I ilike $1 then %L', col, col), ' ') || ' else ''related part / party'' end' into v_case_f from unnest(v_cols) col;
    select 'case ' || string_agg(format('when t.%I ilike $1 then left(t.%I::text, 180)', col, col), ' ') || ' else null end' into v_case_s from unnest(v_cols) col;
    v_where := concat_ws(' or ', nullif(v_where, ''), nullif(array_to_string(v_rel, ' or '), ''));
    v_case_f := coalesce(v_case_f, '''related part / party''');
    v_case_s := coalesce(v_case_s, 'null');

    v_sql := format(
      'select coalesce(jsonb_agg(jsonb_build_object(''source_table'', %L, ''record_id'', x.id, ''module_key'', %L, ''title'', x.ti, ''subtitle'', x.su,'
      || ' ''matched_field'', x.mf, ''snippet'', x.sn, ''web_route'', %L, ''record_type'', %L)), ''[]''::jsonb)'
      || ' from (select t.id, (%s)::text ti, (%s)::text su, (%s)::text mf, (%s)::text sn from public.%I t where %s limit %s) x',
      t.tbl, v_entry ->> 0, v_entry ->> 2, v_entry ->> 1, v_title, v_sub, v_case_f, v_case_s, t.tbl, v_where, v_per);
    begin
      execute v_sql into v_chunk using v_pat, v_part_ids, v_party_ids;
    exception when others then
      v_chunk := '[]'::jsonb;  -- one unusual table must never break Global Search
    end;
    v_out := v_out || coalesce(v_chunk, '[]'::jsonb);
  end loop;

  return query
    select e->>'source_table', (e->>'record_id')::uuid, e->>'module_key',
           case when e->>'title' ~ '^[0-9a-f]{8}-[0-9a-f]{4}-' then coalesce(nullif(left(e->>'snippet', 80), ''), e->>'record_type') else e->>'title' end,
           e->>'subtitle', e->>'matched_field',
           case when e->>'matched_field' = 'related part / party' then null else e->>'snippet' end, e->>'web_route', e->>'record_type'
      from jsonb_array_elements(v_out) e
     order by case when lower(e->>'title') = lower(v_q) then 0 when e->>'title' ilike v_q || '%' then 1
                   when e->>'matched_field' = 'related part / party' then 3 else 2 end,
              e->>'record_type', e->>'title'
     limit v_limit;
end $$;

revoke all on function public.qcms_global_search(text, integer) from public, anon;
grant execute on function public.qcms_global_search(text, integer) to authenticated;
revoke all on function public.qcms_kpi_dashboard(text) from public, anon;
grant execute on function public.qcms_kpi_dashboard(text) to authenticated;
revoke all on function public.qcms_my_pending_tasks(integer) from public, anon;
grant execute on function public.qcms_my_pending_tasks(integer) to authenticated;
grant execute on function public.qcms_kpi_chart(text, text, jsonb) to authenticated;
grant execute on function public.qcms_kpi_card(text, numeric, text, text, text) to authenticated;
grant execute on function public.qcms_search_table_map() to authenticated;

notify pgrst, 'reload schema';
