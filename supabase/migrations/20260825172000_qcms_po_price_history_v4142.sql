-- QCMS v4.14.2 - Purchase Order source visibility + full price history
-- Additive only. Existing rows and transactional data are preserved.

alter table public.part_supplier_price_history
  add column if not exists freight numeric,
  add column if not exists tool_cost numeric,
  add column if not exists packing_forwarding numeric,
  add column if not exists profit numeric,
  add column if not exists icc_rejection numeric;

comment on column public.part_supplier_price_history.price is
  'Controlled supplier/FSI Part basic rate used for PO price history and default PO unit price.';
comment on column public.part_supplier_price_history.freight is
  'Optional freight component for the controlled price revision.';
comment on column public.part_supplier_price_history.tool_cost is
  'Optional tool cost component for the controlled price revision.';
comment on column public.part_supplier_price_history.packing_forwarding is
  'Optional packing and forwarding (P&F) component for the controlled price revision.';
comment on column public.part_supplier_price_history.profit is
  'Optional profit component for the controlled price revision.';
comment on column public.part_supplier_price_history.icc_rejection is
  'Optional ICC/rejection component for the controlled price revision.';
