# QCMS v4.14.1 - Additive Heat Capacity / MetLAB Traverse / Quality Decision / PO Price History

Build: `4141-HEAT-SUM-METLAB-TRAVERSE-LOGIN-APPROVAL-PO-PRICE`

## Controlled scope

This release is additive and preserves all v4.14.0 workflows and data. It does not reset or delete master, RMTC, inspection, OSP, Supply Chain, Purchase Order or notification data.

## RMTC - same Heat with different Supplier RMTC

- Heat Number remains the global material genealogy identity.
- Each distinct Supplier RMTC Number remains a separate RMTC certificate/record.
- The Global Heat certified steel quantity is now the **sum of the active, non-rejected certificate quantities** for that Heat Number.
- Example: Heat `H1` / Supplier RMTC `A` = 5,000 kg plus Heat `H1` / Supplier RMTC `B` = 3,000 kg gives Global Heat certified quantity = 8,000 kg.
- Existing committed/inward steel guards continue to prevent the combined capacity from being reduced below material already committed.
- Existing same-Heat + same-Supplier-RMTC duplicate protection remains unchanged.

## MetLAB

- Report Number is generated automatically; user entry is disabled for new reports.
- `METLAB_REPORT` sequence now prints year in `YY` format while preserving the existing yearly sequence counter.
- Parameter print serial numbers are always sequential `1, 2, 3 ...`.
- MetLAB PDF typography is 20% larger than the prior controlled report style and uses the page area more effectively.
- New multi-location **Case Depth / Microhardness Traverse** supports:
  - first point `0.05 mm`;
  - subsequent points `0.10, 0.20, 0.30 ... mm`;
  - up to 8 named locations (for example Ground Face / ID / OD);
  - in-app line-chart preview;
  - controlled PDF traverse table and Distance-vs-Hardness chart;
  - Excel Case Depth Traverse sheet.
- MetLAB Conclusion is now a controlled selection: Pending / On Hold / Accepted / Accepted Under Reserve / Rejected, with Conclusion Remark where required.
- Accepted conclusion is blocked when an applicable MetLAB result is out of specification or not evaluated.

## Dimensional / MetLAB edit and approval

- New/Edit pages have direct selectors to open existing reports.
- Draft report variable fields remain editable.
- FINAL reports can only be changed through **Controlled Amendment**; saving an amendment returns the record to DRAFT and clears prior validation/approval timestamps for fresh approval.
- Approved By is fixed to the active Employee Master record resolved from the current QCMS login.
- Database finalization rechecks both the module approval permission and the logged-in employee identity.

## Out-of-specification visual control

- FAIL observations in MetLAB and Dimensional PDF reports use bold red text with a light-red background.
- Reserve/Hold observations use bold amber styling.
- Result / Final Decision / controlled MetLAB Conclusion use status-aware colors.
- Excel report exports apply the same FAIL/HOLD/PASS visual logic to result and applicable observation cells.
- Enterprise table rendering also highlights observation cells when a row Result/Decision is FAIL, REJECTED, HOLD or Accepted Under Reserve.

## Purchase Order price revision history

- Part Master Supplier + FSI Part Price History includes `Remark` for each revision period.
- Purchase Order item snapshots retain Start Date / End Date / Price / Currency / UOM / Remark.
- Each printed PO Part item now includes its own **PRICE REVISION HISTORY** table directly below that Part's technical data.
- The original/customer Part Number confidentiality rule is unchanged; supplier-facing PO continues to use FSI Part Number.

## Verification

Release verification includes Python compile, online-readiness check, `verify_phase1.py`, and the complete pytest regression suite including the v4.14.1 acceptance tests.
