# QCMS v4.14.20

- Fixes Add New RMTC/TC for an existing Heat so a new Supplier TC uses its own certified quantity while sharing the canonical Heat Code and global Heat ledger.
- Adds direct Edit/Delete controls for OSP Material Out, Sample Receipt, OSP Dimensional, OSP MetLAB and OSP Inward.
- OSP edits are permission controlled and deletion requires current-password confirmation; unsafe downstream genealogy blocks destructive changes.
- Adds live RPCs for controlled Material Out edits, Sample Receipt clearing and OSP Inward receipt edits.
