# QUALITY CONTROL MONITORING SYSTEM 4.10.1

Live Supabase-first Quality Control, RMTC, OSP and inspection workflow for Four Star Industries.

Visible workspaces:

1. Dashboard
2. Masters
3. RMTC
4. Material Inward
5. OSP Transactions
6. Inspections
7. Records Centre
8. NPD / APQP
9. QC Calculation Tools
10. Templates
11. Reports




## Release 4.10.1 — Customer Standards Bank, Rich Selection & NPD Card Status

- Added controlled **Customer Standards & Specification Bank** with standard code/name, author/issuing authority, revision number/date, Customer, related Process and private downloadable attachment.
- Added multiple Customer Standard links inside Part Master, including direct attachment download and Part Master PDF listing.
- Process Master now shows related customer standards and allows direct controlled attachment download.
- Selection fields now use richer Code · Name · important-detail labels across the central masters and major transaction/inspection workflows, including RMTC Supplier and Steel Mill selection.
- NPD Order Process Status now renders each pending Part as one horizontal card row with process cards beside it instead of a dataframe grid.
- NPD pending-status PDF uses the same visual colors: green Completed, blue In Process, amber Pending, red Overdue and purple On Hold.

## Release 4.10.0 — Universal Delete, My Account, Master Import & One-Screen NPD Status

- Password-confirmed delete controls across user-facing masters, transactions, inspections, NPD/APQP and QC calculation records, subject to module Delete permission.
- New **My Account** page for every signed-in user to change their own login password after verifying the current password.
- Removed the legacy First Administrator field/tab from the login page.
- Added one-screen **Order Process Status** matrix: each pending Part Number / Order is one row with process operations, real-time status and target dates beside it.
- Added Excel/CSV **Master Import** for every controlled master definition, with update-not-duplicate behavior.
- Standard and OSP MetLAB support four microstructure photographs with individual titles; RMTC supports three photograph titles.
- Records Centre and pending NPD process status provide controlled PDF printing to every user with View access.


## Release 4.9.7 — NPD / APQP Process Flow & Real-Time Order Status

- New top-level **NPD / APQP** module.
- Part-wise **Process Flow Designer** using Process Master and operational sequence numbers (0, 10, 20, ...).
- **NPD Status** order entry with Customer, Part, Order Qty, Start Date and Delivery Date.
- Order-specific process cards with target dates and real-time Pending / In Progress / Completed / Hold / Overdue status.
- Process status editor for target date, completed date, responsible person and remarks.
- **APQP** project header, standard APQP gates and completion dashboard.
- Additive Supabase migration; existing QCMS data remains intact.

## Release 4.9.6 — Global Heat Balance, QCMS Branding and Controlled PDF Reports

- Visible application identity changed to **QUALITY CONTROL MONITORING SYSTEM**.
- Added a common application and print footer with developer attribution, email, copyright owner and app version.
- RMTC print header shows Heat Number before RMTC Number, with Heat Number 50% larger.
- Added Global Heat Quantity Balance & Record List to RMTC Entry and RMTC PDF.
- Added three RMTC microstructure photograph slots and included the photographs in the RMTC Record PDF.
- Added A4 portrait PDFs for MetLAB, OSP MetLAB / Dimensional, Final Inspection and Material Inward records.
- Existing Supabase data remains preserved.

## Release 4.9.5 — Compact A4 Portrait RMTC Print Layout

- RMTC Record PDF is now fixed to **A4 portrait**.
- Report header, section bars, data tables and footer share the same left/right edge for a controlled aligned print layout.
- Every RMTC section remains in bordered table-grid form, including Chemistry, Jominy, DI/Hardenability, Mechanical Properties, Heat Treatment/Other Requirements and Validation.
- Worksheet and validation sections flow continuously without forced page breaks so the report uses the minimum practical number of pages.
- Header/footer rendering now adapts to both portrait RMTC reports and existing landscape operational reports.
- Existing Supabase masters, RMTC records, OSP/inspection transactions, users, permissions and attachments are unchanged.

## Release 4.9.4 — Workflow Spacing and RMTC Record PDF

- Increased application, title-card, KPI-card and submenu spacing to stop labels and workflow content from overlapping.
- Rebuilt workflow progress charts as spacious colour-separated cards with current, completed, pending, hold and rejected state symbols.
- Applied the workflow-card treatment to RMTC and OSP progress visualizations and removed the repeated OSP workflow navigation row.
- Added a controlled **RMTC Record PDF** from the RMTC Records page.
- The RMTC PDF includes RMTC header/traceability fields, covered Part Worksheets, Chemical Composition, Jominy Results, DI/Hardenability, Mechanical Properties, Heat Treatment/Other Requirements, validation status and final decision.
- PDF sections use bordered table grids, repeated Four Star/QSMS header and footer, page numbering and status highlighting.
- Existing Supabase masters, RMTC records, transactions, attachments and inspection data remain unchanged.

## Release 4.9.3 — High-Contrast Export Shipment App Theme

- Corrected the washed-out QSMS shell and menu backgrounds seen on Streamlit Cloud.
- Added Streamlit 1.60+ compatible keyed-container selectors so the navy-to-blue header always renders.
- Applied the Export Shipment Monitoring System light-blue application background and Aptos/Segoe UI font stack.
- Increased contrast for inactive and active module buttons, module submenus, user panel and app launcher.
- Prevented Streamlit stale-rerun opacity from making menus and header text unreadable.
- Kept the single main menu and single active-module submenu introduced in v4.9.2.
- No Supabase table, user, attachment, transaction or existing Part Master data is deleted or reset.

## Release 4.9.2 — Simplified MetLAB Requirements, Process Master and Unified Print Theme

- Removed the legacy Heat Treatment Details and broad OSP Process & Inward Specifications grids from Part Master.
- Added a dedicated Process Master for controlled In-house and Outsourced process definitions.
- Added **OSP Inspection for MetLAB**: select the outsourced Process, then maintain only Parameter, Minimum Specification and Maximum Specification.
- Added **Metallurgical Requirements**: Part-level final drawing requirements without a Process selection, using the same three-column grid.
- OSP MetLAB layouts are created from the selected Part + OSP Process requirements only.
- Final Metallurgical layouts are created from the Part-level Metallurgical Requirements only.
- OSP inspection queues now skip inspection types that are not required by the Part + Process configuration.
- Reworked the persistent main menu and module submenu to the approved navy/blue Export Shipment visual style.
- Suppressed duplicate page-level navigation bars.
- Added a consistent Four Star Industries header, footer, page number and blue report theme to PDF and Excel report outputs.
- Existing Heat Treatment and OSP specification data remains preserved in Supabase but is no longer shown in the simplified Part Master interface.

## Release 4.9.1 — OSP Process Parameter Groups and Heat/OSP Reports

- Part Master groups all OSP parameters under the selected Part Number and OSP Process.
- Every parameter supports minimum, maximum, unit, characteristic type, inspection type and checking method.
- One optional process drawing can be attached to each Part + OSP Process group.
- Approved Dimensional and MetLAB layouts are generated directly from the grouped process parameters.
- Generated layouts retain their source process group and drawing metadata.
- Added Heat Number Global Balance with full RMTC, Material Inward, OSP Out and OSP Inward transactions.
- Added Heat/Part-wise OSP outward, inward, quantity at vendor and balance available to send.
- Reports support Excel download and live Heat/Part filters.
- Existing QSMS records and attachments remain unchanged.

## Release 4.8.6 — Supplier RMTC Identity & Heat Steel Ledger

- The same Heat Number may be used by multiple RMTC records only when the Supplier RMTC Number is different.
- Supplier and Part Number may repeat when the supplier has issued a new RMTC number.
- The Heat Steel Ledger lists Part-wise planned quantity, planned steel, inward quantity, inward steel, global Heat quantity and balance.
- Heat Steel Ledger records can be downloaded to Excel.
- Global Heat steel validation remains shared across every RMTC, supplier, part and inward transaction.
- Existing records remain unchanged.


## Release 4.8.4 — Unified Records and Inward Status Consistency

- Add a prominent **Add New RMTC for This Heat Number** action while retaining the searched Heat Number.
- Permit a new RMTC for the same Heat Number when Supplier or Part Number differs, while active duplicate Supplier–Part combinations remain blocked.
- Add one Records Centre page covering RMTC, Material Inward, Dimensional, MetLAB, Inspection Layouts and Masters.
- Use one enriched Material Inward register for Dashboard, Inward Entry and Inward Records so counts and statuses match.
- Show Supplier and Part names instead of UUIDs on Dashboard and registers.
- Show existing Hold Pending Inspection inward records directly on the Material Inward entry page.

## Release 4.8.3 — Heat Number Search and Global Steel Ledger

- Search the Heat Number before creating an RMTC.
- View every RMTC, Supplier, Part Number, planned quantity and steel usage under that Heat Number.
- Reuse a rejected RMTC Heat Number for a new Supplier or Part Number.
- Prevent active duplicate Supplier–Part combinations.
- Enforce one global steel balance across all RMTC and Material Inward transactions for the Heat Number.

## Release 4.8.2 — Automatic Master Codes and Dashboard Analytics

- RMTC certificate quantity is treated as the total steel quantity for the complete Heat Number.
- Every covered Part Worksheet records Part Production Quantity, supplier Input Weight and calculated Planned Steel Quantity.
- Total planned steel across all parts cannot exceed the RMTC heat steel quantity.
- Material Inward splits production into Accepted, Rejected and On Hold quantities in pieces and calculates each steel quantity automatically.
- Cumulative steel consumption across all inward transactions and all parts for the Heat Number cannot exceed the RMTC steel quantity.
- MetLAB reports support four private microstructure images with individual captions.
- Supplier forging parameters are inherited from the Part Master and displayed in source selection.
- Dimensional and MetLAB layouts are automatically selected from approved Part + Process + Inspection Stage layouts, with manual override.
- Layout name and layout type/section are inherited automatically.
- Dimensional characteristics are generated from the selected approved layout.
- Raw Material MetLAB mirrors the RMTC Part Worksheet with Chemistry, Jominy, Heat Treatment / Mechanical Requirements and additional layout characteristics.
- Multi-row grid saves use bulk Supabase upsert to reduce submission time.

## RMTC Workflow

Save the RMTC header, complete each Part Worksheet, submit for validation, validate against masters, and record the authorized final decision. Manual acceptance remains available with a mandatory reason and audit history.

## Local run

```bash
cd /Users/dhokaleraj/QSMS
source .venv/bin/activate
python -m streamlit run streamlit_app.py --server.port 8510
```

## GitHub

```bash
./scripts/push_github.sh
```

Local Supabase secrets remain in `.streamlit/secrets.toml` and are excluded from Git.


## Release 4.8.2 — Automatic Master Codes and Dashboard Analytics

- Automatic editable codes for Customers, Suppliers, Steel Mills, OSP Vendors, Approved Sources, Processes, Inspection Stages and Quality Assets.
- Expanded KPI dashboard with steel and production totals.
- Pie charts for recent inward disposition, RMTC validation status and inward status.
- Existing records and codes remain unchanged.

### Heat Steel Ledger
The same Heat Number may have multiple RMTC records only when the Supplier RMTC Number is different. The Heat Steel Ledger lists Part-wise planned steel, inward steel, global Heat quantity and balance.
