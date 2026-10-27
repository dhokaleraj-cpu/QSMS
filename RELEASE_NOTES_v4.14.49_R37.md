# STAWN QCMS v4.14.49 R37b (includes R37, R36b, R36, R35b, R35)

## R37b
- **Part Master price history now saves.**
  - **Cause:** the grid had no row id. Changing a row's Start Date or UOM inserted a new period that overlapped the old one, and Supabase refused it (partial save).
  - **Now:** rows keep their id, the whole grid is checked before saving, and the previous period is closed automatically.
- **Purchase Order amendment (Edit PO → Amend PO):**
  - **What you enter:** an amendment reason, an Effective Date (separate from the PO date), a new unit price and / or quantity per line (the latest price is suggested from price history for the effective date), and header changes.
  - **Numbering:** the PO number stays the same, and the amendment number increases (Amd 1, 2, …).
  - **Limits:** quantity is never below what has already been received.
  - **Price history:** a changed price is written to price history from the effective date.
  - **After saving:** the PO goes back to approval.
- **PO print / Excel:**
  - Every page carries "Amendment No. N · Amendment Date · Effective Date".
  - An amendment history section shows the old and new price and quantity per line.
  - All price revision rows of each line are printed, with no row limit.
- **Updater:** the OSP multi-source test no longer times out on the Mac.

## KPI dashboards
- **Clickable cards:** click any KPI card to open the list of the records behind its number. That list has filters, opens a record when you click a row, offers Preview / Download of the print PDF for a row, and exports the list to Excel / PDF. The number on a card and its record list always agree: all 126 module cards were checked on live data.
- **Module highlight cards:** 28 modules have their own card row, covering:
  - **Quality:** MetLAB, Dimensional, Bend Test, RMTC, Inward, OSP, customer and supplier complaints, Calibration, Standard Room, QC Calc
  - **Supply Chain:** customer orders, RM procurement, POs, RM receipt, RM to forging, forging, production / dispatch
  - **Other:** NPD / APQP, Masters, Indirect Purchase

  The rows are at the top of each module home page and in the KPI Dashboard's new "Modules" view, together with your own pending tasks.
- **"+" button (top right):** New transaction (only what you are allowed to create), New e-mail, New query (Global Search / AI), New dashboard.

## Print-layout PDFs everywhere
- **Every record:** preview and download its print PDF, in the same look as the Purchase Order. Records that already had their own layout keep it (PO, MetLAB, Bend, Dimensional, RMTC, Inward, complaints, QC calc, OSP challan, indirect PO / GRN). All other transactions and masters get a full record print with related lines, names instead of codes, attachments list, status watermark and page numbers.
- **Where:** Global Search results, the record view, Records Centre, the KPI lists and the entry / register screens.
- **Global Search:** clicking any result opens the record; anything without its own screen opens in a full record view with the PDF.

## OSP
- **Material Out:** now a full returnable delivery challan with:
  - challan number series and date
  - plant, vendor and ship-to
  - user, ship via, incoterm, expected return and payment term
  - item lines with value and GST
  - heat number and batch code
  - process to be done
  - totals and vehicle number

  The print matches your RETURNABLE DELIVERY CHALLAN. The bottom section records the vendor's return challan / invoice: number, date, quantity returned and balance. OSP Inward receipts count as returns automatically. Customer details never print.
- **OSP Dimensional draft save:** the save no longer fails for layout "CASE CARBURIZING 9265". The same layout the page offers is now accepted when saving.
- **OSP MetLAB post-receipt "Pending":** batches already released leave the pending list.
  - **Cause:** these jobs were released on draft MetLAB reports, and those drafts were deleted on 23 Oct.
  - **Still to record:** 00013 and 00020 have no post-receipt MetLAB report. They appear in a separate "released without report" list so the report can still be recorded.

## Indirect Purchase (new module)
- **Setup:** item master with categories and an Excel template, and purchase requisitions.
- **Indirect PO:** own IPO number series, approval route, edit with password and reason, cancel, e-mail to supplier, PDF / Excel.
- **Indirect Inward (GRN):** gate entry, invoice / DC, partial receipts and over-receipt tolerance.
- **Stock:** stock ledger, issue to department and stock register.
- It is completely separate from Direct POs and the supply-chain flow. Permission module: INDIRECT_PURCHASE (Procurement / Supply Chain / Management can create and approve by default).

## Apps
- **Android v3.5.0 and iPhone / iPad v1.2.0:**
  - clickable KPI and module cards
  - "+" menu
  - PDF preview / download on records and search results
