# QCMS v4.14.49 R35 handover

Read RELEASE_NOTES_v4.14.49_R35.md for the user-facing list.

## Database (live on xxrxopzxzyjnzumrwuwy)
The four migration files are listed in supabase/auto_apply.json, so the updater re-applies them. All four are idempotent.
- `supabase/migrations/20261021100000_qcms_r35_quality_fixes.sql`
  - tenant_id defaults for 23 tables
  - activity log policy and index
  - `npd_order_steps.process_name_snapshot`
- `supabase/migrations/20261021110000_qcms_r35_supply_chain.sql`
  - `qcms_part_stage_stock(part, heat)`
  - six indexes
  - `qcms_remove_po_source(source_id, reason)`: **not yet live**. The Supabase MCP needs confirmation for DELETE statements, so the updater's `scripts/apply_sql.py` applies it.
- `supabase/migrations/20261021120000_qcms_r35_notifications_licensing.sql`
  - Tables:
    - `qcms_user_notifications`
    - `qcms_push_devices`
    - `qcms_whatsapp_settings`
    - `qcms_stawn_developers`, seeded with dhokaleraj@icloud.com and rajesh.dhokale@fourstarindustries.com
    - `qcms_licences`
    - `qcms_licence_secret`, with no API access
    - `qcms_company_profiles`
  - Notification RPCs: `qcms_my_notifications`, `qcms_unread_notification_count`, `qcms_mark_notifications_read`, `qcms_notify`, `qcms_register_push_device`, `qcms_set_my_whatsapp`.
  - Licence RPCs: `qcms_licence_status`, `qcms_validate_licence`, `qcms_activate_licence`.
  - Developer RPCs: `qcms_dev_issue_licence`, `qcms_dev_update_licence`, `qcms_dev_licence_overview`, `qcms_dev_create_company`, `qcms_dev_assign_profile`.
  - Triggers: PO approvals, delete requests, inspection and lab reports, complaints and CAPA, customer orders, e-mail outbox to in-app.
  - Seat-limit trigger on profiles.
  - Four Star seed: ENTERPRISE licence, 50 users, no expiry.
  - pg_cron jobs `qcms-push-dispatch-2min` and `qcms-whatsapp-dispatch-2min`.
- `supabase/migrations/20261021130000_qcms_r35_dashboards_search.sql`
  - `qcms_user_dashboards`
  - `qcms_kpi_dashboard(department)`
  - `qcms_my_pending_tasks`
  - `qcms_global_search(query, limit)`
  - `qcms_search_table_map`

## Edge functions
Both are deployed with verify_jwt off and authenticate with the scheduler token.
- `qcms-push-dispatch`. Secrets: APNS_KEY_P8, APNS_KEY_ID, APNS_TEAM_ID, and optionally FCM_SERVICE_ACCOUNT_JSON.
- `qcms-whatsapp-dispatch`. Secret: WHATSAPP_TOKEN.

Until their secrets are set, both functions do nothing.

## Website
New pages:
- `notifications`
- `licence-company`
- `stawn-developer` (shown only to STAWN developers)

Shell changes:
- licence gate (it never blocks when the check fails)
- notification bell
- reminder for the one-time company setup
- STAWN QCMS header with the licensee shown underneath

New service module: `core/licence_service.py`.

## Mobile
- **Android v3.4.0 (versionCode 340)** adds:
  - Notif, NotifScreen, NotifJob (JobScheduler, every 15 minutes), BootReceiver
  - KpiHomeScreen
  - Licence
  - GenSearch, which now calls qcms_global_search

  There is no FCM SDK, because the app is framework-only.
- **iOS v1.1.0 build 2** adds:
  - Notifications.swift (APNs registration and inbox)
  - KpiDashboardView.swift (Swift Charts)
  - Licence.swift
  - STAWNQCMS.entitlements (aps-environment)

  Team ID detection lives in BUILD_STAWN_QCMS_iOS.command. Release builds sign with Apple Distribution.

## Data notes for the user
- Saket Jha (qcd11@) has an employee record but no login. Create the login in Users & Access.
- Komal (mlab@ → nikhil@) and Badri (mlab1@ → mlab@) appear crossed in the Link check.
- Layout "CASE CARBURIZING 9265" is saved under Quench & Tempering.
