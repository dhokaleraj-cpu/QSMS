-- QSMS 4.5.0: NA-aware RMTC validation and Material Inward role fallback.
begin;

create or replace function public.can_write_table(target_table text)
returns boolean
language plpgsql
stable
security definer
set search_path=public,auth
as $$
declare role_name text:=coalesce(public.current_app_role(),'VIEWER');
begin
  if role_name='ADMIN' then return true; end if;
  if public.qsms_has_module_write(target_table) then return true; end if;
  if target_table in ('parties','material_grades','material_grade_elements','parts','part_supplier_links','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','processes','inspection_stages','master_value_catalog') then
    return role_name in ('QUALITY_MANAGER','MASTER_DATA');
  elsif target_table in ('employees','quality_assets') then
    return role_name in ('QUALITY_MANAGER','MASTER_DATA','QUALITY_ENGINEER');
  elsif target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results') then
    return role_name in ('QUALITY_MANAGER','METLAB_APPROVER','SQA');
  elsif target_table='inward_lots' then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION');
  end if;
  return false;
end;
$$;

create or replace function public.qsms_evaluate_rmtc(p_rmtc_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_tenant uuid:=public.current_tenant_id();
  v_header public.rmtc_approvals%rowtype;
  v_pa record;
  v_source_status text;v_grade_status text;v_raw_status text;
  v_chemistry_status text;v_jominy_status text;v_requirement_status text;v_approval_status text;
  v_chem_all integer;v_chem_fail integer;v_jominy_total integer;v_jominy_fail integer;
  v_req_total integer;v_req_fail integer;v_part_count integer:=0;v_approved_count integer:=0;
  v_header_chem_all integer;v_header_chem_fail integer;v_summary jsonb;v_di_required boolean;
begin
  if auth.uid() is null or v_tenant is null then raise exception 'An authenticated QSMS session is required'; end if;
  if not public.can_write_table('rmtc_approvals') then raise exception 'Your QSMS user cannot evaluate an RMTC'; end if;
  select * into v_header from public.rmtc_approvals where id=p_rmtc_id and tenant_id=v_tenant for update;
  if v_header.id is null then raise exception 'RMTC record was not found'; end if;

  update public.rmtc_chemistry_results c
  set result=case
      when c.result='NOT_APPLICABLE' then 'NOT_APPLICABLE'
      when c.actual_value is null then 'NOT_EVALUATED'
      when (c.minimum_value is null or c.actual_value>=c.minimum_value)
       and (c.maximum_value is null or c.actual_value<=c.maximum_value) then 'PASS'
      else 'FAIL' end,
      updated_at=now(),updated_by=auth.uid()
  where c.rmtc_approval_id=p_rmtc_id;

  update public.rmtc_jominy_results jr
  set result=case
      when jr.applicability='NOT_APPLICABLE' then 'NOT_APPLICABLE'
      when jr.actual_hrc is null then 'NOT_EVALUATED'
      when exists(
        select 1 from public.part_jominy_requirements req
        where req.part_id=jr.part_id and req.jominy_distance_id=jr.jominy_distance_id and req.status='ACTIVE'
          and (req.minimum_hrc is null or jr.actual_hrc>=req.minimum_hrc)
          and (req.maximum_hrc is null or jr.actual_hrc<=req.maximum_hrc)
      ) then 'PASS' else 'FAIL' end,
      updated_at=now(),updated_by=auth.uid()
  where jr.rmtc_approval_id=p_rmtc_id;

  for v_pa in
    select pa.*,p.material_grade_id from public.rmtc_part_approvals pa
    join public.parts p on p.id=pa.part_id
    where pa.rmtc_approval_id=p_rmtc_id order by p.part_number
  loop
    v_part_count:=v_part_count+1;
    v_grade_status:=case when v_pa.material_grade_id=v_header.material_grade_id then 'PASS' else 'FAIL' end;
    v_source_status:=case when exists(
      select 1 from public.part_supplier_links link
      where link.tenant_id=v_tenant and link.part_id=v_pa.part_id and link.supplier_id=v_header.supplier_id
        and (link.steel_mill_id is null or link.steel_mill_id=v_header.steel_mill_id)
        and link.approved=true and (link.valid_from is null or link.valid_from<=current_date)
        and (link.valid_to is null or link.valid_to>=current_date)
    ) then 'PASS' else 'FAIL' end;
    v_raw_status:=case when exists(
      select 1 from public.part_raw_material_details src
      where src.tenant_id=v_tenant and src.part_id=v_pa.part_id and src.supplier_id=v_header.supplier_id and src.status='ACTIVE'
    ) then 'PASS' else 'FAIL' end;

    select count(*),count(*) filter(where result not in ('PASS','NOT_APPLICABLE'))
      into v_chem_all,v_chem_fail from public.rmtc_chemistry_results
      where rmtc_approval_id=p_rmtc_id and part_id=v_pa.part_id;
    v_chemistry_status:=case when v_chem_all>0 and v_chem_fail=0 then 'PASS' else 'FAIL' end;

    select count(*),count(*) filter(where coalesce(jr.applicability,'APPLICABLE')<>'NOT_APPLICABLE'
      and (jr.id is null or jr.actual_hrc is null or jr.result<>'PASS' or jr.calculated_result not in ('PASS','NOT_APPLICABLE')))
      into v_jominy_total,v_jominy_fail
      from public.part_jominy_requirements req
      left join public.rmtc_jominy_results jr
        on jr.rmtc_approval_id=p_rmtc_id and jr.part_id=v_pa.part_id and jr.jominy_distance_id=req.jominy_distance_id
      where req.part_id=v_pa.part_id and req.status='ACTIVE';
    v_jominy_status:=case when v_jominy_total=0 or v_jominy_fail=0 then 'PASS' else 'FAIL' end;

    select count(*),count(*) filter(where result not in ('PASS','NOT_APPLICABLE'))
      into v_req_total,v_req_fail from public.rmtc_requirement_results rr
      where rr.rmtc_approval_id=p_rmtc_id and rr.part_id=v_pa.part_id
        and rr.requirement_source in ('PART_HEAT_TREATMENT','PART_RMTC');
    v_requirement_status:=case when v_req_total=0 or v_req_fail=0 then 'PASS' else 'FAIL' end;
    select exists(select 1 from public.part_heat_treatment_details h where h.part_id=v_pa.part_id and h.status='ACTIVE' and upper(h.parameter_name) like '%DI%') into v_di_required;
    if v_di_required and (v_pa.actual_di_status not in ('PASS','NOT_APPLICABLE') or v_pa.calculated_di_status not in ('PASS','NOT_APPLICABLE')) then
      v_requirement_status:='FAIL';
    end if;

    v_approval_status:=case when v_source_status='PASS' and v_grade_status='PASS' and v_raw_status='PASS'
      and v_chemistry_status='PASS' and v_jominy_status='PASS' and v_requirement_status='PASS'
      then 'APPROVED' else 'REJECTED' end;
    if v_approval_status='APPROVED' then v_approved_count:=v_approved_count+1; end if;

    update public.rmtc_part_approvals set
      approval_status=v_approval_status,source_status=v_source_status,material_grade_status=v_grade_status,
      raw_material_status=v_raw_status,chemistry_status=v_chemistry_status,jominy_status=v_jominy_status,
      requirement_status=v_requirement_status,
      approval_reason=jsonb_build_object('source',v_source_status,'material_grade',v_grade_status,'raw_material',v_raw_status,'chemistry',v_chemistry_status,'jominy',v_jominy_status,'requirements',v_requirement_status),
      updated_at=now(),updated_by=auth.uid()
    where id=v_pa.id;
  end loop;

  select count(*),count(*) filter(where result not in ('PASS','NOT_APPLICABLE'))
    into v_header_chem_all,v_header_chem_fail from public.rmtc_chemistry_results where rmtc_approval_id=p_rmtc_id;
  v_chemistry_status:=case when v_header_chem_all>0 and v_header_chem_fail=0 then 'PASS' else 'FAIL' end;
  v_summary:=jsonb_build_object('part_count',v_part_count,'approved_part_count',v_approved_count,'rejected_part_count',greatest(v_part_count-v_approved_count,0),'chemistry_status',v_chemistry_status,'chemistry_rows',v_header_chem_all,'evaluated_at',now());

  update public.rmtc_approvals set
    chemistry_compliance=v_chemistry_status,
    chemistry_results=coalesce((select jsonb_object_agg(part_id::text||':'||element,actual_value order by part_id,element) from public.rmtc_chemistry_results where rmtc_approval_id=p_rmtc_id),'{}'::jsonb),
    chemistry_failures=coalesce((select jsonb_agg(jsonb_build_object('part_id',part_id,'element',element,'actual',actual_value,'minimum',minimum_value,'maximum',maximum_value) order by part_id,element) from public.rmtc_chemistry_results where rmtc_approval_id=p_rmtc_id and result not in ('PASS','NOT_APPLICABLE')),'[]'::jsonb),
    validation_result=case when v_part_count>0 and v_approved_count=v_part_count then 'PASS' else 'FAIL' end,
    validation_summary=v_summary,updated_at=now(),updated_by=auth.uid()
  where id=p_rmtc_id;
  return v_summary;
end;
$$;

commit;
