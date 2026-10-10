"""R18: print column alignment, email From = company mailbox (user name, reply to user), editable From."""
from pathlib import Path

from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from core import mail_service as ms
from core import reporting as r

ROOT = Path(__file__).resolve().parents[1]


def test_column_alignment_rules():
    assert r._column_alignment("Sr") == TA_CENTER
    assert r._column_alignment("Parameter / Characteristic") == TA_LEFT
    assert r._column_alignment("Specification") == TA_CENTER
    assert r._column_alignment("Result") == TA_CENTER
    assert r._column_alignment("Remarks") == TA_LEFT
    assert r._column_alignment("Planned kg") == TA_RIGHT


def test_grid_applies_alignment_and_centres_numbers():
    st = r._controlled_styles()
    g = r._rmtc_grid([["Sr", "Parameter", "Specification", "Qty kg", "Result"], ["1", "Hardness", "58-62", "120", "PASS"]], [10, 50, 40, 30, 20], st["header"], st["small"], status_columns=(4,))
    row = g._cellvalues[1]
    assert row[0].style.alignment == TA_CENTER and row[1].style.alignment == TA_LEFT and row[2].style.alignment == TA_CENTER
    assert row[3].style.alignment == TA_RIGHT and row[4].style.alignment == TA_CENTER
    assert all(c.style.alignment == TA_CENTER for c in g._cellvalues[0])


class _Repo:
    def __init__(self): self.rows = []
    def select(self, table, eq=None, **_):
        return [r for r in self.rows if all(r.get(k) == v for k, v in (eq or {}).items())]
    def insert(self, table, payload):
        row = {"id": str(len(self.rows) + 1), **payload}; self.rows.append(row); return row
    def update(self, table, rid, payload):
        row = next(r for r in self.rows if r["id"] == rid); row.update(payload); return row


def test_editable_from_saved_per_user():
    repo = _Repo()
    assert ms.load_user_from(repo, "u1") == {}
    ms.save_user_from(repo, "u1", "Rajesh Dhokale", "rajesh@fsi.in")
    ms.save_user_from(repo, "u1", "Rajesh D", "rajesh.d@fsi.in")
    assert ms.load_user_from(repo, "u1") == {"name": "Rajesh D", "email": "rajesh.d@fsi.in"} and len(repo.rows) == 1
    try:
        ms.save_user_from(repo, "u1", "X", "bad")
        assert False
    except ValueError:
        pass


def test_company_mode_is_default_and_edge_function_uses_company_from():
    rows = ms.company_outbox_rows(subject="S", html_body="b", text_body="b", to=[ms.Recipient("a@fsi.in", "A", "x")], sender_name="Rajesh", sender_email="rajesh@fsi.in")
    assert rows[0]["context"]["from_mode"] == "COMPANY"
    ts = (ROOT / "supabase/functions/qcms-send-email/index.ts").read_text()
    assert 'String(ctx.from_mode || "COMPANY").toUpperCase() !== "USER"' in ts and "via QCMS" in ts and "replyTo: quoted(ctx.sender_name, senderEmail)" in ts
    from core.system_settings import EMAIL_FROM_MODES
    assert set(EMAIL_FROM_MODES) == {"COMPANY", "USER"}
    page = (ROOT / "app_pages/email_center.py").read_text()
    assert 'key="mail_from_email"' in page and "Save From details" in page
