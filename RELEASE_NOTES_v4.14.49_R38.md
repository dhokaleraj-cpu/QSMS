# STAWN QCMS v4.14.49 R38

This release covers the website, Android app v3.6.0 and iPhone / iPad app v1.3.0. The database changes are already live, and the updater re-applies them safely.

## RMTC
- **QR code on approval.** When an RMTC is approved, QCMS creates a QR code (PNG) and attaches it to the record.
  - The QR opens the approved RMTC on the website, with downloads for the RMTC print PDF and the supplier test certificate. A QCMS login is required, so nothing confidential is public.
  - The RMTC number, heat, grade, supplier and approval date are printed beside the QR, so the label is useful without a phone.
  - The QR is printed on the RMTC print PDF.
  - **Print Label PDF (100 x 60 mm)** makes a label for the material storage location. It has a blank Location box.
  - Every active Quality / QA / QC employee gets an e-mail with the QR PNG and the RMTC PDF. If the e-mail fails, the approval still goes through.
- **Sections applicable.** For each RMTC you can choose which sections apply, such as Chemistry, Mechanical or Jominy.
  - The choice defaults to the Part Master setting.
  - Sections that don't apply are hidden from entry, validation, approval, records and print.

## Chemistry and Jominy grids (all modules)
- Chemistry grids are now horizontal: elements across the top, Min / Max / Actual down the side. This applies to entry, view and print.
- Jominy grids are horizontal too, with an extra **mm** row under each inch position. For example, J5/16" shows as 7.94 mm.

## PPAP Document Manager (new, under NPD & APQP)
- A PPAP package is linked to its APQP project, and you can open one from the other.
- The checklist has the 32 elements from your PPAP tracker. Each element has:
  - required / not applicable
  - responsible person, due date and status
  - file uploads that keep every revision
- Progress, overdue and due-soon figures are shown, along with tracker Excel import and export.
- **Download all** or **Download selected** gives a ZIP organised like your sample package, with a PSW / index PDF and the tracker Excel.
- **Send package to customer** goes only to that package's own customer.
  - Packages over 10 MB are sent as a 7-day download link.
  - Supplier addresses are blocked.
- Daily due / overdue e-mails go to the responsible person, and the package owner is copied.

## Part Master
- **Part Processes** (new section). For each operation you can set a mandatory flag and add optional drawings, specifications and work instructions, all with revision history.
- **ECN / PCN.**
  - Replacing a finish drawing or a process drawing now requires an ECN, using your FSI/806/F05 format.
  - The ECN has numbering, approval and implementation actions, plus a print PDF and Excel copy.
  - A new ECN is e-mailed to Quality and NPD.
- **Sections applicable.** Sections that don't apply are hidden in entry and left out of the Part Master print. The RMTC uses this setting as its default.

## Website shell
- The STAWN QCMS icon is now clearly visible in the header.
- The licensed company's logo is on the right of the ribbon, before your name.
- The app version now appears only in **User details** (the button next to Sign out).
- STAWN Developer Console → section H: add, replace or reset the login page cover photo.
- E-mail subjects now start with the department, for example "Supply Chain · PO … approval overdue", instead of "QCMS".
- A Purchase Order downloads automatically (supplier-safe copy) as soon as you approve it.
- **Employee Master** now holds a photo, which is also shown in the header. Viewing an employee shows:
  - who they report to
  - the escalation level above that
  - their direct reports
  - approval routes they are part of

## OSP
- "Create OSP Material Out" and "Returnable Delivery Challan" are now **one form**. Saving creates both.
- The record view has Details, Print and Vendor returns tabs.
- Older material outs without a challan still open and print.

## Updater
- The updater now also deploys changed e-mail reminder functions to Supabase, using the same Keychain token as the SQL step.
