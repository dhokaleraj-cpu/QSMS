# QCMS v4.14.49 R15 — Bend Test module, OSP approval guidance, free AI, Android 1.1.0

## 1. Bend Test — separate module and separate layout master
- New **Bend Test** menu group (Quality): Bend Test Report · **Bend Test Layout Master** · Bend Test Reports. Bend Test Records stay under Records.
- Bend Test layouts are their own controlled scope (`inspection_plans.inspection_method = 'BEND_TEST'`). A Part can now have one current **Bend Test** layout AND one current **general MetLAB** layout for the same Part + Stage + Process. Bend plan numbers end in `-BEND`.
- Fixes the red error "Only one current inspection layout is allowed…" when saving a Bend Test layout (needs the R15 SQL once — see below).

## 2. Bend Test report = customer report layout (1006/2026/7237)
- Single A4 page: BEND TEST REPORT header grid (Report No, Date, Part, Customer, Material, Baking Batch, Batch Qty, Heat Code, Diameter, FSI/HT Batch), Baking/Aging spec vs actual, Bend Test Results (Load Vs CHT, CHT, included angle, status), **Load Vs CHT graph + Bend Test Part photos** (slot 1 graph, slots 2-4 part/plating photos), surface remark, Part Bend Angle, photo captions, Conclusion, Prepared By / Verified & Approved By, Reference Documents.
- New "BEND TEST REPORT DETAILS" fields on the Bend Test entry screen.

## 3. OSP Dimensional / MetLAB — "manager unable to approve"
- The Finalize button now says exactly why it is not available (already FINAL by whom/when, no Approve right, decision still Pending, Approved By must be the signed-in employee, login not linked to an employee).
- **OSP Quality Gate Checklist** shows all four gate reports (Sample/Receipt × Dimensional/MetLAB) so the user sees which report is still missing.
- Approved By defaults to the signed-in employee.
- Example: D9-DIR-2026-00112 is already FINAL/Accepted (approved by EMP-0012). The OSP batch stays pending because its **Post-receipt (OSP Receipt) MetLAB report has not been created** yet.

## 4. AI prompt search — FREE option
- AI Assistant now supports **Google Gemini (free tier)** and **Groq (free tier)** besides Claude and OpenAI (paid).
- `bash scripts/set_ai_key.sh` → choose 1 (Gemini FREE). Engine auto-selects from secrets (`QCMS_AI_PROVIDER`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `QCMS_AI_MODEL`).
- Note: ChatGPT Plus / Claude Pro chat subscriptions do not include API access. Free API tiers are rate-limited and the provider may use free-tier prompts to improve its services.

## 5. Android app 1.1.0 (versionCode 19)
- Camera option in every photo upload (bend part, microstructure, complaint photos), loading progress bar, offline / server-waking retry screen, Clear cache & reload. All new QCMS modules appear automatically because the website owns the menu.
- APK builds on GitHub Actions (workflow "QCMS First-App Android APK") on every push, or locally with `mobile/android_first_app/BUILD_AND_INSTALL_SAMSUNG.command`.

## Database
- Run once in Supabase SQL Editor: `QCMS_R15_RUN_IN_SUPABASE.sql` (R14 email tables + R15 bend layout scope; safe to re-run).
