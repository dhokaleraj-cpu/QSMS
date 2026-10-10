-- QCMS 4.14.49 R14 · Personal Microsoft 365 email (send to employees / departments / groups)
-- Security model:
--   qcms_user_mail_accounts : OWNER-ONLY. Only the signed-in user (auth.uid()) can read,
--                             write or delete their own row. There is deliberately NO
--                             admin / tenant policy, so administrators cannot read it
--                             through the app or the Data API. The refresh token is
--                             additionally encrypted by the app before it is stored.
--   qcms_mail_groups        : readable by everyone in the company (tenant); editable by
--                             the creator or a QCMS ADMIN.
--   qcms_mail_sent_log      : OWNER-ONLY sent-items log (metadata only, no body).

create table if not exists public.qcms_user_mail_accounts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  provider text not null default 'MS365' check (provider in ('MS365')),
  mailbox_email text not null,
  display_name text,
  encrypted_refresh_token text not null,
  token_scope text,
  connected_at timestamptz not null default now(),
  last_used_at timestamptz,
  updated_at timestamptz not null default now(),
  unique (user_id)
);
alter table public.qcms_user_mail_accounts enable row level security;
alter table public.qcms_user_mail_accounts force row level security;
revoke all on public.qcms_user_mail_accounts from anon;
grant select, insert, update, delete on public.qcms_user_mail_accounts to authenticated;
drop policy if exists owner_select on public.qcms_user_mail_accounts;
create policy owner_select on public.qcms_user_mail_accounts for select to authenticated using (user_id = auth.uid());
drop policy if exists owner_insert on public.qcms_user_mail_accounts;
create policy owner_insert on public.qcms_user_mail_accounts for insert to authenticated with check (user_id = auth.uid() and tenant_id = public.current_tenant_id());
drop policy if exists owner_update on public.qcms_user_mail_accounts;
create policy owner_update on public.qcms_user_mail_accounts for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid() and tenant_id = public.current_tenant_id());
drop policy if exists owner_delete on public.qcms_user_mail_accounts;
create policy owner_delete on public.qcms_user_mail_accounts for delete to authenticated using (user_id = auth.uid());

create table if not exists public.qcms_mail_groups (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  group_name text not null,
  description text,
  member_employee_ids uuid[] not null default '{}',
  extra_emails text[] not null default '{}',
  status text not null default 'ACTIVE' check (status in ('ACTIVE','INACTIVE')),
  created_by uuid not null default auth.uid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists qcms_mail_groups_name_uq on public.qcms_mail_groups (tenant_id, lower(btrim(group_name)));
alter table public.qcms_mail_groups enable row level security;
revoke all on public.qcms_mail_groups from anon;
grant select, insert, update, delete on public.qcms_mail_groups to authenticated;
drop policy if exists tenant_select on public.qcms_mail_groups;
create policy tenant_select on public.qcms_mail_groups for select to authenticated using (tenant_id = public.current_tenant_id());
drop policy if exists tenant_insert on public.qcms_mail_groups;
create policy tenant_insert on public.qcms_mail_groups for insert to authenticated with check (tenant_id = public.current_tenant_id() and created_by = auth.uid());
drop policy if exists owner_or_admin_update on public.qcms_mail_groups;
create policy owner_or_admin_update on public.qcms_mail_groups for update to authenticated
  using (tenant_id = public.current_tenant_id() and (created_by = auth.uid() or exists (select 1 from public.profiles p where p.id = auth.uid() and upper(p.role) = 'ADMIN')))
  with check (tenant_id = public.current_tenant_id());
drop policy if exists owner_or_admin_delete on public.qcms_mail_groups;
create policy owner_or_admin_delete on public.qcms_mail_groups for delete to authenticated
  using (tenant_id = public.current_tenant_id() and (created_by = auth.uid() or exists (select 1 from public.profiles p where p.id = auth.uid() and upper(p.role) = 'ADMIN')));

create table if not exists public.qcms_mail_sent_log (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  sender_user_id uuid not null default auth.uid(),
  sender_email text not null,
  subject text,
  recipient_count integer not null default 0,
  recipient_summary text,
  message_count integer not null default 1,
  status text not null check (status in ('SENT','FAILED','PARTIAL')),
  error_text text,
  sent_at timestamptz not null default now()
);
alter table public.qcms_mail_sent_log enable row level security;
revoke all on public.qcms_mail_sent_log from anon;
grant select, insert on public.qcms_mail_sent_log to authenticated;
drop policy if exists owner_select on public.qcms_mail_sent_log;
create policy owner_select on public.qcms_mail_sent_log for select to authenticated using (sender_user_id = auth.uid());
drop policy if exists owner_insert on public.qcms_mail_sent_log;
create policy owner_insert on public.qcms_mail_sent_log for insert to authenticated with check (sender_user_id = auth.uid() and tenant_id = public.current_tenant_id());
create index if not exists qcms_mail_sent_log_sender_idx on public.qcms_mail_sent_log (sender_user_id, sent_at desc);
-- QCMS R15 · Separate Bend Test Layout Master.
-- A Bend Test layout (inspection_method = 'BEND_TEST') is its own controlled scope, so a Part can
-- have one current Bend Test layout AND one current general MetLAB layout for the same
-- Part + Stage + Process + Layout Type. Re-runnable.
alter table public.inspection_plans add column if not exists inspection_method text not null default 'GENERAL';

-- Mark existing layouts that are already Bend Test layouts (plan number / name / title says BEND).
update public.inspection_plans
   set inspection_method = 'BEND_TEST', updated_at = now()
 where upper(coalesce(layout_type,'')) = 'METLAB'
   and upper(coalesce(inspection_method,'GENERAL')) <> 'BEND_TEST'
   and (upper(coalesce(plan_number,'')) like '%-BEND%' or upper(coalesce(layout_name,'')) like '%BEND TEST%' or upper(coalesce(report_title,'')) like '%BEND TEST%');

drop index if exists public.uq_qcms_inspection_plan_current_scope;
create unique index uq_qcms_inspection_plan_current_scope
  on public.inspection_plans(
    tenant_id,
    part_id,
    coalesce(process_id,'00000000-0000-0000-0000-000000000000'::uuid),
    coalesce(inspection_stage_id,'00000000-0000-0000-0000-000000000000'::uuid),
    upper(coalesce(layout_type,'DIMENSIONAL')),
    upper(coalesce(inward_type,'MATERIAL_INWARD')),
    upper(coalesce(requirement_scope,'GENERAL')),
    (case when upper(coalesce(inspection_method,'GENERAL')) = 'BEND_TEST' then 'BEND_TEST' else 'GENERAL' end)
  )
  where upper(coalesce(status,'DRAFT')) in ('DRAFT','APPROVAL_PENDING','APPROVED')
    and upper(coalesce(requirement_scope,'GENERAL')) <> 'FINAL_METALLURGICAL';

comment on index public.uq_qcms_inspection_plan_current_scope is
  'QCMS R15 one current layout per Part + Stage + Process + Layout Type + Inward Type + Requirement Scope + Inspection Method (Bend Test separate from general MetLAB).';
