# QSMS Release 4.8.0

## Steel and production quantity control

RMTC certificate quantity is the controlled steel quantity in kilograms. Material Inward stores:

- Steel Quantity Inward (kg)
- Part Production Quantity (pcs)
- Input Weight (kg/part), inherited from the selected Part Master supplier source
- Required Steel Quantity (kg), calculated as production quantity × input weight
- Remaining RMTC steel balance

Database validation blocks a transaction when required production steel exceeds inward steel or when cumulative inward steel exceeds the RMTC steel balance.

## Inspection layout selection

Approved layouts are ranked automatically using Part Number, Process, Inspection Stage and Layout Type. The highest-ranked exact match is selected automatically; an authorized user may manually select another approved layout.

The report inherits layout name, layout type/section, process, stage and characteristic grid.

## Raw Material MetLAB

The report mirrors the RMTC Part Worksheet:

1. Chemical Composition
2. Jominy Hardenability
3. Heat Treatment / Mechanical Requirements
4. Additional approved layout characteristics

All report sections remain linked to Material Inward, RMTC, Part Number, Heat Number and Internal Heat Code.

## Performance

Master, layout and report grids use one bulk Supabase upsert request instead of one request per row.
