# QCMS v4.14.29 — RMTC / Bend Test / Chemical Grid / Case Depth / Permissions

Build: `41429-RMTC-BEND-CHEM-CASEDEPTH-PERMISSIONS`

## Controlled scope

- **RMTC Approved Raw Material Source:** source options now come from Part Master Approved Sources (`part_supplier_links`) and are matched to the ACTIVE Raw Material Detail needed for weight/section/route genealogy. An approved Supplier/Steel Mill no longer disappears simply because the old RMTC selector only read `part_raw_material_details`. If the Raw Material Detail is missing, the approved source remains visible and is clearly blocked until setup is completed.
- **Section permissions:** Users & Access exposes section-wise View/Create/Edit rows for every QCMS module, including Material Grade, Reference Masters, Employee Master, Material Inward, Inspection Layouts, QC Calculation Tools and Users & Access itself.
- **Bend Test:** MetLAB Inspection Layout Master adds `BEND_TEST` as an Inspection Method / Sub Category. New Bend Test layouts can start with Baking Temperature, Baking Time, Base Metal Hardness below plating, Load, CHT, Bend Angle, Bend Test Status and Plating Surface Condition.
- **Bend Test output:** controlled PDF title and sections use BEND TEST REPORT, BAKING / AGING, BEND TEST RESULTS and Bend Test evidence/photo labels.
- **Chemical analysis:** linked Raw Material MetLAB chemical values are entered horizontally. Controlled order is C, Mn, Si, S, P, Cr, Ni, Mo, V, Al, Cu, Nb, Ti, then configured extras, with Al/N2 Ratio last when configured. The PDF uses the same horizontal order.
- **Case Depth Traverse:** each MetLAB characteristic has an explicit Case Depth Traverse checkbox and Traverse Location. Multiple checked characteristics create multiple traverse locations while preserving legacy Case Depth parameter-name behavior for historical layouts.
- **Reusable references:** MetLAB Specification Reference and Reference Documents / Statements are selectable from reusable controlled values and newly entered values are remembered after save.
- **Conclusion:** optional Conclusion Remark is persisted in MetLAB results and appears as a separately highlighted report row. Conclusion, remark and Final Decision use differentiated fill/font styling in PDF and Excel output.
- **OSP selectors:** FSI Batch Number, Vendor Batch Number and source batch/lot identity are shown more explicitly in OSP transaction selectors/register context.

## Database / deployment

This is a **source-only** controlled release. No new Supabase migration is required. v4.14.29 reuses existing `inspection_plan_characteristics.layout_metadata`, MetLAB `results` JSON and `master_value_catalog` capabilities already present in the controlled v4.14.28 database baseline.

The macOS updater must preserve all production/master/RMTC/OSP/Quality/Supply Chain/NPD/Complaint/Calibration data, Git history, `.env`, `.streamlit/secrets.toml`, uploads, logs, exports and Supabase link state.
