from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RECORD_ROUTES = {
    "records-center", "heat-ledger", "rmtc-records", "inward-records", "osp-records",
    "dimensional-records", "metlab-records", "inspection-layout-records",
    "complaint-records", "qc-calculation-records", "part-records", "process-records",
    "grade-records", "reference-records", "employee-records", "standards-records",
}


def _module_submenus() -> dict:
    tree = ast.parse((ROOT / "streamlit_app.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "MODULE_SUBMENUS" for t in node.targets):
                return ast.literal_eval(node.value)
    raise AssertionError("MODULE_SUBMENUS was not found")


def test_release_version():
    assert (ROOT / "VERSION").read_text().strip() == "4.11.0"
    assert (ROOT / "docs/RELEASE_4_11_0.md").exists()


def test_every_record_route_lives_only_under_records_menu():
    menus = _module_submenus()
    records_paths = {item[0] for item in menus["Records"]}
    assert records_paths == RECORD_ROUTES
    for module, items in menus.items():
        if module == "Records":
            continue
        leaked = RECORD_ROUTES.intersection({item[0] for item in items})
        assert not leaked, f"{module} still contains record routes: {sorted(leaked)}"


def test_record_routes_activate_records_top_level_module():
    app = (ROOT / "streamlit_app.py").read_text()
    assert "RECORD_ROUTES = {" in app
    assert '**{path: "Records" for path in RECORD_ROUTES}' in app
    assert 'module_submenu(current_module, *MODULE_SUBMENUS[current_module], max_columns=8)' in app


def test_minimal_metallic_ui_contract():
    ui = (ROOT / "core/ui.py").read_text()
    auth = (ROOT / "core/auth.py").read_text()
    config = (ROOT / ".streamlit/config.toml").read_text()
    for token in (
        "QCMS 4.11.0 — minimal metallic enterprise UX",
        "--qcms-metal-bg:#F1F3F5",
        "--qcms-metal-steel:#315F79",
        "fsi-top-menu-title{display:none!important;}",
        "BUILD 4110-MINIMAL-RECORDS-UX",
    ):
        assert token in ui
    assert "4110-MINIMAL-RECORDS-UX" in auth
    assert 'backgroundColor = "#F1F3F5"' in config
    assert 'primaryColor = "#315F79"' in config
