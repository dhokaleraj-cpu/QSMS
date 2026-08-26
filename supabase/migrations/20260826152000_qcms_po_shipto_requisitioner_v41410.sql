-- QCMS v4.14.10 - Controlled PO Ship-To master selection + logged-in employee Requisitioner
-- Additive / backward-compatible. Existing Purchase Orders and snapshots are preserved.

alter table public.supply_purchase_orders
  add column if not exists ship_to_party_id uuid references public.parties(id),
  add column if not exists ship_to_source_type text,
  add column if not exists requisitioner_employee_id uuid references public.employees(id);

create index if not exists idx_supply_purchase_orders_ship_to_party
  on public.supply_purchase_orders(tenant_id, ship_to_party_id);
create index if not exists idx_supply_purchase_orders_requisitioner_employee
  on public.supply_purchase_orders(tenant_id, requisitioner_employee_id);

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid='public.supply_purchase_orders'::regclass
      and conname='supply_purchase_orders_ship_to_source_type_check'
  ) then
    alter table public.supply_purchase_orders
      add constraint supply_purchase_orders_ship_to_source_type_check
      check (ship_to_source_type is null or ship_to_source_type in ('CUSTOMER','SUPPLIER','VENDOR'));
  end if;
end $$;

create or replace function public.qcms_control_supply_po_identity()
returns trigger
language plpgsql
set search_path to 'public','auth'
as $$
declare
  v_emp_id uuid;
  v_emp public.employees%rowtype;
  v_party public.parties%rowtype;
  v_types text[];
begin
  -- Backward-compatible server control: when the authenticated login resolves to
  -- Employee Master, overwrite any client-supplied Requisitioner with that employee.
  v_emp_id := public.qcms_current_login_employee_id();
  if v_emp_id is not null then
    select * into v_emp
    from public.employees
    where id=v_emp_id and tenant_id=new.tenant_id and status='ACTIVE';
    if v_emp.id is not null then
      new.requisitioner_employee_id := v_emp.id;
      new.requisitioner := nullif(btrim(concat_ws(' ',v_emp.first_name,v_emp.last_name)),'');
    end if;
  end if;

  -- New v4.14.10 POs provide ship_to_party_id. Historical/legacy inserts without
  -- the link keep their pre-existing ship_to_snapshot so old deployments remain usable.
  if new.ship_to_party_id is not null then
    select * into v_party
    from public.parties
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
      'source_type',new.ship_to_source_type,
      'source_party_id',v_party.id,
      'party_code',v_party.party_code,
      'party_name',v_party.party_name,
      'address',v_party.address,
      'city',v_party.city,
      'state',v_party.state,
      'country',v_party.country,
      'tax_identifier',v_party.tax_identifier,
      'contact_person',v_party.contact_person,
      'phone',v_party.phone,
      'email',v_party.email
    );
  end if;
  return new;
end;
$$;

drop trigger if exists trg_qcms_control_supply_po_identity on public.supply_purchase_orders;
create trigger trg_qcms_control_supply_po_identity
before insert or update of ship_to_party_id,ship_to_source_type,requisitioner,requisitioner_employee_id
on public.supply_purchase_orders
for each row execute function public.qcms_control_supply_po_identity();
