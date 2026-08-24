-- QCMS v4.14.0 — PO source eligibility, HSN/SAC and email notifications

alter table public.parts add column if not exists hsn_sac_code text;
alter table public.supply_purchase_order_items add column if not exists hsn_sac_code text;


-- v4.14.0 makes Supply Flow a first-class Customer Order field so PO eligibility
-- never depends on parsing display remarks.
alter table public.supply_customer_orders add column if not exists supply_flow text;
update public.supply_customer_orders
set supply_flow = case
  when upper(coalesce(remarks,'')) like '%[[QCMS_SUPPLY_FLOW=DIRECT_FORGING]]%' then 'DIRECT_FORGING'
  else 'FSI_RM'
end
where supply_flow is null or btrim(supply_flow)='';
alter table public.supply_customer_orders alter column supply_flow set default 'FSI_RM';
alter table public.supply_customer_orders alter column supply_flow set not null;
do $$ begin
  if not exists (select 1 from pg_constraint where conname='supply_customer_orders_supply_flow_check') then
    alter table public.supply_customer_orders add constraint supply_customer_orders_supply_flow_check
      check (supply_flow in ('FSI_RM','DIRECT_FORGING'));
  end if;
end $$;
comment on column public.supply_customer_orders.supply_flow is 'QCMS controlled Supply Chain route: FSI_RM or DIRECT_FORGING.';

comment on column public.parts.hsn_sac_code is 'Default HSN / SAC code for supplier-facing purchase orders.';
comment on column public.supply_purchase_order_items.hsn_sac_code is 'Purchase Order line HSN / SAC snapshot; may be overridden during PO creation.';

create table if not exists public.qcms_email_settings(
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null unique references public.tenants(id) on delete cascade,
  enabled boolean not null default false,
  smtp_host text,
  smtp_port integer not null default 587 check (smtp_port between 1 and 65535),
  smtp_username text,
  smtp_password text,
  sender_email text,
  sender_name text not null default 'QCMS',
  reply_to text,
  use_tls boolean not null default true,
  use_ssl boolean not null default false,
  timeout_seconds integer not null default 20 check (timeout_seconds between 5 and 120),
  last_test_at timestamptz,
  last_test_status text,
  last_test_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid() references auth.users(id),
  updated_by uuid default auth.uid() references auth.users(id)
);

create table if not exists public.qcms_notification_routes(
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  event_key text not null,
  route_label text not null,
  employee_id uuid references public.employees(id),
  fallback_email text,
  subject_template text,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid() references auth.users(id),
  updated_by uuid default auth.uid() references auth.users(id),
  unique(tenant_id,event_key)
);

create table if not exists public.qcms_notification_outbox(
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  event_key text not null,
  recipient_email text not null,
  recipient_name text,
  subject text not null,
  body_text text not null,
  related_table text,
  related_id uuid,
  context jsonb not null default '{}'::jsonb,
  status text not null default 'PENDING' check (status in ('PENDING','SENDING','SENT','FAILED','CANCELLED')),
  attempts integer not null default 0,
  last_error text,
  sent_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid() references auth.users(id)
);

create index if not exists idx_qcms_notification_outbox_pending
  on public.qcms_notification_outbox(tenant_id,status,created_at);
create index if not exists idx_qcms_notification_routes_event
  on public.qcms_notification_routes(tenant_id,event_key,enabled);

alter table public.qcms_email_settings enable row level security;
alter table public.qcms_notification_routes enable row level security;
alter table public.qcms_notification_outbox enable row level security;

-- Email server credentials are Administrator-only. The Edge Function uses service-role access.
drop policy if exists qcms_email_settings_admin on public.qcms_email_settings;
create policy qcms_email_settings_admin on public.qcms_email_settings
for all to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN')
with check (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

-- Routes can be read by signed-in users so the app can resolve the next responsibility,
-- while only Administrators can maintain them.
drop policy if exists qcms_notification_routes_read on public.qcms_notification_routes;
create policy qcms_notification_routes_read on public.qcms_notification_routes
for select to authenticated
using (tenant_id=public.current_tenant_id());
drop policy if exists qcms_notification_routes_admin_write on public.qcms_notification_routes;
create policy qcms_notification_routes_admin_write on public.qcms_notification_routes
for all to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN')
with check (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

-- Any authenticated QCMS transaction may enqueue a notification for its own tenant.
-- Reading/cancelling the outbox is restricted to Administrators.
drop policy if exists qcms_notification_outbox_insert on public.qcms_notification_outbox;
create policy qcms_notification_outbox_insert on public.qcms_notification_outbox
for insert to authenticated
with check (tenant_id=public.current_tenant_id());
drop policy if exists qcms_notification_outbox_admin_read on public.qcms_notification_outbox;
create policy qcms_notification_outbox_admin_read on public.qcms_notification_outbox
for select to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');
drop policy if exists qcms_notification_outbox_creator_read on public.qcms_notification_outbox;
create policy qcms_notification_outbox_creator_read on public.qcms_notification_outbox
for select to authenticated
using (tenant_id=public.current_tenant_id() and created_by=auth.uid());
drop policy if exists qcms_notification_outbox_admin_update on public.qcms_notification_outbox;
create policy qcms_notification_outbox_admin_update on public.qcms_notification_outbox
for update to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN')
with check (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

grant select,insert,update,delete on public.qcms_email_settings to authenticated;
grant select,insert,update,delete on public.qcms_notification_routes to authenticated;
grant select,insert,update on public.qcms_notification_outbox to authenticated;

-- Default responsibility routes based on the current Employee Master when matching employees exist.
insert into public.qcms_notification_routes(tenant_id,event_key,route_label,employee_id,fallback_email,subject_template,enabled)
select e.tenant_id,'RMTC_APPROVAL_PENDING','RMTC approval pending',e.id,e.email,'QCMS · RMTC approval pending',true
from public.employees e
where lower(btrim(e.first_name))='gulab' and lower(btrim(e.last_name))='varpe' and e.status='ACTIVE'
on conflict (tenant_id,event_key) do update set
  employee_id=excluded.employee_id,fallback_email=excluded.fallback_email,route_label=excluded.route_label,subject_template=excluded.subject_template,enabled=true,updated_at=now();

insert into public.qcms_notification_routes(tenant_id,event_key,route_label,employee_id,fallback_email,subject_template,enabled)
select e.tenant_id,'METLAB_APPROVAL_PENDING','MetLAB approval pending',e.id,e.email,'QCMS · MetLAB approval pending',true
from public.employees e
where lower(btrim(e.first_name))='gulab' and lower(btrim(e.last_name))='varpe' and e.status='ACTIVE'
on conflict (tenant_id,event_key) do update set
  employee_id=excluded.employee_id,fallback_email=excluded.fallback_email,route_label=excluded.route_label,subject_template=excluded.subject_template,enabled=true,updated_at=now();

insert into public.qcms_notification_routes(tenant_id,event_key,route_label,employee_id,fallback_email,subject_template,enabled)
select e.tenant_id,'DIMENSIONAL_APPROVAL_PENDING','Dimensional inspection approval pending',e.id,e.email,'QCMS · Dimensional approval pending',true
from public.employees e
where lower(btrim(e.first_name))='nitin' and lower(btrim(e.last_name))='nanavare' and e.status='ACTIVE'
on conflict (tenant_id,event_key) do update set
  employee_id=excluded.employee_id,fallback_email=excluded.fallback_email,route_label=excluded.route_label,subject_template=excluded.subject_template,enabled=true,updated_at=now();

-- Additional workflow events start disabled until an Administrator maps a responsible employee.
insert into public.qcms_notification_routes(tenant_id,event_key,route_label,enabled)
select t.id,v.event_key,v.route_label,false
from public.tenants t
cross join (values
 ('RM_PROCUREMENT_PENDING','Raw Material procurement pending'),
 ('RM_RECEIPT_PENDING','Raw Material receipt pending'),
 ('FORGING_ORDER_PENDING','Forging order pending'),
 ('FORGING_RECEIPT_PENDING','Forging receipt pending'),
 ('OSP_SAMPLE_PENDING','OSP sample inspection pending')
) v(event_key,route_label)
on conflict (tenant_id,event_key) do nothing;

comment on table public.qcms_email_settings is 'QCMS v4.14.0 tenant SMTP settings. SMTP password is never rendered back to normal application users; delivery is server-side through qcms-send-email.';
comment on table public.qcms_notification_routes is 'QCMS v4.14.0 configurable transaction-to-responsible-person email routing.';
comment on table public.qcms_notification_outbox is 'QCMS v4.14.0 reliable notification outbox with retry/audit status.';
