# QCMS v4.14.4

Build: `4144-METLAB-EDIT-MASTER-DUPLICATE-OPENING-IMPORT-SMTP-GUIDE`

## Corrective scope

- MetLAB plan selection no longer raises `StopIteration` when a saved or recommended plan is missing from the current active-plan list; historical saved plans are recovered when available and safe fallback is used otherwise.
- RMTC, MetLAB and Dimensional pages show a clear Edit Selected Record section. Final records can be reopened to Draft by verifying the current user password when that user has module Edit permission; Administrator role is not required.
- Master duplicate checking is identity-driven. Natural keys remain exact; fuzzy word duplicate checks are limited to explicitly mapped identity name/description fields. Reusable revision, manufacturer, model, designation, method, parameter, remarks and address data may repeat. Part Description remains repeatable.
- Customer Standard Bank validates Standard Code and Standard / Specification Name as identity fields.
- Opening Stock is a dedicated Supply Chain module with Excel template download, current-stock export, duplicate-safe import preview and new-row-only import. Opening Reference is the import identity control.
- Microsoft 365 error `535 5.7.139` is identified in the Email Server page as an Exchange Online SMTP AUTH policy issue, with mailbox/tenant checklist and STARTTLS settings.
- Existing v4.14.3 schema and production data are preserved; this source-only corrective release does not reset or migrate business data.
