# QCMS 4.12.2 — Supply Chain Master-Linked Traceability

Build: `4122-SUPPLY-CHAIN-MASTER-LINKED-TRACEABILITY`

## Scope

This release extends the Supply Chain module without resetting any existing QCMS transaction or master data.

- Customer Order / Schedule: master-linked Customer, Part, Material Grade and Raw Material details; six months of monthly schedule quantities/dates entered in one horizontal row.
- Customer Order Excel Import: reads only columns A–F after the detected header row (`Item`, `Description`, `Order no.`, `PosNr`, `Quantity`, `Delivery date`). Matching Customer + Order No. + PosNr records are not duplicated. Changed values are previewed and require explicit confirmation before update.
- RM Procurement: only customer-order RM balances pending procurement are presented, sorted by upcoming customer delivery date.
- RM Receipt: existing Material Inward is the single source of truth. The Supply Chain RM Receipt is linked/mirrored from Material Inward and carries RMTC Number, RMTC Date, RMTC Quantity, Heat Number and Heat Code.
- Sequential queues: each stage lists only pending output from the immediately previous stage rather than repeating the full Customer Order list.
- Genealogy: Material Inward / Heat / Heat Code / linked record IDs are carried through RM-to-Forging, Forging, Machining, Finished Goods and Customer Dispatch.
- Global search: searchable registers and pending queues throughout Supply Chain, including Supply Chain Traceability.
- Exports: PDF and Excel download options on Supply Chain registers, queues and selected contexts.
- Controls: edit controls on Supply Chain entries and current-password-confirmed permanent delete via the existing QCMS delete service.
- Status display: complete/closed/received/dispatched states are green; overdue/rejected are red; pending is orange; in-progress is blue. Completed flow cards use a green tick.
- Duplicate protection: punctuation/case/spacing-insensitive Customer Order import checks plus stronger matching-word checks for human-readable controlled master names.
- Readability: staged section titles are reduced by approximately 20%, while normal application text is increased by approximately 10% from the prior release.

## Database migration

Run `APPLY_ONCE_SUPABASE_v4.12.2.sql` once before deploying the application update. The migration is additive and does not reset existing data.
