# QCMS 4.14.49 R10 — 3 October 2026

R9 acceptance review hardening (Forging Purchase Order source control):

- Server-side Forging PO gate runs before any database write; previously these rules were enforced only by the UI.
- FSI RM → Forging → Production: a Forging PO now requires an RM-to-Forger dispatch of the same Customer Order that is not already linked to an active (non-cancelled) Forging PO.
- The Forging PO supplier must be the forger the RM was dispatched to. The PO page now locks the Supplier list to that forger and blocks mixing dispatches sent to different forgers.
- FSI RM → Direct Production orders are rejected for Forging PO at the service level as well as in eligibility.
- Forging PO quantity per Customer Order cannot exceed the pending forging balance (order qty − active forging ordered qty).
- Eligible Forging PO Sources grid now shows Heat Code and "Forger (RM sent to)" for acceptance verification.
- Cancelled Forging POs release their RM dispatch for Cancel & Reissue (database cancel function already marks stages CANCELLED).

No SQL migration. No live database writes or emails during preparation.
