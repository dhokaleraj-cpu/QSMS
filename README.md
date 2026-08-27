# QCMS v4.14.15

## v4.14.15 controlled changes
- Adds Flow 3: Customer Order → RM Procurement → RM PO → RM Receipt → Direct Production/Machining → Dispatch, with all forging stages bypassed.
- RM Procurement and RM PO remain available for both FSI-RM flows; Forging PO/RM-to-Forger lists exclude the direct-production route.
- Material Inward/RM Receipt can become the Machining source for Flow 3 with Heat/Inward genealogy retained.
- Admin Email Settings now exposes a dedicated **TEST EMAIL TEMPLATE** section with manual To/CC and popup confirmation.

Current controlled build: `41415-DIRECT-PRODUCTION-FLOW-EMAIL-TEMPLATE-TEST`

This additive release retains every earlier QCMS workflow and adds:

- MetLAB Case Depth / Microhardness Traverse is driven strictly by **Additional Layout Characteristics** whose **Parameter** contains the words `Case Depth`.
- Case Depth locations (for example Ground Face / ID / OD) and their specifications are read-only in MetLAB and are derived from the matching layout characteristics; only distance-wise traverse readings are entered by the user.
- Specification text alone cannot activate the Case Depth Traverse.
- Raw Material Purchase Order current price resolves by **Part + Supplier + selected Raw Material Detail**, with UOM as a preference/fallback rather than a hard blocker, so valid RM price-history rows saved as PCS/NOS remain usable on KGS RM POs.
- Complete PO price revision history remains tied to the exact Raw Material Detail.
- New **Company Branch Master** stores reusable company/plant/address/GST/contact data.
- Logged-in Employee Master `Plant` resolves to the active Company Branch context shown across authenticated QCMS modules.
- Purchase Orders use Company Branch as the controlled issuing plant and Company Branch is also available as a Ship-To source alongside Customer, Supplier and Vendor/OSP masters.
- Existing PO snapshots and production/master/quality/Supply Chain/RMTC/OSP data are preserved.
