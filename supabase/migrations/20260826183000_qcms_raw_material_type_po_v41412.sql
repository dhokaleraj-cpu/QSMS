-- QCMS v4.14.12 - controlled Raw Material Type list / backward-compatible label migration
begin;

comment on column public.part_raw_material_details.material_section_name is
  'QCMS Raw Material Type (legacy physical column name retained for backward compatibility).';

insert into public.master_value_catalog(tenant_id,field_key,value_text)
select t.id,'part.rm_type',v.value_text
from public.tenants t
cross join (values ('Round Black Bar'),('Bright Bar')) as v(value_text)
on conflict (tenant_id,field_key,normalized_value) do update
set status='ACTIVE', value_text=excluded.value_text, updated_at=now();

commit;
