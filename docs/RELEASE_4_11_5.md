# QCMS 4.11.5 — Complaint Evidence Visibility, Section Grading & Header Grid

## Header layout correction
- The header uses three logical zones: company, QCMS title, and user/actions.
- The user card sits above a separate two-column Account / Exit row.
- Account and Exit have fixed equal heights and no vertical negative positioning, preventing overlap at normal desktop widths.

## Customer / Supplier complaint evidence
- Photographs & Multiple Attachments is visible directly on Customer Complaint and Supplier Complaint Entry.
- New complaints can select multiple photographs before the first save.
- Every selected photograph has its own mandatory title.
- New complaint evidence is uploaded immediately after the complaint record receives its ID.
- Existing complaints can add multiple titled photographs and multiple supporting documents without replacing prior files.
- Photo/attachment registers remain visible on the entry page and in Detailed Complaint Analysis.

## Color grading
- Customer entry: Details blue, Responsibility teal, Evidence violet, Action amber, Commercial rose, Follow-up green.
- Supplier entry: Details violet, Responsibility green, Evidence sky, Action orange, Commercial steel, Follow-up olive.
- Background tones are intentionally low saturation to preserve the Export Shipment-style QCMS shell and keep long forms readable.

## Safety
- Uses the existing additive v4.11.4 complaint-media schema.
- No existing complaint, attachment, drawing, RMTC, inward, OSP, inspection, user or permission record is reset.

Build: `4115-COMPLAINT-EVIDENCE-HEADER-GRID`.
