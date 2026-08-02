-- QSMS 4.7.1: calculated Jominy distance, reusable grid values and complete disposition choices.
begin;

create or replace function public.qsms_sync_jominy_distance()
returns trigger
language plpgsql
set search_path = public, auth
as $$
begin
  if new.distance_16th is null or new.distance_16th < 1 or new.distance_16th > 16 then
    raise exception 'Jominy distance must be between 1/16 and 16/16 inch';
  end if;
  new.distance_label := new.distance_16th::text || '/16"';
  new.distance_mm := round((new.distance_16th::numeric * 25.4::numeric) / 16::numeric, 2);
  return new;
end;
$$;

drop trigger if exists trg_sync_jominy_distance on public.jominy_distances;
create trigger trg_sync_jominy_distance
before insert or update of distance_16th, distance_label, distance_mm
on public.jominy_distances
for each row execute function public.qsms_sync_jominy_distance();

update public.jominy_distances set distance_16th = distance_16th;

create or replace function public.qsms_sync_part_jominy_distance()
returns trigger
language plpgsql
set search_path = public, auth
as $$
declare d public.jominy_distances%rowtype;
begin
  if new.jominy_distance_id is not null then
    select * into d from public.jominy_distances
     where id=new.jominy_distance_id and tenant_id=new.tenant_id;
  elsif nullif(btrim(coalesce(new.distance_label,'')),'') is not null then
    select * into d from public.jominy_distances
     where tenant_id=new.tenant_id and distance_label=btrim(new.distance_label);
  end if;
  if d.id is null then raise exception 'Select a valid Jominy distance in inches'; end if;
  new.jominy_distance_id := d.id;
  new.distance_label := d.distance_label;
  return new;
end;
$$;

drop trigger if exists trg_sync_part_jominy_distance on public.part_jominy_requirements;
create trigger trg_sync_part_jominy_distance
before insert or update of jominy_distance_id, distance_label
on public.part_jominy_requirements
for each row execute function public.qsms_sync_part_jominy_distance();

update public.part_jominy_requirements r
set jominy_distance_id=d.id, distance_label=d.distance_label
from public.jominy_distances d
where r.tenant_id=d.tenant_id and r.distance_label=d.distance_label;

insert into public.master_value_catalog(tenant_id,field_key,value_text)
select distinct tenant_id,'part.rm_section',btrim(section_size)
from public.part_raw_material_details where nullif(btrim(coalesce(section_size,'')),'') is not null
on conflict (tenant_id,field_key,normalized_value) do update
set usage_count=public.master_value_catalog.usage_count+1,last_used_at=now(),status='ACTIVE',updated_at=now();

insert into public.master_value_catalog(tenant_id,field_key,value_text)
select distinct tenant_id,'part.forging_route',btrim(forging_route)
from public.part_raw_material_details where nullif(btrim(coalesce(forging_route,'')),'') is not null
on conflict (tenant_id,field_key,normalized_value) do update
set usage_count=public.master_value_catalog.usage_count+1,last_used_at=now(),status='ACTIVE',updated_at=now();

insert into public.master_value_catalog(tenant_id,field_key,value_text)
select distinct tenant_id,'part.heat_parameter',btrim(parameter_name)
from public.part_heat_treatment_details where nullif(btrim(coalesce(parameter_name,'')),'') is not null
on conflict (tenant_id,field_key,normalized_value) do update
set usage_count=public.master_value_catalog.usage_count+1,last_used_at=now(),status='ACTIVE',updated_at=now();

insert into public.master_value_catalog(tenant_id,field_key,value_text)
select distinct tenant_id,'part.heat_requirement',btrim(requirement_value)
from public.part_heat_treatment_details where nullif(btrim(coalesce(requirement_value,'')),'') is not null
on conflict (tenant_id,field_key,normalized_value) do update
set usage_count=public.master_value_catalog.usage_count+1,last_used_at=now(),status='ACTIVE',updated_at=now();

alter table public.rmtc_approvals drop constraint if exists rmtc_approvals_disposition_check;
alter table public.rmtc_approvals add constraint rmtc_approvals_disposition_check
check(disposition in ('PENDING','ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED'));
alter table public.rmtc_part_approvals drop constraint if exists rmtc_part_approvals_disposition_check;
alter table public.rmtc_part_approvals add constraint rmtc_part_approvals_disposition_check
check(disposition in ('PENDING','ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED'));
alter table public.inward_lots drop constraint if exists inward_lots_receipt_disposition_check;
alter table public.inward_lots add constraint inward_lots_receipt_disposition_check
check(receipt_disposition in ('PENDING','ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED'));
alter table public.inward_lots drop constraint if exists inward_lots_quality_disposition_check;
alter table public.inward_lots add constraint inward_lots_quality_disposition_check
check(quality_disposition in ('PENDING','ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED'));
alter table public.inspection_reports drop constraint if exists inspection_reports_disposition_check;
alter table public.inspection_reports add constraint inspection_reports_disposition_check
check(disposition in ('PENDING','ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED'));
alter table public.lab_tests drop constraint if exists lab_tests_disposition_check;
alter table public.lab_tests add constraint lab_tests_disposition_check
check(disposition in ('PENDING','ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED'));

create or replace function public.qsms_decide_rmtc(p_rmtc_id uuid, p_decisions jsonb, p_approved_by_employee_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_header public.rmtc_approvals%rowtype; v_role text:=public.current_app_role(); v_item jsonb;
  v_part_id uuid; v_disposition text; v_reason text; v_auto_status text;
  v_total integer:=0; v_accepted integer:=0; v_reserve integer:=0; v_rejected integer:=0;
  v_pending integer:=0; v_hold integer:=0; v_header_disposition text; v_header_status text; v_is_final boolean:=false;
begin
  if v_role not in ('ADMIN','QUALITY_MANAGER','METLAB_APPROVER') and not exists(
    select 1 from public.user_module_permissions p where p.profile_id=auth.uid()
      and p.tenant_id=public.current_tenant_id() and p.module_key='RMTC_ENTRY' and p.can_approve=true
  ) then raise exception 'Your user does not have RMTC approval permission'; end if;
  select * into v_header from public.rmtc_approvals where id=p_rmtc_id and tenant_id=public.current_tenant_id() for update;
  if v_header.id is null then raise exception 'RMTC record was not found'; end if;
  if v_header.status<>'APPROVAL_PENDING' then raise exception 'RMTC must be approval pending before decision'; end if;
  if v_header.validated_at is null then raise exception 'RMTC validation must be completed before decision'; end if;
  if not public.qsms_employee_has_authority(p_approved_by_employee_id,'RMTC_APPROVE') then raise exception 'The selected approver does not have RMTC approval authority'; end if;
  if jsonb_typeof(p_decisions)<>'array' or jsonb_array_length(p_decisions)=0 then raise exception 'Select a decision for each covered Part Number'; end if;
  perform public.qsms_evaluate_rmtc(p_rmtc_id);
  for v_item in select value from jsonb_array_elements(p_decisions) loop
    v_part_id:=nullif(v_item->>'part_id','')::uuid;
    v_disposition:=upper(replace(btrim(coalesce(v_item->>'disposition','')),' ','_'));
    v_reason:=nullif(btrim(coalesce(v_item->>'reason','')),'');
    if v_disposition not in ('PENDING','ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED') then raise exception 'Invalid RMTC decision for Part %',v_part_id; end if;
    select approval_status into v_auto_status from public.rmtc_part_approvals where rmtc_approval_id=p_rmtc_id and part_id=v_part_id for update;
    if v_auto_status is null then raise exception 'Part decision does not belong to the selected RMTC'; end if;
    if v_disposition='ACCEPTED' and v_auto_status<>'APPROVED' then raise exception 'Part % failed automated validation. Use Accepted Under Reserve, On Hold or Reject it',v_part_id; end if;
    if v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE','REJECTED') and v_reason is null then raise exception 'A reason is mandatory for On Hold, Accepted Under Reserve or Rejected decisions'; end if;
    update public.rmtc_part_approvals set disposition=v_disposition,decision_reason=v_reason,
      decision_at=case when v_disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED') then now() else null end,
      decision_by_employee_id=p_approved_by_employee_id,updated_at=now(),updated_by=auth.uid()
    where rmtc_approval_id=p_rmtc_id and part_id=v_part_id;
    v_total:=v_total+1;
    case v_disposition when 'ACCEPTED' then v_accepted:=v_accepted+1;
      when 'ACCEPTED_UNDER_RESERVE' then v_reserve:=v_reserve+1;
      when 'REJECTED' then v_rejected:=v_rejected+1;
      when 'ON_HOLD' then v_hold:=v_hold+1;
      else v_pending:=v_pending+1; end case;
  end loop;
  if v_total<>(select count(*) from public.rmtc_part_approvals where rmtc_approval_id=p_rmtc_id) then raise exception 'A decision row is required for every covered Part Number'; end if;
  if v_pending>0 then v_header_disposition:='PENDING'; v_header_status:='APPROVAL_PENDING';
  elsif v_hold>0 then v_header_disposition:='ON_HOLD'; v_header_status:='APPROVAL_PENDING';
  else
    v_is_final:=true;
    v_header_disposition:=case when v_accepted=0 and v_reserve=0 then 'REJECTED' when v_reserve>0 then 'ACCEPTED_UNDER_RESERVE' else 'ACCEPTED' end;
    v_header_status:=case when v_rejected=v_total then 'REJECTED' when v_rejected>0 then 'PARTIALLY_APPROVED' else 'APPROVED' end;
  end if;
  update public.rmtc_approvals set disposition=v_header_disposition,
    disposition_reason=case when v_header_disposition='ON_HOLD' then 'One or more covered parts are On Hold'
      when v_header_disposition='ACCEPTED_UNDER_RESERVE' then 'One or more covered parts accepted under reserve'
      when v_header_disposition='REJECTED' then 'All covered parts rejected' else null end,
    decision_at=case when v_is_final then now() else null end,decision_by_employee_id=p_approved_by_employee_id,
    approved_by_employee_id=p_approved_by_employee_id,approved_at=case when v_is_final then now() else null end,
    approved_by=case when v_is_final then auth.uid() else null end,status=v_header_status,
    rejection_reason=case when v_header_status='REJECTED' then 'All covered Part Numbers were rejected' else null end,
    updated_at=now(),updated_by=auth.uid() where id=p_rmtc_id;
  return jsonb_build_object('status',v_header_status,'disposition',v_header_disposition,'part_count',v_total,
    'pending',v_pending,'on_hold',v_hold,'accepted',v_accepted,'accepted_under_reserve',v_reserve,'rejected',v_rejected,'finalized',v_is_final);
end;
$$;

create or replace function public.qsms_finalize_dimensional_report(p_report_id uuid,p_disposition text,p_reason text,p_validated_by_employee_id uuid,p_approved_by_employee_id uuid)
returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare v_report public.inspection_reports%rowtype; v_bad integer; v_disposition text:=upper(replace(btrim(coalesce(p_disposition,'')),' ','_'));
begin
  if not public.qsms_has_module_approve('DIMENSIONAL_REPORT') then raise exception 'Dimensional Report approval permission is required'; end if;
  if v_disposition not in ('ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED') then raise exception 'Select On Hold, Accepted, Accepted Under Reserve or Rejected'; end if;
  if v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE','REJECTED') and btrim(coalesce(p_reason,''))='' then raise exception 'A hold, reserve or rejection reason is mandatory'; end if;
  select * into v_report from public.inspection_reports where id=p_report_id and tenant_id=public.current_tenant_id() for update;
  if v_report.id is null then raise exception 'Dimensional report was not found'; end if;
  select count(*) into v_bad from public.inspection_results where inspection_report_id=p_report_id and result not in ('PASS','NOT_APPLICABLE');
  if v_disposition='ACCEPTED' and v_bad>0 then raise exception 'Accepted is allowed only when every applicable characteristic passes'; end if;
  update public.inspection_reports set disposition=v_disposition,disposition_reason=nullif(btrim(coalesce(p_reason,'')),''),
    validated_by_employee_id=p_validated_by_employee_id,approved_by_employee_id=p_approved_by_employee_id,validated_at=now(),decision_at=now(),
    status=case when v_disposition='ON_HOLD' then 'ON_HOLD' else 'FINAL' end,
    overall_result=case when v_disposition='REJECTED' then 'FAIL' when v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE') then 'HOLD' else 'PASS' end,
    updated_at=now(),updated_by=auth.uid() where id=p_report_id;
  return public.qsms_refresh_inward_quality_gate(v_report.inward_lot_id);
end; $$;

create or replace function public.qsms_finalize_metlab_report(p_report_id uuid,p_disposition text,p_reason text,p_validated_by_employee_id uuid,p_approved_by_employee_id uuid)
returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare v_report public.lab_tests%rowtype; v_disposition text:=upper(replace(btrim(coalesce(p_disposition,'')),' ','_')); v_bad integer:=0;
begin
  if not public.qsms_has_module_approve('METLAB_REPORT') then raise exception 'MetLAB Report approval permission is required'; end if;
  if v_disposition not in ('ON_HOLD','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED') then raise exception 'Select On Hold, Accepted, Accepted Under Reserve or Rejected'; end if;
  if v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE','REJECTED') and btrim(coalesce(p_reason,''))='' then raise exception 'A hold, reserve or rejection reason is mandatory'; end if;
  select * into v_report from public.lab_tests where id=p_report_id and tenant_id=public.current_tenant_id() for update;
  if v_report.id is null then raise exception 'MetLAB report was not found'; end if;
  select count(*) into v_bad from jsonb_array_elements(coalesce(v_report.results->'rows','[]'::jsonb)) row_item
    where coalesce(row_item->>'result','NOT_EVALUATED') not in ('PASS','NOT_APPLICABLE');
  if v_disposition='ACCEPTED' and v_bad>0 then raise exception 'Accepted is allowed only when every applicable test result passes'; end if;
  update public.lab_tests set disposition=v_disposition,disposition_reason=nullif(btrim(coalesce(p_reason,'')),''),
    validated_by_employee_id=p_validated_by_employee_id,approved_by_employee_id=p_approved_by_employee_id,validated_at=now(),decision_at=now(),
    status=case when v_disposition='ON_HOLD' then 'ON_HOLD' else 'FINAL' end,
    overall_result=case when v_disposition='REJECTED' then 'FAIL' when v_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE') then 'HOLD' else 'PASS' end,
    updated_at=now(),updated_by=auth.uid() where id=p_report_id;
  return public.qsms_refresh_inward_quality_gate(v_report.inward_lot_id);
end; $$;

create or replace function public.qsms_refresh_inward_quality_gate(p_inward_id uuid)
returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare v_inward public.inward_lots%rowtype; v_dim text:='PENDING'; v_dim_reason text; v_met text:='PENDING'; v_met_reason text;
  v_quality text:='PENDING'; v_status text:='HOLD_PENDING_INSPECTION'; v_met_status text:='PENDING'; v_dim_status text:='PENDING'; v_reason text;
begin
  select * into v_inward from public.inward_lots where id=p_inward_id for update;
  if v_inward.id is null then raise exception 'Material Inward record was not found'; end if;
  select disposition,disposition_reason into v_dim,v_dim_reason from public.inspection_reports
    where inward_lot_id=p_inward_id and report_type='DIMENSIONAL' and status in ('FINAL','ON_HOLD') order by decision_at desc nulls last,updated_at desc limit 1;
  v_dim:=coalesce(v_dim,'PENDING');
  select disposition,disposition_reason into v_met,v_met_reason from public.lab_tests
    where inward_lot_id=p_inward_id and test_type='METLAB' and status in ('FINAL','ON_HOLD') order by decision_at desc nulls last,updated_at desc limit 1;
  v_met:=coalesce(v_met,'PENDING');
  v_dim_status:=case v_dim when 'ACCEPTED' then 'PASS' when 'ACCEPTED_UNDER_RESERVE' then 'HOLD' when 'ON_HOLD' then 'HOLD' when 'REJECTED' then 'FAIL' else 'PENDING' end;
  v_met_status:=case v_met when 'ACCEPTED' then 'PASS' when 'ACCEPTED_UNDER_RESERVE' then 'HOLD' when 'ON_HOLD' then 'HOLD' when 'REJECTED' then 'FAIL' else 'PENDING' end;
  if v_dim='REJECTED' or v_met='REJECTED' then v_quality:='REJECTED';v_status:='REJECTED';
  elsif v_dim in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') and v_met in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then
    v_quality:=case when v_dim='ACCEPTED_UNDER_RESERVE' or v_met='ACCEPTED_UNDER_RESERVE' then 'ACCEPTED_UNDER_RESERVE' else 'ACCEPTED' end;v_status:='RELEASED';
  elsif v_dim='ON_HOLD' or v_met='ON_HOLD' then v_quality:='ON_HOLD';v_status:='HOLD_PENDING_INSPECTION';
  end if;
  v_reason:=nullif(concat_ws(' | ',case when v_met in ('ON_HOLD','ACCEPTED_UNDER_RESERVE','REJECTED') then 'MetLAB: '||coalesce(v_met_reason,'') end,
    case when v_dim in ('ON_HOLD','ACCEPTED_UNDER_RESERVE','REJECTED') then 'Dimensional: '||coalesce(v_dim_reason,'') end),'');
  update public.inward_lots set metallurgical_status=v_met_status,dimensional_status=v_dim_status,quality_disposition=v_quality,quality_reason=v_reason,status=v_status,
    released_at=case when v_status='RELEASED' then coalesce(released_at,now()) else null end,updated_at=now(),updated_by=auth.uid() where id=p_inward_id;
  return jsonb_build_object('inward_id',p_inward_id,'metlab_disposition',v_met,'dimensional_disposition',v_dim,'quality_disposition',v_quality,'status',v_status,'quality_reason',v_reason);
end; $$;

create or replace function public.enforce_inward_rmtc_link()
returns trigger language plpgsql security definer set search_path=public,auth as $$
declare cert public.rmtc_approvals%rowtype; part_decision public.rmtc_part_approvals%rowtype; already_received numeric; allocated_to_batches numeric;
begin
  select * into cert from public.rmtc_approvals where id=new.rmtc_approval_id;
  if cert.id is null then raise exception 'Linked RMTC approval does not exist'; end if;
  if cert.tenant_id<>new.tenant_id then raise exception 'RMTC and inward tenant mismatch'; end if;
  if cert.status not in ('APPROVED','PARTIALLY_APPROVED') or cert.disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then raise exception 'Material inward is allowed only against an Accepted or Accepted Under Reserve RMTC'; end if;
  if new.rmtc_part_approval_id is null then select * into part_decision from public.rmtc_part_approvals where rmtc_approval_id=cert.id and part_id=coalesce(new.part_id,cert.part_id) limit 1;
  else select * into part_decision from public.rmtc_part_approvals where id=new.rmtc_part_approval_id and rmtc_approval_id=cert.id; end if;
  if part_decision.id is null then raise exception 'Select a covered RMTC Part Number'; end if;
  if part_decision.disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then raise exception 'The selected RMTC Part Number is not accepted for inward'; end if;
  new.rmtc_part_approval_id:=part_decision.id;new.part_id:=part_decision.part_id;new.supplier_id:=cert.supplier_id;new.heat_number:=cert.heat_number;new.heat_code:=cert.heat_code;new.rmtc_disposition:=part_decision.disposition;
  select coalesce(sum(quantity_received),0) into already_received from public.inward_lots where rmtc_approval_id=cert.id and (new.id is null or id<>new.id);
  if already_received+new.quantity_received>cert.certificate_quantity then raise exception 'Material inward quantity exceeds the available RMTC certificate balance'; end if;
  select coalesce(sum(quantity_started),0) into allocated_to_batches from public.production_batches where inward_lot_id=new.id and parent_batch_id is null;
  if allocated_to_batches>new.quantity_accepted then raise exception 'Accepted inward quantity cannot be reduced below quantity already allocated to production batches'; end if;
  if new.receipt_disposition='REJECTED' then new.quantity_accepted:=0;new.quantity_rejected:=new.quantity_received;new.status:='REJECTED';
  elsif new.receipt_disposition in ('ON_HOLD','ACCEPTED_UNDER_RESERVE') then
    if nullif(btrim(coalesce(new.reserve_reason,'')),'') is null then raise exception 'Reason is mandatory for On Hold or Accepted Under Reserve inward'; end if;
    new.status:='HOLD_PENDING_INSPECTION';
  elsif new.receipt_disposition='ACCEPTED' then
    new.quantity_accepted:=case when new.quantity_accepted=0 then new.quantity_received-new.quantity_rejected else new.quantity_accepted end;
    new.status:=case when new.metallurgical_status in ('PASS','NOT_REQUIRED') and new.dimensional_status in ('PASS','NOT_REQUIRED') then 'RELEASED' else 'HOLD_PENDING_INSPECTION' end;
  else new.status:='HOLD_PENDING_INSPECTION'; end if;
  return new;
end; $$;

commit;
