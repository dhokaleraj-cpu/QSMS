# QCMS 4.11.4 — Complaint Media & Header Layout Fix

## Complaint entry media
- Customer Complaint and Supplier Complaint entries support repeatable titled photographs.
- Each photograph requires a Photograph Title and is retained as an individual controlled storage object.
- Multiple supporting files may be selected and uploaded in one action; previous files are never replaced.
- Photo and attachment registers remain linked to the complaint and are available from Detailed Complaint Analysis.
- Complaint PDFs include a Photographs & Attachments register with title, file name and upload time.
- Controlled file deletion continues to require the current QCMS password and Complaint Management archive permission.

## Header correction
- User information occupies its own dedicated header column.
- Account and Exit occupy a separate action rail, preventing overlap with the profile card.
- Export Shipment-style navy-to-blue QCMS shell remains unchanged otherwise.

## Data safety
- Additive migration only (`document_attachments.document_title` plus complaint attachment permission/storage rules).
- No complaint, drawing, RMTC, inward, OSP, inspection, user or attachment record is reset.

Build: `4114-COMPLAINT-MEDIA-HEADER-FIX`.
