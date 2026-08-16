# QCMS 4.11.3 — Controlled Drawing Revision History

This standalone QCMS release extends Part Master Controlled Drawings without replacing existing Part, attachment, user, or transaction data.

## Controlled Drawing fields
Each Finish Drawing, Forging Drawing, and Heat Treatment Drawing release records:
- Drawing Number
- Revision Number
- Revision Date
- Controlled drawing file
- Status (ACTIVE / INACTIVE)
- Release timestamp
- Superseded timestamp

## Revision rules
- Releasing a new revision creates a new attachment record and a new Storage object.
- The prior ACTIVE revision of the same drawing type is automatically changed to INACTIVE.
- Historical drawing files are never overwritten by a normal new-revision release.
- All old revisions remain visible and downloadable in Drawing Revision History.
- Duplicate Drawing Number + Revision Number is rejected for the same Part and drawing type.
- Only one ACTIVE revision per Part + drawing type is enforced at database level.
- The active Finish Drawing updates the Part Master summary Drawing Number and Drawing Revision.

## Safety
The migration is additive. It adds drawing-control metadata to `document_attachments` and a permission-checked activation RPC. No existing attachment, Part Master, inspection, RMTC, OSP, complaint, user, or transaction data is reset or deleted.

Build: `4113-DRAWING-HISTORY`.
