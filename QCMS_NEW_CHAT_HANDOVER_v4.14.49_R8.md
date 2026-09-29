# QCMS 4.14.49 R8 — Multi-RMTC / multi-heat OSP Material Out

Prepared 29 September 2026. Cumulative successor to R7. Existing QSMS project: /Users/dhokaleraj/QSMS. Supabase project: xxrxopzxzyjnzumrwuwy.

## What the user requested

Send the same part to an OSP vendor using multiple RMTCs and different heat numbers under one Material Out document. Receive samples and full/partial inward quantities separately by batch. Preserve all existing heat-wise genealogy and quality gates.

## Operator workflow

1. Open **OSP Material Out** and select the part.
2. Use **Select RMTCs / Heat Numbers / Source Lots** to choose multiple released source lots. Choices show RMTC, supplier certificate reference, heat, inward/source batch and available pieces. The same heat text never substitutes for an exact inward or certificate ID.
3. Select one OSP process/specification and approved vendor. Enter one dispatch challan, dispatch date, expected return date and common remarks.
4. Enter **Out Qty pcs** and **Sample Qty pcs** independently for each source line. Save once. Up to 100 source lines are allowed per document; all must belong to the same part and tenant.
5. The system creates one Material Out header, named OUT- followed by the first generated OSP job number. It retains a separate existing OSP job and FSI child batch for every heat line.
6. In **Sample Receipt**, select the individual Material Out line / RMTC / heat / FSI batch. Record that batch's vendor batch number and sample. Dimensional and MetLab decisions remain specific to that heat batch.
7. In **OSP Material Inward**, select the sample-approved individual batch. Receive full or partial quantities against its remaining balance. Receiving or approving one heat does not receive or release another heat in the document.
8. Open **Multi-Heat Material Out Documents** to see all lines, download one consolidated Material Out PDF, or edit/delete the document under existing permissions and downstream safeguards.
9. The OSP register presents one summary per Material Out followed by heat-wise details. Legacy single-heat records remain available and retain their original identities.

## Data model and traceability

New `osp_material_outs` stores the document ID, document number, tenant, original request identity/payload and audit fields. Existing `osp_jobs` gains nullable `material_out_id` and `material_out_line_no`. Existing records are not backfilled or rewritten.

Each line retains its original source inward lot (and through it, RMTC approval and part approval), source batch, heat number/code, OSP child batch, vendor/process/specification, dispatched quantity, sample gates, partial receipts, quality reports and subsequent production/dispatch lineage. Physical heats must remain segregated and labelled; the shared document does not merge inventory or acceptance decisions.

The consolidated PDF lists all RMTC/heat/source inward/FSI batch/quantity lines. Individual transaction and inspection selectors show the common Material Out number plus RMTC and batch identity. Existing individual controlled inspection PDFs remain linked to their individual job/batch.

## Database behavior

- `qcms_create_osp_material_out`: one PostgreSQL transaction calls the existing dispatch routines for all lines. Any invalid line rolls back the header, all child jobs and all allocations. Deterministic source row locking and existing balance/release guards prevent over-allocation.
- Request UUID and tenant uniqueness provide retry protection. Replaying the same save returns the original document. Reusing that UUID with different input is rejected. The app rotates the request only after confirming every saved line.
- The wrapper validates source uniqueness, one source identity per line, matching part/tenant, date order, finite positive quantities and sample quantities no greater than 20 or that line's dispatched quantity.
- `qcms_update_osp_material_out_group`: updates the complete existing line set and common header fields atomically. The existing material-out update routine blocks changes after downstream sample/inspection/inward activity. Adding/replacing sources in an existing document is not supported; create a new document when appropriate.
- A deferred consistency trigger ensures common Part, Vendor, Process, Specification, challan, dates and remarks across a document. A separate guard prevents reassignment of a grouped heat line to another source/batch/document.
- `qcms_delete_osp_material_out_group`: uses the existing controlled delete routine for every line; if one line cannot be deleted, none are deleted. Each permitted deletion restores that line's source balance. Password confirmation and Archive permission remain in the UI.
- New RPCs are SECURITY INVOKER, require an authenticated session and relevant OSP permission, and are not executable by anon/PUBLIC. The new table has tenant RLS and audit/touch triggers.

## Database deployment already completed

Migration `supabase/migrations/20260929083249_qcms_r8_multi_heat_osp_material_out.sql` was generated with the Supabase CLI, passed a rollback-only schema dry run, and was applied to **xxrxopzxzyjnzumrwuwy** on 29 September 2026.

Post-apply verification confirmed RLS enabled, create/edit/delete RPCs present, SECURITY INVOKER, authenticated execution allowed, anonymous execution denied, and zero new material-out documents/grouped jobs. No business records or approvals were changed and no emails were sent. Security advisors reported no finding referencing the new feature. Existing unrelated advisories were not changed.

`supabase/preapplied/qcms_r8_multi_heat_osp_contract.json` records the verified project and migration hash. Supplemental migration `20260929085020_qcms_r8_osp_archive_lock.sql` was also applied and verified. Its UPDATE policy permits archive-only users to lock the document for controlled deletion, while WITH CHECK (false) prevents that policy granting header edits. The isolated database test confirms both behaviors. The Mac updater validates both migration hashes in that certificate locally and does not require a manual SQL step or Supabase CLI login. This certificate is for the specified production project; other installations must apply the bundled additive migration before enabling the source.

## Changed / added files

- core/osp_service.py — exact RMTC enrichment, document grouping, line validation and atomic RPC calls.
- app_pages/osp_transactions.py — multi-source entry, line quantities, document summary/PDF/edit/delete, batch-specific downstream labels. Existing material-out management remains accessible when there is no dispatch balance.
- app_pages/osp_inspections.py — common document/RMTC labels without changing heat-specific report IDs or quality gates.
- Supabase migration and preapplied certificate listed above.
- tests/test_r8_multi_heat_osp.py — validation, service routing, genealogy, independent queues and Streamlit multi-source submit tests.
- tests/sql/r8_osp_fixture.sql and test_r8_osp_transaction.mjs — isolated PostgreSQL tests of the migration/wrapper, using controlled doubles for existing legacy RPCs.
- DEPLOYMENT_MANIFEST.json — revision R8 and feature/schema certificate metadata. Application version/build stays 4.14.49 / 41449-ANDROID-SINGLE-NATIVE-DRAWER-V12 for compatibility with the cumulative release checks.

## Install and push

Download `QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R8.command` to Downloads:

```bash
bash "$HOME/Downloads/QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R8.command"
```

Default target is /Users/dhokaleraj/QSMS on main, version 4.14.49. The updater creates an external backup and safety stash, checks its payload and migration certificate hashes, preserves Git history/secrets/runtime data, copies cumulative source without deleting unrelated runtime files, compiles, runs readiness/phase checks and the full Python suite, commits, pushes origin/main and compares local/remote commit SHAs. A rejected push stops without a force push.

Existing production Edge Functions and reminder schedules are not redeployed. A successful GitHub main push triggers the existing **QCMS First-App Android APK** workflow; download **QCMS-FIRST-APP-APK** from its artifacts. The app source/GitHub push/APK build have not been deployed from this workspace; run the updater to publish this release.

Backups are printed under $HOME/QSMS_BACKUPS. Preserve the backup and safety stash. Recover local modifications deliberately rather than blindly applying an older updater over this release. The additive schema may remain when reverting source; old records and older source do not require its removal.

## Validation and acceptance

Exact results are in QCMS_VALIDATION_v4.14.49_R8.txt. The isolated PostgreSQL checks exercise native transactions, permissions, RLS, trigger consistency and rollback; they do not replace live end-to-end acceptance of every existing production RPC/trigger. Streamlit AppTest verifies selecting two sources and submitting one RPC. No real production dispatch was created for testing.

After deployment, use released RMTCs for the same part with different heats. Verify one header/PDF and two independent FSI batches; receive a sample against only the first batch and confirm the second remains pending; approve that first sample and receive a partial inward; verify only its balance changes. Confirm over-allocation and invalid-line saves create no partial document, and downstream activity blocks an unsafe document edit/delete.

All prior R7 fixes remain included: raw-part Section E purchasing authority, supplier approval validity, customer-order traceability, inward-only Layout Master MetLab rules, final-only Section H, NaN save cleanup and earlier login/save/PO stability fixes.
