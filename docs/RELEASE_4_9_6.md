# QSMS 4.9.6 — QCMS Branding, Global Heat Balance and Controlled PDF Reports

## Release scope

This release continues the Quality Control Monitoring System production branch without resetting or deleting existing Supabase users, masters, RMTC records, material inward records, OSP transactions, inspection reports or attachments.

## User-facing changes

- Renamed the visible application identity everywhere to **QUALITY CONTROL MONITORING SYSTEM**.
- Added a common web footer on every route with developer attribution, email, copyright owner and application version.
- Added the same controlled footer and version on every PDF page.
- RMTC PDF header now shows **Heat Number before RMTC Number**, with Heat Number exactly 50% larger in font height.
- Added **Global Heat Quantity Balance & Record List** to RMTC Entry and the RMTC controlled PDF.
- Added exactly three controlled **RMTC Microstructure Photograph** slots and included the photographs in the RMTC PDF.
- Added controlled A4 portrait PDF output for **MetLAB**, **OSP MetLAB / OSP Dimensional**, **Final / Dimensional Inspection**, and **Material Inward** records.
- The MetLAB report follows the laboratory-report structure used by Four Star: traceability header, parameter/specification/observation grid, microstructure photographs, conclusion and approval sign-offs.

## Data safety

The release is additive and preserves existing production data. Microstructure image storage uses the existing controlled document attachment register. The included SQL migration only adds optional RMTC metadata columns and does not alter or delete existing records.
