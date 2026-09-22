# QUALITY CONTROL MONITORING SYSTEM (QCMS/QSMS)
## Complete New-Chat Handover — v4.14.47

### Controlled baseline
- Application Version: `4.14.47`
- Build: `41447-PO-WATERMARK-20-APPROVER-STAMP`
- Project path: `/Users/dhokaleraj/QSMS`
- Database schema baseline remains `4.14.45`; no v4.14.47 SQL migration.
- Android v0.2.2 is preserved; no APK rebuild is required for this print-only release.

### Purchase Order print control
- APPROVED / PENDING APPROVAL watermark is rendered with `setFillAlpha(0.20)` and light-grey ink for readable underlying content.
- Approved PO first page has a bottom-right QCMS DIGITAL APPROVAL stamp.
- Stamp includes approver Employee Master name/code and approval date/time in IST.
- No approval stamp is printed on pending documents.

### Preserved
- Android v0.2.2 v1.2-style auto-hide drawer.
- Persistent login restoration after browser/WebView refresh.
- v4.14.45 shared raw forging/casting source, same-price-across-parts and controlled layout identity.
