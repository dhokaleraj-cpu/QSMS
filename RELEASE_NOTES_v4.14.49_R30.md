# QCMS v4.14.49 R30 — full native Android app v3.0.0 + spreadsheet grids (app and website)

## Android app v3.0.0 — every module native (no website pages)
Bottom tabs **Home · Supply · Quality · Masters · More**, ~75 modules, all reading and writing the same tables,
functions, numbering, statuses and validations as the website:
- **Supply:** Customer Orders / Schedules, Purchase Orders (create, edit, add orders, approve, cancel), PO approval,
  native PO PDF (B5 print layout, watermark, terms) + send to supplier with email preview, supplier confirmations,
  RM orders, RM receipt, RM to forging, forging orders / receipts, production / customer dispatch, opening stock, traceability.
- **Quality:** RMTC approvals (worksheet, decision), material inward, heat ledger / summary, dimensional reports,
  MetLAB, bend test, inspection layouts, OSP material out / register / receipts, calibration status, quality assets,
  calibration / validation records, part-process links, standard room, customer / supplier complaints (actions, follow-up, analysis, closure).
- **Masters:** Part Master (RM details with the R28 part-scoped save, Jominy, metallurgy, technical data, prices, sources,
  standards, drawings), material grades, Jominy distances, processes, inspection stages, branches, employees, customers /
  suppliers / mills / vendors, customer standards.
- **More:** NPD flow / orders, APQP, PFD / PFMEA / control plans, QC calculation tools, heat / OSP / inward / RMTC reports,
  global search, 10 KPI dashboards with charts, report builder, master lists, records (deletion requests, deleted records,
  activity log, email outbox), email send / sent / groups, My Account (password change) and Administration
  (users & access, system settings, email server, print layout designer, CSV master import).
- Photos from the camera on every record with attachments; CSV export / share from every grid.

## Grids that slide like Excel
- **App:** every grid is a spreadsheet canvas: slide in any direction (diagonal too) with momentum, pinch to zoom,
  frozen header row and first column, always-visible scroll bars, tap a row to open it, full-screen button.
- **Website:** every display grid has frozen header + first column, drag with the mouse / swipe with the finger in both
  directions, always-visible scroll bars, ◀ ▶ ▲ ▼ buttons, arrow keys and a quick filter box. Editable grids
  scroll inside a fixed height with the first column pinned.

## Database
No new SQL. The R28 recovery SQL (fixed in R29) is applied automatically if it is still pending.

## Not in the app (website only, by design)
Excel (.xlsx) import/export (CSV in the app), the AI assistant tab of Global Search, personal mailbox passwords
(My Email Settings) and the batch PO ZIP / batch supplier email.
