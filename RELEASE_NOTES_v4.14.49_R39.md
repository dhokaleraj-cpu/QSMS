# STAWN QCMS v4.14.49 R39: Android app v3.7.0 matches the website

## Android app v3.7.0
Of the 123 website pages, 120 now open as native screens in the app. The other 3 open the website page inside the app:
- Templates
- Deployment Diagnostics
- My Email Settings: your mailbox password is never stored on the phone.

The full page-by-page list is in `mobile/ANDROID_WEB_PARITY.md`.

- **STAWN Developer Console** (STAWN developer login only):
  - all companies and licences, with issue, renew, suspend, re-activate and revoke
  - create a company and assign its company administrator
  - edit any company's profile and logo
  - add, replace or reset the login cover photo
  - delete trial data (password and confirmation phrase required)
- **Licence & Company** for the company administrator: licence status, activation, company profile and logo.
- **Top bar:** STAWN logo on the left; the licensed company's logo and your employee photo on the right. The app version appears only in My Account / About.
- **Employee Master:** a photo for each employee. Opening an employee shows who they report to, the escalation chain, their direct reports and the approval routes they are in.
- **OSP:**
  - one Material Out + Returnable Delivery Challan form
  - a register with one row per material out
  - each record has Details, Print (customer-safe challan PDF) and Vendor returns
  - OSP inspection queues follow the website rules
- **Indirect Purchase:**
  - purchase orders, the approval worklist, requisitions (convert to PO) and GRN printing / approval
  - item master and stock ledger
- **Purchase Orders:**
  - amendments with an effective date, the latest price or quantity, and the amendment number on the PDF
  - editing price history no longer produces an overlap error
  - an approved PO is saved to Downloads and opened automatically as the supplier-safe copy
- **PPAP Document Manager:**
  - packages from the 32-element template, linked to the APQP project
  - responsible person, due date and status for each element
  - document revisions, and a ZIP of all or selected documents
  - send the package to its own customer
- **RMTC:**
  - the QR code can be saved, shared or e-mailed as PNG, JPEG, PDF or a 100 × 60 mm label
  - approving an RMTC in the app e-mails the QR and the RMTC PDF to the Quality department
  - you can choose which sections apply to each RMTC
  - chemistry and Jominy grids are horizontal, with the mm row
- **Part Master:**
  - Part Processes, each with its drawings and specifications and their revision history
  - replacing a drawing asks for an ECN first
  - ECN / PCN approval, implementation actions, PDF and an ECN register
  - you can choose which sections apply to each part
- **Dashboard and search:**
  - module KPI cards, My Dashboards, and Inventory & Stock reports with filters and export
  - search results, KPI cards and notifications open the exact record
- **E-mails:** subjects start with the department, as on the website.

## PPAP e-mails (website and app)
- **As soon as a PPAP package is created**, each responsible person gets one e-mail. The package owner is copied. It contains:
  - the package, PPAP number, submission level and customer
  - part number and name, drawing number and revision, material grade
  - a table of their own elements with due dates
  - the current part drawings, process drawings, specifications and standards as attachments (up to 18 files / 10 MB; any extra files are listed by name)
- The same e-mail goes out when someone is reassigned or a due date changes. There is also a "Send assignment e-mail again" button.
- **Daily reminders** for elements that are due or overdue carry the same part details. A drawing or specification is attached again only if that person hasn't received it in the last 7 days. A new drawing revision is attached straight away.
- Subjects start with the department, for example "Quality · PPAP <no> · <part> · your N element(s) due from <date>".
- These e-mails go only to your own employees, never to customer or supplier addresses.

## QR code downloads (website)
The approved-RMTC QR panel offers:
- **PNG** and **JPEG**: each has the caption with the RMTC details
- **PDF**
- the 100 × 60 mm label PDF

The files are named `RMTC_<no>_QR.png/.jpg/.pdf`.
