# QCMS 4.14.49 R9 — 3 October 2026

- Fix RM PO save rejection for FSI RM → Direct Production.
- Retain the FSI RM → receipt → forger dispatch → forging PO → forging receipt sequence.
- Verify one RM PO across customer orders and different parts, with separate allocations; isolate editable grid state when selection changes.
- Add a numeric bend angle and explicit part bend photograph label, with angle in PDF/Excel and photographs in PDF.
- Preserve MetLab inspection method, reference documents and conclusion remark during save.
- Enable recipient confirmation and approval notification when saving an existing editable MetLab draft as well as a new report.
- Include all earlier cumulative fixes and Android source/workflow.

No new R9 migration is required. This is a source update; run the included updater to test, commit and push GitHub. The APK is produced by GitHub Actions after a successful push.
