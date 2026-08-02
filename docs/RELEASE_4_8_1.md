# QSMS Release 4.8.1

## Heat-wise Production Control

- Part Production Quantity is mandatory in every RMTC Part Worksheet.
- Planned Steel Quantity = Part Production Quantity × supplier Input Weight.
- Sum of planned steel for every part under a Heat Number cannot exceed RMTC Steel Quantity.
- Material Inward records Accepted, Rejected and On Hold production quantities in pieces.
- Accepted, Rejected and On Hold steel quantities are calculated automatically.
- Cumulative steel quantity across all inward transactions and parts cannot exceed the RMTC Heat quantity.
- Cumulative part quantity cannot exceed the production plan for that Part Number.

## MetLAB Evidence

- Four private microstructure image uploads are available.
- Each image has an independent caption/location field.
- Image paths are stored with the MetLAB report and protected by Supabase Storage policies.

## Templates

- RMTC Entry template includes part production plan and calculated steel.
- Material Inward template includes production disposition breakdown and calculated steel.
- MetLAB layout template includes four microstructure image slots.

Existing records, users and transactions are preserved.
