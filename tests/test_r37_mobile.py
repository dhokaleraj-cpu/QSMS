"""R37: Android app v3.5.0 / iOS app v1.2.0 (build 3) - KPI drill-down lists, module cards, "+" quick actions, Print PDF."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AND = ROOT / "mobile/android_qcms_app"
JAVA = AND / "app/src/main/java/com/fourstar/qcmsapp"
IOS = ROOT / "mobile/ios_stawn_qcms"
SWIFT = IOS / "STAWNQCMS"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def balanced(src: str) -> bool:
    return src.count("{") == src.count("}") and src.count("(") == src.count(")")


# ------------------------------------------------------------------ versions
def test_versions():
    gradle = read(AND / "app/build.gradle")
    assert "versionCode 360" in gradle and "versionName '3.6.0'" in gradle
    mp = read(IOS / "make_project.py")
    assert 'else "1.3.0"' in mp and 'else "4"' in mp
    assert 'VERSION="1.3.0"' in read(IOS / "BUILD_STAWN_QCMS_iOS.command")
    core = read(SWIFT / "Core.swift")
    assert '?? "1.3.0"' in core and '?? "4"' in core
    pbx = read(IOS / "STAWNQCMS.xcodeproj/project.pbxproj")
    assert 'MARKETING_VERSION = "1.3.0"' in pbx and 'CURRENT_PROJECT_VERSION = "4"' in pbx
    assert '"QuickActions.swift"' in pbx and 'DEVELOPMENT_TEAM = ""' in pbx
    assert "## v3.5.0 (R37)" in read(AND / "README_ANDROID_APP.md")
    assert "## New in v1.2.0 (build 3, R37)" in read(IOS / "README_IOS.md")


# ------------------------------------------------------------------ Android
def test_android_kpi_records_drilldown():
    k = read(JAVA / "KpiDetails.java")
    assert balanced(k)
    assert '"qcms_kpi_records"' in k and '"p_card_key"' in k and '"p_department"' in k and '"p_limit", 500' in k
    for col in ("source_table", "record_id", "reference", "part", "party", "status", "record_date", "detail"):
        assert f'"{col}"' in k, col
    # row opens the record natively (record screen / module / web fallback through Notif.open)
    assert "Notif.open(a, table, id, route, title)" in k
    # RPC missing / failing -> fall back to the module
    assert "opening the module" in k and "a.back();" in k
    home = read(JAVA / "KpiHomeScreen.java")
    assert "KpiDetails.openCard(a, key," in home and 's(c, "key")' in home
    # pending tasks open their record
    assert 'KpiDetails.tableForModuleKey(mod)' in home and '"related_table"' in home


def test_android_module_cards_strip():
    home = read(JAVA / "KpiHomeScreen.java")
    assert '"qcms_module_cards"' in home and "KpiDetails.moduleStrip(" in home and "MODULE_CACHE" in home
    k = read(JAVA / "KpiDetails.java")
    assert "static View moduleStrip(" in k and "static List<String[]> subFigures(" in k and '"sub_figures"' in k


def test_android_plus_quick_actions():
    main = read(JAVA / "MainActivity.java")
    assert 'barButton("+")' in main and "KpiDetails.quickActions(this)" in main
    k = read(JAVA / "KpiDetails.java")
    assert "New transaction" in k and "New e-mail" in k and "New query" in k and 'openWeb("Search & AI", "global-search")' in main
    assert 'a.newRecord(m.key)' in k and 'Notif.open(a, "", "", t[2], t[0])' in k and 'void openSearchAi()' in main
    assert 'Catalog.get("email_send")' in k and '"email-send"' in k


def test_android_print_pdf_everywhere():
    k = read(JAVA / "KpiDetails.java")
    assert "static void printRecord(" in k and "RptReports.forRecord(api, module, id)" in k and "Catalog.adhoc(table)" in k
    search = read(JAVA / "GenSearchScreen.java")
    assert ".onLongRow(" in search and "KpiDetails.printRecord(a, r.table, id, r.route)" in search
    sheet = read(JAVA / "SheetView.java")
    assert "onLongPress" in sheet and "setOnRowLongClick" in sheet
    assert "public DataGrid onLongRow(" in read(JAVA / "DataGrid.java")
    kit = read(JAVA / "ExportKit.java")
    assert "interface RecordPrint" in kit and "screen instanceof RecordPrint" in kit
    assert "View PDF" in kit and "Download PDF" in kit and "Share PDF" in kit
    for name in ("RecordScreen.java", "AssetDetailScreen.java", "PoDetailScreen.java"):
        assert "implements ExportKit.RecordPrint" in read(JAVA / name), name


# ------------------------------------------------------------------ iOS
def test_ios_kpi_records_and_module_cards():
    q = read(SWIFT / "QuickActions.swift")
    assert balanced(q)
    assert '"qcms_kpi_records"' in q and '"p_card_key"' in q and '"p_department"' in q
    assert "struct KpiRecordsView" in q and "struct ModuleCardsStrip" in q and "static func parse(" in q
    assert "openModule(replace: true)" in q            # RPC missing -> module
    main = read(SWIFT / "MainView.swift")
    assert "case kpiRecords(String, String, String, String)" in main and "KpiRecordsView(key: key" in main
    k = read(SWIFT / "KpiDashboardView.swift")
    assert balanced(k)
    assert '"qcms_module_cards"' in k and "ModuleCardsStrip(cards: modules" in k
    assert 'key: J.str(c["key"])' in k and "QuickActions.openCard(nav: nav" in k
    assert 'relatedTable: J.str(t["related_table"])' in k and "table: t.relatedTable" in k


def test_ios_plus_menu_and_print_pdf():
    q = read(SWIFT / "QuickActions.swift")
    assert "struct QuickAddMenu" in q and "New transaction" in q and "New e-mail" in q and "New query" in q
    assert 'nav.push(.form(t.moduleKey, ""))' in q and '"global-search"' in q and '"email-send"' in q
    assert "enum RecordPdf" in q and "RptReports.forRecord(m, id)" in q and "static func adhoc(table:" in q
    notif = read(SWIFT / "Notifications.swift")
    assert "QuickAddMenu()" in notif
    search = read(SWIFT / "SearchView.swift")
    assert ".contextMenu" in search and "RecordPdf.make(table: r.table, id: r.id)" in search and "PdfViewer(item: $0)" in search
    rec = read(SWIFT / "RecordView.swift")
    assert "Print layout PDF · Preview · Save · Share" in rec and "PdfViewer(item: $0)" in rec


def test_ios_swift_conservative():
    """No Swift 5.9+ only syntax (iOS 16 / Swift 5.7 target)."""
    for name in ("QuickActions.swift", "KpiDashboardView.swift", "SearchView.swift"):
        src = read(SWIFT / name)
        assert "#Preview" not in src and "@Observable" not in src and "if let " not in re.sub(r"if let \w+ = ", "", src), name
        assert not re.search(r"=\s*(if|switch)\s", src), name


def test_android_drill_mapping_and_section_cards():
    k = read(JAVA / "KpiDetails.java")
    assert balanced(k)
    # card "drill" object (table + filter) -> generic PostgREST list; label -> key; client fallback per key
    assert "static void openDrill(" in k and "static String filterQuery(" in k and "static String keyForLabel(" in k
    assert "static String[] fallbackDrill(" in k and "fallbackDrill(key)" in k
    for frag in ('"inward_lots", "status=eq.HOLD_PENDING_INSPECTION"', '"quality_complaints", "status=not.in.(CLOSED,CANCELLED)"',
                 '"metlab pending", "metlab_pending"', '"complaints open", "complaints_open"', '"calibration overdue", "calibration_overdue"'):
        assert frag in k, frag
    home = read(JAVA / "KpiHomeScreen.java")
    assert 'c.optJSONObject("drill")' in home and "KpiDetails.openDrill(a, drill" in home and "KpiDetails.keyForLabel(" in home
    # module infographic cards on Supply / Quality / Masters / More
    assert "static void sectionModuleCards(" in k and '"SUPPLY_CHAIN", "PRODUCTION"' in k
    assert "KpiDetails.sectionModuleCards(a, highlights, tab)" in read(JAVA / "SectionScreen.java")
    # "+" New transaction only lists modules with Create permission; New query focuses the search box
    assert 'GenUtil.permissions(api, perm).optBoolean("can_create", false)' in k and "GenSearchScreen.newQuery(a)" in k
    search = read(JAVA / "GenSearchScreen.java")
    assert "implements ExportDoc.Source" in search and "static GenSearchScreen newQuery(" in search and "showSoftInput" in search
    assert "Results PDF · Preview · Download · Share" in search and "ExportKit.showData(a, this, null)" in search


def test_ios_drill_mapping_section_cards_and_search():
    q = read(SWIFT / "QuickActions.swift")
    assert balanced(q)
    assert "static func fallbackDrill(" in q and "static func keyForLabel(" in q and "static func filterQuery(" in q
    assert "nav.push(.kpiDrill(drillTable, drillQuery, title, route))" in q and "KpiRecord.loadDrill(" in q
    assert "static func creatable() async -> Set<String>" in q and '"can_create"' in q and "allowedList" in q
    main = read(SWIFT / "MainView.swift")
    assert balanced(main)
    assert "case kpiDrill(String, String, String, String)" in main and "drillTable: table, drillQuery: query" in main
    assert '"qcms_module_cards"' in main and "ModuleCardsStrip(cards: modules" in main and "QuickActions.departments(tab: tab)" in main
    k = read(SWIFT / "KpiDashboardView.swift")
    assert 'J.obj(c["drill"])' in k and "QuickActions.keyForLabel(c.label)" in k
    search = read(SWIFT / "SearchView.swift")
    assert balanced(search)
    assert "@FocusState private var focused: Bool" in search and ".focused($focused)" in search
    assert "resultsPdf()" in search and "RptReports.register(" in search and ".swipeActions(edge: .trailing)" in search
    for name in ("MainView.swift",):
        src = read(SWIFT / name)
        assert "#Preview" not in src and "@Observable" not in src and not re.search(r"=\s*(if|switch)\s", src), name


def test_no_secrets_in_apps():
    q = read(SWIFT / "QuickActions.swift") + read(JAVA / "KpiDetails.java")
    assert "service_role" not in q
