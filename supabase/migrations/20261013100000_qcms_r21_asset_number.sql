-- QCMS R21 · run once in Supabase → SQL Editor (safe to re-run).
-- Asset Number for Quality Assets (gauges, fixtures, instruments) used by the Calibration module.
alter table public.quality_assets add column if not exists asset_number text;
create unique index if not exists uq_quality_assets_asset_number
  on public.quality_assets (tenant_id, lower(asset_number))
  where asset_number is not null and btrim(asset_number) <> '';
comment on column public.quality_assets.asset_number is 'Company asset register number (QCMS R21)';
notify pgrst, 'reload schema';
