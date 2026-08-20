# QCMS 4.12.5

Build: `4125-QUALITY-DECISION-EXPORT-MIS`

## MetLAB and Dimensional Reports

- Both linked and standalone report modes now use three distinct controlled fields:
  - **Conclusion** — report-level technical conclusion.
  - **Final Decision** — Pending / On Hold / Accepted / Accepted Under Reserve / Rejected.
  - **Decision Reason** — mandatory where required for Hold / Reserve / Rejection and controlled override cases.
- Standalone MetLAB and Dimensional reports can be finalized without trying to refresh a Material Inward quality gate when no inward/OSP parent exists.
- Entry and Records screens provide **Download / Print PDF** and **Download Excel Report** actions.
- Controlled PDF and Excel outputs show Conclusion, Final Decision and Decision Reason separately together with prepared/validated/approved traceability.

## Supply Chain Monthly Order / Dispatch MIS

- **B - Monthly Order / Dispatch Summary** is grouped by:
  - Month
  - Customer Name
  - Part Number
  - Part Description
- The summary keeps Order / Schedule Qty, Dispatched Qty, Pending Dispatch and Dispatch Achievement % for each customer/part/month combination.

## Database / Deployment

No new Supabase migration is required by v4.12.5. Existing report columns (`remarks`, `disposition`, `disposition_reason`) are used as controlled Conclusion / Final Decision / Decision Reason fields, preserving historical records and avoiding a separate SQL action.
