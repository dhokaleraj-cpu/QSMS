# STAWN QCMS v4.14.49 R40: public RMTC QR codes (website + Android v3.7.1)

## Public QR, no login
- **Anyone who scans** an approved RMTC's QR gets one PDF straight away, with no login.
  - Page 1 is an index: RMTC no, heat, grade, supplier, approval date and FSI part numbers.
  - The index lists every document with its own Download link, plus **Download all (ZIP)**.
  - After it come the RMTC certificate and every RMTC attachment (PDFs and photos), merged into the same file.
- **The QR holds a random 32-character code**, not the RMTC number, so nobody can guess the links of other RMTCs.
- **Revoke QR (new code)** switches off a lost or old label. The old label stops working, so print a new one.
- **Customer details stay internal.** The public certificate shows FSI part numbers only: no customer name, customer PO or customer part number.
- **Certificate on approval.** Approving an RMTC (website or app) creates the public QR, stores the customer-safe certificate and e-mails Quality with the public link.

## New "RMTC QR Codes" page, directly below RMTC (website and app)
- A list of approved RMTCs, with search and filters.
- For each RMTC:
  - the QR and the public link
  - the documents the scan will show
  - QR downloads as PNG, JPEG and PDF, and the 100 × 60 mm label
  - ZIP and one-PDF downloads
  - Refresh and Revoke
- **Bulk actions:**
  - "Create public QR + certificate for all approved RMTCs without one". Run this once: the 47 RMTCs approved before this release have no public QR yet.
  - "Print labels for selected" gives one PDF with many labels.

## Technical
- Supabase function `qcms-rmtc-certificate` v5 (public): `?t=` shows everything, `&f=zip` gives the ZIP, `&f=pdf` downloads the combined PDF, `&f=index` gives the index page only, and `&d=<file>` downloads one file.
- Migration `20261029120000_qcms_r40_public_qr.sql`, already live.
- Android app v3.7.1.
