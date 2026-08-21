# QCMS v4.13.4 — Priority UI, Reusable RMTC Balance & Duplicate-Safe Imports

Build: `4134-PRIORITY-UI-RMTC-REUSE-DUPLICATE-SAFE-IMPORT`

## UI priority refresh

- Replaces display-only Streamlit dataframes with a deterministic enterprise HTML grid so table headers, borders, rows, status badges and numeric alignment render consistently in local and Streamlit Cloud environments.
- Enforces visible bordered pockets for forms, read-only/display fields, cards and reusable containers.
- Keeps maroon page/section hierarchy and stronger staged/collapsible section headings.
- Keeps the public login isolated from the application navigation and uses a cropped Four Star factory image sized to the reference frame.
- Retains the global footer: `Developed by Rajesh Dhokale | dhokaleraj@icloud.com | Copyrights by STAWN`.

## RMTC reusable balance

An Accepted / Accepted Under Reserve RMTC may be used in more than one Material Inward / production allocation for the same or another **already-approved covered part**. The RMTC's certificate steel quantity is the global cumulative consumption ceiling.

- The original per-part planned quantity remains planning information and no longer blocks a later allocation while certified RMTC steel balance remains.
- Every inward allocation still requires an accepted covered-part decision and valid Part Master supplier / forging parameters.
- Global RMTC steel usage cannot exceed the certificate quantity.
- Existing production-batch allocation guards and material disposition controls remain active.

## Duplicate-safe imports

Imports are insert-only for natural-key duplicates:

- Master Import skips records already present in the database and skips repeated rows inside the same workbook.
- Customer Order import treats matching Customer + Order No. + PosNr as `SKIP_DUPLICATE`; existing orders are never overwritten by import.
- Reference workbook import creates only missing master/link records and never updates existing records.
- Inspection Layout import rejects a duplicate Part + Plan No. + Revision + Layout Type combination.

This is an additive/non-destructive release. Existing records are preserved.
