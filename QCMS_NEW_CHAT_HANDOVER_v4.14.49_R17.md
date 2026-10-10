# QCMS v4.14.49 R17 — Print Design B, default email server, KPI Dashboards first

## 1. Print Design B ("Open Lines") on all quality prints
- RMTC, MetLAB, Bend Test, Dimensional, OSP Dimensional / MetLAB and Material Inward PDFs.
- White page; the only shaded element is the teal section heading. Horizontal lines only.
- Bigger text (body 8–8.6 pt, was 5–5.4 pt) and taller rows; white page header with logo, title and a teal rule.
- Colour-coded text: **Conclusion = dark green (bold)**, **Remarks / Conclusion Remark / Decision Reason = burnt orange (italic)**,
  results/decisions coloured by status (Accepted/Pass green, Rejected/Fail red, Hold amber, Pending blue).

## 2. Email module uses the default email server only
- No Office 365 sign-in. Send Email always uses the server in Admin → Email Settings; recipients see the user's name and email, replies go to the user.
- System Settings: the Microsoft 365 sign-in section is replaced by "Email Module · Default Email Server" (status + Send-As note).
- My Email Settings now shows how your emails appear (name / email) and your signature.

## 3. KPI Dashboards is the first page after login
- KPIs is first in the header and the left menu; Home/Dashboard stays available.

## Handover state
- Design B implemented in core/reporting.py shared helpers (_rmtc_grid, _rmtc_section_bar, _rmtc_labeled_grid, _quality_conclusion_table, _controlled_styles, _PageNumberCanvas header) + bend builder. Colours: TEAL, CONCLUSION_COLOR, REMARK_COLOR, STATUS_TEXT.
- Legacy tests updated for the new design (v41429, v495 page count <=3, v496 fonts, v450 default page, r14 settings).
- Pending: Gemini AQ. key test output; layout concept A–D.
