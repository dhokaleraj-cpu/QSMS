-- QCMS R23 · run once in Supabase → SQL Editor (safe to re-run).
-- Per-Purchase-Order print options: sections hidden on THIS PO's print (chosen at PO entry / PDF page).
alter table public.supply_purchase_orders add column if not exists print_options jsonb not null default '{}'::jsonb;
comment on column public.supply_purchase_orders.print_options is 'QCMS R23: {"show_source_reference": false, ...} overrides the Print Layout Designer for this PO';
notify pgrst, 'reload schema';
