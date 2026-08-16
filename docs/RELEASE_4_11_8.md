# QCMS 4.11.8 — Global Collapsible Workflow Sections

Build: `4118-GLOBAL-STAGED-SECTIONS`

## User experience
QCMS now uses one reusable `stage_section()` framework for multi-section operational workflows. Each stage is labelled A, B, C, D... and is collapsed by default. The user expands only the stage needed for the current task.

## Color system
All workflow stages use the same QCMS blue family. Stage A begins with the lightest blue grade and later stages use progressively deeper light-blue grades while retaining high contrast. Unrelated multi-colour complaint palettes are removed.

## Covered workflows
- Customer Complaint / Supplier Complaint
- Detailed Complaint Analysis & CAPA
- Part Master
- Material Grade
- Process Master
- Material Inward
- RMTC Entry / Part Worksheet / Approval
- Dimensional Inspection
- MetLAB
- OSP Inspection
- NPD Process Flow / Order Entry / Order Status / APQP
- Users & Access
- My Account

Dashboard, Inspection Home and multi-section Reports use the same collapsed stage framework. Records Centre remains tab-separated because each tab is already a single focused register.

## Safety
No Supabase migration or production-data reset is required. Existing attachments, drawing revisions, complaint evidence and permissions are preserved.
