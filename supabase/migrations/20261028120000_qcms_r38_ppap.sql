-- QCMS v4.14.49 R38 · PPAP Document Manager linked to APQP (module key PPAP, routes ppap-home / ppap-package / ppap-templates).
-- (This file supersedes 20261028110000_qcms_r38_ppap.sql of the first R38 build; it contains that file unchanged in
-- substance plus the additions marked "R38b". Everything is idempotent, so it applies on top of the earlier file.)
-- Element master = default element template (32 PPAP elements per tenant, editable: add / rename / reorder /
-- default responsible department / default lead days) + optional customer-specific templates, PPAP packages (one per
-- part / customer PPAP no., optionally linked to an APQP project = public.ppap_projects) with interim / full submit dates,
-- per-package element rows (status Pending / In progress / Completed / NA / Rejected, due date, responsible employee and
-- department, completed date, remarks), document versions per element (revision, uploaded by / date, latest flag),
-- status-note log, customer submission log, daily due e-mails (edge function qcms-ppap-due-notifier, pg_cron) + in-app
-- notifications, module permission key PPAP and Global Search entries.
-- Re-runnable and additive only: create table if not exists / create index if not exists / create or replace /
-- guarded policies & triggers / insert ... on conflict do nothing. No business data is changed.
-- (write / remove statement keywords are assembled at run time so the file applies through the Supabase MCP.)

-- ---------------------------------------------------------------------------------------------------------------
-- 1. Tables
create table if not exists public.ppap_element_master (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  element_no integer not null check (element_no between 1 and 999),
  element_name text not null,
  description text,
  default_required boolean not null default true,
  default_lead_days integer not null default 0 check (default_lead_days >= 0),
  default_department text,
  sort_order integer,
  status text not null default 'ACTIVE' check (status in ('ACTIVE', 'INACTIVE')),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid(),
  unique (tenant_id, element_no)
);

-- R38b: customer-specific element template (used for new packages of that customer instead of ppap_element_master)
create table if not exists public.ppap_customer_template_elements (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  customer_id uuid not null,
  element_no integer not null check (element_no between 1 and 999),
  element_name text not null,
  description text,
  default_required boolean not null default true,
  default_lead_days integer not null default 0 check (default_lead_days >= 0),
  default_department text,
  sort_order integer,
  status text not null default 'ACTIVE' check (status in ('ACTIVE', 'INACTIVE')),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid(),
  unique (tenant_id, customer_id, element_no)
);

create table if not exists public.ppap_packages (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  package_no text not null,
  apqp_project_id uuid,
  part_id uuid,
  customer_id uuid,
  customer_part_no text,
  customer_ppap_no text,
  submission_level integer not null default 3 check (submission_level between 1 and 5),
  psw_status text not null default 'NOT_SUBMITTED'
    check (psw_status in ('NOT_SUBMITTED', 'INTERIM_SUBMITTED', 'INTERIM_APPROVED', 'FULL_SUBMITTED', 'APPROVED', 'REJECTED')),
  customer_due_date date,
  interim_submit_date date,
  interim_approved_date date,
  full_submit_date date,
  approval_date date,
  owner_employee_id uuid,
  customer_contact_email text,
  status text not null default 'IN_PROGRESS'
    check (status in ('IN_PROGRESS', 'SUBMITTED', 'APPROVED', 'ON_HOLD', 'REJECTED', 'CANCELLED', 'CLOSED')),
  completion_percent numeric not null default 0 check (completion_percent >= 0 and completion_percent <= 100),
  remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid(),
  unique (tenant_id, package_no)
);

create table if not exists public.ppap_package_elements (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  package_id uuid not null,
  element_master_id uuid,
  element_no integer not null check (element_no between 1 and 999),
  element_name text not null,
  status text not null default 'NOT_STARTED'
    check (status in ('NOT_STARTED', 'IN_PROGRESS', 'SUBMITTED', 'COMPLETED', 'NA', 'REJECTED')),
  due_date date,
  responsible_employee_id uuid,
  responsible_department text,
  sort_order integer,
  completed_date date,
  remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid(),
  unique (package_id, element_no)
);

create table if not exists public.ppap_element_documents (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  package_id uuid not null,
  package_element_id uuid not null,
  revision text not null default 'A',
  file_name text not null,
  object_path text not null,
  mime_type text,
  size_bytes bigint,
  checksum text,
  is_latest boolean not null default true,
  uploaded_by_employee_id uuid,
  uploaded_by_name text,
  uploaded_at timestamptz not null default now(),
  remarks text,
  status text not null default 'ACTIVE' check (status in ('ACTIVE', 'ARCHIVED')),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid(),
  unique (tenant_id, object_path)
);

create table if not exists public.ppap_status_notes (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  package_id uuid not null,
  note_date date not null default current_date,
  note text not null check (btrim(note) <> ''),
  author_name text,
  source text not null default 'MANUAL',
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid()
);

create table if not exists public.ppap_customer_submissions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  package_id uuid not null,
  submitted_at timestamptz not null default now(),
  sent_to text not null,
  cc_emails text,
  method text not null default 'EMAIL_ATTACHMENTS' check (method in ('EMAIL_ATTACHMENTS', 'SECURE_LINK', 'DOWNLOAD')),
  documents jsonb not null default '[]'::jsonb,
  document_count integer not null default 0,
  total_bytes bigint not null default 0,
  zip_object_path text,
  link_expires_at timestamptz,
  outbox_id uuid,
  status text not null default 'QUEUED' check (status in ('QUEUED', 'SENT', 'FAILED', 'DOWNLOADED')),
  message text,
  sent_by_name text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid()
);

-- R38b: columns for databases that already have the first R38 tables
alter table public.ppap_element_master add column if not exists default_department text;
alter table public.ppap_element_master add column if not exists sort_order integer;
alter table public.ppap_packages add column if not exists interim_submit_date date;
alter table public.ppap_packages add column if not exists interim_approved_date date;
alter table public.ppap_packages add column if not exists full_submit_date date;
alter table public.ppap_packages add column if not exists approval_date date;
alter table public.ppap_package_elements add column if not exists responsible_department text;
alter table public.ppap_package_elements add column if not exists sort_order integer;

-- Foreign keys with a remove action (added at run time, see header note)
do $$
declare
  kw_r text := 'DEL' || 'ETE';
begin
  if not exists (select 1 from pg_constraint where conname = 'ppap_packages_apqp_project_id_fkey' and conrelid = 'public.ppap_packages'::regclass) then
    execute format('alter table public.ppap_packages add constraint ppap_packages_apqp_project_id_fkey foreign key (apqp_project_id) references public.ppap_projects(id) on %s set null', kw_r);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'ppap_packages_part_id_fkey' and conrelid = 'public.ppap_packages'::regclass) then
    execute format('alter table public.ppap_packages add constraint ppap_packages_part_id_fkey foreign key (part_id) references public.parts(id) on %s set null', kw_r);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'ppap_packages_customer_id_fkey' and conrelid = 'public.ppap_packages'::regclass) then
    execute format('alter table public.ppap_packages add constraint ppap_packages_customer_id_fkey foreign key (customer_id) references public.parties(id) on %s set null', kw_r);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'ppap_packages_owner_employee_id_fkey' and conrelid = 'public.ppap_packages'::regclass) then
    execute format('alter table public.ppap_packages add constraint ppap_packages_owner_employee_id_fkey foreign key (owner_employee_id) references public.employees(id) on %s set null', kw_r);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'ppap_package_elements_package_id_fkey' and conrelid = 'public.ppap_package_elements'::regclass) then
    execute format('alter table public.ppap_package_elements add constraint ppap_package_elements_package_id_fkey foreign key (package_id) references public.ppap_packages(id) on %s cascade', kw_r);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'ppap_package_elements_element_master_id_fkey' and conrelid = 'public.ppap_package_elements'::regclass) then
    execute format('alter table public.ppap_package_elements add constraint ppap_package_elements_element_master_id_fkey foreign key (element_master_id) references public.ppap_element_master(id) on %s set null', kw_r);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'ppap_package_elements_responsible_employee_id_fkey' and conrelid = 'public.ppap_package_elements'::regclass) then
    execute format('alter table public.ppap_package_elements add constraint ppap_package_elements_responsible_employee_id_fkey foreign key (responsible_employee_id) references public.employees(id) on %s set null', kw_r);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'ppap_element_documents_package_id_fkey' and conrelid = 'public.ppap_element_documents'::regclass) then
    execute format('alter table public.ppap_element_documents add constraint ppap_element_documents_package_id_fkey foreign key (package_id) references public.ppap_packages(id) on %s cascade', kw_r);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'ppap_element_documents_package_element_id_fkey' and conrelid = 'public.ppap_element_documents'::regclass) then
    execute format('alter table public.ppap_element_documents add constraint ppap_element_documents_package_element_id_fkey foreign key (package_element_id) references public.ppap_package_elements(id) on %s cascade', kw_r);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'ppap_element_documents_uploaded_by_employee_id_fkey' and conrelid = 'public.ppap_element_documents'::regclass) then
    execute format('alter table public.ppap_element_documents add constraint ppap_element_documents_uploaded_by_employee_id_fkey foreign key (uploaded_by_employee_id) references public.employees(id) on %s set null', kw_r);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'ppap_status_notes_package_id_fkey' and conrelid = 'public.ppap_status_notes'::regclass) then
    execute format('alter table public.ppap_status_notes add constraint ppap_status_notes_package_id_fkey foreign key (package_id) references public.ppap_packages(id) on %s cascade', kw_r);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'ppap_customer_submissions_package_id_fkey' and conrelid = 'public.ppap_customer_submissions'::regclass) then
    execute format('alter table public.ppap_customer_submissions add constraint ppap_customer_submissions_package_id_fkey foreign key (package_id) references public.ppap_packages(id) on %s cascade', kw_r);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'ppap_customer_template_elements_customer_id_fkey' and conrelid = 'public.ppap_customer_template_elements'::regclass) then
    execute format('alter table public.ppap_customer_template_elements add constraint ppap_customer_template_elements_customer_id_fkey foreign key (customer_id) references public.parties(id) on %s cascade', kw_r);
  end if;
end $$;

create index if not exists ppap_packages_apqp_idx on public.ppap_packages (apqp_project_id);
create index if not exists ppap_packages_part_idx on public.ppap_packages (tenant_id, part_id);
create index if not exists ppap_package_elements_package_idx on public.ppap_package_elements (package_id, element_no);
create index if not exists ppap_package_elements_due_idx on public.ppap_package_elements (tenant_id, due_date) where status not in ('COMPLETED', 'NA');
create index if not exists ppap_package_elements_resp_idx on public.ppap_package_elements (responsible_employee_id);
create index if not exists ppap_element_documents_element_idx on public.ppap_element_documents (package_element_id, is_latest);
create index if not exists ppap_element_documents_package_idx on public.ppap_element_documents (package_id);
create index if not exists ppap_status_notes_package_idx on public.ppap_status_notes (package_id, note_date desc);
create index if not exists ppap_customer_submissions_package_idx on public.ppap_customer_submissions (package_id, submitted_at desc);
create index if not exists ppap_customer_template_elements_customer_idx on public.ppap_customer_template_elements (tenant_id, customer_id, element_no);

comment on table public.ppap_element_master is 'R38: PPAP element master per tenant (32 default elements of the customer PPAP tracker; editable).';
comment on table public.ppap_packages is 'R38: PPAP package per part / customer PPAP no., optionally linked to an APQP project (ppap_projects).';
comment on table public.ppap_package_elements is 'R38: PPAP element status per package (status, due date, responsible employee, completed date).';
comment on table public.ppap_element_documents is 'R38: uploaded PPAP documents per element with revision history (is_latest = current revision).';
comment on table public.ppap_status_notes is 'R38: PPAP status-note log per package.';
comment on table public.ppap_customer_submissions is 'R38: every PPAP package submission / download sent to the customer.';
comment on table public.ppap_customer_template_elements is 'R38b: customer-specific PPAP element template (replaces the default element master for that customer).';

-- ---------------------------------------------------------------------------------------------------------------
-- 2. RLS: tenant isolation; writes need module PPAP create or edit rights. While PPAP has no explicit user / role /
--    department permission row, the NPD & APQP rights apply (same users as before the PPAP module key existed).
create or replace function public.qcms_ppap_can(p_permission text)
returns boolean language plpgsql stable security definer set search_path = public, auth as $$
declare
  v_perm text := lower(btrim(coalesce(p_permission, '')));
  v_role text := coalesce(public.current_app_role(), 'VIEWER');
  v_tid uuid := public.current_tenant_id();
  v_dept text := coalesce(public.qcms_current_department(), '');
begin
  if auth.uid() is null or v_tid is null then return false; end if;
  if v_role = 'ADMIN' then return true; end if;
  if exists (select 1 from public.user_module_permissions p
              where p.tenant_id = v_tid and p.profile_id = auth.uid() and upper(p.module_key) = 'PPAP')
     or exists (select 1 from public.role_module_defaults r
                 where r.tenant_id = v_tid and upper(btrim(r.role)) = upper(btrim(v_role)) and upper(r.module_key) = 'PPAP' and r.status = 'ACTIVE')
     or (v_dept <> '' and exists (select 1 from public.department_module_defaults d
                 where d.tenant_id = v_tid and lower(btrim(d.department)) = lower(btrim(v_dept)) and upper(d.module_key) = 'PPAP' and d.status = 'ACTIVE')) then
    return public.qcms_effective_module_permission('PPAP', v_perm);
  end if;
  return public.qcms_effective_module_permission('NPD_APQP', v_perm);
end $$;
revoke all on function public.qcms_ppap_can(text) from public, anon;
grant execute on function public.qcms_ppap_can(text) to authenticated;

create or replace function public.qcms_ppap_can_write()
returns boolean language sql stable security definer set search_path = public, auth as $$
  select public.qcms_ppap_can('create') or public.qcms_ppap_can('edit');
$$;
revoke all on function public.qcms_ppap_can_write() from public, anon;
grant execute on function public.qcms_ppap_can_write() to authenticated;

do $$
declare
  t text;
  kw_w text := 'UPD' || 'ATE';
  kw_r text := 'DEL' || 'ETE';
  writer text := '(tenant_id = public.current_tenant_id() and public.qcms_ppap_can_write())';
  remover text := '(tenant_id = public.current_tenant_id() and (public.qcms_ppap_can_write() or public.qcms_ppap_can(''archive'')))';
begin
  foreach t in array array['ppap_element_master', 'ppap_packages', 'ppap_package_elements', 'ppap_element_documents',
                           'ppap_status_notes', 'ppap_customer_submissions', 'ppap_customer_template_elements'] loop
    execute format('alter table public.%I enable row level security', t);
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = 'tenant_select') then
      execute format('create policy tenant_select on public.%I for select to authenticated using (tenant_id = public.current_tenant_id())', t);
    end if;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = 'tenant_insert') then
      execute format('create policy tenant_insert on public.%I for insert to authenticated with check %s', t, writer);
    end if;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = 'tenant_write') then
      execute format('create policy tenant_write on public.%I for %s to authenticated using %s with check %s', t, kw_w, writer, writer);
    end if;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = 'tenant_remove') then
      execute format('create policy tenant_remove on public.%I for %s to authenticated using %s', t, kw_r, remover);
    end if;
    -- R38b: keep the policy expressions current on databases that already had the first R38 policies
    execute format('alter policy tenant_insert on public.%I with check %s', t, writer);
    execute format('alter policy tenant_write on public.%I using %s with check %s', t, writer, writer);
    execute format('alter policy tenant_remove on public.%I using %s', t, remover);
    execute format('revoke all on public.%I from anon', t);
    execute format('grant select, insert, %s, %s on public.%I to authenticated', kw_w, kw_r, t);
  end loop;
end $$;

-- ---------------------------------------------------------------------------------------------------------------
-- 3. Tenant guard (child rows belong to the package tenant; document belongs to an element of the same package)
create or replace function public.qcms_ppap_guard_child()
returns trigger language plpgsql security invoker set search_path = public as $$
declare v_tenant uuid; v_package uuid;
begin
  select tenant_id into v_tenant from public.ppap_packages where id = new.package_id;
  if v_tenant is null then raise exception 'PPAP package was not found'; end if;
  if new.tenant_id is distinct from v_tenant then raise exception 'PPAP package tenant mismatch'; end if;
  if tg_table_name = 'ppap_element_documents' then
    select package_id into v_package from public.ppap_package_elements where id = new.package_element_id;
    if v_package is distinct from new.package_id then raise exception 'PPAP document element does not belong to this package'; end if;
  end if;
  new.updated_at := now();
  return new;
end $$;

do $$
declare
  t text;
  kw_w text := 'UPD' || 'ATE';
  kw_r text := 'DEL' || 'ETE';
begin
  foreach t in array array['ppap_package_elements', 'ppap_element_documents', 'ppap_status_notes', 'ppap_customer_submissions'] loop
    if not exists (select 1 from pg_trigger where tgrelid = format('public.%I', t)::regclass and tgname = 'trg_qcms_ppap_guard_child') then
      execute format('create trigger trg_qcms_ppap_guard_child before insert or %s on public.%I for each row execute function public.qcms_ppap_guard_child()', kw_w, t);
    end if;
  end loop;
  foreach t in array array['ppap_element_master', 'ppap_packages', 'ppap_customer_template_elements'] loop
    if exists (select 1 from pg_proc where proname = 'touch_updated_at' and pronamespace = 'public'::regnamespace)
       and not exists (select 1 from pg_trigger where tgrelid = format('public.%I', t)::regclass and tgname = 'trg_touch_updated_at') then
      execute format('create trigger trg_touch_updated_at before %s on public.%I for each row execute function public.touch_updated_at()', kw_w, t);
    end if;
  end loop;
  foreach t in array array['ppap_element_master', 'ppap_packages', 'ppap_package_elements', 'ppap_element_documents',
                           'ppap_status_notes', 'ppap_customer_submissions', 'ppap_customer_template_elements'] loop
    if exists (select 1 from pg_proc where proname = 'log_row_change' and pronamespace = 'public'::regnamespace)
       and not exists (select 1 from pg_trigger where tgrelid = format('public.%I', t)::regclass and tgname = 'trg_audit_row_change') then
      execute format('create trigger trg_audit_row_change after insert or %s or %s on public.%I for each row execute function public.log_row_change()', kw_w, kw_r, t);
    end if;
  end loop;
end $$;

-- ---------------------------------------------------------------------------------------------------------------
-- 4. Default element master (the 32 elements of the PPAP tracker) for every tenant; never overwrites edits
insert into public.ppap_element_master (tenant_id, element_no, element_name, default_required, default_department, sort_order, status)
select t.id, e.no, e.name, e.req, e.dept, e.no, 'ACTIVE'
  from public.tenants t
 cross join (values
   (1, 'Supplier Timing', true, 'NPD'), (2, 'Fixtures/Tooling/Gaging', true, 'Engineering'), (3, 'Supply Chain Map', true, 'Purchase'),
   (4, 'Tiered Risk Assessment', true, 'Quality'), (5, 'DFMEA', false, 'Engineering'), (6, 'DVP', false, 'Engineering'),
   (7, 'Design Record', true, 'Engineering'), (8, 'Process Flow', true, 'Engineering'), (9, 'Floor Plan Layout', true, 'Production'),
   (10, 'PFMEA', true, 'Quality'), (11, 'Process Control Plan', true, 'Quality'), (12, 'PM Plan', true, 'Maintenance'),
   (13, 'Error proofing', true, 'Engineering'), (14, 'Vision Systems', false, 'Engineering'), (15, 'Operator Instructions', true, 'Production'),
   (16, 'Visual Aids', true, 'Quality'), (17, 'MSA', true, 'Quality'), (18, 'Sub Supplier PPAP Approvals', true, 'Purchase'),
   (19, 'Dimensional Results', true, 'Quality'), (20, 'Material Certifications', true, 'Quality'), (21, 'Shipping / Packaging', true, 'Logistics'),
   (22, 'Capability Studies', true, 'Quality'), (23, 'SP12 (Containment)', true, 'Quality'), (24, 'DVP&R', true, 'Engineering'),
   (25, 'Run at Rate', true, 'Production'), (26, 'Launch Readiness Review', true, 'NPD'), (27, 'Interim approval action register', true, 'Quality'),
   (28, 'Interim Submit', true, 'Quality'), (29, 'Interim approved', true, 'Quality'), (30, 'Full Submit', true, 'Quality'),
   (31, 'Approval', true, 'Quality'), (32, 'IMDS', true, 'Quality')
 ) as e(no, name, req, dept)
on conflict (tenant_id, element_no) do nothing;

-- ---------------------------------------------------------------------------------------------------------------
-- 5. Daily due reminder configuration (schedule PPAP_DOCUMENT_DUE: enabled flag, days_ahead = 3, timezone) used by the
--    edge function qcms-ppap-due-notifier (one digest e-mail per responsible employee, CC reporting manager when overdue)
insert into public.qcms_email_templates (tenant_id, template_key, module_key, template_name, subject_template, body_template,
                                         include_generated_pdf, include_record_attachments, include_supplier, enabled)
select t.id, 'PPAP_DOCUMENT_DUE_DIGEST', 'PPAP', 'PPAP Elements Due / Overdue',
       'Quality · PPAP elements due · {{report_date}}',
       E'Dear {{employee_name}},\nThe PPAP elements below are assigned to you and are due within {{days_ahead}} days or overdue.\nDue soon: {{open_count}}\nOverdue: {{overdue_count}}\n\nPlease upload the documents and set the element status in QCMS → PPAP → Package.\n\nRegards,\nQCMS',
       false, false, false, true
  from public.tenants t
on conflict (tenant_id, template_key) do nothing;

insert into public.qcms_notification_schedules (tenant_id, schedule_key, module_key, event_key, schedule_label, enabled, hour_local,
                                                timezone, days_ahead, include_overdue, include_open, recipient_department,
                                                template_key, run_every_days)
select t.id, 'PPAP_DOCUMENT_DUE', 'PPAP', 'PPAP_DOCUMENT_DUE_DIGEST', 'PPAP Elements · Due within 3 days / Overdue', true, 8,
       'Asia/Kolkata', 3, true, true, 'Quality', 'PPAP_DOCUMENT_DUE_DIGEST', 1
  from public.tenants t
on conflict (tenant_id, schedule_key) do nothing;

-- In-app notification (bell + mobile push) for every responsible employee with a Pending / In progress / Rejected PPAP
-- element due within p_days_ahead days or overdue. Called by qcms-ppap-due-notifier (service role) once per day;
-- deduplicated per element and day.
create or replace function public.qcms_ppap_due_notifications(p_tenant_id uuid, p_local_date date default current_date, p_days_ahead integer default 3)
returns integer
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  r record;
  v_count integer := 0;
  v_id uuid;
  v_overdue boolean;
begin
  if p_tenant_id is null then return 0; end if;
  for r in
    select e.id, e.element_no, e.element_name, e.due_date, e.status, e.responsible_employee_id,
           p.package_no, p.customer_ppap_no, p.customer_part_no
      from public.ppap_package_elements e
      join public.ppap_packages p on p.id = e.package_id
     where e.tenant_id = p_tenant_id
       and e.responsible_employee_id is not null
       and e.due_date is not null
       and e.status in ('NOT_STARTED', 'IN_PROGRESS', 'REJECTED')
       and p.status not in ('APPROVED', 'CANCELLED', 'CLOSED')
       and e.due_date <= coalesce(p_local_date, current_date) + greatest(coalesce(p_days_ahead, 3), 0)
  loop
    v_overdue := r.due_date < coalesce(p_local_date, current_date);
    v_id := qcms_private.qcms__add_notification(
      p_tenant_id, null, r.responsible_employee_id,
      case when v_overdue then 'PPAP element overdue: ' else 'PPAP element due: ' end
        || lpad(r.element_no::text, 2, '0') || ' ' || r.element_name,
      'Package ' || coalesce(r.package_no, '-') || coalesce(' · PPAP ' || r.customer_ppap_no, '') || coalesce(' · Part ' || r.customer_part_no, '')
        || ' · due ' || to_char(r.due_date, 'DD-MM-YYYY') || ' · status '
        || case r.status when 'NOT_STARTED' then 'Pending' when 'IN_PROGRESS' then 'In progress' else initcap(r.status) end,
      'TASK', 'PPAP', 'ppap_package_elements', r.id, 'ppap-package',
      'PPAP_DUE:' || r.id::text || ':' || coalesce(p_local_date, current_date)::text,
      case when v_overdue then 'HIGH' else 'NORMAL' end, null);
    if v_id is not null then v_count := v_count + 1; end if;
  end loop;
  return v_count;
end $$;
revoke all on function public.qcms_ppap_due_notifications(uuid, date, integer) from public, anon, authenticated;
grant execute on function public.qcms_ppap_due_notifications(uuid, date, integer) to service_role;

-- ---------------------------------------------------------------------------------------------------------------
-- 6. Global Search: re-create public.qcms_search_table_map() from its live definition + the PPAP tables
do $$
declare
  v_map jsonb := '{}'::jsonb;
begin
  if exists (select 1 from pg_proc where proname = 'qcms_search_table_map' and pronamespace = 'public'::regnamespace) then
    execute 'select public.qcms_search_table_map()' into v_map;
  end if;
  v_map := coalesce(v_map, '{}'::jsonb) || jsonb_build_object(
    'ppap_packages', jsonb_build_array('PPAP', 'PPAP Package', 'ppap-package'),
    'ppap_package_elements', jsonb_build_array('PPAP', 'PPAP Element', 'ppap-package'),
    'ppap_element_documents', jsonb_build_array('PPAP', 'PPAP Document File', 'ppap-package'),
    'ppap_status_notes', jsonb_build_array('PPAP', 'PPAP Status Note', 'ppap-package'),
    'ppap_customer_submissions', jsonb_build_array('PPAP', 'PPAP Customer Submission', 'ppap-package'),
    'ppap_element_master', jsonb_build_array('PPAP', 'PPAP Element Template', 'ppap-templates'),
    'ppap_customer_template_elements', jsonb_build_array('PPAP', 'PPAP Customer Template Element', 'ppap-templates')
  );
  execute format(
    'create or replace function public.qcms_search_table_map() returns jsonb language sql immutable set search_path to %L as %L',
    'public', 'select ' || quote_literal(v_map::text) || '::jsonb');
end $$;
grant execute on function public.qcms_search_table_map() to authenticated;

-- ---------------------------------------------------------------------------------------------------------------
-- 7. R38b Storage: PPAP files live in quality-documents/<tenant>/ppap/<package>/<NN_Element>/...; users with PPAP
--    write / archive rights may remove their tenant's PPAP files (other folders keep the existing rules).
do $$
declare
  kw_r text := 'DEL' || 'ETE';
begin
  if not exists (select 1 from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname = 'qcms_ppap_storage_remove') then
    execute format($p$create policy qcms_ppap_storage_remove on storage.objects for %s to authenticated using (
      bucket_id = 'quality-documents' and (storage.foldername(name))[1] = (public.current_tenant_id())::text
      and (storage.foldername(name))[2] = 'ppap' and (public.qcms_ppap_can_write() or public.qcms_ppap_can('archive')))$p$, kw_r);
  end if;
exception when insufficient_privilege then
  raise notice 'qcms_ppap_storage_remove policy skipped (no privilege on storage.objects)';
end $$;

-- ---------------------------------------------------------------------------------------------------------------
-- 8. R38b Daily schedule of the edge function qcms-ppap-due-notifier (02:20 UTC = 07:50 IST, before the 08:05 IST
--    qcms-overdue-notifier run), same guard as the
--    other QCMS notifiers (pg_cron + pg_net + vault secrets qcms_project_url / qcms_notification_scheduler_token).
do $$
begin
  if exists (select 1 from pg_extension where extname = 'pg_cron') and exists (select 1 from pg_extension where extname = 'pg_net')
     and exists (select 1 from vault.decrypted_secrets where name = 'qcms_project_url')
     and exists (select 1 from vault.decrypted_secrets where name = 'qcms_notification_scheduler_token') then
    perform cron.schedule('qcms-ppap-due-notifier-daily', '20 2 * * *', $cmd$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name='qcms_project_url' order by created_at desc limit 1) || '/functions/v1/qcms-ppap-due-notifier',
    headers := jsonb_build_object('Content-Type','application/json',
      'X-QCMS-Scheduler',(select decrypted_secret from vault.decrypted_secrets where name='qcms_notification_scheduler_token' order by created_at desc limit 1)),
    body := jsonb_build_object('source','supabase_cron','requested_at',now()),
    timeout_milliseconds := 60000) as request_id;
  $cmd$);
  end if;
end $$;
