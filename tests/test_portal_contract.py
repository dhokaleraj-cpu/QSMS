from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def test_portal_contract_uses_common_company_stack():
    contract = json.loads((ROOT / "portal/portal_contract.json").read_text())
    assert contract["app_id"] == "qsms"
    assert contract["technology"] == {"language": "Python", "web_framework": "Streamlit", "database_and_auth": "Supabase", "source_control": "GitHub", "developer_workspace": "VS Code"}
    assert contract["routes"]["local"] == "http://localhost:8510"
    assert contract["phase_1_scope"] == ["Dashboard", "Masters", "RMTC Entry", "Material Inward", "Inspection Layouts", "Dimensional Report", "MetLAB Report"]
