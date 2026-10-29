-- QCMS v4.14.49 R39 · PPAP assignment e-mail (web + Android app trigger the same server-side RPC).
-- "As soon as a PPAP is created the e-mail must go to the responsible person with all part details and drawings
--  including related specification, and reminders to be sent."
--
-- * public.qcms_ppap_department_label(text)   - department label for subjects (R38 rule: subject starts with the department).
-- * public.qcms_ppap_html(text)               - HTML escape for the e-mail body.
-- * public.qcms_ppap_part_context(uuid)       - part details + current drawings / specifications of a package's part:
--     PART_MASTER   FINISH / FORGING / HEAT_TREATMENT drawing (document_attachments, status ACTIVE = current revision)
--     PART_PROCESS  PROCESS_DRAWING / PROCESS_SPEC of the part's process routes (R38 controlled revisions)
--     PART_PROCESS_SPEC OSP process drawings of the part's process specifications
--     CUSTOMER_STANDARD documents of the standards linked to the part (part_standard_links)
--   Used by the RPC below and by the daily reminder edge function qcms-ppap-due-notifier.
-- * public.qcms_ppap_assignment_mail(p_package_id, p_element_ids, p_resend, p_app_url) returns uuid[]
--     One PENDING qcms_notification_outbox row per responsible employee (all of that person's open elements of the
--     package), CC the package owner, drawings first then specifications as storage references in attachment_manifest
--     (max 18 files / 10 MB, the rest listed by name). Deduplicated per package + employee + element set + day
--     (p_resend = true adds a time stamp so "Send assignment e-mail again" always queues a new mail).
--     SECURITY INVOKER: tenant RLS applies; PPAP create / edit right is required (public.qcms_ppap_can_write()).
--     The caller then invokes the edge function qcms-send-email {"outbox_ids": [...]}.
-- * qcms_private.qcms__trg_outbox_to_inapp: PPAP events open the PPAP package page (route ppap-package, module PPAP);
--   PPAP_ASSIGNMENT mails raise no second bell entry (the caller already sends qcms_notify per element).
--
-- CLIENT CONTRACT (website core/ppap_service.py and Android app; see mobile/PPAP_MAIL_CONTRACT.md):
--   1. POST /rest/v1/rpc/qcms_ppap_assignment_mail  (user JWT, never service_role)
--        {"p_package_id": "<uuid>", "p_element_ids": null | ["<uuid>", ...], "p_resend": false | true, "p_app_url": "<https url>" | null}
--      -> JSON array of qcms_notification_outbox ids (uuid[]); [] = nothing new to send (already queued today,
--         no responsible person with an e-mail address, or all elements NA / COMPLETED).
--      Call it after the package is created (p_element_ids null), after responsible persons / elements are assigned or
--      reassigned (p_element_ids = the changed element ids) and from "Send assignment e-mail again" (p_resend true).
--   2. POST /functions/v1/qcms-send-email  {"outbox_ids": [ ...ids from step 1... ]}  (user JWT) - sends the mails with the
--      drawings / specifications from attachment_manifest. Skip the call when the array is empty.
--   Errors are raised as plain messages (not signed in / no PPAP edit right / package not found) - show them to the user.
--   Daily reminders: edge function qcms-ppap-due-notifier (cron) uses qcms_ppap_part_context for the same part details + files.
-- Subject: "<Department> · PPAP <package no> · <part no (name)> · your <n> element(s) due from DD-MM-YYYY".
-- Reminder attachment rule (qcms-ppap-due-notifier): a file is attached again to the same person at most once in 7 days.
-- Applied live 28-10-2026 (first version) and re-applied 29-10-2026 with the subject above.
-- Additive / re-runnable: create or replace only.

create or replace function public.qcms_ppap_department_label(p_value text)
returns text language sql immutable set search_path = '' as $$
  select case
    when coalesce(btrim(p_value), '') = '' then 'Quality'
    when lower(regexp_replace(p_value, '[^A-Za-z0-9]+', '', 'g')) in ('qcmsteam', 'qcms', 'all', 'none') then 'Quality'
    else coalesce((select v.label from (values
        ('quality', 'Quality'), ('qa', 'Quality'), ('qc', 'Quality'), ('metlab', 'MetLAB'), ('lab', 'MetLAB'),
        ('supplychain', 'Supply Chain'), ('scm', 'Supply Chain'), ('purchase', 'Purchase'), ('procurement', 'Purchase'),
        ('stores', 'Stores'), ('store', 'Stores'), ('npd', 'NPD'), ('rd', 'R & D'), ('engineering', 'Engineering'),
        ('production', 'Production'), ('management', 'Management'), ('admin', 'Admin'), ('administration', 'Admin'),
        ('hr', 'HR'), ('accounts', 'Accounts'), ('marketing', 'Marketing'), ('businessdevelopment', 'Business Development'),
        ('maintenance', 'Maintenance'), ('dispatch', 'Dispatch'), ('logistics', 'Logistics')) as v(k, label)
       where v.k = lower(regexp_replace(p_value, '[^A-Za-z0-9]+', '', 'g'))), btrim(regexp_replace(p_value, '\s+', ' ', 'g')))
  end;
$$;

create or replace function public.qcms_ppap_html(p_value text)
returns text language sql immutable set search_path = '' as $$
  select replace(replace(replace(replace(coalesce(p_value, ''), '&', '&amp;'), '<', '&lt;'), '>', '&gt;'), '"', '&quot;');
$$;

-- ---------------------------------------------------------------------------------------------------------------
create or replace function public.qcms_ppap_part_context(p_package_id uuid)
returns jsonb
language plpgsql
stable
security invoker
set search_path = public
as $$
declare
  v_pkg public.ppap_packages%rowtype;
  v_part public.parts%rowtype;
  v_grade text;
  v_customer text;
  v_owner jsonb;
  v_docs jsonb;
begin
  select * into v_pkg from public.ppap_packages where id = p_package_id;
  if not found then return null; end if;
  if v_pkg.part_id is not null then
    select * into v_part from public.parts where id = v_pkg.part_id;
    select nullif(concat_ws(' · ', nullif(g.material_number, ''), nullif(g.grade_code, ''), nullif(g.standard, '')), '')
      into v_grade from public.material_grades g where g.id = v_part.material_grade_id;
  end if;
  select party_name into v_customer from public.parties where id = v_pkg.customer_id;
  select jsonb_build_object('id', e.id, 'name', btrim(concat_ws(' ', e.first_name, e.last_name)), 'email', e.email, 'department', e.department)
    into v_owner from public.employees e where e.id = v_pkg.owner_employee_id;

  with docs as (
    select 1 as grp,
           case d.document_type when 'FINISH_DRAWING' then 1 when 'FORGING_DRAWING' then 2 else 3 end as ord,
           'drawing'::text as kind, initcap(replace(d.document_type, '_', ' ')) as category,
           d.file_name, d.object_path, d.mime_type, d.size_bytes, d.revision, d.drawing_number, d.document_title, d.created_at
      from public.document_attachments d
     where v_pkg.part_id is not null and d.entity_type = 'PART_MASTER' and d.entity_id = v_pkg.part_id and d.status = 'ACTIVE'
       and d.document_type in ('FINISH_DRAWING', 'FORGING_DRAWING', 'HEAT_TREATMENT_DRAWING')
    union all
    select 2, case d.document_type when 'PROCESS_DRAWING' then 1 else 2 end,
           case d.document_type when 'PROCESS_DRAWING' then 'drawing' else 'spec' end,
           concat_ws(' · ', case d.document_type when 'PROCESS_DRAWING' then 'Process drawing' else 'Process specification' end,
                     nullif(concat_ws(' ', 'OP', r.operation_no::text, r.process_name_snapshot), 'OP')),
           d.file_name, d.object_path, d.mime_type, d.size_bytes, d.revision, d.drawing_number, d.document_title, d.created_at
      from public.document_attachments d
      join public.part_process_routes r on r.id = d.entity_id
     where v_pkg.part_id is not null and d.entity_type = 'PART_PROCESS' and r.part_id = v_pkg.part_id
       and coalesce(r.status, 'ACTIVE') = 'ACTIVE' and d.status = 'ACTIVE' and d.document_type in ('PROCESS_DRAWING', 'PROCESS_SPEC')
    union all
    select 2, 3, 'drawing', concat_ws(' · ', 'OSP process drawing', nullif(s.process_specification, '')),
           d.file_name, d.object_path, d.mime_type, d.size_bytes, coalesce(d.revision, s.drawing_revision), coalesce(d.drawing_number, s.drawing_number),
           d.document_title, d.created_at
      from public.document_attachments d
      join public.part_process_specifications s on s.id = d.entity_id
     where v_pkg.part_id is not null and d.entity_type = 'PART_PROCESS_SPEC' and s.part_id = v_pkg.part_id
       and coalesce(s.status, 'ACTIVE') = 'ACTIVE' and d.status = 'ACTIVE'
    union all
    select 3, 1, 'spec', concat_ws(' · ', 'Standard', nullif(cs.standard_code, ''), nullif(cs.standard_name, '')),
           d.file_name, d.object_path, d.mime_type, d.size_bytes, coalesce(d.revision, cs.revision_number), null::text,
           d.document_title, d.created_at
      from public.document_attachments d
      join public.customer_standards cs on cs.id = d.entity_id
      join public.part_standard_links l on l.standard_id = cs.id and l.part_id = v_pkg.part_id and coalesce(l.status, 'ACTIVE') = 'ACTIVE'
     where v_pkg.part_id is not null and d.entity_type = 'CUSTOMER_STANDARD' and d.status = 'ACTIVE'
  )
  select coalesce(jsonb_agg(jsonb_build_object(
           'bucket', 'quality-documents', 'object_path', x.object_path, 'file_name', x.file_name,
           'mime_type', coalesce(nullif(x.mime_type, ''), 'application/octet-stream'),
           'size_bytes', coalesce(nullif(x.size_bytes, 0), nullif(o.metadata ->> 'size', '')::bigint, 0),
           'in_storage', o.id is not null,
           'kind', x.kind, 'category', x.category, 'revision', x.revision, 'drawing_number', x.drawing_number, 'title', x.document_title)
           order by x.grp, x.ord, x.category, x.created_at desc), '[]'::jsonb)
    into v_docs
    from (select distinct on (object_path) * from docs where coalesce(object_path, '') <> '' order by object_path, grp, ord) x
    left join lateral (select so.id, so.metadata from storage.objects so
                        where so.bucket_id = 'quality-documents' and so.name = x.object_path limit 1) o on true;

  return jsonb_build_object(
    'package', jsonb_build_object('id', v_pkg.id, 'tenant_id', v_pkg.tenant_id, 'package_no', v_pkg.package_no,
        'customer_ppap_no', v_pkg.customer_ppap_no, 'customer_part_no', v_pkg.customer_part_no,
        'submission_level', v_pkg.submission_level, 'customer_due_date', v_pkg.customer_due_date, 'status', v_pkg.status,
        'psw_status', v_pkg.psw_status),
    'part', case when v_part.id is null then null else jsonb_build_object('id', v_part.id, 'part_number', v_part.part_number,
        'fsi_part_number', v_part.fsi_part_number, 'part_name', v_part.part_name, 'drawing_number', v_part.drawing_number,
        'drawing_revision', v_part.drawing_revision, 'material_grade', v_grade, 'finished_weight_kg', v_part.finished_weight_kg,
        'forging_weight_kg', v_part.forging_weight_kg, 'gross_weight_kg', v_part.gross_weight_kg, 'section_size', v_part.section_size,
        'manufacturing_route', v_part.manufacturing_route, 'hsn_sac_code', v_part.hsn_sac_code) end,
    'customer', v_customer, 'owner', v_owner, 'documents', v_docs);
end $$;
revoke all on function public.qcms_ppap_part_context(uuid) from public, anon;
grant execute on function public.qcms_ppap_part_context(uuid) to authenticated, service_role;

-- ---------------------------------------------------------------------------------------------------------------
create or replace function public.qcms_ppap_assignment_mail(p_package_id uuid, p_element_ids uuid[] default null,
                                                            p_resend boolean default false, p_app_url text default null)
returns uuid[]
language plpgsql
volatile
security invoker
set search_path = public
as $$
declare
  c_max_bytes constant bigint := 10 * 1024 * 1024;   -- same limit as the PPAP customer e-mail (core/ppap_service.MAX_EMAIL_BYTES)
  c_max_files constant integer := 18;
  v_tid uuid := public.current_tenant_id();
  v_ctx jsonb;
  v_pkg jsonb;
  v_part jsonb;
  v_owner jsonb;
  v_docs jsonb;
  v_doc jsonb;
  v_manifest jsonb := '[]'::jsonb;
  v_listed jsonb := '[]'::jsonb;
  v_bytes bigint := 0;
  v_size bigint;
  v_base text;
  v_link text;
  v_part_rows text := '';
  v_part_text text := '';
  v_doc_rows text := '';
  v_doc_text text := '';
  v_emp record;
  v_el record;
  v_rows text;
  v_text_rows text;
  v_count integer;
  v_ids uuid[];
  v_key text;
  v_subject text;
  v_html text;
  v_body text;
  v_cc text[];
  v_id uuid;
  v_out uuid[] := '{}';
  v_label text;
  v_value text;
  v_dept text;
  v_min_due date;
  v_th text := 'padding:6px 8px;border:1px solid #0B5858;background:#0F6E6E;color:#FFFFFF;font-size:12px;text-align:left';
  v_td text := 'padding:6px 8px;border:1px solid #D5E4E4;font-size:12px;vertical-align:top';
begin
  if auth.uid() is null or v_tid is null then raise exception 'Sign in to QCMS first.'; end if;
  if not public.qcms_ppap_can_write() then raise exception 'PPAP create / edit permission is required to send the assignment e-mail.'; end if;
  if not exists (select 1 from public.ppap_packages where id = p_package_id and tenant_id = v_tid) then
    raise exception 'PPAP package was not found.';
  end if;

  v_ctx := public.qcms_ppap_part_context(p_package_id);
  v_pkg := v_ctx -> 'package';
  v_part := coalesce(v_ctx -> 'part', '{}'::jsonb);
  v_owner := coalesce(v_ctx -> 'owner', '{}'::jsonb);
  v_docs := coalesce(v_ctx -> 'documents', '[]'::jsonb);

  -- link to the PPAP package page
  v_base := nullif(rtrim(btrim(coalesce(p_app_url, '')), '/'), '');
  if v_base is null or v_base !~* '^https?://' or v_base ~* '//(localhost|127\.0\.0\.1|0\.0\.0\.0)' then
    v_base := null;
    begin
      select nullif(rtrim(btrim(app_link), '/'), '') into v_base from public.qcms_whatsapp_settings where tenant_id = v_tid limit 1;
    exception when others then v_base := null;
    end;
    if v_base is null or v_base !~* '^https?://' then v_base := 'https://vf6fa9hrhxquqxmfgyy4wf.streamlit.app'; end if;
  end if;
  v_link := v_base || '/ppap-package?ppap=' || p_package_id::text;

  -- part details block (only the fields that have a value)
  foreach v_label in array array['Part Number', 'FSI Part Number', 'Part Name', 'Customer Part No.', 'Drawing No. / Rev.',
                                 'Material Grade', 'Finished Weight (kg)', 'Forging Weight (kg)', 'Gross Weight (kg)', 'Section Size',
                                 'Manufacturing Route', 'Customer'] loop
    v_value := case v_label
      when 'Part Number' then v_part ->> 'part_number'
      when 'FSI Part Number' then v_part ->> 'fsi_part_number'
      when 'Part Name' then v_part ->> 'part_name'
      when 'Customer Part No.' then v_pkg ->> 'customer_part_no'
      when 'Drawing No. / Rev.' then nullif(concat_ws(' / Rev. ', nullif(v_part ->> 'drawing_number', ''), nullif(v_part ->> 'drawing_revision', '')), '')
      when 'Material Grade' then v_part ->> 'material_grade'
      when 'Finished Weight (kg)' then v_part ->> 'finished_weight_kg'
      when 'Forging Weight (kg)' then v_part ->> 'forging_weight_kg'
      when 'Gross Weight (kg)' then v_part ->> 'gross_weight_kg'
      when 'Section Size' then v_part ->> 'section_size'
      when 'Manufacturing Route' then v_part ->> 'manufacturing_route'
      when 'Customer' then v_ctx ->> 'customer' end;
    if coalesce(btrim(v_value), '') <> '' then
      v_part_rows := v_part_rows || format('<tr><td style="%s;background:#F3F7F7;font-weight:700;width:34%%">%s</td><td style="%s">%s</td></tr>',
                                           v_td, public.qcms_ppap_html(v_label), v_td, public.qcms_ppap_html(v_value));
      v_part_text := v_part_text || format(E'  %s: %s\n', v_label, v_value);
    end if;
  end loop;

  -- drawings first, then specifications; attach while the e-mail stays within 18 files / 10 MB, list the rest
  for v_doc in select value from jsonb_array_elements(v_docs) loop
    v_size := coalesce(nullif(v_doc ->> 'size_bytes', '')::bigint, 0);
    if v_size <= 0 then v_size := 2 * 1024 * 1024; end if;   -- unknown size: count 2 MB
    if coalesce((v_doc ->> 'in_storage')::boolean, false) = false then
      v_listed := v_listed || jsonb_build_array(v_doc ->> 'file_name');
      v_value := 'File not found in storage - open it in QCMS';
    elsif jsonb_array_length(v_manifest) < c_max_files and v_bytes + v_size <= c_max_bytes then
      v_manifest := v_manifest || jsonb_build_array(jsonb_build_object('bucket', v_doc ->> 'bucket', 'object_path', v_doc ->> 'object_path',
                       'file_name', v_doc ->> 'file_name', 'mime_type', v_doc ->> 'mime_type', 'generated', false));
      v_bytes := v_bytes + v_size;
      v_value := 'Attached';
    else
      v_listed := v_listed || jsonb_build_array(v_doc ->> 'file_name');
      v_value := 'Not attached (e-mail size) - open it in QCMS';
    end if;
    v_doc_rows := v_doc_rows || format('<tr><td style="%s">%s</td><td style="%s">%s</td><td style="%s">%s</td><td style="%s">%s</td><td style="%s">%s</td></tr>',
        v_td, public.qcms_ppap_html(v_doc ->> 'category'), v_td, public.qcms_ppap_html(coalesce(v_doc ->> 'file_name', '')),
        v_td, public.qcms_ppap_html(coalesce(nullif(v_doc ->> 'drawing_number', ''), '-')), v_td, public.qcms_ppap_html(coalesce(nullif(v_doc ->> 'revision', ''), '-')),
        v_td, public.qcms_ppap_html(v_value));
    v_doc_text := v_doc_text || format(E'  - %s: %s (Rev. %s) - %s\n', v_doc ->> 'category', v_doc ->> 'file_name',
                                       coalesce(nullif(v_doc ->> 'revision', ''), '-'), v_value);
  end loop;

  -- one e-mail per responsible employee with an e-mail address
  for v_emp in
    select e.id, e.email, btrim(concat_ws(' ', e.first_name, e.last_name)) as name, e.department
      from public.employees e
     where e.tenant_id = v_tid
       and coalesce(btrim(e.email), '') ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'
       and e.id in (select x.responsible_employee_id from public.ppap_package_elements x
                     where x.package_id = p_package_id and x.responsible_employee_id is not null
                       and x.status not in ('NA', 'COMPLETED')
                       and (p_element_ids is null or x.id = any(p_element_ids)))
     order by lower(e.email)
  loop
    v_rows := ''; v_text_rows := ''; v_count := 0; v_ids := '{}'; v_min_due := null;
    for v_el in
      select x.id, x.element_no, x.element_name, x.due_date, x.status, x.remarks
        from public.ppap_package_elements x
       where x.package_id = p_package_id and x.responsible_employee_id = v_emp.id and x.status not in ('NA', 'COMPLETED')
         and (p_element_ids is null or x.id = any(p_element_ids))
       order by coalesce(x.sort_order, x.element_no), x.element_no
    loop
      v_count := v_count + 1;
      v_ids := v_ids || v_el.id;
      if v_el.due_date is not null and (v_min_due is null or v_el.due_date < v_min_due) then v_min_due := v_el.due_date; end if;
      v_value := case v_el.status when 'NOT_STARTED' then 'Pending' when 'IN_PROGRESS' then 'In progress' when 'SUBMITTED' then 'Submitted'
                                  when 'REJECTED' then 'Rejected' else initcap(replace(v_el.status, '_', ' ')) end;
      v_rows := v_rows || format('<tr><td style="%s;text-align:center">%s</td><td style="%s">%s</td><td style="%s;white-space:nowrap">%s</td><td style="%s">%s</td><td style="%s">%s</td></tr>',
          v_td, lpad(v_el.element_no::text, 2, '0'), v_td, public.qcms_ppap_html(v_el.element_name),
          v_td, coalesce(to_char(v_el.due_date, 'DD-MM-YYYY'), 'not set'), v_td, public.qcms_ppap_html(v_value),
          v_td, public.qcms_ppap_html(coalesce(v_el.remarks, '')));
      v_text_rows := v_text_rows || format(E'  %s %s · due %s · %s%s\n', lpad(v_el.element_no::text, 2, '0'), v_el.element_name,
          coalesce(to_char(v_el.due_date, 'DD-MM-YYYY'), 'not set'), v_value, case when coalesce(v_el.remarks, '') = '' then '' else ' · ' || v_el.remarks end);
    end loop;
    if v_count = 0 then continue; end if;

    v_dept := public.qcms_ppap_department_label(v_emp.department);
    -- department first (R38 rule), e.g. "Quality · PPAP PPAP-1234 · 10012345 (Flange) · your 4 element(s) due from 05-11-2026"
    v_subject := format('%s · PPAP %s · %s · your %s element(s) %s', v_dept, v_pkg ->> 'package_no',
                        coalesce(nullif(concat_ws(' ', nullif(v_part ->> 'part_number', ''),
                                                  case when coalesce(v_part ->> 'part_name', '') <> '' then '(' || (v_part ->> 'part_name') || ')' end), ''),
                                 nullif(v_pkg ->> 'customer_part_no', ''), 'Part not linked'),
                        v_count, case when v_min_due is null then 'assigned (due date not set)' else 'due from ' || to_char(v_min_due, 'DD-MM-YYYY') end);
    v_key := 'PPAP_ASSIGNMENT:' || p_package_id::text || ':' || v_emp.id::text || ':'
             || md5(array_to_string(array(select unnest(v_ids)::text order by 1), ',')) || ':' || current_date::text
             || case when p_resend then ':' || to_char(clock_timestamp(), 'HH24MISSMS') else '' end;
    v_cc := '{}';
    if coalesce(v_owner ->> 'email', '') ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' and lower(v_owner ->> 'email') <> lower(v_emp.email) then
      v_cc := array[btrim(v_owner ->> 'email')];
    end if;

    v_html := '<!doctype html><html><body style="margin:0;padding:0;background:#F3F6F8">'
      || '<div style="max-width:1000px;margin:0 auto;padding:16px;font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.5;color:#273444">'
      || '<div style="background:#0F6E6E;color:#FFFFFF;padding:12px 16px;border-radius:6px 6px 0 0;font-size:16px;font-weight:700">'
      || public.qcms_ppap_html(format('PPAP %s · elements assigned to you', v_pkg ->> 'package_no')) || '</div>'
      || '<div style="background:#FFFFFF;padding:16px;border:1px solid #D5E4E4;border-top:0;border-radius:0 0 6px 6px">'
      || format('<p style="margin:0 0 8px 0">Dear %s,</p>', public.qcms_ppap_html(coalesce(nullif(v_emp.name, ''), 'Colleague')))
      || format('<p style="margin:0 0 8px 0">You are responsible for %s PPAP element(s) of package <b>%s</b>. The current part drawings and related specifications are attached (or listed below).</p>',
                v_count, public.qcms_ppap_html(v_pkg ->> 'package_no'))
      || '<table style="border-collapse:collapse;width:100%;margin:6px 0 12px 0">'
      || format('<tr><td style="%s;background:#F3F7F7;font-weight:700;width:34%%">PPAP Package No.</td><td style="%s">%s</td></tr>', v_td, v_td, public.qcms_ppap_html(v_pkg ->> 'package_no'))
      || format('<tr><td style="%s;background:#F3F7F7;font-weight:700">Customer PPAP No.</td><td style="%s">%s</td></tr>', v_td, v_td, public.qcms_ppap_html(coalesce(nullif(v_pkg ->> 'customer_ppap_no', ''), '-')))
      || format('<tr><td style="%s;background:#F3F7F7;font-weight:700">Submission Level</td><td style="%s">Level %s</td></tr>', v_td, v_td, public.qcms_ppap_html(coalesce(v_pkg ->> 'submission_level', '3')))
      || format('<tr><td style="%s;background:#F3F7F7;font-weight:700">Customer Due Date</td><td style="%s">%s</td></tr>', v_td, v_td,
                coalesce(to_char((v_pkg ->> 'customer_due_date')::date, 'DD-MM-YYYY'), '-'))
      || format('<tr><td style="%s;background:#F3F7F7;font-weight:700">PPAP Owner</td><td style="%s">%s</td></tr>', v_td, v_td, public.qcms_ppap_html(coalesce(nullif(v_owner ->> 'name', ''), '-')))
      || '</table>'
      || '<div style="font-weight:700;color:#0F6E6E;margin:10px 0 4px 0">PART DETAILS</div>'
      || '<table style="border-collapse:collapse;width:100%;margin:0 0 12px 0">'
      || case when v_part_rows = '' then format('<tr><td style="%s">No Part Master record is linked to this package.</td></tr>', v_td) else v_part_rows end
      || '</table>'
      || '<div style="font-weight:700;color:#0F6E6E;margin:10px 0 4px 0">YOUR PPAP ELEMENTS</div>'
      || format('<table style="border-collapse:collapse;width:100%%;margin:0 0 12px 0"><tr><th style="%s">No.</th><th style="%s">Element</th><th style="%s">Due Date</th><th style="%s">Status</th><th style="%s">Remarks</th></tr>',
                v_th, v_th, v_th, v_th, v_th)
      || v_rows || '</table>'
      || '<div style="font-weight:700;color:#0F6E6E;margin:10px 0 4px 0">CURRENT DRAWINGS &amp; SPECIFICATIONS</div>'
      || case when v_doc_rows = '' then '<p style="margin:0 0 12px 0">No controlled drawing or specification is stored for this part yet.</p>'
              else format('<table style="border-collapse:collapse;width:100%%;margin:0 0 12px 0"><tr><th style="%s">Document</th><th style="%s">File</th><th style="%s">Drawing No.</th><th style="%s">Rev.</th><th style="%s">E-mail</th></tr>',
                          v_th, v_th, v_th, v_th, v_th) || v_doc_rows || '</table>' end
      || format('<p style="margin:12px 0"><a href="%s" style="background:#0F6E6E;color:#FFFFFF;padding:8px 14px;border-radius:4px;text-decoration:none;font-weight:700">Open the PPAP package in QCMS</a></p>',
                public.qcms_ppap_html(v_link))
      || '<p style="margin:0;color:#5C7778;font-size:12px">Upload the documents and set the element status in QCMS → PPAP → Package (website or Android app). '
      || 'You will get a daily reminder for elements due within 3 days or overdue.</p>'
      || '</div></div></body></html>';

    v_body := format(E'Dear %s,\n\nYou are responsible for %s PPAP element(s) of package %s.\n\nPPAP Package No.: %s\nCustomer PPAP No.: %s\nSubmission Level: Level %s\nCustomer Due Date: %s\nPPAP Owner: %s\n\nPART DETAILS\n%s\nYOUR PPAP ELEMENTS\n%s\nCURRENT DRAWINGS & SPECIFICATIONS\n%s\nOpen the PPAP package: %s\n\nUpload the documents and set the element status in QCMS → PPAP → Package.',
                     coalesce(nullif(v_emp.name, ''), 'Colleague'), v_count, v_pkg ->> 'package_no', v_pkg ->> 'package_no',
                     coalesce(nullif(v_pkg ->> 'customer_ppap_no', ''), '-'), coalesce(v_pkg ->> 'submission_level', '3'),
                     coalesce(to_char((v_pkg ->> 'customer_due_date')::date, 'DD-MM-YYYY'), '-'), coalesce(nullif(v_owner ->> 'name', ''), '-'),
                     case when v_part_text = '' then E'  No Part Master record is linked.\n' else v_part_text end, v_text_rows,
                     case when v_doc_text = '' then E'  No controlled drawing or specification is stored for this part yet.\n' else v_doc_text end, v_link);

    v_id := null;
    insert into public.qcms_notification_outbox (tenant_id, event_key, recipient_email, recipient_name, cc_emails, subject, body_text, body_html,
                                                 related_table, related_id, context, template_key, attachment_manifest, dedupe_key,
                                                 is_automatic, scheduled_for, status)
    values (v_tid, 'PPAP_ASSIGNMENT', btrim(v_emp.email), nullif(v_emp.name, ''), v_cc, v_subject, v_body, v_html,
            'ppap_packages', p_package_id,
            jsonb_build_object('module_key', 'PPAP', 'department', v_dept, 'web_route', 'ppap-package', 'package_id', p_package_id,
                               'package_no', v_pkg ->> 'package_no', 'employee_id', v_emp.id, 'element_ids', to_jsonb(v_ids),
                               'element_count', v_count, 'attached_count', jsonb_array_length(v_manifest), 'listed_files', v_listed,
                               'link', v_link, 'source', 'qcms_ppap_assignment_mail'),
            'PPAP_ASSIGNMENT', v_manifest, v_key, false, now(), 'PENDING')
    on conflict (tenant_id, dedupe_key) where dedupe_key is not null do nothing
    returning id into v_id;
    if v_id is not null then v_out := v_out || v_id; end if;
  end loop;
  return v_out;
end $$;
revoke all on function public.qcms_ppap_assignment_mail(uuid, uuid[], boolean, text) from public, anon;
grant execute on function public.qcms_ppap_assignment_mail(uuid, uuid[], boolean, text) to authenticated;
comment on function public.qcms_ppap_assignment_mail(uuid, uuid[], boolean, text) is
  'R39: queue the PPAP assignment e-mail (part details, elements, current drawings / specifications) per responsible employee; returns outbox ids for qcms-send-email.';

-- ---------------------------------------------------------------------------------------------------------------
-- Outbox -> in-app notification: PPAP events open the PPAP package; PPAP_ASSIGNMENT has its own qcms_notify per element.
create or replace function qcms_private.qcms__trg_outbox_to_inapp()
 returns trigger
 language plpgsql
 security definer
 set search_path to 'public', 'auth'
as $function$
declare
  k text := upper(coalesce(new.event_key, '')); v_cat text; v_route text; v_module text; v_source text;
  v_profile uuid; v_employee uuid;
begin
  begin
    if k in ('USER_EMAIL', 'EMAIL_SERVER_TEST', 'PPAP_ASSIGNMENT') or coalesce(new.recipient_email, '') = '' then return new; end if;
    select p.id into v_profile from public.profiles p where p.tenant_id = new.tenant_id and lower(p.email) = lower(btrim(new.recipient_email)) and p.status = 'ACTIVE' limit 1;
    select e.id into v_employee from public.employees e where e.tenant_id = new.tenant_id and lower(e.email) = lower(btrim(new.recipient_email)) limit 1;
    if v_profile is null and v_employee is null then return new; end if;   -- suppliers / customers: e-mail only
    v_cat := case when k like '%APPROVAL%' then 'APPROVAL'
                  when k like '%DIGEST%' then 'INFO'
                  when k like '%PENDING%' or k like '%REQUIRED%' or k like '%OVERDUE%' or k like '%BIENNIAL%' then 'TASK'
                  when k like '%COMPLAINT%' then 'TASK' else ('UPD' || 'ATE') end;
    v_route := case when k like 'PO\_%' escape '\' then 'supply-po-order-list'
                    when k like 'RM\_PO%' escape '\' or k like 'RM\_%' escape '\' then 'supply-rm-procurement'
                    when k like 'FORGING%' then 'supply-forging'
                    when k like 'CUSTOMER\_ORDER%' escape '\' then 'supply-customer-orders'
                    when k like 'OSP%' then 'osp-home'
                    when k like 'RMTC%' then 'rmtc-approval'
                    when k like 'NPD%' then 'npd-status'
                    when k like 'PPAP%' then 'ppap-package'
                    when k like '%COMPLAINT%' then 'complaints-home'
                    when k like 'DIMENSIONAL%' then 'dimensional-entry'
                    when k like 'METLAB%' then 'metlab-entry'
                    when k like ('DEL' || 'ETE%') then 'records-center'
                    else 'dashboard' end;
    v_module := case when v_route like 'supply-%' then 'SUPPLY_CHAIN' when v_route like 'osp-%' then 'OSP_TRANSACTIONS'
                     when v_route like 'rmtc-%' then 'RMTC_ENTRY' when v_route like 'npd-%' then 'NPD_APQP'
                     when v_route like 'ppap-%' then 'PPAP'
                     when v_route like 'complaint%' then 'COMPLAINT_MANAGEMENT' when v_route like 'dimensional%' then 'DIMENSIONAL_REPORT'
                     when v_route like 'metlab%' then 'METLAB_REPORT' else null end;
    -- same source keys as the direct triggers, so one event = one notification
    v_source := case
      when k in ('PO_PENDING_APPROVAL', 'PO_APPROVAL_PENDING') and new.related_id is not null then 'PO_APPROVAL:' || new.related_id || ':' || current_date
      when k in ('DIMENSIONAL_APPROVAL_PENDING', 'METLAB_APPROVAL_PENDING') and new.related_id is not null then 'INSP_APPROVAL:' || new.related_id
      when k = ('DEL' || 'ETE_APPROVAL_REQUEST') and new.related_id is not null then 'DEL_REQ:' || new.related_id
      else 'OUTBOX:' || k || ':' || coalesce(new.related_id::text, new.dedupe_key, new.id::text) || ':' || current_date end;
    if k in ('PO_PENDING_APPROVAL', 'PO_APPROVAL_PENDING') then v_route := 'supply-po-approval'; end if;
    perform qcms_private.qcms__add_notification(new.tenant_id, v_profile, v_employee, coalesce(nullif(new.subject, ''), initcap(replace(k, '_', ' '))),
      left(coalesce(new.body_text, ''), 1500), v_cat, v_module, new.related_table, new.related_id, v_route, v_source,
      case when v_cat = 'APPROVAL' then 'HIGH' else 'NORMAL' end, new.created_by);
  exception when others then null;
  end;
  return new;
end $function$;
