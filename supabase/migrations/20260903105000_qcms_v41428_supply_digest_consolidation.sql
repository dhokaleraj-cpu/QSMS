-- QCMS v4.14.28 corrective consolidation
-- Use one dedicated two-day XLSX supply digest Edge Function and disable the interim duplicate schedule keys.

create table if not exists public.qcms_supply_digest_state (
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  schedule_key text not null,
  last_run_local_date date,
  last_run_at timestamptz,
  updated_at timestamptz not null default now(),
  primary key(tenant_id,schedule_key)
);

alter table public.qcms_supply_digest_state enable row level security;
revoke all on public.qcms_supply_digest_state from anon,authenticated;
grant select,insert,update,delete on public.qcms_supply_digest_state to service_role;

-- Keep the user-facing schedules semantically clear: they run every 2 days even though
-- the preserved internal key uses the historical *_BIENNIAL name.
insert into public.qcms_email_templates
(tenant_id,template_key,module_key,template_name,subject_template,body_template,include_generated_pdf,include_record_attachments,include_supplier,enabled)
select t.id,v.template_key,'SUPPLY_CHAIN',v.template_name,v.subject_template,v.body_template,false,false,false,true
from public.tenants t
cross join (values
 ('CUSTOMER_ORDER_OVERDUE_BIENNIAL_DIGEST','Customer Orders · Overdue · Every 2 Days','QCMS · Overdue Customer Orders · {{report_date}}','Dear Team,\n\nAttached is the QCMS Excel list of overdue Customer Orders as on {{report_date}}.\nOverdue records: {{overdue_count}}.\n\nRegards,\nFour Star Industries Pvt Ltd\nQCMS'),
 ('RM_PENDING_BIENNIAL_DIGEST','RM Procurement · Pending · Every 2 Days','QCMS · Pending RM Procurement · {{report_date}}','Dear Supply Chain Team,\n\nAttached is the QCMS Excel list of pending Raw Material procurement requirements as on {{report_date}}.\nPending records: {{open_count}} · Overdue: {{overdue_count}}.\n\nRegards,\nFour Star Industries Pvt Ltd\nQCMS'),
 ('PO_PENDING_BIENNIAL_DIGEST','Purchase Orders · Pending · Every 2 Days','QCMS · Pending Purchase Orders · {{report_date}}','Dear Supply Chain Team,\n\nAttached is the QCMS Excel list of Purchase Orders requiring action as on {{report_date}}.\nPending records: {{open_count}} · Overdue: {{overdue_count}}.\n\nRegards,\nFour Star Industries Pvt Ltd\nQCMS'),
 ('FORGING_RECEIPT_OVERDUE_BIENNIAL_DIGEST','Forging Receipts · Overdue · Every 2 Days','QCMS · Overdue Forging Receipts · {{report_date}}','Dear Supply Chain Team,\n\nAttached is the QCMS Excel list of overdue Forging Receipts as on {{report_date}}.\nOverdue records: {{overdue_count}}.\n\nRegards,\nFour Star Industries Pvt Ltd\nQCMS')
) v(template_key,template_name,subject_template,body_template)
on conflict(tenant_id,template_key) do update set
 module_key=excluded.module_key,template_name=excluded.template_name,subject_template=excluded.subject_template,
 body_template=excluded.body_template,include_generated_pdf=false,include_record_attachments=false,include_supplier=false,
 enabled=true,updated_at=now();

insert into public.qcms_notification_schedules
(tenant_id,schedule_key,module_key,event_key,schedule_label,enabled,hour_local,timezone,days_ahead,include_overdue,include_open,recipient_department,recipient_departments,include_suppliers,template_key,run_every_days,export_format)
select t.id,v.schedule_key,'SUPPLY_CHAIN',v.schedule_key,v.schedule_label,true,8,'Asia/Kolkata',v.days_ahead,v.include_overdue,v.include_open,v.primary_department,v.departments,false,v.template_key,2,'XLSX'
from public.tenants t
cross join (values
 ('CUSTOMER_ORDER_OVERDUE_BIENNIAL','Overdue Customer Orders · Every 2 Days',0,true,false,'Supply Chain',array['Supply Chain','Marketing','Management','Procurement']::text[],'CUSTOMER_ORDER_OVERDUE_BIENNIAL_DIGEST'),
 ('RM_PENDING_BIENNIAL','Pending RM Procurement · Every 2 Days',365,true,true,'Supply Chain',array['Supply Chain']::text[],'RM_PENDING_BIENNIAL_DIGEST'),
 ('PO_PENDING_BIENNIAL','Pending Purchase Orders · Every 2 Days',365,true,true,'Supply Chain',array['Supply Chain']::text[],'PO_PENDING_BIENNIAL_DIGEST'),
 ('FORGING_RECEIPT_OVERDUE_BIENNIAL','Overdue Forging Receipts · Every 2 Days',0,true,false,'Supply Chain',array['Supply Chain']::text[],'FORGING_RECEIPT_OVERDUE_BIENNIAL_DIGEST')
) v(schedule_key,schedule_label,days_ahead,include_overdue,include_open,primary_department,departments,template_key)
on conflict(tenant_id,schedule_key) do update set
 module_key=excluded.module_key,event_key=excluded.event_key,schedule_label=excluded.schedule_label,enabled=true,
 hour_local=8,timezone='Asia/Kolkata',days_ahead=excluded.days_ahead,include_overdue=excluded.include_overdue,
 include_open=excluded.include_open,recipient_department=excluded.recipient_department,recipient_departments=excluded.recipient_departments,
 include_suppliers=false,template_key=excluded.template_key,run_every_days=2,export_format='XLSX',updated_at=now();

-- Disable the interim duplicate keys introduced while the dedicated digest function was being consolidated.
update public.qcms_notification_schedules
set enabled=false,updated_at=now()
where schedule_key in ('CUSTOMER_ORDER_OVERDUE_2DAY','RM_ORDER_PENDING_2DAY','PURCHASE_ORDER_PENDING_2DAY','FORGING_RECEIPT_OVERDUE_2DAY');

-- Ensure the dedicated notifier cron exists. Do not replace a healthy existing job.
do $$
begin
  if not exists(select 1 from cron.job where jobname='qcms-supply-digest-notifier-hourly' and active) then
    perform cron.schedule(
      'qcms-supply-digest-notifier-hourly',
      '15 * * * *',
      $cron$
      select net.http_post(
        url := (select decrypted_secret from vault.decrypted_secrets where name='qcms_project_url' order by created_at desc limit 1) || '/functions/v1/qcms-supply-digest-notifier',
        headers := jsonb_build_object('Content-Type','application/json','X-QCMS-Scheduler',(select decrypted_secret from vault.decrypted_secrets where name='qcms_notification_scheduler_token' order by created_at desc limit 1)),
        body := jsonb_build_object('source','supabase_cron','requested_at',now()),
        timeout_milliseconds := 30000
      ) as request_id;
      $cron$
    );
  end if;
end $$;

update public.qcms_release_schema_state
set details=coalesce(details,'{}'::jsonb)||jsonb_build_object(
  'two_day_excel_digests',true,
  'supply_digest_edge_function','qcms-supply-digest-notifier',
  'supply_digest_duplicate_schedules_disabled',true
), applied_at=now()
where version='4.14.28';
