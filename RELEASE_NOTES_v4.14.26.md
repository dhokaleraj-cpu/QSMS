# QCMS v4.14.26 — Complaint Media / Calibration & Validation / Standard Room / NPD Email Cards

**Build:** `41426-COMPLAINT-MEDIA-CALIBRATION-STANDARD-ROOM-NPD-CARDS`

## Complaint Management
- Customer and Supplier complaints now capture **Heat Number** and **Batch Code / Lot Number**.
- Complaint PDF print layouts embed the actual attached complaint photographs.
- Complaint Excel exports include a dedicated **Photographs** sheet with embedded images and an attachment register.
- PDF and Excel downloads are available directly on Complaint Entry/Analysis/Records screens.
- Complaint register/search includes Heat and Batch identity.

## Supply Chain Home
- Overdue Customer Orders appear first as red **PRIORITY · OVERDUE CUSTOMER ORDERS** cards with Customer, Part, Delivery Date, Days Overdue and Next Stage.

## Calibration & Validation
- New **Calibration & Validation** module for Gauges / Fixtures / Quality Assets.
- Link each asset to Part + Process + intended characteristic/use.
- Calibration / Validation / Both service types with configurable frequencies (1 month, 3 months, 6 months, 1 year, 2 years, custom).
- Drawings, asset photographs, calibration reports and certificates are controlled attachments.
- Calibration/validation history records service date, result, report/certificate, agency, performed-by employee and next due date.
- Daily reminder to the **Quality** department begins 30 days before due and repeats while due/overdue until the next valid calibration/validation record is completed.

## Standard Room Inspection
- New Standard Room record for **CMM, Counter, VMM, Roughness Tester, Height Gauge, Profile Projector, Roundness Tester, Contour Tracer, Hardness Tester and Other**.
- Records Part, Process, Heat Number, Batch Code, quantity, report/program reference, operator and Pass/Fail/Hold/Pending status.
- Report/photo attachments plus same-screen PDF and Excel exports.

## NPD/APQP Email Notifications
- NPD open/overdue digest emails now include a visual card view for each process stage.
- **Completed = green**, **Overdue = red**, **In Process = blue**, **On Hold = purple**, **Pending = amber**.
- Order/Part/Customer/Delivery/Progress are shown in the email body for quick status understanding.

## Deployment
- The additive v4.14.26 Supabase migration was applied and verified on the live QSMS project during controlled release packaging.
- The macOS updater is therefore source deployment only: no manual SQL, no `supabase login`, and no Supabase access-token requirement.
- Existing production/master/quality/RMTC/OSP/Supply Chain data is preserved.
