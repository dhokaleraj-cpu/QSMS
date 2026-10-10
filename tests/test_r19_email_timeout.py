"""R19: Send Email no longer fails on 'The read operation timed out' - outbox rows decide the result."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_outbox_outcome_mapping():
    from app_pages.email_center import _outbox_outcome
    assert _outbox_outcome([{"status": "SENT"}, {"status": "SENT"}]) == ("SENT", None)
    st, err = _outbox_outcome([{"status": "SENT"}, {"status": "FAILED", "last_error": "550 bad"}])
    assert st == "PARTIAL" and "550" in err
    st, err = _outbox_outcome([{"status": "SENDING"}], {"error": "The read operation timed out"})
    assert st == "QUEUED" and "timed out" not in err


class _Repo:
    def __init__(self): self.calls = 0
    def select(self, table, eq=None, limit=None, require_live=False):
        self.calls += 1
        return [{"id": eq["id"], "status": "SENT" if self.calls > 2 else "SENDING"}]


def test_wait_for_outbox_polls_until_sent(monkeypatch):
    import app_pages.email_center as ec
    monkeypatch.setattr(ec.time, "sleep", lambda s: None)
    rows = ec._wait_for_outbox(_Repo(), ["a"], timeout=30)
    assert rows[0]["status"] == "SENT"


def test_functions_timeout_raised():
    src = (ROOT / "core/database.py").read_text()
    assert "function_client_timeout=60" in src
