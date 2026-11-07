"""R41: delete automatic e-mail reminder schedules (website + Android) and the reminder functions honour deleted rows."""
from __future__ import annotations

from pathlib import Path

import pytest

from core import reminder_admin

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "mobile/android_qcms_app/app/src/main/java/com/fourstar/qcmsapp"


class FakeRepo:
    def __init__(self):
        self.deleted: list[tuple[str, str]] = []

    def delete(self, table, record_id):
        self.deleted.append((table, record_id))


def test_delete_requires_selection_and_password():
    repo = FakeRepo()
    with pytest.raises(ValueError):
        reminder_admin.delete_schedules(repo, [], "pw", verify=lambda p: None)
    with pytest.raises(ValueError):
        reminder_admin.delete_schedules(repo, ["a"], "  ", verify=lambda p: None)
    assert repo.deleted == []


def test_wrong_password_deletes_nothing():
    repo = FakeRepo()

    def verify(_password):
        raise PermissionError("The password is incorrect.")

    with pytest.raises(PermissionError):
        reminder_admin.delete_schedules(repo, ["a", "b"], "bad", verify=verify)
    assert repo.deleted == []


def test_delete_after_password_check():
    repo, seen = FakeRepo(), []
    count = reminder_admin.delete_schedules(repo, ["a", "", "b"], "pw", verify=seen.append)
    assert count == 2 and seen == ["pw"]
    assert repo.deleted == [("qcms_notification_schedules", "a"), ("qcms_notification_schedules", "b")]


def test_labels_and_impact():
    row = {"schedule_key": "PPAP_DOCUMENT_DUE", "schedule_label": "PPAP Documents", "module_key": "NPD_APQP", "enabled": False}
    assert reminder_admin.schedule_label(row) == "PPAP Documents · Npd Apqp · Disabled"
    lines = reminder_admin.impact_lines([row])
    assert "PPAP Documents" in lines[0] and "PPAP element" in lines[0]


def test_website_page_offers_delete():
    page = (ROOT / "app_pages/email_settings.py").read_text(encoding="utf-8")
    assert "DELETE AUTOMATIC EMAIL REMINDERS" in page and "_render_schedule_delete(repo)" in page
    assert "delete_schedules(repo, chosen, password)" in page and 'type="password"' in page


def test_reminder_functions_stop_when_schedule_deleted():
    fn = ROOT / "supabase/functions"
    ppap = (fn / "qcms-ppap-due-notifier/index.ts").read_text(encoding="utf-8")
    assert "if ((!schedule || schedule.enabled === false) && !body.force) continue;" in ppap
    approval = (fn / "qcms-po-approval-overdue/index.ts").read_text(encoding="utf-8")
    assert 'eq("schedule_key","PO_PENDING_APPROVAL")' in approval and "if(!gate||gate.enabled===false)" in approval
    deploy = (ROOT / "supabase/auto_deploy_functions.json").read_text(encoding="utf-8")
    assert "qcms-po-approval-overdue" in deploy and "qcms-ppap-due-notifier" in deploy


def test_android_offers_delete():
    src = (ANDROID / "AdmEmailAuto.java").read_text(encoding="utf-8")
    assert "Delete reminder" in src and "qcms_notification_schedules" in src and "verifyPassword" in src
