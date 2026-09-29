-- R8: one material-out document, separate existing heat-wise OSP jobs.
begin;
create table if not exists public.osp_material_outs (
 id uuid primary key default gen_random_uuid(),
 tenant_id uuid not null references public.tenants(id),
 material_out_number text not null,
 request_id uuid not null,
 request_payload jsonb not null,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 created_by uuid default auth.uid(),
 updated_by uuid default auth.uid(),
 unique(tenant_id,request_id), unique(tenant_id,material_out_number)
);
alter table public.osp_material_outs enable row level security;
create policy tenant_select on public.osp_material_outs for select to authenticated using(tenant_id=public.current_tenant_id());
create policy tenant_insert on public.osp_material_outs for insert to authenticated with check(tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('OSP_TRANSACTIONS','create'));
create policy tenant_update on public.osp_material_outs for update to authenticated using(tenant_id=public.current_tenant_id() and public.can_write_table('osp_jobs')) with check(tenant_id=public.current_tenant_id() and public.can_write_table('osp_jobs'));
create policy tenant_delete on public.osp_material_outs for delete to authenticated using(tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('OSP_TRANSACTIONS','archive'));
grant select,insert,update,delete on public.osp_material_outs to authenticated;
create trigger trg_touch_updated_at before update on public.osp_material_outs for each row execute function public.touch_updated_at();
create trigger trg_audit_row_change after insert or update or delete on public.osp_material_outs for each row execute function public.log_row_change();
alter table public.osp_jobs add column if not exists material_out_id uuid references public.osp_material_outs(id) on delete restrict;
alter table public.osp_jobs add column if not exists material_out_line_no integer;
create unique index if not exists uq_osp_material_out_line on public.osp_jobs(material_out_id,material_out_line_no) where material_out_id is not null;

create or replace function public.qcms_guard_osp_material_out_line() returns trigger
language plpgsql security invoker set search_path='' as $$
declare g public.osp_material_outs%rowtype;
begin
 if tg_op='UPDATE' and old.material_out_id is not null and
    (new.material_out_id is distinct from old.material_out_id or new.material_out_line_no is distinct from old.material_out_line_no
     or new.source_inward_lot_id is distinct from old.source_inward_lot_id or new.opening_stock_id is distinct from old.opening_stock_id
     or new.source_batch_id is distinct from old.source_batch_id or new.osp_batch_id is distinct from old.osp_batch_id) then
   raise exception 'A Material Out heat line cannot be reassigned to another source or document';
 end if;
 if new.material_out_id is null then return new; end if;
 select * into g from public.osp_material_outs where id=new.material_out_id for update;
 if g.id is null or g.tenant_id<>new.tenant_id or new.material_out_line_no is null or new.material_out_line_no<1 then
   raise exception 'Invalid Material Out document / tenant / line';
 end if;
 return new;
end $$;
create trigger trg_osp_material_out_line before insert or update on public.osp_jobs for each row execute function public.qcms_guard_osp_material_out_line();

create or replace function public.qcms_check_osp_material_out_consistency() returns trigger
language plpgsql security invoker set search_path='' as $$
begin
 if new.material_out_id is not null and exists(
  select 1 from public.osp_jobs a join public.osp_jobs b on b.material_out_id=a.material_out_id
  where a.material_out_id=new.material_out_id and
  row(a.tenant_id,a.part_id,a.vendor_id,a.process_id,a.process_specification_id,a.dispatch_date,a.dispatch_challan,a.expected_return_date,a.dispatch_remarks)
  is distinct from row(b.tenant_id,b.part_id,b.vendor_id,b.process_id,b.process_specification_id,b.dispatch_date,b.dispatch_challan,b.expected_return_date,b.dispatch_remarks)
 ) then raise exception 'All heat lines must retain the same Part, Vendor, Process and Material Out header'; end if;
 return null;
end $$;
create constraint trigger trg_osp_material_out_consistency after insert or update on public.osp_jobs deferrable initially deferred for each row execute function public.qcms_check_osp_material_out_consistency();

create or replace function public.qcms_create_osp_material_out(p_request_id uuid,p_header jsonb,p_lines jsonb)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare tid uuid:=public.current_tenant_id(); g public.osp_material_outs%rowtype; item jsonb; job jsonb; jobs jsonb:='[]';
 source_id uuid; source_part uuid; wanted_part uuid; qty numeric; sample_qty numeric; pos integer:=0; request jsonb;
begin
 if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
 if not public.qcms_effective_module_permission('OSP_TRANSACTIONS','create') then raise exception 'OSP Transactions create permission is required'; end if;
 if p_request_id is null or jsonb_typeof(p_header) is distinct from 'object' or jsonb_typeof(p_lines) is distinct from 'array' then raise exception 'Select Material Out header and heat lines'; end if;
 if jsonb_array_length(p_lines) not between 1 and 100 then raise exception 'Select between 1 and 100 heat lines'; end if;
 request:=jsonb_build_object('header',p_header,'lines',p_lines);
 perform pg_advisory_xact_lock(hashtextextended(tid::text||p_request_id::text,0));
 select * into g from public.osp_material_outs where tenant_id=tid and request_id=p_request_id;
 if g.id is not null then
  if g.request_payload<>request then raise exception 'This save request already created a different Material Out. Start a new entry.'; end if;
  select coalesce(jsonb_agg(to_jsonb(o) order by material_out_line_no),'[]') into jobs from public.osp_jobs o where material_out_id=g.id and tenant_id=tid;
  return to_jsonb(g)||jsonb_build_object('lines',jobs,'replayed',true);
 end if;
 if nullif(btrim(p_header->>'dispatch_challan'),'') is null or nullif(p_header->>'dispatch_date','') is null then raise exception 'Material Out date and challan are required'; end if;
 if (p_header->>'expected_return_date')::date < (p_header->>'dispatch_date')::date then raise exception 'Expected return cannot precede dispatch'; end if;
 if exists(select 1 from jsonb_array_elements(p_lines) x group by coalesce(x->>'inward_lot_id','')||':'||coalesce(x->>'opening_stock_id','') having count(*)>1) then raise exception 'A source may appear only once in the Material Out'; end if;
 select part_id into wanted_part from public.part_process_specifications where id=(p_header->>'process_specification_id')::uuid and tenant_id=tid and process_id=(p_header->>'process_id')::uuid and status='ACTIVE' and inward_type='OSP_PROCESS';
 if wanted_part is null then raise exception 'Select an ACTIVE Part Process Specification'; end if;
 -- Deterministic source lock order; existing dispatch RPCs enforce source release and available quantity again.
 for item in select value from jsonb_array_elements(p_lines) order by coalesce(value->>'inward_lot_id',''),coalesce(value->>'opening_stock_id','') loop
  if (nullif(item->>'inward_lot_id','') is null) = (nullif(item->>'opening_stock_id','') is null) then raise exception 'Each heat line needs exactly one source'; end if;
  source_part:=null;
  if nullif(item->>'inward_lot_id','') is not null then
   source_id:=(item->>'inward_lot_id')::uuid;
   select part_id into source_part from public.inward_lots where id=source_id and tenant_id=tid for update;
  else
   source_id:=(item->>'opening_stock_id')::uuid;
   select part_id into source_part from public.supply_opening_stock where id=source_id and tenant_id=tid for update;
  end if;
  if source_part is distinct from wanted_part then raise exception 'All heat lines must belong to the selected Part and tenant'; end if;
  qty:=(item->>'quantity_dispatched')::numeric; sample_qty:=(item->>'sample_quantity')::numeric;
  if qty is null or qty::text in ('NaN','Infinity','-Infinity') or qty<=0 then raise exception 'Every heat line requires a finite positive dispatch quantity'; end if;
  if sample_qty is null or sample_qty::text in ('NaN','Infinity','-Infinity') or sample_qty<=0 or sample_qty>least(qty,20) then raise exception 'Sample quantity must be positive, at most 20, and no more than its heat-line quantity'; end if;
 end loop;
 insert into public.osp_material_outs(tenant_id,material_out_number,request_id,request_payload) values(tid,'OUT-'||p_request_id::text,p_request_id,request) returning * into g;
 for item in select value from jsonb_array_elements(p_lines) loop
  pos:=pos+1;
  if nullif(item->>'inward_lot_id','') is not null then
   job:=public.qsms_create_osp_dispatch((item->>'inward_lot_id')::uuid,(p_header->>'vendor_id')::uuid,(p_header->>'process_id')::uuid,(p_header->>'process_specification_id')::uuid,(p_header->>'dispatch_date')::date,p_header->>'dispatch_challan',(item->>'quantity_dispatched')::numeric,(p_header->>'expected_return_date')::date,(item->>'sample_quantity')::numeric,p_header->>'remarks');
  else
   job:=public.qsms_create_osp_dispatch_from_opening_stock((item->>'opening_stock_id')::uuid,(p_header->>'vendor_id')::uuid,(p_header->>'process_id')::uuid,(p_header->>'process_specification_id')::uuid,(p_header->>'dispatch_date')::date,p_header->>'dispatch_challan',(item->>'quantity_dispatched')::numeric,(p_header->>'expected_return_date')::date,(item->>'sample_quantity')::numeric,p_header->>'remarks');
  end if;
  update public.osp_jobs set material_out_id=g.id,material_out_line_no=pos where id=(job->>'id')::uuid and tenant_id=tid;
  if not found then raise exception 'Could not link the saved heat line'; end if;
  if pos=1 then update public.osp_material_outs set material_out_number='OUT-'||(job->>'osp_job_number') where id=g.id returning * into g; end if;
  jobs:=jobs||jsonb_build_array(job||jsonb_build_object('material_out_id',g.id,'material_out_line_no',pos));
 end loop;
 return to_jsonb(g)||jsonb_build_object('lines',jobs,'replayed',false);
end $$;

create or replace function public.qcms_update_osp_material_out_group(p_material_out_id uuid,p_header jsonb,p_lines jsonb)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare tid uuid:=public.current_tenant_id(); j public.osp_jobs%rowtype; item jsonb; jobs jsonb:='[]';
begin
 if auth.uid() is null or tid is null or not public.qcms_effective_module_permission('OSP_TRANSACTIONS','edit') then raise exception 'OSP Transactions edit permission is required'; end if;
 perform 1 from public.osp_material_outs where id=p_material_out_id and tenant_id=tid for update;
 if not found then raise exception 'Material Out not found'; end if;
 if jsonb_typeof(p_lines) is distinct from 'array' then raise exception 'Provide every heat line'; end if;
 if jsonb_array_length(p_lines)=0 or jsonb_array_length(p_lines)<>(select count(*) from public.osp_jobs where material_out_id=p_material_out_id and tenant_id=tid) or exists(select 1 from jsonb_array_elements(p_lines) x group by x->>'id' having count(*)>1) then raise exception 'Provide each existing heat line exactly once'; end if;
 if (p_header->>'expected_return_date')::date < (p_header->>'dispatch_date')::date then raise exception 'Expected return cannot precede dispatch'; end if;
 for item in select value from jsonb_array_elements(p_lines) order by value->>'id' loop
  select * into j from public.osp_jobs where id=(item->>'id')::uuid and material_out_id=p_material_out_id and tenant_id=tid for update;
  if not found then raise exception 'Heat line does not belong to this Material Out'; end if;
  if nullif(p_header->>'dispatch_date','') is null or (item->>'quantity_dispatched')::numeric is null or (item->>'quantity_dispatched')::numeric::text in ('NaN','Infinity','-Infinity') then raise exception 'Date and finite quantities are required'; end if;
  jobs:=jobs||jsonb_build_array(public.qcms_update_osp_material_out(j.id,(p_header->>'dispatch_date')::date,p_header->>'dispatch_challan',(item->>'quantity_dispatched')::numeric,(p_header->>'expected_return_date')::date,p_header->>'remarks'));
 end loop;
 return jsonb_build_object('id',p_material_out_id,'lines',jobs);
end $$;

create or replace function public.qcms_delete_osp_material_out_group(p_material_out_id uuid)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare tid uuid:=public.current_tenant_id(); j record;
begin
 if auth.uid() is null or tid is null or not public.qcms_effective_module_permission('OSP_TRANSACTIONS','archive') then raise exception 'OSP Transactions Delete/Archive permission is required'; end if;
 perform 1 from public.osp_material_outs where id=p_material_out_id and tenant_id=tid for update;
 if not found then raise exception 'Material Out not found'; end if;
 for j in select id from public.osp_jobs where material_out_id=p_material_out_id and tenant_id=tid order by id loop
  perform public.qcms_delete_osp_transaction(j.id);
 end loop;
 delete from public.osp_material_outs where id=p_material_out_id and tenant_id=tid;
 return jsonb_build_object('deleted',true,'material_out_id',p_material_out_id);
end $$;

revoke all on function public.qcms_guard_osp_material_out_line(), public.qcms_check_osp_material_out_consistency(), public.qcms_create_osp_material_out(uuid,jsonb,jsonb), public.qcms_update_osp_material_out_group(uuid,jsonb,jsonb), public.qcms_delete_osp_material_out_group(uuid) from public,anon;
grant execute on function public.qcms_create_osp_material_out(uuid,jsonb,jsonb), public.qcms_update_osp_material_out_group(uuid,jsonb,jsonb), public.qcms_delete_osp_material_out_group(uuid) to authenticated;
notify pgrst,'reload schema';
commit;
