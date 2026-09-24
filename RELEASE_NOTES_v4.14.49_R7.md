# QCMS 4.14.49 R7

Linked raw forging/casting parts now supply current Section E details, valid supplier approvals and prices through the customer-order and forging-PO flow. For 10199346 → 10121529, the PO buys 10121529 and preserves 10199346 customer-order traceability.

The Part Master grid refreshes inherited values when the source/supplier is selected. Missing source rows, invalid approvals, unsuitable prices and unavailable live source verification stop the purchase flow with a validation message. Saved PO snapshots remain stable on reprint; explicit master refresh reloads linked source data.

The source raw part must own ACTIVE Section E rows, valid supplier approvals and current prices. The live check found these source rows/approvals missing on 10121529; no production data was modified.

Includes the full prior R6 fixes and GitHub Android build workflow. No new schema migration or Edge Function deployment. Use the R7 updater and handover; do not run earlier updater revisions afterward.
