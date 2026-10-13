# QCMS v4.14.49 R25 — Admin approval for deleting approved records, Deleted Records archive, APK 1.2.0

- **Approved transactions cannot be deleted directly** (approved POs, confirmed supplier confirmations, approved RMTC,
  released inwards, final Dimensional / MetLAB reports, completed OSP, closed / approved APQP & complaint records …).
  The delete panel shows "Send deletion request to Admin" (reason + password). The database also blocks it.
- **Records → Deletion Requests:** the Admin approves (QCMS deletes it through the normal controlled delete, linked
  records are still checked) or rejects, with a note. Admins get an email for every new request. An Admin can also use
  "Admin: approve & delete now" (reason + password, logged as a request).
- **Records → Deleted Records:** every deleted record (including the 347 already in the audit log) with its data at
  deletion, deleted by, reason, requested by, approved by. Filter by type / dates, print one record or the register as PDF.
- **Android app 1.2.0 (versionCode 20):** built automatically by GitHub Actions on this push → artifact
  QCMS-FIRST-APP-APK → QCMS_Mobile_FIRST_APP_v1.2.0_TEST.apk (full QCMS web app with all modules, camera upload,
  downloads, offline retry).
- One SQL step: QCMS_R25_RUN_IN_SUPABASE.sql.

## Handover
- core/delete_approval.py (is_approved, request_delete, decide, deleted_records, PDFs, approved_delete_controls).
- DB: qcms_delete_requests, trg_qcms_guard_approved_delete (session flag qcms.approved_delete), qcms_request_delete, qcms_decide_delete_request (ADMIN), qcms_deleted_records.
- SQL tested on local PostgreSQL 16 stub.
