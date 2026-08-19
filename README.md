# QUALITY CONTROL MONITORING SYSTEM 4.12.2

## Release 4.12.2 — Supply Chain Master-Linked Traceability

- Build: `4122-SUPPLY-CHAIN-MASTER-LINKED-TRACEABILITY`.
- Sequential Supply Chain pending queues, master-driven inherited context and full Heat/Material Inward genealogy.
- Customer Order six-month schedule row and A–F Excel import with duplicate/change confirmation.
- Material Inward is the RM Receipt source of truth; RMTC Number/Date/Qty and Heat carry downstream.
- Supply Chain global search, coloured status cards/grids, PDF/Excel exports and password-confirmed delete.
- Section titles reduced ~20%; normal application fonts increased ~10%.


## Release 4.12.1 — Master-Driven Standalone Reports & Automatic OSP Layouts
- Standalone **MetLAB** and **Dimensional Inspection** reports now use the selected Part Master as the controlling source for Customer, Material Grade, Part Name, Drawing Number/Revision and approved supplier context.
- Standalone reports capture **Heat Number, Heat Code, Supplier/HT/OSP Batch Number, Internal/FSI Batch Number, Supplier Invoice/Reference, Quantity, Sample/Lot Reference and Supply/Process Condition** in the report header.
- **OSP Stage** selection loads only OSP processes configured for the selected part and automatically selects the approved OSP inspection layout generated from the Part Master process specification.
- OSP Process Specification, Process Drawing Number/Revision and OSP Vendor are carried into the transaction/report context.
- Final-stage MetLAB reports automatically prefer the controlled **Final Metallurgical** layout generated from Part Master metallurgical requirements.
- Controlled A4 PDF headers follow the supplied laboratory report structure and show Customer, Supplier/OSP Vendor, Material Grade, Heat/Batch traceability, quantity, condition, specification, process and drawing context.
- Database changes are additive only. Existing QCMS users, permissions, transactions, attachments, report records and IDs are preserved.
- Build: `4121-MASTER-DRIVEN-STANDALONE-REPORTS`.

## Release 4.12.0 — Supply Chain, Flexible Inspection Stages & Interactive Status Cards
- Adds an end-to-end **Supply Chain** module linked by one customer-order Master Reference from customer order/schedule through RM procurement, RM receipt, RM dispatch to forging, forging order/receipt, machining, finished goods and final customer dispatch.
- Purchase-order and monthly-schedule modes are supported. Monthly schedule references are generated as `PART_MM_YYYY`, and the same Customer + Part + Month cannot be entered twice.
- Customer-order quantity is converted from pcs to required RM kg using the selected forging supplier **Gross Weight** from Part Master Raw Material Details.
- Raw-material purchasing is protected by a database-level cumulative **125% maximum** of the customer-order RM requirement. Duplicate RM orders and duplicate forging orders for the same customer reference/supplier are blocked.
- Forging-supplier RM balance is tracked as material dispatched minus material consumed by forging receipts.
- The same customer Master Reference remains visible in RM purchase orders, receipts, forging dispatch/order/receipt and downstream machining/FG/customer dispatch records, with search-based traceability.
- Dimensional and MetLAB reports now support standalone **Raw Material Stage**, **OSP Stage** and **Final Dispatch Stage** entries without mandatory RMTC, inward-lot or production-batch linkage. Existing linked workflows remain available.
- NPD Status process cards are clickable. Users can update Status, Completed Date and Remarks from the selected card; overdue cards pulse red until resolved.
- Customer/Supplier Complaint Dashboard now displays NPD-style workflow cards showing complaint progression and overdue state.
- Part Master **E - Raw Material Details** supports multiple named raw-material sections and shows Supplier Name plus City/State/Country.
- Application form/UI font sizing is increased approximately 20% for readability while KPI/NPD cards are reduced approximately 20% in height.
- Existing QCMS data and transaction IDs are preserved; Supply Chain tables are new/additive.
- Build: `4120-SUPPLY-CHAIN-INSPECTION`.


## Release 4.11.8 — Global Collapsible A→H Workflow Sections
- QCMS now uses one reusable staged-section framework across multi-section workflows instead of page-specific section styling.
- Every staged section is collapsed by default. Users expand only the section they are actively working on.
- Section order is shown as A, B, C, D... and restarts naturally for each workflow/tab.
- One coordinated navy/blue color family is used throughout the app; each stage receives a progressively deeper light-blue grade rather than unrelated colors.
- Stage headings remain 26px, 900-weight bold, preserving the requested 100% title-size increase.
- The staged framework is applied to Customer/Supplier Complaints, Detailed Complaint Analysis, Part Master, Material Grade, Process Master, Material Inward, RMTC Entry/Part/Approval, Dimensional Inspection, MetLAB, OSP Inspection, NPD Process Flow/Order Status/APQP, Users & Access, and My Account.
- Dashboard, Inspection Home and multi-section Reports now use the same collapsed A/B/C… stage sequence. Records Centre retains its tab-separated register layout because each tab exposes one register rather than multiple simultaneous sections.
- Existing titled complaint photographs, multiple attachments, controlled drawing revision history, centralized Records navigation and Export Shipment-style shell are preserved.
- No database migration or data reset is required.
- Build: `4118-GLOBAL-STAGED-SECTIONS`.

## Release 4.11.7 — Collapsible A→E Complaint Stage Workflow
- Customer Complaint and Supplier Complaint now use five expandable stages: A Complaint Details, B Responsibility, C Photographs & Multiple Attachments, D Containment / Root Cause / Corrective Action, and E Debit Note / Commercial Settlement.
- Stage header text is 26px and 900-weight bold, approximately 100% larger than the historic 13px section title.
- Stage A opens by default; stages B–E stay collapsed until selected, reducing page height and improving focus.
- Existing Customer and Supplier color grading is preserved on each expandable stage.
- Titled photographs, multiple attachments, drawing revision history, centralized Records navigation and Export Shipment-style shell remain unchanged.
- No database migration or data reset is required.
- Build: `4117-COMPLAINT-STAGE-EXPANDERS`.


## Release 4.11.6 — High-Visibility Complaint Section Color Grading
- Customer Complaint and Supplier Complaint now use clearly different pastel backgrounds for Complaint Details, Responsibility, Photographs & Multiple Attachments, Containment / Root Cause / Corrective Action, and Debit Note / Commercial Settlement.
- The keyed complaint container itself is styled so Streamlit border-wrapper changes cannot hide the section background.
- Each section also has a matching title strip and left accent border while preserving high-contrast field labels.
- No database migration or data reset is required.
- Build: `4116-COMPLAINT-SECTION-COLORS`.



## Release 4.11.5 — Complaint Evidence Visibility, Section Grading & Header Grid

- Fixes Account / Exit overlap by placing the QCMS profile card and a separate horizontal Account / Exit row in the same dedicated right-side header zone.
- Customer Complaint and Supplier Complaint Entry always show the Photographs & Multiple Attachments section.
- New complaints may select multiple photographs before the first Save; every photograph receives its own mandatory title and is uploaded after the complaint record is created.
- Existing complaints support multiple titled photographs and multiple supporting attachments without overwriting earlier evidence.
- Customer Complaint sections use blue / teal / violet / amber / rose / green low-saturation grades.
- Supplier Complaint sections use violet / green / sky / orange / steel / olive low-saturation grades.
- Existing RCA/CAPA, complaint PDF media register, Drawing Revision History, centralized Records navigation and Export Shipment-style shell are preserved.
- No new destructive data operation is introduced.
- Build: `4115-COMPLAINT-EVIDENCE-HEADER-GRID`.


## Release 4.11.4 — Complaint Media & Header Layout Fix

- Customer and Supplier Complaint entries support titled photographs and repeatable multiple attachments.
- Complaint photographs are shown as thumbnails and remain linked to the complaint record.
- Multiple supporting documents can be uploaded in one action; each remains individually downloadable.
- Complaint PDF includes the photo/document register.
- Header profile, Account and Exit controls use dedicated columns/rows so they cannot overlap.
- Existing QCMS data, drawing history, Records navigation and Export Shipment-style shell are preserved.
- Build: `4114-COMPLAINT-MEDIA-HEADER-FIX`.

Standalone QCMS release. The combined Enterprise application is not part of this release.


## Release 4.11.3 — Controlled Drawing Revision History

- Part Master Controlled Drawings now record Drawing Number, Revision Number and Revision Date per released file.
- Finish, Forging and Heat Treatment drawings maintain full revision history.
- Releasing a new revision automatically sets the previous revision to INACTIVE without deleting or overwriting its stored drawing.
- Old drawings remain listed and downloadable from Drawing Revision History.
- Database controls prevent duplicate revision identities and enforce only one ACTIVE revision per drawing type.
- Current Finish Drawing Number/Revision in the Part header is derived from the active controlled Finish Drawing.
- Export Shipment-inspired QCMS header/menu theme and centralized Records navigation are retained.
- Build: `4113-DRAWING-HISTORY`.

## Release 4.11.2 — Export Shipment Header & Module Theme

- Restores the proven Four Star Export Shipment visual shell: navy-to-blue rounded header, white QCMS title, compact company/logo block, and a translucent user/version/date card.
- Shows a separate white `MODULES` heading bar followed by a transparent horizontal module rail.
- Only the active main module uses the blue gradient; inactive modules remain clean dark text on the light application background.
- Removes the standalone `Apps` launcher from the QCMS header because this release is the standalone QCMS application.
- Retains the centralized Records navigation from 4.11.0/4.11.1 and all QCMS data/workflows.
- Build: `4112-EXPORT-SHELL`.

## Release 4.11.1 — High-Contrast Zoho-Inspired White/Blue UI

- Fixes low-contrast/invisible application header and main menu introduced by overlapping legacy CSS.
- Uses a bright white application shell, dark readable typography, restrained blue active states and a very light warm/sky background.
- Keeps the QCMS 4.11.0 Records-centralization rule: all record/register pages remain under the main Records module.
- Preserves all existing Supabase data, authentication, module permissions and QCMS workflows.
- Build: `4111-ZOHO-VISIBLE-SHELL`.

Live Supabase-first Quality Control, RMTC, OSP and inspection workflow for Four Star Industries.

Visible workspaces:

1. Dashboard
2. Masters
3. RMTC
4. Material Inward
5. OSP Transactions
6. Supply Chain
7. NPD / APQP
8. QC Calculation Tools
9. Complaints / CAPA
10. Inspections
11. Records
12. Reports
13. Templates

**QCMS 4.11.0 navigation rule:** every register and records page is centralized under the main **Records** module. Operational modules now focus only on entry, workflow, analysis and approval.

The application UI uses a compact light-metallic shell with restrained steel-blue accents, reduced card height, lighter section hierarchy and denser ERP navigation.




## Release 4.11.1 — High-Contrast Zoho-Inspired White/Blue UI

- Centralized every Records/Register page under the top-level **Records** module.
- Removed duplicate Records items from Dashboard, Masters, RMTC, Inward, OSP, QC Tools, Complaints, Inspections and Reports submenus.
- Record pages keep **Records** active in the main application rail.
- Rebuilt the QCMS shell with a compact metallic silver/white visual system, steel-blue accents, smaller cards, thinner navigation and reduced shadows.
- Reworked page/section hierarchy, forms, KPI cards and data tables for a denser modern ERP experience.
- Matching metallic styling applied to the QCMS sign-in experience.
- No Supabase migration or data reset is required.


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