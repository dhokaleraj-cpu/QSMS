-- QCMS v4.14.28
-- OSP batch genealogy / approved-layout queue resilience + two-day Excel digest schedules.

alter table public.qcms_notification_schedules
  add column if not exists run_every_days integer not null default 1,
  add column if not exists recipient_departments text[] not null default '{}'::text[],
  add column if not exists export_format text not null default 'PDF';

update public.qcms_notification_schedules set run_every_days=1 where run_every_days is null or run_every_days < 1;
update public.qcms_notification_schedules set recipient_departments='{}'::text[] where recipient_departments is null;
update public.qcms_notification_schedules set export_format='PDF' where nullif(btrim(export_format),'') is null;

-- Approved OSP layouts are authoritative evidence that the inspection type is required.
update public.part_process_specifications p
set dimensional_required=true, updated_at=now()
where p.status='ACTIVE'
  and p.inward_type='OSP_PROCESS'
  and coalesce(p.dimensional_required,false)=false
  and exists (
    select 1 from public.inspection_plans ip
    where ip.source_process_specification_id=p.id
      and ip.status='APPROVED'
      and ip.layout_type='DIMENSIONAL'
  );

update public.part_process_specifications p
set metlab_required=true, updated_at=now()
where p.status='ACTIVE'
  and p.inward_type='OSP_PROCESS'
  and coalesce(p.metlab_required,false)=false
  and exists (
    select 1 from public.inspection_plans ip
    where ip.source_process_specification_id=p.id
      and ip.status='APPROVED'
      and ip.layout_type='METLAB'
  );

-- Existing open OSP jobs must inherit the corrected requirement flags so the quality gate
-- and Sample Dimensional / MetLAB queues stay aligned with the approved layouts.
update public.osp_jobs o
set required_tests = (
      select coalesce(array_agg(distinct x order by x), '{}'::text[])
      from unnest(
        coalesce(o.required_tests,'{}'::text[]) ||
        array_remove(array[
          case when coalesce(p.dimensional_required,false) then 'DIMENSIONAL' end,
          case when coalesce(p.metlab_required,false) then 'METLAB' end
        ], null)
      ) as u(x)
    ),
    updated_at=now()
from public.part_process_specifications p
where p.id=o.process_specification_id
  and o.status not in ('COMPLETED','REJECTED','CANCELLED');

create or replace function public.qcms_sync_osp_requirement_from_approved_layout()
returns trigger
language plpgsql
security definer
set search_path='public','auth'
as $$
begin
  if new.status='APPROVED' and new.source_process_specification_id is not null and new.layout_type in ('DIMENSIONAL','METLAB') then
    update public.part_process_specifications
       set dimensional_required = case when new.layout_type='DIMENSIONAL' then true else dimensional_required end,
           metlab_required = case when new.layout_type='METLAB' then true else metlab_required end,
           updated_at=now()
     where id=new.source_process_specification_id
       and inward_type='OSP_PROCESS';

    update public.osp_jobs o
       set required_tests=(
             select coalesce(array_agg(distinct x order by x),'{}'::text[])
             from unnest(coalesce(o.required_tests,'{}'::text[]) || array[new.layout_type]) as u(x)
           ),
           updated_at=now()
     where o.process_specification_id=new.source_process_specification_id
       and o.status not in ('COMPLETED','REJECTED','CANCELLED');
  end if;
  return new;
end;
$$;

revoke all on function public.qcms_sync_osp_requirement_from_approved_layout() from public, anon, authenticated;
grant execute on function public.qcms_sync_osp_requirement_from_approved_layout() to service_role;

drop trigger if exists trg_qcms_sync_osp_requirement_from_approved_layout on public.inspection_plans;
create trigger trg_qcms_sync_osp_requirement_from_approved_layout
after insert or update of status,layout_type,source_process_specification_id on public.inspection_plans
for each row execute function public.qcms_sync_osp_requirement_from_approved_layout();

-- Internal two-day Excel digest templates.
insert into public.qcms_email_templates
(tenant_id,template_key,module_key,template_name,subject_template,body_template,include_generated_pdf,include_record_attachments,include_supplier,enabled)
select t.id, v.template_key, 'SUPPLY_CHAIN', v.template_name, v.subject_template, v.body_template, false, false, false, true
from public.tenants t
cross join (values
 ('CUSTOMER_ORDER_OVERDUE_2DAY','Customer Orders · Overdue · Two-Day Excel Digest','QCMS · Overdue Customer Orders · {{report_date}}','Dear Team,\n\nAttached is the QCMS Excel list of overdue Customer Orders as on {{report_date}}.\nOverdue records: {{overdue_count}}.\n\nRegards,\nFour Star Industries Pvt Ltd\nQCMS'),
 ('RM_ORDER_PENDING_2DAY','RM Orders · Pending · Two-Day Excel Digest','QCMS · Pending RM Orders · {{report_date}}','Dear Supply Chain Team,\n\nAttached is the QCMS Excel list of pending Raw Material procurement orders as on {{report_date}}.\nPending records: {{open_count}}.\n\nRegards,\nFour Star Industries Pvt Ltd\nQCMS'),
 ('PURCHASE_ORDER_PENDING_2DAY','Purchase Orders · Pending · Two-Day Excel Digest','QCMS · Pending Purchase Orders · {{report_date}}','Dear Supply Chain Team,\n\nAttached is the QCMS Excel list of Purchase Orders pending approval, supplier confirmation or receipt as on {{report_date}}.\nPending records: {{open_count}} · Overdue: {{overdue_count}}.\n\nRegards,\nFour Star Industries Pvt Ltd\nQCMS'),
 ('FORGING_RECEIPT_OVERDUE_2DAY','Forging Receipts · Overdue · Two-Day Excel Digest','QCMS · Overdue Forging Receipts · {{report_date}}','Dear Supply Chain Team,\n\nAttached is the QCMS Excel list of overdue Forging Receipts as on {{report_date}}.\nOverdue records: {{overdue_count}}.\n\nRegards,\nFour Star Industries Pvt Ltd\nQCMS')
) v(template_key,template_name,subject_template,body_template)
on conflict(tenant_id,template_key) do update set
 module_key=excluded.module_key,template_name=excluded.template_name,subject_template=excluded.subject_template,
 body_template=excluded.body_template,include_generated_pdf=false,include_record_attachments=false,include_supplier=false,enabled=true,updated_at=now();

insert into public.qcms_notification_schedules
(tenant_id,schedule_key,module_key,event_key,schedule_label,enabled,hour_local,timezone,days_ahead,include_overdue,include_open,recipient_department,recipient_departments,include_suppliers,template_key,run_every_days,export_format,last_run_local_date,last_run_at)
select t.id, v.schedule_key, 'SUPPLY_CHAIN', v.schedule_key, v.schedule_label, true, 8, 'Asia/Kolkata', v.days_ahead,
       v.include_overdue, v.include_open, v.primary_department, v.departments, false, v.schedule_key, 2, 'XLSX', null, null
from public.tenants t
cross join (values
 ('CUSTOMER_ORDER_OVERDUE_2DAY','Overdue Customer Orders · Every Two Days',0,true,false,null::text,array['Supply Chain','Marketing','Management','Procurement']::text[]),
 ('RM_ORDER_PENDING_2DAY','Pending RM Orders · Every Two Days',365,true,true,'Supply Chain',array['Supply Chain']::text[]),
 ('PURCHASE_ORDER_PENDING_2DAY','Pending Purchase Orders · Every Two Days',365,true,true,'Supply Chain',array['Supply Chain']::text[]),
 ('FORGING_RECEIPT_OVERDUE_2DAY','Overdue Forging Receipts · Every Two Days',0,true,false,'Supply Chain',array['Supply Chain']::text[])
) v(schedule_key,schedule_label,days_ahead,include_overdue,include_open,primary_department,departments)
on conflict(tenant_id,schedule_key) do update set
 module_key=excluded.module_key,event_key=excluded.event_key,schedule_label=excluded.schedule_label,enabled=true,
 hour_local=8,timezone='Asia/Kolkata',days_ahead=excluded.days_ahead,include_overdue=excluded.include_overdue,
 include_open=excluded.include_open,recipient_department=excluded.recipient_department,
 recipient_departments=excluded.recipient_departments,include_suppliers=false,template_key=excluded.template_key,
 run_every_days=2,export_format='XLSX',updated_at=now();

insert into public.qcms_release_schema_state(version,build,details)
values('4.14.28','41428-OSP-BATCH-GENEALOGY-TWO-DAY-EXCEL',jsonb_build_object(
 'osp_fsi_batch_chain',true,
 'osp_material_out_remarks_chain',true,
 'osp_approved_layout_queue_sync',true,
 'two_day_excel_digests',true
))
on conflict(version) do update set build=excluded.build,details=excluded.details,applied_at=now();

create or replace function public.qcms_release_schema_version()
returns text language sql immutable set search_path='pg_catalog'
as $$ select '4.14.28'::text $$;
revoke all on function public.qcms_release_schema_version() from public;
grant execute on function public.qcms_release_schema_version() to anon,authenticated,service_role;
