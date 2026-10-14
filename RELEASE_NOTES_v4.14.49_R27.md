# QCMS v4.14.49 R27 — PO preview before approval, send-to-supplier choice

- **Preview before approval** (Purchase Orders register and Approval / Confirmation page): the approver sees the
  "Sections shown on print" tick-boxes and the PO preview exactly as the supplier will receive it (download too).
- **Send or not send:** switch "Send the approved PO to the supplier by email now". On: email preview (To = supplier,
  others CC, subject, message, PDF with the ticked sections) and the button reads "Approve Purchase Order & send to
  supplier". Off: "Approve Purchase Order (do not send)" - nothing is emailed.
- The ticked sections are saved on the PO at approval, so later downloads and emails print the same way.
- An approved PO that was not sent can be emailed later from the Approval page ("SEND APPROVED PO TO SUPPLIER"),
  the PO PDF page or batch email - all with the section tick-boxes and preview.
- No database step.
