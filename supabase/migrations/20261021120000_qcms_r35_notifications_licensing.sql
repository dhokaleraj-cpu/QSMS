-- QCMS v4.14.49 R35 · In-app notifications, mobile push devices, WhatsApp auto messages,
-- STAWN licensing (company licence, seats, online key validation), company profile and STAWN developer.
-- Additive and safe to re-run. Never changes or deletes business data.

-- =====================================================================================
-- 0) Helpers (internal functions live in schema qcms_private, which the REST API does not expose)
-- =====================================================================================
create schema if not exists qcms_private;
revoke all on schema qcms_private from public, anon, authenticated;
create table if not exists public.qcms_stawn_developers (
  profile_id uuid primary key,
  email text,
  full_name text,
  active boolean not null default true,
  created_at timestamptz not null default now()
);
create or replace function public.qcms_is_stawn_developer()
returns boolean language sql stable security definer set search_path = public, auth as $$
  select exists (select 1 from public.qcms_stawn_developers d where d.profile_id = auth.uid() and d.active)
$$;

alter table public.qcms_stawn_developers enable row level security;
revoke all on public.qcms_stawn_developers from anon;
revoke insert, update, delete on public.qcms_stawn_developers from authenticated;
grant select on public.qcms_stawn_developers to authenticated;
do $pol$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'qcms_stawn_developers' and policyname = 'qcms_stawn_developers_select') then
    create policy qcms_stawn_developers_select on public.qcms_stawn_developers for select to authenticated
  using (profile_id = auth.uid() or public.qcms_is_stawn_developer());
  end if;
end $pol$;

revoke all on function public.qcms_is_stawn_developer() from public, anon;
grant execute on function public.qcms_is_stawn_developer() to authenticated;

-- Seed the STAWN developer login(s). Profile role stays ADMIN, so every existing role check treats
-- the developer like the top administrator; the developer flag adds the cross-company console.
insert into public.qcms_stawn_developers (profile_id, email, full_name)
select p.id, p.email, p.full_name from public.profiles p
where lower(p.email) in ('dhokaleraj@icloud.com', 'rajesh.dhokale@fourstarindustries.com')
on conflict (profile_id) do nothing;

create or replace function public.qcms__my_employee_ids()
returns setof uuid language sql stable security definer set search_path = public, auth as $$
  select e.id from public.employees e
  where e.tenant_id = public.current_tenant_id()
    and (e.profile_id = auth.uid()
         or (e.profile_id is null and lower(coalesce(e.email,'')) = lower(coalesce((select p.email from public.profiles p where p.id = auth.uid()), '#'))))
$$;
revoke all on function public.qcms__my_employee_ids() from public, anon;
grant execute on function public.qcms__my_employee_ids() to authenticated;

-- =====================================================================================
-- 1) In-app notifications
-- =====================================================================================
create table if not exists public.qcms_user_notifications (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id(),
  recipient_profile_id uuid,
  recipient_employee_id uuid,
  title text not null,
  body text,
  category text not null default 'UPDATE',
  module_key text,
  related_table text,
  related_id uuid,
  web_route text,
  priority text not null default 'NORMAL',
  is_read boolean not null default false,
  read_at timestamptz,
  created_at timestamptz not null default now(),
  created_by uuid,
  push_status text default 'PENDING',
  whatsapp_status text,
  source_key text,
  push_attempts integer not null default 0,
  pushed_at timestamptz,
  push_error text,
  whatsapp_sent_at timestamptz,
  whatsapp_error text
);
alter table public.qcms_user_notifications add column if not exists source_key text;
alter table public.qcms_user_notifications add column if not exists push_attempts integer not null default 0;
alter table public.qcms_user_notifications add column if not exists pushed_at timestamptz;
alter table public.qcms_user_notifications add column if not exists push_error text;
alter table public.qcms_user_notifications add column if not exists whatsapp_sent_at timestamptz;
alter table public.qcms_user_notifications add column if not exists whatsapp_error text;

create index if not exists qcms_user_notifications_profile_idx on public.qcms_user_notifications (recipient_profile_id, is_read, created_at desc);
create index if not exists qcms_user_notifications_employee_idx on public.qcms_user_notifications (recipient_employee_id, is_read, created_at desc);
create index if not exists qcms_user_notifications_push_idx on public.qcms_user_notifications (push_status, created_at) where push_status = 'PENDING';
create index if not exists qcms_user_notifications_wa_idx on public.qcms_user_notifications (whatsapp_status, created_at) where whatsapp_status = 'PENDING';
create unique index if not exists qcms_user_notifications_dedupe
  on public.qcms_user_notifications (tenant_id, (coalesce(recipient_profile_id, recipient_employee_id)), source_key)
  where source_key is not null;

alter table public.qcms_user_notifications enable row level security;
revoke all on public.qcms_user_notifications from anon;
revoke insert, update, delete on public.qcms_user_notifications from authenticated;
grant select on public.qcms_user_notifications to authenticated;
do $pol$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'qcms_user_notifications' and policyname = 'qcms_user_notifications_select') then
    create policy qcms_user_notifications_select on public.qcms_user_notifications for select to authenticated
  using (tenant_id = public.current_tenant_id()
         and (recipient_profile_id = auth.uid()
              or recipient_employee_id in (select public.qcms__my_employee_ids())));
  end if;
end $pol$;

-- WhatsApp settings (Meta WhatsApp Business Cloud API). The access token is NEVER stored here:
-- it is the edge-function secret WHATSAPP_TOKEN.
create table if not exists public.qcms_whatsapp_settings (
  tenant_id uuid primary key default public.current_tenant_id(),
  enabled boolean not null default false,
  phone_number_id text,
  business_account_id text,
  api_version text not null default 'v21.0',
  approval_template text not null default 'qcms_approval_request',
  task_template text not null default 'qcms_task_alert',
  update_template text not null default 'qcms_update_alert',
  template_language text not null default 'en',
  send_categories text[] not null default array['APPROVAL','TASK'],
  default_country_code text not null default '91',
  app_link text,
  updated_at timestamptz not null default now(),
  updated_by uuid
);
alter table public.qcms_whatsapp_settings enable row level security;
revoke all on public.qcms_whatsapp_settings from anon;
grant select, insert, update on public.qcms_whatsapp_settings to authenticated;
do $pol$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'qcms_whatsapp_settings' and policyname = 'qcms_whatsapp_settings_select') then
    create policy qcms_whatsapp_settings_select on public.qcms_whatsapp_settings for select to authenticated
  using (tenant_id = public.current_tenant_id() or public.qcms_is_stawn_developer());
  end if;
end $pol$;
do $pol$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'qcms_whatsapp_settings' and policyname = 'qcms_whatsapp_settings_write') then
    create policy qcms_whatsapp_settings_write on public.qcms_whatsapp_settings for insert to authenticated
  with check (tenant_id = public.current_tenant_id() and (public.current_app_role() = 'ADMIN' or public.qcms_is_stawn_developer()));
  end if;
end $pol$;
do $pol$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'qcms_whatsapp_settings' and policyname = 'qcms_whatsapp_settings_update') then
    create policy qcms_whatsapp_settings_update on public.qcms_whatsapp_settings for update to authenticated
  using (tenant_id = public.current_tenant_id() and (public.current_app_role() = 'ADMIN' or public.qcms_is_stawn_developer()))
  with check (tenant_id = public.current_tenant_id());
  end if;
end $pol$;

alter table public.employees add column if not exists whatsapp_opt_in boolean not null default false;

-- Internal writer used by triggers and qcms_notify. Never raises.
create or replace function qcms_private.qcms__add_notification(
  p_tenant_id uuid, p_profile_id uuid, p_employee_id uuid, p_title text, p_body text,
  p_category text default 'UPDATE', p_module_key text default null, p_related_table text default null,
  p_related_id uuid default null, p_web_route text default null, p_source_key text default null,
  p_priority text default 'NORMAL', p_created_by uuid default null)
returns uuid language plpgsql security definer set search_path = public, auth as $$
declare
  v_profile uuid := p_profile_id;
  v_employee uuid := p_employee_id;
  v_email text;
  v_id uuid;
  v_wa text;
  v_cat text := upper(coalesce(nullif(btrim(p_category), ''), 'UPDATE'));
begin
  if p_tenant_id is null or coalesce(btrim(p_title), '') = '' then return null; end if;
  if v_employee is not null and v_profile is null then
    select e.profile_id, e.email into v_profile, v_email from public.employees e where e.id = v_employee and e.tenant_id = p_tenant_id;
    if v_profile is null and coalesce(v_email, '') <> '' then
      select p.id into v_profile from public.profiles p where p.tenant_id = p_tenant_id and lower(p.email) = lower(v_email) and p.status = 'ACTIVE' limit 1;
    end if;
  end if;
  if v_profile is not null and v_employee is null then
    select e.id into v_employee from public.employees e where e.tenant_id = p_tenant_id and e.profile_id = v_profile limit 1;
    if v_employee is null then
      select e.id into v_employee from public.employees e join public.profiles p on lower(p.email) = lower(e.email)
      where e.tenant_id = p_tenant_id and p.id = v_profile limit 1;
    end if;
  end if;
  if v_profile is null and v_employee is null then return null; end if;
  -- the person who caused the event does not need a notification about it
  if v_profile is not null and v_profile = coalesce(p_created_by, auth.uid()) and v_cat in ('APPROVAL','TASK') and coalesce(p_source_key, '') not like 'TEST:%' then
    return null;
  end if;
  select case when s.enabled and v_cat = any(s.send_categories) then 'PENDING' else null end into v_wa
  from public.qcms_whatsapp_settings s where s.tenant_id = p_tenant_id;
  insert into public.qcms_user_notifications (tenant_id, recipient_profile_id, recipient_employee_id, title, body, category,
      module_key, related_table, related_id, web_route, priority, created_by, source_key, whatsapp_status, push_status)
  values (p_tenant_id, v_profile, v_employee, left(btrim(p_title), 300), left(p_body, 4000), v_cat, p_module_key, p_related_table,
      p_related_id, p_web_route, upper(coalesce(p_priority, 'NORMAL')), coalesce(p_created_by, auth.uid()), p_source_key, v_wa,
      case when v_profile is null then 'NO_DEVICE' else 'PENDING' end)
  on conflict (tenant_id, (coalesce(recipient_profile_id, recipient_employee_id)), source_key) where source_key is not null do nothing
  returning id into v_id;
  return v_id;
exception when others then
  return null;
end $$;
revoke all on function qcms_private.qcms__add_notification(uuid,uuid,uuid,text,text,text,text,text,uuid,text,text,text,uuid) from public, anon, authenticated;

create or replace function public.qcms_notify(
  p_recipient_profile_id uuid, p_recipient_employee_id uuid, p_title text, p_body text,
  p_category text default 'UPDATE', p_module_key text default null, p_related_table text default null,
  p_related_id uuid default null, p_web_route text default null)
returns uuid language plpgsql security definer set search_path = public, auth as $$
declare tid uuid := public.current_tenant_id();
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if p_recipient_profile_id is not null and not exists (select 1 from public.profiles p where p.id = p_recipient_profile_id and p.tenant_id = tid) then
    raise exception 'Recipient is not a user of this company';
  end if;
  if p_recipient_employee_id is not null and not exists (select 1 from public.employees e where e.id = p_recipient_employee_id and e.tenant_id = tid) then
    raise exception 'Recipient is not an employee of this company';
  end if;
  return qcms_private.qcms__add_notification(tid, p_recipient_profile_id, p_recipient_employee_id, p_title, p_body, p_category,
    p_module_key, p_related_table, p_related_id, p_web_route, null, 'NORMAL', auth.uid());
end $$;
revoke all on function public.qcms_notify(uuid,uuid,text,text,text,text,text,uuid,text) from public, anon;
grant execute on function public.qcms_notify(uuid,uuid,text,text,text,text,text,uuid,text) to authenticated;

create or replace function public.qcms_my_notifications(p_limit integer default 50, p_unread_only boolean default false)
returns setof public.qcms_user_notifications language sql stable security definer set search_path = public, auth as $$
  select n.* from public.qcms_user_notifications n
  where n.tenant_id = public.current_tenant_id()
    and (n.recipient_profile_id = auth.uid() or n.recipient_employee_id in (select public.qcms__my_employee_ids()))
    and (not coalesce(p_unread_only, false) or not n.is_read)
  order by n.created_at desc
  limit greatest(1, least(coalesce(p_limit, 50), 500))
$$;
revoke all on function public.qcms_my_notifications(integer, boolean) from public, anon;
grant execute on function public.qcms_my_notifications(integer, boolean) to authenticated;

create or replace function public.qcms_unread_notification_count()
returns integer language sql stable security definer set search_path = public, auth as $$
  select count(*)::integer from public.qcms_user_notifications n
  where n.tenant_id = public.current_tenant_id() and not n.is_read
    and (n.recipient_profile_id = auth.uid() or n.recipient_employee_id in (select public.qcms__my_employee_ids()))
$$;
revoke all on function public.qcms_unread_notification_count() from public, anon;
grant execute on function public.qcms_unread_notification_count() to authenticated;

create or replace function public.qcms_mark_notifications_read(p_ids uuid[] default null)
returns integer language plpgsql security definer set search_path = public, auth as $$
declare v integer;
begin
  if auth.uid() is null then raise exception 'Authenticated QCMS session required'; end if;
  update public.qcms_user_notifications n set is_read = true, read_at = now()
  where n.tenant_id = public.current_tenant_id() and not n.is_read
    and (n.recipient_profile_id = auth.uid() or n.recipient_employee_id in (select public.qcms__my_employee_ids()))
    and (p_ids is null or n.id = any(p_ids));
  get diagnostics v = row_count;
  return v;
end $$;
revoke all on function public.qcms_mark_notifications_read(uuid[]) from public, anon;
grant execute on function public.qcms_mark_notifications_read(uuid[]) to authenticated;

-- My own WhatsApp opt-in (own employee row only)
create or replace function public.qcms_set_my_whatsapp(p_opt_in boolean, p_mobile_number text default null)
returns jsonb language plpgsql security definer set search_path = public, auth as $$
declare v_emp uuid; v_num text := nullif(regexp_replace(coalesce(p_mobile_number, ''), '[^0-9+]', '', 'g'), '');
begin
  if auth.uid() is null then raise exception 'Authenticated QCMS session required'; end if;
  select id into v_emp from public.qcms__my_employee_ids() as id limit 1;
  if v_emp is null then raise exception 'Your login is not linked to an Employee record. Ask the administrator to link it in Users & Access.'; end if;
  update public.employees set whatsapp_opt_in = coalesce(p_opt_in, false),
         mobile_number = coalesce(v_num, mobile_number), updated_at = now()
  where id = v_emp;
  return (select jsonb_build_object('employee_id', e.id, 'whatsapp_opt_in', e.whatsapp_opt_in, 'mobile_number', e.mobile_number) from public.employees e where e.id = v_emp);
end $$;
revoke all on function public.qcms_set_my_whatsapp(boolean, text) from public, anon;
grant execute on function public.qcms_set_my_whatsapp(boolean, text) to authenticated;

-- =====================================================================================
-- 2) Mobile push devices
-- =====================================================================================
create table if not exists public.qcms_push_devices (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id(),
  profile_id uuid not null default auth.uid(),
  platform text not null,
  token text not null unique,
  app_version text,
  enabled boolean not null default true,
  last_seen_at timestamptz not null default now(),
  last_error text,
  created_at timestamptz not null default now()
);
create index if not exists qcms_push_devices_profile_idx on public.qcms_push_devices (profile_id) where enabled;
alter table public.qcms_push_devices enable row level security;
revoke all on public.qcms_push_devices from anon;
revoke insert, update, delete on public.qcms_push_devices from authenticated;
grant select on public.qcms_push_devices to authenticated;
do $pol$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'qcms_push_devices' and policyname = 'qcms_push_devices_select') then
    create policy qcms_push_devices_select on public.qcms_push_devices for select to authenticated using (profile_id = auth.uid());
  end if;
end $pol$;

create or replace function public.qcms_register_push_device(p_platform text, p_token text, p_app_version text default null)
returns void language plpgsql security definer set search_path = public, auth as $$
declare tid uuid := public.current_tenant_id(); v_platform text := upper(coalesce(btrim(p_platform), ''));
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if v_platform not in ('IOS', 'IOS_SANDBOX', 'ANDROID', 'WEB') then raise exception 'Unknown push platform %', p_platform; end if;
  if coalesce(btrim(p_token), '') = '' or length(p_token) > 4096 then raise exception 'Push token is missing'; end if;
  insert into public.qcms_push_devices (tenant_id, profile_id, platform, token, app_version, enabled, last_seen_at, last_error)
  values (tid, auth.uid(), v_platform, btrim(p_token), p_app_version, true, now(), null)
  on conflict (token) do update set tenant_id = excluded.tenant_id, profile_id = excluded.profile_id, platform = excluded.platform,
     app_version = excluded.app_version, enabled = true, last_seen_at = now(), last_error = null;
end $$;
revoke all on function public.qcms_register_push_device(text, text, text) from public, anon;
grant execute on function public.qcms_register_push_device(text, text, text) to authenticated;

-- =====================================================================================
-- 3) Automatic notifications (DB triggers; never block the business transaction)
-- =====================================================================================
create or replace function qcms_private.qcms__emp_name(p_employee_id uuid)
returns text language sql stable security definer set search_path = public as $$
  select nullif(btrim(coalesce(e.first_name,'') || ' ' || coalesce(e.last_name,'')), '') from public.employees e where e.id = p_employee_id
$$;
revoke all on function qcms_private.qcms__emp_name(uuid) from public, anon, authenticated;

-- 3a) Purchase orders: approval request -> approver(s); decision / cancel -> submitter + creator
create or replace function qcms_private.qcms__trg_po_notifications()
returns trigger language plpgsql security definer set search_path = public, auth as $$
declare
  r record; v_dept text; v_found boolean := false; v_po text := coalesce(new.po_number, 'draft');
  v_sup text; v_key text;
begin
  begin
    select coalesce(pt.party_name, pt.party_code) into v_sup from public.parties pt where pt.id = new.supplier_id;
    if new.approval_status = 'PENDING_APPROVAL' and (tg_op = 'INSERT' or old.approval_status is distinct from new.approval_status) then
      v_key := 'PO_APPROVAL:' || new.id || ':' || current_date;   -- same key as the e-mail mirror below
      if new.approver_employee_id is not null then
        perform qcms_private.qcms__add_notification(new.tenant_id, null, new.approver_employee_id, 'Approval required · PO ' || v_po,
          'Purchase Order ' || v_po || coalesce(' for ' || v_sup, '') || ' is waiting for your approval' ||
          coalesce(' (submitted by ' || qcms_private.qcms__emp_name(new.submitted_by_employee_id) || ')', '') || '.',
          'APPROVAL', 'SUPPLY_CHAIN', 'supply_purchase_orders', new.id, 'supply-po-approval', v_key, 'HIGH', new.updated_by);
        v_found := true;
      else
        select lower(btrim(coalesce(e.department, ''))) into v_dept from public.employees e where e.id = new.submitted_by_employee_id;
        for r in
          select ar.employee_id from public.qcms_module_approval_routes ar
          where ar.tenant_id = new.tenant_id and ar.module_key = 'SUPPLY_CHAIN' and ar.status = 'ACTIVE' and ar.required
            and ar.employee_id is not null and (ar.department is null or lower(btrim(ar.department)) = coalesce(v_dept, ''))
            and coalesce(ar.level_no, 1) = (select min(coalesce(a2.level_no, 1)) from public.qcms_module_approval_routes a2
               where a2.tenant_id = new.tenant_id and a2.module_key = 'SUPPLY_CHAIN' and a2.status = 'ACTIVE' and a2.required and a2.employee_id is not null
                 and (a2.department is null or lower(btrim(a2.department)) = coalesce(v_dept, '')))
        loop
          perform qcms_private.qcms__add_notification(new.tenant_id, null, r.employee_id, 'Approval required · PO ' || v_po,
            'Purchase Order ' || v_po || coalesce(' for ' || v_sup, '') || ' is waiting for your approval.',
            'APPROVAL', 'SUPPLY_CHAIN', 'supply_purchase_orders', new.id, 'supply-po-approval', v_key, 'HIGH', new.updated_by);
          v_found := true;
        end loop;
        if not v_found then
          for r in select e.reports_to_employee_id as employee_id from public.employees e
                   where e.id = new.submitted_by_employee_id and e.reports_to_employee_id is not null loop
            perform qcms_private.qcms__add_notification(new.tenant_id, null, r.employee_id, 'Approval required · PO ' || v_po,
              'Purchase Order ' || v_po || coalesce(' for ' || v_sup, '') || ' is waiting for your approval.',
              'APPROVAL', 'SUPPLY_CHAIN', 'supply_purchase_orders', new.id, 'supply-po-approval', v_key, 'HIGH', new.updated_by);
          end loop;
        end if;
      end if;
    end if;
    if tg_op = 'UPDATE' and new.approval_status in ('APPROVED', 'REJECTED', 'CANCELLED')
       and old.approval_status is distinct from new.approval_status then
      v_key := 'PO_DECISION:' || new.id || ':' || new.approval_status;
      perform qcms_private.qcms__add_notification(new.tenant_id, null, new.submitted_by_employee_id,
        'PO ' || v_po || ' ' || lower(new.approval_status),
        'Purchase Order ' || v_po || coalesce(' for ' || v_sup, '') || ' was ' || lower(new.approval_status) ||
        coalesce(' by ' || qcms_private.qcms__emp_name(coalesce(new.approver_employee_id, new.cancelled_by_employee_id)), '') ||
        coalesce('. Remarks: ' || nullif(btrim(coalesce(new.approval_remarks, new.cancellation_reason, '')), ''), '') || '.',
        case when new.approval_status = 'APPROVED' then 'UPDATE' else 'ALERT' end,
        'SUPPLY_CHAIN', 'supply_purchase_orders', new.id, 'supply-po-order-list', v_key, 'NORMAL', new.updated_by);
      if new.created_by is not null then
        perform qcms_private.qcms__add_notification(new.tenant_id, new.created_by, null,
          'PO ' || v_po || ' ' || lower(new.approval_status),
          'Purchase Order ' || v_po || coalesce(' for ' || v_sup, '') || ' was ' || lower(new.approval_status) || '.',
          case when new.approval_status = 'APPROVED' then 'UPDATE' else 'ALERT' end,
          'SUPPLY_CHAIN', 'supply_purchase_orders', new.id, 'supply-po-order-list', v_key, 'NORMAL', new.updated_by);
      end if;
    end if;
  exception when others then null;
  end;
  return new;
end $$;
revoke all on function qcms_private.qcms__trg_po_notifications() from public, anon, authenticated;
create or replace trigger qcms_r35_po_notifications after insert or update of approval_status on public.supply_purchase_orders
for each row execute function qcms_private.qcms__trg_po_notifications();

-- 3b) Deletion requests: request -> Admin / Quality Manager; decision -> requester
create or replace function qcms_private.qcms__trg_delete_request_notifications()
returns trigger language plpgsql security definer set search_path = public, auth as $$
declare r record; v_label text := coalesce(nullif(new.record_label, ''), new.table_name);
begin
  begin
    if tg_op = 'INSERT' and coalesce(new.status, 'PENDING') = 'PENDING' then
      for r in select p.id from public.profiles p where p.tenant_id = new.tenant_id and p.status = 'ACTIVE'
                 and p.role in ('ADMIN', 'QUALITY_MANAGER') and p.id is distinct from new.requested_by loop
        perform qcms_private.qcms__add_notification(new.tenant_id, r.id, null, 'Deletion approval required · ' || v_label,
          'A deletion request is waiting for approval. Record: ' || v_label || '. Reason: ' || coalesce(new.reason, '-') || '.',
          'APPROVAL', 'RECORDS', 'qcms_delete_requests', new.id, 'records-center', 'DEL_REQ:' || new.id, 'HIGH', new.requested_by);
      end loop;
    elsif tg_op = 'UPDATE' and new.status is distinct from old.status and new.status <> 'PENDING' and new.requested_by is not null then
      perform qcms_private.qcms__add_notification(new.tenant_id, new.requested_by, null, 'Deletion request ' || lower(new.status) || ' · ' || v_label,
        'Your deletion request for ' || v_label || ' is ' || lower(new.status) || coalesce('. Note: ' || nullif(new.decision_note, ''), '') || '.',
        case when new.status in ('REJECTED', 'FAILED') then 'ALERT' else 'UPDATE' end,
        'RECORDS', 'qcms_delete_requests', new.id, 'records-center', 'DEL_RESULT:' || new.id || ':' || new.status, 'NORMAL', new.decided_by);
    end if;
  exception when others then null;
  end;
  return new;
end $$;
revoke all on function qcms_private.qcms__trg_delete_request_notifications() from public, anon, authenticated;
create or replace trigger qcms_r35_delete_request_notifications after insert or update of status on public.qcms_delete_requests
for each row execute function qcms_private.qcms__trg_delete_request_notifications();

-- 3c) Inspection reports (Dimensional / OSP Dimensional) and lab tests (MetLAB / Bend / OSP MetLAB)
create or replace function qcms_private.qcms__trg_inspection_notifications()
returns trigger language plpgsql security definer set search_path = public, auth as $$
declare
  v_kind text; v_route text; v_module text; v_no text := coalesce(new.report_number, 'draft'); v_part text;
  v_new jsonb := to_jsonb(new); v_old jsonb := case when tg_op = 'UPDATE' then to_jsonb(old) else '{}'::jsonb end;
  v_osp boolean := new.osp_job_id is not null;
begin
  begin
    if tg_table_name = 'inspection_reports' then
      v_kind := case when v_osp then 'OSP Dimensional' else 'Dimensional' end;
      v_route := case when v_osp then 'osp-dimensional' else 'dimensional-entry' end; v_module := 'DIMENSIONAL_REPORT';
    else
      if upper(coalesce(v_new->>'layout_type_name', '')) like '%BEND%' then v_kind := 'Bend Test'; v_route := 'bend-test-entry';
      else v_kind := case when v_osp then 'OSP MetLAB' else 'MetLAB' end; v_route := case when v_osp then 'osp-metlab' else 'metlab-entry' end; end if;
      v_module := 'METLAB_REPORT';
    end if;
    select coalesce(p.part_number, p.fsi_part_number) into v_part from public.parts p where p.id = new.part_id;
    if coalesce(new.status, 'DRAFT') <> 'FINAL' then
      -- validator assigned and validation pending
      if new.validated_by_employee_id is not null and new.validated_at is null
         and (tg_op = 'INSERT' or (v_old->>'validated_by_employee_id') is distinct from (v_new->>'validated_by_employee_id')) then
        perform qcms_private.qcms__add_notification(new.tenant_id, null, new.validated_by_employee_id, v_kind || ' report to validate · ' || v_no,
          v_kind || ' report ' || v_no || coalesce(' (part ' || v_part || ')', '') || coalesce(', heat ' || nullif(new.heat_number, ''), '') ||
          ' is waiting for your validation.', 'TASK', v_module, tg_table_name, new.id, v_route,
          'INSP_VALIDATE:' || new.id || ':' || new.validated_by_employee_id, 'HIGH', new.updated_by);
      end if;
      -- validated -> approver
      if new.approved_by_employee_id is not null and new.validated_at is not null
         and (tg_op = 'INSERT' or (v_old->>'validated_at') is null or (v_old->>'approved_by_employee_id') is distinct from (v_new->>'approved_by_employee_id')) then
        perform qcms_private.qcms__add_notification(new.tenant_id, null, new.approved_by_employee_id, v_kind || ' report to approve · ' || v_no,
          v_kind || ' report ' || v_no || coalesce(' (part ' || v_part || ')', '') || ' is validated and waiting for your approval / final decision.',
          'APPROVAL', v_module, tg_table_name, new.id, v_route, 'INSP_APPROVAL:' || new.id, 'HIGH', new.updated_by);
      end if;
    elsif tg_op = 'UPDATE' and coalesce(old.status, '') <> 'FINAL' then
      perform qcms_private.qcms__add_notification(new.tenant_id, null, new.prepared_by_employee_id, v_kind || ' report finalized · ' || v_no,
        v_kind || ' report ' || v_no || coalesce(' (part ' || v_part || ')', '') || ' was finalized' ||
        coalesce(': ' || nullif(new.disposition, ''), '') || '.', 'UPDATE', v_module, tg_table_name, new.id, v_route,
        'INSP_FINAL:' || new.id, 'NORMAL', new.updated_by);
      if new.created_by is not null then
        perform qcms_private.qcms__add_notification(new.tenant_id, new.created_by, null, v_kind || ' report finalized · ' || v_no,
          v_kind || ' report ' || v_no || ' was finalized' || coalesce(': ' || nullif(new.disposition, ''), '') || '.',
          'UPDATE', v_module, tg_table_name, new.id, v_route, 'INSP_FINAL:' || new.id, 'NORMAL', new.updated_by);
      end if;
    end if;
  exception when others then null;
  end;
  return new;
end $$;
revoke all on function qcms_private.qcms__trg_inspection_notifications() from public, anon, authenticated;
create or replace trigger qcms_r35_inspection_notifications after insert or update on public.inspection_reports
for each row execute function qcms_private.qcms__trg_inspection_notifications();
create or replace trigger qcms_r35_labtest_notifications after insert or update on public.lab_tests
for each row execute function qcms_private.qcms__trg_inspection_notifications();

-- 3d) Complaint assignments and CAPA action owners
create or replace function qcms_private.qcms__trg_complaint_notifications()
returns trigger language plpgsql security definer set search_path = public, auth as $$
declare v_no text; v_new jsonb := to_jsonb(new); v_old jsonb := case when tg_op = 'UPDATE' then to_jsonb(old) else '{}'::jsonb end;
  f text; v_emp uuid; v_role text;
begin
  begin
    if tg_table_name = 'quality_complaints' then
      v_no := coalesce(new.complaint_number, 'complaint');
      foreach f in array array['fourstar_responsible_employee_id','containment_responsible_employee_id','root_cause_responsible_employee_id'] loop
        if (v_new->>f) is not null and (v_new->>f) is distinct from (v_old->>f) and coalesce(new.status, 'OPEN') not in ('CLOSED','CANCELLED') then
          v_emp := (v_new->>f)::uuid;
          v_role := case f when 'fourstar_responsible_employee_id' then 'responsible person'
                           when 'containment_responsible_employee_id' then 'containment owner' else 'root-cause owner' end;
          perform qcms_private.qcms__add_notification(new.tenant_id, null, v_emp, 'Complaint assigned · ' || v_no,
            'You are the ' || v_role || ' for ' || lower(coalesce(new.complaint_type, '')) || ' complaint ' || v_no ||
            coalesce(': ' || nullif(new.subject, ''), '') || coalesce('. Target closure ' || to_char(new.target_closure_date, 'DD-MM-YYYY'), '') || '.',
            'TASK', 'COMPLAINT_MANAGEMENT', 'quality_complaints', new.id, 'complaint-analysis', 'CMP:' || new.id || ':' || f || ':' || v_emp, 'NORMAL', new.updated_by);
        end if;
      end loop;
    else
      if new.owner_employee_id is not null and (tg_op = 'INSERT' or old.owner_employee_id is distinct from new.owner_employee_id)
         and coalesce(new.status, 'OPEN') not in ('CLOSED','COMPLETED','CANCELLED') then
        select c.complaint_number into v_no from public.quality_complaints c where c.id = new.complaint_id;
        perform qcms_private.qcms__add_notification(new.tenant_id, null, new.owner_employee_id, 'CAPA action assigned · ' || coalesce(v_no, ''),
          coalesce(new.action_type, 'Action') || ' ' || coalesce(new.action_no::text, '') || ': ' || left(coalesce(new.action_description, ''), 300) ||
          coalesce('. Target ' || to_char(new.target_date, 'DD-MM-YYYY'), '') || '.',
          'TASK', 'COMPLAINT_MANAGEMENT', 'quality_complaints', new.complaint_id, 'complaint-analysis', 'CAPA:' || new.id || ':' || new.owner_employee_id, 'NORMAL', new.updated_by);
      end if;
    end if;
  exception when others then null;
  end;
  return new;
end $$;
revoke all on function qcms_private.qcms__trg_complaint_notifications() from public, anon, authenticated;
create or replace trigger qcms_r35_complaint_notifications after insert or update on public.quality_complaints
for each row execute function qcms_private.qcms__trg_complaint_notifications();
create or replace trigger qcms_r35_capa_notifications after insert or update of owner_employee_id on public.quality_complaint_actions
for each row execute function qcms_private.qcms__trg_complaint_notifications();

-- 3e) Customer orders: responsible employee receives the task
create or replace function qcms_private.qcms__trg_customer_order_notifications()
returns trigger language plpgsql security definer set search_path = public, auth as $$
declare v_part text;
begin
  begin
    if new.responsible_employee_id is not null and (tg_op = 'INSERT' or old.responsible_employee_id is distinct from new.responsible_employee_id) then
      select coalesce(p.part_number, p.fsi_part_number) into v_part from public.parts p where p.id = new.part_id;
      perform qcms_private.qcms__add_notification(new.tenant_id, null, new.responsible_employee_id,
        'New customer order task · ' || coalesce(new.customer_order_no, '-') || coalesce(' / ' || nullif(new.order_position, ''), ''),
        'Customer order ' || coalesce(new.customer_order_no, '-') || coalesce(' pos ' || nullif(new.order_position, ''), '') ||
        coalesce(', part ' || v_part, '') || coalesce(', ' || trim(to_char(new.order_qty_pcs, 'FM999G999G990')) || ' pcs', '') ||
        coalesce(', due ' || to_char(new.customer_delivery_date, 'DD-MM-YYYY'), '') || ' is assigned to you.',
        'TASK', 'SUPPLY_CHAIN', 'supply_customer_orders', new.id, 'supply-customer-orders',
        'CO_TASK:' || new.id || ':' || new.responsible_employee_id, 'NORMAL', coalesce(new.updated_by, new.created_by));
    end if;
  exception when others then null;
  end;
  return new;
end $$;
revoke all on function qcms_private.qcms__trg_customer_order_notifications() from public, anon, authenticated;
create or replace trigger qcms_r35_customer_order_notifications after insert or update of responsible_employee_id on public.supply_customer_orders
for each row execute function qcms_private.qcms__trg_customer_order_notifications();

-- 3f) Every e-mail the app queues for a QCMS user also appears in that user's in-app notifications
create or replace function qcms_private.qcms__trg_outbox_to_inapp()
returns trigger language plpgsql security definer set search_path = public, auth as $$
declare
  k text := upper(coalesce(new.event_key, '')); v_cat text; v_route text; v_module text; v_source text;
  v_profile uuid; v_employee uuid;
begin
  begin
    if k in ('USER_EMAIL', 'EMAIL_SERVER_TEST') or coalesce(new.recipient_email, '') = '' then return new; end if;
    select p.id into v_profile from public.profiles p where p.tenant_id = new.tenant_id and lower(p.email) = lower(btrim(new.recipient_email)) and p.status = 'ACTIVE' limit 1;
    select e.id into v_employee from public.employees e where e.tenant_id = new.tenant_id and lower(e.email) = lower(btrim(new.recipient_email)) limit 1;
    if v_profile is null and v_employee is null then return new; end if;   -- suppliers / customers: e-mail only
    v_cat := case when k like '%APPROVAL%' then 'APPROVAL'
                  when k like '%DIGEST%' then 'INFO'
                  when k like '%PENDING%' or k like '%REQUIRED%' or k like '%OVERDUE%' or k like '%BIENNIAL%' then 'TASK'
                  when k like '%COMPLAINT%' then 'TASK' else 'UPDATE' end;
    v_route := case when k like 'PO\_%' escape '\' then 'supply-po-order-list'
                    when k like 'RM\_PO%' escape '\' or k like 'RM\_%' escape '\' then 'supply-rm-procurement'
                    when k like 'FORGING%' then 'supply-forging'
                    when k like 'CUSTOMER\_ORDER%' escape '\' then 'supply-customer-orders'
                    when k like 'OSP%' then 'osp-home'
                    when k like 'RMTC%' then 'rmtc-approval'
                    when k like 'NPD%' then 'npd-status'
                    when k like '%COMPLAINT%' then 'complaints-home'
                    when k like 'DIMENSIONAL%' then 'dimensional-entry'
                    when k like 'METLAB%' then 'metlab-entry'
                    when k like 'DELETE%' then 'records-center'
                    else 'dashboard' end;
    v_module := case when v_route like 'supply-%' then 'SUPPLY_CHAIN' when v_route like 'osp-%' then 'OSP_TRANSACTIONS'
                     when v_route like 'rmtc-%' then 'RMTC_ENTRY' when v_route like 'npd-%' then 'NPD_APQP'
                     when v_route like 'complaint%' then 'COMPLAINT_MANAGEMENT' when v_route like 'dimensional%' then 'DIMENSIONAL_REPORT'
                     when v_route like 'metlab%' then 'METLAB_REPORT' else null end;
    -- same source keys as the direct triggers, so one event = one notification
    v_source := case
      when k in ('PO_PENDING_APPROVAL', 'PO_APPROVAL_PENDING') and new.related_id is not null then 'PO_APPROVAL:' || new.related_id || ':' || current_date
      when k in ('DIMENSIONAL_APPROVAL_PENDING', 'METLAB_APPROVAL_PENDING') and new.related_id is not null then 'INSP_APPROVAL:' || new.related_id
      when k = 'DELETE_APPROVAL_REQUEST' and new.related_id is not null then 'DEL_REQ:' || new.related_id
      else 'OUTBOX:' || k || ':' || coalesce(new.related_id::text, new.dedupe_key, new.id::text) || ':' || current_date end;
    if k in ('PO_PENDING_APPROVAL', 'PO_APPROVAL_PENDING') then v_route := 'supply-po-approval'; end if;
    perform qcms_private.qcms__add_notification(new.tenant_id, v_profile, v_employee, coalesce(nullif(new.subject, ''), initcap(replace(k, '_', ' '))),
      left(coalesce(new.body_text, ''), 1500), v_cat, v_module, new.related_table, new.related_id, v_route, v_source,
      case when v_cat = 'APPROVAL' then 'HIGH' else 'NORMAL' end, new.created_by);
  exception when others then null;
  end;
  return new;
end $$;
revoke all on function qcms_private.qcms__trg_outbox_to_inapp() from public, anon, authenticated;
create or replace trigger qcms_r35_outbox_to_inapp after insert on public.qcms_notification_outbox
for each row execute function qcms_private.qcms__trg_outbox_to_inapp();

-- =====================================================================================
-- 4) STAWN licensing, company profile
-- =====================================================================================
create table if not exists public.qcms_licence_secret (
  id smallint primary key default 1 check (id = 1),
  secret text not null,
  created_at timestamptz not null default now()
);
alter table public.qcms_licence_secret enable row level security;
revoke all on public.qcms_licence_secret from public, anon, authenticated;
insert into public.qcms_licence_secret (id, secret) values (1, encode(extensions.gen_random_bytes(32), 'hex')) on conflict (id) do nothing;

create table if not exists public.qcms_licences (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  licence_key text not null unique,
  plan text not null default 'STANDARD',
  max_users integer not null default 10 check (max_users > 0),
  modules text[] not null default array['ALL'],
  valid_from date not null default current_date,
  valid_to date,
  status text not null default 'ACTIVE' check (status in ('ACTIVE', 'SUSPENDED', 'REVOKED', 'SUPERSEDED')),
  issued_by uuid,
  issued_at timestamptz not null default now(),
  activated_at timestamptz,
  activated_by uuid,
  last_validated_at timestamptz,
  last_validation jsonb,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists qcms_licences_one_active on public.qcms_licences (tenant_id) where status = 'ACTIVE';
alter table public.qcms_licences enable row level security;
revoke all on public.qcms_licences from anon;
revoke insert, update, delete on public.qcms_licences from authenticated;
grant select on public.qcms_licences to authenticated;
do $pol$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'qcms_licences' and policyname = 'qcms_licences_select') then
    create policy qcms_licences_select on public.qcms_licences for select to authenticated
  using ((tenant_id = public.current_tenant_id() and public.current_app_role() = 'ADMIN') or public.qcms_is_stawn_developer());
  end if;
end $pol$;

create table if not exists public.qcms_company_profiles (
  tenant_id uuid primary key,
  legal_name text,
  display_name text,
  address_line1 text,
  address_line2 text,
  city text,
  state text,
  country text default 'India',
  pincode text,
  gstin text,
  pan text,
  cin text,
  contact_person text,
  contact_email text,
  contact_phone text,
  website text,
  industry text,
  logo_path text,
  setup_complete boolean not null default false,
  completed_at timestamptz,
  completed_by uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  updated_by uuid
);
alter table public.qcms_company_profiles enable row level security;
revoke all on public.qcms_company_profiles from anon;
grant select, insert, update on public.qcms_company_profiles to authenticated;
do $pol$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'qcms_company_profiles' and policyname = 'qcms_company_profiles_select') then
    create policy qcms_company_profiles_select on public.qcms_company_profiles for select to authenticated
  using (tenant_id = public.current_tenant_id() or public.qcms_is_stawn_developer());
  end if;
end $pol$;
do $pol$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'qcms_company_profiles' and policyname = 'qcms_company_profiles_insert') then
    create policy qcms_company_profiles_insert on public.qcms_company_profiles for insert to authenticated
  with check ((tenant_id = public.current_tenant_id() and public.current_app_role() = 'ADMIN') or public.qcms_is_stawn_developer());
  end if;
end $pol$;
do $pol$ begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'qcms_company_profiles' and policyname = 'qcms_company_profiles_update') then
    create policy qcms_company_profiles_update on public.qcms_company_profiles for update to authenticated
  using ((tenant_id = public.current_tenant_id() and public.current_app_role() = 'ADMIN') or public.qcms_is_stawn_developer())
  with check ((tenant_id = public.current_tenant_id() and public.current_app_role() = 'ADMIN') or public.qcms_is_stawn_developer());
  end if;
end $pol$;

-- Key = STAWN-QCMS-AAAAA-BBBBB-CCCCC-DDDDD ; DDDDD = HMAC-SHA256(secret, tenant|AAAAABBBBBCCCCC) checksum.
create or replace function qcms_private.qcms__b32(p_bytes bytea, p_len integer)
returns text language plpgsql immutable set search_path = public as $$
declare alphabet text := '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'; out text := ''; i integer;
begin
  for i in 0 .. p_len - 1 loop
    out := out || substr(alphabet, (get_byte(p_bytes, i % length(p_bytes)) % 32) + 1, 1);
  end loop;
  return out;
end $$;
revoke all on function qcms_private.qcms__b32(bytea, integer) from public, anon, authenticated;

create or replace function qcms_private.qcms__licence_checksum(p_tenant_id uuid, p_body text)
returns text language sql stable security definer set search_path = public, extensions as $$
  select qcms_private.qcms__b32(extensions.hmac(convert_to(p_tenant_id::text || '|' || upper(p_body), 'UTF8'),
                                          convert_to(s.secret, 'UTF8'), 'sha256'), 5)
  from public.qcms_licence_secret s where s.id = 1
$$;
revoke all on function qcms_private.qcms__licence_checksum(uuid, text) from public, anon, authenticated;

create or replace function qcms_private.qcms__new_licence_key(p_tenant_id uuid)
returns text language plpgsql volatile security definer set search_path = public, extensions as $$
declare g1 text; g2 text; g3 text;
begin
  g1 := qcms_private.qcms__b32(extensions.gen_random_bytes(5), 5);
  g2 := qcms_private.qcms__b32(extensions.gen_random_bytes(5), 5);
  g3 := qcms_private.qcms__b32(extensions.gen_random_bytes(5), 5);
  return 'STAWN-QCMS-' || g1 || '-' || g2 || '-' || g3 || '-' || qcms_private.qcms__licence_checksum(p_tenant_id, g1 || g2 || g3);
end $$;
revoke all on function qcms_private.qcms__new_licence_key(uuid) from public, anon, authenticated;

create or replace function qcms_private.qcms__used_seats(p_tenant_id uuid)
returns integer language sql stable security definer set search_path = public as $$
  select count(*)::integer from public.profiles p
  where p.tenant_id = p_tenant_id and p.status = 'ACTIVE'
    and not exists (select 1 from public.qcms_stawn_developers d where d.profile_id = p.id and d.active)
$$;
revoke all on function qcms_private.qcms__used_seats(uuid) from public, anon, authenticated;

-- Core evaluation (no side effects)
create or replace function qcms_private.qcms__licence_eval(p_licence public.qcms_licences)
returns jsonb language plpgsql stable security definer set search_path = public as $$
declare v_body text; v_sum text; v_ok boolean; v_status text; v_grace date; v_used integer;
begin
  if p_licence.id is null then
    return jsonb_build_object('valid', false, 'status', 'NONE', 'reason', 'No STAWN QCMS licence is registered for this company.');
  end if;
  v_body := regexp_replace(upper(p_licence.licence_key), '^STAWN-QCMS-([A-Z0-9]{5})-([A-Z0-9]{5})-([A-Z0-9]{5})-([A-Z0-9]{5})$', '\1\2\3');
  v_sum := right(upper(p_licence.licence_key), 5);
  v_ok := upper(p_licence.licence_key) ~ '^STAWN-QCMS-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}$'
          and v_sum = qcms_private.qcms__licence_checksum(p_licence.tenant_id, v_body);
  v_grace := case when p_licence.valid_to is null then null else p_licence.valid_to + 7 end;
  v_used := qcms_private.qcms__used_seats(p_licence.tenant_id);
  v_status := case
    when not v_ok then 'INVALID'
    when p_licence.status <> 'ACTIVE' then p_licence.status
    when p_licence.valid_from > current_date then 'NOT_STARTED'
    when p_licence.valid_to is null or p_licence.valid_to >= current_date then 'ACTIVE'
    when v_grace >= current_date then 'GRACE'
    else 'EXPIRED' end;
  return jsonb_build_object(
    'valid', v_status in ('ACTIVE', 'GRACE'), 'status', v_status,
    'reason', case v_status when 'ACTIVE' then 'Licence valid' when 'GRACE' then 'Licence expired on ' || to_char(p_licence.valid_to, 'DD-MM-YYYY') || ' – 7-day grace period until ' || to_char(v_grace, 'DD-MM-YYYY')
              when 'EXPIRED' then 'Licence expired on ' || to_char(p_licence.valid_to, 'DD-MM-YYYY') when 'INVALID' then 'Licence key failed the STAWN signature check'
              when 'NOT_STARTED' then 'Licence starts on ' || to_char(p_licence.valid_from, 'DD-MM-YYYY') else 'Licence is ' || lower(v_status) end,
    'plan', p_licence.plan, 'max_users', p_licence.max_users, 'used_users', v_used, 'modules', to_jsonb(p_licence.modules),
    'valid_from', p_licence.valid_from, 'expires_on', p_licence.valid_to, 'grace_until', v_grace,
    'licence_key_masked', 'STAWN-QCMS-•••••-•••••-•••••-' || right(p_licence.licence_key, 5),
    'licence_id', p_licence.id, 'last_validated_at', p_licence.last_validated_at);
end $$;
revoke all on function qcms_private.qcms__licence_eval(public.qcms_licences) from public, anon, authenticated;

create or replace function public.qcms_validate_licence(p_key text)
returns jsonb language plpgsql security definer set search_path = public, auth as $$
declare v_key text := upper(regexp_replace(coalesce(p_key, ''), '\s', '', 'g')); l public.qcms_licences; res jsonb;
begin
  if auth.uid() is null then raise exception 'Authenticated QCMS session required'; end if;
  select * into l from public.qcms_licences where licence_key = v_key;
  if l.id is null then
    return jsonb_build_object('valid', false, 'status', 'UNKNOWN', 'reason', 'This licence key is not issued by STAWN PRECISION PRIVATE LIMITED.');
  end if;
  if l.tenant_id is distinct from public.current_tenant_id() and not public.qcms_is_stawn_developer() then
    return jsonb_build_object('valid', false, 'status', 'OTHER_COMPANY', 'reason', 'This licence key belongs to another company.');
  end if;
  res := qcms_private.qcms__licence_eval(l) || jsonb_build_object('validated_online', true, 'validated_at', now());
  update public.qcms_licences set last_validated_at = now(), last_validation = res where id = l.id;
  return res;
end $$;
revoke all on function public.qcms_validate_licence(text) from public, anon;
grant execute on function public.qcms_validate_licence(text) to authenticated;

-- Company admin activates the key issued by STAWN for their company
create or replace function public.qcms_activate_licence(p_key text)
returns jsonb language plpgsql security definer set search_path = public, auth as $$
declare v_key text := upper(regexp_replace(coalesce(p_key, ''), '\s', '', 'g')); l public.qcms_licences; res jsonb;
begin
  if auth.uid() is null then raise exception 'Authenticated QCMS session required'; end if;
  if coalesce(public.current_app_role(), '') <> 'ADMIN' and not public.qcms_is_stawn_developer() then
    raise exception 'Only the company administrator can activate the STAWN QCMS licence';
  end if;
  res := public.qcms_validate_licence(v_key);
  if not coalesce((res->>'valid')::boolean, false) then return res; end if;
  select * into l from public.qcms_licences where licence_key = v_key;
  if l.status = 'SUPERSEDED' then return res; end if;
  update public.qcms_licences set activated_at = coalesce(activated_at, now()), activated_by = coalesce(activated_by, auth.uid()), updated_at = now() where id = l.id;
  return res || jsonb_build_object('activated', true);
end $$;
revoke all on function public.qcms_activate_licence(text) from public, anon;
grant execute on function public.qcms_activate_licence(text) to authenticated;

create or replace function public.qcms_licence_status()
returns jsonb language plpgsql security definer set search_path = public, auth as $$
declare tid uuid := public.current_tenant_id(); l public.qcms_licences; ev jsonb; cp public.qcms_company_profiles; t public.tenants;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  select * into l from public.qcms_licences where tenant_id = tid and status = 'ACTIVE' limit 1;
  if l.id is null then
    select * into l from public.qcms_licences where tenant_id = tid order by issued_at desc limit 1;
  end if;
  ev := qcms_private.qcms__licence_eval(l);
  if l.id is not null and (l.last_validated_at is null or l.last_validated_at < now() - interval '1 hour') then
    update public.qcms_licences set last_validated_at = now(), last_validation = ev where id = l.id;
  end if;
  select * into cp from public.qcms_company_profiles where tenant_id = tid;
  select * into t from public.tenants where id = tid;
  return ev || jsonb_build_object(
    'product', 'STAWN QCMS',
    'company_name', coalesce(nullif(cp.display_name, ''), nullif(cp.legal_name, ''), t.tenant_name),
    'company_legal_name', coalesce(nullif(cp.legal_name, ''), t.tenant_name),
    'company_logo_path', cp.logo_path,
    'tenant_id', tid, 'tenant_code', t.tenant_code,
    'is_stawn_developer', public.qcms_is_stawn_developer(),
    'is_company_admin', coalesce(public.current_app_role(), '') = 'ADMIN',
    'setup_complete', coalesce(cp.setup_complete, false),
    'used_users', qcms_private.qcms__used_seats(tid),
    'developer', jsonb_build_object('name', 'STAWN PRECISION PRIVATE LIMITED', 'location', 'Thane, Maharashtra, India',
       'email', 'business@stawnprecision.com', 'website', 'https://stawnprecision.com'));
end $$;
revoke all on function public.qcms_licence_status() from public, anon;
grant execute on function public.qcms_licence_status() to authenticated;

-- ---------- STAWN developer console RPCs ----------
create or replace function qcms_private.qcms__require_developer()
returns void language plpgsql stable security definer set search_path = public, auth as $$
begin
  if not public.qcms_is_stawn_developer() then raise exception 'STAWN developer login required'; end if;
end $$;
revoke all on function qcms_private.qcms__require_developer() from public, anon, authenticated;

create or replace function public.qcms_dev_issue_licence(p_tenant_id uuid, p_plan text default 'STANDARD', p_max_users integer default 10,
  p_valid_to date default null, p_modules text[] default array['ALL'], p_notes text default null, p_valid_from date default current_date)
returns jsonb language plpgsql security definer set search_path = public, auth as $$
declare v_key text; v_id uuid;
begin
  perform qcms_private.qcms__require_developer();
  if not exists (select 1 from public.tenants where id = p_tenant_id) then raise exception 'Company (tenant) not found'; end if;
  update public.qcms_licences set status = 'SUPERSEDED', updated_at = now() where tenant_id = p_tenant_id and status = 'ACTIVE';
  v_key := qcms_private.qcms__new_licence_key(p_tenant_id);
  insert into public.qcms_licences (tenant_id, licence_key, plan, max_users, modules, valid_from, valid_to, status, issued_by, notes)
  values (p_tenant_id, v_key, upper(coalesce(nullif(p_plan, ''), 'STANDARD')), greatest(1, coalesce(p_max_users, 10)),
          coalesce(p_modules, array['ALL']), coalesce(p_valid_from, current_date), p_valid_to, 'ACTIVE', auth.uid(), p_notes)
  returning id into v_id;
  return jsonb_build_object('licence_id', v_id, 'licence_key', v_key);
end $$;
revoke all on function public.qcms_dev_issue_licence(uuid,text,integer,date,text[],text,date) from public, anon;
grant execute on function public.qcms_dev_issue_licence(uuid,text,integer,date,text[],text,date) to authenticated;

create or replace function public.qcms_dev_update_licence(p_licence_id uuid, p_status text default null, p_max_users integer default null,
  p_valid_to date default null, p_clear_valid_to boolean default false, p_plan text default null, p_modules text[] default null, p_notes text default null)
returns jsonb language plpgsql security definer set search_path = public, auth as $$
declare l public.qcms_licences;
begin
  perform qcms_private.qcms__require_developer();
  if p_status is not null and upper(p_status) not in ('ACTIVE', 'SUSPENDED', 'REVOKED') then raise exception 'Unknown licence status %', p_status; end if;
  update public.qcms_licences set
    status = coalesce(upper(p_status), status), max_users = coalesce(p_max_users, max_users),
    valid_to = case when p_clear_valid_to then null else coalesce(p_valid_to, valid_to) end,
    plan = coalesce(upper(nullif(p_plan, '')), plan), modules = coalesce(p_modules, modules), notes = coalesce(p_notes, notes), updated_at = now()
  where id = p_licence_id returning * into l;
  if l.id is null then raise exception 'Licence not found'; end if;
  return qcms_private.qcms__licence_eval(l);
end $$;
revoke all on function public.qcms_dev_update_licence(uuid,text,integer,date,boolean,text,text[],text) from public, anon;
grant execute on function public.qcms_dev_update_licence(uuid,text,integer,date,boolean,text,text[],text) to authenticated;

create or replace function public.qcms_dev_licence_overview()
returns table (tenant_id uuid, tenant_code text, company_name text, licence_id uuid, licence_key text, plan text, status text,
  evaluated_status text, valid_to date, max_users integer, used_users integer, last_validated_at timestamptz, setup_complete boolean)
language plpgsql stable security definer set search_path = public, auth as $$
begin
  perform qcms_private.qcms__require_developer();
  return query
  select t.id, t.tenant_code, coalesce(cp.display_name, cp.legal_name, t.tenant_name), l.id, l.licence_key, l.plan, l.status,
         (qcms_private.qcms__licence_eval(l))->>'status', l.valid_to, l.max_users, qcms_private.qcms__used_seats(t.id), l.last_validated_at,
         coalesce(cp.setup_complete, false)
  from public.tenants t
  left join lateral (select x.* from public.qcms_licences x where x.tenant_id = t.id order by (x.status = 'ACTIVE') desc, x.issued_at desc limit 1) l on true
  left join public.qcms_company_profiles cp on cp.tenant_id = t.id
  order by t.tenant_name;
end $$;
revoke all on function public.qcms_dev_licence_overview() from public, anon;
grant execute on function public.qcms_dev_licence_overview() to authenticated;

create or replace function public.qcms_dev_create_company(p_tenant_code text, p_tenant_name text, p_plant_code text default null)
returns uuid language plpgsql security definer set search_path = public, auth as $$
declare v_id uuid;
begin
  perform qcms_private.qcms__require_developer();
  if coalesce(btrim(p_tenant_code), '') = '' or coalesce(btrim(p_tenant_name), '') = '' then raise exception 'Company code and name are required'; end if;
  insert into public.tenants (tenant_code, tenant_name, plant_code, status)
  values (upper(btrim(p_tenant_code)), btrim(p_tenant_name), nullif(btrim(coalesce(p_plant_code, '')), ''), 'ACTIVE') returning id into v_id;
  insert into public.qcms_company_profiles (tenant_id, legal_name, display_name) values (v_id, btrim(p_tenant_name), btrim(p_tenant_name))
  on conflict (tenant_id) do nothing;
  return v_id;
end $$;
revoke all on function public.qcms_dev_create_company(text, text, text) from public, anon;
grant execute on function public.qcms_dev_create_company(text, text, text) to authenticated;

-- Move an existing login (created in Users & Access / sign-up) into a licensed company as its administrator
create or replace function public.protect_profile_privileges()
returns trigger language plpgsql security definer set search_path = public, auth as $$
declare actor_id uuid:=auth.uid(); actor_role text;
begin
  if actor_id is null then return new; end if;
  if current_setting('qcms.dev_profile_move', true) = 'true' and public.qcms_is_stawn_developer() then return new; end if;
  if current_setting('qsms.bootstrap_authorized',true)='true' and actor_id=old.id and old.role='VIEWER' and new.role='ADMIN' then
    new.tenant_id:=old.tenant_id; new.status:='ACTIVE'; return new;
  end if;
  actor_role:=public.current_app_role();
  if actor_role='ADMIN' then new.tenant_id:=old.tenant_id; return new; end if;
  if actor_id<>old.id then raise exception 'Only an administrator can update another user profile'; end if;
  new.tenant_id:=old.tenant_id; new.role:=old.role; new.status:=old.status;
  return new;
end; $$;

create or replace function public.qcms_dev_assign_profile(p_email text, p_tenant_id uuid, p_role text default 'ADMIN')
returns jsonb language plpgsql security definer set search_path = public, auth as $$
declare v_id uuid;
begin
  perform qcms_private.qcms__require_developer();
  if not exists (select 1 from public.tenants where id = p_tenant_id) then raise exception 'Company (tenant) not found'; end if;
  select id into v_id from public.profiles where lower(email) = lower(btrim(p_email));
  if v_id is null then raise exception 'No QCMS login exists for %. Create the login first (Admin → Users & Access).', p_email; end if;
  perform set_config('qcms.dev_profile_move', 'true', true);
  update public.profiles set tenant_id = p_tenant_id, role = upper(coalesce(nullif(p_role, ''), 'ADMIN')), status = 'ACTIVE', updated_at = now() where id = v_id;
  perform set_config('qcms.dev_profile_move', 'false', true);
  return jsonb_build_object('profile_id', v_id, 'tenant_id', p_tenant_id, 'role', upper(coalesce(nullif(p_role, ''), 'ADMIN')));
end $$;
revoke all on function public.qcms_dev_assign_profile(text, uuid, text) from public, anon;
grant execute on function public.qcms_dev_assign_profile(text, uuid, text) to authenticated;

-- Licence seat limit: a new ACTIVE login beyond the licensed users is refused (STAWN developers are not counted).
create or replace function qcms_private.qcms__trg_licence_seat_limit()
returns trigger language plpgsql security definer set search_path = public, auth as $$
declare v_max integer; v_used integer;
begin
  if new.status is distinct from 'ACTIVE' then return new; end if;
  if tg_op = 'UPDATE' and old.status = 'ACTIVE' and old.tenant_id = new.tenant_id then return new; end if;
  if tg_op = 'INSERT' and exists (select 1 from public.profiles p where p.id = new.id) then return new; end if;  -- upsert of an existing login
  if exists (select 1 from public.qcms_stawn_developers d where d.profile_id = new.id and d.active) then return new; end if;
  select l.max_users into v_max from public.qcms_licences l where l.tenant_id = new.tenant_id and l.status = 'ACTIVE' limit 1;
  if v_max is null then return new; end if;
  select qcms_private.qcms__used_seats(new.tenant_id) into v_used;
  if v_used >= v_max then
    raise exception 'STAWN QCMS licence limit reached: % of % licensed users are active. Deactivate a user or ask STAWN PRECISION PRIVATE LIMITED for more users.', v_used, v_max;
  end if;
  return new;
end $$;
revoke all on function qcms_private.qcms__trg_licence_seat_limit() from public, anon, authenticated;
create or replace trigger qcms_r35_licence_seat_limit before insert or update of status, tenant_id on public.profiles
for each row execute function qcms_private.qcms__trg_licence_seat_limit();

-- Seed: Four Star Industries keeps working (active ENTERPRISE licence, no expiry) + company profile row.
insert into public.qcms_company_profiles (tenant_id, legal_name, display_name)
select t.id, t.tenant_name, t.tenant_name from public.tenants t
where t.id = '00000000-0000-0000-0000-000000000001'::uuid
on conflict (tenant_id) do nothing;

do $$
declare v_tid uuid := '00000000-0000-0000-0000-000000000001'::uuid; v_max integer;
begin
  if exists (select 1 from public.tenants where id = v_tid)
     and not exists (select 1 from public.qcms_licences where tenant_id = v_tid) then
    select greatest(50, qcms_private.qcms__used_seats(v_tid) + 10) into v_max;
    insert into public.qcms_licences (tenant_id, licence_key, plan, max_users, modules, valid_from, valid_to, status, notes, activated_at)
    values (v_tid, qcms_private.qcms__new_licence_key(v_tid), 'ENTERPRISE', v_max, array['ALL'], date '2026-01-01', null, 'ACTIVE',
            'R35 seed: Four Star Industries Pvt. Ltd. enterprise licence (no expiry).', now());
  end if;
end $$;

-- =====================================================================================
-- 5) Scheduler: push + WhatsApp dispatch every 2 minutes (same pattern as the other QCMS notifiers)
-- =====================================================================================
do $$
begin
  if exists (select 1 from pg_extension where extname = 'pg_cron') and exists (select 1 from pg_extension where extname = 'pg_net')
     and exists (select 1 from vault.decrypted_secrets where name = 'qcms_project_url')
     and exists (select 1 from vault.decrypted_secrets where name = 'qcms_notification_scheduler_token') then
    perform cron.schedule('qcms-push-dispatch-2min', '*/2 * * * *', $cmd$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name='qcms_project_url' order by created_at desc limit 1) || '/functions/v1/qcms-push-dispatch',
    headers := jsonb_build_object('Content-Type','application/json',
      'X-QCMS-Scheduler',(select decrypted_secret from vault.decrypted_secrets where name='qcms_notification_scheduler_token' order by created_at desc limit 1)),
    body := jsonb_build_object('source','supabase_cron','requested_at',now()),
    timeout_milliseconds := 15000) as request_id;
  $cmd$);
    perform cron.schedule('qcms-whatsapp-dispatch-2min', '*/2 * * * *', $cmd$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name='qcms_project_url' order by created_at desc limit 1) || '/functions/v1/qcms-whatsapp-dispatch',
    headers := jsonb_build_object('Content-Type','application/json',
      'X-QCMS-Scheduler',(select decrypted_secret from vault.decrypted_secrets where name='qcms_notification_scheduler_token' order by created_at desc limit 1)),
    body := jsonb_build_object('source','supabase_cron','requested_at',now()),
    timeout_milliseconds := 15000) as request_id;
  $cmd$);
  end if;
end $$;
