# QCMS v4.14.24

Build: `41424-PO-TECH-GRID-LIVE-IMPORT-APQP-DATE`

## Controlled changes

- Purchase Order PDF now prints all supplier-controlled Technical Data rows marked **Include on PO** as a compact grid under the item. Raw Material POs keep forging-only standard parameters suppressed while custom rows such as Packing, RM Rate, Conversion Cost, Cutting Cost, Shot Blasting and Heat Treatment are included.
- Master Import now provides a **Controlled Template + Live Master Data** download generated from the current QCMS database. The workbook retains the original input sheets and adds current `MASTER_*` reference sheets for Customers, Suppliers, Steel Mills, OSP Vendors, Parts, Material Grades, Processes, Inspection Stages, Quality Assets, Employees and Customer Standards. Users enter only the variable/new values and copy exact controlled master codes/values from the reference sheets.
- Template Centre directs master-import users to the live controlled templates so stale static master values are not reused.
- APQP overdue calculation now safely ignores blank/invalid due dates instead of raising a TypeError.
- No new Supabase migration is required. Existing v4.14.22+ database schema and all production data are preserved.
- Full regression suite: 444/444 tests passed.
