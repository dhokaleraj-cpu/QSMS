-- QCMS v4.14.11 - supplier/raw-material HSN + controlled PD9DDMM00001 PO series
-- Additive / backward-compatible. Existing POs and Part Master rows are preserved.

alter table public.part_raw_material_details
  add column if not exists hsn_sac_code text;

-- Existing Part header HSN remains the backward-compatible fallback. Populate current
-- supplier/raw rows where possible so the new PO entry can read the HSN directly.
update public.part_raw_material_details r
set hsn_sac_code = nullif(btrim(p.hsn_sac_code),'')
from public.parts p
where p.id=r.part_id
  and nullif(btrim(coalesce(r.hsn_sac_code,'')),'') is null
  and nullif(btrim(coalesce(p.hsn_sac_code,'')),'') is not null;

-- New PO numbering series. The 5-digit counter is continuous rather than resetting
-- each day; DDMM is still embedded in every number while permanent uniqueness is
-- retained across future years.
create table if not exists public.supply_po_series_v41411(
  tenant_id uuid primary key references public.tenants(id) on delete cascade,
  current_value bigint not null default 0,
  updated_at timestamptz not null default now(),
  constraint supply_po_series_v41411_range check(current_value between 0 and 99999)
);

alter table public.supply_po_series_v41411 enable row level security;
drop policy if exists tenant_select on public.supply_po_series_v41411;
create policy tenant_select on public.supply_po_series_v41411
for select to authenticated using(tenant_id=public.current_tenant_id());
grant select on public.supply_po_series_v41411 to authenticated;

create or replace function public.qcms_next_supply_po_number()
returns text
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  tid uuid:=public.current_tenant_id();
  next_value bigint;
begin
  if auth.uid() is null or tid is null then
    raise exception 'An authenticated QCMS session is required';
  end if;
  if not public.can_write_table('supply_rm_purchase_orders') and public.current_app_role()<>'ADMIN' then
    raise exception 'Supply Chain procurement create/edit permission is required';
  end if;
  insert into public.supply_po_series_v41411(tenant_id,current_value)
  values(tid,0)
  on conflict(tenant_id) do nothing;
  update public.supply_po_series_v41411
     set current_value=current_value+1,updated_at=now()
   where tenant_id=tid
   returning current_value into next_value;
  if next_value>99999 then
    raise exception 'QCMS Purchase Order five-digit sequence is exhausted';
  end if;
  return 'PD9'||to_char(current_date,'DDMM')||lpad(next_value::text,5,'0');
end;
$$;

revoke all on function public.qcms_next_supply_po_number() from public,anon;
grant execute on function public.qcms_next_supply_po_number() to authenticated;

comment on column public.part_raw_material_details.hsn_sac_code is 'QCMS v4.14.11 supplier/raw-material-specific HSN/SAC inherited by Purchase Orders; Part header HSN remains fallback.';
comment on function public.qcms_next_supply_po_number() is 'QCMS v4.14.11 PO format P + D9 + DDMM + continuous five-digit sequence, e.g. PD9260800001.';
