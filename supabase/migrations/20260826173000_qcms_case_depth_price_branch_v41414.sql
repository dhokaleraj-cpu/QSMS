-- QCMS v4.14.14
-- Layout-driven Case Depth is application/json-only. Database changes here provide:
-- 1) reusable Company Branch Master,
-- 2) PO issuing-branch + Branch Ship-To lineage,
-- while preserving all existing records/snapshots.

create table if not exists public.company_branches(
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  branch_code text not null,
  plant_code text,
  branch_name text not null,
  address_line1 text,
  address_line2 text,
  address_line3 text,
  city text,
  state text,
  postal_code text,
  country text default 'India',
  gstin text,
  contact_person text,
  phone text,
  email text,
  is_default boolean not null default false,
  status text not null default 'ACTIVE' check(status in ('ACTIVE','INACTIVE')),
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);

create unique index if not exists uq_company_branches_tenant_code
  on public.company_branches(tenant_id, lower(btrim(branch_code)));
create unique index if not exists uq_company_branches_one_active_default
  on public.company_branches(tenant_id) where is_default and status='ACTIVE';
create index if not exists idx_company_branches_tenant_status
  on public.company_branches(tenant_id,status,branch_code);

alter table public.company_branches enable row level security;
drop policy if exists tenant_select on public.company_branches;
drop policy if exists tenant_insert on public.company_branches;
drop policy if exists tenant_update on public.company_branches;
drop policy if exists tenant_delete on public.company_branches;
create policy tenant_select on public.company_branches for select to authenticated
  using (tenant_id=public.current_tenant_id());
create policy tenant_insert on public.company_branches for insert to authenticated
  with check (
    tenant_id=public.current_tenant_id() and (
      public.current_app_role() in ('ADMIN','QUALITY_MANAGER','MASTER_DATA') or
      exists(select 1 from public.user_module_permissions p where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and p.module_key='REFERENCE_MASTERS' and p.can_create)
    )
  );
create policy tenant_update on public.company_branches for update to authenticated
  using (
    tenant_id=public.current_tenant_id() and (
      public.current_app_role() in ('ADMIN','QUALITY_MANAGER','MASTER_DATA') or
      exists(select 1 from public.user_module_permissions p where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and p.module_key='REFERENCE_MASTERS' and p.can_edit)
    )
  )
  with check (tenant_id=public.current_tenant_id());
create policy tenant_delete on public.company_branches for delete to authenticated
  using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

grant select,insert,update,delete on public.company_branches to authenticated;

-- Seed the current D9 branch without changing any existing transaction.
insert into public.company_branches(
  tenant_id,branch_code,plant_code,branch_name,address_line1,address_line2,address_line3,
  city,state,postal_code,country,gstin,phone,email,is_default,status,remarks
)
select t.id,
       coalesce(nullif(btrim(t.plant_code),''),'D9'),
       coalesce(nullif(btrim(t.plant_code),''),'D9'),
       t.tenant_name || ' - ' || coalesce(nullif(btrim(t.plant_code),''),'D9'),
       case when coalesce(nullif(btrim(t.plant_code),''),'D9')='D9' then 'Plot No.D9, Chakan MIDC PH II' end,
       case when coalesce(nullif(btrim(t.plant_code),''),'D9')='D9' then 'Bhamboli, Khed' end,
       null,
       case when coalesce(nullif(btrim(t.plant_code),''),'D9')='D9' then 'Pune' end,
       case when coalesce(nullif(btrim(t.plant_code),''),'D9')='D9' then 'Maharashtra' end,
       case when coalesce(nullif(btrim(t.plant_code),''),'D9')='D9' then '410501' end,
       'India',
       case when coalesce(nullif(btrim(t.plant_code),''),'D9')='D9' then '27AAGCF3769A1ZP' end,
       case when coalesce(nullif(btrim(t.plant_code),''),'D9')='D9' then '022 40104412' end,
       case when coalesce(nullif(btrim(t.plant_code),''),'D9')='D9' then 'orders@fourstarindustries.com' end,
       true,'ACTIVE','Seeded from existing QCMS tenant / PO plant identity'
from public.tenants t
where not exists(select 1 from public.company_branches b where b.tenant_id=t.id);

alter table public.supply_purchase_orders
  add column if not exists company_branch_id uuid references public.company_branches(id),
  add column if not exists ship_to_branch_id uuid references public.company_branches(id);

create index if not exists idx_supply_purchase_orders_company_branch
  on public.supply_purchase_orders(tenant_id,company_branch_id);
create index if not exists idx_supply_purchase_orders_ship_to_branch
  on public.supply_purchase_orders(tenant_id,ship_to_branch_id);

alter table public.supply_purchase_orders
  drop constraint if exists supply_purchase_orders_ship_to_source_type_check;
alter table public.supply_purchase_orders
  add constraint supply_purchase_orders_ship_to_source_type_check
  check (ship_to_source_type is null or ship_to_source_type in ('BRANCH','CUSTOMER','SUPPLIER','VENDOR'));

create or replace function public.qcms_control_supply_po_identity()
returns trigger
language plpgsql
set search_path to 'public','auth'
as $$
declare
  v_emp_id uuid;
  v_emp public.employees%rowtype;
  v_party public.parties%rowtype;
  v_branch public.company_branches%rowtype;
  v_ship_branch public.company_branches%rowtype;
  v_types text[];
begin
  v_emp_id := public.qcms_current_login_employee_id();
  if v_emp_id is not null then
    select * into v_emp from public.employees
    where id=v_emp_id and tenant_id=new.tenant_id and status='ACTIVE';
    if v_emp.id is not null then
      new.requisitioner_employee_id := v_emp.id;
      new.requisitioner := nullif(btrim(concat_ws(' ',v_emp.first_name,v_emp.last_name)),'');
    end if;
  end if;

  -- New controlled POs select an issuing Company Branch. Legacy records with a
  -- null link retain the original plant_snapshot unchanged.
  if new.company_branch_id is not null then
    select * into v_branch from public.company_branches
    where id=new.company_branch_id and tenant_id=new.tenant_id and status='ACTIVE';
    if v_branch.id is null then
      raise exception 'Company Branch / Plant must be an ACTIVE Company Branch Master record';
    end if;
    new.plant_snapshot := jsonb_build_object(
      'branch_id',v_branch.id,'branch_code',v_branch.branch_code,'plant_code',coalesce(v_branch.plant_code,v_branch.branch_code),
      'name',v_branch.branch_name,'branch_name',v_branch.branch_name,
      'address1',v_branch.address_line1,'address2',v_branch.address_line2,'address3',v_branch.address_line3,
      'city',v_branch.city,'state',v_branch.state,'postal_code',v_branch.postal_code,'country',v_branch.country,
      'tax_identifier',v_branch.gstin,'gstin',v_branch.gstin,'contact_person',v_branch.contact_person,
      'phone',v_branch.phone,'email',v_branch.email
    );
  end if;

  if new.ship_to_source_type='BRANCH' then
    if new.ship_to_branch_id is null then
      raise exception 'Select a Company Branch for Ship-To';
    end if;
    select * into v_ship_branch from public.company_branches
    where id=new.ship_to_branch_id and tenant_id=new.tenant_id and status='ACTIVE';
    if v_ship_branch.id is null then
      raise exception 'Ship-To Branch must be an ACTIVE Company Branch Master record';
    end if;
    new.ship_to_party_id := null;
    new.ship_to_snapshot := jsonb_build_object(
      'source_type','BRANCH','source_branch_id',v_ship_branch.id,
      'party_code',v_ship_branch.branch_code,'party_name',v_ship_branch.branch_name,
      'branch_code',v_ship_branch.branch_code,'plant_code',coalesce(v_ship_branch.plant_code,v_ship_branch.branch_code),
      'address',concat_ws(', ',nullif(v_ship_branch.address_line1,''),nullif(v_ship_branch.address_line2,''),nullif(v_ship_branch.address_line3,'')),
      'city',v_ship_branch.city,'state',v_ship_branch.state,'postal_code',v_ship_branch.postal_code,'country',v_ship_branch.country,
      'tax_identifier',v_ship_branch.gstin,'contact_person',v_ship_branch.contact_person,'phone',v_ship_branch.phone,'email',v_ship_branch.email
    );
  elsif new.ship_to_party_id is not null then
    new.ship_to_branch_id := null;
    select * into v_party from public.parties
    where id=new.ship_to_party_id and tenant_id=new.tenant_id and status='ACTIVE';
    if v_party.id is null then
      raise exception 'Ship-To party must be an ACTIVE Party Master record';
    end if;
    if new.ship_to_source_type not in ('CUSTOMER','SUPPLIER','VENDOR') then
      raise exception 'Select Ship-To Source as CUSTOMER, SUPPLIER or VENDOR';
    end if;
    v_types := coalesce(v_party.party_types,'{}'::text[]);
    if new.ship_to_source_type='CUSTOMER' and not ('CUSTOMER'=any(v_types)) then
      raise exception 'Selected Ship-To party is not in Customer Master';
    elsif new.ship_to_source_type='SUPPLIER' and not (v_types && array['SUPPLIER','STEEL_MILL']::text[]) then
      raise exception 'Selected Ship-To party is not in Supplier Master';
    elsif new.ship_to_source_type='VENDOR' and not (v_types && array['OSP_VENDOR','FORGING_SUPPLIER']::text[]) then
      raise exception 'Selected Ship-To party is not in Vendor / OSP Master';
    end if;
    new.ship_to_snapshot := jsonb_build_object(
      'source_type',new.ship_to_source_type,'source_party_id',v_party.id,
      'party_code',v_party.party_code,'party_name',v_party.party_name,'address',v_party.address,
      'city',v_party.city,'state',v_party.state,'country',v_party.country,'tax_identifier',v_party.tax_identifier,
      'contact_person',v_party.contact_person,'phone',v_party.phone,'email',v_party.email
    );
  end if;
  return new;
end;
$$;

drop trigger if exists trg_qcms_control_supply_po_identity on public.supply_purchase_orders;
create trigger trg_qcms_control_supply_po_identity
before insert or update of company_branch_id,ship_to_party_id,ship_to_branch_id,ship_to_source_type,requisitioner,requisitioner_employee_id
on public.supply_purchase_orders
for each row execute function public.qcms_control_supply_po_identity();

revoke all on function public.qcms_control_supply_po_identity() from public,anon;
grant execute on function public.qcms_control_supply_po_identity() to authenticated;
