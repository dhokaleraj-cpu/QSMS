# QCMS v4.14.22

Build: `41422-PUBLIC-VERIFY-BLANK-MASTER-RMTC-RESET`

## Fixes
- Removes the updater dependency on Supabase CLI login / `SUPABASE_ACCESS_TOKEN` for an already-live schema. Read-only release verification uses the project's publishable Data API key.
- Master Data Centre entry action is now **New Record** and clears stale edit/widget state before opening the entry page.
- Part, Material Grade, Employee, Reference, Process, Company Branch, Customer Standards and Inspection Layout entry workspaces reset to a blank new record when launched from Master Data Centre.
- Same-Heat RMTC creation now hard-clears all prior certificate/covered-part/source/quantity/prepared-by widget state while retaining only the requested Heat Number and canonical Heat Code.
- Preserves v4.14.21 transaction delete routing and inline delete error handling.

No business data is reset or deleted by this release.
