# QCMS v4.14.47 — PO watermark readability + approver stamp

- Purchase Order PDF watermark opacity is controlled at 20% using a very light grey watermark ink so document content remains readable behind APPROVED / PENDING APPROVAL.
- Approved Purchase Orders print a controlled digital approver stamp on page 1 at the bottom-right.
- Stamp shows APPROVED, approver Employee Master name/code, and the database approval date/time in IST.
- Pending Approval documents do not print an approval stamp.
- All previous Android v0.2.2 navigation, persistent login, v4.14.45 shared raw source and controlled layout functions are preserved.
- Database schema remains v4.14.45; no new Supabase migration is required.
