"""R39: Android app general web parity - KPI drill-down contract (qcms_kpi_drilldown), module infographic groups
(qcms_module_kpis), custom dashboards (qcms_user_dashboards), R36b inventory reports, global search exact-record opening,
"+" quick actions and the web route parity matrix (static checks of the Java sources and mobile/ANDROID_WEB_PARITY.md)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile/android_qcms_app/app/src/main/java/com/fourstar/qcmsapp"
NEW_FILES = ("KpiModules.java", "GenDashScreen.java", "GenInventoryScreen.java", "GenTarget.java")


def read(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def test_new_files_exist_and_are_registered():
    for name in NEW_FILES:
        assert (SRC / name).exists(), name
    cat = read("CatGeneral.java")
    for key, ctor in (("inventory_reports", "GenInventoryScreen::new"), ("my_dashboards", "GenDashScreen::new"),
                      ("module_kpis", "KpiModules.ModulesScreen::new")):
        assert f'"{key}"' in cat and ctor in cat, key
    centres = read("GenCentres.java")
    assert '{"inventory_reports", "Inventory & Stock Reports"' in centres
    kpi = read("GenKpiScreen.java")
    assert "new KpiModules.ModulesScreen(a)" in kpi and "new GenDashScreen(a)" in kpi


def test_kpi_drilldown_contract_order():
    src = read("KpiDetails.java")
    drill = src.index('"qcms_kpi_drilldown"')
    records = src.index('"qcms_kpi_records"', drill)
    fallback = src.index("fallbackDrill(key)", records)
    assert drill < records < fallback
    assert '.put("p_card_key", key).put("p_limit", 500)' in src
    # R37 card JSON: drill.key / args.p_card_key / open_route
    assert 's(drill, "open_route")' in src and 's(args, "p_card_key")' in src
    assert "GenTarget.open(a, table, id, route, title)" in src


def test_module_kpis_groups_and_permissions():
    src = read("KpiModules.java")
    assert 'RPC = "qcms_module_kpis"' in src and '"p_modules", JSONObject.NULL' in src
    assert "GenUtil.canView(api, moduleKey)" in src
    for dept in ("QUALITY", "SUPPLY_CHAIN", "PRODUCTION", "NPD", "MASTERS"):
        assert f'"{dept}"' in src
    assert 'optJSONArray("spark")' in src and '"entry_route"' in src
    assert "KpiDetails.moduleCard(a, c, dept, onTap)" in src
    details = read("KpiDetails.java")
    assert "KpiModules.fillTab(a, holder, tab, () -> sectionModuleCardsLegacy(a, holder, tab))" in details
    assert '"qcms_module_cards"' in details   # older databases keep the one-card-per-module strip
    home = read("KpiHomeScreen.java")
    assert "KpiModules.fillDepartment(" in home and "moduleCardsLegacy(dept, holder)" in home


def test_custom_dashboards_match_web_builder():
    src = read("GenDashScreen.java")
    assert 'TABLE = "qcms_user_dashboards"' in src
    for key in ("owner_profile_id", "shared_with_tenant", "is_default", "sort_order", "layout", "widgets"):
        assert f'"{key}"' in src, key
    for t in ("kpi", "bar", "line", "area", "pie", "table"):
        assert f'{{"{t}", ' in src, t
    for agg in ("count", "sum", "avg", "min", "max"):
        assert f'{{"{agg}", ' in src, agg
    # every website data source (core/dashboard_builder.DATA_SOURCES) with its View-permission module
    web = (ROOT / "core/dashboard_builder.py").read_text(encoding="utf-8")
    block = web[web.index("DATA_SOURCES"):web.index("def new_widget")]
    for source, module in re.findall(r'"([a-z_]+)": \{"label": "[^"]+", "table": "[a-z_]+", "date": "[a-z_]+", "module": "([A-Z_]+)"', block):
        assert f'new Source("{source}", ' in src and f'"{module}"' in src, source
    assert "GenUtil.canView(api, src.module)" in src
    assert "screen.preset = out" in src


def test_inventory_reports_sources_and_filters():
    src = read("GenInventoryScreen.java")
    for view in ("v_qcms_stock_by_stage", "qcms_stock_by_stage", "v_qcms_rm_stock_by_heat", "v_qcms_forging_stock_by_supplier",
                 "v_qcms_stock_movement_ledger", "v_qsms_osp_register"):
        assert view in src, view
    web = (ROOT / "app_pages/inventory_reports.py").read_text(encoding="utf-8")
    for label, column in re.findall(r'"([A-Za-z /()]+(?: kg| pcs)?)": "([a-z_]+)"', web[web.index("STAGE_COLUMNS"):web.index("STAGE_SEQUENCE")]):
        assert f'{{"{label}", "{column}"}}' in src, label
    for tab in ("Stock by Stage", "RM Stock by Heat", "Forging / OSP Stock", "FG Stock & Dispatch", "Stock Movement Ledger"):
        assert f'"{tab}"' in src
    assert "Running Net kg" in src and '"TOTAL"' in src and "ExportKit.menu(a, doc())" in src
    assert "implements ExportDoc.Source" in src
    assert "rangeDialog" in src and "valuesDialog" in src


def test_search_and_notifications_open_exact_record():
    target = read("GenTarget.java")
    for child, parent in (("inspection_results", "inspection_reports"), ("quality_complaint_actions", "quality_complaints"),
                          ("rmtc_chemistry_results", "rmtc_approvals"), ("npd_order_steps", "npd_orders")):
        assert f'{{"{child}", "{parent}", ' in target, child
    assert '"document_attachments"' in target and '"qcms_delete_requests"' in target
    assert "Catalog.adhoc(table)" in target
    search = read("GenSearchScreen.java")
    assert "GenTarget.open(a, r.table, r.recordId, r.route, r.reference)" in search
    assert "KpiDetails.printRecord(a, r.table, id, r.route)" in search
    notif = read("Notif.java")
    assert "GenTarget.open(a, table, id, route, title)" in notif and "GenTarget.TAB_ROUTES.get(r)" in notif
    for route in ("inventory-reports", "kpi-drilldown", "reference-records", "ecn-register", "ppap-package"):
        assert f'{{"{route}", ' in notif, route


def test_quick_actions_follow_web_quick_add():
    src = read("KpiDetails.java")
    web = (ROOT / "core/quick_add.py").read_text(encoding="utf-8")
    for route in re.findall(r'QuickAction\("New transaction", "[^"]+", "[^"]+", "([a-z\-]+)"', web):
        assert f'"{route}", ' in src, route
    assert "new GenDashScreen(a)" in src and "moduleOf(t)" in src


def test_parity_matrix_lists_every_web_route():
    app = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    routes = re.findall(r'\("([a-z0-9\-]+)", st\.Page\(', app[app.index("PAGE_ITEMS = ("):app.index("PAGES = tuple")])
    doc = (ROOT / "mobile/ANDROID_WEB_PARITY.md").read_text(encoding="utf-8")
    for r in routes:
        assert f"| `{r}` |" in doc, r
    assert re.search(r"\*\*Web routes: %d · native: \d+" % len(routes), doc)


def test_no_service_role_or_secrets_in_new_files():
    for name in NEW_FILES:
        src = read(name).lower()
        assert "service_role" not in src and "smtp_password" not in src, name
