"""R12: Design 07 Teal Material theme, faster reruns, AI key setup helper."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_teal_theme_is_applied_last_and_renders():
    ui = (ROOT / "core/ui.py").read_text()
    assert "apply_teal_material_theme()" in ui and "TEAL MATERIAL" in ui and "#0F8B8D" in ui
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string("from core.ui import apply_global_style\napply_global_style()").run()
    assert not app.exception
    assert any("--tm-primary:#0F8B8D" in str(m.value) for m in app.markdown)
    config = (ROOT / ".streamlit/config.toml").read_text()
    assert 'primaryColor = "#0F8B8D"' in config and 'backgroundColor = "#F1F6F6"' in config


def test_repository_reuses_reads_and_clears_after_write():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
import streamlit as st
from core.repository import Repository
class Resp:
    def __init__(self, data): self.data = data
class Query:
    def __init__(self, log, table): self.log = log; self.table = table
    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def order(self, *a, **k): return self
    def insert(self, row): self.row = row; return self
    def execute(self):
        self.log.append(self.table)
        return Resp([getattr(self, "row", {"id": "1", "n": len(self.log)})])
class Client:
    def __init__(self): self.log = []
    def table(self, name): return Query(self.log, name)
repo = Repository.__new__(Repository)
repo.preview = False; repo.client = Client(); repo.tenant_id = ""
repo.select("parts"); repo.select("parts")
st.session_state["after_two_reads"] = list(repo.client.log)
repo.insert("parts", {"id": "2"})
repo.select("parts")
repo.select("parts", require_live=True)
st.session_state["final"] = list(repo.client.log)
''').run()
    assert not app.exception
    assert app.session_state["after_two_reads"] == ["parts"]           # second read served from cache
    assert app.session_state["final"] == ["parts", "parts", "parts", "parts"]  # write cleared cache; require_live bypasses


def test_export_memo_reuses_bytes_inside_streamlit_only():
    from core.export_cache import session_memo_bytes
    calls = []
    @session_memo_bytes
    def build(x):
        calls.append(x); return b"pdf" + bytes([x])
    assert build(1) == build(1) and calls == [1, 1]   # outside Streamlit: never cached
    from core import reporting
    assert hasattr(reporting.metlab_record_pdf_bytes, "__wrapped_uncached__")


def test_activity_logging_is_background_and_employee_link_memoised():
    activity = (ROOT / "core/activity.py").read_text()
    assert "_submit_background(" in activity and "ThreadPoolExecutor" in activity
    auth = (ROOT / "core/auth.py").read_text()
    assert "_qcms_employee_link_memo" in auth


def test_duplicate_checks_use_live_reads():
    assert 'repo.select("parts", limit=10000, require_live=True)' in (ROOT / "app_pages/part_master.py").read_text()
    assert "self.repo.select(table, limit=10000, require_live=True)" in (ROOT / "core/supply_chain_service.py").read_text()


def test_ai_key_script_writes_top_level_keys(tmp_path):
    (tmp_path / "scripts").mkdir(); (tmp_path / ".streamlit").mkdir()
    script = tmp_path / "scripts/set_ai_key.sh"
    script.write_text((ROOT / "scripts/set_ai_key.sh").read_text())
    secrets = tmp_path / ".streamlit/secrets.toml"
    secrets.write_text('[supabase]\nSUPABASE_URL = "x"\nANTHROPIC_API_KEY = "old"\n')
    result = subprocess.run(["bash", str(script)], input="sk-ant-abc123\n", text=True, capture_output=True, env={"QCMS_SKIP_KEY_CHECK": "1", "PATH": "/usr/bin:/bin"})
    assert result.returncode == 0, result.stdout + result.stderr
    import tomllib
    data = tomllib.loads(secrets.read_text())
    assert data["ANTHROPIC_API_KEY"] == "sk-ant-abc123" and data["supabase"] == {"SUPABASE_URL": "x"}
    bad = subprocess.run(["bash", str(script)], input="hello\n", text=True, capture_output=True, env={"QCMS_SKIP_KEY_CHECK": "1", "PATH": "/usr/bin:/bin"})
    assert bad.returncode != 0
