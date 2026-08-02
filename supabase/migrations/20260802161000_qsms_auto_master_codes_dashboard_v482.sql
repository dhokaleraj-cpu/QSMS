-- QSMS 4.8.2 — automatic editable codes for Reference Masters.
begin;

alter table public.part_supplier_links
  add column if not exists source_code text;

create unique index if not exists uq_part_supplier_links_source_code
  on public.part_supplier_links(tenant_id, source_code)
  where source_code is not null;

with existing_max as (
  select tenant_id, coalesce(max(substring(source_code from '([0-9]+)$')::bigint),0) as max_no
  from public.part_supplier_links
  where source_code ~ '^SRC-[0-9]+$'
  group by tenant_id
), ranked as (
  select p.id,p.tenant_id,
         row_number() over(partition by p.tenant_id order by p.created_at,p.id)
         + coalesce(m.max_no,0) as seq
  from public.part_supplier_links p
  left join existing_max m on m.tenant_id=p.tenant_id
  where nullif(btrim(coalesce(p.source_code,'')),'') is null
)
update public.part_supplier_links p
set source_code='SRC-'||lpad(r.seq::text,4,'0'),updated_at=now()
from ranked r where p.id=r.id;

insert into public.number_sequences(tenant_id,sequence_code,prefix,year_format,current_value,padding,reset_frequency,last_reset_year)
select t.id,v.sequence_code,v.prefix,'NONE',v.current_value,4,'NEVER',null
from public.tenants t
cross join lateral (
  values
    ('MASTER_CUSTOMER','CUST',coalesce((select max(substring(p.party_code from '([0-9]+)$')::bigint) from public.parties p where p.tenant_id=t.id and 'CUSTOMER'=any(p.party_types) and p.party_code~'^CUST-[0-9]+$'),0)),
    ('MASTER_SUPPLIER','SUP',coalesce((select max(substring(p.party_code from '([0-9]+)$')::bigint) from public.parties p where p.tenant_id=t.id and 'SUPPLIER'=any(p.party_types) and not ('OSP_VENDOR'=any(p.party_types)) and p.party_code~'^SUP-[0-9]+$'),0)),
    ('MASTER_STEEL_MILL','MILL',coalesce((select max(substring(p.party_code from '([0-9]+)$')::bigint) from public.parties p where p.tenant_id=t.id and 'STEEL_MILL'=any(p.party_types) and p.party_code~'^MILL-[0-9]+$'),0)),
    ('MASTER_OSP_VENDOR','OSPV',coalesce((select max(substring(p.party_code from '([0-9]+)$')::bigint) from public.parties p where p.tenant_id=t.id and 'OSP_VENDOR'=any(p.party_types) and p.party_code~'^OSPV-[0-9]+$'),0)),
    ('MASTER_APPROVED_SOURCE','SRC',coalesce((select max(substring(s.source_code from '([0-9]+)$')::bigint) from public.part_supplier_links s where s.tenant_id=t.id and s.source_code~'^SRC-[0-9]+$'),0)),
    ('MASTER_PROCESS','PROC',coalesce((select max(substring(p.process_code from '([0-9]+)$')::bigint) from public.processes p where p.tenant_id=t.id and p.process_code~'^PROC-[0-9]+$'),0)),
    ('MASTER_INSPECTION_STAGE','STG',coalesce((select max(substring(s.stage_code from '([0-9]+)$')::bigint) from public.inspection_stages s where s.tenant_id=t.id and s.stage_code~'^STG-[0-9]+$'),0)),
    ('MASTER_QUALITY_ASSET','AST',coalesce((select max(substring(a.asset_code from '([0-9]+)$')::bigint) from public.quality_assets a where a.tenant_id=t.id and a.asset_code~'^AST-[0-9]+$'),0))
) as v(sequence_code,prefix,current_value)
on conflict (tenant_id,sequence_code) do update
set prefix=excluded.prefix,year_format='NONE',padding=4,reset_frequency='NEVER',
    current_value=greatest(public.number_sequences.current_value,excluded.current_value),updated_at=now();

create or replace function public.qsms_next_master_code(p_master_key text)
returns text
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  tid uuid:=public.current_tenant_id();
  master_key text:=lower(btrim(coalesce(p_master_key,'')));
  sequence_name text;
  code_prefix text;
  target_table text;
  next_value bigint;
begin
  if auth.uid() is null or tid is null then raise exception 'An authenticated QSMS session is required'; end if;
  case master_key
    when 'customers' then sequence_name:='MASTER_CUSTOMER';code_prefix:='CUST';target_table:='parties';
    when 'suppliers' then sequence_name:='MASTER_SUPPLIER';code_prefix:='SUP';target_table:='parties';
    when 'steel_mills' then sequence_name:='MASTER_STEEL_MILL';code_prefix:='MILL';target_table:='parties';
    when 'osp_vendors' then sequence_name:='MASTER_OSP_VENDOR';code_prefix:='OSPV';target_table:='parties';
    when 'approved_sources' then sequence_name:='MASTER_APPROVED_SOURCE';code_prefix:='SRC';target_table:='part_supplier_links';
    when 'processes' then sequence_name:='MASTER_PROCESS';code_prefix:='PROC';target_table:='processes';
    when 'inspection_stages' then sequence_name:='MASTER_INSPECTION_STAGE';code_prefix:='STG';target_table:='inspection_stages';
    when 'quality_assets' then sequence_name:='MASTER_QUALITY_ASSET';code_prefix:='AST';target_table:='quality_assets';
    else raise exception 'Automatic code generation is not configured for master %',p_master_key;
  end case;
  if not public.can_write_table(target_table) then raise exception 'Create permission is required for this Reference Master'; end if;
  insert into public.number_sequences(tenant_id,sequence_code,prefix,year_format,current_value,padding,reset_frequency,last_reset_year)
  values(tid,sequence_name,code_prefix,'NONE',0,4,'NEVER',null)
  on conflict (tenant_id,sequence_code) do nothing;
  update public.number_sequences
  set current_value=current_value+1,updated_at=now(),updated_by=auth.uid()
  where tenant_id=tid and sequence_code=sequence_name
  returning current_value into next_value;
  return code_prefix||'-'||lpad(next_value::text,4,'0');
end;
$$;

revoke all on function public.qsms_next_master_code(text) from public,anon;
grant execute on function public.qsms_next_master_code(text) to authenticated;

commit;
