# QCMS v4.14.11

Current controlled build: `41411-PO-MASTER-HSN-PRICE-FORM-EMAIL-CONFIRM-SERIES`

This additive release retains every earlier QCMS workflow and adds:

- Purchase Order source selectors showing Customer Name + Customer Part Number + reference/position.
- Supplier/raw-material HSN/SAC directly in Part Master Raw Material Details next to Supplier.
- PO Current Price and HSN/SAC inherited read-only from supplier-specific Part Master data / price history.
- Purchase Order entry submitted as one Streamlit form so normal field edits do not rerun the page individually.
- Centered controlled PO footer.
- Entry-level email notification tick, recipient/CC preview and explicit confirmation on all existing workflow notification entry points.
- New PO number format `PD9DDMM00001` with a continuous five-digit sequence for permanent uniqueness.

Existing production/master/quality/Supply Chain/RMTC/OSP data is preserved.
