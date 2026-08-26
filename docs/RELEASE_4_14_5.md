# QCMS v4.14.5

Build: `4145-DEPLOY-VERIFY-DIRECT-REPORT-EDIT-SMTP-TENANT-GUIDE`

## Corrective deployment release

- Carries forward the v4.14.4 MetLAB StopIteration guard, master identity-only duplicate rules, and separate Opening Stock import/export module.
- Adds direct report selectors at the top of RMTC, MetLAB and Dimensional entry screens so existing records can be loaded for password-controlled editing without navigating through records first.
- Adds a visible live-release banner on the Dashboard so the deployed version/build can be confirmed immediately.
- Microsoft 365 535 5.7.139 is treated as a tenant/security-policy condition that application code cannot override.
- Deployment updater verifies key source hashes after installation and verifies the pushed remote branch commit equals the local release commit before reporting success.
- No business/master/quality/Supply Chain data reset or deletion.
