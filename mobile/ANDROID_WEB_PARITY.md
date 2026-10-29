# Android ⇄ website parity matrix (QCMS v4.14.49 R39 · Android app v3.7.0)

Generated from `streamlit_app.py` (PAGE_ITEMS / ROUTE_MODULE) and the Android catalogue (`Cat*.java`, `Notif.ROUTE_MODULES`).
Status: **NATIVE** = native Android screen/module; **WEB LINK** = opens the website page inside the app (reason below);
**MISSING** = no native screen yet (the route opens the website page in the app). Owner = R39 agent responsible.

**Web routes: 124 · native: 121 · web link: 3 · missing: 0**

| Route | Web title | Web group | Android module / screen | Status | Owner |
|---|---|---|---|---|---|
| `dashboard` | Dashboard | Dashboard | Home tab · KPI start dashboard (KpiHomeScreen) | NATIVE | G |
| `deployment-diagnostics` | Deployment Diagnostics | Admin | In-app website page (WebScreen) | WEB LINK | A |
| `masters` | Masters | Masters | Masters tab (module KPI groups + masters) | NATIVE | G |
| `company-branch-entry` | Company Branch Master | Masters | `company_branches` · Company Branches | NATIVE | A |
| `company-branch-records` | Company Branch Records | Masters | `company_branches` · Company Branches | NATIVE | A |
| `rmtc-entry` | RMTC Entry | RMTC | `rmtc` · RMTC Approvals | NATIVE | Q |
| `rmtc-approved-worksheet` | Approved RMTC Part Worksheet | RMTC | `accepted_rmtc_parts` · Accepted RMTC Parts | NATIVE | Q |
| `inward-entry` | Material Inward | Inward | `inward` · Material Inward | NATIVE | Q |
| `osp-home` | OSP Transactions | OSP | `osp_register` · OSP Register | NATIVE | O |
| `supply-chain-home` | Supply Chain | Supply Chain | Supply tab (module KPI groups + modules) | NATIVE | G |
| `supply-customer-orders` | Supply Customer Orders | Supply Chain | `customer_orders` · Customer Orders / Schedules | NATIVE | G |
| `supply-opening-stock` | Opening Stock & Import | Supply Chain | `opening_stock` · Supply Chain Opening Stock | NATIVE | G |
| `supply-rm-procurement` | Supply RM Procurement | Supply Chain | `rm_po_stages` · Raw Material Orders | NATIVE | G |
| `supply-purchase-orders` | Supply Purchase Orders | Supply Chain | `purchase_orders` · Purchase Orders | NATIVE | O |
| `supply-po-order-list` | Purchase Order List | Supply Chain | `purchase_orders` · Purchase Orders | NATIVE | O |
| `supply-po-edit` | Edit Purchase Order | Supply Chain | `purchase_orders` · Purchase Orders | NATIVE | O |
| `supply-po-pdf` | Purchase Order PDF | Supply Chain | `purchase_orders` · Purchase Orders | NATIVE | O |
| `supply-po-approval` | Purchase Order Approval | Supply Chain | `po_approval` · Purchase Order Approval | NATIVE | O |
| `supply-rm-receipt` | Supply RM Receipt | Supply Chain | `rm_receipts` · RM Receipt · Material Inward Link | NATIVE | G |
| `supply-rm-dispatch` | Supply RM to Forging | Supply Chain | `rm_dispatches` · RM to Forging | NATIVE | G |
| `supply-forging` | Supply Forging | Supply Chain | `forging_orders` · Forging Orders | NATIVE | G |
| `supply-downstream` | Supply Downstream | Supply Chain | `downstream_events` · Part Production / Customer Dispatch | NATIVE | G |
| `supply-traceability` | Supply Traceability | Supply Chain | `traceability` · Traceability | NATIVE | G |
| `supply-order-mis` | Supply Order MIS | Supply Chain | `customer_orders` · Customer Orders / Schedules - Customer Orders module (orders / schedules / dispatch); MIS pivot charts web-only | NATIVE | G |
| `indirect-purchase` | Indirect Purchase | Indirect Purchase | `indirect_purchase_orders` · Indirect Purchase Orders | NATIVE | O |
| `indirect-requisition` | Indirect Purchase Requisition | Indirect Purchase | `indirect_requisitions` · Purchase Requisitions | NATIVE | O |
| `indirect-po` | Indirect Purchase Order | Indirect Purchase | `indirect_purchase_orders` · Indirect Purchase Orders | NATIVE | O |
| `indirect-po-list` | Indirect PO Register | Indirect Purchase | `indirect_purchase_orders` · Indirect Purchase Orders | NATIVE | O |
| `indirect-po-approval` | Indirect PO Approval | Indirect Purchase | `indirect_po_approval` · Indirect PO Approval | NATIVE | O |
| `indirect-inward` | Indirect Inward (GRN) | Indirect Purchase | `indirect_grns` · Indirect Inward (GRN) | NATIVE | O |
| `indirect-items` | Indirect Item Master | Indirect Purchase | `indirect_items` · Indirect Item Master | NATIVE | O |
| `indirect-stock` | Indirect Stock & Issue | Indirect Purchase | `indirect_stock` · Indirect Stock Ledger | NATIVE | O |
| `npd-process-flow` | Process Flow Designer | NPD & APQP | `npd_flows` · Process Flow (NPD) | NATIVE | G |
| `npd-status` | NPD Status | NPD & APQP | `npd_orders` · NPD Orders | NATIVE | G |
| `apqp` | APQP | NPD & APQP | `apqp_projects` · APQP Projects | NATIVE | G |
| `ppap-home` | PPAP | Engineering | `ppap` · PPAP Document Manager | NATIVE | P |
| `ppap-package` | PPAP Package | Engineering | `ppap` · PPAP Document Manager | NATIVE | P |
| `ppap-templates` | PPAP Element Templates | Engineering | `ppap` · PPAP Document Manager | NATIVE | P |
| `qc-tools` | QC Calculation Tools | QC Calculation Tools | `qc_calculations` · QC Calculation Tools - QC Calculation Tools (NpdCalcScreen calculators + saved records) | NATIVE | G |
| `qc-calculation-records` | QC Calculation Records | Dashboard | `qc_calculations` · QC Calculation Tools | NATIVE | G |
| `complaints-home` | Complaint Management | Complaints | `customer_complaints` · Customer Complaints | NATIVE | G |
| `customer-complaint` | Customer Complaint | Complaints | `customer_complaints` · Customer Complaints | NATIVE | G |
| `supplier-complaint` | Supplier Complaint | Complaints | `supplier_complaints` · Supplier Complaints | NATIVE | G |
| `complaint-analysis` | Complaint Analysis & CAPA | Complaints | `customer_complaints` · Customer Complaints | NATIVE | G |
| `complaint-records` | Complaint Records | Dashboard | `customer_complaints` · Customer Complaints | NATIVE | G |
| `customer-complaint-register` | Customer Complaint Register | Complaints | `customer_complaints` · Customer Complaints | NATIVE | G |
| `supplier-complaint-register` | Supplier Complaint Register | Complaints | `supplier_complaints` · Supplier Complaints | NATIVE | G |
| `complaint-email-settings` | Complaint Email Configuration | Complaints | `email_server` · Email Settings - Admin › Email Settings (notification routes, templates, schedules) - complaint routes edited there | NATIVE | G |
| `calibration-validation` | Calibration & Validation | Calibration & Validation | `calibration_records` · Calibration / Validation | NATIVE | G |
| `standard-room-inspection` | Standard Room Inspection | Calibration & Validation | `standard_room` · Standard Room Inspection | NATIVE | G |
| `inspection-home` | Inspections | Inspections | Quality tab (module KPI groups + modules) | NATIVE | G |
| `records-center` | Records Centre | Dashboard | `records_centre` · Records Centre | NATIVE | G |
| `heat-ledger` | Heat Steel Ledger | Dashboard | `heat_ledger` · Heat Steel Ledger | NATIVE | Q |
| `reports-home` | Reports | Reports | `reports_centre` · Reports Centre | NATIVE | G |
| `heat-transaction-report` | Heat Transaction Report | Reports | `rep_heat_transactions` · Heat Transaction Report | NATIVE | G |
| `osp-balance-report` | OSP Heat Balance Report | Reports | `rep_osp_balance` · Heat OSP Balance | NATIVE | O |
| `supply-chain-report` | Supply Chain Order / Dispatch Report | Reports | `customer_orders` · Customer Orders / Schedules - Customer Orders module (orders / schedules / dispatch); MIS pivot charts web-only | NATIVE | G |
| `rmtc-report` | RMTC Report Register | Reports | `rmtc` · RMTC Approvals | NATIVE | Q |
| `inward-report` | Material Inward Report Register | Reports | `inward` · Material Inward | NATIVE | Q |
| `dimensional-report` | Dimensional Inspection Reports | Reports | `dimensional_reports` · Dimensional Reports | NATIVE | G |
| `metlab-report` | MetLAB Reports | Reports | `metlab_reports` · MetLAB Reports | NATIVE | G |
| `complaints-report` | Complaint Reports | Reports | `customer_complaints` · Customer Complaints | NATIVE | G |
| `traceability-report` | Supply Chain Traceability Report | Reports | `traceability` · Traceability | NATIVE | G |
| `npd-report` | NPD Status Report | Reports | `npd_orders` · NPD Orders | NATIVE | G |
| `apqp-report` | APQP Status Report | Reports | `apqp_projects` · APQP Projects | NATIVE | G |
| `qc-report` | QC Calculation Reports | Reports | `qc_calculations` · QC Calculation Tools | NATIVE | G |
| `inspection-layout-report` | Inspection Layout Reports | Reports | `inspection_layouts` · Inspection Layouts | NATIVE | G |
| `standards-report` | Customer Standards Reports | Reports | `customer_standards` · Customer Standards | NATIVE | G |
| `inventory-reports` | Inventory & Stock Reports | Reports | `inventory_reports` · Inventory & Stock Reports - GenInventoryScreen: 5 reports, filters (search / values / date & number ranges), totals, Excel/PDF/print/email | NATIVE | G |
| `templates` | Templates | Templates | In-app website page (WebScreen) | WEB LINK | G |
| `part-entry` | Part Master Entry | Masters | `parts` · Part Master | NATIVE | E |
| `part-records` | Part Master Records | Dashboard | `parts` · Part Master | NATIVE | E |
| `ecn-register` | Engineering Change Notes | Engineering | `ecn_register` · ECN / PCN Register | NATIVE | E |
| `process-entry` | Process Master Entry | Masters | `processes` · Process Master | NATIVE | E |
| `process-records` | Process Master Records | Dashboard | `processes` · Process Master | NATIVE | E |
| `grade-entry` | Material Grade Entry | Masters | `material_grades` · Material Grades | NATIVE | G |
| `grade-records` | Material Grade Records | Dashboard | `material_grades` · Material Grades | NATIVE | G |
| `reference-entry` | Reference Master Entry | Masters | `customers` · Customers - Masters › Parties (customers / suppliers / vendors) + Inspection Stages | NATIVE | G |
| `reference-records` | Reference Master Records | Dashboard | `customers` · Customers - Masters › Parties (customers / suppliers / vendors) + Inspection Stages | NATIVE | G |
| `employee-entry` | Employee Entry | Masters | `employees` · Employee Master | NATIVE | A |
| `employee-records` | Employee Records | Dashboard | `employees` · Employee Master | NATIVE | A |
| `user-access` | Users & Access | Admin | `user_access` · Users & Access | NATIVE | A |
| `email-settings` | Email Server & Notifications | Admin | `email_server` · Email Settings | NATIVE | A |
| `master-import` | Master Import | Masters | `master_import` · Master Import | NATIVE | A |
| `standards-entry` | Customer Standards Entry | Masters | `customer_standards` · Customer Standards | NATIVE | G |
| `standards-records` | Customer Standards Records | Dashboard | `customer_standards` · Customer Standards | NATIVE | G |
| `my-account` | My Account | Dashboard | `my_account` · My Account - GenAccountScreen (login info, password change); personal mailbox settings web-only | NATIVE | G |
| `about` | About STAWN QCMS | Dashboard | `about` · About STAWN QCMS | NATIVE | G |
| `notifications` | My Notifications | Dashboard | NotifScreen (bell / More › Notifications) | NATIVE | G |
| `licence-company` | Licence & Company | Admin | LicCompanyScreen (More › Licence & Company) | NATIVE | A |
| `stawn-developer` | STAWN Developer Console | Admin | DevConsoleScreen (More, STAWN developers only) | NATIVE | A |
| `rmtc-part` | RMTC Part Worksheet | RMTC | `rmtc` · RMTC Approvals | NATIVE | Q |
| `rmtc-records` | RMTC Records | Dashboard | `rmtc` · RMTC Approvals | NATIVE | Q |
| `rmtc-approval` | RMTC Approval | RMTC | `rmtc` · RMTC Approvals | NATIVE | Q |
| `rmtc-qr` | RMTC QR Codes | RMTC | RMTC QR Codes (IncQrScreen, below the RMTC modules) | NATIVE | M (R40) |
| `inward-records` | Material Inward Records | Dashboard | `inward` · Material Inward | NATIVE | Q |
| `osp-material-out` | OSP Material Out | OSP | `osp_material_out` · OSP Material Out | NATIVE | O |
| `osp-sample-receipt` | OSP Sample Receipt | OSP | `osp_register` · OSP Register - OSP Register record action 'Sample Receipt' | NATIVE | O |
| `osp-inward` | OSP Material Inward | OSP | `osp_receipts` · OSP Inward Receipts | NATIVE | O |
| `osp-dimensional` | OSP Dimensional | OSP | `osp_register` · OSP Register - OSP Register record actions 'Sample / Receipt Dimensional inspection' | NATIVE | O |
| `osp-metlab` | OSP MetLAB | OSP | `osp_register` · OSP Register - OSP Register record actions 'Sample / Receipt MetLAB inspection' | NATIVE | O |
| `osp-records` | OSP Records | Dashboard | `osp_register` · OSP Register | NATIVE | O |
| `inspection-layout-entry` | Inspection Layout Entry | Inspections | `inspection_layouts` · Inspection Layouts | NATIVE | G |
| `inspection-layout-records` | Inspection Layout Records | Dashboard | `inspection_layouts` · Inspection Layouts | NATIVE | G |
| `dimensional-entry` | Dimensional Report | Inspections | `dimensional_reports` · Dimensional Reports | NATIVE | G |
| `dimensional-records` | Dimensional Records | Dashboard | `dimensional_reports` · Dimensional Reports | NATIVE | G |
| `metlab-entry` | MetLAB Report | Inspections | `metlab_reports` · MetLAB Reports | NATIVE | G |
| `metlab-records` | MetLAB Records | Dashboard | `metlab_reports` · MetLAB Reports | NATIVE | G |
| `bend-test-entry` | Bend Test Report | Bend Test | `bend_tests` · Bend Test Reports | NATIVE | G |
| `bend-test-records` | Bend Test Records | Dashboard | `bend_tests` · Bend Test Reports | NATIVE | G |
| `bend-test-report` | Bend Test Reports | Reports | `bend_tests` · Bend Test Reports | NATIVE | G |
| `bend-layout-entry` | Bend Test Layout Master | Bend Test | `inspection_layouts` · Inspection Layouts | NATIVE | G |
| `global-search` | Global Search | Search | `global_search` · Global Search - GenSearchScreen; hits open the exact record (GenTarget: child → parent, no module → read-only record view) + Print PDF | NATIVE | G |
| `kpi-dashboards` | KPI Dashboards | KPI Dashboards | `kpi_dashboards` · KPI Dashboards - Live KPI (start page), Modules (KpiModules), My Dashboards (GenDashScreen), Detailed KPIs (GenKpiScreen) | NATIVE | G |
| `kpi-details` | KPI Details | KPI Dashboards | `kpi_dashboards` · KPI Dashboards - same as kpi-drilldown | NATIVE | G |
| `kpi-drilldown` | KPI Drill-down | KPI Dashboards | `module_kpis` · Module KPIs - KPI card → KpiRecordsScreen (qcms_kpi_drilldown → qcms_kpi_records → client drill); filter, CSV, Print PDF per row | NATIVE | G |
| `report-builder` | Report Builder | Reports | `report_builder` · Report Builder | NATIVE | G |
| `master-lists` | Master List Excel | Reports | `master_lists` · Master Lists | NATIVE | G |
| `system-settings` | System Settings | Admin | `system_settings` · System Settings | NATIVE | A |
| `print-designer` | Print Layout Designer | Admin | `print_designer` · Print Layout Designer | NATIVE | A |
| `email-send` | Send Email | Email | `email_send` · Send Email | NATIVE | G |
| `email-groups` | Email Groups | Email | `email_groups` · Email Groups | NATIVE | G |
| `email-my-settings` | My Email Settings | Email | In-app website page (WebScreen) | WEB LINK | G |
| `email-sent` | My Sent Emails | Email | `email_sent` · My Sent Emails | NATIVE | G |

## Web links / missing - reasons

* `deployment-diagnostics` (Deployment Diagnostics, owner A): Server / Streamlit deployment checks (secrets, Python packages) - meaningless on the phone; website page.
* `templates` (Templates, owner G): Excel import templates are generated by Python (openpyxl) on the server side; opened as the website page in the app.
* `email-my-settings` (My Email Settings, owner G): Personal mailbox password must never be stored on the phone (brief: SMTP credentials readable only by their owner); website page.

## Shared behaviour (agent G)

* KPI cards (start page, section tabs, Module KPIs, My Dashboards) open the records behind the number: `qcms_kpi_drilldown(p_card_key, p_limit)` →
  `qcms_kpi_records` (older DB) → client-side drill (contract `mobile/KPI_DRILL_CONTRACT.md`). Rows open the record natively; hold = Print PDF.
* Module infographic groups: `qcms_module_kpis(p_department, p_modules)` (groups hidden without `can_view` on `module_key`); fallback `qcms_module_cards`.
* Top bar "+": New transaction (permission-checked, `core/quick_add.py` list), New e-mail, New query, Ask QCMS AI, New dashboard.
* Search / notification / KPI rows: detail rows open their parent record (`GenTarget`, web `_resolve_target`); tables without an app module open a
  read-only record view with attachments and Print PDF (web record viewer dialog).
* Website-only by design: AI assistant (Search & AI), Excel template generation, deployment diagnostics, personal mailbox password.
