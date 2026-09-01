# QCMS v4.14.17

## Scope
This release closes deployment and approval-routing gaps found while live-verifying v4.14.16. It is additive and does not reset business data.

## Changes
1. Adds tenant scoping for `department_module_defaults`, `user_section_permissions`, `qcms_module_approval_routes` and `supply_stage_responsibilities` repository writes.
2. Adds Admin UI for Module Approval Routes.
3. PO approval precedence: **Configured Route → Reports-To → different employee with Approve permission**. Administrator retains controlled override.
4. Blocks PO self-approval when no explicit target exists.
5. Approval-pending email routes to the same authoritative target.
6. Adds automatic Supabase v4.14.16 baseline verification and v4.14.17 migration application through Management API / current Supabase CLI credentials.
7. Does not use `supabase db push`, because this project's historical live migration timestamps differ from some packaged local timestamps; only the specifically controlled additive SQL is executed.
8. Preserves `supabase/.temp` so linked-project credentials/state are not deleted by the updater.
9. Synchronizes VERSION, build strip, `DEPLOYMENT_MANIFEST.json`, README, release notes and handover.

Build: `41417-AUTO-MIGRATION-APPROVAL-ROUTES-MANIFEST-SYNC`
