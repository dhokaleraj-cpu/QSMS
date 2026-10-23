# STAWN QCMS v4.14.49 R36b (includes R36, R35b and R35)

## R36b additions
- **Customer details are internal only.** Customer name and code, customer PO / order number and position, customer part number, customer delivery date and customer documents never go to a supplier, vendor, steel mill, OSP vendor or any other outside address:
  - **Workflow e-mails:** if any recipient is outside the company, the e-mail is built customer-safe. Customer fields are blanked, PDFs carry no customer details, the PO prints without the customer source reference, and customer documents are not attached.
  - **Scheduled reminders:** the PO confirmation reminder to suppliers shows no customer, customer order no or customer part number, and uses the PO delivery date only. Supplier copies of overdue digests show the FSI part number only. Attached PDFs are customer-free.
  - **Purchase Order PDF / Excel:** the "PO Source Reference" (customer PO / position) is off by default. When ticked for an internal copy it prints stamped "INTERNAL COPY - CUSTOMER DETAILS - NOT FOR SUPPLIER". This also applies to the Android app's PO PDF.
  - **Send Email:** a warning appears whenever a recipient is outside the company.
- **APQP:**
  - Existing projects open again (the selector no longer jumps back to "New").
  - Saving a project updates it instead of creating a duplicate.
  - A register with search and filters lists all projects, with an Edit button on each.
  - Projects also open from Records Centre and Global Search.
- **Inventory & Stock Reports (Reports → Inventory & Stock Reports):**
  - five views:
    - stock by stage for every part
    - RM stock by heat, grade and section
    - forging / OSP stock by supplier
    - FG stock and dispatch
    - stock movement ledger
  - each view has filters, KPI cards, totals and Excel / PDF export
- **Filters on every report:**
  - search, choice lists, date ranges and number ranges, plus "Clear filters"
  - Excel and PDF exports follow the filters
- **Report Builder is in Reports**, with six new inventory data sources.

## Reminder e-mails with tables and attachments
- **PO confirmation pending (to the supplier, daily)**
  - The body has a full table: PO no / date, supplier, part number, FSI part, description, RM section, qty and unit, unit price, value, delivery date, plus totals.
  - Attachments: the PO print-layout PDF and an Excel sheet of the PO lines.
- **PO approval overdue (to approvers)**: the same table, including customer and customer order no, plus the PO PDF and the Excel sheet.
- **All scheduled overdue / open digests**
  - Covered: customer orders, RM procurement, RM and forging POs, OSP returns, calibration, complaints, CAPA follow-ups, NPD steps.
  - The body has a table of part number, description, customer, supplier, qty, price, value, due / delivery date and status.
  - Attachments:
    - the digest PDF
    - an Excel sheet
    - up to 10 record PDFs, such as POs and complaints (15 MB maximum)
- **2-day Excel digests**: the same table in the body, plus the PO PDFs.
- **How the PDFs are kept current**
  - The website saves the latest print-layout PDF of each record automatically: after every workflow e-mail, and every 30 minutes for records with a pending reminder.
  - Email Server & Notifications → "Reminder attachments" → "Prepare attachments now" saves them immediately.

## Delete trial data (STAWN developer only)
- **Where:** STAWN Developer → "Delete trial / test data".
  1. Pick a transaction module and the records.
  2. Preview every linked record that will be deleted, in all tables.
  3. Download an Excel backup.
  4. Confirm with the phrase `DELETE TRIAL DATA`, a reason and your password.
- **What is kept:**
  - Master data (parts, customers / suppliers, grades, employees) is never deleted.
  - Every deleted row is archived first, and each run is logged.
- **Who can use it:** only the STAWN developer login. Company administrators cannot see this section.

## Global search
- **Masters:** every master and detail table is now searched, for example chemistry, test plans, gauges / fixtures, part standards and APQP documents. Masters are ranked first.
- **Opening a result:** click any result row and the record opens.
  - A detail row (such as a layout characteristic, PO line, complaint action or RMTC chemistry) opens its parent record.
  - Attachments open their owner record.
  - Anything without its own screen opens in a full record view; attachments can also be downloaded there.

## iPhone / iPad without a paid Apple Developer membership
- Run `./BUILD_STAWN_QCMS_iOS.command free`.
- **How it works:** it uses your free Apple ID (Personal Team), and you install the app by cable from Xcode.
- **Limits:**
  - Re-install every 7 days.
  - No push notifications. The in-app bell and inbox still work.
