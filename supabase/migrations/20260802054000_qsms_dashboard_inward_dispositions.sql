-- QSMS 4.5.0: RMTC manual dispositions, material inward workflow,
-- common inspection/test dispositions, dashboard support and module permissions.

begin;

alter table public.rmtc_approvals
  add column if not exists disposition text not null default 'PENDING',
  add column if not exists disposition_reason text,
  add column if not exists decision_at timestamptz,
  add column if not exists decision_by_employee_id uuid references public.employees(id);

alter table public.rmtc_part_approvals
  add column if not exists disposition text not null default 'PENDING',
  add column if not exists decision_reason text,
  add column if not exists decision_at timestamptz,
  add column if not exists decision_by_employee_id uuid references public.employees(id);

alter table public.inspection_reports
  add column if not exists disposition text not null default 'PENDING',
  add column if not exists disposition_reason text;

alter table public.lab_tests
  add column if not exists disposition text not null default 'PENDING',
  add column if not exists disposition_reason text;

alter table public.inward_lots
  add column if not exists rmtc_disposition text,
  add column if not exists receipt_disposition text not null default 'PENDING',
  add column if not exists reserve_reason text,
  add column if not exists prepared_by_employee_id uuid references public.employees(id),
  add column if not exists validated_by_employee_id uuid references public.employees(id),
  add column if not exists inward_copy_path text;

alter table public.rmtc_approvals drop constraint if exists rmtc_approvals_disposition_check;
alter table public.rmtc_approvals add constraint rmtc_approvals_disposition_check
  check (disposition in ('PENDING','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED'));

alter table public.rmtc_part_approvals drop constraint if exists rmtc_part_approvals_disposition_check;
alter table public.rmtc_part_approvals add constraint rmtc_part_approvals_disposition_check
  check (disposition in ('PENDING','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED'));

alter table public.inspection_reports drop constraint if exists inspection_reports_disposition_check;
alter table public.inspection_reports add constraint inspection_reports_disposition_check
  check (disposition in ('PENDING','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED'));

alter table public.lab_tests drop constraint if exists lab_tests_disposition_check;
alter table public.lab_tests add constraint lab_tests_disposition_check
  check (disposition in ('PENDING','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED'));

alter table public.inward_lots drop constraint if exists inward_lots_receipt_disposition_check;
alter table public.inward_lots add constraint inward_lots_receipt_disposition_check
  check (receipt_disposition in ('PENDING','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED'));

alter table public.inward_lots drop constraint if exists inward_lots_rmtc_disposition_check;
alter table public.inward_lots add constraint inward_lots_rmtc_disposition_check
  check (rmtc_disposition is null or rmtc_disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE'));

-- Accepted-under-reserve is a controlled release and may include an approved exception.
alter table public.rmtc_approvals drop constraint if exists rmtc_approvals_check;
alter table public.rmtc_approvals add constraint rmtc_approvals_check
  check (
    status not in ('APPROVED','PARTIALLY_APPROVED')
    or disposition='ACCEPTED_UNDER_RESERVE'
    or chemistry_compliance='PASS'
  );

create index if not exists idx_rmtc_disposition
  on public.rmtc_approvals(tenant_id,disposition,status,created_at desc);
create index if not exists idx_rmtc_part_disposition
  on public.rmtc_part_approvals(rmtc_approval_id,disposition,part_id);
create index if not exists idx_inward_rmtc_part
  on public.inward_lots(rmtc_part_approval_id,inward_date desc);
create index if not exists idx_inward_disposition
  on public.inward_lots(tenant_id,receipt_disposition,status,inward_date desc);

create or replace function public.qsms_decide_rmtc(
  p_rmtc_id uuid,
  p_decisions jsonb,
  p_approved_by_employee_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_header public.rmtc_approvals%rowtype;
  v_role text:=public.current_app_role();
  v_item jsonb;
  v_part_id uuid;
  v_disposition text;
  v_reason text;
  v_auto_status text;
  v_total integer:=0;
  v_accepted integer:=0;
  v_reserve integer:=0;
  v_rejected integer:=0;
  v_header_disposition text;
  v_header_status text;
begin
  if v_role not in ('ADMIN','QUALITY_MANAGER','METLAB_APPROVER')
     and not exists(
       select 1 from public.user_module_permissions p
       where p.profile_id=auth.uid() and p.tenant_id=public.current_tenant_id()
         and p.module_key='RMTC_ENTRY' and p.can_approve=true
     ) then
    raise exception 'Your user does not have RMTC approval permission';
  end if;

  select * into v_header
  from public.rmtc_approvals
  where id=p_rmtc_id and tenant_id=public.current_tenant_id()
  for update;

  if v_header.id is null then raise exception 'RMTC record was not found'; end if;
  if v_header.status<>'APPROVAL_PENDING' then
    raise exception 'RMTC must be approval pending before final decision';
  end if;
  if v_header.validated_at is null then
    raise exception 'RMTC validation must be completed before final decision';
  end if;
  if not public.qsms_employee_has_authority(p_approved_by_employee_id,'RMTC_APPROVE') then
    raise exception 'The selected approver does not have RMTC approval authority';
  end if;
  if jsonb_typeof(p_decisions)<>'array' or jsonb_array_length(p_decisions)=0 then
    raise exception 'Select a decision for each covered Part Number';
  end if;

  -- Refresh automated master-validation statuses before applying the controlled decision.
  perform public.qsms_evaluate_rmtc(p_rmtc_id);

  for v_item in select value from jsonb_array_elements(p_decisions)
  loop
    v_part_id:=nullif(v_item->>'part_id','')::uuid;
    v_disposition:=upper(btrim(coalesce(v_item->>'disposition','')));
    v_reason:=nullif(btrim(coalesce(v_item->>'reason','')),'');

    if v_disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED') then
      raise exception 'Invalid RMTC decision for Part %',v_part_id;
    end if;

    select approval_status into v_auto_status
    from public.rmtc_part_approvals
    where rmtc_approval_id=p_rmtc_id and part_id=v_part_id
    for update;

    if v_auto_status is null then raise exception 'Part decision does not belong to the selected RMTC'; end if;
    if v_disposition='ACCEPTED' and v_auto_status<>'APPROVED' then
      raise exception 'Part % failed automated validation. Use Accepted Under Reserve with a reason or Reject it',v_part_id;
    end if;
    if v_disposition in ('ACCEPTED_UNDER_RESERVE','REJECTED') and v_reason is null then
      raise exception 'A reason is mandatory for Accepted Under Reserve or Rejected decisions';
    end if;

    update public.rmtc_part_approvals
       set disposition=v_disposition,
           decision_reason=v_reason,
           decision_at=now(),
           decision_by_employee_id=p_approved_by_employee_id,
           updated_at=now(),updated_by=auth.uid()
     where rmtc_approval_id=p_rmtc_id and part_id=v_part_id;

    v_total:=v_total+1;
    if v_disposition='ACCEPTED' then v_accepted:=v_accepted+1;
    elsif v_disposition='ACCEPTED_UNDER_RESERVE' then v_reserve:=v_reserve+1;
    else v_rejected:=v_rejected+1;
    end if;
  end loop;

  if v_total<>(select count(*) from public.rmtc_part_approvals where rmtc_approval_id=p_rmtc_id) then
    raise exception 'A final decision is required for every covered Part Number';
  end if;

  v_header_disposition:=case
    when v_accepted=0 and v_reserve=0 then 'REJECTED'
    when v_reserve>0 then 'ACCEPTED_UNDER_RESERVE'
    else 'ACCEPTED'
  end;
  v_header_status:=case
    when v_rejected=v_total then 'REJECTED'
    when v_rejected>0 then 'PARTIALLY_APPROVED'
    else 'APPROVED'
  end;

  update public.rmtc_approvals
     set disposition=v_header_disposition,
         disposition_reason=case
           when v_header_disposition='ACCEPTED_UNDER_RESERVE' then 'One or more covered parts accepted under reserve'
           when v_header_disposition='REJECTED' then 'All covered parts rejected'
           else null end,
         decision_at=now(),
         decision_by_employee_id=p_approved_by_employee_id,
         approved_by_employee_id=p_approved_by_employee_id,
         approved_at=now(),approved_by=auth.uid(),
         status=v_header_status,
         rejection_reason=case when v_header_status='REJECTED' then 'All covered Part Numbers were rejected' else null end,
         updated_at=now(),updated_by=auth.uid()
   where id=p_rmtc_id;

  return jsonb_build_object(
    'status',v_header_status,
    'disposition',v_header_disposition,
    'part_count',v_total,
    'accepted',v_accepted,
    'accepted_under_reserve',v_reserve,
    'rejected',v_rejected,
    'decision_at',now()
  );
end;
$$;

revoke all on function public.qsms_decide_rmtc(uuid,jsonb,uuid) from public,anon;
grant execute on function public.qsms_decide_rmtc(uuid,jsonb,uuid) to authenticated;

create or replace function public.enforce_inward_rmtc_link()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  cert public.rmtc_approvals%rowtype;
  part_decision public.rmtc_part_approvals%rowtype;
  already_received numeric;
  allocated_to_batches numeric;
begin
  select * into cert from public.rmtc_approvals where id=new.rmtc_approval_id;
  if cert.id is null then raise exception 'Linked RMTC approval does not exist'; end if;
  if cert.tenant_id<>new.tenant_id then raise exception 'RMTC and inward tenant mismatch'; end if;
  if cert.status not in ('APPROVED','PARTIALLY_APPROVED')
     or cert.disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then
    raise exception 'Material inward is allowed only against an Accepted or Accepted Under Reserve RMTC';
  end if;

  if new.rmtc_part_approval_id is null then
    select * into part_decision
    from public.rmtc_part_approvals
    where rmtc_approval_id=cert.id and part_id=coalesce(new.part_id,cert.part_id)
    limit 1;
  else
    select * into part_decision
    from public.rmtc_part_approvals
    where id=new.rmtc_part_approval_id and rmtc_approval_id=cert.id;
  end if;

  if part_decision.id is null then raise exception 'Select a covered RMTC Part Number'; end if;
  if part_decision.disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then
    raise exception 'The selected RMTC Part Number is not accepted for inward';
  end if;

  new.rmtc_part_approval_id:=part_decision.id;
  new.part_id:=part_decision.part_id;
  new.supplier_id:=cert.supplier_id;
  new.heat_number:=cert.heat_number;
  new.heat_code:=cert.heat_code;
  new.rmtc_disposition:=part_decision.disposition;

  select coalesce(sum(quantity_received),0) into already_received
  from public.inward_lots
  where rmtc_approval_id=cert.id and (new.id is null or id<>new.id);
  if already_received+new.quantity_received>cert.certificate_quantity then
    raise exception 'Material inward quantity exceeds the available RMTC certificate balance';
  end if;

  select coalesce(sum(quantity_started),0) into allocated_to_batches
  from public.production_batches where inward_lot_id=new.id and parent_batch_id is null;
  if allocated_to_batches>new.quantity_accepted then
    raise exception 'Accepted inward quantity cannot be reduced below quantity already allocated to production batches';
  end if;

  if new.receipt_disposition='REJECTED' then
    new.quantity_accepted:=0;
    new.quantity_rejected:=new.quantity_received;
    new.status:='REJECTED';
  elsif new.receipt_disposition='ACCEPTED_UNDER_RESERVE' then
    if nullif(btrim(coalesce(new.reserve_reason,'')),'') is null then
      raise exception 'Reserve reason is mandatory for Accepted Under Reserve inward';
    end if;
    new.status:='HOLD_PENDING_INSPECTION';
  elsif new.receipt_disposition='ACCEPTED' then
    new.quantity_accepted:=case when new.quantity_accepted=0 then new.quantity_received-new.quantity_rejected else new.quantity_accepted end;
    new.status:=case
      when new.metallurgical_status in ('PASS','NOT_REQUIRED')
       and new.dimensional_status in ('PASS','NOT_REQUIRED') then 'RELEASED'
      else 'HOLD_PENDING_INSPECTION' end;
  else
    new.status:='HOLD_PENDING_INSPECTION';
  end if;
  return new;
end;
$$;

create or replace view public.v_qsms_accepted_rmtc_parts
with (security_invoker=true)
as
select
  pa.id as rmtc_part_approval_id,
  pa.tenant_id,
  pa.rmtc_approval_id,
  pa.part_id,
  p.part_number,
  p.part_name,
  r.rmtc_number,
  r.certificate_reference,
  r.certificate_date,
  r.supplier_id,
  supplier.party_name as supplier_name,
  r.steel_mill_id,
  mill.party_name as steel_mill_name,
  r.material_grade_id,
  grade.grade_code as material_grade,
  r.heat_number,
  r.heat_code,
  r.certificate_quantity,
  pa.disposition,
  pa.decision_reason,
  greatest(r.certificate_quantity-coalesce((
    select sum(i.quantity_received) from public.inward_lots i
    where i.rmtc_approval_id=r.id
  ),0),0) as available_quantity
from public.rmtc_part_approvals pa
join public.rmtc_approvals r on r.id=pa.rmtc_approval_id
join public.parts p on p.id=pa.part_id
join public.parties supplier on supplier.id=r.supplier_id
join public.parties mill on mill.id=r.steel_mill_id
left join public.material_grades grade on grade.id=p.material_grade_id
where r.status in ('APPROVED','PARTIALLY_APPROVED')
  and r.disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE')
  and pa.disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE');

grant select on public.v_qsms_accepted_rmtc_parts to authenticated;

create or replace function public.qsms_module_for_table(target_table text)
returns text
language sql
immutable
as $$
  select case
    when target_table in ('parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','document_attachments') then 'PART_MASTER'
    when target_table in ('material_grades','material_grade_elements') then 'MATERIAL_GRADE'
    when target_table in ('parties','part_supplier_links','processes','inspection_stages','quality_assets','jominy_distances','master_value_catalog') then 'REFERENCE_MASTERS'
    when target_table='employees' then 'EMPLOYEE_MASTER'
    when target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results') then 'RMTC_ENTRY'
    when target_table='inward_lots' then 'MATERIAL_INWARD'
    when target_table='user_module_permissions' then 'USER_ACCESS'
    else upper(target_table)
  end;
$$;

create or replace function public.qsms_next_document_number(p_sequence_code text)
returns text
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_tenant uuid:=public.current_tenant_id();
  v_row public.number_sequences%rowtype;
  v_year integer:=extract(year from current_date)::integer;
  v_year_text text;
  v_next bigint;
  v_code text:=upper(btrim(coalesce(p_sequence_code,'')));
begin
  if auth.uid() is null or v_tenant is null then raise exception 'An authenticated QSMS session is required'; end if;
  if v_code='INWARD' then
    if not public.can_write_table('inward_lots') then raise exception 'Your user cannot create Material Inward numbers'; end if;
  elsif not public.can_write_table('rmtc_approvals') then
    raise exception 'Your user cannot create controlled document numbers';
  end if;

  select * into v_row from public.number_sequences
  where tenant_id=v_tenant and upper(sequence_code)=v_code for update;
  if v_row.id is null then raise exception 'Document number sequence % is not configured',p_sequence_code; end if;
  if coalesce(v_row.reset_frequency,'YEARLY')='YEARLY' and coalesce(v_row.last_reset_year,0)<>v_year then
    v_row.current_value:=0;v_row.last_reset_year:=v_year;
  end if;
  v_next:=v_row.current_value+1;
  update public.number_sequences set current_value=v_next,last_reset_year=v_row.last_reset_year,updated_at=now(),updated_by=auth.uid() where id=v_row.id;
  v_year_text:=case upper(coalesce(v_row.year_format,'YYYY')) when 'YY' then right(v_year::text,2) when 'NONE' then null else v_year::text end;
  return concat_ws('-',v_row.prefix,v_year_text,lpad(v_next::text,v_row.padding,'0'));
end;
$$;

commit;
