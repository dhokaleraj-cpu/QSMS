-- QCMS R28 result shown by the updater: one line per Part whose Raw Material row was restored
select p.part_number as part, coalesce(r.material_section_name, '') || ' ' || coalesce(r.section_size, '') as raw_material,
       r.status, (select count(*) from public.part_raw_material_technical_data t where t.raw_material_detail_id = r.id) as technical_rows
  from public.part_raw_material_details r join public.parts p on p.id = r.part_id
 where r.remarks like '%restored by QCMS R28%'
 order by p.part_number;
