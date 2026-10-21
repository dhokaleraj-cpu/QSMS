-- QCMS v4.14.49 R35 · Quality fixes (safe to re-run; additive only)
-- 1. tenant_id defaults: tables written by the website without an explicit tenant_id (for example
--    Calibration & Validation → Part / Process Gauge-Fixture links) failed row-level security (HTTP 403)
--    because tenant_id arrived empty. These tenant tables now default tenant_id to the signed-in company.
-- 2. User Activity register: role check evaluated once per query (was once per row → statement timeout).
-- 3. npd_order_steps.process_name_snapshot: the overdue notifier / Android NPD screen read this column,
--    which only existed on npd_process_flow_steps (HTTP 400 every morning). Added and kept in sync.

set lock_timeout = '10s';

do $$
declare
  t text;
begin
  -- tenant tables that the website / apps write without an explicit tenant_id
  foreach t in array array[
    'audit_findings','audit_plans','calculation_rules','calibration_events','customer_report_package_items',
    'customer_report_packages','document_approvals','gauge_fixture_assets','gauge_fixture_control_records',
    'number_sequences','osp_material_outs','part_rmtc_requirements','qcms_email_templates',
    'qcms_notification_scheduler_config','qcms_notification_schedules','qcms_supply_digest_state',
    'quality_asset_calibration_records','quality_asset_part_process_links','standard_room_inspection_records',
    'standard_room_inspections','standard_room_instruments','standards_register','supply_po_sequences']
  loop
    if exists (
      select 1 from information_schema.columns c
      where c.table_schema = 'public' and c.table_name = t and c.column_name = 'tenant_id' and c.column_default is null
    ) then
      execute format('alter table public.%I alter column tenant_id set default public.current_tenant_id()', t);
    end if;
  end loop;
end $$;

alter policy qcms_activity_admin_select on public.qcms_user_activity_log
  using (
    tenant_id = (select public.current_tenant_id())
    and (select public.current_app_role()) = any (array['ADMIN', 'MANAGEMENT', 'QUALITY_MANAGER'])
  );
create index if not exists idx_qcms_activity_time on public.qcms_user_activity_log (occurred_at desc);

alter table public.npd_order_steps add column if not exists process_name_snapshot text;
-- existing rows: readers fall back to process_name, new / changed rows are filled by the trigger below.

create or replace function public.qcms_npd_order_step_snapshot()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.process_name_snapshot is null or (tg_op = 'UPDATE' and new.process_name is distinct from old.process_name) then
    new.process_name_snapshot := new.process_name;
  end if;
  return new;
end $$;

create or replace trigger trg_qcms_npd_order_step_snapshot
  before insert or update on public.npd_order_steps
  for each row execute function public.qcms_npd_order_step_snapshot();
