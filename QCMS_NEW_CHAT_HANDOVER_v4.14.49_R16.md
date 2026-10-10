# QCMS v4.14.49 R16 — Report Builder, Master List Excel, company-mailbox email, Bend Test at any stage

## 1. Bend Test Layout Master — any stage
- No Inward Type on the Bend Test Layout Master ("Applies To: Any stage (Bend Test)"); Process and Inspection Stage are optional.
- Bend Test Report lists **every approved Bend Test layout of the Part** (raw material, OSP, final or standalone) — pick any one.

## 2. Print designs for approval
- `docs/QCMS_Print_Design_Options_R16.pdf`: Dimensional, MetLAB, RMTC, Bend Test and OSP reports, each in **Design A · Clean Grid** and **Design B · Open Lines**.
- Both: white page, no background colour except section headings, body font 10–10.5 pt (was 5.5–7 pt), row height 20–22 pt.
- After approval, the chosen design is applied to all PDF prints in the next release.

## 3. Report Builder (Reports → Report Builder)
- Any dataset you may view (Parts, Parties, RMTC, Inward, Inspections, MetLAB/Bend, OSP, Complaints, Supply Chain, NPD, Calibration…).
- Choose columns, up to 8 filters (contains / equals / dates between / greater-less / empty), group by with Count / Sum / Average / Min / Max, sort, max rows, bar/line/pie chart.
- Download clean Excel (title, bold header, filter, frozen header, print fit-to-width) or CSV; **save reports** for everyone with the same view rights.

## 4. Master List Excel (Reports → Master List Excel)
- One workbook, one sheet per master: Customers, Suppliers, Steel Mills, OSP Vendors, Parts, Grades, Chemistry, Approved Sources, Customer Standards, Processes, Inspection Stages, Quality Assets, Inspection Plans/Characteristics, Test Plans, Employees.
- Linked IDs shown as part numbers / party names; "Active only" option.

## 5. Email — company mailbox (like the payroll email module)
- Send Email → **Send using: Company mailbox (shows my name & email)** — no personal sign-in needed.
- QCMS sends through the company SMTP account set in Admin → Email Settings; recipients see **User Name <user@email>** as sender and replies go to the user.
- If the company mailbox is not allowed to "Send As" the user (Microsoft 365), QCMS automatically sends as **"User Name via QCMS" <company mailbox>** with Reply-To = user.
- Edge function `qcms-send-email` v5 deployed (all existing notifications unchanged).
- To show the user's own address in Microsoft 365, the M365 admin grants the company mailbox **Send As** on each user mailbox (Exchange admin center → Recipients → Mailboxes → user → Delegation → Send as → add the QCMS mailbox).

## 6. AI key script
- Accepts the new Google key format (`AQ.`) and reads the key from the clipboard.

## Handover state
- New: core/report_builder.py, app_pages/report_builder.py (routes report-builder, master-lists), mail_service.company_outbox_rows, email_center company mode, edge function v5 (repo copy = deployed), InspectionService.bend_plans, tests/test_r16_*.py, scripts/print_design_options_r16.py.
- Pending user decisions: print design choice per module (A/B); layout concept A–D; R14/R15 SQL (QCMS_R15_RUN_IN_SUPABASE.sql) if not yet run; Gemini AQ. key test result.
