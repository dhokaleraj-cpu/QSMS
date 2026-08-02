from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
required = [
    "streamlit_app.py",
    "requirements.txt",
    ".streamlit/config.toml",
    ".streamlit/secrets.toml.example",
    ".github/workflows/quality-checks.yml",
    "portal/app_registry.toml",
    "portal/portal_contract.json",
    "supabase/config.toml",
    "supabase/migrations/20260802043000_qsms_focused_v430.sql",
    "supabase/migrations/20260802043100_qsms_multi_part_rmtc.sql",
    "supabase/migrations/20260802043200_qsms_not_applicable.sql",
    "supabase/migrations/20260802065000_qsms_inspection_workflow_v460.sql",
    "supabase/migrations/20260802065100_qsms_inspection_delete_and_sequences_v460.sql",
    "supabase/migrations/20260802090000_qsms_rmtc_reliability_v472.sql",
    "supabase/migrations/20260802112000_qsms_rmtc_workflow_admin_v473.sql",
    "supabase/migrations/20260802133000_qsms_steel_production_layout_v480.sql",
    "supabase/migrations/20260802133100_qsms_steel_production_allocation_guard_v480.sql",
    "supabase/migrations/20260802150000_qsms_heat_production_microstructure_v481.sql",
    "supabase/migrations/20260802172000_qsms_heat_search_global_steel_v483.sql",
    "supabase/migrations/20260802193000_qsms_unified_records_v484.sql",
    "supabase/migrations/20260802201500_qsms_combined_heat_balance_v485.sql",
    "app_pages/records_center.py",
    "tests/test_v484_unified_records.py",
    "tests/test_v485_combined_heat_balance.py",
    "supabase/migrations/20260802213000_qsms_heat_supplier_rmtc_ledger_v486.sql",
    "tests/test_v486_heat_supplier_rmtc_ledger.py",
    "core/steel_balance.py",
    "tests/test_v483_heat_search_global_steel.py",
    "tests/test_v481_heat_production_microstructure.py",
    "templates/RMTC_Entry_Template.xlsx",
    "templates/Material_Inward_Template.xlsx",
    "templates/MetLAB_Report_Layout_Template.xlsx",
    "app_pages/inspection_layouts.py",
    "app_pages/dimensional_report.py",
    "app_pages/metlab_report.py",
    "data/Dimensional Report.xlsx",
]
missing = [path for path in required if not (ROOT / path).exists()]
secrets = ROOT / ".streamlit" / "secrets.toml"
report = {
    "phase": "QSMS 4.8.6 - Supplier RMTC Identity and Heat Steel Ledger",
    "required_files": len(required),
    "missing": missing,
    "local_secrets_present": secrets.exists(),
    "project_ref_configured": "xxrxopzxzyjnzumrwuwy" in (ROOT / "supabase" / "config.toml").read_text(encoding="utf-8"),
    "portal_contract_present": (ROOT / "portal" / "portal_contract.json").exists(),
}
print(json.dumps(report, indent=2))
raise SystemExit(1 if missing else 0)
