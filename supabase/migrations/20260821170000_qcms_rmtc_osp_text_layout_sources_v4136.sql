-- QCMS v4.13.6 — approved RMTC part extension, partial OSP receipts,
-- separate MetLAB OSP vendor, NUMBER/TEXT characteristics and Part Master approved sources.
begin;

-- ---------------------------------------------------------------------------
-- MetLAB: keep the material supplier and OSP vendor as separate controlled refs.
-- ---------------------------------------------------------------------------
alter table public.lab_tests
  add column if not exists osp_vendor_id uuid references public.parties(id);
create index if not exists idx_lab_tests_osp_vendor on public.lab_tests(osp_vendor_id);

-- ---------------------------------------------------------------------------
-- Part Master metallurgy supports numeric and text characteristics.
-- Legacy VARIABLE/ATTRIBUTE rows remain valid for backward compatibility.
-- ---------------------------------------------------------------------------
alter table public.part_metallurgical_requirements
  add column if not exists characteristic_type text not null default 'NUMBER',
  add column if not exists specification_text text;

alter table public.part_metallurgical_requirements
  drop constraint if exists part_metallurgical_limits_check;
alter table public.part_metallurgical_requirements
  drop constraint if exists part_metallurgical_characteristic_type_check;
alter table public.part_metallurgical_requirements
  add constraint part_metallurgical_characteristic_type_check
  check (characteristic_type in ('NUMBER','TEXT','VARIABLE','ATTRIBUTE'));
alter table public.part_metallurgical_requirements
  add constraint part_metallurgical_limits_check
  check (
    (characteristic_type in ('NUMBER','VARIABLE') and (minimum_spec is not null or maximum_spec is not null))
    or
    (characteristic_type in ('TEXT','ATTRIBUTE') and nullif(btrim(coalesce(specification_text,'')),'') is not null)
  );

create or replace function public.enforce_part_metallurgical_requirement()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare v_part public.parts%rowtype;
begin
  select * into v_part from public.parts where id=new.part_id;
  if v_part.id is null then raise exception 'Select a valid Part Number'; end if;
  new.tenant_id:=v_part.tenant_id;
  new.parameter_name:=btrim(coalesce(new.parameter_name,''));
  new.characteristic_type:=upper(btrim(coalesce(new.characteristic_type,'NUMBER')));
  if new.characteristic_type='VARIABLE' then new.characteristic_type:='NUMBER'; end if;
  if new.characteristic_type='ATTRIBUTE' then new.characteristic_type:='TEXT'; end if;
  if new.parameter_name='' then raise exception 'Metallurgical Parameter is required'; end if;
  if new.characteristic_type='TEXT' then
    new.specification_text:=nullif(btrim(coalesce(new.specification_text,'')),'');
    if new.specification_text is null then raise exception 'Text Specification is required for %',new.parameter_name; end if;
    new.minimum_spec:=null; new.maximum_spec:=null;
  else
    new.specification_text:=null;
    if new.minimum_spec is null and new.maximum_spec is null then
      raise exception 'Enter Minimum or Maximum Specification for %',new.parameter_name;
    end if;
    if new.minimum_spec is not null and new.maximum_spec is not null and new.minimum_spec>new.maximum_spec then
      raise exception 'Minimum Specification cannot exceed Maximum Specification for %',new.parameter_name;
    end if;
  end if;
  new.updated_at:=now(); new.updated_by:=auth.uid();
  return new;
end;
$$;

-- OSP process parameter master: accept NUMBER/TEXT in addition to historical names.
alter table public.part_process_parameter_specifications
  drop constraint if exists part_process_parameter_characteristic_type_check;
alter table public.part_process_parameter_specifications
  add constraint part_process_parameter_characteristic_type_check
  check (characteristic_type in ('NUMBER','TEXT','VARIABLE','ATTRIBUTE'));

create or replace function public.enforce_part_process_parameter_genealogy()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare v_group public.part_process_specifications%rowtype;
begin
  select * into v_group from public.part_process_specifications where id=new.process_specification_id;
  if v_group.id is null then raise exception 'Select a valid Part OSP Process specification group'; end if;
  if v_group.inward_type<>'OSP_PROCESS' then raise exception 'OSP parameters can be linked only to an OSP Process specification group'; end if;
  new.tenant_id:=v_group.tenant_id; new.part_id:=v_group.part_id; new.process_id:=v_group.process_id; new.inward_type:='OSP_PROCESS';
  new.parameter_name:=btrim(coalesce(new.parameter_name,''));
  new.characteristic_type:=upper(btrim(coalesce(new.characteristic_type,'NUMBER')));
  if new.characteristic_type='VARIABLE' then new.characteristic_type:='NUMBER'; end if;
  if new.characteristic_type='ATTRIBUTE' then new.characteristic_type:='TEXT'; end if;
  if new.parameter_name='' then raise exception 'OSP inspection Parameter is required'; end if;
  if new.characteristic_type='TEXT' then
    new.specification_text:=nullif(btrim(coalesce(new.specification_text,'')),'');
    if new.specification_text is null then raise exception 'Text Specification is required for Parameter %',new.parameter_name; end if;
    new.minimum_spec:=null; new.maximum_spec:=null;
  else
    new.specification_text:=nullif(btrim(coalesce(new.specification_text,'')),'');
    if new.minimum_spec is null and new.maximum_spec is null and new.specification_text is null then
      raise exception 'Enter Minimum, Maximum or Specification for Parameter %',new.parameter_name;
    end if;
    if new.minimum_spec is not null and new.maximum_spec is not null and new.minimum_spec>new.maximum_spec then
      raise exception 'Minimum specification cannot exceed Maximum specification for Parameter %',new.parameter_name;
    end if;
  end if;
  new.updated_at:=now(); new.updated_by:=auth.uid();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- Generated layouts carry NUMBER/TEXT exactly from Part Master.
-- ---------------------------------------------------------------------------
create or replace function public.qsms_generate_final_metallurgical_layout(p_part_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_tenant uuid:=public.current_tenant_id(); v_part public.parts%rowtype; v_plan public.inspection_plans%rowtype;
  v_plan_number text; v_revision text; v_used boolean:=false; v_count integer:=0;
begin
  if auth.uid() is null or v_tenant is null then raise exception 'An authenticated QCMS session is required'; end if;
  if not public.can_write_table('inspection_plans') or not public.can_write_table('parts') then raise exception 'Part Master and Inspection Layout edit permissions are required'; end if;
  select * into v_part from public.parts where id=p_part_id and tenant_id=v_tenant;
  if v_part.id is null then raise exception 'Select a valid Part Number'; end if;
  select count(*) into v_count from public.part_metallurgical_requirements where part_id=v_part.id and status='ACTIVE';
  if v_count=0 then raise exception 'Add at least one active Metallurgical Requirement'; end if;
  select * into v_plan from public.inspection_plans where tenant_id=v_tenant and part_id=v_part.id and requirement_scope='FINAL_METALLURGICAL' and layout_type='METLAB' order by effective_date desc nulls last,revision desc limit 1;
  if v_plan.id is not null then select exists(select 1 from public.lab_tests where layout_plan_id=v_plan.id) into v_used; end if;
  v_plan_number:=left('FINAL-'||regexp_replace(v_part.part_number,'[^A-Za-z0-9]+','-','g')||'-MET',100);
  if v_plan.id is null or v_used then
    if v_plan.id is not null then
      update public.inspection_plans set status='SUPERSEDED',updated_at=now(),updated_by=auth.uid() where id=v_plan.id;
      begin v_revision:=lpad((coalesce(nullif(regexp_replace(v_plan.revision,'[^0-9]','','g'),''),'0')::integer+1)::text,2,'0'); exception when others then v_revision:='01'; end;
    else v_revision:='00'; end if;
    insert into public.inspection_plans(tenant_id,part_id,process_id,inspection_stage_id,plan_number,revision,effective_date,sample_plan,status,layout_type,layout_name,report_title,format_number,format_revision,default_sample_size,source_template_name,remarks,inward_type,requirement_scope)
    values(v_tenant,v_part.id,null,null,v_plan_number,v_revision,current_date,'1 sample','APPROVED','METLAB',v_part.part_number||' · Final Metallurgical Requirements','FINAL PART METALLURGICAL INSPECTION REPORT',v_plan_number,'00',1,'PART_MASTER_METALLURGICAL_REQUIREMENTS',coalesce(v_part.drawing_number,'Final drawing requirements'),'MATERIAL_INWARD','FINAL_METALLURGICAL') returning * into v_plan;
  else
    update public.inspection_plans set effective_date=current_date,status='APPROVED',layout_name=v_part.part_number||' · Final Metallurgical Requirements',report_title='FINAL PART METALLURGICAL INSPECTION REPORT',source_template_name='PART_MASTER_METALLURGICAL_REQUIREMENTS',remarks=coalesce(v_part.drawing_number,'Final drawing requirements'),inward_type='MATERIAL_INWARD',requirement_scope='FINAL_METALLURGICAL',updated_at=now(),updated_by=auth.uid() where id=v_plan.id returning * into v_plan;
    delete from public.inspection_plan_characteristics where inspection_plan_id=v_plan.id;
  end if;
  insert into public.inspection_plan_characteristics(tenant_id,inspection_plan_id,sequence_no,characteristic_no,characteristic,specification,lower_spec,upper_spec,unit,characteristic_type,checking_method,checking_aid_text,sample_size,report_section,is_mandatory,allow_na,decimal_places,layout_metadata,status)
  select v_tenant,v_plan.id,r.sequence_no,row_number() over(order by r.sequence_no,r.parameter_name)::text,r.parameter_name,
    case when r.characteristic_type in ('TEXT','ATTRIBUTE') then r.specification_text else concat_ws(' ',case when r.minimum_spec is not null then 'Min '||r.minimum_spec end,case when r.maximum_spec is not null then 'Max '||r.maximum_spec end) end,
    case when r.characteristic_type in ('TEXT','ATTRIBUTE') then null else r.minimum_spec end,
    case when r.characteristic_type in ('TEXT','ATTRIBUTE') then null else r.maximum_spec end,
    null,case when r.characteristic_type in ('TEXT','ATTRIBUTE') then 'TEXT' else 'NUMBER' end,null,null,1,'METLAB',true,false,3,
    jsonb_build_object('source','PART_MASTER_METALLURGICAL_REQUIREMENTS','metallurgical_requirement_id',r.id,'part_id',v_part.id,'drawing_number',v_part.drawing_number,'drawing_revision',v_part.drawing_revision),r.status
  from public.part_metallurgical_requirements r where r.part_id=v_part.id and r.status='ACTIVE' order by r.sequence_no,r.parameter_name;
  get diagnostics v_count=row_count;
  return jsonb_build_object('generated',true,'layout_id',v_plan.id,'plan_number',v_plan.plan_number,'revision',v_plan.revision,'characteristics',v_count);
end;
$$;

-- Existing OSP generator already copies characteristic_type. Normalize generated value to NUMBER/TEXT.
create or replace function public.qsms_v4136_characteristic_type(p_value text)
returns text language sql immutable as $$ select case when upper(coalesce(p_value,'')) in ('TEXT','ATTRIBUTE') then 'TEXT' else 'NUMBER' end $$;

-- ---------------------------------------------------------------------------
-- Approved RMTC: add another Part without invalidating already-approved parts.
-- The Header becomes PARTIALLY_APPROVED while the new Part is pending, which
-- preserves inward eligibility for existing accepted covered parts.
-- ---------------------------------------------------------------------------
create or replace function public.qsms_add_part_to_approved_rmtc(p_rmtc_id uuid,p_part_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  tid uuid:=public.current_tenant_id(); h public.rmtc_approvals%rowtype; p public.parts%rowtype; pa public.rmtc_part_approvals%rowtype;
  v_chem integer:=0; v_jom integer:=0; v_req integer:=0; v_req2 integer:=0;
begin
  if auth.uid() is null or tid is null then raise exception 'An authenticated QCMS session is required'; end if;
  if not public.can_write_table('rmtc_approvals') then raise exception 'RMTC edit permission is required'; end if;
  select * into h from public.rmtc_approvals where id=p_rmtc_id and tenant_id=tid for update;
  if h.id is null then raise exception 'RMTC record was not found'; end if;
  if h.status not in ('APPROVED','PARTIALLY_APPROVED') or h.disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then
    raise exception 'Part Numbers can be added only to an Accepted / Accepted Under Reserve approved RMTC';
  end if;
  select * into p from public.parts where id=p_part_id and tenant_id=tid and status='ACTIVE';
  if p.id is null then raise exception 'Select an active Part Number'; end if;
  if p.material_grade_id is distinct from h.material_grade_id then raise exception 'The selected Part Material Grade does not match this RMTC Heat Material Grade'; end if;
  select * into pa from public.rmtc_part_approvals where rmtc_approval_id=h.id and part_id=p.id limit 1;
  if pa.id is not null then return to_jsonb(pa)||jsonb_build_object('already_covered',true); end if;

  insert into public.rmtc_part_approvals(tenant_id,rmtc_approval_id,part_id,approval_status,disposition)
  values(tid,h.id,p.id,'PENDING','PENDING') returning * into pa;

  -- Chemistry is a Heat/RMTC result. Reuse existing actual values for the same element,
  -- but apply the newly-added Part's material-grade limits during evaluation.
  insert into public.rmtc_chemistry_results(
    tenant_id,rmtc_approval_id,part_id,material_grade_element_id,element,minimum_value,maximum_value,
    actual_value,unit,result,remarks
  )
  select tid,h.id,p.id,e.id,e.element,e.minimum,e.maximum,
         src.actual_value,e.unit,'NOT_EVALUATED',src.remarks
  from public.material_grade_elements e
  left join lateral (
    select cr.actual_value,cr.remarks from public.rmtc_chemistry_results cr
    where cr.rmtc_approval_id=h.id and cr.element=e.element and cr.actual_value is not null
    order by cr.updated_at desc limit 1
  ) src on true
  where e.material_grade_id=p.material_grade_id
  on conflict (tenant_id,rmtc_approval_id,part_id,material_grade_element_id) do nothing;
  get diagnostics v_chem=row_count;

  -- Jominy is also Heat/RMTC test data. Reuse any recorded actual/calculated value at the
  -- same distance; the new Part's Jominy bands are still evaluated independently.
  insert into public.rmtc_jominy_results(
    tenant_id,rmtc_approval_id,part_id,jominy_distance_id,distance_label,distance_mm,
    actual_hrc,calculated_hrc,result,calculated_result,applicability,remarks
  )
  select tid,h.id,p.id,d.id,
         case when req.distance_label ilike 'J%' then 'J'||d.distance_label else d.distance_label end,
         d.distance_mm,src.actual_hrc,src.calculated_hrc,'NOT_EVALUATED','NOT_EVALUATED','APPLICABLE',src.remarks
  from public.part_jominy_requirements req
  join public.jominy_distances d on d.id=req.jominy_distance_id
  left join lateral (
    select jr.actual_hrc,jr.calculated_hrc,jr.remarks from public.rmtc_jominy_results jr
    where jr.rmtc_approval_id=h.id and jr.jominy_distance_id=d.id
      and (jr.actual_hrc is not null or jr.calculated_hrc is not null)
    order by jr.updated_at desc limit 1
  ) src on true
  where req.part_id=p.id and req.status='ACTIVE'
  on conflict (tenant_id,rmtc_approval_id,part_id,jominy_distance_id) do nothing;
  get diagnostics v_jom=row_count;

  insert into public.rmtc_requirement_results(
    tenant_id,rmtc_approval_id,part_id,requirement_source,source_requirement_id,
    requirement_code,requirement_name,requirement_value,actual_value,unit,sequence_no,result
  )
  select tid,h.id,p.id,'PART_HEAT_TREATMENT',r.id,
         'HT_'||upper(trim(both '_' from regexp_replace(r.parameter_name,'[^A-Za-z0-9]+','_','g'))),
         r.parameter_name,r.requirement_value,
         (select x.actual_value from public.rmtc_requirement_results x
          where x.rmtc_approval_id=h.id and x.requirement_name=r.parameter_name and nullif(btrim(coalesce(x.actual_value,'')),'') is not null
          order by x.updated_at desc limit 1),
         null,r.sequence_no,'NOT_EVALUATED'
  from public.part_heat_treatment_details r
  where r.part_id=p.id and r.status='ACTIVE';
  get diagnostics v_req=row_count;

  insert into public.rmtc_requirement_results(
    tenant_id,rmtc_approval_id,part_id,requirement_source,source_requirement_id,
    requirement_code,requirement_name,requirement_value,actual_value,unit,sequence_no,result
  )
  select tid,h.id,p.id,'PART_RMTC',r.id,r.requirement_code,r.requirement_name,
         case when r.expected_text is not null then r.expected_text
              when r.minimum_value is not null and r.maximum_value is not null then r.minimum_value::text||' - '||r.maximum_value::text
              when r.minimum_value is not null then 'Minimum '||r.minimum_value::text
              when r.maximum_value is not null then 'Maximum '||r.maximum_value::text end,
         (select x.actual_value from public.rmtc_requirement_results x
          where x.rmtc_approval_id=h.id and x.requirement_code=r.requirement_code and nullif(btrim(coalesce(x.actual_value,'')),'') is not null
          order by x.updated_at desc limit 1),
         r.unit,r.sequence_no,'NOT_EVALUATED'
  from public.part_rmtc_requirements r
  where r.part_id=p.id and r.status='ACTIVE';
  get diagnostics v_req2=row_count; v_req:=v_req+v_req2;

  update public.rmtc_approvals
     set status='PARTIALLY_APPROVED',validation_result='NOT_EVALUATED',updated_at=now(),updated_by=auth.uid()
   where id=h.id;
  return to_jsonb(pa)||jsonb_build_object(
    'already_covered',false,'chemistry_rows',v_chem,'jominy_rows',v_jom,'requirement_rows',v_req,
    'existing_parts_remain_released',true
  );
end;
$$;

create or replace function public.qsms_validate_added_rmtc_part(p_rmtc_id uuid,p_part_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare tid uuid:=public.current_tenant_id(); pa public.rmtc_part_approvals%rowtype; result jsonb;
begin
  if auth.uid() is null or tid is null then raise exception 'An authenticated QCMS session is required'; end if;
  select pa.* into pa from public.rmtc_part_approvals pa join public.rmtc_approvals h on h.id=pa.rmtc_approval_id where pa.rmtc_approval_id=p_rmtc_id and pa.part_id=p_part_id and h.tenant_id=tid;
  if pa.id is null then raise exception 'Covered RMTC Part Number was not found'; end if;
  if pa.worksheet_completed_at is null then raise exception 'Save the Part Worksheet before validation'; end if;
  result:=public.qsms_evaluate_rmtc(p_rmtc_id);
  select * into pa from public.rmtc_part_approvals where rmtc_approval_id=p_rmtc_id and part_id=p_part_id;
  return to_jsonb(pa)||jsonb_build_object('evaluation',result);
end;
$$;

create or replace function public.qsms_decide_added_rmtc_part(p_rmtc_id uuid,p_part_id uuid,p_disposition text,p_reason text,p_approved_by_employee_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  tid uuid:=public.current_tenant_id(); h public.rmtc_approvals%rowtype; pa public.rmtc_part_approvals%rowtype;
  disp text:=upper(btrim(coalesce(p_disposition,''))); accepted_count integer; reserve_count integer; pending_count integer; total_count integer; rejected_count integer;
  new_status text; new_disp text;
begin
  if auth.uid() is null or tid is null then raise exception 'An authenticated QCMS session is required'; end if;
  if not public.can_write_table('rmtc_approvals') then raise exception 'RMTC approval permission is required'; end if;
  if disp not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED','ON_HOLD') then raise exception 'Select a valid final decision'; end if;
  if not public.qsms_employee_has_authority(p_approved_by_employee_id,'RMTC_APPROVE') then raise exception 'Select an active employee with RMTC approval authority'; end if;
  select * into h from public.rmtc_approvals where id=p_rmtc_id and tenant_id=tid for update;
  select * into pa from public.rmtc_part_approvals where rmtc_approval_id=p_rmtc_id and part_id=p_part_id for update;
  if h.id is null or pa.id is null then raise exception 'RMTC or covered Part Number was not found'; end if;
  if pa.worksheet_completed_at is null then raise exception 'Save the Part Worksheet before final decision'; end if;
  if pa.approval_status not in ('APPROVED','REJECTED') then raise exception 'Validate the added Part against masters before final decision'; end if;
  if disp in ('ACCEPTED_UNDER_RESERVE','REJECTED','ON_HOLD') and nullif(btrim(coalesce(p_reason,'')),'') is null then raise exception 'Decision / reserve reason is mandatory'; end if;
  if disp='ACCEPTED' and pa.approval_status<>'APPROVED' and nullif(btrim(coalesce(p_reason,'')),'') is null then raise exception 'Manual acceptance reason is mandatory because automated validation did not pass'; end if;
  update public.rmtc_part_approvals set disposition=disp,decision_reason=nullif(btrim(coalesce(p_reason,'')),''),decision_at=now(),decision_by_employee_id=p_approved_by_employee_id,updated_at=now(),updated_by=auth.uid() where id=pa.id returning * into pa;
  select count(*),count(*) filter(where disposition='ACCEPTED'),count(*) filter(where disposition='ACCEPTED_UNDER_RESERVE'),count(*) filter(where disposition in ('PENDING','ON_HOLD')),count(*) filter(where disposition='REJECTED')
  into total_count,accepted_count,reserve_count,pending_count,rejected_count from public.rmtc_part_approvals where rmtc_approval_id=p_rmtc_id;
  if pending_count>0 then new_status:='PARTIALLY_APPROVED';
  elsif accepted_count+reserve_count=total_count then new_status:='APPROVED';
  elsif accepted_count+reserve_count>0 then new_status:='PARTIALLY_APPROVED';
  else new_status:='REJECTED'; end if;
  if accepted_count+reserve_count>0 then new_disp:=case when reserve_count>0 then 'ACCEPTED_UNDER_RESERVE' else 'ACCEPTED' end;
  elsif pending_count>0 then new_disp:='ON_HOLD'; else new_disp:='REJECTED'; end if;
  update public.rmtc_approvals set status=new_status,disposition=new_disp,decision_by_employee_id=p_approved_by_employee_id,decision_at=now(),updated_at=now(),updated_by=auth.uid() where id=h.id;
  return to_jsonb(pa)||jsonb_build_object('rmtc_status',new_status,'rmtc_disposition',new_disp);
end;
$$;

-- ---------------------------------------------------------------------------
-- OSP partial material inward history. Each receipt is preserved, while osp_jobs
-- continues to carry cumulative quantity and latest receipt fields for compatibility.
-- ---------------------------------------------------------------------------
create table if not exists public.osp_receipts(
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  osp_job_id uuid not null references public.osp_jobs(id) on delete cascade,
  receipt_number text not null,
  receipt_date date not null,
  receipt_challan text not null,
  vendor_invoice_number text not null,
  vendor_invoice_date date not null,
  tc_number text not null,
  tc_date date not null,
  vendor_batch_number text not null,
  quantity_received numeric not null check(quantity_received>0),
  remarks text,
  created_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  unique(tenant_id,receipt_number)
);
create index if not exists idx_osp_receipts_job on public.osp_receipts(osp_job_id,receipt_date,created_at);
alter table public.osp_receipts enable row level security;
drop policy if exists tenant_select on public.osp_receipts; drop policy if exists tenant_insert on public.osp_receipts; drop policy if exists tenant_delete on public.osp_receipts;
create policy tenant_select on public.osp_receipts for select to authenticated using(tenant_id=public.current_tenant_id());
create policy tenant_insert on public.osp_receipts for insert to authenticated with check(tenant_id=public.current_tenant_id() and public.can_write_table('osp_jobs'));
create policy tenant_delete on public.osp_receipts for delete to authenticated using(tenant_id=public.current_tenant_id() and (public.current_app_role()='ADMIN' or public.can_write_table('osp_jobs')));
grant select,insert,delete on public.osp_receipts to authenticated;

create or replace function public.qsms_receive_osp_batch(p_osp_job_id uuid,p_receipt_date date,p_receipt_challan text,p_vendor_invoice_number text,p_vendor_invoice_date date,p_tc_number text,p_tc_date date,p_vendor_batch_number text,p_quantity_received numeric,p_remarks text)
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
 tid uuid:=public.current_tenant_id(); job_row public.osp_jobs%rowtype; receipt_no text; remaining numeric; new_total numeric; receipt_row public.osp_receipts%rowtype;
begin
 if auth.uid() is null or tid is null then raise exception 'An authenticated QCMS session is required'; end if;
 if not public.can_write_table('osp_jobs') then raise exception 'OSP Transactions create/edit permission is required'; end if;
 select * into job_row from public.osp_jobs where id=p_osp_job_id and tenant_id=tid for update;
 if job_row.id is null then raise exception 'OSP Material Out record was not found'; end if;
 if job_row.sample_gate_status not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then raise exception 'OSP inward is blocked until the Sample Dimensional and MetLAB inspections are Accepted or Accepted Under Reserve'; end if;
 remaining:=greatest(coalesce(job_row.quantity_dispatched,0)-coalesce(job_row.quantity_received,0),0);
 if remaining<=0 then raise exception 'The complete OSP dispatched quantity has already been inwarded'; end if;
 if coalesce(p_quantity_received,0)<=0 or p_quantity_received>remaining then raise exception 'OSP inward quantity must be greater than zero and cannot exceed remaining quantity % pieces',remaining; end if;
 if nullif(btrim(coalesce(p_receipt_challan,'')),'') is null or nullif(btrim(coalesce(p_vendor_invoice_number,'')),'') is null or p_vendor_invoice_date is null or nullif(btrim(coalesce(p_tc_number,'')),'') is null or p_tc_date is null or nullif(btrim(coalesce(p_vendor_batch_number,'')),'') is null then raise exception 'Receipt challan, Vendor Invoice Number/Date, TC Number/Date and Vendor Batch Number are mandatory'; end if;
 if job_row.vendor_batch_number is not null and upper(btrim(job_row.vendor_batch_number))<>upper(btrim(p_vendor_batch_number)) then raise exception 'Vendor Batch Number must match the batch validated during the sample inspection'; end if;
 receipt_no:=public.qsms_next_document_number('OSP_RECEIPT');
 insert into public.osp_receipts(tenant_id,osp_job_id,receipt_number,receipt_date,receipt_challan,vendor_invoice_number,vendor_invoice_date,tc_number,tc_date,vendor_batch_number,quantity_received,remarks)
 values(tid,job_row.id,receipt_no,p_receipt_date,btrim(p_receipt_challan),btrim(p_vendor_invoice_number),p_vendor_invoice_date,btrim(p_tc_number),p_tc_date,btrim(p_vendor_batch_number),p_quantity_received,nullif(btrim(coalesce(p_remarks,'')),'')) returning * into receipt_row;
 new_total:=coalesce(job_row.quantity_received,0)+p_quantity_received;
 update public.osp_jobs set receipt_number=receipt_no,receipt_date=p_receipt_date,receipt_challan=btrim(p_receipt_challan),vendor_invoice_number=btrim(p_vendor_invoice_number),vendor_invoice_date=p_vendor_invoice_date,tc_number=btrim(p_tc_number),tc_date=p_tc_date,vendor_batch_number=btrim(p_vendor_batch_number),quantity_received=new_total,quantity_rejected_at_receipt=0,receipt_status=case when new_total>=quantity_dispatched then 'COMPLETE' else 'PARTIAL' end,receipt_quality_disposition='PENDING',inspection_status='PENDING',status='PART_RECEIVED',receipt_remarks=nullif(btrim(coalesce(p_remarks,'')),''),updated_at=now(),updated_by=auth.uid() where id=job_row.id returning * into job_row;
 update public.production_batches set vendor_batch_number=job_row.vendor_batch_number,quantity_available=0,status='HOLD_PENDING_OSP_INSPECTION',updated_at=now(),updated_by=auth.uid() where id=job_row.osp_batch_id;
 insert into public.batch_movements(tenant_id,batch_id,movement_type,from_process_id,to_process_id,quantity,movement_date,reference,remarks) values(tid,job_row.osp_batch_id,'OSP_RECEIPT',job_row.process_id,null,p_quantity_received,p_receipt_date,receipt_no,btrim(p_receipt_challan));
 return to_jsonb(job_row)||jsonb_build_object('current_receipt',to_jsonb(receipt_row),'receipt_quantity',p_quantity_received,'remaining_quantity',greatest(job_row.quantity_dispatched-new_total,0));
end;
$$;

revoke all on function public.qsms_add_part_to_approved_rmtc(uuid,uuid) from public,anon;
revoke all on function public.qsms_validate_added_rmtc_part(uuid,uuid) from public,anon;
revoke all on function public.qsms_decide_added_rmtc_part(uuid,uuid,text,text,uuid) from public,anon;
grant execute on function public.qsms_add_part_to_approved_rmtc(uuid,uuid) to authenticated;
grant execute on function public.qsms_validate_added_rmtc_part(uuid,uuid) to authenticated;
grant execute on function public.qsms_decide_added_rmtc_part(uuid,uuid,text,text,uuid) to authenticated;

comment on function public.qsms_add_part_to_approved_rmtc(uuid,uuid) is 'QCMS v4.13.6: extend an accepted RMTC to another compatible Part without blocking already-approved Part usage.';
comment on table public.osp_receipts is 'QCMS v4.13.6: partial OSP vendor receipts retained as transaction history.';

commit;
