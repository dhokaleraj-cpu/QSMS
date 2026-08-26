-- QCMS v4.14.7 — next-stage routing, templates, attachments and automatic open/overdue email reports.
-- Additive only. Existing business/master/quality/supply-chain data is preserved.

alter table public.parties add column if not exists notification_emails text;
comment on column public.parties.notification_emails is 'Additional comma/semicolon separated email recipients used for controlled QCMS supplier/customer notifications.';

alter table public.qcms_notification_routes add column if not exists department text;
alter table public.qcms_notification_routes add column if not exists department_cc boolean not null default false;
alter table public.qcms_notification_routes add column if not exists send_to_supplier boolean not null default false;
alter table public.qcms_notification_routes add column if not exists template_key text;
alter table public.qcms_notification_routes add column if not exists next_stage text;

alter table public.qcms_notification_outbox add column if not exists cc_emails text[] not null default '{}';
alter table public.qcms_notification_outbox add column if not exists bcc_emails text[] not null default '{}';
alter table public.qcms_notification_outbox add column if not exists body_html text;
alter table public.qcms_notification_outbox add column if not exists template_key text;
alter table public.qcms_notification_outbox add column if not exists attachment_manifest jsonb not null default '[]'::jsonb;
alter table public.qcms_notification_outbox add column if not exists dedupe_key text;
alter table public.qcms_notification_outbox add column if not exists is_automatic boolean not null default false;
alter table public.qcms_notification_outbox add column if not exists scheduled_for timestamptz;
create unique index if not exists uq_qcms_notification_outbox_dedupe
  on public.qcms_notification_outbox(tenant_id,dedupe_key)
  where dedupe_key is not null;

create table if not exists public.qcms_email_templates(
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  template_key text not null,
  module_key text not null,
  template_name text not null,
  subject_template text not null,
  body_template text not null,
  include_generated_pdf boolean not null default true,
  include_record_attachments boolean not null default true,
  include_supplier boolean not null default false,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid() references auth.users(id),
  updated_by uuid default auth.uid() references auth.users(id),
  unique(tenant_id,template_key)
);

create table if not exists public.qcms_notification_schedules(
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  schedule_key text not null,
  module_key text not null,
  event_key text not null,
  schedule_label text not null,
  enabled boolean not null default true,
  hour_local integer not null default 8 check (hour_local between 0 and 23),
  timezone text not null default 'Asia/Kolkata',
  days_ahead integer not null default 7 check (days_ahead between 0 and 365),
  include_overdue boolean not null default true,
  include_open boolean not null default true,
  recipient_department text,
  employee_id uuid references public.employees(id),
  include_suppliers boolean not null default false,
  template_key text,
  last_run_local_date date,
  last_run_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid() references auth.users(id),
  updated_by uuid default auth.uid() references auth.users(id),
  unique(tenant_id,schedule_key)
);

create table if not exists public.qcms_notification_scheduler_config(
  tenant_id uuid primary key references public.tenants(id) on delete cascade,
  scheduler_token_hash text not null,
  updated_at timestamptz not null default now()
);

alter table public.qcms_email_templates enable row level security;
alter table public.qcms_notification_schedules enable row level security;
alter table public.qcms_notification_scheduler_config enable row level security;

drop policy if exists qcms_email_templates_read on public.qcms_email_templates;
create policy qcms_email_templates_read on public.qcms_email_templates
for select to authenticated using (tenant_id=public.current_tenant_id());
drop policy if exists qcms_email_templates_admin on public.qcms_email_templates;
create policy qcms_email_templates_admin on public.qcms_email_templates
for all to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN')
with check (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

drop policy if exists qcms_notification_schedules_read on public.qcms_notification_schedules;
create policy qcms_notification_schedules_read on public.qcms_notification_schedules
for select to authenticated using (tenant_id=public.current_tenant_id());
drop policy if exists qcms_notification_schedules_admin on public.qcms_notification_schedules;
create policy qcms_notification_schedules_admin on public.qcms_notification_schedules
for all to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN')
with check (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

drop policy if exists qcms_notification_scheduler_config_admin on public.qcms_notification_scheduler_config;
create policy qcms_notification_scheduler_config_admin on public.qcms_notification_scheduler_config
for select to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

grant select,insert,update,delete on public.qcms_email_templates to authenticated;
grant select,insert,update,delete on public.qcms_notification_schedules to authenticated;
grant select on public.qcms_notification_scheduler_config to authenticated;

-- Template placeholders use {{field_name}}. NotificationService enriches the context
-- from the linked QCMS transaction before rendering.
insert into public.qcms_email_templates
(tenant_id,template_key,module_key,template_name,subject_template,body_template,include_generated_pdf,include_record_attachments,include_supplier,enabled)
select t.id,v.template_key,v.module_key,v.template_name,v.subject_template,v.body_template,v.include_pdf,v.include_docs,v.include_supplier,true
from public.tenants t cross join (values
 ('RMTC_APPROVAL_PENDING','RMTC_ENTRY','RMTC Approval Pending','QCMS · RMTC approval pending · {{document_no}}',
  'Dear {{department}},\n\nRMTC {{document_no}} is ready for the next controlled stage.\nHeat: {{heat_number}}\nPart: {{part_number}} / FSI {{fsi_part_number}}\nSupplier: {{supplier_name}}\nNext Stage: {{next_stage}}\n\nPlease complete the pending QCMS action.\n\nRegards,\nQCMS',true,true,false),
 ('DIMENSIONAL_APPROVAL_PENDING','DIMENSIONAL_REPORT','Dimensional Approval Pending','QCMS · Dimensional approval pending · {{document_no}}',
  'Dear {{department}},\n\nDimensional Report {{document_no}} is ready for validation / approval.\nPart: {{part_number}} / FSI {{fsi_part_number}}\nDate: {{inspection_date}}\nNext Stage: {{next_stage}}\n\nThe controlled PDF and available supporting documents are attached.\n\nRegards,\nQCMS',true,true,false),
 ('METLAB_APPROVAL_PENDING','METLAB_REPORT','MetLAB Approval Pending','QCMS · MetLAB approval pending · {{document_no}}',
  'Dear {{department}},\n\nMetLAB Report {{document_no}} is ready for validation / approval.\nPart: {{part_number}} / FSI {{fsi_part_number}}\nHeat: {{heat_number}}\nNext Stage: {{next_stage}}\n\nThe controlled PDF and available supporting documents are attached.\n\nRegards,\nQCMS',true,true,false),
 ('RM_PROCUREMENT_PENDING','SUPPLY_CHAIN','RM Procurement Pending','QCMS · RM procurement pending · {{document_no}}',
  'Dear {{department}},\n\nRaw Material procurement is pending.\nCustomer Order / Schedule: {{document_no}}\nPart: {{part_number}} / FSI {{fsi_part_number}}\nRequired RM: {{required_rm_kg}} kg\nCustomer Delivery: {{due_date}}\nNext Stage: {{next_stage}}\n\nPlease initiate the required procurement action.\n\nRegards,\nQCMS',true,true,false),
 ('RM_PO_CREATED','SUPPLY_CHAIN','Raw Material PO Created','QCMS · Raw Material PO · {{document_no}} · action required',
  'Dear Sir / Madam,\n\nRaw Material Purchase Order {{document_no}} has been released through QCMS.\nSupplier: {{supplier_name}}\nDelivery Date: {{due_date}}\nNext Stage: {{next_stage}}\n\nThe controlled Purchase Order PDF and available supporting documents are attached.\n\nRegards,\nFour Star Industries QCMS',true,true,true),
 ('FORGING_PO_CREATED','SUPPLY_CHAIN','Forging PO Created','QCMS · Forging PO · {{document_no}} · action required',
  'Dear Sir / Madam,\n\nForging Purchase Order {{document_no}} has been released through QCMS.\nSupplier: {{supplier_name}}\nDelivery Date: {{due_date}}\nNext Stage: {{next_stage}}\n\nThe controlled Purchase Order PDF and available supporting documents are attached.\n\nRegards,\nFour Star Industries QCMS',true,true,true),
 ('RM_RECEIPT_PENDING','SUPPLY_CHAIN','RM Receipt Pending','QCMS · RM receipt pending · {{document_no}}',
  'Dear {{department}},\n\nThe next Raw Material receipt action is pending for {{document_no}}.\nSupplier: {{supplier_name}}\nDelivery: {{due_date}}\nNext Stage: {{next_stage}}\n\nRegards,\nQCMS',true,true,false),
 ('FORGING_ORDER_PENDING','SUPPLY_CHAIN','Forging Order Pending','QCMS · Forging order pending · {{document_no}}',
  'Dear {{department}},\n\nForging order action is pending for {{document_no}}.\nPart: {{part_number}} / FSI {{fsi_part_number}}\nNext Stage: {{next_stage}}\n\nRegards,\nQCMS',true,true,false),
 ('FORGING_RECEIPT_PENDING','SUPPLY_CHAIN','Forging Receipt Pending','QCMS · Forging receipt pending · {{document_no}}',
  'Dear {{department}},\n\nForging receipt is pending for {{document_no}}.\nSupplier: {{supplier_name}}\nDue Date: {{due_date}}\nNext Stage: {{next_stage}}\n\nRegards,\nQCMS',true,true,false),
 ('OSP_SAMPLE_PENDING','OSP_TRANSACTIONS','OSP Sample Inspection Pending','QCMS · OSP sample inspection pending · {{document_no}}',
  'Dear {{department}},\n\nOSP sample inspection is pending for {{document_no}}.\nPart: {{part_number}} / FSI {{fsi_part_number}}\nSupplier / OSP Vendor: {{supplier_name}}\nVendor Batch: {{vendor_batch_number}}\nNext Stage: {{next_stage}}\n\nRegards,\nQCMS',true,true,false),
 ('CUSTOMER_ORDER_OPEN_OVERDUE_DIGEST','SUPPLY_CHAIN','Open / Overdue Customer Orders','QCMS · Open / overdue Customer Orders · {{report_date}}',
  'Dear {{department}},\n\nAttached is the current QCMS Open / Overdue Customer Order report.\nOpen / due-soon records: {{open_count}}\nOverdue records: {{overdue_count}}\nReport Date: {{report_date}}\n\nPlease review the pending actions and update QCMS.\n\nRegards,\nQCMS',true,false,false),
 ('RM_PO_OPEN_OVERDUE_DIGEST','SUPPLY_CHAIN','Open / Overdue RM Purchase Orders','QCMS · Open / overdue RM Purchase Orders · {{report_date}}',
  'Dear {{department}},\n\nAttached is the current QCMS Open / Overdue Raw Material PO report.\nOpen / due-soon records: {{open_count}}\nOverdue records: {{overdue_count}}\nReport Date: {{report_date}}\n\nSupplier-specific copies are issued when supplier notification email addresses are available.\n\nRegards,\nQCMS',true,false,true),
 ('FORGING_ORDER_OPEN_OVERDUE_DIGEST','SUPPLY_CHAIN','Open / Overdue Forging Orders','QCMS · Open / overdue Forging Orders · {{report_date}}',
  'Dear {{department}},\n\nAttached is the current QCMS Open / Overdue Forging Order report.\nOpen / due-soon records: {{open_count}}\nOverdue records: {{overdue_count}}\nReport Date: {{report_date}}\n\nSupplier-specific copies are issued when supplier notification email addresses are available.\n\nRegards,\nQCMS',true,false,true),
 ('OSP_RETURN_OPEN_OVERDUE_DIGEST','OSP_TRANSACTIONS','Open / Overdue OSP Returns','QCMS · Open / overdue OSP Returns · {{report_date}}',
  'Dear {{department}},\n\nAttached is the current QCMS Open / Overdue OSP Return report.\nOpen / due-soon records: {{open_count}}\nOverdue records: {{overdue_count}}\nReport Date: {{report_date}}\n\nOSP Vendor-specific copies are issued when vendor notification email addresses are available.\n\nRegards,\nQCMS',true,false,true),
 ('NPD_PROCESS_OPEN_OVERDUE_DIGEST','NPD_APQP','Open / Overdue NPD Process Steps','QCMS · Open / overdue NPD Process Steps · {{report_date}}',
  'Dear QCMS User,\n\nAttached is the current QCMS NPD process action report.\nOpen / due-soon records: {{open_count}}\nOverdue records: {{overdue_count}}\nReport Date: {{report_date}}\n\nPlease complete your assigned actions in QCMS.\n\nRegards,\nQCMS',true,false,false)
) v(template_key,module_key,template_name,subject_template,body_template,include_pdf,include_docs,include_supplier)
on conflict (tenant_id,template_key) do update set
 module_key=excluded.module_key, template_name=excluded.template_name,
 subject_template=excluded.subject_template, body_template=excluded.body_template,
 include_generated_pdf=excluded.include_generated_pdf,
 include_record_attachments=excluded.include_record_attachments,
 include_supplier=excluded.include_supplier, updated_at=now();

-- Extend / seed next-stage routes. Existing explicitly assigned employees are preserved.
insert into public.qcms_notification_routes
(tenant_id,event_key,route_label,department,department_cc,send_to_supplier,template_key,next_stage,enabled)
select t.id,v.event_key,v.route_label,v.department,v.department_cc,v.send_to_supplier,v.template_key,v.next_stage,true
from public.tenants t cross join (values
 ('RMTC_APPROVAL_PENDING','RMTC approval pending','Quality',true,false,'RMTC_APPROVAL_PENDING','RMTC Validation / Final Decision'),
 ('DIMENSIONAL_APPROVAL_PENDING','Dimensional approval pending','Quality',true,false,'DIMENSIONAL_APPROVAL_PENDING','Dimensional Validation / Final Decision'),
 ('METLAB_APPROVAL_PENDING','MetLAB approval pending','Quality',true,false,'METLAB_APPROVAL_PENDING','MetLAB Validation / Final Decision'),
 ('RM_PROCUREMENT_PENDING','RM procurement pending','Supply Chain',true,false,'RM_PROCUREMENT_PENDING','Raw Material Purchase Order'),
 ('RM_PO_CREATED','Raw Material PO released','Supply Chain',true,true,'RM_PO_CREATED','Raw Material Receipt / Material Inward'),
 ('FORGING_PO_CREATED','Forging PO released','Supply Chain',true,true,'FORGING_PO_CREATED','Forging Receipt'),
 ('RM_RECEIPT_PENDING','RM receipt pending','Supply Chain',true,false,'RM_RECEIPT_PENDING','Raw Material Receipt / Material Inward'),
 ('FORGING_ORDER_PENDING','Forging order pending','Supply Chain',true,false,'FORGING_ORDER_PENDING','Forging Purchase Order'),
 ('FORGING_RECEIPT_PENDING','Forging receipt pending','Supply Chain',true,false,'FORGING_RECEIPT_PENDING','Forging Receipt'),
 ('OSP_SAMPLE_PENDING','OSP sample inspection pending','Quality',true,false,'OSP_SAMPLE_PENDING','OSP Sample Dimensional / MetLAB')
) v(event_key,route_label,department,department_cc,send_to_supplier,template_key,next_stage)
on conflict (tenant_id,event_key) do update set
 route_label=excluded.route_label,
 department=coalesce(public.qcms_notification_routes.department,excluded.department),
 department_cc=excluded.department_cc,
 send_to_supplier=excluded.send_to_supplier,
 template_key=excluded.template_key,
 next_stage=excluded.next_stage,
 enabled=true,
 updated_at=now();

-- Daily schedules are checked hourly by a protected Supabase Cron function. The
-- configured local hour and time zone decide whether a report actually runs.
insert into public.qcms_notification_schedules
(tenant_id,schedule_key,module_key,event_key,schedule_label,enabled,hour_local,timezone,days_ahead,include_overdue,include_open,recipient_department,include_suppliers,template_key)
select t.id,v.schedule_key,v.module_key,v.event_key,v.schedule_label,true,8,'Asia/Kolkata',v.days_ahead,true,true,v.department,v.include_suppliers,v.template_key
from public.tenants t cross join (values
 ('CUSTOMER_ORDER_OPEN_OVERDUE','SUPPLY_CHAIN','CUSTOMER_ORDER_OPEN_OVERDUE_DIGEST','Customer Orders · Open / Overdue',7,'Supply Chain',false,'CUSTOMER_ORDER_OPEN_OVERDUE_DIGEST'),
 ('RM_PO_OPEN_OVERDUE','SUPPLY_CHAIN','RM_PO_OPEN_OVERDUE_DIGEST','Raw Material PO · Open / Overdue',7,'Supply Chain',true,'RM_PO_OPEN_OVERDUE_DIGEST'),
 ('FORGING_ORDER_OPEN_OVERDUE','SUPPLY_CHAIN','FORGING_ORDER_OPEN_OVERDUE_DIGEST','Forging Orders · Open / Overdue',7,'Supply Chain',true,'FORGING_ORDER_OPEN_OVERDUE_DIGEST'),
 ('OSP_RETURN_OPEN_OVERDUE','OSP_TRANSACTIONS','OSP_RETURN_OPEN_OVERDUE_DIGEST','OSP Returns · Open / Overdue',7,'Supply Chain',true,'OSP_RETURN_OPEN_OVERDUE_DIGEST'),
 ('NPD_PROCESS_OPEN_OVERDUE','NPD_APQP','NPD_PROCESS_OPEN_OVERDUE_DIGEST','NPD Processes · Open / Overdue',7,'R & D',false,'NPD_PROCESS_OPEN_OVERDUE_DIGEST')
) v(schedule_key,module_key,event_key,schedule_label,days_ahead,department,include_suppliers,template_key)
on conflict (tenant_id,schedule_key) do update set
 module_key=excluded.module_key,event_key=excluded.event_key,schedule_label=excluded.schedule_label,
 recipient_department=excluded.recipient_department,include_suppliers=excluded.include_suppliers,
 template_key=excluded.template_key,updated_at=now();

-- Scheduler infrastructure. A random token is generated inside Postgres, stored in
-- Vault in plaintext and stored in application tables only as SHA-256. No scheduler
-- secret is embedded in QCMS source code or the deployment updater.
create extension if not exists pg_net with schema extensions;
create extension if not exists pg_cron;

do $$
declare
  v_token text;
  v_secret_id uuid;
  v_tenant uuid;
begin
  select decrypted_secret into v_token from vault.decrypted_secrets where name='qcms_notification_scheduler_token' order by created_at desc limit 1;
  if v_token is null then
    v_token := encode(gen_random_bytes(32),'hex');
    perform vault.create_secret(v_token,'qcms_notification_scheduler_token','QCMS automatic notification scheduler token');
  end if;
  if not exists (select 1 from vault.decrypted_secrets where name='qcms_project_url') then
    perform vault.create_secret('https://xxrxopzxzyjnzumrwuwy.supabase.co','qcms_project_url','QCMS Supabase project URL for Cron Edge Function calls');
  end if;
  for v_tenant in select id from public.tenants loop
    insert into public.qcms_notification_scheduler_config(tenant_id,scheduler_token_hash,updated_at)
    values(v_tenant,encode(digest(v_token,'sha256'),'hex'),now())
    on conflict (tenant_id) do update set scheduler_token_hash=excluded.scheduler_token_hash,updated_at=now();
  end loop;
end $$;

do $$
declare v_job bigint;
begin
  select jobid into v_job from cron.job where jobname='qcms-overdue-notifier-hourly' limit 1;
  if v_job is not null then perform cron.unschedule(v_job); end if;
end $$;

select cron.schedule(
  'qcms-overdue-notifier-hourly',
  '5 * * * *',
  $cron$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name='qcms_project_url' order by created_at desc limit 1) || '/functions/v1/qcms-overdue-notifier',
    headers := jsonb_build_object(
      'Content-Type','application/json',
      'X-QCMS-Scheduler',(select decrypted_secret from vault.decrypted_secrets where name='qcms_notification_scheduler_token' order by created_at desc limit 1)
    ),
    body := jsonb_build_object('source','supabase_cron','requested_at',now()),
    timeout_milliseconds := 15000
  ) as request_id;
  $cron$
);

comment on table public.qcms_email_templates is 'QCMS v4.14.7 module/event email templates with controlled PDF/document attachment flags.';
comment on table public.qcms_notification_schedules is 'QCMS v4.14.7 automatic daily open/overdue report schedules evaluated hourly in each configured time zone.';
