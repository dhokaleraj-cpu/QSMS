-- QSMS 4.8.6 — Supplier RMTC identity and Heat Steel Ledger.
-- The same Heat Number may be used by multiple RMTC records only when the
-- Supplier RMTC Number is different. Global Heat steel quantity remains shared.
begin;

create or replace function public.qsms_normalize_supplier_rmtc_number(p_value text)
returns text
language sql
immutable
set search_path=public
as $$
  select upper(regexp_replace(btrim(coalesce(p_value,'')),'[^A-Za-z0-9]','','g'));
$$;

alter table public.rmtc_approvals
  add column if not exists normalized_supplier_rmtc_number text;

update public.rmtc_approvals
set normalized_supplier_rmtc_number=public.qsms_normalize_supplier_rmtc_number(certificate_reference)
where normalized_supplier_rmtc_number is distinct from public.qsms_normalize_supplier_rmtc_number(certificate_reference);

do $$
begin
  if exists(
    select 1
    from public.rmtc_approvals
    where public.qsms_normalize_supplier_rmtc_number(certificate_reference)<>''
    group by tenant_id,normalized_heat_number,public.qsms_normalize_supplier_rmtc_number(certificate_reference)
    having count(*)>1
  ) then
    raise exception 'Duplicate Heat Number and Supplier RMTC Number records exist. Resolve them before applying QSMS 4.8.6.';
  end if;
end $$;

create unique index if not exists uq_rmtc_heat_supplier_rmtc_number
  on public.rmtc_approvals(tenant_id,normalized_heat_number,normalized_supplier_rmtc_number)
  where normalized_supplier_rmtc_number<>'';

create index if not exists idx_rmtc_supplier_rmtc_number
  on public.rmtc_approvals(tenant_id,normalized_supplier_rmtc_number,created_at desc);

create or replace function public.enforce_rmtc_supplier_rmtc_identity()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
begin
  new.normalized_heat_number:=public.qsms_normalize_heat_number(new.heat_number);
  new.normalized_supplier_rmtc_number:=public.qsms_normalize_supplier_rmtc_number(new.certificate_reference);

  if new.normalized_heat_number='' then
    raise exception 'Heat Number is required';
  end if;
  if new.normalized_supplier_rmtc_number='' then
    raise exception 'Supplier RMTC Number is required';
  end if;
  if exists(
    select 1 from public.rmtc_approvals r
    where r.tenant_id=new.tenant_id
      and r.normalized_heat_number=new.normalized_heat_number
      and r.normalized_supplier_rmtc_number=new.normalized_supplier_rmtc_number
      and r.id<>new.id
  ) then
    raise exception 'Heat Number % already has Supplier RMTC Number %. Enter a different Supplier RMTC Number.',new.heat_number,new.certificate_reference;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_rmtc_supplier_rmtc_identity on public.rmtc_approvals;
create trigger trg_rmtc_supplier_rmtc_identity
before insert or update of heat_number,certificate_reference
on public.rmtc_approvals
for each row execute function public.enforce_rmtc_supplier_rmtc_identity();

-- QSMS 4.8.3 blocked the same Heat + Supplier + Part combination. The revised
-- control is Heat + Supplier RMTC Number, so the same Supplier/Part may be used
-- again when the supplier issues a different RMTC number.
drop trigger if exists trg_heat_part_supplier_duplicate on public.rmtc_part_approvals;

create or replace function public.qsms_save_rmtc_header(p_rmtc_id uuid,p_payload jsonb,p_part_ids uuid[])
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_tenant uuid:=public.current_tenant_id();
  v_id uuid:=p_rmtc_id;
  v_row public.rmtc_approvals%rowtype;
  v_summary jsonb;
  v_created boolean:=false;
  v_rmtc_number text:=btrim(coalesce(p_payload->>'rmtc_number',''));
  v_supplier_rmtc text:=btrim(coalesce(p_payload->>'certificate_reference',''));
  v_heat_number text:=btrim(coalesce(p_payload->>'heat_number',''));
  v_normalized_heat text;
  v_normalized_supplier_rmtc text;
begin
  if auth.uid() is null or v_tenant is null then raise exception 'An authenticated QSMS session is required'; end if;
  if not public.can_write_table('rmtc_approvals') then raise exception 'Your user cannot create or edit RMTC records'; end if;
  if p_part_ids is null or cardinality(p_part_ids)=0 then raise exception 'Select at least one Part Number'; end if;
  if v_rmtc_number='' then raise exception 'QSMS RMTC Number is required'; end if;
  if v_heat_number='' then raise exception 'Heat Number is required'; end if;
  if v_supplier_rmtc='' then raise exception 'Supplier RMTC Number is required'; end if;

  v_normalized_heat:=public.qsms_normalize_heat_number(v_heat_number);
  v_normalized_supplier_rmtc:=public.qsms_normalize_supplier_rmtc_number(v_supplier_rmtc);

  if exists(
    select 1 from public.rmtc_approvals r
    where r.tenant_id=v_tenant
      and r.normalized_heat_number=v_normalized_heat
      and r.normalized_supplier_rmtc_number=v_normalized_supplier_rmtc
      and (v_id is null or r.id<>v_id)
  ) then
    raise exception 'Heat Number % already has Supplier RMTC Number %. Enter a different Supplier RMTC Number.',v_heat_number,v_supplier_rmtc;
  end if;

  if v_id is null then
    select * into v_row from public.rmtc_approvals
     where tenant_id=v_tenant and rmtc_number=v_rmtc_number
     for update;
    if v_row.id is not null then
      if v_row.status<>'DRAFT' then raise exception 'RMTC Number % already exists and is not editable',v_rmtc_number; end if;
      v_id:=v_row.id;
    else
      v_id:=gen_random_uuid();
      insert into public.rmtc_approvals(
        id,tenant_id,rmtc_number,entry_date,certificate_reference,certificate_date,
        part_id,supplier_id,steel_mill_id,material_grade_id,heat_number,heat_code,
        certificate_quantity,chemistry_results,chemistry_compliance,chemistry_failures,
        mechanical_results,status,selected_source_detail_id,rm_section,forging_route,
        prepared_by_employee_id,prepared_at,remarks,normalized_heat_number,normalized_supplier_rmtc_number
      ) values(
        v_id,v_tenant,v_rmtc_number,(p_payload->>'entry_date')::date,
        v_supplier_rmtc,(p_payload->>'certificate_date')::date,
        nullif(p_payload->>'part_id','')::uuid,nullif(p_payload->>'supplier_id','')::uuid,
        nullif(p_payload->>'steel_mill_id','')::uuid,nullif(p_payload->>'material_grade_id','')::uuid,
        v_heat_number,btrim(coalesce(p_payload->>'heat_code','')),
        coalesce((p_payload->>'certificate_quantity')::numeric,0),'{}'::jsonb,'NOT_EVALUATED','[]'::jsonb,
        '{}'::jsonb,'DRAFT',nullif(p_payload->>'selected_source_detail_id','')::uuid,
        nullif(p_payload->>'rm_section',''),nullif(p_payload->>'forging_route',''),
        nullif(p_payload->>'prepared_by_employee_id','')::uuid,
        coalesce(nullif(p_payload->>'prepared_at','')::timestamptz,now()),nullif(p_payload->>'remarks',''),
        v_normalized_heat,v_normalized_supplier_rmtc
      );
      v_created:=true;
    end if;
  else
    select * into v_row from public.rmtc_approvals
     where id=v_id and tenant_id=v_tenant for update;
    if v_row.id is null then raise exception 'RMTC record was not found'; end if;
    if v_row.status<>'DRAFT' then raise exception 'Only a Draft RMTC header can be edited'; end if;
  end if;

  if not v_created then
    update public.rmtc_approvals set
      rmtc_number=v_rmtc_number,
      entry_date=(p_payload->>'entry_date')::date,
      certificate_reference=v_supplier_rmtc,
      normalized_supplier_rmtc_number=v_normalized_supplier_rmtc,
      certificate_date=(p_payload->>'certificate_date')::date,
      part_id=nullif(p_payload->>'part_id','')::uuid,
      supplier_id=nullif(p_payload->>'supplier_id','')::uuid,
      steel_mill_id=nullif(p_payload->>'steel_mill_id','')::uuid,
      material_grade_id=nullif(p_payload->>'material_grade_id','')::uuid,
      heat_number=v_heat_number,
      normalized_heat_number=v_normalized_heat,
      heat_code=btrim(coalesce(p_payload->>'heat_code','')),
      certificate_quantity=coalesce((p_payload->>'certificate_quantity')::numeric,0),
      selected_source_detail_id=nullif(p_payload->>'selected_source_detail_id','')::uuid,
      rm_section=nullif(p_payload->>'rm_section',''),
      forging_route=nullif(p_payload->>'forging_route',''),
      prepared_by_employee_id=nullif(p_payload->>'prepared_by_employee_id','')::uuid,
      prepared_at=coalesce(prepared_at,nullif(p_payload->>'prepared_at','')::timestamptz,now()),
      remarks=nullif(p_payload->>'remarks',''),updated_at=now(),updated_by=auth.uid()
    where id=v_id;
  end if;

  v_summary:=public.qsms_initialize_rmtc_details(v_id,p_part_ids);
  select * into v_row from public.rmtc_approvals where id=v_id;
  return to_jsonb(v_row)||jsonb_build_object('created',v_created,'worksheet_summary',v_summary);
end;
$$;

create or replace view public.v_qsms_heat_steel_ledger with (security_invoker=true) as
select
  u.tenant_id,u.normalized_heat_number,u.heat_number,
  hs.global_steel_quantity_kg,hs.active_planned_steel_quantity_kg,
  hs.inward_steel_quantity_kg as heat_inward_steel_quantity_kg,
  hs.remaining_planned_steel_quantity_kg as heat_remaining_planned_steel_quantity_kg,
  hs.committed_steel_quantity_kg,hs.available_unallocated_steel_quantity_kg as heat_balance_quantity_kg,
  case when hs.committed_steel_quantity_kg<=hs.global_steel_quantity_kg+0.001 then 'VALID' else 'OVER_LIMIT' end as heat_balance_status,
  u.rmtc_approval_id,u.rmtc_number,r.certificate_reference as supplier_rmtc_number,
  r.normalized_supplier_rmtc_number,u.rmtc_status,u.rmtc_disposition,
  u.rmtc_steel_quantity_kg,u.supplier_id,u.supplier_name,
  u.rmtc_part_approval_id,u.part_id,u.part_number,u.part_name,
  u.automated_validation,u.part_disposition,
  u.planned_production_quantity_pcs,u.input_weight_kg,u.planned_steel_quantity_kg,
  u.inward_production_quantity_pcs,u.inward_steel_quantity_kg,
  u.remaining_planned_steel_quantity_kg,u.created_at,u.updated_at
from public.v_qsms_heat_rmtc_usage u
join public.rmtc_approvals r on r.id=u.rmtc_approval_id
join public.v_qsms_heat_summary hs
  on hs.tenant_id=u.tenant_id and hs.normalized_heat_number=u.normalized_heat_number;

grant select on public.v_qsms_heat_steel_ledger to authenticated;
grant execute on function public.qsms_normalize_supplier_rmtc_number(text) to authenticated;

commit;
