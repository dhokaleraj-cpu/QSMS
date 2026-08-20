# QCMS 4.12.4

Build: `4124-DUAL-SUPPLY-FLOW-MIS`

## Supply Chain Flows

1. **Flow 1 · RM Responsible FSI**
   - Customer Order
   - RM Procurement
   - RM Receipt / Material Inward
   - RM to Forger
   - Forging Order
   - Forging Receipt
   - Part Production
   - Customer Dispatch

2. **Flow 2 · RM Responsible Forger / Supplier**
   - Customer Order
   - Forging Order
   - Forging Receipt
   - Part Production
   - Customer Dispatch

RM Procurement, RM Receipt and RM-to-Forger pages automatically remain limited to Flow 1 records. Forging Order accepts either the pending Flow 1 RM-dispatch source or the pending Flow 2 Customer Order source.

## Material Inward

- Adds an explicit **Enable Supply Chain Link** switch.
- When enabled, the operator selects a pending RM Procurement record and the linked Customer Order/Part is inherited as a poka-yoke.
- When disabled, the Material Inward transaction is standalone and does not create a Supply Chain RM Receipt mirror.
- Existing linked inward records may be unlinked only when no downstream RM-to-Forger transaction exists.

## Order / Schedule MIS

- Adds a new **Monthly Schedule / Order MIS** page under Supply Chain.
- Filters: Month, Customer, Part Number, Order Type, Supply Flow and Status.
- Monthly summary: Order/Schedule Qty, Dispatched Qty, Pending Dispatch and Dispatch Achievement %.
- Detailed MIS: Customer Order/Monthly Schedule, PosNr, delivery date, order qty, dispatched qty, pending dispatch, latest dispatch reference/date, invoice and ASN.
- Customer/Part monthly aggregation.
- Global search plus PDF and Excel exports.

## Database / Deployment

No new Supabase migration is required by v4.12.4. The two-flow choice is stored backward-compatibly in the existing Customer Order controlled remarks metadata, while Flow 2 uses zero FSI RM requirement so the existing RM procurement queue naturally excludes it. Existing v4.12.3 records remain Flow 1 unless explicitly changed before downstream transactions begin.
