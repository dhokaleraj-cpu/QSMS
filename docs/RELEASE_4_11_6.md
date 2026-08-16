# QCMS 4.11.6 — High-Visibility Complaint Section Color Grading

Customer Complaint and Supplier Complaint entry forms now use distinct, visibly tinted section panels.

## Customer palette
- Complaint Details: blue
- Responsibility: teal
- Photographs & Multiple Attachments: lavender
- Containment / Root Cause / Corrective Action: amber
- Debit Note / Commercial Settlement: rose

## Supplier palette
- Complaint Details: violet
- Responsibility: green
- Photographs & Multiple Attachments: cyan
- Containment / Root Cause / Corrective Action: orange
- Debit Note / Commercial Settlement: metallic slate

The color is applied to the keyed container plus title strip and accent border so it remains visible across Streamlit DOM revisions. No database migration is required.

Build: `4116-COMPLAINT-SECTION-COLORS`.
