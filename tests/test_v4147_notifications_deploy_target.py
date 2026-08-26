from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def test_v4147_release_identity_and_runtime_proof():
    assert (ROOT / "VERSION").read_text().strip() in {"4.14.7", "4.14.8", "4.14.9"}
    app = text("streamlit_app.py")
    diag = text("app_pages/deployment_diagnostics.py")
    manifest = text("DEPLOYMENT_MANIFEST.json")
    assert any(token in app for token in ("4147-NEXT-STAGE-EMAIL-TEMPLATES-AUTO-OVERDUE-DEPLOY-TARGET", "4148-AUTO-SAFETY-SNAPSHOT-DIRTY-WORKTREE-DEPLOY", "4149-DEPENDENCY-BOOTSTRAP-REMOTE-DEPLOY"))
    assert "Git origin" in diag and "Git HEAD" in diag and "Streamlit main file" in diag
    assert '"streamlit_deploy_target_proof"' in manifest


def test_v4147_next_stage_templates_and_supplier_copy():
    settings = text("app_pages/email_settings.py")
    notify = text("core/notification_service.py")
    masters = text("core/master_definitions.py")
    assert "NEXT-STAGE RESPONSIBILITY ROUTING" in settings
    assert "MODULE EMAIL TEMPLATES" in settings
    assert "CC Responsible Department" in settings
    assert "Copy linked Supplier / Vendor" in settings
    assert "qcms_email_templates" in notify
    assert "department_emails" in notify
    assert "send_to_supplier" in notify
    assert "notification_emails" in masters


def test_v4147_pdf_and_document_attachments_are_supported():
    notify = text("core/notification_service.py")
    sender = text("supabase/functions/qcms-send-email/index.ts")
    assert "attachment_manifest" in notify
    assert "include_generated_pdf" in notify
    assert "include_record_attachments" in notify
    assert "purchase_order_pdf_bytes" in notify
    assert "metlab_record_pdf_bytes" in notify
    assert "dimensional_record_pdf_bytes" in notify
    assert "attachments" in sender
    assert "storage.from" in sender
    assert "cc_emails" in sender


def test_v4147_first_approval_email_sees_uploaded_report_documents():
    dim = text("app_pages/dimensional_report.py")
    met = text("app_pages/metlab_report.py")
    # In each create path the upload must occur before notify.
    assert dim.index('service.upload_attachment("DIMENSIONAL_REPORT"') < dim.index('"DIMENSIONAL_APPROVAL_PENDING"')
    assert met.index('service.upload_attachment("METLAB_REPORT"') < met.index('"METLAB_APPROVAL_PENDING"')


def test_v4147_automatic_open_overdue_scheduler_contract():
    migration = text("supabase/migrations/20260826143000_qcms_notification_templates_overdue_v4147.sql")
    edge = text("supabase/functions/qcms-overdue-notifier/index.ts")
    settings = text("app_pages/email_settings.py")
    for token in (
        "qcms_notification_schedules",
        "CUSTOMER_ORDER_OPEN_OVERDUE_DIGEST",
        "RM_PO_OPEN_OVERDUE_DIGEST",
        "FORGING_ORDER_OPEN_OVERDUE_DIGEST",
        "OSP_RETURN_OPEN_OVERDUE_DIGEST",
        "NPD_PROCESS_OPEN_OVERDUE_DIGEST",
        "pg_cron",
        "pg_net",
        "qcms-overdue-notifier-hourly",
    ):
        assert token in migration
    assert "AUTOMATIC OPEN / OVERDUE REPORT EMAILS" in settings
    assert "X-QCMS-Scheduler" in edge
    assert "supplier" in edge.casefold()
    assert "pdf" in edge.casefold()


def test_v4147_po_events_use_po_created_templates():
    supply = text("app_pages/supply_chain.py")
    assert '"RM_PO_CREATED"' in supply
    assert '"FORGING_PO_CREATED"' in supply


def test_v4147_no_known_mailbox_password_or_scheduler_secret_in_source():
    # The actual SMTP credential and scheduler token must never be embedded in source.
    all_text = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in ROOT.rglob("*")
        if p.is_file() and p.suffix.lower() in {".py", ".sql", ".ts", ".md", ".json", ".toml"}
    )
    forbidden_literal = "Rajesh" + "@2011"
    assert forbidden_literal not in all_text
    scheduler_assignment = "qcms_notification_scheduler_token" + " ="
    assert scheduler_assignment not in all_text
