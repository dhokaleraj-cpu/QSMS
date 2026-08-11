# QSMS Release 4.9.5

## Compact A4 Portrait RMTC Record

This release refines the RMTC Record print layout requested after the v4.9.4 preview.

### Print layout

- RMTC Record PDFs use A4 portrait only.
- The report header, all section bars, every table grid, footer rule and page-number area use one common printable edge.
- Column widths are recalculated for portrait A4 so borders finish at the same right edge as the header.
- Chemical Composition, Jominy, DI/Hardenability, Mechanical Properties, Heat Treatment/Other Requirements and validation remain controlled grid sections.
- Validation is reformatted into a readable paired-status grid instead of an excessively wide 12-column landscape-style table.
- Repeated worksheet page breaks and the forced final validation page break are removed. `CondPageBreak` is used only to prevent orphan headings, allowing content to flow into the minimum practical page count.
- Table fonts and cell paddings are compacted while retaining readable status highlighting.
- Header/footer canvas logic now reads the active page size, so existing landscape reports remain landscape while RMTC uses portrait.

### Data safety

No schema reset or data deletion is included. Existing Supabase users, masters, RMTC records, Material Inward records, OSP transactions, inspections, attachments, audit history and permissions are preserved.
