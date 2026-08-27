-- QCMS v4.14.15 · third Supply Chain route: FSI RM -> Direct Production
begin;

alter table public.supply_customer_orders
  drop constraint if exists supply_customer_orders_supply_flow_check;
alter table public.supply_customer_orders
  add constraint supply_customer_orders_supply_flow_check
  check (supply_flow in ('FSI_RM','DIRECT_FORGING','FSI_RM_DIRECT_PRODUCTION'));
comment on column public.supply_customer_orders.supply_flow is
  'QCMS controlled Supply Chain route: FSI_RM (RM -> forging -> production), DIRECT_FORGING, or FSI_RM_DIRECT_PRODUCTION (RM -> direct production).';

alter table public.supply_downstream_events
  add column if not exists source_rm_receipt_id uuid references public.supply_rm_receipts(id) on delete restrict;
create index if not exists idx_supply_downstream_rm_receipt
  on public.supply_downstream_events(tenant_id, source_rm_receipt_id)
  where source_rm_receipt_id is not null;

create or replace function public.qcms_supply_inherit_downstream()
returns trigger language plpgsql security definer set search_path=public as $$
declare
  fr public.supply_forging_receipts%rowtype;
  rr public.supply_rm_receipts%rowtype;
  ev public.supply_downstream_events%rowtype;
  source_flow text;
begin
  if new.event_type='MACHINING' then
    if new.source_forging_receipt_id is not null and new.source_rm_receipt_id is not null then
      raise exception 'Machining can be linked to either a Forging Receipt or a Direct-Production RM Receipt, not both';
    end if;
    if new.source_rm_receipt_id is not null then
      select * into rr from public.supply_rm_receipts
       where id=new.source_rm_receipt_id and tenant_id=new.tenant_id;
      if rr.id is null then raise exception 'Linked RM Receipt is invalid'; end if;
      select supply_flow into source_flow from public.supply_customer_orders
       where id=rr.customer_order_id and tenant_id=new.tenant_id;
      if coalesce(source_flow,'')<>'FSI_RM_DIRECT_PRODUCTION' then
        raise exception 'Direct RM-to-Production is allowed only for the FSI RM -> Direct Production flow';
      end if;
      new.customer_order_id:=rr.customer_order_id;
      new.inward_lot_id:=rr.inward_lot_id;
      new.heat_number:=rr.heat_number;
      new.heat_code:=rr.heat_code;
      new.source_forging_receipt_id:=null;
      new.source_event_id:=null;
    else
      if new.source_forging_receipt_id is null then
        raise exception 'Machining must be linked to a pending Forging Receipt or Direct-Production RM Receipt';
      end if;
      select * into fr from public.supply_forging_receipts
       where id=new.source_forging_receipt_id and tenant_id=new.tenant_id;
      if fr.id is null then raise exception 'Linked Forging Receipt is invalid'; end if;
      new.customer_order_id:=fr.customer_order_id;
      new.inward_lot_id:=fr.inward_lot_id;
      new.heat_number:=fr.heat_number;
      new.heat_code:=fr.heat_code;
      new.source_rm_receipt_id:=null;
      new.source_event_id:=null;
    end if;
  elsif new.event_type in ('FINISHED_GOODS','CUSTOMER_DISPATCH') then
    if new.source_event_id is null then raise exception 'This stage must be linked to the immediately previous Supply Chain stage'; end if;
    select * into ev from public.supply_downstream_events where id=new.source_event_id and tenant_id=new.tenant_id;
    if ev.id is null then raise exception 'Linked previous Supply Chain stage is invalid'; end if;
    if new.event_type='FINISHED_GOODS' and ev.event_type<>'MACHINING' then raise exception 'Finished Goods must be linked to Machining'; end if;
    if new.event_type='CUSTOMER_DISPATCH' and ev.event_type<>'FINISHED_GOODS' then raise exception 'Customer Dispatch must be linked to Finished Goods'; end if;
    new.customer_order_id:=ev.customer_order_id;
    new.inward_lot_id:=ev.inward_lot_id;
    new.heat_number:=ev.heat_number;
    new.heat_code:=ev.heat_code;
    new.source_forging_receipt_id:=null;
    new.source_rm_receipt_id:=null;
  end if;
  return new;
end; $$;

drop trigger if exists trg_qcms_supply_inherit_downstream on public.supply_downstream_events;
create trigger trg_qcms_supply_inherit_downstream
before insert or update of event_type,source_forging_receipt_id,source_rm_receipt_id,source_event_id,customer_order_id,inward_lot_id,heat_number,heat_code
on public.supply_downstream_events for each row execute function public.qcms_supply_inherit_downstream();

commit;
