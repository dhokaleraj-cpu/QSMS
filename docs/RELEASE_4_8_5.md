# QSMS 4.8.5 — Combined Heat Steel Balance

## Purpose

Protect one Heat Number against double allocation across RMTC plans and Material Inward transactions.

## Controlled formula

```text
Committed Heat Steel
= Inward Steel Already Used
+ Remaining Planned Steel Not Yet Inwarded
```

The remaining planned quantity is calculated per RMTC Part Worksheet as:

```text
Remaining Planned Steel
= max(Planned Steel - Inward Steel for that Part Plan, 0)
```

This avoids counting the same steel once as an RMTC plan and again after it is inwarded.

## RMTC controls

- New or edited part plans are checked against the global Heat quantity.
- Global Heat quantity cannot be reduced below inward steel plus remaining active plans.
- Rejected and superseded RMTC plans do not reserve Heat steel.

## Material Inward controls

- The selected part can consume its own remaining reserved plan.
- Other active part reservations are protected.
- Heat Steel Available Before Entry and Heat Steel Balance After Entry are shown.
- A negative after-entry balance is blocked in the UI and database.

Existing data, users, permissions and transactions are preserved.
