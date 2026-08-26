# QCMS v4.14.7

Build: `4147-NEXT-STAGE-EMAIL-TEMPLATES-AUTO-OVERDUE-DEPLOY-TARGET`

## Controlled scope
- Prove live Streamlit Git origin / Git HEAD / main file before accepting deployment.
- Route workflow email to responsible next-stage department and employee.
- CC responsible department and optionally linked supplier / OSP vendor.
- Attach generated QCMS PDF and controlled supporting documents when enabled by template.
- Maintain module/event email subject/body templates in Admin.
- Send automatic daily open / due-soon / overdue PDF reports through Supabase Cron.
- Keep supplier copies conditional on Party Master email / notification email availability.
- Preserve v4.14.6 MetLAB/Dimensional/RMTC edit controls, Opening Stock, PO fixes and all production data.
