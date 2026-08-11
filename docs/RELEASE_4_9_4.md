# QSMS 4.9.4 — Workflow Spacing and RMTC Record PDF

## Scope

This release continues the live QSMS v4.9.3 application without deleting, resetting or migrating existing production data.

## UI and workflow improvements

- Enlarged page-title, section-title, status-card and submenu spacing so text remains readable on Streamlit Cloud and common desktop resolutions.
- Reworked `workflow_progress` into responsive, horizontally scrollable step cards.
- Every workflow step receives a distinct visual tone while state is still communicated independently by symbol and status class:
  - `✓` completed
  - `●` current
  - `○` pending
  - `!` hold
  - `×` rejected
- Removed the duplicated OSP page-link row beneath **OSP WORKFLOW** and replaced it with a six-step workflow progress chart.
- RMTC progress charts use the same visual language for RMTC Entry, Part Worksheet, Validation and Final Decision.

## RMTC Record PDF

A new **Download RMTC Record PDF** action is available from RMTC Records. The controlled PDF contains:

1. RMTC header and traceability data from RMTC Entry.
2. Covered Part Worksheet register.
3. Supplier RMTC mechanical-property data when recorded.
4. One detailed Part Worksheet per covered part including:
   - Part/material and production-plan data
   - Chemical Composition
   - Jominy Results
   - DI / Hardenability
   - Mechanical Properties
   - Heat Treatment & Other Requirements
5. Final validation-status grid and final decision.
6. Prepared/validated/approved metadata.

The document uses the standard QSMS navy/blue controlled-report header/footer, table grids, page numbering and semantic status highlighting.

## Data safety

No destructive Supabase operation is included. Existing users, masters, RMTC records, Material Inward, OSP, inspection transactions, attachments and audit history are preserved.
