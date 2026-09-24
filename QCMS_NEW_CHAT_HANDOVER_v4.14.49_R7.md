# QCMS 4.14.49 R7 handover

Prepared 24 September 2026. Supersedes the R6 delivery; contains the full cumulative source and Android First-App source.

## Requested business rule

Customer order part **10199346** consumes raw forging/casting part **10121529**. The finished part's Section E row is the link and supplier selection. The linked raw part's current Section E owns the purchasing specifications, supplier approvals and commercial data. The forging PO identifies **10121529**, and its source allocations still identify the customer order for **10199346**.

## Implemented flow

1. Select Forging or Casting, the linked raw part and supplier in the finished-part Section E grid. Changes to these driver cells refresh the grid immediately. Weights, grade, codes, HSN, lead time, section and route come from the linked source. The selected supplier's valid approval reference, supplier part number and validity dates appear below the grid. Save revalidates the source; edits to inherited values must be made on the raw part itself.
2. The source part must be ACTIVE. Its selected supplier must have an approved Section E supplier link whose validity includes today; empty date bounds are open ended. Missing, revoked, expired or future approvals stop purchasing.
3. Source selection reads the latest ACTIVE Section E row for the source part and selected supplier, ordered by updated_at, created_at and ID. Inactive rows and other suppliers are excluded. The raw part can own bar details; the finished link remains Forging/Casting. Maintain only the intended current row as ACTIVE where rows are not interchangeable revisions. Nested raw-part links are rejected with a clear message; use the part owning the purchasing details directly.
4. Customer order creation revalidates linked data and calculates its weight snapshot from the current source. It retains the finished part ID and finished-part link ID. Customer-order edits refresh linked weight as well.
5. Forging PO supplier choices use valid source rows. Preview and save use source technical data and source-specific price history. Piece prices accept NOS or PCS; per-kg prices, inactive prices and another raw-row's price cannot silently substitute. A covering current price is required.
6. The purchased item number is the raw part's part_number, e.g. 10121529; the customer's 10199346 remains in original-part and customer-order allocation genealogy. The PO saves source row ID, raw part number and approval references in its technical snapshot. Required material quantity uses the source weight.
7. Saved PO reprints retain linked source specifications and price-history snapshots. Explicit PO master refresh reloads source details and revalidates approvals/prices before allocation writes. Changing/removing the purchased source requires Cancel & Reissue. Existing historical POs are not automatically rewritten.
8. Source/master/approval/price reads used by this mechanism require live reads; a transient database failure cannot substitute cached source data.

## Live data prerequisite

The read-only data check in this work found raw part 10121529 ACTIVE (FSI number 1529), but **zero ACTIVE raw-material detail rows and zero approved supplier links on that raw part**. The finished part has links to it. This release deliberately does not copy finished-part values or invent supplier approvals.

Before using the new flow, open Part Master **10121529**, Section E, and maintain:

- Its ACTIVE purchasing raw-material row for each intended supplier, including grade, HSN, weights, lead time, section and route.
- Approved supplier source links with the correct approval reference and validity.
- Applicable current supplier price history linked to that raw-material row, in NOS/PCS for the forging PO, plus required technical heading/value rows.

Then select raw part 10121529 and that supplier on finished part 10199346, save, create the customer order, and create the forging PO. No live master data, POs, reports, emails, schema or Edge Functions were changed during this task.

## Changed application files

- core/raw_source.py — shared current-source resolver, approval validity and live-read validation.
- core/supply_chain_service.py — linked options, customer weights, source prices and technical snapshots, forging PO creation/revision/reprints.
- app_pages/part_master.py — reactive source grid, inherited cells, approval display and stable ID updates for linked rows.
- app_pages/supply_chain.py — source validation messages, valid supplier options and linked PO preview.
- core/repository.py — optional require_live read flag; default behavior for other callers retained.
- tests/test_r7_linked_raw_flow.py — behavior tests for source selection, stale data, validity, pricing, order/PO genealogy, revisions, reprints and connection failure.
- tests/test_v4143_part_supply_auth_opening_stock.py — obsolete form-only contract updated for the reactive grid.
- DEPLOYMENT_MANIFEST.json — R7 revision and features. Version/build identity stays 4.14.49 / 41449-ANDROID-SINGLE-NATIVE-DRAWER-V12 for release compatibility.

## Installation and GitHub build

Download QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R7.command into Downloads and run:

```bash
bash "$HOME/Downloads/QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R7.command"
```

Default project: /Users/dhokaleraj/QSMS, branch main, installed version 4.14.49. The updater makes an external backup and safety stash, verifies its embedded payload checksum, copies source without deleting runtime data, compiles, checks readiness, runs regression tests, commits and pushes origin/main, and compares the remote commit SHA. A rejected push stops without force-pushing. Local GitHub credentials and network access are required.

Secrets, runtime uploads/logs/exports and local Android SDK settings are excluded from source staging. Backup location is printed under $HOME/QSMS_BACKUPS. Recover uncommitted work from the named safety stash/backup; it is not automatically reapplied over the release. On a deployment problem, retain the backup and logs before restoring or reverting the release commit.

The bundled QCMS First-App Android APK workflow builds on GitHub after a main push using Java 17 and Android API 35. Download artifact QCMS-FIRST-APP-APK. This delivery is source; no APK build or GitHub push has been performed from this workspace. No new schema migration is required beyond existing v4.14.45. Production reminder Edge Functions are not redeployed by the updater.

## Prior fixes included

R4/R5/R6 source remains included: duplicate-login stability, PO approval quantity helper, save transition checks, non-finite JSON cleanup for MetLab saves, inward MetLab Layout Master isolation, and Section H restricted to final MetLab dispatch scope. Existing overdue PO approval responsibility controls and Android build workflow remain present.

## Verification and remaining acceptance

See QCMS_VALIDATION_v4.14.49_R7.txt for exact test results. Automated tests use a fake repository to exercise the complete linked forging-PO create path and controlled revision path. Live Streamlit interaction, database triggers/RLS and the GitHub APK build must be verified after installation. This workspace is a source snapshot, not the user's Git checkout.

Acceptance: load current approved source values in Section E; create order 10199346; verify PO item 10121529 and current price/weights; check original-order allocation; expire approval and confirm blocked creation; restore approval, revise source and verify explicit PO refresh; confirm old PO reprints remain unchanged.
