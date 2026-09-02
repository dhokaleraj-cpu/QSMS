# QCMS v4.14.25 Release Notes

Build: `41425-PO-EDIT-MASTER-STATE-TRANSACTION-EDIT-PERFORMANCE`

## Purchase Order controlled edit
- Adds **Edit Selected Purchase Order** to the controlled PO register.
- Supplier and source finished-Part identities are immutable during in-place edit. Supplier change continues through Cancel & Reissue.
- Editable order/delivery/Ship-To/commercial/source-allocation fields are validated against downstream receipt quantities.
- Saving a revision returns the PO to `PENDING_APPROVAL`, clears prior approval, and resets supplier confirmation for reconfirmation after approval.
- Optional **Refresh Latest Master Data** (default ON) refreshes current HSN, RM details, technical-data snapshot, current price and price-history snapshot when the edited transaction is saved.
- Historical before/after values remain available through the existing row audit trail.

## Exact master/transaction record reload
- Fixes the video-reported condition where the selected master code/id was correct but other fields came from a previously selected record.
- Record-specific widget namespaces include the record id and database update timestamp.
- Reference Master saved values are always first in learned-value selectors.
- Applied across Company Branch, Reference, Employee, Part, Material Grade, Process, Inspection Layout and Customer Standards masters and major transaction editors.

## Controlled edit navigation
- Records Centre adds a consistent **Open Selected Record for Controlled Edit** action.
- It routes to the owning source module rather than bypassing approval, audit or genealogy rules.
- Material Inward, OSP, Dimensional, MetLAB, NPD/APQP, Complaints and Supply Chain transaction roots use controlled edit paths.

## PO performance
- Adds request/page memoization for repeated master and transaction reads.
- Replaces repeated per-order/per-PO database lookups with bulk totals/source/receipt grouping.
- Caches Company Branch and Supplier PO Confirmation lookups during the page render.

## Deployment
- Source-only. No new Supabase migration.
- Required DB baseline: v4.14.22 / `QCMS_V41422_FULL_READY`.
- Existing production data, secrets, Git repository/branch and Streamlit deployment are preserved.
