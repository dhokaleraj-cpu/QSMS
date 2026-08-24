-- QCMS v4.14.1
-- 1) Same Heat Number + different Supplier RMTC Number contributes additional certified steel quantity.
-- 2) MetLAB report sequence uses YY year format.
-- 3) Report approval is performed only by the logged-in employee who has module approval permission.
-- Existing data is preserved; no destructive data reset is performed.
begin;

-- -----------------------------------------------------------------------------
-- HEAT CAPACITY = SUM OF DISTINCT RMTC CERTIFICATE QUANTITIES FOR THE SAME HEAT
-- Heat + Supplier RMTC uniqueness remains protected by QCMS v4.8.6.
-- -----------------------------------------------------------------------------
create or replace function public.enforce_rmtc_heat_identity()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_other_capacity numeric:=0;
  v_projected_capacity numeric:=0;
  v_inward_steel numeric:=0;
  v_remaining_planned numeric:=0;
  v_committed numeric:=0;
begin
  new.normalized_heat_number:=public.qsms_normalize_heat_number(new.heat_number);
  if new.normalized_heat_number='' then raise exception 'Heat Number is required'; end if;
  if coalesce(new.certificate_quantity,0)<=0 then raise exception 'RMTC Certificate Quantity must be greater than zero'; end if;

  select coalesce(sum(coalesce(r.certificate_quantity,0)),0) into v_other_capacity
  from public.rmtc_approvals r
  where r.tenant_id=new.tenant_id
    and r.normalized_heat_number=new.normalized_heat_number
    and r.id<>new.id
    and r.status not in ('REJECTED','SUPERSEDED')
    and coalesce(r.disposition,'PENDING')<>'REJECTED';

  v_projected_capacity:=v_other_capacity + case
    when coalesce(new.status,'DRAFT') in ('REJECTED','SUPERSEDED') or coalesce(new.disposition,'PENDING')='REJECTED' then 0
    else coalesce(new.certificate_quantity,0)
  end;

  select coalesce(sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)),0)
    into v_inward_steel
  from public.inward_lots i
  join public.rmtc_approvals r on r.id=i.rmtc_approval_id
  where r.tenant_id=new.tenant_id
    and r.normalized_heat_number=new.normalized_heat_number;

  select coalesce(sum(greatest(coalesce(pa.planned_steel_quantity_kg,0)-coalesce(part_inward.inward_steel,0),0)),0)
    into v_remaining_planned
  from public.rmtc_part_approvals pa
  join public.rmtc_approvals r on r.id=pa.rmtc_approval_id
  left join lateral (
    select sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)) as inward_steel
    from public.inward_lots i where i.rmtc_part_approval_id=pa.id
  ) part_inward on true
  where r.tenant_id=new.tenant_id
    and r.normalized_heat_number=new.normalized_heat_number
    and r.id<>new.id
    and r.status not in ('REJECTED','SUPERSEDED')
    and coalesce(r.disposition,'PENDING')<>'REJECTED';

  -- DRAFT header edits happen before any inward. Include its saved Part plans when editing.
  if new.id is not null and coalesce(new.status,'DRAFT') not in ('REJECTED','SUPERSEDED') and coalesce(new.disposition,'PENDING')<>'REJECTED' then
    v_remaining_planned:=v_remaining_planned + coalesce((
      select sum(greatest(coalesce(pa.planned_steel_quantity_kg,0)-coalesce(part_inward.inward_steel,0),0))
      from public.rmtc_part_approvals pa
      left join lateral (
        select sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)) as inward_steel
        from public.inward_lots i where i.rmtc_part_approval_id=pa.id
      ) part_inward on true
      where pa.rmtc_approval_id=new.id
    ),0);
  end if;

  v_committed:=v_inward_steel+v_remaining_planned;
  if v_projected_capacity+0.001<v_committed then
    raise exception 'Combined certified Heat quantity % kg cannot be lower than committed Heat steel % kg (Inward % kg + Remaining planned % kg)',
      round(v_projected_capacity,3),round(v_committed,3),round(v_inward_steel,3),round(v_remaining_planned,3);
  end if;
  return new;
end;
$$;

create or replace function public.enforce_rmtc_certificate_production_limit()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_capacity numeric:=0;
  v_inward_steel numeric:=0;
  v_remaining_planned numeric:=0;
  v_committed numeric:=0;
begin
  select coalesce(sum(coalesce(r.certificate_quantity,0)),0)
    into v_capacity
  from public.rmtc_approvals r
  where r.tenant_id=new.tenant_id
    and r.normalized_heat_number=new.normalized_heat_number
    and r.id<>new.id
    and r.status not in ('REJECTED','SUPERSEDED')
    and coalesce(r.disposition,'PENDING')<>'REJECTED';

  -- BEFORE UPDATE still sees the OLD row in the table. Exclude it explicitly, then add
  -- NEW only when the certificate remains active/non-rejected.
  if coalesce(new.status,'DRAFT') not in ('REJECTED','SUPERSEDED') and coalesce(new.disposition,'PENDING')<>'REJECTED' then
    v_capacity:=v_capacity+coalesce(new.certificate_quantity,0);
  end if;

  select coalesce(sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)),0)
    into v_inward_steel
  from public.inward_lots i
  join public.rmtc_approvals r on r.id=i.rmtc_approval_id
  where r.tenant_id=new.tenant_id and r.normalized_heat_number=new.normalized_heat_number;

  select coalesce(sum(greatest(coalesce(pa.planned_steel_quantity_kg,0)-coalesce(part_inward.inward_steel,0),0)),0)
    into v_remaining_planned
  from public.rmtc_part_approvals pa
  join public.rmtc_approvals r on r.id=pa.rmtc_approval_id
  left join lateral (
    select sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)) as inward_steel
    from public.inward_lots i where i.rmtc_part_approval_id=pa.id
  ) part_inward on true
  where r.tenant_id=new.tenant_id and r.normalized_heat_number=new.normalized_heat_number
    and r.status not in ('REJECTED','SUPERSEDED') and coalesce(r.disposition,'PENDING')<>'REJECTED';

  v_committed:=v_inward_steel+v_remaining_planned;
  if v_capacity+0.001<v_committed then
    raise exception 'Combined certified Heat quantity cannot be reduced below committed steel % kg (Inward % kg + Remaining planned % kg)',
      round(v_committed,3),round(v_inward_steel,3),round(v_remaining_planned,3);
  end if;
  return new;
end;
$$;

create or replace function public.enforce_rmtc_part_production_plan()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  header_row public.rmtc_approvals%rowtype;
  source_row public.part_raw_material_details%rowtype;
  global_quantity numeric:=0;
  heat_inward_steel numeric:=0;
  current_part_inward_steel numeric:=0;
  current_part_inward_pieces numeric:=0;
  other_remaining_planned numeric:=0;
  projected_current_remaining numeric:=0;
  projected_commitment numeric:=0;
  planned_pieces numeric:=coalesce(new.planned_production_quantity_pcs,0);
  input_weight numeric;
begin
  select * into header_row from public.rmtc_approvals where id=new.rmtc_approval_id;
  if header_row.id is null then raise exception 'Linked RMTC header does not exist'; end if;

  select coalesce(sum(coalesce(r.certificate_quantity,0)),0) into global_quantity
  from public.rmtc_approvals r
  where r.tenant_id=header_row.tenant_id
    and r.normalized_heat_number=header_row.normalized_heat_number
    and r.status not in ('REJECTED','SUPERSEDED')
    and coalesce(r.disposition,'PENDING')<>'REJECTED';

  select * into source_row from public.part_raw_material_details d
  where d.tenant_id=new.tenant_id and d.part_id=new.part_id and d.supplier_id=header_row.supplier_id and d.status='ACTIVE'
  order by case when d.id=header_row.selected_source_detail_id then 0 else 1 end,d.sequence_no,d.created_at
  limit 1;

  input_weight:=coalesce(new.input_weight_kg,source_row.input_weight_kg,source_row.gross_weight_kg,source_row.forging_weight_kg,0);
  if planned_pieces>0 and input_weight<=0 then
    raise exception 'Input Weight (kg/part) is required in Part Master supplier forging parameters';
  end if;
  new.input_weight_kg:=nullif(input_weight,0);
  new.planned_production_quantity_pcs:=planned_pieces;
  new.planned_steel_quantity_kg:=round(planned_pieces*input_weight,3);

  select coalesce(sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)),0),
         coalesce(sum(coalesce(i.production_quantity_pcs,0)),0)
    into current_part_inward_steel,current_part_inward_pieces
  from public.inward_lots i where i.rmtc_part_approval_id=new.id;

  if planned_pieces<current_part_inward_pieces then
    raise exception 'Planned production quantity cannot be reduced below % pieces already inwarded',current_part_inward_pieces;
  end if;

  select coalesce(sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)),0)
    into heat_inward_steel
  from public.inward_lots i
  join public.rmtc_approvals r on r.id=i.rmtc_approval_id
  where r.tenant_id=header_row.tenant_id and r.normalized_heat_number=header_row.normalized_heat_number;

  select coalesce(sum(greatest(coalesce(pa.planned_steel_quantity_kg,0)-coalesce(part_inward.inward_steel,0),0)),0)
    into other_remaining_planned
  from public.rmtc_part_approvals pa
  join public.rmtc_approvals r on r.id=pa.rmtc_approval_id
  left join lateral (
    select sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)) as inward_steel
    from public.inward_lots i where i.rmtc_part_approval_id=pa.id
  ) part_inward on true
  where r.tenant_id=header_row.tenant_id
    and r.normalized_heat_number=header_row.normalized_heat_number
    and pa.id<>new.id
    and r.status not in ('REJECTED','SUPERSEDED')
    and coalesce(r.disposition,'PENDING')<>'REJECTED';

  projected_current_remaining:=case
    when header_row.status in ('REJECTED','SUPERSEDED') or coalesce(header_row.disposition,'PENDING')='REJECTED' then 0
    else greatest(new.planned_steel_quantity_kg-current_part_inward_steel,0)
  end;
  projected_commitment:=heat_inward_steel+other_remaining_planned+projected_current_remaining;

  if projected_commitment>global_quantity+0.001 then
    raise exception 'Committed Heat steel % kg exceeds combined certified Heat quantity % kg (Inward % kg + Remaining planned % kg)',
      round(projected_commitment,3),round(global_quantity,3),round(heat_inward_steel,3),
      round(other_remaining_planned+projected_current_remaining,3);
  end if;
  return new;
end;
$$;

create or replace function public.enforce_global_heat_inward_limit()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_header public.rmtc_approvals%rowtype;
  v_global_quantity numeric:=0;
  v_inward_steel numeric:=0;
  v_remaining_planned numeric:=0;
  v_committed numeric:=0;
begin
  select * into v_header from public.rmtc_approvals where id=new.rmtc_approval_id;
  if v_header.id is null then return new; end if;

  select coalesce(sum(coalesce(r.certificate_quantity,0)),0) into v_global_quantity
  from public.rmtc_approvals r
  where r.tenant_id=v_header.tenant_id and r.normalized_heat_number=v_header.normalized_heat_number
    and r.status not in ('REJECTED','SUPERSEDED') and coalesce(r.disposition,'PENDING')<>'REJECTED';

  select coalesce(sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)),0)
    into v_inward_steel
  from public.inward_lots i
  join public.rmtc_approvals r on r.id=i.rmtc_approval_id
  where r.tenant_id=v_header.tenant_id and r.normalized_heat_number=v_header.normalized_heat_number;

  select coalesce(sum(greatest(coalesce(pa.planned_steel_quantity_kg,0)-coalesce(part_inward.inward_steel,0),0)),0)
    into v_remaining_planned
  from public.rmtc_part_approvals pa
  join public.rmtc_approvals r on r.id=pa.rmtc_approval_id
  left join lateral (
    select sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)) as inward_steel
    from public.inward_lots i where i.rmtc_part_approval_id=pa.id
  ) part_inward on true
  where r.tenant_id=v_header.tenant_id
    and r.normalized_heat_number=v_header.normalized_heat_number
    and r.status not in ('REJECTED','SUPERSEDED')
    and coalesce(r.disposition,'PENDING')<>'REJECTED';

  v_committed:=v_inward_steel+v_remaining_planned;
  if v_committed>v_global_quantity+0.001 then
    raise exception 'Committed Heat steel % kg exceeds combined certified Heat quantity % kg after Material Inward (Inward % kg + Remaining planned % kg)',
      round(v_committed,3),round(v_global_quantity,3),round(v_inward_steel,3),round(v_remaining_planned,3);
  end if;
  return new;
end;
$$;

create or replace view public.v_qsms_heat_summary with (security_invoker=true) as
with headers as (
  select
    tenant_id,normalized_heat_number,min(heat_number) as heat_number,
    coalesce(sum(coalesce(certificate_quantity,0)) filter(
      where status not in ('REJECTED','SUPERSEDED') and coalesce(disposition,'PENDING')<>'REJECTED'
    ),0) as global_steel_quantity_kg,
    count(distinct id) as rmtc_count,
    count(distinct id) filter(where status in ('REJECTED','SUPERSEDED') or disposition='REJECTED') as rejected_rmtc_count,
    count(distinct id) filter(where status not in ('REJECTED','SUPERSEDED') and coalesce(disposition,'PENDING')<>'REJECTED') as active_rmtc_count,
    max(updated_at) as last_activity_at
  from public.rmtc_approvals
  group by tenant_id,normalized_heat_number
), part_usage as (
  select
    r.tenant_id,r.normalized_heat_number,pa.id as rmtc_part_approval_id,
    coalesce(pa.planned_steel_quantity_kg,0) as planned_steel_quantity_kg,
    coalesce((
      select sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0))
      from public.inward_lots i where i.rmtc_part_approval_id=pa.id
    ),0) as inward_part_steel_quantity_kg
  from public.rmtc_part_approvals pa
  join public.rmtc_approvals r on r.id=pa.rmtc_approval_id
  where r.status not in ('REJECTED','SUPERSEDED') and coalesce(r.disposition,'PENDING')<>'REJECTED'
), plans as (
  select
    tenant_id,normalized_heat_number,
    coalesce(sum(planned_steel_quantity_kg),0) as active_planned_steel_quantity_kg,
    coalesce(sum(greatest(planned_steel_quantity_kg-inward_part_steel_quantity_kg,0)),0) as remaining_planned_steel_quantity_kg
  from part_usage group by tenant_id,normalized_heat_number
), inward as (
  select
    r.tenant_id,r.normalized_heat_number,
    coalesce(sum(coalesce(i.required_steel_quantity_kg,i.steel_quantity_kg,i.quantity_received,0)),0) as inward_steel_quantity_kg
  from public.inward_lots i
  join public.rmtc_approvals r on r.id=i.rmtc_approval_id
  group by r.tenant_id,r.normalized_heat_number
)
select
  h.tenant_id,h.normalized_heat_number,h.heat_number,h.global_steel_quantity_kg,
  h.rmtc_count,h.rejected_rmtc_count,h.active_rmtc_count,
  coalesce(p.active_planned_steel_quantity_kg,0) as active_planned_steel_quantity_kg,
  coalesce(i.inward_steel_quantity_kg,0) as inward_steel_quantity_kg,
  coalesce(p.remaining_planned_steel_quantity_kg,0) as remaining_planned_steel_quantity_kg,
  coalesce(i.inward_steel_quantity_kg,0)+coalesce(p.remaining_planned_steel_quantity_kg,0) as committed_steel_quantity_kg,
  greatest(h.global_steel_quantity_kg-coalesce(i.inward_steel_quantity_kg,0)-coalesce(p.remaining_planned_steel_quantity_kg,0),0) as available_unallocated_steel_quantity_kg,
  greatest(h.global_steel_quantity_kg-coalesce(i.inward_steel_quantity_kg,0)-coalesce(p.remaining_planned_steel_quantity_kg,0),0) as available_steel_quantity_kg,
  h.last_activity_at
from headers h
left join plans p on p.tenant_id=h.tenant_id and p.normalized_heat_number=h.normalized_heat_number
left join inward i on i.tenant_id=h.tenant_id and i.normalized_heat_number=h.normalized_heat_number;

grant select on public.v_qsms_heat_summary to authenticated;
comment on view public.v_qsms_heat_summary is
'QCMS v4.14.1: one Heat Number can contain multiple distinct Supplier RMTC certificates; global certified steel is the sum of active/non-rejected RMTC certificate quantities.';

-- -----------------------------------------------------------------------------
-- METLAB NUMBERING: automatic sequence + YY year.
-- Existing sequence value is retained; only year presentation changes.
-- -----------------------------------------------------------------------------
update public.number_sequences
set year_format='YY', updated_at=now()
where upper(sequence_code)='METLAB_REPORT' and coalesce(year_format,'YYYY')<>'YY';

-- -----------------------------------------------------------------------------
-- APPROVAL IDENTITY: the login profile is resolved to one active Employee.
-- profile_id is preferred; exact email and exact normalized full name are safe fallbacks
-- for legacy Employee rows that predate profile_id linking.
-- -----------------------------------------------------------------------------
create or replace function public.qcms_current_login_employee_id()
returns uuid
language plpgsql
security invoker
set search_path=public,auth
as $$
declare
  v_profile public.profiles%rowtype;
  v_employee_id uuid;
begin
  if auth.uid() is null then return null; end if;
  select * into v_profile from public.profiles where id=auth.uid() and status='ACTIVE';
  if v_profile.id is null then return null; end if;

  select e.id into v_employee_id
  from public.employees e
  where e.tenant_id=v_profile.tenant_id and e.status='ACTIVE'
    and (
      e.profile_id=v_profile.id
      or (coalesce(e.email,'')<>'' and lower(btrim(e.email))=lower(btrim(coalesce(v_profile.email,''))))
      or lower(regexp_replace(btrim(coalesce(e.first_name,'')||' '||coalesce(e.last_name,'')),'\\s+',' ','g'))
         = lower(regexp_replace(btrim(coalesce(v_profile.full_name,'')),'\\s+',' ','g'))
    )
  order by
    case when e.profile_id=v_profile.id then 0
         when lower(btrim(coalesce(e.email,'')))=lower(btrim(coalesce(v_profile.email,''))) then 1
         else 2 end,
    e.created_at
  limit 1;
  return v_employee_id;
end;
$$;

revoke all on function public.qcms_current_login_employee_id() from public,anon;
grant execute on function public.qcms_current_login_employee_id() to authenticated;

create or replace function public.qsms_finalize_dimensional_report(p_report_id uuid,p_disposition text,p_reason text,p_validated_by_employee_id uuid,p_approved_by_employee_id uuid)
returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare
  v_report public.inspection_reports%rowtype;
  v_bad integer;
  v_disposition text:=upper(replace(btrim(coalesce(p_disposition,'')),' ','_'));
  v_login_employee uuid;
begin
  if not public.qsms_has_module_approve('DIMENSIONAL_REPORT') then raise exception 'Dimensional Report approval permission is required'; end if;
  v_login_employee:=public.qcms_current_login_employee_id();
  if v_login_employee is null then raise exception 'Your QCMS login is not linked to an active Employee Master record'; end if;
  if p_approved_by_employee_id is null or p_approved_by_employee_id<>v_login_employee then
    raise exception 'Approved By must be the currently logged-in employee';
  end if;
  if v_disposition not in ('ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED') then raise exception 'Select On Hold, Accepted, Accepted Under Reserve or Rejected'; end if;
  if v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE','REJECTED') and btrim(coalesce(p_reason,''))='' then raise exception 'A hold, reserve or rejection reason is mandatory'; end if;
  select * into v_report from public.inspection_reports where id=p_report_id and tenant_id=public.current_tenant_id() for update;
  if v_report.id is null then raise exception 'Dimensional report was not found'; end if;
  select count(*) into v_bad from public.inspection_results where inspection_report_id=p_report_id and result not in ('PASS','NOT_APPLICABLE');
  if v_disposition='ACCEPTED' and v_bad>0 then raise exception 'Accepted is allowed only when every applicable characteristic passes; use Accepted Under Reserve or Rejected'; end if;
  update public.inspection_reports set disposition=v_disposition,disposition_reason=nullif(btrim(coalesce(p_reason,'')),''),
    validated_by_employee_id=p_validated_by_employee_id,approved_by_employee_id=v_login_employee,validated_at=now(),decision_at=case when v_disposition='ON_HOLD' then null else now() end,
    status=case when v_disposition='ON_HOLD' then 'ON_HOLD' else 'FINAL' end,
    overall_result=case when v_disposition='REJECTED' then 'FAIL' when v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE') then 'HOLD' else 'PASS' end,
    updated_at=now(),updated_by=auth.uid() where id=p_report_id;
  if v_report.osp_job_id is not null then return public.qsms_refresh_osp_quality_gate(v_report.osp_job_id); end if;
  if v_report.inward_lot_id is not null then return public.qsms_refresh_inward_quality_gate(v_report.inward_lot_id); end if;
  return jsonb_build_object('report_id',p_report_id,'status',case when v_disposition='ON_HOLD' then 'ON_HOLD' else 'FINAL' end,'disposition',v_disposition,'approved_by_employee_id',v_login_employee);
end;
$$;

create or replace function public.qsms_finalize_metlab_report(p_report_id uuid,p_disposition text,p_reason text,p_validated_by_employee_id uuid,p_approved_by_employee_id uuid)
returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare
  v_report public.lab_tests%rowtype;
  v_disposition text:=upper(replace(btrim(coalesce(p_disposition,'')),' ','_'));
  v_bad integer:=0;
  v_login_employee uuid;
begin
  if not public.qsms_has_module_approve('METLAB_REPORT') then raise exception 'MetLAB Report approval permission is required'; end if;
  v_login_employee:=public.qcms_current_login_employee_id();
  if v_login_employee is null then raise exception 'Your QCMS login is not linked to an active Employee Master record'; end if;
  if p_approved_by_employee_id is null or p_approved_by_employee_id<>v_login_employee then
    raise exception 'Approved By must be the currently logged-in employee';
  end if;
  if v_disposition not in ('ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED') then raise exception 'Select On Hold, Accepted, Accepted Under Reserve or Rejected'; end if;
  if v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE','REJECTED') and btrim(coalesce(p_reason,''))='' then raise exception 'A hold, reserve or rejection reason is mandatory'; end if;
  select * into v_report from public.lab_tests where id=p_report_id and tenant_id=public.current_tenant_id() for update;
  if v_report.id is null then raise exception 'MetLAB report was not found'; end if;
  select count(*) into v_bad from (
    select coalesce(item->>'result','NOT_EVALUATED') result from jsonb_array_elements(coalesce(v_report.results->'rows','[]'::jsonb)) item
    union all select coalesce(item->>'result','NOT_EVALUATED') from jsonb_array_elements(coalesce(v_report.results->'chemistry_rows','[]'::jsonb)) item
    union all select coalesce(item->>'result','NOT_EVALUATED') from jsonb_array_elements(coalesce(v_report.results->'jominy_rows','[]'::jsonb)) item
    union all select coalesce(item->>'result','NOT_EVALUATED') from jsonb_array_elements(coalesce(v_report.results->'requirement_rows','[]'::jsonb)) item
  ) evaluated where result not in ('PASS','NOT_APPLICABLE');
  if v_disposition='ACCEPTED' and v_bad>0 then
    raise exception 'Accepted is allowed only when every applicable MetLAB result passes; use Accepted Under Reserve or Rejected';
  end if;
  update public.lab_tests set disposition=v_disposition,disposition_reason=nullif(btrim(coalesce(p_reason,'')),''),
    validated_by_employee_id=p_validated_by_employee_id,approved_by_employee_id=v_login_employee,validated_at=now(),decision_at=case when v_disposition='ON_HOLD' then null else now() end,
    status=case when v_disposition='ON_HOLD' then 'ON_HOLD' else 'FINAL' end,
    overall_result=case when v_disposition='REJECTED' then 'FAIL' when v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE') then 'HOLD' else 'PASS' end,
    updated_at=now(),updated_by=auth.uid() where id=p_report_id;
  if v_report.osp_job_id is not null then return public.qsms_refresh_osp_quality_gate(v_report.osp_job_id); end if;
  if v_report.inward_lot_id is not null then return public.qsms_refresh_inward_quality_gate(v_report.inward_lot_id); end if;
  return jsonb_build_object('report_id',p_report_id,'status',case when v_disposition='ON_HOLD' then 'ON_HOLD' else 'FINAL' end,'disposition',v_disposition,'approved_by_employee_id',v_login_employee);
end;
$$;

comment on function public.qsms_finalize_metlab_report(uuid,text,text,uuid,uuid) is
'QCMS v4.14.1: Final Decision is approved only by the logged-in employee with MetLAB module approval permission.';
comment on function public.qsms_finalize_dimensional_report(uuid,text,text,uuid,uuid) is
'QCMS v4.14.1: Final Decision is approved only by the logged-in employee with Dimensional module approval permission.';

commit;
