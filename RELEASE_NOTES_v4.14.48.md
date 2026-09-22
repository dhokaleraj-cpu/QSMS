# QCMS v4.14.48 — 5% PO Watermark + Real Approver + Stable Session + Android Every Release

- Purchase Order PDF watermark is now **5% opacity**, very-light, and merged **behind** PO content so text/grids remain readable.
- Approved PO first-page digital approval stamp resolves the actual Employee Master approver name/code/designation and saved approval timestamp. Generic `Authorised Approver` is no longer used when an Employee Master link exists.
- Legacy approved POs can recover the approver Employee Master from the stored approving user/profile linkage when `approver_employee_id` is missing.
- The duplicated/stacked page effect seen in the supplied video is corrected: persistent-auth storage writes are now fire-and-forget, the auth payload is stable across widget reruns, auth bridge containers are forced to zero height, and refresh restores from the same-origin cookie before mounting the localStorage bridge.
- Android advances to **v0.2.3 / versionCode 14** with the v1.2-style native auto-hide drawer preserved.
- GitHub Actions `QCMS Android Test APK` now runs automatically on **every push to main** and still exposes the manual **Run workflow** action.
- Database schema remains **v4.14.45**. No SQL migration, Supabase CLI login, or manual SQL is required.
