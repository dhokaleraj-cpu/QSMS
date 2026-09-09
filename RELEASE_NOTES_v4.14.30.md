# QCMS v4.14.30 — RMTC Supplier Dedup / Bend Test Discovery / Global Search

Build: `41430-RMTC-SUPPLIER-DEDUP-BEND-GLOBAL-SEARCH`

## Controlled scope

- **RMTC Approved Raw Material Source — one Supplier only:** the selector now groups Part Master source data by Supplier and shows exactly one selectable row for each approved Supplier. Repeated Raw Material Detail or approval rows no longer create repeated Supplier lines.
- **Exact Raw Material genealogy preserved:** after choosing the Supplier, a separate **Raw Material Detail** field selects the required active Part Master section / section size / forging route. If only one detail exists it is selected automatically. RMTC continues to persist the exact `selected_source_detail_id` rather than losing source genealogy during de-duplication.
- **Approved-source setup guard preserved:** an approved Supplier with no ACTIVE Raw Material Detail remains visible with a setup warning and RMTC save remains blocked until the required Part Master Raw Material Detail is completed.
- **Dedicated Bend Test access:** Bend Test is no longer hidden only inside the general MetLAB workflow. Dedicated **Bend Test Entry**, **Bend Test Records** and **Bend Test Reports** routes are available from Inspections, Records and Reports, plus a Bend Test card on Inspection Home.
- **Bend Test still uses the controlled MetLAB layout model:** no duplicate database report type was introduced. `layout_type=METLAB` remains authoritative and Bend Test is filtered by controlled `inspection_method=BEND_TEST` metadata.
- **App-wide Global Search:** a persistent search field is available in the application shell and a dedicated **Search → Global Search** page searches major QCMS masters and transaction registers.
- **Global Search coverage:** supports Part Number, FSI Part Number, Part Name, Heat Number/Code, RMTC, FSI/production batch, Vendor Batch, Supplier/Customer/OSP Vendor, PO/order numbers, reports, complaints, inspection layouts, NPD/APQP, gauges/calibration and Standard Room records where the identifier is available in the controlled register.
- **Relationship-aware search:** Part and Party matches expand through controlled foreign-key links so searching a Part Number or Supplier/Customer can surface linked RMTC, Inward, OSP, Supply Chain and Quality records even when the transaction stores only the master ID.
- **Permission-aware search:** results are filtered through the existing QCMS effective module View permission engine and the same Repository/Supabase tenant/RLS controls. Global Search does not grant access to a module the employee cannot view.
- **Controlled record opening:** search results open the source record through existing controlled edit/navigation logic; Bend Test records route to the dedicated Bend Test entry.

## Preserved v4.14.29 functions

The v4.14.29 horizontal Chemical Analysis, Bend Test starter characteristics/report formatting, Case Depth Traverse checkbox and multiple locations, reusable MetLAB references, highlighted Conclusion/Final Decision, all-module section permissions and expanded OSP batch identity remain preserved.

## Database / deployment

This is a **source-only** controlled release. No new Supabase migration is required. The required database baseline remains the already-applied and verified **v4.14.28** contract.

The macOS updater must preserve all production/master/RMTC/OSP/Quality/Supply Chain/NPD/Complaint/Calibration data, Git history, `.env`, `.streamlit/secrets.toml`, uploads, logs, exports, virtual environment and Supabase link state.
