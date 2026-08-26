# QCMS v4.14.12

Current controlled build: `41412-RM-TYPE-PO-RM-DETAILS-FORGING-FILTER-DUPLICATE-GUARD`

This additive release retains every earlier QCMS workflow and adds:

- Part Master `Raw Material Section` renamed in the UI to **Raw Material Type** while preserving the existing database column for backward compatibility.
- Controlled Raw Material Type list starts with **Round Black Bar** and **Bright Bar** and retains existing values.
- Reusable **Section Size** and **Forging Route** additions reject exact/fuzzy 2-3-word duplicates.
- Raw Material PO item details now print **Raw Material Type + Material Grade + Section Size** immediately beneath each item.
- Forging-specific parameters/weights/routes are intentionally removed from Raw Material procurement PO printouts.
- Forging Purchase Orders retain the full Raw Material / Forging Parameters & FSI Technical Data section.
- RM Purchase Order entry grids show Raw Material Type, Material Grade and Section Size from Part Master.

Existing production/master/quality/Supply Chain/RMTC/OSP data is preserved.
