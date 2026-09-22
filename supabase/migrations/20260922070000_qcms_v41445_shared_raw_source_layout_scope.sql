-- QCMS v4.14.45 — shared raw forging/casting source + controlled layout identity.
-- Additive migration. Existing production/master/quality/supply-chain records are preserved.

begin;

-- -----------------------------------------------------------------------------
-- 1) A finished Part may explicitly consume the raw forging/casting of another
--    Part Master record. This is an identity/genealogy link, not a duplicate Part.
-- -----------------------------------------------------------------------------
alter table public.part_raw_material_details
  add column if not exists source_part_id uuid references public.parts(id) on delete restrict;

create index if not exists idx_qcms_part_raw_source_part
  on public.part_raw_material_details(tenant_id, source_part_id, supplier_id, status)
  where source_part_id is not null;

comment on column public.part_raw_material_details.source_part_id is
  'QCMS v4.14.45 optional Source Raw Forging / Casting Part. For Forging/Casting only, links a finished Part raw-material row to another Part Master whose common raw forging/casting is consumed. Finished-Part genealogy remains on the target Part.';

create or replace function public.qcms_guard_raw_source_part()
returns trigger
language plpgsql
security definer
set search_path=public,auth,pg_catalog
as $$
declare
  v_target_tenant uuid;
  v_source_tenant uuid;
  v_source_status text;
begin
  if new.source_part_id is null then
    return new;
  end if;

  if new.part_id is null then
    raise exception 'Target Part is required before selecting Source Raw Forging / Casting Part';
  end if;
  if new.source_part_id = new.part_id then
    raise exception 'Source Raw Forging / Casting Part must be a different Part Master record';
  end if;
  if lower(btrim(coalesce(new.material_section_name,''))) not in ('forging','casting') then
    raise exception 'Source Raw Forging / Casting Part can be used only for Raw Material Type Forging or Casting';
  end if;

  select tenant_id into v_target_tenant from public.parts where id=new.part_id;
  select tenant_id,status into v_source_tenant,v_source_status from public.parts where id=new.source_part_id;
  if v_target_tenant is null then
    raise exception 'Target Part Master record is invalid';
  end if;
  if v_source_tenant is null then
    raise exception 'Source Raw Forging / Casting Part Master record is invalid';
  end if;
  if v_source_tenant <> v_target_tenant then
    raise exception 'Source Raw Forging / Casting Part must belong to the same tenant';
  end if;
  if upper(coalesce(v_source_status,'ACTIVE')) <> 'ACTIVE' then
    raise exception 'Source Raw Forging / Casting Part must be ACTIVE';
  end if;

  -- Stop A -> B -> ... -> A loops. UNION (not UNION ALL) also terminates safely
  -- if historical data already contains a repeated branch.
  if exists(
    with recursive source_chain(part_id) as (
      select new.source_part_id
      union
      select d.source_part_id
      from public.part_raw_material_details d
      join source_chain c on d.part_id=c.part_id
      where d.source_part_id is not null
        and upper(coalesce(d.status,'ACTIVE'))='ACTIVE'
        and (new.id is null or d.id<>new.id)
    )
    select 1 from source_chain where part_id=new.part_id
  ) then
    raise exception 'Source Raw Forging / Casting Part creates a circular Part genealogy';
  end if;

  return new;
end;
$$;

drop trigger if exists trg_qcms_guard_raw_source_part on public.part_raw_material_details;
create trigger trg_qcms_guard_raw_source_part
before insert or update of part_id,source_part_id,material_section_name,status
on public.part_raw_material_details
for each row execute function public.qcms_guard_raw_source_part();

-- Price history remains intentionally Part-scoped. Equal numeric rates are valid
-- on different Part Master records. The existing unique index is identity/date
-- based and deliberately does NOT include the price value.
comment on table public.part_supplier_price_history is
  'QCMS v4.14.45 supplier + Part price history. The same commercial rate/value is explicitly allowed on different Part Master records; overlap control remains scoped to Supplier + Part + UOM/date.';

-- -----------------------------------------------------------------------------
-- 2) One CURRENT layout per controlled Part/Stage/Process/type scope.
--    Historical layouts are retained by changing duplicate current rows to
--    SUPERSEDED. Auto-generated FINAL_METALLURGICAL plans remain outside this rule.
-- -----------------------------------------------------------------------------
with ranked as (
  select p.id,
         row_number() over (
           partition by p.tenant_id,
                        p.part_id,
                        coalesce(p.process_id,'00000000-0000-0000-0000-000000000000'::uuid),
                        coalesce(p.inspection_stage_id,'00000000-0000-0000-0000-000000000000'::uuid),
                        upper(coalesce(p.layout_type,'DIMENSIONAL')),
                        upper(coalesce(p.inward_type,'MATERIAL_INWARD')),
                        upper(coalesce(p.requirement_scope,'GENERAL'))
           order by case upper(coalesce(p.status,'DRAFT'))
                      when 'APPROVED' then 1
                      when 'APPROVAL_PENDING' then 2
                      when 'DRAFT' then 3
                      else 4
                    end,
                    p.effective_date desc nulls last,
                    p.updated_at desc nulls last,
                    p.created_at desc nulls last,
                    p.id desc
         ) as rn
  from public.inspection_plans p
  where upper(coalesce(p.status,'DRAFT')) in ('DRAFT','APPROVAL_PENDING','APPROVED')
    and upper(coalesce(p.requirement_scope,'GENERAL')) <> 'FINAL_METALLURGICAL'
)
update public.inspection_plans p
set status='SUPERSEDED', updated_at=now(), updated_by=auth.uid()
from ranked r
where p.id=r.id and r.rn>1;

drop index if exists public.uq_qcms_inspection_plan_current_scope;
create unique index uq_qcms_inspection_plan_current_scope
  on public.inspection_plans(
    tenant_id,
    part_id,
    coalesce(process_id,'00000000-0000-0000-0000-000000000000'::uuid),
    coalesce(inspection_stage_id,'00000000-0000-0000-0000-000000000000'::uuid),
    upper(coalesce(layout_type,'DIMENSIONAL')),
    upper(coalesce(inward_type,'MATERIAL_INWARD')),
    upper(coalesce(requirement_scope,'GENERAL'))
  )
  where upper(coalesce(status,'DRAFT')) in ('DRAFT','APPROVAL_PENDING','APPROVED')
    and upper(coalesce(requirement_scope,'GENERAL')) <> 'FINAL_METALLURGICAL';

comment on index public.uq_qcms_inspection_plan_current_scope is
  'QCMS v4.14.45 one current layout per Part + Stage + Process + Layout Type + Inward Type + Requirement Scope. Older history remains SUPERSEDED.';

-- -----------------------------------------------------------------------------
-- 3) Public read-only release contract used by the controlled automatic updater.
-- -----------------------------------------------------------------------------
create or replace function public.qcms_release_schema_version()
returns text
language sql
immutable
set search_path=pg_catalog
as $$ select '4.14.45'::text $$;

revoke all on function public.qcms_release_schema_version() from public;
grant execute on function public.qcms_release_schema_version() to anon,authenticated,service_role;

create or replace function public.qcms_release_contract_v41445()
returns text
language plpgsql
stable
set search_path=public,pg_catalog
as $$
begin
  if public.qcms_release_schema_version()='4.14.45'
     and exists(
       select 1 from information_schema.columns
       where table_schema='public' and table_name='part_raw_material_details' and column_name='source_part_id'
     )
     and to_regprocedure('public.qcms_guard_raw_source_part()') is not null
     and exists(
       select 1 from pg_trigger t
       join pg_class c on c.oid=t.tgrelid
       join pg_namespace n on n.oid=c.relnamespace
       where n.nspname='public' and c.relname='part_raw_material_details'
         and t.tgname='trg_qcms_guard_raw_source_part' and not t.tgisinternal
     )
     and to_regclass('public.uq_qcms_inspection_plan_current_scope') is not null
  then
    return 'QCMS_V41445_FULL_READY';
  end if;
  return 'QCMS_V41445_INCOMPLETE';
end;
$$;

revoke all on function public.qcms_release_contract_v41445() from public;
grant execute on function public.qcms_release_contract_v41445() to anon,authenticated,service_role;

insert into public.qcms_release_schema_state(version,build,applied_at,details)
values(
  '4.14.45',
  '41445-SHARED-RAW-SOURCE-LAYOUT-CONTROL',
  now(),
  jsonb_build_object(
    'same_price_across_different_parts',true,
    'source_raw_forging_casting_part',true,
    'source_part_cycle_guard',true,
    'layout_auto_plan_number',true,
    'one_current_layout_per_scope',true
  )
)
on conflict(version) do update
set build=excluded.build,applied_at=excluded.applied_at,details=excluded.details;

commit;
