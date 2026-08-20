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
    assert (ROOT / "VERSION").read_text().strip() in {"4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6"}
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
    # QCMS 4.11.1 supersedes the 4.11.0 metallic layer with a higher-contrast
    # white/blue shell while retaining the same compact ERP density.
    ui = (ROOT / "core/ui.py").read_text()
    auth = (ROOT / "core/auth.py").read_text()
    config = (ROOT / ".streamlit/config.toml").read_text()
    for token in (
        "QCMS 4.11.1 — Zoho-inspired clean white/blue enterprise shell visibility layer.",
        "--qcms-zoho-blue:#1884D8",
        "fsi-top-menu-title{display:none!important;}",
        "BUILD 4111-ZOHO-VISIBLE-SHELL",
        "color:#17202A!important",
        "color:#202A33!important",
    ):
        assert token in ui
    assert "4111-ZOHO-VISIBLE-SHELL" in auth
    assert 'backgroundColor = "#F8FBFE"' in config or 'backgroundColor = "#EFEFEF"' in config
    assert 'primaryColor = "#1884D8"' in config
