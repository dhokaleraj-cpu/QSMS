# QCMS 4.11.0 — Central Records Navigation & Minimal Metallic UX

## Scope

This release is based on the standalone QCMS 4.10.9 application. It does not include or depend on the FSI combined/Enterprise trial application.

## Records navigation

All register/record pages are now owned by the main **Records** module. Operational modules contain entry, workflow, approval and analysis pages only.

Records now contains:

- Records Centre
- RMTC Records
- Material Inward Records
- OSP Records
- Dimensional Records
- MetLAB Records
- Inspection Layout Records
- Complaint Records
- QC Calculation Records
- Heat Steel Ledger
- Part Master Records
- Process Master Records
- Material Grade Records
- Reference Master Records
- Employee Records
- Customer Standards Records

When any of these pages is open, the top-level **Records** module remains active.

## Minimal metallic UI

The application shell was redesigned with a compact light-metallic visual system:

- neutral silver/white application background
- compact white metallic header with a thin steel accent
- smaller company/title/user blocks
- low-height top module rail
- compact second-level navigation with up to eight items per row
- lighter section headings instead of heavy filled bars
- smaller KPI/status cards
- reduced shadows and border radii
- denser form controls and data tables
- matching metallic login styling
- existing Aptos/Segoe UI typography retained

The design direction is influenced by modern internal-tool and ERP patterns: clear modular navigation, strong hierarchy, reduced visual weight, whitespace, and contextual rather than decorative color.

## Safety

No Supabase schema migration is required. Existing QCMS users, permissions, Parts, RMTC, inward, OSP, inspection, MetLAB, NPD/APQP, complaints, standards, attachments, calculations and transaction records are preserved.
