# QCMS / QSMS cumulative handover — 4.14.49 R9

Release date: 3 October 2026. Supersedes R8; includes all R4–R8 source fixes. Base application version remains 4.14.49 and Android build identity remains 41449-ANDROID-SINGLE-NATIVE-DRAWER-V12. DEPLOYMENT_MANIFEST.json identifies this cumulative update as R9.

## Install and push

Download QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R9.command into Downloads, then run:

```bash
bash "$HOME/Downloads/QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R9.command"
```

The self-contained updater targets /Users/dhokaleraj/QSMS on main. It creates an external backup and safety stash, checks its embedded payload, copies the complete source while preserving local secrets/runtime files, installs missing declared dependencies, runs compile/readiness/regression gates, commits and pushes without force, then compares the local and remote commit IDs. Stop and read its error if a gate fails; do not bypass it. Backup locations are printed by the command.

The existing GitHub Android workflow builds on the main push using its configured Java 17 / Android API 35 environment. Download QCMS-FIRST-APP-APK from the successful workflow. The release archive contains Android source, not a newly compiled APK. This workspace has not pushed GitHub or tested an installed production APK.

R9 needs no new SQL migration: bend metadata is stored in the existing lab_tests.results JSON, photographs use existing controlled attachments, and procurement retains existing allocation tables. R8's preapplied multi-heat OSP migrations and checksum certificate remain included and unchanged. No live database records were modified and no emails were sent while making R9.

## Procurement flows

| Customer-order flow | Execution sequence |
| --- | --- |
| FSI RM → Direct Production | RM procurement PO → RM receipt → production/machining → later process/dispatch; no forging PO |
| FSI RM → Forging → Production | RM procurement PO → RM receipt → RM to forger → forging part PO → forging receipt → later process/dispatch |
| Direct Forging → Production | Direct forging PO → forging receipt → production; no FSI RM procurement PO |

Root cause: create_purchase_order accepted only FSI_RM although eligibility already accepted FSI_RM_DIRECT_PRODUCTION. Its save gate now uses FLOW_REQUIRES_FSI_RM, the same set used by eligibility.

For one RM procurement PO, select several eligible customer orders/schedules in the existing multiselect, including different parts. They must have a common supplier maintained in Part Master and valid price/HSN data. Edit each order's allocation in kg. The existing backend creates one header with material item lines, one source allocation per customer order, and separate RM execution rows for receipt genealogy. Compatible common supplier material codes may consolidate; different materials retain separate item lines. Supplier compatibility, saved procurement decision and remaining-balance checks remain enforced. Grid state is now scoped to the selected order set and supplier so edits do not carry across a changed selection.

The existing forging source selector waits for RM-to-forger dispatch for FSI_RM. Direct-production orders remain ineligible for forging. A regression verifies these source gates. Production execution of the entire receipt/forging chain was not performed during this release.

## Bend test

Both standalone and inward-linked Bend Test entry now show Part Bend Angle (degrees), optional for draft/legacy compatibility. Valid range is 0–360; NaN, infinity, negative, nonnumeric and greater-than-360 values are rejected before save. A missing value stays missing instead of becoming a fabricated zero measurement.

Photo slot 2 is explicitly labelled Part Bend Photograph; all four existing controlled evidence slots and captions remain available. Upload the actual part photograph there. PDF includes the angle and existing evidence image grid. Excel includes the angle in Report Summary. Save now also preserves inspection_method, reference_documents and conclusion_remark, which were previously dropped by the service; this keeps saved Bend Test reports classified and printable correctly.

## MetLab approval email

New reports and existing editable drafts offer Email notification after save. Tick it, review/edit To and CC, click Review & Confirm Email Recipients, confirm, then save. Changing recipients invalidates confirmation. Existing drafts default to email off to avoid accidental repeat notifications. The report and uploaded evidence are saved before approval notification; confirmation is cleared after a send attempt returns, so a later save requires renewed confirmation. The saved report ID is retained before attachment/email processing, reducing the risk of creating a second report after a later-stage failure.

This is an approval-request notification, not automatic final approval. Finalization permissions and validator/approver controls remain in place. Testing used a fake notification preview; it did not send real mail.

## Changed application files

- core/supply_chain_service.py — RM flow save gate.
- app_pages/supply_chain.py — multi-part guidance and selection-specific allocation/item grid state.
- core/inspection_service.py — preserve report metadata and validate/persist bend angle.
- app_pages/metlab_report.py — angle/photo entry, saved-draft confirmation/send controls and early retained report ID.
- core/reporting.py — bend angle in PDF and Excel.
- tests/test_r9_rm_bend_approval.py — 16 regression cases.
- DEPLOYMENT_MANIFEST.json — R9 revision and feature list.

The complete source includes earlier duplicate-login fixes, NaN-to-null serialization, PO approval quantity helper, overdue notification code, inward Layout Master isolation from Section H, current linked raw-part/supplier data (including 10199346 → 10121529), and multi-RMTC/heat OSP material-out functionality. See the included R7 and R8 handovers for their detailed contracts and historical live migration verification.

## Acceptance after deployment

1. For a known eligible FSI RM → Direct Production order, create an RM PO and confirm the erroneous Direct Forging rejection is gone.
2. Select two orders for different parts with one common supplier. Verify one PO, both item lines/allocations, and their separate receipt links and quantities.
3. For FSI RM → Forging → Production, complete normal PO approval and supplier confirmation, RM receipt and RM-to-forger stages. Then choose the dispatch as the forging PO source, verify the forger and heat references, and receive forging normally.
4. Save/reopen a Bend Test with an angle and photo. Check PDF and Excel, then confirm the selected approval recipients before requesting approval.
5. Check prior multi-heat OSP records and independent receipt/sample balances remain available.

Use controlled test records for acceptance. The release validation file distinguishes local regression results from unperformed production operations.
