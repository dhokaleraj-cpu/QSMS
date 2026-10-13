# QCMS v4.14.49 R23 — PO line numbers, hide sections per PO, preview before save, email preview

- **PO line numbers:** new LINE column (1/2, 2/2 …) in the item row; PO Source Reference, Technical Data and
  Price History headings show "LINE 1 OF 2" when a PO has several lines.
- **PO totals:** new PO LINES and TOTAL QTY (combined quantity of all lines per UOM, e.g. 12,012 KGS) above Subtotal.
- **Hide sections per PO:** at PO entry choose sections to hide on this PO's print (PO Source Reference, Raw Material
  Details & Supplier Technical Data, Price Revision History, Plant, Vendor, Ship-To, Reference, Old PO, Special
  Instructions, Approval Stamp). Saved with the PO; change it later on the PO PDF page (preview + "Save for this PO").
- **Preview before save:** "Preview PO PDF (not saved)" runs all PO checks and shows the PDF without saving anything.
- **Email preview before sending:** Send Email page shows From / To / CC / BCC / Subject / attachments and the message
  as recipients will see it; every workflow email (entry notifications, record emails, batch PO emails, PO approval
  emails) has a preview.
- One SQL step: QCMS_R23_RUN_IN_SUPABASE.sql (adds supply_purchase_orders.print_options). Until it is run, POs are
  still created normally — only the per-PO section choice is not stored.
