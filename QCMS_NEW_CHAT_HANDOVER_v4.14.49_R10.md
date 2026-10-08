# QCMS / QSMS cumulative handover — 4.14.49 R10

Release date: 3 October 2026. Supersedes R9 and includes all R4–R9 fixes. Base version 4.14.49, build 41449-ANDROID-SINGLE-NATIVE-DRAWER-V12 (unchanged); DEPLOYMENT_MANIFEST.json release_revision = R10. No new SQL migration.

## Install and push

```bash
bash "$HOME/Downloads/QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R10.command"
```

Same self-contained updater pattern as R9: requires /Users/dhokaleraj/QSMS on main at VERSION 4.14.49; external backup + safety stash; payload SHA-256 check; installs source while preserving .env / .streamlit/secrets.toml / uploads / logs; compile, readiness, phase verification, focused R4–R10 regressions and full pytest; commit and push (no force); local/remote SHA comparison. GitHub Actions builds the Android APK on the main push.

## R10 changes (from R9 acceptance review)

Finding: R9 acceptance step 3 ("verify the forger and heat references") relied only on the UI. `create_purchase_order(po_type=FORGING)` accepted an FSI RM order with no RM dispatch, a dispatch belonging to another order or already used, a supplier different from the forger the RM was dispatched to, a Direct Production order, and quantities above the order balance.

Fix: `SupplyChainService._assert_forging_sources()` runs before the PO header insert:

| Flow | Rule |
| --- | --- |
| FSI RM → Direct Production | Forging PO rejected |
| FSI RM → Forging → Production | rm_dispatch.id required; dispatch exists, same customer_order_id, not linked to an active Forging PO, not repeated in the payload; dispatch.forging_supplier_id (when set) must equal PO supplier |
| Direct Forging → Production | no dispatch needed |
| All | total qty per order ≤ order_qty_pcs − active forging_ordered_pcs; COMPLETED/CANCELLED orders rejected |

UI (app_pages/supply_chain.py, Purchase Order page, Forging): Supplier options are intersected with the dispatch forger; dispatches to different forgers in one PO are blocked; eligible grid shows Heat Code and Forger (RM sent to).

Test fixture note: tests/test_r7_linked_raw_flow.py service() order now declares supply_flow DIRECT_FORGING and order_qty_pcs 100 (a forging PO without RM dispatch is the Direct Forging contract).

## Changed files

- core/supply_chain_service.py — `_assert_forging_sources` + call in FORGING branch.
- app_pages/supply_chain.py — supplier lock to dispatch forger; grid columns.
- tests/test_r10_forging_source_gate.py — 7 new regressions (dispatch inheritance of forger/heat/inward, missing dispatch, wrong forger, foreign/reused dispatch, cancel releases dispatch, direct-production rejection, qty balance).
- tests/test_r7_linked_raw_flow.py — fixture flow/qty.
- DEPLOYMENT_MANIFEST.json — R10 revision + r10_changes.
- RELEASE_NOTES / HANDOVER / VALIDATION R10.

## Acceptance after deployment (live, controlled test records)

1. FSI RM → Direct Production: create RM PO; no Direct Forging rejection. Try a Forging PO for it → rejected.
2. Two orders, different parts, common supplier → one RM PO, two item lines, separate allocations and receipt links.
3. FSI RM → Forging: PO approval + supplier confirmation → RM receipt → RM to forger → Forging PO: Supplier list shows only the dispatch forger; grid shows heat number/code and forger; receive forging.
4. Bend Test with angle + photo: save/reopen, PDF/Excel, confirm approval recipients.
5. Prior multi-heat OSP records and receipt/sample balances still available.
