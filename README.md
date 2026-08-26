# QCMS v4.14.13

Current controlled build: `41413-METLAB-CASE-DEPTH-RECORD-EMAIL-TEMPLATE-TEST-CONFIRM`

This additive release retains every earlier QCMS workflow and adds:

- MetLAB **Case Depth / Microhardness Traverse** entry with controlled Case Depth Locations.
- Default traverse starts at **0.05 mm**, then 0.10, 0.20, 0.30 mm and onward; users can add/edit distance rows.
- Multiple Case Depth Locations per report (for example Ground Face, ID and OD), with duplicate-location validation.
- MetLAB PDF and Excel output include the Case Depth Traverse table; PDF includes a multi-location Distance-vs-Hardness chart.
- Case Depth Traverse becomes mandatory when the selected MetLAB layout contains a case-depth characteristic; otherwise it may be explicitly marked Not Applicable with a reason.
- Saved RMTC, MetLAB, Dimensional, Purchase Order and OSP records expose a controlled **Send Email Notification for This Record** action.
- Entry-level email **To / CC are editable**, with a modal confirmation required before the notification can be released.
- Admin Email Templates can be tested with a **manually entered test recipient / CC**, again with a confirmation dialog.
- Normal generated QCMS PDFs and controlled record documents remain available as email attachments according to the selected template.

No database reset is required; MetLAB traverse data is stored inside the existing controlled MetLAB results JSON structure. Existing production/master/quality/Supply Chain/RMTC/OSP data is preserved.
